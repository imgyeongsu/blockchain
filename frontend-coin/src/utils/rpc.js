/**
 * @module rpc
 * @description JSON-RPC 2.0 클라이언트. JackpotChain 노드와 통신합니다.
 *
 * 모든 RPC 호출은 이 파일의 `rpc()` 함수를 통해 이루어지며,
 * 실제 노드 주소는 config.js / .env 에서 주입됩니다.
 * 컴포넌트가 노드 주소에 직접 의존하지 않으므로 환경 교체가 용이합니다.
 */
import { DEFAULT_RPC_URL, STORAGE_KEYS } from '../config'

/**
 * 런타임 RPC URL을 반환합니다.
 * localStorage 설정이 있으면 우선 사용하고, 없으면 .env 기본값을 사용합니다.
 * @returns {string} RPC 엔드포인트 URL
 */
function getRpcUrl() {
  return localStorage.getItem(STORAGE_KEYS.RPC_URL) || DEFAULT_RPC_URL
}

let reqId = 1

// ── 공통 응답 타입 정의 ────────────────────────────────────────────────────────

/**
 * @typedef {Object} BlockchainInfo
 * @property {number} blocks          - 현재 블록 높이
 * @property {number} headers         - 헤더 수
 * @property {string} bestblockhash   - 최신 블록 해시
 * @property {number} difficulty      - 현재 난이도
 * @property {number} connections     - 연결된 피어 수
 * @property {number} [networkhashps] - 네트워크 해시레이트 (H/s)
 */

/**
 * @typedef {Object} Block
 * @property {string}   hash       - 블록 해시
 * @property {number}   height     - 블록 높이
 * @property {number}   time       - 유닉스 타임스탬프
 * @property {string[]} tx         - 트랜잭션 ID 목록
 * @property {number}   difficulty - 이 블록의 난이도
 */

/**
 * @typedef {Object} MempoolInfo
 * @property {number} size  - 멤풀 트랜잭션 수
 * @property {number} bytes - 멤풀 전체 크기(bytes)
 */

/**
 * @typedef {Object} PeerInfo
 * @property {string}  addr      - 피어 주소 (host:port)
 * @property {boolean} inbound   - 인바운드 연결 여부
 * @property {number}  [version] - 프로토콜 버전
 */

/**
 * @typedef {Object} JackpotPool
 * @property {number} balance - 잭팟 풀 잔액 (satoshi)
 */

/**
 * @typedef {Object} UTXO
 * @property {string} txid    - 트랜잭션 ID
 * @property {number} vout    - 출력 인덱스
 * @property {number} amount  - 금액 (JACK)
 * @property {string} address - 주소
 */

// ── JSON-RPC 2.0 기반 통신 ─────────────────────────────────────────────────────

/**
 * JSON-RPC 2.0 요청을 전송하고 result를 반환합니다.
 *
 * @param {string} method     - RPC 메서드 이름
 * @param {Array}  [params=[]] - 메서드 파라미터
 * @returns {Promise<any>} RPC result 값
 * @throws {Error} HTTP 오류 또는 RPC 레벨 오류 시
 */
export async function rpc(method, params = []) {
  const url = getRpcUrl()
  const body = JSON.stringify({ jsonrpc: '2.0', method, params, id: reqId++ })
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  if (data.error) throw new Error(data.error.message || JSON.stringify(data.error))
  return data.result
}

// ── 블록체인 정보 ──────────────────────────────────────────────────────────────

/** @returns {Promise<BlockchainInfo>} */
export const getBlockchainInfo = () => rpc('getblockchaininfo')

/**
 * @param {string} hash - 블록 해시
 * @returns {Promise<Block>}
 */
export const getBlock = (hash) => rpc('getblock', [hash])

/**
 * @param {number} height - 블록 높이
 * @returns {Promise<string>} 블록 해시
 */
export const getBlockHash = (height) => rpc('getblockhash', [height])

/** @returns {Promise<string>} 최신 블록 해시 */
export const getBestBlockHash = () => rpc('getbestblockhash')

/** @returns {Promise<number>} 현재 블록 높이 */
export const getBlockCount = () => rpc('getblockcount')

/**
 * verbose=true로 원시 트랜잭션을 조회합니다.
 * @param {string} txid - 트랜잭션 ID
 * @returns {Promise<object>} 디코딩된 트랜잭션 객체
 */
export const getRawTransaction = (txid) => rpc('getrawtransaction', [txid, true])

// ── 멤풀 ───────────────────────────────────────────────────────────────────────

/** @returns {Promise<MempoolInfo>} */
export const getMempoolInfo = () => rpc('getmempoolinfo')

/** @returns {Promise<string[]>} 멤풀 트랜잭션 ID 목록 */
export const getRawMempool = () => rpc('getrawmempool')

// ── 네트워크 ──────────────────────────────────────────────────────────────────

/** @returns {Promise<PeerInfo[]>} */
export const getPeerInfo = () => rpc('getpeerinfo')

/** @returns {Promise<object>} 네트워크 정보 */
export const getNetworkInfo = () => rpc('getnetworkinfo')

// ── 지갑 ──────────────────────────────────────────────────────────────────────

/**
 * 지갑 전체 잔액을 반환합니다.
 * @returns {Promise<number|object>} 잔액 (JACK 숫자 또는 { JACK, POT } 객체)
 */
export const getBalance = () => rpc('getbalance')

/**
 * 특정 주소의 UTXO 목록을 조회합니다.
 * 주소 미지정 시 지갑 전체 UTXO를 반환합니다.
 * @param {string} [address] - 필터링할 주소 (옵션)
 * @returns {Promise<UTXO[]>}
 */
export const listUnspent = (address) =>
  rpc('listunspent', address ? [0, 9999999, [address]] : [])

/** @returns {Promise<string>} 새 수신 주소 */
export const getNewAddress = () => rpc('getnewaddress')

/**
 * 서명된 트랜잭션을 네트워크에 브로드캐스트합니다.
 * @param {string} hex - 서명된 트랜잭션 hex 문자열
 * @returns {Promise<string>} txid
 */
export const sendRawTransaction = (hex) => rpc('sendrawtransaction', [hex])

/**
 * 지갑에서 직접 주소로 송금합니다 (테스트/데모용).
 * @param {string} address - 수신 주소
 * @param {number} amount  - 송금액 (JACK)
 * @returns {Promise<string>} txid
 */
export const sendToAddress = (address, amount) => rpc('sendtoaddress', [address, amount])

// ── 가챠(로또) ────────────────────────────────────────────────────────────────

/** @returns {Promise<object>} 가챠 전체 정보 */
export const getGachaInfo = () => rpc('getgachainfo')

/** @returns {Promise<JackpotPool>} 잭팟 풀 잔액 */
export const getJackpotPool = () => rpc('getjackpotpool')

/** @returns {Promise<object[]>} 가챠 종류 목록 */
export const getGachaTypes = () => rpc('getgachatypes')

/**
 * Commit TX를 생성합니다 (Commit-Reveal 1단계).
 * type은 옵션으로, 지정하지 않으면 서버 기본값을 사용합니다.
 * @param {number}  target - 선택 번호 (0~15)
 * @param {number}  [type] - 가챠 종류 ID
 * @returns {Promise<string>} Commit TX ID
 */
export const gachaCommit = (target, type) =>
  rpc('gachacommit', [target, type].filter((v) => v !== undefined))

/** @returns {Promise<object[]>} 내 커밋 목록 */
export const listGachaCommits = () => rpc('listgachacommits')

/**
 * Reveal TX를 생성합니다 (Commit-Reveal 2단계).
 * @param {string} commitHash - Commit 단계에서 생성된 해시
 * @returns {Promise<string>} Reveal TX ID
 */
export const gachaReveal = (commitHash) => rpc('gachareveal', [commitHash])

/**
 * 특정 주소의 로또 커밋 목록을 조회합니다.
 * @param {string} [address] - 필터링할 주소 (옵션)
 * @returns {Promise<object[]>}
 */
export const listLottoCommits = (address) =>
  rpc('listlottocommits', address ? [address] : [])

/**
 * 로또 결과를 확인합니다.
 * @param {string} commitHash - 확인할 커밋 해시
 * @returns {Promise<object>} 결과 객체
 */
export const lottoCheckResult = (commitHash) => rpc('lottocheckresult', [commitHash])
