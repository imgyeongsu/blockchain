#!/usr/bin/env python3
"""
단일 노드 실행 테스트

Usage:
    python run_node.py [port] [options]

Options:
    --seed          시드 노드 모드 (랑데부 서버 실행)
    --connect IP:PORT   특정 피어에 연결
    --no-nat        NAT 매핑 비활성화

Examples:
    python run_node.py 8333 --seed              # 시드 노드
    python run_node.py 8335 --connect 127.0.0.1:8333  # 일반 노드
"""

import sys
import os
import asyncio
import argparse

# 상위 디렉토리의 jackpotchain 패키지 import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jackpotchain.network.node import Node, NodeConfig
from jackpotchain.network.peer import PeerAddress
from jackpotchain.consensus.chain import Blockchain


def parse_args():
    parser = argparse.ArgumentParser(description="JackpotChain Network Test Node")
    parser.add_argument("port", type=int, nargs="?", default=8333, help="P2P 포트 (기본: 8333)")
    parser.add_argument("--seed", action="store_true", help="시드 노드 모드 (랑데부 서버 실행)")
    parser.add_argument("--connect", type=str, help="연결할 피어 (IP:PORT)")
    parser.add_argument("--no-nat", action="store_true", help="NAT 매핑 비활성화")
    parser.add_argument("--rendezvous", type=str, help="랑데부 시드 (IP:PORT)")
    return parser.parse_args()


async def main():
    args = parse_args()
    port = args.port

    print("=" * 60)
    print("JackpotChain Network Test Node")
    print("=" * 60)
    print(f"  Port: {port}")
    print(f"  Mode: {'SEED NODE (랑데부 서버)' if args.seed else '일반 노드'}")
    print(f"  NAT:  {'비활성' if args.no_nat else '활성'}")
    print("=" * 60)

    # 랑데부 시드 설정
    rendezvous_seeds = []
    if args.rendezvous:
        rendezvous_seeds.append(args.rendezvous)

    # 설정
    config = NodeConfig(
        host="0.0.0.0",
        port=port,
        user_agent=f"/NetworkTest:{port}/",
        max_outbound=4,
        max_inbound=4,
        nat_enabled=not args.no_nat,
        is_seed_node=args.seed,
        rendezvous_port=port + 1,  # 시드 노드면 랑데부 포트
        rendezvous_seeds=rendezvous_seeds,
        holepunch_enabled=len(rendezvous_seeds) > 0,
    )

    # 블록체인 (테스트용 인메모리)
    blockchain = Blockchain()

    # 노드 생성
    node = Node(config, blockchain)

    # 블록 수신 콜백
    def on_block(block, peer_info):
        print(f"\n[Block] {block.get_hash().hex()[:16]}... from {peer_info.address}")
        blockchain.add_block(block)
        print(f"  Height: {blockchain.get_height()}")

    node.set_block_callback(on_block)

    # 노드 시작
    print(f"\n[Starting]...")
    await node.start()

    # 초기 연결
    if args.connect:
        ip, port_str = args.connect.split(":")
        seed = PeerAddress(ip, int(port_str))
        print(f"\n[Connecting] to {seed}...")
        success = await node.connect_to_peer(seed)
        print(f"  Result: {'성공' if success else '실패'}")

    # 상태 출력 루프
    print("\n[Running] Ctrl+C to stop")
    print("-" * 60)

    try:
        while True:
            await asyncio.sleep(30)
            stats = node.peer_manager.get_stats()

            # NAT 상태
            nat_status = "N/A"
            if node.nat_manager and node.nat_manager.is_mapped:
                ext = node.nat_manager.external_address
                nat_status = f"{ext[0]}:{ext[1]}"

            print(f"\n[Status] Height: {blockchain.get_height()} | "
                  f"Peers: {stats['connected']} | "
                  f"External: {nat_status}")

            # 연결된 피어 목록
            for peer in node.peer_manager.get_connected_peers():
                direction = "IN" if peer.is_inbound else "OUT"
                print(f"  [{direction}] {peer.address.ip}:{peer.address.port} "
                      f"({peer.state.value}, h={peer.height})")

    except KeyboardInterrupt:
        print("\n\n[Stopping]...")
    finally:
        await node.stop()
        print("[Stopped]")


if __name__ == "__main__":
    asyncio.run(main())
