# JackpotChain TODO

> 최종 업데이트: 2026-03-19

## 배포

- [ ] **AWS 시드노드 코드 업데이트**
  - 자동 지급 방식 반영
  - 테스트 필요

## 개선 (Medium)

- [ ] **PONG RTT 계산 구현**
  - 위치: `network/node.py:340`
  - ADVANCE.md로 이관

- [ ] **UTXO 예약 ↔ mempool 동기화**
  - 위치: `gacha/service.py`
  - mempool 제거 시 UTXO 예약 자동 해제

## 향후 개선

> 상세: [ADVANCE.md](ADVANCE.md)

- [ ] Lotto Payout 블록 검증 (채굴자 조작 방지)
- [ ] Go/Rust 리라이트
- [ ] 모니터링 (Prometheus/Grafana)
- [ ] 웹 대시보드

---

## 완료

### 2026-03-19
- [x] Claim TX 제거 → 채굴자 자동 지급 방식 전환
- [x] TUI Claims 탭 → History(당첨이력) 탭 교체
- [x] RPC _mining_loop blockchain 파라미터 누락 수정

### 2026-03-20 (긴급 버그 수정 5건)
- [x] miner.py height 버그 수정 (timestamp → height 파라미터화)
- [x] wallet.py 개인키 AES-256-GCM 암호화 구현
- [x] _block_buffer, _pending_blocks 크기 제한 추가
- [x] sync/manager.py 헤더 검증 파라미터 추가
- [x] pool_snapshot 동적 조회 (1등 상금 검증)

### 2026-03-18
- [x] TX 전파 버그 수정 (`network/node.py:_handle_tx`)
- [x] 연속 commit UTXO 충돌 방지 (`gacha/service.py`)
- [x] TUI Send 버튼 추가
- [x] Exchange TX → Jackpot Pool 80% 적립 수정
- [x] 정수 연산 전환 (float ratio → int percent)
- [x] Claim payout 유효성 → 자동 지급으로 대체됨
- [x] LOTTO_CLAIM 검증 → Claim 제거로 불필요
