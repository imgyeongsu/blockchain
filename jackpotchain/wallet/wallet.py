"""
Step 13: 지갑
- 키 관리
- 주소 생성
- TX 서명
- 개인키 암호화 (AES-256-GCM)
"""

import os
import json
import time
from typing import Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from ..crypto.signature import generate_keypair, sign, private_key_to_public_key
from ..crypto.address import pubkey_to_address, validate_address
from ..crypto.hash import sha256, double_sha256
from ..crypto.encryption import (
    encrypt_private_key,
    decrypt_private_key,
    is_encryption_available,
)
from ..core.transaction import Transaction, TxInput, TxOutput
from ..core.utxo import UTXO, UTXOSet
from ..script.standard import create_p2pkh_script_pubkey, create_p2pkh_script_sig
from ..constants import MIN_TX_FEE, COIN


@dataclass
class AddressInfo:
    """주소 정보"""
    address: str
    public_key: bytes
    private_key: bytes  # 메모리에서는 복호화된 상태
    label: str = ""
    created_at: float = 0
    is_change: bool = False


@dataclass
class WalletTx:
    """지갑 TX 정보"""
    txid: bytes
    tx: Transaction
    block_hash: Optional[bytes] = None
    block_height: Optional[int] = None
    confirmations: int = 0
    timestamp: float = 0


class Wallet:
    """
    단순 지갑 구현

    기능:
    - 키 생성/관리
    - 잔액 조회
    - TX 생성/서명
    - 개인키 암호화 (AES-256-GCM + PBKDF2)
    """

    def __init__(self, wallet_file: str = None, password: str = None):
        self.wallet_file = Path(wallet_file) if wallet_file else None

        # 주소 → AddressInfo
        self._addresses: Dict[str, AddressInfo] = {}

        # 감시 전용 주소
        self._watch_only: set = set()

        # 거래 내역
        self._transactions: Dict[bytes, WalletTx] = {}

        # 암호화 관련
        self._password: Optional[str] = password
        self._encrypted: bool = False
        self._locked: bool = False

        # 로드
        if self.wallet_file and self.wallet_file.exists():
            self._load()

    def _load(self):
        """지갑 파일 로드"""
        if not self.wallet_file or not self.wallet_file.exists():
            return

        with open(self.wallet_file, 'r') as f:
            data = json.load(f)

        self._encrypted = data.get('encrypted', False)

        for addr_data in data.get('addresses', []):
            # 암호화된 지갑
            if self._encrypted:
                if not self._password:
                    # 잠금 상태 - 공개키만 로드
                    self._locked = True
                    info = AddressInfo(
                        address=addr_data['address'],
                        public_key=bytes.fromhex(addr_data['public_key']),
                        private_key=b'',  # 잠금 상태
                        label=addr_data.get('label', ''),
                        created_at=addr_data.get('created_at', 0),
                        is_change=addr_data.get('is_change', False)
                    )
                else:
                    # 복호화
                    encrypted_key = bytes.fromhex(addr_data['private_key'])
                    try:
                        private_key = decrypt_private_key(encrypted_key, self._password)
                    except ValueError as e:
                        raise ValueError(f"지갑 복호화 실패: {e}")

                    info = AddressInfo(
                        address=addr_data['address'],
                        public_key=bytes.fromhex(addr_data['public_key']),
                        private_key=private_key,
                        label=addr_data.get('label', ''),
                        created_at=addr_data.get('created_at', 0),
                        is_change=addr_data.get('is_change', False)
                    )
            else:
                # 평문 지갑 (하위 호환)
                info = AddressInfo(
                    address=addr_data['address'],
                    public_key=bytes.fromhex(addr_data['public_key']),
                    private_key=bytes.fromhex(addr_data['private_key']),
                    label=addr_data.get('label', ''),
                    created_at=addr_data.get('created_at', 0),
                    is_change=addr_data.get('is_change', False)
                )

            self._addresses[info.address] = info

        self._watch_only = set(data.get('watch_only', []))

    def _save(self):
        """지갑 파일 저장"""
        if not self.wallet_file:
            return

        if self._locked:
            raise RuntimeError("지갑이 잠금 상태입니다. unlock() 후 저장하세요.")

        self.wallet_file.parent.mkdir(parents=True, exist_ok=True)

        addresses_data = []
        for info in self._addresses.values():
            if self._password and is_encryption_available():
                # 암호화하여 저장
                encrypted_key = encrypt_private_key(info.private_key, self._password)
                private_key_hex = encrypted_key.hex()
            else:
                # 평문 저장 (하위 호환)
                private_key_hex = info.private_key.hex()

            addresses_data.append({
                'address': info.address,
                'public_key': info.public_key.hex(),
                'private_key': private_key_hex,
                'label': info.label,
                'created_at': info.created_at,
                'is_change': info.is_change,
            })

        data = {
            'encrypted': bool(self._password and is_encryption_available()),
            'addresses': addresses_data,
            'watch_only': list(self._watch_only),
        }

        with open(self.wallet_file, 'w') as f:
            json.dump(data, f, indent=2)

    def is_encrypted(self) -> bool:
        """지갑이 암호화되어 있는지"""
        return self._encrypted

    def is_locked(self) -> bool:
        """지갑이 잠금 상태인지"""
        return self._locked

    def unlock(self, password: str) -> bool:
        """
        지갑 잠금 해제

        Returns:
            True: 성공, False: 실패
        """
        if not self._encrypted:
            return True  # 암호화 안 된 지갑

        if not self._locked:
            return True  # 이미 잠금 해제됨

        self._password = password
        try:
            self._load()
            self._locked = False
            return True
        except ValueError:
            self._password = None
            return False

    def lock(self):
        """지갑 잠금 (메모리에서 개인키 제거)"""
        if not self._encrypted:
            return

        for info in self._addresses.values():
            info.private_key = b''

        self._password = None
        self._locked = True

    def encrypt_wallet(self, password: str) -> bool:
        """
        기존 지갑 암호화

        Args:
            password: 암호화 비밀번호

        Returns:
            True: 성공
        """
        if not is_encryption_available():
            raise RuntimeError("cryptography 라이브러리가 필요합니다")

        if self._locked:
            raise RuntimeError("지갑이 잠금 상태입니다")

        self._password = password
        self._encrypted = True
        self._save()
        return True

    def change_password(self, old_password: str, new_password: str) -> bool:
        """비밀번호 변경"""
        if not self._encrypted:
            raise RuntimeError("암호화되지 않은 지갑입니다")

        if self._locked:
            if not self.unlock(old_password):
                return False

        self._password = new_password
        self._save()
        return True

    def generate_address(self, label: str = "", is_change: bool = False) -> str:
        """새 주소 생성"""
        private_key, public_key = generate_keypair()
        address = pubkey_to_address(public_key)

        info = AddressInfo(
            address=address,
            public_key=public_key,
            private_key=private_key,
            label=label,
            created_at=time.time(),
            is_change=is_change
        )

        self._addresses[address] = info
        self._save()

        return address

    def import_private_key(self, private_key: bytes, label: str = "") -> str:
        """개인키 가져오기"""
        public_key = private_key_to_public_key(private_key)
        address = pubkey_to_address(public_key)

        if address in self._addresses:
            return address

        info = AddressInfo(
            address=address,
            public_key=public_key,
            private_key=private_key,
            label=label,
            created_at=time.time()
        )

        self._addresses[address] = info
        self._save()

        return address

    def add_watch_only(self, address: str) -> bool:
        """감시 전용 주소 추가"""
        if not validate_address(address):
            return False

        self._watch_only.add(address)
        self._save()
        return True

    def get_addresses(self, include_change: bool = True) -> List[str]:
        """모든 주소 목록"""
        if include_change:
            return list(self._addresses.keys())
        return [a for a, info in self._addresses.items() if not info.is_change]

    def get_change_address(self) -> str:
        """잔돈 주소 (없으면 생성)"""
        for addr, info in self._addresses.items():
            if info.is_change:
                return addr
        return self.generate_address(is_change=True)

    def get_balance(self, utxo_set: UTXOSet, current_height: int = 0) -> int:
        """총 잔액"""
        total = 0
        for address in self._addresses:
            total += utxo_set.get_balance(address, current_height)
        return total

    def get_utxos(self, utxo_set: UTXOSet) -> List[UTXO]:
        """내 UTXO 목록"""
        utxos = []
        for address in self._addresses:
            utxos.extend(utxo_set.get_utxos_for_address(address))
        return utxos

    def select_utxos(
        self,
        utxo_set: UTXOSet,
        amount: int,
        current_height: int = 0,
        is_spent_in_mempool: Callable[[bytes, int], bool] = None
    ) -> Tuple[List[UTXO], int]:
        """
        UTXO 선택

        Args:
            is_spent_in_mempool: mempool에서 UTXO 사용 여부 확인 함수

        Returns:
            (selected_utxos, total_value)
        """
        utxos = self.get_utxos(utxo_set)

        # 성숙한 UTXO만 + mempool 미사용
        mature_utxos = [
            u for u in utxos
            if u.is_mature(current_height)
            and (is_spent_in_mempool is None or not is_spent_in_mempool(u.tx_id, u.output_index))
        ]

        # 금액 순 정렬 (작은 것부터)
        mature_utxos.sort(key=lambda u: u.output.jack_value)

        selected = []
        total = 0

        for utxo in mature_utxos:
            selected.append(utxo)
            total += utxo.output.jack_value
            if total >= amount:
                break

        return selected, total

    def create_transaction(
        self,
        utxo_set: UTXOSet,
        recipients: List[Tuple[str, int]],  # (address, amount)
        fee: int = MIN_TX_FEE,
        current_height: int = 0,
        is_spent_in_mempool: Callable[[bytes, int], bool] = None
    ) -> Tuple[Optional[Transaction], str]:
        """
        TX 생성 및 서명

        Args:
            is_spent_in_mempool: mempool에서 UTXO 사용 여부 확인 함수

        Returns:
            (transaction, error_message)
        """
        if self._locked:
            return None, "지갑이 잠금 상태입니다. unlock() 후 사용하세요."

        # 총 출금액
        total_out = sum(amount for _, amount in recipients) + fee

        # UTXO 선택 (mempool에서 사용 중인 UTXO 제외)
        selected, total_in = self.select_utxos(
            utxo_set, total_out, current_height, is_spent_in_mempool
        )

        if total_in < total_out:
            return None, f"Insufficient funds: {total_in} < {total_out}"

        # 입력 생성 (서명 전)
        inputs = []
        for utxo in selected:
            inp = TxInput(
                prev_tx_id=utxo.tx_id,
                output_index=utxo.output_index,
                script_sig=b'',  # 나중에 서명
                sequence=0xFFFFFFFF
            )
            inputs.append(inp)

        # 출력 생성
        outputs = []
        for address, amount in recipients:
            from ..crypto.address import address_to_pubkey_hash
            pubkey_hash = address_to_pubkey_hash(address)
            script = create_p2pkh_script_pubkey(pubkey_hash)
            outputs.append(TxOutput(jack_value=amount, script_pubkey=script))

        # 잔돈 출력
        change = total_in - total_out
        if change > 0:
            change_address = self.get_change_address()
            from ..crypto.address import address_to_pubkey_hash
            change_pubkey_hash = address_to_pubkey_hash(change_address)
            change_script = create_p2pkh_script_pubkey(change_pubkey_hash)
            outputs.append(TxOutput(jack_value=change, script_pubkey=change_script))

        # TX 생성
        tx = Transaction(
            version=1,
            inputs=inputs,
            outputs=outputs,
            locktime=0
        )

        # 각 입력에 대해 서명
        for i, (inp, utxo) in enumerate(zip(inputs, selected)):
            # 해당 UTXO의 주소에서 키 찾기
            address = self._find_address_for_utxo(utxo, utxo_set)
            if address is None or address not in self._addresses:
                return None, f"Cannot find key for input {i}"

            info = self._addresses[address]

            # 서명 해시 계산 (Bitcoin SIGHASH_ALL 방식)
            sig_hash = tx.get_signature_hash(i, utxo.output.script_pubkey)

            # 서명 (message_hash, private_key 순서)
            signature = sign(sig_hash, info.private_key)
            script_sig = create_p2pkh_script_sig(signature, info.public_key)
            inp.script_sig = script_sig

        return tx, ""

    def _find_address_for_utxo(self, utxo: UTXO, utxo_set: UTXOSet) -> Optional[str]:
        """UTXO의 주소 찾기"""
        from ..script.standard import get_address_from_script_pubkey
        return get_address_from_script_pubkey(utxo.output.script_pubkey)

    def sign_transaction(
        self,
        tx: Transaction,
        utxos: List[UTXO]
    ) -> Tuple[bool, str]:
        """TX 서명"""
        if self._locked:
            return False, "지갑이 잠금 상태입니다"

        for i, (inp, utxo) in enumerate(zip(tx.inputs, utxos)):
            address = self._find_address_for_utxo(utxo, None)
            if address is None or address not in self._addresses:
                return False, f"Cannot find key for input {i}"

            info = self._addresses[address]

            # 서명 해시 계산 (Bitcoin SIGHASH_ALL 방식)
            sig_hash = tx.get_signature_hash(i, utxo.output.script_pubkey)

            signature = sign(sig_hash, info.private_key)
            script_sig = create_p2pkh_script_sig(signature, info.public_key)
            inp.script_sig = script_sig

        return True, ""

    def export_private_key(self, address: str) -> Optional[bytes]:
        """개인키 내보내기"""
        if self._locked:
            return None

        info = self._addresses.get(address)
        return info.private_key if info else None

    def get_info(self) -> dict:
        """지갑 정보"""
        return {
            'addresses': len(self._addresses),
            'watch_only': len(self._watch_only),
            'transactions': len(self._transactions),
            'encrypted': self._encrypted,
            'locked': self._locked,
        }
