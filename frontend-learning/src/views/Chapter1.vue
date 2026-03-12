<template>
  <div class="chapter-wrapper" :style="wrapperStyle">
    <!-- 물가 상승 오버레이 -->
    <div class="inflation-overlay" :style="overlayStyle"></div>

    <!-- 중앙은행 배너 -->
    <transition name="banner-slide">
      <div v-if="showCentralBankBanner" class="central-bank-banner">
        🏦 중앙은행: 화폐 추가 발행 승인! 물가 상승 속도 2배!
      </div>
    </transition>

    <div class="content-container">
      <!-- 상단 네비게이션 -->
      <div class="nav-bar">
        <RouterLink to="/" class="nav-link">← 홈으로</RouterLink>
        <span class="chapter-label">Chapter 1</span>
      </div>

      <!-- ───────────────── STEP 1: 인트로 ───────────────── -->
      <transition name="fade">
        <div v-if="step === 1" class="step-container">
          <div class="glass-card intro-card">
            <div class="chapter-badge">CHAPTER 01</div>
            <h1 class="intro-title">자취생의 절규</h1>
            <h2 class="intro-subtitle">내 월급 vs 미친 물가</h2>
            <div class="divider"></div>
            <p class="intro-message">
              아무리 열심히 일해도<br />
              <span class="highlight">물가를 이길 수 없다면?</span>
            </p>
            <p class="intro-desc">
              중앙은행이 화폐를 찍어낼수록<br />
              당신의 저축은 조용히 녹아내립니다.
            </p>
            <button class="btn-primary" @click="step = 2">시작하기</button>
          </div>
        </div>
      </transition>

      <!-- ───────────────── STEP 2: 초기 세팅 ───────────────── -->
      <transition name="fade">
        <div v-if="step === 2" class="step-container">
          <h2 class="step-title">현재 상황을 확인하세요</h2>
          <div class="two-col">
            <!-- 왼쪽: 내 지갑 -->
            <div class="glass-card wallet-card">
              <div class="card-label">나의 지갑 잔액</div>
              <div class="wallet-amount">{{ formatWon(balance) }}</div>
              <button class="btn-earn" @click="earn">💰 돈 벌기 +{{ formatWon(ch1EarnPerClick) }}</button>
            </div>
            <!-- 오른쪽: 생존 장바구니 -->
            <div class="glass-card basket-card">
              <div class="card-label">🛒 생존 장바구니</div>
              <ul class="basket-list">
                <li>
                  <span class="item-icon">🍗</span>
                  <span class="item-name">치킨 한 마리</span>
                  <span class="item-price">{{ formatWon(chickenPrice) }}</span>
                </li>
                <li>
                  <span class="item-icon">🏠</span>
                  <span class="item-name">다음 달 월세</span>
                  <span class="item-price">{{ formatWon(rentPrice) }}</span>
                </li>
                <li>
                  <span class="item-icon">🥚</span>
                  <span class="item-name">계란 한 판</span>
                  <span class="item-price">{{ formatWon(eggPrice) }}</span>
                </li>
              </ul>
            </div>
          </div>
          <button class="btn-primary" @click="startGame">게임 시작</button>
        </div>
      </transition>

      <!-- ───────────────── STEP 3: 핵심 인터랙션 ───────────────── -->
      <transition name="fade">
        <div v-if="step === 3" class="step-container">
          <h2 class="step-title rat-race-title">🐭 THE RAT RACE</h2>

          <div class="two-col">
            <!-- 내 지갑 -->
            <div class="glass-card wallet-card">
              <div class="card-label">나의 지갑 잔액</div>
              <div class="wallet-amount">{{ formatWon(balance) }}</div>
              <button class="btn-earn btn-earn-active" @click="earn">
                💰 돈 벌기<br /><small>+{{ formatWon(ch1EarnPerClick) }}</small>
              </button>
              <div class="earn-hint">클릭해서 돈을 버세요!</div>
            </div>

            <!-- 물가 현황 -->
            <div class="glass-card basket-card">
              <div class="card-label">📈 실시간 물가</div>
              <ul class="basket-list">
                <li>
                  <span class="item-icon">🍗</span>
                  <span class="item-name">치킨 한 마리</span>
                  <span
                    class="item-price"
                    :class="{ shake: shakeChicken }"
                  >{{ formatWon(chickenPrice) }}</span>
                </li>
                <li>
                  <span class="item-icon">🏠</span>
                  <span class="item-name">다음 달 월세</span>
                  <span
                    class="item-price"
                    :class="{ shake: shakeRent }"
                  >{{ formatWon(rentPrice) }}</span>
                </li>
                <li>
                  <span class="item-icon">🥚</span>
                  <span class="item-name">계란 한 판</span>
                  <span
                    class="item-price"
                    :class="{ shake: shakeEgg }"
                  >{{ formatWon(eggPrice) }}</span>
                </li>
              </ul>
              <div class="inflation-speed-indicator">
                <span class="speed-label">물가 상승 속도</span>
                <span class="speed-value" :class="{ 'speed-doubled': inflationDoubled }">
                  {{ inflationDoubled ? '🔥 2배 가속 중!' : '⚡ 상승 중' }}
                </span>
              </div>
            </div>
          </div>

          <!-- 결과 보기 버튼 -->
          <button class="btn-primary" @click="showResult">결과 확인하기 →</button>

          <!-- 실시간 SVG 라인 차트 -->
          <div class="glass-card chart-card">
            <div class="chart-title">📊 내 수입 vs 치킨 가격 (실시간)</div>
            <div class="chart-wrapper">
              <svg
                ref="chartSvg"
                class="line-chart"
                viewBox="0 0 600 180"
                preserveAspectRatio="none"
              >
                <!-- 그리드 라인 -->
                <line x1="0" y1="36" x2="600" y2="36" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>
                <line x1="0" y1="72" x2="600" y2="72" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>
                <line x1="0" y1="108" x2="600" y2="108" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>
                <line x1="0" y1="144" x2="600" y2="144" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>

                <!-- 내 수입 라인 -->
                <polyline
                  v-if="balanceHistory.length > 1"
                  :points="balancePoints"
                  fill="none"
                  stroke="#007AFF"
                  stroke-width="2.5"
                  stroke-linejoin="round"
                  stroke-linecap="round"
                />
                <!-- 치킨 가격 라인 -->
                <polyline
                  v-if="chickenHistory.length > 1"
                  :points="chickenPoints"
                  fill="none"
                  stroke="#FF3B30"
                  stroke-width="2.5"
                  stroke-linejoin="round"
                  stroke-linecap="round"
                />

                <!-- 레전드 -->
                <circle cx="16" cy="170" r="5" fill="#007AFF"/>
                <text x="26" y="174" fill="rgba(255,255,255,0.7)" font-size="11" font-family="JetBrains Mono, monospace">내 잔액</text>
                <circle cx="90" cy="170" r="5" fill="#FF3B30"/>
                <text x="100" y="174" fill="rgba(255,255,255,0.7)" font-size="11" font-family="JetBrains Mono, monospace">치킨 가격</text>
              </svg>
            </div>
          </div>
        </div>
      </transition>

      <!-- ───────────────── STEP 4: 결과 ───────────────── -->
      <transition name="fade">
        <div v-if="step === 4" class="step-container">
          <div class="glass-card result-card">
            <div class="result-badge">GAME OVER</div>
            <h2 class="result-title">물가가 당신을 이겼습니다</h2>

            <div class="result-compare">
              <div class="compare-item compare-you">
                <div class="compare-label">당신이 번 돈</div>
                <div class="compare-amount you-amount">{{ formatWon(balance) }}</div>
              </div>
              <div class="compare-vs">VS</div>
              <div class="compare-item compare-chicken">
                <div class="compare-label">치킨 한 마리</div>
                <div class="compare-amount chicken-amount">{{ formatWon(chickenPrice) }}</div>
              </div>
            </div>

            <div class="quote-box">
              <div class="quote-mark">"</div>
              <p class="quote-text">
                당신의 노동은 정직했지만,<br />
                화폐의 가치는 정직하지 않았습니다.
              </p>
              <div class="quote-mark closing">"</div>
            </div>

            <div class="teaser-text">
              누구도 마음대로 찍어낼 수 없는 자산이 있다면?
            </div>

            <RouterLink to="/chapter2" class="btn-primary btn-next">
              Chapter 2로 이동 →
            </RouterLink>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup>
/**
 * Chapter1.vue — UI 렌더링 전담
 * 게임 비즈니스 로직(상태·인터벌·물가 계산)은 useInflationGame 컴포저블에 위임합니다.
 */
import { ref, computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useInflationGame } from '../composables/useInflationGame'
import { CH1 } from '../config'

// ─── 게임 로직 (컴포저블에서 주입) ──────────────────────
const {
  balance, chickenPrice, rentPrice, eggPrice,
  inflationDoubled, showCentralBankBanner,
  shakeChicken, shakeRent, shakeEgg,
  balanceHistory, chickenHistory,
  MAX_HISTORY, inflationProgress,
  formatWon, earn, startGame: _startGame, stopGame,
} = useInflationGame()

const ch1EarnPerClick = CH1.EARN_PER_CLICK

// ─── UI 전용 상태 ────────────────────────────────────────
const step = ref(1)

// ─── 스타일 (UI 관심사) ──────────────────────────────────
const wrapperStyle = computed(() => ({ background: '#080808' }))

const overlayStyle = computed(() => {
  if (step.value !== 3 && step.value !== 4) return { opacity: 0 }
  return {
    background: `rgba(255, 0, 0, ${inflationProgress.value * 0.15})`,
    opacity: 1,
  }
})

// ─── 게임 시작 브릿지 ────────────────────────────────────
function startGame() {
  step.value = 3
  _startGame()
}

function showResult() {
  stopGame()
  step.value = 4
}

// ─── SVG 차트 포인트 계산 (뷰 표현 로직) ─────────────────
const SVG_W = 600
const SVG_H = 160

function toPoints(history, allValues) {
  if (history.length < 2) return ''
  const maxVal = Math.max(...allValues, 1)
  const minVal = Math.min(...allValues, 0)
  const range = maxVal - minVal || 1
  return history
    .map((v, i) => {
      const x = (i / (MAX_HISTORY - 1)) * SVG_W
      const y = SVG_H - ((v - minVal) / range) * (SVG_H - 20) - 5
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

const balancePoints = computed(() => {
  const allVals = [...balanceHistory.value, ...chickenHistory.value]
  return toPoints(balanceHistory.value, allVals)
})

const chickenPoints = computed(() => {
  const allVals = [...balanceHistory.value, ...chickenHistory.value]
  return toPoints(chickenHistory.value, allVals)
})
</script>

<style scoped>
/* ── 기본 레이아웃 ──────────────────────────────────────── */
.chapter-wrapper {
  min-height: 100vh;
  width: 100%;
  position: relative;
  font-family: 'JetBrains Mono', 'Courier New', monospace;
  color: #ffffff;
  overflow-x: hidden;
}

.inflation-overlay {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 1;
  transition: background 0.6s ease;
}

.content-container {
  position: relative;
  z-index: 2;
  max-width: 760px;
  margin: 0 auto;
  padding: 24px 20px 60px;
}

/* ── 네비게이션 ─────────────────────────────────────────── */
.nav-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
}

.nav-link {
  color: rgba(255, 255, 255, 0.5);
  text-decoration: none;
  font-size: 13px;
  letter-spacing: 0.05em;
  transition: color 0.2s;
}
.nav-link:hover { color: rgba(255, 255, 255, 0.9); }

.chapter-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.3);
  letter-spacing: 0.15em;
  text-transform: uppercase;
}

/* ── 중앙은행 배너 ──────────────────────────────────────── */
.central-bank-banner {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  background: linear-gradient(90deg, #8B0000, #FF0000, #8B0000);
  color: #fff;
  text-align: center;
  padding: 14px 20px;
  font-size: 14px;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  letter-spacing: 0.04em;
  box-shadow: 0 4px 24px rgba(255, 0, 0, 0.5);
}

.banner-slide-enter-active,
.banner-slide-leave-active {
  transition: transform 0.4s ease, opacity 0.4s ease;
}
.banner-slide-enter-from { transform: translateY(-100%); opacity: 0; }
.banner-slide-leave-to   { transform: translateY(-100%); opacity: 0; }

/* ── glass-card ─────────────────────────────────────────── */
.glass-card {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 16px;
  padding: 28px 24px;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

/* ── 페이드 트랜지션 ─────────────────────────────────────── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.45s ease, transform 0.45s ease;
}
.fade-enter-from { opacity: 0; transform: translateY(18px); }
.fade-leave-to   { opacity: 0; transform: translateY(-10px); }

/* ── 스텝 공통 ──────────────────────────────────────────── */
.step-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.step-title {
  font-size: 20px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.85);
  text-align: center;
  margin: 0 0 4px;
  letter-spacing: 0.05em;
}

.rat-race-title {
  font-size: 24px;
  color: #FF3B30;
  text-shadow: 0 0 20px rgba(255, 59, 48, 0.5);
}

/* ── 2열 레이아웃 ───────────────────────────────────────── */
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
@media (max-width: 560px) {
  .two-col { grid-template-columns: 1fr; }
}

/* ── STEP 1: 인트로 카드 ────────────────────────────────── */
.intro-card {
  text-align: center;
  padding: 48px 32px;
}

.chapter-badge {
  display: inline-block;
  font-size: 11px;
  letter-spacing: 0.2em;
  color: #007AFF;
  border: 1px solid rgba(0, 122, 255, 0.4);
  border-radius: 20px;
  padding: 4px 14px;
  margin-bottom: 20px;
}

.intro-title {
  font-size: 36px;
  font-weight: 800;
  margin: 0 0 8px;
  letter-spacing: -0.01em;
  background: linear-gradient(135deg, #ffffff, rgba(255,255,255,0.6));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.intro-subtitle {
  font-size: 16px;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.45);
  margin: 0 0 24px;
  letter-spacing: 0.05em;
}

.divider {
  width: 48px;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
  margin: 0 auto 24px;
}

.intro-message {
  font-size: 18px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.75);
  margin: 0 0 12px;
}

.highlight {
  color: #FF3B30;
  font-weight: 700;
}

.intro-desc {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.35);
  line-height: 1.8;
  margin: 0 0 36px;
}

/* ── 버튼 ───────────────────────────────────────────────── */
.btn-primary {
  display: block;
  width: 100%;
  max-width: 342px;
  height: 64px;
  margin: 0 auto;
  background: #007AFF;
  color: #fff;
  border: none;
  border-radius: 14px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.05em;
  cursor: pointer;
  text-decoration: none;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s, transform 0.1s, box-shadow 0.2s;
  box-shadow: 0 4px 20px rgba(0, 122, 255, 0.35);
}
.btn-primary:hover {
  background: #0063D1;
  box-shadow: 0 6px 28px rgba(0, 122, 255, 0.5);
}
.btn-primary:active { transform: scale(0.97); }

.btn-next {
  width: 100%;
  max-width: 342px;
}

/* ── 지갑 카드 ──────────────────────────────────────────── */
.card-label {
  font-size: 11px;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: 12px;
}

.wallet-amount {
  font-size: 28px;
  font-weight: 800;
  color: #34C759;
  margin-bottom: 20px;
  letter-spacing: -0.02em;
  text-shadow: 0 0 20px rgba(52, 199, 89, 0.4);
}

.btn-earn {
  width: 100%;
  padding: 14px;
  background: rgba(52, 199, 89, 0.15);
  border: 1px solid rgba(52, 199, 89, 0.35);
  border-radius: 12px;
  color: #34C759;
  font-family: 'JetBrains Mono', monospace;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.15s, transform 0.1s, box-shadow 0.2s;
  line-height: 1.4;
}
.btn-earn:hover {
  background: rgba(52, 199, 89, 0.25);
  box-shadow: 0 0 16px rgba(52, 199, 89, 0.3);
}
.btn-earn:active { transform: scale(0.96); }

.btn-earn-active {
  animation: pulse-earn 2s infinite;
}

@keyframes pulse-earn {
  0%, 100% { box-shadow: 0 0 0 0 rgba(52, 199, 89, 0.4); }
  50%       { box-shadow: 0 0 0 8px rgba(52, 199, 89, 0); }
}

.earn-hint {
  margin-top: 10px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.3);
  text-align: center;
}

/* ── 장바구니 ───────────────────────────────────────────── */
.basket-list {
  list-style: none;
  padding: 0;
  margin: 0 0 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.basket-list li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.07);
}

.item-icon { font-size: 18px; flex-shrink: 0; }

.item-name {
  flex: 1;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  letter-spacing: 0.03em;
}

.item-price {
  font-size: 14px;
  font-weight: 700;
  color: #FF3B30;
  display: inline-block;
  transition: color 0.2s;
}

/* ── shake 애니메이션 ────────────────────────────────────── */
@keyframes shake {
  0%  { transform: translateX(0); }
  20% { transform: translateX(-4px); color: #FF6B6B; }
  40% { transform: translateX(4px);  color: #FF0000; }
  60% { transform: translateX(-3px); }
  80% { transform: translateX(3px);  }
  100%{ transform: translateX(0); }
}

.shake {
  animation: shake 0.4s ease;
}

/* ── 물가 속도 인디케이터 ───────────────────────────────── */
.inflation-speed-indicator {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.speed-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
  letter-spacing: 0.08em;
}

.speed-value {
  font-size: 12px;
  color: rgba(255, 200, 0, 0.8);
  font-weight: 700;
}

.speed-doubled {
  color: #FF3B30;
  animation: blink 0.8s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.4; }
}

/* ── 차트 카드 ──────────────────────────────────────────── */
.chart-card {
  padding: 20px 20px 16px;
}

.chart-title {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.55);
  margin-bottom: 16px;
  letter-spacing: 0.05em;
}

.chart-wrapper {
  width: 100%;
  overflow: hidden;
  border-radius: 8px;
}

.line-chart {
  width: 100%;
  height: 180px;
  display: block;
}

/* ── STEP 4: 결과 카드 ──────────────────────────────────── */
.result-card {
  text-align: center;
  padding: 48px 32px;
}

.result-badge {
  display: inline-block;
  font-size: 11px;
  letter-spacing: 0.2em;
  color: #FF3B30;
  border: 1px solid rgba(255, 59, 48, 0.4);
  border-radius: 20px;
  padding: 4px 14px;
  margin-bottom: 16px;
}

.result-title {
  font-size: 24px;
  font-weight: 800;
  margin: 0 0 32px;
  color: rgba(255, 255, 255, 0.85);
}

.result-compare {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  margin-bottom: 32px;
  flex-wrap: wrap;
}

.compare-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.compare-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.compare-amount {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.you-amount { color: #34C759; }
.chicken-amount {
  color: #FF3B30;
  text-shadow: 0 0 20px rgba(255, 59, 48, 0.5);
}

.compare-vs {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.25);
  font-weight: 700;
  letter-spacing: 0.1em;
}

.quote-box {
  position: relative;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 24px 28px;
  margin-bottom: 28px;
  text-align: left;
}

.quote-mark {
  font-size: 48px;
  color: rgba(255, 255, 255, 0.12);
  line-height: 1;
  font-family: Georgia, serif;
  position: absolute;
  top: 8px;
  left: 16px;
}

.quote-mark.closing {
  top: auto;
  bottom: 8px;
  left: auto;
  right: 16px;
}

.quote-text {
  font-size: 15px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.7);
  margin: 0;
  padding: 0 20px;
  font-style: italic;
}

.teaser-text {
  font-size: 15px;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 32px;
  line-height: 1.6;
  border-left: 3px solid #007AFF;
  padding-left: 16px;
  text-align: left;
}
</style>
