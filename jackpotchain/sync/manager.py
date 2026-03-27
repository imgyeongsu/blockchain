"""
Step 9-10: 동기화 관리
- Initial Block Download (IBD)
- 헤더 우선 동기화
- 다중 피어 병렬 블록 다운로드
"""

import asyncio
import time
from datetime import datetime
from typing import Optional, List, Set, Dict
from dataclasses import dataclass
from enum import Enum

from ..consensus.chain import Blockchain, ChainState
from ..core.block import Block, BlockHeader
from ..network.peer import PeerInfo, PeerManager, PeerAddress
from ..constants import MAX_HEADERS_SIZE


def _log(tag: str, msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][{tag}] {msg}")


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
    1. GETHEADERS로 헤더 우선 다운로드
    2. 헤더 검증 후 blockchain에 저장
    3. 다중 피어에서 블록 병렬 다운로드
    4. out-of-order 블록 버퍼링 후 순서대로 체인에 추가
    """

    # 피어당 최대 동시 블록 요청
    MAX_PER_PEER = 16
    # 블록 버퍼 최대 크기 (MAX_PER_PEER × 최대 피어 수 이상이어야 함)
    MAX_BLOCK_BUFFER = 1000
    # 블록 수신 타임아웃 (초)
    STALL_TIMEOUT = 30
    # HEADERS 응답 타임아웃 (초)
    HEADERS_TIMEOUT = 10
    # HEADERS 재시도 최대 횟수
    MAX_HEADERS_RETRIES = 2

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

        # 헤더 동기화
        self._headers_synced = 0
        self._last_header_hash: Optional[bytes] = None  # 마지막 수신 헤더 해시 (locator용)

        # 블록 다운로드 대기열 (높이순 정렬된 리스트)
        self._blocks_to_fetch: List[bytes] = []
        self._blocks_to_fetch_set: Set[bytes] = set()  # O(1) 멤버십 체크
        self._fetch_index: int = 0  # 다음 요청할 위치 (리스트 재스캔 방지)
        self._downloading: Set[bytes] = set()
        self._peer_downloads: Dict[PeerAddress, Set[bytes]] = {}
        self._block_buffer: Dict[bytes, Block] = {}

        # 통계
        self._blocks_downloaded = 0
        self._download_start_time = 0
        self._last_block_time = 0

        # HEADERS 타임아웃
        self._headers_request_time: float = 0
        self._headers_retries: int = 0
        self._watchdog_task: Optional[asyncio.Task] = None

        # 콜백 (node.py에서 설정)
        self._request_headers_callback = None   # async (locator, peer_address?) -> None
        self._request_blocks_callback = None    # async (block_hashes, peer_address) -> None

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

    # =================================================================
    # 동기화 시작
    # =================================================================

    async def start_sync(self):
        """동기화 시작 — HEADERS 단계부터"""
        if not self.needs_sync():
            self.state = SyncState.SYNCED
            return

        self.state = SyncState.HEADERS
        self._download_start_time = time.time()
        self._blocks_downloaded = 0
        self._headers_synced = 0
        self._headers_retries = 0

        _log('SYNC', f'헤더 우선 동기화 시작: 로컬={self.blockchain.get_height()}, 목표={self._best_known_height}')
        await self._request_headers()

        # watchdog 시작
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
        self._watchdog_task = asyncio.ensure_future(self._headers_watchdog())

    # =================================================================
    # 헤더 동기화
    # =================================================================

    async def _request_headers(self):
        """GETHEADERS 요청 — 마지막 헤더 해시를 locator 선두에 포함"""
        if self._request_headers_callback:
            locator = self.blockchain.get_block_locator()
            # 헤더 전용 블록의 마지막 해시를 locator 앞에 추가
            if self._last_header_hash and self._last_header_hash not in locator:
                locator = [self._last_header_hash] + locator
            self._headers_request_time = time.time()
            await self._request_headers_callback(locator)

    async def _headers_watchdog(self):
        """HEADERS 응답 타임아웃 감시 — 응답 없으면 재시도 또는 IDLE 복귀"""
        try:
            while self.state == SyncState.HEADERS:
                await asyncio.sleep(self.HEADERS_TIMEOUT)

                if self.state != SyncState.HEADERS:
                    break

                elapsed = time.time() - self._headers_request_time
                if elapsed < self.HEADERS_TIMEOUT:
                    continue

                self._headers_retries += 1
                if self._headers_retries <= self.MAX_HEADERS_RETRIES:
                    _log('SYNC', f'HEADERS 타임아웃 ({elapsed:.0f}초), 재시도 {self._headers_retries}/{self.MAX_HEADERS_RETRIES}')
                    await self._request_headers()
                else:
                    _log('SYNC', f'HEADERS 재시도 초과 ({self.MAX_HEADERS_RETRIES}회), INV 블록 수신 모드로 전환')
                    self.state = SyncState.SYNCED
                    self.blockchain.state = ChainState.SYNCED
                    self._headers_retries = 0
                    break
        except asyncio.CancelledError:
            pass

    async def on_headers_received(self, peer_address: PeerAddress, raw_headers: List[bytes]):
        """
        HEADERS 메시지 수신 처리

        Args:
            peer_address: 보낸 피어
            raw_headers: 80바이트 직렬화된 헤더 목록
        """
        if self.state != SyncState.HEADERS:
            return

        # HEADERS 응답 수신 → 타임아웃 타이머 리셋
        self._headers_request_time = time.time()
        self._headers_retries = 0

        if not raw_headers:
            # 빈 응답 → 헤더 동기화 완료
            self._transition_to_blocks()
            return

        # 1. raw bytes → BlockHeader 파싱 + 개별 PoW 검증
        headers = []
        for raw in raw_headers:
            try:
                header, _ = BlockHeader.deserialize(raw)
            except Exception:
                _log('SYNC', f'헤더 파싱 실패, 피어 밴: {peer_address.ip}')
                self.peer_manager.add_ban_score(peer_address, 20)
                return

            # PoW 검증 (개별 헤더)
            if not header.verify_pow():
                _log('SYNC', f'헤더 PoW 실패, 피어 밴: {peer_address.ip}')
                self.peer_manager.add_ban_score(peer_address, 20)
                return

            headers.append(header)

        # 2. blockchain에 헤더 저장 (add_headers가 연결성/중복 체크)
        added, msg = self.blockchain.add_headers(headers)
        if "Invalid" in msg:
            # PoW 실패 등 심각한 오류
            _log('SYNC', f'헤더 저장 실패: {msg}, 피어 밴: {peer_address.ip}')
            self.peer_manager.add_ban_score(peer_address, 20)
            return
        self._headers_synced += added
        # 마지막 헤더 해시 기록 (다음 GETHEADERS locator용)
        if headers:
            self._last_header_hash = headers[-1].get_hash()
        _log('SYNC', f'헤더 수신: {len(headers)}개 (추가: {added}개, 총: {self._headers_synced}개)')

        # 3. 상태 전환 판단
        if len(raw_headers) < MAX_HEADERS_SIZE or added == 0:
            # 2000개 미만이거나, 추가 가능한 헤더가 없으면 → BLOCKS 전환
            self._transition_to_blocks()
        else:
            # 2000개 전부 추가됨 → 더 있을 수 있음
            await self._request_headers()

    def _transition_to_blocks(self):
        """HEADERS → BLOCKS 상태 전환"""
        # 다운로드할 블록 목록 = 헤더는 있지만 블록이 없는 것들 (높이순)
        self._blocks_to_fetch = self.blockchain.get_headers_to_download()
        self._blocks_to_fetch_set = set(self._blocks_to_fetch)
        self._fetch_index = 0

        if not self._blocks_to_fetch:
            _log('SYNC', '다운로드할 블록 없음 → 동기화 완료')
            self.state = SyncState.SYNCED
            self.blockchain.state = ChainState.SYNCED
            return

        self.state = SyncState.BLOCKS
        self._last_block_time = time.time()
        _log('SYNC', f'블록 다운로드 시작: {len(self._blocks_to_fetch)}개 블록 대기')
        asyncio.ensure_future(self._request_blocks())

    # =================================================================
    # 블록 다운로드 (다중 피어 병렬)
    # =================================================================

    async def _request_blocks(self):
        """다중 피어에 블록 병렬 분배 요청

        _fetch_index부터 높이순으로 스캔하면서
        빈 슬롯이 있는 피어에게 순서대로 할당한다.
        예: 피어 3개 × 16슬롯 = 최대 48블록 동시 다운로드
        """
        if not self._blocks_to_fetch_set and not self._downloading:
            self._finish_sync()
            return

        if not self._request_blocks_callback:
            return

        # 블록을 가진 피어만 선택 (start_height > 로컬 높이)
        local_height = self.blockchain.get_height()
        peers = [p for p in self.peer_manager.get_connected_peers()
                 if p.start_height > local_height]
        if not peers:
            return

        # 피어별 빈 슬롯 계산 + 높이 매핑
        peer_slots: Dict[PeerAddress, int] = {}
        peer_heights: Dict[PeerAddress, int] = {}
        for peer in peers:
            addr = peer.address
            in_flight = len(self._peer_downloads.get(addr, set()))
            if in_flight < self.MAX_PER_PEER:
                peer_slots[addr] = self.MAX_PER_PEER - in_flight
                peer_heights[addr] = peer.start_height

        if not peer_slots:
            return

        # 피어별 요청 목록
        peer_requests: Dict[PeerAddress, List[bytes]] = {addr: [] for addr in peer_slots}
        peer_list = list(peer_slots.keys())
        peer_idx = 0

        # _fetch_index부터 스캔하며 라운드로빈 분배
        total_slots = sum(peer_slots.values())
        assigned = 0
        i = self._fetch_index

        while i < len(self._blocks_to_fetch) and assigned < total_slots:
            block_hash = self._blocks_to_fetch[i]
            i += 1

            if block_hash not in self._blocks_to_fetch_set:
                continue  # 이미 완료됨
            if block_hash in self._downloading or block_hash in self._block_buffer:
                continue  # 이미 요청 중이거나 버퍼에 있음

            # 블록 높이 조회
            block_idx = self.blockchain.get_block_index(block_hash)
            block_height = block_idx.height if block_idx else 0

            # 빈 슬롯이 있고 이 블록을 가진 피어 찾기 (라운드로빈)
            found = False
            for _ in range(len(peer_list)):
                addr = peer_list[peer_idx]
                peer_idx = (peer_idx + 1) % len(peer_list)
                if (len(peer_requests[addr]) < peer_slots[addr]
                        and peer_heights[addr] >= block_height):
                    peer_requests[addr].append(block_hash)
                    self._downloading.add(block_hash)
                    assigned += 1
                    found = True
                    break

            if not found:
                break  # 이 블록을 줄 수 있는 피어가 없음 → 중단

        # _fetch_index 업데이트 (완료된 블록 건너뛰기)
        self._fetch_index = i

        # 각 피어에게 GETDATA 전송
        for addr, hashes in peer_requests.items():
            if hashes:
                self._peer_downloads.setdefault(addr, set()).update(hashes)
                await self._request_blocks_callback(hashes, addr)

    # =================================================================
    # 블록 수신
    # =================================================================

    async def on_block_received(self, block: Block, peer: PeerInfo):
        """
        블록 수신 처리

        - 다운로드 추적에서 제거
        - 메인 체인에 연결 가능하면 즉시 추가
        - 불가능하면 버퍼에 저장
        - 추가 성공 후 버퍼에서 연쇄 처리
        """
        block_hash = block.get_hash()
        self._last_block_time = time.time()

        # 다운로드 추적 제거
        self._downloading.discard(block_hash)
        self._blocks_to_fetch_set.discard(block_hash)
        if peer and peer.address in self._peer_downloads:
            self._peer_downloads[peer.address].discard(block_hash)

        # 이전 블록이 존재하는지 확인 (메인 체인 또는 사이드 체인 모두 허용)
        prev_hash = block.header.prev_block_hash
        if prev_hash != bytes(32) and prev_hash not in self.blockchain._block_index:
            # 이전 블록이 아예 없음 → 버퍼에 저장
            if len(self._block_buffer) < self.MAX_BLOCK_BUFFER:
                self._block_buffer[block_hash] = block
                if len(self._block_buffer) % 50 == 0:
                    _log('SYNC', f'버퍼: {len(self._block_buffer)}개 (prev 대기: {prev_hash.hex()[:16]})')
            return

        # 체인에 추가 시도
        if not await self._try_add_block(block, peer):
            return

        # 버퍼에서 연쇄 처리
        await self._flush_buffer(peer)

        # 추가 블록 요청
        if self.state == SyncState.BLOCKS:
            if self._blocks_to_fetch_set or self._downloading:
                await self._request_blocks()
            elif not self._block_buffer:
                self._finish_sync()

    async def _try_add_block(self, block: Block, peer: PeerInfo) -> bool:
        """블록을 체인에 추가

        IBD에서는 validate_block을 스킵한다:
        - PoW: 헤더 단계에서 이미 검증 완료
        - TX 검증: 기존 체인 블록이 validate_block 없이 추가되었으므로 호환성 유지
        - 체인 리셋 후 깨끗한 블록만 있으면 validate_block 활성화 가능
        """
        try:
            success, msg = self.blockchain.add_block(block)
        except Exception as e:
            _log('SYNC', f'블록 추가 예외: {type(e).__name__}: {e}')
            return False

        if success:
            self._blocks_downloaded += 1

            # reorg 감지 → SYNCED 상태(실시간)에서만 버퍼 flush
            # IBD 중에는 블록 순서가 뒤섞여 리오그가 빈번하므로 버퍼를 유지해야 함
            if self.blockchain.state == ChainState.REORGING and self.state == SyncState.SYNCED:
                _log('SYNC', f'reorg 감지 — 블록 버퍼 초기화 ({len(self._block_buffer)}개)')
                self._block_buffer.clear()

            if self._blocks_downloaded % 100 == 0:
                elapsed = time.time() - self._download_start_time
                bps = self._blocks_downloaded / elapsed if elapsed > 0 else 0
                _log('SYNC', f'블록 진행: {self._blocks_downloaded}개 ({bps:.0f} blocks/s), 높이: {self.blockchain.get_height()}, 버퍼: {len(self._block_buffer)}개, 대기: {len(self._blocks_to_fetch_set)}개')

            # 사이드 체인 경고
            if "side chain" in msg.lower():
                _log('SYNC', f'⚠ 사이드체인 추가: hash={block.get_hash().hex()[:16]}, msg={msg}')

            return True
        else:
            _log('SYNC', f'블록 추가 실패: {msg}, hash={block.get_hash().hex()[:16]}')
            return False

    async def _flush_buffer(self, peer: PeerInfo):
        """버퍼에서 메인 체인에 연결 가능한 블록들을 연쇄 처리"""
        processed = True
        while processed:
            processed = False
            for buf_hash, buf_block in list(self._block_buffer.items()):
                if buf_block.header.prev_block_hash in self.blockchain._block_index:
                    del self._block_buffer[buf_hash]
                    if await self._try_add_block(buf_block, peer):
                        processed = True
                        break

    # =================================================================
    # 피어 단절 처리
    # =================================================================

    def on_peer_disconnected(self, peer_address: PeerAddress):
        """피어 단절 시 해당 피어의 in-flight 블록 정리"""
        stale = self._peer_downloads.pop(peer_address, set())
        for block_hash in stale:
            self._downloading.discard(block_hash)

        if stale:
            # _fetch_index를 0으로 리셋하여 해제된 블록을 다른 피어에 재분배
            self._fetch_index = 0
            _log('SYNC', f'피어 단절: {peer_address.ip} — {len(stale)}개 블록 재요청 대기')

    # =================================================================
    # 완료
    # =================================================================

    def _finish_sync(self):
        """동기화 완료"""
        elapsed = time.time() - self._download_start_time if self._download_start_time else 0
        bps = self._blocks_downloaded / elapsed if elapsed > 0 else 0

        self.state = SyncState.SYNCED
        self.blockchain.state = ChainState.SYNCED
        self._block_buffer.clear()
        self._downloading.clear()
        self._peer_downloads.clear()
        self._fetch_index = 0

        _log('SYNC', f'동기화 완료! 높이={self.blockchain.get_height()}, '
             f'{self._blocks_downloaded}개 블록, {elapsed:.1f}s ({bps:.0f} blocks/s)')

    # =================================================================
    # 통계 / 유틸
    # =================================================================

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
            headers_synced=self._headers_synced,
            blocks_downloaded=self._blocks_downloaded,
            blocks_per_second=bps,
            eta_seconds=eta
        )

    def is_synced(self) -> bool:
        """동기화 완료 여부"""
        return self.state == SyncState.SYNCED
