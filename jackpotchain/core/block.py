"""
Step 2.2: 블록 구조
- BlockHeader, Block
"""

import struct
import time
from typing import List, Optional
from dataclasses import dataclass, field

from ..crypto.hash import double_sha256
from ..crypto.merkle import build_merkle_tree
from ..constants import (
    INITIAL_DIFFICULTY,
    GENESIS_TIMESTAMP,
    GENESIS_MESSAGE,
    BLOCK_REWARD,
)
from .transaction import Transaction, TxInput, TxOutput, encode_varint, decode_varint


@dataclass
class BlockHeader:
    """블록 헤더 (80 bytes)"""
    version: int = 1                    # 버전 (4 bytes)
    prev_block_hash: bytes = bytes(32)  # 이전 블록 해시 (32 bytes)
    merkle_root: bytes = bytes(32)      # Merkle Root (32 bytes)
    timestamp: int = 0                  # Unix timestamp (4 bytes)
    difficulty_target: int = INITIAL_DIFFICULTY  # 난이도 (4 bytes, compact)
    nonce: int = 0                      # PoW 해답 (4 bytes)

    def serialize(self) -> bytes:
        """직렬화 (80 bytes)"""
        return (
            struct.pack('<I', self.version) +
            self.prev_block_hash[::-1] +  # little-endian
            self.merkle_root[::-1] +      # little-endian
            struct.pack('<I', self.timestamp) +
            struct.pack('<I', self.difficulty_target) +
            struct.pack('<I', self.nonce)
        )

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> tuple:
        """역직렬화, (BlockHeader, 새 offset) 반환"""
        version = struct.unpack('<I', data[offset:offset+4])[0]
        offset += 4

        prev_block_hash = data[offset:offset+32][::-1]  # big-endian
        offset += 32

        merkle_root = data[offset:offset+32][::-1]  # big-endian
        offset += 32

        timestamp = struct.unpack('<I', data[offset:offset+4])[0]
        offset += 4

        difficulty_target = struct.unpack('<I', data[offset:offset+4])[0]
        offset += 4

        nonce = struct.unpack('<I', data[offset:offset+4])[0]
        offset += 4

        return cls(version, prev_block_hash, merkle_root, timestamp, difficulty_target, nonce), offset

    def get_hash(self) -> bytes:
        """블록 해시 (double SHA256)"""
        return double_sha256(self.serialize())

    def get_hash_hex(self) -> str:
        """블록 해시 (hex, 역순 - 일반적인 표시 방식)"""
        return self.get_hash()[::-1].hex()

    def get_target(self) -> int:
        """compact 난이도 → 256비트 target"""
        # compact format: 0x1d00ffff
        # 첫 바이트: 지수, 나머지 3바이트: 계수
        exponent = self.difficulty_target >> 24
        coefficient = self.difficulty_target & 0x00ffffff

        # target = coefficient * 2^(8 * (exponent - 3))
        if exponent <= 3:
            target = coefficient >> (8 * (3 - exponent))
        else:
            target = coefficient << (8 * (exponent - 3))

        return target

    def verify_pow(self) -> bool:
        """PoW 검증: hash < target"""
        block_hash = self.get_hash()
        hash_int = int.from_bytes(block_hash, 'big')
        target = self.get_target()
        return hash_int < target


@dataclass
class Block:
    """블록"""
    header: BlockHeader = field(default_factory=BlockHeader)
    transactions: List[Transaction] = field(default_factory=list)

    _hash: Optional[bytes] = field(default=None, repr=False, compare=False)

    def serialize(self) -> bytes:
        """직렬화"""
        result = self.header.serialize()
        result += encode_varint(len(self.transactions))
        for tx in self.transactions:
            result += tx.serialize()
        return result

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> tuple:
        """역직렬화, (Block, 새 offset) 반환"""
        header, offset = BlockHeader.deserialize(data, offset)

        tx_count, offset = decode_varint(data, offset)
        transactions = []
        for _ in range(tx_count):
            tx, offset = Transaction.deserialize(data, offset)
            transactions.append(tx)

        return cls(header, transactions), offset

    def get_hash(self) -> bytes:
        """블록 해시"""
        if self._hash is None:
            self._hash = self.header.get_hash()
        return self._hash

    def get_hash_hex(self) -> str:
        """블록 해시 (hex)"""
        return self.header.get_hash_hex()

    def calculate_merkle_root(self) -> bytes:
        """트랜잭션들로 Merkle Root 계산"""
        if not self.transactions:
            return bytes(32)
        tx_hashes = [tx.get_txid() for tx in self.transactions]
        return build_merkle_tree(tx_hashes)

    def verify_merkle_root(self) -> bool:
        """Merkle Root 검증"""
        return self.header.merkle_root == self.calculate_merkle_root()

    def verify_pow(self) -> bool:
        """PoW 검증"""
        return self.header.verify_pow()

    def get_coinbase(self) -> Optional[Transaction]:
        """Coinbase TX 반환"""
        if self.transactions and self.transactions[0].is_coinbase():
            return self.transactions[0]
        return None

    def size(self) -> int:
        """블록 크기 (바이트)"""
        return len(self.serialize())

    def tx_count(self) -> int:
        """트랜잭션 개수"""
        return len(self.transactions)

    def __hash__(self):
        return hash(self.get_hash())

    def __eq__(self, other):
        if isinstance(other, Block):
            return self.get_hash() == other.get_hash()
        return False


def create_genesis_block(miner_address: str = None) -> Block:
    """
    Genesis Block 생성 (하드코딩)
    - Output 0: 블록 보상 50 JACK (채굴자)
    - Output 1: 잭팟풀 초기 자금 1,000,000 JACK

    모든 노드가 동일한 제네시스 블록을 사용하도록 값이 하드코딩됨.
    """
    from ..crypto.address import JACKPOT_POOL_ADDRESS
    from ..constants import (
        GENESIS_JACKPOT_POOL_FUNDING,
        GENESIS_NONCE,
        GENESIS_MERKLE_ROOT,
    )

    # Genesis Coinbase TX
    coinbase_input = TxInput(
        prev_tx_id=bytes(32),
        output_index=0xFFFFFFFF,
        script_sig=GENESIS_MESSAGE,
        sequence=0xFFFFFFFF
    )

    # Output 0: 채굴자 보상
    coinbase_output = TxOutput(
        jack_value=BLOCK_REWARD,
        script_pubkey=b''  # Genesis는 특수 처리
    )

    # Output 1: 잭팟풀 초기 자금
    jackpot_pool_output = TxOutput(
        jack_value=GENESIS_JACKPOT_POOL_FUNDING,
        script_pubkey=b'JACKPOT_POOL'  # 잭팟풀 특수 마커
    )

    coinbase_tx = Transaction(
        version=1,
        inputs=[coinbase_input],
        outputs=[coinbase_output, jackpot_pool_output],
        locktime=0
    )

    # 블록 헤더 (하드코딩된 값 사용)
    header = BlockHeader(
        version=1,
        prev_block_hash=bytes(32),
        merkle_root=GENESIS_MERKLE_ROOT,  # 하드코딩
        timestamp=GENESIS_TIMESTAMP,
        difficulty_target=INITIAL_DIFFICULTY,
        nonce=GENESIS_NONCE  # 하드코딩
    )

    block = Block(header=header, transactions=[coinbase_tx])

    return block
