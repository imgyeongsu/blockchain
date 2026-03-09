"""
NAT Traversal - PCP/NAT-PMP 자동 포트 매핑

Bitcoin Core v29.0 전략:
  1순위: PCP (Port Control Protocol, RFC 6887)
  2순위: NAT-PMP (RFC 6886) - PCP 실패 시
  3순위: 아웃바운드 전용 모드

참고: 홈서버/시드노드는 공유기에서 수동 포트포워딩 권장
"""

import asyncio
import socket
import struct
import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class NATProtocol(Enum):
    """NAT 프로토콜 타입"""
    NONE = "none"
    PCP = "pcp"
    NAT_PMP = "nat-pmp"
    MANUAL = "manual"  # 수동 포트포워딩


@dataclass
class MappingResult:
    """포트 매핑 결과"""
    success: bool
    protocol: NATProtocol
    external_ip: Optional[str] = None
    external_port: Optional[int] = None
    internal_port: Optional[int] = None
    lifetime: int = 0  # 초 단위
    error: Optional[str] = None


class NATManager:
    """
    NAT 자동 포트 매핑 관리자

    Usage:
        nat = NATManager(internal_port=8333)
        result = await nat.setup_port_mapping()
        if result.success:
            print(f"외부 주소: {result.external_ip}:{result.external_port}")
    """

    # 프로토콜 상수
    NAT_PMP_PORT = 5351
    PCP_PORT = 5351

    # NAT-PMP 옵코드
    NAT_PMP_OP_EXTERNAL_IP = 0
    NAT_PMP_OP_MAP_UDP = 1
    NAT_PMP_OP_MAP_TCP = 2

    # PCP 옵코드
    PCP_OP_MAP = 1
    PCP_OP_PEER = 2

    # 기본 설정
    DEFAULT_LIFETIME = 7200  # 2시간
    RETRY_LIFETIME = 3600    # 재시도 시 1시간

    def __init__(
        self,
        internal_port: int = 8333,
        lifetime: int = DEFAULT_LIFETIME,
        gateway: Optional[str] = None
    ):
        self.internal_port = internal_port
        self.lifetime = lifetime
        self._gateway = gateway
        self._active_protocol: NATProtocol = NATProtocol.NONE
        self._mapping_result: Optional[MappingResult] = None
        self._refresh_task: Optional[asyncio.Task] = None

    @property
    def is_mapped(self) -> bool:
        """포트 매핑 활성화 여부"""
        return self._mapping_result is not None and self._mapping_result.success

    @property
    def external_address(self) -> Optional[Tuple[str, int]]:
        """외부 주소 (ip, port)"""
        if self._mapping_result and self._mapping_result.success:
            return (self._mapping_result.external_ip, self._mapping_result.external_port)
        return None

    def _get_gateway(self) -> Optional[str]:
        """기본 게이트웨이 주소 찾기"""
        if self._gateway:
            return self._gateway

        try:
            # UDP 소켓으로 게이트웨이 찾기 (연결 안 함)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]

            # 일반적인 게이트웨이 추정 (x.x.x.1)
            parts = local_ip.split('.')
            gateway = f"{parts[0]}.{parts[1]}.{parts[2]}.1"
            return gateway
        except Exception as e:
            logger.debug(f"게이트웨이 탐지 실패: {e}")
            return None

    async def setup_port_mapping(self) -> MappingResult:
        """
        포트 매핑 설정 (PCP → NAT-PMP → 실패)
        """
        gateway = self._get_gateway()
        if not gateway:
            return MappingResult(
                success=False,
                protocol=NATProtocol.NONE,
                error="게이트웨이를 찾을 수 없음"
            )

        logger.info(f"NAT 포트 매핑 시도 (게이트웨이: {gateway}, 포트: {self.internal_port})")

        # 1순위: PCP
        result = await self._try_pcp(gateway)
        if result.success:
            logger.info(f"PCP 매핑 성공: {result.external_ip}:{result.external_port}")
            self._active_protocol = NATProtocol.PCP
            self._mapping_result = result
            self._start_refresh_task()
            return result

        # 2순위: NAT-PMP
        result = await self._try_nat_pmp(gateway)
        if result.success:
            logger.info(f"NAT-PMP 매핑 성공: {result.external_ip}:{result.external_port}")
            self._active_protocol = NATProtocol.NAT_PMP
            self._mapping_result = result
            self._start_refresh_task()
            return result

        # 실패
        logger.warning("NAT 포트 매핑 실패 - 아웃바운드 전용 모드로 동작")
        return MappingResult(
            success=False,
            protocol=NATProtocol.NONE,
            error="PCP/NAT-PMP 모두 실패"
        )

    async def _try_pcp(self, gateway: str) -> MappingResult:
        """PCP (Port Control Protocol) 시도"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(3.0)
            sock.setblocking(False)

            # PCP MAP 요청 생성
            request = self._build_pcp_map_request()

            loop = asyncio.get_event_loop()
            await loop.sock_sendto(sock, request, (gateway, self.PCP_PORT))

            try:
                response, _ = await asyncio.wait_for(
                    loop.sock_recvfrom(sock, 1024),
                    timeout=3.0
                )
                return self._parse_pcp_response(response)
            except asyncio.TimeoutError:
                return MappingResult(
                    success=False,
                    protocol=NATProtocol.PCP,
                    error="PCP 응답 타임아웃"
                )
            finally:
                sock.close()

        except Exception as e:
            return MappingResult(
                success=False,
                protocol=NATProtocol.PCP,
                error=f"PCP 오류: {e}"
            )

    def _build_pcp_map_request(self) -> bytes:
        """PCP MAP 요청 패킷 생성"""
        # PCP 헤더 (24 bytes)
        version = 2
        opcode = self.PCP_OP_MAP
        lifetime = self.lifetime

        # 클라이언트 IP (IPv4-mapped IPv6)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
        except:
            local_ip = "0.0.0.0"

        ip_parts = [int(x) for x in local_ip.split('.')]
        client_ip = bytes([0]*10 + [0xff, 0xff] + ip_parts)

        header = struct.pack(
            '>BBH I 12s',
            version,
            opcode,
            0,  # reserved
            lifetime,
            client_ip
        )

        # MAP 옵코드 페이로드 (36 bytes)
        import os
        nonce = os.urandom(12)
        protocol = 6  # TCP
        internal_port = self.internal_port
        suggested_external_port = self.internal_port
        suggested_external_ip = bytes(16)  # 모든 IP 허용

        payload = struct.pack(
            '>12s B 3x HH 16s',
            nonce,
            protocol,
            internal_port,
            suggested_external_port,
            suggested_external_ip
        )

        return header + payload

    def _parse_pcp_response(self, data: bytes) -> MappingResult:
        """PCP 응답 파싱"""
        if len(data) < 24:
            return MappingResult(
                success=False,
                protocol=NATProtocol.PCP,
                error="응답 길이 부족"
            )

        version, opcode, reserved, result_code, lifetime = struct.unpack(
            '>BBH B 3x I', data[:12]
        )

        if result_code != 0:
            error_msgs = {
                1: "UNSUPP_VERSION",
                2: "NOT_AUTHORIZED",
                3: "MALFORMED_REQUEST",
                4: "UNSUPP_OPCODE",
                5: "UNSUPP_OPTION",
                6: "MALFORMED_OPTION",
                7: "NETWORK_FAILURE",
                8: "NO_RESOURCES",
                9: "UNSUPP_PROTOCOL",
            }
            return MappingResult(
                success=False,
                protocol=NATProtocol.PCP,
                error=f"PCP 오류: {error_msgs.get(result_code, result_code)}"
            )

        # MAP 응답에서 외부 주소 추출
        if len(data) >= 60:
            # 외부 IP (마지막 4바이트가 IPv4)
            external_ip_bytes = data[56:60]
            external_ip = socket.inet_ntoa(external_ip_bytes)

            # 외부 포트
            external_port = struct.unpack('>H', data[42:44])[0]

            return MappingResult(
                success=True,
                protocol=NATProtocol.PCP,
                external_ip=external_ip,
                external_port=external_port,
                internal_port=self.internal_port,
                lifetime=lifetime
            )

        return MappingResult(
            success=False,
            protocol=NATProtocol.PCP,
            error="MAP 응답 파싱 실패"
        )

    async def _try_nat_pmp(self, gateway: str) -> MappingResult:
        """NAT-PMP 시도"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(3.0)
            sock.setblocking(False)

            loop = asyncio.get_event_loop()

            # 1. 외부 IP 요청
            external_ip = await self._nat_pmp_get_external_ip(sock, gateway, loop)
            if not external_ip:
                sock.close()
                return MappingResult(
                    success=False,
                    protocol=NATProtocol.NAT_PMP,
                    error="외부 IP 조회 실패"
                )

            # 2. 포트 매핑 요청
            request = self._build_nat_pmp_map_request()
            await loop.sock_sendto(sock, request, (gateway, self.NAT_PMP_PORT))

            try:
                response, _ = await asyncio.wait_for(
                    loop.sock_recvfrom(sock, 1024),
                    timeout=3.0
                )
                result = self._parse_nat_pmp_map_response(response)
                if result.success:
                    result.external_ip = external_ip
                return result
            except asyncio.TimeoutError:
                return MappingResult(
                    success=False,
                    protocol=NATProtocol.NAT_PMP,
                    error="NAT-PMP MAP 응답 타임아웃"
                )
            finally:
                sock.close()

        except Exception as e:
            return MappingResult(
                success=False,
                protocol=NATProtocol.NAT_PMP,
                error=f"NAT-PMP 오류: {e}"
            )

    async def _nat_pmp_get_external_ip(
        self,
        sock: socket.socket,
        gateway: str,
        loop: asyncio.AbstractEventLoop
    ) -> Optional[str]:
        """NAT-PMP로 외부 IP 조회"""
        # 요청: version(1) + opcode(1)
        request = struct.pack('>BB', 0, self.NAT_PMP_OP_EXTERNAL_IP)

        try:
            await loop.sock_sendto(sock, request, (gateway, self.NAT_PMP_PORT))
            response, _ = await asyncio.wait_for(
                loop.sock_recvfrom(sock, 1024),
                timeout=3.0
            )

            if len(response) >= 12:
                version, opcode, result_code, epoch, ip_bytes = struct.unpack(
                    '>BB H I 4s', response[:12]
                )
                if result_code == 0:
                    return socket.inet_ntoa(ip_bytes)
        except:
            pass

        return None

    def _build_nat_pmp_map_request(self) -> bytes:
        """NAT-PMP MAP 요청 생성"""
        return struct.pack(
            '>BB HHI',
            0,  # version
            self.NAT_PMP_OP_MAP_TCP,  # opcode
            0,  # reserved
            self.internal_port,  # internal port
            self.lifetime  # lifetime
        )

    def _parse_nat_pmp_map_response(self, data: bytes) -> MappingResult:
        """NAT-PMP MAP 응답 파싱"""
        if len(data) < 16:
            return MappingResult(
                success=False,
                protocol=NATProtocol.NAT_PMP,
                error="응답 길이 부족"
            )

        version, opcode, result_code, epoch, internal_port, external_port, lifetime = struct.unpack(
            '>BB H I HHI', data[:16]
        )

        if result_code != 0:
            error_msgs = {
                1: "UNSUPP_VERSION",
                2: "NOT_AUTHORIZED",
                3: "NETWORK_FAILURE",
                4: "OUT_OF_RESOURCES",
                5: "UNSUPP_OPCODE",
            }
            return MappingResult(
                success=False,
                protocol=NATProtocol.NAT_PMP,
                error=f"NAT-PMP 오류: {error_msgs.get(result_code, result_code)}"
            )

        return MappingResult(
            success=True,
            protocol=NATProtocol.NAT_PMP,
            external_port=external_port,
            internal_port=internal_port,
            lifetime=lifetime
        )

    def _start_refresh_task(self):
        """매핑 갱신 태스크 시작"""
        if self._refresh_task:
            self._refresh_task.cancel()

        self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def _refresh_loop(self):
        """매핑 갱신 루프 (lifetime의 절반마다)"""
        while True:
            if not self._mapping_result:
                break

            refresh_interval = max(self._mapping_result.lifetime // 2, 60)
            await asyncio.sleep(refresh_interval)

            logger.debug(f"NAT 매핑 갱신 중...")

            gateway = self._get_gateway()
            if not gateway:
                continue

            if self._active_protocol == NATProtocol.PCP:
                result = await self._try_pcp(gateway)
            elif self._active_protocol == NATProtocol.NAT_PMP:
                result = await self._try_nat_pmp(gateway)
            else:
                break

            if result.success:
                self._mapping_result = result
                logger.debug(f"NAT 매핑 갱신 완료 (lifetime: {result.lifetime}s)")
            else:
                logger.warning(f"NAT 매핑 갱신 실패: {result.error}")

    async def remove_mapping(self):
        """포트 매핑 제거"""
        if self._refresh_task:
            self._refresh_task.cancel()
            self._refresh_task = None

        if not self._mapping_result or not self._mapping_result.success:
            return

        gateway = self._get_gateway()
        if not gateway:
            return

        try:
            if self._active_protocol == NATProtocol.NAT_PMP:
                # lifetime=0으로 매핑 제거
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(1.0)
                request = struct.pack(
                    '>BB HHI',
                    0, self.NAT_PMP_OP_MAP_TCP,
                    0, self.internal_port, 0  # lifetime=0
                )
                sock.sendto(request, (gateway, self.NAT_PMP_PORT))
                sock.close()

            elif self._active_protocol == NATProtocol.PCP:
                # PCP도 lifetime=0으로 제거
                self.lifetime = 0
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(1.0)
                request = self._build_pcp_map_request()
                sock.sendto(request, (gateway, self.PCP_PORT))
                sock.close()

            logger.info("NAT 매핑 제거 완료")
        except Exception as e:
            logger.debug(f"NAT 매핑 제거 오류: {e}")

        self._mapping_result = None
        self._active_protocol = NATProtocol.NONE
