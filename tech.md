# JackpotChain 기술 스택

## 개요
JackpotChain은 Python 기반의 블록체인 구현체로, 로또 시스템을 내장한 Layer 1 체인입니다.

---

## 언어 및 런타임

| 구분 | 기술 | 버전 | 용도 |
|------|------|------|------|
| Language | Python | 3.12+ | 메인 개발 언어 |
| Runtime | CPython | 3.12 | 표준 인터프리터 |

---

## 핵심 라이브러리

### 암호화 (Cryptography)
| 라이브러리 | 용도 |
|-----------|------|
| `ecdsa` | ECDSA 서명 (secp256k1) |
| `hashlib` (내장) | SHA256 해싱 |

### 네트워크 (Networking)
| 라이브러리 | 용도 |
|-----------|------|
| `asyncio` (내장) | 비동기 P2P 통신 |
| `aiohttp` | HTTP RPC 서버 |
| `socket` (내장) | DNS 시드 조회 |

### 데이터 처리
| 라이브러리 | 용도 |
|-----------|------|
| `struct` (내장) | 바이너리 직렬화/역직렬화 |
| `json` (내장) | 설정 파일, 피어 캐시 |
| `dataclasses` (내장) | 데이터 구조 정의 |

### 테스트
| 라이브러리 | 용도 |
|-----------|------|
| `pytest` | 단위 테스트 |
| `pytest-asyncio` | 비동기 테스트 |

### 기타
| 라이브러리 | 용도 |
|-----------|------|
| `colorama` | 터미널 컬러 출력 |
| `Pygments` | 구문 강조 |

---

## 모듈 구조

```
jackpotchain/
├── core/           # 핵심 자료구조
│   ├── block.py        # Block, BlockHeader
│   ├── transaction.py  # Transaction, TxInput, TxOutput
│   └── utxo.py         # UTXO Set
│
├── crypto/         # 암호화
│   ├── hash.py         # SHA256, Double SHA256
│   ├── merkle.py       # Merkle Tree
│   └── address.py      # 주소 생성/검증 (Base58Check)
│
├── script/         # 스크립트 엔진
│   ├── opcodes.py      # OP 코드 정의
│   ├── interpreter.py  # 스크립트 실행기
│   └── standard.py     # P2PKH, Commit, Claim 스크립트
│
├── consensus/      # 합의
│   ├── chain.py        # Blockchain (체인 관리)
│   ├── difficulty.py   # 난이도 조절
│   └── miner.py        # PoW 채굴
│
├── validation/     # 검증
│   ├── block.py        # 블록 검증
│   └── transaction.py  # 트랜잭션 검증
│
├── network/        # P2P 네트워크
│   ├── protocol.py     # 메시지 정의 (VERSION, INV, BLOCK, ADDR 등)
│   ├── peer.py         # 피어 관리
│   ├── node.py         # P2P 노드
│   └── discovery.py    # 피어 발견 (DNS 시드, 캐시)
│
├── gacha/          # 로또 시스템
│   ├── commit_reveal.py  # Commit-Reveal 로직
│   ├── pool.py           # 잭팟 풀 관리
│   ├── game.py           # 로또 게임 로직
│   └── service.py        # 서비스 레이어
│
├── asset/          # 자산 관리
│   ├── manager.py      # JACK/POT 자산 관리
│   └── exchange.py     # JACK → POT 교환
│
├── mempool/        # 메모리 풀
│   └── pool.py         # 미확인 TX 관리
│
├── storage/        # 저장소
│   └── database.py     # 블록/UTXO 저장
│
├── wallet/         # 지갑
│   └── wallet.py       # 키 관리, TX 생성
│
├── rpc/            # RPC 서버
│   └── server.py       # JSON-RPC API
│
├── cli/            # CLI
│   └── main.py         # 명령줄 인터페이스
│
└── scripts/        # 유틸리티
    └── test_multinode.py  # 멀티노드 테스트
```

---

## 프로토콜 스택

### P2P 메시지 타입
| 메시지 | 용도 |
|--------|------|
| `VERSION` / `VERACK` | 핸드셰이크 |
| `INV` / `GETDATA` | 인벤토리 교환 |
| `BLOCK` / `TX` | 데이터 전송 |
| `GETBLOCKS` / `GETHEADERS` | 동기화 |
| `ADDR` / `GETADDR` | 피어 발견 |
| `PING` / `PONG` | 연결 유지 |

### 트랜잭션 버전
| 버전 | 용도 |
|------|------|
| v1 | 일반 전송 |
| v2 | JACK → POT 교환 |
| v3 | 로또 Commit |
| v5 | 로또 Claim |

---

## 합의 알고리즘

| 항목 | 값 |
|------|-----|
| 알고리즘 | Proof of Work (PoW) |
| 해시 함수 | SHA256d |
| 블록 시간 | 15초 목표 |
| 난이도 조절 | 50블록마다 |

---

## 향후 기술 (계획)

| 기술 | 용도 | 상태 |
|------|------|------|
| LevelDB / RocksDB | 고성능 저장소 | 계획 |
| WebSocket | 실시간 이벤트 | 계획 |
| Prometheus | 모니터링 | 계획 |
| Docker | 컨테이너 배포 | 계획 |

---

## 의존성 (requirements.txt)

```
aiohttp==3.13.3      # RPC 서버
ecdsa==0.19.1        # ECDSA 서명
pytest==9.0.2        # 테스트
pytest-asyncio==1.3.0
colorama==0.4.6      # 터미널 출력
Pygments==2.19.2     # 구문 강조
```

---

## 실행 환경

```bash
# 가상환경 생성
python -m venv .venv

# 의존성 설치
pip install -r requirements.txt

# 테스트 실행
pytest jackpotchain/tests/ -v

# 멀티노드 테스트
python -m scripts.test_multinode node1
```
