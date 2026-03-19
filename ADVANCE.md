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

### 헤더 전용 검증 (Headers-First Sync)
- 현재 블록 전체를 받아서 검증
- 헤더만 먼저 검증 후 블록 바디 요청하는 방식으로 변경

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
