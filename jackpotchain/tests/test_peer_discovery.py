"""
피어 발견 흐름 검증 테스트

환경 구축 없이 코드 로직만으로 검증:
1. GETADDR/ADDR 주소 교환이 캐시에 저장되는가?
2. 캐시가 충분하면 하드코딩 시드를 건너뛰는가?
3. 시드 노드가 자기가 아는 피어 주소를 제대로 응답하는가?
4. 죽은 피어만 캐시에 있을 때 교착 빠지는가?
"""

import json
import time
import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from jackpotchain.network.peer import PeerManager, PeerAddress, PeerState, PeerInfo
from jackpotchain.network.discovery import PeerDiscovery, PeerCache, HARDCODED_SEEDS
from jackpotchain.network.protocol import (
    MessageType, AddrMessage, NetAddress,
)


# =============================================================================
# 1. PeerCache 단위 테스트
# =============================================================================

class TestPeerCache:
    """peers.json 캐시 저장/로드 검증"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_save_and_load(self):
        """캐시에 저장한 피어가 로드 시 복원되는가"""
        cache = PeerCache(self.tmpdir)
        cache.add("1.2.3.4", 9333, services=1, timestamp=int(time.time()))
        cache.add("5.6.7.8", 9333, services=1, timestamp=int(time.time()))
        cache.save()

        # 새 캐시 인스턴스로 로드
        cache2 = PeerCache(self.tmpdir)
        loaded = cache2.load()

        assert loaded == 2
        peers = cache2.get_peers(count=10)
        ips = {p.ip for p in peers}
        assert "1.2.3.4" in ips
        assert "5.6.7.8" in ips

    def test_duplicate_update(self):
        """같은 IP:포트를 다시 추가하면 업데이트 되는가 (중복 안 생기는가)"""
        cache = PeerCache(self.tmpdir)
        cache.add("1.2.3.4", 9333, timestamp=100)
        cache.add("1.2.3.4", 9333, timestamp=200)

        peers = cache.get_peers(count=10)
        assert len(peers) == 1

    def test_max_peers_limit(self):
        """캐시 최대 개수(2000) 초과 시 오래된 것부터 버리는가"""
        cache = PeerCache(self.tmpdir)
        cache._max_peers = 10  # 테스트용 축소

        now = int(time.time())
        for i in range(20):
            cache.add(f"10.0.0.{i}", 9333, timestamp=now - 20 + i)

        cache.save()

        cache2 = PeerCache(self.tmpdir)
        cache2._max_peers = 10
        loaded = cache2.load()
        assert loaded == 10  # 최대 10개만 저장됨

        # 최근 timestamp가 높은 것이 남아야 함
        peers = cache2.get_peers(count=20)
        ips = {p.ip for p in peers}
        assert "10.0.0.19" in ips  # 가장 최근
        assert "10.0.0.0" not in ips  # 가장 오래됨


# =============================================================================
# 2. PeerDiscovery 흐름 테스트
# =============================================================================

class TestPeerDiscovery:
    """피어 발견 흐름 검증"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_empty_cache_falls_back_to_seeds(self):
        """캐시 비었을 때 하드코딩 시드로 fallback 하는가"""
        discovery = PeerDiscovery(self.tmpdir)

        # DNS는 실패한다고 가정 (도메인 없음)
        with patch.object(discovery, '_resolve_dns', return_value=[]):
            peers = discovery.initialize()

        # 하드코딩 시드가 반환되어야 함
        ips = {p.ip for p in peers}
        for seed_ip, _ in HARDCODED_SEEDS:
            assert seed_ip in ips

    def test_cached_good_peers_skip_seeds(self):
        """캐시에 최근 성공 피어 10개 이상 있으면 시드 조회를 건너뛰는가"""
        cache = PeerCache(self.tmpdir)
        for i in range(15):
            cache.add(f"50.0.1.{i+10}", 9333, timestamp=int(time.time()))
            cache.mark_success(f"50.0.1.{i+10}", 9333)  # 성공 기록 필수
        cache.save()

        discovery = PeerDiscovery(self.tmpdir)
        with patch.object(discovery, '_query_seeds') as mock_seeds:
            peers = discovery.initialize()

        # 성공 피어가 충분하므로 시드 조회 안 함
        mock_seeds.assert_not_called()
        assert len(peers) > 0

    def test_addr_message_adds_to_cache(self):
        """ADDR 메시지로 받은 주소가 캐시에 추가되는가"""
        discovery = PeerDiscovery(self.tmpdir)

        new_addrs = [
            PeerAddress(ip="8.8.8.8", port=9333, services=1, timestamp=int(time.time())),
            PeerAddress(ip="52.1.1.1", port=9333, services=1, timestamp=int(time.time())),
        ]
        discovery.add_addresses(new_addrs)

        # 캐시에 저장되었는지
        assert len(discovery.cache) == 2

        # 저장 후 다시 로드해도 남는지
        discovery.save()
        discovery2 = PeerDiscovery(self.tmpdir)
        discovery2.cache.load()
        assert len(discovery2.cache) == 2

    def test_get_addr_to_send_returns_recent(self):
        """GETADDR 응답에 최근 3일 이내 피어만 포함되는가"""
        discovery = PeerDiscovery(self.tmpdir)

        now = int(time.time())
        # 최근 피어
        discovery.add_addresses([
            PeerAddress(ip="1.0.0.1", port=9333, timestamp=now),
        ])
        # 오래된 피어 (4일 전)
        discovery.cache.add("2.0.0.1", 9333, timestamp=now - 4 * 86400)

        result = discovery.get_addr_to_send(count=100)
        ips = {p.ip for p in result}

        assert "1.0.0.1" in ips
        assert "2.0.0.1" not in ips  # 3일 초과 → 제외

    def test_dead_cache_no_deadlock(self):
        """캐시에 죽은 피어만 10개+ 있을 때 시드도 조회하는가 (교착 방지)"""
        cache = PeerCache(self.tmpdir)
        for i in range(15):
            # 오래전에 본 피어, 연결 실패 이력 (success=0)
            cache.add(f"10.0.0.{i}", 9333, timestamp=int(time.time()) - 86400 * 10)
            cache.mark_attempt(f"10.0.0.{i}", 9333)  # 시도만 있고 성공 없음
        cache.save()

        discovery = PeerDiscovery(self.tmpdir, allow_private_ip=True)

        with patch.object(discovery, '_query_seeds', wraps=discovery._query_seeds) as mock_seeds:
            with patch.object(discovery, '_resolve_dns', return_value=[]):
                peers = discovery.initialize()

        # 성공한 피어가 없으므로 시드 조회가 호출되어야 함
        mock_seeds.assert_called_once()

        # 시드가 결과에 포함되어야 함
        peer_ips = {p.ip for p in peers}
        assert "54.116.13.57" in peer_ips


# =============================================================================
# 3. Node의 GETADDR/ADDR 핸들링 (단위 테스트)
# =============================================================================

class TestNodeAddrExchange:
    """Node 레벨에서 주소 교환 흐름 검증"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_handle_addr_saves_to_discovery(self):
        """_handle_addr로 받은 주소가 discovery + peer_manager에 저장되는가"""
        from jackpotchain.network.node import Node, NodeConfig

        config = NodeConfig(port=19333, data_dir=self.tmpdir, allow_private_ip=True)
        node = Node(config)

        # ADDR 메시지 생성: 피어 2개 주소
        net_addrs = []
        for ip in ["3.3.3.3", "4.4.4.4"]:
            net_addrs.append(NetAddress.from_ipv4(ip, 9333, timestamp=int(time.time())))

        addr_msg = AddrMessage(addresses=net_addrs)
        payload = addr_msg.serialize()

        # _handle_addr 호출
        sender = PeerAddress(ip="1.1.1.1", port=9333)
        asyncio.get_event_loop().run_until_complete(
            node._handle_addr(sender, payload)
        )

        # discovery 캐시에 추가되었는가
        assert len(node.discovery.cache) >= 2

        # peer_manager._known_addresses에도 추가되었는가
        known_ips = {a.ip for a in node.peer_manager._known_addresses}
        assert "3.3.3.3" in known_ips
        assert "4.4.4.4" in known_ips

    def test_handle_getaddr_returns_known_peers(self):
        """_handle_getaddr가 알고 있는 피어 주소를 응답하는가"""
        from jackpotchain.network.node import Node, NodeConfig

        config = NodeConfig(port=19334, data_dir=self.tmpdir)
        node = Node(config)

        # discovery에 피어 추가
        now = int(time.time())
        node.discovery.add_addresses([
            PeerAddress(ip="5.5.5.5", port=9333, timestamp=now),
            PeerAddress(ip="6.6.6.6", port=9333, timestamp=now),
        ])

        # _send_message를 mock
        sent_messages = []

        async def mock_send(addr, msg_type, payload):
            sent_messages.append((addr, msg_type, payload))

        node._send_message = mock_send

        # _handle_getaddr 호출
        requester = PeerAddress(ip="9.9.9.9", port=9333)
        # 커넥션도 mock (send에 필요)
        node._connections[requester] = (MagicMock(), MagicMock())

        asyncio.get_event_loop().run_until_complete(
            node._handle_getaddr(requester)
        )

        # ADDR 메시지가 전송되었는가
        assert len(sent_messages) == 1
        addr, msg_type, payload = sent_messages[0]
        assert msg_type == MessageType.ADDR

        # payload 역직렬화하여 주소 확인
        addr_msg = AddrMessage.deserialize(payload)
        response_ips = {na.to_ipv4() for na in addr_msg.addresses}
        assert "5.5.5.5" in response_ips
        assert "6.6.6.6" in response_ips

    def test_getaddr_spam_protection(self):
        """같은 피어에서 24시간 내 재요청하면 무시하는가"""
        from jackpotchain.network.node import Node, NodeConfig

        config = NodeConfig(port=19335, data_dir=self.tmpdir)
        node = Node(config)

        now = int(time.time())
        node.discovery.add_addresses([
            PeerAddress(ip="5.5.5.5", port=9333, timestamp=now),
        ])

        sent_messages = []

        async def mock_send(addr, msg_type, payload):
            sent_messages.append((addr, msg_type, payload))

        node._send_message = mock_send
        requester = PeerAddress(ip="9.9.9.9", port=9333)
        node._connections[requester] = (MagicMock(), MagicMock())

        loop = asyncio.get_event_loop()

        # 첫 번째 요청 → 응답
        loop.run_until_complete(node._handle_getaddr(requester))
        assert len(sent_messages) == 1

        # 두 번째 요청 → 무시 (24시간 제한)
        loop.run_until_complete(node._handle_getaddr(requester))
        assert len(sent_messages) == 1  # 여전히 1개

    def test_verack_triggers_getaddr(self):
        """핸드셰이크 완료 후 자동으로 GETADDR이 전송되는가"""
        from jackpotchain.network.node import Node, NodeConfig

        config = NodeConfig(port=19336, data_dir=self.tmpdir)
        node = Node(config)

        sent_messages = []

        async def mock_send(addr, msg_type, payload):
            sent_messages.append((addr, msg_type, payload))

        node._send_message = mock_send

        peer_addr = PeerAddress(ip="7.7.7.7", port=9333)
        # 피어를 HANDSHAKING 상태로 추가
        node.peer_manager.add_peer(peer_addr, is_inbound=False)
        node.peer_manager.update_peer_state(peer_addr, PeerState.HANDSHAKING)
        node._connections[peer_addr] = (MagicMock(), MagicMock())

        # VERACK 처리
        loop = asyncio.get_event_loop()
        loop.run_until_complete(node._handle_verack(peer_addr))

        # GETADDR가 전송되었는가
        getaddr_sent = any(
            msg_type == MessageType.GETADDR
            for _, msg_type, _ in sent_messages
        )
        assert getaddr_sent, "VERACK 후 GETADDR가 자동 전송되어야 함"


# =============================================================================
# 4. PeerManager 연결 선택 로직
# =============================================================================

class TestPeerManagerSelection:
    """피어 매니저가 캐시된 주소로 연결을 시도하는가"""

    def test_known_addresses_used_for_connection(self):
        """add_peer_address로 추가한 주소가 get_peers_to_connect에 나오는가"""
        pm = PeerManager()

        # ADDR로 받은 피어 주소 추가 (시드 아님)
        pm.add_peer_address(PeerAddress(ip="3.3.3.3", port=9333))
        pm.add_peer_address(PeerAddress(ip="4.4.4.4", port=9333))

        candidates = pm.get_peers_to_connect(count=5)
        ips = {c.ip for c in candidates}
        assert "3.3.3.3" in ips
        assert "4.4.4.4" in ips

    def test_seeds_prioritized_over_others(self):
        """시드 노드가 일반 피어보다 우선 연결되는가"""
        pm = PeerManager()
        pm.add_seed_nodes([("1.1.1.1", 9333)])
        pm.add_peer_address(PeerAddress(ip="2.2.2.2", port=9333))

        candidates = pm.get_peers_to_connect(count=5)
        # 시드가 먼저 와야 함
        assert candidates[0].ip == "1.1.1.1"

    def test_connected_peers_excluded(self):
        """이미 연결된 피어는 후보에서 제외되는가"""
        pm = PeerManager()
        addr = PeerAddress(ip="3.3.3.3", port=9333)
        pm.add_peer_address(addr)

        # 연결
        pm.add_peer(addr, is_inbound=False)

        candidates = pm.get_peers_to_connect(count=5)
        ips = {c.ip for c in candidates}
        assert "3.3.3.3" not in ips  # 이미 연결됨


# =============================================================================
# 5. 전체 시나리오: 시드 → 주소교환 → 캐시 → 시드 없이 재연결
# =============================================================================

class TestFullDiscoveryScenario:
    """
    E2E 시나리오 (네트워크 없이 코드 로직만 검증)

    시나리오:
    1. Node A 시작 → 캐시 비어서 시드로 연결
    2. 시드에서 ADDR 응답 → Node B, C 주소 수신
    3. Node A 종료 → 캐시 저장
    4. Node A 재시작 → 캐시에서 B, C에 직접 연결 (시드 안 거침)
    """

    def test_seed_to_cache_to_direct_connection(self):
        tmpdir = tempfile.mkdtemp()

        # === Phase 1: 최초 시작 (캐시 비어있음) ===
        discovery1 = PeerDiscovery(tmpdir)

        with patch.object(discovery1, '_resolve_dns', return_value=[]):
            initial_peers = discovery1.initialize()

        # 시드만 반환됨
        initial_ips = {p.ip for p in initial_peers}
        assert "54.116.13.57" in initial_ips  # 하드코딩 시드

        # === Phase 2: 시드 연결 후 ADDR로 피어 주소 수신 ===
        now = int(time.time())
        received_addrs = [
            PeerAddress(ip="100.0.0.1", port=9333, timestamp=now),
            PeerAddress(ip="100.0.0.2", port=9333, timestamp=now),
            PeerAddress(ip="100.0.0.3", port=9333, timestamp=now),
            PeerAddress(ip="100.0.0.4", port=9333, timestamp=now),
            PeerAddress(ip="100.0.0.5", port=9333, timestamp=now),
            PeerAddress(ip="100.0.0.6", port=9333, timestamp=now),
            PeerAddress(ip="100.0.0.7", port=9333, timestamp=now),
            PeerAddress(ip="100.0.0.8", port=9333, timestamp=now),
            PeerAddress(ip="100.0.0.9", port=9333, timestamp=now),
            PeerAddress(ip="100.0.0.10", port=9333, timestamp=now),
        ]
        discovery1.add_addresses(received_addrs)

        # 실제로 연결 성공했다고 기록 (핸드셰이크 완료 시 mark_good 호출됨)
        for addr in received_addrs:
            discovery1.mark_good(addr)

        # 캐시에 10개 + 시드 들어있음
        assert len(discovery1.cache) >= 10

        # === Phase 3: 종료 → 캐시 저장 ===
        discovery1.save()

        # peers.json이 존재하는지
        cache_file = Path(tmpdir) / "peers.json"
        assert cache_file.exists()

        # === Phase 4: 재시작 → 캐시에서 직접 연결 ===
        discovery2 = PeerDiscovery(tmpdir)

        with patch.object(discovery2, '_query_seeds') as mock_seeds:
            restart_peers = discovery2.initialize()

        # 시드를 조회하지 않았어야 함
        mock_seeds.assert_not_called()

        # 반환된 피어에 캐시된 주소가 포함되어야 함
        restart_ips = {p.ip for p in restart_peers}
        cached_found = restart_ips & {"100.0.0.1", "100.0.0.2", "100.0.0.3"}
        assert len(cached_found) > 0, "캐시된 피어가 연결 후보에 있어야 함"

        # 하드코딩 시드가 아닌 주소로 연결 가능해야 함
        non_seed_ips = restart_ips - {"54.116.13.57", "127.0.0.1"}
        assert len(non_seed_ips) > 0, "시드가 아닌 피어로 직접 연결 가능해야 함"
