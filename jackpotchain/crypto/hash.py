"""
Step 1.1: 해시 함수 모듈
- SHA-256, Double SHA-256, HASH160
"""

import hashlib


def sha256(data: bytes) -> bytes:
    """SHA-256 해시"""
    return hashlib.sha256(data).digest()


def double_sha256(data: bytes) -> bytes:
    """Double SHA-256 (블록/TX 해시용)"""
    return sha256(sha256(data))


def hash160(data: bytes) -> bytes:
    """RIPEMD160(SHA256(x)) - 주소 생성용"""
    sha = hashlib.sha256(data).digest()
    ripemd = hashlib.new('ripemd160')
    ripemd.update(sha)
    return ripemd.digest()


# 편의 함수
def sha256_hex(data: bytes) -> str:
    """SHA-256 해시 (hex 문자열)"""
    return sha256(data).hex()


def double_sha256_hex(data: bytes) -> str:
    """Double SHA-256 (hex 문자열)"""
    return double_sha256(data).hex()
