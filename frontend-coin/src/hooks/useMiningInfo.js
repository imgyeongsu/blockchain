/**
 * @module useMiningInfo
 * @description 채굴 대시보드용 블록체인 정보를 POLL_INTERVAL_MS 주기로 폴링합니다.
 */
import { useRpc } from './useRpc'
import { getBlockchainInfo } from '../utils/rpc'
import { POLL_INTERVAL_MS } from '../config'

/**
 * @typedef {Object} MiningInfoResult
 * @property {object|null} info    - getblockchaininfo 응답 (difficulty, networkhashps 등)
 * @property {boolean}     loading
 * @property {string|null} error
 * @property {Function}    refresh
 */

/**
 * 채굴 관련 블록체인 정보를 폴링합니다.
 * @returns {MiningInfoResult}
 */
export function useMiningInfo() {
  const { data: info, loading, error, refetch } = useRpc(getBlockchainInfo, POLL_INTERVAL_MS)
  return { info, loading, error, refresh: refetch }
}
