# JackpotChain TODO

> 최종 업데이트: 2026-03-18

## 긴급 (Critical)

- [ ] **miner.py height 버그 수정**
  - 위치: `consensus/miner.py:127`
  - 문제: `height = prev_block.header.timestamp + 1` (타임스탬프를 높이로 잘못 사용)
  - 영향: 블록 높이 계산 오류

- [ ] **wallet.py 개인키 암호화**
  - 위치: `wallet/wallet.py:84, 105`
  - 문제: 개인키 평문 저장
  - 영향: 보안 취약점

## 중요 (High)

- [ ] **_block_buffer 크기 제한**
  - 위치: `network/node.py`
  - 문제: 버퍼 크기 제한 없음
  - 영향: 메모리 누수 가능

- [ ] **헤더 검증 로직 구현**
  - 위치: `sync/manager.py:140`
  - 문제: 헤더 수신 후 검증 안 함
  - 영향: 악의적 헤더 수용 가능

- [ ] **Claim payout 유효성 검사 강화**
  - 위치: `gacha/service.py:create_claim()`
  - 문제: payout 금액 검증 부실
  - 영향: 풀 고갈 가능

- [ ] **LOTTO_CLAIM 검증 완성**
  - 위치: `validation/transaction.py`
  - 문제: `is_lotto_claim` 변수 선언 후 미사용
  - 영향: 검증 우회 가능

## 개선 (Medium)

- [ ] **PONG RTT 계산 구현**
  - 위치: `network/node.py:340`
  - 문제: `pass  # TODO: RTT 계산`
  - 영향: 피어 상태 모니터링 불가

- [ ] **디버그 로그 정리**
  - 위치: `mempool/pool.py`, `rpc/server.py`
  - 문제: 디버그용 print 문 정리 필요

- [ ] **UTXO 예약 ↔ mempool 동기화**
  - 위치: `gacha/service.py`
  - 문제: mempool 제거 시 UTXO 예약 자동 해제 안 됨

## 배포

- [ ] **AWS 시드노드 코드 업데이트**
  - TX 전파 버그 수정 반영
  - 테스트 필요

---

## 완료 (2026-03-18)

- [x] TX 전파 버그 수정 (`network/node.py:_handle_tx`)
- [x] 연속 commit UTXO 충돌 방지 (`gacha/service.py`)
- [x] TUI Send 버튼 추가 (`tui/widgets/wallet.py`)
- [x] Exchange TX → Jackpot Pool 80% 적립 수정
- [x] 정수 연산 전환 (float ratio → int percent)
