# consensus.py - 간단한 PoW 합의 알고리즘
# 정합성 최소화 버전

import hashlib

DIFFICULTY = 5  # 해시 앞 0 개수

class Consensus:
    """간단한 PoW 합의"""

    @staticmethod
    def calculate_hash(index, prev_hash, data, timestamp, nonce):
        """블록 해시 계산"""
        block_string = f"{index}{prev_hash}{data}{timestamp}{nonce}"
        return hashlib.sha256(block_string.encode()).hexdigest()

    @staticmethod
    def is_valid_proof(hash_value, difficulty=DIFFICULTY):
        """PoW 검증: 해시가 난이도 조건 만족?"""
        return hash_value.startswith("0" * difficulty)

    @staticmethod
    def mine(block):
        """채굴: 유효한 nonce 찾기"""
        target = "0" * DIFFICULTY
        while not block.hash.startswith(target):
            block.nonce += 1
            block.hash = Consensus.calculate_hash(
                block.index, block.prev_hash, block.data,
                block.timestamp, block.nonce
            )
        return block

    @staticmethod
    def is_valid_block(block, prev_block):
        """블록 검증 (간단 버전)"""
        # 1. 인덱스 연속?
        if block.index != prev_block.index + 1:
            return False

        # 2. prev_hash 일치?
        if block.prev_hash != prev_block.hash:
            return False

        # 3. 해시 정확?
        calculated = Consensus.calculate_hash(
            block.index, block.prev_hash, block.data,
            block.timestamp, block.nonce
        )
        if block.hash != calculated:
            return False

        # 4. PoW 만족?
        if not Consensus.is_valid_proof(block.hash):
            return False

        return True

    @staticmethod
    def is_valid_chain(chain):
        """체인 전체 검증"""
        for i in range(1, len(chain)):
            if not Consensus.is_valid_block(chain[i], chain[i-1]):
                return False
        return True

    @staticmethod
    def resolve_conflicts(my_chain, other_chain):
        """
        충돌 해결: Longest Chain Rule
        더 긴 유효한 체인을 선택

        Returns: (교체여부, 선택된 체인)
        """
        # 상대 체인이 더 길고 유효하면 교체
        if len(other_chain) > len(my_chain):
            if Consensus.is_valid_chain(other_chain):
                return True, other_chain

        return False, my_chain
