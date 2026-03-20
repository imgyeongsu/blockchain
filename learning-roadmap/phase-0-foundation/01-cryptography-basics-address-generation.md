# RIPEMD-160 & Base58: 블록체인 주소 생성

> **보조 문서 (01-cryptography-basics.md의 주소 생성 확장)**  
> **학습 날짜:** 2025-02-12  
> **난이도:** ⭐⭐☆☆☆ (개념 중심)  
> **예상 소요 시간:** 30분

---

## 🎯 학습 목표

- [ ] RIPEMD-160이 무엇이고 왜 사용하는지
- [ ] Base58과 Base64의 차이
- [ ] Base58Check와 체크섬의 역할
- [ ] 공개키에서 주소까지 전체 과정
- [ ] JackpotChain 주소 형식

---

## 1. RIPEMD-160

### 1.1 한마디로

**RIPEMD-160 = SHA-256의 짧은 버전**

```
SHA-256:
  입력: 아무거나
  출력: 256비트 (32 bytes, 64자리 16진수)
  
RIPEMD-160:
  입력: 아무거나
  출력: 160비트 (20 bytes, 40자리 16진수)
```

---

### 1.2 왜 두 번 해시하는가?

**공개키 → 주소 과정:**
```
공개키 (33 bytes)
  ↓ SHA-256
해시1 (32 bytes)
  ↓ RIPEMD-160
해시2 (20 bytes) ← 주소의 핵심 부분

이유:
  1. 주소 길이 단축 (저장 공간 절약)
  2. 보안 강화 (두 개 다른 해시 함수)
     → 하나가 깨져도 다른 하나가 방어
     → "방어 깊이 (Defense in Depth)"
```

**왜 SHA-256만 안 쓰고 RIPEMD-160도 쓰는가?**
```
Bitcoin의 설계 (Satoshi Nakamoto):
  - SHA-256: NSA 설계 (의심 가능)
  - RIPEMD-160: 유럽 설계 (독립적)
  → 둘 다 동시에 깨질 확률 극히 낮음

추가 장점:
  - 주소 20 bytes로 단축
  - QR 코드 크기 감소
  - 트랜잭션 크기 감소
```

---

### 1.3 실제 예시

```
공개키 (압축, 33 bytes):
  02a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2

↓ SHA-256

해시1 (32 bytes):
  5f3a7b9c1d8e2f4a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0

↓ RIPEMD-160

해시2 (20 bytes):
  1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0

길이 비교:
  공개키:      33 bytes (66자)
  SHA-256:     32 bytes (64자)
  RIPEMD-160:  20 bytes (40자)
  
→ 20 bytes = 최종 주소의 핵심 부분
```

---

## 2. Base58

### 2.1 한마디로

**Base58 = 사람이 읽기 쉬운 인코딩**

```
비유: 16진수 주소 vs 사람 친화적 주소

16진수:
  1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0
  → 읽기 어려움
  → 오타 내기 쉬움
  → 손으로 쓰기 거의 불가능

Base58:
  JACK1qxyz...abc
  → 읽기 쉬움
  → 오타 감소
  → 손으로 쓸 수 있음
```

---

### 2.2 Base58 vs Base64

**Base64 (일반적):**
```
문자 집합 (64개):
  A-Z (26개)
  a-z (26개)
  0-9 (10개)
  + , / (2개)
  
예시:
  SGVsbG8gV29ybGQ=
  
문제점:
  ❌ 0 (숫자)와 O (대문자 오) - 헷갈림
  ❌ 1 (숫자)와 l (소문자 엘) - 헷갈림
  ❌ 1 (숫자)와 I (대문자 아이) - 헷갈림
  ❌ + , / 기호 - URL에서 문제
  ❌ = 패딩 - 불필요한 문자
```

**Base58 (Bitcoin 방식):**
```
문자 집합 (58개):
  123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz

제외된 문자:
  ❌ 0 (숫자 제로) - 대문자 O와 헷갈림
  ❌ O (대문자 오) - 숫자 0과 헷갈림
  ❌ I (대문자 아이) - 숫자 1, 소문자 l과 헷갈림
  ❌ l (소문자 엘) - 숫자 1, 대문자 I와 헷갈림

장점:
  ✅ 손으로 쓰기 쉬움
  ✅ 읽고 말하기 쉬움
  ✅ QR 코드 효율적
  ✅ URL-safe (특수문자 없음)
  ✅ 이중 클릭으로 전체 선택 가능
```

---

### 2.3 Base58 인코딩 원리

**기본 개념: 진법 변환**
```
10진수 → 58진수 변환

비유:
  10진수 12345를 16진수로: 3039
  10진수 12345를 58진수로: 4dr (Base58 문자표 사용)
```

**변환 과정:**
```
10진수: 12345
58진수로 변환:

  12345 ÷ 58 = 212 ... 나머지 49
  212 ÷ 58 = 3 ... 나머지 38
  3 ÷ 58 = 0 ... 나머지 3
  
역순으로 읽기:
  3 → 문자표[3] = '4'
  38 → 문자표[38] = 'd'  
  49 → 문자표[49] = 'r'
  
결과: "4dr"
```

**실제 예시:**
```
RIPEMD-160 해시 (20 bytes):
  1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0
  
↓ Base58 인코딩

결과 (~25-35자):
  3CMNFxN1oHBc4R9G...
```

---

### 2.4 Base58Check (체크섬 포함)

**문제: 일반 Base58**
```
데이터만 인코딩
→ 오타 시 이상한 주소로 전송
→ 돈 날릴 위험! ⚠️

예:
  올바른 주소: JACK1qxyz...abc
  오타 입력:   JACK1qxyZ...abc (z → Z)
  
  → 다른 주소로 전송
  → 영원히 잃어버림 💀
```

**해결: Base58Check**
```
데이터 + 체크섬 포함
→ 오타 시 자동 감지
→ 전송 차단

과정:
  1. 버전 바이트 (1 byte)
  2. 페이로드 (20 bytes)
  3. 체크섬 계산 (4 bytes)
  4. 모두 합치기
  5. Base58 인코딩
```

---

## 3. 주소 생성 전체 과정

### 3.1 단계별 상세

```
Step 1: 개인키 생성
  d = random(256 bits)
  예: c9afa9d845ba75166b5c215767b1d6934e50c3db36e89b127b8a622b120f6721

Step 2: 공개키 생성
  Q = d × G (타원곡선 스칼라 곱셈)
  압축: 02a1b2c3d4e5f6a7... (33 bytes)

Step 3: SHA-256 해시
  hash1 = SHA-256(공개키)
       = 5f3a7b9c1d8e2f4a... (32 bytes)
  
  목적: 공개키를 안전하게 숨김

Step 4: RIPEMD-160 해시
  hash2 = RIPEMD-160(hash1)
       = 1a2b3c4d5e6f7a8b... (20 bytes)
  
  목적: 주소 길이 단축

Step 5: 버전 바이트 추가
  versioned = 0x4A + hash2
            = 4a1a2b3c4d5e6f7a... (21 bytes)
  
  0x4A = 'J' (JackpotChain 표시)
  
  다른 예:
    Bitcoin: 0x00
    Bitcoin Testnet: 0x6F
    Litecoin: 0x30

Step 6: 체크섬 계산
  double_hash = SHA-256(SHA-256(versioned))
  checksum = double_hash의 처음 4 bytes
          = abcd1234

Step 7: 최종 조합
  final = versioned + checksum
       = 4a1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0abcd1234
       = 25 bytes

Step 8: Base58 인코딩
  address = Base58(final)
         = JACK1qxyz...abc
         
  결과: 약 35자의 사람이 읽을 수 있는 주소
```

---

### 3.2 시각화

```
개인키 (32 bytes)
  ↓ ECDSA 스칼라 곱셈
공개키 (33 bytes)
  ↓ SHA-256
해시1 (32 bytes)
  ↓ RIPEMD-160
해시2 (20 bytes)
  ↓ + 버전 바이트 (1 byte)
버전 해시 (21 bytes)
  ↓ + 체크섬 (4 bytes)
최종 데이터 (25 bytes)
  ↓ Base58 인코딩
주소 (문자열)
  
"JACK1qxyz...abc"
(약 35자)
```

---

## 4. 체크섬의 작동 원리

### 4.1 체크섬 계산

```
입력 데이터:
  버전 + 페이로드 = 21 bytes

계산:
  1단계: SHA-256
    hash1 = SHA-256(입력)
  
  2단계: SHA-256 한 번 더 (Double SHA-256)
    hash2 = SHA-256(hash1)
  
  3단계: 처음 4 bytes 추출
    checksum = hash2[0:4]

왜 두 번?
  - SHA-256에 혹시 모를 취약점 대비
  - Bitcoin 설계 방식 (Length Extension Attack 방어)
```

---

### 4.2 주소 검증 과정

```
사용자가 주소 입력:
  JACK1qxyz...abc

검증 과정:
  1. Base58 디코딩
     → 25 bytes 바이너리 데이터
  
  2. 분리
     버전: 1 byte
     페이로드: 20 bytes
     체크섬: 4 bytes
  
  3. 체크섬 재계산
     expected = SHA-256(SHA-256(버전 + 페이로드))[0:4]
  
  4. 비교
     if 체크섬 == expected:
       ✅ 유효한 주소
     else:
       ❌ 잘못된 주소 (오타!)

오타 감지율:
  4 bytes = 32 bits
  → 2^32 = 약 42억 가지
  → 무작위 오타가 통과할 확률: 1/42억
  → 거의 100% 감지
```

---

## 5. 왜 이렇게 복잡한가?

### 5.1 각 단계의 목적

```
SHA-256:
  목적: 공개키 보호, 길이 균일화
  보안: 2^128 충돌 저항성
  
RIPEMD-160:
  목적: 주소 길이 단축 (저장 공간)
  보안: 2^80 (충분함, 이미 SHA-256로 보호됨)
  
Base58:
  목적: 사람 친화적
  보안: 인코딩일 뿐 (보안 무관)
  
체크섬:
  목적: 오타 방지
  보안: 전송 오류 감지 (100%)
```

---

### 5.2 보안 계층 (Defense in Depth)

```
Layer 1: 개인키
  보안: ECDSA 이산 로그 문제 (2^128)
  
Layer 2: SHA-256
  보안: 충돌 저항성 (2^128)
  공격자가 SHA-256을 깨도 공개키 복구 불가
  
Layer 3: RIPEMD-160
  보안: 충돌 저항성 (2^80)
  공격자가 RIPEMD-160을 깨도 SHA-256이 방어
  
Layer 4: 체크섬
  보안: 전송 오류 감지
  무결성 보장

→ 다층 방어 전략!
```

---

### 5.3 공간 효율성

```
공개키 직접 사용 시:
  33 bytes × Base58 = ~45자
  
현재 방식:
  20 bytes × Base58 = ~35자
  
절감: 약 22%

블록체인 전체:
  1,000,000 주소 × 10 bytes 절감 = 10 MB
  → 의미 있는 절감
```

---

## 6. JackpotChain 주소 예시

### 6.1 주소 형식

```
메인넷 (버전 0x4A):
  JACK1qxyz...abc
  
  특징:
    - 항상 "JACK"으로 시작
    - 35자 내외
    - 대소문자 구분
    - 0, O, I, l 없음

테스트넷 (버전 0x6F):
  JTEST1xyz...def
  
  특징:
    - "JTEST"로 시작
    - 개발/테스트용
    - 실제 가치 없음

P2SH - 스크립트 주소 (버전 0x4B):
  JACK3abc...xyz
  
  특징:
    - "JACK3"으로 시작
    - MultiSig 등 복잡한 조건
```

---

### 6.2 검증 예시 (의사코드)

```
function validateAddress(address):
    try:
        # 1. Base58 디코딩
        decoded = base58_decode(address)
        
        if len(decoded) != 25:
            return false, "잘못된 길이"
        
        # 2. 분리
        version = decoded[0:1]
        payload = decoded[1:21]
        checksum = decoded[21:25]
        
        # 3. 체크섬 재계산
        hash1 = SHA256(version + payload)
        hash2 = SHA256(hash1)
        expected_checksum = hash2[0:4]
        
        # 4. 비교
        if checksum != expected_checksum:
            return false, "체크섬 불일치 - 오타 가능성"
        
        # 5. 버전 확인
        if version == 0x4A:
            return true, "유효한 메인넷 주소"
        else if version == 0x6F:
            return true, "유효한 테스트넷 주소"
        else:
            return false, "알 수 없는 버전"
        
    catch error:
        return false, "디코딩 실패"
```

---

## 7. 실전 팁

### 7.1 주소 사용 시 주의사항

```
✅ 해야 할 것:
  - 복사-붙여넣기 사용 (손으로 입력 금지)
  - 처음 4자, 마지막 4자 육안 확인
  - 테스트 전송 (소액) 후 본 전송
  - QR 코드 활용

❌ 하지 말아야 할 것:
  - 손으로 주소 입력
  - 스크린샷만 보고 입력
  - 검증 없이 전송
  - 의심스러운 주소에 전송
```

---

### 7.2 QR 코드 활용

```
주소를 QR 코드로:
  - 오타 위험 제로
  - 모바일 지갑에서 스캔
  - 빠른 전송

QR 코드 포맷:
  jackpotchain:JACK1qxyz...abc
  또는
  JACK1qxyz...abc

추가 정보 포함 가능:
  jackpotchain:JACK1qxyz...abc?amount=100&label=Coffee
```

---

## 8. 핵심 요약

### 주소 생성 공식

```
주소 = Base58Check(버전 + RIPEMD160(SHA256(공개키)))
```

### 3가지 핵심 개념

**1. RIPEMD-160**
```
- SHA-256의 짧은 버전 (160비트)
- 주소 길이 단축용 (20 bytes)
- 이중 해시로 보안 강화
```

**2. Base58**
```
- 사람이 읽기 쉬운 인코딩
- 헷갈리는 문자 제외 (0, O, I, l)
- URL-safe, 손으로 쓰기 가능
```

**3. Base58Check (체크섬)**
```
- Double SHA-256으로 체크섬 생성
- 오타 자동 감지 (100% 가까이)
- 잘못된 전송 방지
```

---

## 9. 체크리스트

이해했는지 확인:

- [ ] RIPEMD-160이 무엇인지
- [ ] 왜 SHA-256과 RIPEMD-160 둘 다 쓰는지 (보안 + 공간)
- [ ] Base58이 Base64보다 나은 이유 (가독성)
- [ ] 체크섬의 역할 (오타 방지)
- [ ] 공개키 → 주소 전체 과정 (8단계)
- [ ] 주소 검증 방법

---

## 10. 참고 자료

**Bitcoin 주소:**
- Bitcoin Developer Guide - Addresses
- BIP 13: Address Format for P2SH
- Base58Check Encoding

**라이브러리:**
- Python: base58, hashlib
- JavaScript: bs58, crypto
- Go: btcutil

**도구:**
- Bitcoin Address Generator
- QR Code Generator
- Base58 Encoder/Decoder

---

**다음:** [01-cryptography-basics.md](01-cryptography-basics.md)로 돌아가서 Merkle Tree 학습 →
