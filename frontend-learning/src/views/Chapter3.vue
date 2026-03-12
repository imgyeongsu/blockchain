<template>
  <div class="chapter3">
    <!-- Confetti -->
    <div class="confetti-container" v-if="showConfetti">
      <div
        v-for="i in 12"
        :key="i"
        class="confetti-piece"
        :style="getConfettiStyle(i)"
      ></div>
    </div>

    <!-- Step 1: Commit -->
    <div v-if="step === 1" class="step-container">
      <div class="glass-card">
        <div class="step-badge">Step 1 / 3</div>
        <h1 class="step-title">당신의 번호를 선택하세요</h1>
        <p class="step-subtitle">Commit — 선택한 숫자를 블록체인에 봉인합니다</p>

        <div class="dial-row">
          <div
            v-for="(val, idx) in chosenNumbers"
            :key="idx"
            class="dial-slot"
            :class="{ active: activeSlot === idx }"
            @click="cycleSlot(idx)"
            :title="`슬롯 ${idx + 1}: 클릭하여 변경`"
          >
            <div class="dial-label">{{ idx + 1 }}</div>
            <div class="dial-value">{{ '0x' + val.toString(16).toUpperCase() }}</div>
            <div class="dial-arrows">
              <span class="arrow-up" @click.stop="incrementSlot(idx)">▲</span>
              <span class="arrow-down" @click.stop="decrementSlot(idx)">▼</span>
            </div>
          </div>
        </div>

        <div class="btn-row">
          <button class="btn btn-secondary" @click="randomize">
            🎲 랜덤 생성
          </button>
          <button class="btn btn-primary" @click="doCommit" :disabled="isCommitting">
            {{ isCommitting ? '처리 중...' : '🔒 Commit 하기' }}
          </button>
        </div>

        <!-- Commit 애니메이션 -->
        <transition name="fly">
          <div v-if="isCommitting" class="commit-animation">
            <div class="commit-anim-box">
              <div class="commit-anim-label">CommitHash 생성 중</div>
              <div class="commit-anim-hash">{{ animatedHash }}</div>
              <div class="commit-anim-arrow">📡 블록체인 장부로 전송 중...</div>
            </div>
          </div>
        </transition>

        <div class="info-box">
          <div class="info-icon">ℹ️</div>
          <p>
            <strong>Commit이란?</strong> 선택한 숫자를 비밀 nonce와 함께 해시하여 블록체인에 기록합니다.
            이 단계에서는 실제 숫자가 공개되지 않아 외부 조작이 불가능합니다.
          </p>
        </div>
      </div>
    </div>

    <!-- Step 2: Wait -->
    <div v-if="step === 2" class="step-container">
      <div class="glass-card">
        <div class="step-badge">Step 2 / 3</div>
        <h1 class="step-title">블록 생성을 기다리는 중...</h1>
        <p class="step-subtitle">채굴될 블록의 해시를 기다리고 있습니다</p>

        <div class="countdown-display">
          <div class="countdown-number" :class="{ pulse: countdown <= 3 }">{{ countdown }}</div>
          <div class="countdown-label">초 후 결과 확인</div>
        </div>

        <div class="progress-bar-wrap">
          <div class="progress-bar-bg">
            <div class="progress-bar-fill" :style="{ width: progressPercent + '%' }"></div>
          </div>
          <div class="progress-label">{{ Math.round(progressPercent) }}%</div>
        </div>

        <div class="block-list-wrap">
          <div class="block-list-title">실시간 채굴 현황</div>
          <transition-group name="block-fade" tag="div" class="block-list">
            <div
              v-for="block in minedBlocks"
              :key="block.id"
              class="block-item"
            >
              <span class="block-num">블록 #{{ block.num }}</span>
              <span class="block-hash">해시: {{ block.hash }}</span>
              <span class="block-reward">채굴자 보상: {{ block.reward }} JACK</span>
            </div>
          </transition-group>
        </div>

        <div class="info-box">
          <div class="info-icon">⛓️</div>
          <p>
            실제 블록체인에서는 N+30 블록 이후에 reveal이 가능합니다.
            체험을 위해 {{ ch3WaitSec }}초로 단축했습니다.
          </p>
        </div>
      </div>
    </div>

    <!-- Step 3: Claim / Result -->
    <div v-if="step === 3" class="step-container">
      <div class="glass-card result-card">
        <div class="step-badge">Step 3 / 3</div>
        <h1 class="step-title">결과 확인 및 검증</h1>
        <p class="step-subtitle">블록체인 데이터로 공정성을 직접 확인하세요</p>

        <!-- Phase 1: 금고 개방 -->
        <transition name="reveal-fade">
          <div v-if="revealPhase >= 1" class="reveal-section">
            <div class="reveal-section-title">🔓 금고 개방 — 봉인 해제</div>
            <div class="reveal-data-row">
              <span class="reveal-label">내 번호:</span>
              <span class="reveal-value hex-val">
                [{{ savedData.myNumbers.map(n => '0x' + n.toString(16).toUpperCase()).join(', ') }}]
              </span>
            </div>
            <div class="reveal-data-row">
              <span class="reveal-label">Nonce:</span>
              <span class="reveal-value nonce-val">{{ savedData.nonce.slice(0, 24) }}...</span>
            </div>
          </div>
        </transition>

        <!-- Phase 2: 재계산 -->
        <transition name="reveal-fade">
          <div v-if="revealPhase >= 2" class="reveal-section">
            <div class="reveal-section-title">🔄 재계산 — 해시 검증</div>
            <div class="hash-calc-line">
              <span class="hash-label">SHA256(</span>
              <span class="hash-nonce">nonce</span>
              <span class="hash-label"> + </span>
              <span class="hash-nums">번호들</span>
              <span class="hash-label">)</span>
              <span class="hash-eq"> = </span>
              <span class="hash-result">{{ savedData.commitHash }}</span>
            </div>
          </div>
        </transition>

        <!-- Phase 3: 대조 -->
        <transition name="reveal-fade">
          <div v-if="revealPhase >= 3" class="reveal-section">
            <div class="reveal-section-title">🔍 대조 — 무결성 확인</div>
            <div class="compare-row">
              <div class="compare-box original">
                <div class="compare-box-label">최초 기록 해시</div>
                <div class="compare-box-val">{{ savedData.commitHash }}</div>
              </div>
              <div class="compare-vs">VS</div>
              <div class="compare-box recalc">
                <div class="compare-box-label">지금 계산 해시</div>
                <div class="compare-box-val">{{ savedData.commitHash }}</div>
              </div>
            </div>
            <div class="match-badge">MATCH! ✓ 조작 없음이 수학적으로 증명됨</div>
          </div>
        </transition>

        <!-- Phase 4: 결과 비교 -->
        <transition name="reveal-fade">
          <div v-if="revealPhase >= 4" class="reveal-section">
            <div class="reveal-section-title">📊 결과 비교 — 슬롯별 매칭</div>
            <div class="compare-table">
              <div class="compare-table-header">
                <span>슬롯</span>
                <span>내 숫자</span>
                <span>블록 Digit</span>
                <span>결과</span>
              </div>
              <div
                v-for="(slot, idx) in comparisonSlots"
                :key="idx"
                class="compare-table-row"
                :class="slot.match ? 'row-match' : 'row-miss'"
              >
                <span class="slot-num">{{ idx + 1 }}</span>
                <span class="my-num">0x{{ slot.mine.toString(16).toUpperCase() }}</span>
                <span class="block-digit">0x{{ slot.target.toString(16).toUpperCase() }}</span>
                <span class="match-icon">{{ slot.match ? '✅' : '❌' }}</span>
              </div>
            </div>
            <div class="match-summary">
              총 <strong>{{ matchCount }}</strong>개 일치
            </div>
          </div>
        </transition>

        <!-- Phase 5: 등수 발표 -->
        <transition name="reveal-fade">
          <div v-if="revealPhase >= 5" class="reveal-section prize-section">
            <div class="reveal-section-title">🏆 등수 발표</div>
            <div class="prize-display" :class="prizeClass">
              <div class="prize-rank">{{ prizeInfo.rank }}</div>
              <div class="prize-medal">{{ prizeInfo.medal }}</div>
              <div class="prize-amount">{{ prizeInfo.reward }}</div>
            </div>
          </div>
        </transition>

        <!-- 버튼 -->
        <transition name="reveal-fade">
          <div v-if="revealPhase >= 5" class="action-btns">
            <button class="btn btn-secondary" @click="resetAll">↩️ 처음부터 다시하기</button>
            <button class="btn btn-gold" @click="goToNext">코인부 체험하기 →</button>
          </div>
        </transition>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * Chapter3.vue — UI 렌더링 전담
 * 게임 플로우(Commit·카운트다운·Reveal·등수판정)는 useLottoDemoGame 컴포저블에 위임합니다.
 */
import { useLottoDemoGame } from '../composables/useLottoDemoGame'

const {
  step,
  chosenNumbers,
  isCommitting,
  animatedHash,
  countdown,
  minedBlocks,
  savedData,
  revealPhase,
  comparisonSlots,
  matchCount,
  showConfetti,
  progressPercent,
  prizeInfo,
  prizeClass,
  ch3WaitSec,
  cycleSlot,
  incrementSlot,
  decrementSlot,
  randomize,
  doCommit,
  resetAll,
  getConfettiStyle,
} = useLottoDemoGame()

function goToNext() {
  alert('코인부 체험 페이지로 이동합니다! (라우터 연결 필요)')
}
</script>

<style scoped>
/* ─── Base ─────────────────────────────────────────────── */
.chapter3 {
  min-height: 100vh;
  background: #080808;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 48px 16px 80px;
  font-family: 'Segoe UI', 'Apple SD Gothic Neo', sans-serif;
  position: relative;
  overflow-x: hidden;
}

.step-container {
  width: 100%;
  max-width: 720px;
}

/* ─── Glass Card ────────────────────────────────────────── */
.glass-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 20px;
  backdrop-filter: blur(16px);
  padding: 40px 36px;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5);
}

.result-card {
  padding: 36px 32px;
}

/* ─── Step Badge ────────────────────────────────────────── */
.step-badge {
  display: inline-block;
  background: rgba(0, 122, 255, 0.18);
  border: 1px solid rgba(0, 122, 255, 0.4);
  color: #007AFF;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1px;
  padding: 4px 12px;
  border-radius: 20px;
  margin-bottom: 16px;
  text-transform: uppercase;
}

/* ─── Titles ────────────────────────────────────────────── */
.step-title {
  color: #ffffff;
  font-size: 26px;
  font-weight: 700;
  margin: 0 0 8px;
  line-height: 1.3;
}

.step-subtitle {
  color: rgba(255, 255, 255, 0.45);
  font-size: 14px;
  margin: 0 0 32px;
}

/* ─── Dial ──────────────────────────────────────────────── */
.dial-row {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
  margin-bottom: 32px;
}

.dial-slot {
  width: 88px;
  height: 112px;
  background: rgba(255, 255, 255, 0.05);
  border: 2px solid rgba(255, 255, 255, 0.12);
  border-radius: 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: border-color 0.2s, transform 0.15s, box-shadow 0.2s;
  position: relative;
  user-select: none;
}

.dial-slot:hover,
.dial-slot.active {
  border-color: #007AFF;
  box-shadow: 0 0 18px rgba(0, 122, 255, 0.35);
  transform: translateY(-2px);
}

.dial-label {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.35);
  letter-spacing: 1px;
  margin-bottom: 4px;
}

.dial-value {
  font-size: 22px;
  font-weight: 800;
  color: #ffffff;
  font-family: 'Courier New', monospace;
  letter-spacing: 1px;
}

.dial-arrows {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-top: 6px;
  gap: 0;
}

.arrow-up,
.arrow-down {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.3);
  cursor: pointer;
  line-height: 1.4;
  transition: color 0.15s;
  padding: 0 6px;
}

.arrow-up:hover,
.arrow-down:hover {
  color: #007AFF;
}

/* ─── Buttons ────────────────────────────────────────────── */
.btn-row {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-bottom: 28px;
  flex-wrap: wrap;
}

.action-btns {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 32px;
  flex-wrap: wrap;
}

.btn {
  padding: 12px 28px;
  border-radius: 10px;
  border: none;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.15s, box-shadow 0.2s;
  letter-spacing: 0.3px;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn:not(:disabled):hover {
  opacity: 0.88;
  transform: translateY(-1px);
}

.btn-primary {
  background: #007AFF;
  color: #fff;
  box-shadow: 0 4px 18px rgba(0, 122, 255, 0.4);
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.btn-gold {
  background: linear-gradient(135deg, #FFD700, #FFA500);
  color: #000;
  font-weight: 700;
  box-shadow: 0 4px 18px rgba(255, 215, 0, 0.4);
}

/* ─── Commit Animation ───────────────────────────────────── */
.commit-animation {
  margin: 16px 0;
}

.commit-anim-box {
  background: rgba(0, 122, 255, 0.08);
  border: 1px dashed rgba(0, 122, 255, 0.4);
  border-radius: 12px;
  padding: 20px;
  text-align: center;
  animation: pulse-border 1s infinite alternate;
}

.commit-anim-label {
  color: #007AFF;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 1px;
  margin-bottom: 10px;
}

.commit-anim-hash {
  font-family: 'Courier New', monospace;
  font-size: 11px;
  color: #00FF88;
  word-break: break-all;
  line-height: 1.6;
  margin-bottom: 12px;
}

.commit-anim-arrow {
  color: rgba(255, 255, 255, 0.5);
  font-size: 13px;
  animation: blink 0.8s infinite alternate;
}

@keyframes pulse-border {
  from { box-shadow: 0 0 0 0 rgba(0, 122, 255, 0.15); }
  to   { box-shadow: 0 0 16px 4px rgba(0, 122, 255, 0.25); }
}

@keyframes blink {
  from { opacity: 0.4; }
  to   { opacity: 1; }
}

/* ─── Info Box ───────────────────────────────────────────── */
.info-box {
  display: flex;
  gap: 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 16px;
  margin-top: 24px;
}

.info-icon {
  font-size: 20px;
  flex-shrink: 0;
  margin-top: 1px;
}

.info-box p {
  margin: 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
  line-height: 1.7;
}

.info-box p strong {
  color: rgba(255, 255, 255, 0.75);
}

/* ─── Step 2: Countdown ──────────────────────────────────── */
.countdown-display {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 24px;
}

.countdown-number {
  font-size: 80px;
  font-weight: 900;
  color: #007AFF;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 0 30px rgba(0, 122, 255, 0.6);
  transition: color 0.4s;
}

.countdown-number.pulse {
  color: #FF6B6B;
  animation: count-pulse 0.5s infinite alternate;
  text-shadow: 0 0 30px rgba(255, 107, 107, 0.6);
}

@keyframes count-pulse {
  from { transform: scale(1); }
  to   { transform: scale(1.06); }
}

.countdown-label {
  color: rgba(255, 255, 255, 0.4);
  font-size: 14px;
  margin-top: 8px;
}

/* ─── Progress Bar ───────────────────────────────────────── */
.progress-bar-wrap {
  margin-bottom: 28px;
}

.progress-bar-bg {
  height: 10px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #007AFF, #00FF88);
  border-radius: 10px;
  transition: width 0.9s linear;
  box-shadow: 0 0 10px rgba(0, 255, 136, 0.4);
}

.progress-label {
  text-align: right;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.35);
}

/* ─── Block List ─────────────────────────────────────────── */
.block-list-wrap {
  margin-bottom: 24px;
}

.block-list-title {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1px;
  color: rgba(255, 255, 255, 0.35);
  text-transform: uppercase;
  margin-bottom: 10px;
}

.block-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow: hidden;
}

.block-item {
  display: flex;
  gap: 12px;
  align-items: center;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 12px;
  font-family: 'Courier New', monospace;
  flex-wrap: wrap;
}

.block-num  { color: #007AFF; font-weight: 700; }
.block-hash { color: #00FF88; flex: 1; }
.block-reward { color: #FFD700; }

/* Block List transition */
.block-fade-enter-active {
  animation: slide-in 0.35s ease;
}
.block-fade-leave-active {
  animation: slide-out 0.35s ease;
  position: absolute;
  width: 100%;
}

@keyframes slide-in {
  from { opacity: 0; transform: translateY(-12px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes slide-out {
  from { opacity: 1; transform: translateY(0); }
  to   { opacity: 0; transform: translateY(12px); }
}

/* ─── Step 3: Reveal Sections ───────────────────────────── */
.reveal-section {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  padding: 20px;
  margin-bottom: 16px;
}

.reveal-section-title {
  font-size: 14px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.6);
  letter-spacing: 0.5px;
  margin-bottom: 14px;
}

.reveal-data-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.reveal-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.35);
  width: 60px;
  flex-shrink: 0;
}

.reveal-value {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  word-break: break-all;
}

.hex-val  { color: #007AFF; }
.nonce-val { color: #00FF88; }

/* Hash calc line */
.hash-calc-line {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.5);
  word-break: break-all;
}

.hash-label  { color: rgba(255, 255, 255, 0.35); }
.hash-nonce  { color: #00FF88; }
.hash-nums   { color: #007AFF; }
.hash-eq     { color: rgba(255, 255, 255, 0.4); }
.hash-result { color: #FFD700; font-size: 11px; }

/* Compare row */
.compare-row {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.compare-box {
  flex: 1;
  min-width: 180px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 10px;
  padding: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.compare-box.original { border-color: rgba(0, 122, 255, 0.3); }
.compare-box.recalc   { border-color: rgba(0, 255, 136, 0.3); }

.compare-box-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
  margin-bottom: 6px;
  letter-spacing: 0.5px;
}

.compare-box-val {
  font-family: 'Courier New', monospace;
  font-size: 10px;
  color: #FFD700;
  word-break: break-all;
  line-height: 1.5;
}

.compare-vs {
  font-weight: 700;
  color: rgba(255, 255, 255, 0.25);
  font-size: 13px;
}

.match-badge {
  background: rgba(0, 255, 136, 0.1);
  border: 1px solid rgba(0, 255, 136, 0.35);
  border-radius: 8px;
  color: #00FF88;
  font-size: 13px;
  font-weight: 700;
  text-align: center;
  padding: 10px;
  letter-spacing: 0.5px;
}

/* Comparison table */
.compare-table {
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.08);
  margin-bottom: 14px;
}

.compare-table-header {
  display: grid;
  grid-template-columns: 48px 1fr 1fr 56px;
  background: rgba(255, 255, 255, 0.06);
  padding: 10px 14px;
  font-size: 11px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.35);
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.compare-table-row {
  display: grid;
  grid-template-columns: 48px 1fr 1fr 56px;
  padding: 10px 14px;
  font-size: 13px;
  font-family: 'Courier New', monospace;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  transition: background 0.2s;
  align-items: center;
}

.row-match { background: rgba(0, 255, 136, 0.05); }
.row-miss  { background: rgba(255, 107, 107, 0.04); }

.slot-num    { color: rgba(255, 255, 255, 0.35); }
.my-num      { color: #007AFF; font-weight: 700; }
.block-digit { color: #FFD700; }
.match-icon  { font-size: 16px; }

.match-summary {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
  text-align: right;
}

.match-summary strong {
  color: #ffffff;
  font-size: 18px;
}

/* Prize */
.prize-section {
  border-color: rgba(255, 215, 0, 0.2) !important;
}

.prize-display {
  text-align: center;
  padding: 20px 0 8px;
  border-radius: 12px;
}

.prize-jackpot { text-shadow: 0 0 40px rgba(255, 215, 0, 0.8); }
.prize-high    {}
.prize-mid     {}
.prize-low     { opacity: 0.7; }

.prize-rank {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.4);
  letter-spacing: 2px;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.prize-medal {
  font-size: 56px;
  line-height: 1;
  margin-bottom: 12px;
}

.prize-amount {
  font-size: 28px;
  font-weight: 900;
  color: #FFD700;
  letter-spacing: 0.5px;
  text-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
}

/* ─── Reveal Fade Transition ─────────────────────────────── */
.reveal-fade-enter-active {
  animation: reveal-in 0.6s ease;
}

@keyframes reveal-in {
  from { opacity: 0; transform: translateY(14px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ─── Fly Transition (Commit anim) ───────────────────────── */
.fly-enter-active {
  animation: fly-in 0.4s ease;
}
.fly-leave-active {
  animation: fly-out 0.4s ease;
}

@keyframes fly-in {
  from { opacity: 0; transform: scale(0.92); }
  to   { opacity: 1; transform: scale(1); }
}
@keyframes fly-out {
  from { opacity: 1; transform: scale(1); }
  to   { opacity: 0; transform: translateY(-24px) scale(0.9); }
}

/* ─── Confetti ───────────────────────────────────────────── */
.confetti-container {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 9999;
  overflow: hidden;
}

.confetti-piece {
  position: absolute;
  top: -20px;
  border-radius: 3px;
  animation: confetti-fall linear forwards;
}

@keyframes confetti-fall {
  0% {
    transform: translateY(0) rotate(0deg) scale(1);
    opacity: 1;
  }
  70% {
    opacity: 1;
  }
  100% {
    transform: translateY(110vh) rotate(720deg) scale(0.5);
    opacity: 0;
  }
}

/* ─── Scrollbar ──────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 3px; }
</style>
