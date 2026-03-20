"""
Step 9-10: 동기화 관리
- Initial Block Download (IBD)
- 헤더 우선 동기화
"""

import asyncio
import time
from collections import deque
from typing import Optional, List, Set
from dataclasses import dataclass
from enum import Enum

from ..consensus.chain import Blockchain, ChainState
from ..consensus.difficulty import get_next_difficulty
from ..core.block import Block, BlockHeader
from ..network.peer import PeerInfo, PeerManager
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

    # 피어당 최대 동시 요청 블록 수
    BLOCKS_PER_PEER = 16

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
        self._num_sync_peers = 1  # 병렬 다운로드에 참여하는 피어 수

        # 다운로드 대기열 및 고아 블록 버퍼
        self._headers_to_fetch: deque = deque()        # 순서 보장용 (O(1) popleft)
        self._headers_set: Set[bytes] = set()          # O(1) 멤버십 체크용
        self._blocks_to_fetch: Set[bytes] = set()
        self._downloading: Set[bytes] = set()
        self._downloading_since: dict[bytes, float] = {}  # hash → 요청 시각
        self._block_buffer: dict[bytes, tuple] = {}       # hash → (Block, PeerInfo)

        # 재요청 타임아웃 (초): 이 시간 안에 블록 안 오면 재요청
        self.DOWNLOAD_TIMEOUT = 5

        # drain 전용 asyncio.Event - 새 블록이 버퍼에 들어올 때 signal
        self._drain_event: asyncio.Event = asyncio.Event()
        self._drain_task: Optional[asyncio.Task] = None

        # 신뢰하는 sync 피어 주소 (비인가 피어 헤더 주입 방지)
        self._sync_peer_address = None

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

        # drain 전용 태스크 시작 (아직 없으면)
        if self._drain_task is None or self._drain_task.done():
            self._drain_task = asyncio.create_task(self._drain_loop())

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

    async def on_headers_received(self, address, headers: List):
        """헤더 수신"""
        if self.state != SyncState.HEADERS:
            return

        # 비인가 피어 헤더 주입 방지: 신뢰하는 sync 피어만 수락
        if self._sync_peer_address is not None and address != self._sync_peer_address:
            return

        for header_bytes in headers:
            try:
                # 1. 수신한 바이트 배열을 BlockHeader 객체로 변환 (역직렬화)
                header, _ = BlockHeader.deserialize(header_bytes)
                header_hash = header.get_hash()

                # 2. 로컬 블록체인에 이미 추가되어 있는 블록인지 검사 (중복 다운로드 방지)
                if self.blockchain.has_block(header_hash):
                    continue

                # 3. 작업증명(PoW) 일차적 검증
                # 악의적인 공격자가 쓰레기 데이터를 보내더라도 PoW를 통과하지 못하면
                # 블록 본문을 다운로드하기 전에 즉시 무시하여 대역폭과 디스크 I/O를 절약합니다.
                if not header.verify_pow():
                    # (실제 환경에서는 여기서 해당 Peer의 신뢰도 점수를 깎습니다)
                    continue

                # 4. 중복 추가 방지 후 다운로드 큐에 등록
                if header_hash not in self._headers_set:
                    self._blocks_to_fetch.add(header_hash)
                    self._headers_to_fetch.append(header_hash)
                    self._headers_set.add(header_hash)

            except Exception:
                # 직렬화 형식이 잘못되었거나 파싱 실패 시 무시
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
            # 모든 블록 다운로드 완료 - drain loop가 처리 완료 시 SYNCED 설정
            return

        if self._request_blocks_callback:
            # 동시 요청 제한: 피어 수에 비례하여 in-flight 윈도우 확장
            max_in_flight = self.BLOCKS_PER_PEER * max(1, self._num_sync_peers)
            to_request = []
            for block_hash in self._headers_to_fetch:
                if block_hash in self._blocks_to_fetch and block_hash not in self._downloading:
                    to_request.append(block_hash)
                    self._downloading.add(block_hash)
                    if len(to_request) >= max_in_flight:
                        break

            now = time.time()
            for bh in to_request:
                self._downloading_since[bh] = now

            if to_request:
                await self._request_blocks_callback(to_request)

    def _process_single_block(self, block: Block, peer: PeerInfo) -> bool:
        """단일 블록의 체인 유효성 검증 및 추가 시도

        IBD 중에는 경량 검증만 수행 (PoW는 헤더 단계에서 이미 검증됨):
        - 헤더 검증 (PoW, 타임스탬프, 난이도)
        - 구조 검증 (Merkle Root, Coinbase 존재)
        - 트랜잭션 서명 검증은 생략 (Bitcoin Core와 동일한 IBD 최적화)
        """
        from ..validation.block import validate_block_header, validate_block_structure

        prev_block = self.blockchain.get_tip()
        prev_header = prev_block.header if prev_block else None
        expected_difficulty = get_next_difficulty(
            self.blockchain.get_height(),
            self.blockchain.get_block_by_height
        )

        # 1. 헤더 검증 (PoW + 타임스탬프 + 난이도)
        header_result = validate_block_header(
            block.header, prev_header, expected_difficulty
        )
        if not header_result.is_valid:
            block_hash = block.get_hash().hex()[:16]
            height = self.blockchain.get_height() + 1
            print(f"[SYNC] 헤더 검증 실패: height={height}, hash={block_hash}...")
            print(f"[SYNC]   error={header_result.error}, message={header_result.message}")
            print(f"[SYNC]   block.difficulty={block.header.difficulty_target:#x}, expected={expected_difficulty:#x}")
            print(f"[SYNC]   block.timestamp={block.header.timestamp}, prev.timestamp={prev_header.timestamp if prev_header else 'N/A'}")
            self.peer_manager.add_ban_score(peer.address, 20)
            return False

        # 2. 구조 검증 (Merkle Root, Coinbase 존재 등)
        struct_result = validate_block_structure(block)
        if not struct_result.is_valid:
            block_hash = block.get_hash().hex()[:16]
            height = self.blockchain.get_height() + 1
            print(f"[SYNC] 구조 검증 실패: height={height}, hash={block_hash}...")
            print(f"[SYNC]   error={struct_result.error}, message={struct_result.message}")
            self.peer_manager.add_ban_score(peer.address, 20)
            return False

        # 3. 체인에 추가 (add_block이 prev_hash 연결성 + UTXO 적용 처리)
        success, msg = self.blockchain.add_block(block)
        if not success:
            tip = self.blockchain.get_tip()
            tip_hash = tip.get_hash() if tip else b''
            prev_hash = block.header.prev_block_hash
            print(f"[SYNC] add_block 실패: {msg}")
            print(f"[SYNC]   block_hash  = {block.get_hash().hex()[:16]}...")
            print(f"[SYNC]   prev_hash   = {prev_hash.hex()[:16]}...")
            print(f"[SYNC]   current_tip = {tip_hash.hex()[:16]}... (height={self.blockchain.get_height()})")
            print(f"[SYNC]   prev==tip?  = {prev_hash == tip_hash}")
            print(f"[SYNC]   prev in idx?= {prev_hash in self.blockchain._block_index}")
            print(f"[SYNC]   prev in blk?= {prev_hash in self.blockchain._blocks}")
        return success

    async def on_block_received(self, block: Block, peer: PeerInfo):
        """블록 수신 - 버퍼에 보관 후 drain task에 알림"""
        block_hash = block.get_hash()

        # 다운로드 목록에서 제거
        self._downloading.discard(block_hash)
        self._downloading_since.pop(block_hash, None)
        self._blocks_to_fetch.discard(block_hash)

        if block_hash in self._headers_set:
            self._block_buffer[block_hash] = (block, peer)
            self._drain_event.set()   # drain task 깨우기
        else:
            # 외부 실시간 전파 블록
            self._process_single_block(block, peer)

    async def _drain_loop(self):
        """독립 태스크: 버퍼에서 블록을 순서대로 꺼내 체인에 조립
        event loop를 블록킹하지 않도록 블록마다 await"""
        try:
            while self.state in (SyncState.HEADERS, SyncState.BLOCKS):
                # 새 블록이 버퍼에 들어올 때까지 대기
                await self._drain_event.wait()
                self._drain_event.clear()

                # 순서대로 drain
                while self._headers_to_fetch:
                    expected_hash = self._headers_to_fetch[0]

                    if expected_hash not in self._block_buffer:
                        break   # 아직 다음 블록 미도착

                    next_block, peer = self._block_buffer.pop(expected_hash)

                    try:
                        success = self._process_single_block(next_block, peer)
                    except Exception as e:
                        import traceback
                        print(f"[SYNC] ★ _process_single_block 예외 발생!")
                        print(f"[SYNC]   height={self.blockchain.get_height() + 1}, hash={expected_hash.hex()[:16]}...")
                        print(f"[SYNC]   exception: {type(e).__name__}: {e}")
                        traceback.print_exc()
                        success = False

                    if success:
                        self._blocks_downloaded += 1
                        self._headers_to_fetch.popleft()
                        self._headers_set.discard(expected_hash)
                        if self._blocks_downloaded % 100 == 0 or self._blocks_downloaded <= 5:
                            print(f"[SYNC] 블록 #{self._blocks_downloaded} 추가 완료: height={self.blockchain.get_height()}, hash={expected_hash.hex()[:12]}...")
                        # 모든 블록 처리 완료
                        if not self._headers_to_fetch:
                            self.state = SyncState.SYNCED
                            self.blockchain.state = ChainState.SYNCED
                            return
                        # 슬롯이 비었으니 추가 요청
                        await self._request_blocks()
                    else:
                        self._headers_to_fetch.popleft()
                        self._headers_set.discard(expected_hash)
                        self.state = SyncState.IDLE
                        print(f"[SYNC] 블록 검증 실패 - sync 초기화: {expected_hash.hex()[:8]}...")
                        return

                    # 블록마다 event loop에 제어 반환 (다른 코루틴이 메시지를 받을 수 있게)
                    await asyncio.sleep(0)

            print("[SYNC] drain loop 종료")
        except asyncio.CancelledError:
            print("[SYNC] drain loop 취소됨")
        except Exception as e:
            import traceback
            print(f"[SYNC] ★★★ drain loop 예외로 죽음! ★★★")
            print(f"[SYNC]   exception: {type(e).__name__}: {e}")
            traceback.print_exc()
            self.state = SyncState.IDLE

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

    async def check_stalled_downloads(self):
        """타임아웃된 in-flight 블록을 _downloading에서 해제하여 재요청 가능하게 함"""
        if self.state != SyncState.BLOCKS:
            return

        now = time.time()
        timed_out = [
            bh for bh, t in self._downloading_since.items()
            if now - t > self.DOWNLOAD_TIMEOUT
        ]

        if not timed_out:
            return

        print(f"[SYNC] 타임아웃 블록 {len(timed_out)}개 재요청 큐로 반환")
        for bh in timed_out:
            self._downloading.discard(bh)
            self._downloading_since.pop(bh, None)
            # _blocks_to_fetch에 다시 넣어 재요청 대상으로 만듦
            if bh in self._headers_set:
                self._blocks_to_fetch.add(bh)

        await self._request_blocks()

    def reset_sync(self):
        """동기화 상태 초기화 (sync 피어 연결 끊김 등 예외 상황 시 호출)"""
        self.state = SyncState.IDLE
        self._sync_peer_address = None
        self._headers_to_fetch.clear()
        self._headers_set.clear()
        self._blocks_to_fetch.clear()
        self._downloading.clear()
        self._downloading_since.clear()
        self._block_buffer.clear()
        self._blocks_downloaded = 0
        self._download_start_time = 0
        if self._drain_task and not self._drain_task.done():
            self._drain_task.cancel()
        self._drain_task = None
        self._drain_event.clear()

    def is_synced(self) -> bool:
        """동기화 완료 여부"""
        return self.state == SyncState.SYNCED
