"""
Step 11: 저장소
- 블록/TX 영구 저장
- 인덱스 관리
"""

import os
import json
import struct
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from ..core.block import Block
from ..core.transaction import Transaction
from ..core.utxo import UTXO, UTXOSet
from ..constants import get_default_data_dir


class BlockStore:
    """
    블록 저장소 (파일 기반)

    구조:
    - blocks/  : 블록 데이터 (블록 해시별)
    - index/   : 인덱스 (높이 → 해시)
    - utxo/    : UTXO 스냅샷
    """

    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir or get_default_data_dir())
        self.blocks_dir = self.data_dir / "blocks"
        self.index_dir = self.data_dir / "index"
        self.utxo_dir = self.data_dir / "utxo"

        # 디렉토리 생성
        self.blocks_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.utxo_dir.mkdir(parents=True, exist_ok=True)

        # 메모리 인덱스
        self._height_to_hash: Dict[int, bytes] = {}
        self._hash_to_height: Dict[bytes, int] = {}

        # 인덱스 로드
        self._load_index()

    def _load_index(self):
        """인덱스 로드"""
        index_file = self.index_dir / "height_index.dat"
        if index_file.exists():
            with open(index_file, 'rb') as f:
                while True:
                    data = f.read(36)  # 4 bytes height + 32 bytes hash
                    if len(data) < 36:
                        break
                    height = struct.unpack('<I', data[:4])[0]
                    block_hash = data[4:36]
                    self._height_to_hash[height] = block_hash
                    self._hash_to_height[block_hash] = height

    def _save_index(self):
        """인덱스 저장 (Atomic - 크래시 안전)"""
        index_file = self.index_dir / "height_index.dat"
        temp_file = self.index_dir / "height_index.dat.tmp"

        # 임시 파일에 먼저 저장
        with open(temp_file, 'wb') as f:
            for height, block_hash in sorted(self._height_to_hash.items()):
                f.write(struct.pack('<I', height) + block_hash)
            f.flush()
            os.fsync(f.fileno())  # 디스크에 확실히 기록

        # 원자적 교체 (크래시 시에도 안전)
        os.replace(temp_file, index_file)

    def _block_path(self, block_hash: bytes) -> Path:
        """블록 파일 경로"""
        hex_hash = block_hash.hex()
        subdir = hex_hash[:2]
        return self.blocks_dir / subdir / f"{hex_hash}.blk"

    def save_block(self, block: Block, height: int):
        """블록 저장"""
        block_hash = block.get_hash()
        path = self._block_path(block_hash)
        path.parent.mkdir(exist_ok=True)

        with open(path, 'wb') as f:
            f.write(block.serialize())

        # 인덱스 업데이트
        self._height_to_hash[height] = block_hash
        self._hash_to_height[block_hash] = height
        self._save_index()

    def load_block(self, block_hash: bytes) -> Optional[Block]:
        """블록 로드"""
        path = self._block_path(block_hash)
        if not path.exists():
            return None

        with open(path, 'rb') as f:
            data = f.read()
            block, _ = Block.deserialize(data)
            return block

    def load_block_by_height(self, height: int) -> Optional[Block]:
        """높이로 블록 로드"""
        block_hash = self._height_to_hash.get(height)
        if block_hash:
            return self.load_block(block_hash)
        return None

    def get_height(self, block_hash: bytes) -> Optional[int]:
        """블록 높이 조회"""
        return self._hash_to_height.get(block_hash)

    def get_tip_height(self) -> int:
        """최신 높이"""
        if not self._height_to_hash:
            return -1
        return max(self._height_to_hash.keys())

    def get_tip_hash(self) -> bytes:
        """최신 블록 해시"""
        height = self.get_tip_height()
        return self._height_to_hash.get(height, bytes(32))

    def has_block(self, block_hash: bytes) -> bool:
        """블록 존재 여부"""
        return block_hash in self._hash_to_height

    def delete_block(self, block_hash: bytes):
        """블록 삭제"""
        height = self._hash_to_height.pop(block_hash, None)
        if height is not None:
            self._height_to_hash.pop(height, None)
            self._save_index()

        path = self._block_path(block_hash)
        if path.exists():
            path.unlink()


class TxIndex:
    """트랜잭션 인덱스 (txid → 블록 위치)"""

    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir or get_default_data_dir())
        self.index_file = self.data_dir / "index" / "tx_index.dat"

        # txid → (block_hash, tx_index_in_block)
        self._index: Dict[bytes, Tuple[bytes, int]] = {}
        self._load()

    def _load(self):
        """인덱스 로드"""
        if self.index_file.exists():
            with open(self.index_file, 'rb') as f:
                while True:
                    data = f.read(68)  # 32 + 32 + 4
                    if len(data) < 68:
                        break
                    txid = data[:32]
                    block_hash = data[32:64]
                    tx_index = struct.unpack('<I', data[64:68])[0]
                    self._index[txid] = (block_hash, tx_index)

    def _save(self):
        """인덱스 저장"""
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_file, 'wb') as f:
            for txid, (block_hash, tx_index) in self._index.items():
                f.write(txid + block_hash + struct.pack('<I', tx_index))

    def add_block_txs(self, block: Block, block_hash: bytes):
        """블록의 TX들 인덱싱"""
        for i, tx in enumerate(block.transactions):
            self._index[tx.get_txid()] = (block_hash, i)
        self._save()

    def remove_block_txs(self, block: Block):
        """블록의 TX들 제거"""
        for tx in block.transactions:
            self._index.pop(tx.get_txid(), None)
        self._save()

    def get_tx_location(self, txid: bytes) -> Optional[Tuple[bytes, int]]:
        """TX 위치 조회"""
        return self._index.get(txid)

    def has_tx(self, txid: bytes) -> bool:
        """TX 존재 여부"""
        return txid in self._index
