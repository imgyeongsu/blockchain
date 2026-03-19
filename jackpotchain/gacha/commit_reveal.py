"""
로또 시스템: 자동 지급 방식

- Commit: 6자리 hex 숫자 배열 제출 (각 0x0 ~ 0xf) — 평문 저장
- 18블록 후 채굴자가 자동으로 당첨 판정 + 지급 TX 블록에 포함
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
    LOTTO_PRIZE_1ST_PERCENT,
    LOTTO_PRIZE_2ND,
    LOTTO_PRIZE_3RD,
    LOTTO_PRIZE_4TH,
    LOTTO_PRIZE_5TH,
    LOTTO_PRIZE_6TH_POT,
    COIN,
)


class CommitStatus(Enum):
    """커밋 상태"""
    PENDING = "pending"          # 판정 대기 중 (N+18 이전)
    RESOLVED = "resolved"        # 판정 완료 (자동 지급됨)
    EXPIRED = "expired"          # 미처리 (비정상)


class LottoPrize(Enum):
    """등급"""
    JACKPOT = 1      # 6개 일치 - 잭팟 풀 50% (다수 당첨 시 N등분)
    SECOND = 2       # 5개 일치 - 100,000 JACK
    THIRD = 3        # 4개 일치 - 20,000 JACK
    FOURTH = 4       # 3개 일치 - 2,000 JACK
    FIFTH = 5        # 2개 일치 - 300 JACK
    SIXTH = 6        # 1개 일치 - 1 POT 재지급
    NONE = 0         # 0개 일치 - 꽝


@dataclass
class CommitRecord:
    """커밋 기록"""
    commit_hash: bytes                      # TX ID (키)
    player_address: str
    commit_height: int                      # Commit 블록 높이
    commit_tx_id: bytes
    chosen_numbers: List[int]               # 6자리 숫자 [0x0~0xf, ...]
    pool_snapshot: int = 0                  # Commit 시점 잭팟 풀 잔액

    # 판정 결과 (자동 지급 후 채움)
    claim_height: Optional[int] = None      # 지급 블록 높이
    claim_tx_id: Optional[bytes] = None
    nonce: Optional[bytes] = None           # 미사용 (호환용)
    result_digits: Optional[List[int]] = None
    matches: int = 0
    prize: LottoPrize = LottoPrize.NONE
    payout: int = 0


def generate_commit(chosen_numbers: List[int] = None) -> Tuple[bytes, bytes, List[int]]:
    """
    Commit 생성 (호환용 — nonce는 더 이상 사용하지 않지만 API 유지)

    Returns:
        (commit_hash_unused, nonce_unused, chosen_numbers)
    """
    nonce = os.urandom(32)  # 미사용

    if chosen_numbers is None:
        chosen_numbers = [
            int.from_bytes(os.urandom(1), 'big') % LOTTO_DIGIT_BASE
            for _ in range(LOTTO_DIGIT_COUNT)
        ]

    if len(chosen_numbers) != LOTTO_DIGIT_COUNT:
        raise ValueError(f"Must have exactly {LOTTO_DIGIT_COUNT} digits")
    for d in chosen_numbers:
        if not (0 <= d < LOTTO_DIGIT_BASE):
            raise ValueError(f"Each digit must be 0~{LOTTO_DIGIT_BASE - 1}")

    # commit_hash는 더 이상 사용하지 않음 (TX ID가 키)
    data = nonce + bytes(chosen_numbers)
    commit_hash = sha256(data)

    return commit_hash, nonce, chosen_numbers


def extract_result_digit(block_hash: bytes) -> int:
    """블록 해시에서 결과 숫자 추출 (마지막 바이트 하위 4비트)"""
    return block_hash[-1] & 0x0f


def calculate_result_digits(comparison_block_hashes: List[bytes]) -> List[int]:
    """6개 비교 블록 해시에서 결과 숫자 배열 추출"""
    if len(comparison_block_hashes) != LOTTO_DIGIT_COUNT:
        raise ValueError(f"Need exactly {LOTTO_DIGIT_COUNT} block hashes")
    return [extract_result_digit(h) for h in comparison_block_hashes]


def count_matches(chosen_numbers: List[int], result_digits: List[int]) -> int:
    """일치 개수 계산 (순서대로 비교)"""
    if len(chosen_numbers) != LOTTO_DIGIT_COUNT or len(result_digits) != LOTTO_DIGIT_COUNT:
        return 0
    return sum(1 for i in range(LOTTO_DIGIT_COUNT) if chosen_numbers[i] == result_digits[i])


def determine_prize(matches: int) -> LottoPrize:
    """일치 개수로 등급 판정"""
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


def calculate_payout(prize: LottoPrize, pool_snapshot: int) -> Tuple[int, int]:
    """
    등급별 보상 계산

    Returns:
        (jack_payout, pot_payout)
    """
    if prize == LottoPrize.JACKPOT:
        return (pool_snapshot * LOTTO_PRIZE_1ST_PERCENT // 100, 0)
    elif prize == LottoPrize.SECOND:
        return (LOTTO_PRIZE_2ND, 0)
    elif prize == LottoPrize.THIRD:
        return (LOTTO_PRIZE_3RD, 0)
    elif prize == LottoPrize.FOURTH:
        return (LOTTO_PRIZE_4TH, 0)
    elif prize == LottoPrize.FIFTH:
        return (LOTTO_PRIZE_5TH, 0)
    elif prize == LottoPrize.SIXTH:
        return (0, LOTTO_PRIZE_6TH_POT)
    else:
        return (0, 0)


def get_comparison_heights(commit_height: int) -> List[int]:
    """비교 블록 높이들 계산: [N+3, N+6, N+9, N+12, N+15, N+18]"""
    return [commit_height + offset for offset in LOTTO_COMPARISON_OFFSETS]


def get_commit_status(commit: CommitRecord, current_height: int) -> CommitStatus:
    """커밋 상태 조회"""
    if commit.claim_height is not None:
        return CommitStatus.RESOLVED
    gap = current_height - commit.commit_height
    if gap < LOTTO_MIN_CLAIM_GAP:
        return CommitStatus.PENDING
    return CommitStatus.PENDING  # 자동 지급 대기 중


# 하위 호환용
def verify_commit(commit_hash, nonce, chosen_numbers):
    """[DEPRECATED] Commit 검증 — 자동 지급에서는 불필요"""
    return True

def is_claim_valid(commit_height, claim_height):
    """[DEPRECATED] 호환용"""
    return True, "OK"

def calculate_winning_slot(nonce, block_hash):
    """[DEPRECATED]"""
    return 0

def check_win(target, winning_slot):
    """[DEPRECATED]"""
    return False

def is_reveal_valid(commit_height, reveal_height):
    """[DEPRECATED]"""
    return True, "OK"

def blocks_until_claimable(commit_height, current_height):
    """[DEPRECATED]"""
    return max(0, LOTTO_MIN_CLAIM_GAP - (current_height - commit_height))

def blocks_until_expire(commit_height, current_height):
    """[DEPRECATED]"""
    return 0


class CommitStore:
    """커밋 저장소"""

    def __init__(self):
        self._commits: dict = {}
        self._by_address: dict = {}
        self._by_height: dict = {}

    def add_commit(self, record: CommitRecord):
        """커밋 추가"""
        self._commits[record.commit_hash] = record
        if record.player_address not in self._by_address:
            self._by_address[record.player_address] = set()
        self._by_address[record.player_address].add(record.commit_hash)
        if record.commit_height not in self._by_height:
            self._by_height[record.commit_height] = set()
        self._by_height[record.commit_height].add(record.commit_hash)

    def get_commit(self, commit_hash: bytes) -> Optional[CommitRecord]:
        return self._commits.get(commit_hash)

    def get_commits_by_address(self, address: str) -> list:
        hashes = self._by_address.get(address, set())
        return [self._commits[h] for h in hashes if h in self._commits]

    def get_commits_at_height(self, height: int) -> list:
        """특정 높이의 Commit 목록"""
        hashes = self._by_height.get(height, set())
        return [self._commits[h] for h in hashes if h in self._commits]

    def get_pending_commits(self, current_height: int) -> list:
        """판정 대기 중인 커밋들"""
        return [c for c in self._commits.values() if c.claim_height is None]

    def get_claimable_commits(self, current_height: int) -> list:
        """[호환용] 판정 대기 커밋"""
        return self.get_pending_commits(current_height)

    def update_claim(self, **kwargs):
        """판정 결과 업데이트"""
        commit_hash = kwargs.get('commit_hash')
        commit = self._commits.get(commit_hash)
        if commit:
            for key, value in kwargs.items():
                if key != 'commit_hash' and hasattr(commit, key):
                    setattr(commit, key, value)
