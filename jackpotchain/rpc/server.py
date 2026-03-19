"""
Step 14: RPC 서버
- JSON-RPC API
- 노드 제어
"""

import json
import asyncio
import os
from pathlib import Path
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass
from aiohttp import web

from ..consensus.chain import Blockchain
from ..consensus.difficulty import difficulty_to_hashrate, get_next_difficulty
from ..consensus.miner import create_block_template, mine_block
from ..mempool.pool import Mempool
from ..wallet.wallet import Wallet
from ..network.node import Node
from ..constants import DEFAULT_RPC_PORT, LOTTO_MIN_CLAIM_GAP, TX_VERSION_GACHA_COMMIT
from ..gacha.game import GachaGame
from ..gacha.service import GachaService, create_gacha_service
from ..script.standard import is_commit_script


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
        wallet_dir: str = None,
        host: str = "127.0.0.1",
        port: int = DEFAULT_RPC_PORT
    ):
        self.blockchain = blockchain
        self.mempool = mempool or Mempool()
        self.wallet = wallet
        self.node = node
        self.gacha = gacha or GachaGame()
        self.gacha_service = gacha_service or create_gacha_service(data_dir=data_dir)

        # 다중 지갑 지원
        self.wallet_dir = wallet_dir
        self.wallets: Dict[str, Wallet] = {}  # name -> Wallet
        self._load_all_wallets()

        # 블록 해시 조회 콜백 설정
        def get_block_hash(height: int) -> bytes:
            block = blockchain.get_block_by_height(height)
            return block.get_hash() if block else None

        self.gacha.set_block_hash_getter(get_block_hash)
        # gacha_service.game에도 설정 (create_claim에서 사용)
        if self.gacha_service and hasattr(self.gacha_service, 'game'):
            self.gacha_service.game.set_block_hash_getter(get_block_hash)

        self.host = host
        self.port = port

        self._app = web.Application()
        self._app.router.add_post('/', self._handle_request)

        # 채굴 상태
        self._mining = False
        self._mining_address: Optional[str] = None
        self._mining_task: Optional[asyncio.Task] = None
        self._mining_stats = {
            'blocks_mined': 0,
            'total_hashes': 0,
            'hashrate': 0.0,
        }

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
        self._methods['getbalances'] = self._getbalances  # JACK + POT
        self._methods['getnewaddress'] = self._getnewaddress
        self._methods['listunspent'] = self._listunspent
        self._methods['sendtoaddress'] = self._sendtoaddress

        # Network
        self._methods['getnetworkinfo'] = self._getnetworkinfo
        self._methods['getpeerinfo'] = self._getpeerinfo

        # Mining
        self._methods['getmininginfo'] = self._getmininginfo
        self._methods['startmining'] = self._startmining
        self._methods['stopmining'] = self._stopmining

        # Lotto (자동 지급 방식)
        self._methods['getlottoinfo'] = self._getlottoinfo
        self._methods['getjackpotpool'] = self._getjackpotpool
        self._methods['lottocommit'] = self._lottocommit
        self._methods['lottocheckresult'] = self._lottocheckresult
        self._methods['listlottocommits'] = self._listlottocommits

        # Legacy aliases
        self._methods['getgachainfo'] = self._getlottoinfo
        self._methods['gachacommit'] = self._lottocommit
        self._methods['listgachacommits'] = self._listlottocommits

        # Exchange (JACK -> POT)
        self._methods['exchangetopot'] = self._exchangetopot
        self._methods['getexchangeinfo'] = self._getexchangeinfo

        # Wallet Management
        self._methods['listwallets'] = self._listwallets
        self._methods['setwallet'] = self._setwallet
        self._methods['getactivewallet'] = self._getactivewallet

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

    def _getbalances(self, address: str = None) -> dict:
        """JACK + POT 잔액 조회"""
        from ..constants import ASSET_ID_POT, COIN

        current_height = self.blockchain.get_height()

        if address:
            # 특정 주소의 UTXO
            utxos = self.blockchain.utxo_set.get_utxos_for_address(address)
        elif self.wallet:
            # 지갑의 모든 주소 UTXO
            utxos = self.wallet.get_utxos(self.blockchain.utxo_set)
        else:
            raise Exception("Wallet not available")

        # mature UTXO만 필터
        mature_utxos = [u for u in utxos if u.is_mature(current_height)]

        jack_balance = 0
        pot_balance = 0

        for utxo in mature_utxos:
            jack_balance += utxo.output.jack_value
            if utxo.output.assets and ASSET_ID_POT in utxo.output.assets:
                pot_balance += utxo.output.assets[ASSET_ID_POT]

        return {
            'jack': jack_balance / COIN,
            'pot': pot_balance / COIN,
            'jack_satoshi': jack_balance,
            'pot_satoshi': pot_balance,
        }

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
                    'assets': utxo.output.assets,
                    'confirmations': self.blockchain.get_height() - utxo.block_height + 1
                }
                for utxo in utxos
            ]

        if not self.wallet:
            raise Exception("Wallet not available")

        from ..script.standard import get_address_from_script_pubkey

        utxos = self.wallet.get_utxos(self.blockchain.utxo_set)
        current_height = self.blockchain.get_height()
        return [
            {
                'txid': utxo.tx_id.hex(),
                'vout': utxo.output_index,
                'address': get_address_from_script_pubkey(utxo.output.script_pubkey),
                'amount': utxo.output.jack_value / 100_000_000,
                'assets': utxo.output.assets,
                'confirmations': max(0, current_height - utxo.block_height + 1),
            }
            for utxo in utxos
        ]

    async def _sendtoaddress(self, address: str, amount: float) -> str:
        """송금"""
        if not self.wallet:
            raise Exception("Wallet not available")

        amount_satoshi = int(amount * 100_000_000)

        # mempool 체크 함수
        is_spent = self.mempool.is_utxo_spent if self.mempool else None

        tx, error = self.wallet.create_transaction(
            self.blockchain.utxo_set,
            [(address, amount_satoshi)],
            current_height=self.blockchain.get_height(),
            is_spent_in_mempool=is_spent
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
            'mining': self._mining,
            'mining_address': self._mining_address,
            'blocks_mined': self._mining_stats['blocks_mined'],
            'hashrate': self._mining_stats['hashrate'],
        }

    def _startmining(self, address: str = None) -> dict:
        """채굴 시작"""
        if self._mining:
            return {'success': False, 'error': 'Already mining'}

        # 주소 결정
        if address:
            self._mining_address = address
        elif self.wallet:
            addresses = self.wallet.get_addresses()
            if addresses:
                self._mining_address = addresses[0]
            else:
                self._mining_address = self.wallet.generate_address()
        else:
            return {'success': False, 'error': 'No mining address provided'}

        self._mining = True
        self._mining_task = asyncio.create_task(self._mining_loop())

        return {
            'success': True,
            'message': f'Mining started',
            'address': self._mining_address
        }

    def _stopmining(self) -> dict:
        """채굴 중지"""
        if not self._mining:
            return {'success': False, 'error': 'Not mining'}

        self._mining = False
        if self._mining_task:
            self._mining_task.cancel()
            self._mining_task = None

        return {
            'success': True,
            'message': 'Mining stopped',
            'blocks_mined': self._mining_stats['blocks_mined']
        }

    async def _mining_loop(self):
        """채굴 루프"""
        print(f"[Miner] Started mining to {self._mining_address}")

        while self._mining:
            try:
                # IBD 중이면 대기
                if self.node and self.node.is_syncing:
                    await asyncio.sleep(1)
                    continue

                # 블록 템플릿 생성
                txs = self.mempool.get_txs_for_block()
                if txs:
                    print(f"[Miner] Including {len(txs)} TXs from mempool")
                tip = self.blockchain.get_tip()
                difficulty = get_next_difficulty(
                    self.blockchain.get_height(),
                    self.blockchain.get_block_by_height
                )

                template = create_block_template(
                    prev_block=tip,
                    miner_address=self._mining_address,
                    transactions=txs,
                    difficulty_target=difficulty,
                    height=self.blockchain.get_height() + 1,
                    blockchain=self.blockchain
                )

                # 비동기 채굴 (블로킹 방지)
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: mine_block(template, max_nonce=500_000)
                )

                self._mining_stats['total_hashes'] += result.hash_count
                if result.elapsed_time > 0:
                    self._mining_stats['hashrate'] = result.hash_count / result.elapsed_time

                if result.success:
                    self._mining_stats['blocks_mined'] += 1

                    # 블록 추가
                    success, msg = self.blockchain.add_block(result.block)
                    if success:
                        new_height = self.blockchain.get_height()
                        print(f"[Miner] Block {new_height} mined!")

                        # mempool에서 TX 제거
                        for tx in result.block.transactions[1:]:
                            self.mempool.remove_tx(tx.get_txid())

                        # pending commit block_height 업데이트
                        self._update_pending_commits_for_block(result.block, new_height)

                        # 네트워크 전파
                        if self.node:
                            asyncio.create_task(
                                self.node.broadcast_block(result.block)
                            )
                    else:
                        print(f"[Miner] Block rejected: {msg}")

                await asyncio.sleep(0.1)  # CPU 과부하 방지

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Miner] Error: {e}")
                await asyncio.sleep(1)

        print("[Miner] Mining stopped")

    def _update_pending_commits_for_block(self, block, height: int):
        """블록 내 commit TX의 pending commit block_height 업데이트"""
        for tx in block.transactions:
            if tx.version == TX_VERSION_GACHA_COMMIT:
                for output in tx.outputs:
                    if is_commit_script(output.script_pubkey):
                        tx_id = tx.get_txid()
                        self.gacha_service.update_commit_status(
                            commit_hash=b'\x00' * 32,
                            tx_id=tx_id,
                            block_height=height
                        )
                        break

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
            'comparison_blocks': 'N+3, N+6, N+9, N+12, N+15, N+18',
            'auto_payout': 'N+18 블록에서 자동 판정 및 지급',
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
        """잭팟 풀 상태 (UTXO 기반)"""
        # UTXO 기반 잔액 계산 (Exchange TX의 JACKPOT_POOL 출력 포함)
        pool_utxos = self.blockchain.utxo_set.get_pool_utxos()
        utxo_balance = sum(utxo.output.jack_value for utxo in pool_utxos)

        # 인메모리 pool 통계 (엔트리, 수집 등)
        pool_stats = self.gacha.pool.get_stats()

        return {
            'balance': utxo_balance / 100_000_000,
            'balance_satoshi': utxo_balance,
            'next_jackpot': utxo_balance * 50 // 100 / 100_000_000,
            'next_jackpot_satoshi': utxo_balance * 50 // 100,
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

        # Commit TX 생성 (mempool에서 사용 중인 UTXO 제외)
        tx, pending, error = self.gacha_service.create_commit(
            wallet=self.wallet,
            utxo_set=self.blockchain.utxo_set,
            current_height=self.blockchain.get_height(),
            chosen_numbers=chosen_numbers,
            is_spent_in_mempool=self.mempool.is_utxo_spent if self.mempool else None
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
            # 실패 시 pending commit 취소 (UTXO 예약 해제)
            self.gacha_service.cancel_pending_commit(pending.commit_hash)
            raise Exception(f"Failed to add to mempool: {msg}")

        # 네트워크 전파
        if self.node:
            await self.node.broadcast_tx(tx)

        return {
            'success': True,
            'chosen_numbers': pending.chosen_numbers,
            'chosen_hex': [hex(n) for n in pending.chosen_numbers],
            'tx_id': tx.get_txid().hex(),
            'comparison_blocks': "N+3, N+6, N+9, N+12, N+15, N+18 (N = commit block)",
            'message': "Commit 완료. N+18 블록에서 자동으로 당첨 판정 및 지급됩니다."
        }

    def _lottocheckresult(self, tx_id_hex: str) -> dict:
        """
        로또 결과 확인 (자동 지급이므로 조회만 가능)

        Args:
            tx_id_hex: Commit TX ID (hex)
        """
        tx_id = bytes.fromhex(tx_id_hex)
        commit_info = self.blockchain.get_commit_info(tx_id)

        if commit_info is None:
            raise Exception("Commit TX not found in blockchain")

        current_height = self.blockchain.get_height()
        from ..constants import LOTTO_MIN_CLAIM_GAP
        from ..gacha.commit_reveal import get_comparison_heights, calculate_result_digits, count_matches, determine_prize, calculate_payout

        comparison_heights = get_comparison_heights(commit_info.block_height)
        payout_block = commit_info.block_height + LOTTO_MIN_CLAIM_GAP

        if current_height < comparison_heights[-1]:
            return {
                'success': False,
                'status': 'pending',
                'commit_height': commit_info.block_height,
                'payout_block': payout_block,
                'blocks_remaining': payout_block - current_height,
                'message': f"대기 중. 블록 {payout_block}에서 자동 판정됩니다."
            }

        # 결과 계산
        block_hashes = []
        for h in comparison_heights:
            block = self.blockchain.get_block_by_height(h)
            if block:
                block_hashes.append(block.get_hash())
            else:
                return {'success': False, 'error': f"Block {h} not found"}

        result_digits = calculate_result_digits(block_hashes)
        chosen = commit_info.chosen_numbers or []
        matches = count_matches(chosen, result_digits)
        prize = determine_prize(matches)
        payout_jack, payout_pot = calculate_payout(prize, 0)

        paid = commit_info.payout_height > 0

        return {
            'success': True,
            'chosen_numbers': chosen,
            'chosen_hex': [hex(n) for n in chosen],
            'result_digits': result_digits,
            'result_hex': [hex(n) for n in result_digits],
            'matches': matches,
            'prize': prize.name,
            'prize_rank': prize.value,
            'payout_jack': payout_jack / 100_000_000,
            'payout_pot': payout_pot / 100_000_000,
            'paid': paid,
            'payout_block': payout_block,
            'status': 'paid' if paid else ('resolved' if current_height >= payout_block else 'pending'),
        }

    def _listlottocommits(self, address: str = None) -> list:
        """대기 중인 Commit 목록"""
        pending_commits = self.gacha_service.get_pending_commits(address)
        current_height = self.blockchain.get_height()
        from ..gacha.commit_reveal import get_comparison_heights
        from ..constants import LOTTO_MIN_CLAIM_GAP

        result = []
        for c in pending_commits:
            commit_height = c.block_height if c.block_height > 0 else current_height
            comparison_heights = get_comparison_heights(commit_height)
            payout_block = commit_height + LOTTO_MIN_CLAIM_GAP

            if c.block_height == 0:
                status = "pending_mine"
            elif current_height < comparison_heights[-1]:
                status = "pending"
            else:
                status = "ready"

            result.append({
                'tx_id': c.tx_id.hex() if c.tx_id else '',
                'chosen_numbers': c.chosen_numbers,
                'chosen_hex': [hex(n) for n in c.chosen_numbers] if c.chosen_numbers else [],
                'player_address': c.address,
                'commit_height': c.block_height,
                'status': status,
                'payout_block': payout_block,
                'blocks_until_payout': max(0, payout_block - current_height),
                'comparison_blocks': comparison_heights,
            })

        return result

    # =========================================================================
    # Exchange Methods (JACK -> POT)
    # =========================================================================

    def _getexchangeinfo(self) -> dict:
        """교환 정보 조회"""
        from ..constants import EXCHANGE_RATE, COIN
        return {
            'rate': f'{EXCHANGE_RATE} JACK = 1 POT',
            'jack_per_pot': EXCHANGE_RATE,
            'direction': 'JACK -> POT only (one-way)',
            'min_jack': EXCHANGE_RATE,
        }

    async def _exchangetopot(self, jack_amount: float) -> dict:
        """
        JACK -> POT 교환

        Args:
            jack_amount: 교환할 JACK 수량

        Returns:
            {pot_received, jack_burned, tx_id, ...}
        """
        if not self.wallet:
            raise Exception("Wallet not available")

        from ..asset.exchange import calculate_exchange, create_exchange_tx
        from ..constants import COIN

        jack_satoshi = round(jack_amount * COIN)

        # 교환 계산
        result = calculate_exchange(jack_satoshi)
        if not result.success:
            raise Exception(result.error)

        # UTXO 선택
        utxos = self.wallet.get_utxos(self.blockchain.utxo_set)
        current_height = self.blockchain.get_height()

        # Mature UTXO만 선택 + mempool에서 사용 중이 아닌 것
        mature_utxos = [
            u for u in utxos
            if u.is_mature(current_height)
            and not (self.mempool and self.mempool.is_utxo_spent(u.tx_id, u.output_index))
        ]

        # 충분한 JACK 수집
        selected = []
        total = 0
        for utxo in mature_utxos:
            if utxo.output.jack_value > 0:
                from ..core.transaction import TxInput
                inp = TxInput(
                    prev_tx_id=utxo.tx_id,
                    output_index=utxo.output_index,
                    script_sig=b'',
                    sequence=0xFFFFFFFF
                )
                selected.append((inp, utxo))
                total += utxo.output.jack_value
                if total >= jack_satoshi:
                    break

        if total < jack_satoshi:
            raise Exception(f"Insufficient JACK balance: {total / COIN} < {jack_amount}")

        # 주소
        addresses = self.wallet.get_addresses()
        recipient = addresses[0] if addresses else ""
        change_addr = self.wallet.get_change_address()

        # 교환 TX 생성
        tx, error = create_exchange_tx(
            inputs=selected,
            exchange_jack=jack_satoshi,
            recipient_address=recipient,
            change_address=change_addr
        )

        if error:
            raise Exception(error)

        # 서명
        from ..crypto.signature import sign
        from ..script.standard import create_p2pkh_script_sig

        for i, (inp, utxo) in enumerate(selected):
            # 주소에서 개인키 찾기
            from ..script.standard import get_address_from_script_pubkey
            addr = get_address_from_script_pubkey(utxo.output.script_pubkey)
            if addr and addr in self.wallet._addresses:
                info = self.wallet._addresses[addr]
                sig_hash = tx.get_signature_hash(i, utxo.output.script_pubkey)
                signature = sign(sig_hash, info.private_key)
                tx.inputs[i].script_sig = create_p2pkh_script_sig(signature, info.public_key)

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

        return {
            'success': True,
            'tx_id': tx.get_txid().hex(),
            'jack_exchanged': jack_amount,
            'jack_burned': result.jack_burned / COIN,
            'pot_received': result.pot_amount / COIN,
            'jack_change': result.jack_change / COIN,
        }

    # =========================================================================
    # Wallet Management
    # =========================================================================

    def _load_all_wallets(self) -> None:
        """wallet_dir의 모든 지갑 로드"""
        if not self.wallet_dir:
            # wallet_dir 없으면 기존 wallet만 사용
            if self.wallet:
                # 기존 wallet의 파일명 추출
                wallet_path = Path(self.wallet.wallet_file) if hasattr(self.wallet, 'wallet_file') and self.wallet.wallet_file else None
                if wallet_path:
                    name = wallet_path.stem
                    self.wallets[name] = self.wallet
            return

        wallet_path = Path(self.wallet_dir)
        if not wallet_path.exists():
            return

        for wf in wallet_path.glob("*.json"):
            try:
                w = Wallet(str(wf))
                name = wf.stem
                self.wallets[name] = w
                # 첫 번째 지갑을 기본 활성 지갑으로
                if self.wallet is None:
                    self.wallet = w
            except Exception:
                pass  # 로드 실패 무시

    def _listwallets(self) -> dict:
        """로드된 지갑 목록"""
        active_name = None
        if self.wallet:
            for name, w in self.wallets.items():
                if w is self.wallet:
                    active_name = name
                    break

        result = []
        for name, w in self.wallets.items():
            addrs = w.get_addresses()
            result.append({
                'name': name,
                'addresses': len(addrs),
                'active': name == active_name,
            })
        return {
            'wallets': result,
            'count': len(result),
            'active': active_name,
        }

    def _setwallet(self, name: str) -> dict:
        """활성 지갑 변경"""
        if name not in self.wallets:
            raise Exception(f"Wallet not found: {name}")

        self.wallet = self.wallets[name]
        return {
            'success': True,
            'active': name,
            'addresses': len(self.wallet.get_addresses()),
        }

    def _getactivewallet(self) -> dict:
        """현재 활성 지갑 정보"""
        if not self.wallet:
            return {'active': None}

        active_name = None
        for name, w in self.wallets.items():
            if w is self.wallet:
                active_name = name
                break

        return {
            'active': active_name,
            'addresses': self.wallet.get_addresses(),
            'watch_only': list(self.wallet._watch_only) if hasattr(self.wallet, '_watch_only') else [],
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
