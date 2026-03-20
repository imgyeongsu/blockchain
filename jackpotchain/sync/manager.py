"""
Step 9-10: 동기화 관리
- Initial Block Download (IBD)
- 헤더 우선 동기화 (Header-First Sync)
"""

import asyncio
import time
from typing import Optional, List, Set
from dataclasses import dataclass
from enum import Enum

from ..consensus.chain import Blockchain, ChainState
from ..consensus.difficulty import get_next_difficulty
from ..core.block import Block, BlockHeader
from ..network.peer import PeerInfo, PeerManager
from ..validation.block import validate_block
from ..constants import MAX_HEADERS_SIZE


class SyncState(Enum):
    """동기화 상태"""
    IDLE = "idle"
    HEADERS = "headers"        # 헤더 동기화 중
    BLOCKS = "blocks"          # 블록 다운로드 중
    SYNCED = "synced"          # 동기화 완료


@dataclass
class SyncStats:
    """동기화 통계"""
    state: SyncState
    local_height: int
    best_known_height: int
    headers_synced: int
    blocks_downloaded: int
    blocks_per_second: float
    eta_seconds: float


class SyncManager:
    """
    블록체인 동기화 관리자 (Header-First)

    전략:
    1. 헤더 우선 다운로드 + PoW 검증
    2. 검증된 헤더의 블록 본문 병렬 다운로드
    3. 검증 후 체인에 추가
    """

    # 상태 상수 (외부에서 SyncState import 없이 접근용)
    IDLE = SyncState.IDLE
    HEADERS = SyncState.HEADERS
    BLOCKS = SyncState.BLOCKS
    SYNCED = SyncState.SYNCED

    # 동시 블록 요청 제한
    BATCH_SIZE = 16
    # 동기화 타임아웃 (초) - 응답 없으면 상태 초기화
    SYNC_TIMEOUT = 120

    def __init__(
        self,
        blockchain: Blockchain,
        peer_manager: PeerManager
    ):
        self.blockchain = blockchain
        self.peer_manager = peer_manager

        # 상태
        self.state = SyncState.IDLE
        self._best_known_height = 0

        # 다운로드 대기열
        self._headers_to_fetch: List[bytes] = []
        self._blocks_to_fetch: Set[bytes] = set()
        self._downloading: Set[bytes] = set()

        # 타임아웃 추적
        self._last_activity: float = 0

        # 통계
        self._blocks_downloaded = 0
        self._download_start_time = 0

        # 콜백
        self._request_headers_callback = None
        self._request_blocks_callback = None

    def set_callbacks(self, request_headers, request_blocks):
        """콜백 설정"""
        self._request_headers_callback = request_headers
        self._request_blocks_callback = request_blocks

    def update_peer_height(self, peer: PeerInfo, height: int):
        """피어 높이 업데이트"""
        if height > self._best_known_height:
            self._best_known_height = height

    def needs_sync(self) -> bool:
        """동기화 필요 여부"""
        return self.blockchain.get_height() < self._best_known_height

    def _check_timeout(self) -> bool:
        """타임아웃 체크. 타임아웃이면 상태 초기화 후 True 반환"""
        if self._last_activity > 0 and time.time() - self._last_activity > self.SYNC_TIMEOUT:
            print(f"[SYNC] 동기화 타임아웃 ({self.SYNC_TIMEOUT}s), 상태 초기화 (높이: {self.blockchain.get_height()})")
            self.reset()
            return True
        return False

    def reset(self):
        """동기화 상태 초기화"""
        self.state = SyncState.IDLE
        self._headers_to_fetch.clear()
        self._blocks_to_fetch.clear()
        self._downloading.clear()
        self._last_activity = 0

    async def start_sync(self):
        """동기화 시작"""
        if not self.needs_sync():
            self.state = SyncState.SYNCED
            return

        self.state = SyncState.HEADERS
        self._download_start_time = time.time()
        self._last_activity = time.time()
        self._blocks_downloaded = 0

        # 헤더 요청
        await self._request_headers()

    async def _request_headers(self):
        """헤더 요청"""
        if self._request_headers_callback:
            locator = self._build_block_locator()
            await self._request_headers_callback(locator)

    def _build_block_locator(self) -> List[bytes]:
        """블록 로케이터 생성 (지수 간격)"""
        locator = []
        height = self.blockchain.get_height()
        step = 1

        while height >= 0:
            block = self.blockchain.get_block_by_height(height)
            if block:
                locator.append(block.get_hash())

            if len(locator) >= 10:
                step *= 2

            height -= step

            if len(locator) >= 100:
                break

        # Genesis 추가
        genesis = self.blockchain.get_block_by_height(0)
        if genesis and genesis.get_hash() not in locator:
            locator.append(genesis.get_hash())

        return locator

    async def on_headers_received(self, address, headers: List):
        """헤더 수신 — PoW 검증 후 다운로드 큐에 추가"""
        if self.state != SyncState.HEADERS:
            return

        self._last_activity = time.time()

        for header_bytes in headers:
            try:
                header, _ = BlockHeader.deserialize(header_bytes)
                header_hash = header.get_hash()

                # 이미 있는 블록이면 스킵
                if self.blockchain.has_block(header_hash):
                    continue

                # PoW 검증 — 실패 시 본문 다운로드 없이 폐기 (대역폭 절약)
                if not header.verify_pow():
                    continue

                # 다운로드 큐에 추가 (Set으로 중복 방지)
                self._blocks_to_fetch.add(header_hash)
                # 순서 보장용 리스트
                self._headers_to_fetch.append(header_hash)

            except Exception:
                pass

        if len(headers) < MAX_HEADERS_SIZE:
            # 헤더 동기화 완료 → 블록 다운로드 단계
            self.state = SyncState.BLOCKS
            print(f"[SYNC] 헤더 동기화 완료, 블록 {len(self._blocks_to_fetch)}개 다운로드 시작")
            await self._request_blocks()
        else:
            # 추가 헤더 요청
            await self._request_headers()

    async def _request_blocks(self):
        """블록 요청 (배치)"""
        if not self._blocks_to_fetch and not self._downloading:
            # 블록 동기화 완료
            self.state = SyncState.SYNCED
            self.blockchain.state = ChainState.SYNCED
            print(f"[SYNC] 동기화 완료! 현재 높이: {self.blockchain.get_height()}")
            return

        if self._request_blocks_callback:
            to_request = []
            for block_hash in list(self._blocks_to_fetch):
                if block_hash not in self._downloading:
                    to_request.append(block_hash)
                    self._downloading.add(block_hash)
                    if len(to_request) >= self.BATCH_SIZE:
                        break

            if to_request:
                await self._request_blocks_callback(to_request)

    async def on_block_received(self, block: Block, peer: PeerInfo):
        """블록 수신 — 검증 후 체인에 추가"""
        block_hash = block.get_hash()

        # 다운로드 목록에서 제거
        self._downloading.discard(block_hash)
        self._blocks_to_fetch.discard(block_hash)
        self._last_activity = time.time()

        # 이전 블록 헤더 및 예상 난이도
        prev_block = self.blockchain.get_tip()
        prev_header = prev_block.header if prev_block else None
        expected_difficulty = get_next_difficulty(
            self.blockchain.get_height(),
            self.blockchain.get_block_by_height
        )

        # 검증
        result = validate_block(
            block,
            self.blockchain.utxo_set,
            self.blockchain.get_height() + 1,
            prev_header=prev_header,
            expected_difficulty=expected_difficulty,
            blockchain=self.blockchain
        )

        if result.is_valid:
            success, _ = self.blockchain.add_block(block)
            if success:
                self._blocks_downloaded += 1
        else:
            # 잘못된 블록 — 피어 밴 점수 추가
            self.peer_manager.add_ban_score(peer.address, 20)

        # 추가 블록 요청
        if self.state == SyncState.BLOCKS:
            await self._request_blocks()

    def get_stats(self) -> SyncStats:
        """동기화 통계"""
        elapsed = time.time() - self._download_start_time if self._download_start_time else 0
        bps = self._blocks_downloaded / elapsed if elapsed > 0 else 0

        remaining = self._best_known_height - self.blockchain.get_height()
        eta = remaining / bps if bps > 0 else float('inf')

        return SyncStats(
            state=self.state,
            local_height=self.blockchain.get_height(),
            best_known_height=self._best_known_height,
            headers_synced=len(self._headers_to_fetch),
            blocks_downloaded=self._blocks_downloaded,
            blocks_per_second=bps,
            eta_seconds=eta
        )

    def is_synced(self) -> bool:
        """동기화 완료 여부"""
        return self.state == SyncState.SYNCED
