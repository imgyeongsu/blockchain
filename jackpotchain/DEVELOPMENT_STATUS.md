# JackpotChain 개발 현황

> 최종 업데이트: 2024-02-26

---

## 1. 프로젝트 개요

**JackpotChain**은 가챠(복권) 시스템이 내장된 UTXO 기반 블록체인입니다.

### 핵심 특징
- **UTXO 모델**: Bitcoin 스타일의 미사용 출력 기반
- **듀얼 에셋**: JACK (기본 화폐) + POT (가챠 토큰)
- **Commit-Reveal 가챠**: 공정한 온체인 난수 생성
- **PoW 합의**: 15초 블록 타임

### 기술 스택
- Python 3.8+
- aiohttp (비동기 RPC)
- ecdsa (ECDSA 서명)
- pytest (테스트)

---

## 2. 구현 완료 모듈

### 2.1 Core Layer

| 모듈 | 파일 | 상태 | 설명 |
|------|------|:----:|------|
| **crypto** | hash.py | ✅ | SHA256, RIPEMD160, Double SHA256 |
| | signature.py | ✅ | ECDSA secp256k1 서명/검증 |
| | address.py | ✅ | Base58Check, 주소 생성 |
| | merkle.py | ✅ | Merkle Tree, SPV 증명 |
| **core** | transaction.py | ✅ | TxInput, TxOutput, Transaction |
| | block.py | ✅ | BlockHeader, Block, Genesis |
| | utxo.py | ✅ | UTXO, UTXOSet 관리 |
| **script** | opcodes.py | ✅ | Bitcoin 호환 OpCodes |
| | interpreter.py | ✅ | 스택 기반 VM |
| | standard.py | ✅ | P2PKH, OP_RETURN 템플릿 |

### 2.2 Consensus Layer

| 모듈 | 파일 | 상태 | 설명 |
|------|------|:----:|------|
| **consensus** | difficulty.py | ✅ | 난이도 조정 (50블록 주기) |
| | miner.py | ✅ | Coinbase TX, PoW 채굴 |
| | chain.py | ✅ | 체인 관리, Fork 처리 |
| **validation** | transaction.py | ✅ | TX 구조/서명/잔액 검증 |
| | block.py | ✅ | 블록 헤더/PoW/TX 검증 |

### 2.3 Application Layer

| 모듈 | 파일 | 상태 | 설명 |
|------|------|:----:|------|
| **asset** | manager.py | ✅ | JACK/POT 멀티에셋 |
| | exchange.py | ✅ | JACK→POT 교환 (100:1) |
| **gacha** | pool.py | ✅ | 잭팟 풀 (수수료 30% 누적) |
| | commit_reveal.py | ✅ | Commit-Reveal 난수 |
| | game.py | ✅ | 가챠 게임 로직 |

### 2.4 Network Layer

| 모듈 | 파일 | 상태 | 설명 |
|------|------|:----:|------|
| **network** | protocol.py | ✅ | P2P 메시지 타입 |
| | peer.py | ✅ | 피어 관리, Ban |
| | node.py | ✅ | 노드 로직, 메시지 처리 |
| **sync** | manager.py | ✅ | IBD, 헤더 동기화 |

### 2.5 Storage & Service Layer

| 모듈 | 파일 | 상태 | 설명 |
|------|------|:----:|------|
| **storage** | database.py | ✅ | 블록/TX 파일 저장 |
| **mempool** | pool.py | ✅ | 미확인 TX 풀 |
| **wallet** | wallet.py | ✅ | 키 관리, TX 서명 |
| **rpc** | server.py | ✅ | JSON-RPC API |
| **cli** | main.py | ✅ | CLI 엔트리포인트 |

---

## 3. 현재 실행 방법

### 3.1 설치

```bash
cd blockchain
python -m venv .venv
source .venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt
```

### 3.2 실행

```bash
# 도움말
python -m jackpotchain.cli.main --help

# 노드 실행
python -m jackpotchain.cli.main node --port 8333 --rpc-port 8332

# 지갑 생성
python -m jackpotchain.cli.main wallet create

# 채굴 (별도 터미널, 현재 노드와 미연동)
python -m jackpotchain.cli.main mine --address <주소>
```

### 3.3 RPC 테스트

```bash
# 블록체인 정보
curl -X POST http://127.0.0.1:8332 \
  -d '{"method":"getblockchaininfo","params":[],"id":1}'

# 사용 가능한 명령어
curl -X POST http://127.0.0.1:8332 \
  -d '{"method":"help","params":[],"id":1}'
```

---

## 4. 알려진 제한사항

### 4.1 현재 미연동 상태
- ❌ `mine` 명령어가 노드와 별도 블록체인 사용
- ❌ 채굴된 블록이 네트워크에 전파되지 않음

### 4.2 미구현 기능
- ❌ 블록 영구 저장 (메모리 전용)
- ❌ UTXO 스냅샷 저장/복원
- ❌ 피어 발견 (DNS Seeds)
- ❌ SPV 라이트 클라이언트
- ❌ 가챠 TX 검증 통합

### 4.3 테스트 부족
- ❌ 단위 테스트 미작성
- ❌ 통합 테스트 미작성
- ❌ 네트워크 시뮬레이션 미수행

---

## 5. 남은 작업 (TODO)

### 5.1 즉시 필요 (Priority: High)

#### 🔴 채굴-노드 통합
```
목표: node --mine --address <주소> 로 통합 실행
예상 작업량: 2-3시간
```

변경 사항:
1. `cli/main.py` - `--mine`, `--address` 플래그 추가
2. `run_node()` - 백그라운드 채굴 태스크 추가
3. 블록 발견 시 체인 추가 + 브로드캐스트

#### 🔴 블록 영구 저장
```
목표: 재시작 시 블록체인 복원
예상 작업량: 3-4시간
```

변경 사항:
1. `storage/database.py` - 이미 구현됨
2. `consensus/chain.py` - 시작 시 로드 로직 추가
3. 블록 추가 시 자동 저장

### 5.2 중요 기능 (Priority: Medium)

#### 🟡 테스트 코드 작성
```
목표: 핵심 모듈 80%+ 커버리지
예상 작업량: 1-2일
```

테스트 대상:
- `tests/test_crypto.py` - 해시, 서명, 주소
- `tests/test_transaction.py` - TX 생성/검증
- `tests/test_block.py` - 블록 생성/검증
- `tests/test_gacha.py` - Commit-Reveal 로직

#### 🟡 가챠 시스템 통합
```
목표: 실제 TX로 가챠 플레이 가능
예상 작업량: 4-5시간
```

변경 사항:
1. `validation/transaction.py` - Commit/Reveal TX 검증
2. `rpc/server.py` - 가챠 관련 RPC 추가
3. `cli/main.py` - gacha 서브커맨드 추가

#### 🟡 멀티 노드 테스트
```
목표: 로컬에서 3개 노드 동기화 확인
예상 작업량: 2-3시간
```

### 5.3 확장 기능 (Priority: Low)

#### 🟢 Dashboard UI
- 웹 기반 (Flask/FastAPI) 또는 TUI (Rich)
- 실시간 블록/TX 모니터링
- 지갑 잔액, 가챠 현황

#### 🟢 PyInstaller 패키징
```bash
# 목표
jackpotchain.exe node --mine --address <주소>
```

#### 🟢 Docker 지원
```yaml
# docker-compose.yml
services:
  node1:
    build: .
    command: node --mine --address JACK...
    ports:
      - "8333:8333"
      - "8332:8332"
```

---

## 6. 발전 방향

### Phase 1: MVP 완성 (1-2주)
- [x] 핵심 모듈 구현
- [ ] 채굴-노드 통합
- [ ] 블록 영구 저장
- [ ] 기본 테스트 작성
- [ ] 로컬 멀티노드 테스트

### Phase 2: 기능 완성 (2-3주)
- [ ] 가챠 시스템 전체 통합
- [ ] JACK↔POT 교환 테스트
- [ ] 잭팟 당첨 시나리오 검증
- [ ] 난이도 조정 검증
- [ ] 재조직(Reorg) 테스트

### Phase 3: 사용성 개선 (2-3주)
- [ ] Dashboard UI
- [ ] 지갑 암호화
- [ ] 트랜잭션 히스토리
- [ ] 블록 탐색기 (웹)
- [ ] PyInstaller 패키징

### Phase 4: 네트워크 확장 (선택)
- [ ] 외부 노드 연결 (AWS)
- [ ] NAT Traversal
- [ ] 피어 발견 자동화
- [ ] 성능 최적화

---

## 7. 파일 구조

```
jackpotchain/
├── __init__.py          # 패키지 메인
├── constants.py         # 전역 상수
├── setup.py             # 패키지 설정
├── requirements.txt     # 의존성
│
├── crypto/              # 암호학
│   ├── hash.py
│   ├── signature.py
│   ├── address.py
│   └── merkle.py
│
├── core/                # 핵심 자료구조
│   ├── transaction.py
│   ├── block.py
│   └── utxo.py
│
├── script/              # 스크립트 VM
│   ├── opcodes.py
│   ├── interpreter.py
│   └── standard.py
│
├── consensus/           # 합의
│   ├── difficulty.py
│   ├── miner.py
│   └── chain.py
│
├── validation/          # 검증
│   ├── transaction.py
│   └── block.py
│
├── asset/               # 에셋 관리
│   ├── manager.py
│   └── exchange.py
│
├── gacha/               # 가챠 시스템
│   ├── pool.py
│   ├── commit_reveal.py
│   └── game.py
│
├── network/             # P2P 네트워크
│   ├── protocol.py
│   ├── peer.py
│   └── node.py
│
├── sync/                # 동기화
│   └── manager.py
│
├── storage/             # 저장소
│   └── database.py
│
├── mempool/             # 메모리풀
│   └── pool.py
│
├── wallet/              # 지갑
│   └── wallet.py
│
├── rpc/                 # RPC API
│   └── server.py
│
├── cli/                 # CLI
│   └── main.py
│
├── dashboard/           # (미구현)
├── scripts/             # 유틸리티 스크립트
└── tests/               # 테스트
```

---

## 8. 참고 자료

### 학습 로드맵
- `learning-roadmap/` 디렉토리 참조

### 구현 명세서
- `IMPLEMENTATION_SPEC.md` 참조

### 외부 자료
- Bitcoin Developer Guide
- Mastering Bitcoin (O'Reilly)
- Bitcoin Core 소스코드

---

## 9. 기여 가이드

### 코드 스타일
- Python PEP8 준수
- Type Hints 사용
- Docstring 필수

### 커밋 메시지
```
feat: 새 기능
fix: 버그 수정
docs: 문서
test: 테스트
refactor: 리팩토링
```

### PR 체크리스트
- [ ] 테스트 통과
- [ ] 문서 업데이트
- [ ] 코드 리뷰

---

*이 문서는 개발 진행에 따라 업데이트됩니다.*
