# JackpotChain

UTXO 기반 블록체인 + 온체인 가챠(복권) 시스템

## 특징

- **UTXO 모델**: Bitcoin 스타일 미사용 출력 기반
- **듀얼 에셋**: JACK (기본 화폐) + POT (가챠 토큰)
- **Commit-Reveal 가챠**: 공정한 온체인 난수 생성 (1% 당첨)
- **PoW 합의**: ~10초 블록 타임 (테스트넷)

---

## 설치

```bash
# 1. 가상환경 생성
cd blockchain
python -m venv .venv

# 2. 활성화
# Windows (Git Bash)
source .venv/Scripts/activate
# Windows (CMD)
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# 3. 의존성 설치
pip install -r requirements.txt
```

---

## 실행

### 노드 + 채굴 (권장)

```bash
# 지갑 생성 (최초 1회)
python -m jackpotchain.cli.main wallet create

# 노드 실행 + 채굴
python -m jackpotchain.cli.main node --mine --address <주소> --data-dir ./data

# 예시
python -m jackpotchain.cli.main node --mine --address WqUDneonGfCqgxqg28oKdUR5Z9ofieTtms --data-dir ./data
```

### 노드만 실행 (채굴 없음)

```bash
python -m jackpotchain.cli.main node --port 8333 --rpc-port 8332 --data-dir ./data
```

### 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--port` | P2P 포트 | 8333 |
| `--rpc-port` | RPC 포트 | 8332 |
| `--data-dir` | 데이터 저장 경로 | ./data |
| `--mine` | 채굴 활성화 | - |
| `--address` | 채굴 보상 주소 | - |
| `--seed` | 시드 노드 (ip:port) | - |

---

## 지갑 명령어

```bash
# 새 주소 생성
python -m jackpotchain.cli.main wallet create

# 주소 목록
python -m jackpotchain.cli.main wallet address

# 잔액 조회 (RPC 필요)
python -m jackpotchain.cli.main wallet balance
```

---

## RPC API

노드 실행 중 `http://127.0.0.1:8332`로 JSON-RPC 호출

### 블록체인 정보

```bash
# 체인 정보
curl -X POST http://127.0.0.1:8332 -d '{"method":"getblockchaininfo","params":[],"id":1}'

# 블록 조회
curl -X POST http://127.0.0.1:8332 -d '{"method":"getblock","params":["<blockhash>"],"id":1}'

# 높이로 블록해시 조회
curl -X POST http://127.0.0.1:8332 -d '{"method":"getblockhash","params":[0],"id":1}'
```

### 지갑

```bash
# 잔액 조회
curl -X POST http://127.0.0.1:8332 -d '{"method":"getbalance","params":[],"id":1}'

# UTXO 목록
curl -X POST http://127.0.0.1:8332 -d '{"method":"listunspent","params":[],"id":1}'

# 새 주소 생성
curl -X POST http://127.0.0.1:8332 -d '{"method":"getnewaddress","params":[],"id":1}'

# 송금
curl -X POST http://127.0.0.1:8332 -d '{"method":"sendtoaddress","params":["<address>", 10.0],"id":1}'
```

### 가챠 시스템

```bash
# 가챠 정보
curl -X POST http://127.0.0.1:8332 -d '{"method":"getgachainfo","params":[],"id":1}'

# 잭팟 풀 현황
curl -X POST http://127.0.0.1:8332 -d '{"method":"getjackpotpool","params":[],"id":1}'
```

### 네트워크

```bash
# 피어 정보
curl -X POST http://127.0.0.1:8332 -d '{"method":"getpeerinfo","params":[],"id":1}'

# 멤풀 상태
curl -X POST http://127.0.0.1:8332 -d '{"method":"getmempoolinfo","params":[],"id":1}'
```

### 전체 명령어

```bash
curl -X POST http://127.0.0.1:8332 -d '{"method":"help","params":[],"id":1}'
```

---

## 테스트

```bash
# 전체 테스트
pytest jackpotchain/tests/ -v

# 모듈별 테스트
pytest jackpotchain/tests/test_crypto.py -v
pytest jackpotchain/tests/test_core.py -v
pytest jackpotchain/tests/test_gacha.py -v
pytest jackpotchain/tests/test_network.py -v
```

---

## 프로젝트 구조

```
blockchain/
├── jackpotchain/
│   ├── crypto/          # 암호학 (해시, 서명, 주소)
│   ├── core/            # 핵심 (TX, Block, UTXO)
│   ├── script/          # 스크립트 VM
│   ├── consensus/       # 합의 (난이도, 채굴, 체인)
│   ├── validation/      # 검증
│   ├── asset/           # 에셋 관리 (JACK/POT)
│   ├── gacha/           # 가챠 시스템
│   ├── network/         # P2P 네트워크
│   ├── storage/         # 블록 저장
│   ├── mempool/         # 미확인 TX 풀
│   ├── wallet/          # 지갑
│   ├── rpc/             # JSON-RPC 서버
│   ├── cli/             # CLI
│   └── tests/           # 테스트 (82개)
├── learning-roadmap/    # 학습 자료
├── requirements.txt
└── README.md
```

---

## 설정값

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| 블록 타임 | 15초 | 목표 블록 간격 |
| 블록 보상 | 50 JACK | 채굴 보상 |
| 난이도 조정 | 50블록 | 조정 주기 |
| 가챠 비용 | 1 POT | 1회 플레이 |
| 당첨 확률 | 1% | 100슬롯 중 1개 |
| 잭팟 지급 | 60% | 풀의 60% 지급 |

---

## 상세 문서

- [개발 현황](jackpotchain/DEVELOPMENT_STATUS.md)
- [구현 명세](learning-roadmap/IMPLEMENTATION_SPEC.md)
- [학습 로드맵](learning-roadmap/README.md)
