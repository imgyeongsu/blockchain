"""
잭팟 풀 관리 (16-2 Final 기준)

참가비 분배:
- 80% → 잭팟 풀 적립
- 19% → 소각 (디플레이션)
- 1% → 채굴자 보상

보상 지급:
- 1등: Commit 시점 풀 잔액의 50%
- 2~5등: 고정 JACK 보상
- 6등: 1 POT 재지급
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import deque

from ..constants import (
    LOTTO_PRIZE_1ST_PERCENT,
    LOTTO_POOL_PERCENT,
    LOTTO_BURN_PERCENT,
    LOTTO_COST_JACK,
    FEE_JACKPOT_PERCENT,
    COIN,
)


@dataclass
class PoolTransaction:
    """풀 입출금 기록"""
    block_height: int
    tx_id: bytes
    amount: int           # 양수: 입금, 음수: 출금
    tx_type: str          # "entry", "fee", "payout", "initial", "revert"


@dataclass
class EntryDistribution:
    """참가비 분배 결과"""
    pool_amount: int      # 풀 적립 (80%)
    burn_amount: int      # 소각 (19%)
    miner_amount: int     # 채굴자 (1%)


class JackpotPool:
    """
    잭팟 풀 관리 (16-2 Final)

    입금:
    - 로또 참가비의 80% (100 JACK 중 80 JACK)
    - 블록 수수료의 30% (기존 유지)

    출금:
    - 1등 당첨 시: Commit 시점 풀 잔액의 50%
    """

    def __init__(self, initial_balance: int = 0):
        self._balance = initial_balance
        self._history: deque = deque(maxlen=1000)  # 최근 1000개 기록
        self._snapshots: Dict[int, int] = {}  # block_height -> balance (스냅샷)

        if initial_balance > 0:
            self._history.append(PoolTransaction(
                block_height=0,
                tx_id=bytes(32),
                amount=initial_balance,
                tx_type="initial"
            ))
            self._snapshots[0] = initial_balance

    @property
    def balance(self) -> int:
        """현재 잔액"""
        return self._balance

    def process_entry(
        self,
        entry_amount: int,
        block_height: int,
        tx_id: bytes = None
    ) -> EntryDistribution:
        """
        로또 참가비 처리

        Args:
            entry_amount: 참가비 (기본 100 JACK)
            block_height: 블록 높이
            tx_id: 트랜잭션 ID

        Returns:
            EntryDistribution: 분배 결과
        """
        pool_amount = entry_amount * LOTTO_POOL_PERCENT // 100
        burn_amount = entry_amount * LOTTO_BURN_PERCENT // 100
        miner_amount = entry_amount - pool_amount - burn_amount  # 나머지

        if pool_amount > 0:
            self._balance += pool_amount
            self._history.append(PoolTransaction(
                block_height=block_height,
                tx_id=tx_id or bytes(32),
                amount=pool_amount,
                tx_type="entry"
            ))

        return EntryDistribution(
            pool_amount=pool_amount,
            burn_amount=burn_amount,
            miner_amount=miner_amount
        )

    def add_fee(self, amount: int, block_height: int, tx_id: bytes = None):
        """수수료 입금 (기존 호환)"""
        if amount <= 0:
            return

        self._balance += amount
        self._history.append(PoolTransaction(
            block_height=block_height,
            tx_id=tx_id or bytes(32),
            amount=amount,
            tx_type="fee"
        ))

    def take_snapshot(self, block_height: int):
        """
        블록 높이 시점 잔액 스냅샷 저장

        Commit TX가 블록에 포함될 때 호출하여
        1등 보상 계산 기준 저장
        """
        self._snapshots[block_height] = self._balance

    def get_snapshot(self, block_height: int) -> int:
        """
        특정 블록 높이 시점 잔액 조회

        Args:
            block_height: Commit 블록 높이

        Returns:
            해당 시점 잔액 (없으면 현재 잔액)
        """
        # 정확한 높이 스냅샷이 있으면 반환
        if block_height in self._snapshots:
            return self._snapshots[block_height]

        # 없으면 가장 가까운 이전 스냅샷 찾기
        valid_heights = [h for h in self._snapshots.keys() if h <= block_height]
        if valid_heights:
            closest = max(valid_heights)
            return self._snapshots[closest]

        # 스냅샷이 전혀 없으면 현재 잔액
        return self._balance

    def calculate_jackpot_payout(self, commit_height: int) -> int:
        """
        1등 당첨금 계산

        Args:
            commit_height: Commit 블록 높이

        Returns:
            당첨금 (Commit 시점 잔액의 50%)
        """
        snapshot = self.get_snapshot(commit_height)
        return snapshot * LOTTO_PRIZE_1ST_PERCENT // 100

    def process_jackpot_payout(
        self,
        commit_height: int,
        claim_height: int,
        tx_id: bytes
    ) -> int:
        """
        1등 당첨 처리 (출금)

        Args:
            commit_height: Commit 블록 높이 (스냅샷 기준)
            claim_height: Claim 블록 높이 (기록용)
            tx_id: Claim TX ID

        Returns:
            지급 금액
        """
        payout = self.calculate_jackpot_payout(commit_height)

        if payout > 0 and payout <= self._balance:
            self._balance -= payout
            self._history.append(PoolTransaction(
                block_height=claim_height,
                tx_id=tx_id,
                amount=-payout,
                tx_type="payout"
            ))

        return payout

    def revert_payout(self, amount: int, block_height: int, tx_id: bytes):
        """지급 취소 (재조직 시)"""
        self._balance += amount
        self._history.append(PoolTransaction(
            block_height=block_height,
            tx_id=tx_id,
            amount=amount,
            tx_type="revert"
        ))

    def cleanup_old_snapshots(self, current_height: int, keep_blocks: int = 100):
        """
        오래된 스냅샷 정리

        Args:
            current_height: 현재 블록 높이
            keep_blocks: 유지할 최근 블록 수
        """
        cutoff = current_height - keep_blocks
        old_heights = [h for h in self._snapshots.keys() if h < cutoff]
        for h in old_heights:
            del self._snapshots[h]

    def get_history(self, limit: int = 100) -> List[PoolTransaction]:
        """최근 기록 조회"""
        return list(self._history)[-limit:]

    def get_stats(self) -> dict:
        """풀 통계"""
        total_entries = sum(tx.amount for tx in self._history if tx.tx_type == "entry")
        total_fees = sum(tx.amount for tx in self._history if tx.tx_type == "fee")
        total_payouts = sum(-tx.amount for tx in self._history if tx.tx_type == "payout")
        payout_count = sum(1 for tx in self._history if tx.tx_type == "payout")

        return {
            'balance': self._balance,
            'total_entries': total_entries,
            'total_fees_collected': total_fees,
            'total_payouts': total_payouts,
            'payout_count': payout_count,
            'next_jackpot': self._balance * LOTTO_PRIZE_1ST_PERCENT // 100,
            'history_size': len(self._history),
            'snapshot_count': len(self._snapshots),
        }

    def serialize(self) -> bytes:
        """직렬화 (저장용)"""
        import struct
        return struct.pack('<Q', self._balance)

    @classmethod
    def deserialize(cls, data: bytes) -> 'JackpotPool':
        """역직렬화"""
        import struct
        balance = struct.unpack('<Q', data[:8])[0]
        return cls(initial_balance=balance)


def calculate_pool_contribution(block_fees: int) -> int:
    """블록 수수료에서 풀 기여분 계산"""
    return block_fees * FEE_JACKPOT_PERCENT // 100


def calculate_entry_distribution(entry_amount: int = None) -> EntryDistribution:
    """
    참가비 분배 계산 (유틸리티)

    Args:
        entry_amount: 참가비 (기본 100 JACK)

    Returns:
        EntryDistribution
    """
    if entry_amount is None:
        entry_amount = LOTTO_COST_JACK

    pool_amount = entry_amount * LOTTO_POOL_PERCENT // 100
    burn_amount = entry_amount * LOTTO_BURN_PERCENT // 100
    miner_amount = entry_amount - pool_amount - burn_amount

    return EntryDistribution(
        pool_amount=pool_amount,
        burn_amount=burn_amount,
        miner_amount=miner_amount
    )


# =============================================================================
# 하위 호환 (deprecated)
# =============================================================================

def calculate_payout(pool_balance: int) -> int:
    """
    [DEPRECATED] 기존 단일 당첨금 방식
    새 코드에서는 calculate_jackpot_payout() 사용
    """
    return pool_balance * LOTTO_PRIZE_1ST_PERCENT // 100
