# JackpotChain 구현 명세서

> 기능별 구현 Step 가이드 (MVP 6주 기준)

---

## 개요

### 프로젝트 요약
- **목표**: 가챠 시스템이 내장된 UTXO 기반 블록체인
- **에셋**: JACK (네이티브 코인) + POT (가챠 토큰)
- **합의**: PoW (15초 블록 타임)
- **특징**: Commit-Reveal 기반 탈중앙화 가챠

### 기술 스택 (권장)
- **언어**: Python (MVP) → Rust (확장)
- **DB**: LevelDB / RocksDB
- **네트워크**: TCP 소켓 (P2P)
- **암호학**: ecdsa, hashlib (secp256k1)

---

## Step 1: 암호학 모듈 (1-2일)

### 1.1 해시 함수
```
파일: crypto/hash.py

구현 항목:
  □ sha256(data: bytes) -> bytes
  □ double_sha256(data: bytes) -> bytes  # 블록/TX 해시용
  □ hash160(data: bytes) -> bytes        # RIPEMD160(SHA256(x)) - 주소용

테스트:
  □ 빈 문자열 해시 검증
  □ Avalanche Effect 확인 (1비트 변경 → 완전히 다른 해시)
```

### 1.2 ECDSA 서명
```
파일: crypto/signature.py

구현 항목:
  □ generate_keypair() -> (private_key, public_key)
    - 곡선: secp256k1
    - 개인키: 256비트 랜덤
    - 공개키: 압축/비압축 포맷 지원

  □ sign(message_hash: bytes, private_key: bytes) -> bytes
    - DER 인코딩 + SIGHASH 타입 추가
    - RFC 6979 deterministic nonce 권장

  □ verify(message_hash: bytes, signature: bytes, public_key: bytes) -> bool

테스트:
  □ 서명 생성 후 검증 성공
  □ 메시지 변조 시 검증 실패
  □ 잘못된 공개키로 검증 실패
```

### 1.3 주소 생성
```
파일: crypto/address.py

구현 항목:
  □ pubkey_to_address(pubkey: bytes) -> str
    1. SHA256 해시
    2. RIPEMD160 해시
    3. 버전 바이트 추가 (0x4A = JACK)
    4. 체크섬 추가 (4바이트)
    5. Base58 인코딩

  □ validate_address(address: str) -> bool
    - 체크섬 검증
    - 버전 바이트 확인

주소 형식:
  - 일반 주소: JACKxxxx... (버전 0x4A)
  - P2SH 주소: JACK3xxx... (버전 0x4B)
  - 잭팟 풀: JACKPOT_POOL_ADDRESS (하드코딩)
  - 소각 주소: JACK_BURN_ADDRESS (하드코딩)
```

### 1.4 Merkle Tree
```
파일: crypto/merkle.py

구현 항목:
  □ build_merkle_tree(tx_hashes: List[bytes]) -> bytes
    - 홀수면 마지막 복제
    - 재귀적으로 상위 레벨 생성
    - 루트 반환

  □ get_merkle_proof(tx_hash: bytes, tx_hashes: List[bytes]) -> List[bytes]
    - SPV 증명용 sibling 해시 리스트

  □ verify_merkle_proof(tx_hash: bytes, proof: List[bytes], root: bytes) -> bool

테스트:
  □ TX 1개 → 루트 = 해당 TX 해시
  □ TX 4개 → 정상 트리 구성
  □ 증명 생성 및 검증
```

---

## Step 2: 데이터 구조 (2-3일)

### 2.1 트랜잭션 구조
```
파일: core/transaction.py

클래스: TxInput
  □ prev_tx_id: bytes (32)      # 이전 TX 해시
  □ output_index: int (4)       # Output 인덱스
  □ script_sig: bytes           # 서명 스크립트
  □ sequence: int (4)           # 시퀀스 번호

클래스: TxOutput
  □ jack_value: int (8)         # JACK 금액 (satoshi)
  □ assets: Dict[str, int]      # 추가 에셋 {"POT": amount}
  □ script_pubkey: bytes        # 잠금 스크립트

클래스: Transaction
  □ version: int (4)            # 1=일반, 2=Exchange, 3=Commit, 4=Reveal
  □ inputs: List[TxInput]
  □ outputs: List[TxOutput]
  □ locktime: int (4)

메서드:
  □ serialize() -> bytes        # 직렬화 (네트워크/저장용)
  □ deserialize(data: bytes) -> Transaction
  □ get_txid() -> bytes         # double_sha256(serialize())
  □ get_hash() -> bytes         # 서명용 해시 (SIGHASH 타입별)
```

### 2.2 블록 구조
```
파일: core/block.py

클래스: BlockHeader
  □ version: int (4)            # 프로토콜 버전
  □ prev_block_hash: bytes (32) # 이전 블록 해시
  □ merkle_root: bytes (32)     # TX 머클 루트
  □ timestamp: int (4)          # Unix timestamp
  □ difficulty_target: int (4)  # 난이도 (compact format)
  □ nonce: int (4)              # PoW 해답

클래스: Block
  □ header: BlockHeader
  □ transactions: List[Transaction]

메서드:
  □ serialize_header() -> bytes  # 80 bytes
  □ get_hash() -> bytes          # double_sha256(header)
  □ calculate_merkle_root() -> bytes
  □ verify_pow() -> bool         # hash < target
```

### 2.3 UTXO 구조
```
파일: core/utxo.py

클래스: UTXO
  □ tx_id: bytes (32)
  □ output_index: int
  □ jack_value: int
  □ assets: Dict[str, int]
  □ script_pubkey: bytes
  □ block_height: int           # 생성된 블록 높이

클래스: UTXOSet
  □ utxos: Dict[(tx_id, index), UTXO]

메서드:
  □ add_utxo(utxo: UTXO)
  □ remove_utxo(tx_id: bytes, index: int)
  □ get_utxo(tx_id: bytes, index: int) -> UTXO | None
  □ get_balance(address: str) -> Dict[str, int]  # 주소별 잔액
  □ get_jackpot_balance() -> int                 # 잭팟 풀 잔액
```

---

## Step 3: Script 시스템 (2-3일)

### 3.1 OP_CODE 정의
```
파일: script/opcodes.py

상수 정의:
  # 스택 조작
  □ OP_DUP = 0x76
  □ OP_DROP = 0x75
  □ OP_SWAP = 0x7c

  # 암호학
  □ OP_HASH160 = 0xa9
  □ OP_HASH256 = 0xaa
  □ OP_CHECKSIG = 0xac
  □ OP_CHECKMULTISIG = 0xae

  # 비교
  □ OP_EQUAL = 0x87
  □ OP_EQUALVERIFY = 0x88

  # 특수
  □ OP_RETURN = 0x6a
  □ OP_FALSE = 0x00
  □ OP_TRUE = 0x51
```

### 3.2 Script 인터프리터
```
파일: script/interpreter.py

클래스: ScriptInterpreter
  □ stack: List[bytes]

메서드:
  □ execute(script: bytes, tx: Transaction, input_index: int) -> bool
    - 스택 기반 실행
    - OP_CODE별 분기
    - 최종 스택 top이 true면 성공

  □ evaluate_p2pkh(sig: bytes, pubkey: bytes, pubkey_hash: bytes) -> bool
    - P2PKH 빠른 경로 (95% TX 커버)
```

### 3.3 표준 Script 생성
```
파일: script/standard.py

함수:
  □ create_p2pkh_scriptpubkey(pubkey_hash: bytes) -> bytes
    # OP_DUP OP_HASH160 <hash> OP_EQUALVERIFY OP_CHECKSIG

  □ create_p2pkh_scriptsig(signature: bytes, pubkey: bytes) -> bytes
    # <signature> <pubkey>

  □ create_op_return(data: bytes) -> bytes
    # OP_RETURN <data>

  □ is_p2pkh(script: bytes) -> bool
    # 패턴 매칭
```

---

## Step 4: PoW 합의 (2일)

### 4.1 난이도 관리
```
파일: consensus/difficulty.py

상수:
  □ TARGET_BLOCK_TIME = 15        # 목표 블록 간격 (초)
  □ DIFFICULTY_ADJUSTMENT_INTERVAL = 50  # 조절 주기 (블록)
  □ MAX_ADJUSTMENT_FACTOR = 4     # 최대 조절 배율

함수:
  □ compact_to_target(bits: int) -> int
    # 4바이트 compact → 256비트 target

  □ target_to_compact(target: int) -> int
    # 256비트 target → 4바이트 compact

  □ calculate_next_target(prev_target: int, actual_time: int, expected_time: int) -> int
    # 새 난이도 = 이전 난이도 × (실제시간 / 예상시간)
    # 4배 제한 적용
```

### 4.2 채굴
```
파일: consensus/miner.py

클래스: Miner
  □ mempool: Mempool
  □ blockchain: Blockchain

메서드:
  □ create_coinbase_tx(miner_address: str, fees: int, block_height: int) -> Transaction
    # 블록 보상 50 JACK + 수수료 분배 (50/30/20)
    # Output[0]: 채굴자 (50 + fees*50%)
    # Output[1]: 잭팟 풀 (fees*30%)
    # Output[2]: OP_RETURN 소각 (fees*20%)

  □ create_block_template(prev_block: Block) -> Block
    # Mempool에서 TX 선택
    # Coinbase TX 생성
    # Merkle Root 계산
    # 헤더 구성

  □ mine(block: Block) -> Block | None
    # nonce 0부터 시도
    # hash < target 찾기
    # 타임아웃 처리
```

### 4.3 체인 관리
```
파일: consensus/chain.py

클래스: Blockchain
  □ blocks: List[Block]
  □ utxo_set: UTXOSet
  □ orphan_blocks: Dict[hash, Block]

메서드:
  □ add_block(block: Block) -> bool
    # 블록 검증
    # 체인에 추가
    # UTXO Set 업데이트
    # 재구성 처리 (orphan)

  □ validate_block(block: Block) -> bool
    # 헤더 검증 (PoW, timestamp, prev_hash)
    # Merkle Root 검증
    # 모든 TX 검증

  □ get_longest_chain() -> List[Block]
    # Longest Chain Rule

  □ handle_fork(new_block: Block)
    # 포크 감지 및 해결
```

---

## Step 5: TX 검증 (2-3일)

### 5.1 기본 검증
```
파일: validation/transaction.py

함수:
  □ validate_tx_format(tx: Transaction) -> (bool, str)
    # 크기 제한 (< 1MB)
    # Input/Output 개수 > 0
    # 금액 범위 (0 < value < MAX_MONEY)
    # 중복 Input 없음

  □ validate_tx_context(tx: Transaction, utxo_set: UTXOSet, mempool: Mempool) -> (bool, str)
    # Input UTXO 존재 확인
    # 이중 지불 확인
    # 수수료 계산 및 최소 수수료 확인
```

### 5.2 에셋 검증
```
파일: validation/asset.py

함수:
  □ validate_asset_balance(tx: Transaction, utxo_set: UTXOSet) -> (bool, str)
    # JACK: Input >= Output + Fee
    # POT: Input >= Output (수수료 불가)
    # 각 에셋별 보존 법칙

  □ validate_min_jack(tx: Transaction) -> (bool, str)
    # 모든 Output에 MIN_JACK (0.01) 이상
    # OP_RETURN 제외
```

### 5.3 버전별 검증
```
파일: validation/tx_types.py

함수:
  □ validate_v1_transfer(tx: Transaction) -> (bool, str)
    # 에셋 보존 (Mint/Burn 없음)

  □ validate_v2_exchange(tx: Transaction) -> (bool, str)
    # burn_amount = Input JACK - Output JACK - fee
    # expected_pot = burn_amount / 100
    # actual_pot == expected_pot
    # OP_RETURN 소각 기록 확인
    # Input에 POT 없음 확인

  □ validate_v3_commit(tx: Transaction) -> (bool, str)
    # POT Burn (1 POT)
    # commit_hash 포함 확인
    # Commit UTXO 생성 확인

  □ validate_v4_reveal(tx: Transaction, blockchain: Blockchain) -> (bool, str)
    # Commit TX 참조 확인
    # SHA256(secret) == commit_hash
    # Reveal 기한 (50블록 이내)
    # 당첨 계산 검증
    # 잭팟 풀 지급 검증 (당첨 시)
```

### 5.4 서명 검증
```
파일: validation/signature.py

함수:
  □ validate_input_signature(tx: Transaction, input_index: int, utxo: UTXO) -> bool
    # script_sig + script_pubkey 결합
    # Script 실행
    # ECDSA 검증

  □ compute_sighash(tx: Transaction, input_index: int, prev_scriptpubkey: bytes, sighash_type: int) -> bytes
    # SIGHASH_ALL, NONE, SINGLE, ANYONECANPAY 처리
```

---

## Step 6: 멀티에셋 시스템 (2일)

### 6.1 에셋 정의
```
파일: asset/constants.py

상수:
  □ JACK_ASSET_ID = ""           # 빈 문자열 (네이티브)
  □ POT_ASSET_ID = "POT"
  □ EXCHANGE_RATE = 100          # 100 JACK = 1 POT
  □ MIN_JACK = 1_000_000         # 0.01 JACK (satoshi)
  □ BLOCK_REWARD = 50_00_000_000 # 50 JACK (satoshi)
```

### 6.2 시스템 주소
```
파일: asset/system.py

상수:
  □ JACKPOT_POOL_ADDRESS = "JACK_JACKPOT_POOL_xxxxx"
  □ BURN_ADDRESS = "JACK_BURN_xxxxx"

함수:
  □ is_system_address(address: str) -> bool
  □ is_jackpot_address(address: str) -> bool
  □ is_burn_address(address: str) -> bool
```

### 6.3 Exchange TX 생성
```
파일: asset/exchange.py

함수:
  □ create_exchange_tx(
      sender_utxos: List[UTXO],
      jack_amount: int,
      sender_address: str,
      private_key: bytes
    ) -> Transaction
    # version = 2
    # POT mint = jack_amount / 100
    # JACK 소각 (OP_RETURN)
    # 거스름돈 처리
```

---

## Step 7: 가챠 시스템 (3-4일)

### 7.1 Commit TX
```
파일: gacha/commit.py

함수:
  □ generate_secret() -> bytes
    # 32바이트 암호학적 랜덤

  □ create_commit_tx(
      sender_utxos: List[UTXO],
      secret: bytes,
      sender_address: str,
      private_key: bytes
    ) -> Transaction
    # version = 3
    # commit_hash = SHA256(secret)
    # POT 1개 소각
    # Commit UTXO 생성
```

### 7.2 Reveal TX
```
파일: gacha/reveal.py

상수:
  □ WIN_PROBABILITY = 0.01       # 1%
  □ PAYOUT_RATIO = 0.60          # 60%
  □ MIN_REVEAL_GAP = 2           # 최소 블록 간격
  □ MAX_REVEAL_GAP = 50          # Reveal 기한

함수:
  □ calculate_result(secret: bytes, commit_block_hash: bytes) -> int
    # result = SHA256(secret + commit_block_hash)
    # 256비트 정수로 변환

  □ is_winner(result: int) -> bool
    # result < 2^256 * WIN_PROBABILITY

  □ calculate_payout(jackpot_balance: int) -> int
    # payout = jackpot_balance * PAYOUT_RATIO

  □ create_reveal_tx(
      commit_utxo: UTXO,
      secret: bytes,
      commit_block_hash: bytes,
      jackpot_utxos: List[UTXO],  # 당첨 시에만
      player_address: str,
      private_key: bytes,
      blockchain: Blockchain
    ) -> Transaction
    # version = 4
    # secret 공개
    # 당첨 시 잭팟 풀에서 지급
```

### 7.3 가챠 검증
```
파일: gacha/validation.py

함수:
  □ validate_commit(tx: Transaction) -> (bool, str)
    # POT 소각 확인
    # commit_hash 형식 확인

  □ validate_reveal(tx: Transaction, blockchain: Blockchain) -> (bool, str)
    # Commit TX 참조 확인
    # 블록 간격 확인 (2 ~ 50)
    # secret 검증 (hash 일치)
    # 당첨 결과 재계산
    # 당첨금 = Commit 블록 시점 풀 잔액 기준
```

---

## Step 8: P2P 네트워크 (3-4일)

### 8.1 메시지 프로토콜
```
파일: network/protocol.py

메시지 타입:
  □ VERSION = 0x01      # 핸드셰이크
  □ VERACK = 0x02       # 버전 확인
  □ PING = 0x03
  □ PONG = 0x04
  □ GETADDR = 0x05      # 피어 요청
  □ ADDR = 0x06         # 피어 목록
  □ INV = 0x07          # 인벤토리 알림
  □ GETDATA = 0x08      # 데이터 요청
  □ TX = 0x09           # 트랜잭션
  □ BLOCK = 0x0a        # 블록
  □ GETHEADERS = 0x0b   # 헤더 요청
  □ HEADERS = 0x0c      # 헤더 목록
  □ GETBLOCKS = 0x0d    # 블록 해시 요청

클래스: Message
  □ magic: bytes (4)    # 네트워크 식별자
  □ command: int
  □ length: int
  □ checksum: bytes (4)
  □ payload: bytes
```

### 8.2 피어 관리
```
파일: network/peer.py

클래스: Peer
  □ ip: str
  □ port: int
  □ socket: socket
  □ version: int
  □ services: int
  □ last_seen: int
  □ misbehavior_score: int

클래스: PeerManager
  □ peers: List[Peer]
  □ max_outbound: int = 6
  □ max_inbound: int = 2

메서드:
  □ connect(ip: str, port: int) -> Peer
  □ disconnect(peer: Peer)
  □ broadcast(message: Message)
  □ handle_misbehavior(peer: Peer, reason: str)
```

### 8.3 노드
```
파일: network/node.py

클래스: Node
  □ blockchain: Blockchain
  □ mempool: Mempool
  □ peer_manager: PeerManager
  □ is_mining: bool

메서드:
  □ start()
  □ stop()
  □ handle_message(peer: Peer, message: Message)
  □ relay_tx(tx: Transaction)
  □ relay_block(block: Block)
```

### 8.4 블록 전파 (Gossip)
```
파일: network/propagation.py

함수:
  □ propagate_block(block: Block, peers: List[Peer])
    # INV 메시지 브로드캐스트
    # GETDATA 요청 처리
    # 중복 전파 방지

  □ propagate_tx(tx: Transaction, peers: List[Peer])
```

---

## Step 9: 동기화 (2-3일)

### 9.1 초기 블록 다운로드 (IBD)
```
파일: sync/ibd.py

클래스: IBDManager
  □ target_height: int
  □ current_height: int
  □ downloading: Set[hash]

메서드:
  □ start_ibd(peers: List[Peer])
    # 1. GETHEADERS로 헤더 다운로드
    # 2. 헤더 체인 검증
    # 3. 병렬 블록 다운로드
    # 4. 순차 블록 검증/적용

  □ download_headers(peer: Peer, start_hash: bytes) -> List[BlockHeader]

  □ download_blocks_parallel(block_hashes: List[bytes], peers: List[Peer])
```

### 9.2 체크포인트
```
파일: sync/checkpoint.py

상수:
  □ CHECKPOINTS = {
      0: "genesis_hash...",
      10000: "hash_at_10000...",
      # ...
    }

함수:
  □ is_checkpoint(height: int) -> bool
  □ verify_checkpoint(height: int, block_hash: bytes) -> bool
  □ should_skip_signature(height: int, latest_checkpoint: int) -> bool
    # 체크포인트 이전 블록은 서명 스킵 (IBD 최적화)
```

---

## Step 10: 저장소 (2일)

### 10.1 블록 저장소
```
파일: storage/blocks.py

클래스: BlockStore
  □ db: LevelDB

메서드:
  □ put_block(block: Block)
  □ get_block(hash: bytes) -> Block | None
  □ get_block_by_height(height: int) -> Block | None
  □ get_header(hash: bytes) -> BlockHeader | None
```

### 10.2 UTXO 저장소
```
파일: storage/utxo_db.py

클래스: UTXODatabase
  □ db: LevelDB
  □ cache: LRUCache         # 10,000 ~ 100,000 엔트리

메서드:
  □ put_utxo(utxo: UTXO)
  □ delete_utxo(tx_id: bytes, index: int)
  □ get_utxo(tx_id: bytes, index: int) -> UTXO | None
  □ batch_update(additions: List[UTXO], deletions: List[tuple])
  □ flush()
```

### 10.3 인덱스
```
파일: storage/index.py

클래스: AddressIndex
  □ 주소 → UTXO 목록 (잔액 조회용)

클래스: JackpotIndex
  □ 잭팟 주소 UTXO 전용 인덱스 (빠른 풀 잔액 조회)
```

---

## Step 11: Mempool (1일)

```
파일: mempool/mempool.py

클래스: Mempool
  □ txs: Dict[bytes, Transaction]  # txid → tx
  □ max_size: int = 300 * 1024 * 1024  # 300 MB

메서드:
  □ add_tx(tx: Transaction) -> bool
    # 검증 후 추가
    # 이중 지불 확인
    # 수수료율 기반 정렬

  □ remove_tx(txid: bytes)

  □ get_txs_for_block(max_size: int) -> List[Transaction]
    # 수수료율 높은 순으로 선택

  □ evict_low_fee_txs()
    # 상한 초과 시 퇴출

  □ remove_confirmed_txs(block: Block)
    # 블록에 포함된 TX 제거
```

---

## Step 12: 지갑 (2일)

### 12.1 키 관리
```
파일: wallet/keystore.py

클래스: KeyStore
  □ keys: Dict[address, (private_key, public_key)]

메서드:
  □ generate_key() -> str  # 주소 반환
  □ import_key(private_key: bytes) -> str
  □ export_key(address: str) -> bytes
  □ sign(address: str, message: bytes) -> bytes
  □ save(filepath: str, password: str)
  □ load(filepath: str, password: str)
```

### 12.2 잔액 조회
```
파일: wallet/balance.py

함수:
  □ get_balance(addresses: List[str], utxo_set: UTXOSet) -> Dict[str, Dict[str, int]]
    # 주소별, 에셋별 잔액

  □ get_utxos(addresses: List[str], utxo_set: UTXOSet) -> List[UTXO]
    # 지갑의 모든 UTXO
```

### 12.3 TX 생성
```
파일: wallet/builder.py

클래스: TransactionBuilder

메서드:
  □ build_transfer(
      from_address: str,
      to_address: str,
      jack_amount: int,
      pot_amount: int,
      utxos: List[UTXO],
      keystore: KeyStore
    ) -> Transaction

  □ build_exchange(
      address: str,
      jack_amount: int,
      utxos: List[UTXO],
      keystore: KeyStore
    ) -> Transaction

  □ build_gacha_commit(
      address: str,
      utxos: List[UTXO],
      keystore: KeyStore
    ) -> (Transaction, bytes)  # (tx, secret)

  □ build_gacha_reveal(
      commit_utxo: UTXO,
      secret: bytes,
      blockchain: Blockchain,
      keystore: KeyStore
    ) -> Transaction
```

---

## Step 13: RPC/API (2일)

```
파일: rpc/server.py

클래스: RPCServer

엔드포인트:
  # 블록체인 정보
  □ getblockchaininfo() -> dict
  □ getblock(hash) -> Block
  □ getblockheader(hash) -> BlockHeader
  □ getbestblockhash() -> str

  # TX
  □ gettransaction(txid) -> Transaction
  □ sendrawtransaction(hex) -> str  # txid
  □ getrawtransaction(txid) -> str  # hex

  # UTXO
  □ getutxo(txid, index) -> UTXO
  □ getbalance(address) -> dict

  # 가챠
  □ getjackpotbalance() -> int
  □ getgachastats() -> dict

  # 채굴
  □ getmininginfo() -> dict
  □ setmining(enabled: bool) -> bool

  # 네트워크
  □ getpeerinfo() -> list
  □ getconnectioncount() -> int

  # Mempool
  □ getmempoolinfo() -> dict
  □ getrawmempool() -> list
```

---

## Step 14: 테스트 (지속적)

### 14.1 단위 테스트
```
tests/
  □ test_crypto.py      # 해시, 서명, 주소
  □ test_transaction.py # TX 생성, 직렬화
  □ test_block.py       # 블록 생성, 검증
  □ test_script.py      # Script 실행
  □ test_validation.py  # TX/블록 검증
  □ test_exchange.py    # Exchange TX
  □ test_gacha.py       # Commit/Reveal
  □ test_utxo.py        # UTXO Set
```

### 14.2 통합 테스트
```
tests/integration/
  □ test_mining.py      # 채굴 → 블록 생성
  □ test_sync.py        # 노드 간 동기화
  □ test_fork.py        # 포크 해결
  □ test_gacha_flow.py  # 전체 가챠 플로우
```

### 14.3 시나리오 테스트
```
tests/scenarios/
  □ 이중 지불 시도
  □ 잘못된 블록 전파
  □ 채굴자 가챠 조작 시도
  □ 잭팟 풀 고갈 시나리오
```

---

## 구현 일정 (6주)

### Week 1: Foundation
- Day 1-2: Step 1 (암호학)
- Day 3-4: Step 2 (데이터 구조)
- Day 5: Step 3 (Script 기초)

### Week 2: Core
- Day 1-2: Step 3 완성 + Step 4 (PoW)
- Day 3-4: Step 5 (TX 검증)
- Day 5: Step 6 (멀티에셋)

### Week 3: Gacha + Network
- Day 1-2: Step 7 (가챠)
- Day 3-4: Step 8 (P2P 기초)
- Day 5: Step 8 완성

### Week 4: Sync + Storage
- Day 1-2: Step 9 (동기화)
- Day 3-4: Step 10 (저장소)
- Day 5: Step 11 (Mempool)

### Week 5: Wallet + API + CLI
- Day 1-2: Step 12 (지갑)
- Day 3-4: Step 13 (RPC)
- Day 5: Step 15 (CLI 기본)

### Week 6: 패키징 + Polish
- Day 1: Step 15 완성 (exe 패키징)
- Day 2: Step 16 (간단 대시보드) - 선택
- Day 3-4: 버그 수정 + 성능 최적화
- Day 5: 데모 준비 + 배포 패키지 생성

---

## 핵심 파라미터 요약

```
블록 타임:          15초
블록 크기:          1 MB
블록 보상:          50 JACK (고정)
난이도 조절 주기:   50 블록
최소 수수료:        0.01 JACK

수수료 분배:
  - 채굴자: 50%
  - 잭팟 풀: 30%
  - 소각: 20%

Exchange:
  - 비율: 100 JACK = 1 POT
  - 일방향 (역교환 불가)

가챠:
  - 비용: 1 POT
  - 당첨 확률: 1%
  - 당첨금: 풀의 60%
  - Reveal 기한: 50블록
  - 최소 간격: 2블록

최소 JACK:          0.01 JACK (UTXO당)
```

---

## Step 15: CLI & 패키징 (2일)

### 15.1 CLI 인터페이스
```
파일: cli/main.py

명령어 구조:
  jackpot [command] [options]

기본 명령어:
  □ jackpot start
      --mining              # 채굴 활성화
      --address <addr>      # 채굴 보상 주소
      --port <port>         # P2P 포트 (기본: 8333)
      --rpc-port <port>     # RPC 포트 (기본: 8332)
      --seeds <ip:port,...> # 시드 노드 목록
      --data-dir <path>     # 데이터 저장 경로

  □ jackpot stop           # 노드 중지

  □ jackpot status         # 현재 상태 출력
      - 블록 높이
      - 연결된 피어 수
      - 채굴 상태
      - 잭팟 풀 잔액

  □ jackpot wallet
      create                # 새 지갑 생성
      balance               # 잔액 조회
      send <to> <amount>    # JACK 전송
      exchange <amount>     # JACK → POT 교환
      gacha                 # 가챠 플레이

예시:
  # 채굴 노드 시작 (원라인!)
  jackpot start --mining --address JACKxxxx...

  # 일반 노드만 시작
  jackpot start

  # 시드 노드 지정해서 시작
  jackpot start --seeds 10.0.1.100:8333,10.0.1.101:8333
```

### 15.2 설정 파일
```
파일: config.yaml (또는 config.json)

# 기본 설정 파일 예시
network:
  port: 8333
  rpc_port: 8332
  seeds:
    - "10.0.1.100:8333"
    - "10.0.1.101:8333"

mining:
  enabled: true
  address: "JACKxxxx..."      # 보상 받을 주소
  threads: 4                   # 채굴 스레드 수

wallet:
  path: "./wallet.dat"

data:
  dir: "./data"

설정 우선순위:
  1. CLI 옵션 (최우선)
  2. 설정 파일
  3. 기본값
```

### 15.3 원클릭 채굴 모드
```
# 첫 실행 시 자동 설정
jackpot start --mining --auto-setup

자동 설정 동작:
  1. 지갑 없으면 → 자동 생성
  2. 주소 없으면 → 새 주소 생성
  3. 시드 노드 연결 시도
  4. IBD 시작 (동기화)
  5. 동기화 완료 후 채굴 시작

화면 출력:
  ╔══════════════════════════════════════════╗
  ║        JackpotChain Mining Node          ║
  ╠══════════════════════════════════════════╣
  ║ Status:     Mining ⛏️                     ║
  ║ Block:      12,345                       ║
  ║ Peers:      5                            ║
  ║ Hashrate:   1.2 MH/s                     ║
  ║ Your JACK:  150.00                       ║
  ║ Your POT:   3                            ║
  ║ Jackpot:    5,432 JACK                   ║
  ╚══════════════════════════════════════════╝

  [Press Q to quit, G for gacha, S for status]
```

### 15.4 exe 패키징 (Windows)
```
도구: PyInstaller

빌드 스크립트: build.py
  □ pyinstaller --onefile --name jackpot cli/main.py
  □ 아이콘 추가: --icon=jackpot.ico
  □ 콘솔 모드: --console

생성 파일:
  dist/
    jackpot.exe          # Windows 실행 파일 (단일 파일)

사용법:
  # 더블클릭 또는 cmd에서:
  jackpot.exe start --mining --auto-setup
```

### 15.5 플랫폼별 패키징
```
Windows:
  □ jackpot.exe (PyInstaller)
  □ 설치 프로그램 (Inno Setup) - 선택

macOS:
  □ jackpot (Unix 실행 파일)
  □ jackpot.app (앱 번들) - 선택

Linux:
  □ jackpot (바이너리)
  □ Docker 이미지 - 선택

배포 구조:
  jackpot-v1.0.0-win64.zip
    ├── jackpot.exe
    ├── config.yaml.example
    └── README.txt

  jackpot-v1.0.0-linux64.tar.gz
    ├── jackpot
    ├── config.yaml.example
    └── README.txt
```

### 15.6 Docker (선택)
```
파일: Dockerfile

FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 8333 8332
ENTRYPOINT ["python", "cli/main.py"]
CMD ["start"]

실행:
  docker run -d --name jackpot-node \
    -p 8333:8333 \
    -v jackpot-data:/app/data \
    jackpotchain/node start --mining
```

### 15.7 간편 실행 스크립트
```
Windows: start-mining.bat
  @echo off
  jackpot.exe start --mining --auto-setup
  pause

Linux/Mac: start-mining.sh
  #!/bin/bash
  ./jackpot start --mining --auto-setup

더블클릭만으로 채굴 시작!
```

---

## Step 16: 대시보드 UI (선택, 2일)

### 16.1 웹 대시보드
```
파일: dashboard/server.py

기술: Flask + HTML/CSS/JS (간단하게)

URL: http://localhost:8080

페이지:
  □ / (메인)
      - 노드 상태
      - 채굴 통계
      - 최근 블록
      - 잭팟 풀 현황

  □ /wallet
      - 잔액 (JACK, POT)
      - 거래 내역
      - 전송 폼
      - Exchange 폼

  □ /gacha
      - 가챠 플레이 버튼
      - 당첨 기록
      - 확률 통계

  □ /explorer
      - 블록 탐색
      - TX 조회
      - 주소 조회
```

### 16.2 터미널 UI (TUI)
```
도구: rich 또는 textual (Python)

실시간 대시보드:
  □ 블록/TX 카운터
  □ 해시레이트 그래프
  □ 피어 연결 상태
  □ 로그 스트림

인터랙티브 메뉴:
  [M] Mining On/Off
  [G] Play Gacha
  [W] Wallet
  [Q] Quit
```

---

## 참고: 파일 구조

```
jackpotchain/
├── crypto/
│   ├── hash.py
│   ├── signature.py
│   ├── address.py
│   └── merkle.py
├── core/
│   ├── transaction.py
│   ├── block.py
│   └── utxo.py
├── script/
│   ├── opcodes.py
│   ├── interpreter.py
│   └── standard.py
├── consensus/
│   ├── difficulty.py
│   ├── miner.py
│   └── chain.py
├── validation/
│   ├── transaction.py
│   ├── asset.py
│   ├── tx_types.py
│   └── signature.py
├── asset/
│   ├── constants.py
│   ├── system.py
│   └── exchange.py
├── gacha/
│   ├── commit.py
│   ├── reveal.py
│   └── validation.py
├── network/
│   ├── protocol.py
│   ├── peer.py
│   ├── node.py
│   └── propagation.py
├── sync/
│   ├── ibd.py
│   └── checkpoint.py
├── storage/
│   ├── blocks.py
│   ├── utxo_db.py
│   └── index.py
├── mempool/
│   └── mempool.py
├── wallet/
│   ├── keystore.py
│   ├── balance.py
│   └── builder.py
├── rpc/
│   └── server.py
├── cli/
│   ├── main.py            # CLI 진입점
│   ├── commands.py        # 명령어 처리
│   └── tui.py             # 터미널 UI
├── dashboard/
│   ├── server.py          # 웹 대시보드 서버
│   ├── templates/         # HTML 템플릿
│   └── static/            # CSS/JS
├── scripts/
│   ├── start-mining.bat   # Windows 간편 실행
│   ├── start-mining.sh    # Linux/Mac 간편 실행
│   └── build.py           # exe 빌드 스크립트
├── config.yaml.example    # 설정 파일 예시
└── tests/
    ├── test_*.py
    └── integration/
```

---

**작성일:** 2026-02-26
**기반 문서:** learning-roadmap Phase 0~4
