import { useState, useEffect, useCallback } from 'react'

/**
 * RPC 호출 훅 — 자동 폴링 지원
 * @param {Function} fetcher - rpc 함수
 * @param {number} interval - 폴링 간격(ms), 0이면 수동
 */
export function useRpc(fetcher, interval = 0) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    try {
      const result = await fetcher()
      setData(result)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [fetcher])

  useEffect(() => {
    fetch()
    if (!interval) return
    const id = setInterval(fetch, interval)
    return () => clearInterval(id)
  }, [fetch, interval])

  return { data, loading, error, refetch: fetch }
}

/**
 * 단순 폴링 훅
 */
export function usePolling(fetcher, intervalMs = 15000) {
  return useRpc(fetcher, intervalMs)
}
