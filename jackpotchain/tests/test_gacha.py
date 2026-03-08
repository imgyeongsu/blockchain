"""
로또 시스템 테스트 (16-2 Final)
- 6자리 숫자 Commit
- 6개 블록 해시 비교
- 등급별 보상
"""

import pytest
from jackpotchain.gacha.commit_reveal import (
    generate_commit, verify_commit,
    calculate_result_digits, count_matches, determine_prize,
    calculate_payout, get_comparison_heights,
    is_claim_valid, get_commit_status,
    CommitRecord, CommitStore, CommitStatus, LottoPrize,
    extract_result_digit,
    # 레거시 호환
    calculate_winning_slot, check_win, is_reveal_valid,
)
from jackpotchain.gacha.pool import (
    JackpotPool, calculate_pool_contribution,
    calculate_entry_distribution, EntryDistribution,
)
from jackpotchain.gacha.game import LottoGame, LottoPlayResult
from jackpotchain.constants import (
    LOTTO_DIGIT_COUNT, LOTTO_DIGIT_BASE,
    LOTTO_MIN_CLAIM_GAP, LOTTO_MAX_CLAIM_GAP,
    LOTTO_PRIZE_1ST_RATIO, LOTTO_PRIZE_2ND, LOTTO_PRIZE_3RD,
    LOTTO_PRIZE_4TH, LOTTO_PRIZE_5TH,
)


class TestLottoCommit:
    """6자리 로또 Commit 테스트"""

    def test_generate_commit_random(self):
        """랜덤 6자리 숫자 생성"""
        commit_hash, nonce, chosen_numbers = generate_commit()

        assert len(commit_hash) == 32
        assert len(nonce) == 32
        assert len(chosen_numbers) == LOTTO_DIGIT_COUNT
        for d in chosen_numbers:
            assert 0 <= d < LOTTO_DIGIT_BASE

    def test_generate_commit_with_numbers(self):
        """지정된 숫자로 커밋 생성"""
        chosen = [0x3, 0xa, 0xf, 0x1, 0x8, 0xc]
        commit_hash, nonce, actual = generate_commit(chosen)

        assert actual == chosen
        assert verify_commit(commit_hash, nonce, actual) is True

    def test_verify_commit_valid(self):
        """유효한 커밋 검증"""
        commit_hash, nonce, chosen = generate_commit()
        assert verify_commit(commit_hash, nonce, chosen) is True

    def test_verify_commit_invalid(self):
        """잘못된 커밋 검증"""
        commit_hash, nonce, chosen = generate_commit()

        # 잘못된 nonce
        wrong_nonce = bytes(32)
        assert verify_commit(commit_hash, wrong_nonce, chosen) is False

        # 잘못된 숫자
        wrong_numbers = [(d + 1) % LOTTO_DIGIT_BASE for d in chosen]
        assert verify_commit(commit_hash, nonce, wrong_numbers) is False

    def test_invalid_digit_count(self):
        """잘못된 자릿수"""
        with pytest.raises(ValueError):
            generate_commit([1, 2, 3, 4, 5])  # 5자리

    def test_invalid_digit_value(self):
        """잘못된 숫자 값"""
        with pytest.raises(ValueError):
            generate_commit([1, 2, 3, 4, 5, 16])  # 16 > max


class TestResultCalculation:
    """결과 계산 테스트"""

    def test_extract_result_digit(self):
        """블록 해시에서 결과 숫자 추출"""
        # 마지막 바이트가 0xab -> 하위 4비트 = 0xb = 11
        block_hash = bytes(31) + bytes([0xab])
        digit = extract_result_digit(block_hash)
        assert digit == 0xb

    def test_calculate_result_digits(self):
        """6개 블록 해시에서 결과 배열 추출"""
        hashes = [
            bytes(31) + bytes([0x03]),
            bytes(31) + bytes([0x1a]),
            bytes(31) + bytes([0x2f]),
            bytes(31) + bytes([0x31]),
            bytes(31) + bytes([0x48]),
            bytes(31) + bytes([0x5c]),
        ]
        results = calculate_result_digits(hashes)
        assert results == [0x3, 0xa, 0xf, 0x1, 0x8, 0xc]

    def test_count_matches_all(self):
        """6개 전부 일치"""
        chosen = [0x3, 0xa, 0xf, 0x1, 0x8, 0xc]
        result = [0x3, 0xa, 0xf, 0x1, 0x8, 0xc]
        assert count_matches(chosen, result) == 6

    def test_count_matches_none(self):
        """0개 일치"""
        chosen = [0x0, 0x1, 0x2, 0x3, 0x4, 0x5]
        result = [0xf, 0xe, 0xd, 0xc, 0xb, 0xa]
        assert count_matches(chosen, result) == 0

    def test_count_matches_partial(self):
        """일부 일치"""
        chosen = [0x3, 0xa, 0xf, 0x1, 0x8, 0xc]
        result = [0x3, 0x0, 0xf, 0x0, 0x8, 0x0]  # 3개 일치
        assert count_matches(chosen, result) == 3


class TestPrizeDetermination:
    """등급 판정 테스트"""

    def test_prize_jackpot(self):
        """1등: 6개 일치"""
        assert determine_prize(6) == LottoPrize.JACKPOT

    def test_prize_second(self):
        """2등: 5개 일치"""
        assert determine_prize(5) == LottoPrize.SECOND

    def test_prize_third(self):
        """3등: 4개 일치"""
        assert determine_prize(4) == LottoPrize.THIRD

    def test_prize_fourth(self):
        """4등: 3개 일치"""
        assert determine_prize(3) == LottoPrize.FOURTH

    def test_prize_fifth(self):
        """5등: 2개 일치"""
        assert determine_prize(2) == LottoPrize.FIFTH

    def test_prize_sixth(self):
        """6등: 1개 일치"""
        assert determine_prize(1) == LottoPrize.SIXTH

    def test_prize_none(self):
        """꽝: 0개 일치"""
        assert determine_prize(0) == LottoPrize.NONE


class TestPayoutCalculation:
    """보상 계산 테스트"""

    def test_jackpot_payout(self):
        """1등: 풀의 50%"""
        pool_snapshot = 1_000_000_00_000_000  # 1,000,000 JACK
        payout = calculate_payout(LottoPrize.JACKPOT, pool_snapshot)
        assert payout == int(pool_snapshot * LOTTO_PRIZE_1ST_RATIO)

    def test_second_payout(self):
        """2등: 100,000 JACK"""
        payout = calculate_payout(LottoPrize.SECOND, 0)
        assert payout == LOTTO_PRIZE_2ND

    def test_third_payout(self):
        """3등: 20,000 JACK"""
        payout = calculate_payout(LottoPrize.THIRD, 0)
        assert payout == LOTTO_PRIZE_3RD

    def test_fourth_payout(self):
        """4등: 2,000 JACK"""
        payout = calculate_payout(LottoPrize.FOURTH, 0)
        assert payout == LOTTO_PRIZE_4TH

    def test_fifth_payout(self):
        """5등: 300 JACK"""
        payout = calculate_payout(LottoPrize.FIFTH, 0)
        assert payout == LOTTO_PRIZE_5TH

    def test_sixth_payout(self):
        """6등: 0 JACK (POT 별도 처리)"""
        payout = calculate_payout(LottoPrize.SIXTH, 0)
        assert payout == 0

    def test_none_payout(self):
        """꽝: 0"""
        payout = calculate_payout(LottoPrize.NONE, 0)
        assert payout == 0


class TestClaimTiming:
    """Claim 타이밍 테스트"""

    def test_comparison_heights(self):
        """비교 블록 높이 계산"""
        heights = get_comparison_heights(500)
        assert heights == [505, 510, 515, 520, 525, 530]

    def test_claim_valid_at_n30(self):
        """N+30에서 Claim 가능"""
        valid, _ = is_claim_valid(500, 530)
        assert valid is True

    def test_claim_valid_at_n80(self):
        """N+80에서 Claim 가능"""
        valid, _ = is_claim_valid(500, 580)
        assert valid is True

    def test_claim_too_early(self):
        """N+30 이전 Claim 불가"""
        valid, reason = is_claim_valid(500, 529)
        assert valid is False
        assert "early" in reason.lower()

    def test_claim_expired(self):
        """N+80 이후 Claim 불가"""
        valid, reason = is_claim_valid(500, 581)
        assert valid is False
        assert "expired" in reason.lower()


class TestCommitStore:
    """CommitStore 테스트"""

    def test_add_and_get_commit(self):
        """커밋 추가 및 조회"""
        store = CommitStore()

        commit_hash, nonce, chosen = generate_commit()
        record = CommitRecord(
            commit_hash=commit_hash,
            player_address='test_address',
            commit_height=100,
            commit_tx_id=b'\x01' * 32,
            chosen_numbers=chosen
        )

        store.add_commit(record)

        retrieved = store.get_commit(commit_hash)
        assert retrieved is not None
        assert retrieved.player_address == 'test_address'
        assert retrieved.chosen_numbers == chosen

    def test_commit_status_pending(self):
        """PENDING 상태"""
        commit_hash, _, chosen = generate_commit()
        record = CommitRecord(
            commit_hash=commit_hash,
            player_address='test',
            commit_height=100,
            commit_tx_id=b'\x01' * 32,
            chosen_numbers=chosen
        )

        # current_height = 110 (gap = 10 < 30)
        status = get_commit_status(record, 110)
        assert status == CommitStatus.PENDING

    def test_commit_status_claimable(self):
        """CLAIMABLE 상태"""
        commit_hash, _, chosen = generate_commit()
        record = CommitRecord(
            commit_hash=commit_hash,
            player_address='test',
            commit_height=100,
            commit_tx_id=b'\x01' * 32,
            chosen_numbers=chosen
        )

        # current_height = 135 (gap = 35, 30 <= gap <= 80)
        status = get_commit_status(record, 135)
        assert status == CommitStatus.CLAIMABLE

    def test_commit_status_expired(self):
        """EXPIRED 상태"""
        commit_hash, _, chosen = generate_commit()
        record = CommitRecord(
            commit_hash=commit_hash,
            player_address='test',
            commit_height=100,
            commit_tx_id=b'\x01' * 32,
            chosen_numbers=chosen
        )

        # current_height = 185 (gap = 85 > 80)
        status = get_commit_status(record, 185)
        assert status == CommitStatus.EXPIRED


class TestJackpotPool:
    """잭팟 풀 테스트 (16-2 Final)"""

    def test_initial_balance(self):
        """초기 잔액"""
        pool = JackpotPool(initial_balance=1_000_000)
        assert pool.balance == 1_000_000

    def test_process_entry(self):
        """참가비 처리 (80/19/1 분배)"""
        pool = JackpotPool()
        dist = pool.process_entry(100_00_000_000, block_height=1)  # 100 JACK

        assert dist.pool_amount == 80_00_000_000   # 80%
        assert dist.burn_amount == 19_00_000_000   # 19%
        assert dist.miner_amount == 1_00_000_000   # 1%
        assert pool.balance == 80_00_000_000

    def test_snapshot(self):
        """풀 스냅샷"""
        pool = JackpotPool(initial_balance=1_000_000)
        pool.take_snapshot(100)
        pool.add_fee(500_000, block_height=101)

        # 100 시점 스냅샷 조회
        assert pool.get_snapshot(100) == 1_000_000
        # 현재 잔액
        assert pool.balance == 1_500_000

    def test_jackpot_payout(self):
        """1등 당첨금 계산 (Commit 시점 기준)"""
        pool = JackpotPool(initial_balance=10_000_000)
        pool.take_snapshot(100)

        # 이후 풀 증가
        pool.add_fee(5_000_000, block_height=101)

        # 1등 당첨금은 100 시점 기준 50%
        payout = pool.calculate_jackpot_payout(100)
        assert payout == 5_000_000  # 10,000,000 * 0.5

    def test_entry_distribution_utility(self):
        """참가비 분배 유틸리티"""
        dist = calculate_entry_distribution(100_00_000_000)
        assert dist.pool_amount == 80_00_000_000
        assert dist.burn_amount == 19_00_000_000
        assert dist.miner_amount == 1_00_000_000


class TestLottoGame:
    """로또 게임 통합 테스트"""

    def test_create_game(self):
        """게임 인스턴스 생성"""
        game = LottoGame()
        assert game.pool is not None
        assert game.store is not None

    def test_game_stats(self):
        """게임 통계"""
        game = LottoGame()
        game.pool.add_fee(1_000_000, block_height=1)

        stats = game.get_stats()
        assert 'balance' in stats
        assert stats['balance'] == 1_000_000


class TestLegacyCompatibility:
    """레거시 호환 테스트"""

    def test_winning_slot_still_works(self):
        """기존 winning_slot 함수 동작"""
        nonce = b'\x01' * 32
        block_hash = b'\x02' * 32

        slot = calculate_winning_slot(nonce, block_hash)
        assert 0 <= slot <= 99

    def test_check_win_still_works(self):
        """기존 check_win 함수 동작"""
        assert check_win(42, 42) is True
        assert check_win(42, 43) is False

    def test_reveal_valid_alias(self):
        """is_reveal_valid는 is_claim_valid의 별칭"""
        valid1, _ = is_reveal_valid(100, 130)
        valid2, _ = is_claim_valid(100, 130)
        assert valid1 == valid2


class TestProbability:
    """확률 분포 테스트"""

    @pytest.mark.slow
    def test_result_digit_distribution(self):
        """결과 숫자 분포 (0-15 균등)"""
        import os
        counts = [0] * 16

        for _ in range(1600):
            block_hash = os.urandom(32)
            digit = extract_result_digit(block_hash)
            counts[digit] += 1

        # 각 숫자가 최소 10번은 나와야 함
        for count in counts:
            assert count >= 10


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
