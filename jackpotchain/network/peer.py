"""
Step 8.2: 피어 관리
- 피어 연결 상태
- 피어 풀 관리
"""

import time
import asyncio
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from ..constants import MAX_OUTBOUND_CONNECTIONS, MAX_INBOUND_CONNECTIONS


class PeerState(Enum):
    """피어 상태"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    HANDSHAKING = "handshaking"
    READY = "ready"
    BANNED = "banned"


@dataclass
class PeerAddress:
    """피어 주소"""
    ip: str
    port: int
    services: int = 1
    timestamp: int = 0

    def __hash__(self):
        return hash((self.ip, self.port))

    def __eq__(self, other):
        if isinstance(other, PeerAddress):
            return self.ip == other.ip and self.port == other.port
        return False

    def __str__(self):
        return f"{self.ip}:{self.port}"


@dataclass
class PeerInfo:
    """피어 정보"""
    address: PeerAddress
    state: PeerState = PeerState.DISCONNECTED
    version: int = 0
    user_agent: str = ""
    start_height: int = 0
    services: int = 0
    is_inbound: bool = False

    # 통계
    connected_at: float = 0
    last_seen: float = 0
    last_send: float = 0
    last_recv: float = 0
    bytes_sent: int = 0
    bytes_recv: int = 0
    ping_time: float = 0

    # 동기화
    best_height: int = 0
    synced_headers: int = 0

    # Ban 정보
    ban_score: int = 0
    ban_until: float = 0


class PeerManager:
    """
    피어 매니저

    - 연결 관리
    - 피어 발견
    - Ban 관리
    """

    def __init__(
        self,
        max_outbound: int = MAX_OUTBOUND_CONNECTIONS,
        max_inbound: int = MAX_INBOUND_CONNECTIONS
    ):
        self.max_outbound = max_outbound
        self.max_inbound = max_inbound

        # 연결된 피어
        self._peers: Dict[PeerAddress, PeerInfo] = {}

        # 알려진 피어 주소
        self._known_addresses: Set[PeerAddress] = set()

        # 시드 노드
        self._seed_nodes: List[PeerAddress] = []

        # Ban 목록
        self._banned: Dict[str, float] = {}  # ip -> ban_until

        # 통계
        self._total_connections = 0
        self._failed_connections = 0

    def add_seed_nodes(self, seeds: List[tuple]):
        """시드 노드 추가"""
        for ip, port in seeds:
            self._seed_nodes.append(PeerAddress(ip, port))
            self._known_addresses.add(PeerAddress(ip, port))

    def add_peer_address(self, address: PeerAddress):
        """피어 주소 추가"""
        if not self.is_banned(address.ip):
            self._known_addresses.add(address)

    def get_peer(self, address: PeerAddress) -> Optional[PeerInfo]:
        """피어 정보 조회"""
        return self._peers.get(address)

    def get_connected_peers(self) -> List[PeerInfo]:
        """연결된 피어 목록"""
        return [p for p in self._peers.values() if p.state == PeerState.READY]

    def get_outbound_count(self) -> int:
        """아웃바운드 연결 수"""
        return sum(1 for p in self._peers.values()
                   if not p.is_inbound and p.state != PeerState.DISCONNECTED)

    def get_inbound_count(self) -> int:
        """인바운드 연결 수"""
        return sum(1 for p in self._peers.values()
                   if p.is_inbound and p.state != PeerState.DISCONNECTED)

    def can_connect_outbound(self) -> bool:
        """아웃바운드 연결 가능 여부"""
        return self.get_outbound_count() < self.max_outbound

    def can_accept_inbound(self) -> bool:
        """인바운드 연결 수용 가능 여부"""
        return self.get_inbound_count() < self.max_inbound

    def add_peer(self, address: PeerAddress, is_inbound: bool = False) -> Optional[PeerInfo]:
        """피어 추가"""
        if self.is_banned(address.ip):
            return None

        if is_inbound and not self.can_accept_inbound():
            return None
        if not is_inbound and not self.can_connect_outbound():
            return None

        if address in self._peers:
            return self._peers[address]

        peer = PeerInfo(
            address=address,
            state=PeerState.CONNECTING,
            is_inbound=is_inbound,
            connected_at=time.time()
        )
        self._peers[address] = peer
        self._total_connections += 1

        return peer

    def update_peer_state(self, address: PeerAddress, state: PeerState):
        """피어 상태 업데이트"""
        if address in self._peers:
            self._peers[address].state = state
            if state == PeerState.DISCONNECTED:
                self._failed_connections += 1

    def remove_peer(self, address: PeerAddress):
        """피어 제거"""
        if address in self._peers:
            del self._peers[address]

    def update_peer_height(self, address: PeerAddress, height: int):
        """피어 높이 업데이트"""
        if address in self._peers:
            self._peers[address].best_height = height

    def update_peer_version(self, address: PeerAddress, version_msg):
        """핸드셰이크 정보 업데이트"""
        if address in self._peers:
            peer = self._peers[address]
            peer.version = version_msg.version
            peer.user_agent = version_msg.user_agent.decode('utf-8', errors='ignore')
            peer.start_height = version_msg.start_height
            peer.services = version_msg.services

    def ban_peer(self, ip: str, duration: float = 86400):
        """피어 밴 (기본 24시간)"""
        self._banned[ip] = time.time() + duration

        # 해당 IP의 모든 연결 제거
        to_remove = [addr for addr in self._peers if addr.ip == ip]
        for addr in to_remove:
            self.remove_peer(addr)

    def is_banned(self, ip: str) -> bool:
        """밴 여부 확인"""
        if ip in self._banned:
            if time.time() < self._banned[ip]:
                return True
            else:
                del self._banned[ip]
        return False

    def add_ban_score(self, address: PeerAddress, score: int, threshold: int = 100):
        """밴 점수 추가"""
        if address in self._peers:
            self._peers[address].ban_score += score
            if self._peers[address].ban_score >= threshold:
                self.ban_peer(address.ip)
                return True
        return False

    def get_peers_to_connect(self, count: int = 1) -> List[PeerAddress]:
        """연결할 피어 목록 반환"""
        connected = set(self._peers.keys())
        banned_ips = set(self._banned.keys())

        candidates = [
            addr for addr in self._known_addresses
            if addr not in connected and addr.ip not in banned_ips
        ]

        # 시드 노드 우선
        seeds = [addr for addr in candidates if addr in self._seed_nodes]
        others = [addr for addr in candidates if addr not in self._seed_nodes]

        return (seeds + others)[:count]

    def get_best_peer(self) -> Optional[PeerInfo]:
        """가장 높은 체인을 가진 피어"""
        ready_peers = self.get_connected_peers()
        if not ready_peers:
            return None
        return max(ready_peers, key=lambda p: p.best_height)

    def get_stats(self) -> dict:
        """통계"""
        return {
            'connected': len([p for p in self._peers.values() if p.state != PeerState.DISCONNECTED]),
            'outbound': self.get_outbound_count(),
            'inbound': self.get_inbound_count(),
            'known_addresses': len(self._known_addresses),
            'banned': len(self._banned),
            'total_connections': self._total_connections,
            'failed_connections': self._failed_connections,
        }

    def get_addr_to_send(self, count: int = 1000) -> List[PeerAddress]:
        """ADDR 메시지용 주소 목록"""
        # 최근에 본 주소 우선
        addresses = list(self._known_addresses)
        addresses.sort(key=lambda a: a.timestamp, reverse=True)
        return addresses[:count]
