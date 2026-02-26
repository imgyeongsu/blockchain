"""
네트워크 모듈 테스트
- P2P 통신
- 멀티 노드 동기화
"""

import pytest
import asyncio
from jackpotchain.network.node import Node, NodeConfig
from jackpotchain.network.peer import PeerManager, PeerAddress
from jackpotchain.network.protocol import (
    MessageType, MessageHeader, InvType,
    VersionMessage, InvMessage, InvItem, GetDataMessage,
    create_message, parse_message
)
from jackpotchain.consensus.chain import Blockchain
from jackpotchain.core.block import create_genesis_block


class TestMessageProtocol:
    """메시지 프로토콜 테스트"""

    def test_version_message_serialization(self):
        """Version 메시지 직렬화/역직렬화"""
        import time

        msg = VersionMessage(
            version=70015,
            services=1,
            timestamp=int(time.time()),
            start_height=100,
            user_agent=b'/JackpotChain:0.1.0/'
        )

        serialized = msg.serialize()
        assert len(serialized) > 0

        # 전체 메시지 생성
        full_msg = create_message(MessageType.VERSION, serialized)
        assert len(full_msg) >= 24 + len(serialized)

        # 파싱
        header, payload = parse_message(full_msg)
        assert header is not None
        assert header.command[:7] == b'version'

    def test_message_header(self):
        """메시지 헤더 직렬화"""
        from jackpotchain.constants import NETWORK_MAGIC

        header = MessageHeader(
            magic=NETWORK_MAGIC,
            command=MessageType.PING.value,
            length=8,
            checksum=b'\x00\x00\x00\x00'
        )

        serialized = header.serialize()
        assert len(serialized) == 24

        # 역직렬화
        parsed = MessageHeader.deserialize(serialized)
        assert parsed.magic == NETWORK_MAGIC
        assert parsed.length == 8

    def test_inv_message(self):
        """Inventory 메시지"""
        inv = InvMessage(items=[
            InvItem(InvType.BLOCK, b'\x01' * 32),
            InvItem(InvType.TX, b'\x02' * 32)
        ])

        serialized = inv.serialize()
        assert len(serialized) > 0

        # 역직렬화
        parsed = InvMessage.deserialize(serialized)
        assert len(parsed.items) == 2
        assert parsed.items[0].inv_type == InvType.BLOCK
        assert parsed.items[1].inv_type == InvType.TX

    def test_inv_item(self):
        """인벤토리 아이템"""
        item = InvItem(InvType.BLOCK, b'\xAB' * 32)

        serialized = item.serialize()
        assert len(serialized) == 36  # 4 + 32

        parsed, _ = InvItem.deserialize(serialized)
        assert parsed.inv_type == InvType.BLOCK
        assert parsed.hash == b'\xAB' * 32

    def test_getdata_message(self):
        """GetData 메시지"""
        getdata = GetDataMessage(items=[
            InvItem(InvType.BLOCK, b'\x01' * 32)
        ])

        serialized = getdata.serialize()

        # 역직렬화
        parsed = GetDataMessage.deserialize(serialized)
        assert len(parsed.items) == 1


class TestPeerManager:
    """피어 관리자 테스트"""

    def test_peer_address(self):
        """피어 주소"""
        addr = PeerAddress(ip="127.0.0.1", port=8333)
        assert str(addr) == "127.0.0.1:8333"

    def test_add_seed_nodes(self):
        """시드 노드 추가"""
        manager = PeerManager()
        manager.add_seed_nodes([
            ("192.168.1.1", 8333),
            ("192.168.1.2", 8333)
        ])

        # 알려진 피어 목록에 추가됨 (private 속성 직접 접근)
        assert len(manager._known_addresses) >= 2

    def test_peer_stats(self):
        """피어 통계"""
        manager = PeerManager()
        stats = manager.get_stats()

        assert 'connected' in stats
        assert 'inbound' in stats
        assert 'outbound' in stats


class TestNode:
    """노드 테스트"""

    def test_node_creation(self):
        """노드 생성"""
        blockchain = Blockchain()
        config = NodeConfig(port=18333)  # 테스트넷 포트

        node = Node(config, blockchain)

        assert node.config.port == 18333
        assert node.blockchain is blockchain

    def test_node_config(self):
        """노드 설정"""
        config = NodeConfig(
            host="0.0.0.0",
            port=8333,
            max_outbound=8,
            max_inbound=4
        )

        assert config.port == 8333
        assert config.max_outbound == 8
        assert config.max_inbound == 4


class TestMultiNodeSimulation:
    """멀티 노드 시뮬레이션 테스트"""

    def test_two_nodes_handshake_simulation(self):
        """두 노드 핸드셰이크 시뮬레이션"""
        import time

        # Node A: Version 메시지 생성
        node_a_version = VersionMessage(
            version=70015,
            services=1,
            timestamp=int(time.time()),
            start_height=0,
            user_agent=b'/NodeA/'
        )

        # Node B: Version 메시지 생성
        node_b_version = VersionMessage(
            version=70015,
            services=1,
            timestamp=int(time.time()),
            start_height=0,
            user_agent=b'/NodeB/'
        )

        # 메시지 생성
        msg_a = create_message(MessageType.VERSION, node_a_version.serialize())
        msg_b = create_message(MessageType.VERSION, node_b_version.serialize())

        # 파싱
        header_a, payload_a = parse_message(msg_a)
        header_b, payload_b = parse_message(msg_b)

        assert header_a is not None
        assert header_b is not None
        assert header_a.command[:7] == b'version'
        assert header_b.command[:7] == b'version'

        # Version 메시지 역직렬화
        parsed_a = VersionMessage.deserialize(payload_a)
        parsed_b = VersionMessage.deserialize(payload_b)

        assert parsed_a.user_agent == b'/NodeA/'
        assert parsed_b.user_agent == b'/NodeB/'

    def test_block_propagation_simulation(self):
        """블록 전파 시뮬레이션"""
        genesis = create_genesis_block()

        # Node A: 새 블록 발견 → INV 전송
        inv = InvMessage(items=[
            InvItem(InvType.BLOCK, genesis.get_hash())
        ])
        inv_msg = create_message(MessageType.INV, inv.serialize())

        # Node B: INV 수신 → GETDATA 전송
        getdata = GetDataMessage(items=[
            InvItem(InvType.BLOCK, genesis.get_hash())
        ])
        getdata_msg = create_message(MessageType.GETDATA, getdata.serialize())

        # 모든 메시지 파싱 가능 확인
        header1, _ = parse_message(inv_msg)
        header2, _ = parse_message(getdata_msg)

        assert header1 is not None
        assert header2 is not None

    def test_chain_sync_simulation(self):
        """체인 동기화 시뮬레이션"""
        # 노드 A: 체인 생성
        chain_a = Blockchain()

        # 노드 B: 체인 생성
        chain_b = Blockchain()

        # 두 체인이 동일 제네시스 보유 확인
        assert chain_a.get_tip_hash() == chain_b.get_tip_hash()
        assert chain_a.get_height() == chain_b.get_height()

    def test_inventory_types(self):
        """인벤토리 타입"""
        assert InvType.TX.value == 1
        assert InvType.BLOCK.value == 2
        assert InvType.ERROR.value == 0


class TestNetworkIntegration:
    """네트워크 통합 테스트"""

    def test_blockchain_with_genesis(self):
        """제네시스 블록 체인"""
        blockchain = Blockchain()

        # 제네시스 블록 확인
        genesis = blockchain.get_block_by_height(0)
        assert genesis is not None
        assert genesis.transactions[0].is_coinbase()

    def test_mempool_integration(self):
        """멤풀 통합"""
        from jackpotchain.mempool.pool import Mempool

        mempool = Mempool()
        stats = mempool.get_stats()

        assert stats['count'] == 0
        assert stats['size'] == 0

    def test_full_node_components(self):
        """전체 노드 컴포넌트 통합"""
        from jackpotchain.mempool.pool import Mempool
        from jackpotchain.wallet.wallet import Wallet
        from jackpotchain.gacha.game import GachaGame

        # 모든 컴포넌트 인스턴스화
        blockchain = Blockchain()
        mempool = Mempool()
        wallet = Wallet()
        gacha = GachaGame()

        config = NodeConfig(port=18333)
        node = Node(config, blockchain)

        # 컴포넌트 연결 확인
        assert node.blockchain.get_height() >= 0
        assert mempool.get_stats()['count'] == 0
        assert gacha.pool.balance >= 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
