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
    from ..crypto.address import pubkey_hash_to_address, JACKPOT_POOL_ADDRESS, BURN_ADDRESS

    # 특수 마커 처리 (제네시스 블록 등)
    if script_pubkey == b'JACKPOT_POOL':
        return JACKPOT_POOL_ADDRESS
    if script_pubkey == b'BURN':
        return BURN_ADDRESS

    # P2PKH 형식
    pubkey_hash = extract_p2pkh_pubkey_hash(script_pubkey)
    if pubkey_hash:
        return pubkey_hash_to_address(pubkey_hash)
    return None


# === JackpotChain 특수 스크립트 ===

# =============================================================================
# 로또 Commit
# =============================================================================

def create_commit_script(chosen_numbers: list) -> bytes:
    """
    Lotto Commit TX용 OP_RETURN

    Format: OP_RETURN "LOTTO" <chosen_numbers(6 bytes)>

    Args:
        chosen_numbers: 6자리 숫자 배열 (각 0~15)

    Security:
        숫자가 평문으로 포함되지만, 당첨 판정은 N+18 블록 해시 기반이므로
        commit 시점 채굴자는 결과를 조작할 수 없음
    """
    data = b'LOTTO' + bytes(chosen_numbers)
    return create_op_return_script(data)


def is_commit_script(script: bytes) -> bool:
    """Commit 스크립트인지 (LOTTO prefix)"""
    data = extract_op_return_data(script)
    if data is None:
        return False
    return data.startswith(b'LOTTO')


def extract_commit_numbers(script: bytes) -> Optional[list]:
    """
    Commit 스크립트에서 chosen_numbers 추출

    Returns:
        chosen_numbers (6자리 list) or None
    """
    data = extract_op_return_data(script)
    if data is None:
        return None

    # LOTTO 형식: "LOTTO" + 6 bytes numbers
    if data.startswith(b'LOTTO') and len(data) >= 11:
        return list(data[5:11])

    return None


# =============================================================================
# 로또 자동 지급 (Payout TX - 채굴자가 블록에 포함)
# =============================================================================

def create_lotto_payout_script(commit_tx_id: bytes, chosen_numbers: list, result_digits: list, matches: int) -> bytes:
    """
    로또 자동 지급 TX용 OP_RETURN (결과 기록)

    Format: OP_RETURN "PAYOUT" <commit_tx_id(32)> <chosen(6)> <result(6)> <matches(1)>

    Args:
        commit_tx_id: 원본 Commit TX ID (32 bytes)
        chosen_numbers: 선택한 숫자 (6 bytes)
        result_digits: 블록해시 추출 결과 (6 bytes)
        matches: 일치 수 (1 byte)
    """
    data = b'PAYOUT' + commit_tx_id + bytes(chosen_numbers) + bytes(result_digits) + bytes([matches])
    return create_op_return_script(data)


def is_payout_script(script: bytes) -> bool:
    """Payout 스크립트인지"""
    data = extract_op_return_data(script)
    return data is not None and data.startswith(b'PAYOUT')


def extract_payout_data(script: bytes) -> Optional[Tuple[bytes, list, list, int]]:
    """
    Payout 스크립트에서 데이터 추출

    Returns:
        (commit_tx_id, chosen_numbers, result_digits, matches) or None
    """
    data = extract_op_return_data(script)
    if data is None:
        return None

    # PAYOUT 형식: "PAYOUT"(6) + tx_id(32) + chosen(6) + result(6) + matches(1) = 51
    if data.startswith(b'PAYOUT') and len(data) >= 51:
        commit_tx_id = data[6:38]
        chosen_numbers = list(data[38:44])
        result_digits = list(data[44:50])
        matches = data[50]
        return commit_tx_id, chosen_numbers, result_digits, matches

    return None
