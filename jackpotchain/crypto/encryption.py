"""
개인키 암호화 모듈

AES-256-GCM + PBKDF2 기반 암호화
"""

import os
import hashlib
from typing import Tuple

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


# 상수
SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32  # AES-256
ITERATIONS = 100_000


def is_encryption_available() -> bool:
    """암호화 라이브러리 사용 가능 여부"""
    return CRYPTO_AVAILABLE


def derive_key(password: str, salt: bytes) -> bytes:
    """
    비밀번호에서 암호화 키 유도 (PBKDF2)

    Args:
        password: 사용자 비밀번호
        salt: 랜덤 salt

    Returns:
        32바이트 키
    """
    if CRYPTO_AVAILABLE:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE,
            salt=salt,
            iterations=ITERATIONS,
        )
        return kdf.derive(password.encode('utf-8'))
    else:
        # fallback: hashlib
        return hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            ITERATIONS,
            dklen=KEY_SIZE
        )


def encrypt_private_key(private_key: bytes, password: str) -> bytes:
    """
    개인키 암호화

    형식: salt (16) + nonce (12) + ciphertext + tag (16)

    Args:
        private_key: 암호화할 개인키 (32바이트)
        password: 암호화 비밀번호

    Returns:
        암호화된 데이터
    """
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography 라이브러리가 필요합니다: pip install cryptography")

    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = derive_key(password, salt)

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, private_key, None)

    # salt + nonce + ciphertext (includes tag)
    return salt + nonce + ciphertext


def decrypt_private_key(encrypted_data: bytes, password: str) -> bytes:
    """
    개인키 복호화

    Args:
        encrypted_data: 암호화된 데이터
        password: 복호화 비밀번호

    Returns:
        원본 개인키

    Raises:
        ValueError: 잘못된 비밀번호 또는 손상된 데이터
    """
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography 라이브러리가 필요합니다: pip install cryptography")

    if len(encrypted_data) < SALT_SIZE + NONCE_SIZE + 16:
        raise ValueError("암호화된 데이터가 너무 짧습니다")

    salt = encrypted_data[:SALT_SIZE]
    nonce = encrypted_data[SALT_SIZE:SALT_SIZE + NONCE_SIZE]
    ciphertext = encrypted_data[SALT_SIZE + NONCE_SIZE:]

    key = derive_key(password, salt)

    try:
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)
    except Exception:
        raise ValueError("잘못된 비밀번호이거나 데이터가 손상되었습니다")


def verify_password(encrypted_data: bytes, password: str) -> bool:
    """비밀번호 검증"""
    try:
        decrypt_private_key(encrypted_data, password)
        return True
    except ValueError:
        return False
