"""
Core 모듈 테스트
- Transaction, Block, UTXO
"""

import pytest
from jackpotchain.core.transaction import Transaction, TxInput, TxOutput, encode_varint, decode_varint
from jackpotchain.core.block import Block, BlockHeader, create_genesis_block
from jackpotchain.core.utxo import UTXO, UTXOSet
from jackpotchain.crypto.hash import double_sha256


class TestVarint:
    """가변 길이 정수 테스트"""

    def test_varint_small(self):
        """작은 값 (< 0xfd)"""
        for n in [0, 1, 100, 252]:
            encoded = encode_varint(n)
            decoded, offset = decode_varint(encoded, 0)
            assert decoded == n
            assert offset == 1

    def test_varint_medium(self):
        """중간 값 (0xfd ~ 0xffff)"""
        for n in [253, 1000, 65535]:
            encoded = encode_varint(n)
            decoded, offset = decode_varint(encoded, 0)
            assert decoded == n
            assert offset == 3

    def test_varint_large(self):
        """큰 값 (> 0xffff)"""
        for n in [65536, 100000, 0xffffffff]:
            encoded = encode_varint(n)
            decoded, offset = decode_varint(encoded, 0)
            assert decoded == n


class TestTransaction:
    """트랜잭션 테스트"""

    def test_create_simple_tx(self):
        """간단한 TX 생성"""
        inp = TxInput(
            prev_tx_id=bytes(32),
            output_index=0,
            script_sig=b'test_sig',
            sequence=0xFFFFFFFF
        )
        out = TxOutput(
            jack_value=1000000,
            script_pubkey=b'test_pubkey'
        )
        tx = Transaction(
            version=1,
            inputs=[inp],
            outputs=[out],
            locktime=0
        )

        assert tx.version == 1
        assert len(tx.inputs) == 1
        assert len(tx.outputs) == 1

    def test_tx_serialization(self):
        """TX 직렬화/역직렬화"""
        inp = TxInput(
            prev_tx_id=b'\x01' * 32,
            output_index=0,
            script_sig=b'signature',
            sequence=0xFFFFFFFF
        )
        out = TxOutput(
            jack_value=5000000000,
            script_pubkey=b'pubkey_script'
        )
        tx = Transaction(
            version=1,
            inputs=[inp],
            outputs=[out],
            locktime=0
        )

        serialized = tx.serialize()
        deserialized, _ = Transaction.deserialize(serialized)

        assert deserialized.version == tx.version
        assert deserialized.inputs[0].prev_tx_id == tx.inputs[0].prev_tx_id
        assert deserialized.outputs[0].jack_value == tx.outputs[0].jack_value

    def test_txid(self):
        """TXID 계산"""
        inp = TxInput(
            prev_tx_id=bytes(32),
            output_index=0xFFFFFFFF,
            script_sig=b'coinbase',
            sequence=0xFFFFFFFF
        )
        out = TxOutput(
            jack_value=5000000000,
            script_pubkey=b''
        )
        tx = Transaction(
            version=1,
            inputs=[inp],
            outputs=[out],
            locktime=0
        )

        txid = tx.get_txid()
        assert len(txid) == 32
        assert txid == double_sha256(tx.serialize())

    def test_is_coinbase(self):
        """Coinbase TX 판별"""
        # Coinbase TX
        coinbase_inp = TxInput(
            prev_tx_id=bytes(32),
            output_index=0xFFFFFFFF,
            script_sig=b'coinbase',
            sequence=0xFFFFFFFF
        )
        coinbase_tx = Transaction(
            version=1,
            inputs=[coinbase_inp],
            outputs=[TxOutput(jack_value=5000000000, script_pubkey=b'')],
            locktime=0
        )
        assert coinbase_tx.is_coinbase() is True

        # 일반 TX
        normal_inp = TxInput(
            prev_tx_id=b'\x01' * 32,
            output_index=0,
            script_sig=b'sig',
            sequence=0xFFFFFFFF
        )
        normal_tx = Transaction(
            version=1,
            inputs=[normal_inp],
            outputs=[TxOutput(jack_value=1000000, script_pubkey=b'')],
            locktime=0
        )
        assert normal_tx.is_coinbase() is False

    def test_multi_asset_output(self):
        """멀티 에셋 출력"""
        out = TxOutput(
            jack_value=1000000,
            script_pubkey=b'test',
            assets={'POT': 100000000}
        )
        assert out.jack_value == 1000000
        assert out.assets['POT'] == 100000000


class TestBlock:
    """블록 테스트"""

    def test_create_genesis(self):
        """Genesis 블록 생성"""
        genesis = create_genesis_block()

        assert genesis.header.version == 1
        assert genesis.header.prev_block_hash == bytes(32)
        assert len(genesis.transactions) >= 1
        assert genesis.transactions[0].is_coinbase()

    def test_block_serialization(self):
        """블록 직렬화/역직렬화"""
        genesis = create_genesis_block()
        serialized = genesis.serialize()
        deserialized, _ = Block.deserialize(serialized)

        assert deserialized.header.version == genesis.header.version
        assert deserialized.header.timestamp == genesis.header.timestamp
        assert deserialized.get_hash() == genesis.get_hash()

    def test_block_hash(self):
        """블록 해시"""
        genesis = create_genesis_block()
        hash1 = genesis.get_hash()
        hash2 = genesis.get_hash()

        assert len(hash1) == 32
        assert hash1 == hash2  # 결정론적

    def test_merkle_root(self):
        """Merkle Root 계산"""
        genesis = create_genesis_block()

        calculated = genesis.calculate_merkle_root()
        assert len(calculated) == 32

        # 헤더의 merkle_root와 일치해야 함
        assert genesis.verify_merkle_root()

    def test_block_header_serialization(self):
        """블록 헤더 직렬화 (80 bytes)"""
        genesis = create_genesis_block()
        header_bytes = genesis.header.serialize()

        assert len(header_bytes) == 80


class TestUTXO:
    """UTXO 테스트"""

    def test_utxo_creation(self):
        """UTXO 생성"""
        out = TxOutput(jack_value=1000000, script_pubkey=b'test')
        utxo = UTXO(
            tx_id=b'\x01' * 32,
            output_index=0,
            output=out,
            block_height=100
        )

        assert utxo.output.jack_value == 1000000
        assert utxo.block_height == 100

    def test_utxo_maturity(self):
        """Coinbase 성숙도"""
        out = TxOutput(jack_value=5000000000, script_pubkey=b'')
        utxo = UTXO(
            tx_id=b'\x01' * 32,
            output_index=0,
            output=out,
            block_height=100,
            is_coinbase=True
        )

        # 100블록 후에 성숙
        assert utxo.is_mature(150) is False
        assert utxo.is_mature(199) is False
        assert utxo.is_mature(200) is True
        assert utxo.is_mature(300) is True

    def test_utxo_set_add_remove(self):
        """UTXOSet 추가/제거"""
        utxo_set = UTXOSet()

        out = TxOutput(jack_value=1000000, script_pubkey=b'test')
        utxo = UTXO(
            tx_id=b'\x01' * 32,
            output_index=0,
            output=out,
            block_height=1
        )

        # 추가
        utxo_set.add_utxo(utxo, 'test_address')
        assert utxo_set.has_utxo(b'\x01' * 32, 0) is True
        assert len(utxo_set) == 1

        # 제거
        removed = utxo_set.remove_utxo(b'\x01' * 32, 0)
        assert removed is not None
        assert utxo_set.has_utxo(b'\x01' * 32, 0) is False
        assert len(utxo_set) == 0

    def test_utxo_set_balance(self):
        """UTXOSet 잔액 계산"""
        utxo_set = UTXOSet()
        address = 'test_address'

        # 3개 UTXO 추가
        for i in range(3):
            out = TxOutput(jack_value=1000000 * (i + 1), script_pubkey=b'test')
            utxo = UTXO(
                tx_id=bytes([i] * 32),
                output_index=0,
                output=out,
                block_height=1
            )
            utxo_set.add_utxo(utxo, address)

        # 잔액 = 1 + 2 + 3 = 6 (단위: 1000000)
        balance = utxo_set.get_balance(address)
        assert balance == 6000000


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
