import { useMiningInfo } from '../hooks/useMiningInfo'
import { CHAIN } from '../config'

/**
 * Mining — 채굴 대시보드
 *
 * 관심사 분리:
 *   - 블록체인 정보 폴링·에러 처리 → useMiningInfo 훅
 *   - 채굴 파라미터(보상·블록타임·난이도 주기) → config.js CHAIN 상수
 *   - UI 렌더링 → 이 컴포넌트
 */
export default function Mining() {
  const { info, loading, error } = useMiningInfo()

  return (
    <div className="max-w-lg mx-auto px-4 py-8 pb-20 sm:pb-8">
      <h2 className="text-xl font-bold text-white mb-6">⛏️ 채굴 대시보드</h2>

      {/* 에러 배너 */}
      {error && (
        <div className="glass-card p-3 mb-4 text-xs font-mono" style={{ color: '#FF453A', borderColor: 'rgba(255,69,58,0.3)' }}>
          ⚠️ RPC 오류: {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 mb-6">
        {[
          { label: '현재 난이도', value: info?.difficulty?.toFixed(6) ?? '—', color: '#007AFF' },
          { label: '블록 높이', value: info?.height ?? info?.blocks ?? '—', color: '#00FF88' },
          { label: '해시레이트', value: info?.networkhashps ? `${(info.networkhashps / 1000).toFixed(2)} KH/s` : '—', color: '#FFD700' },
          { label: '블록 보상', value: `${CHAIN.BLOCK_REWARD_JACK} JACK`, color: '#888' },
        ].map((s) => (
          <div key={s.label} className="glass-card p-4">
            <div className="text-xs text-gray-500 mb-1">{s.label}</div>
            <div className="text-xl font-bold" style={{ color: s.color }}>{s.value}</div>
          </div>
        ))}
      </div>

      <div className="glass-card p-5">
        <div className="text-xs text-gray-500 mb-3">채굴 정보</div>
        <div className="text-sm text-gray-400 space-y-2">
          <div>• 블록 타임: {CHAIN.BLOCK_TIME_SEC}초 목표</div>
          <div>• 난이도 조정: {CHAIN.DIFFICULTY_ADJUST_BLOCKS}블록 주기</div>
          <div>• 합의: Proof of Work (SHA256)</div>
          <div>• 채굴 보상: Coinbase TX로 자동 지급</div>
        </div>
      </div>
    </div>
  )
}
