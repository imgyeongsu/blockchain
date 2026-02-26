"""
Step 4.3: 체인 관리
- 블록 체인 관리
- Fork 처리
- 재조직 (Reorg)
"""

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

from ..core.block import Block, create_genesis_block
from ..core.utxo import UTXOSet
from .difficulty import compact_to_target


class ChainState(Enum):
    """체인 상태"""
    SYNCING = "syncing"
    SYNCED = "synced"
    REORGING = "reorging"


@dataclass
class ChainTip:
    """체인 끝 정보"""
    block_hash: bytes
    height: int
    total_work: int


@dataclass
class BlockIndex:
    """블록 인덱스 (메타데이터)"""
    block_hash: bytes
    prev_hash: bytes
    height: int
    timestamp: int
    difficulty: int
    total_work: int  # 누적 작업량
    is_valid: bool = True
    is_in_main_chain: bool = True


class Blockchain:
    """
    블록체인 관리 클래스
    - 체인 상태 관리
    - Fork 감지 및 처리
    - 재조직 (Reorg)
    """

    def __init__(self, genesis_block: Block = None):
        # 블록 저장소 (hash -> Block)
        self._blocks: Dict[bytes, Block] = {}

        # 블록 인덱스 (hash -> BlockIndex)
        self._block_index: Dict[bytes, BlockIndex] = {}

        # 높이별 블록 해시 (height -> hash) - 메인 체인만
        self._height_to_hash: Dict[int, bytes] = {}

        # 체인 팁들 (여러 브랜치 추적)
        self._tips: Dict[bytes, ChainTip] = {}

        # 메인 체인 팁
        self._main_tip: Optional[ChainTip] = None

        # UTXO Set
        self.utxo_set = UTXOSet()

        # 상태
        self.state = ChainState.SYNCING

        # Genesis 블록 추가
        if genesis_block is None:
            genesis_block = create_genesis_block()
        self._add_genesis(genesis_block)

    def _add_genesis(self, block: Block):
        """Genesis 블록 추가"""
        block_hash = block.get_hash()

        self._blocks[block_hash] = block

        index = BlockIndex(
            block_hash=block_hash,
            prev_hash=bytes(32),
            height=0,
            timestamp=block.header.timestamp,
            difficulty=block.header.difficulty_target,
            total_work=self._calculate_work(block.header.difficulty_target),
            is_valid=True,
            is_in_main_chain=True
        )
        self._block_index[block_hash] = index
        self._height_to_hash[0] = block_hash

        tip = ChainTip(
            block_hash=block_hash,
            height=0,
            total_work=index.total_work
        )
        self._tips[block_hash] = tip
        self._main_tip = tip

    def _calculate_work(self, difficulty_target: int) -> int:
        """난이도에서 작업량 계산"""
        target = compact_to_target(difficulty_target)
        if target == 0:
            return 0
        # work = 2^256 / (target + 1)
        return (2 ** 256) // (target + 1)

    def add_block(self, block: Block) -> Tuple[bool, str]:
        """
        블록 추가

        Returns:
            (success, message)
        """
        block_hash = block.get_hash()

        # 이미 존재하면 무시
        if block_hash in self._blocks:
            return False, "Block already exists"

        # 이전 블록 확인
        prev_hash = block.header.prev_block_hash
        if prev_hash not in self._block_index:
            return False, "Previous block not found"

        prev_index = self._block_index[prev_hash]

        # 인덱스 생성
        new_height = prev_index.height + 1
        new_work = prev_index.total_work + self._calculate_work(block.header.difficulty_target)

        index = BlockIndex(
            block_hash=block_hash,
            prev_hash=prev_hash,
            height=new_height,
            timestamp=block.header.timestamp,
            difficulty=block.header.difficulty_target,
            total_work=new_work,
            is_valid=True,
            is_in_main_chain=False  # 나중에 결정
        )

        self._blocks[block_hash] = block
        self._block_index[block_hash] = index

        # 팁 업데이트
        new_tip = ChainTip(
            block_hash=block_hash,
            height=new_height,
            total_work=new_work
        )

        # 이전 블록이 팁이었으면 제거
        if prev_hash in self._tips:
            del self._tips[prev_hash]

        self._tips[block_hash] = new_tip

        # 메인 체인 결정 (가장 많은 작업량)
        if new_work > self._main_tip.total_work:
            old_tip = self._main_tip
            self._main_tip = new_tip
            index.is_in_main_chain = True

            # 재조직 필요 여부 확인
            if old_tip.block_hash != prev_hash:
                self._reorganize(old_tip.block_hash, block_hash)
            else:
                # 단순 확장
                self._height_to_hash[new_height] = block_hash

            return True, "Block added to main chain"
        else:
            return True, "Block added to side chain"

    def _reorganize(self, old_tip_hash: bytes, new_tip_hash: bytes):
        """
        체인 재조직

        Args:
            old_tip_hash: 이전 메인 체인 팁
            new_tip_hash: 새 메인 체인 팁
        """
        self.state = ChainState.REORGING

        # 공통 조상 찾기
        old_chain = self._get_ancestors(old_tip_hash)
        new_chain = self._get_ancestors(new_tip_hash)

        common_ancestor = None
        for block_hash in old_chain:
            if block_hash in new_chain:
                common_ancestor = block_hash
                break

        if common_ancestor is None:
            # 이론적으로 발생하면 안됨 (Genesis가 공통)
            raise RuntimeError("No common ancestor found")

        # 되돌릴 블록들 (old tip -> common ancestor)
        blocks_to_disconnect = []
        current = old_tip_hash
        while current != common_ancestor:
            blocks_to_disconnect.append(current)
            current = self._block_index[current].prev_hash

        # 연결할 블록들 (common ancestor -> new tip)
        blocks_to_connect = []
        current = new_tip_hash
        while current != common_ancestor:
            blocks_to_connect.append(current)
            current = self._block_index[current].prev_hash
        blocks_to_connect.reverse()

        # 메인 체인 마킹 업데이트
        for block_hash in blocks_to_disconnect:
            self._block_index[block_hash].is_in_main_chain = False
            height = self._block_index[block_hash].height
            if height in self._height_to_hash:
                del self._height_to_hash[height]

        for block_hash in blocks_to_connect:
            self._block_index[block_hash].is_in_main_chain = True
            height = self._block_index[block_hash].height
            self._height_to_hash[height] = block_hash

        # TODO: UTXO Set 업데이트 (disconnect/connect)

        self.state = ChainState.SYNCED

    def _get_ancestors(self, block_hash: bytes, limit: int = 1000) -> List[bytes]:
        """블록의 조상들 반환"""
        ancestors = []
        current = block_hash
        for _ in range(limit):
            ancestors.append(current)
            index = self._block_index.get(current)
            if index is None or index.prev_hash == bytes(32):
                break
            current = index.prev_hash
        return ancestors

    def get_block(self, block_hash: bytes) -> Optional[Block]:
        """블록 조회"""
        return self._blocks.get(block_hash)

    def get_block_by_height(self, height: int) -> Optional[Block]:
        """높이로 블록 조회 (메인 체인)"""
        block_hash = self._height_to_hash.get(height)
        if block_hash:
            return self._blocks.get(block_hash)
        return None

    def get_block_index(self, block_hash: bytes) -> Optional[BlockIndex]:
        """블록 인덱스 조회"""
        return self._block_index.get(block_hash)

    def get_height(self) -> int:
        """현재 높이"""
        return self._main_tip.height if self._main_tip else -1

    def get_tip(self) -> Optional[Block]:
        """메인 체인 팁 블록"""
        if self._main_tip:
            return self._blocks.get(self._main_tip.block_hash)
        return None

    def get_tip_hash(self) -> bytes:
        """메인 체인 팁 해시"""
        return self._main_tip.block_hash if self._main_tip else bytes(32)

    def has_block(self, block_hash: bytes) -> bool:
        """블록 존재 여부"""
        return block_hash in self._blocks

    def is_in_main_chain(self, block_hash: bytes) -> bool:
        """메인 체인 소속 여부"""
        index = self._block_index.get(block_hash)
        return index.is_in_main_chain if index else False

    def get_confirmations(self, block_hash: bytes) -> int:
        """확인 수 (메인 체인 기준)"""
        index = self._block_index.get(block_hash)
        if not index or not index.is_in_main_chain:
            return 0
        return self._main_tip.height - index.height + 1

    def get_difficulty(self) -> int:
        """현재 난이도"""
        tip = self.get_tip()
        return tip.header.difficulty_target if tip else 0

    def get_total_work(self) -> int:
        """누적 작업량"""
        return self._main_tip.total_work if self._main_tip else 0

    def get_all_tips(self) -> List[ChainTip]:
        """모든 팁 반환 (디버깅용)"""
        return list(self._tips.values())

    def get_chain_hashes(self, start_height: int = 0, count: int = 500) -> List[bytes]:
        """체인 해시 목록 (동기화용)"""
        hashes = []
        for h in range(start_height, min(start_height + count, self._main_tip.height + 1)):
            if h in self._height_to_hash:
                hashes.append(self._height_to_hash[h])
        return hashes

    def find_fork_point(self, block_hashes: List[bytes]) -> Tuple[int, bytes]:
        """
        분기점 찾기

        Args:
            block_hashes: 상대방의 블록 해시 목록

        Returns:
            (fork_height, fork_hash)
        """
        for block_hash in block_hashes:
            index = self._block_index.get(block_hash)
            if index and index.is_in_main_chain:
                return index.height, block_hash
        return 0, self._height_to_hash.get(0, bytes(32))
