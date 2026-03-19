"""
로또 게임 로직 (자동 지급 방식)

Flow:
1. Commit TX (v3): 6자리 숫자 선택 + 1 POT 참가비
2. 18블록 후 채굴자가 자동으로 당첨 판정 + 지급 TX 생성
"""

from typing import Optional, Tuple, List, Callable
from dataclasses import dataclass

from ..core.transaction import Transaction, TxInput, TxOutput
from ..script.standard import (
    create_p2pkh_script_pubkey,
    create_commit_script,
    extract_commit_numbers,
    is_commit_script,
    create_lotto_payout_script,
)
from ..crypto.address import address_to_pubkey_hash, validate_address, JACKPOT_POOL_ADDRESS
from ..constants import (
    TX_VERSION_GACHA_COMMIT,
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
    calculate_result_digits,
    count_matches,
    determine_prize,
    calculate_payout,
    get_comparison_heights,
    CommitRecord,
    CommitStore,
    LottoPrize,
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


@dataclass
class PayoutInfo:
    """자동 지급 정보 (채굴자가 블록에 포함)"""
    commit_tx_id: bytes
    player_address: str
    chosen_numbers: List[int]
    result_digits: List[int]
    matches: int
    prize: LottoPrize
    payout_jack: int
    payout_pot: int
    pool_snapshot: int


class LottoGame:
    """
    로또 게임 관리 (자동 지급 방식)

    Flow:
    1. Commit TX: 6자리 숫자 + 1 POT → 블록에 포함
    2. 채굴자가 블록 H 생성 시 H-18 블록의 Commit TX 조회 → 판정 → 지급 TX 자동 포함
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
    ) -> Tuple[Optional[Transaction], List[int], str]:
        """
        Commit TX 생성

        Args:
            inputs: UTXO 입력들
            player_address: 플레이어 주소
            chosen_numbers: 6자리 숫자 (None이면 랜덤)
            change_address: 잔돈 주소

        Returns:
            (tx, chosen_numbers, error)
        """
        # 입력 중 POT 잔액 확인
        total_pot = 0
        for _, utxo in inputs:
            total_pot += utxo.output.assets.get(ASSET_ID_POT, 0)

        if total_pot < LOTTO_COST_POT:
            return None, [], f"Insufficient POT: {total_pot} < {LOTTO_COST_POT}"

        # 숫자 유효성 검사
        if chosen_numbers is not None:
            if len(chosen_numbers) != LOTTO_DIGIT_COUNT:
                return None, [], f"Must choose exactly {LOTTO_DIGIT_COUNT} numbers"
            for d in chosen_numbers:
                if not (0 <= d < LOTTO_DIGIT_BASE):
                    return None, [], f"Each number must be 0~{LOTTO_DIGIT_BASE - 1}"
        else:
            # 랜덤 숫자 생성
            import os
            chosen_numbers = [
                int.from_bytes(os.urandom(1), 'big') % LOTTO_DIGIT_BASE
                for _ in range(LOTTO_DIGIT_COUNT)
            ]

        # 주소 유효성 검증
        if not validate_address(player_address):
            return None, [], f"Invalid player address: {player_address}"
        if change_address and not validate_address(change_address):
            return None, [], f"Invalid change address: {change_address}"

        # 입력 생성
        tx_inputs = [inp for inp, _ in inputs]

        # 출력 생성
        outputs = []

        # 1. Commit OP_RETURN (숫자 평문)
        commit_output = TxOutput(
            jack_value=0,
            script_pubkey=create_commit_script(chosen_numbers)
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

        return tx, chosen_numbers, ""

    def validate_commit_tx(self, tx: Transaction) -> Tuple[bool, str]:
        """Commit TX 검증"""
        if tx.version != TX_VERSION_GACHA_COMMIT:
            return False, "Invalid TX version"

        commit_found = False
        for out in tx.outputs:
            if is_commit_script(out.script_pubkey):
                numbers = extract_commit_numbers(out.script_pubkey)
                if numbers and len(numbers) == LOTTO_DIGIT_COUNT:
                    # 각 숫자가 유효 범위인지 검증
                    if all(0 <= d < LOTTO_DIGIT_BASE for d in numbers):
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
        chosen_numbers를 OP_RETURN에서 직접 추출
        """
        for out in tx.outputs:
            if is_commit_script(out.script_pubkey):
                chosen_numbers = extract_commit_numbers(out.script_pubkey)
                if chosen_numbers:
                    record = CommitRecord(
                        commit_hash=tx.get_txid(),  # TX ID를 키로 사용
                        player_address=player_address,
                        commit_height=block_height,
                        commit_tx_id=tx.get_txid(),
                        chosen_numbers=chosen_numbers,
                        pool_snapshot=pool_balance
                    )
                    self.store.add_commit(record)
                    self.pool.take_snapshot(block_height)
                    break

    # =========================================================================
    # 자동 지급 (채굴자가 블록 생성 시 호출)
    # =========================================================================

    def get_payouts_for_block(
        self,
        current_height: int,
        get_block_hash: Callable[[int], bytes],
        get_commits_at_height: Callable[[int], List[Tuple[bytes, str, List[int], int]]],
    ) -> List[PayoutInfo]:
        """
        블록 H 생성 시 H-18 블록의 Commit TX에 대한 지급 정보 계산

        Args:
            current_height: 현재 생성할 블록 높이 H
            get_block_hash: 높이→블록해시 조회
            get_commits_at_height: 높이→[(tx_id, player_address, chosen_numbers, pool_snapshot)] 조회

        Returns:
            List[PayoutInfo] — 지급할 항목들
        """
        from ..constants import LOTTO_MIN_CLAIM_GAP, LOTTO_PRIZE_1ST_PERCENT

        target_height = current_height - LOTTO_MIN_CLAIM_GAP
        if target_height < 1:
            return []

        # H-18 블록의 Commit TX 조회
        commits = get_commits_at_height(target_height)
        if not commits:
            return []

        # 비교 블록 해시 조회
        comparison_heights = get_comparison_heights(target_height)
        comparison_hashes = []
        for h in comparison_heights:
            bh = get_block_hash(h)
            if bh is None:
                return []  # 비교 블록이 아직 없으면 지급 불가
            comparison_hashes.append(bh)

        # 결과 숫자 추출
        result_digits = calculate_result_digits(comparison_hashes)

        # 각 Commit에 대해 당첨 판정
        payouts = []
        jackpot_winners = []

        for tx_id, player_address, chosen_numbers, pool_snapshot in commits:
            matches = count_matches(chosen_numbers, result_digits)
            prize = determine_prize(matches)

            if prize == LottoPrize.NONE:
                continue

            payout_jack = 0
            payout_pot = 0

            if prize == LottoPrize.JACKPOT:
                # 1등은 나중에 분배 계산
                jackpot_winners.append((tx_id, player_address, chosen_numbers, pool_snapshot, matches))
                continue
            else:
                payout_jack, payout_pot = calculate_payout(prize, pool_snapshot)

            payouts.append(PayoutInfo(
                commit_tx_id=tx_id,
                player_address=player_address,
                chosen_numbers=chosen_numbers,
                result_digits=result_digits,
                matches=matches,
                prize=prize,
                payout_jack=payout_jack,
                payout_pot=payout_pot,
                pool_snapshot=pool_snapshot,
            ))

        # 1등 분배: 같은 블록 당첨자끼리 풀 50%를 N등분
        if jackpot_winners:
            # 풀 스냅샷 중 최소값 사용 (보수적)
            pool_for_jackpot = min(ps for _, _, _, ps, _ in jackpot_winners)
            total_jackpot = pool_for_jackpot * LOTTO_PRIZE_1ST_PERCENT // 100
            per_winner = total_jackpot // len(jackpot_winners)

            for tx_id, player_address, chosen_numbers, pool_snapshot, matches in jackpot_winners:
                payouts.append(PayoutInfo(
                    commit_tx_id=tx_id,
                    player_address=player_address,
                    chosen_numbers=chosen_numbers,
                    result_digits=result_digits,
                    matches=matches,
                    prize=LottoPrize.JACKPOT,
                    payout_jack=per_winner,
                    payout_pot=0,
                    pool_snapshot=pool_snapshot,
                ))

        return payouts

    # =========================================================================
    # 유틸리티
    # =========================================================================

    def get_stats(self) -> dict:
        """게임 통계"""
        pool_stats = self.pool.get_stats()
        return {
            **pool_stats,
            'pending_commits': len(self.store.get_pending_commits(0)),
        }


# 하위 호환
GachaGame = LottoGame
GachaPlayResult = LottoPlayResult
