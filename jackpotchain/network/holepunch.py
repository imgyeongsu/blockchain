"""
TCP Hole Punching - NAT 뒤 노드 간 직접 연결

공유기 설정 없이 인바운드 연결을 가능하게 하는 TCP 홀펀칭.
시드 노드가 랑데부 서버 역할을 겸한다.

Flow:
  1. NAT 뒤 노드가 랑데부 서버에 REGISTER
  2. 서버가 노드의 외부 IP:port 반환 (REGISTER_ACK)
  3. 연결 요청 시 서버가 양쪽에 PUNCH_INITIATE 전송
  4. 양쪽이 동시에 TCP connect (simultaneous open)
"""

import asyncio
import os
import socket
import struct
import sys
import time
import logging
from typing import Optional, Tuple, Dict
from dataclasses import dataclass

from ..constants import (
    DEFAULT_RENDEZVOUS_PORT,
    HOLEPUNCH_TIMEOUT,
    HOLEPUNCH_RETRY_COUNT,
    HOLEPUNCH_RETRY_DELAY,
    RENDEZVOUS_HEARTBEAT_INTERVAL,
    RENDEZVOUS_STALE_TIMEOUT,
)

logger = logging.getLogger(__name__)

# 랑데부 프로토콜 매직
HP_MAGIC = b'\x48\x50'  # "HP"

# 메시지 타입
MSG_REGISTER = 0x01
MSG_REGISTER_ACK = 0x02
MSG_CONNECT_REQUEST = 0x03
MSG_PUNCH_INITIATE = 0x04
MSG_PUNCH_ACK = 0x05
MSG_HEARTBEAT = 0x06
MSG_HEARTBEAT_ACK = 0x07


@dataclass
class HolePunchResult:
    """홀펀칭 결과"""
    success: bool
    reader: Optional[asyncio.StreamReader] = None
    writer: Optional[asyncio.StreamWriter] = None
    peer_ip: Optional[str] = None
    peer_port: Optional[int] = None
    error: Optional[str] = None


@dataclass
class RendezvousRegistration:
    """랑데부 서버의 노드 등록 정보"""
    node_id: bytes           # 8바이트 노드 ID
    external_ip: str
    external_port: int
    listening_port: int      # 노드의 P2P 리스닝 포트
    writer: asyncio.StreamWriter
    last_heartbeat: float


class RendezvousProtocol:
    """랑데부 프로토콜 메시지 생성/파싱"""

    @staticmethod
    def build_message(msg_type: int, payload: bytes = b'') -> bytes:
        """메시지 패킹: [2B magic][1B type][2B length][payload]"""
        return HP_MAGIC + struct.pack('>BH', msg_type, len(payload)) + payload

    @staticmethod
    def parse_header(data: bytes) -> Optional[Tuple[int, int]]:
        """헤더 파싱 -> (msg_type, payload_length) or None"""
        if len(data) < 5:
            return None
        if data[:2] != HP_MAGIC:
            return None
        msg_type, length = struct.unpack('>BH', data[2:5])
        return msg_type, length

    # --- 메시지 빌더 ---

    @staticmethod
    def build_register(listening_port: int, node_id: bytes) -> bytes:
        """REGISTER: [2B port][8B node_id]"""
        payload = struct.pack('>H', listening_port) + node_id
        return RendezvousProtocol.build_message(MSG_REGISTER, payload)

    @staticmethod
    def build_register_ack(external_ip: str, external_port: int, status: int = 0) -> bytes:
        """REGISTER_ACK: [4B ip][2B port][1B status]"""
        ip_bytes = socket.inet_aton(external_ip)
        payload = ip_bytes + struct.pack('>HB', external_port, status)
        return RendezvousProtocol.build_message(MSG_REGISTER_ACK, payload)

    @staticmethod
    def build_connect_request(target_ip: str, target_port: int, requester_node_id: bytes) -> bytes:
        """CONNECT_REQUEST: [4B target_ip][2B target_port][8B requester_node_id]"""
        ip_bytes = socket.inet_aton(target_ip)
        payload = ip_bytes + struct.pack('>H', target_port) + requester_node_id
        return RendezvousProtocol.build_message(MSG_CONNECT_REQUEST, payload)

    @staticmethod
    def build_punch_initiate(
        peer_ip: str, peer_port: int, peer_node_id: bytes, session_id: bytes
    ) -> bytes:
        """PUNCH_INITIATE: [4B ip][2B port][8B node_id][8B session_id]"""
        ip_bytes = socket.inet_aton(peer_ip)
        payload = ip_bytes + struct.pack('>H', peer_port) + peer_node_id + session_id
        return RendezvousProtocol.build_message(MSG_PUNCH_INITIATE, payload)

    @staticmethod
    def build_punch_ack(session_id: bytes, status: int = 0) -> bytes:
        """PUNCH_ACK: [8B session_id][1B status]"""
        payload = session_id + struct.pack('>B', status)
        return RendezvousProtocol.build_message(MSG_PUNCH_ACK, payload)

    @staticmethod
    def build_heartbeat(node_id: bytes) -> bytes:
        """HEARTBEAT: [8B node_id]"""
        return RendezvousProtocol.build_message(MSG_HEARTBEAT, node_id)

    @staticmethod
    def build_heartbeat_ack() -> bytes:
        """HEARTBEAT_ACK: (empty)"""
        return RendezvousProtocol.build_message(MSG_HEARTBEAT_ACK)

    # --- 메시지 파서 ---

    @staticmethod
    def parse_register(payload: bytes) -> Tuple[int, bytes]:
        """-> (listening_port, node_id)"""
        port = struct.unpack('>H', payload[:2])[0]
        node_id = payload[2:10]
        return port, node_id

    @staticmethod
    def parse_register_ack(payload: bytes) -> Tuple[str, int, int]:
        """-> (external_ip, external_port, status)"""
        ip = socket.inet_ntoa(payload[:4])
        port, status = struct.unpack('>HB', payload[4:7])
        return ip, port, status

    @staticmethod
    def parse_connect_request(payload: bytes) -> Tuple[str, int, bytes]:
        """-> (target_ip, target_port, requester_node_id)"""
        ip = socket.inet_ntoa(payload[:4])
        port = struct.unpack('>H', payload[4:6])[0]
        node_id = payload[6:14]
        return ip, port, node_id

    @staticmethod
    def parse_punch_initiate(payload: bytes) -> Tuple[str, int, bytes, bytes]:
        """-> (peer_ip, peer_port, peer_node_id, session_id)"""
        ip = socket.inet_ntoa(payload[:4])
        port = struct.unpack('>H', payload[4:6])[0]
        node_id = payload[6:14]
        session_id = payload[14:22]
        return ip, port, node_id, session_id


# =============================================================================
# 랑데부 서버 (시드 노드에서 실행)
# =============================================================================

class RendezvousServer:
    """
    랑데부 서버 - 시드 노드가 겸임

    NAT 뒤 노드들의 외부 주소를 기록하고,
    홀펀칭 요청 시 양쪽에 상대방 주소를 전달한다.
    """

    def __init__(self, port: int = DEFAULT_RENDEZVOUS_PORT):
        self.port = port
        self._server: Optional[asyncio.Server] = None
        self._registry: Dict[bytes, RendezvousRegistration] = {}  # node_id -> registration
        # 외부주소(ip:port)로 node_id 역검색
        self._addr_to_node: Dict[str, bytes] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self, host: str = "0.0.0.0"):
        """서버 시작"""
        self._running = True
        self._server = await asyncio.start_server(
            self._handle_client, host, self.port,
            reuse_address=True
        )
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info(f"[Rendezvous] 서버 시작 - {host}:{self.port}")

    async def stop(self):
        """서버 중지"""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        # 연결 정리
        for reg in self._registry.values():
            try:
                reg.writer.close()
            except Exception:
                pass
        self._registry.clear()
        self._addr_to_node.clear()
        logger.info("[Rendezvous] 서버 중지")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """클라이언트 연결 처리"""
        addr = writer.get_extra_info('peername')
        client_ip, client_port = addr[0], addr[1]
        node_id = None
        buffer = b''

        try:
            while self._running:
                data = await asyncio.wait_for(reader.read(4096), timeout=RENDEZVOUS_STALE_TIMEOUT)
                if not data:
                    break

                buffer += data

                while len(buffer) >= 5:
                    parsed = RendezvousProtocol.parse_header(buffer)
                    if parsed is None:
                        buffer = b''
                        break

                    msg_type, payload_len = parsed
                    total_len = 5 + payload_len
                    if len(buffer) < total_len:
                        break

                    payload = buffer[5:total_len]
                    buffer = buffer[total_len:]

                    if msg_type == MSG_REGISTER:
                        node_id = await self._handle_register(
                            payload, client_ip, client_port, writer
                        )

                    elif msg_type == MSG_CONNECT_REQUEST:
                        await self._handle_connect_request(payload, client_ip, client_port)

                    elif msg_type == MSG_HEARTBEAT:
                        await self._handle_heartbeat(payload, writer)

                    elif msg_type == MSG_PUNCH_ACK:
                        pass  # 로깅만

        except (asyncio.TimeoutError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            logger.debug(f"[Rendezvous] 클라이언트 오류: {e}")
        finally:
            # 등록 제거
            if node_id and node_id in self._registry:
                reg = self._registry.pop(node_id)
                addr_key = f"{reg.external_ip}:{reg.listening_port}"
                self._addr_to_node.pop(addr_key, None)
                logger.debug(f"[Rendezvous] 등록 해제: {node_id.hex()}")
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _handle_register(
        self, payload: bytes, client_ip: str, client_port: int,
        writer: asyncio.StreamWriter
    ) -> bytes:
        """REGISTER 처리"""
        listening_port, node_id = RendezvousProtocol.parse_register(payload)

        reg = RendezvousRegistration(
            node_id=node_id,
            external_ip=client_ip,
            external_port=client_port,
            listening_port=listening_port,
            writer=writer,
            last_heartbeat=time.time()
        )
        self._registry[node_id] = reg

        # 역검색용 (외부IP + 리스닝포트 조합)
        addr_key = f"{client_ip}:{listening_port}"
        self._addr_to_node[addr_key] = node_id

        logger.info(
            f"[Rendezvous] 노드 등록: {node_id.hex()[:8]}.. "
            f"외부={client_ip}:{client_port} 리스닝={listening_port}"
        )

        # REGISTER_ACK 전송
        ack = RendezvousProtocol.build_register_ack(client_ip, client_port)
        writer.write(ack)
        await writer.drain()

        return node_id

    async def _handle_connect_request(
        self, payload: bytes, requester_ip: str, requester_port: int
    ):
        """CONNECT_REQUEST 처리 - 양쪽에 PUNCH_INITIATE 전송"""
        target_ip, target_port, requester_node_id = RendezvousProtocol.parse_connect_request(payload)

        # 타겟 노드 찾기 (외부IP + 리스닝포트로 검색)
        addr_key = f"{target_ip}:{target_port}"
        target_node_id = self._addr_to_node.get(addr_key)

        if not target_node_id or target_node_id not in self._registry:
            logger.debug(f"[Rendezvous] 타겟 노드 미등록: {addr_key}")
            return

        target_reg = self._registry[target_node_id]
        requester_reg = self._registry.get(requester_node_id)

        if not requester_reg:
            logger.debug(f"[Rendezvous] 요청자 미등록: {requester_node_id.hex()[:8]}")
            return

        # 세션 ID 생성
        session_id = os.urandom(8)

        logger.info(
            f"[Rendezvous] 홀펀치 중개: "
            f"{requester_reg.external_ip}:{requester_reg.external_port} <-> "
            f"{target_reg.external_ip}:{target_reg.external_port}"
        )

        # 양쪽에 PUNCH_INITIATE 전송 (가능한 동시에)
        # 요청자에게: 타겟의 외부 주소 전달
        msg_to_requester = RendezvousProtocol.build_punch_initiate(
            target_reg.external_ip, target_reg.external_port,
            target_node_id, session_id
        )
        # 타겟에게: 요청자의 외부 주소 전달
        msg_to_target = RendezvousProtocol.build_punch_initiate(
            requester_reg.external_ip, requester_reg.external_port,
            requester_node_id, session_id
        )

        try:
            requester_reg.writer.write(msg_to_requester)
            target_reg.writer.write(msg_to_target)
            await asyncio.gather(
                requester_reg.writer.drain(),
                target_reg.writer.drain()
            )
        except Exception as e:
            logger.debug(f"[Rendezvous] PUNCH_INITIATE 전송 실패: {e}")

    async def _handle_heartbeat(self, payload: bytes, writer: asyncio.StreamWriter):
        """HEARTBEAT 처리"""
        node_id = payload[:8]
        if node_id in self._registry:
            self._registry[node_id].last_heartbeat = time.time()
        ack = RendezvousProtocol.build_heartbeat_ack()
        writer.write(ack)
        await writer.drain()

    async def _cleanup_loop(self):
        """만료된 등록 정리"""
        while self._running:
            await asyncio.sleep(RENDEZVOUS_STALE_TIMEOUT)
            now = time.time()
            stale = [
                nid for nid, reg in self._registry.items()
                if now - reg.last_heartbeat > RENDEZVOUS_STALE_TIMEOUT
            ]
            for nid in stale:
                reg = self._registry.pop(nid)
                addr_key = f"{reg.external_ip}:{reg.listening_port}"
                self._addr_to_node.pop(addr_key, None)
                try:
                    reg.writer.close()
                except Exception:
                    pass
                logger.debug(f"[Rendezvous] 만료 제거: {nid.hex()[:8]}")


# =============================================================================
# 홀펀치 클라이언트 (모든 노드에서 실행)
# =============================================================================

class HolePunchClient:
    """
    TCP Hole Punch 클라이언트

    1. 랑데부 서버에 등록 (외부 IP:port 확인)
    2. PUNCH_INITIATE 수신 시 동시 TCP open 시도
    3. 성공 시 (reader, writer) 반환
    """

    def __init__(self, local_port: int, node_id: bytes):
        self.local_port = local_port
        self.node_id = node_id
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._registered = False
        self._external_ip: Optional[str] = None
        self._external_port: Optional[int] = None

        # 홀펀칭 결과 콜백 (node.py에서 설정)
        self._on_punch_success: Optional[callable] = None

        # 대기 중인 펀치 세션
        self._pending_punches: Dict[bytes, asyncio.Future] = {}

    @property
    def is_registered(self) -> bool:
        return self._registered

    @property
    def external_ip(self) -> Optional[str]:
        return self._external_ip

    @property
    def external_port(self) -> Optional[int]:
        return self._external_port

    async def register(self, rendezvous_host: str, rendezvous_port: int = DEFAULT_RENDEZVOUS_PORT) -> bool:
        """랑데부 서버에 등록"""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(rendezvous_host, rendezvous_port),
                timeout=10
            )

            # REGISTER 전송
            msg = RendezvousProtocol.build_register(self.local_port, self.node_id)
            self._writer.write(msg)
            await self._writer.drain()

            # REGISTER_ACK 수신
            data = await asyncio.wait_for(self._reader.read(4096), timeout=10)
            if not data or len(data) < 5:
                return False

            parsed = RendezvousProtocol.parse_header(data)
            if not parsed or parsed[0] != MSG_REGISTER_ACK:
                return False

            payload = data[5:5 + parsed[1]]
            self._external_ip, self._external_port, status = \
                RendezvousProtocol.parse_register_ack(payload)

            if status != 0:
                return False

            self._registered = True

            # 하트비트 시작
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            # PUNCH_INITIATE 수신 대기 시작
            self._listen_task = asyncio.create_task(self._listen_for_punches())

            logger.info(
                f"[HolePunch] 랑데부 등록 성공: "
                f"외부={self._external_ip}:{self._external_port}"
            )
            return True

        except Exception as e:
            logger.debug(f"[HolePunch] 랑데부 등록 실패: {e}")
            return False

    async def request_punch(self, target_ip: str, target_port: int) -> HolePunchResult:
        """
        특정 피어에 대한 홀펀칭 요청

        1. 랑데부 서버에 CONNECT_REQUEST
        2. PUNCH_INITIATE 수신 대기
        3. 동시 TCP open 실행
        """
        if not self._registered or not self._writer:
            return HolePunchResult(success=False, error="랑데부 서버 미등록")

        # CONNECT_REQUEST 전송
        msg = RendezvousProtocol.build_connect_request(
            target_ip, target_port, self.node_id
        )
        try:
            self._writer.write(msg)
            await self._writer.drain()
        except Exception as e:
            return HolePunchResult(success=False, error=f"요청 전송 실패: {e}")

        # PUNCH_INITIATE 응답을 _listen_for_punches에서 처리
        # Future로 결과 대기
        future = asyncio.get_event_loop().create_future()
        # target 기반 키 (대기 중인 펀치)
        punch_key = f"{target_ip}:{target_port}".encode()
        self._pending_punches[punch_key] = future

        try:
            result = await asyncio.wait_for(future, timeout=HOLEPUNCH_TIMEOUT)
            return result
        except asyncio.TimeoutError:
            self._pending_punches.pop(punch_key, None)
            return HolePunchResult(success=False, error="홀펀칭 타임아웃")

    async def _listen_for_punches(self):
        """랑데부 서버에서 PUNCH_INITIATE 수신 대기"""
        buffer = b''

        try:
            while self._registered and self._reader:
                data = await self._reader.read(4096)
                if not data:
                    break

                buffer += data

                while len(buffer) >= 5:
                    parsed = RendezvousProtocol.parse_header(buffer)
                    if not parsed:
                        buffer = b''
                        break

                    msg_type, payload_len = parsed
                    total_len = 5 + payload_len
                    if len(buffer) < total_len:
                        break

                    payload = buffer[5:total_len]
                    buffer = buffer[total_len:]

                    if msg_type == MSG_PUNCH_INITIATE:
                        asyncio.create_task(self._handle_punch_initiate(payload))
                    elif msg_type == MSG_HEARTBEAT_ACK:
                        pass  # OK

        except (asyncio.CancelledError, ConnectionResetError):
            pass
        except Exception as e:
            logger.debug(f"[HolePunch] 수신 대기 오류: {e}")
        finally:
            self._registered = False

    async def _handle_punch_initiate(self, payload: bytes):
        """PUNCH_INITIATE 수신 - 동시 TCP open 실행"""
        peer_ip, peer_port, peer_node_id, session_id = \
            RendezvousProtocol.parse_punch_initiate(payload)

        logger.info(
            f"[HolePunch] 펀치 시작: {peer_ip}:{peer_port} "
            f"(session={session_id.hex()[:8]})"
        )

        # 동시 TCP open 시도
        result = await self._execute_simultaneous_open(peer_ip, peer_port)

        # PUNCH_ACK 전송
        if self._writer:
            status = 0 if result.success else 1
            ack = RendezvousProtocol.build_punch_ack(session_id, status)
            try:
                self._writer.write(ack)
                await self._writer.drain()
            except Exception:
                pass

        # 대기 중인 Future가 있으면 결과 전달
        punch_key = f"{peer_ip}:{peer_port}".encode()
        future = self._pending_punches.pop(punch_key, None)
        if future and not future.done():
            future.set_result(result)
        elif result.success and self._on_punch_success:
            # 상대방이 먼저 요청한 경우 (내가 요청한 게 아닌 경우)
            await self._on_punch_success(result)

    async def _execute_simultaneous_open(
        self, peer_ip: str, peer_port: int
    ) -> HolePunchResult:
        """
        TCP Simultaneous Open 시도

        두 가지를 동시에 실행:
        1. connect() - 상대방의 외부 주소로 TCP 연결 시도
        2. accept() - 같은 포트에서 인바운드 연결 대기

        어느 쪽이든 먼저 성공하면 사용
        """

        async def try_connect() -> Optional[Tuple[asyncio.StreamReader, asyncio.StreamWriter]]:
            """반복적으로 connect 시도"""
            for attempt in range(HOLEPUNCH_RETRY_COUNT):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    if sys.platform != 'win32':
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                    sock.setblocking(False)
                    sock.bind(('0.0.0.0', self.local_port))

                    loop = asyncio.get_event_loop()
                    await asyncio.wait_for(
                        loop.sock_connect(sock, (peer_ip, peer_port)),
                        timeout=2.0
                    )

                    # 성공! StreamReader/Writer로 변환
                    reader, writer = await asyncio.open_connection(sock=sock)
                    logger.info(f"[HolePunch] connect 성공: {peer_ip}:{peer_port} (시도 {attempt + 1})")
                    return reader, writer

                except (ConnectionRefusedError, OSError, asyncio.TimeoutError):
                    try:
                        sock.close()
                    except Exception:
                        pass
                    await asyncio.sleep(HOLEPUNCH_RETRY_DELAY)
                except Exception as e:
                    try:
                        sock.close()
                    except Exception:
                        pass
                    logger.debug(f"[HolePunch] connect 시도 {attempt + 1} 실패: {e}")
                    await asyncio.sleep(HOLEPUNCH_RETRY_DELAY)

            return None

        async def try_accept() -> Optional[Tuple[asyncio.StreamReader, asyncio.StreamWriter]]:
            """같은 포트에서 인바운드 대기"""
            try:
                server = await asyncio.start_server(
                    lambda r, w: None,  # 더미 (아래에서 직접 처리)
                    '0.0.0.0', self.local_port,
                    reuse_address=True
                )

                # 타임아웃까지 대기
                await asyncio.sleep(HOLEPUNCH_TIMEOUT)
                server.close()
                await server.wait_closed()
            except Exception:
                pass
            return None

        # 두 방법 동시 실행
        connect_task = asyncio.create_task(try_connect())
        # accept는 이미 node의 서버가 처리하므로 connect만 시도
        # (node의 _handle_inbound에서 인바운드 연결 처리)

        try:
            result = await asyncio.wait_for(connect_task, timeout=HOLEPUNCH_TIMEOUT)
            if result:
                reader, writer = result
                return HolePunchResult(
                    success=True,
                    reader=reader,
                    writer=writer,
                    peer_ip=peer_ip,
                    peer_port=peer_port
                )
        except asyncio.TimeoutError:
            connect_task.cancel()
        except Exception as e:
            logger.debug(f"[HolePunch] 실행 오류: {e}")

        return HolePunchResult(
            success=False,
            peer_ip=peer_ip,
            peer_port=peer_port,
            error="동시 TCP open 실패"
        )

    async def _heartbeat_loop(self):
        """주기적 하트비트 전송"""
        try:
            while self._registered and self._writer:
                await asyncio.sleep(RENDEZVOUS_HEARTBEAT_INTERVAL)
                msg = RendezvousProtocol.build_heartbeat(self.node_id)
                try:
                    self._writer.write(msg)
                    await self._writer.drain()
                except Exception:
                    self._registered = False
                    break
        except asyncio.CancelledError:
            pass

    async def stop(self):
        """클라이언트 중지"""
        self._registered = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._listen_task:
            self._listen_task.cancel()

        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass

        self._pending_punches.clear()
        logger.info("[HolePunch] 클라이언트 중지")
