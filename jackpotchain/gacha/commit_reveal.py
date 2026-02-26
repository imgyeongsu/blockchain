"""
Step 7.2: Commit-Reveal 패턴
- 공정한 온체인 난수 생성
- Commit: hash(nonce + target) 제출
- Reveal: nonce 공개, 당첨 여부 결정
"""

import os
import struct
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from ..crypto.hash import sha256, double_sha256
from ..constants import (
    GACHA_WIN_PROBABILITY,
    GACHA_MIN_REVEAL_GAP,
    GACHA_MAX_REVEAL_GAP,
)


class CommitStatus(Enum):
    """커밋 상태"""
    PENDING = "pending"      # Reveal 대기 중
    REVEALED = "revealed"    # Reveal 완료
    EXPIRED = "expired"      # 기한 만료
    INVALID = "invalid"      # 무효


@dataclass
class CommitRecord:
    """커밋 기록"""
    commit_hash: bytes      # SHA256(nonce || target)
    player_address: str
    commit_height: int      # Commit 블록 높이
    commit_tx_id: bytes
    target: int             # 목표 슬롯 (0-99)

    # Reveal 정보 (나중에 채움)
    reveal_height: Optional[int] = None
    reveal_tx_id: Optional[bytes] = None
    nonce: Optional[bytes] = None
    result: Optional[bool] = None  # 당첨 여부


def generate_commit(target: int = None) -> Tuple[bytes, bytes, int]:
    """
    Commit 생성

    Args:
        target: 목표 슬롯 (0-99), None이면 랜덤

    Returns:
        (commit_hash, nonce, target)
    """
    # 랜덤 nonce (32 bytes)
    nonce = os.urandom(32)

    # 랜덤 target (없으면)
    if target is None:
        target = int.from_bytes(os.urandom(1), 'big') % 100

    # commit_hash = SHA256(nonce || target)
    data = nonce + struct.pack('B', target)
    commit_hash = sha256(data)

    return commit_hash, nonce, target


def verify_commit(commit_hash: bytes, nonce: bytes, target: int) -> bool:
    """Commit 검증"""
    data = nonce + struct.pack('B', target)
    expected_hash = sha256(data)
    return commit_hash == expected_hash


def calculate_winning_slot(
    nonce: bytes,
    block_hash: bytes
) -> int:
    """
    당첨 슬롯 계산

    결합 해시를 기반으로 0-99 슬롯 결정
    - nonce: 플레이어 제공 (예측 불가)
    - block_hash: 네트워크 제공 (조작 불가)

    Returns:
        winning_slot: 0-99
    """
    # 결합 해시
    combined = sha256(nonce + block_hash)

    # 해시의 마지막 2바이트를 정수로 변환
    value = int.from_bytes(combined[-2:], 'big')

    # 0-99 범위로 변환
    return value % 100


def check_win(target: int, winning_slot: int) -> bool:
    """
    당첨 여부 확인

    1% 확률 = 100개 슬롯 중 1개 당첨
    target이 winning_slot과 같으면 당첨

    Args:
        target: 플레이어가 선택한 슬롯 (0-99)
        winning_slot: 계산된 당첨 슬롯 (0-99)

    Returns:
        True if won
    """
    return target == winning_slot


def is_reveal_valid(commit_height: int, reveal_height: int) -> Tuple[bool, str]:
    """
    Reveal 타이밍 검증

    Args:
        commit_height: Commit 블록 높이
        reveal_height: Reveal 블록 높이

    Returns:
        (is_valid, reason)
    """
    gap = reveal_height - commit_height

    if gap < GACHA_MIN_REVEAL_GAP:
        return False, f"Too early: gap {gap} < min {GACHA_MIN_REVEAL_GAP}"

    if gap > GACHA_MAX_REVEAL_GAP:
        return False, f"Expired: gap {gap} > max {GACHA_MAX_REVEAL_GAP}"

    return True, "OK"


def get_commit_status(
    commit: CommitRecord,
    current_height: int
) -> CommitStatus:
    """커밋 상태 조회"""
    if commit.reveal_height is not None:
        return CommitStatus.REVEALED

    gap = current_height - commit.commit_height

    if gap > GACHA_MAX_REVEAL_GAP:
        return CommitStatus.EXPIRED

    if gap < GACHA_MIN_REVEAL_GAP:
        return CommitStatus.PENDING

    return CommitStatus.PENDING  # Reveal 가능


def blocks_until_reveal(commit_height: int, current_height: int) -> int:
    """Reveal까지 남은 블록 수"""
    gap = current_height - commit_height

    if gap >= GACHA_MIN_REVEAL_GAP:
        return 0  # 이미 Reveal 가능

    return GACHA_MIN_REVEAL_GAP - gap


def blocks_until_expire(commit_height: int, current_height: int) -> int:
    """만료까지 남은 블록 수"""
    gap = current_height - commit_height

    if gap >= GACHA_MAX_REVEAL_GAP:
        return 0  # 이미 만료

    return GACHA_MAX_REVEAL_GAP - gap


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

    def get_pending_commits(self, current_height: int) -> list:
        """Reveal 대기 중인 커밋들"""
        pending = []
        for commit in self._commits.values():
            if get_commit_status(commit, current_height) == CommitStatus.PENDING:
                pending.append(commit)
        return pending

    def update_reveal(
        self,
        commit_hash: bytes,
        reveal_height: int,
        reveal_tx_id: bytes,
        nonce: bytes,
        result: bool
    ):
        """Reveal 결과 업데이트"""
        commit = self._commits.get(commit_hash)
        if commit:
            commit.reveal_height = reveal_height
            commit.reveal_tx_id = reveal_tx_id
            commit.nonce = nonce
            commit.result = result

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
