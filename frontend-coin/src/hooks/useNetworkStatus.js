/**
 * @module useNetworkStatus
 * @description 피어 목록, 네트워크 정보, 멤풀 상태를 POLL_INTERVAL_MS 주기로 함께 폴링합니다.
 * 세 RPC를 Promise.all로 묶어 단일 useRpc 인스턴스로 처리합니다.
 */
import { useCallback } from 'react'
import { useRpc } from './useRpc'
import { getPeerInfo, getNetworkInfo, getMempoolInfo } from '../utils/rpc'
import { POLL_INTERVAL_MS } from '../config'

/**
 * @typedef {Object} PeerInfo
 * @property {string}  addr    - 피어 주소 (ip:port)
 * @property {boolean} inbound - true면 인바운드 연결
 * @property {number}  [version] - 프로토콜 버전
 */

/**
 * @typedef {Object} NetworkStatusResult
 * @property {PeerInfo[]}  peers   - 연결된 피어 목록 (없으면 [])
 * @property {object|null} netInfo - getnetworkinfo 응답
 * @property {object|null} mempool - getmempoolinfo 응답 (size, bytes 등)
 * @property {boolean}     loading
 * @property {string|null} error
 * @property {Function}    refresh
 */

/**
 * 네트워크 상태 전반을 폴링합니다.
 * @returns {NetworkStatusResult}
 */
export function useNetworkStatus() {
  const fetcher = useCallback(
    () => Promise.all([getPeerInfo(), getNetworkInfo(), getMempoolInfo()]),
    []
  )
  const { data, loading, error, refetch } = useRpc(fetcher, POLL_INTERVAL_MS)
  const [peers, netInfo, mempool] = data ?? [[], null, null]
  return { peers: peers ?? [], netInfo, mempool, loading, error, refresh: refetch }
}
