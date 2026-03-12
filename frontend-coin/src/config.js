/**
 * JackpotChain 코인부 — 전역 설정
 *
 * 환경별 URL은 .env 파일로 관리 (VITE_* 접두사 필수)
 * 나머지 게임/블록체인 파라미터는 이 파일 한 곳에서만 수정합니다.
 */

// ── 외부 URL ──────────────────────────────────────────────────────────────────
/** 블록체인 RPC 노드 주소. .env의 VITE_RPC_URL로 덮어쓸 수 있습니다. */
export const DEFAULT_RPC_URL = import.meta.env.VITE_RPC_URL || 'http://127.0.0.1:8332'

/** 학습부(Vue) 서비스 주소 */
export const LEARNING_URL = import.meta.env.VITE_LEARNING_URL || 'http://localhost:5174'

// ── 폴링 ──────────────────────────────────────────────────────────────────────
/** 홈/네트워크/채굴 대시보드 실시간 데이터 갱신 주기 (ms) */
export const POLL_INTERVAL_MS = Number(import.meta.env.VITE_POLL_INTERVAL_MS) || 15000

// ── 블록체인 파라미터 ────────────────────────────────────────────────────────
export const CHAIN = {
  /** 블록 보상 (JACK, 표시용) */
  BLOCK_REWARD_JACK: 50,
  /** 목표 블록 생성 시간 (초) */
  BLOCK_TIME_SEC: 30,
  /** 난이도 조정 주기 (블록) */
  DIFFICULTY_ADJUST_BLOCKS: 50,
  /** RPC 포트 (안내 문구용) */
  RPC_PORT: Number(import.meta.env.VITE_RPC_PORT) || 8332,
}

// ── 토큰/교환 ─────────────────────────────────────────────────────────────────
export const TOKEN = {
  /** JACK satoshi 단위 (1 JACK = 10^8 satoshi) */
  SATOSHI_PER_JACK: 1e8,
  /** JACK → POT 교환 비율 (JACK 몇 개당 1 POT) */
  JACK_PER_POT: Number(import.meta.env.VITE_JACK_PER_POT) || 100,
}

// ── 로또(가챠) 파라미터 ───────────────────────────────────────────────────────
export const LOTTO = {
  /** 숫자 슬롯 개수 */
  SLOT_COUNT: 6,
  /** 선택 가능한 hex 값 목록 (0x0 ~ 0xF) */
  HEX_DIGITS: ['0','1','2','3','4','5','6','7','8','9','A','B','C','D','E','F'],
  /** Commit 후 Claim 가능해지기까지 UI 체험용 대기 시간 (초) */
  WAIT_COUNTDOWN_SEC: Number(import.meta.env.VITE_LOTTO_WAIT_SEC) || 30,
  /** 결과 비교에 사용하는 블록 오프셋 목록 (기능명세서 8.2.1 기준) */
  COMPARE_OFFSETS: [3, 6, 9, 12, 15, 18],
  /** 결과 계산에 사용하는 비교 블록 수 */
  COMPARE_BLOCK_COUNT: 6,
  /** Claim 가능 시작 블록 오프셋 — 마지막 비교 블록(N+18) 이후 (기능명세서 8.3.1) */
  CLAIM_START_OFFSET: 18,
  /** Claim 만료 블록 오프셋 (기능명세서 8.3.1) */
  CLAIM_EXPIRE_OFFSET: 80,
  /** 참가비 1회 (POT) */
  COST_POT: 1,
  /** 참가비(JACK) 중 잭팟 풀 적립 비율 */
  POOL_RATIO: 0.80,
  /** 참가비(JACK) 중 소각 비율 */
  BURN_RATIO: 0.19,
  /** 참가비(JACK) 중 채굴자 수수료 비율 */
  MINER_RATIO: 0.01,
}

// ── 보상 구조 ─────────────────────────────────────────────────────────────────
/** judgeRank / Jackpot 페이지 공통 보상 테이블 */
export const RANK_TABLE = [
  { min: 6, label: '1등 🥇', reward: '잭팟 풀의 50%',  rewardJACK: null,       poolRatio: 0.50 },
  { min: 5, label: '2등 🥈', reward: '100,000 JACK',   rewardJACK: 10000000000, poolRatio: null },
  { min: 4, label: '3등 🥉', reward: '20,000 JACK',    rewardJACK: 2000000000,  poolRatio: null },
  { min: 3, label: '4등',    reward: '2,000 JACK',     rewardJACK: 200000000,   poolRatio: null },
  { min: 2, label: '5등',    reward: '300 JACK',       rewardJACK: 30000000,    poolRatio: null },
  { min: 1, label: '6등',    reward: '1 POT 반환',     rewardJACK: 0,           poolRatio: null },
  { min: 0, label: '꽝',     reward: '없음',            rewardJACK: 0,           poolRatio: null },
]

// ── localStorage 키 ────────────────────────────────────────────────────────────
export const STORAGE_KEYS = {
  WALLET:       import.meta.env.VITE_STORAGE_PREFIX ? `${import.meta.env.VITE_STORAGE_PREFIX}_wallet`  : 'jackpotchain_wallet',
  LOTTO_HISTORY:import.meta.env.VITE_STORAGE_PREFIX ? `${import.meta.env.VITE_STORAGE_PREFIX}_lotto`   : 'jackpotchain_lotto',
  RPC_URL:      import.meta.env.VITE_STORAGE_PREFIX ? `${import.meta.env.VITE_STORAGE_PREFIX}_rpc_url` : 'rpc_url',
}
