<template>
  <div class="chapter2-wrapper">

    <!-- ===================== STEP 1: 인트로 ===================== -->
    <transition name="fade">
      <div v-if="step === 1" class="stage stage-1">
        <div class="intro-header">
          <span class="chapter-label">CHAPTER 2</span>
          <h1 class="title">모두가 보고 있다</h1>
          <p class="subtitle">중앙 서버 없이 어떻게 데이터를 신뢰할 수 있을까요?</p>
        </div>
        <div class="black-box" @click="openBox">
          <div class="box-inner">
            <div class="box-icon">🏦</div>
            <p class="box-hint">이 안에 은행 장부가 있습니다.<br>클릭해서 열어보세요.</p>
          </div>
          <div class="box-glow"></div>
        </div>
      </div>
    </transition>

    <!-- ===================== STEP 2: 투명화 ===================== -->
    <transition name="fade">
      <div v-if="step === 2" class="stage stage-2">
        <h2 class="stage-title">장부가 열렸습니다</h2>
        <p class="stage-desc">모든 참여자가 동일한 장부를 가지고 있습니다</p>
        <div class="nodes-grid sync-grid">
          <div
            v-for="(node, i) in nodes"
            :key="i"
            class="node-card glass-card appear-node"
            :style="{ animationDelay: `${i * 100}ms` }"
          >
            <div class="node-header">
              <span class="node-id">NODE #{{ i }}</span>
              <span class="sync-badge">SYNCED</span>
            </div>
            <div class="node-value">{{ node.value }}</div>
            <div class="node-hash">hash: 0x{{ dummyHash(i) }}</div>
          </div>
        </div>
        <button class="btn-primary" @click="step = 3">조작 시도하기</button>
      </div>
    </transition>

    <!-- ===================== STEP 3: 조작 체험 ===================== -->
    <transition name="fade">
      <div v-if="step === 3" class="stage stage-3">
        <h2 class="stage-title">장부를 조작해보세요</h2>
        <p class="stage-desc">첫 번째 노드(NODE #0)의 값을 바꿔보세요</p>
        <div class="nodes-grid">
          <div
            v-for="(node, i) in nodes"
            :key="i"
            class="node-card glass-card"
            :class="{
              'node-glitch': i === 0 && isGlitching,
              'node-editable': i === 0 && !isGlitching,
            }"
          >
            <div class="node-header">
              <span class="node-id">NODE #{{ i }}</span>
              <span v-if="i === 0 && !isGlitching" class="edit-badge">EDITABLE</span>
              <span v-else class="lock-badge">LOCKED</span>
            </div>
            <div v-if="i === 0 && !isGlitching" class="node-edit-area">
              <input
                ref="editInput"
                v-model="editValue"
                class="node-input"
                @keydown.enter="submitTamper"
                placeholder="값을 수정하세요..."
              />
              <button class="btn-confirm" @click="submitTamper">확인</button>
            </div>
            <div v-else class="node-value">{{ node.value }}</div>
            <div class="node-hash">hash: 0x{{ dummyHash(i) }}</div>
          </div>
        </div>

        <!-- 빨간 오버레이 -->
        <transition name="overlay-fade">
          <div v-if="showOverlay" class="red-overlay">
            <div class="watermark">⚠️ INVALID DATA DETECTED</div>
          </div>
        </transition>

        <!-- 토스트 -->
        <transition name="toast-slide">
          <div v-if="showToast" class="toast toast-error">
            다른 5개 노드와 데이터가 불일치합니다. 강제 복원됨.
          </div>
        </transition>
      </div>
    </transition>

    <!-- ===================== STEP 4: 검증 ===================== -->
    <transition name="fade">
      <div v-if="step === 4" class="stage stage-4">
        <h2 class="stage-title">네트워크 검증 중...</h2>
        <p class="stage-desc">모든 노드가 서로의 데이터를 교차 검증합니다</p>
        <div class="verify-container">
          <!-- SVG 레이저 라인 -->
          <svg class="laser-svg" viewBox="0 0 600 400" xmlns="http://www.w3.org/2000/svg">
            <line
              v-for="(pos, i) in nodePositions"
              :key="i"
              :x1="300" :y1="200"
              :x2="pos.x" :y2="pos.y"
              class="laser-line"
              :style="{ animationDelay: `${i * 200}ms` }"
            />
          </svg>
          <div class="nodes-grid verify-grid">
            <div
              v-for="(node, i) in nodes"
              :key="i"
              class="node-card glass-card"
              :class="{ 'node-verified': verifiedNodes[i] }"
            >
              <div class="node-header">
                <span class="node-id">NODE #{{ i }}</span>
                <transition name="check-pop">
                  <span v-if="verifiedNodes[i]" class="immutable-badge">IMMUTABLE</span>
                </transition>
              </div>
              <div class="node-value">{{ node.value }}</div>
              <transition name="check-pop">
                <div v-if="verifiedNodes[i]" class="verified-text">[VERIFIED] ✓</div>
              </transition>
              <div class="node-hash">hash: 0x{{ dummyHash(i) }}</div>
            </div>
          </div>
        </div>
        <transition name="fade">
          <button v-if="allVerified" class="btn-primary" @click="step = 5">다음 단계</button>
        </transition>
      </div>
    </transition>

    <!-- ===================== STEP 5: 결론 ===================== -->
    <transition name="fade">
      <div v-if="step === 5" class="stage stage-5">
        <div class="conclusion-card glass-card">
          <div class="quote-mark">"</div>
          <p class="quote-text">블록체인에서 비밀은 없습니다.</p>
          <div class="quote-mark closing">"</div>
          <p class="conclusion-body">
            조작이 불가능한 것이 아니라,<br>
            <strong>모두에게 들키기 때문에</strong> 통하지 않는 것입니다.
          </p>
          <div class="conclusion-icons">
            <span class="c-icon">👁️</span>
            <span class="c-icon">🔗</span>
            <span class="c-icon">🛡️</span>
          </div>
        </div>
        <RouterLink to="/chapter3" class="btn-primary btn-link">
          Chapter 3으로 이동 →
        </RouterLink>
      </div>
    </transition>

    <!-- 스텝 인디케이터 -->
    <div class="step-indicator">
      <span
        v-for="s in 5"
        :key="s"
        class="step-dot"
        :class="{ active: step === s, done: step > s }"
      ></span>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted } from 'vue'
import { RouterLink } from 'vue-router'

// ── 상태 ──────────────────────────────────────────────
const step = ref(1)

const DEFAULT_VALUE = '사용자A: 100 JACK'

const nodes = reactive(
  Array.from({ length: 6 }, (_, i) => ({ id: i, value: DEFAULT_VALUE }))
)

const editValue = ref(DEFAULT_VALUE)
const editInput = ref(null)
const isGlitching = ref(false)
const showOverlay = ref(false)
const showToast = ref(false)

const verifiedNodes = reactive(Array(6).fill(false))
const allVerified = computed(() => verifiedNodes.every(Boolean))

// SVG 레이저용 노드 위치 (600×400 viewBox 기준)
const nodePositions = [
  { x: 80,  y: 80  },
  { x: 300, y: 50  },
  { x: 520, y: 80  },
  { x: 80,  y: 320 },
  { x: 300, y: 350 },
  { x: 520, y: 320 },
]

// ── 헬퍼 ──────────────────────────────────────────────
function dummyHash(i) {
  const hashes = ['3f9a2b', 'c1d4e8', '7a0b12', 'ff4421', '88ccdd', '5e3190']
  return hashes[i % hashes.length]
}

// ── Step 1 → 2 ────────────────────────────────────────
function openBox() {
  step.value = 2
}

// ── Step 3: 조작 제출 ─────────────────────────────────
async function submitTamper() {
  if (!editValue.value || editValue.value === DEFAULT_VALUE) return

  isGlitching.value = true
  showOverlay.value = true

  await new Promise(r => setTimeout(r, 800))

  showToast.value = true
  nodes[0].value = DEFAULT_VALUE
  editValue.value = DEFAULT_VALUE

  await new Promise(r => setTimeout(r, 1200))

  showOverlay.value = false
  showToast.value = false
  isGlitching.value = false

  await new Promise(r => setTimeout(r, 400))
  step.value = 4

  // 검증 stagger
  nextTick(() => {
    nodes.forEach((_, i) => {
      setTimeout(() => {
        verifiedNodes[i] = true
      }, 400 + i * 200)
    })
  })
}

// ── Step 4 진입 시 바로 검증 트리거 (step watch) ───────
import { watch } from 'vue'
watch(step, (val) => {
  if (val === 4) {
    // 혹시 직접 step=4로 올 경우 대비
    nodes.forEach((_, i) => {
      setTimeout(() => { verifiedNodes[i] = true }, 400 + i * 200)
    })
  }
  if (val === 3) {
    nextTick(() => {
      editInput.value?.[0]?.focus()
    })
  }
})
</script>

<style scoped>
/* ── 기반 레이아웃 ───────────────────────────────────── */
.chapter2-wrapper {
  min-height: 100vh;
  background: #080808;
  color: #e8e8e8;
  font-family: 'Inter', 'Segoe UI', sans-serif;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  position: relative;
  overflow: hidden;
}

.stage {
  width: 100%;
  max-width: 880px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2rem;
  position: absolute;
}

/* ── glass-card ─────────────────────────────────────── */
.glass-card {
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 16px;
  padding: 1.25rem 1.5rem;
  transition: border-color 0.4s ease, box-shadow 0.4s ease;
}

/* ── 버튼 ───────────────────────────────────────────── */
.btn-primary {
  background: #007AFF;
  color: #fff;
  border: none;
  border-radius: 12px;
  padding: 0.85rem 2rem;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  width: 100%;
  max-width: 340px;
  letter-spacing: 0.03em;
  transition: background 0.2s, transform 0.15s;
  text-align: center;
  text-decoration: none;
  display: inline-block;
}
.btn-primary:hover { background: #0063d1; transform: translateY(-2px); }
.btn-primary:active { transform: translateY(0); }
.btn-link { margin-top: 1.5rem; }

/* ── 스텝 인디케이터 ─────────────────────────────────── */
.step-indicator {
  position: fixed;
  bottom: 1.5rem;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 0.5rem;
  z-index: 100;
}
.step-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: rgba(255,255,255,0.2);
  transition: background 0.3s, transform 0.3s;
}
.step-dot.active { background: #007AFF; transform: scale(1.4); }
.step-dot.done   { background: #00FF88; }

/* ── 공통 텍스트 ─────────────────────────────────────── */
.chapter-label {
  font-size: 0.75rem;
  letter-spacing: 0.2em;
  color: #007AFF;
  text-transform: uppercase;
  font-weight: 700;
}
.title {
  font-size: 2.4rem;
  font-weight: 800;
  margin: 0.4rem 0;
  background: linear-gradient(135deg, #fff 0%, #a0c4ff 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.subtitle {
  color: rgba(255,255,255,0.5);
  font-size: 1rem;
  margin: 0;
}
.stage-title {
  font-size: 1.8rem;
  font-weight: 700;
  margin: 0;
  color: #fff;
}
.stage-desc {
  color: rgba(255,255,255,0.5);
  font-size: 0.95rem;
  margin: -0.5rem 0 0;
  text-align: center;
}
.intro-header { text-align: center; }

/* ════════════════════════════════════════════════════
   STEP 1 — 블랙 박스
   ════════════════════════════════════════════════════ */
.black-box {
  width: 220px;
  height: 220px;
  background: #0a0a0a;
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  transition: transform 0.2s, box-shadow 0.3s;
}
.black-box:hover {
  transform: scale(1.04);
  box-shadow: 0 0 40px rgba(0, 122, 255, 0.3);
}
.black-box:active { transform: scale(0.97); }
.box-inner { text-align: center; z-index: 1; }
.box-icon { font-size: 2.5rem; display: block; margin-bottom: 0.6rem; }
.box-hint {
  font-size: 0.82rem;
  color: rgba(255,255,255,0.45);
  line-height: 1.5;
  margin: 0;
}
.box-glow {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 50% 50%, rgba(0,122,255,0.08) 0%, transparent 70%);
  animation: pulse-glow 2.5s ease-in-out infinite;
}
@keyframes pulse-glow {
  0%, 100% { opacity: 0.4; }
  50%       { opacity: 1; }
}

/* ════════════════════════════════════════════════════
   STEP 2 & 3 — 노드 그리드
   ════════════════════════════════════════════════════ */
.nodes-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  width: 100%;
}
.node-card {
  min-height: 130px;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.node-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.node-id {
  font-size: 0.7rem;
  letter-spacing: 0.12em;
  color: rgba(255,255,255,0.4);
  font-weight: 600;
}
.sync-badge, .edit-badge, .lock-badge, .immutable-badge {
  font-size: 0.65rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  letter-spacing: 0.08em;
}
.sync-badge   { background: rgba(0,255,136,0.15); color: #00FF88; border: 1px solid rgba(0,255,136,0.3); }
.edit-badge   { background: rgba(255,69,10,0.15);  color: #FF8C00; border: 1px solid rgba(255,140,0,0.3); }
.lock-badge   { background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.3); border: 1px solid rgba(255,255,255,0.1); }
.immutable-badge { background: rgba(0,255,136,0.2); color: #00FF88; border: 1px solid rgba(0,255,136,0.4); }

.node-value {
  font-size: 0.9rem;
  font-weight: 600;
  color: #e8e8e8;
  word-break: break-all;
}
.node-hash {
  font-size: 0.68rem;
  color: rgba(255,255,255,0.2);
  font-family: 'Courier New', monospace;
}
.verified-text {
  font-size: 0.9rem;
  font-weight: 700;
  color: #00FF88;
  text-shadow: 0 0 10px rgba(0,255,136,0.6);
}

/* Step 2 등장 애니메이션 */
.appear-node {
  opacity: 0;
  animation: node-appear 0.5s ease forwards;
}
@keyframes node-appear {
  from { opacity: 0; transform: scale(0.8) translateY(10px); }
  to   { opacity: 1; transform: scale(1) translateY(0); }
}

/* ── 편집 영역 ───────────────────────────────────────── */
.node-editable {
  border-color: rgba(255, 140, 0, 0.5) !important;
  box-shadow: 0 0 20px rgba(255,140,0,0.15);
}
.node-edit-area { display: flex; flex-direction: column; gap: 0.5rem; }
.node-input {
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,140,0,0.5);
  border-radius: 8px;
  color: #fff;
  font-size: 0.85rem;
  padding: 0.45rem 0.7rem;
  outline: none;
  width: 100%;
  box-sizing: border-box;
  transition: border-color 0.2s;
}
.node-input:focus { border-color: #FF8C00; }
.btn-confirm {
  background: rgba(255,140,0,0.8);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 0.8rem;
  font-weight: 600;
  padding: 0.4rem 0.8rem;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-confirm:hover { background: #FF8C00; }

/* ── Glitch 노드 ─────────────────────────────────────── */
.node-glitch {
  border-color: #FF453A !important;
  box-shadow: 0 0 30px rgba(255,69,58,0.5);
  animation: glitch-shake 0.5s ease;
}
@keyframes glitch-shake {
  0%   { transform: translate(0); }
  10%  { transform: translate(-4px, 2px); filter: hue-rotate(90deg); }
  20%  { transform: translate(4px, -2px); }
  30%  { transform: translate(-3px, 3px); filter: hue-rotate(180deg); }
  40%  { transform: translate(3px, -3px); }
  50%  { transform: translate(-2px, 2px); filter: hue-rotate(270deg); }
  60%  { transform: translate(2px, -1px); }
  70%  { transform: translate(-1px, 1px); filter: hue-rotate(0deg); }
  80%  { transform: translate(1px, 0); }
  90%  { transform: translate(0, 1px); }
  100% { transform: translate(0); }
}

/* ── 빨간 오버레이 & 워터마크 ──────────────────────── */
.red-overlay {
  position: fixed;
  inset: 0;
  background: rgba(255, 40, 40, 0.18);
  z-index: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
.watermark {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) rotate(-30deg);
  font-size: 3rem;
  font-weight: 900;
  color: rgba(255, 69, 58, 0.85);
  white-space: nowrap;
  letter-spacing: 0.08em;
  text-shadow: 0 0 30px rgba(255,69,58,0.6);
  pointer-events: none;
  animation: watermark-pulse 0.3s ease-in-out infinite alternate;
}
@keyframes watermark-pulse {
  from { opacity: 0.7; }
  to   { opacity: 1; }
}

/* ── 토스트 ─────────────────────────────────────────── */
.toast {
  position: fixed;
  bottom: 3.5rem;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(30, 30, 30, 0.95);
  border: 1px solid rgba(255, 69, 58, 0.6);
  border-radius: 12px;
  color: #FF453A;
  font-size: 0.88rem;
  font-weight: 600;
  padding: 0.75rem 1.5rem;
  z-index: 600;
  white-space: nowrap;
  box-shadow: 0 8px 30px rgba(0,0,0,0.5);
}

/* ════════════════════════════════════════════════════
   STEP 4 — 검증 SVG
   ════════════════════════════════════════════════════ */
.verify-container {
  position: relative;
  width: 100%;
}
.laser-svg {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 0;
}
.laser-line {
  stroke: #00FF88;
  stroke-width: 1.5;
  stroke-dasharray: 400;
  stroke-dashoffset: 400;
  opacity: 0.6;
  animation: laser-draw 0.5s ease forwards;
}
@keyframes laser-draw {
  to { stroke-dashoffset: 0; }
}
.verify-grid {
  position: relative;
  z-index: 1;
}
.node-verified {
  border-color: #00FF88 !important;
  box-shadow: 0 0 20px rgba(0,255,136,0.25);
}

/* ════════════════════════════════════════════════════
   STEP 5 — 결론
   ════════════════════════════════════════════════════ */
.stage-5 { gap: 2.5rem; }
.conclusion-card {
  max-width: 560px;
  width: 100%;
  text-align: center;
  padding: 2.5rem 2rem;
}
.quote-mark {
  font-size: 4rem;
  color: #007AFF;
  line-height: 0.5;
  font-family: Georgia, serif;
}
.quote-mark.closing { display: block; margin-top: 0.5rem; }
.quote-text {
  font-size: 1.5rem;
  font-weight: 700;
  color: #fff;
  margin: 1rem 0;
  line-height: 1.4;
}
.conclusion-body {
  font-size: 1rem;
  color: rgba(255,255,255,0.6);
  line-height: 1.7;
  margin: 1rem 0;
}
.conclusion-body strong { color: #00FF88; }
.conclusion-icons {
  display: flex;
  justify-content: center;
  gap: 1rem;
  margin-top: 1.5rem;
  font-size: 1.5rem;
}
.c-icon { animation: float-icon 3s ease-in-out infinite; }
.c-icon:nth-child(2) { animation-delay: 0.5s; }
.c-icon:nth-child(3) { animation-delay: 1s; }
@keyframes float-icon {
  0%, 100% { transform: translateY(0); }
  50%       { transform: translateY(-6px); }
}

/* ════════════════════════════════════════════════════
   트랜지션
   ════════════════════════════════════════════════════ */
.fade-enter-active, .fade-leave-active { transition: opacity 0.4s ease, transform 0.4s ease; }
.fade-enter-from { opacity: 0; transform: translateY(16px); }
.fade-leave-to   { opacity: 0; transform: translateY(-16px); }

.overlay-fade-enter-active, .overlay-fade-leave-active { transition: opacity 0.3s ease; }
.overlay-fade-enter-from, .overlay-fade-leave-to { opacity: 0; }

.toast-slide-enter-active, .toast-slide-leave-active { transition: opacity 0.3s, transform 0.3s; }
.toast-slide-enter-from { opacity: 0; transform: translateX(-50%) translateY(12px); }
.toast-slide-leave-to   { opacity: 0; transform: translateX(-50%) translateY(12px); }

.check-pop-enter-active { transition: opacity 0.35s ease, transform 0.35s cubic-bezier(0.34,1.56,0.64,1); }
.check-pop-enter-from   { opacity: 0; transform: scale(0.5); }

/* ── 반응형 ─────────────────────────────────────────── */
@media (max-width: 640px) {
  .nodes-grid { grid-template-columns: repeat(2, 1fr); }
  .title { font-size: 1.7rem; }
  .watermark { font-size: 2rem; }
}
</style>
