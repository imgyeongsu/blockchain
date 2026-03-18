"""
Step 4.2: 채굴 모듈
- Coinbase TX 생성
- PoW 채굴
"""

import time
import struct
from typing import List, Optional, Callable
from dataclasses import dataclass

from ..core.block import Block, BlockHeader
from ..core.transaction import Transaction, TxInput, TxOutput
from ..crypto.hash import double_sha256
from ..crypto.address import address_to_pubkey_hash, validate_address, is_system_address, JACKPOT_POOL_ADDRESS, BURN_ADDRESS
from ..script.standard import create_p2pkh_script_pubkey
from ..constants import (
    BLOCK_REWARD,
    FEE_MINER_PERCENT,
    FEE_JACKPOT_PERCENT,
)
from .difficulty import compact_to_target


@dataclass
class MiningResult:
    """채굴 결과"""
    success: bool
    block: Optional[Block] = None
    nonce: int = 0
    hash_count: int = 0
    elapsed_time: float = 0.0


def create_coinbase_tx(
    block_height: int,
    miner_address: str,
    total_fees: int = 0,
    extra_data: bytes = b''
) -> Transaction:
    """
    Coinbase 트랜잭션 생성

    Args:
        block_height: 블록 높이 (BIP34)
        miner_address: 채굴자 주소
        total_fees: 총 수수료
        extra_data: 추가 데이터 (최대 100 bytes)

    Returns:
        coinbase_tx: Coinbase 트랜잭션
    """
    # Coinbase input (null outpoint)
    # BIP34: 블록 높이를 scriptSig에 포함
    height_bytes = block_height.to_bytes((block_height.bit_length() + 7) // 8, 'little')
    script_sig = bytes([len(height_bytes)]) + height_bytes + extra_data

    coinbase_input = TxInput(
        prev_tx_id=bytes(32),
        output_index=0xFFFFFFFF,
        script_sig=script_sig,
        sequence=0xFFFFFFFF
    )

    outputs = []

    # 수수료 분배 계산 (정수 연산)
    miner_fee = total_fees * FEE_MINER_PERCENT // 100
    jackpot_fee = total_fees * FEE_JACKPOT_PERCENT // 100
    burn_fee = total_fees - miner_fee - jackpot_fee  # 나머지는 burn

    # 1. 채굴자 보상 (블록 보상 + 채굴자 수수료)
    miner_total = BLOCK_REWARD + miner_fee
    if not is_system_address(miner_address):
        if not validate_address(miner_address):
            raise ValueError(f"Invalid miner address: {miner_address}")
        miner_pubkey_hash = address_to_pubkey_hash(miner_address)
        miner_script = create_p2pkh_script_pubkey(miner_pubkey_hash)
    else:
        miner_script = b''  # Genesis 등 특수 케이스

    outputs.append(TxOutput(
        jack_value=miner_total,
        script_pubkey=miner_script
    ))

    # 2. Jackpot Pool (수수료의 30%)
    if jackpot_fee > 0:
        outputs.append(TxOutput(
            jack_value=jackpot_fee,
            script_pubkey=b'JACKPOT_POOL'  # 특수 마커
        ))

    # 3. Burn (수수료의 20%) - 출력에 포함하지 않음 (실제 소각)
    # burn은 출력이 없어서 자동으로 소각됨

    return Transaction(
        version=1,
        inputs=[coinbase_input],
        outputs=outputs,
        locktime=0
    )


def create_block_template(
    prev_block: Block,
    miner_address: str,
    transactions: List[Transaction],
    difficulty_target: int
) -> Block:
    """
    블록 템플릿 생성 (채굴 준비)

    Args:
        prev_block: 이전 블록
        miner_address: 채굴자 주소
        transactions: 포함할 트랜잭션들 (coinbase 제외)
        difficulty_target: 난이도

    Returns:
        block_template: 채굴할 블록 (nonce=0)
    """
    # 수수료 계산
    total_fees = sum(tx.fee for tx in transactions if hasattr(tx, 'fee') and tx.fee)

    # Coinbase TX
    height = prev_block.header.timestamp + 1  # 임시 높이 (실제로는 외부에서 관리)
    coinbase_tx = create_coinbase_tx(
        block_height=height,
        miner_address=miner_address,
        total_fees=total_fees
    )

    # 전체 TX 리스트 (Coinbase 먼저)
    all_transactions = [coinbase_tx] + transactions

    # 블록 헤더
    header = BlockHeader(
        version=1,
        prev_block_hash=prev_block.get_hash(),
        merkle_root=bytes(32),  # 나중에 계산
        timestamp=int(time.time()),
        difficulty_target=difficulty_target,
        nonce=0
    )

    block = Block(header=header, transactions=all_transactions)

    # Merkle Root 계산
    block.header.merkle_root = block.calculate_merkle_root()

    return block


def mine_block(
    block: Block,
    max_nonce: int = 0xFFFFFFFF,
    callback: Callable[[int, int], bool] = None
) -> MiningResult:
    """
    블록 채굴 (PoW)

    Args:
        block: 채굴할 블록
        max_nonce: 최대 nonce (기본: 2^32 - 1)
        callback: 진행 콜백 (nonce, hash_count) -> continue?

    Returns:
        MiningResult: 채굴 결과
    """
    target = compact_to_target(block.header.difficulty_target)

    start_time = time.time()
    hash_count = 0

    for nonce in range(max_nonce + 1):
        block.header.nonce = nonce
        block._hash = None  # 캐시 무효화

        block_hash = block.get_hash()
        hash_int = int.from_bytes(block_hash, 'big')
        hash_count += 1

        # 성공!
        if hash_int < target:
            elapsed = time.time() - start_time
            return MiningResult(
                success=True,
                block=block,
                nonce=nonce,
                hash_count=hash_count,
                elapsed_time=elapsed
            )

        # 콜백
        if callback and hash_count % 10000 == 0:
            if not callback(nonce, hash_count):
                break

    elapsed = time.time() - start_time
    return MiningResult(
        success=False,
        nonce=nonce,
        hash_count=hash_count,
        elapsed_time=elapsed
    )


def update_block_timestamp(block: Block) -> Block:
    """타임스탬프 갱신 (채굴 중 사용)"""
    block.header.timestamp = int(time.time())
    block.header.merkle_root = block.calculate_merkle_root()
    block._hash = None
    return block


def estimate_mining_time(difficulty_target: int, hashrate: float) -> float:
    """
    예상 채굴 시간 계산

    Args:
        difficulty_target: compact 난이도
        hashrate: 해시레이트 (hashes/sec)

    Returns:
        estimated_seconds: 예상 소요 시간 (초)
    """
    target = compact_to_target(difficulty_target)
    probability = target / (2 ** 256)
    expected_hashes = 1 / probability
    return expected_hashes / hashrate
