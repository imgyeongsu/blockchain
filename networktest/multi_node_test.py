#!/usr/bin/env python3
"""
멀티 노드 로컬 테스트

3개 노드를 로컬에서 실행하고 서로 연결/동기화 테스트

Usage:
    python multi_node_test.py
    python multi_node_test.py --holepunch   # 홀펀치 테스트 포함
"""

import sys
import os
import asyncio
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jackpotchain.network.node import Node, NodeConfig
from jackpotchain.network.peer import PeerAddress
from jackpotchain.consensus.chain import Blockchain
from jackpotchain.consensus.miner import Miner


class TestNode:
    """테스트용 노드 래퍼"""

    def __init__(self, name: str, port: int, is_seed: bool = False,
                 seed_port: int = None, rendezvous_seed: str = None):
        self.name = name
        self.port = port
        self.seed_port = seed_port

        self.config = NodeConfig(
            host="0.0.0.0",
            port=port,
            user_agent=f"/{name}/",
            max_outbound=4,
            max_inbound=4,
            nat_enabled=False,  # 로컬 테스트
            is_seed_node=is_seed,
            rendezvous_port=port + 1,
            rendezvous_seeds=[rendezvous_seed] if rendezvous_seed else [],
            holepunch_enabled=bool(rendezvous_seed),
        )

        self.blockchain = Blockchain()
        self.node = Node(self.config, self.blockchain)
        self.miner = Miner(self.blockchain)

        # 콜백 설정
        self.node.set_block_callback(self._on_block)

    def _on_block(self, block, peer_info):
        source = f"from {peer_info.address.port}" if peer_info else "local"
        success, msg = self.blockchain.add_block(block)
        if success:
            print(f"  [{self.name}] Block added ({source}) → Height: {self.blockchain.get_height()}")

    async def start(self):
        print(f"[{self.name}] Starting on port {self.port}...")
        await self.node.start()

        # 시드 노드에 연결
        if self.seed_port:
            await asyncio.sleep(0.5)
            seed = PeerAddress("127.0.0.1", self.seed_port)
            success = await self.node.connect_to_peer(seed)
            print(f"  [{self.name}] Connect to seed: {'OK' if success else 'FAIL'}")

    async def stop(self):
        await self.node.stop()
        print(f"[{self.name}] Stopped")

    async def mine_block(self):
        """블록 채굴"""
        address = f"test_address_{self.name}"
        result = self.miner.mine_block(address.encode())
        if result.success:
            self.blockchain.add_block(result.block)
            await self.node.broadcast_block(result.block)
            return result.block
        return None

    def status(self) -> dict:
        stats = self.node.peer_manager.get_stats()
        return {
            "name": self.name,
            "port": self.port,
            "height": self.blockchain.get_height(),
            "peers": stats["connected"],
            "outbound": stats["outbound"],
            "inbound": stats["inbound"],
        }


async def run_basic_test():
    """기본 3노드 테스트"""
    print("\n" + "=" * 60)
    print("Basic 3-Node Test")
    print("=" * 60)

    nodes = [
        TestNode("Seed", 8333, is_seed=True),
        TestNode("NodeA", 8335, seed_port=8333),
        TestNode("NodeB", 8337, seed_port=8333),
    ]

    # 시작
    print("\n[Phase 1] Starting nodes...")
    for node in nodes:
        await node.start()
        await asyncio.sleep(0.3)

    # 연결 대기
    print("\n[Phase 2] Waiting for connections...")
    await asyncio.sleep(3)

    # 상태 확인
    print("\n[Phase 3] Status:")
    print("-" * 50)
    for node in nodes:
        s = node.status()
        print(f"  {s['name']:8} | Port {s['port']} | Height {s['height']} | "
              f"Peers {s['peers']} (out:{s['outbound']}, in:{s['inbound']})")
    print("-" * 50)

    # 블록 채굴 테스트
    print("\n[Phase 4] Mining test...")
    seed_node = nodes[0]
    block = await seed_node.mine_block()
    if block:
        print(f"  [Seed] Mined block: {block.get_hash().hex()[:16]}...")

    # 전파 대기
    await asyncio.sleep(2)

    # 동기화 확인
    print("\n[Phase 5] Sync check:")
    for node in nodes:
        s = node.status()
        print(f"  {s['name']:8} | Height: {s['height']}")

    # 정리
    print("\n[Cleanup]...")
    for node in nodes:
        await node.stop()

    print("\n[Test Complete]")


async def run_holepunch_test():
    """홀펀치 테스트"""
    print("\n" + "=" * 60)
    print("Hole Punch Test")
    print("=" * 60)
    print("NOTE: 로컬에서는 홀펀칭 불필요 (NAT 없음)")
    print("      실제 테스트는 다른 네트워크에서 수행")
    print("=" * 60)

    # 시드 노드 (랑데부 서버)
    seed = TestNode("Seed", 8333, is_seed=True)
    await seed.start()
    print(f"[Seed] 랑데부 서버 실행 중 (포트 8334)")

    # 클라이언트 노드들 (랑데부 시드 지정)
    rendezvous = "127.0.0.1:8334"
    node_a = TestNode("NodeA", 8335, rendezvous_seed=rendezvous)
    node_b = TestNode("NodeB", 8337, rendezvous_seed=rendezvous)

    await node_a.start()
    await node_b.start()

    await asyncio.sleep(3)

    # 상태
    print("\n[Status]:")
    for node in [seed, node_a, node_b]:
        s = node.status()
        nat = node.node.nat_manager
        ext = nat.external_address if nat and nat.is_mapped else None
        print(f"  {s['name']:8} | Peers: {s['peers']} | External: {ext}")

    # 정리
    print("\n[Cleanup]...")
    for node in [node_b, node_a, seed]:
        await node.stop()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--holepunch", action="store_true", help="홀펀치 테스트")
    args = parser.parse_args()

    if args.holepunch:
        await run_holepunch_test()
    else:
        await run_basic_test()


if __name__ == "__main__":
    asyncio.run(main())
