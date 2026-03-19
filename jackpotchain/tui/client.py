"""
RPC Client for TUI

JSON-RPC 클라이언트
"""

import asyncio
import aiohttp
from typing import Any, Optional
from dataclasses import dataclass


@dataclass
class RPCResponse:
    """RPC 응답"""
    success: bool
    result: Any = None
    error: str = ""


class RPCClient:
    """JSON-RPC 클라이언트"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8332):
        self.host = host
        self.port = port
        self.url = f"http://{host}:{port}"
        self._session: Optional[aiohttp.ClientSession] = None
        self._request_id = 0

    async def _ensure_session(self):
        """세션 확보"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def close(self):
        """세션 종료"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def call(self, method: str, *params) -> RPCResponse:
        """RPC 호출"""
        await self._ensure_session()

        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": list(params) if params else []
        }

        try:
            async with self._session.post(self.url, json=payload, timeout=10) as resp:
                data = await resp.json()

                if "error" in data and data["error"]:
                    return RPCResponse(
                        success=False,
                        error=data["error"].get("message", "Unknown error")
                    )

                return RPCResponse(
                    success=True,
                    result=data.get("result")
                )
        except aiohttp.ClientError as e:
            return RPCResponse(success=False, error=f"Connection error: {e}")
        except asyncio.TimeoutError:
            return RPCResponse(success=False, error="Request timeout")
        except Exception as e:
            return RPCResponse(success=False, error=str(e))

    # =========================================================================
    # Blockchain
    # =========================================================================

    async def get_blockchain_info(self) -> RPCResponse:
        """블록체인 정보"""
        return await self.call("getblockchaininfo")

    async def get_block_count(self) -> RPCResponse:
        """블록 높이"""
        return await self.call("getblockcount")

    async def get_recent_blocks(self, count: int = 10) -> RPCResponse:
        """최근 블록 요약"""
        return await self.call("getrecentblocks", [count])

    # =========================================================================
    # Wallet
    # =========================================================================

    async def get_balance(self, address: str = None) -> RPCResponse:
        """잔액 조회"""
        if address:
            return await self.call("getbalance", address)
        return await self.call("getbalance")

    async def get_balances(self, address: str = None) -> RPCResponse:
        """JACK + POT 잔액 조회"""
        if address:
            return await self.call("getbalances", address)
        return await self.call("getbalances")

    async def get_new_address(self, label: str = "") -> RPCResponse:
        """새 주소 생성"""
        return await self.call("getnewaddress", label)

    async def list_unspent(self, address: str = None) -> RPCResponse:
        """UTXO 목록"""
        if address:
            return await self.call("listunspent", address)
        return await self.call("listunspent")

    async def send_to_address(self, address: str, amount: float) -> RPCResponse:
        """송금"""
        return await self.call("sendtoaddress", address, amount)

    async def exchange_to_pot(self, jack_amount: float) -> RPCResponse:
        """JACK -> POT 교환"""
        return await self.call("exchangetopot", jack_amount)

    async def list_wallets(self) -> RPCResponse:
        """로드된 지갑 목록"""
        return await self.call("listwallets")

    async def set_wallet(self, name: str) -> RPCResponse:
        """활성 지갑 변경"""
        return await self.call("setwallet", name)

    async def get_active_wallet(self) -> RPCResponse:
        """현재 활성 지갑"""
        return await self.call("getactivewallet")

    # =========================================================================
    # Network
    # =========================================================================

    async def get_network_info(self) -> RPCResponse:
        """네트워크 정보"""
        return await self.call("getnetworkinfo")

    async def get_peer_info(self) -> RPCResponse:
        """피어 정보"""
        return await self.call("getpeerinfo")

    # =========================================================================
    # Mining
    # =========================================================================

    async def get_mining_info(self) -> RPCResponse:
        """채굴 정보"""
        return await self.call("getmininginfo")

    async def start_mining(self, address: str = None) -> RPCResponse:
        """채굴 시작"""
        if address:
            return await self.call("startmining", address)
        return await self.call("startmining")

    async def stop_mining(self) -> RPCResponse:
        """채굴 중지"""
        return await self.call("stopmining")

    # =========================================================================
    # Mempool
    # =========================================================================

    async def get_mempool_info(self) -> RPCResponse:
        """멤풀 정보"""
        return await self.call("getmempoolinfo")

    # =========================================================================
    # Lotto
    # =========================================================================

    async def get_lotto_info(self) -> RPCResponse:
        """로또 정보"""
        return await self.call("getlottoinfo")

    async def get_jackpot_pool(self) -> RPCResponse:
        """잭팟 풀 상태"""
        return await self.call("getjackpotpool")

    async def lotto_commit(self, chosen_numbers: list = None) -> RPCResponse:
        """로또 참여"""
        if chosen_numbers:
            return await self.call("lottocommit", chosen_numbers)
        return await self.call("lottocommit")

    async def lotto_check_result(self, tx_id: str) -> RPCResponse:
        """로또 결과 확인 (TX ID로 조회)"""
        return await self.call("lottocheckresult", tx_id)

    async def list_lotto_commits(self, address: str = None) -> RPCResponse:
        """대기 중인 커밋 목록"""
        if address:
            return await self.call("listlottocommits", address)
        return await self.call("listlottocommits")
