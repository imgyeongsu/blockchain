"""
Step 2.3: UTXO 관리
- UTXO (Unspent Transaction Output)
- UTXOSet (전체 UTXO 관리)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import struct

from .transaction import Transaction, TxOutput


@dataclass
class UTXO:
    """단일 UTXO"""
    tx_id: bytes              # 트랜잭션 ID (32 bytes)
    output_index: int         # 출력 인덱스
    output: TxOutput          # 실제 출력 데이터
    block_height: int = 0     # 포함된 블록 높이 (Coinbase 성숙도 체크용)
    is_coinbase: bool = False # Coinbase 여부

    def get_outpoint(self) -> Tuple[bytes, int]:
        """UTXO 식별자 (tx_id, output_index)"""
        return (self.tx_id, self.output_index)

    def get_outpoint_key(self) -> bytes:
        """직렬화된 outpoint (저장용)"""
        return self.tx_id + struct.pack('<I', self.output_index)

    @classmethod
    def from_outpoint_key(cls, key: bytes) -> Tuple[bytes, int]:
        """outpoint key 파싱"""
        tx_id = key[:32]
        output_index = struct.unpack('<I', key[32:36])[0]
        return tx_id, output_index

    def is_mature(self, current_height: int, coinbase_maturity: int = 100) -> bool:
        """
        Coinbase UTXO 성숙도 체크
        - Coinbase TX 출력은 100블록 후에야 사용 가능
        """
        if not self.is_coinbase:
            return True
        return (current_height - self.block_height) >= coinbase_maturity


class UTXOSet:
    """
    전체 UTXO 집합 관리
    - 메모리 기반 (MVP)
    - 추후 LevelDB 등으로 교체 가능
    """

    def __init__(self):
        # key: (tx_id, output_index), value: UTXO
        self._utxos: Dict[Tuple[bytes, int], UTXO] = {}
        # 주소별 UTXO 인덱스 (빠른 조회용)
        self._by_address: Dict[str, Set[Tuple[bytes, int]]] = {}

    def add_utxo(self, utxo: UTXO, address: str = None):
        """UTXO 추가"""
        outpoint = utxo.get_outpoint()
        self._utxos[outpoint] = utxo

        if address:
            if address not in self._by_address:
                self._by_address[address] = set()
            self._by_address[address].add(outpoint)

    def remove_utxo(self, tx_id: bytes, output_index: int) -> Optional[UTXO]:
        """UTXO 제거 (소비됨)"""
        outpoint = (tx_id, output_index)
        utxo = self._utxos.pop(outpoint, None)

        if utxo:
            # 주소 인덱스에서도 제거
            for address, outpoints in self._by_address.items():
                if outpoint in outpoints:
                    outpoints.discard(outpoint)
                    break

        return utxo

    def get_utxo(self, tx_id: bytes, output_index: int) -> Optional[UTXO]:
        """UTXO 조회"""
        return self._utxos.get((tx_id, output_index))

    def has_utxo(self, tx_id: bytes, output_index: int) -> bool:
        """UTXO 존재 여부"""
        return (tx_id, output_index) in self._utxos

    def get_utxos_for_address(self, address: str) -> list:
        """특정 주소의 모든 UTXO"""
        outpoints = self._by_address.get(address, set())
        return [self._utxos[op] for op in outpoints if op in self._utxos]

    def get_all_utxos(self) -> list:
        """모든 UTXO 반환"""
        return list(self._utxos.values())

    def get_pool_utxos(self) -> list:
        """잭팟 풀 UTXO 반환"""
        return [
            utxo for utxo in self._utxos.values()
            if utxo.output.script_pubkey == b'JACKPOT_POOL'
        ]

    def get_balance(self, address: str, current_height: int = 0) -> int:
        """주소의 잔액 (성숙한 UTXO만)"""
        utxos = self.get_utxos_for_address(address)
        return sum(
            utxo.output.jack_value
            for utxo in utxos
            if utxo.is_mature(current_height)
        )

    def get_asset_balance(self, address: str, asset_id: str, current_height: int = 0) -> int:
        """주소의 특정 자산 잔액"""
        utxos = self.get_utxos_for_address(address)
        return sum(
            utxo.output.assets.get(asset_id, 0)
            for utxo in utxos
            if utxo.is_mature(current_height)
        )

    def apply_transaction(
        self,
        tx: Transaction,
        block_height: int,
        get_address_from_script: callable = None
    ) -> List['UTXO']:
        """
        트랜잭션 적용 (UTXO 업데이트)
        - 입력의 UTXO 제거
        - 출력을 새 UTXO로 추가

        Returns:
            spent_utxos: 소비된 UTXO 목록 (Reorg 시 복원용)
        """
        tx_id = tx.get_txid()
        is_coinbase = tx.is_coinbase()
        spent_utxos: List[UTXO] = []

        # 입력 처리 (Coinbase 제외)
        if not is_coinbase:
            for inp in tx.inputs:
                # 제거 전에 UTXO 저장 (undo용)
                spent = self.remove_utxo(inp.prev_tx_id, inp.output_index)
                if spent:
                    spent_utxos.append(spent)

        # 출력 처리
        for idx, out in enumerate(tx.outputs):
            utxo = UTXO(
                tx_id=tx_id,
                output_index=idx,
                output=out,
                block_height=block_height,
                is_coinbase=is_coinbase
            )

            # 주소 추출 (script_pubkey 파싱)
            address = None
            if get_address_from_script:
                address = get_address_from_script(out.script_pubkey)

            self.add_utxo(utxo, address)

        return spent_utxos

    def revert_transaction(
        self,
        tx: Transaction,
        spent_utxos: list,
        get_address_from_script: callable = None
    ):
        """
        트랜잭션 되돌리기 (재조직 시)
        - 출력 UTXO 제거
        - 입력 UTXO 복원
        """
        tx_id = tx.get_txid()

        # 출력 제거
        for idx in range(len(tx.outputs)):
            self.remove_utxo(tx_id, idx)

        # 입력 복원
        for utxo in spent_utxos:
            address = None
            if get_address_from_script:
                address = get_address_from_script(utxo.output.script_pubkey)
            self.add_utxo(utxo, address)

    def total_supply(self) -> int:
        """전체 JACK 공급량"""
        return sum(utxo.output.jack_value for utxo in self._utxos.values())

    def utxo_count(self) -> int:
        """UTXO 개수"""
        return len(self._utxos)

    def clear(self):
        """초기화"""
        self._utxos.clear()
        self._by_address.clear()

    def __len__(self):
        return len(self._utxos)

    def __iter__(self):
        return iter(self._utxos.values())
