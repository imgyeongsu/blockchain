"""
Step 8.3: 노드 로직
- 메시지 처리
- 블록/TX 전파
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

from .protocol import (
    MessageType, MessageHeader,
    VersionMessage, InvMessage, InvItem, InvType,
    GetDataMessage, GetBlocksMessage,
    create_message, parse_message,
)
from .peer import PeerManager, PeerAddress, PeerState, PeerInfo
from ..consensus.chain import Blockchain
from ..core.block import Block
from ..core.transaction import Transaction
from ..constants import DEFAULT_PORT


@dataclass
class NodeConfig:
    """노드 설정"""
    host: str = "0.0.0.0"
    port: int = DEFAULT_PORT
    user_agent: str = "/JackpotChain:0.1.0/"
    max_outbound: int = 6
    max_inbound: int = 2
    relay: bool = True


class Node:
    """
    P2P 노드

    - 피어 연결 관리
    - 메시지 송수신
    - 블록/TX 전파
    """

    def __init__(self, config: NodeConfig = None, blockchain: Blockchain = None):
        self.config = config or NodeConfig()
        self.blockchain = blockchain or Blockchain()
        self.peer_manager = PeerManager(
            max_outbound=self.config.max_outbound,
            max_inbound=self.config.max_inbound
        )

        # 연결 (PeerAddress -> (reader, writer))
        self._connections: Dict[PeerAddress, tuple] = {}

        # 콜백
        self._on_block: Optional[Callable[[Block, PeerInfo], None]] = None
        self._on_tx: Optional[Callable[[Transaction, PeerInfo], None]] = None

        # 상태
        self._running = False
        self._server = None
        self._nonce = int(time.time() * 1000) % (2**64)

    @property
    def height(self) -> int:
        return self.blockchain.get_height()

    def set_block_callback(self, callback: Callable):
        """블록 수신 콜백 설정"""
        self._on_block = callback

    def set_tx_callback(self, callback: Callable):
        """TX 수신 콜백 설정"""
        self._on_tx = callback

    async def start(self):
        """노드 시작"""
        self._running = True

        # 서버 시작
        self._server = await asyncio.start_server(
            self._handle_inbound,
            self.config.host,
            self.config.port
        )

        # 연결 유지 태스크
        asyncio.create_task(self._maintain_connections())

    async def stop(self):
        """노드 정지"""
        self._running = False

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        # 모든 연결 종료
        for addr in list(self._connections.keys()):
            await self._disconnect(addr)

    async def connect_to_peer(self, address: PeerAddress) -> bool:
        """피어에 연결"""
        if not self.peer_manager.can_connect_outbound():
            return False

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(address.ip, address.port),
                timeout=10
            )

            peer = self.peer_manager.add_peer(address, is_inbound=False)
            if peer is None:
                writer.close()
                await writer.wait_closed()
                return False

            self._connections[address] = (reader, writer)
            asyncio.create_task(self._handle_peer(address, reader, writer))

            # 핸드셰이크 시작
            await self._send_version(address)
            return True

        except Exception as e:
            self.peer_manager.update_peer_state(address, PeerState.DISCONNECTED)
            return False

    async def _handle_inbound(self, reader, writer):
        """인바운드 연결 처리"""
        addr = writer.get_extra_info('peername')
        address = PeerAddress(ip=addr[0], port=addr[1])

        if not self.peer_manager.can_accept_inbound():
            writer.close()
            await writer.wait_closed()
            return

        peer = self.peer_manager.add_peer(address, is_inbound=True)
        if peer is None:
            writer.close()
            await writer.wait_closed()
            return

        self._connections[address] = (reader, writer)
        await self._handle_peer(address, reader, writer)

    async def _handle_peer(self, address: PeerAddress, reader, writer):
        """피어 메시지 처리 루프"""
        buffer = b''

        try:
            while self._running:
                data = await asyncio.wait_for(reader.read(8192), timeout=300)
                if not data:
                    break

                buffer += data
                peer = self.peer_manager.get_peer(address)
                if peer:
                    peer.bytes_recv += len(data)
                    peer.last_recv = time.time()

                # 메시지 파싱
                while len(buffer) >= 24:
                    header, payload = parse_message(buffer)
                    if header is None:
                        break

                    msg_len = 24 + header.length
                    if len(buffer) < msg_len:
                        break

                    buffer = buffer[msg_len:]
                    await self._process_message(address, header, payload)

        except asyncio.TimeoutError:
            pass
        except Exception as e:
            pass
        finally:
            await self._disconnect(address)

    async def _process_message(self, address: PeerAddress, header: MessageHeader, payload: bytes):
        """메시지 처리"""
        cmd = header.command.rstrip(b'\x00')
        peer = self.peer_manager.get_peer(address)

        if cmd == b'version':
            await self._handle_version(address, payload)
        elif cmd == b'verack':
            await self._handle_verack(address)
        elif cmd == b'ping':
            await self._handle_ping(address, payload)
        elif cmd == b'pong':
            pass  # TODO: RTT 계산
        elif cmd == b'inv':
            await self._handle_inv(address, payload)
        elif cmd == b'getdata':
            await self._handle_getdata(address, payload)
        elif cmd == b'block':
            await self._handle_block(address, payload)
        elif cmd == b'tx':
            await self._handle_tx(address, payload)
        elif cmd == b'getblocks':
            await self._handle_getblocks(address, payload)
        elif cmd == b'getheaders':
            await self._handle_getheaders(address, payload)

    async def _handle_version(self, address: PeerAddress, payload: bytes):
        """VERSION 메시지 처리"""
        version_msg = VersionMessage.deserialize(payload)
        self.peer_manager.update_peer_version(address, version_msg)
        self.peer_manager.update_peer_height(address, version_msg.start_height)
        self.peer_manager.update_peer_state(address, PeerState.HANDSHAKING)

        # VERACK 전송
        await self._send_message(address, MessageType.VERACK, b'')

        # 인바운드면 VERSION도 전송
        peer = self.peer_manager.get_peer(address)
        if peer and peer.is_inbound:
            await self._send_version(address)

    async def _handle_verack(self, address: PeerAddress):
        """VERACK 메시지 처리"""
        self.peer_manager.update_peer_state(address, PeerState.READY)

    async def _handle_ping(self, address: PeerAddress, payload: bytes):
        """PING 처리"""
        await self._send_message(address, MessageType.PONG, payload)

    async def _handle_inv(self, address: PeerAddress, payload: bytes):
        """INV 처리 - 새로운 블록/TX 알림"""
        inv_msg = InvMessage.deserialize(payload)

        # 모르는 것만 요청
        to_fetch = []
        for item in inv_msg.items:
            if item.inv_type == InvType.BLOCK:
                if not self.blockchain.has_block(item.hash):
                    to_fetch.append(item)
            elif item.inv_type == InvType.TX:
                # TODO: Mempool 확인
                to_fetch.append(item)

        if to_fetch:
            getdata = GetDataMessage(items=to_fetch)
            await self._send_message(address, MessageType.GETDATA, getdata.serialize())

    async def _handle_getdata(self, address: PeerAddress, payload: bytes):
        """GETDATA 처리"""
        getdata = GetDataMessage.deserialize(payload)

        for item in getdata.items:
            if item.inv_type == InvType.BLOCK:
                block = self.blockchain.get_block(item.hash)
                if block:
                    await self._send_message(address, MessageType.BLOCK, block.serialize())
            elif item.inv_type == InvType.TX:
                # TODO: Mempool에서 조회
                pass

    async def _handle_block(self, address: PeerAddress, payload: bytes):
        """BLOCK 수신"""
        block, _ = Block.deserialize(payload)
        peer = self.peer_manager.get_peer(address)

        if self._on_block:
            self._on_block(block, peer)

    async def _handle_tx(self, address: PeerAddress, payload: bytes):
        """TX 수신"""
        tx, _ = Transaction.deserialize(payload)
        peer = self.peer_manager.get_peer(address)

        if self._on_tx:
            self._on_tx(tx, peer)

    async def _handle_getblocks(self, address: PeerAddress, payload: bytes):
        """GETBLOCKS 처리"""
        msg = GetBlocksMessage.deserialize(payload)

        # 분기점 찾기
        fork_height, _ = self.blockchain.find_fork_point(msg.block_locator)

        # INV 전송
        hashes = self.blockchain.get_chain_hashes(fork_height + 1, 500)
        items = [InvItem(InvType.BLOCK, h) for h in hashes]
        if items:
            inv = InvMessage(items)
            await self._send_message(address, MessageType.INV, inv.serialize())

    async def _handle_getheaders(self, address: PeerAddress, payload: bytes):
        """GETHEADERS 처리"""
        # TODO: HEADERS 응답
        pass

    async def _send_version(self, address: PeerAddress):
        """VERSION 전송"""
        version_msg = VersionMessage(
            timestamp=int(time.time()),
            nonce=self._nonce,
            user_agent=self.config.user_agent.encode(),
            start_height=self.height,
            relay=self.config.relay
        )
        await self._send_message(address, MessageType.VERSION, version_msg.serialize())

    async def _send_message(self, address: PeerAddress, msg_type: MessageType, payload: bytes):
        """메시지 전송"""
        if address not in self._connections:
            return

        reader, writer = self._connections[address]
        message = create_message(msg_type, payload)

        try:
            writer.write(message)
            await writer.drain()

            peer = self.peer_manager.get_peer(address)
            if peer:
                peer.bytes_sent += len(message)
                peer.last_send = time.time()
        except Exception:
            await self._disconnect(address)

    async def _disconnect(self, address: PeerAddress):
        """연결 종료"""
        if address in self._connections:
            reader, writer = self._connections.pop(address)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

        self.peer_manager.update_peer_state(address, PeerState.DISCONNECTED)
        self.peer_manager.remove_peer(address)

    async def _maintain_connections(self):
        """연결 유지"""
        while self._running:
            # 필요하면 새 연결 시도
            if self.peer_manager.can_connect_outbound():
                to_connect = self.peer_manager.get_peers_to_connect(1)
                for addr in to_connect:
                    await self.connect_to_peer(addr)

            await asyncio.sleep(30)

    async def broadcast_block(self, block: Block):
        """블록 브로드캐스트"""
        item = InvItem(InvType.BLOCK, block.get_hash())
        inv = InvMessage([item])
        payload = inv.serialize()

        for addr in list(self._connections.keys()):
            await self._send_message(addr, MessageType.INV, payload)

    async def broadcast_tx(self, tx: Transaction):
        """TX 브로드캐스트"""
        item = InvItem(InvType.TX, tx.get_txid())
        inv = InvMessage([item])
        payload = inv.serialize()

        for addr in list(self._connections.keys()):
            await self._send_message(addr, MessageType.INV, payload)
