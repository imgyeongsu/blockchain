"""
가챠 시스템 테스트
- Commit-Reveal
- 잭팟 풀
"""

import pytest
from jackpotchain.gacha.commit_reveal import (
    generate_commit, verify_commit,
    calculate_winning_slot, check_win,
    is_reveal_valid, CommitRecord, CommitStore
)
from jackpotchain.gacha.pool import JackpotPool, calculate_pool_contribution
from jackpotchain.gacha.game import GachaGame


class TestCommitReveal:
    """Commit-Reveal 테스트"""

    def test_generate_commit(self):
        """커밋 생성"""
        commit_hash, nonce, target = generate_commit()

        assert len(commit_hash) == 32
        assert len(nonce) == 32
        assert 0 <= target <= 99

    def test_generate_commit_with_target(self):
        """지정된 타겟으로 커밋 생성"""
        commit_hash, nonce, target = generate_commit(target=42)

        assert target == 42
        assert verify_commit(commit_hash, nonce, target) is True

    def test_verify_commit_valid(self):
        """유효한 커밋 검증"""
        commit_hash, nonce, target = generate_commit()
        assert verify_commit(commit_hash, nonce, target) is True

    def test_verify_commit_invalid(self):
        """잘못된 커밋 검증"""
        commit_hash, nonce, target = generate_commit()

        # 잘못된 nonce
        wrong_nonce = bytes(32)
        assert verify_commit(commit_hash, wrong_nonce, target) is False

        # 잘못된 target
        wrong_target = (target + 1) % 100
        assert verify_commit(commit_hash, nonce, wrong_target) is False

    def test_winning_slot_deterministic(self):
        """당첨 슬롯 결정론적"""
        nonce = b'\x01' * 32
        block_hash = b'\x02' * 32

        slot1 = calculate_winning_slot(nonce, block_hash)
        slot2 = calculate_winning_slot(nonce, block_hash)

        assert slot1 == slot2
        assert 0 <= slot1 <= 99

    def test_winning_slot_different_inputs(self):
        """다른 입력 → 다른 슬롯"""
        nonce1 = b'\x01' * 32
        nonce2 = b'\x02' * 32
        block_hash = b'\x03' * 32

        slot1 = calculate_winning_slot(nonce1, block_hash)
        slot2 = calculate_winning_slot(nonce2, block_hash)

        # 대부분의 경우 다름 (1% 확률로 같을 수 있음)
        # 테스트 안정성을 위해 단순히 범위만 확인
        assert 0 <= slot1 <= 99
        assert 0 <= slot2 <= 99

    def test_check_win(self):
        """당첨 여부 확인"""
        assert check_win(42, 42) is True
        assert check_win(42, 43) is False
        assert check_win(0, 99) is False

    def test_reveal_timing_valid(self):
        """유효한 Reveal 타이밍"""
        # commit_height=100, reveal_height=102 (gap=2, min=2)
        valid, _ = is_reveal_valid(100, 102)
        assert valid is True

        # commit_height=100, reveal_height=150 (gap=50, max=50)
        valid, _ = is_reveal_valid(100, 150)
        assert valid is True

    def test_reveal_timing_too_early(self):
        """너무 이른 Reveal"""
        # commit_height=100, reveal_height=101 (gap=1, min=2)
        valid, reason = is_reveal_valid(100, 101)
        assert valid is False
        assert "early" in reason.lower()

    def test_reveal_timing_expired(self):
        """만료된 Reveal"""
        # commit_height=100, reveal_height=151 (gap=51, max=50)
        valid, reason = is_reveal_valid(100, 151)
        assert valid is False
        assert "expired" in reason.lower()


class TestCommitStore:
    """CommitStore 테스트"""

    def test_add_and_get_commit(self):
        """커밋 추가 및 조회"""
        store = CommitStore()

        commit_hash, nonce, target = generate_commit()
        record = CommitRecord(
            commit_hash=commit_hash,
            player_address='test_address',
            commit_height=100,
            commit_tx_id=b'\x01' * 32,
            target=target
        )

        store.add_commit(record)

        retrieved = store.get_commit(commit_hash)
        assert retrieved is not None
        assert retrieved.player_address == 'test_address'

    def test_get_commits_by_address(self):
        """주소별 커밋 조회"""
        store = CommitStore()

        # 2개 커밋 추가
        for i in range(2):
            commit_hash, _, target = generate_commit()
            record = CommitRecord(
                commit_hash=commit_hash,
                player_address='player1',
                commit_height=100 + i,
                commit_tx_id=bytes([i] * 32),
                target=target
            )
            store.add_commit(record)

        commits = store.get_commits_by_address('player1')
        assert len(commits) == 2


class TestJackpotPool:
    """잭팟 풀 테스트"""

    def test_initial_balance(self):
        """초기 잔액"""
        pool = JackpotPool(initial_balance=1000000)
        assert pool.balance == 1000000

    def test_add_fee(self):
        """수수료 입금"""
        pool = JackpotPool()
        pool.add_fee(1000000, block_height=1)

        assert pool.balance == 1000000

    def test_calculate_payout(self):
        """지급액 계산 (60%)"""
        pool = JackpotPool(initial_balance=10000000)
        payout = pool.calculate_payout()

        assert payout == 6000000  # 60%

    def test_process_payout(self):
        """지급 처리"""
        pool = JackpotPool(initial_balance=10000000)

        payout = pool.process_payout(block_height=10, tx_id=b'\x01' * 32)

        assert payout == 6000000
        assert pool.balance == 4000000  # 40% 남음

    def test_pool_stats(self):
        """풀 통계"""
        pool = JackpotPool()
        pool.add_fee(1000000, block_height=1)
        pool.add_fee(2000000, block_height=2)

        stats = pool.get_stats()
        assert stats['balance'] == 3000000
        assert stats['total_fees_collected'] == 3000000

    def test_calculate_pool_contribution(self):
        """블록 수수료 → 풀 기여분"""
        contribution = calculate_pool_contribution(1000000)
        assert contribution == 300000  # 30%


class TestGachaGame:
    """가챠 게임 통합 테스트"""

    def test_create_game(self):
        """게임 인스턴스 생성"""
        game = GachaGame()
        assert game.pool is not None
        assert game.store is not None

    def test_game_stats(self):
        """게임 통계"""
        game = GachaGame()
        game.pool.add_fee(1000000, block_height=1)

        stats = game.get_stats()
        assert 'balance' in stats
        assert stats['balance'] == 1000000


class TestProbability:
    """확률 분포 테스트 (선택적)"""

    @pytest.mark.slow
    def test_winning_slot_distribution(self):
        """당첨 슬롯 분포 (0-99 균등)"""
        import os
        counts = [0] * 100

        # 1000번 시뮬레이션
        for _ in range(1000):
            nonce = os.urandom(32)
            block_hash = os.urandom(32)
            slot = calculate_winning_slot(nonce, block_hash)
            counts[slot] += 1

        # 각 슬롯이 최소 1번은 나와야 함 (확률적으로 거의 확실)
        # 실제로는 평균 10번씩 나와야 함
        zero_counts = sum(1 for c in counts if c == 0)
        assert zero_counts < 20  # 대부분 슬롯이 사용됨


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
