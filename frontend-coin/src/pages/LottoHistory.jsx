import { loadLottoHistory } from '../utils/crypto'

export default function LottoHistory() {
  const history = loadLottoHistory()
  const total = history.length
  const wins = history.filter((h) => h.matches >= 1).length

  return (
    <div className="max-w-lg mx-auto px-4 py-8 pb-20 sm:pb-8">
      <h2 className="text-xl font-bold text-white mb-6">📜 로또 히스토리</h2>
      <div className="grid grid-cols-3 gap-3 mb-6">
        {[
          { label: '총 참여', value: total },
          { label: '당첨', value: wins },
          { label: '당첨률', value: total ? `${((wins/total)*100).toFixed(1)}%` : '—' },
        ].map((s) => (
          <div key={s.label} className="glass-card p-4 text-center">
            <div className="text-xs text-gray-500 mb-1">{s.label}</div>
            <div className="text-xl font-bold text-white">{s.value}</div>
          </div>
        ))}
      </div>
      {history.length === 0 ? (
        <div className="glass-card p-8 text-center text-gray-600 text-sm">아직 참여 내역이 없습니다</div>
      ) : (
        <div className="flex flex-col gap-2">
          {history.map((h, i) => (
            <div key={i} className="glass-card p-4">
              <div className="flex justify-between items-center mb-1">
                <span className="text-sm text-white font-mono">{h.myNumbers?.join(' ')}</span>
                <span className="text-xs" style={{ color: h.matches >= 3 ? '#FFD700' : '#888' }}>{h.label || '—'}</span>
              </div>
              <div className="text-xs text-gray-600">{new Date(h.ts).toLocaleString('ko-KR')}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
