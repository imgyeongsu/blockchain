"""
Step 5.2: 블록 검증
- 헤더 검증
- PoW 검증
- 트랜잭션 검증
"""

import time
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum

from ..core.block import Block, BlockHeader
from ..core.utxo import UTXOSet
from ..consensus.difficulty import compact_to_target, hash_meets_target
from ..constants import (
    MAX_BLOCK_SIZE,
    MAX_BLOCK_TIME_DRIFT,
    BLOCK_REWARD,
)
from .transaction import (
    validate_transaction,
    validate_coinbase,
    TxValidationResult,
    TxValidationError,
)


class BlockValidationError(Enum):
    """블록 검증 에러 코드"""
    VALID = 0
    BLOCK_TOO_LARGE = 1
    INVALID_HEADER = 2
    INVALID_MERKLE_ROOT = 3
    INVALID_POW = 4
    INVALID_TIMESTAMP = 5
    INVALID_DIFFICULTY = 6
    NO_COINBASE = 7
    INVALID_COINBASE = 8
    DUPLICATE_TX = 9
    INVALID_TX = 10
    PREV_BLOCK_NOT_FOUND = 11


@dataclass
class BlockValidationResult:
    """블록 검증 결과"""
    is_valid: bool
    error: BlockValidationError = BlockValidationError.VALID
    message: str = ""
    total_fees: int = 0


def validate_block_header(
    header: BlockHeader,
    prev_header: Optional[BlockHeader] = None,
    expected_difficulty: int = None
) -> BlockValidationResult:
    """
    블록 헤더 검증

    검증 항목:
    - PoW
    - 타임스탬프
    - 난이도
    """
    # PoW 검증
    if not header.verify_pow():
        return BlockValidationResult(
            is_valid=False,
            error=BlockValidationError.INVALID_POW,
            message="PoW verification failed"
        )

    # 타임스탬프 검증
    current_time = int(time.time())

    # 미래 시간 제한 (2시간)
    if header.timestamp > current_time + MAX_BLOCK_TIME_DRIFT:
        return BlockValidationResult(
            is_valid=False,
            error=BlockValidationError.INVALID_TIMESTAMP,
            message=f"Block timestamp too far in future"
        )

    # 이전 블록보다 이후여야 함
    if prev_header and header.timestamp <= prev_header.timestamp:
        return BlockValidationResult(
            is_valid=False,
            error=BlockValidationError.INVALID_TIMESTAMP,
            message="Block timestamp must be greater than previous"
        )

    # 난이도 검증
    if expected_difficulty is not None and header.difficulty_target != expected_difficulty:
        return BlockValidationResult(
            is_valid=False,
            error=BlockValidationError.INVALID_DIFFICULTY,
            message=f"Invalid difficulty: expected {expected_difficulty}, got {header.difficulty_target}"
        )

    return BlockValidationResult(is_valid=True)


def validate_block_structure(block: Block) -> BlockValidationResult:
    """
    블록 구조 검증

    검증 항목:
    - 크기 제한
    - Merkle Root
    - Coinbase 존재
    - 중복 TX 없음
    """
    # 크기 검증
    block_size = block.size()
    if block_size > MAX_BLOCK_SIZE:
        return BlockValidationResult(
            is_valid=False,
            error=BlockValidationError.BLOCK_TOO_LARGE,
            message=f"Block size {block_size} exceeds max {MAX_BLOCK_SIZE}"
        )

    # Merkle Root 검증
    if not block.verify_merkle_root():
        return BlockValidationResult(
            is_valid=False,
            error=BlockValidationError.INVALID_MERKLE_ROOT,
            message="Merkle root mismatch"
        )

    # Coinbase 검증 (첫 번째 TX)
    if not block.transactions:
        return BlockValidationResult(
            is_valid=False,
            error=BlockValidationError.NO_COINBASE,
            message="Block has no transactions"
        )

    if not block.transactions[0].is_coinbase():
        return BlockValidationResult(
            is_valid=False,
            error=BlockValidationError.NO_COINBASE,
            message="First transaction is not coinbase"
        )

    # 나머지 TX 중 Coinbase가 있으면 안됨
    for tx in block.transactions[1:]:
        if tx.is_coinbase():
            return BlockValidationResult(
                is_valid=False,
                error=BlockValidationError.INVALID_TX,
                message="Multiple coinbase transactions"
            )

    # 중복 TX 검증
    seen_txids = set()
    for tx in block.transactions:
        txid = tx.get_txid()
        if txid in seen_txids:
            return BlockValidationResult(
                is_valid=False,
                error=BlockValidationError.DUPLICATE_TX,
                message="Duplicate transaction"
            )
        seen_txids.add(txid)

    return BlockValidationResult(is_valid=True)


def validate_block_transactions(
    block: Block,
    utxo_set: UTXOSet,
    block_height: int,
    expected_reward: int = BLOCK_REWARD,
    blockchain = None
) -> BlockValidationResult:
    """
    블록 내 트랜잭션 검증

    검증 항목:
    - 각 TX 유효성
    - Coinbase 보상
    - 수수료 합계

    Args:
        block: 검증할 블록
        utxo_set: UTXO Set
        block_height: 블록 높이
        expected_reward: 예상 블록 보상
        blockchain: Blockchain 참조 (LOTTO_CLAIM 검증용, optional)
    """
    total_fees = 0

    # 일반 TX 검증 (Coinbase 제외)
    for tx in block.transactions[1:]:
        result = validate_transaction(tx, utxo_set, block_height, blockchain)
        if not result.is_valid:
            return BlockValidationResult(
                is_valid=False,
                error=BlockValidationError.INVALID_TX,
                message=f"Invalid TX: {result.message}"
            )
        total_fees += result.fee

    # Coinbase 검증
    coinbase = block.transactions[0]
    coinbase_result = validate_coinbase(
        coinbase,
        block_height,
        expected_reward,
        total_fees
    )
    if not coinbase_result.is_valid:
        return BlockValidationResult(
            is_valid=False,
            error=BlockValidationError.INVALID_COINBASE,
            message=f"Invalid coinbase: {coinbase_result.message}"
        )

    return BlockValidationResult(
        is_valid=True,
        total_fees=total_fees
    )


def validate_block(
    block: Block,
    utxo_set: UTXOSet,
    block_height: int,
    prev_header: Optional[BlockHeader] = None,
    expected_difficulty: int = None,
    expected_reward: int = BLOCK_REWARD,
    blockchain = None
) -> BlockValidationResult:
    """
    전체 블록 검증 (통합)

    Args:
        block: 검증할 블록
        utxo_set: UTXO Set
        block_height: 블록 높이
        prev_header: 이전 블록 헤더
        expected_difficulty: 예상 난이도
        expected_reward: 예상 블록 보상
        blockchain: Blockchain 참조 (LOTTO_CLAIM 검증용, optional)
    """
    # 1. 헤더 검증
    result = validate_block_header(
        block.header,
        prev_header,
        expected_difficulty
    )
    if not result.is_valid:
        return result

    # 2. 구조 검증
    result = validate_block_structure(block)
    if not result.is_valid:
        return result

    # 3. 트랜잭션 검증
    result = validate_block_transactions(
        block,
        utxo_set,
        block_height,
        expected_reward,
        blockchain
    )
    if not result.is_valid:
        return result

    return BlockValidationResult(
        is_valid=True,
        total_fees=result.total_fees
    )


def quick_validate_header(header: BlockHeader) -> bool:
    """
    빠른 헤더 검증 (네트워크 수신 시)
    - PoW만 확인
    """
    return header.verify_pow()


def validate_header_chain(
    headers: list,
    start_header: BlockHeader = None
) -> BlockValidationResult:
    """
    헤더 체인 검증 (SPV용)

    검증 항목:
    - 연결성
    - PoW
    - 난이도 규칙
    """
    prev_header = start_header

    for i, header in enumerate(headers):
        # 연결성 검증
        if prev_header:
            expected_prev_hash = prev_header.get_hash()
            if header.prev_block_hash != expected_prev_hash:
                return BlockValidationResult(
                    is_valid=False,
                    error=BlockValidationError.PREV_BLOCK_NOT_FOUND,
                    message=f"Header {i} not connected to previous"
                )

        # 헤더 검증
        result = validate_block_header(header, prev_header)
        if not result.is_valid:
            return BlockValidationResult(
                is_valid=False,
                error=result.error,
                message=f"Header {i}: {result.message}"
            )

        prev_header = header

    return BlockValidationResult(is_valid=True)
