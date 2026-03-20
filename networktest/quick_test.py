#!/usr/bin/env python3
"""
빠른 연결 테스트

2개 노드를 실행하고 3초간 연결 테스트 후 종료

Usage:
    python quick_test.py
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jackpotchain.network.node import Node, NodeConfig
from jackpotchain.network.peer import PeerAddress
from jackpotchain.consensus.chain import Blockchain


async def main():
    print("Quick Connection Test")
    print("-" * 40)

    # 노드 A (서버)
    config_a = NodeConfig(port=18333, nat_enabled=False, is_seed_node=True)
    node_a = Node(config_a, Blockchain())

    # 노드 B (클라이언트)
    config_b = NodeConfig(port=18335, nat_enabled=False)
    node_b = Node(config_b, Blockchain())

    print("[1] Starting Node A (port 18333)...")
    await node_a.start()

    print("[2] Starting Node B (port 18335)...")
    await node_b.start()

    print("[3] Connecting B -> A...")
    success = await node_b.connect_to_peer(PeerAddress("127.0.0.1", 18333))
    print(f"    Result: {'SUCCESS' if success else 'FAILED'}")

    print("[4] Waiting 2s for handshake...")
    await asyncio.sleep(2)

    # 결과
    stats_a = node_a.peer_manager.get_stats()
    stats_b = node_b.peer_manager.get_stats()

    print("\n[Result]")
    print(f"  Node A: {stats_a['connected']} peers (in:{stats_a['inbound']})")
    print(f"  Node B: {stats_b['connected']} peers (out:{stats_b['outbound']})")

    # 정리
    print("\n[5] Stopping...")
    await node_b.stop()
    await node_a.stop()

    # 최종 판정
    if stats_a['connected'] >= 1 and stats_b['connected'] >= 1:
        print("\n✓ TEST PASSED")
    else:
        print("\n✗ TEST FAILED")


if __name__ == "__main__":
    asyncio.run(main())
