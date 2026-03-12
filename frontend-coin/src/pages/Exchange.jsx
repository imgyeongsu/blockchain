import { useState, useEffect } from 'react'
import { getBalance } from '../utils/rpc'
import { formatJACK, formatPOT, loadWallet } from '../utils/crypto'
import { useToast } from '../components/Toast'
import { TOKEN } from '../config'

const RATIO = TOKEN.JACK_PER_POT

export default function Exchange() {
  const wallet = loadWallet()
  const [jackAmount, setJackAmount] = useState('')
  const [balance, setBalance] = useState(null)
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState([])
  const { show } = useToast()

  const potAmount = Math.floor(Number(jackAmount) / RATIO)

  useEffect(() => {
    if (!wallet) return
    getBalance().then(setBalance).catch(() => {})
  }, [])

  const handleExchange = async () => {
    if (!wallet) { show('지갑을 먼저 연결해주세요.', 'warning'); return }
    if (!jackAmount || potAmount < 1) { show(`최소 ${RATIO} JACK이 필요합니다.`, 'warning'); return }
    setLoading(true)
    try {
      // 실제로는 JACK→POT 교환 TX 생성 (version=2, output[0]=POT, output[1]=잔돈)
      // 시뮬레이션:
      await new Promise((r) => setTimeout(r, 800))
      const entry = {
        id: Date.now(),
        jackIn: Number(jackAmount),
        potOut: potAmount,
        ts: Date.now(),
        status: 'pending',
      }
      setHistory((prev) => [entry, ...prev])
      show(`${jackAmount} JACK → ${potAmount} POT 교환 요청됨!`, 'success')
      setJackAmount('')
    } catch (e) {
      show('교환 실패: ' + e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-md mx-auto px-4 py-8 pb-20 sm:pb-8">
      <h2 className="text-xl font-bold text-white mb-2">🔄 JACK ↔ POT 교환</h2>
      <p className="text-gray-500 text-xs mb-6">로또 참여에는 POT이 필요합니다. 1 POT = 복권 1회</p>

      {/* 비율 안내 */}
      <div className="glass-card p-4 mb-4 flex items-center justify-between">
        <div className="text-center flex-1">
          <div className="text-2xl font-bold" style={{ color: '#007AFF' }}>{RATIO}</div>
          <div className="text-xs text-gray-500">JACK</div>
        </div>
        <div className="text-2xl text-gray-600">→</div>
        <div className="text-center flex-1">
          <div className="text-2xl font-bold" style={{ color: '#FFD700' }}>1</div>
          <div className="text-xs text-gray-500">POT</div>
        </div>
      </div>

      {/* 잔액 */}
      {balance && (
        <div className="text-xs text-gray-500 mb-4">
          보유: {formatJACK(balance?.JACK ?? balance)} / {formatPOT(balance?.POT ?? 0)}
        </div>
      )}

      {/* 입력 */}
      <div className="glass-card p-5 flex flex-col gap-4 mb-4">
        <div>
          <label className="text-xs text-gray-500 block mb-1">JACK 입력</label>
          <input
            type="number"
            placeholder="100, 200, 500..."
            value={jackAmount}
            onChange={(e) => setJackAmount(e.target.value)}
            className="w-full bg-transparent border border-gray-700 rounded-lg px-3 py-2 text-white outline-none focus:border-blue-500 text-sm"
          />
        </div>
        <div className="glass-card p-3 flex items-center justify-between" style={{ background: 'rgba(255,215,0,0.06)', borderColor: 'rgba(255,215,0,0.2)' }}>
          <span className="text-xs text-gray-500">받을 POT</span>
          <span className="text-xl font-bold" style={{ color: '#FFD700' }}>{potAmount || 0} POT</span>
        </div>
        {jackAmount && Number(jackAmount) % RATIO !== 0 && (
          <div className="text-xs" style={{ color: '#FF453A' }}>※ {Number(jackAmount) % RATIO} JACK은 교환 불가 (100 단위)</div>
        )}
        <button className="btn-primary" onClick={handleExchange} disabled={loading || potAmount < 1}>
          {loading ? '처리 중...' : `${jackAmount || 0} JACK → ${potAmount || 0} POT 교환`}
        </button>
      </div>

      {/* 히스토리 */}
      {history.length > 0 && (
        <div>
          <div className="text-xs text-gray-500 mb-2">교환 히스토리</div>
          <div className="flex flex-col gap-2">
            {history.map((h) => (
              <div key={h.id} className="glass-card p-3 flex items-center justify-between">
                <div className="text-sm">{h.jackIn} JACK → <span style={{ color: '#FFD700' }}>{h.potOut} POT</span></div>
                <span className="badge-warning">pending</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
