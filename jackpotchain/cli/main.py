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
from pathlib import Path


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
    node_parser.add_argument('--data-dir', default='./data', help='Data directory')
    node_parser.add_argument('--seed', action='append', help='Seed node (ip:port)')
    # 채굴 통합 옵션
    node_parser.add_argument('--mine', action='store_true', help='Enable mining')
    node_parser.add_argument('--address', help='Mining reward address (required if --mine)')

    # wallet 명령
    wallet_parser = subparsers.add_parser('wallet', help='Wallet operations')
    wallet_parser.add_argument('action', choices=['create', 'balance', 'address', 'send'])
    wallet_parser.add_argument('--wallet-file', default='./wallet.json')
    wallet_parser.add_argument('--to', help='Recipient address (for send)')
    wallet_parser.add_argument('--amount', type=float, help='Amount (for send)')

    # mine 명령 (독립 실행용, 레거시)
    mine_parser = subparsers.add_parser('mine', help='Mining (standalone, use node --mine instead)')
    mine_parser.add_argument('--address', required=True, help='Mining reward address')
    mine_parser.add_argument('--threads', type=int, default=1, help='Mining threads')

    args = parser.parse_args()

    if args.command == 'node':
        run_node(args)
    elif args.command == 'wallet':
        run_wallet(args)
    elif args.command == 'mine':
        run_miner(args)
    else:
        parser.print_help()


def run_node(args):
    """노드 실행 (채굴 통합 지원)"""
    from ..consensus.chain import Blockchain
    from ..network.node import Node, NodeConfig
    from ..rpc.server import RPCServer
    from ..mempool.pool import Mempool
    from ..wallet.wallet import Wallet

    # 채굴 옵션 검증
    if args.mine and not args.address:
        print("Error: --address required when --mine is enabled")
        sys.exit(1)

    print(f"Starting JackpotChain node on port {args.port}...")
    print(f"Data directory: {args.data_dir}")

    # 초기화 (영구 저장 활성화)
    blockchain = Blockchain(data_dir=args.data_dir)
    mempool = Mempool()
    wallet = Wallet()

    config = NodeConfig(
        port=args.port
    )
    node = Node(config, blockchain)

    # 시드 노드 추가
    if args.seed:
        from ..network.peer import PeerAddress
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
        from ..consensus.miner import create_block_template, mine_block

        print(f"Mining enabled. Reward address: {args.address}")
        mining_stats['is_mining'] = True

        while True:
            try:
                # 블록 템플릿 생성
                txs = mempool.get_txs_for_block()
                tip = blockchain.get_tip()
                difficulty = tip.header.difficulty_target

                template = create_block_template(
                    prev_block=tip,
                    miner_address=args.address,
                    transactions=txs,
                    difficulty_target=difficulty
                )

                height = blockchain.get_height() + 1
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

                    # 체인에 추가
                    success, msg = blockchain.add_block(result.block)
                    if success:
                        # UTXO 업데이트
                        for tx in result.block.transactions:
                            blockchain.utxo_set.apply_transaction(tx, blockchain.get_height())

                        # 네트워크에 브로드캐스트
                        await node.broadcast_block(result.block)
                        print(f"[Miner] Block added and broadcasted. New height: {blockchain.get_height()}")
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

    async def run():
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
    from ..wallet.wallet import Wallet
    from ..consensus.chain import Blockchain

    wallet = Wallet(args.wallet_file)

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


def run_miner(args):
    """독립 채굴 실행 (레거시, node --mine 권장)"""
    from ..consensus.chain import Blockchain
    from ..consensus.miner import create_block_template, mine_block
    from ..mempool.pool import Mempool

    print(f"[WARNING] Standalone mining. Use 'node --mine' for integrated mining.")
    print(f"Starting miner. Reward address: {args.address}")

    blockchain = Blockchain()
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
            difficulty = tip.header.difficulty_target

            template = create_block_template(
                prev_block=tip,
                miner_address=args.address,
                transactions=txs,
                difficulty_target=difficulty
            )

            print(f"\nMining block {blockchain.get_height() + 1}...")

            result = mine_block(template, callback=mining_callback)

            if result.success:
                block_count += 1
                print(f"\n*** Block found! ***")
                print(f"  Hash: {result.block.get_hash_hex()}")
                print(f"  Nonce: {result.nonce}")
                print(f"  Time: {result.elapsed_time:.2f}s")
                hashrate = result.hash_count / result.elapsed_time if result.elapsed_time > 0 else float('inf')
                print(f"  Hashrate: {hashrate:.2f} H/s")

                blockchain.add_block(result.block)

                for tx in result.block.transactions:
                    blockchain.utxo_set.apply_transaction(tx, blockchain.get_height())

                print(f"  Total blocks mined: {block_count}")

        except KeyboardInterrupt:
            print(f"\nMining stopped. Total blocks: {block_count}")
            break


if __name__ == '__main__':
    main()
