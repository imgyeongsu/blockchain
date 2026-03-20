# JackpotChain 노드 실행 가이드

## AWS 시드 노드
- **IP**: `54.116.13.57:9777`
- **상태**: 상시 운영 중

---

## 로컬 노드 실행

### 1. 기본 실행 (채굴 포함)
```bash
# 가상환경 활성화
source jackpotchain/.venv/bin/activate  # Linux/Mac
# 또는
jackpotchain/.venv/Scripts/activate  # Windows

# 노드 실행
python -m jackpotchain.cli.main node \
  --mine \
  --address <지갑주소> \
  --port 9778 \
  --rpc-port 9779 \
  --data-dir ./data \
  --seed 54.116.13.57:9777
```

### 2. 시드 노드 전용 (채굴 없이)
```bash
python -m jackpotchain.cli.main node \
  --seed-node \
  --port 9777 \
  --rpc-port 9776 \
  --data-dir ./data
```

### 3. 백그라운드 실행 (Linux)
```bash
nohup python -m jackpotchain.cli.main node \
  --seed-node \
  --port 9777 \
  --rpc-port 9776 \
  --data-dir ./data > node.log 2>&1 &
```

---

## 지갑 관리

### 지갑 생성
```bash
python -m jackpotchain.cli.main wallet create
```

### 지갑 주소 확인
```bash
python -m jackpotchain.cli.main wallet address
```

---

## RPC 명령어

### 블록체인 정보
```bash
curl -X POST http://127.0.0.1:9779 \
  -d '{"method":"getblockchaininfo","params":[],"id":1}'
```

### 피어 정보
```bash
curl -X POST http://127.0.0.1:9779 \
  -d '{"method":"getpeerinfo","params":[],"id":1}'
```

### 잔액 확인
```bash
curl -X POST http://127.0.0.1:9779 \
  -d '{"method":"getbalance","params":["<주소>"],"id":1}'
```

### 특정 높이 블록 해시
```bash
curl -X POST http://127.0.0.1:9779 \
  -d '{"method":"getblockhash","params":[100],"id":1}'
```

---

## CLI 옵션 설명

| 옵션 | 설명 |
|------|------|
| `--mine` | 채굴 활성화 |
| `--address` | 채굴 보상 받을 지갑 주소 |
| `--port` | P2P 포트 (기본: 9777) |
| `--rpc-port` | RPC 포트 (기본: 9776) |
| `--data-dir` | 블록체인 데이터 저장 경로 |
| `--seed` | 연결할 시드 노드 (ip:port) |
| `--seed-node` | 시드 노드로 실행 |

---

## 테스트 시나리오

### 로컬 2노드 경쟁 채굴
```bash
# 터미널 1 - Node1
python -m jackpotchain.cli.main node \
  --mine --address <주소1> \
  --port 9778 --rpc-port 9779 \
  --data-dir ./data \
  --seed 54.116.13.57:9777

# 터미널 2 - Node2
python -m jackpotchain.cli.main node \
  --mine --address <주소2> \
  --port 9780 --rpc-port 9781 \
  --data-dir ./data2 \
  --seed 127.0.0.1:9778
```

### 합의 확인
```bash
# 두 노드의 같은 높이 블록 해시 비교
curl -s http://127.0.0.1:9779 -d '{"method":"getblockhash","params":[100],"id":1}'
curl -s http://127.0.0.1:9781 -d '{"method":"getblockhash","params":[100],"id":1}'
```

---

## 테스트된 지갑 주소

| 용도 | 주소 |
|------|------|
| 로컬 테스트 1 | `X4Eq8y3Xn6esGzU2yvYAcTthQwhb8dFiCy` |
| 로컬 테스트 2 | `WsQdsBg45NzVXNxjHvdH5i2x8hNSSptHWK` |
| AWS 시드 | `X4Nqvw2Y3Yx5BNsgmj8XRpe8xe7DUnd2Hv` |

---

## 문제 해결

### 동기화 안 됨
1. 피어 연결 확인: `getpeerinfo`
2. 시드 노드 IP/포트 확인
3. 방화벽 설정 확인

### 블록 높이가 안 올라감
1. 채굴 주소 설정 확인 (`--address`)
2. 난이도 확인 (너무 높으면 시간 오래 걸림)

### 두 노드 체인이 다름
1. 같은 제네시스 블록인지 확인
2. 피어 연결 확인
3. data 폴더 삭제 후 재동기화
