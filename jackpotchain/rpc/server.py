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
from ..consensus.difficulty import difficulty_to_hashrate
from ..mempool.pool import Mempool
from ..wallet.wallet import Wallet
from ..network.node import Node
from ..constants import DEFAULT_RPC_PORT
from ..gacha.game import GachaGame
from ..gacha.service import GachaService, create_gacha_service


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
        gacha_service: GachaService = None,
        data_dir: str = None,
        host: str = "127.0.0.1",
        port: int = DEFAULT_RPC_PORT
    ):
        self.blockchain = blockchain
        self.mempool = mempool or Mempool()
        self.wallet = wallet
        self.node = node
        self.gacha = gacha or GachaGame()
        self.gacha_service = gacha_service or create_gacha_service(data_dir=data_dir)

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

        # Lotto (16-2 Final)
        self._methods['getlottoinfo'] = self._getlottoinfo
        self._methods['getjackpotpool'] = self._getjackpotpool
        self._methods['lottocommit'] = self._lottocommit
        self._methods['lottoclaim'] = self._lottoclaim
        self._methods['lottocheckresult'] = self._lottocheckresult
        self._methods['listlottocommits'] = self._listlottocommits

        # Legacy aliases (deprecated)
        self._methods['getgachainfo'] = self._getlottoinfo
        self._methods['gachacommit'] = self._lottocommit
        self._methods['gachareveal'] = self._lottoclaim
        self._methods['listgachacommits'] = self._listlottocommits

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

    def _getbalance(self, address: str = None) -> float:
        """잔액 조회 (주소 지정 가능)"""
        current_height = self.blockchain.get_height()

        if address:
            # 특정 주소의 잔액 조회
            balance = self.blockchain.utxo_set.get_balance(address, current_height)
            return balance / 100_000_000  # satoshi → JACK

        if not self.wallet:
            raise Exception("Wallet not available")

        balance = self.wallet.get_balance(
            self.blockchain.utxo_set,
            current_height
        )
        return balance / 100_000_000  # satoshi → JACK

    def _getnewaddress(self, label: str = "") -> str:
        """새 주소 생성"""
        if not self.wallet:
            raise Exception("Wallet not available")

        return self.wallet.generate_address(label)

    def _listunspent(self, address: str = None) -> list:
        """UTXO 목록 (주소 지정 가능)"""
        if address:
            # 특정 주소의 UTXO
            utxos = self.blockchain.utxo_set.get_utxos_for_address(address)
            return [
                {
                    'txid': utxo.outpoint.txid.hex(),
                    'vout': utxo.outpoint.index,
                    'address': address,
                    'amount': utxo.output.jack_value / 100_000_000,
                    'confirmations': self.blockchain.get_height() - utxo.block_height + 1
                }
                for utxo in utxos
            ]

        if not self.wallet:
            raise Exception("Wallet not available")

        utxos = self.wallet.get_utxos(self.blockchain.utxo_set)
        current_height = self.blockchain.get_height()
        return [
            {
                'txid': utxo.tx_id.hex(),
                'vout': utxo.output_index,
                'amount': utxo.output.jack_value / 100_000_000,
                'confirmations': max(0, current_height - utxo.block_height + 1),
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
        difficulty = self.blockchain.get_difficulty()
        return {
            'blocks': self.blockchain.get_height(),
            'difficulty': difficulty,
            'networkhashps': difficulty_to_hashrate(difficulty),
            'pooledtx': self.mempool.get_stats()['count'],
        }

    # =========================================================================
    # Lotto Methods (16-2 Final)
    # =========================================================================

    def _getlottoinfo(self) -> dict:
        """로또 시스템 정보"""
        stats = self.gacha.get_stats()
        return {
            'system': 'JackpotChain Lotto (16-2 Final)',
            'pool_balance': stats['balance'] / 100_000_000,  # JACK
            'pool_balance_satoshi': stats['balance'],
            'next_jackpot': stats.get('next_jackpot', stats['balance'] * 0.5) / 100_000_000,
            'total_entries': stats.get('total_entries', 0),
            'total_payouts': stats['total_payouts'],
            'payout_count': stats['payout_count'],
            'pending_commits': stats['pending_commits'],
            'digit_count': 6,
            'digit_base': 16,
            'comparison_blocks': 'N+5, N+10, N+15, N+20, N+25, N+30',
            'claim_window': 'N+30 ~ N+80',
            'prize_table': {
                '1st (6 matches)': 'Jackpot Pool 50%',
                '2nd (5 matches)': '100,000 JACK',
                '3rd (4 matches)': '20,000 JACK',
                '4th (3 matches)': '2,000 JACK',
                '5th (2 matches)': '300 JACK',
                '6th (1 match)': '1 POT refund',
            }
        }

    def _getjackpotpool(self) -> dict:
        """잭팟 풀 상태"""
        pool_stats = self.gacha.pool.get_stats()
        return {
            'balance': pool_stats['balance'] / 100_000_000,
            'balance_satoshi': pool_stats['balance'],
            'next_jackpot': pool_stats['balance'] * 0.5 / 100_000_000,
            'next_jackpot_satoshi': int(pool_stats['balance'] * 0.5),
            'total_entries': pool_stats.get('total_entries', 0) / 100_000_000,
            'total_collected': pool_stats.get('total_fees_collected', 0) / 100_000_000,
            'snapshot_count': pool_stats.get('snapshot_count', 0),
        }

    async def _lottocommit(self, chosen_numbers: list = None) -> dict:
        """
        로또 참여 (Commit TX 생성 및 전파)

        Args:
            chosen_numbers: 6자리 숫자 배열 [0-15, 0-15, ...] (None이면 랜덤)

        Returns:
            {commit_hash, chosen_numbers, tx_id, ...}
        """
        if not self.wallet:
            raise Exception("Wallet not available")

        # 숫자 검증
        if chosen_numbers is not None:
            if len(chosen_numbers) != 6:
                raise Exception("Must choose exactly 6 numbers")
            for d in chosen_numbers:
                if not (0 <= d <= 15):
                    raise Exception("Each number must be 0-15 (hex 0x0-0xf)")

        # Commit TX 생성
        tx, pending, error = self.gacha_service.create_commit(
            wallet=self.wallet,
            utxo_set=self.blockchain.utxo_set,
            current_height=self.blockchain.get_height(),
            chosen_numbers=chosen_numbers
        )

        if error:
            raise Exception(error)

        # Mempool에 추가
        success, msg = self.mempool.add_tx(
            tx,
            self.blockchain.utxo_set,
            self.blockchain.get_height()
        )

        if not success:
            raise Exception(f"Failed to add to mempool: {msg}")

        # 네트워크 전파
        if self.node:
            await self.node.broadcast_tx(tx)

        return {
            'success': True,
            'commit_hash': pending.commit_hash.hex(),
            'chosen_numbers': pending.chosen_numbers,
            'chosen_hex': [hex(n) for n in pending.chosen_numbers],
            'tx_id': tx.get_txid().hex(),
            'comparison_blocks': f"N+5, N+10, N+15, N+20, N+25, N+30 (where N = commit block)",
            'claim_window': "N+30 ~ N+80",
            'message': "Commit created. Wait for N+30 blocks to claim result."
        }

    async def _lottoclaim(self, commit_hash: str) -> dict:
        """
        로또 결과 확정 및 보상 수령 (Claim TX 생성 및 전파)

        Args:
            commit_hash: Commit 해시 (hex)

        Returns:
            {matches, prize, payout, tx_id, ...}
        """
        if not self.wallet:
            raise Exception("Wallet not available")

        commit_hash_bytes = bytes.fromhex(commit_hash)
        current_height = self.blockchain.get_height()

        # 결과 미리 확인
        preview = self.gacha.check_result(commit_hash_bytes, current_height)
        if preview and not preview.success:
            raise Exception(preview.error)

        # Claim TX 생성
        tx, error = self.gacha_service.create_claim(
            wallet=self.wallet,
            utxo_set=self.blockchain.utxo_set,
            commit_hash=commit_hash_bytes,
            current_height=current_height
        )

        if error:
            raise Exception(error)

        # Mempool에 추가
        success, msg = self.mempool.add_tx(
            tx,
            self.blockchain.utxo_set,
            current_height
        )

        if not success:
            raise Exception(f"Failed to add to mempool: {msg}")

        # 네트워크 전파
        if self.node:
            await self.node.broadcast_tx(tx)

        # 결과 반환
        result = {
            'success': True,
            'tx_id': tx.get_txid().hex(),
            'commit_hash': commit_hash,
            'chosen_numbers': preview.chosen_numbers if preview else [],
            'result_digits': preview.result_digits if preview else [],
            'matches': preview.matches if preview else 0,
            'prize': preview.prize.name if preview else 'NONE',
            'payout_jack': preview.payout_jack / 100_000_000 if preview else 0,
            'payout_pot': preview.payout_pot / 100_000_000 if preview else 0,
            'message': "Claim TX broadcast. Reward will be credited when included in a block."
        }

        return result

    def _lottocheckresult(self, commit_hash: str) -> dict:
        """
        로또 결과 미리보기 (Claim 전)

        Args:
            commit_hash: Commit 해시 (hex)

        Returns:
            {matches, prize, expected_payout, ...}
        """
        commit_hash_bytes = bytes.fromhex(commit_hash)
        current_height = self.blockchain.get_height()

        result = self.gacha.check_result(commit_hash_bytes, current_height)

        if result is None:
            raise Exception("Commit not found")

        if not result.success:
            return {
                'success': False,
                'error': result.error,
                'message': result.error
            }

        return {
            'success': True,
            'chosen_numbers': result.chosen_numbers,
            'chosen_hex': [hex(n) for n in result.chosen_numbers] if result.chosen_numbers else [],
            'result_digits': result.result_digits,
            'result_hex': [hex(n) for n in result.result_digits] if result.result_digits else [],
            'matches': result.matches,
            'prize': result.prize.name,
            'prize_rank': result.prize.value,
            'expected_payout_jack': result.payout_jack / 100_000_000,
            'expected_payout_pot': result.payout_pot / 100_000_000,
            'can_claim': True,
        }

    def _listlottocommits(self, address: str = None) -> list:
        """
        대기 중인 Commit 목록

        Args:
            address: 특정 주소 (None이면 전체)

        Returns:
            [{commit_hash, chosen_numbers, status, ...}, ...]
        """
        commits = self.gacha.get_pending_commits(address, self.blockchain.get_height())
        current_height = self.blockchain.get_height()

        from ..gacha.commit_reveal import get_commit_status, get_comparison_heights

        result = []
        for c in commits:
            comparison_heights = get_comparison_heights(c.commit_height)
            status = get_commit_status(c, current_height)

            result.append({
                'commit_hash': c.commit_hash.hex(),
                'chosen_numbers': c.chosen_numbers,
                'chosen_hex': [hex(n) for n in c.chosen_numbers] if c.chosen_numbers else [],
                'player_address': c.player_address,
                'commit_height': c.commit_height,
                'tx_id': c.commit_tx_id.hex() if c.commit_tx_id else '',
                'pool_snapshot': c.pool_snapshot / 100_000_000,
                'status': status.value,
                'can_claim': status.value == 'claimable',
                'comparison_blocks': comparison_heights,
                'claim_deadline': c.commit_height + 80,
                'blocks_until_claimable': max(0, (c.commit_height + 30) - current_height),
                'blocks_until_expire': max(0, (c.commit_height + 80) - current_height),
            })

        return result

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
