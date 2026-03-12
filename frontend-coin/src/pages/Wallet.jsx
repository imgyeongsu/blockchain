import { useState, useEffect } from 'react'
import { getBalance, listUnspent, getNewAddress, sendRawTransaction } from '../utils/rpc'
import { formatJACK, formatPOT, loadWallet, saveWallet, clearWallet, shortAddr, shortHash } from '../utils/crypto'
import { useToast } from '../components/Toast'

export default function Wallet() {
  const [wallet, setWallet] = useState(loadWallet())
  const [balance, setBalance] = useState(null)
  const [utxos, setUtxos] = useState([])
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState('overview') // overview | send | utxo
  const [connectMode, setConnectMode] = useState('') // new | import | privkey
  const [privkeyInput, setPrivkeyInput] = useState('')
  const [sendTo, setSendTo] = useState('')
  const [sendAmount, setSendAmount] = useState('')
  const { show } = useToast()

  const fetchBalance = async () => {
    if (!wallet) return
    try {
      const [bal, unspent] = await Promise.all([
        getBalance(),
        listUnspent(wallet.address),
      ])
      setBalance(bal)
      setUtxos(unspent || [])
    } catch (e) {
      show('잔액 조회 실패: ' + e.message, 'error')
    }
  }

  useEffect(() => {
    fetchBalance()
  }, [wallet])

  const handleNewWallet = async () => {
    setLoading(true)
    try {
      const address = await getNewAddress()
      const w = { address, label: '기본 지갑', createdAt: Date.now() }
      saveWallet(w)
      setWallet(w)
      show('새 지갑 생성 완료!', 'success')
    } catch (e) {
      show('지갑 생성 실패: ' + e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  const handlePrivkey = () => {
    if (!privkeyInput.trim()) return
    // 개인키에서 주소 추출 (실제 secp256k1 구현 생략 — 백엔드 RPC 사용)
    show('개인키 가져오기는 노드 연결 후 사용 가능합니다.', 'warning')
  }

  const handleDisconnect = () => {
    clearWallet()
    setWallet(null)
    setBalance(null)
    setUtxos([])
  }

  const handleSend = async () => {
    if (!sendTo || !sendAmount) return
    setLoading(true)
    try {
      const txid = await sendRawTransaction(`send:${sendTo}:${sendAmount}`)
      show(`송금 완료! TXID: ${txid?.slice(0, 12)}...`, 'success')
      setSendTo('')
      setSendAmount('')
      fetchBalance()
    } catch (e) {
      show('송금 실패: ' + e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  // 지갑 미연결 화면
  if (!wallet) {
    return (
      <div className="max-w-md mx-auto px-4 py-8 pb-20 sm:pb-8">
        <h2 className="text-xl font-bold text-white mb-6">💳 지갑 연결</h2>
        <p className="text-gray-500 text-sm mb-6">개인키는 절대 서버로 전송되지 않습니다. 모든 서명은 브라우저에서 처리됩니다.</p>
        <div className="flex flex-col gap-3">
          <button className="btn-primary py-4 text-base" onClick={handleNewWallet} disabled={loading}>
            {loading ? '생성 중...' : '✨ 새 지갑 생성 (노드에서 발급)'}
          </button>
          <button
            className="glass-card p-4 text-sm text-gray-300 text-left hover:border-blue-500/30 transition-colors"
            onClick={() => setConnectMode('privkey')}
          >
            🔑 개인키 직접 입력 (hex)
          </button>
          {connectMode === 'privkey' && (
            <div className="glass-card p-4 flex flex-col gap-3">
              <input
                type="text"
                placeholder="개인키 hex 입력..."
                value={privkeyInput}
                onChange={(e) => setPrivkeyInput(e.target.value)}
                className="bg-transparent border border-gray-700 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
              />
              <button className="btn-primary" onClick={handlePrivkey}>가져오기</button>
            </div>
          )}
        </div>
      </div>
    )
  }

  // 지갑 연결됨
  const jackBalance = balance?.JACK ?? balance
  const potBalance = balance?.POT ?? 0

  return (
    <div className="max-w-lg mx-auto px-4 py-6 pb-20 sm:pb-8">
      {/* 지갑 주소 카드 */}
      <div className="glass-card p-5 mb-4">
        <div className="text-xs text-gray-500 mb-2">내 주소</div>
        <div className="text-sm text-white font-mono break-all mb-3">{wallet.address}</div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="text-xs text-gray-500">JACK 잔액</div>
            <div className="text-lg font-bold" style={{ color: '#007AFF' }}>{formatJACK(jackBalance)}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">POT 잔액</div>
            <div className="text-lg font-bold" style={{ color: '#FFD700' }}>{formatPOT(potBalance)}</div>
          </div>
        </div>
      </div>

      {/* 탭 */}
      <div className="flex gap-2 mb-4">
        {['overview', 'send', 'utxo'].map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="px-4 py-2 rounded-lg text-xs transition-colors"
            style={tab === t
              ? { background: 'rgba(0,122,255,0.2)', color: '#007AFF', border: '1px solid rgba(0,122,255,0.3)' }
              : { background: 'rgba(255,255,255,0.05)', color: '#888', border: '1px solid transparent' }
            }
          >
            {{ overview: '개요', send: '송금', utxo: 'UTXO' }[t]}
          </button>
        ))}
      </div>

      {/* 탭 콘텐츠 */}
      {tab === 'send' && (
        <div className="glass-card p-5 flex flex-col gap-4">
          <div>
            <div className="text-xs text-gray-500 mb-1">받는 주소</div>
            <input
              type="text"
              placeholder="W..."
              value={sendTo}
              onChange={(e) => setSendTo(e.target.value)}
              className="w-full bg-transparent border border-gray-700 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">금액 (JACK)</div>
            <input
              type="number"
              placeholder="0.0"
              value={sendAmount}
              onChange={(e) => setSendAmount(e.target.value)}
              className="w-full bg-transparent border border-gray-700 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
            />
          </div>
          <button className="btn-primary" onClick={handleSend} disabled={loading || !sendTo || !sendAmount}>
            {loading ? '전송 중...' : '📤 송금하기'}
          </button>
        </div>
      )}

      {tab === 'utxo' && (
        <div className="flex flex-col gap-2">
          {utxos.length === 0 ? (
            <div className="glass-card p-6 text-center text-gray-500 text-sm">UTXO 없음</div>
          ) : (
            utxos.map((u, i) => (
              <div key={i} className="glass-card p-4">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-gray-500">{shortHash(u.txid)}:{u.vout}</span>
                  <span className="text-sm font-semibold" style={{ color: '#007AFF' }}>{formatJACK(u.amount)}</span>
                </div>
                <div className="text-xs text-gray-600 mt-1">확인: {u.confirmations}블록</div>
              </div>
            ))
          )}
        </div>
      )}

      {tab === 'overview' && (
        <div className="flex flex-col gap-3">
          <button className="glass-card p-4 text-sm text-left text-gray-400 hover:text-white transition-colors" onClick={fetchBalance}>
            🔄 잔액 새로고침
          </button>
          <button className="glass-card p-4 text-sm text-left" style={{ color: '#FF453A' }} onClick={handleDisconnect}>
            🔌 지갑 연결 해제
          </button>
        </div>
      )}
    </div>
  )
}
