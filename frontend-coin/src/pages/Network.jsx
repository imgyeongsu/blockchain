import { useNetworkStatus } from '../hooks/useNetworkStatus'

/**
 * Network — 네트워크 현황 페이지
 *
 * 관심사 분리:
 *   - 데이터 폴링·에러 처리 → useNetworkStatus 훅
 *   - 상태 표시·피어 목록 렌더링 → 이 컴포넌트
 */
export default function Network() {
  const { peers, mempool, loading, error } = useNetworkStatus()

  /** 피어 수를 기반으로 연결 상태를 판정합니다. */
  const syncStatus = loading ? '...' : peers.length > 0 ? 'SYNCED' : 'OFFLINE'
  const statusColor = { SYNCED: '#00FF88', SYNCING: '#FFD700', OFFLINE: '#FF453A', '...': '#888' }

  return (
    <div className="max-w-lg mx-auto px-4 py-8 pb-20 sm:pb-8">
      <h2 className="text-xl font-bold text-white mb-6">🌐 네트워크 현황</h2>

      {/* 에러 배너 */}
      {error && (
        <div className="glass-card p-3 mb-4 text-xs font-mono" style={{ color: '#FF453A', borderColor: 'rgba(255,69,58,0.3)' }}>
          ⚠️ RPC 오류: {error}
        </div>
      )}

      {/* 상태 카드들 */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        {[
          { label: '연결 상태', value: syncStatus, color: statusColor[syncStatus] },
          { label: '연결 피어', value: loading ? '—' : peers.length, color: '#007AFF' },
          { label: '멤풀 TX', value: mempool?.size ?? '—', color: '#00FF88' },
          { label: '멤풀 크기', value: mempool?.bytes ? `${mempool.bytes} B` : '—', color: '#888' },
        ].map((s) => (
          <div key={s.label} className="glass-card p-4">
            <div className="text-xs text-gray-500 mb-1">{s.label}</div>
            <div className="text-xl font-bold" style={{ color: s.color }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* 피어 목록 */}
      <div className="text-xs text-gray-500 mb-3">피어 목록</div>
      {loading ? (
        <div className="glass-card p-6 text-center text-gray-600 text-sm">로딩 중...</div>
      ) : peers.length === 0 ? (
        <div className="glass-card p-6 text-center text-gray-600 text-sm">연결된 피어 없음</div>
      ) : (
        <div className="flex flex-col gap-2">
          {peers.map((p, i) => (
            <div key={i} className="glass-card p-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-white font-mono">{p.addr || p.address}</span>
                <span className={p.inbound ? 'badge-info' : 'badge-success'}>{p.inbound ? 'IN' : 'OUT'}</span>
              </div>
              {p.version && <div className="text-xs text-gray-600 mt-1">v{p.version}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
