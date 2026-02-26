"""
Step 7.3: 가챠 게임 로직
- 전체 게임 흐름 관리
- TX 생성 및 검증
"""

from typing import Optional, Tuple, List
from dataclasses import dataclass

from ..core.transaction import Transaction, TxInput, TxOutput
from ..script.standard import (
    create_p2pkh_script_pubkey,
    create_commit_script,
    create_reveal_script,
    extract_commit_hash,
    extract_reveal_data,
    is_commit_script,
    is_reveal_script,
)
from ..crypto.address import address_to_pubkey_hash, JACKPOT_POOL_ADDRESS
from ..constants import (
    TX_VERSION_GACHA_COMMIT,
    TX_VERSION_GACHA_REVEAL,
    GACHA_COST_POT,
    ASSET_ID_POT,
)
from .pool import JackpotPool
from .commit_reveal import (
    generate_commit,
    verify_commit,
    calculate_winning_slot,
    check_win,
    is_reveal_valid,
    CommitRecord,
    CommitStore,
    CommitStatus,
    get_commit_status,
)


@dataclass
class GachaPlayResult:
    """가챠 플레이 결과"""
    won: bool
    payout: int = 0
    winning_slot: int = 0
    target_slot: int = 0


class GachaGame:
    """
    가챠 게임 관리

    Flow:
    1. Commit TX: hash(nonce + target) 제출 + 1 POT 비용
    2. 2+ 블록 대기
    3. Reveal TX: nonce 공개 → 당첨 여부 결정
    """

    def __init__(self, pool: JackpotPool = None, store: CommitStore = None):
        self.pool = pool or JackpotPool()
        self.store = store or CommitStore()

    # =========================================================================
    # Commit Phase
    # =========================================================================

    def create_commit_tx(
        self,
        inputs: list,           # List of (TxInput, UTXO)
        player_address: str,
        target: int = None,     # 목표 슬롯 (0-99)
        change_address: str = None
    ) -> Tuple[Optional[Transaction], bytes, bytes, int, str]:
        """
        Commit TX 생성

        Returns:
            (tx, commit_hash, nonce, target, error)
        """
        # 입력 중 POT 잔액 확인
        total_pot = 0
        for _, utxo in inputs:
            total_pot += utxo.output.assets.get(ASSET_ID_POT, 0)

        if total_pot < GACHA_COST_POT:
            return None, b'', b'', 0, f"Insufficient POT: {total_pot} < {GACHA_COST_POT}"

        # Commit 생성
        commit_hash, nonce, target = generate_commit(target)

        # 입력 생성
        tx_inputs = [inp for inp, _ in inputs]

        # 출력 생성
        outputs = []

        # 1. Commit OP_RETURN
        commit_output = TxOutput(
            jack_value=0,
            script_pubkey=create_commit_script(commit_hash)
        )
        outputs.append(commit_output)

        # 2. POT 잔돈 (있으면)
        pot_change = total_pot - GACHA_COST_POT
        if pot_change > 0:
            change_addr = change_address or player_address
            change_pubkey_hash = address_to_pubkey_hash(change_addr)
            change_output = TxOutput(
                jack_value=0,
                script_pubkey=create_p2pkh_script_pubkey(change_pubkey_hash),
                assets={ASSET_ID_POT: pot_change}
            )
            outputs.append(change_output)

        # 3. JACK 잔돈 (있으면)
        total_jack = sum(utxo.output.jack_value for _, utxo in inputs)
        if total_jack > 0:
            change_addr = change_address or player_address
            change_pubkey_hash = address_to_pubkey_hash(change_addr)
            jack_change_output = TxOutput(
                jack_value=total_jack,
                script_pubkey=create_p2pkh_script_pubkey(change_pubkey_hash)
            )
            outputs.append(jack_change_output)

        tx = Transaction(
            version=TX_VERSION_GACHA_COMMIT,
            inputs=tx_inputs,
            outputs=outputs,
            locktime=0
        )

        return tx, commit_hash, nonce, target, ""

    def validate_commit_tx(self, tx: Transaction) -> Tuple[bool, str]:
        """Commit TX 검증"""
        if tx.version != TX_VERSION_GACHA_COMMIT:
            return False, "Invalid TX version"

        # Commit OP_RETURN 찾기
        commit_found = False
        for out in tx.outputs:
            if is_commit_script(out.script_pubkey):
                commit_hash = extract_commit_hash(out.script_pubkey)
                if commit_hash and len(commit_hash) == 32:
                    commit_found = True
                    break

        if not commit_found:
            return False, "No valid commit hash found"

        # POT 비용은 입력에서 차감됨 (UTXOSet에서 검증)

        return True, ""

    def process_commit(
        self,
        tx: Transaction,
        player_address: str,
        block_height: int,
        target: int = 0  # target은 Reveal에서 알 수 있음
    ):
        """Commit 처리 (블록 적용 시)"""
        commit_hash = None
        for out in tx.outputs:
            if is_commit_script(out.script_pubkey):
                commit_hash = extract_commit_hash(out.script_pubkey)
                break

        if commit_hash:
            record = CommitRecord(
                commit_hash=commit_hash,
                player_address=player_address,
                commit_height=block_height,
                commit_tx_id=tx.get_txid(),
                target=target
            )
            self.store.add_commit(record)

    # =========================================================================
    # Reveal Phase
    # =========================================================================

    def create_reveal_tx(
        self,
        inputs: list,           # List of (TxInput, UTXO)
        commit_hash: bytes,
        nonce: bytes,
        target: int,
        player_address: str,
        change_address: str = None
    ) -> Tuple[Optional[Transaction], str]:
        """
        Reveal TX 생성

        Returns:
            (tx, error)
        """
        # Commit 검증
        if not verify_commit(commit_hash, nonce, target):
            return None, "Invalid commit verification"

        # 입력 생성
        tx_inputs = [inp for inp, _ in inputs]

        # 출력 생성
        outputs = []

        # 1. Reveal OP_RETURN
        reveal_output = TxOutput(
            jack_value=0,
            script_pubkey=create_reveal_script(nonce, target)
        )
        outputs.append(reveal_output)

        # 2. JACK 잔돈
        total_jack = sum(utxo.output.jack_value for _, utxo in inputs)
        if total_jack > 0:
            change_addr = change_address or player_address
            change_pubkey_hash = address_to_pubkey_hash(change_addr)
            outputs.append(TxOutput(
                jack_value=total_jack,
                script_pubkey=create_p2pkh_script_pubkey(change_pubkey_hash)
            ))

        tx = Transaction(
            version=TX_VERSION_GACHA_REVEAL,
            inputs=tx_inputs,
            outputs=outputs,
            locktime=0
        )

        return tx, ""

    def validate_reveal_tx(
        self,
        tx: Transaction,
        current_height: int
    ) -> Tuple[bool, str]:
        """Reveal TX 검증"""
        if tx.version != TX_VERSION_GACHA_REVEAL:
            return False, "Invalid TX version"

        # Reveal 데이터 추출
        nonce, target = None, None
        for out in tx.outputs:
            if is_reveal_script(out.script_pubkey):
                result = extract_reveal_data(out.script_pubkey)
                if result:
                    nonce, target = result
                    break

        if nonce is None:
            return False, "No valid reveal data found"

        # 대응하는 Commit 찾기
        from ..crypto.hash import sha256
        import struct
        commit_hash = sha256(nonce + struct.pack('B', target))
        commit = self.store.get_commit(commit_hash)

        if commit is None:
            return False, "Commit not found"

        # 타이밍 검증
        valid, reason = is_reveal_valid(commit.commit_height, current_height)
        if not valid:
            return False, reason

        # Commit 검증
        if not verify_commit(commit_hash, nonce, target):
            return False, "Commit verification failed"

        return True, ""

    def process_reveal(
        self,
        tx: Transaction,
        block_hash: bytes,
        block_height: int
    ) -> GachaPlayResult:
        """
        Reveal 처리 (당첨 여부 결정)

        Returns:
            GachaPlayResult
        """
        # Reveal 데이터 추출
        nonce, target = None, None
        for out in tx.outputs:
            if is_reveal_script(out.script_pubkey):
                result = extract_reveal_data(out.script_pubkey)
                if result:
                    nonce, target = result
                    break

        if nonce is None:
            return GachaPlayResult(won=False)

        # Commit 찾기
        from ..crypto.hash import sha256
        import struct
        commit_hash = sha256(nonce + struct.pack('B', target))
        commit = self.store.get_commit(commit_hash)

        if commit is None:
            return GachaPlayResult(won=False)

        # 당첨 슬롯 계산
        winning_slot = calculate_winning_slot(nonce, block_hash)

        # 당첨 여부
        won = check_win(target, winning_slot)

        # 지급액
        payout = 0
        if won:
            payout = self.pool.process_payout(block_height, tx.get_txid())

        # 기록 업데이트
        self.store.update_reveal(
            commit_hash=commit_hash,
            reveal_height=block_height,
            reveal_tx_id=tx.get_txid(),
            nonce=nonce,
            result=won
        )

        return GachaPlayResult(
            won=won,
            payout=payout,
            winning_slot=winning_slot,
            target_slot=target
        )

    # =========================================================================
    # 유틸리티
    # =========================================================================

    def get_pending_commits(self, address: str = None) -> List[CommitRecord]:
        """대기 중인 커밋 조회"""
        if address:
            commits = self.store.get_commits_by_address(address)
            return [c for c in commits if c.reveal_height is None]
        return self.store.get_pending_commits(0)  # 높이는 나중에 필터링

    def get_stats(self) -> dict:
        """게임 통계"""
        pool_stats = self.pool.get_stats()
        return {
            **pool_stats,
            'pending_commits': len(self.get_pending_commits()),
        }
