/**
 * @module useChainInfo
 * @description 블록체인 기본 정보와 잭팟 풀을 POLL_INTERVAL_MS 주기로 함께 폴링합니다.
 * 두 RPC를 Promise.all로 묶어 단일 useRpc 인스턴스로 처리합니다.
 */
import { useCallback } from 'react'
import { useRpc } from './useRpc'
import { getBlockchainInfo, getJackpotPool } from '../utils/rpc'
import { POLL_INTERVAL_MS } from '../config'

/**
 * @typedef {Object} ChainInfoResult
 * @property {object|null} chainInfo - getblockchaininfo 응답 (blocks, difficulty, connections 등)
 * @property {object|null} jackpot   - getjackpotpool 응답 (balance 등)
 * @property {boolean}     loading   - 최초 로딩 여부
 * @property {string|null} error     - 마지막 에러 메시지
 * @property {Function}    refresh   - 수동 갱신
 */

/**
 * 블록체인 정보와 잭팟 풀을 함께 폴링합니다.
 * @returns {ChainInfoResult}
 */
export function useChainInfo() {
  const fetcher = useCallback(() => Promise.all([getBlockchainInfo(), getJackpotPool()]), [])
  const { data, loading, error, refetch } = useRpc(fetcher, POLL_INTERVAL_MS)
  const [chainInfo, jackpot] = data ?? [null, null]
  return { chainInfo, jackpot, loading, error, refresh: refetch }
}
