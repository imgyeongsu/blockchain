"""
CLI 엔트리포인트
- 노드 실행
- 지갑 관리
- 채굴
"""

import argparse
import asyncio
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

    # wallet 명령
    wallet_parser = subparsers.add_parser('wallet', help='Wallet operations')
    wallet_parser.add_argument('action', choices=['create', 'balance', 'address', 'send'])
    wallet_parser.add_argument('--wallet-file', default='./wallet.json')
    wallet_parser.add_argument('--to', help='Recipient address (for send)')
    wallet_parser.add_argument('--amount', type=float, help='Amount (for send)')

    # mine 명령
    mine_parser = subparsers.add_parser('mine', help='Mining')
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
    """노드 실행"""
    from ..consensus.chain import Blockchain
    from ..network.node import Node, NodeConfig
    from ..rpc.server import RPCServer
    from ..mempool.pool import Mempool
    from ..wallet.wallet import Wallet

    print(f"Starting JackpotChain node on port {args.port}...")

    # 초기화
    blockchain = Blockchain()
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

    async def run():
        await node.start()
        await rpc.start()
        print(f"Node running. RPC at http://127.0.0.1:{args.rpc_port}")
        print("Press Ctrl+C to stop")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
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
        # 블록체인 필요 (간단히 로컬에서)
        print("Balance check requires running node. Use RPC: getbalance")

    elif args.action == 'send':
        if not args.to or not args.amount:
            print("Error: --to and --amount required for send")
            return
        print(f"Send {args.amount} JACK to {args.to}")
        print("Use RPC: sendtoaddress")


def run_miner(args):
    """채굴 실행"""
    from ..consensus.chain import Blockchain
    from ..consensus.miner import create_block_template, mine_block
    from ..mempool.pool import Mempool

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
            # 블록 템플릿 생성
            txs = mempool.get_txs_for_block()
            tip = blockchain.get_tip()

            from ..consensus.difficulty import get_next_difficulty
            difficulty = tip.header.difficulty_target  # 간단히 이전 난이도 사용

            template = create_block_template(
                prev_block=tip,
                miner_address=args.address,
                transactions=txs,
                difficulty_target=difficulty
            )

            print(f"\nMining block {blockchain.get_height() + 1}...")

            # 채굴
            result = mine_block(template, callback=mining_callback)

            if result.success:
                block_count += 1
                print(f"\n*** Block found! ***")
                print(f"  Hash: {result.block.get_hash_hex()}")
                print(f"  Nonce: {result.nonce}")
                print(f"  Time: {result.elapsed_time:.2f}s")
                print(f"  Hashrate: {result.hash_count / result.elapsed_time:.2f} H/s")

                # 체인에 추가
                blockchain.add_block(result.block)

                # UTXO 업데이트
                for tx in result.block.transactions:
                    blockchain.utxo_set.apply_transaction(tx, blockchain.get_height())

                print(f"  Total blocks mined: {block_count}")

        except KeyboardInterrupt:
            print(f"\nMining stopped. Total blocks: {block_count}")
            break


if __name__ == '__main__':
    main()
