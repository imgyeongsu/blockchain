/**
 * @module crypto
 * @description 브라우저 사이드 암호화 유틸리티.
 * 개인키는 절대 서버로 전송하지 않으며, 모든 서명·해시는 브라우저 내에서만 처리됩니다.
 * Web Crypto API를 사용하므로 HTTPS 또는 localhost 환경이 필요합니다.
 */
import { TOKEN, RANK_TABLE, STORAGE_KEYS } from '../config'

// ── 포맷 유틸 ─────────────────────────────────────────────────────────────────

/**
 * satoshi 단위 값을 JACK 표시 문자열로 변환합니다.
 * 내부 금액은 항상 satoshi(정수)로 처리하며, 표시용으로만 소수점을 사용합니다.
 * @param {number|null} satoshi - satoshi 단위 금액
 * @returns {string} 예: "12,345.00000001 JACK"
 */
export function formatJACK(satoshi) {
  if (satoshi == null) return '0 JACK'
  const jack = Number(satoshi) / TOKEN.SATOSHI_PER_JACK
  return `${jack.toLocaleString('ko-KR', { maximumFractionDigits: 8 })} JACK`
}

/**
 * POT 금액을 표시 문자열로 변환합니다.
 * @param {number|null} amount - POT 금액
 * @returns {string} 예: "5 POT"
 */
export function formatPOT(amount) {
  if (amount == null) return '0 POT'
  return `${Number(amount)} POT`
}

/**
 * 긴 해시를 앞·뒤 일부만 표시하는 축약 문자열로 변환합니다.
 * @param {string} hash - 해시 문자열
 * @param {number} [len=8] - 앞에 표시할 문자 수
 * @returns {string} 예: "a1b2c3d4...ef12"
 */
export function shortHash(hash, len = 8) {
  if (!hash) return ''
  return `${hash.slice(0, len)}...${hash.slice(-4)}`
}

/**
 * 주소를 앞·뒤 일부만 표시하는 축약 문자열로 변환합니다.
 * @param {string} addr - 블록체인 주소
 * @param {number} [len=6] - 앞에 표시할 문자 수
 * @returns {string} 예: "1A2b3C...x9y8"
 */
export function shortAddr(addr, len = 6) {
  if (!addr) return ''
  return `${addr.slice(0, len)}...${addr.slice(-4)}`
}

// ── 시간 포맷 ─────────────────────────────────────────────────────────────────

/**
 * 유닉스 타임스탬프를 상대적 시간 문자열로 변환합니다.
 * @param {number} ts - 유닉스 타임스탬프(초)
 * @returns {string} 예: "3분 전", "2시간 전"
 */
export function timeAgo(ts) {
  const diff = Math.floor(Date.now() / 1000) - ts
  if (diff < 60) return `${diff}초 전`
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`
  return `${Math.floor(diff / 86400)}일 전`
}

// ── nonce 생성 ────────────────────────────────────────────────────────────────

/**
 * 암호학적으로 안전한 256비트 랜덤 nonce를 생성합니다.
 * Commit TX에 사용되어 사전 계산 공격을 방지합니다.
 * @returns {string} 64자리 hex 문자열
 */
export function generateNonce() {
  const arr = new Uint8Array(32)
  crypto.getRandomValues(arr)
  return Array.from(arr).map((b) => b.toString(16).padStart(2, '0')).join('')
}

// ── SHA-256 ───────────────────────────────────────────────────────────────────

/**
 * 문자열의 SHA-256 해시를 계산합니다.
 * Web Crypto API를 사용하므로 서버 의존 없이 브라우저에서 검증 가능합니다.
 * @param {string} str - 해시할 입력 문자열
 * @returns {Promise<string>} 64자리 hex 해시
 */
export async function sha256hex(str) {
  const buf = new TextEncoder().encode(str)
  const hash = await crypto.subtle.digest('SHA-256', buf)
  return Array.from(new Uint8Array(hash)).map((b) => b.toString(16).padStart(2, '0')).join('')
}

// ── 로또 등수 판정 ────────────────────────────────────────────────────────────

/**
 * @typedef {Object} RankResult
 * @property {number}      matches    - 일치한 슬롯 수
 * @property {number}      min        - 해당 등수의 최소 일치 수
 * @property {string}      label      - 등수 레이블 (예: '1등 🥇')
 * @property {string}      reward     - 보상 설명 (예: '잭팟 풀의 50%')
 * @property {number|null} rewardJACK - 보상 satoshi 값 (잭팟은 null)
 */

/**
 * 사용자 번호와 블록 digit를 비교하여 등수를 판정합니다.
 * 보상 테이블(RANK_TABLE)은 config.js에서 중앙 관리하므로
 * 보상 구조 변경 시 이 함수를 수정할 필요가 없습니다.
 *
 * @param {string[]} myNumbers   - 사용자 선택 번호 (예: ['0xA', '0x3', ...])
 * @param {string[]} blockDigits - 비교 블록 해시 digit (예: ['0xA', '0x1', ...])
 * @returns {RankResult} 등수 판정 결과
 */
export function judgeRank(myNumbers, blockDigits) {
  const matches = myNumbers.filter((n, i) => {
    const my = parseInt(n.replace('0x', ''), 16)
    const target = parseInt(blockDigits[i], 16)
    return my === target
  }).length

  const rank = RANK_TABLE.find((r) => matches >= r.min) || RANK_TABLE[RANK_TABLE.length - 1]
  return { matches, ...rank }
}

// ── Commit Hash 계산 ──────────────────────────────────────────────────────────

/**
 * nonce + 선택 번호를 결합하여 Commit Hash를 계산합니다.
 * 이 해시가 블록체인에 기록되며, Reveal 단계에서 원본 데이터를 공개하면
 * 누구나 재계산하여 조작 여부를 검증할 수 있습니다.
 *
 * @param {string}   nonce   - generateNonce()로 생성한 hex 문자열
 * @param {string[]} numbers - 선택 번호 배열 (예: ['0xA', '0x3', ...])
 * @returns {Promise<string>} Commit Hash (64자 hex)
 */
export async function calcCommitHash(nonce, numbers) {
  const str = nonce + numbers.join('')
  return sha256hex(str)
}

// ── 로컬 지갑 저장/불러오기 ───────────────────────────────────────────────────

/**
 * @typedef {Object} Wallet
 * @property {string} address    - 블록체인 주소
 * @property {string} [label]    - 사용자 지정 레이블
 */

/**
 * 지갑 정보를 localStorage에 저장합니다.
 * 개인키는 저장하지 않으며, 주소·레이블만 저장합니다.
 * @param {Wallet} wallet - 저장할 지갑 객체
 */
export function saveWallet(wallet) {
  localStorage.setItem(STORAGE_KEYS.WALLET, JSON.stringify(wallet))
}

/**
 * localStorage에서 지갑 정보를 불러옵니다.
 * @returns {Wallet|null} 저장된 지갑 또는 null
 */
export function loadWallet() {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.WALLET)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

/**
 * localStorage에서 지갑 정보를 삭제합니다.
 */
export function clearWallet() {
  localStorage.removeItem(STORAGE_KEYS.WALLET)
}

// ── 로또 히스토리 저장 ────────────────────────────────────────────────────────

/**
 * @typedef {Object} LottoCommit
 * @property {string}   nonce       - 사용한 nonce
 * @property {string[]} myNumbers   - 선택 번호 배열
 * @property {string}   commitHash  - Commit Hash
 * @property {number}   ts          - 커밋 시각 (ms)
 * @property {string}   status      - 'COMMITTED' | 'CLAIMED' | 'EXPIRED'
 */

/**
 * 로또 커밋 기록을 localStorage 히스토리에 추가합니다.
 * 최대 100개를 유지하며, 초과 시 오래된 항목을 제거합니다.
 * @param {LottoCommit} data - 저장할 커밋 데이터
 */
export function saveLottoCommit(data) {
  const list = loadLottoHistory()
  list.unshift(data)
  localStorage.setItem(STORAGE_KEYS.LOTTO_HISTORY, JSON.stringify(list.slice(0, 100)))
}

/**
 * localStorage에서 로또 히스토리를 불러옵니다.
 * @returns {LottoCommit[]} 히스토리 배열 (없으면 빈 배열)
 */
export function loadLottoHistory() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEYS.LOTTO_HISTORY) || '[]')
  } catch {
    return []
  }
}
