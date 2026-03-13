"""
Step 3.2: 스크립트 인터프리터
- 스택 기반 가상머신
- scriptSig + scriptPubKey 실행
"""

from typing import List, Optional
from dataclasses import dataclass, field

from .opcodes import (
    OpCode, is_push_data, get_push_size, is_disabled, opcode_to_name
)
from ..crypto.hash import sha256, double_sha256, hash160
from ..crypto.signature import verify


@dataclass
class ScriptError(Exception):
    """스크립트 실행 에러"""
    message: str
    opcode: Optional[int] = None

    def __str__(self):
        if self.opcode is not None:
            return f"{self.message} (opcode: {opcode_to_name(self.opcode)})"
        return self.message


@dataclass
class ScriptContext:
    """스크립트 실행 컨텍스트"""
    # 서명 검증에 필요한 TX 데이터
    tx_hash: bytes = field(default_factory=lambda: bytes(32))
    input_index: int = 0

    # 실행 제한
    max_ops: int = 201
    max_stack_size: int = 1000
    max_script_size: int = 10000


class ScriptInterpreter:
    """스택 기반 스크립트 인터프리터"""

    def __init__(self, context: ScriptContext = None):
        self.context = context or ScriptContext()
        self.stack: List[bytes] = []
        self.alt_stack: List[bytes] = []
        self.op_count = 0

    def reset(self):
        """상태 초기화"""
        self.stack.clear()
        self.alt_stack.clear()
        self.op_count = 0

    def execute(self, script: bytes) -> bool:
        """
        스크립트 실행
        Returns: True if script succeeds (stack top is truthy)
        """
        if len(script) > self.context.max_script_size:
            raise ScriptError("Script too large")

        pos = 0
        while pos < len(script):
            opcode = script[pos]
            pos += 1

            # 데이터 푸시
            if is_push_data(opcode):
                data_size, data_start = get_push_size(opcode, script, pos)
                data = script[data_start:data_start + data_size]
                pos = data_start + data_size

                if len(data) != data_size:
                    raise ScriptError("Unexpected end of script")

                self._push(data)
                continue

            # OP 실행
            self._execute_op(opcode)

        # 스택이 비어있으면 실패
        if not self.stack:
            return False

        # 스택 top이 truthy면 성공
        return self._is_truthy(self.stack[-1])

    def execute_combined(self, script_sig: bytes, script_pubkey: bytes) -> bool:
        """
        scriptSig + scriptPubKey 순차 실행
        비트코인과 동일한 방식
        """
        self.reset()

        # 1. scriptSig 실행 (데이터를 스택에 푸시)
        self.execute(script_sig)

        # 스택 복사 (P2SH용, MVP에서는 미사용)
        stack_copy = self.stack.copy()

        # 2. scriptPubKey 실행 (검증)
        return self.execute(script_pubkey)

    def _push(self, data: bytes):
        """스택에 푸시"""
        if len(self.stack) >= self.context.max_stack_size:
            raise ScriptError("Stack overflow")
        self.stack.append(data)

    def _pop(self) -> bytes:
        """스택에서 팝"""
        if not self.stack:
            raise ScriptError("Stack underflow")
        return self.stack.pop()

    def _peek(self, index: int = -1) -> bytes:
        """스택 확인 (제거 안함)"""
        try:
            return self.stack[index]
        except IndexError:
            raise ScriptError("Stack underflow")

    def _is_truthy(self, data: bytes) -> bool:
        """참/거짓 판단"""
        # 빈 바이트열 = False
        if not data:
            return False
        # 0 (음수 0 포함) = False
        for i, byte in enumerate(data):
            if byte != 0:
                # 마지막 바이트의 0x80만 있으면 음수 0
                if i == len(data) - 1 and byte == 0x80:
                    return False
                return True
        return False

    def _to_int(self, data: bytes) -> int:
        """바이트를 정수로 (little-endian, 부호 있음)"""
        if not data:
            return 0
        # 부호 비트 처리
        negative = data[-1] & 0x80
        if negative:
            data = data[:-1] + bytes([data[-1] & 0x7f])
        value = int.from_bytes(data, 'little')
        return -value if negative else value

    def _from_int(self, value: int) -> bytes:
        """정수를 바이트로"""
        if value == 0:
            return b''

        negative = value < 0
        abs_value = abs(value)

        # 최소 바이트로 인코딩
        result = []
        while abs_value:
            result.append(abs_value & 0xff)
            abs_value >>= 8

        # 부호 비트 처리
        if result[-1] & 0x80:
            result.append(0x80 if negative else 0x00)
        elif negative:
            result[-1] |= 0x80

        return bytes(result)

    def _execute_op(self, opcode: int):
        """단일 opcode 실행"""
        self.op_count += 1
        if self.op_count > self.context.max_ops:
            raise ScriptError("Op limit exceeded", opcode)

        if is_disabled(opcode):
            raise ScriptError("Disabled opcode", opcode)

        # Constants
        if opcode == OpCode.OP_0:
            self._push(b'')
        elif opcode == OpCode.OP_1NEGATE:
            self._push(self._from_int(-1))
        elif OpCode.OP_1 <= opcode <= OpCode.OP_16:
            self._push(self._from_int(opcode - OpCode.OP_1 + 1))

        # Flow Control
        elif opcode == OpCode.OP_NOP:
            pass
        elif opcode == OpCode.OP_VERIFY:
            if not self._is_truthy(self._pop()):
                raise ScriptError("OP_VERIFY failed", opcode)
        elif opcode == OpCode.OP_RETURN:
            raise ScriptError("OP_RETURN encountered", opcode)

        # Stack Operations
        elif opcode == OpCode.OP_DUP:
            self._push(self._peek())
        elif opcode == OpCode.OP_DROP:
            self._pop()
        elif opcode == OpCode.OP_2DUP:
            self._push(self._peek(-2))
            self._push(self._peek(-2))
        elif opcode == OpCode.OP_2DROP:
            self._pop()
            self._pop()
        elif opcode == OpCode.OP_SWAP:
            a = self._pop()
            b = self._pop()
            self._push(a)
            self._push(b)
        elif opcode == OpCode.OP_OVER:
            self._push(self._peek(-2))
        elif opcode == OpCode.OP_ROT:
            c = self._pop()
            b = self._pop()
            a = self._pop()
            self._push(b)
            self._push(c)
            self._push(a)
        elif opcode == OpCode.OP_NIP:
            top = self._pop()
            self._pop()
            self._push(top)
        elif opcode == OpCode.OP_TUCK:
            top = self._pop()
            second = self._pop()
            self._push(top)
            self._push(second)
            self._push(top)
        elif opcode == OpCode.OP_DEPTH:
            self._push(self._from_int(len(self.stack)))
        elif opcode == OpCode.OP_IFDUP:
            if self._is_truthy(self._peek()):
                self._push(self._peek())

        # Arithmetic
        elif opcode == OpCode.OP_ADD:
            b = self._to_int(self._pop())
            a = self._to_int(self._pop())
            self._push(self._from_int(a + b))
        elif opcode == OpCode.OP_SUB:
            b = self._to_int(self._pop())
            a = self._to_int(self._pop())
            self._push(self._from_int(a - b))
        elif opcode == OpCode.OP_1ADD:
            a = self._to_int(self._pop())
            self._push(self._from_int(a + 1))
        elif opcode == OpCode.OP_1SUB:
            a = self._to_int(self._pop())
            self._push(self._from_int(a - 1))
        elif opcode == OpCode.OP_NEGATE:
            a = self._to_int(self._pop())
            self._push(self._from_int(-a))
        elif opcode == OpCode.OP_ABS:
            a = self._to_int(self._pop())
            self._push(self._from_int(abs(a)))
        elif opcode == OpCode.OP_NOT:
            a = self._to_int(self._pop())
            self._push(self._from_int(1 if a == 0 else 0))
        elif opcode == OpCode.OP_0NOTEQUAL:
            a = self._to_int(self._pop())
            self._push(self._from_int(0 if a == 0 else 1))

        # Comparison
        elif opcode == OpCode.OP_EQUAL:
            a = self._pop()
            b = self._pop()
            self._push(self._from_int(1 if a == b else 0))
        elif opcode == OpCode.OP_EQUALVERIFY:
            a = self._pop()
            b = self._pop()
            if a != b:
                raise ScriptError("OP_EQUALVERIFY failed", opcode)
        elif opcode == OpCode.OP_NUMEQUAL:
            b = self._to_int(self._pop())
            a = self._to_int(self._pop())
            self._push(self._from_int(1 if a == b else 0))
        elif opcode == OpCode.OP_NUMEQUALVERIFY:
            b = self._to_int(self._pop())
            a = self._to_int(self._pop())
            if a != b:
                raise ScriptError("OP_NUMEQUALVERIFY failed", opcode)
        elif opcode == OpCode.OP_NUMNOTEQUAL:
            b = self._to_int(self._pop())
            a = self._to_int(self._pop())
            self._push(self._from_int(1 if a != b else 0))
        elif opcode == OpCode.OP_LESSTHAN:
            b = self._to_int(self._pop())
            a = self._to_int(self._pop())
            self._push(self._from_int(1 if a < b else 0))
        elif opcode == OpCode.OP_GREATERTHAN:
            b = self._to_int(self._pop())
            a = self._to_int(self._pop())
            self._push(self._from_int(1 if a > b else 0))
        elif opcode == OpCode.OP_LESSTHANOREQUAL:
            b = self._to_int(self._pop())
            a = self._to_int(self._pop())
            self._push(self._from_int(1 if a <= b else 0))
        elif opcode == OpCode.OP_GREATERTHANOREQUAL:
            b = self._to_int(self._pop())
            a = self._to_int(self._pop())
            self._push(self._from_int(1 if a >= b else 0))
        elif opcode == OpCode.OP_MIN:
            b = self._to_int(self._pop())
            a = self._to_int(self._pop())
            self._push(self._from_int(min(a, b)))
        elif opcode == OpCode.OP_MAX:
            b = self._to_int(self._pop())
            a = self._to_int(self._pop())
            self._push(self._from_int(max(a, b)))
        elif opcode == OpCode.OP_WITHIN:
            max_val = self._to_int(self._pop())
            min_val = self._to_int(self._pop())
            x = self._to_int(self._pop())
            self._push(self._from_int(1 if min_val <= x < max_val else 0))

        # Crypto
        elif opcode == OpCode.OP_SHA256:
            data = self._pop()
            self._push(sha256(data))
        elif opcode == OpCode.OP_HASH256:
            data = self._pop()
            self._push(double_sha256(data))
        elif opcode == OpCode.OP_HASH160:
            data = self._pop()
            self._push(hash160(data))
        elif opcode == OpCode.OP_CHECKSIG:
            pubkey = self._pop()
            sig = self._pop()
            # 서명 검증
            valid = self._verify_signature(sig, pubkey)
            self._push(self._from_int(1 if valid else 0))
        elif opcode == OpCode.OP_CHECKSIGVERIFY:
            pubkey = self._pop()
            sig = self._pop()
            if not self._verify_signature(sig, pubkey):
                raise ScriptError("OP_CHECKSIGVERIFY failed", opcode)

        # NOPs (무시)
        elif opcode in (OpCode.OP_NOP1, OpCode.OP_NOP4, OpCode.OP_NOP5,
                        OpCode.OP_NOP6, OpCode.OP_NOP7, OpCode.OP_NOP8,
                        OpCode.OP_NOP9, OpCode.OP_NOP10):
            pass

        else:
            raise ScriptError(f"Unknown opcode: {hex(opcode)}", opcode)

    def _verify_signature(self, sig: bytes, pubkey: bytes) -> bool:
        """ECDSA 서명 검증"""
        if not sig or not pubkey:
            return False

        try:
            # DER 형식 서명에서 sighash type 제거 (마지막 1바이트)
            if len(sig) > 1:
                actual_sig = sig[:-1]
                # sighash_type = sig[-1]  # 향후 사용
            else:
                actual_sig = sig

            # 서명 검증 (message_hash, signature, public_key 순서)
            return verify(self.context.tx_hash, actual_sig, pubkey)
        except Exception:
            return False


def verify_script(
    script_sig: bytes,
    script_pubkey: bytes,
    tx_hash: bytes,
    input_index: int = 0
) -> bool:
    """
    스크립트 검증 헬퍼 함수
    """
    context = ScriptContext(tx_hash=tx_hash, input_index=input_index)
    interpreter = ScriptInterpreter(context)
    try:
        return interpreter.execute_combined(script_sig, script_pubkey)
    except ScriptError:
        return False
