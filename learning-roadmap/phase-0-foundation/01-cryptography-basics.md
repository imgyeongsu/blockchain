# 01. 암호학 기초 (Cryptography Basics)

> **Phase 0: Foundation**  
> **예상 소요 시간:** 1-2시간  
> **선행 학습:** 없음  
> **난이도:** ⭐⭐☆☆☆

---

## 🎯 학습 목표

이 문서를 완료하면:
- [ ] 해시 함수가 무엇인지, 왜 블록체인에 필수인지 설명할 수 있다
- [ ] SHA-256의 특성 3가지를 말할 수 있다
- [ ] 공개키 암호화와 대칭키 암호화의 차이를 설명할 수 있다
- [ ] 디지털 서명의 생성과 검증 과정을 이해한다
- [ ] Merkle Tree의 용도와 작동 원리를 이해한다

---

## 1. 해시 함수 (Hash Function)

### 1.1 개념

**정의:**
```
해시 함수 = 임의 크기 데이터 → 고정 크기 값

예시:
  "Hello World" → SHA-256 → "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e"
  "Hello World!" → SHA-256 → "7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069"
```

**특징:**
- 입력이 1비트만 바뀌어도 출력은 완전히 다름 (Avalanche Effect)
- 같은 입력 → 항상 같은 출력 (Deterministic)
- 출력으로부터 입력 역추적 불가능 (One-way)

---

### 1.2 SHA-256

**사양:**
```
입력: 임의 크기 (0 ~ 2^64 - 1 bits)
출력: 256 bits (64개 16진수 문자)

예시:
  빈 문자열 → "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  "a" → "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb"
  "JackpotChain" → "5e8f7c9d2e4b3a1f6c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1"
```

**충돌 저항성:**
```
Birthday Paradox 계산:
  2^256 가능한 해시
  2^128번 시도하면 50% 충돌 확률
  
  현재 컴퓨터 속도:
    - 1초에 10^12 해시 가능 (ASIC)
    - 2^128번 = 3.4 × 10^38번
    - 소요 시간 = 10^19 년 (우주 나이의 1억배)
  
  결론: 사실상 충돌 불가능
```

---

### 1.3 블록체인에서의 활용

**용도 1: 블록 연결**
```
Block N:
  prev_hash: "0000abc123..."  ← Block N-1의 해시
  data: "거래 내역"
  hash: "0000def456..."       ← 이 블록의 해시

→ prev_hash로 체인 형성
→ 과거 블록 수정 시 모든 후속 블록 해시 변경
→ 위변조 감지 용이
```

**용도 2: PoW**
```
목표: hash(block) < target

예:
  target = 0000FFFF...
  
  nonce = 0: hash = A3F2... ❌
  nonce = 1: hash = 8B41... ❌
  ...
  nonce = 123456: hash = 0000A1B2... ✅
```

**용도 3: 주소 생성**
```
공개키 → SHA-256 → RIPEMD-160 → Base58 → 주소

예:
  공개키: 04a1b2c3d4...
  SHA-256: e5f6a7b8c9...
  RIPEMD-160: 1A2B3C4D5E...
  Base58: JACKxyz123...
```

---

## 2. 공개키 암호화 (Public Key Cryptography)

### 2.1 대칭키 vs 공개키

**대칭키 (Symmetric):**
```
암호화와 복호화에 같은 키 사용

Alice                  Bob
  ↓ 메시지 + 키 → 암호문
                       ↓ 암호문 + 키 → 메시지

문제:
  - 키 전달이 안전해야 함
  - 사람마다 다른 키 필요 (N명 = N개 키)
```

**공개키 (Asymmetric):**
```
암호화와 복호화에 다른 키 사용

Alice의 키 쌍:
  - 공개키 (Public Key): 누구나 알 수 있음
  - 개인키 (Private Key): Alice만 알고 있음

Bob → Alice:
  Bob이 Alice 공개키로 암호화
  → Alice만 개인키로 복호화 가능

장점:
  - 키 전달 문제 해결
  - N명 = N개 키 쌍 (2N개 키)
```

---

### 2.2 ECDSA (타원곡선 디지털 서명)

**JackpotChain이 사용하는 알고리즘:**
```
곡선: secp256k1 (Bitcoin과 동일)

키 생성:
  개인키 (d): 랜덤 256비트 정수
  공개키 (Q): Q = d × G (G는 생성점)

특징:
  - Q로부터 d 계산 불가능 (이산 로그 문제)
  - 키 크기 작음 (256비트)
  - 서명 빠름
```

---

### 2.3 디지털 서명

**서명 과정:**
```
Step 1: 메시지 해시
  message_hash = SHA-256(message)

Step 2: 서명 생성
  signature = sign(message_hash, private_key)
  
  출력: (r, s) 쌍 (각 256비트)

Step 3: 서명 + 메시지 전송
  send(message, signature, public_key)
```

**검증 과정:**
```
Step 1: 메시지 해시 (동일)
  message_hash = SHA-256(message)

Step 2: 서명 검증
  valid = verify(message_hash, signature, public_key)
  
  → 수학적으로 계산
  → true/false 반환

핵심:
  - 개인키 없이도 검증 가능
  - 서명 위조 불가능 (개인키 필요)
  - 메시지 수정 시 검증 실패
```

**실제 예시:**
```
Alice가 Bob에게 100 JACK 송금:

TX 내용:
  from: Alice
  to: Bob
  amount: 100 JACK

서명:
  Alice의 개인키로 서명
  signature = sign(hash(TX), Alice_private_key)

검증:
  네트워크 노드들:
    verify(hash(TX), signature, Alice_public_key)
    → Alice가 정말 보낸 것인지 확인
    → TX 위변조 여부 확인
```

---

## 3. Merkle Tree

### 3.1 개념

**정의:**
```
트랜잭션들을 이진 트리로 구성
각 부모는 자식들의 해시를 합친 해시

예시: 4개 TX

        Root Hash (merkle_root)
         /              \
      H(AB)            H(CD)
      /   \            /   \
    H(A) H(B)       H(C) H(D)
     |    |          |    |
    TX_A TX_B      TX_C TX_D
```

---

### 3.2 용도

**용도 1: 블록 헤더 간소화**
```
블록 헤더에 모든 TX 포함 시:
  1000개 TX × 500 bytes = 500 KB
  
Merkle Root 사용:
  merkle_root = 32 bytes
  
  → 헤더 크기 대폭 감소
  → 경량 노드(SPV)가 헤더만 다운로드 가능
```

**용도 2: TX 포함 증명 (Merkle Proof)**
```
질문: TX_C가 블록에 포함되었나?

증명:
  1. H(D) 제공
  2. H(AB) 제공
  
  검증:
    step 1: H(CD) = hash(H(C) + H(D))
    step 2: Root = hash(H(AB) + H(CD))
    step 3: Root == 블록 헤더의 merkle_root?
  
  필요 데이터: log₂(N) 개 해시
    1000개 TX → 10개 해시만 필요
    (vs 모든 TX 다운로드)
```

---

### 3.3 구현 아이디어

```
의사코드:

function buildMerkleTree(transactions):
    # Leaf 노드 생성
    leaves = [hash(tx) for tx in transactions]
    
    # 홀수면 마지막 복제
    if len(leaves) % 2 == 1:
        leaves.append(leaves[-1])
    
    # 재귀적으로 상위 레벨 생성
    while len(leaves) > 1:
        next_level = []
        for i in range(0, len(leaves), 2):
            parent = hash(leaves[i] + leaves[i+1])
            next_level.append(parent)
        
        if len(next_level) % 2 == 1:
            next_level.append(next_level[-1])
        
        leaves = next_level
    
    return leaves[0]  # Root

function verifyMerkleProof(tx_hash, proof, merkle_root):
    current = tx_hash
    
    for sibling in proof:
        current = hash(current + sibling)
    
    return current == merkle_root
```

---

## 4. JackpotChain에서의 활용

### 4.1 블록 구조
```
BlockHeader:
  - prev_hash: SHA-256 (이전 블록 연결)
  - merkle_root: Merkle Tree (TX 요약)
  - timestamp: 시간
  - difficulty_target: PoW 목표
  - nonce: PoW 해답
```

### 4.2 트랜잭션 서명
```
Transaction:
  inputs: [...]
  outputs: [...]
  
서명 대상:
  signature = sign(hash(inputs + outputs), private_key)

검증:
  각 input마다:
    verify(hash(tx), input.signature, input.public_key)
```

### 4.3 주소 체계
```
개인키 (256 bits)
  ↓ ECDSA 곱셈
공개키 (512 bits)
  ↓ SHA-256
해시 (256 bits)
  ↓ RIPEMD-160
짧은 해시 (160 bits)
  ↓ Base58Check
주소 (문자열)
```

---

## 5. 보안 고려사항

### 5.1 개인키 관리
```
❌ 절대 하지 말 것:
  - 개인키를 평문으로 저장
  - 개인키를 네트워크로 전송
  - 개인키를 코드에 하드코딩
  - 같은 nonce 재사용 (ECDSA)

✅ 해야 할 것:
  - 암호화된 지갑 파일
  - BIP39 니모닉 (복구 문구)
  - 하드웨어 지갑 (콜드 월렛)
  - 키 도출 함수 (PBKDF2, scrypt)
```

### 5.2 랜덤성
```
위험한 랜덤:
  random.seed(1234)  # 예측 가능 ❌

안전한 랜덤:
  os.urandom(32)     # OS 엔트로피 ✅
  secrets.token_bytes(32)  # Python 3.6+ ✅
```

---

## 6. 실습 아이디어

### 6.1 해시 체험
```
온라인 도구:
  https://emn178.github.io/online-tools/sha256.html

실습:
  1. "Hello" 입력 → 해시 기록
  2. "hello" 입력 → 해시 비교 (완전히 다름)
  3. 아주 긴 텍스트 입력 → 해시는 항상 64자
```

### 6.2 서명 실습 (Python)
```python
# 간단한 예시 (개념만)
from hashlib import sha256
from ecdsa import SigningKey, SECP256k1

# 키 생성
private_key = SigningKey.generate(curve=SECP256k1)
public_key = private_key.get_verifying_key()

# 메시지
message = b"Alice sends 100 JACK to Bob"
message_hash = sha256(message).digest()

# 서명
signature = private_key.sign(message_hash)

# 검증
is_valid = public_key.verify(signature, message_hash)
print(f"서명 유효: {is_valid}")  # True
```

---

## 7. 핵심 요약

### 암호학 3대 기둥

**1. 해시 함수 (SHA-256)**
```
용도: 무결성 검증
특징: One-way, 충돌 저항성
블록체인: 블록 연결, PoW, 주소 생성
```

**2. 공개키 암호화 (ECDSA)**
```
용도: 신원 증명
특징: 공개키로 검증, 개인키로 서명
블록체인: TX 서명, 소유권 증명
```

**3. Merkle Tree**
```
용도: 효율적 검증
특징: log(N) 증명 크기
블록체인: 블록 헤더 간소화, SPV
```

---

## 8. 체크리스트

### 이해했는지 확인:

- [ ] SHA-256이 왜 "one-way"인지 설명할 수 있다
- [ ] 같은 입력을 해시하면 항상 같은 출력이 나오는 이유를 안다
- [ ] 공개키와 개인키의 역할 차이를 설명할 수 있다
- [ ] 디지털 서명이 어떻게 위조를 방지하는지 이해한다
- [ ] Merkle Tree가 어떻게 검증 효율을 높이는지 안다

### 다음 단계:
```
→ [02-data-structures.md](02-data-structures.md)
  블록과 트랜잭션의 구체적인 구조 학습
```

---

## 9. 추가 학습 자료

**영상:**
- 3Blue1Brown - "But how does bitcoin actually work?" (YouTube)
- Computerphile - "Hashing Algorithms and Security" (YouTube)

**문서:**
- Bitcoin Developer Guide - Keys and Addresses
- NIST FIPS 180-4 (SHA-256 표준)

**실습:**
- https://andersbrownworth.com/blockchain/ (블록체인 시뮬레이터)

---

**다음:** [02. 데이터 구조](02-data-structures.md) →
