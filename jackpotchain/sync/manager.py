"""
Step 9-10: 동기화 관리
- Initial Block Download (IBD)
- 헤더 우선 동기화
"""

import asyncio
import time
from typing import Optional, List, Set
from dataclasses import dataclass
from enum import Enum

from ..consensus.chain import Blockchain, ChainState
from ..core.block import Block
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
    블록체인 동기화 관리자

    전략:
    1. 헤더 우선 다운로드
    2. 병렬 블록 다운로드
    3. 검증 후 체인에 추가
    """

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

    async def start_sync(self):
        """동기화 시작"""
        if not self.needs_sync():
            self.state = SyncState.SYNCED
            return

        self.state = SyncState.HEADERS
        self._download_start_time = time.time()

        # 헤더 요청
        await self._request_headers()

    async def _request_headers(self):
        """헤더 요청"""
        if self._request_headers_callback:
            # 블록 로케이터 생성
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

    async def on_headers_received(self, headers: List):
        """헤더 수신"""
        if self.state != SyncState.HEADERS:
            return

        for header in headers:
            # TODO: 헤더 검증 및 저장
            pass

        if len(headers) < MAX_HEADERS_SIZE:
            # 헤더 동기화 완료
            self.state = SyncState.BLOCKS
            await self._request_blocks()
        else:
            # 추가 헤더 요청
            await self._request_headers()

    async def _request_blocks(self):
        """블록 요청"""
        if not self._blocks_to_fetch and not self._downloading:
            # 블록 동기화 완료
            self.state = SyncState.SYNCED
            self.blockchain.state = ChainState.SYNCED
            return

        if self._request_blocks_callback:
            # 동시 요청 제한
            to_request = []
            for block_hash in self._blocks_to_fetch:
                if block_hash not in self._downloading:
                    to_request.append(block_hash)
                    self._downloading.add(block_hash)
                    if len(to_request) >= 16:
                        break

            if to_request:
                await self._request_blocks_callback(to_request)

    async def on_block_received(self, block: Block, peer: PeerInfo):
        """블록 수신"""
        block_hash = block.get_hash()

        # 다운로드 목록에서 제거
        self._downloading.discard(block_hash)
        self._blocks_to_fetch.discard(block_hash)

        # 검증
        result = validate_block(
            block,
            self.blockchain.utxo_set,
            self.blockchain.get_height() + 1,
            blockchain=self.blockchain
        )

        if result.is_valid:
            # 체인에 추가 (UTXO 자동 적용됨)
            success, _ = self.blockchain.add_block(block)
            if success:
                self._blocks_downloaded += 1
        else:
            # 잘못된 블록 - 피어 밴 점수 추가
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
