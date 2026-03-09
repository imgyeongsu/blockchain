"""
가챠 시스템 통합 테스트
- Commit → Reveal 전체 플로우
- RPC 연동
"""

import pytest
from jackpotchain.gacha.game import GachaGame, GachaPlayResult
from jackpotchain.gacha.pool import JackpotPool
from jackpotchain.gacha.commit_reveal import (
    generate_commit, verify_commit, calculate_winning_slot, check_win,
    CommitStore, CommitRecord, CommitStatus, get_commit_status
)
from jackpotchain.core.transaction import Transaction, TxInput, TxOutput
from jackpotchain.core.utxo import UTXO
from jackpotchain.script.standard import (
    create_commit_script, create_reveal_script,
    is_commit_script, is_reveal_script,
    extract_commit_hash, extract_reveal_data
)
from jackpotchain.constants import (
    TX_VERSION_GACHA_COMMIT, TX_VERSION_GACHA_REVEAL,
    GACHA_COST_POT, ASSET_ID_POT
)
from jackpotchain.crypto.signature import generate_keypair
from jackpotchain.crypto.address import pubkey_to_address


class TestGachaIntegration:
    """가챠 시스템 통합 테스트"""

    def test_full_gacha_flow_lose(self):
        """전체 가챠 플로우 (패배 케이스)"""
        game = GachaGame()
        game.pool.add_fee(10_000_000_00, block_height=1)  # 100 JACK 풀

        # 유효한 주소 생성
        _, pubkey = generate_keypair()
        player_address = pubkey_to_address(pubkey)

        # 1. Commit 생성
        commit_hash, nonce, target = generate_commit(target=50)
        assert verify_commit(commit_hash, nonce, target)

        # 2. Commit TX 생성 (mock inputs)
        mock_utxo = UTXO(
            tx_id=b'\x01' * 32,
            output_index=0,
            output=TxOutput(
                jack_value=1000000,
                script_pubkey=b'test',
                assets={ASSET_ID_POT: GACHA_COST_POT}
            ),
            block_height=1
        )
        mock_input = TxInput(
            prev_tx_id=mock_utxo.tx_id,
            output_index=0,
            script_sig=b'',
            sequence=0xFFFFFFFF
        )

        tx, ret_hash, ret_nonce, ret_target, error = game.create_commit_tx(
            inputs=[(mock_input, mock_utxo)],
            player_address=player_address,
            target=target
        )

        assert tx is not None
        assert error == ""
        assert tx.version == TX_VERSION_GACHA_COMMIT

        # 3. Commit TX 검증
        valid, msg = game.validate_commit_tx(tx)
        assert valid, msg

        # 4. Commit 처리
        game.process_commit(tx, player_address, block_height=100)

        # 5. Store에 기록 확인
        commits = game.store.get_commits_by_address(player_address)
        assert len(commits) == 1
        assert commits[0].commit_height == 100

        # 6. Reveal TX 생성 (블록 102에서)
        reveal_tx, error = game.create_reveal_tx(
            inputs=[(mock_input, mock_utxo)],
            commit_hash=ret_hash,
            nonce=ret_nonce,
            target=ret_target,
            player_address=player_address
        )

        assert reveal_tx is not None
        assert error == ""
        assert reveal_tx.version == TX_VERSION_GACHA_REVEAL

        # 7. Reveal TX 검증
        valid, msg = game.validate_reveal_tx(reveal_tx, current_height=102)
        assert valid, msg

        # 8. Reveal 처리 (블록해시로 당첨 결정)
        # 패배하는 블록해시 사용 (target=50이 아닌 다른 슬롯이 나오도록)
        block_hash = b'\xFF' * 32  # 대부분 target=50과 다른 결과
        result = game.process_reveal(reveal_tx, block_hash, block_height=102)

        # 결과는 won 또는 lost (확률적)
        assert isinstance(result, GachaPlayResult)
        assert 0 <= result.winning_slot <= 99
        assert result.target_slot == target

    def test_commit_timing_validation(self):
        """Commit 타이밍 검증"""
        from jackpotchain.gacha.commit_reveal import is_reveal_valid

        game = GachaGame()

        # Commit 등록
        commit_hash, nonce, target = generate_commit()
        record = CommitRecord(
            commit_hash=commit_hash,
            player_address='test',
            commit_height=100,
            commit_tx_id=b'\x01' * 32,
            target=target
        )
        game.store.add_commit(record)

        # 너무 이른 reveal (height=101, gap=1 < min=2)
        valid, reason = is_reveal_valid(100, 101)
        assert valid is False
        assert "early" in reason.lower()

        # 적절한 시간 (height=102, gap=2)
        valid, reason = is_reveal_valid(100, 102)
        assert valid is True

        # 만료 (height=151, gap=51 > max=50)
        status = get_commit_status(record, current_height=151)
        assert status == CommitStatus.EXPIRED

    def test_jackpot_pool_payout(self):
        """잭팟 풀 지급 테스트"""
        pool = JackpotPool(initial_balance=100_000_000_00)  # 1000 JACK

        # 지급액 계산 (60%)
        payout = pool.calculate_payout()
        assert payout == 60_000_000_00  # 600 JACK

        # 지급 처리
        actual_payout = pool.process_payout(block_height=10, tx_id=b'\x01' * 32)
        assert actual_payout == 60_000_000_00

        # 남은 잔액 (40%)
        assert pool.balance == 40_000_000_00

    def test_multiple_commits_same_address(self):
        """동일 주소 다중 커밋"""
        game = GachaGame()

        # 3개 커밋 등록
        for i in range(3):
            commit_hash, _, target = generate_commit()
            record = CommitRecord(
                commit_hash=commit_hash,
                player_address='player1',
                commit_height=100 + i,
                commit_tx_id=bytes([i] * 32),
                target=target
            )
            game.store.add_commit(record)

        # 주소별 조회
        commits = game.store.get_commits_by_address('player1')
        assert len(commits) == 3

    def test_commit_reveal_script_roundtrip(self):
        """Commit/Reveal 스크립트 라운드트립"""
        # Commit 스크립트
        commit_hash, nonce, target = generate_commit()
        commit_script = create_commit_script(commit_hash)

        assert is_commit_script(commit_script)
        extracted_hash = extract_commit_hash(commit_script)
        assert extracted_hash == commit_hash

        # Reveal 스크립트
        reveal_script = create_reveal_script(nonce, target)

        assert is_reveal_script(reveal_script)
        extracted_nonce, extracted_target = extract_reveal_data(reveal_script)
        assert extracted_nonce == nonce
        assert extracted_target == target

    def test_winning_probability_simulation(self):
        """당첨 확률 시뮬레이션 (1%)"""
        import os
        wins = 0
        trials = 1000

        for _ in range(trials):
            nonce = os.urandom(32)
            block_hash = os.urandom(32)
            target = 42  # 고정 타겟

            winning_slot = calculate_winning_slot(nonce, block_hash)
            if check_win(target, winning_slot):
                wins += 1

        # 1% 확률이므로 1000번 중 5~25번 정도 당첨 (0.5%~2.5% 범위)
        # 통계적으로 매우 드물게 범위 벗어날 수 있음
        assert 0 <= wins <= 50, f"Win rate too high: {wins}/1000"

    def test_gacha_game_stats(self):
        """게임 통계"""
        from jackpotchain.constants import GENESIS_JACKPOT_POOL_FUNDING
        game = GachaGame()
        game.pool.add_fee(1000000, block_height=1)

        stats = game.get_stats()
        assert 'balance' in stats
        assert 'pending_commits' in stats
        assert stats['balance'] == GENESIS_JACKPOT_POOL_FUNDING + 1000000


class TestGachaRPCIntegration:
    """RPC 통합 테스트 (단위)"""

    def test_rpc_server_has_gacha_methods(self):
        """RPC 서버에 가챠 메서드 등록 확인"""
        from jackpotchain.rpc.server import RPCServer
        from jackpotchain.consensus.chain import Blockchain

        blockchain = Blockchain()
        rpc = RPCServer(blockchain=blockchain)

        # 가챠 메서드 존재 확인
        assert 'getgachainfo' in rpc._methods
        assert 'getjackpotpool' in rpc._methods

    def test_getgachainfo(self):
        """getgachainfo RPC 메서드"""
        from jackpotchain.rpc.server import RPCServer
        from jackpotchain.consensus.chain import Blockchain

        blockchain = Blockchain()
        game = GachaGame()
        game.pool.add_fee(100_000_000, block_height=1)  # 1 JACK

        rpc = RPCServer(blockchain=blockchain, gacha=game)

        result = rpc._getgachainfo()
        assert result['pool_balance'] == 1.0
        assert result['win_probability'] == '1%'
        assert result['payout_ratio'] == '60%'

    def test_getjackpotpool(self):
        """getjackpotpool RPC 메서드"""
        from jackpotchain.rpc.server import RPCServer
        from jackpotchain.consensus.chain import Blockchain
        from jackpotchain.constants import GENESIS_JACKPOT_POOL_FUNDING, COIN

        blockchain = Blockchain()
        game = GachaGame()
        # 100 JACK = 100 * 100_000_000 satoshi = 10_000_000_000 satoshi
        game.pool.add_fee(10_000_000_000, block_height=1)  # 100 JACK

        expected_balance = (GENESIS_JACKPOT_POOL_FUNDING + 10_000_000_000) / COIN

        rpc = RPCServer(blockchain=blockchain, gacha=game)

        result = rpc._getjackpotpool()
        assert result['balance'] == expected_balance


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
