"""
로또 게임 로직 (16-2 Final)

Flow:
1. Commit TX (v3): 6자리 숫자 선택 + 1 POT 참가비
2. 18블록 대기 (N+18까지)
3. Claim TX (v5): 6개 블록 해시와 비교하여 등급 판정 및 보상 수령
"""

from typing import Optional, Tuple, List, Callable
from dataclasses import dataclass

from ..core.transaction import Transaction, TxInput, TxOutput
from ..script.standard import (
    create_p2pkh_script_pubkey,
    create_commit_script,
    create_claim_script,
    extract_commit_hash,
    extract_commit_data,
    extract_claim_data,
    is_commit_script,
    is_claim_script,
)
from ..crypto.address import address_to_pubkey_hash, validate_address, JACKPOT_POOL_ADDRESS
from ..constants import (
    TX_VERSION_GACHA_COMMIT,
    TX_VERSION_LOTTO_CLAIM,
    LOTTO_COST_POT,
    LOTTO_DIGIT_COUNT,
    LOTTO_DIGIT_BASE,
    LOTTO_COMPARISON_OFFSETS,
    ASSET_ID_POT,
    ASSET_ID_JACK,
    COIN,
)
from .pool import JackpotPool
from .commit_reveal import (
    generate_commit,
    verify_commit,
    calculate_result_digits,
    count_matches,
    determine_prize,
    calculate_payout,
    get_comparison_heights,
    is_claim_valid,
    CommitRecord,
    CommitStore,
    CommitStatus,
    LottoPrize,
    get_commit_status,
)


@dataclass
class LottoPlayResult:
    """로또 플레이 결과"""
    success: bool
    matches: int = 0
    prize: LottoPrize = LottoPrize.NONE
    payout_jack: int = 0        # JACK 보상
    payout_pot: int = 0         # POT 보상 (6등)
    chosen_numbers: List[int] = None
    result_digits: List[int] = None
    error: str = ""


class LottoGame:
    """
    로또 게임 관리 (16-2 Final)

    Flow:
    1. Commit TX: 6자리 숫자 제출 + 1 POT 비용
    2. 30+ 블록 대기 (비교 블록 생성 대기)
    3. Claim TX: 결과 확정 + 보상 수령
    """

    def __init__(
        self,
        pool: JackpotPool = None,
        store: CommitStore = None,
        get_block_hash: Callable[[int], bytes] = None
    ):
        from ..constants import GENESIS_JACKPOT_POOL_FUNDING
        self.pool = pool or JackpotPool(initial_balance=GENESIS_JACKPOT_POOL_FUNDING)
        self.store = store or CommitStore()
        # 블록 해시 조회 함수 (체인에서 주입)
        self._get_block_hash = get_block_hash

    def set_block_hash_getter(self, getter: Callable[[int], bytes]):
        """블록 해시 조회 함수 설정"""
        self._get_block_hash = getter

    # =========================================================================
    # Commit Phase
    # =========================================================================

    def create_commit_tx(
        self,
        inputs: list,               # List of (TxInput, UTXO)
        player_address: str,
        chosen_numbers: List[int] = None,
        change_address: str = None
    ) -> Tuple[Optional[Transaction], bytes, bytes, List[int], str]:
        """
        Commit TX 생성

        Args:
            inputs: UTXO 입력들
            player_address: 플레이어 주소
            chosen_numbers: 6자리 숫자 (None이면 랜덤)
            change_address: 잔돈 주소

        Returns:
            (tx, commit_hash, nonce, chosen_numbers, error)
        """
        # 입력 중 POT 잔액 확인
        total_pot = 0
        for _, utxo in inputs:
            total_pot += utxo.output.assets.get(ASSET_ID_POT, 0)

        if total_pot < LOTTO_COST_POT:
            return None, b'', b'', [], f"Insufficient POT: {total_pot} < {LOTTO_COST_POT}"

        # 숫자 유효성 검사
        if chosen_numbers is not None:
            if len(chosen_numbers) != LOTTO_DIGIT_COUNT:
                return None, b'', b'', [], f"Must choose exactly {LOTTO_DIGIT_COUNT} numbers"
            for d in chosen_numbers:
                if not (0 <= d < LOTTO_DIGIT_BASE):
                    return None, b'', b'', [], f"Each number must be 0~{LOTTO_DIGIT_BASE - 1}"

        # 주소 유효성 검증
        effective_address = change_address or player_address
        if not validate_address(player_address):
            return None, b'', b'', 0, f"Invalid player address: {player_address}"
        if change_address and not validate_address(change_address):
            return None, b'', b'', 0, f"Invalid change address: {change_address}"

        # Commit 생성
        commit_hash, nonce, chosen_numbers = generate_commit(chosen_numbers)

        # 입력 생성
        tx_inputs = [inp for inp, _ in inputs]

        # 출력 생성
        outputs = []

        # 1. Commit OP_RETURN (해시만 - 숫자는 로컬 저장)
        commit_output = TxOutput(
            jack_value=0,
            script_pubkey=create_commit_script(commit_hash)
        )
        outputs.append(commit_output)

        # 2. POT 잔돈 (있으면)
        pot_change = total_pot - LOTTO_COST_POT
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

        return tx, commit_hash, nonce, chosen_numbers, ""

    def validate_commit_tx(self, tx: Transaction) -> Tuple[bool, str]:
        """Commit TX 검증"""
        if tx.version != TX_VERSION_GACHA_COMMIT:
            return False, "Invalid TX version"

        # Commit 데이터 확인 (해시만 검증 - 숫자는 Claim 시 공개)
        commit_found = False
        for out in tx.outputs:
            if is_commit_script(out.script_pubkey):
                commit_hash = extract_commit_data(out.script_pubkey)
                if commit_hash and len(commit_hash) == 32:
                    commit_found = True
                    break

        if not commit_found:
            return False, "No valid commit data found"

        return True, ""

    def process_commit(
        self,
        tx: Transaction,
        player_address: str,
        block_height: int,
        pool_balance: int = 0
    ):
        """
        Commit 처리 (블록 적용 시)

        Args:
            tx: Commit TX
            player_address: 플레이어 주소
            block_height: 블록 높이
            pool_balance: 현재 풀 잔액 (스냅샷용)

        Note:
            숫자는 Commit에 포함되지 않음 (Claim 시 공개)
        """
        for out in tx.outputs:
            if is_commit_script(out.script_pubkey):
                commit_hash = extract_commit_data(out.script_pubkey)
                if commit_hash:
                    record = CommitRecord(
                        commit_hash=commit_hash,
                        player_address=player_address,
                        commit_height=block_height,
                        commit_tx_id=tx.get_txid(),
                        chosen_numbers=[],  # Claim 시 공개됨
                        pool_snapshot=pool_balance
                    )
                    self.store.add_commit(record)

                    # 풀 스냅샷 저장
                    self.pool.take_snapshot(block_height)
                    break

    # =========================================================================
    # Claim Phase
    # =========================================================================

    def create_claim_tx(
        self,
        inputs: list,               # List of (TxInput, UTXO)
        commit_hash: bytes,
        nonce: bytes,
        chosen_numbers: List[int],
        player_address: str,
        change_address: str = None
    ) -> Tuple[Optional[Transaction], str]:
        """
        Claim TX 생성

        Args:
            inputs: UTXO 입력들 (JACK 수수료용)
            commit_hash: 원래 Commit의 해시
            nonce: 원래 nonce
            chosen_numbers: 6자리 숫자
            player_address: 플레이어 주소
            change_address: 잔돈 주소

        Returns:
            (tx, error)
        """
        # Commit 검증
        if not verify_commit(commit_hash, nonce, chosen_numbers):
            return None, "Invalid commit verification"

        # 주소 유효성 검증
        if not validate_address(player_address):
            return None, f"Invalid player address: {player_address}"
        if change_address and not validate_address(change_address):
            return None, f"Invalid change address: {change_address}"

        # 입력 생성
        tx_inputs = [inp for inp, _ in inputs]

        # 출력 생성
        outputs = []

        # 1. Claim OP_RETURN
        claim_output = TxOutput(
            jack_value=0,
            script_pubkey=create_claim_script(commit_hash, nonce, chosen_numbers)
        )
        outputs.append(claim_output)

        # 2. JACK 잔돈 (수수료 제외)
        total_jack = sum(utxo.output.jack_value for _, utxo in inputs)
        if total_jack > 0:
            change_addr = change_address or player_address
            change_pubkey_hash = address_to_pubkey_hash(change_addr)
            outputs.append(TxOutput(
                jack_value=total_jack,
                script_pubkey=create_p2pkh_script_pubkey(change_pubkey_hash)
            ))

        tx = Transaction(
            version=TX_VERSION_LOTTO_CLAIM,
            inputs=tx_inputs,
            outputs=outputs,
            locktime=0
        )

        return tx, ""

    def validate_claim_tx(
        self,
        tx: Transaction,
        current_height: int
    ) -> Tuple[bool, str]:
        """
        Claim TX 검증

        Args:
            tx: Claim TX
            current_height: 현재 블록 높이

        Returns:
            (is_valid, reason)
        """
        if tx.version != TX_VERSION_LOTTO_CLAIM:
            return False, "Invalid TX version (expected v5)"

        # Claim 데이터 추출
        claim_data = None
        for out in tx.outputs:
            if is_claim_script(out.script_pubkey):
                claim_data = extract_claim_data(out.script_pubkey)
                break

        if claim_data is None:
            return False, "No valid claim data found"

        commit_hash, nonce, chosen_numbers = claim_data

        # Commit 검증
        if not verify_commit(commit_hash, nonce, chosen_numbers):
            return False, "Commit verification failed"

        # 대응하는 Commit 찾기
        commit = self.store.get_commit(commit_hash)
        if commit is None:
            return False, "Commit not found"

        # 이미 Claim했는지 확인
        if commit.claim_height is not None:
            return False, "Already claimed"

        # 타이밍 검증 (N+18 ~ N+80)
        valid, reason = is_claim_valid(commit.commit_height, current_height)
        if not valid:
            return False, reason

        return True, ""

    def process_claim(
        self,
        tx: Transaction,
        block_height: int,
        comparison_block_hashes: List[bytes] = None
    ) -> LottoPlayResult:
        """
        Claim 처리 (결과 판정 + 보상 수령)

        Args:
            tx: Claim TX
            block_height: Claim 블록 높이
            comparison_block_hashes: 6개 비교 블록 해시 (없으면 조회)

        Returns:
            LottoPlayResult
        """
        # Claim 데이터 추출
        claim_data = None
        for out in tx.outputs:
            if is_claim_script(out.script_pubkey):
                claim_data = extract_claim_data(out.script_pubkey)
                break

        if claim_data is None:
            return LottoPlayResult(success=False, error="No claim data")

        commit_hash, nonce, chosen_numbers = claim_data

        # Commit 찾기
        commit = self.store.get_commit(commit_hash)
        if commit is None:
            return LottoPlayResult(success=False, error="Commit not found")

        # 비교 블록 해시 조회
        if comparison_block_hashes is None:
            if self._get_block_hash is None:
                return LottoPlayResult(success=False, error="Block hash getter not set")

            comparison_heights = get_comparison_heights(commit.commit_height)
            comparison_block_hashes = []
            for h in comparison_heights:
                block_hash = self._get_block_hash(h)
                if block_hash is None:
                    return LottoPlayResult(
                        success=False,
                        error=f"Comparison block {h} not found"
                    )
                comparison_block_hashes.append(block_hash)

        if len(comparison_block_hashes) != LOTTO_DIGIT_COUNT:
            return LottoPlayResult(
                success=False,
                error=f"Need {LOTTO_DIGIT_COUNT} block hashes"
            )

        # 결과 숫자 추출
        result_digits = calculate_result_digits(comparison_block_hashes)

        # 일치 개수 계산
        matches = count_matches(chosen_numbers, result_digits)

        # 등급 판정
        prize = determine_prize(matches)

        # 보상 계산
        payout_jack = 0
        payout_pot = 0

        if prize == LottoPrize.JACKPOT:
            # 1등: Commit 시점 풀 잔액의 50%
            payout_jack = self.pool.process_jackpot_payout(
                commit.commit_height,
                block_height,
                tx.get_txid()
            )
        elif prize != LottoPrize.NONE:
            # 2~6등: calculate_payout이 (jack, pot) 튜플 반환
            payout_jack, payout_pot = calculate_payout(prize, commit.pool_snapshot)

        # 기록 업데이트
        self.store.update_claim(
            commit_hash=commit_hash,
            claim_height=block_height,
            claim_tx_id=tx.get_txid(),
            nonce=nonce,
            result_digits=result_digits,
            matches=matches,
            prize=prize,
            payout=payout_jack + payout_pot  # 총 보상 (기록용)
        )

        return LottoPlayResult(
            success=True,
            matches=matches,
            prize=prize,
            payout_jack=payout_jack,
            payout_pot=payout_pot,  # 6등: 1 POT mint
            chosen_numbers=chosen_numbers,
            result_digits=result_digits
        )

    # =========================================================================
    # 유틸리티
    # =========================================================================

    def get_claimable_commits(self, address: str = None, current_height: int = 0) -> List[CommitRecord]:
        """Claim 가능한 커밋 조회"""
        if address:
            commits = self.store.get_commits_by_address(address)
            return [
                c for c in commits
                if get_commit_status(c, current_height) == CommitStatus.CLAIMABLE
            ]
        return self.store.get_claimable_commits(current_height)

    def get_pending_commits(self, address: str = None, current_height: int = 0) -> List[CommitRecord]:
        """대기 중인 커밋 조회 (PENDING + CLAIMABLE)"""
        if address:
            commits = self.store.get_commits_by_address(address)
            return [c for c in commits if c.claim_height is None]
        return self.store.get_pending_commits(current_height)

    def check_result(
        self,
        commit_hash: bytes,
        chosen_numbers: List[int],
        current_height: int,
        commit_height: int = 0
    ) -> Optional[LottoPlayResult]:
        """
        결과 미리보기 (Claim 전)

        Args:
            commit_hash: Commit 해시
            chosen_numbers: 사용자가 로컬에 저장한 6자리 숫자
            current_height: 현재 블록 높이
            commit_height: Commit 블록 높이 (없으면 store에서 조회)

        Returns:
            LottoPlayResult (Claim 안 해도 결과 확인 가능)

        Note:
            숫자는 Commit에 포함되지 않으므로 사용자가 제공해야 함
        """
        # commit_height가 제공되지 않으면 store에서 조회
        if commit_height == 0:
            commit = self.store.get_commit(commit_hash)
            if commit is None:
                return None
            commit_height = commit.commit_height

        # 숫자 유효성 검사
        if len(chosen_numbers) != LOTTO_DIGIT_COUNT:
            return LottoPlayResult(success=False, error="Invalid chosen_numbers length")

        # 비교 블록이 모두 생성되었는지 확인
        comparison_heights = get_comparison_heights(commit_height)
        if current_height < comparison_heights[-1]:
            return LottoPlayResult(
                success=False,
                error=f"Wait until block {comparison_heights[-1]}"
            )

        if self._get_block_hash is None:
            return LottoPlayResult(success=False, error="Block hash getter not set")

        # 비교 블록 해시 조회
        comparison_block_hashes = []
        for h in comparison_heights:
            block_hash = self._get_block_hash(h)
            if block_hash is None:
                return LottoPlayResult(success=False, error=f"Block {h} not found")
            comparison_block_hashes.append(block_hash)

        # 결과 계산
        result_digits = calculate_result_digits(comparison_block_hashes)
        matches = count_matches(chosen_numbers, result_digits)
        prize = determine_prize(matches)

        # 예상 보상 계산
        payout_jack = 0
        payout_pot = 0
        if prize == LottoPrize.JACKPOT:
            payout_jack = self.pool.calculate_jackpot_payout(commit_height)
        elif prize != LottoPrize.NONE:
            # 2~6등: calculate_payout이 (jack, pot) 튜플 반환
            pool_snapshot = self.pool.balance
            payout_jack, payout_pot = calculate_payout(prize, pool_snapshot)

        return LottoPlayResult(
            success=True,
            matches=matches,
            prize=prize,
            payout_jack=payout_jack,
            payout_pot=payout_pot,  # 6등: 1 POT mint
            chosen_numbers=chosen_numbers,
            result_digits=result_digits
        )

    def get_stats(self) -> dict:
        """게임 통계"""
        pool_stats = self.pool.get_stats()
        return {
            **pool_stats,
            'pending_commits': len(self.get_pending_commits()),
        }


# =============================================================================
# 하위 호환 (deprecated)
# =============================================================================

# 기존 GachaGame 별칭
GachaGame = LottoGame
GachaPlayResult = LottoPlayResult
