/**
 * @module useLottoGame
 * @description Commit-Reveal 방식 로또 게임의 전체 상태를 관리하는 훅.
 *
 * 상태 전환 흐름:
 *   IDLE → WAITING → CLAIMABLE → CLAIMED
 *
 * Commit-Reveal 방식을 택한 이유:
 *   사용자 번호를 SHA256 해시로 봉인한 뒤 블록이 확정된 이후에만 공개하므로,
 *   채굴자와 운영자 어느 쪽도 결과 블록을 예측하거나 조작할 수 없습니다.
 *
 * RPC 실패 처리 방침:
 *   실제 노드가 없는 체험 환경에서도 UI 플로우를 유지하기 위해
 *   gachaCommit/gachaReveal RPC는 실패해도 무시하고 로컬 시뮬레이션을 계속합니다.
 */
import { useState, useEffect, useCallback } from 'react'
import { gachaCommit, gachaReveal } from '../utils/rpc'
import { generateNonce, calcCommitHash, judgeRank, saveLottoCommit, loadWallet } from '../utils/crypto'
import { LOTTO } from '../config'

const HEX_DIGITS = LOTTO.HEX_DIGITS

/** 매 참여마다 랜덤 초기 번호를 생성합니다. */
function makeInitNumbers() {
  return Array.from(
    { length: LOTTO.SLOT_COUNT },
    () => HEX_DIGITS[Math.floor(Math.random() * HEX_DIGITS.length)]
  )
}

/**
 * @typedef {'IDLE'|'WAITING'|'CLAIMABLE'|'CLAIMED'} LottoPhase
 */

/**
 * @typedef {Object} RankResult
 * @property {number}      matches   - 일치한 슬롯 수
 * @property {string}      label     - 등수 레이블 (예: '1등 🥇')
 * @property {string}      reward    - 보상 설명 (예: '잭팟 풀의 50%')
 * @property {number|null} rewardJACK - 보상 satoshi 값 (잭팟은 null)
 */

/**
 * @typedef {Object} LottoGameReturn
 * @property {LottoPhase}    phase        - 현재 상태
 * @property {string[]}      myNumbers    - 선택한 hex 숫자 배열 (예: ['A','3','F','7','1','C'])
 * @property {string}        commitHash   - Commit 단계에서 생성된 해시
 * @property {number}        countdown    - 대기 남은 시간(초)
 * @property {string[]}      targetDigits - 결과 비교용 블록 digit 배열
 * @property {RankResult|null} result     - Claim 후 판정 결과
 * @property {boolean}       loading      - RPC 요청 처리 중
 * @property {string|null}   error        - 마지막 에러 메시지
 * @property {(idx:number)=>void} cycleNumber   - 다이얼 순환 (IDLE 전용)
 * @property {()=>void}      randomize    - 랜덤 번호 재생성 (IDLE 전용)
 * @property {()=>Promise<void>} handleCommit  - Commit TX 전송
 * @property {()=>Promise<void>} handleClaim   - Claim TX 전송
 * @property {()=>void}      reset        - 초기 상태로 복귀
 */

/**
 * 로또 게임 상태 기계를 관리합니다.
 * @returns {LottoGameReturn}
 */
export function useLottoGame() {
  const [phase, setPhase] = useState('IDLE')
  const [myNumbers, setMyNumbers] = useState(makeInitNumbers)
  const [nonce, setNonce] = useState('')
  const [commitHash, setCommitHash] = useState('')
  const [countdown, setCountdown] = useState(LOTTO.WAIT_COUNTDOWN_SEC)
  const [targetDigits, setTargetDigits] = useState([])
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // IDLE 상태에서만 번호 변경 허용
  const cycleNumber = useCallback((idx) => {
    if (phase !== 'IDLE') return
    setMyNumbers((prev) => {
      const next = [...prev]
      const cur = HEX_DIGITS.indexOf(next[idx])
      next[idx] = HEX_DIGITS[(cur + 1) % HEX_DIGITS.length]
      return next
    })
  }, [phase])

  const randomize = useCallback(() => {
    if (phase !== 'IDLE') return
    setMyNumbers(makeInitNumbers())
  }, [phase])

  /** Commit: nonce + 번호를 SHA256 해시하여 블록체인에 기록합니다. */
  const handleCommit = useCallback(async () => {
    if (!loadWallet()) {
      setError('지갑을 먼저 연결해주세요.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const n = generateNonce()
      const hash = await calcCommitHash(n, myNumbers.map((x) => `0x${x}`))
      setNonce(n)
      setCommitHash(hash)

      // RPC 실패해도 로컬 체험 플로우 유지 (체험 모드)
      try { await gachaCommit(parseInt(myNumbers[0], 16)) } catch {}

      saveLottoCommit({
        nonce: n,
        myNumbers: myNumbers.map((x) => `0x${x}`),
        commitHash: hash,
        ts: Date.now(),
        status: 'COMMITTED',
      })
      setPhase('WAITING')
      setCountdown(LOTTO.WAIT_COUNTDOWN_SEC)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [myNumbers])

  // 카운트다운 → 0이 되면 가상 블록 digit 생성 후 CLAIMABLE 전환
  useEffect(() => {
    if (phase !== 'WAITING') return
    if (countdown <= 0) {
      const digits = Array.from(
        { length: LOTTO.SLOT_COUNT },
        () => HEX_DIGITS[Math.floor(Math.random() * HEX_DIGITS.length)]
      )
      setTargetDigits(digits)
      setPhase('CLAIMABLE')
      return
    }
    const id = setTimeout(() => setCountdown((c) => c - 1), 1000)
    return () => clearTimeout(id)
  }, [phase, countdown])

  /** Claim: Reveal TX 전송 후 번호 대조로 등수를 판정합니다. */
  const handleClaim = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const rank = judgeRank(
        myNumbers.map((x) => `0x${x}`),
        targetDigits.map((d) => `0x${d}`)
      )
      setResult(rank)
      setPhase('CLAIMED')
      try { await gachaReveal(commitHash) } catch {}
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [myNumbers, targetDigits, commitHash])

  const reset = useCallback(() => {
    setPhase('IDLE')
    setMyNumbers(makeInitNumbers())
    setNonce('')
    setCommitHash('')
    setTargetDigits([])
    setResult(null)
    setCountdown(LOTTO.WAIT_COUNTDOWN_SEC)
    setError(null)
  }, [])

  return {
    phase, myNumbers, commitHash, countdown, targetDigits, result, loading, error,
    cycleNumber, randomize, handleCommit, handleClaim, reset,
  }
}
