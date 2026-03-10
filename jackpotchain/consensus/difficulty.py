"""
Step 4.1: 난이도 조정
- 50블록마다 조정
- 목표: 30초/블록
"""

from ..constants import (
    DIFFICULTY_ADJUSTMENT_INTERVAL,
    TARGET_BLOCK_TIME,
    INITIAL_DIFFICULTY,
    MAX_DIFFICULTY_CHANGE,
)


def compact_to_target(compact: int) -> int:
    """
    Compact 난이도 → 256비트 target
    compact format: 0x1d00ffff
    - 첫 바이트: 지수
    - 나머지 3바이트: 계수
    """
    exponent = compact >> 24
    coefficient = compact & 0x00ffffff

    if exponent <= 3:
        target = coefficient >> (8 * (3 - exponent))
    else:
        target = coefficient << (8 * (exponent - 3))

    return target


def target_to_compact(target: int) -> int:
    """
    256비트 target → Compact 난이도
    """
    if target == 0:
        return 0

    # 바이트 수 계산
    target_bytes = target.bit_length() // 8 + 1
    exponent = target_bytes

    # 상위 3바이트 추출
    if exponent <= 3:
        coefficient = target << (8 * (3 - exponent))
    else:
        coefficient = target >> (8 * (exponent - 3))

    # 부호 비트 처리 (coefficient의 최상위 비트가 1이면 지수 증가)
    if coefficient & 0x00800000:
        coefficient >>= 8
        exponent += 1

    return (exponent << 24) | (coefficient & 0x00ffffff)


def calculate_difficulty_ratio(target: int) -> float:
    """
    난이도 비율 계산 (Bitcoin 스타일)
    difficulty = max_target / current_target
    """
    max_target = compact_to_target(INITIAL_DIFFICULTY)
    if target == 0:
        return float('inf')
    return max_target / target


def calculate_new_difficulty(
    prev_difficulty: int,
    actual_time: int,
    expected_time: int = None
) -> int:
    """
    새 난이도 계산

    Args:
        prev_difficulty: 이전 compact 난이도
        actual_time: 실제 걸린 시간 (초)
        expected_time: 예상 시간 (기본: DIFFICULTY_ADJUSTMENT_INTERVAL * TARGET_BLOCK_TIME)

    Returns:
        new_difficulty: 새 compact 난이도
    """
    if expected_time is None:
        expected_time = DIFFICULTY_ADJUSTMENT_INTERVAL * TARGET_BLOCK_TIME

    # 비율 계산
    ratio = actual_time / expected_time

    # 최대 변화율 제한 (x4 또는 /4)
    if ratio < 1 / MAX_DIFFICULTY_CHANGE:
        ratio = 1 / MAX_DIFFICULTY_CHANGE
    elif ratio > MAX_DIFFICULTY_CHANGE:
        ratio = MAX_DIFFICULTY_CHANGE

    # 새 target 계산
    prev_target = compact_to_target(prev_difficulty)
    new_target = int(prev_target * ratio)

    # 최소/최대 target 제한
    max_target = compact_to_target(INITIAL_DIFFICULTY)
    if new_target > max_target:
        new_target = max_target
    if new_target <= 0:
        new_target = 1

    return target_to_compact(new_target)


def get_next_difficulty(chain_tip_height: int, get_block_func) -> int:
    """
    다음 블록의 난이도 결정

    Args:
        chain_tip_height: 현재 체인 끝 높이
        get_block_func: 블록 조회 함수 (height -> Block)

    Returns:
        next_difficulty: 다음 블록의 compact 난이도
    """
    next_height = chain_tip_height + 1

    # 조정 블록이 아니면 이전 난이도 유지
    if next_height % DIFFICULTY_ADJUSTMENT_INTERVAL != 0:
        current_block = get_block_func(chain_tip_height)
        return current_block.header.difficulty_target

    # 조정 블록: 지난 INTERVAL 블록의 시간 계산
    current_block = get_block_func(chain_tip_height)
    interval_start_block = get_block_func(chain_tip_height - DIFFICULTY_ADJUSTMENT_INTERVAL + 1)

    actual_time = current_block.header.timestamp - interval_start_block.header.timestamp

    return calculate_new_difficulty(
        current_block.header.difficulty_target,
        actual_time
    )


def verify_difficulty(block_difficulty: int, expected_difficulty: int) -> bool:
    """난이도 검증"""
    return block_difficulty == expected_difficulty


def hash_meets_target(block_hash: bytes, target: int) -> bool:
    """해시가 target 이하인지 확인"""
    hash_int = int.from_bytes(block_hash, 'big')
    return hash_int < target


def difficulty_to_hashrate(difficulty: float, block_time: int = TARGET_BLOCK_TIME) -> float:
    """
    난이도를 해시레이트로 변환 (hashes/second)
    """
    # 2^256 / target = hashes needed
    # hashes_needed / block_time = hashrate
    max_target = compact_to_target(INITIAL_DIFFICULTY)
    target = max_target / difficulty
    hashes_needed = 2**256 / target
    return hashes_needed / block_time
