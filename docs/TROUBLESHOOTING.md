# JackpotChain 트러블슈팅 가이드

## 현재 상황 (2026-03-12)

### 완료된 작업

1. **AWS 시드 노드 설정**
   - IP: `54.116.13.57:9333`
   - 상태: 정상 동작 중 (140+ 블록)
   - 실행 명령어:
     ```bash
     nohup python3 -m jackpotchain.cli.main node --seed-node --port 9333 --rpc-port 9332 --data-dir ./data > node.log 2>&1 &
     ```

2. **제네시스 블록 하드코딩**
   - 모든 노드가 동일한 제네시스 블록 사용하도록 수정
   - 파일: `constants.py`, `core/block.py`
   - 제네시스 해시: `c41d65b3c0b76dea7142202a37f5b10f8275aba8370387636e35640e30c7a0d9`

3. **시드 노드 설정**
   - 파일: `network/discovery.py`
   - AWS 시드: `("54.116.13.57", 9333)`

4. **디버깅 로그 추가**
   - `[SYNC]` - 동기화 관련 로그
   - `[CHAIN]` - 블록 추가 관련 로그

---

## 미해결 이슈

### 동기화 중단 문제

**증상:**
- 로컬 노드가 AWS 시드에 연결됨 (피어로 잡힘)
- 11블록까지 동기화 후 멈춤
- AWS 시드는 140블록 보유

**예상 원인:**
1. IBD 로직에서 GETBLOCKS 요청 후 응답 처리 문제
2. INV 메시지 수신 후 GETDATA 요청 누락
3. BLOCK 수신 후 체인 추가 실패

**디버깅 방법:**
```bash
# 로컬 노드 실행 (로그 확인)
python -m jackpotchain.cli.main node --mine --address <주소> --port 9334 --rpc-port 9335 --data-dir ./data --seed 54.116.13.57:9333

# 로그에서 확인할 것:
# 1. [SYNC] IBD 시작 → 나오는지?
# 2. [SYNC] GETBLOCKS 요청 → 나오는지?
# 3. [SYNC] INV 수신 → 나오는지?
# 4. [SYNC] GETDATA 요청 → 나오는지?
# 5. [SYNC] BLOCK 수신 → 나오는지?
# 6. [CHAIN] 블록 추가 성공/실패 → 어떤 메시지?
```

---

## 주요 RPC 명령어

```bash
# 블록체인 정보
curl -X POST http://127.0.0.1:9335 -d '{"method":"getblockchaininfo","params":[],"id":1}'

# 피어 정보
curl -X POST http://127.0.0.1:9335 -d '{"method":"getpeerinfo","params":[],"id":1}'

# 잔액 확인
curl -X POST http://127.0.0.1:9335 -d '{"method":"getbalance","params":["<주소>"],"id":1}'
```

---

## 지갑 주소

| 용도 | 주소 |
|------|------|
| 로컬 테스트 1 | `X4Eq8y3Xn6esGzU2yvYAcTthQwhb8dFiCy` |
| 로컬 테스트 2 | `WsQdsBg45NzVXNxjHvdH5i2x8hNSSptHWK` |
| AWS 시드 | `X4Nqvw2Y3Yx5BNsgmj8XRpe8xe7DUnd2Hv` |

---

## 다음 단계

1. **로그 분석**
   - AWS와 로컬 양쪽에서 `[SYNC]`, `[CHAIN]` 로그 확인
   - 어디서 흐름이 끊기는지 파악

2. **예상 수정 위치**
   - `network/node.py` - 메시지 핸들링
   - `consensus/chain.py` - 블록 검증/추가
   - `sync/manager.py` - 동기화 상태 관리

3. **테스트 시나리오**
   - AWS 시드 재시작 후 로컬 연결
   - 로그 확인하여 병목 지점 파악
   - 수정 후 재테스트

---

## 로그 태그 설명

| 태그 | 위치 | 설명 |
|------|------|------|
| `[SYNC] IBD 시작` | node.py | 핸드셰이크 완료 후 동기화 시작 |
| `[SYNC] GETBLOCKS 요청` | node.py | 블록 로케이터로 블록 요청 |
| `[SYNC] GETBLOCKS 수신` | node.py | 피어로부터 GETBLOCKS 수신 |
| `[SYNC] INV 응답` | node.py | 블록 해시 목록 전송 |
| `[SYNC] INV 수신` | node.py | 블록/TX 알림 수신 |
| `[SYNC] GETDATA 요청` | node.py | 블록/TX 데이터 요청 |
| `[SYNC] BLOCK 수신` | node.py | 블록 데이터 수신 |
| `[CHAIN] 블록 추가 성공` | chain.py | 메인 체인에 블록 추가됨 |
| `[CHAIN] 블록 추가 실패` | chain.py | 블록 추가 실패 (이유 표시) |

---

## 커밋 히스토리

```
0caa395 feat: 제네시스 블록 하드코딩 및 AWS 시드 노드 추가
```

---

## 참고 파일

- `jackpotchain/network/node.py` - P2P 노드, 메시지 핸들링
- `jackpotchain/network/protocol.py` - 메시지 타입 정의
- `jackpotchain/consensus/chain.py` - 블록체인, 블록 추가
- `jackpotchain/sync/manager.py` - 동기화 관리
- `jackpotchain/network/discovery.py` - 피어 발견, 시드 노드
