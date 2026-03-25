"""
가챠 서비스 레이어 (자동 지급 방식)

- Commit TX 생성 지원
- 이벤트 훅
- 지갑 연동
"""

import os
import json
import time
import struct
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Callable, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

from ..crypto.hash import sha256
from ..crypto.signature import sign
from ..crypto.address import address_to_pubkey_hash, pubkey_to_address
from ..core.transaction import Transaction, TxInput, TxOutput
from ..core.utxo import UTXO, UTXOSet
from ..script.standard import (
    create_p2pkh_script_pubkey,
    create_p2pkh_script_sig,
    create_commit_script,
)
from ..constants import (
    TX_VERSION_GACHA_COMMIT,
    LOTTO_COST_POT,
    LOTTO_DIGIT_COUNT,
    LOTTO_DIGIT_BASE,
    ASSET_ID_POT,
    ASSET_ID_JACK,
    MIN_TX_FEE,
)
from .commit_reveal import generate_commit
from .pool import JackpotPool
from .game import GachaGame, GachaPlayResult, LottoPlayResult, LottoGame
from .commit_reveal import LottoPrize


# =============================================================================
# 이벤트 시스템
# =============================================================================

class GachaEvent(Enum):
    """가챠 이벤트 타입"""
    COMMIT_CREATED = "commit_created"
    COMMIT_BROADCAST = "commit_broadcast"
    WIN = "win"
    LOSE = "lose"
    PAYOUT = "payout"
    ERROR = "error"


@dataclass
class GachaEventData:
    """이벤트 데이터"""
    event: GachaEvent
    timestamp: float = field(default_factory=time.time)
    address: str = ""
    commit_hash: str = ""
    tx_id: str = ""
    target: int = 0
    winning_slot: int = 0
    payout: int = 0
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class GachaEventEmitter:
    """이벤트 발행기"""

    def __init__(self):
        self._listeners: Dict[GachaEvent, List[Callable]] = {}
        self._global_listeners: List[Callable] = []

    def on(self, event: GachaEvent, callback: Callable):
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(callback)

    def on_all(self, callback: Callable):
        self._global_listeners.append(callback)

    def off(self, event: GachaEvent, callback: Callable):
        if event in self._listeners:
            self._listeners[event].remove(callback)

    def emit(self, data: GachaEventData):
        if data.event in self._listeners:
            for cb in self._listeners[data.event]:
                try:
                    cb(data)
                except Exception as e:
                    print(f"[GachaEvent] Listener error: {e}")
        for cb in self._global_listeners:
            try:
                cb(data)
            except Exception as e:
                print(f"[GachaEvent] Global listener error: {e}")


# =============================================================================
# 가챠 타입 인터페이스
# =============================================================================

@dataclass
class GachaConfig:
    """가챠 설정"""
    name: str = "default"
    cost_pot: int = LOTTO_COST_POT
    slots: int = 100
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'GachaConfig':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class GachaType(ABC):
    """가챠 타입 인터페이스"""

    @property
    @abstractmethod
    def type_id(self) -> str:
        pass

    @property
    @abstractmethod
    def config(self) -> GachaConfig:
        pass


class StandardGacha(GachaType):
    """기본 로또"""

    def __init__(self, config: GachaConfig = None):
        self._config = config or GachaConfig(name="lotto")

    @property
    def type_id(self) -> str:
        return "lotto"

    @property
    def config(self) -> GachaConfig:
        return self._config


# =============================================================================
# PendingCommit
# =============================================================================

@dataclass
class PendingCommit:
    """대기 중인 Commit"""
    commit_hash: bytes          # 미사용 (호환용)
    nonce: bytes                # 미사용 (호환용)
    chosen_numbers: List[int]
    address: str
    created_at: float
    tx_id: bytes = b''
    block_height: int = 0
    pool_snapshot: int = 0
    gacha_type: str = "lotto"
    target: int = 0

    def to_dict(self) -> dict:
        return {
            'commit_hash': self.commit_hash.hex(),
            'nonce': self.nonce.hex(),
            'chosen_numbers': self.chosen_numbers,
            'address': self.address,
            'created_at': self.created_at,
            'tx_id': self.tx_id.hex() if self.tx_id else '',
            'block_height': self.block_height,
            'pool_snapshot': self.pool_snapshot,
            'gacha_type': self.gacha_type,
            'target': self.target,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PendingCommit':
        return cls(
            commit_hash=bytes.fromhex(data['commit_hash']),
            nonce=bytes.fromhex(data['nonce']),
            chosen_numbers=data.get('chosen_numbers', []),
            address=data['address'],
            created_at=data['created_at'],
            tx_id=bytes.fromhex(data['tx_id']) if data.get('tx_id') else b'',
            block_height=data.get('block_height', 0),
            pool_snapshot=data.get('pool_snapshot', 0),
            gacha_type=data.get('gacha_type', 'lotto'),
            target=data.get('target', 0),
        )


# =============================================================================
# 가챠 서비스
# =============================================================================

class GachaService:
    """가챠 서비스 (자동 지급 방식)"""

    def __init__(self, game: GachaGame = None, data_dir: str = None):
        self.game = game or GachaGame()
        self.events = GachaEventEmitter()
        self._gacha_types: Dict[str, GachaType] = {}
        self._register_default_types()
        self._pending_commits: Dict[str, List[PendingCommit]] = {}
        self._reserved_utxos: Dict[Tuple[bytes, int], bytes] = {}
        self._data_dir = Path(data_dir) if data_dir else None
        if self._data_dir:
            self._load_state()

    def _register_default_types(self):
        self.register_gacha_type(StandardGacha())

    def register_gacha_type(self, gacha_type: GachaType):
        self._gacha_types[gacha_type.type_id] = gacha_type

    def get_gacha_type(self, type_id: str) -> Optional[GachaType]:
        return self._gacha_types.get(type_id)

    def list_gacha_types(self) -> List[dict]:
        return [
            {'type_id': gt.type_id, 'config': gt.config.to_dict()}
            for gt in self._gacha_types.values()
            if gt.config.enabled
        ]

    # =========================================================================
    # Commit 생성
    # =========================================================================

    def create_commit(
        self,
        wallet,
        utxo_set: UTXOSet,
        current_height: int,
        chosen_numbers: List[int] = None,
        target: int = None,
        gacha_type: str = "lotto",
        is_spent_in_mempool: Callable[[bytes, int], bool] = None,
        mempool=None,
        from_address: str = None,
    ) -> Tuple[Optional[Transaction], Optional[PendingCommit], str]:
        """Commit TX 생성"""
        if chosen_numbers is not None:
            if len(chosen_numbers) != LOTTO_DIGIT_COUNT:
                return None, None, f"Must choose exactly {LOTTO_DIGIT_COUNT} numbers"
            for d in chosen_numbers:
                if not (0 <= d < LOTTO_DIGIT_BASE):
                    return None, None, f"Each number must be 0-{LOTTO_DIGIT_BASE - 1}"
        else:
            chosen_numbers = [
                int.from_bytes(os.urandom(1), 'big') % LOTTO_DIGIT_BASE
                for _ in range(LOTTO_DIGIT_COUNT)
            ]

        # POT UTXO 선택 (mempool에서 사용 중인 UTXO 제외, 미확인 잔돈 포함)
        pot_utxos = self._select_pot_utxos(wallet, utxo_set, LOTTO_COST_POT, current_height, is_spent_in_mempool, mempool, from_address)
        if not pot_utxos:
            return None, None, f"Insufficient POT balance (need {LOTTO_COST_POT / 1e8} POT)"

        # TX 입력/출력 생성
        inputs = []
        total_jack = 0
        total_pot = 0

        for utxo in pot_utxos:
            inp = TxInput(
                prev_tx_id=utxo.tx_id,
                output_index=utxo.output_index,
                script_sig=b'',
                sequence=0xFFFFFFFF
            )
            inputs.append((inp, utxo))
            total_jack += utxo.output.jack_value
            total_pot += utxo.output.assets.get(ASSET_ID_POT, 0)

        if total_jack < MIN_TX_FEE:
            jack_utxos = self._select_jack_utxos(wallet, utxo_set, MIN_TX_FEE, current_height, is_spent_in_mempool, mempool, from_address)
            for utxo in jack_utxos:
                inp = TxInput(
                    prev_tx_id=utxo.tx_id,
                    output_index=utxo.output_index,
                    script_sig=b'',
                    sequence=0xFFFFFFFF
                )
                inputs.append((inp, utxo))
                total_jack += utxo.output.jack_value

        outputs = []

        # 1. Commit OP_RETURN (숫자 평문)
        outputs.append(TxOutput(
            jack_value=0,
            script_pubkey=create_commit_script(chosen_numbers)
        ))

        # 2. POT 잔돈
        pot_change = total_pot - LOTTO_COST_POT
        if pot_change > 0:
            change_addr = from_address or wallet.get_change_address()
            outputs.append(TxOutput(
                jack_value=0,
                script_pubkey=create_p2pkh_script_pubkey(address_to_pubkey_hash(change_addr)),
                assets={ASSET_ID_POT: pot_change}
            ))

        # 3. JACK 잔돈
        jack_change = total_jack - MIN_TX_FEE
        if jack_change > 0:
            change_addr = from_address or wallet.get_change_address()
            outputs.append(TxOutput(
                jack_value=jack_change,
                script_pubkey=create_p2pkh_script_pubkey(address_to_pubkey_hash(change_addr))
            ))

        tx = Transaction(
            version=TX_VERSION_GACHA_COMMIT,
            inputs=[inp for inp, _ in inputs],
            outputs=outputs,
            locktime=0
        )

        # 서명
        for i, (inp, utxo) in enumerate(inputs):
            address = self._get_utxo_address(utxo)
            if address and address in wallet._addresses:
                info = wallet._addresses[address]
                sig_hash = tx.get_signature_hash(i, utxo.output.script_pubkey)
                signature = sign(sig_hash, info.private_key)
                tx.inputs[i].script_sig = create_p2pkh_script_sig(signature, info.public_key)

        # PendingCommit
        addresses = wallet.get_addresses()
        player_address = addresses[0] if addresses else ""
        pool_snapshot = self.game.pool.balance if self.game else 0

        pending = PendingCommit(
            commit_hash=b'\x00' * 32,  # 미사용
            nonce=b'\x00' * 32,        # 미사용
            chosen_numbers=chosen_numbers,
            address=player_address,
            created_at=time.time(),
            tx_id=tx.get_txid(),
            pool_snapshot=pool_snapshot,
            gacha_type=gacha_type
        )

        self._add_pending_commit(player_address, pending)

        used_utxos = [utxo for _, utxo in inputs]
        self._reserve_utxos(used_utxos, pending.commit_hash)

        self.events.emit(GachaEventData(
            event=GachaEvent.COMMIT_CREATED,
            address=player_address,
            metadata={'chosen_numbers': chosen_numbers}
        ))

        return tx, pending, ""

    # =========================================================================
    # 상태 관리
    # =========================================================================

    def get_pending_commits(self, address: str = None) -> List[PendingCommit]:
        if address:
            return self._pending_commits.get(address, [])
        all_commits = []
        for commits in self._pending_commits.values():
            all_commits.extend(commits)
        return all_commits

    def update_commit_status(self, commit_hash: bytes, tx_id: bytes, block_height: int):
        pending = self._find_pending_commit_by_txid(tx_id)
        if pending:
            pending.tx_id = tx_id
            pending.block_height = block_height
            self._save_state()

    def remove_commit(self, commit_hash: bytes):
        for address, commits in self._pending_commits.items():
            for commit in commits:
                if commit.commit_hash == commit_hash:
                    commits.remove(commit)
                    self._save_state()
                    return

    def cancel_pending_commit(self, commit_hash: bytes):
        self.release_reserved_utxos(commit_hash)
        self.remove_commit(commit_hash)

    def get_stats(self) -> dict:
        game_stats = self.game.get_stats()
        return {
            **game_stats,
            'gacha_types': list(self._gacha_types.keys()),
            'pending_commits_total': sum(len(c) for c in self._pending_commits.values()),
        }

    # =========================================================================
    # 유틸리티
    # =========================================================================

    def _is_utxo_reserved(self, utxo: UTXO) -> bool:
        key = (utxo.tx_id, utxo.output_index)
        return key in self._reserved_utxos

    def _reserve_utxos(self, utxos: List[UTXO], commit_hash: bytes):
        for utxo in utxos:
            key = (utxo.tx_id, utxo.output_index)
            self._reserved_utxos[key] = commit_hash

    def release_reserved_utxos(self, commit_hash: bytes):
        to_remove = [k for k, v in self._reserved_utxos.items() if v == commit_hash]
        for key in to_remove:
            del self._reserved_utxos[key]

    def _select_pot_utxos(self, wallet, utxo_set, amount, current_height,
                          is_spent_in_mempool: Callable[[bytes, int], bool] = None,
                          mempool=None, from_address: str = None) -> List[UTXO]:
        from ..script.standard import get_address_from_script_pubkey

        # 확정 UTXO + mempool 미확인 잔돈 합치기
        utxos = wallet.get_utxos(utxo_set)
        if mempool:
            addresses = set(wallet._addresses)
            unconfirmed = mempool.get_unconfirmed_utxos(addresses, get_address_from_script_pubkey)
            # 확정 UTXO와 중복 제거
            confirmed_outpoints = {(u.tx_id, u.output_index) for u in utxos}
            for u in unconfirmed:
                if (u.tx_id, u.output_index) not in confirmed_outpoints:
                    utxos.append(u)

        # from_address 지정 시 해당 주소 UTXO만 필터
        if from_address:
            utxos = [u for u in utxos if get_address_from_script_pubkey(u.output.script_pubkey) == from_address]

        pot_utxos = []
        total = 0
        for utxo in utxos:
            if not utxo.is_mature(current_height):
                continue
            if self._is_utxo_reserved(utxo):
                continue
            # mempool에서 이미 사용 중인 UTXO 제외
            if is_spent_in_mempool and is_spent_in_mempool(utxo.tx_id, utxo.output_index):
                continue
            pot_amount = utxo.output.assets.get(ASSET_ID_POT, 0)
            if pot_amount > 0:
                pot_utxos.append(utxo)
                total += pot_amount
                if total >= amount:
                    break
        return pot_utxos if total >= amount else []

    def _select_jack_utxos(self, wallet, utxo_set, amount, current_height,
                           is_spent_in_mempool: Callable[[bytes, int], bool] = None,
                           mempool=None, from_address: str = None) -> List[UTXO]:
        from ..script.standard import get_address_from_script_pubkey

        utxos = wallet.get_utxos(utxo_set)
        if mempool:
            addresses = set(wallet._addresses)
            unconfirmed = mempool.get_unconfirmed_utxos(addresses, get_address_from_script_pubkey)
            confirmed_outpoints = {(u.tx_id, u.output_index) for u in utxos}
            for u in unconfirmed:
                if (u.tx_id, u.output_index) not in confirmed_outpoints:
                    utxos.append(u)

        # from_address 지정 시 해당 주소 UTXO만 필터
        if from_address:
            utxos = [u for u in utxos if get_address_from_script_pubkey(u.output.script_pubkey) == from_address]

        jack_utxos = []
        total = 0
        for utxo in utxos:
            if not utxo.is_mature(current_height):
                continue
            if self._is_utxo_reserved(utxo):
                continue
            # mempool에서 이미 사용 중인 UTXO 제외
            if is_spent_in_mempool and is_spent_in_mempool(utxo.tx_id, utxo.output_index):
                continue
            if utxo.output.jack_value > 0:
                jack_utxos.append(utxo)
                total += utxo.output.jack_value
                if total >= amount:
                    break
        return jack_utxos if total >= amount else []

    def _get_utxo_address(self, utxo: UTXO) -> Optional[str]:
        from ..script.standard import get_address_from_script_pubkey
        return get_address_from_script_pubkey(utxo.output.script_pubkey)

    def _add_pending_commit(self, address: str, commit: PendingCommit):
        if address not in self._pending_commits:
            self._pending_commits[address] = []
        self._pending_commits[address].append(commit)
        self._save_state()

    def _find_pending_commit(self, commit_hash: bytes) -> Optional[PendingCommit]:
        for commits in self._pending_commits.values():
            for commit in commits:
                if commit.commit_hash == commit_hash:
                    return commit
        return None

    def _find_pending_commit_by_txid(self, tx_id: bytes) -> Optional[PendingCommit]:
        for commits in self._pending_commits.values():
            for commit in commits:
                if commit.tx_id == tx_id:
                    return commit
        return None

    def _save_state(self):
        if not self._data_dir:
            return
        self._data_dir.mkdir(parents=True, exist_ok=True)
        state_file = self._data_dir / "gacha_state.json"
        state = {
            'pending_commits': {
                addr: [c.to_dict() for c in commits]
                for addr, commits in self._pending_commits.items()
            }
        }
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def _load_state(self):
        if not self._data_dir:
            return
        state_file = self._data_dir / "gacha_state.json"
        if not state_file.exists():
            return
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
            self._pending_commits = {
                addr: [PendingCommit.from_dict(c) for c in commits]
                for addr, commits in state.get('pending_commits', {}).items()
            }
        except Exception as e:
            print(f"[GachaService] Failed to load state: {e}")


# =============================================================================
# 팩토리
# =============================================================================

def create_gacha_service(data_dir: str = None, custom_types: List[GachaType] = None) -> GachaService:
    service = GachaService(data_dir=data_dir)
    if custom_types:
        for gt in custom_types:
            service.register_gacha_type(gt)
    return service
