"""
Step 1.4: Merkle Tree 모듈
- 블록 내 TX들의 요약 해시 계산
- SPV 증명 생성/검증
"""

from typing import List, Tuple
from .hash import double_sha256


def build_merkle_tree(tx_hashes: List[bytes]) -> bytes:
    """
    TX 해시 리스트로 Merkle Root 계산
    Args:
        tx_hashes: TX 해시 리스트 (각 32 bytes)
    Returns:
        merkle_root: 32 bytes
    """
    if not tx_hashes:
        # 빈 블록의 경우 (Coinbase만 있어도 최소 1개)
        return bytes(32)

    # TX가 1개면 그게 루트
    if len(tx_hashes) == 1:
        return tx_hashes[0]

    # 리스트 복사 (원본 수정 방지)
    level = list(tx_hashes)

    while len(level) > 1:
        # 홀수면 마지막 복제
        if len(level) % 2 == 1:
            level.append(level[-1])

        # 다음 레벨 계산
        next_level = []
        for i in range(0, len(level), 2):
            combined = level[i] + level[i + 1]
            parent = double_sha256(combined)
            next_level.append(parent)

        level = next_level

    return level[0]


def get_merkle_proof(tx_hash: bytes, tx_hashes: List[bytes]) -> List[Tuple[bytes, bool]]:
    """
    특정 TX의 Merkle Proof 생성
    Args:
        tx_hash: 증명할 TX의 해시
        tx_hashes: 블록 내 모든 TX 해시
    Returns:
        proof: [(sibling_hash, is_left), ...] 리스트
               is_left=True면 sibling이 왼쪽
    """
    if tx_hash not in tx_hashes:
        raise ValueError("TX not found in list")

    if len(tx_hashes) == 1:
        return []  # 단일 TX는 증명 불필요

    proof = []
    level = list(tx_hashes)
    target = tx_hash

    while len(level) > 1:
        # 홀수면 마지막 복제
        if len(level) % 2 == 1:
            level.append(level[-1])

        # 타겟의 인덱스 찾기
        target_index = level.index(target)

        # 짝/홀수 인덱스에 따라 sibling 결정
        if target_index % 2 == 0:
            # 짝수 인덱스: sibling은 오른쪽
            sibling = level[target_index + 1]
            is_left = False
        else:
            # 홀수 인덱스: sibling은 왼쪽
            sibling = level[target_index - 1]
            is_left = True

        proof.append((sibling, is_left))

        # 다음 레벨 계산
        next_level = []
        for i in range(0, len(level), 2):
            combined = level[i] + level[i + 1]
            parent = double_sha256(combined)
            next_level.append(parent)

            # 타겟의 부모 찾기
            if i == target_index or i + 1 == target_index:
                target = parent

        level = next_level

    return proof


def verify_merkle_proof(
    tx_hash: bytes,
    proof: List[Tuple[bytes, bool]],
    merkle_root: bytes
) -> bool:
    """
    Merkle Proof 검증
    Args:
        tx_hash: 검증할 TX의 해시
        proof: get_merkle_proof의 결과
        merkle_root: 블록 헤더의 merkle_root
    Returns:
        bool: 유효하면 True
    """
    current = tx_hash

    for sibling, is_left in proof:
        if is_left:
            combined = sibling + current
        else:
            combined = current + sibling
        current = double_sha256(combined)

    return current == merkle_root


def calculate_merkle_root(transactions: list) -> bytes:
    """
    Transaction 객체 리스트에서 Merkle Root 계산
    (Transaction 클래스가 get_txid() 메서드를 가정)
    """
    if not transactions:
        return bytes(32)

    tx_hashes = [tx.get_txid() for tx in transactions]
    return build_merkle_tree(tx_hashes)
