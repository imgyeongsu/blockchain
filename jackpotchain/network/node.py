"""
Step 8.3: 노드 로직
- 메시지 처리
- 블록/TX 전파
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass


def _log(tag: str, msg: str):
    """타임스탬프 로그"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][{tag}] {msg}")

from .protocol import (
    MessageType, MessageHeader,
    VersionMessage, InvMessage, InvItem, InvType,
    GetDataMessage, GetBlocksMessage, GetHeadersMessage, HeadersMessage,
    AddrMessage, NetAddress,
    create_message, parse_message,
)
from .peer import PeerManager, PeerAddress, PeerState, PeerInfo
from .discovery import PeerDiscovery
from .nat import NATManager, NATProtocol
from .holepunch import HolePunchClient, RendezvousServer, HolePunchResult
from ..consensus.chain import Blockchain
from ..core.block import Block
from ..core.transaction import Transaction
from ..mempool.pool import Mempool
from ..constants import DEFAULT_PORT, DEFAULT_RENDEZVOUS_PORT, MAX_INV_SIZE

# 블록 버퍼/대기열 최대 크기 (메모리 누수 방지)
MAX_BLOCK_BUFFER_SIZE = 1000
MAX_PENDING_BLOCKS = 5000


@dataclass
class NodeConfig:
    """노드 설정"""
    host: str = "0.0.0.0"
    port: int = DEFAULT_PORT
    user_agent: str = "/JackpotChain:0.1.0/"
    max_outbound: int = 8
    max_inbound: int = 32
    relay: bool = True
    data_dir: str = None  # 피어 캐시 저장 경로
    discovery_interval: int = 1800  # 피어 발견 주기 (30분)
    # NAT 설정
    nat_enabled: bool = True  # PCP/NAT-PMP 자동 포트 매핑
    nat_lifetime: int = 7200  # 매핑 유효기간 (초)
    # Hole Punch 설정
    holepunch_enabled: bool = True
    rendezvous_port: int = DEFAULT_RENDEZVOUS_PORT  # 8334
    rendezvous_seeds: list = None  # 랑데부 시드 노드 (ip:port)
    is_seed_node: bool = False  # True면 랑데부 서버도 실행
    allow_private_ip: bool = False  # True면 사설 IP 피어도 캐시 허용 (로컬 테스트용)


class Node:
    """
    P2P 노드

    - 피어 연결 관리
    - 메시지 송수신
    - 블록/TX 전파
    """

    def __init__(self, config: NodeConfig = None, blockchain: Blockchain = None, mempool: Mempool = None):
        self.config = config or NodeConfig()
        self.blockchain = blockchain or Blockchain()
        self.mempool = mempool  # TX 전파용 (없으면 TX 기능 비활성)

        # 상태 (NAT 초기화보다 먼저)
        self._running = False
        self._server = None
        self._nonce = int(time.time() * 1000) % (2**64)

        self.peer_manager = PeerManager(
            max_outbound=self.config.max_outbound,
            max_inbound=self.config.max_inbound
        )

        # 피어 발견
        self.discovery = PeerDiscovery(self.config.data_dir, allow_private_ip=self.config.allow_private_ip)

        # NAT 자동 포트 매핑
        self.nat_manager: Optional[NATManager] = None
        if self.config.nat_enabled:
            self.nat_manager = NATManager(
                internal_port=self.config.port,
                lifetime=self.config.nat_lifetime,
                holepunch_enabled=self.config.holepunch_enabled,
                rendezvous_seeds=self.config.rendezvous_seeds or [],
                node_id=self._nonce.to_bytes(8, 'big')
            )

        # 홀펀치 / 랑데부
        self._holepunch_client: Optional[HolePunchClient] = None
        self._rendezvous_server: Optional[RendezvousServer] = None

        # 연결 (PeerAddress -> (reader, writer))
        self._connections: Dict[PeerAddress, tuple] = {}

        # 콜백
        self._on_block: Optional[Callable[[Block, PeerInfo], None]] = None
        self._on_tx: Optional[Callable[[Transaction, PeerInfo], None]] = None
        self._headers_callback: Optional[Callable] = None

        # GETADDR 요청 시간 추적 (스팸 방지)
        self._last_getaddr: Dict[PeerAddress, float] = {}

        # 순차 블록 동기화용 (high/low watermark 방식)
        self._pending_blocks: List[bytes] = []  # 대기 중인 블록 해시 목록
        self._sync_peer: Optional[PeerAddress] = None  # 동기화 중인 피어
        self._requesting: set = set()  # 현재 요청 중인 블록 해시
        self._block_buffer: Dict[bytes, Block] = {}  # 순서 대기 중인 블록
        self._batch_size: int = 16  # high watermark: 최대 in-flight 수
        self._low_watermark: int = 4  # low watermark: 이 이하로 떨어지면 추가 요청
        self._sync_start_time: float = 0  # 마지막 블록 수신 시각 (watchdog용)
        self._sync_timeout: int = 120  # 동기화 세션 타임아웃 (초)
        self._last_inv_count: int = 0  # 마지막 INV에서 받은 블록 수 (연속 동기화 판단용)

    @property
    def height(self) -> int:
        return self.blockchain.get_height()

    @property
    def external_address(self) -> Optional[tuple]:
        """외부에서 접근 가능한 주소 (ip, port)"""
        if self.nat_manager and self.nat_manager.is_mapped:
            return self.nat_manager.external_address
        return None

    @property
    def is_syncing(self) -> bool:
        """IBD(Initial Block Download) 중인지 확인"""
        if self._sync_peer is not None:
            # 타임아웃 경과 시 좀비 동기화 상태 자동 해제
            if self._sync_start_time > 0 and time.time() - self._sync_start_time > self._sync_timeout:
                _log('SYNC', f'동기화 타임아웃 감지, 상태 초기화 (높이: {self.height})')
                self._sync_peer = None
                self._pending_blocks.clear()
                self._requesting.clear()
                self._block_buffer.clear()
                return False
            return True
        return len(self._pending_blocks) > 0

    def set_block_callback(self, callback: Callable):
        """블록 수신 콜백 설정"""
        self._on_block = callback

    def set_tx_callback(self, callback: Callable):
        """TX 수신 콜백 설정"""
        self._on_tx = callback

    def set_headers_callback(self, callback: Callable):
        """헤더 수신 콜백 설정"""
        self._headers_callback = callback

    async def start(self):
        """노드 시작"""
        self._running = True

        # 시드 노드면 랑데부 서버 시작
        if self.config.is_seed_node:
            self._rendezvous_server = RendezvousServer(port=self.config.rendezvous_port)
            await self._rendezvous_server.start(self.config.host)
            _log('Rendezvous', f'랑데부 서버 시작 - 포트 {self.config.rendezvous_port}')

        # 서버 먼저 시작 (수동 포트포워딩 감지에 필요)
        self._server = await asyncio.start_server(
            self._handle_inbound,
            self.config.host,
            self.config.port
        )

        # NAT 포트 매핑 (PCP → NAT-PMP → UPnP → HolePunch → 수동 감지 → 실패)
        if self.nat_manager:
            nat_result = await self.nat_manager.setup_port_mapping()
            if nat_result.success:
                if nat_result.protocol == NATProtocol.MANUAL:
                    _log('NAT', f'수동 포트포워딩 감지 - 인바운드 가능 ({nat_result.external_ip}:{nat_result.external_port})')
                else:
                    _log('NAT', f'포트 매핑 성공: {nat_result.external_ip}:{nat_result.external_port} ({nat_result.protocol.value})')
                # 홀펀치 클라이언트 참조 저장
                if nat_result.protocol == NATProtocol.HOLEPUNCH and self.nat_manager.holepunch_client:
                    self._holepunch_client = self.nat_manager.holepunch_client
                    self._holepunch_client._on_punch_success = self._on_holepunch_inbound
            else:
                _log('NAT', '포트 매핑 실패 - 아웃바운드 전용 모드')

        # 피어 발견 초기화
        initial_peers = self.discovery.initialize()
        for addr in initial_peers:
            self.peer_manager.add_peer_address(addr)

        # 시드 노드에 즉시 연결
        for addr in initial_peers[:5]:
            asyncio.create_task(self.connect_to_peer(addr))

        # 연결 유지 태스크
        asyncio.create_task(self._maintain_connections())

        # 피어 발견 태스크
        asyncio.create_task(self._discovery_loop())

        # 동기화 워치독
        asyncio.create_task(self._sync_watchdog())

        # 피어 ping keepalive
        asyncio.create_task(self._ping_loop())

    async def _sync_watchdog(self):
        """동기화 stall 감지 — 5초 무응답 시 stale 요청 정리 후 재요청"""
        while self._running:
            await asyncio.sleep(5)
            if self._sync_peer and self._pending_blocks and self._requesting:
                if self._sync_start_time > 0 and time.time() - self._sync_start_time > 5:
                    stale = len(self._requesting)
                    self._requesting.clear()
                    self._sync_start_time = time.time()
                    _log('SYNC', f'watchdog: stale {stale}개 정리, 재요청 (대기: {len(self._pending_blocks)}개)')
                    await self._request_next_block()

    async def stop(self):
        """노드 정지"""
        self._running = False

        # 랑데부 서버 중지
        if self._rendezvous_server:
            await self._rendezvous_server.stop()

        # NAT 매핑 제거 (홀펀치 클라이언트도 여기서 정리)
        if self.nat_manager:
            await self.nat_manager.remove_mapping()

        # 피어 캐시 저장
        self.discovery.save()

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
            # 직접 연결 실패 - 홀펀칭 시도
            if self._holepunch_client and self._holepunch_client.is_registered:
                hp_result = await self._holepunch_client.request_punch(
                    address.ip, address.port
                )
                if hp_result.success:
                    peer = self.peer_manager.add_peer(address, is_inbound=False)
                    if peer:
                        self._connections[address] = (hp_result.reader, hp_result.writer)
                        asyncio.create_task(
                            self._handle_peer(address, hp_result.reader, hp_result.writer)
                        )
                        await self._send_version(address)
                        _log('HolePunch', f'피어 연결 성공: {address.ip}:{address.port}')
                        return True

            _log('PEER', f'연결 실패: {address.ip}:{address.port} - {e}')
            self.peer_manager.update_peer_state(address, PeerState.DISCONNECTED)
            return False

    async def _on_holepunch_inbound(self, result: HolePunchResult):
        """홀펀칭으로 인바운드 연결 수신"""
        if not result.success:
            return

        address = PeerAddress(ip=result.peer_ip, port=result.peer_port)

        if not self.peer_manager.can_accept_inbound():
            if result.writer:
                result.writer.close()
            return

        peer = self.peer_manager.add_peer(address, is_inbound=True)
        if peer is None:
            if result.writer:
                result.writer.close()
            return

        self._connections[address] = (result.reader, result.writer)
        asyncio.create_task(
            self._handle_peer(address, result.reader, result.writer)
        )
        _log('HolePunch', f'인바운드 연결 수신: {result.peer_ip}:{result.peer_port}')

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
        elif cmd == b'headers':
            await self._handle_headers(address, payload)
        elif cmd == b'getaddr':
            await self._handle_getaddr(address)
        elif cmd == b'addr':
            await self._handle_addr(address, payload)

    async def _handle_version(self, address: PeerAddress, payload: bytes):
        """VERSION 메시지 처리"""
        version_msg = VersionMessage.deserialize(payload)
        _log('SYNC', f'VERSION 수신: height={version_msg.start_height} from {address.ip}:{address.port}')
        self.peer_manager.update_peer_version(address, version_msg)
        self.peer_manager.update_peer_height(address, version_msg.start_height)
        peer = self.peer_manager.get_peer(address)
        if peer and peer.state != PeerState.READY:
            self.peer_manager.update_peer_state(address, PeerState.HANDSHAKING)

        # VERACK 전송
        await self._send_message(address, MessageType.VERACK, b'')

        # 인바운드 피어의 리스닝 주소를 discovery에 등록
        # (TCP 연결의 임시 포트가 아닌, VERSION에 광고된 리스닝 포트 사용)
        peer = self.peer_manager.get_peer(address)
        if peer and peer.is_inbound and version_msg.addr_trans_port > 0:
            listen_addr = PeerAddress(
                ip=address.ip,
                port=version_msg.addr_trans_port,
                services=version_msg.services,
                timestamp=int(time.time())
            )
            self.discovery.add_addresses([listen_addr])
            self.discovery.mark_good(listen_addr)

        # 인바운드면 VERSION도 전송
        if peer and peer.is_inbound:
            await self._send_version(address)

        # 아웃바운드면 VERSION 수신 후 동기화 체크 (피어 height 확인됨)
        if peer and not peer.is_inbound and peer.state == PeerState.READY:
            await self._check_sync(address)

    async def _handle_verack(self, address: PeerAddress):
        """VERACK 메시지 처리"""
        self.peer_manager.update_peer_state(address, PeerState.READY)

        # 연결 성공 기록
        self.discovery.mark_good(address)

        # 피어에게 주소 요청
        await self._send_getaddr(address)

        # 동기화 체크 (READY 상태 확정 후 인바운드/아웃바운드 모두 체크)
        # 아웃바운드는 VERSION 수신 시 아직 READY가 아니라 스킵되므로 여기서 처리
        peer = self.peer_manager.get_peer(address)
        if peer and peer.state == PeerState.READY:
            await self._check_sync(address)

    async def _check_sync(self, address: PeerAddress):
        """동기화 필요 여부 확인 및 시작"""
        peer = self.peer_manager.get_peer(address)
        if peer and peer.start_height > self.height:
            _log('SYNC', f'IBD 시작: 로컬={self.height}, 피어={peer.start_height}, 주소={address.ip}:{address.port}')
            await self._request_blocks(address)
        else:
            _log('SYNC', f'동기화 불필요: 로컬={self.height}, 피어={peer.start_height if peer else 'N/A'}')

    async def _handle_ping(self, address: PeerAddress, payload: bytes):
        """PING 처리"""
        await self._send_message(address, MessageType.PONG, payload)

    async def _handle_inv(self, address: PeerAddress, payload: bytes):
        """INV 처리 - 새로운 블록/TX 알림"""
        inv_msg = InvMessage.deserialize(payload)

        # [SYNC-LOG] INV 수신
        block_count = sum(1 for i in inv_msg.items if i.inv_type == InvType.BLOCK)
        tx_count = sum(1 for i in inv_msg.items if i.inv_type == InvType.TX)
        _log('SYNC', f'INV 수신: 블록 {block_count}개, TX {tx_count}개 from {address.ip}:{address.port}')

        # TX는 바로 요청 (MAX_INV_SIZE 제한, 5.7)
        tx_to_fetch = []
        for item in inv_msg.items:
            if item.inv_type == InvType.TX:
                if self.mempool and not self.mempool.has_tx(item.hash):
                    tx_to_fetch.append(item)
                    if len(tx_to_fetch) >= MAX_INV_SIZE:
                        break

        if tx_to_fetch:
            getdata = GetDataMessage(items=tx_to_fetch)
            await self._send_message(address, MessageType.GETDATA, getdata.serialize())

        # 블록은 순차 요청 (pending 큐에 저장)
        block_hashes = []
        for item in inv_msg.items:
            if item.inv_type == InvType.BLOCK:
                if not self.blockchain.has_block(item.hash):
                    block_hashes.append(item.hash)

        if block_hashes:
            # 대기열 크기 제한
            if len(block_hashes) > MAX_PENDING_BLOCKS:
                _log('SYNC', f'대기열 크기 제한: {len(block_hashes)} -> {MAX_PENDING_BLOCKS}')
                block_hashes = block_hashes[:MAX_PENDING_BLOCKS]

            # 이전 피어 요청 잔여물 초기화 (5.4)
            self._requesting.clear()
            self._pending_blocks = block_hashes
            self._sync_peer = address
            self._sync_start_time = time.time()  # 세션 타임아웃 추적 (5.6)
            self._last_inv_count = block_count
            _log('SYNC', f'블록 {len(block_hashes)}개 대기열에 추가, 순차 다운로드 시작')
            await self._request_next_block()

    async def _request_next_block(self):
        """대기 중인 다음 블록들 요청 (배치)"""
        if not self._pending_blocks or not self._sync_peer:
            return

        # 세션 타임아웃 체크 (5.6)
        if time.time() - self._sync_start_time > self._sync_timeout:
            _log('SYNC', f'세션 타임아웃 ({self._sync_timeout}s). 동기화 중단.')
            self._sync_peer = None
            self._pending_blocks.clear()
            self._requesting.clear()
            self._block_buffer.clear()
            return

        # High/Low Watermark: in-flight가 low 이하일 때만 high까지 채움
        in_flight = len(self._requesting)
        if in_flight > self._low_watermark:
            return  # 아직 충분히 요청 중 — 추가 요청 안 함

        slots = self._batch_size - in_flight  # high watermark까지 채울 수량
        to_request = []
        for block_hash in self._pending_blocks:
            if block_hash not in self._requesting and block_hash not in self._block_buffer:
                to_request.append(block_hash)
                if len(to_request) >= slots:
                    break

        if not to_request:
            return

        # 요청 중 표시
        for h in to_request:
            self._requesting.add(h)

        # 여러 블록 한번에 요청
        items = [InvItem(InvType.BLOCK, h) for h in to_request]
        getdata = GetDataMessage(items=items)
        _log('SYNC', f'GETDATA 요청: {len(items)}개 블록 (대기: {len(self._pending_blocks)}개)')
        await self._send_message(self._sync_peer, MessageType.GETDATA, getdata.serialize())

    async def _handle_getdata(self, address: PeerAddress, payload: bytes):
        """GETDATA 처리"""
        getdata = GetDataMessage.deserialize(payload)

        for item in getdata.items:
            if item.inv_type == InvType.BLOCK:
                block = self.blockchain.get_block(item.hash)
                if block:
                    await self._send_message(address, MessageType.BLOCK, block.serialize())
            elif item.inv_type == InvType.TX:
                # Mempool에서 TX 조회 후 전송
                tx = None
                if self.mempool:
                    tx = self.mempool.get_tx(item.hash)
                # mempool에 없으면 최근 블록에서 검색 (채굴 직후 레이스 컨디션 대응)
                if tx is None:
                    tx = self._find_tx_in_recent_blocks(item.hash)
                if tx:
                    await self._send_message(address, MessageType.TX, tx.serialize())

    async def _handle_block(self, address: PeerAddress, payload: bytes):
        """BLOCK 수신"""
        block, _ = Block.deserialize(payload)
        peer = self.peer_manager.get_peer(address)
        block_hash = block.get_hash()

        # 마지막 블록 수신 시각 갱신 (watchdog용)
        self._sync_start_time = time.time()

        # 요청 목록에서 제거
        self._requesting.discard(block_hash)

        # 이전 블록이 없으면 버퍼에 저장
        prev_hash = block.header.prev_block_hash
        if prev_hash != bytes(32) and not self.blockchain.has_block(prev_hash):
            # 버퍼에 저장 (나중에 처리)
            if block_hash in self._pending_blocks:
                # 버퍼 크기 제한 체크
                if len(self._block_buffer) >= MAX_BLOCK_BUFFER_SIZE:
                    # 가장 오래된 항목 제거
                    oldest_key = next(iter(self._block_buffer))
                    del self._block_buffer[oldest_key]
                    _log('BUFFER', f'크기 제한 초과, 오래된 블록 제거: {oldest_key.hex()[:16]}...')

                self._block_buffer[block_hash] = block
            else:
                # 동기화 목록에 없는 블록 - GETBLOCKS 요청
                _log('SYNC', f'이전 블록 없음, GETBLOCKS 요청 (prev={prev_hash.hex()[:16]}...)')
                await self._request_blocks(address)
            return

        # 블록 처리
        if self._on_block:
            self._on_block(block, peer)

        # 블록에 포함된 TX를 mempool에서 제거 (콜백 누락 대비 안전장치)
        if self.mempool:
            for tx in block.transactions[1:]:  # coinbase 제외
                self.mempool.remove_tx(tx.get_txid())

        # 피어 높이 갱신 (체인 현재 높이로)
        chain_height = self.blockchain.get_height() if self.blockchain else 0
        if chain_height > 0:
            self.peer_manager.update_peer_height(address, chain_height)

        # 다른 피어들에게 재전파 (보낸 피어 제외)
        await self._relay_block(block, exclude=address)

        # 처리된 블록 제거
        if block_hash in self._pending_blocks:
            self._pending_blocks.remove(block_hash)

        # 버퍼에서 연결 가능한 블록들 처리
        processed = True
        while processed:
            processed = False
            for buf_hash, buf_block in list(self._block_buffer.items()):
                if self.blockchain.has_block(buf_block.header.prev_block_hash):
                    if self._on_block:
                        self._on_block(buf_block, peer)
                    # 블록에 포함된 TX를 mempool에서 제거
                    if self.mempool:
                        for tx in buf_block.transactions[1:]:
                            self.mempool.remove_tx(tx.get_txid())
                    # 재전파
                    await self._relay_block(buf_block, exclude=address)
                    del self._block_buffer[buf_hash]
                    if buf_hash in self._pending_blocks:
                        self._pending_blocks.remove(buf_hash)
                    processed = True
                    break

        # 다음 배치 요청
        if self._pending_blocks:
            await self._request_next_block()
        elif self._last_inv_count >= 500 and self._sync_peer:
            # 이전 INV가 최대치(500)였으면 피어에 더 많은 블록이 있을 수 있음
            _log('SYNC', f'배치 완료 (높이: {self.height}), 추가 블록 요청...')
            await self._request_blocks(self._sync_peer)
        else:
            _log('SYNC', f'동기화 완료! 현재 높이: {self.height}')
            self._sync_peer = None
            self._block_buffer.clear()
            self._requesting.clear()  # 요청 잔여물 초기화 (5.5)

    async def _handle_tx(self, address: PeerAddress, payload: bytes):
        """TX 수신 (orphan TX 대기열 포함)"""
        tx, _ = Transaction.deserialize(payload)
        peer = self.peer_manager.get_peer(address)

        # mempool에 추가
        if self.mempool and not self.mempool.has_tx(tx.get_txid()):
            success, msg = self.mempool.add_tx(
                tx,
                self.blockchain.utxo_set,
                self.blockchain.get_height()
            )
            if success:
                # 다른 피어에게 재전파
                await self._relay_tx(tx, exclude=address)
                # orphan TX 재시도 (이 TX의 출력을 기다리던 TX)
                await self._retry_orphan_txs(tx.get_txid(), address)
            elif "UTXO not found" in msg:
                # 부모 TX가 아직 없음 → orphan 대기열에 추가
                if not hasattr(self, '_orphan_txs'):
                    self._orphan_txs = {}
                txid = tx.get_txid()
                if len(self._orphan_txs) < 100:  # 최대 100개 제한
                    self._orphan_txs[txid] = (tx, address)

        if self._on_tx:
            self._on_tx(tx, peer)

    async def _retry_orphan_txs(self, parent_txid: bytes, address: PeerAddress):
        """부모 TX가 들어오면 orphan TX 재시도"""
        if not hasattr(self, '_orphan_txs') or not self._orphan_txs:
            return

        resolved = []
        for txid, (tx, orig_addr) in list(self._orphan_txs.items()):
            # 이 TX가 parent_txid를 참조하는지 확인
            refs_parent = any(inp.prev_tx_id == parent_txid for inp in tx.inputs)
            if not refs_parent:
                continue

            success, msg = self.mempool.add_tx(
                tx,
                self.blockchain.utxo_set,
                self.blockchain.get_height()
            )
            if success:
                resolved.append(txid)
                await self._relay_tx(tx, exclude=orig_addr)
            elif "UTXO not found" not in msg:
                resolved.append(txid)  # 다른 이유로 실패 → 제거

        for txid in resolved:
            self._orphan_txs.pop(txid, None)

    async def _handle_getblocks(self, address: PeerAddress, payload: bytes):
        """GETBLOCKS 처리"""
        msg = GetBlocksMessage.deserialize(payload)

        # [SYNC-LOG] GETBLOCKS 수신
        _log('SYNC', f'GETBLOCKS 수신 from {address.ip}:{address.port}, locator 크기: {len(msg.block_locator)}')

        # 분기점 찾기
        fork_height, _ = self.blockchain.find_fork_point(msg.block_locator)
        _log('SYNC', f'분기점: height={fork_height}')

        # INV 전송
        hashes = self.blockchain.get_chain_hashes(fork_height + 1, 500)
        items = [InvItem(InvType.BLOCK, h) for h in hashes]
        if items:
            _log('SYNC', f'INV 응답: {len(items)}개 블록 해시 전송')
            inv = InvMessage(items)
            await self._send_message(address, MessageType.INV, inv.serialize())
        else:
            _log('SYNC', 'INV 응답: 전송할 블록 없음')

    async def _handle_getheaders(self, address: PeerAddress, payload: bytes):
        """GETHEADERS 처리 - 블록 헤더 목록 반환"""
        if not self.blockchain:
            return

        try:
            msg = GetHeadersMessage.deserialize(payload)
        except Exception:
            return

        # 1. block_locator에서 공통 블록 찾기
        start_height = 0
        for block_hash in msg.block_locator:
            index = self.blockchain.get_block_index(block_hash)
            if index and index.is_in_main_chain:
                start_height = index.height + 1
                break

        # 2. 헤더 수집 (최대 2000개)
        headers = []
        current_height = self.blockchain.get_height()
        hash_stop = msg.hash_stop

        for height in range(start_height, min(start_height + 2000, current_height + 1)):
            block = self.blockchain.get_block_by_height(height)
            if not block:
                break

            headers.append(block.header.serialize())

            # hash_stop 도달 시 중단
            if hash_stop != bytes(32) and block.get_hash() == hash_stop:
                break

        # 3. HEADERS 응답
        if headers:
            headers_msg = HeadersMessage(headers=headers)
            await self._send_message(address, MessageType.HEADERS, headers_msg.serialize())

    async def _handle_headers(self, address: PeerAddress, payload: bytes):
        """HEADERS 처리 - 블록 헤더 수신 (동기화용)"""
        try:
            msg = HeadersMessage.deserialize(payload)
        except Exception:
            return

        if not msg.headers:
            return

        # 피어의 synced_headers 업데이트
        peer = self.peer_manager.get_peer(address)
        if peer:
            peer.synced_headers += len(msg.headers)

        # 콜백이 있으면 호출 (SyncManager에서 처리)
        if self._headers_callback:
            await self._headers_callback(address, msg.headers)

    async def _handle_getaddr(self, address: PeerAddress):
        """GETADDR 처리 - 알고 있는 피어 주소 전송"""
        # 스팸 방지: 24시간에 한 번만 응답
        last = self._last_getaddr.get(address, 0)
        if time.time() - last < 86400:
            return
        self._last_getaddr[address] = time.time()

        # 주소 목록 생성
        peers = self.discovery.get_addr_to_send(count=1000)
        if not peers:
            return

        addresses = []
        for peer in peers:
            net_addr = NetAddress.from_ipv4(
                peer.ip, peer.port,
                timestamp=peer.timestamp,
                services=peer.services
            )
            addresses.append(net_addr)

        addr_msg = AddrMessage(addresses=addresses)
        await self._send_message(address, MessageType.ADDR, addr_msg.serialize())

    async def _handle_addr(self, address: PeerAddress, payload: bytes):
        """ADDR 처리 - 피어 주소 수신"""
        try:
            addr_msg = AddrMessage.deserialize(payload)
        except Exception:
            return

        # 주소 변환 및 저장
        new_addresses = []
        for net_addr in addr_msg.addresses:
            ip_str = net_addr.to_ipv4()
            if ip_str:
                peer_addr = PeerAddress(
                    ip=ip_str,
                    port=net_addr.port,
                    services=net_addr.services,
                    timestamp=net_addr.timestamp
                )
                new_addresses.append(peer_addr)

        # 피어 발견에 추가
        self.discovery.add_addresses(new_addresses)

        # 피어 매니저에도 추가
        for addr in new_addresses:
            self.peer_manager.add_peer_address(addr)

    async def _send_getaddr(self, address: PeerAddress):
        """GETADDR 전송"""
        await self._send_message(address, MessageType.GETADDR, b'')

    async def _request_blocks(self, address: PeerAddress):
        """블록 동기화 요청 (GETBLOCKS)"""
        # Block locator 생성: 최근 블록들의 해시
        locator = self.blockchain.get_block_locator()
        # [SYNC-LOG] GETBLOCKS 요청
        _log('SYNC', f'GETBLOCKS 요청: locator 크기={len(locator)}, 현재 높이={self.blockchain.get_height()}')
        msg = GetBlocksMessage(block_locator=locator)
        await self._send_message(address, MessageType.GETBLOCKS, msg.serialize())

    async def _send_version(self, address: PeerAddress):
        """VERSION 전송"""
        _log('SYNC', f'VERSION 전송: height={self.height} to {address.ip}:{address.port}')
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

        # 연결이 끊기면 즉시 재연결 시도
        if self._running and self.peer_manager.can_connect_outbound():
            asyncio.create_task(self._reconnect_soon())

    async def _reconnect_soon(self):
        """끊김 후 3초 대기 → 재연결"""
        await asyncio.sleep(3)
        if not self._running:
            return
        to_connect = self.peer_manager.get_peers_to_connect(1)
        if not to_connect:
            connected = set(str(a) for a in self._connections.keys())
            to_connect = self.discovery.get_peers_to_connect(count=1, exclude=connected)
        for addr in to_connect:
            await self.connect_to_peer(addr)

    async def _ping_loop(self):
        """주기적으로 연결된 피어에 ping 전송 — 타임아웃(300s) 방지"""
        import os
        while self._running:
            await asyncio.sleep(120)
            for address in list(self._connections.keys()):
                nonce = os.urandom(8)
                await self._send_message(address, MessageType.PING, nonce)

    async def _maintain_connections(self):
        """연결 유지"""
        while self._running:
            # 필요하면 새 연결 시도
            if self.peer_manager.can_connect_outbound():
                # 먼저 피어 매니저에서 가져오기
                to_connect = self.peer_manager.get_peers_to_connect(1)

                # 없으면 discovery에서 가져오기
                if not to_connect:
                    connected = set(str(a) for a in self._connections.keys())
                    to_connect = self.discovery.get_peers_to_connect(
                        count=1, exclude=connected
                    )

                for addr in to_connect:
                    self.discovery.mark_attempt(addr)
                    await self.connect_to_peer(addr)

            await asyncio.sleep(30)

    async def _discovery_loop(self):
        """주기적 피어 발견"""
        # 첫 실행은 5분 후
        await asyncio.sleep(300)

        while self._running:
            try:
                # 연결된 피어 중 랜덤하게 GETADDR 요청
                ready_peers = self.peer_manager.get_connected_peers()
                if ready_peers:
                    import random
                    target = random.choice(ready_peers)
                    await self._send_getaddr(target.address)

                # 캐시 저장
                self.discovery.save()

            except Exception:
                pass

            # 다음 발견까지 대기
            await asyncio.sleep(self.config.discovery_interval)

    async def broadcast_block(self, block: Block):
        """블록 브로드캐스트"""
        item = InvItem(InvType.BLOCK, block.get_hash())
        inv = InvMessage([item])
        payload = inv.serialize()

        for addr in list(self._connections.keys()):
            await self._send_message(addr, MessageType.INV, payload)

    async def broadcast_tx(self, tx: Transaction):
        """TX 브로드캐스트 (병렬 전송)"""
        item = InvItem(InvType.TX, tx.get_txid())
        inv = InvMessage([item])
        payload = inv.serialize()

        peers = list(self._connections.keys())
        _log('TX', f'브로드캐스트: {tx.get_txid().hex()[:16]}... → {len(peers)}개 피어')
        await asyncio.gather(
            *(self._send_message(addr, MessageType.INV, payload) for addr in peers),
            return_exceptions=True
        )

    async def _relay_block(self, block: Block, exclude: PeerAddress = None):
        """블록 재전파 (수신한 피어 제외)"""
        item = InvItem(InvType.BLOCK, block.get_hash())
        inv = InvMessage([item])
        payload = inv.serialize()

        relayed = 0
        for addr in list(self._connections.keys()):
            if addr != exclude:
                await self._send_message(addr, MessageType.INV, payload)
                relayed += 1

        if relayed > 0:
            _log('RELAY', f'블록 {block.get_hash().hex()[:16]}... → {relayed}개 피어')

    async def _relay_tx(self, tx: Transaction, exclude: PeerAddress = None):
        """TX 재전파 (수신한 피어 제외, 병렬 전송)"""
        item = InvItem(InvType.TX, tx.get_txid())
        inv = InvMessage([item])
        payload = inv.serialize()

        targets = [addr for addr in self._connections.keys() if addr != exclude]
        if targets:
            await asyncio.gather(
                *(self._send_message(addr, MessageType.INV, payload) for addr in targets),
                return_exceptions=True
            )

    def _find_tx_in_recent_blocks(self, txid: bytes, depth: int = 10) -> Optional[Transaction]:
        """최근 블록에서 TX 검색 (mempool에서 제거된 직후 GETDATA 대응)"""
        height = self.blockchain.get_height()
        for h in range(height, max(0, height - depth), -1):
            block = self.blockchain.get_block_by_height(h)
            if block:
                for tx in block.transactions:
                    if tx.get_txid() == txid:
                        return tx
        return None
