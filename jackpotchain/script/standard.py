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

def create_commit_script(commit_hash: bytes) -> bytes:
    """
    Commit TX용 OP_RETURN
    OP_RETURN "COMMIT" <commit_hash>
    """
    data = b'COMMIT' + commit_hash
    return create_op_return_script(data)


def create_reveal_script(nonce: bytes, target: int) -> bytes:
    """
    Reveal TX용 OP_RETURN
    OP_RETURN "REVEAL" <nonce> <target>
    """
    data = b'REVEAL' + nonce + target.to_bytes(1, 'big')
    return create_op_return_script(data)


def is_commit_script(script: bytes) -> bool:
    """Commit 스크립트인지"""
    data = extract_op_return_data(script)
    return data is not None and data.startswith(b'COMMIT')


def is_reveal_script(script: bytes) -> bool:
    """Reveal 스크립트인지"""
    data = extract_op_return_data(script)
    return data is not None and data.startswith(b'REVEAL')


def extract_commit_hash(script: bytes) -> Optional[bytes]:
    """Commit 스크립트에서 commit_hash 추출"""
    data = extract_op_return_data(script)
    if data and data.startswith(b'COMMIT') and len(data) >= 38:
        return data[6:38]  # 32 bytes commit hash
    return None


def extract_reveal_data(script: bytes) -> Optional[Tuple[bytes, int]]:
    """Reveal 스크립트에서 (nonce, target) 추출"""
    data = extract_op_return_data(script)
    if data and data.startswith(b'REVEAL') and len(data) >= 39:
        nonce = data[6:38]    # 32 bytes nonce
        target = data[38]     # 1 byte target
        return nonce, target
    return None
