import { useJackpotPool } from '../hooks/useJackpotPool'
import { formatJACK } from '../utils/crypto'
import { RANK_TABLE, LOTTO } from '../config'

/**
 * Jackpot — 잭팟 풀 현황 페이지
 *
 * 관심사 분리:
 *   - 풀 잔액 폴링·에러 처리 → useJackpotPool 훅
 *   - RANK_TABLE 보상 구조 데이터 → config.js
 *   - UI 렌더링 → 이 컴포넌트
 */
export default function Jackpot() {
  const { pool, loading, error } = useJackpotPool()

  return (
    <div className="max-w-lg mx-auto px-4 py-8 pb-20 sm:pb-8">
      <h2 className="text-xl font-bold text-white mb-6">💰 잭팟 풀 현황</h2>

      {/* 에러 배너 */}
      {error && (
        <div className="glass-card p-3 mb-4 text-xs font-mono" style={{ color: '#FF453A', borderColor: 'rgba(255,69,58,0.3)' }}>
          ⚠️ RPC 오류: {error}
        </div>
      )}

      {/* 풀 잔액 */}
      <div className="glass-card p-8 text-center mb-6">
        <div className="text-xs text-gray-500 mb-2">현재 풀 잔액</div>
        {loading ? (
          <div className="text-4xl font-bold text-gray-600">—</div>
        ) : (
          <div className="text-4xl font-bold" style={{ color: '#FFD700' }}>{formatJACK(pool?.balance)}</div>
        )}
        <div className="text-xs text-gray-600 mt-2">참가비의 {LOTTO.POOL_RATIO * 100}%가 누적됩니다</div>
      </div>

      {/* 보상 구조 — RANK_TABLE에서 렌더링 (하드코딩 없음) */}
      <div className="glass-card p-5">
        <div className="text-xs text-gray-500 mb-3">보상 구조</div>
        {RANK_TABLE.filter((r) => r.min > 0).map((r) => (
          <div key={r.min} className="flex justify-between py-2 border-b border-gray-800 last:border-0">
            <span className="text-sm text-gray-300">{r.label} ({r.min}개 일치)</span>
            <span className="text-sm" style={{ color: '#FFD700' }}>{r.reward}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
