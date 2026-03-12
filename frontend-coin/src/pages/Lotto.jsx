import { useEffect } from 'react'
import { useLottoGame } from '../hooks/useLottoGame'
import { useToast } from '../components/Toast'
import { LOTTO } from '../config'

/**
 * Lotto — Commit-Reveal 로또 참여 페이지
 *
 * 관심사 분리:
 *   - 상태 기계(IDLE→WAITING→CLAIMABLE→CLAIMED)·RPC 호출 → useLottoGame 훅
 *   - 토스트 피드백 — 훅의 phase/error 상태를 관찰하여 이 컴포넌트에서 표시
 *     (Toast는 UI 레이어에 속하므로 훅이 직접 호출하지 않습니다)
 *   - UI 렌더링 → 이 컴포넌트
 */
export default function Lotto() {
  const { show } = useToast()
  const {
    phase, myNumbers, commitHash, countdown, targetDigits,
    result, loading, error,
    cycleNumber, randomize, handleCommit, handleClaim, reset,
  } = useLottoGame()

  // 에러 발생 시 토스트 표시
  useEffect(() => {
    if (error) show(error, 'error')
  }, [error])

  // 단계 전환 시 성공/정보 토스트 표시
  useEffect(() => {
    if (phase === 'WAITING') show('Commit 완료! 블록 생성을 기다립니다.', 'success')
    if (phase === 'CLAIMED' && result) {
      show(`결과: ${result.label} — ${result.reward}`, result.matches >= 3 ? 'success' : 'info')
    }
  }, [phase, result])

  return (
    <div className="max-w-md mx-auto px-4 py-8 pb-20 sm:pb-8">
      <h2 className="text-xl font-bold text-white mb-1">🎰 로또 참여</h2>
      <p className="text-gray-500 text-xs mb-6">Commit-Reveal 방식 — 누구도 결과를 조작할 수 없습니다</p>

      {/* 진행 단계 표시 */}
      <div className="flex items-center gap-2 mb-6">
        {['IDLE', 'WAITING', 'CLAIMABLE', 'CLAIMED'].map((s, i) => (
          <div key={s} className="flex items-center gap-1">
            <div
              className="w-2 h-2 rounded-full transition-colors"
              style={{ background: (['IDLE', 'WAITING', 'CLAIMABLE', 'CLAIMED'].indexOf(phase) >= i) ? '#007AFF' : '#333' }}
            />
            {i < 3 && <div className="w-4 h-px" style={{ background: '#222' }} />}
          </div>
        ))}
        <span className="text-xs text-gray-500 ml-2">{phase}</span>
      </div>

      {/* IDLE: 숫자 선택 */}
      {phase === 'IDLE' && (
        <div className="flex flex-col gap-4">
          <div className="glass-card p-5">
            <div className="text-xs text-gray-500 mb-3">6개 숫자를 선택하세요 (클릭으로 순환, 0~F)</div>
            <div className="grid grid-cols-6 gap-2 mb-4">
              {myNumbers.map((n, i) => (
                <button
                  key={i}
                  onClick={() => cycleNumber(i)}
                  className="flex flex-col items-center justify-center rounded-xl py-3 transition-all active:scale-95"
                  style={{ background: 'rgba(0,122,255,0.15)', border: '1px solid rgba(0,122,255,0.4)', color: '#007AFF' }}
                >
                  <span className="text-[10px] text-gray-600">0x</span>
                  <span className="text-lg font-bold">{n}</span>
                </button>
              ))}
            </div>
            <button
              onClick={randomize}
              className="w-full py-2 rounded-lg text-sm text-gray-400 transition-colors"
              style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)' }}
            >
              🎲 랜덤 생성
            </button>
          </div>
          <button className="btn-primary py-4 text-base" onClick={handleCommit} disabled={loading}>
            {loading ? '처리 중...' : '🔒 1 POT 소모하여 Commit'}
          </button>
          <p className="text-xs text-gray-600 text-center">비용: 1 POT (= {LOTTO.COST_POT * 100} JACK)</p>
        </div>
      )}

      {/* WAITING: 블록 대기 카운트다운 */}
      {phase === 'WAITING' && (
        <div className="glass-card p-6 text-center">
          <div className="text-4xl font-bold mb-2" style={{ color: '#007AFF' }}>{countdown}</div>
          <div className="text-sm text-gray-400 mb-4">블록 생성 대기 중...</div>
          <div className="progress-bar mb-4">
            <div
              className="progress-fill"
              style={{ width: `${((LOTTO.WAIT_COUNTDOWN_SEC - countdown) / LOTTO.WAIT_COUNTDOWN_SEC) * 100}%` }}
            />
          </div>
          <div className="text-xs text-gray-600">
            Commit Hash: <span className="font-mono">{commitHash.slice(0, 16)}...</span>
          </div>
          <div className="text-xs text-gray-600 mt-1">nonce는 로컬에 안전하게 저장됨</div>
        </div>
      )}

      {/* CLAIMABLE: Claim 단계 */}
      {phase === 'CLAIMABLE' && (
        <div className="flex flex-col gap-4">
          <div className="glass-card p-5">
            <div className="text-sm font-semibold text-white mb-3">⏰ Claim 가능!</div>
            <div className="text-xs text-gray-500 mb-3">비교 블록 해시 마지막 digit:</div>
            <div className="grid grid-cols-6 gap-2 mb-3">
              {targetDigits.map((d, i) => (
                <div key={i} className="text-center py-2 rounded-lg text-sm font-bold" style={{ background: 'rgba(255,215,0,0.1)', color: '#FFD700' }}>
                  0x{d}
                </div>
              ))}
            </div>
            <div className="text-xs text-gray-500 mb-2">내 숫자 vs 결과:</div>
            <div className="grid grid-cols-6 gap-2">
              {myNumbers.map((n, i) => {
                const match = n === targetDigits[i]
                return (
                  <div
                    key={i}
                    className="text-center py-2 rounded-lg text-xs"
                    style={{
                      background: match ? 'rgba(0,255,136,0.1)' : 'rgba(255,69,58,0.1)',
                      color: match ? '#00FF88' : '#FF453A',
                      border: `1px solid ${match ? 'rgba(0,255,136,0.3)' : 'rgba(255,69,58,0.3)'}`,
                    }}
                  >
                    0x{n}<br />{match ? '✅' : '❌'}
                  </div>
                )
              })}
            </div>
          </div>
          <button className="btn-primary py-4 text-base" onClick={handleClaim} disabled={loading}>
            {loading ? '처리 중...' : '🎁 결과 수령 (Claim)'}
          </button>
        </div>
      )}

      {/* CLAIMED: 결과 */}
      {phase === 'CLAIMED' && result && (
        <div className="flex flex-col gap-4">
          <div
            className="glass-card p-6 text-center"
            style={{ borderColor: result.matches >= 3 ? 'rgba(255,215,0,0.4)' : 'rgba(255,255,255,0.1)' }}
          >
            <div className="text-4xl mb-3">
              {result.matches >= 6 ? '🎊' : result.matches >= 3 ? '🥳' : '😢'}
            </div>
            <div className="text-2xl font-bold mb-1" style={{ color: result.matches >= 3 ? '#FFD700' : '#fff' }}>
              {result.label}
            </div>
            <div className="text-sm text-gray-400 mb-2">{result.matches}개 일치</div>
            <div className="text-lg" style={{ color: '#00FF88' }}>{result.reward}</div>
          </div>
          <button className="btn-primary" onClick={reset}>다시 참여하기</button>
          <a className="text-center text-xs py-2" href="/lotto/history" style={{ color: '#007AFF' }}>
            히스토리 보기 →
          </a>
        </div>
      )}
    </div>
  )
}
