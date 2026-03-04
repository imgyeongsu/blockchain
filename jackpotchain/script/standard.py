"""
Step 3.3: 표준 스크립트 템플릿
- P2PKH (Pay to Public Key Hash)
- OP_RETURN (데이터 임베딩)
"""

from typing import Optional, Tuple
from .opcodes import OpCode


def create_p2pkh_script_pubkey(pubkey_hash: bytes) -> bytes:
    """
    P2PKH scriptPubKey 생성
    OP_DUP OP_HASH160 <pubkey_hash> OP_EQUALVERIFY OP_CHECKSIG
    """
    if len(pubkey_hash) != 20:
        raise ValueError("pubkey_hash must be 20 bytes")

    return bytes([
        OpCode.OP_DUP,
        OpCode.OP_HASH160,
        0x14,  # PUSHDATA 20 bytes
    ]) + pubkey_hash + bytes([
        OpCode.OP_EQUALVERIFY,
        OpCode.OP_CHECKSIG,
    ])


def create_p2pkh_script_sig(signature: bytes, pubkey: bytes) -> bytes:
    """
    P2PKH scriptSig 생성
    <signature> <pubkey>
    """
    # 서명 + sighash type (SIGHASH_ALL = 0x01)
    sig_with_type = signature + bytes([0x01])

    result = bytes()

    # 서명 푸시
    if len(sig_with_type) <= 75:
        result += bytes([len(sig_with_type)]) + sig_with_type
    else:
        result += bytes([OpCode.OP_PUSHDATA1, len(sig_with_type)]) + sig_with_type

    # 공개키 푸시
    if len(pubkey) <= 75:
        result += bytes([len(pubkey)]) + pubkey
    else:
        result += bytes([OpCode.OP_PUSHDATA1, len(pubkey)]) + pubkey

    return result


def create_op_return_script(data: bytes) -> bytes:
    """
    OP_RETURN 스크립트 생성 (데이터 임베딩용)
    OP_RETURN <data>
    """
    if len(data) > 80:
        raise ValueError("OP_RETURN data must be <= 80 bytes")

    result = bytes([OpCode.OP_RETURN])

    if len(data) <= 75:
        result += bytes([len(data)]) + data
    else:
        result += bytes([OpCode.OP_PUSHDATA1, len(data)]) + data

    return result


def is_p2pkh_script_pubkey(script: bytes) -> bool:
    """P2PKH scriptPubKey 형식인지 확인"""
    # OP_DUP OP_HASH160 0x14 <20 bytes> OP_EQUALVERIFY OP_CHECKSIG
    return (
        len(script) == 25 and
        script[0] == OpCode.OP_DUP and
        script[1] == OpCode.OP_HASH160 and
        script[2] == 0x14 and
        script[23] == OpCode.OP_EQUALVERIFY and
        script[24] == OpCode.OP_CHECKSIG
    )


def is_op_return_script(script: bytes) -> bool:
    """OP_RETURN 스크립트인지 확인"""
    return len(script) > 0 and script[0] == OpCode.OP_RETURN


def extract_p2pkh_pubkey_hash(script_pubkey: bytes) -> Optional[bytes]:
    """P2PKH scriptPubKey에서 pubkey_hash 추출"""
    if is_p2pkh_script_pubkey(script_pubkey):
        return script_pubkey[3:23]
    return None


def extract_op_return_data(script: bytes) -> Optional[bytes]:
    """OP_RETURN 스크립트에서 데이터 추출"""
    if not is_op_return_script(script):
        return None

    if len(script) < 2:
        return b''

    pos = 1
    opcode = script[pos]
    pos += 1

    # 데이터 크기 확인
    if opcode <= 75:
        data_size = opcode
    elif opcode == OpCode.OP_PUSHDATA1:
        if pos >= len(script):
            return None
        data_size = script[pos]
        pos += 1
    else:
        return None

    if pos + data_size > len(script):
        return None

    return script[pos:pos + data_size]


def get_script_type(script_pubkey: bytes) -> str:
    """스크립트 타입 반환"""
    if is_p2pkh_script_pubkey(script_pubkey):
        return "P2PKH"
    elif is_op_return_script(script_pubkey):
        return "OP_RETURN"
    elif len(script_pubkey) == 0:
        return "EMPTY"
    else:
        return "UNKNOWN"


def get_address_from_script_pubkey(script_pubkey: bytes) -> Optional[str]:
    """scriptPubKey에서 주소 추출"""
    from ..crypto.address import pubkey_hash_to_address

    pubkey_hash = extract_p2pkh_pubkey_hash(script_pubkey)
    if pubkey_hash:
        return pubkey_hash_to_address(pubkey_hash)
    return None


# === JackpotChain 특수 스크립트 ===

# =============================================================================
# 로또 Commit (16-2 Final)
# =============================================================================

def create_commit_script(commit_hash: bytes, chosen_numbers: list = None) -> bytes:
    """
    Lotto Commit TX용 OP_RETURN

    Format: OP_RETURN "LOTTO" <commit_hash> [<chosen_numbers>]

    Args:
        commit_hash: SHA256(nonce || chosen_numbers) - 32 bytes
        chosen_numbers: 6자리 숫자 배열 (선택적, 공개 여부 결정)

    Note:
        16-2 설계에서 숫자는 Commit TX에 포함 (미래 블록 해시로 비교하므로
        숫자를 알아도 결과 예측 불가)
    """
    data = b'LOTTO' + commit_hash
    if chosen_numbers is not None:
        if len(chosen_numbers) == 6:
            data += bytes(chosen_numbers)
    return create_op_return_script(data)


def is_commit_script(script: bytes) -> bool:
    """Commit 스크립트인지 (LOTTO 또는 레거시 COMMIT)"""
    data = extract_op_return_data(script)
    if data is None:
        return False
    return data.startswith(b'LOTTO') or data.startswith(b'COMMIT')


def extract_commit_hash(script: bytes) -> Optional[bytes]:
    """Commit 스크립트에서 commit_hash 추출"""
    data = extract_op_return_data(script)
    if data is None:
        return None

    # LOTTO 형식 (신규)
    if data.startswith(b'LOTTO') and len(data) >= 37:
        return data[5:37]  # 32 bytes commit hash

    # COMMIT 형식 (레거시)
    if data.startswith(b'COMMIT') and len(data) >= 38:
        return data[6:38]

    return None


def extract_commit_data(script: bytes) -> Optional[Tuple[bytes, list]]:
    """
    Commit 스크립트에서 (commit_hash, chosen_numbers) 추출

    Returns:
        (commit_hash, chosen_numbers) or None
    """
    data = extract_op_return_data(script)
    if data is None:
        return None

    # LOTTO 형식 (신규): "LOTTO" + 32 bytes hash + 6 bytes numbers
    if data.startswith(b'LOTTO') and len(data) >= 37:
        commit_hash = data[5:37]
        chosen_numbers = list(data[37:43]) if len(data) >= 43 else []
        return commit_hash, chosen_numbers

    # COMMIT 형식 (레거시): "COMMIT" + 32 bytes hash
    if data.startswith(b'COMMIT') and len(data) >= 38:
        commit_hash = data[6:38]
        return commit_hash, []

    return None


# =============================================================================
# 로또 Claim (16-2 Final)
# =============================================================================

def create_claim_script(commit_hash: bytes, nonce: bytes, chosen_numbers: list) -> bytes:
    """
    Lotto Claim TX용 OP_RETURN

    Format: OP_RETURN "CLAIM" <commit_hash> <nonce> <chosen_numbers>

    Args:
        commit_hash: 원래 Commit의 해시 - 32 bytes
        nonce: 원래 Commit에 사용한 nonce - 32 bytes
        chosen_numbers: 6자리 숫자 배열 - 6 bytes
    """
    data = b'CLAIM' + commit_hash + nonce + bytes(chosen_numbers)
    return create_op_return_script(data)


def is_claim_script(script: bytes) -> bool:
    """Claim 스크립트인지"""
    data = extract_op_return_data(script)
    return data is not None and data.startswith(b'CLAIM')


def extract_claim_data(script: bytes) -> Optional[Tuple[bytes, bytes, list]]:
    """
    Claim 스크립트에서 (commit_hash, nonce, chosen_numbers) 추출

    Returns:
        (commit_hash, nonce, chosen_numbers) or None
    """
    data = extract_op_return_data(script)
    if data is None:
        return None

    # CLAIM 형식: "CLAIM" + 32 bytes hash + 32 bytes nonce + 6 bytes numbers
    if data.startswith(b'CLAIM') and len(data) >= 75:
        commit_hash = data[5:37]
        nonce = data[37:69]
        chosen_numbers = list(data[69:75])
        return commit_hash, nonce, chosen_numbers

    return None


# =============================================================================
# Reveal (deprecated - 하위 호환용)
# =============================================================================

def create_reveal_script(nonce: bytes, target: int) -> bytes:
    """
    [DEPRECATED] Reveal TX용 OP_RETURN
    새 코드에서는 create_claim_script() 사용
    """
    data = b'REVEAL' + nonce + target.to_bytes(1, 'big')
    return create_op_return_script(data)


def is_reveal_script(script: bytes) -> bool:
    """[DEPRECATED] Reveal 스크립트인지"""
    data = extract_op_return_data(script)
    return data is not None and data.startswith(b'REVEAL')


def extract_reveal_data(script: bytes) -> Optional[Tuple[bytes, int]]:
    """[DEPRECATED] Reveal 스크립트에서 (nonce, target) 추출"""
    data = extract_op_return_data(script)
    if data and data.startswith(b'REVEAL') and len(data) >= 39:
        nonce = data[6:38]    # 32 bytes nonce
        target = data[38]     # 1 byte target
        return nonce, target
    return None
