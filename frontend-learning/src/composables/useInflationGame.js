/**
 * @module useInflationGame
 * @description Chapter 1 인플레이션 시뮬레이션의 게임 로직을 담당하는 컴포저블.
 *
 * View(Chapter1.vue)는 UI 렌더링에만 집중하고,
 * 게임 상태·인터벌·물가 계산 등 비즈니스 로직은 이 컴포저블에서 관리합니다.
 *
 * 인플레이션 가속 조건:
 *   잔액이 CH1.INFLATION_DOUBLE_TRIGGER 이상이 되면 중앙은행 이벤트가 발생하여
 *   물가 상승 속도가 2배로 빨라집니다. 이를 통해 "열심히 벌수록 물가도 더 빨리 오른다"는
 *   경제적 아이러니를 체험하게 합니다.
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import { CH1 } from '../config'

/**
 * @typedef {Object} InflationGameReturn
 * @property {import('vue').Ref<number>}   balance            - 현재 잔액 (원)
 * @property {import('vue').Ref<number>}   chickenPrice       - 치킨 가격 (원)
 * @property {import('vue').Ref<number>}   rentPrice          - 월세 (원)
 * @property {import('vue').Ref<number>}   eggPrice           - 계란 가격 (원)
 * @property {import('vue').Ref<boolean>}  inflationDoubled   - 인플레이션 2배 상태 여부
 * @property {import('vue').Ref<boolean>}  showCentralBankBanner - 중앙은행 배너 표시 여부
 * @property {import('vue').Ref<boolean>}  shakeChicken       - 치킨 가격 흔들림 애니메이션
 * @property {import('vue').Ref<boolean>}  shakeRent          - 월세 흔들림 애니메이션
 * @property {import('vue').Ref<boolean>}  shakeEgg           - 계란 가격 흔들림 애니메이션
 * @property {import('vue').Ref<number[]>} balanceHistory     - 잔액 히스토리 (SVG 차트용)
 * @property {import('vue').Ref<number[]>} chickenHistory     - 치킨 가격 히스토리
 * @property {import('vue').ComputedRef<number>} inflationProgress - 인플레이션 진행도 (0~1)
 * @property {number}   MAX_HISTORY - 그래프 최대 포인트 수
 * @property {Function} formatWon   - (n: number) => string  원화 포맷
 * @property {Function} earn        - 돈 벌기 (+CH1.EARN_PER_CLICK)
 * @property {Function} startGame   - 인플레이션 시뮬레이션 시작
 */

/**
 * 인플레이션 시뮬레이션 게임 상태와 로직을 제공합니다.
 * @returns {InflationGameReturn}
 */
export function useInflationGame() {
  // ── 상태 ────────────────────────────────────────────────
  const balance = ref(CH1.INIT_BALANCE)
  const chickenPrice = ref(CH1.INIT_CHICKEN_PRICE)
  const rentPrice = ref(CH1.INIT_RENT_PRICE)
  const eggPrice = ref(CH1.INIT_EGG_PRICE)

  const inflationDoubled = ref(false)
  const showCentralBankBanner = ref(false)

  const shakeChicken = ref(false)
  const shakeRent = ref(false)
  const shakeEgg = ref(false)

  /** SVG 라인 차트용 히스토리 버퍼 */
  const balanceHistory = ref([])
  const chickenHistory = ref([])
  const MAX_HISTORY = CH1.MAX_HISTORY

  let inflationInterval = null
  let historyInterval = null

  // ── 계산된 값 ──────────────────────────────────────────
  /**
   * 인플레이션 진행도 (0 ~ 1).
   * 배경 오버레이 강도 계산에 사용합니다.
   */
  const inflationProgress = computed(() => {
    const min = CH1.INIT_CHICKEN_PRICE
    const max = CH1.GAME_OVER_PRICE
    return Math.min((chickenPrice.value - min) / (max - min), 1)
  })

  // ── 포맷 ────────────────────────────────────────────────
  /**
   * @param {number} n - 금액(원)
   * @returns {string} 예: "₩1,000"
   */
  function formatWon(n) {
    return '₩' + n.toLocaleString('ko-KR')
  }

  // ── 인터랙션 ────────────────────────────────────────────
  /** 돈 벌기 버튼 핸들러 */
  function earn() {
    balance.value += CH1.EARN_PER_CLICK
  }

  /** step 3 시작: 인플레이션 및 히스토리 추적 인터벌 시작 */
  function startGame(stepRef) {
    balanceHistory.value = [balance.value]
    chickenHistory.value = [chickenPrice.value]
    startInflation(stepRef)
    startHistoryTracking(stepRef)
  }

  function triggerShake(refObj) {
    refObj.value = true
    setTimeout(() => { refObj.value = false }, 400)
  }

  /**
   * 재귀 setTimeout 기반 인플레이션 틱.
   * inflationDoubled 상태에 따라 틱 간격이 동적으로 바뀌므로
   * setInterval 대신 setTimeout 재귀를 사용합니다.
   */
  function startInflation(stepRef) {
    const interval = () => (inflationDoubled.value ? CH1.INFLATION_FAST_MS : CH1.INFLATION_INTERVAL_MS)

    function tick() {
      if (stepRef.value !== 3) return

      chickenPrice.value += CH1.CHICKEN_RISE
      rentPrice.value += CH1.RENT_RISE
      eggPrice.value += CH1.EGG_RISE

      triggerShake(shakeChicken)
      triggerShake(shakeRent)
      triggerShake(shakeEgg)

      if (chickenPrice.value > CH1.GAME_OVER_PRICE) {
        stepRef.value = 4
        clearAllIntervals()
        return
      }

      inflationInterval = setTimeout(tick, interval())
    }

    inflationInterval = setTimeout(tick, interval())
  }

  /** 일정 주기로 잔액·가격 히스토리를 기록합니다 (SVG 차트용). */
  function startHistoryTracking(stepRef) {
    historyInterval = setInterval(() => {
      if (stepRef.value !== 3) return
      balanceHistory.value.push(balance.value)
      chickenHistory.value.push(chickenPrice.value)
      if (balanceHistory.value.length > MAX_HISTORY) {
        balanceHistory.value.shift()
        chickenHistory.value.shift()
      }
    }, CH1.INFLATION_INTERVAL_MS)
  }

  function clearAllIntervals() {
    if (inflationInterval) { clearTimeout(inflationInterval); inflationInterval = null }
    if (historyInterval) { clearInterval(historyInterval); historyInterval = null }
  }

  // ── 중앙은행 이벤트 감시 ────────────────────────────────
  /**
   * 잔액이 트리거 임계값에 도달하면 인플레이션 속도를 2배로 올립니다.
   * step === 3 조건으로 게임 중에만 발동합니다.
   */
  watch(balance, (val, _prev, onCleanup) => {
    // onCleanup은 사용하지 않지만 watch 시그니처 유지
    void onCleanup
    if (val >= CH1.INFLATION_DOUBLE_TRIGGER && !inflationDoubled.value) {
      inflationDoubled.value = true
      showCentralBankBanner.value = true
      const t = setTimeout(() => { showCentralBankBanner.value = false }, 4000)
      // watch 재실행 시 타이머 클리어 (반응성 사이클 보호)
      onCleanup(() => clearTimeout(t))
    }
  })

  onUnmounted(clearAllIntervals)

  return {
    balance, chickenPrice, rentPrice, eggPrice,
    inflationDoubled, showCentralBankBanner,
    shakeChicken, shakeRent, shakeEgg,
    balanceHistory, chickenHistory,
    MAX_HISTORY, inflationProgress,
    formatWon, earn, startGame,
  }
}
