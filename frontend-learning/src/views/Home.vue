<template>
  <div class="min-h-screen flex flex-col items-center justify-center px-4 py-16">
    <!-- Header -->
    <div class="text-center mb-12">
      <div class="text-xs tracking-[0.3em] text-gray-500 mb-3 uppercase">JackpotChain Education Edition</div>
      <h1 class="text-4xl md:text-5xl font-bold mb-4" style="font-family:monospace">
        <span style="color:#007AFF">싸또</span><span style="color:#FFD700">777</span>
      </h1>
      <p class="text-gray-400 text-lg max-w-md mx-auto leading-relaxed">
        블록체인의 원리,<br/>
        <span class="text-white font-semibold">눈으로 보고 몸으로 채굴하며 깨닫는다.</span>
      </p>
    </div>

    <!-- Chapter Cards -->
    <div class="grid gap-4 w-full max-w-md">
      <RouterLink
        v-for="ch in chapters"
        :key="ch.id"
        :to="ch.path"
        class="glass-card p-5 flex items-center gap-4 hover:border-blue-500/40 transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] cursor-pointer no-underline"
        style="text-decoration:none"
      >
        <div class="text-3xl w-12 text-center flex-shrink-0">{{ ch.icon }}</div>
        <div class="flex-1 min-w-0">
          <div class="text-xs text-gray-500 mb-1">Chapter {{ ch.id }}</div>
          <div class="text-white font-semibold text-sm">{{ ch.title }}</div>
          <div class="text-gray-400 text-xs mt-1 truncate">{{ ch.desc }}</div>
        </div>
        <div class="text-gray-600 text-lg flex-shrink-0">›</div>
      </RouterLink>
    </div>

    <!-- Footer note -->
    <div class="mt-12 text-center">
      <p class="text-gray-600 text-xs leading-relaxed max-w-xs mx-auto">
        ※ 본 서비스는 학습용 시뮬레이션이며,<br/>JACK 코인은 실제 가치가 없습니다.
      </p>
    </div>
  </div>
</template>

<script setup>
import { RouterLink } from 'vue-router'

const chapters = [
  {
    id: 1,
    path: '/chapter1',
    icon: '💸',
    title: '자취생의 절규 — 내 월급 vs 미친 물가',
    desc: '인플레이션을 몸으로 느껴보세요',
  },
  {
    id: 2,
    path: '/chapter2',
    icon: '🔗',
    title: '모두가 보고 있다 — 틈 없는 진실의 장부',
    desc: '분산 장부의 투명성과 조작 불가능성',
  },
  {
    id: 3,
    path: '/chapter3',
    icon: '🎰',
    title: '미니 데모 — 100% 투명한 로또',
    desc: 'Commit-Reveal로 공정성을 직접 확인',
  },
]
</script>
