"""
Step 1.2: ECDSA 서명 모듈
- secp256k1 곡선 사용 (Bitcoin과 동일)
"""

import secrets
import hashlib
from typing import Tuple

# ecdsa 라이브러리 사용 (pip install ecdsa)
try:
    from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError
    from ecdsa.util import sigencode_der, sigdecode_der
    ECDSA_AVAILABLE = True
except ImportError:
    ECDSA_AVAILABLE = False
    print("Warning: ecdsa library not installed. Run: pip install ecdsa")


def generate_keypair() -> Tuple[bytes, bytes]:
    """
    새 키쌍 생성
    Returns: (private_key: 32 bytes, public_key: 33 bytes compressed)
    """
    if not ECDSA_AVAILABLE:
        raise ImportError("ecdsa library required")

    # 개인키 생성 (32바이트 랜덤)
    private_key = SigningKey.generate(curve=SECP256k1)

    # 공개키 (압축 형식)
    public_key = private_key.get_verifying_key()

    return (
        private_key.to_string(),  # 32 bytes
        compress_public_key(public_key.to_string())  # 33 bytes
    )


def compress_public_key(pubkey_uncompressed: bytes) -> bytes:
    """
    비압축 공개키(64 bytes) → 압축 공개키(33 bytes)
    """
    if len(pubkey_uncompressed) == 33:
        return pubkey_uncompressed  # 이미 압축됨

    if len(pubkey_uncompressed) == 65:
        # 0x04 prefix 제거
        pubkey_uncompressed = pubkey_uncompressed[1:]

    x = pubkey_uncompressed[:32]
    y = pubkey_uncompressed[32:]

    # y 좌표의 짝/홀로 prefix 결정
    if y[-1] % 2 == 0:
        prefix = b'\x02'
    else:
        prefix = b'\x03'

    return prefix + x


def decompress_public_key(pubkey_compressed: bytes) -> bytes:
    """
    압축 공개키(33 bytes) → 비압축 공개키(64 bytes)
    """
    if len(pubkey_compressed) == 64:
        return pubkey_compressed  # 이미 비압축

    if len(pubkey_compressed) != 33:
        raise ValueError(f"Invalid compressed pubkey length: {len(pubkey_compressed)}")

    prefix = pubkey_compressed[0]
    x = int.from_bytes(pubkey_compressed[1:], 'big')

    # secp256k1 곡선 파라미터
    p = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F

    # y^2 = x^3 + 7 (mod p)
    y_squared = (pow(x, 3, p) + 7) % p
    y = pow(y_squared, (p + 1) // 4, p)

    # prefix에 따라 y 선택
    if (prefix == 0x02 and y % 2 != 0) or (prefix == 0x03 and y % 2 == 0):
        y = p - y

    return x.to_bytes(32, 'big') + y.to_bytes(32, 'big')


def sign(message_hash: bytes, private_key: bytes) -> bytes:
    """
    메시지 해시에 서명
    Args:
        message_hash: 32 bytes (SHA256 해시)
        private_key: 32 bytes
    Returns:
        signature: DER 인코딩된 서명 (70-72 bytes)
    """
    if not ECDSA_AVAILABLE:
        raise ImportError("ecdsa library required")

    sk = SigningKey.from_string(private_key, curve=SECP256k1)
    signature = sk.sign_digest(
        message_hash,
        sigencode=sigencode_der
    )
    return signature


def verify(message_hash: bytes, signature: bytes, public_key: bytes) -> bool:
    """
    서명 검증
    Args:
        message_hash: 32 bytes
        signature: DER 인코딩된 서명
        public_key: 33 bytes (압축) 또는 64 bytes (비압축)
    Returns:
        bool: 유효하면 True
    """
    if not ECDSA_AVAILABLE:
        raise ImportError("ecdsa library required")

    try:
        # 압축 공개키면 비압축으로 변환
        if len(public_key) == 33:
            public_key = decompress_public_key(public_key)

        vk = VerifyingKey.from_string(public_key, curve=SECP256k1)
        return vk.verify_digest(
            signature,
            message_hash,
            sigdecode=sigdecode_der
        )
    except (BadSignatureError, Exception):
        return False


def private_key_to_public_key(private_key: bytes) -> bytes:
    """개인키에서 공개키 도출"""
    if not ECDSA_AVAILABLE:
        raise ImportError("ecdsa library required")

    sk = SigningKey.from_string(private_key, curve=SECP256k1)
    vk = sk.get_verifying_key()
    return compress_public_key(vk.to_string())
