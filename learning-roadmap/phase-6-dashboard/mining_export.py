"""
JackpotChain 채굴 성과 Mock 데이터 생성기
- 1분마다 새 블록 데이터를 생성해서 mining_stats.csv에 저장
- 나중에 실제 LevelDB 연결 시 generate_block() 함수만 교체하면 됨
"""

import csv
import os
import random
import time
from datetime import datetime

# ── 파라미터 ───────────────────────────────────────────
TARGET_BLOCK_TIME   = 15      # 목표 블록 타임 (초)
DIFFICULTY_ADJUST   = 50      # 난이도 조정 주기 (블록 수)
REWARD_JACK         = 50.0    # 블록 보상 (JACK)
FORK_RATE           = 0.13    # 포크 발생 확률
MAX_TX_PER_BLOCK    = 20      # 블록당 최대 트랜잭션 수
REFRESH_INTERVAL    = 60      # CSV 갱신 주기 (초)
CSV_PATH            = os.path.join(os.path.dirname(__file__), "mining_stats.csv")
CSV_HEADER          = [
    "block_height", "timestamp", "mining_time_sec",
    "nonce_attempts", "difficulty", "reward_jack",
    "tx_count", "is_fork", "block_hash_prefix"
]
# ──────────────────────────────────────────────────────


def calc_nonce_attempts(difficulty: int) -> int:
    """
    difficulty = 해시 앞자리 0의 개수 (16진수 기준)
    평균 시도 횟수 = 16^difficulty
    실제 PoW처럼 기하분포로 샘플링
    """
    success_prob = (1 / 16) ** difficulty
    return int(random.expovariate(success_prob))


def calc_mining_time(nonce_attempts: int, hash_per_sec: int = 50_000) -> float:
    """
    nonce 시도 횟수 / 초당 해시 속도 = 채굴 소요 시간
    hash_per_sec: Mock 채굴자의 해시 속도
    """
    return round(nonce_attempts / hash_per_sec, 2)


def make_block_hash(difficulty: int) -> str:
    """
    difficulty 개수만큼 앞자리가 0인 8자리 16진수 해시 생성
    예) difficulty=4 → '0000a1b2'
    """
    prefix = "0" * difficulty
    suffix_len = 8 - difficulty
    suffix = "".join(random.choices("0123456789abcdef", k=suffix_len))
    return prefix + suffix


def adjust_difficulty(current: int, recent_blocks: list) -> int:
    """
    최근 DIFFICULTY_ADJUST개 블록의 평균 블록 타임을 보고 난이도 조정
    평균 > 목표 * 1.1 → 난이도 낮춤 (너무 어려움)
    평균 < 목표 * 0.9 → 난이도 높임 (너무 쉬움)
    """
    if len(recent_blocks) < DIFFICULTY_ADJUST:
        return current

    avg_time = sum(b["mining_time_sec"] for b in recent_blocks) / len(recent_blocks)

    if avg_time > TARGET_BLOCK_TIME * 1.1:
        return max(1, current - 1)
    elif avg_time < TARGET_BLOCK_TIME * 0.9:
        return current + 1
    return current


def generate_block(height: int, difficulty: int, timestamp: datetime) -> dict:
    """블록 1개 Mock 데이터 생성"""
    nonce_attempts  = calc_nonce_attempts(difficulty)
    mining_time_sec = calc_mining_time(nonce_attempts)

    return {
        "block_height":    height,
        "timestamp":       timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "mining_time_sec": mining_time_sec,
        "nonce_attempts":  nonce_attempts,
        "difficulty":      difficulty,
        "reward_jack":     REWARD_JACK,
        "tx_count":        random.randint(0, MAX_TX_PER_BLOCK),
        "is_fork":         random.random() < FORK_RATE,
        "block_hash_prefix": make_block_hash(difficulty),
    }


def save_csv(blocks: list):
    """블록 리스트를 CSV로 저장"""
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(blocks)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] CSV 저장 완료 — 총 {len(blocks)}개 블록")


def run():
    """메인 루프: 1분마다 새 블록 추가 후 CSV 갱신"""
    blocks     = []
    difficulty = 4          # 초기 난이도
    height     = 1
    now        = datetime.now()

    print("=== JackpotChain Mock 데이터 생성기 시작 ===")
    print(f"저장 경로: {CSV_PATH}")
    print(f"갱신 주기: {REFRESH_INTERVAL}초\n")

    while True:
        # 새 블록 생성
        block = generate_block(height, difficulty, now)
        blocks.append(block)

        # 난이도 조정 (50블록마다)
        if height % DIFFICULTY_ADJUST == 0:
            recent = blocks[-DIFFICULTY_ADJUST:]
            new_difficulty = adjust_difficulty(difficulty, recent)
            if new_difficulty != difficulty:
                print(f"  난이도 조정: {difficulty} → {new_difficulty} (블록 {height})")
            difficulty = new_difficulty

        # CSV 저장
        save_csv(blocks)
        print(
            f"  블록 {height:>5} | "
            f"time={block['mining_time_sec']:>6.1f}s | "
            f"difficulty={difficulty} | "
            f"tx={block['tx_count']:>2} | "
            f"fork={block['is_fork']}"
        )

        height += 1
        now     = datetime.now()
        time.sleep(REFRESH_INTERVAL)


if __name__ == "__main__":
    run()
