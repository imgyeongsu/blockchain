# 02. 데이터 구조 (Data Structures)

> **Phase 0: Foundation**  
> **학습 날짜:** 2025-02-12  
> **난이도:** ⭐⭐☆☆☆  
> **예상 소요 시간:** 1-2시간  
> **선행 학습:** [01. 암호학 기초](01-cryptography-basics.md)

---

## 🎯 학습 목표

이 문서를 완료하면:
- [ ] 블록 헤더의 6가지 필드를 설명할 수 있다
- [ ] prev_block_hash가 어떻게 체인을 형성하는지 이해한다
- [ ] Transaction의 Input/Output 구조를 안다
- [ ] UTXO 소비와 생성 과정을 설명할 수 있다
- [ ] 블록 검증 과정을 이해한다
- [ ] Genesis Block의 특별함을 안다

---

## 1. 전체 그림

### 1.1 블록체인 구조

**비유: 레고 블록 연결**
```
[Genesis Block] → [Block 1] → [Block 2] → [Block 3] → ...
     최초             ↑          ↑          ↑
                  이전 해시   이전 해시   이전 해시
```

**각 블록:**
```
블록 = 상자
  ├── 헤더 (겉면 라벨) - 80 bytes
  │   - 이전 블록 주소
  │   - 타임스탬프
  │   - 난이도
  │   - 등등...
  │
  └── 트랜잭션들 (내용물) - 가변 크기
      - TX 1
      - TX 2
      - ...
```

---

### 1.2 3가지 핵심 구조

```
1. Block Header (블록 헤더)
   → 블록의 메타데이터
   → 80 bytes (작음!)
   → SPV 노드는 이것만 다운로드

2. Transaction (트랜잭션)
   → 실제 거래 내역
   → 가변 크기 (~500 bytes)
   → Input/Output 구조

3. Chain (체인)
   → 블록들의 연결
   → prev_hash로 연결
   → 위변조 불가능
```

---

## 2. 블록 헤더 (Block Header)

### 2.1 왜 헤더가 중요한가?

**비유: 책의 목차**
```
책:
  - 목차 (2페이지) ← 빠르게 훑어보기
  - 본문 (500페이지) ← 자세한 내용

블록:
  - 헤더 (80 bytes) ← 빠른 검증
  - 트랜잭션들 (1 MB) ← 자세한 거래
```

**경량 노드(SPV) 장점:**
```
헤더만 다운로드:
  80 bytes × 1,000,000 블록 = 80 MB
  → 모바일에서도 가능! 📱

전체 블록 다운로드:
  1 MB × 1,000,000 블록 = 1 TB
  → 불가능... 💀
```

---

### 2.2 블록 헤더 구조 (JackpotChain)

```
Block Header (80 bytes):

┌─────────────────────────────────┐
│ version          (4 bytes)      │  버전 정보
├─────────────────────────────────┤
│ prev_block_hash  (32 bytes)     │  이전 블록 연결
├─────────────────────────────────┤
│ merkle_root      (32 bytes)     │  모든 TX의 지문
├─────────────────────────────────┤
│ timestamp        (4 bytes)      │  생성 시간
├─────────────────────────────────┤
│ difficulty_target (4 bytes)     │  채굴 난이도
├─────────────────────────────────┤
│ nonce            (4 bytes)      │  PoW 해답
└─────────────────────────────────┘

총합: 4 + 32 + 32 + 4 + 4 + 4 = 80 bytes
```

---

### 2.3 각 필드 상세

#### 1. version (4 bytes)

```
목적: 프로토콜 버전
값: 0x00000001

예시:
  version 1: 초기 버전
  version 2: 새로운 기능 추가
  
사용:
  노드가 블록을 어떻게 해석할지 결정
  
하위 호환성:
  version 2 노드는 version 1 블록도 처리 가능
```

---

#### 2. prev_block_hash (32 bytes)

```
목적: 이전 블록과 연결
값: SHA-256 해시 (32 bytes)

예시:
  Block 100의 prev_block_hash
  = hash(Block 99의 헤더)
  = "0000abc123def456..."

의미:
  - 체인 형성의 핵심
  - 이것 때문에 "블록체인"이라고 부름
  - 과거 블록 변조 시 감지 가능
```

**계산 방법:**
```
Block 99 Header:
  version + prev_hash + merkle_root + timestamp + target + nonce
  = 80 bytes

Hash:
  hash1 = SHA-256(header)
  hash2 = SHA-256(hash1)  ← Double SHA-256
  
Block 100의 prev_block_hash = hash2
```

---

#### 3. merkle_root (32 bytes)

```
목적: 모든 TX를 32 bytes로 요약
값: Merkle Tree의 Root Hash

예시:
  500개 TX (500 KB)
  → Merkle Tree 구성
  → Root Hash (32 bytes)

장점:
  1. 무결성: TX 하나라도 바뀌면 Root 바뀜
  2. 효율성: 32 bytes로 모든 TX 대표
  3. SPV: Merkle Proof로 TX 포함 증명
```

**계산:**
```
[TX1] [TX2] [TX3] [TX4]
  ↓     ↓     ↓     ↓
[H1]  [H2]  [H3]  [H4]  (Leaf)
  \   /      \   /
  [H12]      [H34]      (Branch)
    \         /
     [Root]             (Merkle Root)
```

---

#### 4. timestamp (4 bytes)

```
목적: 블록 생성 시간
값: Unix Timestamp (초 단위, 4 bytes)

예시:
  2026-02-12 14:30:00
  = 1739369400

범위:
  4 bytes = 0 ~ 2^32 - 1
  = 1970-01-01 ~ 2106-02-07
  
사용:
  - 난이도 조절 (블록 간격 계산)
  - 블록 순서 확인
  - 타임아웃 검증
```

**검증 규칙:**
```
1. 미래 시간 아님:
   timestamp <= 현재 시간 + 2시간

2. 이전 블록보다 늦음:
   timestamp > prev_block.timestamp

3. 중앙값 규칙 (Bitcoin):
   timestamp > median(최근 11블록 timestamp)
```

---

#### 5. difficulty_target (4 bytes)

```
목적: PoW 난이도 표시
값: 압축된 형태 (compact format)

의미:
  hash(block_header) < target이어야 유효
  
  target이 작을수록 어려움:
    0000FFFF... → 16개 0 (쉬움)
    00000FFF... → 20개 0 (어려움)
```

**Compact Format:**
```
4 bytes로 256 bits target 표현

예: 0x1d00ffff

구조:
  첫 1 byte (0x1d): 지수
  나머지 3 bytes (0x00ffff): 계수
  
계산:
  target = 0x00ffff × 2^(8 × (0x1d - 3))
```

**조절:**
```
JackpotChain:
  매 50 블록마다 조절
  목표: 15초 블록 타임 유지
  
계산:
  예상 시간 = 50 × 15초 = 750초
  실제 시간 = 실제로 걸린 시간
  
  새 target = 현재 target × (실제 / 예상)
```

---

#### 6. nonce (4 bytes)

```
목적: PoW 해답
값: 0 ~ 2^32 - 1 (약 42억)

채굴 과정:
  nonce = 0
  while True:
    hash = SHA-256(SHA-256(header))
    if hash < target:
      break  # 성공!
    nonce += 1
    if nonce >= 2^32:
      # 다른 필드 변경 (timestamp, merkle_root)
      nonce = 0

평균 시도 횟수:
  target = 0000FFFF...
  → 평균 2^16 = 65,536번 시도
  
  target = 00000FFF...
  → 평균 2^20 = 1,048,576번 시도
```

---

### 2.4 헤더 해시 계산

**블록의 ID = 헤더의 해시**

```
Block Hash = SHA-256(SHA-256(header))

의사코드:
  header = serialize(
    version,
    prev_block_hash,
    merkle_root,
    timestamp,
    difficulty_target,
    nonce
  )
  
  hash1 = SHA-256(header)
  hash2 = SHA-256(hash1)  ← Double SHA-256
  
  block_hash = hash2
```

**왜 두 번 해시?**
```
1. 보안 강화
   - Length Extension Attack 방어
   
2. Bitcoin 설계 방식
   - Satoshi의 선택
   - 이유는 명확하지 않음
   
3. 관례
   - 대부분의 블록체인이 따름
```

---

## 3. 트랜잭션 (Transaction)

### 3.1 UTXO 기반 구조

**개념:**
```
Transaction = Input(소비) + Output(생성)

Input: 기존 UTXO를 소비
Output: 새 UTXO를 생성

규칙:
  Σ(Inputs) >= Σ(Outputs) + Fee
```

**비유: 현금 거래**
```
Alice가 50,000원 지폐 1장 가짐
Bob에게 30,000원 주고 싶음

Input:
  - 50,000원 지폐 (소비)

Output:
  - Bob: 30,000원 (새 지폐)
  - Alice: 19,900원 (거스름돈)

수수료: 100원
```

---

### 3.2 Transaction 구조

```
Transaction:

┌──────────────────────────────────┐
│ version (4 bytes)                │  TX 버전
├──────────────────────────────────┤
│ input_count (varint)             │  Input 개수
├──────────────────────────────────┤
│ Inputs []                        │  
│   ┌──────────────────────────┐   │
│   │ prev_tx_id (32 bytes)    │   │  이전 TX
│   │ output_index (4 bytes)   │   │  어느 Output?
│   │ script_sig (가변)         │   │  서명
│   │ sequence (4 bytes)       │   │  시퀀스 번호
│   └──────────────────────────┘   │
├──────────────────────────────────┤
│ output_count (varint)            │  Output 개수
├──────────────────────────────────┤
│ Outputs []                       │
│   ┌──────────────────────────┐   │
│   │ value (8 bytes)          │   │  금액
│   │ script_pubkey (가변)     │   │  잠금 조건
│   └──────────────────────────┘   │
├──────────────────────────────────┤
│ locktime (4 bytes)               │  잠금 시간
└──────────────────────────────────┘

크기: 가변 (평균 ~500 bytes)
```

---

### 3.3 TxInput (입력)

**의미: "이 UTXO를 쓰겠다!"**

```
TxInput:
  - prev_tx_id: 32 bytes (어느 트랜잭션의)
  - output_index: 4 bytes (몇 번째 Output을)
  - script_sig: 가변 (서명 - 내가 주인임을 증명)
  - sequence: 4 bytes (나중에 설명)
```

**예시:**
```
Alice의 지갑:
  UTXO 1: 50 JACK
    from TX "abc123...", output index 0
    
  UTXO 2: 30 JACK
    from TX "def456...", output index 1

Alice → Bob 70 JACK 전송:

Input 1:
  prev_tx_id: "abc123..."
  output_index: 0
  script_sig: <Alice's signature>
  
Input 2:
  prev_tx_id: "def456..."
  output_index: 1
  script_sig: <Alice's signature>

총 Input: 50 + 30 = 80 JACK
```

**script_sig (서명):**
```
목적: UTXO 주인임을 증명

내용:
  - 서명 (signature)
  - 공개키 (public key)

검증:
  verify(signature, tx_hash, public_key)
  → true면 소비 가능
```

---

### 3.4 TxOutput (출력)

**의미: "이 사람에게 이만큼"**

```
TxOutput:
  - value: 8 bytes (금액, satoshi 단위)
  - script_pubkey: 가변 (잠금 조건)
```

**예시 (계속):**
```
Output 1 (Bob에게):
  value: 70 JACK
  script_pubkey: <Bob's address로 잠금>

Output 2 (거스름돈):
  value: 9.9 JACK
  script_pubkey: <Alice's address로 잠금>

총 Output: 70 + 9.9 = 79.9 JACK
수수료: 80 - 79.9 = 0.1 JACK
```

**script_pubkey (잠금):**
```
목적: UTXO를 잠금 (소유자만 열 수 있음)

P2PKH (Pay to Public Key Hash):
  OP_DUP
  OP_HASH160
  <공개키 해시>
  OP_EQUALVERIFY
  OP_CHECKSIG

의미:
  "이 공개키의 주인만 열 수 있음"
```

---

### 3.5 멀티에셋 UTXO (JackpotChain)

**차이점: Output에 여러 에셋**

```
TxOutput (JackpotChain):
  - assets: {
      "": 100,              // JACK (네이티브)
      "policy1.POT": 50,    // POT 토큰
      "policy2.NFT_123": 1  // NFT
    }
  - script_pubkey: 잠금 조건
```

**예시: Alice → Bob**
```
전송 내역:
  - 100 JACK
  - 50 POT
  - NFT #123

Transaction:
  Inputs: [
    {
      prev_tx: "abc...",
      index: 0,
      assets: {
        "": 150 JACK,
        "policy1.POT": 50,
        "policy2.NFT_123": 1
      }
    }
  ]
  
  Outputs: [
    {
      assets: {
        "": 100 JACK,
        "policy1.POT": 50,
        "policy2.NFT_123": 1
      },
      script_pubkey: "Bob's address"
    },
    {
      assets: {
        "": 49.9 JACK  // 거스름돈
      },
      script_pubkey: "Alice's address"
    }
  ]

검증:
  각 에셋마다 Input >= Output 확인
  JACK: 150 >= 100 + 49.9 + 0.1(fee) ✅
  POT: 50 >= 50 ✅
  NFT: 1 >= 1 ✅
```

---

### 3.6 Script 시스템

**간단 버전 (P2PKH):**

```
잠금 (script_pubkey):
  "공개키 해시가 이것과 일치하고
   올바른 서명이 있어야 함"

열쇠 (script_sig):
  "여기 서명과 공개키입니다"

검증:
  1. 공개키를 해시
  2. script_pubkey의 해시와 비교
  3. 서명 검증
  4. 모두 통과하면 소비 가능 ✅
```

**스택 기반 실행:**
```
Step 1: script_sig 실행
  Stack: [signature, pubkey]

Step 2: script_pubkey 실행
  OP_DUP: Stack: [signature, pubkey, pubkey]
  OP_HASH160: Stack: [signature, pubkey, hash(pubkey)]
  <pubkey_hash>: Stack: [signature, pubkey, hash(pubkey), expected_hash]
  OP_EQUALVERIFY: 비교 후 제거
  OP_CHECKSIG: 서명 검증
  
결과:
  Stack: [true] → 성공 ✅
  Stack: [false] → 실패 ❌
```

---

## 4. 체인 연결 (Blockchain)

### 4.1 체인의 핵심: prev_block_hash

**연결 구조:**
```
Block 0 (Genesis)
  ├─ hash: "0000abc..."
  └─ prev_hash: "0000000..." (없음)
       ↓
Block 1
  ├─ hash: "0000def..."
  └─ prev_hash: "0000abc..." ← Block 0 참조
       ↓
Block 2
  ├─ hash: "0000ghi..."
  └─ prev_hash: "0000def..." ← Block 1 참조
       ↓
Block 3
  ├─ hash: "0000jkl..."
  └─ prev_hash: "0000ghi..." ← Block 2 참조
```

---

### 4.2 체인 검증

**정방향 검증:**
```
Block 0 → Block 1 → Block 2 → Block 3

각 블록:
  1. 헤더 해시 계산
     block_hash = SHA-256(SHA-256(header))
  
  2. 다음 블록의 prev_hash와 비교
     block_1.prev_hash == block_0.hash?
  
  3. 일치하면 연결됨 ✅
```

**역방향 검증:**
```
Block 3 ← Block 2 ← Block 1 ← Block 0

각 블록:
  1. prev_hash로 이전 블록 찾기
  
  2. 이전 블록 해시 계산
  
  3. prev_hash와 일치하면 ✅
```

---

### 4.3 위변조 감지

**시나리오: Block 1 데이터 변조**

```
변조 전:
  Block 1:
    transactions: [TX A, TX B]
    merkle_root: "1234..."
    hash: "0000def..."
    
  Block 2:
    prev_hash: "0000def..." ✅

변조 후:
  Block 1:
    transactions: [TX A, TX C]  (TX B → TX C)
    merkle_root: "5678..."  (바뀜!)
    hash: "0000xyz..."  (바뀜!)
    
  Block 2:
    prev_hash: "0000def..."  (그대로)
    
  불일치! ❌
```

**연쇄 반응 (Cascading Effect):**
```
Block 1 변조
  ↓
Block 1 hash 변경
  ↓
Block 2 prev_hash 불일치
  ↓
Block 2도 재작성 필요
  ↓
Block 2 hash 변경
  ↓
Block 3 prev_hash 불일치
  ↓
...

결과:
  모든 후속 블록을 재계산해야 함
  = 모든 PoW를 다시 풀어야 함
  = 계산 비용 막대함
  = 사실상 불가능
```

---

### 4.4 Genesis Block (창세 블록)

**특별한 첫 블록:**

```
Genesis Block:
  - block_height: 0
  - prev_block_hash: "0000000...000" (0으로 채움)
  - 하드코딩됨 (소스코드에 박혀있음)
  - 변경 불가능

JackpotChain Genesis:
  version: 1
  prev_block_hash: "0000000...000"
  merkle_root: "abc123..." (Coinbase TX만)
  timestamp: 1735689600 (2026-01-01 00:00:00 UTC)
  difficulty_target: 0x1d00ffff (최저 난이도)
  nonce: 0
  
  transactions: [
    Coinbase TX: 50 JACK → Genesis 주소
  ]
  
  message: "JackpotChain Genesis - 2026"
```

**하드코딩 예시:**
```python
GENESIS_BLOCK = {
    "version": 1,
    "prev_block_hash": "0" * 64,
    "merkle_root": "abc123...",
    "timestamp": 1735689600,
    "difficulty_target": 0x1d00ffff,
    "nonce": 0
}

def is_genesis(block):
    return block.height == 0
```

---

## 5. 블록 생성 과정

### 5.1 채굴자 관점

```
Step 1: TX 수집
  - Mempool에서 TX 선택
  - 수수료 높은 것 우선 (fee/byte)
  - 블록 크기 제한 (1 MB)

Step 2: Coinbase TX 생성
  Input: 없음 (새로 발행)
  Output: 
    - 블록 보상: 50 JACK
    - TX 수수료 합계
    - 총: 50 + fees

Step 3: Merkle Tree 계산
  [Coinbase, TX1, TX2, ...] → Merkle Root

Step 4: 블록 헤더 구성
  version: 1
  prev_block_hash: get_latest_block().hash
  merkle_root: 위에서 계산
  timestamp: current_time()
  difficulty_target: get_current_difficulty()
  nonce: 0

Step 5: PoW (채굴)
  while True:
    header = serialize(헤더)
    hash = SHA-256(SHA-256(header))
    
    if hash < target:
      print("블록 발견!")
      break
    
    nonce += 1
    
    if nonce >= 2^32:
      # nonce 소진
      timestamp += 1  (또는 TX 재배치)
      nonce = 0

Step 6: 블록 전파
  broadcast(new_block)
```

---

### 5.2 검증자 관점

```
Step 1: 블록 수신
  receive(new_block)

Step 2: 헤더 검증
  ✅ version 확인 (지원하는 버전?)
  ✅ prev_block_hash 확인 (체인 연결?)
  ✅ timestamp 검증 (미래 아님? 이전보다 늦음?)
  ✅ difficulty_target 검증 (올바른 난이도?)
  ✅ PoW 검증 (hash < target?)

Step 3: Merkle Root 검증
  계산한 merkle_root == 헤더의 merkle_root?

Step 4: TX 검증 (각각)
  for tx in block.transactions:
    ✅ Input UTXO 존재?
    ✅ 서명 유효?
    ✅ script 실행 성공?
    ✅ Input 합 >= Output 합 + 수수료?
    ✅ 이중 지불 아님?
    ✅ 멀티에셋: 각 에셋 balance 확인

Step 5: 블록 추가
  if 모든 검증 통과:
    - 블록을 체인에 추가
    - UTXO Set 업데이트
      - Input UTXO 제거
      - Output UTXO 추가
    - Mempool에서 포함된 TX 제거
    - 블록 전파 (다른 노드에게)
  else:
    - 블록 거부
    - 피어에게 경고
```

---

## 6. 실전 예시

### 6.1 Block #100

```
=== Block Header ===
version: 1
prev_block_hash: "0000a1b2c3d4e5f6789012345678901234567890..."
merkle_root: "1234567890abcdef1234567890abcdef12345678..."
timestamp: 1739369400 (2026-02-12 14:30:00 UTC)
difficulty_target: 0x1d00ffff
nonce: 2847563

=== Block Body ===
transaction_count: 501

Transactions:
  [0] Coinbase:
      Outputs: [50 JACK → Miner's address]
      
  [1] Alice → Bob:
      Inputs: [150 JACK from prev TX]
      Outputs: [100 JACK → Bob, 49.9 JACK → Alice]
      Fee: 0.1 JACK
      
  [2] Bob → Charlie:
      Inputs: [100 JACK from TX[1]]
      Outputs: [50 JACK → Charlie, 49.98 JACK → Bob]
      Fee: 0.02 JACK
      
  ...
  
  [500] Gacha TX:
      Inputs: [10 POT]
      Outputs: [NFT #456 → Player]

=== Block Stats ===
size: 1,048,576 bytes (1 MB)
block_hash: "0000def7890123456789012345678901234567890..."
```

---

### 6.2 Transaction 예시

```
=== Transaction Detail ===
tx_id: "789ghi012345jkl678901234567890..."
version: 1

Inputs (2):
  [0]
    prev_tx_id: "abc123..."
    output_index: 0
    script_sig: 
      <signature: 304502...>
      <pubkey: 02a1b2c3...>
    sequence: 0xffffffff
    
  [1]
    prev_tx_id: "def456..."
    output_index: 1
    script_sig:
      <signature: 3045...>
      <pubkey: 02a1...>
    sequence: 0xffffffff

Outputs (2):
  [0]
    value: 100 JACK (10,000,000,000 satoshi)
    script_pubkey:
      OP_DUP
      OP_HASH160
      <pubkey_hash: 1a2b3c...>
      OP_EQUALVERIFY
      OP_CHECKSIG
    
  [1]
    value: 49.9 JACK (4,990,000,000 satoshi)
    script_pubkey:
      OP_DUP
      OP_HASH160
      <pubkey_hash: 4d5e6f...>
      OP_EQUALVERIFY
      OP_CHECKSIG

locktime: 0

=== Verification ===
Input total: 150 JACK
Output total: 149.9 JACK
Fee: 0.1 JACK ✅
```

---

## 7. 핵심 요약

### 7.1 블록 헤더 (80 bytes)

```
6가지 필드:
  1. version (4): 프로토콜 버전
  2. prev_block_hash (32): 체인 연결
  3. merkle_root (32): TX 요약
  4. timestamp (4): 시간
  5. difficulty_target (4): 난이도
  6. nonce (4): PoW 해답
```

---

### 7.2 트랜잭션

```
구조:
  Inputs (소비) + Outputs (생성)

규칙:
  Σ Inputs >= Σ Outputs + Fee

멀티에셋:
  각 에셋마다 balance 확인
```

---

### 7.3 체인 연결

```
메커니즘:
  prev_block_hash로 연결

보안:
  위변조 시 모든 후속 블록 재계산 필요
  = PoW 다시 풀기
  = 사실상 불가능
```

---

## 8. 데이터 흐름도

```
사용자
  ↓ TX 생성
Mempool
  ↓ 채굴자 선택
Merkle Tree
  ↓ Root 계산
블록 헤더
  ↓ PoW
새 블록
  ↓ 전파
검증
  ↓ 성공
체인 추가
  ↓
UTXO Set 업데이트
```

---

## 9. 체크리스트

이해했는지 확인:

- [ ] 블록 헤더 6가지 필드를 말할 수 있다
- [ ] prev_block_hash의 역할 (체인 연결)
- [ ] merkle_root의 역할 (TX 요약)
- [ ] PoW에서 nonce의 역할
- [ ] Transaction Input/Output 구조
- [ ] UTXO 소비와 생성 과정
- [ ] script_sig와 script_pubkey의 차이
- [ ] 체인 검증 방법 (정방향/역방향)
- [ ] 위변조가 감지되는 원리
- [ ] Genesis Block의 특별함

---

## 10. 다음 학습

### 학습 완료:
- ✅ 암호학 기초 (해시, ECDSA, Merkle)
- ✅ 주소 생성 (RIPEMD-160, Base58)
- ✅ UTXO vs Account 모델
- ✅ 데이터 구조 (Block, TX, Chain)

### 다음 추천:
```
→ [05. 트랜잭션 심화](../phase-1-core/05-transactions-deep-dive.md)
  - Script 언어 상세
  - 서명 생성/검증
  - P2PKH, P2SH, MultiSig

→ [06. PoW 합의](../phase-1-core/06-pow-consensus.md)
  - 채굴 상세
  - 난이도 조절 알고리즘
  - Longest Chain Rule
  - 포크 해결

→ [04. 블록 & 블록체인](../phase-1-core/04-blocks-and-blockchain.md)
  - 블록 생성 전체 과정
  - 검증 상세
  - 체인 관리
```

---

## 11. 참고 자료

**Bitcoin 문서:**
- Bitcoin Developer Guide - Block Chain
- Bitcoin Wiki - Protocol Documentation
- Mastering Bitcoin - Chapter 6

**구현:**
- Bitcoin Core Source (C++)
- btcd (Go)
- python-bitcoinlib

**도구:**
- Blockchain Explorer (블록 구조 확인)
- Bitcoin Block Parser

---

**이전:** [01. 암호학 기초](01-cryptography-basics.md)  
**다음:** [04. 블록 & 블록체인](../phase-1-core/04-blocks-and-blockchain.md) →
