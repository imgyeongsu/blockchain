"""
CLI 엔트리포인트
- 노드 실행
- 지갑 관리
- 채굴
"""

import argparse
import asyncio
import time
import sys
import os
from pathlib import Path


def get_default_data_dir() -> str:
    """기본 데이터 디렉토리 (%APPDATA%/JackpotChain/data)"""
    appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    return os.path.join(appdata, 'JackpotChain', 'data')


def get_default_wallet_file() -> str:
    """기본 지갑 파일 (%APPDATA%/JackpotChain/wallets/default.json)"""
    appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    return os.path.join(appdata, 'JackpotChain', 'wallets', 'default.json')


def main():
    parser = argparse.ArgumentParser(
        description="JackpotChain Node",
        prog="jackpotchain"
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # node 명령
    node_parser = subparsers.add_parser('node', help='Run a node')
    node_parser.add_argument('--port', type=int, default=8333, help='P2P port')
    node_parser.add_argument('--rpc-port', type=int, default=8332, help='RPC port')
    node_parser.add_argument('--data-dir', default=None, help='Data directory (default: %%APPDATA%%/JackpotChain/data)')
    node_parser.add_argument('--wallet-file', default=None, help='Wallet file path (default: %%APPDATA%%/JackpotChain/wallets/default.json)')
    node_parser.add_argument('--seed', action='append', help='Seed node (ip:port)')
    # 채굴 통합 옵션
    node_parser.add_argument('--mine', action='store_true', help='Enable mining')
    node_parser.add_argument('--address', help='Mining reward address (required if --mine)')
    # 홀펀치 / 랑데부 옵션
    node_parser.add_argument('--seed-node', action='store_true', help='Run as seed node (enables rendezvous server)')
    node_parser.add_argument('--rendezvous-port', type=int, default=8334, help='Rendezvous server port (default: 8334)')
    node_parser.add_argument('--rendezvous-seed', action='append', help='Rendezvous seed (ip:port) for hole punching')

    # wallet 명령
    wallet_parser = subparsers.add_parser('wallet', help='Wallet operations')
    wallet_parser.add_argument('action', choices=['create', 'balance', 'address', 'send'])
    wallet_parser.add_argument('--wallet-file', default=None, help='Wallet file path')
    wallet_parser.add_argument('--to', help='Recipient address (for send)')
    wallet_parser.add_argument('--amount', type=float, help='Amount (for send)')

    # mine 명령 (독립 실행용, 레거시)
    mine_parser = subparsers.add_parser('mine', help='Mining (standalone, use node --mine instead)')
    mine_parser.add_argument('--address', required=True, help='Mining reward address')
    mine_parser.add_argument('--threads', type=int, default=1, help='Mining threads')

    # tui 명령
    tui_parser = subparsers.add_parser('tui', help='Launch Terminal UI')
    tui_parser.add_argument('--rpc-host', default='127.0.0.1', help='RPC host')
    tui_parser.add_argument('--rpc-port', type=int, default=8332, help='RPC port')

    args = parser.parse_args()

    if args.command == 'node':
        run_node(args)
    elif args.command == 'wallet':
        run_wallet(args)
    elif args.command == 'mine':
        run_miner(args)
    elif args.command == 'tui':
        run_tui(args)
    else:
        # 인자 없이 실행하면 TUI 시작
        run_tui_default()


def run_node(args):
    """노드 실행 (채굴 통합 지원)"""
    from jackpotchain.consensus.chain import Blockchain
    from jackpotchain.network.node import Node, NodeConfig
    from jackpotchain.rpc.server import RPCServer
    from jackpotchain.mempool.pool import Mempool
    from jackpotchain.wallet.wallet import Wallet

    # 채굴 옵션 검증
    if args.mine and not args.address:
        print("Error: --address required when --mine is enabled")
        sys.exit(1)

    # 기본 경로 설정
    data_dir = args.data_dir or get_default_data_dir()
    wallet_file = args.wallet_file or get_default_wallet_file()

    # 지갑 디렉토리 생성
    wallet_dir = os.path.dirname(wallet_file)
    if wallet_dir:
        os.makedirs(wallet_dir, exist_ok=True)

    print(f"Starting JackpotChain node on port {args.port}...")
    print(f"Data directory: {data_dir}")
    print(f"Wallet file: {wallet_file}")

    # 초기화 (영구 저장 활성화)
    blockchain = Blockchain(data_dir=data_dir)
    mempool = Mempool()
    # 지갑 파일 로드
    wallet = Wallet(wallet_file)

    config = NodeConfig(
        port=args.port,
        is_seed_node=args.seed_node,
        rendezvous_port=args.rendezvous_port,
        rendezvous_seeds=args.rendezvous_seed or [],
    )
    node = Node(config, blockchain, mempool)

    # 시드 노드 추가
    if args.seed:
        from jackpotchain.network.peer import PeerAddress
        seeds = []
        for seed in args.seed:
            ip, port = seed.split(':')
            seeds.append((ip, int(port)))
        node.peer_manager.add_seed_nodes(seeds)

    # RPC 서버
    rpc = RPCServer(
        blockchain=blockchain,
        mempool=mempool,
        wallet=wallet,
        node=node,
        data_dir=data_dir,
        wallet_dir=wallet_dir,
        port=args.rpc_port
    )

    # 채굴 상태
    mining_stats = {
        'blocks_mined': 0,
        'total_hashes': 0,
        'start_time': time.time(),
        'is_mining': False
    }

    async def mining_task():
        """백그라운드 채굴 태스크"""
        from jackpotchain.consensus.miner import create_block_template, mine_block
        from jackpotchain.consensus.difficulty import get_next_difficulty
        from jackpotchain.script.standard import get_address_from_script_pubkey

        print(f"Mining enabled. Reward address: {args.address}")
        mining_stats['is_mining'] = True

        while True:
            try:
                # IBD 중이면 채굴 일시 중지
                if node.is_syncing:
                    await asyncio.sleep(1)
                    continue

                # 블록 템플릿 생성
                txs = mempool.get_txs_for_block()
                tip = blockchain.get_tip()
                # 난이도 조정 적용 (50블록마다)
                difficulty = get_next_difficulty(
                    blockchain.get_height(),
                    blockchain.get_block_by_height
                )

                height = blockchain.get_height() + 1
                template = create_block_template(
                    prev_block=tip,
                    miner_address=args.address,
                    transactions=txs,
                    difficulty_target=difficulty,
                    height=height,
                    blockchain=blockchain
                )
                print(f"\n[Miner] Mining block {height}...")

                # 비동기로 채굴 (작은 단위로 나눠서)
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: mine_block(template, max_nonce=1000000)
                )

                mining_stats['total_hashes'] += result.hash_count

                if result.success:
                    mining_stats['blocks_mined'] += 1

                    # Division by zero 방지
                    hashrate = result.hash_count / result.elapsed_time if result.elapsed_time > 0 else float('inf')

                    print(f"\n{'='*50}")
                    print(f"[Miner] *** BLOCK FOUND! ***")
                    print(f"  Height: {height}")
                    print(f"  Hash: {result.block.get_hash_hex()}")
                    print(f"  Nonce: {result.nonce}")
                    print(f"  Time: {result.elapsed_time:.2f}s")
                    print(f"  Hashrate: {hashrate:.0f} H/s")
                    print(f"  Total mined: {mining_stats['blocks_mined']}")
                    print(f"{'='*50}\n")

                    # 체인에 추가 (UTXO 자동 적용됨)
                    success, msg = blockchain.add_block(result.block)
                    if success:
                        new_height = blockchain.get_height()

                        # Mempool에서 포함된 TX 제거
                        for tx in result.block.transactions[1:]:  # coinbase 제외
                            mempool.remove_tx(tx.get_txid())

                        # pending commit block_height 업데이트
                        rpc._update_pending_commits_for_block(result.block, new_height)

                        # Reorg 발생 시 disconnect된 TX를 mempool에 복원
                        disconnected_txs = blockchain.pop_disconnected_txs()
                        if disconnected_txs:
                            restored = 0
                            for tx in disconnected_txs:
                                added, _ = mempool.add_tx(tx)
                                if added:
                                    restored += 1
                            print(f"[REORG] {len(disconnected_txs)}개 TX 중 {restored}개 mempool 복원")

                        # 네트워크에 브로드캐스트
                        await node.broadcast_block(result.block)
                        print(f"[Miner] Block added and broadcasted. New height: {new_height}")
                    else:
                        print(f"[Miner] Failed to add block: {msg}")

                # 잠시 대기 (CPU 과부하 방지)
                await asyncio.sleep(0.01)

            except asyncio.CancelledError:
                print("[Miner] Mining stopped")
                break
            except Exception as e:
                print(f"[Miner] Error: {e}")
                await asyncio.sleep(1)

    async def status_task():
        """상태 출력 태스크"""
        while True:
            await asyncio.sleep(30)
            elapsed = time.time() - mining_stats['start_time']
            hashrate = mining_stats['total_hashes'] / elapsed if elapsed > 0 else 0

            print(f"\n[Status] Height: {blockchain.get_height()} | "
                  f"Peers: {len(node.peer_manager.get_connected_peers())} | "
                  f"Mempool: {mempool.get_stats()['count']} txs | "
                  f"Mined: {mining_stats['blocks_mined']} blocks | "
                  f"Hashrate: {hashrate:.0f} H/s")

    def on_block_received(block, peer):
        """피어로부터 블록 수신시 처리"""
        success, msg = blockchain.add_block(block)
        if success:
            new_height = blockchain.get_height()
            print(f"[CHAIN] 피어 블록 추가 성공: height={new_height}")
            # Mempool에서 포함된 TX 제거
            for tx in block.transactions[1:]:  # coinbase 제외
                mempool.remove_tx(tx.get_txid())

            # pending commit block_height 업데이트
            rpc._update_pending_commits_for_block(block, new_height)

            # Reorg 발생 시 disconnect된 TX를 mempool에 복원
            disconnected_txs = blockchain.pop_disconnected_txs()
            if disconnected_txs:
                restored = 0
                for tx in disconnected_txs:
                    added, _ = mempool.add_tx(tx)
                    if added:
                        restored += 1
                print(f"[REORG] {len(disconnected_txs)}개 TX 중 {restored}개 mempool 복원")
        else:
            # 이미 있는 블록이면 무시 (중복 수신)
            if "already exists" not in msg.lower():
                print(f"[CHAIN] 피어 블록 추가 실패: {msg}")

    async def run():
        # 블록 수신 콜백 설정
        node.set_block_callback(on_block_received)

        await node.start()
        await rpc.start()

        print(f"Node running. RPC at http://127.0.0.1:{args.rpc_port}")

        tasks = []

        # 채굴 태스크 (옵션)
        if args.mine:
            tasks.append(asyncio.create_task(mining_task()))

        # 상태 출력 태스크
        tasks.append(asyncio.create_task(status_task()))

        print("Press Ctrl+C to stop")

        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            print("\nShutting down...")
            for task in tasks:
                task.cancel()
            await node.stop()

    asyncio.run(run())


def run_wallet(args):
    """지갑 작업"""
    from jackpotchain.wallet.wallet import Wallet
    from jackpotchain.consensus.chain import Blockchain

    wallet_file = args.wallet_file or get_default_wallet_file()

    # 지갑 디렉토리 생성
    wallet_dir = os.path.dirname(wallet_file)
    if wallet_dir:
        os.makedirs(wallet_dir, exist_ok=True)

    wallet = Wallet(wallet_file)

    if args.action == 'create':
        address = wallet.generate_address()
        print(f"New address: {address}")

    elif args.action == 'address':
        addresses = wallet.get_addresses()
        if addresses:
            print("Addresses:")
            for addr in addresses:
                print(f"  {addr}")
        else:
            print("No addresses. Use 'wallet create' first.")

    elif args.action == 'balance':
        print("Balance check requires running node. Use RPC: getbalance")

    elif args.action == 'send':
        if not args.to or not args.amount:
            print("Error: --to and --amount required for send")
            return
        print(f"Send {args.amount} JACK to {args.to}")
        print("Use RPC: sendtoaddress")


def run_tui(args):
    """TUI 실행 (RPC 옵션 지정)"""
    from jackpotchain.tui.app import run_tui as start_tui
    start_tui(host=args.rpc_host, port=args.rpc_port)


def run_tui_default():
    """TUI 기본 실행 (127.0.0.1:8332)"""
    from jackpotchain.tui.app import run_tui as start_tui
    start_tui()


def run_miner(args):
    """독립 채굴 실행 (레거시, node --mine 권장)"""
    from jackpotchain.consensus.chain import Blockchain
    from jackpotchain.consensus.miner import create_block_template, mine_block
    from jackpotchain.consensus.difficulty import get_next_difficulty
    from jackpotchain.mempool.pool import Mempool
    from jackpotchain.script.standard import get_address_from_script_pubkey

    print(f"[WARNING] Standalone mining. Use 'node --mine' for integrated mining.")
    print(f"Starting miner. Reward address: {args.address}")

    data_dir = get_default_data_dir()
    blockchain = Blockchain(data_dir=data_dir)
    mempool = Mempool()

    def mining_callback(nonce, hash_count):
        if hash_count % 100000 == 0:
            print(f"Mining... {hash_count} hashes tried")
        return True

    block_count = 0
    while True:
        try:
            txs = mempool.get_txs_for_block()
            tip = blockchain.get_tip()
            # 난이도 조정 적용
            difficulty = get_next_difficulty(
                blockchain.get_height(),
                blockchain.get_block_by_height
            )

            height = blockchain.get_height() + 1
            template = create_block_template(
                prev_block=tip,
                miner_address=args.address,
                transactions=txs,
                difficulty_target=difficulty,
                height=height,
                blockchain=blockchain
            )

            print(f"\nMining block {height}...")

            result = mine_block(template, callback=mining_callback)

            if result.success:
                block_count += 1
                print(f"\n*** Block found! ***")
                print(f"  Hash: {result.block.get_hash_hex()}")
                print(f"  Nonce: {result.nonce}")
                print(f"  Time: {result.elapsed_time:.2f}s")
                hashrate = result.hash_count / result.elapsed_time if result.elapsed_time > 0 else float('inf')
                print(f"  Hashrate: {hashrate:.2f} H/s")

                # UTXO 자동 적용됨
                blockchain.add_block(result.block)

                print(f"  Total blocks mined: {block_count}")

        except KeyboardInterrupt:
            print(f"\nMining stopped. Total blocks: {block_count}")
            break


if __name__ == '__main__':
    main()
