/**
 * @module useLottoDemoGame
 * @description Chapter 3 Commit-Reveal 체험 게임 로직을 담당하는 컴포저블.
 *
 * View(Chapter3.vue)는 UI 렌더링에만 집중하고,
 * 게임 플로우·해시 계산·카운트다운 등 비즈니스 로직은 이 컴포저블에서 관리합니다.
 *
 * 실제 체인과의 차이:
 *   - 실제 체인: N+30 블록 이후 Reveal 가능
 *   - 체험 모드: CH3.WAIT_COUNTDOWN_SEC 초 대기 후 즉시 Reveal
 *   - 해시: 실제 SHA-256 대신 경량 폴리노미얼 해시 사용 (브라우저 부담 최소화)
 */
import { ref, computed, onUnmounted } from 'vue'
import { CH3 } from '../config'

/**
 * @typedef {Object} DemoCommitPayload
 * @property {string}   nonce      - 랜덤 nonce (hex)
 * @property {number[]} myNumbers  - 선택 번호 배열 (0~15)
 * @property {string}   commitHash - 계산된 Commit Hash
 */

/**
 * @typedef {Object} ComparisonSlot
 * @property {number}  mine   - 내 번호 (0~15)
 * @property {number}  target - 블록 digit (0~15)
 * @property {boolean} match  - 일치 여부
 */

/**
 * @typedef {Object} PrizeInfo
 * @property {string} rank   - 등수 레이블 (예: '1등')
 * @property {string} medal  - 이모지 메달
 * @property {string} reward - 보상 설명
 */

/**
 * @typedef {Object} MinedBlock
 * @property {number} id     - 고유 ID (블록 번호)
 * @property {number} num    - 블록 번호
 * @property {string} hash   - 축약 해시 (예: '0xa1b2c3d4...')
 * @property {number} reward - 채굴자 보상 (JACK)
 */

/**
 * @typedef {Object} LottoDemoReturn
 * @property {import('vue').Ref<number>}           step            - 현재 스텝 (1|2|3)
 * @property {import('vue').Ref<number[]>}          chosenNumbers   - 선택한 번호 배열
 * @property {import('vue').Ref<boolean>}           isCommitting    - Commit 처리 중 여부
 * @property {import('vue').Ref<string>}            animatedHash    - 점진적으로 표시되는 해시
 * @property {import('vue').Ref<number>}            countdown       - 남은 카운트다운(초)
 * @property {import('vue').Ref<MinedBlock[]>}      minedBlocks     - 실시간 채굴 블록 목록
 * @property {import('vue').Ref<DemoCommitPayload>} savedData       - 저장된 Commit 데이터
 * @property {import('vue').Ref<number>}            revealPhase     - 결과 공개 단계 (0~5)
 * @property {import('vue').Ref<ComparisonSlot[]>}  comparisonSlots - 슬롯별 비교 결과
 * @property {import('vue').Ref<number>}            matchCount      - 일치 슬롯 수
 * @property {import('vue').Ref<boolean>}           showConfetti    - 컨페티 표시 여부
 * @property {import('vue').ComputedRef<number>}    progressPercent - 진행바 %
 * @property {import('vue').ComputedRef<PrizeInfo>} prizeInfo       - 등수 정보
 * @property {import('vue').ComputedRef<string>}    prizeClass      - CSS 클래스
 * @property {number}   ch3WaitSec  - 대기 시간(초) — 템플릿 표시용
 * @property {Function} cycleSlot   - (idx) 슬롯 순환
 * @property {Function} incrementSlot - (idx) 슬롯 증가
 * @property {Function} decrementSlot - (idx) 슬롯 감소
 * @property {Function} randomize   - 전체 랜덤 생성
 * @property {Function} doCommit    - Commit 처리 (async)
 * @property {Function} resetAll    - 초기화
 * @property {Function} getConfettiStyle - (i) 컨페티 파편 스타일
 */

/**
 * Commit-Reveal 체험 게임 상태와 로직을 제공합니다.
 * @returns {LottoDemoReturn}
 */
export function useLottoDemoGame() {
  const step = ref(1)
  const chosenNumbers = ref(Array(CH3.SLOT_COUNT).fill(0))
  const activeSlot = ref(null)
  const isCommitting = ref(false)
  const animatedHash = ref('')

  // Step 2
  const countdown = ref(CH3.WAIT_COUNTDOWN_SEC)
  const minedBlocks = ref([])
  let countdownTimer = null
  let blockTimer = null
  let baseBlockNum = 1240 + Math.floor(Math.random() * 20)

  // Step 3
  const savedData = ref({ nonce: '', myNumbers: [], commitHash: '' })
  const revealPhase = ref(0)
  const comparisonSlots = ref([])
  const matchCount = ref(0)
  const showConfetti = ref(false)
  let revealTimers = []

  // ── Computed ──────────────────────────────────────────────────────────────────

  const progressPercent = computed(
    () => ((CH3.WAIT_COUNTDOWN_SEC - countdown.value) / CH3.WAIT_COUNTDOWN_SEC) * 100
  )

  /**
   * matchCount에 따른 등수 정보를 반환합니다.
   * PRIZE_TABLE을 순서대로 탐색하여 첫 번째 충족 항목을 반환합니다.
   */
  const prizeInfo = computed(() => {
    const n = matchCount.value
    return CH3.PRIZE_TABLE.find(p => n >= p.min) || CH3.PRIZE_TABLE[CH3.PRIZE_TABLE.length - 1]
  })

  const prizeClass = computed(() => {
    const n = matchCount.value
    if (n >= CH3.SLOT_COUNT) return 'prize-jackpot'
    if (n >= 4) return 'prize-high'
    if (n >= 2) return 'prize-mid'
    return 'prize-low'
  })

  // ── Step 1 헬퍼 ──────────────────────────────────────────────────────────────

  function cycleSlot(idx) {
    activeSlot.value = idx
    chosenNumbers.value[idx] = (chosenNumbers.value[idx] + 1) % 16
  }

  function incrementSlot(idx) {
    activeSlot.value = idx
    chosenNumbers.value[idx] = (chosenNumbers.value[idx] + 1) % 16
  }

  function decrementSlot(idx) {
    activeSlot.value = idx
    chosenNumbers.value[idx] = (chosenNumbers.value[idx] + 15) % 16
  }

  function randomize() {
    const arr = new Uint8Array(CH3.SLOT_COUNT)
    crypto.getRandomValues(arr)
    chosenNumbers.value = Array.from(arr).map(v => v % 16)
  }

  /**
   * 경량 폴리노미얼 해시 (체험용).
   * 실제 SHA-256 대신 사용하여 브라우저 비동기 처리 없이 즉시 계산합니다.
   * @param {string} input
   * @returns {string} '0x' + 64자 hex 유사 문자열
   */
  function simpleHash(input) {
    let h1 = 0xdeadbeef, h2 = 0x41c6ce57
    for (let i = 0; i < input.length; i++) {
      const ch = input.charCodeAt(i)
      h1 = Math.imul(h1 ^ ch, 2654435761)
      h2 = Math.imul(h2 ^ ch, 1597334677)
    }
    h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507)
    h1 ^= Math.imul(h2 ^ (h2 >>> 13), 3266489909)
    h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507)
    h2 ^= Math.imul(h1 ^ (h1 >>> 13), 3266489909)
    const base = btoa(input + h1.toString(16) + h2.toString(16))
    let hex = ''
    for (let i = 0; i < base.length && hex.length < 64; i++) {
      hex += base.charCodeAt(i).toString(16).padStart(2, '0')
    }
    return '0x' + hex.slice(0, 64)
  }

  function generateNonce() {
    const arr = new Uint8Array(32)
    crypto.getRandomValues(arr)
    return Array.from(arr).map(b => b.toString(16).padStart(2, '0')).join('')
  }

  function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms))
  }

  /** Commit: 번호 + nonce를 해시하여 localStorage에 저장하고 Step 2로 전환합니다. */
  async function doCommit() {
    isCommitting.value = true
    const nonce = generateNonce()
    const myNumbers = [...chosenNumbers.value]
    const raw = nonce + myNumbers.join('-')
    const commitHash = simpleHash(raw)

    // 해시를 점진적으로 보여주는 애니메이션
    animatedHash.value = ''
    for (let i = 0; i < commitHash.length; i += 3) {
      await delay(30)
      animatedHash.value = commitHash.slice(0, i + 3)
    }
    animatedHash.value = commitHash
    await delay(1200)

    const payload = { nonce, myNumbers, commitHash }
    localStorage.setItem('chapter3_commit', JSON.stringify(payload))
    savedData.value = payload

    isCommitting.value = false
    step.value = 2
    startCountdown()
  }

  // ── Step 2 헬퍼 ──────────────────────────────────────────────────────────────

  function randomHex(len) {
    const chars = '0123456789abcdef'
    let s = '0x'
    for (let i = 0; i < len; i++) s += chars[Math.floor(Math.random() * 16)]
    return s
  }

  function randomBlockReward() {
    return Math.floor(Math.random() * 100) + 10
  }

  /** 카운트다운 및 블록 생성 시뮬레이션을 시작합니다. */
  function startCountdown() {
    countdown.value = CH3.WAIT_COUNTDOWN_SEC
    minedBlocks.value = []

    countdownTimer = setInterval(() => {
      countdown.value--
      if (countdown.value <= 0) {
        clearInterval(countdownTimer)
        clearInterval(blockTimer)
        step.value = 3
        loadAndReveal()
      }
    }, 1000)

    blockTimer = setInterval(() => {
      baseBlockNum++
      minedBlocks.value.unshift({
        id: baseBlockNum,
        num: baseBlockNum,
        hash: randomHex(8) + '...',
        reward: randomBlockReward(),
      })
      if (minedBlocks.value.length > 6) minedBlocks.value.pop()
    }, 1000)
  }

  // ── Step 3 헬퍼 ──────────────────────────────────────────────────────────────

  /** localStorage에서 커밋 데이터를 읽어 단계별 공개 애니메이션을 시작합니다. */
  function loadAndReveal() {
    const raw = localStorage.getItem('chapter3_commit')
    if (raw) savedData.value = JSON.parse(raw)

    const targets = Array.from({ length: CH3.SLOT_COUNT }, () => Math.floor(Math.random() * 16))
    const slots = savedData.value.myNumbers.map((mine, i) => ({
      mine,
      target: targets[i],
      match: mine === targets[i],
    }))
    comparisonSlots.value = slots
    matchCount.value = slots.filter(s => s.match).length

    revealPhase.value = 0
    const phases = [1, 2, 3, 4, 5]
    phases.forEach((phase, i) => {
      const t = setTimeout(() => {
        revealPhase.value = phase
        if (phase === 5 && matchCount.value >= CH3.CONFETTI_MATCH_THRESHOLD) {
          showConfetti.value = true
          const ct = setTimeout(() => { showConfetti.value = false }, 4000)
          revealTimers.push(ct)
        }
      }, (i + 1) * 1200)
      revealTimers.push(t)
    })
  }

  /**
   * 컨페티 파편의 인라인 스타일을 생성합니다.
   * @param {number} i - 파편 인덱스 (1-based)
   * @returns {object} 인라인 스타일 객체
   */
  function getConfettiStyle(i) {
    const colors = ['#FFD700','#007AFF','#00FF88','#FF6B6B','#C678DD','#E5C07B','#61AFEF','#FF8C00','#00CED1','#FF1493','#ADFF2F','#FF69B4']
    return {
      left: `${(i * 8.3) % 100}%`,
      animationDelay: `${(i * 0.15) % 1.5}s`,
      width: `${8 + (i % 5) * 3}px`,
      height: `${8 + (i % 5) * 3}px`,
      background: colors[i % colors.length],
      animationDuration: `${1.5 + (i % 3) * 0.4}s`,
    }
  }

  function clearAll() {
    clearInterval(countdownTimer)
    clearInterval(blockTimer)
    revealTimers.forEach(t => clearTimeout(t))
    revealTimers = []
  }

  function resetAll() {
    clearAll()
    step.value = 1
    chosenNumbers.value = Array(CH3.SLOT_COUNT).fill(0)
    activeSlot.value = null
    isCommitting.value = false
    animatedHash.value = ''
    countdown.value = CH3.WAIT_COUNTDOWN_SEC
    minedBlocks.value = []
    revealPhase.value = 0
    comparisonSlots.value = []
    matchCount.value = 0
    showConfetti.value = false
    localStorage.removeItem('chapter3_commit')
  }

  onUnmounted(clearAll)

  return {
    step, chosenNumbers, isCommitting, animatedHash,
    countdown, minedBlocks,
    savedData, revealPhase, comparisonSlots, matchCount, showConfetti,
    progressPercent, prizeInfo, prizeClass,
    ch3WaitSec: CH3.WAIT_COUNTDOWN_SEC,
    cycleSlot, incrementSlot, decrementSlot, randomize,
    doCommit, resetAll, getConfettiStyle,
  }
}
