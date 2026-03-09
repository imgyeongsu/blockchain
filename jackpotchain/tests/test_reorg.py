"""
Reorg UTXO 재계산 테스트

시나리오:
1. Genesis → Block A → Block B (메인 체인)
2. Genesis → Block A' → Block B' → Block C' (포크 체인, 더 김)
3. Reorg 발생 → UTXO 상태 검증
"""

import pytest
from jackpotchain.core.transaction import Transaction, TxInput, TxOutput
from jackpotchain.core.block import Block, BlockHeader, create_genesis_block
from jackpotchain.core.utxo import UTXO, UTXOSet
from jackpotchain.consensus.chain import Blockchain, ChainState
from jackpotchain.crypto.hash import double_sha256
import time


def create_coinbase_tx(address: bytes, value: int = 5000000000, height: int = 0) -> Transaction:
    """Coinbase TX 생성"""
    # height를 script_sig에 인코딩 (BIP34)
    height_bytes = height.to_bytes((height.bit_length() + 7) // 8 or 1, 'little')
    script_sig = bytes([len(height_bytes)]) + height_bytes + b'coinbase'

    inp = TxInput(
        prev_tx_id=bytes(32),
        output_index=0xFFFFFFFF,
        script_sig=script_sig,
        sequence=0xFFFFFFFF
    )
    out = TxOutput(
        jack_value=value,
        script_pubkey=address
    )
    return Transaction(version=1, inputs=[inp], outputs=[out], locktime=0)


def create_transfer_tx(
    prev_tx_id: bytes,
    output_index: int,
    to_address: bytes,
    value: int,
    signature: bytes = b'test_sig'
) -> Transaction:
    """일반 전송 TX 생성"""
    inp = TxInput(
        prev_tx_id=prev_tx_id,
        output_index=output_index,
        script_sig=signature,
        sequence=0xFFFFFFFF
    )
    out = TxOutput(
        jack_value=value,
        script_pubkey=to_address
    )
    return Transaction(version=1, inputs=[inp], outputs=[out], locktime=0)


def create_block(
    prev_block: Block,
    transactions: list,
    nonce: int = 0
) -> Block:
    """블록 생성 (테스트용, PoW 검증 안 함)"""
    # Merkle root 계산
    if not transactions:
        merkle_root = bytes(32)
    elif len(transactions) == 1:
        merkle_root = transactions[0].get_txid()
    else:
        # 간단한 merkle root (실제로는 더 복잡함)
        hashes = [tx.get_txid() for tx in transactions]
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])
            hashes = [
                double_sha256(hashes[i] + hashes[i+1])
                for i in range(0, len(hashes), 2)
            ]
        merkle_root = hashes[0]

    header = BlockHeader(
        version=1,
        prev_block_hash=prev_block.get_hash(),
        merkle_root=merkle_root,
        timestamp=prev_block.header.timestamp + 600,  # 10분 후
        difficulty_target=0x1f00ffff,  # 쉬운 난이도 (테스트용)
        nonce=nonce
    )

    return Block(header=header, transactions=transactions)


class TestReorgUTXO:
    """Reorg UTXO 재계산 테스트"""

    def setup_method(self):
        """각 테스트 전 초기화"""
        # 주소 (테스트용)
        self.alice = b'alice_address_pubkey'
        self.bob = b'bob_address_pubkey'
        self.charlie = b'charlie_address_pubkey'

    def test_simple_chain_utxo(self):
        """기본 체인 UTXO 테스트 (Reorg 없음)"""
        # Genesis 생성
        genesis = create_genesis_block()
        chain = Blockchain(genesis_block=genesis)

        # Genesis의 coinbase UTXO 확인 (자동 적용됨)
        genesis_coinbase = genesis.transactions[0]
        genesis_txid = genesis_coinbase.get_txid()

        assert chain.utxo_set.has_utxo(genesis_txid, 0)
        assert chain.get_height() == 0

    def test_reorg_restores_spent_utxo(self):
        """
        Reorg 시 소비된 UTXO가 복원되는지 테스트

        시나리오:
        - Block 1: Alice에게 coinbase 지급
        - Block 2 (main): Alice → Bob 전송
        - Block 2' (fork): Alice → Charlie 전송
        - Block 3' (fork): Charlie coinbase

        Reorg 후:
        - Bob의 UTXO는 없어야 함 (되돌려짐)
        - Charlie의 UTXO가 있어야 함
        - Alice의 원래 UTXO는 Charlie에게 소비됨
        """
        # Genesis (UTXO 자동 적용됨)
        genesis = create_genesis_block()
        chain = Blockchain(genesis_block=genesis)

        # Block 1: Alice에게 5 JACK (UTXO 자동 적용됨)
        coinbase1 = create_coinbase_tx(self.alice, 5000000000, height=1)
        block1 = create_block(genesis, [coinbase1], nonce=1)

        success, msg = chain.add_block(block1)
        assert success, f"Block 1 추가 실패: {msg}"

        alice_txid = coinbase1.get_txid()
        assert chain.utxo_set.has_utxo(alice_txid, 0), "Alice UTXO가 없음"

        # Block 2 (main): Alice → Bob 5 JACK
        transfer_to_bob = create_transfer_tx(
            prev_tx_id=alice_txid,
            output_index=0,
            to_address=self.bob,
            value=5000000000
        )
        coinbase2 = create_coinbase_tx(b'miner1', 5000000000, height=2)
        block2 = create_block(block1, [coinbase2, transfer_to_bob], nonce=2)

        success, msg = chain.add_block(block2)
        assert success, f"Block 2 추가 실패: {msg}"
        # UTXO 자동 적용됨 (add_block 내부에서 _connect_block 호출)

        bob_txid = transfer_to_bob.get_txid()

        # 상태 확인: Alice UTXO 소비됨, Bob UTXO 생성됨
        assert not chain.utxo_set.has_utxo(alice_txid, 0), "Alice UTXO가 아직 있음 (소비되어야 함)"
        assert chain.utxo_set.has_utxo(bob_txid, 0), "Bob UTXO가 없음"

        print(f"\n[Before Reorg]")
        print(f"  Height: {chain.get_height()}")
        print(f"  Alice UTXO: {chain.utxo_set.has_utxo(alice_txid, 0)}")
        print(f"  Bob UTXO: {chain.utxo_set.has_utxo(bob_txid, 0)}")

        # === Fork 체인 생성 (더 긴 체인) ===

        # Block 2' (fork): Alice → Charlie 5 JACK
        transfer_to_charlie = create_transfer_tx(
            prev_tx_id=alice_txid,
            output_index=0,
            to_address=self.charlie,
            value=5000000000
        )
        coinbase2_fork = create_coinbase_tx(b'miner2', 5000000000, height=2)
        block2_fork = create_block(block1, [coinbase2_fork, transfer_to_charlie], nonce=100)

        # Block 3' (fork): 추가 블록으로 체인 길이 증가
        coinbase3_fork = create_coinbase_tx(b'miner3', 5000000000, height=3)
        block3_fork = create_block(block2_fork, [coinbase3_fork], nonce=101)

        # Fork 블록 추가 (Block 2'는 side chain으로 추가됨)
        success, msg = chain.add_block(block2_fork)
        assert success, f"Block 2' 추가 실패: {msg}"
        print(f"\nBlock 2' added: {msg}")

        # Block 3' 추가 → 여기서 Reorg 발생해야 함!
        success, msg = chain.add_block(block3_fork)
        assert success, f"Block 3' 추가 실패: {msg}"
        print(f"Block 3' added: {msg}")

        charlie_txid = transfer_to_charlie.get_txid()

        print(f"\n[After Reorg]")
        print(f"  Height: {chain.get_height()}")
        print(f"  Chain state: {chain.state}")
        print(f"  Alice UTXO: {chain.utxo_set.has_utxo(alice_txid, 0)}")
        print(f"  Bob UTXO: {chain.utxo_set.has_utxo(bob_txid, 0)}")
        print(f"  Charlie UTXO: {chain.utxo_set.has_utxo(charlie_txid, 0)}")

        # === Reorg 후 UTXO 상태 검증 ===

        # 높이가 3이어야 함
        assert chain.get_height() == 3, f"Height should be 3, got {chain.get_height()}"

        # Bob의 UTXO는 없어야 함 (Block 2가 되돌려짐)
        # 이 테스트는 현재 구현에서 실패할 것임 (TODO: UTXO disconnect 구현 필요)
        assert not chain.utxo_set.has_utxo(bob_txid, 0), \
            "Bob UTXO should be removed after reorg"

        # Charlie의 UTXO가 있어야 함 (Block 2' 적용됨)
        # 이 테스트도 현재 구현에서 실패할 것임 (TODO: UTXO connect 구현 필요)
        assert chain.utxo_set.has_utxo(charlie_txid, 0), \
            "Charlie UTXO should exist after reorg"

        # Alice의 원래 UTXO는 소비되어야 함
        assert not chain.utxo_set.has_utxo(alice_txid, 0), \
            "Alice UTXO should be spent (by Charlie transfer)"


class TestUTXORevert:
    """UTXOSet.revert_transaction 테스트"""

    def test_revert_simple_transfer(self):
        """간단한 전송 TX 되돌리기"""
        utxo_set = UTXOSet()

        # 초기 상태: Alice가 10 JACK 가짐
        alice_addr = b'alice'
        initial_utxo = UTXO(
            tx_id=b'\x01' * 32,
            output_index=0,
            output=TxOutput(jack_value=10000000, script_pubkey=alice_addr),
            block_height=1
        )
        utxo_set.add_utxo(initial_utxo, 'alice')

        # TX: Alice → Bob 10 JACK
        bob_addr = b'bob'
        transfer_tx = Transaction(
            version=1,
            inputs=[TxInput(
                prev_tx_id=b'\x01' * 32,
                output_index=0,
                script_sig=b'sig',
                sequence=0xFFFFFFFF
            )],
            outputs=[TxOutput(jack_value=10000000, script_pubkey=bob_addr)],
            locktime=0
        )

        # TX 적용
        utxo_set.apply_transaction(transfer_tx, 2)

        tx_id = transfer_tx.get_txid()
        assert not utxo_set.has_utxo(b'\x01' * 32, 0), "Alice UTXO should be spent"
        assert utxo_set.has_utxo(tx_id, 0), "Bob UTXO should exist"

        # TX 되돌리기
        utxo_set.revert_transaction(transfer_tx, [initial_utxo])

        # 상태 확인: 원래대로 복원
        assert utxo_set.has_utxo(b'\x01' * 32, 0), "Alice UTXO should be restored"
        assert not utxo_set.has_utxo(tx_id, 0), "Bob UTXO should be removed"


class TestBlockUndoData:
    """블록 Undo 데이터 테스트 (구현 예정)"""

    @pytest.mark.skip(reason="BlockUndo 구현 후 활성화")
    def test_undo_data_creation(self):
        """블록 적용 시 undo 데이터 생성"""
        pass

    @pytest.mark.skip(reason="BlockUndo 구현 후 활성화")
    def test_undo_data_application(self):
        """undo 데이터로 블록 되돌리기"""
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
