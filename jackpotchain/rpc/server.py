"""
Step 14: RPC 서버
- JSON-RPC API
- 노드 제어
"""

import json
import asyncio
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass
from aiohttp import web

from ..consensus.chain import Blockchain
from ..mempool.pool import Mempool
from ..wallet.wallet import Wallet
from ..network.node import Node
from ..constants import DEFAULT_RPC_PORT
from ..gacha.game import GachaGame


@dataclass
class RPCError:
    """RPC 에러"""
    code: int
    message: str

    def to_dict(self):
        return {'code': self.code, 'message': self.message}


# 표준 에러 코드
RPC_PARSE_ERROR = RPCError(-32700, "Parse error")
RPC_INVALID_REQUEST = RPCError(-32600, "Invalid request")
RPC_METHOD_NOT_FOUND = RPCError(-32601, "Method not found")
RPC_INVALID_PARAMS = RPCError(-32602, "Invalid params")
RPC_INTERNAL_ERROR = RPCError(-32603, "Internal error")


class RPCServer:
    """
    JSON-RPC 서버

    API 카테고리:
    - Blockchain: getblockchaininfo, getblock, getblockhash
    - Network: getnetworkinfo, getpeerinfo
    - Mempool: getmempoolinfo, getrawmempool
    - Wallet: getbalance, getnewaddress, sendtoaddress
    - Mining: getmininginfo, submitblock
    """

    def __init__(
        self,
        blockchain: Blockchain,
        mempool: Mempool = None,
        wallet: Wallet = None,
        node: Node = None,
        gacha: GachaGame = None,
        host: str = "127.0.0.1",
        port: int = DEFAULT_RPC_PORT
    ):
        self.blockchain = blockchain
        self.mempool = mempool or Mempool()
        self.wallet = wallet
        self.node = node
        self.gacha = gacha or GachaGame()

        self.host = host
        self.port = port

        self._app = web.Application()
        self._app.router.add_post('/', self._handle_request)

        # 메서드 등록
        self._methods: Dict[str, Callable] = {}
        self._register_methods()

    def _register_methods(self):
        """RPC 메서드 등록"""
        # Blockchain
        self._methods['getblockchaininfo'] = self._getblockchaininfo
        self._methods['getblock'] = self._getblock
        self._methods['getblockhash'] = self._getblockhash
        self._methods['getblockcount'] = self._getblockcount
        self._methods['getbestblockhash'] = self._getbestblockhash

        # Mempool
        self._methods['getmempoolinfo'] = self._getmempoolinfo
        self._methods['getrawmempool'] = self._getrawmempool
        self._methods['sendrawtransaction'] = self._sendrawtransaction

        # Wallet
        self._methods['getbalance'] = self._getbalance
        self._methods['getnewaddress'] = self._getnewaddress
        self._methods['listunspent'] = self._listunspent
        self._methods['sendtoaddress'] = self._sendtoaddress

        # Network
        self._methods['getnetworkinfo'] = self._getnetworkinfo
        self._methods['getpeerinfo'] = self._getpeerinfo

        # Mining
        self._methods['getmininginfo'] = self._getmininginfo

        # Gacha
        self._methods['getgachainfo'] = self._getgachainfo
        self._methods['getjackpotpool'] = self._getjackpotpool

        # Utility
        self._methods['help'] = self._help

    async def start(self):
        """서버 시작"""
        runner = web.AppRunner(self._app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()

    async def _handle_request(self, request: web.Request) -> web.Response:
        """RPC 요청 처리"""
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return self._error_response(None, RPC_PARSE_ERROR)

        # 배치 요청
        if isinstance(data, list):
            results = []
            for req in data:
                result = await self._process_request(req)
                results.append(result)
            return web.json_response(results)

        # 단일 요청
        result = await self._process_request(data)
        return web.json_response(result)

    async def _process_request(self, data: dict) -> dict:
        """단일 요청 처리"""
        req_id = data.get('id')

        # 필수 필드 확인
        if 'method' not in data:
            return self._error_dict(req_id, RPC_INVALID_REQUEST)

        method = data['method']
        params = data.get('params', [])

        # 메서드 찾기
        if method not in self._methods:
            return self._error_dict(req_id, RPC_METHOD_NOT_FOUND)

        # 실행
        try:
            handler = self._methods[method]

            if isinstance(params, list):
                result = await self._call_method(handler, *params)
            elif isinstance(params, dict):
                result = await self._call_method(handler, **params)
            else:
                result = await self._call_method(handler)

            return {
                'jsonrpc': '2.0',
                'id': req_id,
                'result': result
            }
        except Exception as e:
            return self._error_dict(req_id, RPCError(-32000, str(e)))

    async def _call_method(self, handler: Callable, *args, **kwargs):
        """메서드 호출"""
        if asyncio.iscoroutinefunction(handler):
            return await handler(*args, **kwargs)
        return handler(*args, **kwargs)

    def _error_dict(self, req_id: Any, error: RPCError) -> dict:
        """에러 응답 딕셔너리"""
        return {
            'jsonrpc': '2.0',
            'id': req_id,
            'error': error.to_dict()
        }

    def _error_response(self, req_id: Any, error: RPCError) -> web.Response:
        """에러 응답"""
        return web.json_response(self._error_dict(req_id, error))

    # =========================================================================
    # Blockchain Methods
    # =========================================================================

    def _getblockchaininfo(self) -> dict:
        """블록체인 정보"""
        return {
            'chain': 'jackpotchain',
            'blocks': self.blockchain.get_height(),
            'bestblockhash': self.blockchain.get_tip_hash().hex(),
            'difficulty': self.blockchain.get_difficulty(),
            'mediantime': 0,
            'verificationprogress': 1.0,
            'chainwork': hex(self.blockchain.get_total_work()),
        }

    def _getblock(self, blockhash: str, verbosity: int = 1) -> Any:
        """블록 조회"""
        block_hash = bytes.fromhex(blockhash)
        block = self.blockchain.get_block(block_hash)

        if block is None:
            raise Exception("Block not found")

        if verbosity == 0:
            return block.serialize().hex()

        index = self.blockchain.get_block_index(block_hash)
        return {
            'hash': block.get_hash_hex(),
            'confirmations': self.blockchain.get_confirmations(block_hash),
            'height': index.height if index else 0,
            'version': block.header.version,
            'merkleroot': block.header.merkle_root.hex(),
            'time': block.header.timestamp,
            'nonce': block.header.nonce,
            'difficulty': block.header.difficulty_target,
            'nTx': len(block.transactions),
            'previousblockhash': block.header.prev_block_hash.hex(),
            'tx': [tx.get_txid().hex() for tx in block.transactions] if verbosity > 1 else [],
        }

    def _getblockhash(self, height: int) -> str:
        """높이로 블록 해시 조회"""
        block = self.blockchain.get_block_by_height(height)
        if block is None:
            raise Exception("Block not found")
        return block.get_hash_hex()

    def _getblockcount(self) -> int:
        """블록 높이"""
        return self.blockchain.get_height()

    def _getbestblockhash(self) -> str:
        """최신 블록 해시"""
        return self.blockchain.get_tip_hash().hex()

    # =========================================================================
    # Mempool Methods
    # =========================================================================

    def _getmempoolinfo(self) -> dict:
        """멤풀 정보"""
        stats = self.mempool.get_stats()
        return {
            'size': stats['count'],
            'bytes': stats['size'],
            'usage': stats['size'],
            'minfee': stats['min_fee_rate'],
        }

    def _getrawmempool(self, verbose: bool = False) -> Any:
        """멤풀 TX 목록"""
        txids = self.mempool.get_all_txids()

        if not verbose:
            return [txid.hex() for txid in txids]

        result = {}
        for txid in txids:
            entry = self.mempool._entries.get(txid)
            if entry:
                result[txid.hex()] = {
                    'fee': entry.fee,
                    'size': entry.size,
                    'time': entry.added_time,
                }
        return result

    async def _sendrawtransaction(self, hexstring: str) -> str:
        """TX 브로드캐스트"""
        from ..core.transaction import Transaction

        tx_bytes = bytes.fromhex(hexstring)
        tx, _ = Transaction.deserialize(tx_bytes)

        success, msg = self.mempool.add_tx(
            tx,
            self.blockchain.utxo_set,
            self.blockchain.get_height()
        )

        if not success:
            raise Exception(msg)

        # 네트워크 브로드캐스트
        if self.node:
            await self.node.broadcast_tx(tx)

        return tx.get_txid().hex()

    # =========================================================================
    # Wallet Methods
    # =========================================================================

    def _getbalance(self) -> float:
        """잔액 조회"""
        if not self.wallet:
            raise Exception("Wallet not available")

        balance = self.wallet.get_balance(
            self.blockchain.utxo_set,
            self.blockchain.get_height()
        )
        return balance / 100_000_000  # satoshi → JACK

    def _getnewaddress(self, label: str = "") -> str:
        """새 주소 생성"""
        if not self.wallet:
            raise Exception("Wallet not available")

        return self.wallet.generate_address(label)

    def _listunspent(self) -> list:
        """UTXO 목록"""
        if not self.wallet:
            raise Exception("Wallet not available")

        utxos = self.wallet.get_utxos(self.blockchain.utxo_set)
        return [
            {
                'txid': utxo.tx_id.hex(),
                'vout': utxo.output_index,
                'amount': utxo.output.jack_value / 100_000_000,
                'confirmations': 0,  # TODO
            }
            for utxo in utxos
        ]

    async def _sendtoaddress(self, address: str, amount: float) -> str:
        """송금"""
        if not self.wallet:
            raise Exception("Wallet not available")

        amount_satoshi = int(amount * 100_000_000)

        tx, error = self.wallet.create_transaction(
            self.blockchain.utxo_set,
            [(address, amount_satoshi)],
            current_height=self.blockchain.get_height()
        )

        if tx is None:
            raise Exception(error)

        # 멤풀에 추가
        success, msg = self.mempool.add_tx(
            tx,
            self.blockchain.utxo_set,
            self.blockchain.get_height()
        )

        if not success:
            raise Exception(msg)

        # 브로드캐스트
        if self.node:
            await self.node.broadcast_tx(tx)

        return tx.get_txid().hex()

    # =========================================================================
    # Network Methods
    # =========================================================================

    def _getnetworkinfo(self) -> dict:
        """네트워크 정보"""
        if not self.node:
            return {'connections': 0}

        stats = self.node.peer_manager.get_stats()
        return {
            'version': 70015,
            'subversion': '/JackpotChain:0.1.0/',
            'connections': stats['connected'],
            'connections_in': stats['inbound'],
            'connections_out': stats['outbound'],
        }

    def _getpeerinfo(self) -> list:
        """피어 정보"""
        if not self.node:
            return []

        peers = self.node.peer_manager.get_connected_peers()
        return [
            {
                'addr': str(p.address),
                'version': p.version,
                'subver': p.user_agent,
                'startingheight': p.start_height,
                'synced_headers': p.synced_headers,
                'inbound': p.is_inbound,
            }
            for p in peers
        ]

    # =========================================================================
    # Mining Methods
    # =========================================================================

    def _getmininginfo(self) -> dict:
        """채굴 정보"""
        return {
            'blocks': self.blockchain.get_height(),
            'difficulty': self.blockchain.get_difficulty(),
            'networkhashps': 0,  # TODO
            'pooledtx': self.mempool.get_stats()['count'],
        }

    # =========================================================================
    # Gacha Methods
    # =========================================================================

    def _getgachainfo(self) -> dict:
        """가챠 시스템 정보"""
        stats = self.gacha.get_stats()
        return {
            'pool_balance': stats['balance'] / 100_000_000,  # JACK
            'pool_balance_satoshi': stats['balance'],
            'total_fees_collected': stats['total_fees_collected'],
            'total_payouts': stats['total_payouts'],
            'payout_count': stats['payout_count'],
            'pending_commits': stats['pending_commits'],
            'win_probability': '1%',
            'payout_ratio': '60%',
        }

    def _getjackpotpool(self) -> dict:
        """잭팟 풀 상태"""
        pool_stats = self.gacha.pool.get_stats()
        return {
            'balance': pool_stats['balance'] / 100_000_000,
            'balance_satoshi': pool_stats['balance'],
            'next_payout': pool_stats['balance'] * 0.6 / 100_000_000,
            'total_collected': pool_stats['total_fees_collected'] / 100_000_000,
        }

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _help(self, command: str = None) -> Any:
        """도움말"""
        if command:
            if command in self._methods:
                return f"Help for {command}: (not implemented)"
            raise Exception(f"Unknown command: {command}")

        return list(self._methods.keys())
