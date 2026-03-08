"""
로또 시스템: Commit-Claim 패턴 (16-2 Final 기준)

- Commit: 6자리 hex 숫자 배열 제출 (각 0x0 ~ 0xf)
- Claim: N+30 이후, 6개 블록 해시와 비교하여 등급 판정
- 등급: 일치 개수에 따라 1~6등/꽝
"""

import os
from typing import Optional, Tuple, List
from dataclasses import dataclass, field
from enum import Enum

from ..crypto.hash import sha256
from ..constants import (
    LOTTO_DIGIT_COUNT,
    LOTTO_DIGIT_BASE,
    LOTTO_COMPARISON_OFFSETS,
    LOTTO_MIN_CLAIM_GAP,
    LOTTO_MAX_CLAIM_GAP,
    LOTTO_PRIZE_1ST_RATIO,
    LOTTO_PRIZE_2ND,
    LOTTO_PRIZE_3RD,
    LOTTO_PRIZE_4TH,
    LOTTO_PRIZE_5TH,
    LOTTO_PRIZE_6TH_POT,
    COIN,
)


class CommitStatus(Enum):
    """커밋 상태"""
    PENDING = "pending"          # Claim 대기 중 (N+30 이전)
    CLAIMABLE = "claimable"      # Claim 가능 (N+30 ~ N+80)
    CLAIMED = "claimed"          # Claim 완료
    EXPIRED = "expired"          # 기한 만료 (N+80 이후)
    INVALID = "invalid"          # 무효


class LottoPrize(Enum):
    """등급"""
    JACKPOT = 1      # 6개 일치 - 잭팟 풀 50%
    SECOND = 2       # 5개 일치 - 100,000 JACK
    THIRD = 3        # 4개 일치 - 20,000 JACK
    FOURTH = 4       # 3개 일치 - 2,000 JACK
    FIFTH = 5        # 2개 일치 - 300 JACK
    SIXTH = 6        # 1개 일치 - 1 POT 재지급
    NONE = 0         # 0개 일치 - 꽝


@dataclass
class CommitRecord:
    """커밋 기록"""
    commit_hash: bytes                      # SHA256(nonce || chosen_numbers)
    player_address: str
    commit_height: int                      # Commit 블록 높이
    commit_tx_id: bytes
    chosen_numbers: List[int]               # 6자리 숫자 [0x0~0xf, ...]
    pool_snapshot: int = 0                  # Commit 시점 잭팟 풀 잔액 (1등 보상 계산용)

    # Claim 정보 (나중에 채움)
    claim_height: Optional[int] = None
    claim_tx_id: Optional[bytes] = None
    nonce: Optional[bytes] = None
    result_digits: Optional[List[int]] = None
    matches: int = 0
    prize: LottoPrize = LottoPrize.NONE
    payout: int = 0


def generate_commit(chosen_numbers: List[int] = None) -> Tuple[bytes, bytes, List[int]]:
    """
    Commit 생성

    Args:
        chosen_numbers: 6자리 숫자 배열 (각 0~15), None이면 랜덤

    Returns:
        (commit_hash, nonce, chosen_numbers)
    """
    # 랜덤 nonce (32 bytes)
    nonce = os.urandom(32)

    # 랜덤 숫자 (없으면)
    if chosen_numbers is None:
        chosen_numbers = [
            int.from_bytes(os.urandom(1), 'big') % LOTTO_DIGIT_BASE
            for _ in range(LOTTO_DIGIT_COUNT)
        ]

    # 유효성 검사
    if len(chosen_numbers) != LOTTO_DIGIT_COUNT:
        raise ValueError(f"Must have exactly {LOTTO_DIGIT_COUNT} digits")
    for d in chosen_numbers:
        if not (0 <= d < LOTTO_DIGIT_BASE):
            raise ValueError(f"Each digit must be 0~{LOTTO_DIGIT_BASE - 1}")

    # commit_hash = SHA256(nonce || chosen_numbers)
    data = nonce + bytes(chosen_numbers)
    commit_hash = sha256(data)

    return commit_hash, nonce, chosen_numbers


def verify_commit(commit_hash: bytes, nonce: bytes, chosen_numbers: List[int]) -> bool:
    """Commit 검증"""
    data = nonce + bytes(chosen_numbers)
    expected_hash = sha256(data)
    return commit_hash == expected_hash


def extract_result_digit(block_hash: bytes) -> int:
    """
    블록 해시에서 결과 숫자 추출

    블록 해시의 마지막 hex 자리 (마지막 바이트의 하위 4비트)

    Args:
        block_hash: 32바이트 블록 해시

    Returns:
        result_digit: 0~15 (hex 0x0 ~ 0xf)
    """
    return block_hash[-1] & 0x0f


def calculate_result_digits(comparison_block_hashes: List[bytes]) -> List[int]:
    """
    6개 비교 블록 해시에서 결과 숫자 배열 추출

    Args:
        comparison_block_hashes: [Block(N+5).hash, Block(N+10).hash, ..., Block(N+30).hash]

    Returns:
        result_digits: [d1, d2, d3, d4, d5, d6] 각 0~15
    """
    if len(comparison_block_hashes) != LOTTO_DIGIT_COUNT:
        raise ValueError(f"Need exactly {LOTTO_DIGIT_COUNT} block hashes")

    return [extract_result_digit(h) for h in comparison_block_hashes]


def count_matches(chosen_numbers: List[int], result_digits: List[int]) -> int:
    """
    일치 개수 계산

    순서대로 비교: chosen[i] == result[i] 개수

    Args:
        chosen_numbers: 플레이어가 선택한 6자리
        result_digits: 블록 해시에서 추출한 6자리

    Returns:
        matches: 0~6
    """
    if len(chosen_numbers) != LOTTO_DIGIT_COUNT or len(result_digits) != LOTTO_DIGIT_COUNT:
        return 0

    return sum(1 for i in range(LOTTO_DIGIT_COUNT) if chosen_numbers[i] == result_digits[i])


def determine_prize(matches: int) -> LottoPrize:
    """
    일치 개수로 등급 판정

    Args:
        matches: 0~6

    Returns:
        LottoPrize
    """
    prize_map = {
        6: LottoPrize.JACKPOT,
        5: LottoPrize.SECOND,
        4: LottoPrize.THIRD,
        3: LottoPrize.FOURTH,
        2: LottoPrize.FIFTH,
        1: LottoPrize.SIXTH,
        0: LottoPrize.NONE,
    }
    return prize_map.get(matches, LottoPrize.NONE)


def calculate_payout(prize: LottoPrize, pool_snapshot: int) -> int:
    """
    등급별 보상 계산

    Args:
        prize: 등급
        pool_snapshot: Commit 시점 잭팟 풀 잔액 (1등용)

    Returns:
        payout: JACK satoshi 단위 (6등은 POT으로 따로 처리)
    """
    if prize == LottoPrize.JACKPOT:
        return int(pool_snapshot * LOTTO_PRIZE_1ST_RATIO)
    elif prize == LottoPrize.SECOND:
        return LOTTO_PRIZE_2ND
    elif prize == LottoPrize.THIRD:
        return LOTTO_PRIZE_3RD
    elif prize == LottoPrize.FOURTH:
        return LOTTO_PRIZE_4TH
    elif prize == LottoPrize.FIFTH:
        return LOTTO_PRIZE_5TH
    elif prize == LottoPrize.SIXTH:
        # 6등은 1 POT 재지급 (JACK이 아님, 별도 처리 필요)
        return 0  # POT은 별도 필드로 처리
    else:
        return 0


def get_comparison_heights(commit_height: int) -> List[int]:
    """
    비교 블록 높이들 계산

    Args:
        commit_height: Commit이 포함된 블록 높이 N

    Returns:
        [N+5, N+10, N+15, N+20, N+25, N+30]
    """
    return [commit_height + offset for offset in LOTTO_COMPARISON_OFFSETS]


def is_claim_valid(commit_height: int, claim_height: int) -> Tuple[bool, str]:
    """
    Claim 타이밍 검증

    Args:
        commit_height: Commit 블록 높이 N
        claim_height: Claim 블록 높이

    Returns:
        (is_valid, reason)
    """
    gap = claim_height - commit_height

    if gap < LOTTO_MIN_CLAIM_GAP:
        return False, f"Too early: gap {gap} < min {LOTTO_MIN_CLAIM_GAP} (need N+30)"

    if gap > LOTTO_MAX_CLAIM_GAP:
        return False, f"Expired: gap {gap} > max {LOTTO_MAX_CLAIM_GAP} (deadline N+80)"

    return True, "OK"


def get_commit_status(commit: CommitRecord, current_height: int) -> CommitStatus:
    """커밋 상태 조회"""
    if commit.claim_height is not None:
        return CommitStatus.CLAIMED

    gap = current_height - commit.commit_height

    if gap > LOTTO_MAX_CLAIM_GAP:
        return CommitStatus.EXPIRED

    if gap < LOTTO_MIN_CLAIM_GAP:
        return CommitStatus.PENDING

    return CommitStatus.CLAIMABLE


def blocks_until_claimable(commit_height: int, current_height: int) -> int:
    """Claim 가능까지 남은 블록 수"""
    gap = current_height - commit_height

    if gap >= LOTTO_MIN_CLAIM_GAP:
        return 0  # 이미 Claim 가능

    return LOTTO_MIN_CLAIM_GAP - gap


def blocks_until_expire(commit_height: int, current_height: int) -> int:
    """만료까지 남은 블록 수"""
    gap = current_height - commit_height

    if gap >= LOTTO_MAX_CLAIM_GAP:
        return 0  # 이미 만료

    return LOTTO_MAX_CLAIM_GAP - gap


class CommitStore:
    """
    커밋 저장소

    address -> commit_hash -> CommitRecord
    """

    def __init__(self):
        self._commits: dict = {}  # commit_hash -> CommitRecord
        self._by_address: dict = {}  # address -> set of commit_hashes
        self._by_height: dict = {}  # height -> set of commit_hashes

    def add_commit(self, record: CommitRecord):
        """커밋 추가"""
        self._commits[record.commit_hash] = record

        # 주소 인덱스
        if record.player_address not in self._by_address:
            self._by_address[record.player_address] = set()
        self._by_address[record.player_address].add(record.commit_hash)

        # 높이 인덱스
        if record.commit_height not in self._by_height:
            self._by_height[record.commit_height] = set()
        self._by_height[record.commit_height].add(record.commit_hash)

    def get_commit(self, commit_hash: bytes) -> Optional[CommitRecord]:
        """커밋 조회"""
        return self._commits.get(commit_hash)

    def get_commits_by_address(self, address: str) -> list:
        """주소별 커밋 조회"""
        hashes = self._by_address.get(address, set())
        return [self._commits[h] for h in hashes if h in self._commits]

    def get_claimable_commits(self, current_height: int) -> list:
        """Claim 가능한 커밋들"""
        claimable = []
        for commit in self._commits.values():
            if get_commit_status(commit, current_height) == CommitStatus.CLAIMABLE:
                claimable.append(commit)
        return claimable

    def get_pending_commits(self, current_height: int) -> list:
        """Claim 대기 중인 커밋들 (PENDING + CLAIMABLE)"""
        pending = []
        for commit in self._commits.values():
            status = get_commit_status(commit, current_height)
            if status in (CommitStatus.PENDING, CommitStatus.CLAIMABLE):
                pending.append(commit)
        return pending

    def update_claim(
        self,
        commit_hash: bytes,
        claim_height: int,
        claim_tx_id: bytes,
        nonce: bytes,
        result_digits: List[int],
        matches: int,
        prize: LottoPrize,
        payout: int
    ):
        """Claim 결과 업데이트"""
        commit = self._commits.get(commit_hash)
        if commit:
            commit.claim_height = claim_height
            commit.claim_tx_id = claim_tx_id
            commit.nonce = nonce
            commit.result_digits = result_digits
            commit.matches = matches
            commit.prize = prize
            commit.payout = payout

    def remove_expired(self, current_height: int) -> int:
        """만료된 커밋 제거"""
        expired = []
        for commit_hash, commit in self._commits.items():
            if get_commit_status(commit, current_height) == CommitStatus.EXPIRED:
                expired.append(commit_hash)

        for commit_hash in expired:
            commit = self._commits.pop(commit_hash)
            self._by_address.get(commit.player_address, set()).discard(commit_hash)
            self._by_height.get(commit.commit_height, set()).discard(commit_hash)

        return len(expired)


# =============================================================================
# 하위 호환 함수 (deprecated - 기존 코드 마이그레이션용)
# =============================================================================

def calculate_winning_slot(nonce: bytes, block_hash: bytes) -> int:
    """
    [DEPRECATED] 기존 단일 슬롯 방식
    새 코드에서는 calculate_result_digits() 사용
    """
    combined = sha256(nonce + block_hash)
    value = int.from_bytes(combined[-2:], 'big')
    return value % 100


def check_win(target: int, winning_slot: int) -> bool:
    """
    [DEPRECATED] 기존 단일 슬롯 방식
    새 코드에서는 count_matches() + determine_prize() 사용
    """
    return target == winning_slot


def is_reveal_valid(commit_height: int, reveal_height: int) -> Tuple[bool, str]:
    """
    [DEPRECATED] is_claim_valid()로 대체
    """
    return is_claim_valid(commit_height, reveal_height)
