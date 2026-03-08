"""
Step 12: Mempool
- 미확인 TX 관리
- 수수료 기반 우선순위
"""

import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from collections import OrderedDict

from ..core.transaction import Transaction
from ..core.utxo import UTXOSet
from ..validation.transaction import validate_transaction
from ..constants import MAX_MEMPOOL_SIZE, MAX_TX_SIZE, MIN_RELAY_FEE


@dataclass
class MempoolEntry:
    """Mempool 항목"""
    tx: Transaction
    fee: int
    fee_rate: float  # satoshi/byte
    size: int
    added_time: float
    height: int  # 추가 시점 높이

    # 의존성
    depends_on: Set[bytes] = field(default_factory=set)
    spent_by: Set[bytes] = field(default_factory=set)


class Mempool:
    """
    미확인 트랜잭션 풀

    기능:
    - TX 추가/제거
    - 수수료 기반 정렬
    - 중복 지출 방지
    """

    def __init__(self, max_size: int = MAX_MEMPOOL_SIZE):
        self.max_size = max_size

        # txid → MempoolEntry
        self._entries: Dict[bytes, MempoolEntry] = {}

        # outpoint → txid (지출 추적)
        self._spent_outpoints: Dict[tuple, bytes] = {}

        # 수수료율 정렬 (높은 순)
        self._by_fee_rate: OrderedDict = OrderedDict()

        # 통계
        self._total_size = 0
        self._total_fee = 0

    def add_tx(
        self,
        tx: Transaction,
        utxo_set: UTXOSet,
        current_height: int
    ) -> tuple:
        """
        TX 추가

        Returns:
            (success, message)
        """
        txid = tx.get_txid()

        # 이미 존재
        if txid in self._entries:
            return False, "TX already in mempool"

        # 크기 검증
        tx_size = len(tx.serialize())
        if tx_size > MAX_TX_SIZE:
            return False, f"TX too large: {tx_size} > {MAX_TX_SIZE}"

        # 검증
        result = validate_transaction(tx, utxo_set, current_height)
        if not result.is_valid:
            return False, f"Invalid TX: {result.message}"

        fee = result.fee

        # 최소 수수료
        fee_rate = fee / tx_size
        if fee < MIN_RELAY_FEE:
            return False, f"Fee too low: {fee} < {MIN_RELAY_FEE}"

        # 중복 지출 확인
        for inp in tx.inputs:
            outpoint = (inp.prev_tx_id, inp.output_index)
            if outpoint in self._spent_outpoints:
                conflicting_txid = self._spent_outpoints[outpoint]
                return False, f"Double spend: conflicts with {conflicting_txid.hex()}"

        # 용량 확인
        if self._total_size + tx_size > self.max_size:
            # 낮은 수수료율 TX 제거
            self._evict_low_fee(tx_size)

        # 의존성 확인 (mempool 내 TX 참조)
        depends_on = set()
        for inp in tx.inputs:
            if inp.prev_tx_id in self._entries:
                depends_on.add(inp.prev_tx_id)

        # 엔트리 생성
        entry = MempoolEntry(
            tx=tx,
            fee=fee,
            fee_rate=fee_rate,
            size=tx_size,
            added_time=time.time(),
            height=current_height,
            depends_on=depends_on
        )

        # 추가
        self._entries[txid] = entry
        self._total_size += tx_size
        self._total_fee += fee

        # 지출 추적
        for inp in tx.inputs:
            outpoint = (inp.prev_tx_id, inp.output_index)
            self._spent_outpoints[outpoint] = txid

        # 의존 TX 업데이트
        for dep_txid in depends_on:
            if dep_txid in self._entries:
                self._entries[dep_txid].spent_by.add(txid)

        # 수수료율 정렬
        self._update_fee_order(txid, fee_rate)

        return True, ""

    def remove_tx(self, txid: bytes, remove_descendants: bool = True) -> List[bytes]:
        """
        TX 제거

        Returns:
            제거된 txid 목록
        """
        removed = []

        if txid not in self._entries:
            return removed

        entry = self._entries.pop(txid)
        removed.append(txid)

        self._total_size -= entry.size
        self._total_fee -= entry.fee

        # 지출 추적 제거
        for inp in entry.tx.inputs:
            outpoint = (inp.prev_tx_id, inp.output_index)
            self._spent_outpoints.pop(outpoint, None)

        # 수수료 정렬에서 제거
        self._by_fee_rate.pop(txid, None)

        # 의존 TX에서 제거
        for dep_txid in entry.depends_on:
            if dep_txid in self._entries:
                self._entries[dep_txid].spent_by.discard(txid)

        # 후손 TX 제거
        if remove_descendants:
            for child_txid in list(entry.spent_by):
                removed.extend(self.remove_tx(child_txid, True))

        return removed

    def remove_confirmed_txs(self, txids: List[bytes]):
        """확인된 TX들 제거"""
        for txid in txids:
            self.remove_tx(txid, remove_descendants=False)

    def get_tx(self, txid: bytes) -> Optional[Transaction]:
        """TX 조회"""
        entry = self._entries.get(txid)
        return entry.tx if entry else None

    def has_tx(self, txid: bytes) -> bool:
        """TX 존재 여부"""
        return txid in self._entries

    def get_txs_for_block(self, max_size: int = 900000) -> List[Transaction]:
        """
        블록에 포함할 TX 선택 (수수료율 순)

        Args:
            max_size: 최대 크기 (바이트)

        Returns:
            선택된 TX 목록
        """
        selected = []
        total_size = 0
        included = set()

        # 수수료율 높은 순으로 정렬
        sorted_entries = sorted(
            self._entries.values(),
            key=lambda e: e.fee_rate,
            reverse=True
        )

        for entry in sorted_entries:
            txid = entry.tx.get_txid()

            # 의존 TX가 모두 포함되어야 함
            if not entry.depends_on.issubset(included):
                continue

            if total_size + entry.size > max_size:
                continue

            selected.append(entry.tx)
            included.add(txid)
            total_size += entry.size

        return selected

    def _evict_low_fee(self, needed_size: int):
        """낮은 수수료율 TX 제거"""
        # 수수료율 낮은 순으로 정렬
        sorted_entries = sorted(
            self._entries.items(),
            key=lambda x: x[1].fee_rate
        )

        freed = 0
        for txid, entry in sorted_entries:
            if freed >= needed_size:
                break
            self.remove_tx(txid)
            freed += entry.size

    def _update_fee_order(self, txid: bytes, fee_rate: float):
        """수수료율 순서 업데이트"""
        self._by_fee_rate[txid] = fee_rate
        # OrderedDict 재정렬
        sorted_items = sorted(self._by_fee_rate.items(), key=lambda x: x[1], reverse=True)
        self._by_fee_rate = OrderedDict(sorted_items)

    def get_stats(self) -> dict:
        """통계"""
        return {
            'size': self._total_size,
            'count': len(self._entries),
            'total_fee': self._total_fee,
            'min_fee_rate': min((e.fee_rate for e in self._entries.values()), default=0),
            'max_fee_rate': max((e.fee_rate for e in self._entries.values()), default=0),
        }

    def get_all_txids(self) -> List[bytes]:
        """모든 txid 반환"""
        return list(self._entries.keys())

    def clear(self):
        """초기화"""
        self._entries.clear()
        self._spent_outpoints.clear()
        self._by_fee_rate.clear()
        self._total_size = 0
        self._total_fee = 0
