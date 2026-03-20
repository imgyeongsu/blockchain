# JackpotChain 3일 스프린트 일정표

> 5명이 3일간 집중 개발하는 스케줄

---

## 역할 분담

| 역할 | 담당자 | 담당 모듈 | 예상 라인 |
|:----:|:------:|----------|:---------:|
| **A** (Core) | **임경수** | 상수, 암호화, 자료구조 | ~1,200 |
| **B** (Consensus) | **양한빈** | 합의, 검증 | ~1,100 |
| **C** (Network) | **이동휘** | P2P 네트워크 | ~3,400 |
| **D** (Application) | **이민수** | 로또, 지갑, 스크립트 | ~2,800 |
| **E** (Infra) | **장주윤** | CLI, RPC, 저장소, 테스트 | ~1,500 |

---

## Day 1: 기반 구축

### 오전 (09:00 ~ 12:00)

| 담당 | 담당자 | 작업 내용 | 파일 |
|:----:|:------:|----------|------|
| A | 임경수 | 상수 정의 + 해시/서명 | `constants.py`, `crypto/hash.py`, `crypto/signature.py` |
| B | 양한빈 | 난이도 조정 알고리즘 | `consensus/difficulty.py` |
| C | 이동휘 | 피어 구조체 + 프로토콜 메시지 | `network/peer.py`, `network/protocol.py` |
| D | 이민수 |스크립트 opcode + 표준 스크립트 | `script/opcodes.py`, `script/standard.py` |
| E | 장주윤 | 프로젝트 셋업 + DB | `__init__.py`, `setup.py`, `storage/database.py` |

### 오후 (13:00 ~ 18:00)

| 담당 | 담당자 | 작업 내용 | 파일 |
|:----:|:------:|----------|------|
| A | 임경수 | 주소 생성 + 머클트리 + 트랜잭션 | `crypto/address.py`, `crypto/merkle.py`, `core/transaction.py` |
| B | 양한빈 | 채굴기 구현 | `consensus/miner.py` |
| C | 이동휘 | 피어 발견 (DNS/하드코딩) | `network/discovery.py` |
| D | 이민수 |스크립트 인터프리터 + 지갑 | `script/interpreter.py`, `wallet/wallet.py` |
| E | 장주윤 | 멤풀 구현 | `mempool/pool.py` |

---

## Day 2: 핵심 로직

### 오전 (09:00 ~ 12:00)

| 담당 | 담당자 | 작업 내용 | 파일 |
|:----:|:------:|----------|------|
| A | 임경수 | 블록 구조체 + UTXO | `core/block.py`, `core/utxo.py` |
| B | 양한빈 | TX 검증 + 블록 검증 | `validation/transaction.py`, `validation/block.py` |
| C | 이동휘 | NAT Traversal (PCP/NAT-PMP/UPnP) | `network/nat.py` |
| D | 이민수 |자산 관리 + 교환 | `asset/manager.py`, `asset/exchange.py` |
| E | 장주윤 | RPC 서버 (절반) | `rpc/server.py` (1/2) |

### 오후 (13:00 ~ 18:00)

| 담당 | 담당자 | 작업 내용 | 파일 |
|:----:|:------:|----------|------|
| A | 임경수 | 코드 리뷰 + 버그 수정 | - |
| B | 양한빈 | 블록체인 + Reorg 처리 | `consensus/chain.py` |
| C | 이동휘 | P2P 노드 (메시지 핸들링) | `network/node.py` |
| D | 이민수 |Commit-Reveal + 잭팟 풀 | `gacha/commit_reveal.py`, `gacha/pool.py` |
| E | 장주윤 | RPC 서버 (완료) + CLI (절반) | `rpc/server.py` (2/2), `cli/main.py` (1/2) |

---

## Day 3: 고급 기능 + 통합

### 오전 (09:00 ~ 12:00)

| 담당 | 담당자 | 작업 내용 | 파일 |
|:----:|:------:|----------|------|
| A | 임경수 | README + 기술 문서 | `README.md`, `tech.md` |
| B | 양한빈 | 합의 문서화 | 문서 작업 |
| C | 이동휘 | TCP 홀펀칭 + 동기화 매니저 | `network/holepunch.py`, `sync/manager.py` |
| D | 이민수 |로또 게임 로직 | `gacha/game.py` |
| E | 장주윤 | CLI 완료 + 단위 테스트 | `cli/main.py` (2/2), `tests/test_core.py` |

### 오후 (13:00 ~ 18:00)

| 담당 | 담당자 | 작업 내용 | 파일 |
|:----:|:------:|----------|------|
| A | 임경수 | 통합 테스트 지원 | - |
| B | 양한빈 | 통합 테스트 지원 | - |
| C | 이동휘 | 멀티노드 네트워크 테스트 | `scripts/test_multinode.py` |
| D | 이민수 |로또 서비스 (전체 흐름) | `gacha/service.py` |
| E | 장주윤 | 전체 테스트 + 배포 준비 | `tests/*`, Docker |

---

# 파일별 상세 지시서

## A (Core) 담당 파일

---

### `constants.py`
**구현 내용:**
- 네트워크 파라미터 (MAGIC, PORT)
- 블록 파라미터 (BLOCK_TIME=30초, 난이도 조정 주기=50블록)
- 보상/수수료 상수
- 로또 파라미터 (참가비, 등수별 보상, Claim 윈도우)
- TX 버전 상수

**커밋 메시지:**
```
feat: [core] 전역 상수 정의

- 네트워크: MAGIC, PORT 8333/8332
- 블록: 30초 타임, 50블록 난이도 조정
- 로또: 6자리 hex, N+5~N+30 비교 블록
- 보상: 50 JACK 블록보상, 수수료 분배율
```

---

### `crypto/hash.py`
**구현 내용:**
- `sha256(data)` - 단일 SHA256
- `double_sha256(data)` - SHA256d (비트코인 방식)
- `hash160(data)` - RIPEMD160(SHA256(data))

**커밋 메시지:**
```
feat: [crypto] 해시 함수 구현

- SHA256, SHA256d (double hash)
- HASH160 (주소 생성용)
```

---

### `crypto/signature.py`
**구현 내용:**
- `KeyPair` 클래스 (private/public key)
- `sign(private_key, message)` - ECDSA 서명
- `verify(public_key, message, signature)` - 서명 검증
- secp256k1 커브 사용

**커밋 메시지:**
```
feat: [crypto] ECDSA 서명/검증 구현

- KeyPair 생성 (secp256k1)
- 트랜잭션 서명 및 검증
```

---

### `crypto/address.py`
**구현 내용:**
- `public_key_to_address(pubkey)` - 공개키 → 주소 변환
- `validate_address(address)` - 주소 유효성 검사
- Base58Check 인코딩
- 버전 프리픽스 (메인넷/테스트넷)

**커밋 메시지:**
```
feat: [crypto] 주소 생성 및 검증

- Base58Check 인코딩
- 공개키 → 주소 변환
- 체크섬 검증
```

---

### `crypto/merkle.py`
**구현 내용:**
- `merkle_root(tx_hashes)` - 머클 루트 계산
- 홀수 개일 때 마지막 해시 복제
- 빈 리스트면 32바이트 0 반환

**커밋 메시지:**
```
feat: [crypto] 머클 트리 구현

- 트랜잭션 머클 루트 계산
- 블록 헤더 무결성 검증용
```

---

### `core/transaction.py`
**구현 내용:**
- `TxInput` - prev_tx_id, output_index, signature
- `TxOutput` - amount, script_pubkey, asset_id
- `Transaction` - version, inputs, outputs, locktime
- `get_txid()` - 트랜잭션 해시
- `serialize()` / `deserialize()` - 직렬화
- `is_coinbase()` - 코인베이스 판별

**커밋 메시지:**
```
feat: [core] 트랜잭션 구조체 구현

- TxInput/TxOutput 데이터 클래스
- 트랜잭션 직렬화/역직렬화
- TXID 계산, 코인베이스 판별
```

---

### `core/block.py`
**구현 내용:**
- `BlockHeader` - version, prev_hash, merkle_root, timestamp, bits, nonce
- `Block` - header, transactions
- `get_hash()` - 블록 해시 (SHA256d of header)
- `serialize()` / `deserialize()`
- `calculate_merkle_root()` - TX들로부터 머클루트 계산

**커밋 메시지:**
```
feat: [core] 블록 구조체 구현

- BlockHeader (80 bytes)
- 블록 해시 계산 (SHA256d)
- 머클 루트 자동 계산
```

---

### `core/utxo.py`
**구현 내용:**
- `UTXO` - tx_id, output_index, amount, script, height, asset_id
- `UTXOSet` 클래스
  - `add_utxo()` / `remove_utxo()`
  - `get_utxo(tx_id, index)`
  - `get_balance(address)`
  - `apply_transaction()` - TX 적용 (spent UTXOs 반환)
  - `revert_transaction()` - TX 되돌리기 (Reorg용)

**커밋 메시지:**
```
feat: [core] UTXO 모델 구현

- UTXOSet: UTXO 추가/제거/조회
- 주소별 잔액 계산
- Reorg 지원 (apply/revert)
```

---

## B (Consensus) 담당 파일

---

### `consensus/difficulty.py`
**구현 내용:**
- `bits_to_target(bits)` - compact → 256bit target
- `target_to_bits(target)` - target → compact
- `calculate_next_target()` - 난이도 재계산 (50블록마다)
- `get_difficulty()` - 현재 난이도 (사람이 읽을 수 있는 값)
- 최대 4배 조정 제한

**커밋 메시지:**
```
feat: [consensus] 난이도 조정 알고리즘

- bits ↔ target 변환
- 50블록마다 난이도 재계산
- 최대 4배 변화 제한
```

---

### `consensus/miner.py`
**구현 내용:**
- `create_coinbase_tx(address, height, fees)` - 코인베이스 생성
- `create_block_template(prev_block, txs, address)` - 블록 템플릿
- `mine_block(block, target)` - PoW 채굴 (nonce 탐색)
- `validate_proof_of_work(block)` - PoW 검증

**커밋 메시지:**
```
feat: [consensus] PoW 채굴기 구현

- 코인베이스 트랜잭션 생성
- 블록 템플릿 생성
- Nonce 탐색 (SHA256d)
```

---

### `validation/transaction.py`
**구현 내용:**
- `validate_transaction(tx, utxo_set)` - TX 검증
  - 입력 UTXO 존재 확인
  - 서명 검증
  - 입력 >= 출력 확인 (수수료)
  - 더블 스펜딩 방지
- TX 버전별 추가 검증 (Commit, Claim 등)

**커밋 메시지:**
```
feat: [validation] 트랜잭션 검증 로직

- UTXO 존재/서명 검증
- 잔액 검증 (입력 >= 출력)
- TX 타입별 규칙 검증
```

---

### `validation/block.py`
**구현 내용:**
- `validate_block_header(header, prev_block)` - 헤더 검증
  - prev_hash 일치
  - timestamp 범위
  - PoW 만족
  - bits 올바른지
- `validate_block(block, chain)` - 전체 블록 검증
  - 모든 TX 검증
  - 머클 루트 일치
  - 코인베이스 규칙

**커밋 메시지:**
```
feat: [validation] 블록 검증 로직

- 헤더 검증 (prev_hash, PoW, timestamp)
- 트랜잭션 일괄 검증
- 머클 루트 검증
```

---

### `consensus/chain.py`
**구현 내용:**
- `Blockchain` 클래스
  - `add_block(block)` - 블록 추가 (검증 포함)
  - `get_block(hash)` / `get_block_by_height(height)`
  - `get_height()` - 현재 높이
  - `get_tip()` - 최신 블록
  - `_reorganize()` - 체인 재구성 (Reorg)
  - `_connect_block()` / `_disconnect_block()` - UTXO 연결/해제
  - `get_block_locator()` - IBD용 로케이터
- `_undo_data` - Reorg용 spent UTXO 저장

**커밋 메시지:**
```
feat: [consensus] 블록체인 관리 및 Reorg

- 블록 추가/조회/검증
- 체인 재구성 (Reorg) 처리
- UTXO connect/disconnect
- Block locator (IBD용)
```

---

## C (Network) 담당 파일

---

### `network/peer.py`
**구현 내용:**
- `PeerAddress` - ip, port
- `PeerState` - enum (CONNECTING, CONNECTED, READY, DISCONNECTED)
- `PeerInfo` - address, state, version, height, last_seen, is_inbound
- 피어 상태 관리

**커밋 메시지:**
```
feat: [network] 피어 데이터 구조

- PeerAddress, PeerState, PeerInfo
- 연결 상태 관리
```

---

### `network/protocol.py`
**구현 내용:**
- 메시지 헤더 (magic + command + length + checksum)
- 메시지 타입: VERSION, VERACK, INV, GETDATA, BLOCK, TX, GETBLOCKS, GETHEADERS, HEADERS, ADDR, GETADDR, PING, PONG
- 각 메시지 serialize/deserialize
- `InventoryType` - TX=1, BLOCK=2

**커밋 메시지:**
```
feat: [network] P2P 프로토콜 메시지 정의

- 메시지 헤더 (magic, command, checksum)
- VERSION/VERACK 핸드셰이크
- INV/GETDATA/BLOCK/TX 메시지
- GETHEADERS/HEADERS 프로토콜
```

---

### `network/discovery.py`
**구현 내용:**
- `PeerDiscovery` 클래스
  - DNS 시드 조회
  - 하드코딩 시드 목록
  - `peers.json` 캐시 로드/저장
  - `get_peers()` - 연결할 피어 목록 반환
- GETADDR/ADDR 메시지 처리

**커밋 메시지:**
```
feat: [network] 피어 발견 메커니즘

- DNS 시드 조회
- 하드코딩 시드 노드
- 피어 캐시 (peers.json)
- GETADDR/ADDR 프로토콜
```

---

### `network/nat.py`
**구현 내용:**
- `NATManager` 클래스
- NAT Traversal 순서:
  1. PCP (Port Control Protocol)
  2. NAT-PMP
  3. UPnP (miniupnpc)
  4. 수동 포트포워딩 감지
- `setup_port_mapping()` - 포트 매핑 시도
- `get_external_address()` - 외부 IP:Port
- `cleanup()` - 매핑 해제

**커밋 메시지:**
```
feat: [network] NAT Traversal 구현

- PCP/NAT-PMP/UPnP 자동 시도
- 외부 주소 감지
- 포트 매핑 생명주기 관리
```

---

### `network/node.py`
**구현 내용:**
- `NodeConfig` - 설정 (port, max_peers, nat_enabled 등)
- `Node` 클래스
  - `start()` / `stop()` - 노드 시작/종료
  - `connect_to_peer(address)` - 아웃바운드 연결
  - `_handle_connection()` - 인바운드 처리
  - 메시지 핸들러들 (`_handle_version`, `_handle_block` 등)
  - `broadcast_tx()` / `broadcast_block()` - 전파
- `PeerManager` - 연결된 피어 관리

**커밋 메시지:**
```
feat: [network] P2P 노드 구현

- TCP 서버/클라이언트
- 핸드셰이크 (VERSION/VERACK)
- 메시지 라우팅 및 핸들링
- TX/블록 전파
```

---

### `network/holepunch.py`
**구현 내용:**
- `RendezvousServer` - 시드 노드에서 실행
  - 피어 등록/조회
  - 연결 중개
- `HolePunchClient` - 일반 노드
  - 랑데부 서버에 등록
  - TCP simultaneous open 시도
- 하트비트로 등록 유지

**커밋 메시지:**
```
feat: [network] TCP Hole Punching 구현

- 랑데부 서버 (피어 중개)
- 홀펀치 클라이언트
- NAT 뒤 노드 간 직접 연결
```

---

### `sync/manager.py`
**구현 내용:**
- `SyncManager` 클래스
  - `start_sync(peer)` - 동기화 시작
  - `request_blocks(locator)` - GETBLOCKS 요청
  - `handle_inv()` - INV 처리 → GETDATA
  - `handle_block()` - 블록 수신 처리
- Headers-first 동기화 지원
- 동기화 상태 추적

**커밋 메시지:**
```
feat: [sync] 블록 동기화 매니저

- IBD (Initial Block Download)
- GETBLOCKS/INV/GETDATA 흐름
- Headers-first 동기화
```

---

## D (Application) 담당 파일

---

### `script/opcodes.py`
**구현 내용:**
- OP 코드 상수 정의
  - `OP_DUP`, `OP_HASH160`, `OP_EQUALVERIFY`, `OP_CHECKSIG`
  - `OP_RETURN`, `OP_PUSHDATA` 등
- 바이트 값 매핑

**커밋 메시지:**
```
feat: [script] OP 코드 정의

- 스택 조작 (DUP, DROP, SWAP)
- 암호화 (HASH160, CHECKSIG)
- 흐름 제어 (IF, ELSE, ENDIF)
```

---

### `script/standard.py`
**구현 내용:**
- `create_p2pkh_script(address)` - P2PKH 잠금 스크립트
- `create_p2pkh_unlock(signature, pubkey)` - P2PKH 해제
- `create_commit_script()` - 로또 Commit용
- `create_claim_script()` - 로또 Claim용
- `get_script_type(script)` - 스크립트 타입 판별

**커밋 메시지:**
```
feat: [script] 표준 스크립트 템플릿

- P2PKH 잠금/해제 스크립트
- 로또 Commit/Claim 스크립트
- 스크립트 타입 판별
```

---

### `script/interpreter.py`
**구현 내용:**
- `ScriptInterpreter` 클래스
- `execute(unlock_script, lock_script, tx, input_index)` - 스크립트 실행
- 스택 기반 실행 엔진
- OP 코드별 실행 로직
- 서명 검증 통합

**커밋 메시지:**
```
feat: [script] 스크립트 인터프리터

- 스택 기반 실행 엔진
- OP 코드 실행 로직
- P2PKH 검증 지원
```

---

### `wallet/wallet.py`
**구현 내용:**
- `Wallet` 클래스
  - `create()` / `load(path)` / `save(path)` - 지갑 관리
  - `get_address()` - 현재 주소
  - `get_balance(utxo_set)` - 잔액 조회
  - `create_transaction(to, amount, utxo_set)` - TX 생성
  - `sign_transaction(tx)` - TX 서명
- 키 암호화 저장 (선택)

**커밋 메시지:**
```
feat: [wallet] 지갑 구현

- 키페어 생성/저장/로드
- 잔액 조회 (UTXO 기반)
- 트랜잭션 생성 및 서명
```

---

### `asset/manager.py`
**구현 내용:**
- `AssetManager` 클래스
- JACK / POT 듀얼 에셋 관리
- `get_balance(address, asset_id)` - 에셋별 잔액
- `validate_asset_transfer()` - 에셋 전송 검증

**커밋 메시지:**
```
feat: [asset] 멀티 에셋 관리

- JACK/POT 듀얼 에셋
- 에셋별 잔액 조회
- 전송 검증
```

---

### `asset/exchange.py`
**구현 내용:**
- `ExchangeService` 클래스
- `exchange_jack_to_pot(amount)` - JACK → POT 교환
- 교환 비율: 100 JACK = 1 POT
- 교환 TX 생성 (version=2)

**커밋 메시지:**
```
feat: [asset] JACK ↔ POT 교환

- 100 JACK = 1 POT 고정 비율
- Exchange TX (version 2) 생성
- JACK 소각 처리
```

---

### `gacha/commit_reveal.py`
**구현 내용:**
- `create_commit_hash(nonce, numbers)` - 커밋 해시 생성
- `verify_reveal(commit_hash, nonce, numbers)` - 공개 검증
- `generate_random_nonce()` - 32바이트 난수
- Commit TX / Claim TX 구조

**커밋 메시지:**
```
feat: [gacha] Commit-Reveal 패턴

- 커밋 해시 생성 (SHA256)
- Reveal 검증
- 채굴자 조작 방지
```

---

### `gacha/pool.py`
**구현 내용:**
- `JackpotPool` 클래스
- `add_funds(amount)` - 풀에 자금 추가
- `get_balance()` - 현재 잔액
- `calculate_payout(rank)` - 등수별 보상 계산
- `withdraw(amount)` - 당첨금 출금

**커밋 메시지:**
```
feat: [gacha] 잭팟 풀 관리

- 풀 자금 관리
- 등수별 보상 계산
- 당첨금 지급
```

---

### `gacha/game.py`
**구현 내용:**
- `LottoGame` 클래스
- `check_winning(chosen_numbers, block_hashes)` - 당첨 확인
  - 6개 블록 해시 (N+5, N+10, ..., N+30) 끝자리와 비교
- `calculate_rank(matches)` - 매칭 수 → 등수
- `get_comparison_blocks(commit_height)` - 비교 블록 높이 계산

**커밋 메시지:**
```
feat: [gacha] 로또 게임 로직

- 6자리 숫자 매칭 (블록해시 기반)
- 등수 판정 (1등~6등)
- 비교 블록 높이 계산
```

---

### `gacha/service.py`
**구현 내용:**
- `GachaService` 클래스 - 전체 흐름 통합
- `create_commit_tx(wallet, numbers)` - Commit TX 생성
- `create_claim_tx(wallet, commit_tx, nonce, numbers)` - Claim TX 생성
- `process_claim(claim_tx, chain)` - Claim 처리 및 보상 지급
- `get_pending_commits()` - 미처리 Commit 조회
- Claim 윈도우 검증 (N+30 ~ N+80)

**커밋 메시지:**
```
feat: [gacha] 로또 서비스 통합

- Commit → Claim 전체 흐름
- 참가비 분배 (풀 80%, 소각 19%, 채굴자 1%)
- Claim 윈도우 검증
- 당첨금 자동 지급
```

---

## E (Infra) 담당 파일

---

### `storage/database.py`
**구현 내용:**
- `BlockStorage` 클래스
  - `save_block(block)` - .blk 파일 저장
  - `load_block(hash)` - 블록 로드
  - `save_index()` / `load_index()` - 높이 인덱스
- 파일 구조: `data/blocks/XX/HASH.blk`

**커밋 메시지:**
```
feat: [storage] 블록 저장소

- 블록 파일 저장 (.blk)
- 높이 인덱스 관리
- 샤딩 (해시 앞 2자리)
```

---

### `mempool/pool.py`
**구현 내용:**
- `Mempool` 클래스
  - `add_transaction(tx)` - TX 추가 (검증 포함)
  - `remove_transaction(txid)` - TX 제거
  - `get_transactions(limit)` - 블록에 넣을 TX 선택
  - `get_transaction(txid)` - TX 조회
- 수수료 기반 정렬
- 크기 제한 (300MB)

**커밋 메시지:**
```
feat: [mempool] 트랜잭션 풀

- TX 추가/제거/조회
- 수수료 기반 우선순위
- 메모리 제한 관리
```

---

### `rpc/server.py`
**구현 내용:**
- JSON-RPC 2.0 서버 (aiohttp)
- 메서드:
  - `getblockchaininfo` - 체인 상태
  - `getblock(hash)` - 블록 조회
  - `gettransaction(txid)` - TX 조회
  - `sendrawtransaction(hex)` - TX 전파
  - `getbalance(address)` - 잔액 조회
  - `getmininginfo` - 채굴 정보
  - `getnewaddress` - 새 주소 생성

**커밋 메시지:**
```
feat: [rpc] JSON-RPC 서버

- 블록/TX 조회 API
- 잔액 조회, TX 전송
- 채굴 정보 API
```

---

### `cli/main.py`
**구현 내용:**
- argparse 기반 CLI
- 명령어:
  - `start` - 노드 시작
  - `mine` - 채굴 시작
  - `send <to> <amount>` - 전송
  - `balance [address]` - 잔액
  - `lotto commit/claim` - 로또
  - `status` - 노드 상태
- 설정 파일 로드

**커밋 메시지:**
```
feat: [cli] 커맨드라인 인터페이스

- 노드 시작/종료
- 채굴, 전송, 잔액 조회
- 로또 참여 (commit/claim)
```

---

### `tests/test_core.py`
**구현 내용:**
- Transaction 테스트 (생성, 직렬화, 서명)
- Block 테스트 (생성, 해시, 머클루트)
- UTXO 테스트 (추가, 제거, 잔액)

**커밋 메시지:**
```
test: [core] 핵심 자료구조 테스트

- 트랜잭션 생성/직렬화
- 블록 해시/머클루트 검증
- UTXO 관리 테스트
```

---

### `tests/test_crypto.py`
**구현 내용:**
- 해시 함수 테스트
- 서명/검증 테스트
- 주소 생성/검증 테스트
- 머클 트리 테스트

**커밋 메시지:**
```
test: [crypto] 암호화 모듈 테스트

- SHA256, HASH160 검증
- ECDSA 서명/검증
- 주소 생성 테스트
```

---

### `tests/test_network.py`
**구현 내용:**
- 프로토콜 메시지 직렬화 테스트
- 피어 연결 테스트
- 핸드셰이크 테스트

**커밋 메시지:**
```
test: [network] 네트워크 모듈 테스트

- 메시지 직렬화/역직렬화
- 피어 연결 시뮬레이션
- 핸드셰이크 검증
```

---

### `tests/test_gacha.py`
**구현 내용:**
- Commit-Reveal 테스트
- 당첨 판정 테스트
- 잭팟 풀 테스트
- 전체 흐름 통합 테스트

**커밋 메시지:**
```
test: [gacha] 로또 시스템 테스트

- Commit-Reveal 검증
- 등수 판정 테스트
- 보상 지급 테스트
```

---

### `tests/test_reorg.py`
**구현 내용:**
- 간단한 체인 UTXO 테스트
- Reorg 시 UTXO 복원 테스트
- 트랜잭션 되돌리기 테스트

**커밋 메시지:**
```
test: [consensus] Reorg UTXO 테스트

- 블록 연결/해제 UTXO 검증
- 체인 재구성 시 UTXO 복원
```

---

## 체크리스트

### Day 1 완료 조건
- [ ] 트랜잭션 생성/서명 가능
- [ ] 블록 채굴 가능
- [ ] 피어 연결 가능

### Day 2 완료 조건
- [ ] UTXO 추적 동작
- [ ] 블록 검증 통과
- [ ] RPC로 잔액 조회 가능
- [ ] JACK ↔ POT 교환 가능

### Day 3 완료 조건
- [ ] 로또 Commit → Claim 전체 흐름
- [ ] 3노드 이상 동기화 성공
- [ ] 모든 테스트 통과
- [ ] Docker 배포 준비 완료

---

## 긴급 연락

문제 발생 시 담당자에게 바로 연락!

| 이슈 | 담당 |
|------|:----:|
| 트랜잭션/블록 오류 | 임경수 (A) |
| 합의/검증 실패 | 양한빈 (B) |
| 연결/동기화 문제 | 이동휘 (C) |
| 로또/지갑 버그 | 이민수 (D) |
| 테스트/배포 이슈 | 장주윤 (E) |
