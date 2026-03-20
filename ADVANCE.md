# JackpotChain 향후 개선 사항

> 우선순위 낮음 — 현재 배포 환경에서는 긴급하지 않은 항목들

## 합의 규칙 강화

### Lotto Payout 블록 검증
- **문제**: 채굴자가 payout TX를 누락/조작해도 다른 노드가 거부하지 못함
- **공격 벡터**:
  1. payout TX 누락 → 당첨자에게 미지급
  2. 금액 조작 → 풀에서 과다/과소 지급
  3. 주소 변조 → 채굴자가 당첨금 가로챔
- **해결**: `add_block()` 시 payout 검증 추가
  ```python
  def validate_lotto_payouts(block, height, blockchain):
      # 1. H-18 블록의 커밋 목록 조회
      # 2. 독립적으로 당첨 결과 계산
      # 3. 블록 내 payout TX와 비교
      # 4. 불일치 시 블록 거부
  ```
- **참고**: Bitcoin의 coinbase 보상 초과 블록 거부와 동일한 원리

### Headers-First IBD (Initial Block Download)
- **현재**: GETBLOCKS → INV → GETDATA 순차 동기화 (+ watchdog 재시도)
- **목표**: 헤더 PoW 먼저 검증 → 검증된 블록만 본문 다운로드
- **시도 결과 (2026-03-20)**:
  - SyncManager 구현 (IDLE→HEADERS→BLOCKS→SYNCED 상태머신)
  - 헤더 PoW 검증 동작 확인
  - 블록 다운로드 단계에서 문제 발생:
    1. 배치 16개 동시 요청 시 일부 유실 → `_downloading` 잔류로 stall
    2. 블록 순서 보장 필요 (버퍼링 복잡도 증가)
    3. 기존 coinbase height 버그 블록과 validate_block 충돌
  - **결론**: 블록 다운로드를 파이프라인 방식(1개씩 순차 + 다음 미리 요청)으로 재설계 필요
- **참고**: Bitcoin Core는 헤더 체인 먼저 구축 후 블록을 여러 피어에서 병렬 다운로드

---

## 블록 동기화 속도 개선 이력 (2026-03-20)

### v1: 순차 배치 (제한 없음) — `set` 버전
```
_requesting: set, batch_size: 16, watchdog: 없음
```
- **동작**: 블록 1개 도착 → `_request_next_block()` → 16개 추가 요청
- **문제**: 블록 7개 수신 후 `_requesting`에 360개 누적 (snowball)
  - 매 블록 도착마다 16개씩 새로 요청 → 피어에 요청 폭탄
  - TCP 버퍼 포화 → 유실 → stall → 영원히 멈춤 (watchdog 없음)
- **결과**: 운 좋으면 빠르고, 운 나쁘면 멈춤. 복구 불가.

### v2: set + watchdog
```
_requesting: set, batch_size: 16, watchdog: 10초 간격/10초 타임아웃
```
- **개선**: stall 시 watchdog이 `_requesting` 전체 clear → 재요청
- **문제**: snowball은 여전. 멈출 때마다 최대 20초 대기 (10s sleep + 10s threshold)
- **결과**: 멈춰도 복구는 되지만, 1368블록에 stall 반복 → 하루종일 걸림

### v3: Dict + per-block timeout + in-flight 제한
```
_requesting: Dict[hash, time], batch_size: 16, in-flight 제한: batch_size개
```
- **개선**: 개별 블록 타임아웃 (5초), in-flight 16개 제한으로 snowball 방지
- **문제**: in-flight 제한 + 유실 → 빈 슬롯 1개씩만 열림 → 사실상 순차 (1개씩)
  - GETDATA 요청: 1개 블록 반복 → set 버전보다 오히려 느림
- **결과**: 안정적이지만 느림. 브랜치 `sync-dict-inflight`에 보존.

### v4: High/Low Watermark (현재) ← 채택
```
_requesting: set, batch_size: 16 (high), low_watermark: 4, watchdog: 5초
```
- **핵심**: in-flight가 **4 이하**로 떨어져야 **16까지 한번에 채움**
  - 블록 12개 도착 (in-flight 4) → 12개 한번에 추가 요청 → in-flight 16 복귀
  - 블록 1개 도착 (in-flight 15) → 추가 요청 안 함 (low watermark 이상)
- **장점**:
  1. snowball 방지 (절대 16 초과 안 함)
  2. 배치 효율 유지 (GETDATA 1번에 12개씩)
  3. 불필요한 요청 제거 (매 블록마다 요청 X)
  4. watchdog 5초로 stall 빠른 복구
- **10,000블록 예상**: 안정적 + 빠름
  - 최적: 16블록/RTT → 10,000 / 16 * 0.2s ≈ 2분
  - stall 포함: watchdog 5초 * stall 횟수 추가

## 네트워크

### Mempool 동기화 (연결 시)
- **현재**: 노드 재시작 시 로컬 mempool 초기화, 피어 mempool 수신 안 함
- **증상**: 내가 보낸 TX가 피어 mempool에는 있지만 내 UI에서 안 보임
- **동작상 문제 없음**: 피어가 갖고 있으면 결국 블록에 포함됨
- **Bitcoin도 기본 동기화 안 함** — 필요 시 `sendmempool` 메시지 사용
- **우선순위 낮음**: UX 혼란 정도, 실제 TX 처리에 영향 없음
- **해결 (선택)**: VERACK 후 INV로 mempool txid 교환

### PONG RTT 계산
- 위치: `network/node.py:340`
- PING/PONG 왕복 시간으로 피어 품질 측정

### 피어 밴 로직
- 악의적 피어 자동 차단 (잘못된 블록/TX 전송 시)

## 성능

### UTXO 예약 ↔ Mempool 동기화
- mempool에서 TX 제거 시 UTXO 예약 자동 해제

### 디버그 로그 정리
- `mempool/pool.py`, `rpc/server.py` 등 디버그 print 정리

## 미래

### Go/Rust 리라이트
- Python 프로토타입 → 성능 중심 언어로 전환

### 모니터링
- Prometheus + Grafana 대시보드

### 웹 대시보드
- 블록 탐색기 웹 UI
