"""
피어 발견 테스트
- DNS 시드
- 피어 캐시
- ADDR 메시지
"""

import pytest
import tempfile
import os
import time
from pathlib import Path

from jackpotchain.network.discovery import (
    PeerDiscovery, PeerCache, CachedPeer,
    DNS_SEEDS, HARDCODED_SEEDS,
)
from jackpotchain.network.peer import PeerAddress
from jackpotchain.network.protocol import (
    NetAddress, AddrMessage, MessageType,
    create_message, parse_message,
)


class TestNetAddress:
    """NetAddress 직렬화 테스트"""

    def test_ipv4_conversion(self):
        """IPv4 문자열 변환"""
        addr = NetAddress.from_ipv4("192.168.1.100", 8333)
        assert addr.to_ipv4() == "192.168.1.100"
        assert addr.port == 8333

    def test_serialize_deserialize(self):
        """직렬화/역직렬화"""
        original = NetAddress.from_ipv4(
            "10.0.0.1", 8333,
            timestamp=int(time.time()),
            services=1
        )
        data = original.serialize()
        restored, _ = NetAddress.deserialize(data)

        assert restored.to_ipv4() == original.to_ipv4()
        assert restored.port == original.port
        assert restored.timestamp == original.timestamp
        assert restored.services == original.services


class TestAddrMessage:
    """ADDR 메시지 테스트"""

    def test_empty_message(self):
        """빈 메시지"""
        msg = AddrMessage(addresses=[])
        data = msg.serialize()
        restored = AddrMessage.deserialize(data)
        assert len(restored.addresses) == 0

    def test_single_address(self):
        """단일 주소"""
        addr = NetAddress.from_ipv4("127.0.0.1", 8333)
        msg = AddrMessage(addresses=[addr])
        data = msg.serialize()
        restored = AddrMessage.deserialize(data)

        assert len(restored.addresses) == 1
        assert restored.addresses[0].to_ipv4() == "127.0.0.1"

    def test_multiple_addresses(self):
        """다중 주소"""
        addresses = [
            NetAddress.from_ipv4(f"192.168.1.{i}", 8333 + i)
            for i in range(10)
        ]
        msg = AddrMessage(addresses=addresses)
        data = msg.serialize()
        restored = AddrMessage.deserialize(data)

        assert len(restored.addresses) == 10
        for i, addr in enumerate(restored.addresses):
            assert addr.to_ipv4() == f"192.168.1.{i}"
            assert addr.port == 8333 + i

    def test_full_message_with_header(self):
        """전체 메시지 (헤더 포함)"""
        addr = NetAddress.from_ipv4("10.0.0.1", 8333)
        msg = AddrMessage(addresses=[addr])
        payload = msg.serialize()

        full_msg = create_message(MessageType.ADDR, payload)
        header, parsed_payload = parse_message(full_msg)

        assert header is not None
        assert header.command.rstrip(b'\x00') == b'addr'
        assert parsed_payload == payload


class TestCachedPeer:
    """CachedPeer 테스트"""

    def test_to_peer_address(self):
        """PeerAddress 변환"""
        cached = CachedPeer(
            ip="192.168.1.1",
            port=8333,
            services=1,
            last_seen=1000
        )
        addr = cached.to_peer_address()

        assert addr.ip == "192.168.1.1"
        assert addr.port == 8333
        assert addr.services == 1
        assert addr.timestamp == 1000


class TestPeerCache:
    """PeerCache 테스트"""

    def test_add_and_get(self):
        """피어 추가 및 조회"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PeerCache(tmpdir)

            cache.add("192.168.1.1", 8333)
            cache.add("192.168.1.2", 8334)

            peers = cache.get_peers(count=10)
            assert len(peers) == 2

    def test_save_and_load(self):
        """저장 및 로드"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 저장
            cache1 = PeerCache(tmpdir)
            cache1.add("10.0.0.1", 8333, timestamp=1000)
            cache1.add("10.0.0.2", 8333, timestamp=2000)
            cache1.save()

            # 로드
            cache2 = PeerCache(tmpdir)
            loaded = cache2.load()

            assert loaded == 2
            peers = cache2.get_peers()
            assert len(peers) == 2

    def test_mark_success(self):
        """성공 기록"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PeerCache(tmpdir)
            cache.add("192.168.1.1", 8333)

            cache.mark_attempt("192.168.1.1", 8333)
            cache.mark_attempt("192.168.1.1", 8333)
            cache.mark_success("192.168.1.1", 8333)

            peers = cache.get_peers()
            # 성공률이 높은 피어가 우선

    def test_duplicate_add(self):
        """중복 추가 시 업데이트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PeerCache(tmpdir)

            cache.add("192.168.1.1", 8333, timestamp=1000)
            cache.add("192.168.1.1", 8333, timestamp=2000)

            peers = cache.get_peers()
            assert len(peers) == 1
            assert peers[0].timestamp == 2000

    def test_get_recent_peers(self):
        """최근 피어 조회"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PeerCache(tmpdir)

            now = int(time.time())
            cache.add("192.168.1.1", 8333, timestamp=now)
            cache.add("192.168.1.2", 8333, timestamp=now - 100000)  # 오래됨

            recent = cache.get_recent_peers(max_age=3600)
            assert len(recent) == 1
            assert recent[0].ip == "192.168.1.1"


class TestPeerDiscovery:
    """PeerDiscovery 테스트"""

    def test_initialize_empty(self):
        """빈 캐시로 초기화"""
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery = PeerDiscovery(tmpdir)
            peers = discovery.initialize()

            # 하드코딩 시드 최소 1개 있어야 함
            assert len(peers) >= len(HARDCODED_SEEDS)

    def test_add_addresses(self):
        """주소 추가"""
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery = PeerDiscovery(tmpdir, allow_private_ip=True)
            discovery.initialize()

            # ADDR에서 받은 주소 추가
            new_addrs = [
                PeerAddress(ip="10.1.1.1", port=8333),
                PeerAddress(ip="10.1.1.2", port=8333),
            ]
            discovery.add_addresses(new_addrs)

            # 조회 가능해야 함
            peers = discovery.get_peers_to_connect(count=10)
            ips = [p.ip for p in peers]
            assert "10.1.1.1" in ips

    def test_mark_good_bad(self):
        """성공/시도 기록"""
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery = PeerDiscovery(tmpdir, allow_private_ip=True)
            discovery.initialize()

            addr = PeerAddress(ip="10.0.0.1", port=8333)
            discovery.add_addresses([addr])

            discovery.mark_attempt(addr)
            discovery.mark_good(addr)

    def test_is_private_ip(self):
        """사설 IP 확인"""
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery = PeerDiscovery(tmpdir)

            assert discovery._is_private_ip("10.0.0.1") is True
            assert discovery._is_private_ip("172.16.0.1") is True
            assert discovery._is_private_ip("192.168.1.1") is True
            assert discovery._is_private_ip("127.0.0.1") is True
            assert discovery._is_private_ip("8.8.8.8") is False

    def test_get_addr_to_send(self):
        """ADDR 응답용 주소 목록"""
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery = PeerDiscovery(tmpdir, allow_private_ip=True)

            # 최근 주소 추가
            now = int(time.time())
            recent_addr = PeerAddress(ip="10.1.1.1", port=8333, timestamp=now)
            discovery.add_addresses([recent_addr])

            addrs = discovery.get_addr_to_send(count=100)
            assert len(addrs) >= 1


class TestConstants:
    """상수 테스트"""

    def test_dns_seeds_defined(self):
        """DNS 시드 정의됨"""
        assert len(DNS_SEEDS) > 0

    def test_hardcoded_seeds_defined(self):
        """하드코딩 시드 정의됨"""
        assert len(HARDCODED_SEEDS) > 0
        for ip, port in HARDCODED_SEEDS:
            assert isinstance(ip, str)
            assert isinstance(port, int)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
