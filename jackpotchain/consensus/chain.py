"""
Step 4.3: 체인 관리
- 블록 체인 관리
- Fork 처리
- 재조직 (Reorg)
- 영구 저장 지원
"""

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

from ..core.block import Block, create_genesis_block
from ..core.utxo import UTXO, UTXOSet
from .difficulty import compact_to_target
from ..script.standard import get_address_from_script_pubkey, is_commit_script, extract_commit_hash, is_claim_script, extract_claim_data
from ..constants import TX_VERSION_COMMIT, TX_VERSION_CLAIM


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


@dataclass
class CommitInfo:
    """Commit TX 인덱스 정보 (Claim 검증용)"""
    tx_id: bytes
    block_height: int
    block_hash: bytes
    claim_height: int = 0  # Claim된 높이 (0이면 미클레임)


class Blockchain:
    """
    블록체인 관리 클래스
    - 체인 상태 관리
    - Fork 감지 및 처리
    - 재조직 (Reorg)
    - 영구 저장 (data_dir 지정 시)
    """

    def __init__(self, genesis_block: Block = None, data_dir: str = None):
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

        # Undo 데이터 (Reorg용): block_hash -> List[List[UTXO]]
        # 각 블록의 각 TX가 소비한 UTXO들 저장
        self._undo_data: Dict[bytes, List[List[UTXO]]] = {}

        # Commit TX 인덱스 (Claim 검증용): commit_hash -> CommitInfo
        self._commit_index: Dict[bytes, CommitInfo] = {}

        # Reorg 시 mempool 복원 대상 TX (add_block 호출자가 가져감)
        self._disconnected_txs: list = []

        # 상태
        self.state = ChainState.SYNCING

        # 영구 저장소 (옵션)
        self._store = None
        self._data_dir = data_dir
        if data_dir:
            from ..storage.database import BlockStore
            self._store = BlockStore(data_dir)
            self._load_from_store()
        else:
            # 저장소 없으면 Genesis로 시작
            if genesis_block is None:
                genesis_block = create_genesis_block()
            self._add_genesis(genesis_block)

    def _load_from_store(self):
        """저장소에서 블록체인 로드"""
        tip_height = self._store.get_tip_height()

        if tip_height < 0:
            # 저장된 블록 없음 - Genesis 생성
            genesis = create_genesis_block()
            self._add_genesis(genesis)
            self._store.save_block(genesis, 0)
            print(f"[Chain] Created genesis block")
        else:
            # 저장된 블록 로드
            print(f"[Chain] Loading {tip_height + 1} blocks from storage...")
            for height in range(tip_height + 1):
                block = self._store.load_block_by_height(height)
                if block:
                    if height == 0:
                        self._add_genesis(block)
                    else:
                        self._add_block_internal(block, height)

                    # _connect_block으로 UTXO + undo 데이터 + 인덱싱 일괄 처리
                    self._connect_block(block, height)

            print(f"[Chain] Loaded {tip_height + 1} blocks. Height: {self.get_height()}")

    def _add_block_internal(self, block: Block, height: int):
        """블록 내부 추가 (검증 없이, 로드용)"""
        block_hash = block.get_hash()
        prev_hash = block.header.prev_block_hash

        prev_work = 0
        if prev_hash in self._block_index:
            prev_work = self._block_index[prev_hash].total_work

        new_work = prev_work + self._calculate_work(block.header.difficulty_target)

        index = BlockIndex(
            block_hash=block_hash,
            prev_hash=prev_hash,
            height=height,
            timestamp=block.header.timestamp,
            difficulty=block.header.difficulty_target,
            total_work=new_work,
            is_valid=True,
            is_in_main_chain=True
        )

        self._blocks[block_hash] = block
        self._block_index[block_hash] = index
        self._height_to_hash[height] = block_hash

        tip = ChainTip(
            block_hash=block_hash,
            height=height,
            total_work=new_work
        )
        self._tips = {block_hash: tip}
        self._main_tip = tip

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

        # Genesis 블록 UTXO 적용
        self._connect_block(block, 0)

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
            print(f"[CHAIN] 블록 추가 실패: 이미 존재 (hash={block_hash.hex()[:16]}...)")
            return False, "Block already exists"

        # 이전 블록 확인
        prev_hash = block.header.prev_block_hash
        if prev_hash not in self._block_index:
            print(f"[CHAIN] 블록 추가 실패: 이전 블록 없음 (prev={prev_hash.hex()[:16]}...)")
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
                # UTXO 적용 및 undo 데이터 저장
                self._connect_block(block, new_height)

            # 영구 저장
            if self._store:
                self._store.save_block(block, new_height)

            print(f"[CHAIN] 블록 추가 성공: height={new_height}, hash={block_hash.hex()[:16]}...")
            return True, "Block added to main chain"
        else:
            print(f"[CHAIN] 사이드 체인에 추가: hash={block_hash.hex()[:16]}...")
            return True, "Block added to side chain"

    def _reorganize(self, old_tip_hash: bytes, new_tip_hash: bytes):
        """
        체인 재조직

        Args:
            old_tip_hash: 이전 메인 체인 팁
            new_tip_hash: 새 메인 체인 팁

        Returns:
            disconnected_txs: disconnect된 블록의 TX 목록 (mempool 복원용, coinbase 제외)
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

        # UTXO Set 업데이트 (disconnect/connect)
        # 1. 기존 블록들 되돌리기 (역순으로) — TX 수집
        disconnected_txs = []
        for block_hash in blocks_to_disconnect:
            block = self._blocks.get(block_hash)
            if block:
                # coinbase(인덱스 0) 제외한 TX를 mempool 복원 후보로 수집
                disconnected_txs.extend(block.transactions[1:])
            self._disconnect_block(block_hash)

        # 2. 새 블록들 연결하기
        # 새 체인에 이미 포함된 TX는 mempool 복원 대상에서 제거
        new_chain_txids = set()
        for block_hash in blocks_to_connect:
            block = self._blocks[block_hash]
            height = self._block_index[block_hash].height
            self._connect_block(block, height)
            for tx in block.transactions[1:]:
                new_chain_txids.add(tx.get_txid())

        # 새 체인에 포함되지 않은 TX만 반환 (mempool 복원 대상)
        self._disconnected_txs = [
            tx for tx in disconnected_txs
            if tx.get_txid() not in new_chain_txids
        ]

        self.state = ChainState.SYNCED

    def _connect_block(self, block: Block, height: int):
        """
        블록 연결 (UTXO 적용 + undo 데이터 저장 + commit 인덱싱)

        Args:
            block: 연결할 블록
            height: 블록 높이
        """
        block_hash = block.get_hash()
        undo_data: List[List[UTXO]] = []

        for tx in block.transactions:
            # UTXO 적용 및 소비된 UTXO 저장
            spent_utxos = self.utxo_set.apply_transaction(tx, height, get_address_from_script_pubkey)
            undo_data.append(spent_utxos)

            # Commit TX 인덱싱
            self._index_commit_tx(tx, height, block_hash)
            # Claim TX 인덱싱
            self._index_claim_tx(tx, height)

        # Undo 데이터 저장 (나중에 disconnect용)
        self._undo_data[block_hash] = undo_data

    def _disconnect_block(self, block_hash: bytes):
        """
        블록 연결 해제 (UTXO 되돌리기 + commit/claim 인덱스 제거)

        Args:
            block_hash: 연결 해제할 블록 해시
        """
        block = self._blocks.get(block_hash)
        if not block:
            return

        undo_data = self._undo_data.get(block_hash, [])

        # 트랜잭션을 역순으로 되돌리기
        for i in range(len(block.transactions) - 1, -1, -1):
            tx = block.transactions[i]
            spent_utxos = undo_data[i] if i < len(undo_data) else []
            self.utxo_set.revert_transaction(tx, spent_utxos, get_address_from_script_pubkey)

            # Commit TX 인덱스 제거
            self._unindex_commit_tx(tx)
            # Claim TX 인덱스 되돌리기 (claim_height → 0)
            self._unindex_claim_tx(tx)

        # Undo 데이터 제거
        self._undo_data.pop(block_hash, None)

    def _unindex_claim_tx(self, tx):
        """
        Claim TX 인덱스 되돌리기 (reorg 시)
        해당 commit의 claim_height를 0으로 리셋하여 다시 claim 가능하게 함
        """
        if tx.version != TX_VERSION_CLAIM:
            return

        for output in tx.outputs:
            if is_claim_script(output.script_pubkey):
                claim_data = extract_claim_data(output.script_pubkey)
                if claim_data:
                    commit_hash, nonce, chosen_numbers = claim_data
                    if commit_hash in self._commit_index:
                        self._commit_index[commit_hash].claim_height = 0
                    return

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

    def _index_commit_tx(self, tx, height: int, block_hash: bytes):
        """
        Commit TX 인덱싱 (claim 검증용)

        Commit TX의 OP_RETURN에서 commit_hash 추출 후 인덱스에 저장
        """
        if tx.version != TX_VERSION_COMMIT:
            return

        # OP_RETURN output에서 commit_hash 추출
        for output in tx.outputs:
            if is_commit_script(output.script_pubkey):
                commit_hash = extract_commit_hash(output.script_pubkey)
                if commit_hash:
                    self._commit_index[commit_hash] = CommitInfo(
                        tx_id=tx.get_txid(),
                        block_height=height,
                        block_hash=block_hash
                    )
                    return

    def _unindex_commit_tx(self, tx):
        """
        Commit TX 인덱스 제거 (reorg 시)
        """
        if tx.version != TX_VERSION_COMMIT:
            return

        for output in tx.outputs:
            if is_commit_script(output.script_pubkey):
                commit_hash = extract_commit_hash(output.script_pubkey)
                if commit_hash and commit_hash in self._commit_index:
                    del self._commit_index[commit_hash]
                    return

    def _index_claim_tx(self, tx, height: int):
        """
        Claim TX 인덱싱 - 해당 commit의 claim_height 업데이트
        """
        if tx.version != TX_VERSION_CLAIM:
            return

        for output in tx.outputs:
            if is_claim_script(output.script_pubkey):
                claim_data = extract_claim_data(output.script_pubkey)
                if claim_data:
                    commit_hash, nonce, chosen_numbers = claim_data
                    # 해당 commit의 claim_height 업데이트
                    if commit_hash in self._commit_index:
                        self._commit_index[commit_hash].claim_height = height
                    return

    def pop_disconnected_txs(self) -> list:
        """Reorg 시 disconnect된 TX 목록 반환 및 초기화 (mempool 복원용)"""
        txs = self._disconnected_txs
        self._disconnected_txs = []
        return txs

    def get_commit_info(self, commit_hash: bytes) -> Optional[CommitInfo]:
        """
        Commit 정보 조회 (claim 검증용)

        Args:
            commit_hash: Commit TX의 commit_hash

        Returns:
            CommitInfo or None
        """
        return self._commit_index.get(commit_hash)

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

    def get_block_locator(self) -> List[bytes]:
        """
        Block locator 생성 (GETBLOCKS용)

        최근 블록들의 해시를 반환. 비트코인과 유사하게:
        - 최근 10개는 연속
        - 이후로는 2배씩 간격 증가
        """
        locator = []
        height = self.get_height()

        step = 1
        while height >= 0:
            if height in self._height_to_hash:
                locator.append(self._height_to_hash[height])

            if len(locator) >= 10:
                step *= 2

            height -= step

            # 최대 32개
            if len(locator) >= 32:
                break

        return locator

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
