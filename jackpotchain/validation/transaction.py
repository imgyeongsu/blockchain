"""
Step 5.1: 트랜잭션 검증
- 구조 검증
- 서명 검증
- 잔액 검증
"""

from typing import List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum

from ..core.transaction import Transaction, TxInput, TxOutput
from ..core.utxo import UTXO, UTXOSet
from ..script.interpreter import verify_script
from ..script.standard import is_p2pkh_script_pubkey, is_op_return_script
from ..crypto.hash import double_sha256, sha256
from ..constants import (
    MAX_TX_SIZE,
    TX_VERSION_TRANSFER,
    TX_VERSION_EXCHANGE,
    TX_VERSION_COMMIT,
    TX_VERSION_GACHA_REVEAL,
    COINBASE_MATURITY,
)

if TYPE_CHECKING:
    from ..consensus.chain import Blockchain


class TxValidationError(Enum):
    """검증 에러 코드"""
    VALID = 0
    TX_TOO_LARGE = 1
    EMPTY_INPUTS = 2
    EMPTY_OUTPUTS = 3
    DUPLICATE_INPUT = 4
    INVALID_OUTPOINT = 5
    INPUT_NOT_FOUND = 6
    IMMATURE_COINBASE = 7
    INSUFFICIENT_FUNDS = 8
    NEGATIVE_OUTPUT = 9
    INVALID_SCRIPT = 10
    INVALID_SIGNATURE = 11
    INVALID_VERSION = 12
    DUST_OUTPUT = 13
    INVALID_FEE = 14
    INVALID_PAYOUT = 19


@dataclass
class TxValidationResult:
    """검증 결과"""
    is_valid: bool
    error: TxValidationError = TxValidationError.VALID
    message: str = ""
    fee: int = 0


def validate_tx_structure(tx: Transaction) -> TxValidationResult:
    """트랜잭션 구조 검증"""
    tx_size = len(tx.serialize())
    if tx_size > MAX_TX_SIZE:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.TX_TOO_LARGE,
            message=f"TX size {tx_size} exceeds max {MAX_TX_SIZE}"
        )

    if tx.is_coinbase():
        if len(tx.outputs) < 1:
            return TxValidationResult(
                is_valid=False,
                error=TxValidationError.EMPTY_OUTPUTS,
                message="Coinbase must have at least 1 output"
            )
        return TxValidationResult(is_valid=True)

    if not tx.inputs:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.EMPTY_INPUTS,
            message="TX has no inputs"
        )

    if not tx.outputs:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.EMPTY_OUTPUTS,
            message="TX has no outputs"
        )

    seen_outpoints = set()
    for inp in tx.inputs:
        outpoint = (inp.prev_tx_id, inp.output_index)
        if outpoint in seen_outpoints:
            return TxValidationResult(
                is_valid=False,
                error=TxValidationError.DUPLICATE_INPUT,
                message="Duplicate input"
            )
        seen_outpoints.add(outpoint)

    valid_versions = {
        TX_VERSION_TRANSFER,
        TX_VERSION_EXCHANGE,
        TX_VERSION_COMMIT,
        TX_VERSION_GACHA_REVEAL,  # deprecated but still valid
    }
    if tx.version not in valid_versions:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.INVALID_VERSION,
            message=f"Invalid TX version: {tx.version}"
        )

    for out in tx.outputs:
        if out.jack_value < 0:
            return TxValidationResult(
                is_valid=False,
                error=TxValidationError.NEGATIVE_OUTPUT,
                message="Negative output value"
            )

    return TxValidationResult(is_valid=True)


def is_jackpot_pool_script(script: bytes) -> bool:
    """잭팟 풀 특수 스크립트인지 확인"""
    return script == b'JACKPOT_POOL'


def validate_tx_scripts(
    tx: Transaction,
    utxo_set: UTXOSet,
    current_height: int,
    blockchain: 'Blockchain' = None
) -> TxValidationResult:
    """트랜잭션 스크립트 검증"""
    if tx.is_coinbase():
        return TxValidationResult(is_valid=True)

    for idx, inp in enumerate(tx.inputs):
        utxo = utxo_set.get_utxo(inp.prev_tx_id, inp.output_index)
        if utxo is None:
            return TxValidationResult(
                is_valid=False,
                error=TxValidationError.INPUT_NOT_FOUND,
                message=f"Input {idx} UTXO not found"
            )

        if utxo.is_coinbase and not utxo.is_mature(current_height, COINBASE_MATURITY):
            return TxValidationResult(
                is_valid=False,
                error=TxValidationError.IMMATURE_COINBASE,
                message=f"Input {idx} coinbase not mature"
            )

        if is_op_return_script(utxo.output.script_pubkey):
            return TxValidationResult(
                is_valid=False,
                error=TxValidationError.INVALID_SCRIPT,
                message="Cannot spend OP_RETURN output"
            )

        # 잭팟 풀 UTXO는 일반 TX에서 지출 불가
        # (자동 지급은 coinbase-style로 채굴자가 생성)
        if is_jackpot_pool_script(utxo.output.script_pubkey):
            return TxValidationResult(
                is_valid=False,
                error=TxValidationError.INVALID_SCRIPT,
                message="Jackpot pool UTXO cannot be spent directly"
            )

        sig_hash = tx.get_signature_hash(idx, utxo.output.script_pubkey)

        if not verify_script(
            script_sig=inp.script_sig,
            script_pubkey=utxo.output.script_pubkey,
            tx_hash=sig_hash,
            input_index=idx
        ):
            return TxValidationResult(
                is_valid=False,
                error=TxValidationError.INVALID_SIGNATURE,
                message=f"Input {idx} signature verification failed"
            )

    return TxValidationResult(is_valid=True)


def validate_tx_amounts(
    tx: Transaction,
    utxo_set: UTXOSet
) -> TxValidationResult:
    """트랜잭션 금액 검증"""
    if tx.is_coinbase():
        return TxValidationResult(is_valid=True)

    total_input = 0
    for inp in tx.inputs:
        utxo = utxo_set.get_utxo(inp.prev_tx_id, inp.output_index)
        if utxo is None:
            return TxValidationResult(
                is_valid=False,
                error=TxValidationError.INPUT_NOT_FOUND,
                message="Input UTXO not found"
            )
        total_input += utxo.output.jack_value

    total_output = 0
    for out in tx.outputs:
        if not is_op_return_script(out.script_pubkey):
            total_output += out.jack_value

    if total_input < total_output:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.INSUFFICIENT_FUNDS,
            message=f"Input {total_input} < Output {total_output}"
        )

    fee = total_input - total_output

    return TxValidationResult(
        is_valid=True,
        fee=fee
    )


def validate_transaction(
    tx: Transaction,
    utxo_set: UTXOSet,
    current_height: int,
    blockchain: 'Blockchain' = None
) -> TxValidationResult:
    """전체 트랜잭션 검증 (통합)"""
    result = validate_tx_structure(tx)
    if not result.is_valid:
        return result

    if tx.is_coinbase():
        return TxValidationResult(is_valid=True)

    result = validate_tx_scripts(tx, utxo_set, current_height, blockchain)
    if not result.is_valid:
        return result

    result = validate_tx_amounts(tx, utxo_set)
    if not result.is_valid:
        return result

    return TxValidationResult(
        is_valid=True,
        fee=result.fee
    )


def validate_coinbase(
    tx: Transaction,
    block_height: int,
    expected_reward: int,
    total_fees: int
) -> TxValidationResult:
    """Coinbase 트랜잭션 검증"""
    if not tx.is_coinbase():
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.INVALID_SCRIPT,
            message="Not a coinbase transaction"
        )

    inp = tx.inputs[0]
    if inp.prev_tx_id != bytes(32) or inp.output_index != 0xFFFFFFFF:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.INVALID_OUTPOINT,
            message="Invalid coinbase outpoint"
        )

    total_output = sum(out.jack_value for out in tx.outputs)
    max_reward = expected_reward + total_fees

    if total_output > max_reward:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.INVALID_FEE,
            message=f"Coinbase output {total_output} exceeds max {max_reward}"
        )

    script_sig = inp.script_sig
    if len(script_sig) < 1:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.INVALID_SCRIPT,
            message="Coinbase scriptSig too short"
        )

    height_len = script_sig[0]
    if len(script_sig) < 1 + height_len:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.INVALID_SCRIPT,
            message="Invalid height encoding in coinbase"
        )

    encoded_height = int.from_bytes(script_sig[1:1+height_len], 'little')
    if encoded_height != block_height:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.INVALID_SCRIPT,
            message=f"Coinbase height {encoded_height} != block height {block_height}"
        )

    return TxValidationResult(is_valid=True)
