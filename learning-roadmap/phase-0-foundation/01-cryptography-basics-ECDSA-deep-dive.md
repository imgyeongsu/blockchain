# ECDSA 심화: 타원곡선 디지털 서명 알고리즘

> **보조 문서 (01-cryptography-basics.md의 2.2 ECDSA 확장)**  
> **난이도:** ⭐⭐⭐⭐☆ (기술적)  
> **예상 소요 시간:** 2-3시간  
> **선행 지식:** 모듈러 연산, 기본 정수론

---

## 🎯 학습 목표

- [ ] 타원곡선의 수학적 정의 이해
- [ ] 타원곡선 위의 점 연산 (덧셈, 배가, 스칼라 곱셈)
- [ ] secp256k1 파라미터 이해
- [ ] ECDSA 서명 생성 과정
- [ ] ECDSA 서명 검증 원리
- [ ] 보안 고려사항 (nonce 재사용, 타이밍 공격)

---

## 1. 왜 타원곡선인가?

### 1.1 RSA vs ECDSA 비교

| 알고리즘 | 키 크기 | 보안 수준 | 서명 크기 | 속도 |
|---------|--------|----------|----------|------|
| RSA-2048 | 2048 bits | 112-bit | 256 bytes | 느림 |
| RSA-3072 | 3072 bits | 128-bit | 384 bytes | 매우 느림 |
| ECDSA-256 | 256 bits | 128-bit | 64 bytes | 빠름 |

**장점:**
- 작은 키로 같은 보안 수준
- 빠른 서명/검증
- 적은 대역폭

**단점:**
- 복잡한 수학
- 구현 오류 시 치명적
- 양자 컴퓨터에 취약 (RSA도 마찬가지)

---

## 2. 타원곡선 수학

### 2.1 유한체 (Finite Field)

**정의:**
```
F_p = {0, 1, 2, ..., p-1}

연산: mod p
  - 덧셈: (a + b) mod p
  - 곱셈: (a × b) mod p
  - 나눗셈: a / b = a × b⁻¹ mod p
```

**모듈러 역원:**
```
b⁻¹ mod p는 다음을 만족:
  b × b⁻¹ ≡ 1 (mod p)

계산: 확장 유클리드 알고리즘

예시 (p = 23):
  5⁻¹ mod 23 = ?
  
  5 × ? ≡ 1 (mod 23)
  5 × 14 = 70 = 3 × 23 + 1
  → 5⁻¹ = 14
```

---

### 2.2 타원곡선 방정식

**Weierstrass 형태:**
```
y² = x³ + ax + b (mod p)

조건: 4a³ + 27b² ≠ 0 (mod p)  (특이점 없음)
```

**secp256k1:**
```
y² = x³ + 7 (mod p)

where:
  p = 2²⁵⁶ - 2³² - 2⁹ - 2⁸ - 2⁷ - 2⁶ - 2⁴ - 1
  
16진수:
  p = FFFFFFFF FFFFFFFF FFFFFFFF FFFFFFFF 
      FFFFFFFF FFFFFFFF FFFFFFFE FFFFFC2F

이진수 (특수 구조):
  11111111...11111110...11111100101111
  ↑ 224개 1  ↑ 20비트  ↑ 12비트
  
→ 모듈러 연산 최적화 가능 (빠른 reduction)
```

---

### 2.3 점의 개수

**Hasse의 정리:**
```
타원곡선 위의 점 개수 N:
  p + 1 - 2√p ≤ N ≤ p + 1 + 2√p

secp256k1:
  N = p + 1 - ε (거의 p)
  
  정확히:
    N = FFFFFFFF FFFFFFFF FFFFFFFF FFFFFFFE 
        BAAEDCE6 AF48A03B BFD25E8C D0364141
    
  → 약 2²⁵⁶개의 점
```

---

## 3. 타원곡선 연산

### 3.1 점 덧셈 공식

**경우 1: P + Q (P ≠ Q, P ≠ -Q)**
```
P = (x₁, y₁), Q = (x₂, y₂)
P + Q = (x₃, y₃)

계산:
  λ = (y₂ - y₁) / (x₂ - x₁) mod p
    = (y₂ - y₁) × (x₂ - x₁)⁻¹ mod p
  
  x₃ = λ² - x₁ - x₂ mod p
  y₃ = λ(x₁ - x₃) - y₁ mod p
```

**경우 2: P + P = 2P (점 배가)**
```
P = (x₁, y₁)
2P = (x₃, y₃)

계산:
  λ = (3x₁² + a) / (2y₁) mod p
    = 3x₁² × (2y₁)⁻¹ mod p  (secp256k1에서 a=0)
  
  x₃ = λ² - 2x₁ mod p
  y₃ = λ(x₁ - x₃) - y₁ mod p
```

**경우 3: P + (-P) = O**
```
무한원점 (항등원)
```

**경우 4: P + O = P**
```
O는 항등원
```

---

### 3.2 스칼라 곱셈 알고리즘

**Binary Method (Double-and-Add):**
```
k × P를 계산

알고리즘:
  input: k (정수), P (점)
  output: k × P

  1. result ← O
  2. temp ← P
  3. while k > 0:
       if k mod 2 == 1:
         result ← result + temp
       temp ← 2 × temp
       k ← k / 2
  4. return result

시간 복잡도: O(log k)
```

**예시 (k = 13 = 1101₂):**
```
초기:
  result = O
  temp = P
  k = 1101₂

반복 1 (LSB = 1):
  result = O + P = P
  temp = 2P
  k = 110₂

반복 2 (LSB = 0):
  result = P
  temp = 4P
  k = 11₂

반복 3 (LSB = 1):
  result = P + 4P = 5P
  temp = 8P
  k = 1₂

반복 4 (LSB = 1):
  result = 5P + 8P = 13P
  temp = 16P
  k = 0₂

결과: 13P
```

**최적화: NAF (Non-Adjacent Form)**
```
k를 {-1, 0, 1}로 표현
→ 1의 개수 최소화
→ 덧셈 연산 감소

예시:
  15 = 1111₂ (4개 덧셈)
  15 = 10001₂̄ (2개 덧셈)  (̄1 = -1)
     = 16 - 1
     = 16P - P
```

---

## 4. ECDSA 키 생성

### 4.1 도메인 파라미터 (secp256k1)

```
T = (p, a, b, G, n, h)

p: 필드 크기
  FFFFFFFF FFFFFFFF FFFFFFFF FFFFFFFF 
  FFFFFFFF FFFFFFFF FFFFFFFE FFFFFC2F

a: 0

b: 7

G: 생성점 (generator)
  x = 79BE667E F9DCBBAC 55A06295 CE870B07 
      029BFCDB 2DCE28D9 59F2815B 16F81798
  y = 483ADA77 26A3C465 5DA4FBFC 0E1108A8 
      FD17B448 A6855419 9C47D08F FB10D4B8

n: G의 위수 (order)
  FFFFFFFF FFFFFFFF FFFFFFFF FFFFFFFE 
  BAAEDCE6 AF48A03B BFD25E8C D0364141
  
  의미: n × G = O
  → G를 n번 더하면 무한원점

h: cofactor = 1
  전체 점 개수 = h × n
  secp256k1은 h=1이므로 모든 점이 G로 생성됨
```

---

### 4.2 키 쌍 생성

```
알고리즘:

1. 개인키 d 생성:
   d ← random(1, n-1)
   
   → 암호학적으로 안전한 난수 사용
   → 256비트 엔트로피

2. 공개키 Q 계산:
   Q ← d × G
   
   → 스칼라 곱셈 (약 256번 점 연산)
   → (Qx, Qy) 형태

3. 공개키 인코딩:
   비압축 (65 bytes):
     04 || Qx (32 bytes) || Qy (32 bytes)
   
   압축 (33 bytes):
     02 || Qx (32 bytes)  if Qy is even
     03 || Qx (32 bytes)  if Qy is odd
```

**공개키 복원 (압축 → 비압축):**
```
1. x좌표로부터 y² 계산:
   y² = x³ + 7 mod p

2. 제곱근 계산 (Tonelli-Shanks):
   y = ±√(y²) mod p
   
   p mod 4 = 3인 경우 (secp256k1):
     y = (y²)^((p+1)/4) mod p

3. 부호 결정:
   if prefix == 02:
     선택 y가 짝수인 것
   if prefix == 03:
     선택 y가 홀수인 것
```

---

## 5. ECDSA 서명

### 5.1 서명 생성 알고리즘

```
입력:
  - 메시지 m
  - 개인키 d

출력:
  - 서명 (r, s)

과정:

1. 메시지 해시:
   e ← SHA-256(m)
   z ← int(e) mod n
   
   (e를 정수로 변환하되 n으로 축소)

2. 임시 키 쌍 생성:
   k ← random(1, n-1)  ⚠️ 절대 재사용 금지!
   (x₁, y₁) ← k × G

3. r 계산:
   r ← x₁ mod n
   
   if r == 0: go to step 2

4. s 계산:
   s ← k⁻¹(z + rd) mod n
   
   if s == 0: go to step 2

5. 반환:
   signature ← (r, s)
```

**서명 인코딩 (DER):**
```
Bitcoin/Ethereum 형식:
  30 [len] 02 [len_r] [r] 02 [len_s] [s]

secp256k1 raw:
  [r (32 bytes)] [s (32 bytes)]
  
  총 64 bytes
```

---

### 5.2 k 생성 (RFC 6979)

**Deterministic ECDSA:**
```
문제: 랜덤 k는 위험
  - 품질 나쁜 RNG
  - 같은 k 재사용
  - 측정 공격

해결: k를 결정론적으로 생성

알고리즘:
  k = HMAC-DRBG(d, z)
  
  input: 개인키 d, 메시지 해시 z
  output: k

과정:
  1. V ← 0x01 (32 bytes)
  2. K ← 0x00 (32 bytes)
  
  3. K ← HMAC-SHA256(K, V || 0x00 || d || z)
  4. V ← HMAC-SHA256(K, V)
  
  5. K ← HMAC-SHA256(K, V || 0x01 || d || z)
  6. V ← HMAC-SHA256(K, V)
  
  7. k ← HMAC-SHA256(K, V) mod n
  
  8. if k ∈ [1, n-1]: return k
     else: 추가 반복

장점:
  - 같은 메시지는 항상 같은 k
  - 다른 메시지는 완전히 다른 k
  - RNG 불필요
```

---

## 6. ECDSA 검증

### 6.1 검증 알고리즘

```
입력:
  - 메시지 m
  - 서명 (r, s)
  - 공개키 Q

출력:
  - valid: true/false

과정:

1. 범위 검증:
   if r ∉ [1, n-1]: return false
   if s ∉ [1, n-1]: return false

2. 메시지 해시:
   e ← SHA-256(m)
   z ← int(e) mod n

3. 계산:
   w ← s⁻¹ mod n
   u₁ ← zw mod n
   u₂ ← rw mod n

4. 점 계산:
   (x₁, y₁) ← u₁ × G + u₂ × Q
   
   if (x₁, y₁) == O: return false

5. 검증:
   v ← x₁ mod n
   
   return (v == r)
```

---

### 6.2 정확성 증명

**왜 작동하는가?**

```
서명 생성:
  s = k⁻¹(z + rd) mod n

양변에 k를 곱하고 정리:
  ks = z + rd mod n
  k = (z + rd)s⁻¹ mod n
  k = zs⁻¹ + rds⁻¹ mod n
  k = u₁ + u₂d mod n

검증 계산:
  u₁ × G + u₂ × Q
  = u₁ × G + u₂ × (d × G)
  = (u₁ + u₂d) × G
  = k × G

서명 생성 시:
  r = x₁ (k × G의 x좌표)

검증 시:
  v = x₁ (u₁ × G + u₂ × Q의 x좌표)

k × G = u₁ × G + u₂ × Q이므로
→ r = v
→ 검증 성공! ✅
```

---

## 7. 보안 분석

### 7.1 이산 로그 문제 (ECDLP)

**문제:**
```
주어진: G, Q = d × G
찾기: d

타원곡선 이산 로그 문제
→ 현재 최선의 공격: O(√n) (Pollard's rho)
→ 256비트 곡선: 2¹²⁸ 연산 필요 (불가능)
```

**양자 컴퓨터:**
```
Shor's Algorithm:
  O((log n)³) 시간에 이산 로그 해결
  → 양자 컴퓨터가 나오면 ECDSA 깨짐

대안:
  - 양자 저항성 암호 (lattice, hash-based)
  - 더 큰 키 사용 (512비트+)
```

---

### 7.2 nonce 공격

**공격 1: nonce 재사용**
```
같은 k로 두 서명:
  s₁ = k⁻¹(z₁ + rd) mod n
  s₂ = k⁻¹(z₂ + rd) mod n

공격:
  s₁ - s₂ = k⁻¹(z₁ - z₂) mod n
  k = (z₁ - z₂)(s₁ - s₂)⁻¹ mod n

개인키 복구:
  d = (s₁k - z₁)r⁻¹ mod n

실제 사례:
  Sony PS3 (2010): 고정 k 사용 → 해킹
```

**공격 2: 편향된 nonce**
```
k의 몇 비트만 알아도:
  Lattice reduction attack
  → 수백 개 서명으로 개인키 복구

방어:
  RFC 6979 (Deterministic ECDSA)
```

---

### 7.3 사이드 채널 공격

**타이밍 공격:**
```
연산 시간 측정 → 비밀 정보 추출

취약 연산:
  - 모듈러 역원 계산
  - 스칼라 곱셈

방어:
  - Constant-time 연산
  - 블라인딩 (무작위 값 추가)
```

**전력 분석 공격:**
```
전력 소비 패턴 → 비트 값 추출

방어:
  - Masking
  - 이중 스칼라 곱셈
```

---

## 8. 구현 최적화

### 8.1 모듈러 연산 최적화

**Barrett Reduction:**
```
a mod p를 빠르게 계산

전처리:
  μ = ⌊2²ᵏ / p⌋  (k = 비트 수)

계산:
  q = ⌊(a × μ) / 2²ᵏ⌋
  r = a - q × p
  
  if r >= p: r = r - p
  
시간: 2배 빠름 (나눗셈 제거)
```

**Montgomery Multiplication:**
```
곱셈과 모듈러 연산 통합

변환:
  ā = a × 2ᵏ mod p

곱셈:
  c̄ = MontMul(ā, b̄, p)
    = a × b × 2⁻ᵏ mod p

시간: 3배 빠름
```

---

### 8.2 점 연산 최적화

**Jacobian 좌표계:**
```
(x, y) → (X, Y, Z)
  x = X/Z²
  y = Y/Z³

장점:
  - 나눗셈 불필요
  - 점 덧셈 15% 빠름

비용:
  - 메모리 1.5배
  - 최종 변환 필요
```

**사전 계산 (Precomputation):**
```
G의 배수들 미리 계산:
  [G, 2G, 3G, ..., 16G]

k × G 계산 시:
  4비트씩 나눠서 lookup
  
예:
  251 × G = 15×16 + 11
          = lookup(15) + lookup(11)

속도: 2배 빠름
메모리: 16개 점 (512 bytes)
```

---

## 9. JackpotChain 적용

### 9.1 트랜잭션 서명

```
Transaction:
  inputs: [...]
  outputs: [...]

서명 생성:
  1. TX를 직렬화
  2. 각 Input마다:
     - 이전 Output의 script_pubkey 포함
     - SHA-256 해시
     - 개인키로 서명
  3. Input에 서명 첨부

검증:
  1. TX 재구성
  2. 각 Input 서명 검증
  3. 모두 통과 시 유효
```

---

### 9.2 주소 생성

```
1. 개인키 d 생성 (32 bytes)
2. 공개키 Q = d × G (33 bytes 압축)
3. SHA-256(Q) (32 bytes)
4. RIPEMD-160(hash) (20 bytes)
5. Base58Check 인코딩 → 주소

예시:
  JACK1qxyz...abc (35자)
```

---

## 10. 실습 과제

### Level 1: 기초
```
1. 작은 p (p = 23)로 점 덧셈 손으로 계산
2. Double-and-Add로 5 × P 계산
3. Python으로 모듈러 역원 구현
```

### Level 2: 중급
```
1. secp256k1로 키 쌍 생성
2. 메시지 서명 및 검증
3. 같은 k 재사용 공격 실습
```

### Level 3: 고급
```
1. RFC 6979 구현
2. Jacobian 좌표계 변환
3. 타이밍 공격 방어 구현
```

---

## 11. 참고 자료

**표준 문서:**
- SEC 2: Recommended Elliptic Curve Domain Parameters
- RFC 6979: Deterministic Usage of ECDSA
- FIPS 186-4: Digital Signature Standard

**책:**
- Guide to Elliptic Curve Cryptography (Hankerson)
- Implementing Elliptic Curve Cryptography (Rosing)

**코드:**
- libsecp256k1 (Bitcoin Core)
- ecdsa (Python)

---

## 12. 핵심 요약

### ECDSA 3단계

**1. 타원곡선**
```
점들의 집합 + 덧셈 연산
→ 스칼라 곱셈 가능
→ 역연산 (이산 로그) 불가능
```

**2. 서명**
```
s = k⁻¹(z + rd) mod n
→ k, d 없이 검증 가능
→ k 재사용 금지
```

**3. 검증**
```
u₁ × G + u₂ × Q = k × G
→ x좌표가 r과 같은지 확인
```

---

**다음:** [01-cryptography-basics.md](01-cryptography-basics.md)로 돌아가서 2.3 디지털 서명 계속
