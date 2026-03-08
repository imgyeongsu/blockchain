"""
피어 발견 (Peer Discovery)

- DNS 시드 조회
- 하드코딩된 시드 노드
- 피어 주소 캐시 (peers.json)
"""

import os
import json
import time
import socket
import asyncio
import logging
from typing import List, Optional, Set
from dataclasses import dataclass, asdict
from pathlib import Path

from .peer import PeerAddress
from ..constants import DEFAULT_PORT

logger = logging.getLogger(__name__)


# =============================================================================
# 시드 노드 설정
# =============================================================================

# DNS 시드 (실제 운영 시 도메인 등록 필요)
DNS_SEEDS = [
    "seed1.jackpotchain.io",
    "seed2.jackpotchain.io",
    "seed3.jackpotchain.io",
]

# 하드코딩된 시드 노드 (DNS 실패 시 fallback)
HARDCODED_SEEDS = [
    ("127.0.0.1", DEFAULT_PORT),  # 로컬 테스트용
    # 실제 운영 시 공개 노드 IP 추가
    # ("203.0.113.1", DEFAULT_PORT),
    # ("203.0.113.2", DEFAULT_PORT),
]


@dataclass
class CachedPeer:
    """캐시된 피어 정보"""
    ip: str
    port: int
    services: int = 1
    last_seen: int = 0
    last_try: int = 0
    attempts: int = 0
    success: int = 0

    def to_peer_address(self) -> PeerAddress:
        return PeerAddress(
            ip=self.ip,
            port=self.port,
            services=self.services,
            timestamp=self.last_seen
        )


class PeerCache:
    """
    피어 주소 캐시

    peers.json에 저장/로드하여 재시작 시 빠른 연결 지원
    """

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.expanduser("~/.jackpotchain")
        self.data_dir = Path(data_dir)
        self.cache_file = self.data_dir / "peers.json"
        self._peers: dict[str, CachedPeer] = {}  # key: "ip:port"
        self._max_peers = 2000  # 최대 캐시 수

    def _key(self, ip: str, port: int) -> str:
        return f"{ip}:{port}"

    def load(self) -> int:
        """캐시 파일 로드"""
        if not self.cache_file.exists():
            return 0

        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)

            for entry in data.get('peers', []):
                peer = CachedPeer(**entry)
                key = self._key(peer.ip, peer.port)
                self._peers[key] = peer

            logger.info(f"Loaded {len(self._peers)} peers from cache")
            return len(self._peers)
        except Exception as e:
            logger.warning(f"Failed to load peer cache: {e}")
            return 0

    def save(self):
        """캐시 파일 저장"""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)

            # 최근에 본 순으로 정렬하여 상위 N개만 저장
            sorted_peers = sorted(
                self._peers.values(),
                key=lambda p: p.last_seen,
                reverse=True
            )[:self._max_peers]

            data = {
                'version': 1,
                'updated': int(time.time()),
                'peers': [asdict(p) for p in sorted_peers]
            }

            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved {len(sorted_peers)} peers to cache")
        except Exception as e:
            logger.warning(f"Failed to save peer cache: {e}")

    def add(self, ip: str, port: int, services: int = 1, timestamp: int = 0):
        """피어 추가"""
        key = self._key(ip, port)
        if key in self._peers:
            # 기존 피어 업데이트
            peer = self._peers[key]
            peer.services = services
            if timestamp > peer.last_seen:
                peer.last_seen = timestamp
        else:
            self._peers[key] = CachedPeer(
                ip=ip,
                port=port,
                services=services,
                last_seen=timestamp or int(time.time())
            )

    def add_from_peer_address(self, addr: PeerAddress):
        """PeerAddress에서 추가"""
        self.add(addr.ip, addr.port, addr.services, addr.timestamp)

    def mark_attempt(self, ip: str, port: int):
        """연결 시도 기록"""
        key = self._key(ip, port)
        if key in self._peers:
            self._peers[key].last_try = int(time.time())
            self._peers[key].attempts += 1

    def mark_success(self, ip: str, port: int):
        """연결 성공 기록"""
        key = self._key(ip, port)
        if key in self._peers:
            self._peers[key].last_seen = int(time.time())
            self._peers[key].success += 1

    def remove(self, ip: str, port: int):
        """피어 제거"""
        key = self._key(ip, port)
        self._peers.pop(key, None)

    def get_peers(self, count: int = 100, exclude: Set[str] = None) -> List[PeerAddress]:
        """
        연결할 피어 목록 반환

        우선순위:
        1. 성공률 높은 순
        2. 최근에 본 순
        """
        exclude = exclude or set()
        candidates = [
            p for k, p in self._peers.items()
            if k not in exclude
        ]

        # 정렬: 성공률 > 최근 연결
        def score(p: CachedPeer) -> tuple:
            success_rate = p.success / max(p.attempts, 1)
            return (success_rate, p.last_seen)

        candidates.sort(key=score, reverse=True)
        return [p.to_peer_address() for p in candidates[:count]]

    def get_recent_peers(self, max_age: int = 3 * 24 * 3600) -> List[PeerAddress]:
        """최근 N초 이내에 본 피어"""
        cutoff = int(time.time()) - max_age
        return [
            p.to_peer_address()
            for p in self._peers.values()
            if p.last_seen > cutoff
        ]

    def __len__(self) -> int:
        return len(self._peers)


class PeerDiscovery:
    """
    피어 발견 매니저

    1. 시작 시 캐시 로드
    2. DNS 시드 조회
    3. 하드코딩 시드 fallback
    4. ADDR 메시지로 피어 수집
    """

    def __init__(self, data_dir: str = None):
        self.cache = PeerCache(data_dir)
        self._dns_seeds = list(DNS_SEEDS)
        self._hardcoded_seeds = list(HARDCODED_SEEDS)

    def initialize(self) -> List[PeerAddress]:
        """
        초기화 및 부트스트랩

        Returns:
            초기 연결 시도할 피어 목록
        """
        # 1. 캐시 로드
        cached_count = self.cache.load()

        # 2. 캐시에 충분한 피어가 있으면 사용
        if cached_count >= 10:
            peers = self.cache.get_peers(count=20)
            logger.info(f"Using {len(peers)} cached peers")
            return peers

        # 3. 캐시 부족 시 시드 조회
        seed_peers = self._query_seeds()

        # 4. 캐시에 추가
        for addr in seed_peers:
            self.cache.add_from_peer_address(addr)

        return seed_peers

    def _query_seeds(self) -> List[PeerAddress]:
        """시드 노드 조회"""
        peers = []

        # DNS 시드 조회
        for seed in self._dns_seeds:
            try:
                ips = self._resolve_dns(seed)
                for ip in ips:
                    peers.append(PeerAddress(ip=ip, port=DEFAULT_PORT))
                logger.info(f"DNS seed {seed}: {len(ips)} addresses")
            except Exception as e:
                logger.debug(f"DNS seed {seed} failed: {e}")

        # 하드코딩 시드 추가
        for ip, port in self._hardcoded_seeds:
            addr = PeerAddress(ip=ip, port=port)
            if addr not in peers:
                peers.append(addr)

        logger.info(f"Total seed peers: {len(peers)}")
        return peers

    def _resolve_dns(self, hostname: str) -> List[str]:
        """DNS 조회"""
        try:
            # A 레코드 조회
            result = socket.getaddrinfo(hostname, None, socket.AF_INET)
            ips = list(set(r[4][0] for r in result))
            return ips
        except socket.gaierror:
            return []

    async def query_seeds_async(self) -> List[PeerAddress]:
        """비동기 시드 조회"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._query_seeds)

    def add_addresses(self, addresses: List[PeerAddress]):
        """ADDR 메시지에서 받은 주소 추가"""
        for addr in addresses:
            # 기본 검증
            if self._is_valid_address(addr):
                self.cache.add_from_peer_address(addr)

    def _is_valid_address(self, addr: PeerAddress) -> bool:
        """주소 유효성 검사"""
        # 사설 IP 제외 (테스트 시에는 허용)
        # if self._is_private_ip(addr.ip):
        #     return False

        # 포트 범위 확인
        if not (1 <= addr.port <= 65535):
            return False

        return True

    def _is_private_ip(self, ip: str) -> bool:
        """사설 IP 확인"""
        parts = ip.split('.')
        if len(parts) != 4:
            return True
        try:
            a, b = int(parts[0]), int(parts[1])
            if a == 10:
                return True
            if a == 172 and 16 <= b <= 31:
                return True
            if a == 192 and b == 168:
                return True
            if a == 127:
                return True
        except ValueError:
            return True
        return False

    def mark_good(self, addr: PeerAddress):
        """연결 성공한 피어 표시"""
        self.cache.mark_success(addr.ip, addr.port)

    def mark_attempt(self, addr: PeerAddress):
        """연결 시도 표시"""
        self.cache.mark_attempt(addr.ip, addr.port)

    def get_peers_to_connect(self, count: int = 8, exclude: Set[str] = None) -> List[PeerAddress]:
        """연결할 피어 목록"""
        return self.cache.get_peers(count, exclude)

    def get_addr_to_send(self, count: int = 1000) -> List[PeerAddress]:
        """ADDR 응답용 주소 목록 (최근 3일 이내)"""
        return self.cache.get_recent_peers(max_age=3 * 24 * 3600)[:count]

    def save(self):
        """캐시 저장"""
        self.cache.save()

    def __len__(self) -> int:
        return len(self.cache)
