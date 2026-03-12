import { Link } from 'react-router-dom'
import StatCard from '../components/StatCard'
import { useChainInfo } from '../hooks/useChainInfo'
import { formatJACK } from '../utils/crypto'
import { LEARNING_URL, CHAIN } from '../config'

/**
 * Home — 블록체인 메인 대시보드
 *
 * 관심사 분리:
 *   - 데이터 폴링·에러 처리 → useChainInfo 훅
 *   - UI 렌더링 → 이 컴포넌트
 */
export default function Home() {
  const { chainInfo, jackpot, loading, error } = useChainInfo()

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 pb-20 sm:pb-8">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="text-xs tracking-widest text-gray-500 mb-2">JACKPOTCHAIN NETWORK</div>
        <h1 className="text-3xl font-bold mb-1">
          <span style={{ color: '#007AFF' }}>싸또</span>
          <span style={{ color: '#FFD700' }}>777</span>
        </h1>
        <p className="text-gray-500 text-sm">UTXO 기반 온체인 복권 블록체인</p>
      </div>

      {/* 노드 연결 오류 배너 — 데이터 없고 에러 있을 때만 표시 */}
      {!loading && (error || !chainInfo) && (
        <div className="glass-card p-4 mb-6 text-center" style={{ borderColor: 'rgba(255,69,58,0.3)' }}>
          <div style={{ color: '#FF453A' }} className="text-sm mb-1">⚠️ 노드 연결 실패</div>
          <div className="text-gray-500 text-xs">
            JackpotChain 노드를 실행하고 RPC 포트({CHAIN.RPC_PORT})를 확인하세요.
          </div>
          {error && <div className="text-xs mt-1 font-mono" style={{ color: '#FF453A' }}>{error}</div>}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        <StatCard label="블록 높이" value={chainInfo?.height ?? chainInfo?.blocks} loading={loading} color="#007AFF" />
        <StatCard label="잭팟 풀" value={chainInfo ? formatJACK(jackpot?.balance) : null} loading={loading} color="#FFD700" />
        <StatCard label="연결 피어" value={chainInfo?.connections} loading={loading} color="#00FF88" />
        <StatCard label="난이도" value={chainInfo?.difficulty?.toFixed(4)} loading={loading} color="#888" />
      </div>

      {/* Jackpot panel */}
      <div className="glass-card p-5 mb-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-semibold text-white">🎰 잭팟 풀 현황</span>
          <Link to="/jackpot" className="text-xs" style={{ color: '#007AFF' }}>상세보기 →</Link>
        </div>
        <div className="text-2xl font-bold mb-1" style={{ color: '#FFD700' }}>
          {loading ? '—' : formatJACK(jackpot?.balance)}
        </div>
        <div className="text-xs text-gray-500">누적 참가비 80%가 이 풀에 쌓입니다</div>
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        {[
          { to: '/wallet',   icon: '💳', label: '지갑 관리',   sub: 'JACK / POT 잔액' },
          { to: '/exchange', icon: '🔄', label: 'JACK→POT',    sub: '복권 참여권 교환' },
          { to: '/lotto',    icon: '🎰', label: '로또 참여',   sub: 'Commit-Reveal 방식' },
          { to: '/explorer', icon: '🔍', label: '블록 탐색기', sub: '블록/TX/주소 조회' },
        ].map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className="glass-card-hover p-4 flex flex-col gap-1 no-underline"
          >
            <span className="text-2xl">{item.icon}</span>
            <span className="text-sm font-semibold text-white">{item.label}</span>
            <span className="text-xs text-gray-500">{item.sub}</span>
          </Link>
        ))}
      </div>

      {/* Learning link */}
      <div className="glass-card p-4 text-center" style={{ borderColor: 'rgba(0,122,255,0.2)' }}>
        <div className="text-xs text-gray-500 mb-2">블록체인이 처음이신가요?</div>
        <a
          href={LEARNING_URL}
          target="_blank"
          rel="noreferrer"
          className="text-sm font-semibold"
          style={{ color: '#007AFF' }}
        >
          📚 블록체인 교육 학습하기 →
        </a>
      </div>
    </div>
  )
}
