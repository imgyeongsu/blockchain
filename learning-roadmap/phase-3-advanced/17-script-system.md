# 17. 스마트 컨트랙트 — Script 시스템

> **Phase 3: Advanced**  
> **학습 날짜:** 2025-02-19  
> **난이도:** ⭐⭐⭐☆☆  
> **예상 소요 시간:** 1.5-2시간  
> **선행 학습:** [05. 트랜잭션 심화](../phase-1-core/05-transactions-deep-dive.md), [16. 가챠 시스템](16-gacha-system.md)  
> **성격:** 복습 + 통합 정리 (새 개념보다는 기존 내용을 한 곳에 모음)

---

## 🎯 학습 목표

이 문서를 완료하면:
- [ ] Bitcoin Script의 특성과 한계를 한 문장으로 설명할 수 있다
- [ ] JackpotChain의 4가지 TX 타입별 Script를 구분할 수 있다
- [ ] 잭팟 풀, 소각, Commit-Reveal의 Script 잠금 조건을 이해한다
- [ ] TimeLock의 2가지 방식 (절대/상대)을 안다
- [ ] Script로 할 수 있는 것과 없는 것을 구분할 수 있다
- [ ] Ethereum과의 차이를 명확히 설명할 수 있다

---

## 1. Script 복습 (05번 요약)

### 1.1 핵심 특성

```
Bitcoin Script = UTXO의 잠금/해제 조건을 정의하는 언어

5가지 특성:
  1. 스택 기반: push/pop으로 연산
  2. 튜링 불완전: 반복문(loop) 없음 → 무한 루프 불가능
  3. 상태 없음: 외부 데이터 참조 불가
  4. 결정론적: 같은 입력 → 항상 같은 결과
  5. 제한적: 의도적으로 단순하게 설계

왜 튜링 불완전?
  Ethereum: 튜링 완전 → 뭐든 가능 → 버그도 가능 (DAO 해킹)
  Bitcoin: 튜링 불완전 → 제한적 → 안전
  JackpotChain: Bitcoin 방식 채택 → 6주 MVP에 적합
```

### 1.2 잠금과 해제

```
모든 UTXO에는 2가지 Script가 관여:

script_pubkey (잠금 = 자물쇠):
  UTXO를 만들 때 설정
  "이 조건을 충족하면 소비 가능"

script_sig (해제 = 열쇠):
  UTXO를 소비할 때 제출
  "여기 조건 충족 증명이요"

검증:
  script_sig + script_pubkey를 순서대로 실행
  스택 최종 값이 true → 소비 허용 ✅
  스택 최종 값이 false → 소비 거부 ❌
```

### 1.3 표준 Script 패턴

```
=== P2PKH (Pay to Public Key Hash) — 가장 일반적 ===

잠금 (script_pubkey):
  OP_DUP
  OP_HASH160
  <pubkey_hash>       ← 20 bytes
  OP_EQUALVERIFY
  OP_CHECKSIG

해제 (script_sig):
  <signature>
  <pubkey>

실행 흐름:
  1. [sig, pubkey]           ← script_sig push
  2. [sig, pubkey, pubkey]   ← OP_DUP
  3. [sig, pubkey, hash]     ← OP_HASH160
  4. [sig, pubkey, hash, expected_hash] ← push
  5. [sig, pubkey]           ← OP_EQUALVERIFY (비교 후 제거)
  6. [true]                  ← OP_CHECKSIG (서명 검증)
  → 성공! ✅

의미: "이 공개키의 소유자만 소비 가능"
용도: 일반 JACK/POT 전송 (TX version 1)


=== P2SH (Pay to Script Hash) — 복잡한 조건 ===

잠금 (script_pubkey):
  OP_HASH160
  <script_hash>       ← 20 bytes
  OP_EQUAL

해제 (script_sig):
  <데이터들...>
  <redeem_script>     ← 실제 조건 스크립트

검증 2단계:
  1단계: HASH160(redeem_script) == script_hash? (스크립트 확인)
  2단계: redeem_script 실행 (실제 조건 검증)

의미: "이 해시에 해당하는 스크립트의 조건을 충족하면 소비 가능"
용도: MultiSig, TimeLock, 복합 조건
```

---

## 2. JackpotChain 확장 Script

### 2.1 전체 매핑

```
JackpotChain에는 6종류의 Script 패턴이 필요:

┌─────────────────────┬───────────────────────────────────┐
│ 용도                │ Script 패턴                       │
├─────────────────────┼───────────────────────────────────┤
│ 일반 전송           │ P2PKH (표준)                      │
│ MultiSig 지갑       │ P2SH + MultiSig                  │
│ 잭팟 풀 잠금        │ 특수 (가챠 당첨 증명)             │
│ 소각                │ OP_RETURN (소비 불가)             │
│ Commit UTXO 잠금    │ Hash Lock + P2PKH                │
│ TimeLock            │ CLTV / CSV                        │
└─────────────────────┴───────────────────────────────────┘
```

### 2.2 일반 전송 (P2PKH)

```
TX version 1 — 일반 JACK/POT 전송

이건 Bitcoin과 완전히 동일:
  Alice → Bob: 100 JACK

  Alice의 UTXO (script_pubkey):
    OP_DUP OP_HASH160 <alice_hash> OP_EQUALVERIFY OP_CHECKSIG

  Alice가 소비할 때 (script_sig):
    <alice_sig> <alice_pubkey>

  Bob의 새 UTXO (script_pubkey):
    OP_DUP OP_HASH160 <bob_hash> OP_EQUALVERIFY OP_CHECKSIG

특이사항 없음. 05번에서 배운 그대로.
```

### 2.3 소각 Script (OP_RETURN)

```
목적: JACK을 영구 소멸시키기

2곳에서 사용:
  1. Coinbase TX — 수수료 20% 소각
  2. Exchange TX — 교환 JACK 소각

Script:
  OP_RETURN <data>

OP_RETURN의 특성:
  실행하면 즉시 실패 (false)
  → 이 Output은 절대로 소비 불가
  → UTXO Set에 들어가지 않음 (저장 공간 절약)
  → <data>에 소각 금액 등 메모 기록 가능

예시:
  Output: OP_RETURN <0x01> <1000_0000_0000>
  의미: "Exchange 소각, 1000 JACK"

  Output: OP_RETURN <0x02> <200_0000_0000>
  의미: "수수료 소각, 200 JACK"

중요:
  OP_RETURN Output에는 실제 JACK value = 0
  소각 금액은 TX의 Input - Output 차이로 계산
  <data>는 단순 기록용 (검증은 금액 차이로)
```

### 2.4 잭팟 풀 Script

```
목적: 가챠 당첨 시에만 소비 가능한 잠금

=== 설계 선택지 ===

Option A: 프로토콜 레벨 강제 (단순)
  script_pubkey: OP_DUP OP_HASH160 <jackpot_hash> OP_EQUALVERIFY OP_CHECKSIG
  → 일반 P2PKH처럼 생겼지만
  → 잭팟 주소의 "개인키"를 시스템만 알고 있음
  → 실제로는 Gacha Reveal TX 검증 시 프로토콜이 허용

  장점: Script 자체는 단순, 검증 로직을 코드에서 처리
  단점: Script만 보면 일반 주소와 구분 안 됨

Option B: 특수 Script (명시적)
  script_pubkey:
    OP_IF
      <gacha_reveal_condition>   ← 가챠 당첨 증명
    OP_ELSE
      OP_FALSE                    ← 다른 방법으로는 절대 불가
    OP_ENDIF

  장점: Script에서 의도가 명확히 보임
  단점: Script가 복잡해짐

MVP 선택: Option A (프로토콜 레벨)
  → Script는 단순 P2PKH 형태
  → "잭팟 주소의 UTXO를 소비하는 TX는 version 4(Reveal)여야 함"
  → 이 규칙을 프로토콜 검증에서 강제
  → Script 파서를 복잡하게 만들 필요 없음
```

### 2.5 Commit UTXO Script (Hash Lock + 서명)

```
목적: secret의 원상을 제시하고 + 소유자 서명이 있어야 소비 가능

=== Commit UTXO의 잠금 ===

script_pubkey:
  OP_HASH160
  <commit_hash>           ← SHA256(secret)의 RIPEMD160
  OP_EQUALVERIFY
  OP_DUP
  OP_HASH160
  <user_pubkey_hash>      ← 유저 공개키 해시
  OP_EQUALVERIFY
  OP_CHECKSIG

script_sig (Reveal 시):
  <user_sig>
  <user_pubkey>
  <secret>

실행 흐름:
  1. [sig, pubkey, secret]          ← push
  2. [sig, pubkey, hash(secret)]    ← OP_HASH160
  3. [sig, pubkey, hash, expected]  ← push commit_hash
  4. [sig, pubkey]                  ← OP_EQUALVERIFY ✅
  5. [sig, pubkey, pubkey]          ← OP_DUP
  6. [sig, pubkey, user_hash]       ← OP_HASH160
  7. [sig, pubkey, hash, expected]  ← push user_pubkey_hash
  8. [sig, pubkey]                  ← OP_EQUALVERIFY ✅
  9. [true]                         ← OP_CHECKSIG ✅

2중 보호:
  조건 1: secret을 알아야 함 (Hash Lock)
  조건 2: 유저의 서명이 필요 (P2PKH)
  → secret만 알아도 안 되고, 서명만 있어도 안 됨
  → 둘 다 있어야 소비 가능
```

---

## 3. MultiSig

### 3.1 개념

```
MultiSig = M-of-N 다중 서명
  "N개의 키 중 M개의 서명이 있어야 소비 가능"

예시:
  2-of-3: 키 3개 중 2개의 서명 필요
  → 회사 금고: CEO, CFO, CTO 중 2명이 동의해야

JackpotChain 용도:
  팀 공동 지갑 (6명 중 4명 동의)
  긴급 복구 키 (백업)
```

### 3.2 Script

```
=== Bare MultiSig (직접) ===

script_pubkey:
  OP_2                    ← M = 2
  <pubkey_A>
  <pubkey_B>
  <pubkey_C>
  OP_3                    ← N = 3
  OP_CHECKMULTISIG

script_sig:
  OP_0                    ← 버그 호환 (Bitcoin 레거시)
  <sig_A>
  <sig_C>

의미: A, B, C 중 아무 2명의 서명이면 OK


=== P2SH MultiSig (표준) ===

실제로는 P2SH로 감싸서 사용:

script_pubkey:
  OP_HASH160 <script_hash> OP_EQUAL

script_sig:
  OP_0 <sig_A> <sig_C> <redeem_script>

redeem_script:
  OP_2 <pubkey_A> <pubkey_B> <pubkey_C> OP_3 OP_CHECKMULTISIG

장점:
  script_pubkey가 짧음 (주소 크기 동일)
  조건의 복잡도가 외부에 안 보임
```

### 3.3 MVP에서의 MultiSig

```
필수는 아니지만 있으면 좋은 이유:

  1. 팀 공동 자금 관리
     프로젝트 자금을 6명 중 4명이 동의해야 이동
     → 한 명이 횡령 불가

  2. 잭팟 풀 거버넌스 (미래)
     잭팟 풀의 긴급 출금을 MultiSig로 제어
     → 시스템 오류 시 복구 수단

  3. 학습 가치
     Bitcoin의 핵심 기능 중 하나
     → 구현 경험이 가치 있음

구현 우선순위: Phase 2 이후 (MVP 필수 아님)
```

---

## 4. TimeLock

### 4.1 개념

```
TimeLock = "특정 시간/블록 이후에만 소비 가능"

비유:
  "이 수표는 2026년 3월 1일 이후에만 현금화 가능"

블록체인에서:
  "이 UTXO는 Block #10000 이후에만 소비 가능"
```

### 4.2 두 가지 방식

```
=== CLTV (CheckLockTimeVerify) — 절대 시간 ===

"Block #10000 이후에만 소비 가능"

script_pubkey:
  <10000>
  OP_CHECKLOCKTIMEVERIFY
  OP_DROP
  OP_DUP OP_HASH160 <pubkey_hash> OP_EQUALVERIFY OP_CHECKSIG

검증:
  현재 블록 높이 ≥ 10000? → 소비 허용
  현재 블록 높이 < 10000? → 소비 거부

용도:
  "6개월 후에 잠금 해제되는 보상"
  "특정 높이까지 인출 불가"


=== CSV (CheckSequenceVerify) — 상대 시간 ===

"이 UTXO가 생성된 후 100블록(~50분) 이후에만 소비 가능"

script_pubkey:
  <100>
  OP_CHECKSEQUENCEVERIFY
  OP_DROP
  OP_DUP OP_HASH160 <pubkey_hash> OP_EQUALVERIFY OP_CHECKSIG

검증:
  UTXO 생성 블록 + 100 ≤ 현재 블록? → 소비 허용
  아직 100블록 안 지남? → 소비 거부

용도:
  "생성 후 일정 시간 대기 필요"
  → Commit-Reveal의 최소 간격 강제에 사용 가능!
```

### 4.3 JackpotChain에서의 TimeLock 활용

```
활용 1: Reveal 기한을 Script로 강제

  Commit UTXO의 script_pubkey에 TimeLock 추가:

    <50>                          ← 50블록 이내
    OP_CHECKSEQUENCEVERIFY_MAX    ← (커스텀) 상한 확인
    OP_DROP
    OP_HASH160 <commit_hash> OP_EQUALVERIFY
    OP_DUP OP_HASH160 <user_hash> OP_EQUALVERIFY
    OP_CHECKSIG

  → 50블록 지나면 Reveal 불가
  → Script 레벨에서 기한 강제

  MVP에서는?
    프로토콜 레벨에서 검증 (더 단순)
    "Reveal TX의 블록 높이 - Commit 블록 높이 ≤ 50?"
    → Script에 안 넣어도 됨
    → 나중에 Script로 이전 가능


활용 2: Coinbase 성숙도 (Maturity)

  Bitcoin 규칙:
    Coinbase TX의 Output은 100블록 후에만 소비 가능
    → 체인 Reorg로 Coinbase가 무효화될 위험 방지

  JackpotChain:
    블록 타임 30초 → 100블록 = 50분
    또는 50블록 = 25분 (조정 가능)

  구현:
    Script로 넣지 않고 프로토콜에서 강제 (Bitcoin과 동일)
    → Coinbase Output의 block_height + 100 ≤ 현재 높이?


활용 3: 조건부 잠금 (미래)

  시나리오: "1주일 안에 Bob이 안 가져가면 Alice에게 환불"
  
    OP_IF
      OP_DUP OP_HASH160 <bob_hash> OP_EQUALVERIFY OP_CHECKSIG
    OP_ELSE
      <672>                      ← 672블록 ≈ 7일 아님 (30초 × 672 = 5.6시간... 수정: 20160블록 ≈ 7일)
      OP_CHECKLOCKTIMEVERIFY
      OP_DROP
      OP_DUP OP_HASH160 <alice_hash> OP_EQUALVERIFY OP_CHECKSIG
    OP_ENDIF

  Bob의 해제: OP_TRUE <bob_sig> <bob_pubkey>
  Alice의 환불: OP_FALSE <alice_sig> <alice_pubkey> (40320블록 이후)
```

---

## 5. TX 타입별 Script 통합

### 5.1 전체 매핑

```
=== TX version 1: 일반 전송 ===

Input script_sig:
  <signature> <pubkey>

Output script_pubkey:
  OP_DUP OP_HASH160 <pubkey_hash> OP_EQUALVERIFY OP_CHECKSIG

특이사항: 없음 (표준 P2PKH)


=== TX version 2: Exchange ===

Input script_sig:
  <signature> <pubkey>       ← 일반 서명 (JACK UTXO 소비)

Output[0] script_pubkey:     ← POT 수령
  OP_DUP OP_HASH160 <user_hash> OP_EQUALVERIFY OP_CHECKSIG

Output[1] script_pubkey:     ← 거스름돈 (선택)
  OP_DUP OP_HASH160 <user_hash> OP_EQUALVERIFY OP_CHECKSIG

Output[2]:                   ← 소각
  OP_RETURN <burn_data>

특이사항: Output[2]의 OP_RETURN (소비 불가, UTXO Set 미포함)


=== TX version 3: Gacha Commit ===

Input script_sig:
  <signature> <pubkey>       ← 일반 서명 (POT UTXO 소비)

Output[0] script_pubkey:     ← 거스름돈
  OP_DUP OP_HASH160 <user_hash> OP_EQUALVERIFY OP_CHECKSIG

Output[1] script_pubkey:     ← Commit UTXO (Hash Lock + P2PKH)
  OP_HASH160 <commit_hash> OP_EQUALVERIFY
  OP_DUP OP_HASH160 <user_hash> OP_EQUALVERIFY OP_CHECKSIG

특이사항: Commit UTXO의 이중 잠금 (secret + 서명)


=== TX version 4: Gacha Reveal ===

Input[0] script_sig:         ← Commit UTXO 소비
  <signature> <pubkey> <secret>

Input[1~N] script_sig:       ← 잭팟 풀 UTXO 소비 (당첨 시)
  (프로토콜 레벨에서 허용)

Output[0] script_pubkey:     ← 당첨금 (당첨 시)
  OP_DUP OP_HASH160 <winner_hash> OP_EQUALVERIFY OP_CHECKSIG

Output[1] script_pubkey:     ← 잭팟 거스름돈 (당첨 시)
  OP_DUP OP_HASH160 <jackpot_hash> OP_EQUALVERIFY OP_CHECKSIG

특이사항:
  Input[0]에 secret 포함 (Hash Lock 해제)
  잭팟 풀 UTXO 소비는 프로토콜이 허용 (당첨 검증 후)
```

### 5.2 한눈에 보기

```
┌──────────┬──────────────────┬──────────────────┬──────────────┐
│ version  │ Input 해제       │ Output 잠금      │ 특수 Output  │
├──────────┼──────────────────┼──────────────────┼──────────────┤
│ 1 일반   │ P2PKH 서명       │ P2PKH            │ 없음         │
│ 2 교환   │ P2PKH 서명       │ P2PKH + P2PKH    │ OP_RETURN    │
│ 3 Commit │ P2PKH 서명       │ P2PKH + HashLock │ 없음         │
│ 4 Reveal │ HashLock + 서명  │ P2PKH + P2PKH    │ 없음         │
└──────────┴──────────────────┴──────────────────┴──────────────┘
```

---

## 6. Script vs 프로토콜: 어디서 검증하나?

### 6.1 설계 결정

```
JackpotChain의 검증 규칙 중에는
Script로 구현할 수 있는 것과 프로토콜로 강제하는 것이 있음:

Script로 하는 것:
  ✅ UTXO 소유권 증명 (P2PKH 서명)
  ✅ Hash Lock (Commit-Reveal의 secret 검증)
  ✅ MultiSig (다중 서명)
  ✅ OP_RETURN (소각)

프로토콜로 하는 것:
  ✅ TX version별 검증 분기
  ✅ 에셋 보존 법칙 (Input ≥ Output)
  ✅ POT Mint 허용 (version 2만)
  ✅ 수수료 분배 (50/30/20)
  ✅ 당첨 계산 (SHA256 + threshold)
  ✅ Reveal 기한 (50블록)
  ✅ 당첨금 Commit 시점 고정
  ✅ 잭팟 풀 UTXO 소비 허용/거부
  ✅ Coinbase 성숙도 (100블록)
```

### 6.2 왜 이렇게 나누나?

```
Script에 넣으면 좋은 것:
  → UTXO 단위의 조건 (이 UTXO를 누가 쓸 수 있나?)
  → 범용적이고 재사용 가능한 패턴
  → Script 엔진이 자동으로 검증

프로토콜에 넣는 게 나은 것:
  → TX 단위의 규칙 (TX 전체의 에셋 밸런스)
  → 블록 단위의 규칙 (Coinbase 분배, 난이도)
  → JackpotChain 전용 규칙 (가챠, 교환)
  → Script로 표현하면 너무 복잡해지는 것

MVP 원칙:
  "Script는 최소한으로, 나머지는 프로토콜에서"
  → Script 엔진을 단순하게 유지
  → 검증 로직을 코드에서 명확하게
  → 나중에 필요하면 Script로 이전 가능
```

---

## 7. Ethereum과의 비교

### 7.1 근본 차이

```
┌─────────────────┬──────────────────┬──────────────────┐
│                 │ Bitcoin/         │ Ethereum         │
│                 │ JackpotChain     │                  │
├─────────────────┼──────────────────┼──────────────────┤
│ 언어            │ Script (스택)    │ Solidity (고급)  │
│ 튜링 완전       │ ❌               │ ✅               │
│ 상태            │ Stateless        │ Stateful         │
│ 실행 환경       │ TX 검증 시       │ EVM (가상 머신)  │
│ Gas/수수료      │ TX 크기 비례     │ 연산량 비례      │
│ 반복문          │ ❌               │ ✅               │
│ 외부 호출       │ ❌               │ ✅ (다른 컨트랙트)│
│ 복잡도          │ 낮음             │ 높음             │
│ 보안 위험       │ 낮음             │ 높음 (버그 가능) │
│ 구현 시간       │ 짧음             │ 김               │
└─────────────────┴──────────────────┴──────────────────┘
```

### 7.2 각 방식의 장단점

```
Bitcoin Script 방식:

  장점:
    ✅ 단순 → 버그 적음
    ✅ 예측 가능 → 실행 시간 보장
    ✅ 구현 빠름 → MVP 적합
    ✅ 검증 빠름 → 성능 좋음

  단점:
    ❌ 복잡한 로직 불가 (DEX, DAO 등)
    ❌ 확장성 제한
    ❌ 새 기능 = 프로토콜 변경 필요

Ethereum Solidity 방식:

  장점:
    ✅ 무엇이든 프로그래밍 가능
    ✅ 새 기능 = 컨트랙트 배포 (프로토콜 변경 불필요)
    ✅ 생태계 풍부 (DeFi, NFT 등)

  단점:
    ❌ 복잡 → 버그 많음 (DAO 해킹, 수십억 달러 손실)
    ❌ Gas 계산 복잡
    ❌ 구현 난이도 높음
    ❌ 6주 MVP에 부적합

JackpotChain의 선택:
  Bitcoin Script + 프로토콜 레벨 확장
  → 가챠/교환 같은 특수 로직은 프로토콜에
  → UTXO 잠금/해제는 Script에
  → 단순하면서도 필요한 기능 충족
```

---

## 8. Script로 할 수 있는 것 / 없는 것

### 8.1 할 수 있는 것

```
✅ 소유권 증명 (P2PKH, P2SH)
✅ 다중 서명 (MultiSig)
✅ 시간 잠금 (CLTV, CSV)
✅ 해시 잠금 (Hash Lock — Commit-Reveal)
✅ 소각 (OP_RETURN)
✅ 조건 분기 (OP_IF/OP_ELSE)
✅ 기본 연산 (비교, 해시, 서명 검증)
```

### 8.2 할 수 없는 것

```
❌ 반복문 (루프)
   → 무한 루프 방지를 위해 의도적으로 제외
   
❌ 외부 상태 참조
   → "다른 UTXO의 값"이나 "현재 풀 잔액" 같은 것
   → Script 안에서 알 수 없음
   → 프로토콜이 대신 확인
   
❌ 복잡한 연산
   → 곱셈, 나눗셈 비활성화 (Bitcoin)
   → JackpotChain에서도 필요 없음
   
❌ 네트워크 호출
   → 다른 노드나 외부 API 참조 불가
   → 결정론적이어야 하니까
   
❌ UTXO 생성
   → Script는 "검증"만 함
   → 새 UTXO를 만드는 건 TX 구조의 역할
```

---

## 9. MVP 구현 가이드

### 9.1 Script 엔진 구현 범위

```
Phase 1 (필수):
  ✅ OP_DUP, OP_HASH160, OP_EQUALVERIFY, OP_CHECKSIG
     → P2PKH 지원 (일반 전송)
  ✅ OP_RETURN
     → 소각 처리
  ✅ 스택 기본 연산 (push, pop)

Phase 2 (가챠):
  ✅ Hash Lock 지원 (OP_HASH160 + OP_EQUALVERIFY)
     → Commit UTXO 잠금/해제
  ✅ 복합 Script (Hash Lock + P2PKH)

Phase 3 (확장):
  ⬜ OP_CHECKMULTISIG → MultiSig
  ⬜ OP_CHECKLOCKTIMEVERIFY → 절대 TimeLock
  ⬜ OP_CHECKSEQUENCEVERIFY → 상대 TimeLock
  ⬜ OP_IF/OP_ELSE → 조건 분기
  ⬜ P2SH 지원
```

### 9.2 단순화 전략

```
MVP 접근:

  1. Script 엔진은 최소 OP_CODE만 지원
  2. 나머지 검증은 프로토콜 코드에서 처리
  3. P2PKH 패턴을 인식하면 빠른 경로로 처리 (최적화)
  4. 알 수 없는 Script → 거부 (안전하게)

예시:
  TX 수신 → Script 패턴 인식
    P2PKH? → 빠른 서명 검증
    OP_RETURN? → 소각 처리
    Hash Lock + P2PKH? → Commit UTXO 처리
    그 외? → 거부 (MVP에서는 미지원)
```

---

## 10. 핵심 요약

### Script 특성
```
스택 기반, 튜링 불완전, 상태 없음, 결정론적
→ 단순하지만 안전
→ JackpotChain MVP에 적합
```

### 6종 Script 패턴
```
P2PKH: 일반 전송 (서명 검증)
P2SH + MultiSig: 다중 서명
OP_RETURN: 소각 (소비 불가)
Hash Lock + P2PKH: Commit UTXO (secret + 서명)
CLTV: 절대 시간 잠금
CSV: 상대 시간 잠금
```

### Script vs 프로토콜
```
Script: UTXO 소유권, 잠금/해제 조건
프로토콜: 에셋 밸런스, 수수료, 가챠 규칙, Mint/Burn
→ "Script는 최소한으로, 나머지는 프로토콜에서"
```

### Bitcoin vs Ethereum
```
Bitcoin Script: 단순, 안전, 제한적
Solidity: 강력, 위험, 복잡
JackpotChain: Bitcoin Script + 프로토콜 확장
```

---

## 11. 체크리스트

이해했는지 확인:

- [ ] Script의 5가지 특성
- [ ] P2PKH의 실행 흐름
- [ ] OP_RETURN의 역할과 UTXO Set 영향
- [ ] Commit UTXO의 이중 잠금 (Hash Lock + P2PKH)
- [ ] MultiSig의 M-of-N 개념
- [ ] CLTV(절대)와 CSV(상대)의 차이
- [ ] TX version별 Script 매핑
- [ ] Script에서 하는 것 vs 프로토콜에서 하는 것의 구분
- [ ] Ethereum과의 근본 차이
- [ ] MVP Script 엔진 구현 범위

---

## 12. 다음 학습

### Phase 3 완료!
```
✅ 13. 멀티에셋 시스템
✅ 14. 토크노믹스
✅ 15. Exchange 모듈
✅ 16. 가챠 시스템
✅ 17. Script 시스템
```

### 다음:
```
→ Phase 4: 최적화
  - 성능 최적화 (TPS, 병렬 검증, 캐싱)
  - 저장소 설계 (LevelDB, 인덱싱, Pruning)
  - 보안 강화 (입력 검증, Rate Limiting)
  - 테스트 전략 (단위/통합/시나리오)
```

---

## 13. 참고 자료

**Bitcoin Script:**
- Bitcoin Wiki - Script
- BIP 16: P2SH
- BIP 65: OP_CHECKLOCKTIMEVERIFY
- BIP 112: OP_CHECKSEQUENCEVERIFY
- Mastering Bitcoin - Chapter 7

**Hash Lock:**
- Hash Time-Locked Contracts (HTLC)
- Atomic Swap Protocols

**비교:**
- Bitcoin Script vs Ethereum Solidity
- UTXO Script vs Account Smart Contracts

---

**이전:** [16. 가챠 시스템](16-gacha-system.md)  
**다음:** Phase 4 — 최적화 →
