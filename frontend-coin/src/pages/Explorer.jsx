import { useState, useEffect, useCallback } from 'react'
import { getBlockchainInfo, getBlockHash, getBlock, getRawTransaction } from '../utils/rpc'
import { shortHash, formatJACK, timeAgo } from '../utils/crypto'

export default function Explorer() {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState(null)
  const [resultType, setResultType] = useState('') // block | tx | address
  const [recentBlocks, setRecentBlocks] = useState([])
  const [loading, setLoading] = useState(false)
  const [chainHeight, setChainHeight] = useState(0)

  const loadRecentBlocks = useCallback(async () => {
    try {
      const info = await getBlockchainInfo()
      const height = info?.height ?? info?.blocks ?? 0
      setChainHeight(height)
      const blocks = []
      for (let h = height; h > Math.max(0, height - 5); h--) {
        const hash = await getBlockHash(h)
        const block = await getBlock(hash)
        blocks.push(block)
      }
      setRecentBlocks(blocks)
    } catch {}
  }, [])

  useEffect(() => { loadRecentBlocks() }, [loadRecentBlocks])

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setResult(null)
    try {
      const q = query.trim()
      // 높이(숫자)
      if (/^\d+$/.test(q)) {
        const hash = await getBlockHash(parseInt(q))
        const block = await getBlock(hash)
        setResult(block)
        setResultType('block')
      }
      // 블록 해시 (64 hex)
      else if (/^[0-9a-fA-F]{64}$/.test(q)) {
        try {
          const block = await getBlock(q)
          setResult(block)
          setResultType('block')
        } catch {
          const tx = await getRawTransaction(q)
          setResult(tx)
          setResultType('tx')
        }
      }
      // 주소
      else {
        setResult({ address: q })
        setResultType('address')
      }
    } catch (e) {
      setResult({ error: e.message })
      setResultType('error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 pb-20 sm:pb-8">
      <h2 className="text-xl font-bold text-white mb-2">🔍 블록 탐색기</h2>
      <p className="text-gray-500 text-xs mb-4">블록 해시, 높이, TX ID, 주소 검색</p>

      {/* 검색창 */}
      <form onSubmit={handleSearch} className="flex gap-2 mb-6">
        <input
          type="text"
          placeholder="블록 높이 / 해시 / TXID / 주소..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1 bg-transparent border border-gray-700 rounded-xl px-4 py-3 text-sm text-white outline-none focus:border-blue-500"
        />
        <button type="submit" className="btn-primary px-5" disabled={loading}>
          {loading ? '...' : '검색'}
        </button>
      </form>

      {/* 검색 결과 */}
      {result && !result.error && resultType === 'block' && (
        <div className="glass-card p-5 mb-6">
          <div className="text-xs text-gray-500 mb-3">블록 상세</div>
          <div className="grid grid-cols-2 gap-y-2 text-sm">
            {[
              ['높이', result.height],
              ['해시', shortHash(result.hash, 12)],
              ['TX 수', result.tx?.length ?? result.transactions?.length],
              ['시간', result.time ? timeAgo(result.time) : '—'],
              ['크기', result.size ? `${result.size} bytes` : '—'],
              ['난이도', result.difficulty?.toFixed(4)],
            ].map(([k, v]) => (
              <div key={k} className="flex flex-col">
                <span className="text-gray-500 text-xs">{k}</span>
                <span className="text-white font-mono text-xs">{v ?? '—'}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {result?.error && (
        <div className="glass-card p-4 mb-6 text-sm" style={{ color: '#FF453A' }}>
          검색 실패: {result.error}
        </div>
      )}

      {/* 최근 블록 목록 */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm text-gray-400">최근 블록</span>
          <span className="text-xs text-gray-600">높이 #{chainHeight}</span>
        </div>
        {recentBlocks.length === 0 ? (
          <div className="glass-card p-6 text-center text-gray-600 text-sm">
            노드 연결 후 블록 목록이 표시됩니다
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {recentBlocks.map((b) => (
              <div
                key={b?.hash}
                className="glass-card p-4 flex items-center justify-between cursor-pointer hover:border-blue-500/30 transition-colors"
                onClick={() => { setResult(b); setResultType('block'); setQuery(String(b?.height)) }}
              >
                <div>
                  <div className="text-sm font-semibold text-white">#{b?.height}</div>
                  <div className="text-xs text-gray-500 font-mono">{shortHash(b?.hash)}</div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-400">{b?.tx?.length ?? 0} TX</div>
                  <div className="text-xs text-gray-600">{b?.time ? timeAgo(b.time) : ''}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
