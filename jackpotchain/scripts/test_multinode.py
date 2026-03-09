#!/usr/bin/env python
"""
멀티노드 테스트 스크립트

3개 노드를 로컬에서 실행하여 합의와 채굴을 테스트합니다.

사용법:
    # 터미널 1: 시드 노드 (채굴)
    python -m jackpotchain.scripts.test_multinode node1

    # 터미널 2: 일반 노드
    python -m jackpotchain.scripts.test_multinode node2

    # 터미널 3: 일반 노드
    python -m jackpotchain.scripts.test_multinode node3

또는 한 터미널에서 모두 실행:
    python -m jackpotchain.scripts.test_multinode all
"""

import sys
import os
import asyncio
import time
import tempfile
import shutil
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from jackpotchain.consensus.chain import Blockchain
from jackpotchain.consensus.miner import create_block_template, mine_block
from jackpotchain.network.node import Node, NodeConfig
from jackpotchain.network.peer import PeerAddress
from jackpotchain.rpc.server import RPCServer
from jackpotchain.mempool.pool import Mempool
from jackpotchain.wallet.wallet import Wallet


# 노드 설정
NODE_CONFIGS = {
    'node1': {
        'p2p_port': 18333,
        'rpc_port': 18332,
        'mine': True,
        'seeds': [],  # 시드 노드 (첫 번째)
    },
    'node2': {
        'p2p_port': 18334,
        'rpc_port': 18335,
        'mine': False,
        'seeds': [('127.0.0.1', 18333)],
    },
    'node3': {
        'p2p_port': 18336,
        'rpc_port': 18337,
        'mine': False,
        'seeds': [('127.0.0.1', 18333)],
    },
}

# 테스트 주소 (실제 생성된 유효 주소)
TEST_MINER_ADDRESS = "X6u9TUdcTeaMuLCuSeyGCP5mxczHSdoeMZ"


async def run_single_node(node_id: str, data_dir: str = None):
    """단일 노드 실행"""
    config = NODE_CONFIGS.get(node_id)
    if not config:
        print(f"Unknown node: {node_id}")
        return

    # 임시 데이터 디렉토리
    if data_dir is None:
        data_dir = os.path.join(tempfile.gettempdir(), f"jackpotchain_{node_id}")

    os.makedirs(data_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Starting {node_id}")
    print(f"  P2P Port: {config['p2p_port']}")
    print(f"  RPC Port: {config['rpc_port']}")
    print(f"  Data Dir: {data_dir}")
    print(f"  Mining: {config['mine']}")
    print(f"{'='*60}\n")

    # 컴포넌트 초기화
    blockchain = Blockchain(data_dir=data_dir)
    mempool = Mempool()
    wallet = Wallet()

    node_config = NodeConfig(
        port=config['p2p_port'],
        data_dir=data_dir,
    )
    node = Node(node_config, blockchain)

    # 시드 노드 추가
    if config['seeds']:
        node.peer_manager.add_seed_nodes(config['seeds'])
        print(f"Added seed nodes: {config['seeds']}")

    # RPC 서버
    rpc = RPCServer(
        blockchain=blockchain,
        mempool=mempool,
        wallet=wallet,
        node=node,
        port=config['rpc_port']
    )

    # 통계
    stats = {
        'blocks_mined': 0,
        'blocks_received': 0,
        'start_time': time.time(),
    }

    # 블록 수신 콜백
    def on_block_received(block, peer):
        stats['blocks_received'] += 1
        print(f"\n[{node_id}] Received block from peer")
        print(f"  Hash: {block.get_hash().hex()[:16]}...")

        success, msg = blockchain.add_block(block)
        if success:
            # UTXO 자동 적용됨
            print(f"  Added! Height: {blockchain.get_height()}")
        else:
            print(f"  Rejected: {msg}")

    node.set_block_callback(on_block_received)

    # 채굴 태스크
    async def mining_task():
        print(f"[{node_id}] Mining started. Address: {TEST_MINER_ADDRESS[:20]}...")

        while True:
            try:
                tip = blockchain.get_tip()
                txs = mempool.get_txs_for_block()

                template = create_block_template(
                    prev_block=tip,
                    miner_address=TEST_MINER_ADDRESS,
                    transactions=txs,
                    difficulty_target=tip.header.difficulty_target
                )

                height = blockchain.get_height() + 1

                # 비동기 채굴
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: mine_block(template, max_nonce=500000)
                )

                if result.success:
                    stats['blocks_mined'] += 1

                    print(f"\n[{node_id}] *** BLOCK MINED! ***")
                    print(f"  Height: {height}")
                    print(f"  Hash: {result.block.get_hash().hex()[:16]}...")
                    print(f"  Time: {result.elapsed_time:.2f}s")
                    print(f"  Total mined: {stats['blocks_mined']}")

                    success, msg = blockchain.add_block(result.block)
                    if success:
                        # UTXO 자동 적용됨
                        # 네트워크에 브로드캐스트
                        await node.broadcast_block(result.block)
                        print(f"  Broadcasted to {len(node.peer_manager.get_connected_peers())} peers")
                    else:
                        print(f"  Add failed: {msg}")

                await asyncio.sleep(0.01)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{node_id}] Mining error: {e}")
                await asyncio.sleep(1)

    # 상태 출력 태스크
    async def status_task():
        while True:
            await asyncio.sleep(10)
            peers = node.peer_manager.get_connected_peers()
            print(f"\n[{node_id}] Status: "
                  f"Height={blockchain.get_height()} | "
                  f"Peers={len(peers)} | "
                  f"Mined={stats['blocks_mined']} | "
                  f"Received={stats['blocks_received']}")

    # 실행
    await node.start()
    await rpc.start()

    print(f"[{node_id}] Running. RPC: http://127.0.0.1:{config['rpc_port']}")
    print(f"[{node_id}] Press Ctrl+C to stop\n")

    tasks = [asyncio.create_task(status_task())]

    if config['mine']:
        tasks.append(asyncio.create_task(mining_task()))

    try:
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print(f"\n[{node_id}] Shutting down...")
        for task in tasks:
            task.cancel()
        await node.stop()


async def run_all_nodes():
    """모든 노드 동시 실행 (테스트용)"""
    print("Starting all nodes in single process...")
    print("(For real testing, run each node in separate terminal)\n")

    tasks = []
    for node_id in NODE_CONFIGS:
        tasks.append(asyncio.create_task(run_single_node(node_id)))

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\nStopping all nodes...")
        for task in tasks:
            task.cancel()


def print_usage():
    print(__doc__)
    print("\nAvailable nodes:")
    for node_id, config in NODE_CONFIGS.items():
        mine_str = "(miner)" if config['mine'] else ""
        print(f"  {node_id}: P2P={config['p2p_port']}, RPC={config['rpc_port']} {mine_str}")


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    node_id = sys.argv[1]

    if node_id == 'all':
        asyncio.run(run_all_nodes())
    elif node_id in NODE_CONFIGS:
        asyncio.run(run_single_node(node_id))
    elif node_id in ['--help', '-h', 'help']:
        print_usage()
    else:
        print(f"Unknown node: {node_id}")
        print_usage()
        sys.exit(1)


if __name__ == '__main__':
    main()
