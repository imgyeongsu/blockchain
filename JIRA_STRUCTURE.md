# JackpotChain JIRA 구조

> Epic → Story → Task 계층 (Story Point 포함)

---

## 전체 프로젝트 구조

```
EP-01: Frontend
EP-02: Backend
EP-03: Blockchain ← 이 문서의 범위
```

---

## EP-03: Blockchain 요약

| Story | 담당 | Tasks | Story Points |
|-------|:----:|:-----:|:------------:|
| ST-01: Core | A | 8 | 20 SP |
| ST-02: Consensus | B | 8 | 25 SP |
| ST-03: Network | C | 10 | 36 SP |
| ST-04: Application | D | 10 | 30 SP |
| ST-05: Infra | E | 8 | 23 SP |
| **합계** | - | **44** | **134 SP** |

---

## Story Point 기준

| SP | 난이도 | 예상 시간 |
|:--:|--------|----------|
| 1 | 단순 | ~1시간 |
| 2 | 쉬움 | 2-3시간 |
| 3 | 보통 | 반나절 |
| 5 | 복잡 | 하루 |
| 8 | 매우 복잡 | 1.5일 |

---

## ST-01: Core (자료구조 + 암호화)

**담당: A** | **총 20 SP**

| 키 | Task | SP | 파일 | 상태 |
|----|------|:--:|------|:----:|
| T-01 | 전역 상수 정의 | 1 | `constants.py` | TODO |
| T-02 | 해시 함수 (SHA256, HASH160) | 2 | `crypto/hash.py` | TODO |
| T-03 | ECDSA 서명/검증 | 3 | `crypto/signature.py` | TODO |
| T-04 | 주소 생성 (Base58Check) | 2 | `crypto/address.py` | TODO |
| T-05 | 머클 트리 | 2 | `crypto/merkle.py` | TODO |
| T-06 | 트랜잭션 구조체 | 3 | `core/transaction.py` | TODO |
| T-07 | 블록 구조체 | 2 | `core/block.py` | TODO |
| T-08 | UTXO 모델 | 5 | `core/utxo.py` | TODO |

### Task 상세

#### T-01: 전역 상수 정의 (1 SP)
```
구현:
- 네트워크: MAGIC, PORT 8333/8332
- 블록: BLOCK_TIME=30초, DIFFICULTY_INTERVAL=50
- 보상: BLOCK_REWARD=50 JACK, 수수료 분배율
- 로또: 6자리, N+5~N+30 비교, Claim 윈도우

커밋: feat: [core] 전역 상수 정의
```

#### T-02: 해시 함수 (2 SP)
```
구현:
- sha256(data) → bytes
- double_sha256(data) → bytes (SHA256d)
- hash160(data) → bytes (RIPEMD160(SHA256))

커밋: feat: [crypto] 해시 함수 구현 (SHA256, HASH160)
```

#### T-03: ECDSA 서명/검증 (3 SP)
```
구현:
- KeyPair 클래스 (private/public)
- sign(private_key, message) → signature
- verify(public_key, message, signature) → bool
- secp256k1 커브 사용

커밋: feat: [crypto] ECDSA 서명/검증 구현
```

#### T-04: 주소 생성 (2 SP)
```
구현:
- public_key_to_address(pubkey) → str
- validate_address(address) → bool
- Base58Check 인코딩/디코딩
- 버전 프리픽스

커밋: feat: [crypto] 주소 생성 및 검증
```

#### T-05: 머클 트리 (2 SP)
```
구현:
- merkle_root(tx_hashes) → bytes
- 홀수 개면 마지막 복제
- 빈 리스트면 32바이트 0

커밋: feat: [crypto] 머클 트리 구현
```

#### T-06: 트랜잭션 구조체 (3 SP)
```
구현:
- TxInput: prev_tx_id, output_index, signature
- TxOutput: amount, script_pubkey, asset_id
- Transaction: version, inputs, outputs, locktime
- serialize() / deserialize()
- get_txid(), is_coinbase()

커밋: feat: [core] 트랜잭션 구조체 구현
```

#### T-07: 블록 구조체 (2 SP)
```
구현:
- BlockHeader: version, prev_hash, merkle_root, timestamp, bits, nonce
- Block: header, transactions
- get_hash() → SHA256d of header
- serialize() / deserialize()

커밋: feat: [core] 블록 구조체 구현
```

#### T-08: UTXO 모델 (5 SP)
```
구현:
- UTXO: tx_id, index, amount, script, height, asset_id
- UTXOSet 클래스:
  - add_utxo() / remove_utxo()
  - get_utxo(tx_id, index)
  - get_balance(address)
  - apply_transaction() → spent_utxos 반환
  - revert_transaction() (Reorg용)

커밋: feat: [core] UTXO 모델 구현
```

---

## ST-02: Consensus (합의 + 검증)

**담당: B** | **총 25 SP**

| 키 | Task | SP | 파일 | 상태 |
|----|------|:--:|------|:----:|
| T-09 | 난이도 조정 알고리즘 | 3 | `consensus/difficulty.py` | TODO |
| T-10 | PoW 채굴 | 3 | `consensus/miner.py` | TODO |
| T-11 | 블록체인 관리 | 5 | `consensus/chain.py` | TODO |
| T-12 | Reorg 처리 | 5 | `consensus/chain.py` | TODO |
| T-13 | 트랜잭션 검증 | 3 | `validation/transaction.py` | TODO |
| T-14 | 블록 검증 | 3 | `validation/block.py` | TODO |
| T-15 | 제네시스 블록 | 1 | `consensus/chain.py` | TODO |
| T-16 | Block Locator | 2 | `consensus/chain.py` | TODO |

### Task 상세

#### T-09: 난이도 조정 알고리즘 (3 SP)
```
구현:
- bits_to_target(bits) → int
- target_to_bits(target) → int
- calculate_next_target(prev_blocks) → new_bits
- 50블록마다 조정, 최대 4배 제한

커밋: feat: [consensus] 난이도 조정 알고리즘
```

#### T-10: PoW 채굴 (3 SP)
```
구현:
- create_coinbase_tx(address, height, fees)
- create_block_template(prev_block, txs, address)
- mine_block(block, target) → nonce 탐색
- validate_proof_of_work(block) → bool

커밋: feat: [consensus] PoW 채굴기 구현
```

#### T-11: 블록체인 관리 (5 SP)
```
구현:
- Blockchain 클래스:
  - add_block(block) → 검증 후 추가
  - get_block(hash) / get_block_by_height(height)
  - get_height() / get_tip()
  - _blocks, _height_index 관리

커밋: feat: [consensus] 블록체인 관리 클래스
```

#### T-12: Reorg 처리 (5 SP)
```
구현:
- _reorganize(new_tip) → 체인 재구성
- _connect_block(block) → UTXO 적용 + undo 저장
- _disconnect_block(hash) → UTXO 되돌리기
- _undo_data: Dict[hash, List[spent_utxos]]

커밋: feat: [consensus] Reorg UTXO 재계산
```

#### T-13: 트랜잭션 검증 (3 SP)
```
구현:
- validate_transaction(tx, utxo_set):
  - UTXO 존재 확인
  - 서명 검증
  - 입력 >= 출력 (수수료)
  - 더블 스펜딩 방지
  - TX 버전별 규칙 (Commit, Claim 등)

커밋: feat: [validation] 트랜잭션 검증 로직
```

#### T-14: 블록 검증 (3 SP)
```
구현:
- validate_block_header(header, prev):
  - prev_hash 일치
  - timestamp 범위
  - PoW 만족, bits 검증
- validate_block(block, chain):
  - 모든 TX 검증
  - 머클 루트 검증
  - 코인베이스 규칙

커밋: feat: [validation] 블록 검증 로직
```

#### T-15: 제네시스 블록 (1 SP)
```
구현:
- create_genesis_block() → Block
- 하드코딩된 파라미터
- 잭팟풀 초기 자금 100만 JACK

커밋: feat: [consensus] 제네시스 블록 생성
```

#### T-16: Block Locator (2 SP)
```
구현:
- get_block_locator() → List[hash]
- 지수 간격: 0, 1, 2, 4, 8, 16, ...
- IBD GETBLOCKS 요청용

커밋: feat: [consensus] Block Locator 생성
```

---

## ST-03: Network (P2P + 동기화)

**담당: C** | **총 36 SP** ⚠️ 가장 큼

| 키 | Task | SP | 파일 | 상태 |
|----|------|:--:|------|:----:|
| T-17 | 피어 데이터 구조 | 2 | `network/peer.py` | TODO |
| T-18 | 프로토콜 메시지 | 3 | `network/protocol.py` | TODO |
| T-19 | 피어 발견 | 3 | `network/discovery.py` | TODO |
| T-20 | NAT Traversal | 8 | `network/nat.py` | TODO |
| T-21 | P2P 노드 | 5 | `network/node.py` | TODO |
| T-22 | 핸드셰이크 | 2 | `network/node.py` | TODO |
| T-23 | 메시지 핸들링 | 3 | `network/node.py` | TODO |
| T-24 | IBD (블록 동기화) | 3 | `sync/manager.py` | TODO |
| T-25 | TCP Hole Punching | 5 | `network/holepunch.py` | TODO |
| T-26 | 블록/TX 전파 | 2 | `network/node.py` | TODO |

### Task 상세

#### T-17: 피어 데이터 구조 (2 SP)
```
구현:
- PeerAddress: ip, port
- PeerState: enum (CONNECTING, CONNECTED, READY, DISCONNECTED)
- PeerInfo: address, state, version, height, is_inbound

커밋: feat: [network] 피어 데이터 구조
```

#### T-18: 프로토콜 메시지 (3 SP)
```
구현:
- 메시지 헤더: magic(4) + command(12) + length(4) + checksum(4)
- 메시지 타입: VERSION, VERACK, INV, GETDATA, BLOCK, TX,
              GETBLOCKS, GETHEADERS, HEADERS, ADDR, GETADDR, PING, PONG
- serialize() / deserialize() 각 메시지

커밋: feat: [network] P2P 프로토콜 메시지 정의
```

#### T-19: 피어 발견 (3 SP)
```
구현:
- PeerDiscovery 클래스:
  - DNS 시드 조회
  - 하드코딩 시드 목록
  - peers.json 캐시 로드/저장
  - get_peers() → List[PeerAddress]

커밋: feat: [network] 피어 발견 메커니즘
```

#### T-20: NAT Traversal (8 SP) ⚠️
```
구현:
- NATManager 클래스
- 시도 순서: PCP → NAT-PMP → UPnP → 수동 감지
- setup_port_mapping() → bool
- get_external_address() → (ip, port)
- cleanup() → 매핑 해제

커밋: feat: [network] NAT Traversal (PCP/NAT-PMP/UPnP)
```

#### T-21: P2P 노드 (5 SP)
```
구현:
- NodeConfig: port, max_peers, nat_enabled, is_seed_node
- Node 클래스:
  - start() / stop()
  - TCP 서버 (asyncio)
  - connect_to_peer(address) → 아웃바운드
  - _handle_connection() → 인바운드

커밋: feat: [network] P2P 노드 구현
```

#### T-22: 핸드셰이크 (2 SP)
```
구현:
- VERSION 메시지 교환
- VERACK 응답
- 피어 상태 → READY 전환
- 버전/높이 정보 저장

커밋: feat: [network] VERSION/VERACK 핸드셰이크
```

#### T-23: 메시지 핸들링 (3 SP)
```
구현:
- _handle_message(peer, command, payload)
- 메시지별 핸들러 라우팅:
  - _handle_inv, _handle_getdata
  - _handle_block, _handle_tx
  - _handle_ping, _handle_pong

커밋: feat: [network] 메시지 핸들러 라우팅
```

#### T-24: IBD (블록 동기화) (3 SP)
```
구현:
- SyncManager 클래스:
  - start_sync(peer)
  - request_blocks(locator) → GETBLOCKS
  - handle_inv() → GETDATA 요청
  - handle_block() → 블록 수신 처리
- 동기화 상태 추적

커밋: feat: [sync] 블록 동기화 (IBD)
```

#### T-25: TCP Hole Punching (5 SP)
```
구현:
- RendezvousServer: 피어 등록/중개 (시드 노드)
- HolePunchClient: 랑데부 등록, 홀펀치 시도
- TCP simultaneous open
- 하트비트로 등록 유지

커밋: feat: [network] TCP Hole Punching
```

#### T-26: 블록/TX 전파 (2 SP)
```
구현:
- broadcast_block(block) → 모든 피어에 INV
- broadcast_tx(tx) → 모든 피어에 INV
- relay_to_peer(peer, message)

커밋: feat: [network] 블록/TX 전파
```

---

## ST-04: Application (로또 + 지갑 + 에셋)

**담당: D** | **총 30 SP**

| 키 | Task | SP | 파일 | 상태 |
|----|------|:--:|------|:----:|
| T-27 | 스크립트 OP 코드 | 2 | `script/opcodes.py` | TODO |
| T-28 | P2PKH 스크립트 | 2 | `script/standard.py` | TODO |
| T-29 | 스크립트 인터프리터 | 5 | `script/interpreter.py` | TODO |
| T-30 | 지갑 (키 관리) | 3 | `wallet/wallet.py` | TODO |
| T-31 | TX 생성/서명 | 3 | `wallet/wallet.py` | TODO |
| T-32 | JACK/POT 멀티 에셋 | 2 | `asset/manager.py` | TODO |
| T-33 | JACK↔POT 교환 | 2 | `asset/exchange.py` | TODO |
| T-34 | Commit-Reveal 패턴 | 3 | `gacha/commit_reveal.py` | TODO |
| T-35 | 잭팟 풀 관리 | 3 | `gacha/pool.py` | TODO |
| T-36 | 로또 서비스 | 5 | `gacha/service.py` | TODO |

### Task 상세

#### T-27: 스크립트 OP 코드 (2 SP)
```
구현:
- OP_DUP, OP_HASH160, OP_EQUALVERIFY, OP_CHECKSIG
- OP_RETURN, OP_PUSHDATA
- OP_IF, OP_ELSE, OP_ENDIF
- 바이트 값 매핑

커밋: feat: [script] OP 코드 정의
```

#### T-28: P2PKH 스크립트 (2 SP)
```
구현:
- create_p2pkh_script(address) → lock script
- create_p2pkh_unlock(sig, pubkey) → unlock script
- create_commit_script() / create_claim_script()
- get_script_type(script) → 타입 판별

커밋: feat: [script] 표준 스크립트 템플릿
```

#### T-29: 스크립트 인터프리터 (5 SP)
```
구현:
- ScriptInterpreter 클래스
- execute(unlock, lock, tx, index) → bool
- 스택 기반 실행 엔진
- OP 코드별 실행 로직

커밋: feat: [script] 스크립트 인터프리터
```

#### T-30: 지갑 (키 관리) (3 SP)
```
구현:
- Wallet 클래스:
  - create() → 새 지갑
  - load(path) / save(path)
  - get_address() → 현재 주소
  - get_private_key()

커밋: feat: [wallet] 지갑 키 관리
```

#### T-31: TX 생성/서명 (3 SP)
```
구현:
- get_balance(utxo_set) → 잔액
- select_utxos(amount) → UTXO 선택
- create_transaction(to, amount, utxo_set) → TX
- sign_transaction(tx) → 서명된 TX

커밋: feat: [wallet] 트랜잭션 생성 및 서명
```

#### T-32: JACK/POT 멀티 에셋 (2 SP)
```
구현:
- AssetManager 클래스
- ASSET_ID_JACK, ASSET_ID_POT
- get_balance(address, asset_id)
- validate_asset_transfer()

커밋: feat: [asset] JACK/POT 멀티 에셋 관리
```

#### T-33: JACK↔POT 교환 (2 SP)
```
구현:
- ExchangeService 클래스
- exchange_jack_to_pot(amount) → TX
- 비율: 100 JACK = 1 POT
- JACK 소각 처리

커밋: feat: [asset] JACK↔POT 교환 서비스
```

#### T-34: Commit-Reveal 패턴 (3 SP)
```
구현:
- create_commit_hash(nonce, numbers) → hash
- verify_reveal(commit_hash, nonce, numbers) → bool
- generate_random_nonce() → 32바이트
- Commit TX 구조 (version=3)

커밋: feat: [gacha] Commit-Reveal 패턴
```

#### T-35: 잭팟 풀 관리 (3 SP)
```
구현:
- JackpotPool 클래스
- add_funds(amount) / get_balance()
- calculate_payout(rank) → 등수별 보상
- withdraw(amount) → 당첨금 출금
- 초기 자금 100만 JACK

커밋: feat: [gacha] 잭팟 풀 관리
```

#### T-36: 로또 서비스 (5 SP)
```
구현:
- GachaService 클래스:
  - create_commit_tx(wallet, numbers)
  - create_claim_tx(wallet, commit_tx, nonce, numbers)
  - process_claim(claim_tx, chain) → 보상 지급
  - check_winning(numbers, block_hashes) → 등수
- Claim 윈도우: N+30 ~ N+80
- 참가비 분배: 풀 80%, 소각 19%, 채굴자 1%

커밋: feat: [gacha] 로또 서비스 통합
```

---

## ST-05: Infra (CLI + RPC + 저장소 + 테스트)

**담당: E** | **총 23 SP**

| 키 | Task | SP | 파일 | 상태 |
|----|------|:--:|------|:----:|
| T-37 | 블록 저장소 | 3 | `storage/database.py` | TODO |
| T-38 | 멤풀 | 3 | `mempool/pool.py` | TODO |
| T-39 | RPC 서버 | 5 | `rpc/server.py` | TODO |
| T-40 | CLI 명령어 | 3 | `cli/main.py` | TODO |
| T-41 | Core 테스트 | 2 | `tests/test_core.py` | TODO |
| T-42 | Crypto 테스트 | 2 | `tests/test_crypto.py` | TODO |
| T-43 | Network 테스트 | 2 | `tests/test_network.py` | TODO |
| T-44 | Gacha 테스트 | 3 | `tests/test_gacha.py` | TODO |

### Task 상세

#### T-37: 블록 저장소 (3 SP)
```
구현:
- BlockStorage 클래스:
  - save_block(block) → .blk 파일
  - load_block(hash) → Block
  - save_index() / load_index()
- 경로: data/blocks/XX/HASH.blk (샤딩)

커밋: feat: [storage] 블록 저장소
```

#### T-38: 멤풀 (3 SP)
```
구현:
- Mempool 클래스:
  - add_transaction(tx) → 검증 후 추가
  - remove_transaction(txid)
  - get_transactions(limit) → 블록용 TX 선택
- 수수료 기반 정렬
- 크기 제한 300MB

커밋: feat: [mempool] 트랜잭션 풀
```

#### T-39: RPC 서버 (5 SP)
```
구현:
- JSON-RPC 2.0 서버 (aiohttp)
- 메서드:
  - getblockchaininfo
  - getblock, gettransaction
  - sendrawtransaction
  - getbalance
  - getmininginfo, getnewaddress

커밋: feat: [rpc] JSON-RPC 서버
```

#### T-40: CLI 명령어 (3 SP)
```
구현:
- argparse 기반 CLI
- 명령어:
  - start [--port] [--seed]
  - mine <address>
  - send <to> <amount>
  - balance [address]
  - lotto commit/claim
  - status

커밋: feat: [cli] 커맨드라인 인터페이스
```

#### T-41: Core 테스트 (2 SP)
```
구현:
- test_transaction: 생성, 직렬화, 서명
- test_block: 생성, 해시, 머클루트
- test_utxo: 추가, 제거, 잔액, apply/revert

커밋: test: [core] 핵심 자료구조 테스트
```

#### T-42: Crypto 테스트 (2 SP)
```
구현:
- test_hash: SHA256, HASH160 검증
- test_signature: 서명/검증
- test_address: 주소 생성/검증
- test_merkle: 머클 루트 계산

커밋: test: [crypto] 암호화 모듈 테스트
```

#### T-43: Network 테스트 (2 SP)
```
구현:
- test_protocol: 메시지 직렬화
- test_peer: 피어 연결 시뮬레이션
- test_handshake: VERSION/VERACK

커밋: test: [network] 네트워크 모듈 테스트
```

#### T-44: Gacha 테스트 (3 SP)
```
구현:
- test_commit_reveal: 해시 검증
- test_winning: 등수 판정
- test_pool: 보상 계산
- test_integration: Commit → Claim 전체 흐름

커밋: test: [gacha] 로또 시스템 테스트
```

---

## 스프린트 배치 (3일)

### Sprint 1 (Day 1) - 47 SP

| Story | Tasks | SP |
|-------|-------|---:|
| Core | T-01 ~ T-06 | 13 |
| Consensus | T-09, T-10, T-15 | 7 |
| Network | T-17, T-18, T-19 | 8 |
| Application | T-27, T-28, T-30 | 7 |
| Infra | T-37, T-38 | 6 |
| **Day 1 합계** | **16 tasks** | **41** |

### Sprint 2 (Day 2) - 53 SP

| Story | Tasks | SP |
|-------|-------|---:|
| Core | T-07, T-08 | 7 |
| Consensus | T-11, T-13, T-14 | 11 |
| Network | T-20, T-21, T-22 | 15 |
| Application | T-29, T-31, T-32, T-33 | 12 |
| Infra | T-39 | 5 |
| **Day 2 합계** | **14 tasks** | **50** |

### Sprint 3 (Day 3) - 43 SP

| Story | Tasks | SP |
|-------|-------|---:|
| Consensus | T-12, T-16 | 7 |
| Network | T-23, T-24, T-25, T-26 | 13 |
| Application | T-34, T-35, T-36 | 11 |
| Infra | T-40, T-41, T-42, T-43, T-44 | 12 |
| **Day 3 합계** | **14 tasks** | **43** |

---

## 번다운 차트

```
         SP remaining
    140 ┤■■■■■■■■■■■■■■■■■■■■■■■■■■■■
        │
     99 ┤              ■■■■■■■■■■■■■■■■■■■  (Day 1 완료)
        │
     49 ┤                          ■■■■■■■■■  (Day 2 완료)
        │
      0 ┤                                    ■  (Day 3 완료)
        └────────────────────────────────────
          Day 0      Day 1      Day 2      Day 3
```

---

## 체크리스트

### Day 1 완료 조건
- [ ] 트랜잭션 생성/서명 가능
- [ ] 피어 연결 가능
- [ ] 지갑 생성 가능

### Day 2 완료 조건
- [ ] 블록 채굴 가능
- [ ] UTXO 추적 동작
- [ ] RPC 잔액 조회 가능
- [ ] NAT 포트 매핑 동작

### Day 3 완료 조건
- [ ] Reorg 처리 동작
- [ ] 로또 Commit → Claim 가능
- [ ] 3노드 동기화 성공
- [ ] 모든 테스트 통과

---

## JIRA 임포트용 CSV

```csv
Summary,Issue Type,Epic Link,Story Points,Assignee,Status
Blockchain,Epic,,,Unassigned,To Do
Core (자료구조 + 암호화),Story,Blockchain,,A,To Do
전역 상수 정의,Task,Blockchain,1,A,To Do
해시 함수 (SHA256/HASH160),Task,Blockchain,2,A,To Do
ECDSA 서명/검증,Task,Blockchain,3,A,To Do
주소 생성 (Base58Check),Task,Blockchain,2,A,To Do
머클 트리,Task,Blockchain,2,A,To Do
트랜잭션 구조체,Task,Blockchain,3,A,To Do
블록 구조체,Task,Blockchain,2,A,To Do
UTXO 모델,Task,Blockchain,5,A,To Do
Consensus (합의 + 검증),Story,Blockchain,,B,To Do
난이도 조정 알고리즘,Task,Blockchain,3,B,To Do
PoW 채굴,Task,Blockchain,3,B,To Do
블록체인 관리,Task,Blockchain,5,B,To Do
Reorg 처리,Task,Blockchain,5,B,To Do
트랜잭션 검증,Task,Blockchain,3,B,To Do
블록 검증,Task,Blockchain,3,B,To Do
제네시스 블록,Task,Blockchain,1,B,To Do
Block Locator,Task,Blockchain,2,B,To Do
Network (P2P + 동기화),Story,Blockchain,,C,To Do
피어 데이터 구조,Task,Blockchain,2,C,To Do
프로토콜 메시지,Task,Blockchain,3,C,To Do
피어 발견,Task,Blockchain,3,C,To Do
NAT Traversal,Task,Blockchain,8,C,To Do
P2P 노드,Task,Blockchain,5,C,To Do
핸드셰이크,Task,Blockchain,2,C,To Do
메시지 핸들링,Task,Blockchain,3,C,To Do
IBD (블록 동기화),Task,Blockchain,3,C,To Do
TCP Hole Punching,Task,Blockchain,5,C,To Do
블록/TX 전파,Task,Blockchain,2,C,To Do
Application (로또 + 지갑 + 에셋),Story,Blockchain,,D,To Do
스크립트 OP 코드,Task,Blockchain,2,D,To Do
P2PKH 스크립트,Task,Blockchain,2,D,To Do
스크립트 인터프리터,Task,Blockchain,5,D,To Do
지갑 (키 관리),Task,Blockchain,3,D,To Do
TX 생성/서명,Task,Blockchain,3,D,To Do
JACK/POT 멀티 에셋,Task,Blockchain,2,D,To Do
JACK↔POT 교환,Task,Blockchain,2,D,To Do
Commit-Reveal 패턴,Task,Blockchain,3,D,To Do
잭팟 풀 관리,Task,Blockchain,3,D,To Do
로또 서비스,Task,Blockchain,5,D,To Do
Infra (CLI + RPC + 저장소 + 테스트),Story,Blockchain,,E,To Do
블록 저장소,Task,Blockchain,3,E,To Do
멤풀,Task,Blockchain,3,E,To Do
RPC 서버,Task,Blockchain,5,E,To Do
CLI 명령어,Task,Blockchain,3,E,To Do
Core 테스트,Task,Blockchain,2,E,To Do
Crypto 테스트,Task,Blockchain,2,E,To Do
Network 테스트,Task,Blockchain,2,E,To Do
Gacha 테스트,Task,Blockchain,3,E,To Do
```
