/**
 * @module useJackpotPool
 * @description 잭팟 풀 잔액을 POLL_INTERVAL_MS 주기로 폴링합니다.
 */
import { useRpc } from './useRpc'
import { getJackpotPool } from '../utils/rpc'
import { POLL_INTERVAL_MS } from '../config'

/**
 * @typedef {Object} JackpotPoolResult
 * @property {object|null} pool    - getjackpotpool 응답 (balance 등)
 * @property {boolean}     loading
 * @property {string|null} error
 * @property {Function}    refresh
 */

/**
 * 잭팟 풀 정보를 폴링합니다.
 * @returns {JackpotPoolResult}
 */
export function useJackpotPool() {
  const { data: pool, loading, error, refetch } = useRpc(getJackpotPool, POLL_INTERVAL_MS)
  return { pool, loading, error, refresh: refetch }
}
