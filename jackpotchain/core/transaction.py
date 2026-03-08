"""
Step 2.1: 트랜잭션 구조
- TxInput, TxOutput, Transaction
"""

import struct
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from ..crypto.hash import double_sha256
from ..constants import (
    TX_VERSION_TRANSFER,
    SEQUENCE_FINAL,
    JACK_ASSET_ID,
)


def encode_varint(n: int) -> bytes:
    """가변 길이 정수 인코딩 (Bitcoin 스타일)"""
    if n < 0xfd:
        return struct.pack('<B', n)
    elif n <= 0xffff:
        return b'\xfd' + struct.pack('<H', n)
    elif n <= 0xffffffff:
        return b'\xfe' + struct.pack('<I', n)
    else:
        return b'\xff' + struct.pack('<Q', n)


def decode_varint(data: bytes, offset: int = 0) -> tuple:
    """가변 길이 정수 디코딩, (값, 새 offset) 반환"""
    first = data[offset]
    if first < 0xfd:
        return first, offset + 1
    elif first == 0xfd:
        return struct.unpack('<H', data[offset+1:offset+3])[0], offset + 3
    elif first == 0xfe:
        return struct.unpack('<I', data[offset+1:offset+5])[0], offset + 5
    else:
        return struct.unpack('<Q', data[offset+1:offset+9])[0], offset + 9


def encode_varstr(s: bytes) -> bytes:
    """가변 길이 문자열 인코딩"""
    return encode_varint(len(s)) + s


def decode_varstr(data: bytes, offset: int = 0) -> tuple:
    """가변 길이 문자열 디코딩, (bytes, 새 offset) 반환"""
    length, offset = decode_varint(data, offset)
    return data[offset:offset+length], offset + length


@dataclass
class TxInput:
    """트랜잭션 입력"""
    prev_tx_id: bytes          # 이전 TX 해시 (32 bytes)
    output_index: int          # Output 인덱스 (4 bytes)
    script_sig: bytes = b''    # 서명 스크립트 (가변)
    sequence: int = SEQUENCE_FINAL  # 시퀀스 번호 (4 bytes)

    def serialize(self) -> bytes:
        """직렬화"""
        return (
            self.prev_tx_id[::-1] +  # little-endian
            struct.pack('<I', self.output_index) +
            encode_varstr(self.script_sig) +
            struct.pack('<I', self.sequence)
        )

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> tuple:
        """역직렬화, (TxInput, 새 offset) 반환"""
        prev_tx_id = data[offset:offset+32][::-1]  # big-endian으로 변환
        offset += 32

        output_index = struct.unpack('<I', data[offset:offset+4])[0]
        offset += 4

        script_sig, offset = decode_varstr(data, offset)

        sequence = struct.unpack('<I', data[offset:offset+4])[0]
        offset += 4

        return cls(prev_tx_id, output_index, script_sig, sequence), offset

    def is_coinbase(self) -> bool:
        """Coinbase 입력인지 확인"""
        return self.prev_tx_id == bytes(32) and self.output_index == 0xFFFFFFFF


@dataclass
class TxOutput:
    """트랜잭션 출력 (멀티에셋 지원)"""
    jack_value: int            # JACK 금액 (satoshi, 8 bytes)
    assets: Dict[str, int] = field(default_factory=dict)  # 추가 에셋 {asset_id: amount}
    script_pubkey: bytes = b'' # 잠금 스크립트 (가변)

    def serialize(self) -> bytes:
        """직렬화"""
        result = struct.pack('<Q', self.jack_value)

        # 에셋 맵 직렬화
        result += encode_varint(len(self.assets))
        for asset_id, amount in sorted(self.assets.items()):
            result += encode_varstr(asset_id.encode('utf-8'))
            result += struct.pack('<Q', amount)

        result += encode_varstr(self.script_pubkey)
        return result

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> tuple:
        """역직렬화, (TxOutput, 새 offset) 반환"""
        jack_value = struct.unpack('<Q', data[offset:offset+8])[0]
        offset += 8

        asset_count, offset = decode_varint(data, offset)
        assets = {}
        for _ in range(asset_count):
            asset_id_bytes, offset = decode_varstr(data, offset)
            asset_id = asset_id_bytes.decode('utf-8')
            amount = struct.unpack('<Q', data[offset:offset+8])[0]
            offset += 8
            assets[asset_id] = amount

        script_pubkey, offset = decode_varstr(data, offset)

        return cls(jack_value, assets, script_pubkey), offset

    def get_total_value(self, asset_id: str = JACK_ASSET_ID) -> int:
        """특정 에셋의 값 반환"""
        if asset_id == JACK_ASSET_ID:
            return self.jack_value
        return self.assets.get(asset_id, 0)

    def is_op_return(self) -> bool:
        """OP_RETURN 출력인지 확인"""
        return len(self.script_pubkey) > 0 and self.script_pubkey[0] == 0x6a


@dataclass
class Transaction:
    """트랜잭션"""
    version: int = TX_VERSION_TRANSFER  # 버전 (4 bytes)
    inputs: List[TxInput] = field(default_factory=list)
    outputs: List[TxOutput] = field(default_factory=list)
    locktime: int = 0          # 잠금 시간 (4 bytes)

    _txid: Optional[bytes] = field(default=None, repr=False, compare=False)

    def serialize(self) -> bytes:
        """직렬화"""
        result = struct.pack('<I', self.version)

        # Inputs
        result += encode_varint(len(self.inputs))
        for inp in self.inputs:
            result += inp.serialize()

        # Outputs
        result += encode_varint(len(self.outputs))
        for out in self.outputs:
            result += out.serialize()

        result += struct.pack('<I', self.locktime)
        return result

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> tuple:
        """역직렬화, (Transaction, 새 offset) 반환"""
        version = struct.unpack('<I', data[offset:offset+4])[0]
        offset += 4

        input_count, offset = decode_varint(data, offset)
        inputs = []
        for _ in range(input_count):
            inp, offset = TxInput.deserialize(data, offset)
            inputs.append(inp)

        output_count, offset = decode_varint(data, offset)
        outputs = []
        for _ in range(output_count):
            out, offset = TxOutput.deserialize(data, offset)
            outputs.append(out)

        locktime = struct.unpack('<I', data[offset:offset+4])[0]
        offset += 4

        return cls(version, inputs, outputs, locktime), offset

    def get_txid(self) -> bytes:
        """TX ID (double SHA256)"""
        if self._txid is None:
            self._txid = double_sha256(self.serialize())
        return self._txid

    def get_txid_hex(self) -> str:
        """TX ID (hex 문자열, 역순)"""
        return self.get_txid()[::-1].hex()

    def is_coinbase(self) -> bool:
        """Coinbase TX인지 확인"""
        return (
            len(self.inputs) == 1 and
            self.inputs[0].is_coinbase()
        )

    def get_input_sum(self, utxo_getter) -> Dict[str, int]:
        """
        Input 합계 계산
        utxo_getter: (tx_id, output_index) -> TxOutput
        """
        totals = {JACK_ASSET_ID: 0}

        for inp in self.inputs:
            utxo = utxo_getter(inp.prev_tx_id, inp.output_index)
            if utxo:
                totals[JACK_ASSET_ID] += utxo.jack_value
                for asset_id, amount in utxo.assets.items():
                    totals[asset_id] = totals.get(asset_id, 0) + amount

        return totals

    def get_output_sum(self) -> Dict[str, int]:
        """Output 합계 계산"""
        totals = {JACK_ASSET_ID: 0}

        for out in self.outputs:
            if not out.is_op_return():  # OP_RETURN 제외
                totals[JACK_ASSET_ID] += out.jack_value
                for asset_id, amount in out.assets.items():
                    totals[asset_id] = totals.get(asset_id, 0) + amount

        return totals

    def size(self) -> int:
        """TX 크기 (바이트)"""
        return len(self.serialize())

    def __hash__(self):
        return hash(self.get_txid())

    def __eq__(self, other):
        if isinstance(other, Transaction):
            return self.get_txid() == other.get_txid()
        return False
