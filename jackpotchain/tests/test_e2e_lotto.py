"""
로또 E2E 테스트
- 실제 블록체인 + mempool + wallet + gacha 통합
- RPC 레이어 없이 내부 API 직접 호출 (더 빠른 테스트)
"""

import pytest
import time
from typing import List

from jackpotchain.consensus.chain import Blockchain
from jackpotchain.consensus.miner import create_block_template, mine_block
from jackpotchain.consensus.difficulty import get_next_difficulty
from jackpotchain.mempool.pool import Mempool
from jackpotchain.wallet.wallet import Wallet
from jackpotchain.core.transaction import Transaction
from jackpotchain.core.utxo import UTXOSet
from jackpotchain.gacha.game import LottoGame
from jackpotchain.gacha.service import GachaService, create_gacha_service
from jackpotchain.constants import (
    COIN, ASSET_ID_POT, EXCHANGE_RATE,
    LOTTO_COST_POT, LOTTO_DIGIT_COUNT
)
from jackpotchain.crypto.signature import generate_keypair
from jackpotchain.crypto.address import pubkey_to_address
from jackpotchain.asset.exchange import create_exchange_tx


class TestLottoE2E:
    """로또 전체 플로우 E2E 테스트"""

    @pytest.fixture
    def setup_environment(self, tmp_path):
        """테스트 환경 구성"""
        # 블록체인 (인메모리)
        blockchain = Blockchain()
        mempool = Mempool()

        # 지갑 생성
        wallet_path = tmp_path / "test_wallet.json"
        wallet = Wallet(str(wallet_path))
        miner_address = wallet.generate_address()  # 새 주소 생성

        # 가챠 서비스
        gacha_service = create_gacha_service(data_dir=str(tmp_path))

        # 블록 해시 조회 콜백 설정 (service.game에 설정)
        def get_block_hash(height: int) -> bytes:
            block = blockchain.get_block_by_height(height)
            return block.get_hash() if block else None

        gacha_service.game.set_block_hash_getter(get_block_hash)

        return {
            'blockchain': blockchain,
            'mempool': mempool,
            'wallet': wallet,
            'miner_address': miner_address,
            'gacha_service': gacha_service,
            'gacha_game': gacha_service.game,  # service의 game 사용
        }

    def do_exchange(self, env, jack_amount: int) -> Transaction:
        """JACK -> POT 교환 헬퍼"""
        blockchain = env['blockchain']
        mempool = env['mempool']
        wallet = env['wallet']
        miner_address = env['miner_address']

        from jackpotchain.core.transaction import TxInput
        from jackpotchain.crypto.signature import sign
        from jackpotchain.script.standard import create_p2pkh_script_sig

        # 성숙한 UTXO 선택
        utxos = blockchain.utxo_set.get_utxos_for_address(miner_address)
        current_height = blockchain.get_height()
        mature_utxos = [u for u in utxos if u.block_height <= current_height - 100]

        inputs = []
        total_input = 0
        for utxo in mature_utxos:
            inp = TxInput(
                prev_tx_id=utxo.tx_id,
                output_index=utxo.output_index,
                script_sig=b'',
                sequence=0xFFFFFFFF
            )
            inputs.append((inp, utxo))
            total_input += utxo.output.jack_value
            if total_input >= jack_amount + COIN:
                break

        tx, error = create_exchange_tx(
            inputs=inputs,
            exchange_jack=jack_amount,
            recipient_address=miner_address,
            change_address=miner_address
        )
        assert tx is not None, f"Exchange TX failed: {error}"

        # 서명
        for i, (inp, utxo) in enumerate(inputs):
            if miner_address in wallet._addresses:
                info = wallet._addresses[miner_address]
                sig_hash = tx.get_signature_hash(i, utxo.output.script_pubkey)
                signature = sign(sig_hash, info.private_key)
                tx.inputs[i].script_sig = create_p2pkh_script_sig(signature, info.public_key)

        return tx

    def mine_blocks(self, env, count: int) -> List[Transaction]:
        """블록 채굴 헬퍼"""
        blockchain = env['blockchain']
        mempool = env['mempool']
        miner_address = env['miner_address']

        mined_txs = []

        for _ in range(count):
            # 템플릿 생성
            txs = mempool.get_txs_for_block()
            tip = blockchain.get_tip()
            difficulty = get_next_difficulty(
                blockchain.get_height(),
                blockchain.get_block_by_height
            )

            template = create_block_template(
                prev_block=tip,
                miner_address=miner_address,
                transactions=txs,
                difficulty_target=difficulty
            )

            # 채굴 (테스트용 - 난이도 상승에 대비해 충분한 nonce)
            result = mine_block(template, max_nonce=100_000_000)
            assert result.success, "Mining failed"

            # 체인에 추가
            success, msg = blockchain.add_block(result.block)
            assert success, f"Block add failed: {msg}"

            # mempool에서 TX 제거
            for tx in result.block.transactions[1:]:
                mempool.remove_tx(tx.get_txid())
                mined_txs.append(tx)

        return mined_txs

    def test_exchange_jack_to_pot(self, setup_environment):
        """JACK → POT 교환 테스트"""
        env = setup_environment
        blockchain = env['blockchain']
        mempool = env['mempool']
        wallet = env['wallet']
        gacha_service = env['gacha_service']
        miner_address = env['miner_address']

        # 1. 채굴로 JACK 확보 (100블록 이상 - coinbase maturity)
        self.mine_blocks(env, 110)

        initial_height = blockchain.get_height()
        assert initial_height >= 105

        # 2. 잔액 확인
        utxos = blockchain.utxo_set.get_utxos_for_address(miner_address)
        total_jack = sum(u.output.jack_value for u in utxos if u.block_height <= initial_height - 100)
        assert total_jack > 0, "No mature JACK available"

        # 3. 교환 TX 생성
        exchange_amount = 200 * COIN  # 200 JACK → 2 POT

        # 성숙한 UTXO 선택
        mature_utxos = [u for u in utxos if u.block_height <= initial_height - 100]
        inputs = []
        total_input = 0
        for utxo in mature_utxos:
            from jackpotchain.core.transaction import TxInput
            inp = TxInput(
                prev_tx_id=utxo.tx_id,
                output_index=utxo.output_index,
                script_sig=b'',
                sequence=0xFFFFFFFF
            )
            inputs.append((inp, utxo))
            total_input += utxo.output.jack_value
            if total_input >= exchange_amount + COIN:  # +수수료
                break

        tx, error = create_exchange_tx(
            inputs=inputs,
            exchange_jack=exchange_amount,
            recipient_address=miner_address,
            change_address=miner_address
        )

        assert tx is not None, f"Exchange TX failed: {error}"
        assert error == ""

        # 서명
        from jackpotchain.crypto.signature import sign
        from jackpotchain.script.standard import create_p2pkh_script_sig
        for i, (inp, utxo) in enumerate(inputs):
            address = miner_address
            if address in wallet._addresses:
                info = wallet._addresses[address]
                sig_hash = tx.get_signature_hash(i, utxo.output.script_pubkey)
                signature = sign(sig_hash, info.private_key)
                tx.inputs[i].script_sig = create_p2pkh_script_sig(signature, info.public_key)

        # 4. Mempool에 추가
        success, msg = mempool.add_tx(tx, blockchain.utxo_set, initial_height)
        assert success, f"Mempool add failed: {msg}"

        # 5. 채굴
        mined = self.mine_blocks(env, 1)
        assert len(mined) == 1
        assert mined[0].get_txid() == tx.get_txid()

        # 6. POT 잔액 확인
        utxos_after = blockchain.utxo_set.get_utxos_for_address(miner_address)
        pot_balance = 0
        for u in utxos_after:
            if u.output.assets and ASSET_ID_POT in u.output.assets:
                pot_balance += u.output.assets[ASSET_ID_POT]

        expected_pot = (exchange_amount // EXCHANGE_RATE) // COIN * COIN
        assert pot_balance == expected_pot, f"POT balance mismatch: {pot_balance} != {expected_pot}"

        print(f"[PASS] Exchange test: {exchange_amount // COIN} JACK -> {pot_balance // COIN} POT")

    def test_lotto_commit_and_claim(self, setup_environment):
        """로또 Commit → Claim 전체 플로우"""
        env = setup_environment
        blockchain = env['blockchain']
        mempool = env['mempool']
        wallet = env['wallet']
        gacha_service = env['gacha_service']
        gacha_game = env['gacha_game']
        miner_address = env['miner_address']

        # 1. 채굴로 JACK 확보
        self.mine_blocks(env, 110)

        # 2. JACK → POT 교환
        exchange_tx = self.do_exchange(env, 200 * COIN)
        mempool.add_tx(exchange_tx, blockchain.utxo_set, blockchain.get_height())
        self.mine_blocks(env, 1)

        # POT 확인
        utxos = blockchain.utxo_set.get_utxos_for_address(miner_address)
        pot_balance = sum(
            u.output.assets.get(ASSET_ID_POT, 0)
            for u in utxos if u.output.assets
        )
        assert pot_balance >= LOTTO_COST_POT, "Insufficient POT for lotto"

        # 3. 로또 Commit
        chosen_numbers = [1, 2, 3, 4, 5, 6]
        commit_tx, pending, error = gacha_service.create_commit(
            wallet=wallet,
            utxo_set=blockchain.utxo_set,
            current_height=blockchain.get_height(),
            chosen_numbers=chosen_numbers
        )

        assert commit_tx is not None, f"Commit failed: {error}"
        assert pending is not None
        assert pending.chosen_numbers == chosen_numbers

        # Mempool에 추가
        success, msg = mempool.add_tx(commit_tx, blockchain.utxo_set, blockchain.get_height())
        assert success, f"Commit TX mempool add failed: {msg}"

        # 4. Commit TX 채굴
        mined = self.mine_blocks(env, 1)
        assert len(mined) == 1

        commit_height = blockchain.get_height()

        # PendingCommit 업데이트
        gacha_service.update_commit_status(
            pending.commit_hash,
            commit_tx.get_txid(),
            commit_height
        )

        # 5. 18블록 대기 (claim 가능 시점까지)
        self.mine_blocks(env, 18)

        current_height = blockchain.get_height()
        assert current_height >= commit_height + 18

        # 6. 결과 확인
        result = gacha_game.check_result(
            pending.commit_hash,
            chosen_numbers,
            current_height,
            commit_height=commit_height
        )

        assert result is not None, "check_result returned None"
        assert result.success, f"check_result failed: {result.error}"
        assert len(result.result_digits) == LOTTO_DIGIT_COUNT

        print(f"  선택 숫자: {chosen_numbers}")
        print(f"  결과 숫자: {result.result_digits}")
        print(f"  매칭: {result.matches}개")
        print(f"  등수: {result.prize.name}")
        print(f"  예상 JACK 보상: {result.payout_jack // COIN} JACK")
        print(f"  예상 POT 보상: {result.payout_pot // COIN} POT")

        # Claim 전 잔액 기록
        utxos_before = blockchain.utxo_set.get_utxos_for_address(miner_address)
        jack_before = sum(u.output.jack_value for u in utxos_before)
        pool_utxos_before = blockchain.utxo_set.get_pool_utxos()
        pool_before = sum(u.output.jack_value for u in pool_utxos_before)

        # 7. Claim TX 생성
        claim_tx, claim_error = gacha_service.create_claim(
            wallet=wallet,
            utxo_set=blockchain.utxo_set,
            commit_hash=pending.commit_hash,
            current_height=current_height
        )

        assert claim_tx is not None, f"Claim TX failed: {claim_error}"

        # Mempool에 추가
        success, msg = mempool.add_tx(claim_tx, blockchain.utxo_set, current_height)
        assert success, f"Claim TX mempool add failed: {msg}"

        # 8. Claim TX 채굴
        mined = self.mine_blocks(env, 1)
        assert len(mined) == 1
        assert mined[0].get_txid() == claim_tx.get_txid()

        # 9. 당첨금 지급 검증
        utxos_after = blockchain.utxo_set.get_utxos_for_address(miner_address)
        jack_after = sum(u.output.jack_value for u in utxos_after)
        pool_utxos_after = blockchain.utxo_set.get_pool_utxos()
        pool_after = sum(u.output.jack_value for u in pool_utxos_after)

        # 당첨금이 있으면 검증
        if result.payout_jack > 0:
            # 사용자 잔액 증가 확인 (coinbase 보상 포함이라 정확히 payout_jack는 아님)
            print(f"  사용자 JACK 변화: {jack_before // COIN} -> {jack_after // COIN}")
            print(f"  풀 JACK 변화: {pool_before // COIN} -> {pool_after // COIN}")

            # 풀 잔액 감소 확인
            assert pool_after < pool_before, "Pool balance should decrease after payout"
            pool_decrease = pool_before - pool_after
            assert pool_decrease == result.payout_jack, \
                f"Pool decrease {pool_decrease} != payout {result.payout_jack}"
        else:
            print(f"  당첨 없음 (매칭 {result.matches}개)")

        print(f"[PASS] Lotto flow test!")
        print(f"  Commit height: {commit_height}")
        print(f"  Claim height: {blockchain.get_height()}")

    def test_lotto_multiple_commits(self, setup_environment):
        """여러 로또 참여 테스트"""
        env = setup_environment
        blockchain = env['blockchain']
        mempool = env['mempool']
        wallet = env['wallet']
        gacha_service = env['gacha_service']

        # 채굴 + 교환 (500 JACK + 수수료 필요 → 120블록으로 15개 성숙)
        self.mine_blocks(env, 120)
        exchange_tx = self.do_exchange(env, 500 * COIN)  # 5 POT
        mempool.add_tx(exchange_tx, blockchain.utxo_set, blockchain.get_height())
        self.mine_blocks(env, 1)

        # 3번 참여
        commits = []
        for i in range(3):
            numbers = [i, i, i, i, i, i]
            tx, pending, error = gacha_service.create_commit(
                wallet=wallet,
                utxo_set=blockchain.utxo_set,
                current_height=blockchain.get_height(),
                chosen_numbers=numbers
            )

            if tx is None:
                print(f"  Commit {i+1} failed: {error}")
                break

            mempool.add_tx(tx, blockchain.utxo_set, blockchain.get_height())
            self.mine_blocks(env, 1)

            gacha_service.update_commit_status(
                pending.commit_hash,
                tx.get_txid(),
                blockchain.get_height()
            )
            commits.append(pending)

        assert len(commits) >= 1, "At least one commit should succeed"
        print(f"[PASS] Multiple commits test: {len(commits)} commits created")

    def test_claim_timing_validation(self, setup_environment):
        """Claim 타이밍 검증 테스트"""
        env = setup_environment
        blockchain = env['blockchain']
        mempool = env['mempool']
        wallet = env['wallet']
        gacha_service = env['gacha_service']

        # 준비
        self.mine_blocks(env, 110)
        exchange_tx = self.do_exchange(env, 200 * COIN)
        mempool.add_tx(exchange_tx, blockchain.utxo_set, blockchain.get_height())
        self.mine_blocks(env, 1)

        # Commit
        commit_tx, pending, _ = gacha_service.create_commit(
            wallet=wallet,
            utxo_set=blockchain.utxo_set,
            current_height=blockchain.get_height(),
            chosen_numbers=[1, 2, 3, 4, 5, 6]
        )
        mempool.add_tx(commit_tx, blockchain.utxo_set, blockchain.get_height())
        self.mine_blocks(env, 1)

        commit_height = blockchain.get_height()
        gacha_service.update_commit_status(
            pending.commit_hash,
            commit_tx.get_txid(),
            commit_height
        )

        # 10블록만 채굴 (아직 claim 불가)
        self.mine_blocks(env, 10)

        # 너무 이른 Claim 시도
        early_claim_tx, error = gacha_service.create_claim(
            wallet=wallet,
            utxo_set=blockchain.utxo_set,
            commit_hash=pending.commit_hash,
            current_height=blockchain.get_height()
        )

        # 아직 claim 불가능해야 함
        assert early_claim_tx is None or "early" in error.lower() or "wait" in error.lower(), \
            "Early claim should be rejected"

        # 나머지 블록 채굴
        self.mine_blocks(env, 10)  # 총 20블록

        # 이제 claim 가능
        claim_tx, error = gacha_service.create_claim(
            wallet=wallet,
            utxo_set=blockchain.utxo_set,
            commit_hash=pending.commit_hash,
            current_height=blockchain.get_height()
        )

        assert claim_tx is not None, f"Claim should succeed now: {error}"

        print(f"[PASS] Timing validation test")

    def test_guaranteed_win_payout(self, setup_environment):
        """당첨금 지급 검증 (6등 보장 - 첫 비교 블록 매칭까지 재채굴)"""
        env = setup_environment
        blockchain = env['blockchain']
        mempool = env['mempool']
        wallet = env['wallet']
        miner_address = env['miner_address']
        gacha_service = env['gacha_service']
        gacha_game = env['gacha_game']

        from jackpotchain.consensus.miner import create_block_template, mine_block
        from jackpotchain.consensus.difficulty import get_next_difficulty

        print("\n=== 당첨 보장 테스트 (6등 이상) ===")

        # 1. 블록 채굴 (maturity)
        print("[1] 초기 블록 채굴 (110블록)...")
        self.mine_blocks(env, 110)

        # 2. POT 교환
        print("[2] JACK -> POT 교환...")
        exchange_tx = self.do_exchange(env, 200 * COIN)
        mempool.add_tx(exchange_tx, blockchain.utxo_set, blockchain.get_height())
        self.mine_blocks(env, 1)

        # 3. 커밋 생성 - 첫 숫자만 0으로 고정
        chosen_numbers = [0, 1, 2, 3, 4, 5]
        print(f"[3] 커밋 생성: {chosen_numbers}")

        commit_tx, pending, error = gacha_service.create_commit(
            wallet=wallet,
            utxo_set=blockchain.utxo_set,
            current_height=blockchain.get_height(),
            chosen_numbers=chosen_numbers
        )
        assert commit_tx is not None, f"Commit failed: {error}"

        mempool.add_tx(commit_tx, blockchain.utxo_set, blockchain.get_height())
        self.mine_blocks(env, 1)

        commit_height = blockchain.get_height()
        gacha_service.update_commit_status(
            pending.commit_hash, commit_tx.get_txid(), commit_height
        )
        print(f"  커밋 높이: {commit_height}")

        # 4. 첫 번째 비교 블록(N+3)이 매칭될 때까지 채굴
        target_height = commit_height + 3
        target_digit = chosen_numbers[0]  # 첫 번째 숫자

        print(f"[4] 블록 {target_height}이 숫자 {target_digit}(0x{target_digit:x})로 끝날 때까지 채굴...")

        # 먼저 N+1, N+2 채굴
        self.mine_blocks(env, 2)

        # N+3 블록은 해시 끝자리가 target_digit일 때까지 반복
        attempts = 0
        max_attempts = 100

        while attempts < max_attempts:
            attempts += 1

            # 템플릿 생성
            txs = mempool.get_txs_for_block()
            tip = blockchain.get_tip()
            difficulty = get_next_difficulty(
                blockchain.get_height(),
                blockchain.get_block_by_height
            )

            template = create_block_template(
                prev_block=tip,
                miner_address=miner_address,
                transactions=txs,
                difficulty_target=difficulty
            )

            # 채굴
            result = mine_block(template, max_nonce=100_000_000)
            if not result.success:
                continue

            # 해시 끝자리 확인
            block_hash = result.block.get_hash()
            last_digit = block_hash[-1] & 0x0F

            if last_digit == target_digit:
                # 매칭! 블록 추가
                success, msg = blockchain.add_block(result.block)
                assert success, f"Block add failed: {msg}"
                print(f"  시도 {attempts}: 블록 {blockchain.get_height()} 해시 ...{block_hash[-2:].hex()} -> 끝자리 {last_digit} 매치!")
                break
            else:
                # 불일치, nonce 바꿔서 재시도 (템플릿 timestamp 변경으로)
                import time
                time.sleep(0.01)  # timestamp 변경용

        assert blockchain.get_height() == target_height, f"블록 {target_height} 채굴 실패"

        # 5. 나머지 블록 채굴 (N+4 ~ N+18)
        remaining = 18 - 3
        print(f"[5] 나머지 {remaining}블록 채굴...")
        self.mine_blocks(env, remaining)

        # 6. 결과 확인
        result = gacha_game.check_result(
            commit_hash=pending.commit_hash,
            chosen_numbers=chosen_numbers,
            current_height=blockchain.get_height(),
            commit_height=commit_height
        )
        assert result is not None
        assert result.success

        print(f"  결과: {result.result_digits}")
        print(f"  매치: {result.matches}개 -> {result.prize.name}")
        print(f"  예상 지급: {result.payout_jack // COIN} JACK")

        # 최소 1개 매치 확인 (첫 번째 숫자는 보장됨)
        assert result.matches >= 1, f"첫 번째 숫자 매칭 보장했는데 {result.matches}개?"
        assert result.payout_jack > 0, "당첨인데 payout이 0"

        # 7. Claim 전 잔액 기록
        pool_before = sum(u.output.jack_value for u in blockchain.utxo_set.get_pool_utxos())

        # 8. Claim TX 생성 및 채굴
        print("[6] Claim TX 생성...")
        claim_tx, error = gacha_service.create_claim(
            wallet=wallet,
            utxo_set=blockchain.utxo_set,
            commit_hash=pending.commit_hash,
            current_height=blockchain.get_height()
        )
        assert claim_tx is not None, f"Claim failed: {error}"

        mempool.add_tx(claim_tx, blockchain.utxo_set, blockchain.get_height())
        self.mine_blocks(env, 1)

        # 9. 지급 검증
        pool_after = sum(u.output.jack_value for u in blockchain.utxo_set.get_pool_utxos())

        print(f"\n=== 당첨금 지급 결과 ===")
        print(f"풀: {pool_before // COIN} -> {pool_after // COIN} JACK")

        # 풀에서 당첨금 지급 확인
        assert pool_before > pool_after, "풀에서 당첨금이 빠져야 함"

        payout_from_pool = pool_before - pool_after
        print(f"\n[PASS] {result.prize.name} 당첨!")
        print(f"[PASS] 당첨금 {payout_from_pool // COIN} JACK 풀에서 지급 완료!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
