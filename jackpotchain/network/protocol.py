"""
Step 8.1: 네트워크 프로토콜
- 메시지 타입 정의
- 직렬화/역직렬화
"""

import struct
import hashlib
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from ..constants import NETWORK_MAGIC


class MessageType(Enum):
    """메시지 타입"""
    # 핸드셰이크
    VERSION = b'version\x00\x00\x00\x00\x00'
    VERACK = b'verack\x00\x00\x00\x00\x00\x00'

    # 인벤토리
    INV = b'inv\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    GETDATA = b'getdata\x00\x00\x00\x00\x00'
    NOTFOUND = b'notfound\x00\x00\x00\x00'

    # 블록
    BLOCK = b'block\x00\x00\x00\x00\x00\x00\x00'
    GETBLOCKS = b'getblocks\x00\x00\x00'
    GETHEADERS = b'getheaders\x00\x00'
    HEADERS = b'headers\x00\x00\x00\x00\x00'

    # 트랜잭션
    TX = b'tx\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    MEMPOOL = b'mempool\x00\x00\x00\x00\x00'

    # 피어
    ADDR = b'addr\x00\x00\x00\x00\x00\x00\x00\x00'
    GETADDR = b'getaddr\x00\x00\x00\x00\x00'

    # 핑퐁
    PING = b'ping\x00\x00\x00\x00\x00\x00\x00\x00'
    PONG = b'pong\x00\x00\x00\x00\x00\x00\x00\x00'

    # 거부
    REJECT = b'reject\x00\x00\x00\x00\x00\x00'


class InvType(Enum):
    """인벤토리 타입"""
    ERROR = 0
    TX = 1
    BLOCK = 2
    FILTERED_BLOCK = 3
    COMPACT_BLOCK = 4


@dataclass
class MessageHeader:
    """메시지 헤더 (24 bytes)"""
    magic: bytes = NETWORK_MAGIC      # 4 bytes
    command: bytes = b'\x00' * 12     # 12 bytes
    length: int = 0                   # 4 bytes
    checksum: bytes = b'\x00' * 4     # 4 bytes

    def serialize(self) -> bytes:
        return (
            self.magic +
            self.command[:12].ljust(12, b'\x00') +
            struct.pack('<I', self.length) +
            self.checksum
        )

    @classmethod
    def deserialize(cls, data: bytes) -> 'MessageHeader':
        magic = data[:4]
        command = data[4:16]
        length = struct.unpack('<I', data[16:20])[0]
        checksum = data[20:24]
        return cls(magic, command, length, checksum)


@dataclass
class VersionMessage:
    """VERSION 메시지"""
    version: int = 70015
    services: int = 1  # NODE_NETWORK
    timestamp: int = 0
    addr_recv_services: int = 1
    addr_recv_ip: bytes = b'\x00' * 16
    addr_recv_port: int = 8333
    addr_trans_services: int = 1
    addr_trans_ip: bytes = b'\x00' * 16
    addr_trans_port: int = 8333
    nonce: int = 0
    user_agent: bytes = b'/JackpotChain:0.1.0/'
    start_height: int = 0
    relay: bool = True

    def serialize(self) -> bytes:
        result = struct.pack('<i', self.version)
        result += struct.pack('<Q', self.services)
        result += struct.pack('<q', self.timestamp)
        result += struct.pack('<Q', self.addr_recv_services)
        result += self.addr_recv_ip
        result += struct.pack('>H', self.addr_recv_port)
        result += struct.pack('<Q', self.addr_trans_services)
        result += self.addr_trans_ip
        result += struct.pack('>H', self.addr_trans_port)
        result += struct.pack('<Q', self.nonce)
        result += struct.pack('B', len(self.user_agent))
        result += self.user_agent
        result += struct.pack('<i', self.start_height)
        result += struct.pack('?', self.relay)
        return result

    @classmethod
    def deserialize(cls, data: bytes) -> 'VersionMessage':
        offset = 0
        version = struct.unpack('<i', data[offset:offset+4])[0]
        offset += 4
        services = struct.unpack('<Q', data[offset:offset+8])[0]
        offset += 8
        timestamp = struct.unpack('<q', data[offset:offset+8])[0]
        offset += 8
        addr_recv_services = struct.unpack('<Q', data[offset:offset+8])[0]
        offset += 8
        addr_recv_ip = data[offset:offset+16]
        offset += 16
        addr_recv_port = struct.unpack('>H', data[offset:offset+2])[0]
        offset += 2
        addr_trans_services = struct.unpack('<Q', data[offset:offset+8])[0]
        offset += 8
        addr_trans_ip = data[offset:offset+16]
        offset += 16
        addr_trans_port = struct.unpack('>H', data[offset:offset+2])[0]
        offset += 2
        nonce = struct.unpack('<Q', data[offset:offset+8])[0]
        offset += 8
        user_agent_len = data[offset]
        offset += 1
        user_agent = data[offset:offset+user_agent_len]
        offset += user_agent_len
        start_height = struct.unpack('<i', data[offset:offset+4])[0]
        offset += 4
        relay = bool(data[offset]) if offset < len(data) else True

        return cls(
            version=version, services=services, timestamp=timestamp,
            addr_recv_services=addr_recv_services, addr_recv_ip=addr_recv_ip,
            addr_recv_port=addr_recv_port, addr_trans_services=addr_trans_services,
            addr_trans_ip=addr_trans_ip, addr_trans_port=addr_trans_port,
            nonce=nonce, user_agent=user_agent, start_height=start_height,
            relay=relay
        )


@dataclass
class InvItem:
    """인벤토리 아이템"""
    inv_type: InvType
    hash: bytes  # 32 bytes

    def serialize(self) -> bytes:
        return struct.pack('<I', self.inv_type.value) + self.hash

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['InvItem', int]:
        inv_type = InvType(struct.unpack('<I', data[offset:offset+4])[0])
        offset += 4
        hash_bytes = data[offset:offset+32]
        offset += 32
        return cls(inv_type, hash_bytes), offset


@dataclass
class InvMessage:
    """INV 메시지"""
    items: List[InvItem] = field(default_factory=list)

    def serialize(self) -> bytes:
        from ..core.transaction import encode_varint
        result = encode_varint(len(self.items))
        for item in self.items:
            result += item.serialize()
        return result

    @classmethod
    def deserialize(cls, data: bytes) -> 'InvMessage':
        from ..core.transaction import decode_varint
        count, offset = decode_varint(data, 0)
        items = []
        for _ in range(count):
            item, offset = InvItem.deserialize(data, offset)
            items.append(item)
        return cls(items)


@dataclass
class GetDataMessage:
    """GETDATA 메시지"""
    items: List[InvItem] = field(default_factory=list)

    def serialize(self) -> bytes:
        return InvMessage(self.items).serialize()

    @classmethod
    def deserialize(cls, data: bytes) -> 'GetDataMessage':
        inv = InvMessage.deserialize(data)
        return cls(inv.items)


@dataclass
class GetBlocksMessage:
    """GETBLOCKS 메시지"""
    version: int = 70015
    block_locator: List[bytes] = field(default_factory=list)
    hash_stop: bytes = bytes(32)

    def serialize(self) -> bytes:
        from ..core.transaction import encode_varint
        result = struct.pack('<I', self.version)
        result += encode_varint(len(self.block_locator))
        for hash_bytes in self.block_locator:
            result += hash_bytes
        result += self.hash_stop
        return result

    @classmethod
    def deserialize(cls, data: bytes) -> 'GetBlocksMessage':
        from ..core.transaction import decode_varint
        offset = 0
        version = struct.unpack('<I', data[offset:offset+4])[0]
        offset += 4
        count, offset = decode_varint(data, offset)
        block_locator = []
        for _ in range(count):
            block_locator.append(data[offset:offset+32])
            offset += 32
        hash_stop = data[offset:offset+32]
        return cls(version, block_locator, hash_stop)


@dataclass
class NetAddress:
    """네트워크 주소 (ADDR 메시지용)"""
    timestamp: int = 0              # 마지막으로 본 시간
    services: int = 1               # 서비스 플래그
    ip: bytes = b'\x00' * 16        # IPv6 또는 IPv4-mapped (16 bytes)
    port: int = 8333                # 포트

    def serialize(self) -> bytes:
        return (
            struct.pack('<I', self.timestamp) +
            struct.pack('<Q', self.services) +
            self.ip +
            struct.pack('>H', self.port)
        )

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['NetAddress', int]:
        timestamp = struct.unpack('<I', data[offset:offset+4])[0]
        offset += 4
        services = struct.unpack('<Q', data[offset:offset+8])[0]
        offset += 8
        ip = data[offset:offset+16]
        offset += 16
        port = struct.unpack('>H', data[offset:offset+2])[0]
        offset += 2
        return cls(timestamp, services, ip, port), offset

    @classmethod
    def from_ipv4(cls, ip_str: str, port: int, timestamp: int = 0, services: int = 1) -> 'NetAddress':
        """IPv4 문자열에서 생성"""
        parts = [int(p) for p in ip_str.split('.')]
        # IPv4-mapped IPv6: ::ffff:a.b.c.d
        ip_bytes = b'\x00' * 10 + b'\xff\xff' + bytes(parts)
        return cls(timestamp, services, ip_bytes, port)

    def to_ipv4(self) -> Optional[str]:
        """IPv4 문자열로 변환"""
        # IPv4-mapped 확인
        if self.ip[:12] == b'\x00' * 10 + b'\xff\xff':
            return '.'.join(str(b) for b in self.ip[12:16])
        return None


@dataclass
class AddrMessage:
    """ADDR 메시지 - 피어 주소 목록"""
    addresses: List[NetAddress] = field(default_factory=list)

    def serialize(self) -> bytes:
        from ..core.transaction import encode_varint
        result = encode_varint(len(self.addresses))
        for addr in self.addresses:
            result += addr.serialize()
        return result

    @classmethod
    def deserialize(cls, data: bytes) -> 'AddrMessage':
        from ..core.transaction import decode_varint
        count, offset = decode_varint(data, 0)
        # 최대 1000개 제한
        count = min(count, 1000)
        addresses = []
        for _ in range(count):
            addr, offset = NetAddress.deserialize(data, offset)
            addresses.append(addr)
        return cls(addresses)


def create_message(msg_type: MessageType, payload: bytes) -> bytes:
    """완전한 메시지 생성"""
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    header = MessageHeader(
        magic=NETWORK_MAGIC,
        command=msg_type.value,
        length=len(payload),
        checksum=checksum
    )
    return header.serialize() + payload


def parse_message(data: bytes) -> Tuple[Optional[MessageHeader], bytes]:
    """메시지 파싱"""
    if len(data) < 24:
        return None, b''

    header = MessageHeader.deserialize(data[:24])

    # Magic 검증
    if header.magic != NETWORK_MAGIC:
        return None, b''

    # 페이로드 길이 확인
    if len(data) < 24 + header.length:
        return None, b''  # 불완전한 메시지

    payload = data[24:24 + header.length]

    # 체크섬 검증
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    if checksum != header.checksum:
        return None, b''

    return header, payload
