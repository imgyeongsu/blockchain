"""
가챠 서비스 레이어 (확장 가능한 구조)

- 플러그인 스타일 가챠 타입 지원
- 이벤트 훅 시스템
- 유연한 설정
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
    create_reveal_script,
)
from ..constants import (
    TX_VERSION_GACHA_COMMIT,
    TX_VERSION_GACHA_REVEAL,
    TX_VERSION_LOTTO_CLAIM,
    GACHA_COST_POT,
    LOTTO_COST_POT,
    GACHA_WIN_PROBABILITY,
    GACHA_PAYOUT_RATIO,
    GACHA_MIN_REVEAL_GAP,
    GACHA_MAX_REVEAL_GAP,
    LOTTO_MIN_CLAIM_GAP,
    LOTTO_MAX_CLAIM_GAP,
    LOTTO_DIGIT_COUNT,
    LOTTO_DIGIT_BASE,
    ASSET_ID_POT,
    ASSET_ID_JACK,
    MIN_TX_FEE,
)
from .commit_reveal import (
    generate_commit,
    verify_commit,
    calculate_winning_slot,
    check_win,
    get_comparison_heights,
    is_claim_valid,
)
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
    REVEAL_CREATED = "reveal_created"
    REVEAL_BROADCAST = "reveal_broadcast"
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
        """이벤트 리스너 등록"""
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(callback)

    def on_all(self, callback: Callable):
        """모든 이벤트 리스너"""
        self._global_listeners.append(callback)

    def off(self, event: GachaEvent, callback: Callable):
        """리스너 제거"""
        if event in self._listeners:
            self._listeners[event].remove(callback)

    def emit(self, data: GachaEventData):
        """이벤트 발행"""
        # 특정 이벤트 리스너
        if data.event in self._listeners:
            for cb in self._listeners[data.event]:
                try:
                    cb(data)
                except Exception as e:
                    print(f"[GachaEvent] Listener error: {e}")

        # 글로벌 리스너
        for cb in self._global_listeners:
            try:
                cb(data)
            except Exception as e:
                print(f"[GachaEvent] Global listener error: {e}")


# =============================================================================
# 가챠 타입 인터페이스 (플러그인 구조)
# =============================================================================

@dataclass
class GachaConfig:
    """가챠 설정"""
    name: str = "default"
    cost_pot: int = GACHA_COST_POT
    win_probability: float = GACHA_WIN_PROBABILITY
    payout_ratio: float = GACHA_PAYOUT_RATIO
    min_reveal_gap: int = GACHA_MIN_REVEAL_GAP
    max_reveal_gap: int = GACHA_MAX_REVEAL_GAP
    slots: int = 100  # 슬롯 수 (당첨 확률 = 1/slots)
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'GachaConfig':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class GachaType(ABC):
    """가챠 타입 인터페이스 (확장 가능)"""

    @property
    @abstractmethod
    def type_id(self) -> str:
        """타입 식별자"""
        pass

    @property
    @abstractmethod
    def config(self) -> GachaConfig:
        """설정"""
        pass

    @abstractmethod
    def calculate_result(self, nonce: bytes, block_hash: bytes, target: int) -> Tuple[bool, int]:
        """결과 계산 (won, winning_slot)"""
        pass

    @abstractmethod
    def calculate_payout(self, pool_balance: int, commit_height: int) -> int:
        """지급액 계산"""
        pass


class StandardGacha(GachaType):
    """기본 가챠 (1% 당첨, 60% 지급)"""

    def __init__(self, config: GachaConfig = None):
        self._config = config or GachaConfig()

    @property
    def type_id(self) -> str:
        return "standard"

    @property
    def config(self) -> GachaConfig:
        return self._config

    def calculate_result(self, nonce: bytes, block_hash: bytes, target: int) -> Tuple[bool, int]:
        winning_slot = calculate_winning_slot(nonce, block_hash)
        won = check_win(target, winning_slot)
        return won, winning_slot

    def calculate_payout(self, pool_balance: int, commit_height: int) -> int:
        return int(pool_balance * self._config.payout_ratio)


class HighRiskGacha(GachaType):
    """고위험 고보상 가챠 (0.1% 당첨, 90% 지급)"""

    def __init__(self):
        self._config = GachaConfig(
            name="high_risk",
            cost_pot=GACHA_COST_POT * 10,  # 10 POT
            win_probability=0.001,
            payout_ratio=0.90,
            slots=1000
        )

    @property
    def type_id(self) -> str:
        return "high_risk"

    @property
    def config(self) -> GachaConfig:
        return self._config

    def calculate_result(self, nonce: bytes, block_hash: bytes, target: int) -> Tuple[bool, int]:
        combined = sha256(nonce + block_hash)
        value = int.from_bytes(combined[-2:], 'big')
        winning_slot = value % self._config.slots
        won = target == winning_slot
        return won, winning_slot

    def calculate_payout(self, pool_balance: int, commit_height: int) -> int:
        return int(pool_balance * self._config.payout_ratio)


# =============================================================================
# 가챠 서비스 (메인 인터페이스)
# =============================================================================

@dataclass
class PendingCommit:
    """대기 중인 Commit (16-2 Final: 6자리 로또)"""
    commit_hash: bytes
    nonce: bytes
    chosen_numbers: List[int]           # 6자리 숫자 배열 [0-15, ...]
    address: str
    created_at: float
    tx_id: bytes = b''
    block_height: int = 0
    pool_snapshot: int = 0              # Commit 시점 풀 잔액
    gacha_type: str = "lotto"           # 기본값 변경
    target: int = 0                     # 레거시 호환용

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


class GachaService:
    """
    가챠 서비스 (유연한 구조)

    Features:
    - 여러 가챠 타입 지원
    - 이벤트 훅
    - 지갑 연동
    - 상태 저장/로드
    """

    def __init__(
        self,
        game: GachaGame = None,
        data_dir: str = None
    ):
        self.game = game or GachaGame()
        self.events = GachaEventEmitter()

        # 가챠 타입 레지스트리
        self._gacha_types: Dict[str, GachaType] = {}
        self._register_default_types()

        # 대기 중인 commits (지갑별)
        self._pending_commits: Dict[str, List[PendingCommit]] = {}

        # 저장 경로
        self._data_dir = Path(data_dir) if data_dir else None
        if self._data_dir:
            self._load_state()

    def _register_default_types(self):
        """기본 가챠 타입 등록"""
        self.register_gacha_type(StandardGacha())
        self.register_gacha_type(HighRiskGacha())

    def register_gacha_type(self, gacha_type: GachaType):
        """가챠 타입 등록"""
        self._gacha_types[gacha_type.type_id] = gacha_type

    def get_gacha_type(self, type_id: str) -> Optional[GachaType]:
        """가챠 타입 조회"""
        return self._gacha_types.get(type_id)

    def list_gacha_types(self) -> List[dict]:
        """등록된 가챠 타입 목록"""
        return [
            {
                'type_id': gt.type_id,
                'config': gt.config.to_dict()
            }
            for gt in self._gacha_types.values()
            if gt.config.enabled
        ]

    # =========================================================================
    # Commit 생성
    # =========================================================================

    def create_commit(
        self,
        wallet,  # Wallet instance
        utxo_set: UTXOSet,
        current_height: int,
        chosen_numbers: List[int] = None,
        target: int = None,             # 레거시 호환
        gacha_type: str = "lotto"
    ) -> Tuple[Optional[Transaction], Optional[PendingCommit], str]:
        """
        Commit TX 생성 (16-2 Final: 6자리 로또)

        Args:
            wallet: 지갑 인스턴스
            utxo_set: UTXO Set
            current_height: 현재 블록 높이
            chosen_numbers: 6자리 숫자 배열 [0-15, ...] (None이면 랜덤)
            target: 레거시 호환용 (무시됨)
            gacha_type: 가챠 타입

        Returns:
            (tx, pending_commit, error)
        """
        # 숫자 검증
        if chosen_numbers is not None:
            if len(chosen_numbers) != LOTTO_DIGIT_COUNT:
                return None, None, f"Must choose exactly {LOTTO_DIGIT_COUNT} numbers"
            for d in chosen_numbers:
                if not (0 <= d < LOTTO_DIGIT_BASE):
                    return None, None, f"Each number must be 0-{LOTTO_DIGIT_BASE - 1}"

        # POT UTXO 선택
        cost = LOTTO_COST_POT
        pot_utxos = self._select_pot_utxos(wallet, utxo_set, cost, current_height)

        if not pot_utxos:
            return None, None, f"Insufficient POT balance (need {cost / 1e8} POT)"

        # Commit 생성 (6자리 숫자)
        commit_hash, nonce, actual_numbers = generate_commit(chosen_numbers)

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

        # 수수료용 JACK UTXO 추가 (필요시)
        if total_jack < MIN_TX_FEE:
            jack_utxos = self._select_jack_utxos(wallet, utxo_set, MIN_TX_FEE, current_height)
            for utxo in jack_utxos:
                inp = TxInput(
                    prev_tx_id=utxo.tx_id,
                    output_index=utxo.output_index,
                    script_sig=b'',
                    sequence=0xFFFFFFFF
                )
                inputs.append((inp, utxo))
                total_jack += utxo.output.jack_value

        # 출력 생성
        outputs = []

        # 1. Commit OP_RETURN (해시만 - 숫자는 로컬 저장)
        outputs.append(TxOutput(
            jack_value=0,
            script_pubkey=create_commit_script(commit_hash)
        ))

        # 2. POT 잔돈
        pot_change = total_pot - cost
        if pot_change > 0:
            change_addr = wallet.get_change_address()
            outputs.append(TxOutput(
                jack_value=0,
                script_pubkey=create_p2pkh_script_pubkey(address_to_pubkey_hash(change_addr)),
                assets={ASSET_ID_POT: pot_change}
            ))

        # 3. JACK 잔돈 (수수료 차감)
        jack_change = total_jack - MIN_TX_FEE
        if jack_change > 0:
            change_addr = wallet.get_change_address()
            outputs.append(TxOutput(
                jack_value=jack_change,
                script_pubkey=create_p2pkh_script_pubkey(address_to_pubkey_hash(change_addr))
            ))

        # TX 생성
        tx = Transaction(
            version=TX_VERSION_GACHA_COMMIT,
            inputs=[inp for inp, _ in inputs],
            outputs=outputs,
            locktime=0
        )

        # 서명 (Bitcoin SIGHASH_ALL 방식)
        for i, (inp, utxo) in enumerate(inputs):
            address = self._get_utxo_address(utxo)
            if address and address in wallet._addresses:
                info = wallet._addresses[address]
                from ..script.standard import create_p2pkh_script_sig
                sig_hash = tx.get_signature_hash(i, utxo.output.script_pubkey)
                signature = sign(sig_hash, info.private_key)
                tx.inputs[i].script_sig = create_p2pkh_script_sig(signature, info.public_key)

        # PendingCommit 생성
        addresses = wallet.get_addresses()
        player_address = addresses[0] if addresses else ""

        # 풀 잔액 스냅샷
        pool_snapshot = self.game.pool.balance if self.game else 0

        pending = PendingCommit(
            commit_hash=commit_hash,
            nonce=nonce,
            chosen_numbers=actual_numbers,
            address=player_address,
            created_at=time.time(),
            tx_id=tx.get_txid(),
            pool_snapshot=pool_snapshot,
            gacha_type=gacha_type
        )

        # 저장
        self._add_pending_commit(player_address, pending)

        # 이벤트
        self.events.emit(GachaEventData(
            event=GachaEvent.COMMIT_CREATED,
            address=player_address,
            commit_hash=commit_hash.hex(),
            metadata={
                'gacha_type': gacha_type,
                'chosen_numbers': actual_numbers
            }
        ))

        return tx, pending, ""

    # =========================================================================
    # Reveal 생성
    # =========================================================================

    def create_reveal(
        self,
        wallet,
        utxo_set: UTXOSet,
        commit_hash: bytes,
        current_height: int
    ) -> Tuple[Optional[Transaction], str]:
        """
        Reveal TX 생성

        Returns:
            (tx, error)
        """
        # 대응하는 PendingCommit 찾기
        pending = self._find_pending_commit(commit_hash)
        if not pending:
            return None, "Pending commit not found"

        # 타이밍 검증
        if pending.block_height > 0:
            gap = current_height - pending.block_height
            gt = self._gacha_types.get(pending.gacha_type, StandardGacha())

            if gap < gt.config.min_reveal_gap:
                return None, f"Too early to reveal (need {gt.config.min_reveal_gap} blocks)"

            if gap > gt.config.max_reveal_gap:
                return None, f"Reveal expired (max {gt.config.max_reveal_gap} blocks)"

        # JACK UTXO 선택 (수수료용)
        jack_utxos = self._select_jack_utxos(wallet, utxo_set, MIN_TX_FEE, current_height)
        if not jack_utxos:
            return None, "Insufficient JACK for fee"

        # TX 입력
        inputs = []
        total_jack = 0

        for utxo in jack_utxos:
            inp = TxInput(
                prev_tx_id=utxo.tx_id,
                output_index=utxo.output_index,
                script_sig=b'',
                sequence=0xFFFFFFFF
            )
            inputs.append((inp, utxo))
            total_jack += utxo.output.jack_value

        # TX 출력
        outputs = []

        # 1. Reveal OP_RETURN
        outputs.append(TxOutput(
            jack_value=0,
            script_pubkey=create_reveal_script(pending.nonce, pending.target)
        ))

        # 2. JACK 잔돈
        jack_change = total_jack - MIN_TX_FEE
        if jack_change > 0:
            change_addr = wallet.get_change_address()
            outputs.append(TxOutput(
                jack_value=jack_change,
                script_pubkey=create_p2pkh_script_pubkey(address_to_pubkey_hash(change_addr))
            ))

        # TX 생성
        tx = Transaction(
            version=TX_VERSION_GACHA_REVEAL,
            inputs=[inp for inp, _ in inputs],
            outputs=outputs,
            locktime=0
        )

        # 서명 (Bitcoin SIGHASH_ALL 방식)
        for i, (inp, utxo) in enumerate(inputs):
            address = self._get_utxo_address(utxo)
            if address and address in wallet._addresses:
                info = wallet._addresses[address]
                sig_hash = tx.get_signature_hash(i, utxo.output.script_pubkey)
                signature = sign(sig_hash, info.private_key)
                tx.inputs[i].script_sig = create_p2pkh_script_sig(signature, info.public_key)

        # 이벤트
        self.events.emit(GachaEventData(
            event=GachaEvent.REVEAL_CREATED,
            address=pending.address,
            commit_hash=commit_hash.hex(),
            target=pending.target
        ))

        return tx, ""

    # =========================================================================
    # Claim 생성 (16-2 Final)
    # =========================================================================

    def _select_pool_utxos(
        self,
        utxo_set: UTXOSet,
        amount_needed: int
    ) -> List[UTXO]:
        """잭팟 풀 UTXO 선택"""
        all_pool_utxos = utxo_set.get_pool_utxos()
        selected = []
        total = 0

        for utxo in all_pool_utxos:
            selected.append(utxo)
            total += utxo.output.jack_value
            if total >= amount_needed:
                break

        return selected if total >= amount_needed else []

    def create_claim(
        self,
        wallet,
        utxo_set: UTXOSet,
        commit_hash: bytes,
        current_height: int
    ) -> Tuple[Optional[Transaction], str]:
        """
        Claim TX 생성 (당첨금 지급 포함)

        Args:
            wallet: 지갑 인스턴스
            utxo_set: UTXO Set
            commit_hash: Commit 해시
            current_height: 현재 블록 높이

        Returns:
            (tx, error)
        """
        from ..script.standard import create_claim_script

        # 대응하는 PendingCommit 찾기
        pending = self._find_pending_commit(commit_hash)
        if not pending:
            return None, "Pending commit not found"

        # 타이밍 검증 (N+18 ~ N+80)
        if pending.block_height > 0:
            valid, reason = is_claim_valid(pending.block_height, current_height)
            if not valid:
                return None, reason

        # 결과 확인 (당첨 여부 및 지급액 계산)
        result = self.game.check_result(
            commit_hash=commit_hash,
            chosen_numbers=pending.chosen_numbers,
            current_height=current_height,
            commit_height=pending.block_height
        )

        if result is None or not result.success:
            error_msg = result.error if result else "Result check failed"
            return None, error_msg

        # JACK UTXO 선택 (수수료용)
        jack_utxos = self._select_jack_utxos(wallet, utxo_set, MIN_TX_FEE, current_height)
        if not jack_utxos:
            return None, "Insufficient JACK for fee"

        # TX 입력
        inputs = []
        total_jack = 0
        pool_input_total = 0

        # 1. 사용자 UTXO (수수료)
        for utxo in jack_utxos:
            inp = TxInput(
                prev_tx_id=utxo.tx_id,
                output_index=utxo.output_index,
                script_sig=b'',
                sequence=0xFFFFFFFF
            )
            inputs.append((inp, utxo, False))  # False = not pool
            total_jack += utxo.output.jack_value

        # 2. 잭팟 풀 UTXO (당첨금 - JACK 지급용)
        payout_jack = result.payout_jack
        payout_pot = result.payout_pot
        if payout_jack > 0:
            pool_utxos = self._select_pool_utxos(utxo_set, payout_jack)
            if not pool_utxos:
                return None, f"Insufficient pool balance for payout: {payout_jack}"

            for utxo in pool_utxos:
                inp = TxInput(
                    prev_tx_id=utxo.tx_id,
                    output_index=utxo.output_index,
                    script_sig=b'',  # 풀은 서명 불필요 (특수 검증)
                    sequence=0xFFFFFFFF
                )
                inputs.append((inp, utxo, True))  # True = pool
                pool_input_total += utxo.output.jack_value

        # TX 출력
        outputs = []
        recipient_addr = pending.address
        recipient_script = create_p2pkh_script_pubkey(address_to_pubkey_hash(recipient_addr))

        # 1. Claim OP_RETURN (결과 기록)
        outputs.append(TxOutput(
            jack_value=0,
            script_pubkey=create_claim_script(
                pending.commit_hash,
                pending.nonce,
                pending.chosen_numbers
            )
        ))

        # 2. 당첨금 지급 (JACK)
        if payout_jack > 0:
            outputs.append(TxOutput(
                jack_value=payout_jack,
                script_pubkey=recipient_script
            ))

            # 3. 풀 잔돈 반환
            pool_change = pool_input_total - payout_jack
            if pool_change > 0:
                outputs.append(TxOutput(
                    jack_value=pool_change,
                    script_pubkey=b'JACKPOT_POOL'
                ))

        # 3. 6등 POT 보상 (mint - input 없이 생성)
        if payout_pot > 0:
            outputs.append(TxOutput(
                jack_value=0,
                script_pubkey=recipient_script,
                assets={ASSET_ID_POT: payout_pot}
            ))

        # 4. 사용자 JACK 잔돈
        jack_change = total_jack - MIN_TX_FEE
        if jack_change > 0:
            change_addr = wallet.get_change_address()
            outputs.append(TxOutput(
                jack_value=jack_change,
                script_pubkey=create_p2pkh_script_pubkey(address_to_pubkey_hash(change_addr))
            ))

        # TX 생성
        tx = Transaction(
            version=TX_VERSION_LOTTO_CLAIM,
            inputs=[inp for inp, _, _ in inputs],
            outputs=outputs,
            locktime=0
        )

        # 서명 (풀 UTXO는 서명 불필요)
        for i, (inp, utxo, is_pool) in enumerate(inputs):
            if is_pool:
                continue  # 풀 UTXO는 서명 스킵
            address = self._get_utxo_address(utxo)
            if address and address in wallet._addresses:
                info = wallet._addresses[address]
                sig_hash = tx.get_signature_hash(i, utxo.output.script_pubkey)
                signature = sign(sig_hash, info.private_key)
                tx.inputs[i].script_sig = create_p2pkh_script_sig(signature, info.public_key)

        # 이벤트
        event_type = GachaEvent.WIN if payout_jack > 0 else GachaEvent.LOSE
        self.events.emit(GachaEventData(
            event=event_type,
            address=pending.address,
            commit_hash=commit_hash.hex(),
            metadata={
                'chosen_numbers': pending.chosen_numbers,
                'result_digits': result.result_digits,
                'matches': result.matches,
                'prize': result.prize.name,
                'payout_jack': payout_jack
            }
        ))

        return tx, ""

    # =========================================================================
    # 상태 관리
    # =========================================================================

    def get_pending_commits(self, address: str = None) -> List[PendingCommit]:
        """대기 중인 Commit 목록"""
        if address:
            return self._pending_commits.get(address, [])

        all_commits = []
        for commits in self._pending_commits.values():
            all_commits.extend(commits)
        return all_commits

    def update_commit_status(self, commit_hash: bytes, tx_id: bytes, block_height: int):
        """Commit 상태 업데이트 (블록 포함 시)"""
        pending = self._find_pending_commit(commit_hash)
        if pending:
            pending.tx_id = tx_id
            pending.block_height = block_height
            self._save_state()

    def remove_commit(self, commit_hash: bytes):
        """Commit 제거 (Reveal 완료 시)"""
        for address, commits in self._pending_commits.items():
            for commit in commits:
                if commit.commit_hash == commit_hash:
                    commits.remove(commit)
                    self._save_state()
                    return

    def get_stats(self) -> dict:
        """통계"""
        game_stats = self.game.get_stats()
        return {
            **game_stats,
            'gacha_types': list(self._gacha_types.keys()),
            'pending_commits_total': sum(len(c) for c in self._pending_commits.values()),
        }

    # =========================================================================
    # 유틸리티
    # =========================================================================

    def _select_pot_utxos(
        self,
        wallet,
        utxo_set: UTXOSet,
        amount: int,
        current_height: int
    ) -> List[UTXO]:
        """POT UTXO 선택"""
        utxos = wallet.get_utxos(utxo_set)
        pot_utxos = []
        total = 0

        for utxo in utxos:
            if not utxo.is_mature(current_height):
                continue
            pot_amount = utxo.output.assets.get(ASSET_ID_POT, 0)
            if pot_amount > 0:
                pot_utxos.append(utxo)
                total += pot_amount
                if total >= amount:
                    break

        return pot_utxos if total >= amount else []

    def _select_jack_utxos(
        self,
        wallet,
        utxo_set: UTXOSet,
        amount: int,
        current_height: int
    ) -> List[UTXO]:
        """JACK UTXO 선택"""
        utxos = wallet.get_utxos(utxo_set)
        jack_utxos = []
        total = 0

        for utxo in utxos:
            if not utxo.is_mature(current_height):
                continue
            if utxo.output.jack_value > 0:
                jack_utxos.append(utxo)
                total += utxo.output.jack_value
                if total >= amount:
                    break

        return jack_utxos if total >= amount else []

    def _get_utxo_address(self, utxo: UTXO) -> Optional[str]:
        """UTXO 주소 추출"""
        from ..script.standard import get_address_from_script_pubkey
        return get_address_from_script_pubkey(utxo.output.script_pubkey)

    def _add_pending_commit(self, address: str, commit: PendingCommit):
        """PendingCommit 추가"""
        if address not in self._pending_commits:
            self._pending_commits[address] = []
        self._pending_commits[address].append(commit)
        self._save_state()

    def _find_pending_commit(self, commit_hash: bytes) -> Optional[PendingCommit]:
        """PendingCommit 검색"""
        for commits in self._pending_commits.values():
            for commit in commits:
                if commit.commit_hash == commit_hash:
                    return commit
        return None

    def _save_state(self):
        """상태 저장"""
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
        """상태 로드"""
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

def create_gacha_service(
    data_dir: str = None,
    custom_types: List[GachaType] = None
) -> GachaService:
    """
    가챠 서비스 팩토리

    Args:
        data_dir: 상태 저장 디렉토리
        custom_types: 추가 가챠 타입

    Returns:
        GachaService
    """
    service = GachaService(data_dir=data_dir)

    if custom_types:
        for gt in custom_types:
            service.register_gacha_type(gt)

    return service
