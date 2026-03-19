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
from ..script.standard import is_p2pkh_script_pubkey, is_op_return_script, is_claim_script, extract_claim_data
from ..crypto.hash import double_sha256, sha256
from ..constants import (
    MAX_TX_SIZE,
    TX_VERSION_TRANSFER,
    TX_VERSION_EXCHANGE,
    TX_VERSION_COMMIT,
    TX_VERSION_REVEAL,
    TX_VERSION_LOTTO_CLAIM,
    COINBASE_MATURITY,
    LOTTO_DIGIT_COUNT,
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
    # Claim 검증 에러
    INVALID_CLAIM_DATA = 15
    INVALID_COMMIT_HASH = 16
    COMMIT_NOT_FOUND = 17
    INVALID_CLAIM_TIMING = 18
    INVALID_PAYOUT = 19


@dataclass
class TxValidationResult:
    """검증 결과"""
    is_valid: bool
    error: TxValidationError = TxValidationError.VALID
    message: str = ""
    fee: int = 0  # 유효한 경우 수수료


def validate_tx_structure(tx: Transaction) -> TxValidationResult:
    """
    트랜잭션 구조 검증 (UTXO 불필요)

    검증 항목:
    - 크기 제한
    - 입출력 존재
    - 중복 입력 없음
    - 버전 유효
    """
    # 크기 검증
    tx_size = len(tx.serialize())
    if tx_size > MAX_TX_SIZE:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.TX_TOO_LARGE,
            message=f"TX size {tx_size} exceeds max {MAX_TX_SIZE}"
        )

    # Coinbase 특별 처리
    if tx.is_coinbase():
        if len(tx.outputs) < 1:
            return TxValidationResult(
                is_valid=False,
                error=TxValidationError.EMPTY_OUTPUTS,
                message="Coinbase must have at least 1 output"
            )
        return TxValidationResult(is_valid=True)

    # 입력 검증
    if not tx.inputs:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.EMPTY_INPUTS,
            message="TX has no inputs"
        )

    # 출력 검증
    if not tx.outputs:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.EMPTY_OUTPUTS,
            message="TX has no outputs"
        )

    # 중복 입력 검증
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

    # 버전 검증
    valid_versions = {
        TX_VERSION_TRANSFER,
        TX_VERSION_EXCHANGE,
        TX_VERSION_COMMIT,
        TX_VERSION_REVEAL,      # deprecated but still valid
        TX_VERSION_LOTTO_CLAIM,
    }
    if tx.version not in valid_versions:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.INVALID_VERSION,
            message=f"Invalid TX version: {tx.version}"
        )

    # 출력 값 검증
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
    """
    트랜잭션 스크립트 검증

    검증 항목:
    - 입력 UTXO 존재
    - Coinbase 성숙도
    - 서명 유효성
    - LOTTO_CLAIM TX는 잭팟 풀에서 서명 없이 지출 허용 + claim 데이터 검증
    """
    if tx.is_coinbase():
        return TxValidationResult(is_valid=True)

    # LOTTO_CLAIM TX는 별도 검증
    is_lotto_claim = tx.version == TX_VERSION_LOTTO_CLAIM
    lotto_claim_validated = False

    for idx, inp in enumerate(tx.inputs):
        # UTXO 조회
        utxo = utxo_set.get_utxo(inp.prev_tx_id, inp.output_index)
        if utxo is None:
            return TxValidationResult(
                is_valid=False,
                error=TxValidationError.INPUT_NOT_FOUND,
                message=f"Input {idx} UTXO not found"
            )

        # Coinbase 성숙도
        if utxo.is_coinbase and not utxo.is_mature(current_height, COINBASE_MATURITY):
            return TxValidationResult(
                is_valid=False,
                error=TxValidationError.IMMATURE_COINBASE,
                message=f"Input {idx} coinbase not mature"
            )

        # OP_RETURN은 지출 불가
        if is_op_return_script(utxo.output.script_pubkey):
            return TxValidationResult(
                is_valid=False,
                error=TxValidationError.INVALID_SCRIPT,
                message="Cannot spend OP_RETURN output"
            )

        # 잭팟 풀 UTXO는 LOTTO_CLAIM TX에서만 서명 없이 지출 허용
        if is_jackpot_pool_script(utxo.output.script_pubkey):
            if is_lotto_claim:
                # Claim 데이터 검증 (blockchain 있을 때만)
                if blockchain and not lotto_claim_validated:
                    result = validate_lotto_claim(tx, current_height, blockchain)
                    if not result.is_valid:
                        return result
                    lotto_claim_validated = True
                continue  # 서명 검증 스킵
            else:
                return TxValidationResult(
                    is_valid=False,
                    error=TxValidationError.INVALID_SCRIPT,
                    message="Jackpot pool can only be spent by LOTTO_CLAIM TX"
                )

        # 서명 해시 계산 (Bitcoin SIGHASH_ALL 방식)
        sig_hash = tx.get_signature_hash(idx, utxo.output.script_pubkey)

        # 스크립트 검증
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
    """
    트랜잭션 금액 검증

    검증 항목:
    - 입력 >= 출력
    - 수수료 계산
    """
    if tx.is_coinbase():
        return TxValidationResult(is_valid=True)

    # 입력 합계
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

    # 출력 합계 (OP_RETURN 제외)
    total_output = 0
    for out in tx.outputs:
        if not is_op_return_script(out.script_pubkey):
            total_output += out.jack_value

    # 입력 >= 출력
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
    """
    전체 트랜잭션 검증 (통합)

    Args:
        tx: 검증할 트랜잭션
        utxo_set: UTXO Set
        current_height: 현재 블록 높이
        blockchain: Blockchain 참조 (LOTTO_CLAIM 검증용, optional)
    """
    # 1. 구조 검증
    result = validate_tx_structure(tx)
    if not result.is_valid:
        return result

    # Coinbase는 별도 검증
    if tx.is_coinbase():
        return TxValidationResult(is_valid=True)

    # 2. 스크립트 검증
    result = validate_tx_scripts(tx, utxo_set, current_height, blockchain)
    if not result.is_valid:
        return result

    # 3. 금액 검증
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
    """
    Coinbase 트랜잭션 검증

    검증 항목:
    - null outpoint
    - 보상 + 수수료 이하
    - BIP34 (높이 포함)
    """
    if not tx.is_coinbase():
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.INVALID_SCRIPT,
            message="Not a coinbase transaction"
        )

    # 입력 검증 (null outpoint)
    inp = tx.inputs[0]
    if inp.prev_tx_id != bytes(32) or inp.output_index != 0xFFFFFFFF:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.INVALID_OUTPOINT,
            message="Invalid coinbase outpoint"
        )

    # 보상 검증
    total_output = sum(out.jack_value for out in tx.outputs)
    max_reward = expected_reward + total_fees

    if total_output > max_reward:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.INVALID_FEE,
            message=f"Coinbase output {total_output} exceeds max {max_reward}"
        )

    # BIP34: 블록 높이 확인 (scriptSig 첫 바이트)
    script_sig = inp.script_sig
    if len(script_sig) < 1:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.INVALID_SCRIPT,
            message="Coinbase scriptSig too short"
        )

    # 높이 추출
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


def validate_lotto_claim(
    tx: Transaction,
    current_height: int,
    blockchain: 'Blockchain'
) -> TxValidationResult:
    """
    LOTTO_CLAIM TX 검증

    검증 항목:
    1. claim script 파싱 (commit_hash, nonce, chosen_numbers)
    2. SHA256(nonce + numbers) == commit_hash (위조 방지)
    3. commit TX 존재 확인 (인덱스 조회)
    4. claim 타이밍 검증 (N+18 ~ N+68)
    5. prize 계산 및 payout 검증
    """
    from ..gacha.commit_reveal import (
        is_claim_valid,
        get_comparison_heights,
        calculate_result_digits,
        count_matches,
        determine_prize,
        calculate_payout,
    )

    # 1. Claim script 찾기 및 파싱
    claim_data = None
    for output in tx.outputs:
        if is_claim_script(output.script_pubkey):
            claim_data = extract_claim_data(output.script_pubkey)
            break

    if claim_data is None:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.INVALID_CLAIM_DATA,
            message="No valid claim script in outputs"
        )

    commit_hash, nonce, chosen_numbers = claim_data

    # 2. commit_hash 검증: SHA256(nonce + numbers) == commit_hash
    numbers_bytes = bytes(chosen_numbers)
    expected_hash = sha256(nonce + numbers_bytes)

    if expected_hash != commit_hash:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.INVALID_COMMIT_HASH,
            message="Commit hash mismatch: nonce + numbers doesn't match"
        )

    # 3. Commit TX 존재 확인
    commit_info = blockchain.get_commit_info(commit_hash)
    if commit_info is None:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.COMMIT_NOT_FOUND,
            message="Commit TX not found in blockchain"
        )

    commit_height = commit_info.block_height

    # 4. Claim 타이밍 검증 (N+18 ~ N+68)
    valid, reason = is_claim_valid(commit_height, current_height)
    if not valid:
        return TxValidationResult(
            is_valid=False,
            error=TxValidationError.INVALID_CLAIM_TIMING,
            message=f"Invalid claim timing: {reason}"
        )

    # 5. Prize 계산
    comparison_heights = get_comparison_heights(commit_height)

    # 비교 블록 해시 수집
    block_hashes = []
    for h in comparison_heights:
        block = blockchain.get_block_by_height(h)
        if block:
            block_hashes.append(block.get_hash())
        else:
            return TxValidationResult(
                is_valid=False,
                error=TxValidationError.INVALID_CLAIM_DATA,
                message=f"Comparison block at height {h} not found"
            )

    # 당첨 결과 계산
    result_digits = calculate_result_digits(block_hashes)
    matches = count_matches(chosen_numbers, result_digits)
    prize = determine_prize(matches)

    # 6. Payout 검증
    # 잭팟 풀 잔액 조회 (1등 상금 계산용)
    pool_utxos = blockchain.utxo_set.get_pool_utxos()
    pool_balance = sum(utxo.output.jack_value for utxo in pool_utxos)

    # calculate_payout은 (jack_payout, pot_payout) 튜플 반환
    expected_jack, expected_pot = calculate_payout(prize, pool_snapshot=pool_balance)

    # TX에서 실제 payout 추출
    actual_jack = 0
    actual_pot = 0
    from ..constants import ASSET_ID_POT
    for output in tx.outputs:
        # OP_RETURN과 JACKPOT_POOL 제외한 일반 output이 payout
        if not is_op_return_script(output.script_pubkey) and output.script_pubkey != b'JACKPOT_POOL':
            actual_jack += output.jack_value
            actual_pot += output.assets.get(ASSET_ID_POT, 0) if hasattr(output, 'assets') and output.assets else 0

    # 2~5등: JACK 고정 금액 검증
    if prize.value > 0 and prize.value < 6:
        if actual_jack < expected_jack:
            return TxValidationResult(
                is_valid=False,
                error=TxValidationError.INVALID_PAYOUT,
                message=f"JACK payout mismatch: expected >= {expected_jack}, got {actual_jack}"
            )

    # 6등: POT mint 검증
    if prize.value == 6:
        if actual_pot != expected_pot:
            return TxValidationResult(
                is_valid=False,
                error=TxValidationError.INVALID_PAYOUT,
                message=f"POT payout mismatch: expected {expected_pot}, got {actual_pot}"
            )

    return TxValidationResult(is_valid=True)
