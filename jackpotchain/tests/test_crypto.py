"""
암호학 모듈 테스트
- 해시, 서명, 주소
"""

import pytest
from jackpotchain.crypto.hash import sha256, double_sha256, hash160
from jackpotchain.crypto.signature import generate_keypair, sign, verify, private_key_to_public_key
from jackpotchain.crypto.address import (
    pubkey_to_address, validate_address, address_to_pubkey_hash,
    base58_encode, base58_decode, base58check_encode, base58check_decode
)


class TestHash:
    """해시 함수 테스트"""

    def test_sha256_empty(self):
        """빈 입력 SHA256"""
        result = sha256(b'')
        assert len(result) == 32
        # 빈 문자열의 SHA256 해시 (알려진 값)
        expected = bytes.fromhex('e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')
        assert result == expected

    def test_sha256_hello(self):
        """'hello' SHA256"""
        result = sha256(b'hello')
        assert len(result) == 32
        expected = bytes.fromhex('2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824')
        assert result == expected

    def test_double_sha256(self):
        """Double SHA256"""
        result = double_sha256(b'hello')
        assert len(result) == 32
        # double_sha256(hello) = sha256(sha256(hello))
        expected = sha256(sha256(b'hello'))
        assert result == expected

    def test_hash160(self):
        """HASH160 (SHA256 + RIPEMD160)"""
        result = hash160(b'hello')
        assert len(result) == 20


class TestSignature:
    """ECDSA 서명 테스트"""

    def test_generate_keypair(self):
        """키 쌍 생성"""
        private_key, public_key = generate_keypair()
        assert len(private_key) == 32
        assert len(public_key) in [33, 65]  # 압축 또는 비압축

    def test_sign_and_verify(self):
        """서명 및 검증"""
        private_key, public_key = generate_keypair()
        message = b'test message'
        message_hash = sha256(message)  # 32 bytes hash

        signature = sign(message_hash, private_key)
        assert len(signature) > 0

        # 검증 성공
        assert verify(message_hash, signature, public_key) is True

    def test_verify_wrong_message(self):
        """잘못된 메시지 검증 실패"""
        private_key, public_key = generate_keypair()
        message = b'test message'
        wrong_message = b'wrong message'
        message_hash = sha256(message)
        wrong_hash = sha256(wrong_message)

        signature = sign(message_hash, private_key)

        # 다른 메시지로 검증 실패
        assert verify(wrong_hash, signature, public_key) is False

    def test_verify_wrong_key(self):
        """잘못된 키 검증 실패"""
        private_key1, public_key1 = generate_keypair()
        private_key2, public_key2 = generate_keypair()
        message = b'test message'
        message_hash = sha256(message)

        signature = sign(message_hash, private_key1)

        # 다른 공개키로 검증 실패
        assert verify(message_hash, signature, public_key2) is False

    def test_private_to_public(self):
        """개인키 → 공개키 변환"""
        private_key, public_key = generate_keypair()
        derived_public = private_key_to_public_key(private_key)
        assert derived_public == public_key


class TestAddress:
    """주소 생성 테스트"""

    def test_base58_roundtrip(self):
        """Base58 인코딩/디코딩"""
        original = b'\x00\x01\x02\x03\x04'
        encoded = base58_encode(original)
        decoded = base58_decode(encoded)
        assert decoded == original

    def test_base58check_roundtrip(self):
        """Base58Check 인코딩/디코딩"""
        version = 0x4A  # 'J'
        payload = b'\x01\x02\x03\x04\x05' * 4  # 20 bytes

        encoded = base58check_encode(version, payload)
        dec_version, dec_payload = base58check_decode(encoded)

        assert dec_version == version
        assert dec_payload == payload

    def test_pubkey_to_address(self):
        """공개키 → 주소"""
        _, public_key = generate_keypair()
        address = pubkey_to_address(public_key)

        assert isinstance(address, str)
        assert len(address) > 20  # Base58 인코딩된 주소

    def test_validate_address_valid(self):
        """유효한 주소 검증"""
        _, public_key = generate_keypair()
        address = pubkey_to_address(public_key)

        assert validate_address(address) is True

    def test_validate_address_invalid(self):
        """잘못된 주소 검증"""
        assert validate_address("invalid_address") is False
        assert validate_address("") is False
        assert validate_address("JACK") is False

    def test_address_to_pubkey_hash(self):
        """주소 → 공개키 해시"""
        _, public_key = generate_keypair()
        address = pubkey_to_address(public_key)

        pubkey_hash = address_to_pubkey_hash(address)
        assert len(pubkey_hash) == 20

        # hash160(pubkey) == pubkey_hash
        expected_hash = hash160(public_key)
        assert pubkey_hash == expected_hash


class TestDeterminism:
    """결정론적 동작 테스트"""

    def test_same_input_same_hash(self):
        """같은 입력 → 같은 해시"""
        data = b'deterministic test'
        hash1 = sha256(data)
        hash2 = sha256(data)
        assert hash1 == hash2

    def test_different_input_different_hash(self):
        """다른 입력 → 다른 해시"""
        hash1 = sha256(b'input1')
        hash2 = sha256(b'input2')
        assert hash1 != hash2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
