/**
 * JackpotChain 학습부 — 전역 설정
 *
 * 챕터별 시뮬레이션 파라미터를 한 곳에서 관리합니다.
 * 환경 변수(VITE_*)로 일부 값을 덮어쓸 수 있습니다.
 */

// ── Chapter 1: 인플레이션 시뮬레이션 ────────────────────────────────────────
export const CH1 = {
  /** 게임 시작 시 초기 잔액 (원) */
  INIT_BALANCE: 5000,
  /** 초기 물가 */
  INIT_CHICKEN_PRICE: 20000,
  INIT_RENT_PRICE:    500000,
  INIT_EGG_PRICE:     7000,

  /** 돈 벌기 버튼 1회 수입 */
  EARN_PER_CLICK: 1000,

  /** 인플레이션 1틱당 가격 상승량 */
  CHICKEN_RISE: 8000,
  RENT_RISE:    50000,
  EGG_RISE:     2000,

  /** 인플레이션 기본 틱 간격 (ms) */
  INFLATION_INTERVAL_MS: 800,
  /** 인플레이션 2배 가속 시 틱 간격 (ms) */
  INFLATION_FAST_MS: 400,

  /** 이 금액 이상 보유 시 중앙은행 이벤트 발동 (인플레이션 2배) */
  INFLATION_DOUBLE_TRIGGER: 15000,

  /** 치킨 가격이 이 값을 넘으면 게임 오버 */
  GAME_OVER_PRICE: 1000000,

  /** 그래프 최대 히스토리 길이 */
  MAX_HISTORY: 40,
}

// ── Chapter 3: Commit-Reveal 체험 ────────────────────────────────────────────
export const CH3 = {
  /** 선택할 숫자 슬롯 수 */
  SLOT_COUNT: 6,

  /** Commit 후 결과 확인까지 UI 대기 시간 (초) */
  WAIT_COUNTDOWN_SEC: 10,

  /** 컨페티(폭죽) 효과 발동 최소 일치 수 */
  CONFETTI_MATCH_THRESHOLD: 4,

  /** 체험용 보상 테이블 (matchCount 기준 내림차순) */
  PRIZE_TABLE: [
    { min: 6, rank: '1등', medal: '🥇', reward: '잭팟! 50,000 JACK' },
    { min: 5, rank: '2등', medal: '🥈', reward: '10,000 JACK' },
    { min: 4, rank: '3등', medal: '🥉', reward: '2,000 JACK' },
    { min: 3, rank: '4등', medal: '🎖️', reward: '300 JACK' },
    { min: 2, rank: '5등', medal: '🎟️', reward: '1 POT 반환' },
    { min: 0, rank: '꽝',  medal: '😢', reward: '다음 기회에...' },
  ],
}
