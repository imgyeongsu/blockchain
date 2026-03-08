"""
Step 3.1: 스크립트 Opcodes
- 비트코인 호환 최소 OP 코드
- MVP: P2PKH만 지원
"""

from enum import IntEnum


class OpCode(IntEnum):
    """기본 OpCode 정의"""

    # Constants
    OP_0 = 0x00
    OP_FALSE = 0x00
    OP_PUSHDATA1 = 0x4c  # 다음 1바이트가 데이터 길이
    OP_PUSHDATA2 = 0x4d  # 다음 2바이트가 데이터 길이
    OP_PUSHDATA4 = 0x4e  # 다음 4바이트가 데이터 길이
    OP_1NEGATE = 0x4f
    OP_TRUE = 0x51
    OP_1 = 0x51
    OP_2 = 0x52
    OP_3 = 0x53
    OP_4 = 0x54
    OP_5 = 0x55
    OP_6 = 0x56
    OP_7 = 0x57
    OP_8 = 0x58
    OP_9 = 0x59
    OP_10 = 0x5a
    OP_11 = 0x5b
    OP_12 = 0x5c
    OP_13 = 0x5d
    OP_14 = 0x5e
    OP_15 = 0x5f
    OP_16 = 0x60

    # Flow Control
    OP_NOP = 0x61
    OP_IF = 0x63
    OP_NOTIF = 0x64
    OP_ELSE = 0x67
    OP_ENDIF = 0x68
    OP_VERIFY = 0x69
    OP_RETURN = 0x6a  # TX 무효화 (burn)

    # Stack
    OP_DUP = 0x76
    OP_DROP = 0x75
    OP_SWAP = 0x7c
    OP_OVER = 0x78
    OP_ROT = 0x7b
    OP_2DUP = 0x6e
    OP_3DUP = 0x6f
    OP_2DROP = 0x6d
    OP_2SWAP = 0x72
    OP_IFDUP = 0x73
    OP_DEPTH = 0x74
    OP_NIP = 0x77
    OP_PICK = 0x79
    OP_ROLL = 0x7a
    OP_TUCK = 0x7d
    OP_2OVER = 0x70
    OP_2ROT = 0x71

    # Arithmetic
    OP_ADD = 0x93
    OP_SUB = 0x94
    OP_MUL = 0x95  # Disabled in Bitcoin
    OP_DIV = 0x96  # Disabled in Bitcoin
    OP_1ADD = 0x8b
    OP_1SUB = 0x8c
    OP_NEGATE = 0x8f
    OP_ABS = 0x90
    OP_NOT = 0x91
    OP_0NOTEQUAL = 0x92

    # Comparison
    OP_EQUAL = 0x87
    OP_EQUALVERIFY = 0x88
    OP_NUMEQUAL = 0x9c
    OP_NUMEQUALVERIFY = 0x9d
    OP_NUMNOTEQUAL = 0x9e
    OP_LESSTHAN = 0x9f
    OP_GREATERTHAN = 0xa0
    OP_LESSTHANOREQUAL = 0xa1
    OP_GREATERTHANOREQUAL = 0xa2
    OP_MIN = 0xa3
    OP_MAX = 0xa4
    OP_WITHIN = 0xa5

    # Crypto
    OP_RIPEMD160 = 0xa6
    OP_SHA1 = 0xa7
    OP_SHA256 = 0xa8
    OP_HASH160 = 0xa9    # SHA256 + RIPEMD160
    OP_HASH256 = 0xaa    # Double SHA256
    OP_CHECKSIG = 0xac   # 서명 검증
    OP_CHECKSIGVERIFY = 0xad
    OP_CHECKMULTISIG = 0xae
    OP_CHECKMULTISIGVERIFY = 0xaf

    # Locktime
    OP_CHECKLOCKTIMEVERIFY = 0xb1
    OP_CHECKSEQUENCEVERIFY = 0xb2

    # Reserved
    OP_RESERVED = 0x50
    OP_VER = 0x62
    OP_RESERVED1 = 0x89
    OP_RESERVED2 = 0x8a
    OP_NOP1 = 0xb0
    OP_NOP4 = 0xb3
    OP_NOP5 = 0xb4
    OP_NOP6 = 0xb5
    OP_NOP7 = 0xb6
    OP_NOP8 = 0xb7
    OP_NOP9 = 0xb8
    OP_NOP10 = 0xb9

    # Invalid
    OP_INVALIDOPCODE = 0xff


# 1-75 바이트 직접 푸시 (OP_PUSHBYTES_1 ~ OP_PUSHBYTES_75)
def is_push_data(opcode: int) -> bool:
    """데이터 푸시 명령인지"""
    return 0x01 <= opcode <= 0x4e


def get_push_size(opcode: int, script: bytes, pos: int) -> tuple:
    """
    푸시할 데이터 크기와 데이터 시작 위치 반환
    Returns: (data_size, data_start_offset)
    """
    if 0x01 <= opcode <= 0x4b:
        # OP_PUSHBYTES_N: opcode 자체가 크기
        return opcode, pos

    elif opcode == OpCode.OP_PUSHDATA1:
        # 다음 1바이트가 크기
        size = script[pos]
        return size, pos + 1

    elif opcode == OpCode.OP_PUSHDATA2:
        # 다음 2바이트가 크기 (little-endian)
        size = int.from_bytes(script[pos:pos+2], 'little')
        return size, pos + 2

    elif opcode == OpCode.OP_PUSHDATA4:
        # 다음 4바이트가 크기 (little-endian)
        size = int.from_bytes(script[pos:pos+4], 'little')
        return size, pos + 4

    return 0, pos


def opcode_to_name(opcode: int) -> str:
    """OpCode를 문자열로"""
    try:
        return OpCode(opcode).name
    except ValueError:
        if 0x01 <= opcode <= 0x4b:
            return f"OP_PUSHBYTES_{opcode}"
        return f"OP_UNKNOWN_{hex(opcode)}"


def name_to_opcode(name: str) -> int:
    """문자열을 OpCode로"""
    # OP_PUSHBYTES_N 처리
    if name.startswith("OP_PUSHBYTES_"):
        return int(name[13:])

    return OpCode[name].value


# 비활성화된 opcodes (실행 시 에러)
DISABLED_OPCODES = {
    OpCode.OP_MUL,
    OpCode.OP_DIV,
    OpCode.OP_RESERVED,
    OpCode.OP_VER,
    OpCode.OP_RESERVED1,
    OpCode.OP_RESERVED2,
}


def is_disabled(opcode: int) -> bool:
    """비활성화된 opcode인지"""
    return opcode in DISABLED_OPCODES
