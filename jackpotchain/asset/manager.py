"""
Step 6.1: 멀티 에셋 관리
- JACK: 기본 화폐
- POT: 가챠 토큰
"""

from typing import Dict, Optional
from dataclasses import dataclass, field
from enum import Enum

from ..constants import (
    ASSET_ID_JACK,
    ASSET_ID_POT,
    DECIMALS_JACK,
    DECIMALS_POT,
)


class AssetType(Enum):
    """에셋 타입"""
    JACK = "JACK"  # 기본 화폐
    POT = "POT"    # 가챠 토큰


@dataclass
class AssetInfo:
    """에셋 정보"""
    asset_id: str
    name: str
    symbol: str
    decimals: int
    total_supply: int = 0
    max_supply: Optional[int] = None
    is_native: bool = True
    metadata: Dict = field(default_factory=dict)


# 에셋 레지스트리
ASSET_REGISTRY: Dict[str, AssetInfo] = {
    ASSET_ID_JACK: AssetInfo(
        asset_id=ASSET_ID_JACK,
        name="JackpotCoin",
        symbol="JACK",
        decimals=DECIMALS_JACK,
        max_supply=None,  # 무제한 (인플레이션)
        is_native=True
    ),
    ASSET_ID_POT: AssetInfo(
        asset_id=ASSET_ID_POT,
        name="PotToken",
        symbol="POT",
        decimals=DECIMALS_POT,
        max_supply=None,  # 무제한 (JACK 교환으로 생성)
        is_native=True
    ),
}


def get_asset_info(asset_id: str) -> Optional[AssetInfo]:
    """에셋 정보 조회"""
    return ASSET_REGISTRY.get(asset_id)


def is_valid_asset(asset_id: str) -> bool:
    """유효한 에셋인지"""
    return asset_id in ASSET_REGISTRY


def format_amount(amount: int, asset_id: str) -> str:
    """금액 포맷팅"""
    info = get_asset_info(asset_id)
    if info is None:
        return str(amount)

    divisor = 10 ** info.decimals
    value = amount / divisor
    return f"{value:.{info.decimals}f} {info.symbol}"


def parse_amount(value: str, asset_id: str) -> int:
    """문자열 → satoshi 단위"""
    info = get_asset_info(asset_id)
    if info is None:
        raise ValueError(f"Unknown asset: {asset_id}")

    # "10.5 JACK" 또는 "10.5" 형식 처리
    parts = value.strip().split()
    num_str = parts[0]

    multiplier = 10 ** info.decimals
    if '.' in num_str:
        integer_part, decimal_part = num_str.split('.')
        decimal_part = decimal_part[:info.decimals].ljust(info.decimals, '0')
        return int(integer_part) * multiplier + int(decimal_part)
    else:
        return int(num_str) * multiplier


class AssetBalance:
    """주소별 에셋 잔액 관리"""

    def __init__(self):
        # address -> asset_id -> balance
        self._balances: Dict[str, Dict[str, int]] = {}

    def get_balance(self, address: str, asset_id: str = ASSET_ID_JACK) -> int:
        """잔액 조회"""
        if address not in self._balances:
            return 0
        return self._balances[address].get(asset_id, 0)

    def get_all_balances(self, address: str) -> Dict[str, int]:
        """모든 에셋 잔액 조회"""
        return self._balances.get(address, {}).copy()

    def add_balance(self, address: str, asset_id: str, amount: int):
        """잔액 추가"""
        if amount < 0:
            raise ValueError("Amount must be non-negative")

        if address not in self._balances:
            self._balances[address] = {}

        current = self._balances[address].get(asset_id, 0)
        self._balances[address][asset_id] = current + amount

    def subtract_balance(self, address: str, asset_id: str, amount: int) -> bool:
        """잔액 차감 (성공 여부 반환)"""
        if amount < 0:
            raise ValueError("Amount must be non-negative")

        current = self.get_balance(address, asset_id)
        if current < amount:
            return False

        self._balances[address][asset_id] = current - amount
        return True

    def transfer(
        self,
        from_address: str,
        to_address: str,
        asset_id: str,
        amount: int
    ) -> bool:
        """잔액 이체"""
        if not self.subtract_balance(from_address, asset_id, amount):
            return False

        self.add_balance(to_address, asset_id, amount)
        return True

    def clear(self):
        """초기화"""
        self._balances.clear()
