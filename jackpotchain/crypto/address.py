"""
Step 1.3: 주소 생성 모듈
- Base58Check 인코딩
- 주소 형식: JACKxxxx...
"""

from .hash import sha256, hash160

# 버전 바이트
VERSION_PUBKEY = 0x4A      # 'J' - 일반 주소 (JACK...)
VERSION_SCRIPT = 0x4B      # P2SH 주소 (JACK3...)

# Base58 알파벳 (0, O, I, l 제외)
BASE58_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

# 시스템 주소 (하드코딩)
JACKPOT_POOL_ADDRESS = "JACK_JACKPOT_POOL_SYSTEM"
BURN_ADDRESS = "JACK_BURN_SYSTEM"


def base58_encode(data: bytes) -> str:
    """Base58 인코딩"""
    # 선행 0 바이트 개수 세기
    leading_zeros = 0
    for byte in data:
        if byte == 0:
            leading_zeros += 1
        else:
            break

    # bytes를 정수로 변환
    num = int.from_bytes(data, 'big')

    # Base58 변환
    result = ''
    while num > 0:
        num, remainder = divmod(num, 58)
        result = BASE58_ALPHABET[remainder] + result

    # 선행 0은 '1'로 표현
    return '1' * leading_zeros + result


def base58_decode(s: str) -> bytes:
    """Base58 디코딩"""
    # 선행 '1' 개수 세기
    leading_ones = 0
    for char in s:
        if char == '1':
            leading_ones += 1
        else:
            break

    # Base58 → 정수
    num = 0
    for char in s:
        num = num * 58 + BASE58_ALPHABET.index(char)

    # 정수 → bytes
    result = []
    while num > 0:
        num, remainder = divmod(num, 256)
        result.insert(0, remainder)

    return bytes([0] * leading_ones + result)


def base58check_encode(version: int, payload: bytes) -> str:
    """Base58Check 인코딩 (버전 + 페이로드 + 체크섬)"""
    versioned = bytes([version]) + payload
    checksum = sha256(sha256(versioned))[:4]
    return base58_encode(versioned + checksum)


def base58check_decode(address: str) -> tuple:
    """
    Base58Check 디코딩
    Returns: (version: int, payload: bytes)
    Raises: ValueError if checksum invalid
    """
    decoded = base58_decode(address)

    if len(decoded) < 5:
        raise ValueError("Address too short")

    version = decoded[0]
    payload = decoded[1:-4]
    checksum = decoded[-4:]

    # 체크섬 검증
    expected_checksum = sha256(sha256(decoded[:-4]))[:4]
    if checksum != expected_checksum:
        raise ValueError("Invalid checksum")

    return version, payload


def pubkey_to_address(pubkey: bytes, version: int = VERSION_PUBKEY) -> str:
    """
    공개키 → 주소
    1. SHA256
    2. RIPEMD160
    3. 버전 바이트 추가
    4. 체크섬 추가
    5. Base58 인코딩
    """
    pubkey_hash = hash160(pubkey)
    return base58check_encode(version, pubkey_hash)


def script_to_address(script_hash: bytes) -> str:
    """스크립트 해시 → P2SH 주소"""
    return base58check_encode(VERSION_SCRIPT, script_hash)


def validate_address(address: str) -> bool:
    """주소 유효성 검증"""
    # 시스템 주소 체크
    if address in [JACKPOT_POOL_ADDRESS, BURN_ADDRESS]:
        return True

    try:
        version, payload = base58check_decode(address)

        # 버전 확인
        if version not in [VERSION_PUBKEY, VERSION_SCRIPT]:
            return False

        # 페이로드 길이 확인 (RIPEMD160 = 20 bytes)
        if len(payload) != 20:
            return False

        return True
    except (ValueError, IndexError):
        return False


def address_to_pubkey_hash(address: str) -> bytes:
    """주소에서 공개키 해시 추출"""
    version, payload = base58check_decode(address)
    return payload


def pubkey_hash_to_address(pubkey_hash: bytes, version: int = VERSION_PUBKEY) -> str:
    """공개키 해시 → 주소"""
    if len(pubkey_hash) != 20:
        raise ValueError("pubkey_hash must be 20 bytes")
    return base58check_encode(version, pubkey_hash)


def is_system_address(address: str) -> bool:
    """시스템 주소인지 확인"""
    return address in [JACKPOT_POOL_ADDRESS, BURN_ADDRESS]


def is_jackpot_address(address: str) -> bool:
    """잭팟 풀 주소인지 확인"""
    return address == JACKPOT_POOL_ADDRESS


def is_burn_address(address: str) -> bool:
    """소각 주소인지 확인"""
    return address == BURN_ADDRESS
