"""
Step 7.1: 잭팟 풀 관리
- 수수료 30% 누적
- 당첨 시 60% 지급
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import deque

from ..constants import (
    GACHA_PAYOUT_RATIO,
    FEE_JACKPOT_RATIO,
    ASSET_ID_JACK,
)


@dataclass
class PoolTransaction:
    """풀 입출금 기록"""
    block_height: int
    tx_id: bytes
    amount: int           # 양수: 입금, 음수: 출금
    tx_type: str          # "fee", "payout", "initial"


class JackpotPool:
    """
    잭팟 풀 관리

    입금:
    - 블록 수수료의 30%

    출금:
    - 가챠 당첨 시 풀의 60%
    """

    def __init__(self, initial_balance: int = 0):
        self._balance = initial_balance
        self._history: deque = deque(maxlen=1000)  # 최근 1000개 기록

        if initial_balance > 0:
            self._history.append(PoolTransaction(
                block_height=0,
                tx_id=bytes(32),
                amount=initial_balance,
                tx_type="initial"
            ))

    @property
    def balance(self) -> int:
        """현재 잔액"""
        return self._balance

    def add_fee(self, amount: int, block_height: int, tx_id: bytes = None):
        """수수료 입금"""
        if amount <= 0:
            return

        self._balance += amount
        self._history.append(PoolTransaction(
            block_height=block_height,
            tx_id=tx_id or bytes(32),
            amount=amount,
            tx_type="fee"
        ))

    def calculate_payout(self) -> int:
        """당첨 시 지급액 계산"""
        return int(self._balance * GACHA_PAYOUT_RATIO)

    def process_payout(self, block_height: int, tx_id: bytes) -> int:
        """
        당첨 처리 (출금)

        Returns:
            지급 금액
        """
        payout = self.calculate_payout()

        if payout > 0:
            self._balance -= payout
            self._history.append(PoolTransaction(
                block_height=block_height,
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

    def get_history(self, limit: int = 100) -> List[PoolTransaction]:
        """최근 기록 조회"""
        return list(self._history)[-limit:]

    def get_stats(self) -> dict:
        """풀 통계"""
        total_fees = sum(tx.amount for tx in self._history if tx.tx_type == "fee")
        total_payouts = sum(-tx.amount for tx in self._history if tx.tx_type == "payout")
        payout_count = sum(1 for tx in self._history if tx.tx_type == "payout")

        return {
            'balance': self._balance,
            'total_fees_collected': total_fees,
            'total_payouts': total_payouts,
            'payout_count': payout_count,
            'next_payout': self.calculate_payout(),
            'history_size': len(self._history),
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
    return int(block_fees * FEE_JACKPOT_RATIO)
