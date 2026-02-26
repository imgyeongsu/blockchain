# 05. 트랜잭션 심화 (Transactions Deep Dive)

> **Phase 1: Core**  
> **학습 날짜:** 2025-02-12  
> **난이도:** ⭐⭐⭐☆☆  
> **예상 소요 시간:** 2-3시간  
> **선행 학습:** [02. 데이터 구조](../phase-0-foundation/02-data-structures.md)

---

## 🎯 학습 목표

이 문서를 완료하면:
- [ ] Script 언어의 작동 방식을 이해한다
- [ ] P2PKH Script 실행 과정을 단계별로 설명할 수 있다
- [ ] 트랜잭션 서명 생성/검증 과정을 안다
- [ ] P2SH의 개념과 장점을 이해한다
- [ ] MultiSig의 사용처를 알고 구현할 수 있다
- [ ] SIGHASH 타입별 차이를 설명할 수 있다
- [ ] 트랜잭션 검증 전체 플로우를 이해한다

---

## 1. Script 언어 기초

### 1.1 왜 Script가 필요한가?

**문제 상황:**
```
"Alice가 Bob에게 100 JACK 전송"

구현 요구사항:
  - Alice만 보낼 수 있어야 함
  - Bob만 받을 수 있어야 함
  - 중간에 변조 불가능
  - 프로그램적으로 검증 가능
```

**해결책: Script**
```
UTXO에 "잠금 조건"을 프로그램으로 첨부
→ 조건을 만족해야만 소비 가능

비유: 금고의 자물쇠
  - script_pubkey = 자물쇠 (잠금 조건)
  - script_sig = 열쇠 (해제 방법)
  - Script 실행 = 열쇠가 맞는지 확인
```

---

### 1.2 Script 실행 방식

**스택 기반 언어:**
```
스택 = 접시 쌓기

기본 연산:
  push: 위에 올리기
  pop: 위에서 빼기

예시:
  push 5 → Stack: [5]
  push 3 → Stack: [5, 3]
  ADD → Stack: [8]  (5+3을 계산)
```

**Bitcoin Script 특징:**
```
✅ 스택 기반 (Stack-based)
✅ 튜링 불완전 (무한 루프 불가능)
✅ 상태 없음 (Stateless)
✅ 결정론적 (같은 입력 → 같은 결과)

❌ 변수 없음
❌ 함수 정의 불가
❌ 복잡한 제어 흐름 불가
❌ 외부 상태 접근 불가

이유:
  - 검증 속도 (빠름)
  - 보안 (예측 가능)
  - 결정론적 (노드마다 같은 결과)
```

---

### 1.3 기본 OP_CODE

**스택 조작:**
```
OP_DUP: 맨 위 복제
  입력: [5]
  출력: [5, 5]

OP_DROP: 맨 위 제거
  입력: [5, 3]
  출력: [5]

OP_SWAP: 위 두 개 교환
  입력: [5, 3]
  출력: [3, 5]

OP_ROT: 세 번째를 맨 위로
  입력: [a, b, c]
  출력: [b, c, a]
```

**산술 연산:**
```
OP_ADD: 덧셈
  입력: [5, 3]
  출력: [8]

OP_SUB: 뺄셈
  입력: [5, 3]
  출력: [2]

OP_EQUAL: 같은지 확인
  입력: [5, 5]
  출력: [1]  (true)
  
  입력: [5, 3]
  출력: [0]  (false)

OP_EQUALVERIFY: 같은지 확인 후 실패 시 중단
  입력: [5, 5]
  출력: []  (계속 진행)
  
  입력: [5, 3]
  출력: 실패! ❌
```

**암호학 연산:**
```
OP_HASH160: RIPEMD160(SHA256(x))
  입력: [data]
  출력: [hash]  (20 bytes)

OP_HASH256: SHA256(SHA256(x))
  입력: [data]
  출력: [hash]  (32 bytes)

OP_CHECKSIG: 서명 검증
  입력: [signature, pubkey]
  출력: [1] or [0]
  
  동작: verify(signature, message, pubkey)
```

---

## 2. P2PKH (Pay to Public Key Hash)

### 2.1 개념

**의미:**
```
"공개키 해시의 주인에게 지불"

UTXO 생성 시 (송금자):
  "이 공개키 해시를 가진 사람만 쓸 수 있음"
  → script_pubkey에 해시 포함

UTXO 소비 시 (수신자):
  "여기 제 공개키와 서명이요"
  → script_sig에 공개키 + 서명 제공
```

---

### 2.2 P2PKH Script 구조

**잠금 (script_pubkey):**
```
OP_DUP
OP_HASH160
<pubkey_hash>  (20 bytes)
OP_EQUALVERIFY
OP_CHECKSIG

크기: 약 25 bytes
```

**열쇠 (script_sig):**
```
<signature>  (64-72 bytes)
<pubkey>     (33 bytes)

크기: 약 100 bytes
```

---

### 2.3 실행 과정 (단계별 상세)

**초기 상태:**
```
Combined Script:
  <sig> <pubkey> OP_DUP OP_HASH160 <hash> OP_EQUALVERIFY OP_CHECKSIG

Stack: []
```

---

**Step 1: <sig> 푸시**
```
Remaining: <pubkey> OP_DUP OP_HASH160 <hash> OP_EQUALVERIFY OP_CHECKSIG
Stack: [sig]
```

---

**Step 2: <pubkey> 푸시**
```
Remaining: OP_DUP OP_HASH160 <hash> OP_EQUALVERIFY OP_CHECKSIG
Stack: [sig, pubkey]
```

---

**Step 3: OP_DUP (복제)**
```
동작: 맨 위 요소 복제

Remaining: OP_HASH160 <hash> OP_EQUALVERIFY OP_CHECKSIG
Stack: [sig, pubkey, pubkey]
```

---

**Step 4: OP_HASH160 (해시)**
```
동작: 맨 위 요소를 HASH160(RIPEMD160(SHA256))

Remaining: <hash> OP_EQUALVERIFY OP_CHECKSIG
Stack: [sig, pubkey, hash(pubkey)]
```

---

**Step 5: <hash> 푸시**
```
Remaining: OP_EQUALVERIFY OP_CHECKSIG
Stack: [sig, pubkey, hash(pubkey), expected_hash]
```

---

**Step 6: OP_EQUALVERIFY (비교)**
```
동작:
  1. 위 두 요소 팝
  2. 같은지 비교
  3. 다르면 실패 ❌
  4. 같으면 계속

Remaining: OP_CHECKSIG
Stack: [sig, pubkey]

비교:
  hash(pubkey) == expected_hash?
  
  일치: 계속 진행 ✅
  불일치: 즉시 실패 ❌ (EQUALVERIFY의 VERIFY 부분)
```

---

**Step 7: OP_CHECKSIG (서명 검증)**
```
동작:
  1. signature, pubkey 팝
  2. TX 메시지 해시 계산
  3. ECDSA 검증
  4. 결과 푸시

Remaining: (없음)
Stack: [1] or [0]

검증:
  verify(sig, tx_hash, pubkey)
  
  성공: Stack = [1] ✅
  실패: Stack = [0] ❌

최종 판단:
  Stack이 [1]이면 → UTXO 소비 가능
  그 외 → 실패
```

---

### 2.4 시각화

```
Script 실행 흐름:

      sig, pubkey 제공
            ↓
      [sig, pubkey]
            ↓ OP_DUP
    [sig, pubkey, pubkey]
            ↓ OP_HASH160
  [sig, pubkey, hash(pubkey)]
            ↓ push expected_hash
[sig, pubkey, hash(pubkey), expected_hash]
            ↓ OP_EQUALVERIFY
      [sig, pubkey]  (일치 확인)
            ↓ OP_CHECKSIG
          [1]  (서명 검증 성공)
            ↓
        UTXO 소비 가능! ✅
```

---

### 2.5 왜 공개키 해시를 쓰는가?

**공개키 직접 vs 공개키 해시:**

**P2PK (Pay to Public Key):**
```
script_pubkey: <pubkey> OP_CHECKSIG

장점:
  - 간단함 (짧음)
  - 실행 빠름

단점:
  - 공개키 노출 (33 bytes)
  - 주소가 김
  - 양자 컴퓨터 취약
    → 공개키만 있으면 개인키 복구 가능 (미래)
```

**P2PKH (Pay to Public Key Hash):**
```
script_pubkey: OP_DUP OP_HASH160 <hash> OP_EQUALVERIFY OP_CHECKSIG

장점:
  - 주소가 해시 (20 bytes)
  - 공개키 숨김 (사용 전까지)
  - 양자 컴퓨터 저항성 증가
    → UTXO 소비하기 전까지 공개키 모름
  - 주소 형식 통일

단점:
  - 약간 복잡
  - 실행 느림 (무시할 수준)
```

**결론:**
```
P2PKH가 표준
→ 보안성 > 효율성
→ Bitcoin, JackpotChain 모두 사용
```

---

## 3. 서명 생성/검증 과정

### 3.1 서명할 메시지 만들기

**문제:**
```
TX를 서명하려면 TX 전체를 서명해야 함
그런데... script_sig에 서명을 넣어야 함
→ 서명이 아직 없는데 서명을 만들어야 함? 🤔
```

**해결: 서명 전 TX 재구성**
```
서명 생성 시:
  1. script_sig를 빈 칸으로 (또는 제거)
  2. 이전 UTXO의 script_pubkey를 임시로 넣기
  3. 직렬화
  4. 해시
  5. 서명 생성
  6. 원래 script_sig 위치에 서명 넣기
```

---

### 3.2 서명 과정 (상세 예시)

**시나리오:**
```
Alice → Bob 100 JACK 전송

Alice의 UTXO:
  TX ID: abc123...
  Output Index: 0
  Value: 150 JACK
  script_pubkey: <Alice's P2PKH>
```

---

**Step 1: 원본 TX 구성**
```
TX:
  version: 1
  
  inputs: [
    {
      prev_tx_id: "abc123...",
      output_index: 0,
      script_sig: ""  ← 아직 비어있음
      sequence: 0xffffffff
    }
  ]
  
  outputs: [
    {
      value: 100 JACK,
      script_pubkey: <Bob's P2PKH>
    },
    {
      value: 49.9 JACK,
      script_pubkey: <Alice's P2PKH>  (거스름돈)
    }
  ]
  
  locktime: 0
```

---

**Step 2: 서명용 TX 만들기**
```
TX (서명용):
  inputs: [
    {
      prev_tx_id: "abc123...",
      output_index: 0,
      script_sig: <이전 UTXO의 script_pubkey>  ← 임시로 넣기!
      sequence: 0xffffffff
    }
  ]
  
  outputs: [...]  (동일)
  
  locktime: 0
  sighash_type: SIGHASH_ALL (0x01)
```

---

**Step 3: 직렬화 & 해시**
```
tx_bytes = serialize(tx)

예시 (간략):
  01000000  (version)
  01        (input count)
  abc123... (prev_tx_id)
  00000000  (output_index)
  ...       (script_pubkey 내용)
  ffffffff  (sequence)
  02        (output count)
  ...       (outputs)
  00000000  (locktime)
  01000000  (sighash_type)

hash = SHA-256(SHA-256(tx_bytes))
```

---

**Step 4: ECDSA 서명 생성**
```
signature = sign(hash, Alice_private_key)

ECDSA 과정:
  1. k = random nonce (RFC 6979)
  2. R = k × G
  3. r = R.x mod n
  4. s = k⁻¹(hash + r × private_key) mod n
  5. signature = (r, s)

DER 인코딩:
  30 [length] 02 [r_len] [r] 02 [s_len] [s] 01
                                           ↑ sighash_type

크기: 약 71-73 bytes
```

---

**Step 5: script_sig 구성**
```
script_sig:
  <signature> <Alice_pubkey>
  
  순서 중요!
    먼저 signature, 나중에 pubkey
```

---

**Step 6: 최종 TX**
```
TX (최종):
  inputs: [
    {
      prev_tx_id: "abc123...",
      output_index: 0,
      script_sig: <signature> <Alice_pubkey>  ← 완성!
      sequence: 0xffffffff
    }
  ]
  
  outputs: [...]

이제 전파 가능!
```

---

### 3.3 검증 과정 (노드 관점)

**노드가 TX를 받았을 때:**

---

**Step 1: 이전 UTXO 찾기**
```
prev_tx_id = "abc123..."
output_index = 0

UTXO Set에서 검색:
  UTXO = {
    value: 150 JACK,
    script_pubkey: <Alice's P2PKH>
  }

없으면 → 실패 ❌
```

---

**Step 2: Script 실행**
```
Combined Script:
  script_sig + script_pubkey
  = <signature> <pubkey> + OP_DUP OP_HASH160 <hash> OP_EQUALVERIFY OP_CHECKSIG

실행:
  (위에서 본 P2PKH 7단계)

결과: [1] 또는 [0]
```

---

**Step 3: 서명 검증을 위한 TX 재구성**
```
노드가 서명 생성 시와 동일한 방식으로 TX 재구성:
  1. script_sig 제거
  2. script_pubkey 넣기
  3. 직렬화
  4. 해시 계산

hash = SHA-256(SHA-256(tx_bytes))
```

---

**Step 4: ECDSA 서명 검증**
```
verify(signature, hash, pubkey)

ECDSA 검증 과정:
  1. signature에서 (r, s) 추출
  2. w = s⁻¹ mod n
  3. u₁ = hash × w mod n
  4. u₂ = r × w mod n
  5. P = u₁ × G + u₂ × pubkey
  6. v = P.x mod n
  7. v == r? → 성공 ✅

실패 시 → TX 거부 ❌
```

---

**Step 5: 최종 판단**
```
모든 검증 통과:
  - Script 실행 성공 ([1])
  - 서명 검증 성공
  - Balance 확인 (Input >= Output + Fee)

→ TX 유효! UTXO 소비 가능 ✅
```

---

## 4. P2SH (Pay to Script Hash)

### 4.1 왜 필요한가?

**P2PKH의 한계:**
```
간단한 조건만 가능:
  - 한 사람의 서명
  
불가능한 것:
  - 2-of-3 MultiSig (3명 중 2명 서명)
  - Time Lock (일정 시간 후)
  - 복잡한 비즈니스 로직
```

**해결책: P2SH**
```
"스크립트의 해시에게 지불"

아이디어:
  송금자 → 복잡한 조건 몰라도 됨
           해시만 알면 됨
  
  수신자 → 복잡한 조건 직접 제시
           조건 만족하면 받음
```

---

### 4.2 P2SH 장점

```
✅ 송금자 부담 감소
  - 복잡한 Script 몰라도 됨
  - 주소(해시)만 있으면 됨
  - TX 크기 작음

✅ 수신자 유연성
  - 원하는 조건 자유롭게
  - MultiSig, Time Lock 등
  - 조건 변경 가능 (해시만 같으면)

✅ 주소 형식 통일
  - P2PKH와 길이 동일 (20 bytes)
  - 호환성 좋음

JackpotChain:
  버전 바이트: 0x4B
  주소 prefix: JACK3...
```

---

### 4.3 P2SH Script 구조

**잠금 (script_pubkey):**
```
OP_HASH160
<script_hash>  (20 bytes)
OP_EQUAL

크기: 23 bytes
```

**열쇠 (script_sig):**
```
<data1> <data2> ... <redeemScript>

redeemScript:
  실제 잠금 조건
  예: 2-of-3 MultiSig Script
```

---

### 4.4 실행 과정 (2단계)

**Phase 1: 해시 검증**
```
Combined Script:
  <data> ... <redeemScript> OP_HASH160 <script_hash> OP_EQUAL

실행:
  1. redeemScript를 스택에서 가져옴
  2. HASH160 계산
  3. script_hash와 비교
  
  일치: Phase 2로 ✅
  불일치: 실패 ❌
```

**Phase 2: redeemScript 실행**
```
redeemScript를 꺼내서 실행

예: 2-of-3 MultiSig redeemScript
  <data> ... + 2 <pubkey1> <pubkey2> <pubkey3> 3 OP_CHECKMULTISIG
  
  실행:
    MultiSig 검증 (아래 참고)
  
  성공: UTXO 소비 가능 ✅
  실패: TX 거부 ❌
```

---

### 4.5 예시: 2-of-3 MultiSig P2SH

**생성 (Bob, Charlie, Dave 공동 계좌):**

```
Step 1: redeemScript 작성
  redeemScript:
    2  (M)
    <Bob_pubkey>
    <Charlie_pubkey>
    <Dave_pubkey>
    3  (N)
    OP_CHECKMULTISIG

Step 2: 해시 계산
  script_hash = HASH160(redeemScript)
            = "5a7b3c..."

Step 3: P2SH 주소 생성
  versioned = 0x4B + script_hash
  checksum = SHA-256(SHA-256(versioned))[0:4]
  address = Base58(versioned + checksum)
         = "JACK3abc...xyz"

Alice → 이 주소로 전송 (Alice는 MultiSig 조건 몰라도 됨)
```

---

**소비 (Bob + Charlie가 사용):**

```
Step 1: script_sig 구성
  script_sig:
    0  (버그 대응)
    <Bob_signature>
    <Charlie_signature>
    <redeemScript>

Step 2: TX 생성 & 전파

Step 3: 노드 검증
  Phase 1:
    HASH160(redeemScript) == script_hash? ✅
  
  Phase 2:
    redeemScript 실행
    → 2개 서명 검증
    → 성공 ✅
```

---

## 5. MultiSig (다중 서명)

### 5.1 개념

**M-of-N MultiSig:**
```
N개 공개키 중 M개 서명 필요

예시:
  1-of-1: 일반 (P2PKH와 동일)
  2-of-3: 3개 키 중 2개
  3-of-5: 5개 키 중 3개
  5-of-7: 7개 키 중 5개
```

---

### 5.2 사용처

**회사 자금:**
```
3-of-5 MultiSig
  이사 5명 중 3명 동의 필요
  
장점:
  - 한 사람이 독단적으로 사용 불가
  - 일부 키 분실해도 OK
  - 투명한 의사결정
```

**에스크로:**
```
2-of-3 MultiSig
  - 구매자
  - 판매자
  - 중재자
  
정상: 구매자 + 판매자
분쟁: 구매자/판매자 + 중재자
```

**개인 보안:**
```
2-of-3 MultiSig
  - 노트북
  - 스마트폰
  - 하드웨어 지갑
  
장점:
  - 한 기기 분실해도 OK
  - 해킹 어려움 (2개 필요)
```

---

### 5.3 MultiSig Script

**2-of-3 예시:**

**redeemScript:**
```
2                    (M = 2)
<pubkey1>            (33 bytes)
<pubkey2>            (33 bytes)
<pubkey3>            (33 bytes)
3                    (N = 3)
OP_CHECKMULTISIG

크기: 약 105 bytes
```

**script_sig:**
```
0                    (버그 대응)
<signature1>         (71 bytes)
<signature2>         (71 bytes)

크기: 약 145 bytes
```

---

### 5.4 OP_CHECKMULTISIG 작동 원리

**스택 상태:**
```
Initial Stack:
  [0, sig1, sig2, 2, pubkey1, pubkey2, pubkey3, 3]
```

**실행:**
```
1. N (3) 팝 → 공개키 3개 팝
   Stack: [0, sig1, sig2, 2]
   Pubkeys: [pubkey1, pubkey2, pubkey3]

2. M (2) 팝 → 서명 2개 팝
   Stack: [0]
   Signatures: [sig1, sig2]

3. 각 서명을 순서대로 검증
   sig1을 pubkey1, pubkey2, pubkey3로 시도
   → pubkey1에서 성공
   
   sig2를 pubkey2, pubkey3로 시도 (pubkey1은 이미 사용)
   → pubkey2에서 성공

4. M개 서명 모두 유효?
   성공: [1] 푸시
   실패: [0] 푸시

5. 0 팝 (버그 대응)
   
6. 최종 Stack: [1] 또는 [0]
```

**Bitcoin 버그:**
```
OP_CHECKMULTISIG가 1개 더 팝함
→ 스택 언더플로우 방지를 위해 0을 넣음

역사:
  Bitcoin 초기 구현 버그
  → 수정 불가능 (하드포크 필요)
  → Workaround: 0 추가
```

---

### 5.5 P2SH-MultiSig vs 일반 MultiSig

**일반 MultiSig (P2MS):**
```
script_pubkey:
  2 <pubkey1> <pubkey2> <pubkey3> 3 OP_CHECKMULTISIG
  
크기: 105 bytes

단점:
  - 송금자가 전체 Script 제공
  - TX 크기 큼
  - 수수료 높음
  - 거의 사용 안 함
```

**P2SH-MultiSig:**
```
script_pubkey:
  OP_HASH160 <script_hash> OP_EQUAL
  
크기: 23 bytes

장점:
  - 송금자는 해시만 제공
  - TX 크기 작음
  - 수수료 낮음
  - 표준 방식 ✅
```

---

## 6. SIGHASH (서명 해시 타입)

### 6.1 개념

**문제:**
```
TX 서명 시:
  전체 TX를 서명해야 하나?
  일부만 서명하면?
  나중에 수정 가능하면?
```

**SIGHASH 플래그:**
```
서명이 어디까지 적용되는지 지정

플래그 종류:
  SIGHASH_ALL:           0x01 (기본)
  SIGHASH_NONE:          0x02
  SIGHASH_SINGLE:        0x03
  SIGHASH_ANYONECANPAY:  0x80 (비트 플래그)

조합 가능:
  ALL | ANYONECANPAY:    0x81
  NONE | ANYONECANPAY:   0x82
  SINGLE | ANYONECANPAY: 0x83
```

---

### 6.2 SIGHASH_ALL (기본, 0x01)

**의미:**
```
"TX 전체를 서명"
```

**서명 범위:**
```
✅ 모든 Inputs
✅ 모든 Outputs
✅ version, locktime
```

**특징:**
```
- 아무것도 수정 불가능
- 가장 안전
- 95% 이상 사용
- 대부분의 일반 거래
```

**서명 생성:**
```
signature_bytes = sign(tx_hash, private_key)
signature = signature_bytes + 0x01  ← SIGHASH_ALL
```

**예시:**
```
Alice → Bob 100 JACK

서명:
  "이 Input으로 Bob에게 정확히 100 JACK,
   나에게 49.9 JACK 거스름돈"
  
  → 아무것도 수정 불가
```

---

### 6.3 SIGHASH_NONE (0x02)

**의미:**
```
"Outputs는 무관"
```

**서명 범위:**
```
✅ 모든 Inputs
❌ Outputs (서명 안 함)
```

**특징:**
```
- Output을 자유롭게 수정 가능
- 매우 위험
- 거의 사용 안 함
```

**사용처:**
```
"이 Input을 소비하되,
 누구에게 줄지는 나중에 결정"

예: 공개 기부
  서명: "내 100 JACK을 써"
  누군가 Output 추가: "자선단체에 100 JACK"
  
  → TX 완성
```

**위험:**
```
악의적인 노드가 Output 변조:
  "해커에게 100 JACK" ❌
  
→ 돈 도난 가능
→ 실전에서 거의 안 씀
```

---

### 6.4 SIGHASH_SINGLE (0x03)

**의미:**
```
"같은 인덱스의 Output만 서명"
```

**서명 범위:**
```
✅ 이 Input
✅ 같은 인덱스의 Output만
❌ 다른 Outputs
```

**특징:**
```
- 한 Input-Output 쌍만 보장
- 나머지는 수정 가능
```

**사용처:**
```
"이 금액은 이 사람에게,
 나머지는 누가 받든 상관없음"

예:
  Input 0 (100 JACK) → Output 0 (Bob에게 100) 보장
  Output 1, 2는 누가 받든 OK
```

**예시:**
```
크라우드펀딩 보상:

Alice:
  Input 0: 10 JACK
  Output 0: NFT #123
  SIGHASH: SINGLE
  
Bob이 추가:
  Output 1: 수수료 (자신에게)
  
→ Alice는 NFT만 확실히 받음
→ Bob은 수수료 가져감
```

---

### 6.5 SIGHASH_ANYONECANPAY (0x80)

**의미:**
```
"다른 Input 추가 가능"
```

**서명 범위:**
```
✅ 이 Input만
❌ 다른 Inputs (서명 안 함)
```

**조합:**
```
반드시 다른 플래그와 조합:
  - ALL | ANYONECANPAY (0x81)
  - NONE | ANYONECANPAY (0x82)
  - SINGLE | ANYONECANPAY (0x83)
```

---

**ALL | ANYONECANPAY (0x81):**
```
서명 범위:
  ✅ 이 Input만
  ✅ 모든 Outputs

사용처: 크라우드펀딩

예: 목표 100 JACK
  Alice: 30 JACK (ANYONECANPAY)
  Bob: 40 JACK (ANYONECANPAY)
  Charlie: 30 JACK (ANYONECANPAY)
  
  → 합쳐서 100 JACK
  → 누가 참여하든 OK
  → 목표 달성 시 모두 유효

Output:
  프로젝트: 100 JACK (고정)
```

---

**NONE | ANYONECANPAY (0x82):**
```
서명 범위:
  ✅ 이 Input만
  ❌ Outputs 무관

사용처: 공개 기부 + 크라우드펀딩

예:
  여러 사람이 Input 추가
  Output은 나중에 결정
  
위험:
  Output 변조 가능
```

---

**SINGLE | ANYONECANPAY (0x83):**
```
서명 범위:
  ✅ 이 Input
  ✅ 같은 인덱스 Output
  ❌ 다른 Inputs/Outputs

사용처:
  개인 보상 + 크라우드펀딩

예:
  Alice: Input 0 → Output 0 (NFT)
  Bob: Input 1 → Output 1 (NFT)
  
  → 각자 자기 것만 보장
```

---

## 7. 트랜잭션 검증 전체 플로우

### 7.1 검증 단계

**Level 1: 형식 검증 (Syntactic)**
```
속도: 매우 빠름
비용: 낮음

검사 항목:
  ✅ TX 크기 적절? (< 1 MB)
  ✅ Input/Output 개수 유효? (> 0)
  ✅ 금액 범위? (0 < value < MAX_MONEY)
  ✅ 직렬화 올바름?
  ✅ 중복 Input 없음?
  ✅ Coinbase가 아닌데 Input 0개? ❌

실패 시: 즉시 거부 (네트워크 전파 안 함)
```

---

**Level 2: 맥락 검증 (Contextual)**
```
속도: 빠름
비용: 중간

검사 항목:
  ✅ Input 합 >= Output 합 + 수수료?
  ✅ 이중 지불 아님? (Mempool + UTXO Set)
  ✅ locktime 조건 만족?
  ✅ 수수료 적절? (> minimum fee)
  ✅ Input UTXO 존재?

실패 시: TX 거부 (Mempool에 안 넣음)
```

---

**Level 3: Script 검증**
```
속도: 느림
비용: 높음

각 Input마다:
  1. 이전 UTXO 찾기
  2. script_sig + script_pubkey 결합
  3. Script 실행
  4. 결과 [1] 확인
  
실패 시: TX 거부

최적화:
  - 병렬 처리 (Input끼리 독립적)
  - Script 캐싱
```

---

**Level 4: 서명 검증**
```
속도: 매우 느림 (ECDSA 연산)
비용: 매우 높음

각 Input마다:
  1. 서명할 메시지 재구성
  2. ECDSA verify(sig, hash, pubkey)
  
실패 시: TX 거부

최적화:
  - 병렬 처리
  - 서명 캐싱 (같은 TX 여러 번)
  - 배치 검증 (Schnorr 서명)
```

---

### 7.2 검증 의사코드

```python
def validate_transaction(tx, utxo_set, mempool, block_height):
    """트랜잭션 전체 검증"""
    
    # Level 1: 형식 검증
    if len(tx.serialize()) > MAX_TX_SIZE:
        return False, "TX 크기 초과"
    
    if len(tx.inputs) == 0:
        return False, "Input 없음"
    
    if len(tx.outputs) == 0:
        return False, "Output 없음"
    
    for output in tx.outputs:
        if output.value < 0 or output.value > MAX_MONEY:
            return False, "금액 범위 오류"
    
    # Level 2: 맥락 검증
    if check_double_spend(tx, utxo_set, mempool):
        return False, "이중 지불"
    
    input_total = 0
    output_total = sum(out.value for out in tx.outputs)
    
    # Level 3 & 4: 각 Input 검증
    for i, input in enumerate(tx.inputs):
        # 이전 UTXO 찾기
        utxo = utxo_set.get(input.prev_tx_id, input.output_index)
        if not utxo:
            return False, f"Input {i}: UTXO 없음"
        
        input_total += utxo.value
        
        # Script 실행
        script = input.script_sig + utxo.script_pubkey
        result = execute_script(script, tx, i)
        
        if not result or result[-1] != 1:
            return False, f"Input {i}: Script 실패"
        
        # 서명 검증
        sighash_type = get_sighash_type(input.script_sig)
        tx_hash = compute_signature_hash(tx, i, utxo, sighash_type)
        
        # script_sig에서 서명과 공개키 추출
        sig, pubkey = extract_sig_pubkey(input.script_sig)
        
        if not ecdsa_verify(sig, tx_hash, pubkey):
            return False, f"Input {i}: 서명 무효"
    
    # Balance 확인
    fee = input_total - output_total
    
    if fee < 0:
        return False, "수수료 음수"
    
    if fee < get_minimum_fee(tx):
        return False, "수수료 부족"
    
    # locktime 확인
    if not check_locktime(tx, block_height):
        return False, "locktime 조건 불만족"
    
    return True, f"검증 성공 (수수료: {fee})"
```

---

### 7.3 병렬 검증

**Input은 독립적:**
```
Input 0: UTXO A 소비
Input 1: UTXO B 소비
Input 2: UTXO C 소비

→ 서로 다른 UTXO
→ 병렬로 검증 가능

최적화:
  8코어 CPU
  → 8개 Input 동시 검증
  → 8배 빠름
```

**Script 캐싱:**
```
같은 script_pubkey가 많음:
  P2PKH: 대부분 같은 패턴
  
캐싱:
  script_pubkey_hash → 실행 결과
  
  다음에 같은 패턴 보면:
    캐시에서 가져오기
    → 재실행 불필요
```

---

## 8. JackpotChain 특수 사항

### 8.1 멀티에셋 검증

```python
def validate_multiasset_tx(tx):
    """멀티에셋 TX 검증"""
    
    # 에셋별로 분리
    input_assets = defaultdict(int)
    output_assets = defaultdict(int)
    
    for input in tx.inputs:
        utxo = get_utxo(input.prev_tx_id, input.output_index)
        
        for asset_id, amount in utxo.assets.items():
            input_assets[asset_id] += amount
    
    for output in tx.outputs:
        for asset_id, amount in output.assets.items():
            output_assets[asset_id] += amount
    
    # 각 에셋마다 Input >= Output 확인
    for asset_id, output_amount in output_assets.items():
        input_amount = input_assets.get(asset_id, 0)
        
        if asset_id == "":  # JACK (네이티브, 수수료 고려)
            fee = input_amount - output_amount
            
            if fee < 0:
                return False, "JACK 부족"
            
            if fee < get_minimum_fee(tx):
                return False, "수수료 부족"
        
        else:  # 다른 에셋 (수수료 없음)
            if input_amount < output_amount:
                return False, f"{asset_id} 부족"
    
    return True, "OK"
```

---

### 8.2 특수 TX 타입

**Exchange TX:**
```
JACK → POT 교환

특징:
  - Input: JACK만
  - Output: POT 생성 (Mint)
  - 비율 검증 (100 JACK = 1 POT)

검증:
  def validate_exchange_tx(tx):
      jack_in = sum(input JACK)
      pot_out = sum(output POT)
      
      expected_pot = jack_in / 100
      
      if pot_out != expected_pot:
          return False, "교환 비율 오류"
      
      # POT는 새로 생성되므로 Input에 없어도 OK
      return True
```

**Gacha TX (Commit-Reveal):**
```
Phase 1: Commit
  Input: POT
  Output: Commit Hash
  
  script_pubkey:
    OP_HASH160 <commit_hash> OP_EQUAL

Phase 2: Reveal
  Input: Commit UTXO
  Output: NFT (당첨 시) 또는 없음 (꽝)
  
  script_sig:
    <secret> <commit_hash>
  
  검증:
    1. HASH160(secret) == commit_hash
    2. secret으로 랜덤 계산
    3. 확률 검증
    4. 당첨 시 NFT Mint
```

---

## 9. 성능 최적화

### 9.1 서명 캐싱

```python
# 전역 캐시
signature_cache = LRU_Cache(max_size=100000)

def verify_signature_cached(sig, msg_hash, pubkey):
    cache_key = hash(sig + msg_hash + pubkey)
    
    if cache_key in signature_cache:
        return signature_cache[cache_key]
    
    result = ecdsa_verify(sig, msg_hash, pubkey)
    signature_cache[cache_key] = result
    
    return result
```

---

### 9.2 Script 캐싱

```python
# Script 패턴 인식
script_patterns = {
    "P2PKH": compile_pattern("OP_DUP OP_HASH160 <20> OP_EQUALVERIFY OP_CHECKSIG"),
    "P2SH": compile_pattern("OP_HASH160 <20> OP_EQUAL"),
}

def execute_script_optimized(script):
    pattern = recognize_pattern(script)
    
    if pattern == "P2PKH":
        return execute_p2pkh_fast(script)
    elif pattern == "P2SH":
        return execute_p2sh_fast(script)
    else:
        return execute_script_generic(script)
```

---

### 9.3 병렬 검증

```python
from multiprocessing import Pool

def validate_block_parallel(block):
    with Pool(processes=8) as pool:
        # 각 TX를 병렬로 검증
        results = pool.map(validate_transaction, block.transactions)
    
    return all(results)
```

---

## 10. 핵심 요약

### Script 언어
```
- 스택 기반
- 튜링 불완전
- 결정론적
- P2PKH, P2SH가 표준
```

### 서명 과정
```
1. TX 재구성 (script_pubkey 넣기)
2. 직렬화 & 해시
3. ECDSA 서명
4. script_sig 구성
5. SIGHASH 플래그 추가
```

### P2PKH vs P2SH
```
P2PKH: 간단, 1인 서명
P2SH: 복잡한 조건, MultiSig 등
```

### MultiSig
```
M-of-N: N개 중 M개 서명
OP_CHECKMULTISIG
P2SH로 감싸기 (표준)
```

### SIGHASH
```
ALL: 전체 (95%)
NONE: Output 무관 (거의 안 씀)
SINGLE: 한 Output만
ANYONECANPAY: Input 추가 가능 (크라우드펀딩)
```

### 검증 플로우
```
형식 → 맥락 → Script → 서명
병렬 처리 가능
캐싱으로 최적화
```

---

## 11. 체크리스트

- [ ] Script가 스택 기반임을 이해
- [ ] P2PKH 실행 과정 7단계
- [ ] 서명 생성 시 TX 재구성 방법
- [ ] P2SH의 2단계 검증
- [ ] MultiSig의 사용처
- [ ] SIGHASH 4가지 타입 차이
- [ ] TX 검증 4단계
- [ ] 병렬 검증 원리

---

## 12. 다음 학습

### 학습 완료:
- ✅ 암호학 기초
- ✅ 주소 생성
- ✅ 데이터 구조
- ✅ 트랜잭션 심화

### 다음 추천:
```
→ PoW 합의
  - 난이도 조절 알고리즘
  - Longest Chain Rule
  - 포크 해결

→ P2P 네트워크
  - 메시지 프로토콜
  - 블록 전파
  - 동기화

→ 멀티에셋 시스템
  - Asset Policy
  - Mint TX
  - Asset Registry
```

---

## 13. 참고 자료

**Bitcoin Script:**
- Bitcoin Wiki - Script
- BIP 16: P2SH
- Mastering Bitcoin - Chapter 7

**구현:**
- Bitcoin Core - script/interpreter.cpp
- python-bitcoinlib

**도구:**
- Bitcoin Script Debugger
- btcdeb

---

**이전:** [02. 데이터 구조](../phase-0-foundation/02-data-structures.md)  
**다음:** [06. PoW 합의](06-pow-consensus.md) →
