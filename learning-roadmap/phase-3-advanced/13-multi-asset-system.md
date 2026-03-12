# 13. 멀티에셋 시스템 (Multi-Asset System)

> **Phase 3: Advanced**  
> **학습 날짜:** 2025-02-19  
> **난이도:** ⭐⭐⭐⭐☆  
> **예상 소요 시간:** 2-3시간  
> **선행 학습:** [03. UTXO vs Account](../phase-0-foundation/03-utxo-vs-account.md), [05. 트랜잭션 심화](../phase-1-core/05-transactions-deep-dive.md), [07. UTXO Set 관리](../phase-1-core/07-utxo-set-management.md)

---

## 🎯 학습 목표

이 문서를 완료하면:
- [ ] JackpotChain의 에셋 2종 체계 (JACK, POT)를 설명할 수 있다
- [ ] 네이티브 에셋과 파생 에셋의 차이를 이해한다
- [ ] Asset Policy와 Mint/Burn 규칙을 설명할 수 있다
- [ ] 시스템 주소 (잭팟 풀, 소각)의 작동 원리를 안다
- [ ] Coinbase TX의 수수료 분배 구조를 이해한다
- [ ] UTXO에서 멀티에셋을 저장하고 검증하는 방법을 안다
- [ ] Bitcoin과의 차이점을 명확히 구분할 수 있다

---

## 1. 왜 멀티에셋인가?

### 1.1 Bitcoin의 한계

```
Bitcoin:
  에셋 1종: BTC (네이티브 코인)
  다른 토큰? → 불가능 (네이티브하게)
  
  우회 방법:
    Colored Coins: TX에 메타데이터 끼워넣기
    Ordinals: satoshi에 데이터 새기기
    → 전부 "트릭"이지 네이티브가 아님
    → 노드가 토큰을 인식하지 못함
    → 별도 인덱서 필요
```

### 1.2 JackpotChain의 선택

```
JackpotChain:
  Cardano 스타일 네이티브 멀티에셋
  → UTXO 자체에 여러 에셋 포함
  → 노드가 에셋을 직접 인식하고 검증
  → 별도 인덱서 불필요

하지만 Cardano와 다른 점:
  Cardano: 누구나 에셋 발행 가능 (수천 종)
  JackpotChain: 딱 2종만 (JACK + POT)
  → 훨씬 단순! 6주 MVP에 적합
```

### 1.3 경제 루프

```
JackpotChain의 전체 흐름:

  ┌─────────────────────────────────────────┐
  │                                         │
  │   채굴 ──→ JACK 생성 (블록 보상)         │
  │              │                          │
  │              ├─→ 전송/거래 (수수료 발생)  │
  │              │     │                    │
  │              │     ├─ 채굴자 50%         │
  │              │     ├─ 잭팟 풀 30%        │
  │              │     └─ 소각 20%           │
  │              │                          │
  │              └─→ Exchange ──→ POT 생성   │
  │                               │         │
  │                               └─→ 가챠   │
  │                                    │     │
  │                          당첨! ←───┘     │
  │                            │             │
  │                     잭팟 풀에서 JACK 지급  │
  │                                         │
  └─────────────────────────────────────────┘

에셋 2종만으로 완전한 경제 루프 형성!
NFT 없음 — 가챠 보상은 축적된 JACK
```

---

## 2. 에셋 정의

### 2.1 JACK (네이티브 코인)

```
JACK = JackpotChain의 기축 통화

역할:
  1. 가치 저장 (보유)
  2. 거래 수단 (전송)
  3. 수수료 지불 (TX 처리 비용)
  4. 채굴 보상 (블록 생성 인센티브)
  5. 가챠 당첨금 (잭팟 풀에서 지급)

생성 방법:
  Coinbase TX만 가능 (채굴)
  → 블록당 50 JACK (고정, 반감기 없음)

소멸 방법:
  소각 주소로 전송
  → OP_RETURN (영구 소멸)

단위:
  1 JACK = 100,000,000 satoshi (10^8)
  최소 단위: 1 satoshi = 0.00000001 JACK
  
  → Bitcoin과 동일한 정밀도
  → 소수점 연산 없이 정수로 처리

식별:
  asset_id = "" (빈 문자열)
  → 네이티브 코인은 별도 ID 불필요
```

### 2.2 POT (게임 토큰)

```
POT = 가챠 플레이 전용 토큰

역할:
  1. 가챠 플레이 비용 (POT으로만 가챠 가능)
  2. JACK과의 교환 수단

생성 방법:
  Exchange TX만 가능 (JACK → POT 교환)
  → 100 JACK = 1 POT (고정 비율, v1)
  → JACK은 소각됨 (Exchange 시)

소멸 방법:
  가챠 플레이 시 소비
  → POT은 소각 (시스템에서 제거)

단위:
  1 POT = 100,000,000 단위 (10^8)
  최소 단위: 0.00000001 POT

식별:
  asset_id = "POT"
```

### 2.3 비교

```
┌───────────────┬──────────────────┬──────────────────┐
│               │ JACK             │ POT              │
├───────────────┼──────────────────┼──────────────────┤
│ 종류          │ 네이티브 코인     │ 파생 토큰        │
│ 생성          │ Coinbase (채굴)   │ Exchange TX      │
│ 소멸          │ 소각 주소         │ 가챠 소비        │
│ 수수료        │ JACK으로 지불     │ 수수료 불가      │
│ 발행량        │ 무제한 (50/블록)  │ JACK 교환에 비례 │
│ asset_id      │ "" (빈 문자열)   │ "POT"            │
│ 용도          │ 범용             │ 가챠 전용        │
└───────────────┴──────────────────┴──────────────────┘
```

---

## 3. Asset Policy (발행 규칙)

### 3.1 개념

```
Asset Policy = "이 에셋은 어떤 조건에서 생성/소멸 가능한가?"

Bitcoin:
  BTC는 Coinbase에서만 생성
  → Policy가 프로토콜에 하드코딩

Cardano:
  누구나 Policy를 만들어서 에셋 발행 가능
  → Policy Script로 조건 정의
  → policy_id = hash(policy_script)

JackpotChain:
  JACK과 POT의 Policy가 프로토콜에 하드코딩
  → 별도 Policy Script 불필요
  → 단순하지만 확장성 제한 (MVP에 적합)
```

### 3.2 JACK의 Mint Policy

```
JACK 발행 규칙:

  WHERE: Coinbase TX의 Output에서만
  WHO:   채굴자 (블록을 성공적으로 채굴한 노드)
  HOW MUCH: 정확히 50 JACK (블록 보상)
            + TX 수수료의 50% (채굴자 몫)
  WHEN:  매 블록마다 1회

검증:
  블록 수신 시 Coinbase TX 확인:
    ✅ 첫 번째 TX인가?
    ✅ Input이 없는가? (Coinbase 형식)
    ✅ Output 합계 ≤ 50 JACK + 수수료 총합?
    ✅ 수수료 분배가 규칙대로인가? (50/30/20)

위반 시:
  블록 전체 거부
  해당 피어 Misbehavior 점수 증가
```

### 3.3 POT의 Mint Policy

```
POT 발행 규칙:

  WHERE: Exchange TX의 Output에서만
  WHO:   JACK 보유자 (교환 요청자)
  HOW MUCH: Input JACK ÷ 100 (고정 비율)
  WHEN:  Exchange TX가 블록에 포함될 때

검증:
  Exchange TX 수신 시:
    ✅ TX version == 2 (Exchange 타입)
    ✅ Input에 충분한 JACK?
    ✅ Output의 POT = Input JACK ÷ 100?
    ✅ Input JACK은 소각되는가? (소각 주소로 전송)
    ✅ 수수료도 JACK으로 지불되었는가?

예시:
  Input: 1000 JACK
  Output[0]: 10 POT → 요청자
  Output[1]: 소각 (1000 JACK - 수수료)
  수수료: 0.1 JACK
```

### 3.4 POT의 Burn Policy

```
POT 소멸 규칙:

  WHERE: Gacha Commit TX에서
  WHO:   POT 보유자 (가챠 플레이어)
  HOW MUCH: 가챠 1회 비용 (예: 1 POT)
  WHEN:  Gacha Commit TX가 블록에 포함될 때

검증:
  Gacha Commit TX 수신 시:
    ✅ TX version == 3 (Gacha Commit 타입)
    ✅ Input에 충분한 POT?
    ✅ POT이 소각되는가? (Output에 POT 없음)
    ✅ Commit 해시가 올바른 형식인가?
```

---

## 4. UTXO 멀티에셋 구조

### 4.1 Output 구조

```
Bitcoin Output:
  ┌──────────────────────────┐
  │ value (8 bytes)          │  금액 (satoshi)
  │ script_pubkey (가변)     │  잠금 조건
  └──────────────────────────┘

JackpotChain Output:
  ┌──────────────────────────┐
  │ jack_value (8 bytes)     │  JACK 금액
  │ assets (가변)            │  추가 에셋 맵
  │   ├─ count (VarInt)      │  에셋 종류 수
  │   ├─ asset_id (VarStr)   │  에셋 식별자
  │   └─ amount (8 bytes)    │  수량
  │ script_pubkey (가변)     │  잠금 조건
  └──────────────────────────┘
```

### 4.2 실제 UTXO 예시

```
=== JACK만 있는 UTXO (일반 전송) ===

{
  jack_value: 100_0000_0000,    // 100 JACK
  assets: {},                    // 추가 에셋 없음
  script_pubkey: <P2PKH Alice>
}


=== POT이 포함된 UTXO ===

{
  jack_value: 5_0000_0000,      // 5 JACK (수수료용 최소 보유)
  assets: {
    "POT": 10_0000_0000         // 10 POT
  },
  script_pubkey: <P2PKH Bob>
}


=== 여러 에셋이 섞인 UTXO ===

{
  jack_value: 50_0000_0000,     // 50 JACK
  assets: {
    "POT": 3_0000_0000          // 3 POT
  },
  script_pubkey: <P2PKH Charlie>
}
```

### 4.3 최소 JACK 규칙

```
문제:
  POT만 있고 JACK이 0인 UTXO를 만들면?
  → 수수료를 지불할 수 없음!
  → 이 UTXO는 "갇히는" 상태 (소비하려면 수수료 필요)

해결: 최소 JACK 규칙 (Minimum JACK)

  모든 UTXO는 최소 JACK을 포함해야 함
  
  MIN_JACK = 0.01 JACK (1,000,000 satoshi)
  
  → POT를 보내더라도 최소 0.01 JACK 함께 보유
  → Dust 방지와 동일한 원리

검증:
  Output 생성 시:
    if output.jack_value < MIN_JACK:
      if output.assets가 비어있고 output.jack_value == 0:
        OP_RETURN (소각) → 허용
      else:
        거부! "최소 JACK 미충족"

Cardano 참고:
  Cardano도 동일한 문제 → "Min ADA" 규칙
  → 토큰을 보내려면 최소 ADA도 함께 보내야 함
```

---

## 5. 시스템 주소

### 5.1 개념

```
시스템 주소 = 개인키가 없는 특수 목적 주소

일반 주소:
  개인키 → 공개키 → 주소
  소유자가 서명해서 자유롭게 사용

시스템 주소:
  개인키 없음
  특수 조건에서만 사용 가능 (또는 아예 사용 불가)

비유:
  일반 주소 = 내 금고 (내 열쇠로 열기)
  잭팟 주소 = 공공 모금함 (특수 조건으로만 열림)
  소각 주소 = 블랙홀 (넣으면 영원히 사라짐)
```

### 5.2 잭팟 풀 주소

```
주소: JACK_JACKPOT_POOL_ADDRESS (하드코딩)

특성:
  ┌─────────────────────────────────────┐
  │ 돈 넣기: 누구나 가능                 │
  │   → Coinbase TX에서 수수료 30% 전송  │
  │   → 일반 Output으로 생성            │
  │                                     │
  │ 돈 빼기: 가챠 당첨 시에만            │
  │   → Gacha Reveal TX에서만 소비 가능  │
  │   → 일반 서명으로는 절대 불가         │
  └─────────────────────────────────────┘

잠금 조건 (script_pubkey):
  일반 P2PKH가 아닌 특수 Script
  → "가챠 당첨 증명이 있으면 소비 허용"
  → 또는 프로토콜 레벨에서 강제
    (Script 없이 TX 타입으로 검증)

잔액 조회:
  잭팟 풀 잔액 = 잭팟 주소의 모든 UTXO 합산
  → 블록체인에서 누구나 계산 가능
  → 투명하고 검증 가능
```

### 5.3 잭팟 풀의 UTXO 축적

```
=== 블록마다 수수료 30%가 쌓이는 과정 ===

Block #100:
  TX 수수료 총합: 10 JACK
  잭팟 몫: 3 JACK
  
  Coinbase TX Output[1]:
    3 JACK → 잭팟 풀 주소   ← UTXO ① 생성

Block #101:
  TX 수수료 총합: 8 JACK
  잭팟 몫: 2.4 JACK
  
  Coinbase TX Output[1]:
    2.4 JACK → 잭팟 풀 주소 ← UTXO ② 생성

Block #102:
  TX 수수료 총합: 15 JACK
  잭팟 몫: 4.5 JACK
  
  Coinbase TX Output[1]:
    4.5 JACK → 잭팟 풀 주소 ← UTXO ③ 생성

...

Block #200 시점:
  잭팟 풀 UTXO:
    UTXO ①: 3 JACK
    UTXO ②: 2.4 JACK
    UTXO ③: 4.5 JACK
    ... (100개)
    
  잭팟 풀 잔액 = Σ(전부) = 예: 350 JACK
  
→ 별도 DB 변수가 아님!
→ 그냥 잭팟 주소의 UTXO 합계!
→ 기존 UTXO Set 로직 그대로 활용!
```

### 5.4 잭팟 풀에서 당첨금 지급

```
=== 가챠 당첨 시 ===

잭팟 풀 잔액: 350 JACK (UTXO 100개)
당첨금: 풀의 60% = 210 JACK

Gacha Payout TX:
  Input: 잭팟 주소의 UTXO 여러 개 소비
    UTXO ①: 3 JACK
    UTXO ②: 2.4 JACK
    UTXO ③: 4.5 JACK
    ... (210 JACK 이상 될 때까지)
  
  Output[0]: 210 JACK → 당첨자 주소
  Output[1]: 나머지 → 잭팟 주소 (거스름돈)

검증:
  ✅ Gacha Reveal TX에서 당첨이 증명되었는가?
  ✅ 당첨금 = Commit 블록 시점의 풀 잔액 × 비율?
  ✅ 거스름돈이 잭팟 주소로 돌아가는가?

결과:
  당첨자: 210 JACK 수령!
  잭팟 풀: 350 - 210 = 140 JACK 남음
  → 다음 블록부터 다시 수수료로 쌓이기 시작
```

### 5.5 소각 주소

```
주소: JACK_BURN_ADDRESS (하드코딩)

특성:
  ┌─────────────────────────────────────┐
  │ 돈 넣기: 가능                       │
  │   → Coinbase TX에서 수수료 20%      │
  │   → Exchange TX에서 소각분          │
  │                                     │
  │ 돈 빼기: 절대 불가능                 │
  │   → OP_RETURN Script               │
  │   → 어떤 조건으로도 소비 불가        │
  └─────────────────────────────────────┘

구현 방식 2가지:

방식 A: OP_RETURN (UTXO 생성 안 함)
  Output: OP_RETURN <소각 금액 기록>
  → UTXO Set에 들어가지 않음
  → 저장 공간 절약
  → 소각 총량은 블록체인 스캔으로 계산

방식 B: 소비 불가능한 UTXO
  Output: 소각 주소로 전송
  script_pubkey: OP_FALSE (항상 실패)
  → UTXO Set에 들어감 (비효율)
  → 잔액 조회는 쉬움

JackpotChain 선택: 방식 A (OP_RETURN)
  → UTXO Set 비대화 방지
  → 소각 기록은 블록에 남음
```

---

## 6. Coinbase TX 수수료 분배

### 6.1 구조

```
=== 블록 #1000 ===

블록 내 TX들의 수수료 총합: 10 JACK

Coinbase TX:
  Input: 없음 (Coinbase)

  Output[0]: 55 JACK → 채굴자 주소
             = 블록 보상 50 + 수수료 50% (5)
  
  Output[1]: 3 JACK → 잭팟 풀 주소
             = 수수료 30%
  
  Output[2]: OP_RETURN (2 JACK 소각 기록)
             = 수수료 20%

총 발행: 50 JACK (블록 보상만 순수 발행)
총 분배: 50 + 10 = 60 JACK
소각:    2 JACK (유통에서 제거)
```

### 6.2 검증 규칙

```
Coinbase TX 검증:

Step 1: 기본 형식
  ✅ 블록의 첫 번째 TX인가?
  ✅ Input이 없는가?
  ✅ Output이 최소 1개 있는가?

Step 2: 수수료 계산
  total_fee = 0
  for tx in block.transactions[1:]:  // Coinbase 제외
    input_sum = Σ(각 Input의 UTXO 값)
    output_sum = Σ(각 Output의 값)
    total_fee += (input_sum - output_sum)

Step 3: Output 검증
  miner_max = 50_JACK + (total_fee × 50%)
  jackpot_expected = total_fee × 30%
  burn_expected = total_fee × 20%
  
  ✅ Output[0] (채굴자) ≤ miner_max?
  ✅ Output[1] (잭팟)  == jackpot_expected?
  ✅ Output[2] (소각)  == burn_expected?

  주의: 채굴자는 자기 몫을 덜 가져갈 수 있음 (≤)
       잭팟과 소각은 정확해야 함 (==)

Step 4: 수수료가 0이면?
  잭팟 Output과 소각 Output 생략 가능
  → Coinbase TX가 Output 1개만 (채굴자 50 JACK)
```

### 6.3 수수료가 없는 블록

```
TX가 Coinbase 하나뿐인 블록:
  (아무도 TX를 안 보낸 경우)

Coinbase TX:
  Output[0]: 50 JACK → 채굴자
  
  끝! (수수료 0이므로 분배할 것 없음)

이런 블록도 유효함:
  블록 보상 50 JACK만 발행
  잭팟/소각 없음
```

---

## 7. TX 타입별 에셋 흐름

### 7.1 일반 전송 (version 1)

```
Alice → Bob: 100 JACK 전송

TX (version 1):
  Input[0]: Alice의 UTXO (150 JACK)
  
  Output[0]: 100 JACK → Bob
  Output[1]: 49.9 JACK → Alice (거스름돈)
  
  수수료: 0.1 JACK

에셋 규칙:
  각 에셋마다 Input ≥ Output + Fee
  JACK: 150 ≥ 100 + 49.9 + 0.1 ✅
  
  → JACK만 존재, POT 없음
  → 가장 단순한 케이스
```

### 7.2 POT 전송 (version 1)

```
Bob → Charlie: 5 POT 전송

TX (version 1):
  Input[0]: Bob의 UTXO (5 JACK + 10 POT)
  
  Output[0]: 0.01 JACK + 5 POT → Charlie
  Output[1]: 4.89 JACK + 5 POT → Bob (거스름돈)
  
  수수료: 0.1 JACK

에셋 규칙:
  JACK: 5 ≥ 0.01 + 4.89 + 0.1 ✅
  POT:  10 ≥ 5 + 5 ✅
  
  주의: 수수료는 반드시 JACK으로만!
       POT으로 수수료 불가
```

### 7.3 Exchange TX (version 2)

```
Alice: 1000 JACK → 10 POT 교환

TX (version 2):
  Input[0]: Alice의 UTXO (1100 JACK)

  Output[0]: 0.01 JACK + 10 POT → Alice
             (교환 결과)
  Output[1]: 99.89 JACK → Alice
             (거스름돈, 교환에 안 쓴 JACK)
  Output[2]: OP_RETURN (1000 JACK 소각 기록)
             (교환에 사용된 JACK → 소각)
  
  수수료: 0.1 JACK

에셋 규칙 (특수):
  JACK Input:  1100
  JACK Output: 0.01 + 99.89 + 0.1(fee) = 100
  JACK 소각:   1000
  → 1100 = 100 + 1000 ✅

  POT Input:   0 (없었음)
  POT Output:  10
  → POT이 새로 생성됨! (Mint)
  → Mint 양 = 소각 JACK ÷ 100 = 10 ✅

핵심:
  POT는 "무에서 유"가 아님
  → JACK을 태운 대가로 생성됨
  → 교환 비율 검증이 곧 Mint 검증
```

### 7.4 Gacha Commit TX (version 3)

```
Bob: 1 POT으로 가챠 플레이

TX (version 3):
  Input[0]: Bob의 UTXO (5 JACK + 3 POT)

  Output[0]: 4.9 JACK + 2 POT → Bob (거스름돈)
  Output[1]: Commit UTXO
             (특수 Script: hash(secret) 포함)
  
  수수료: 0.1 JACK
  POT 소비: 1 POT (소각)

에셋 규칙:
  JACK: 5 ≥ 4.9 + 0.1 ✅
  POT:  3 → Output에 2 POT + 소비 1 POT = 3 ✅
  
  POT 1개가 사라짐 (Burn)
  → 가챠 비용으로 소각
```

### 7.5 Gacha Reveal TX (version 4)

```
Bob: 가챠 결과 확인

TX (version 4):
  Input[0]: Commit UTXO (Bob의 것)

  데이터: secret (원본 공개)

  당첨 계산:
    result = SHA256(secret + commit_block_hash)
    당첨? = result < threshold

Case A: 꽝
  Output[0]: 잔여 JACK → Bob (Commit UTXO의 JACK)
  → 끝! 풀에서 아무것도 안 나감

Case B: 당첨!
  당첨금 = Commit 블록 시점 잭팟 풀 잔액 × 60%
  
  Input[1~N]: 잭팟 풀 UTXO들 (당첨금 충당)
  
  Output[0]: 당첨금 JACK → Bob
  Output[1]: 잔여 JACK → 잭팟 풀 주소 (거스름돈)

핵심:
  당첨금은 Commit 블록 시점 기준
  → Reveal을 늦춰도 이득 없음!
```

---

## 8. 에셋 검증 통합

### 8.1 일반 규칙 (모든 TX)

```
규칙 1: JACK 보존
  Σ(Input JACK) ≥ Σ(Output JACK) + Fee
  Fee = Σ(Input JACK) - Σ(Output JACK) - Σ(소각 JACK)
  Fee ≥ MIN_FEE

규칙 2: POT 보존 (일반 TX)
  Σ(Input POT) ≥ Σ(Output POT)
  → POT은 수수료로 사용 불가

규칙 3: 최소 JACK
  모든 Output의 jack_value ≥ MIN_JACK
  (OP_RETURN 제외)

규칙 4: Mint/Burn 금지 (일반 TX)
  Output에 새 에셋 등장 불가
  → Exchange TX (version 2)에서만 POT Mint
  → Gacha Commit TX (version 3)에서만 POT Burn
```

### 8.2 TX 타입별 특수 규칙

```
Version 1 (일반):
  → 에셋 보존 법칙만 확인
  → Mint/Burn 없음

Version 2 (Exchange):
  → POT Mint 허용
  → JACK 소각 검증 (교환 비율)
  → 소각 JACK = Mint POT × 100

Version 3 (Gacha Commit):
  → POT Burn 허용 (가챠 비용)
  → Commit 해시 형식 검증
  → Commit 데이터 포함 확인

Version 4 (Gacha Reveal):
  → 잭팟 풀 UTXO 소비 허용 (당첨 시)
  → Commit TX 참조 검증
  → 당첨 계산 검증
  → 당첨금 = Commit 블록 시점 풀 잔액 기준
  → Reveal 기한 확인 (Commit 후 50블록 이내)
```

### 8.3 검증 흐름

```
TX 수신 → 기본 형식 검증
              │
              ▼
         version 확인
         ┌──────┬──────┬──────┬──────┐
         ▼      ▼      ▼      ▼      
       v1      v2      v3      v4
      일반   Exchange  Commit  Reveal
         │      │      │      │
         ▼      ▼      ▼      ▼
    에셋보존  교환비율  POT소각  당첨검증
    확인     + Mint    확인    + 풀지급
         │      │      │      │
         └──────┴──────┴──────┘
                    │
                    ▼
              서명 검증
                    │
                    ▼
              UTXO Set 확인
              (이중지불 방지)
                    │
                    ▼
                유효! ✅
```

---

## 9. 직렬화 (Serialization)

### 9.1 Output 직렬화

```
=== JACK만 있는 Output ===
  jack_value (8 bytes, LE)     // JACK 금액
  asset_count (VarInt)         // 0 (추가 에셋 없음)
  script_pubkey_len (VarInt)   // Script 길이
  script_pubkey (가변)         // 잠금 조건

크기: 8 + 1 + 1 + ~25 = ~35 bytes
→ Bitcoin Output과 거의 동일!


=== POT이 포함된 Output ===
  jack_value (8 bytes, LE)     // JACK 금액
  asset_count (VarInt)         // 1
  asset_id_len (VarInt)        // 3 ("POT")
  asset_id (3 bytes)           // "POT"
  asset_amount (8 bytes, LE)   // POT 금액
  script_pubkey_len (VarInt)   // Script 길이
  script_pubkey (가변)         // 잠금 조건

크기: 8 + 1 + 1 + 3 + 8 + 1 + ~25 = ~47 bytes
→ Bitcoin보다 ~12 bytes 더 큼 (에셋 1종당)
→ 에셋이 2종뿐이라 오버헤드 최소
```

### 9.2 UTXO Set 저장

```
Key: (tx_id, output_index)  // 32 + 4 = 36 bytes

Value:
  jack_value (8 bytes)
  asset_count (1 byte)
  [asset_id + amount] × N    // 에셋당 ~11 bytes
  script_pubkey (가변)
  block_height (4 bytes)      // 생성 블록 높이

인덱스:
  주소 인덱스: 주소 → UTXO 목록 (잔액 조회)
  에셋 인덱스: asset_id → UTXO 목록 (에셋 검색)
  잭팟 인덱스: 잭팟 주소 → UTXO 목록 (풀 잔액)
```

---

## 10. Bitcoin vs Cardano vs JackpotChain

### 10.1 비교

```
┌────────────────┬──────────┬──────────────┬──────────────┐
│                │ Bitcoin  │ Cardano      │ JackpotChain │
├────────────────┼──────────┼──────────────┼──────────────┤
│ 에셋 수        │ 1 (BTC)  │ 무제한       │ 2 (JACK+POT) │
│ 멀티에셋       │ ❌       │ ✅ 네이티브  │ ✅ 네이티브  │
│ 누구나 발행    │ ❌       │ ✅           │ ❌           │
│ Policy Script  │ ❌       │ ✅ (복잡)    │ ❌ (하드코딩) │
│ Min UTXO 비용  │ Dust     │ Min ADA      │ Min JACK     │
│ NFT            │ Ordinals │ 네이티브     │ ❌ 없음      │
│ 구현 복잡도    │ 낮음     │ 높음         │ 중간         │
│ 확장성         │ 낮음     │ 높음         │ 낮음 (의도적)│
└────────────────┴──────────┴──────────────┴──────────────┘
```

### 10.2 JackpotChain의 설계 철학

```
"필요한 만큼만, 단순하게"

  ❌ 범용 에셋 발행 플랫폼이 아님
  ✅ 특정 경제 루프를 위한 최소 에셋 시스템

  JACK: 가치 저장 + 교환 매개
  POT:  가챠 접근 제어 (JACK을 태워야 얻음)
  
  2종이면 충분:
    채굴 → 보유/전송 → 교환 → 가챠 → 당첨
    모든 경제 활동이 커버됨

  MVP 장점:
    - 에셋 Registry 불필요 (종류 고정)
    - Policy Script 불필요 (규칙 하드코딩)
    - 검증 로직 단순 (분기 4개)
    - UTXO 크기 최소 (~12 bytes 추가)
```

---

## 11. SSAFY MVP 구현 가이드

### 11.1 구현 우선순위

```
Phase 1 (필수):
  ✅ JACK 단일 에셋 구현
  ✅ Coinbase TX (블록 보상 50 JACK)
  ✅ 일반 전송 TX (version 1)
  ✅ 수수료 계산 (Input - Output)
  ✅ 기본 UTXO Set (JACK만)

Phase 2 (멀티에셋):
  ✅ Output에 assets 맵 추가
  ✅ POT 에셋 지원
  ✅ Exchange TX (version 2) → POT Mint
  ✅ Coinbase 수수료 분배 (50/30/20)
  ✅ 잭팟 풀 주소 + 소각 주소

Phase 3 (가챠):
  ✅ Gacha Commit TX (version 3) → POT Burn
  ✅ Gacha Reveal TX (version 4) → 잭팟 지급
  ✅ 당첨금 Commit 블록 시점 고정
  ✅ Reveal 기한 (50블록)
```

### 11.2 단순화 포인트

```
MVP에서 생략 가능:

  ❌ 범용 Asset Policy / Policy Script
     → JACK, POT 규칙만 하드코딩

  ❌ 에셋 Registry (온체인 메타데이터)
     → 에셋 2종은 코드에 정의

  ❌ 에셋 인덱스 (에셋별 UTXO 검색)
     → 주소 인덱스로 충분
     → 잭팟 주소만 별도 추적

  ❌ 복잡한 소수점 처리
     → 정수 연산만 (satoshi 단위)

  ❌ POT 수수료 지불
     → JACK으로만 수수료
```

---

## 12. 핵심 요약

### 에셋 체계
```
JACK: 네이티브 코인 (채굴 생성, 범용)
POT:  파생 토큰 (JACK 교환 생성, 가챠 전용)
NFT:  없음 (가챠 보상 = JACK)
```

### 시스템 주소
```
잭팟 풀: 수수료 30% 축적, 가챠 당첨 시 지급
소각:    수수료 20% + Exchange 소각, 영구 소멸
→ 둘 다 개인키 없는 특수 주소
→ UTXO로 투명하게 관리
```

### Coinbase 수수료 분배
```
채굴자: 50 JACK + 수수료 50%
잭팟:   수수료 30%
소각:   수수료 20%
→ 매 블록 Coinbase TX에서 강제
```

### TX 타입
```
v1 일반:    에셋 보존 (Mint/Burn 없음)
v2 Exchange: JACK 소각 → POT Mint
v3 Commit:  POT Burn → 가챠 시작
v4 Reveal:  당첨 시 잭팟 풀에서 JACK 지급
```

### 검증 원칙
```
에셋별 Input ≥ Output (보존 법칙)
Mint/Burn은 특정 TX 타입에서만
수수료는 JACK으로만
최소 JACK 규칙 (Min JACK)
```

---

## 13. 체크리스트

이해했는지 확인:

- [ ] JACK과 POT의 역할 차이
- [ ] JACK의 Mint (Coinbase) / Burn (소각 주소)
- [ ] POT의 Mint (Exchange) / Burn (가챠)
- [ ] 시스템 주소 개념 (개인키 없음)
- [ ] 잭팟 풀이 UTXO로 관리되는 원리
- [ ] 소각 주소와 OP_RETURN
- [ ] Coinbase TX 수수료 분배 구조 (50/30/20)
- [ ] 4가지 TX 타입의 에셋 흐름
- [ ] 최소 JACK (Min JACK) 규칙
- [ ] Output 직렬화에서 에셋 추가 오버헤드
- [ ] Bitcoin/Cardano와의 차이

---

## 14. 다음 학습

### 학습 완료:
- ✅ Phase 0~2 전체
- ✅ 멀티에셋 시스템

### 다음 추천:
```
→ [14. 토크노믹스](14-tokenomics.md)
  - 발행량 분석 (무제한, 50 JACK/블록)
  - 인플레이션 vs 소각 균형
  - 수수료 분배 경제학
  - 잭팟 풀 축적 시뮬레이션

→ [15. Exchange 모듈](15-exchange-module.md)
  - JACK → POT 교환 상세
  - 교환 비율 (v1 고정, v2 AMM)
  - 유동성 관리
```

---

## 15. 참고 자료

**멀티에셋:**
- Cardano Multi-Asset Documentation
- Cardano Ledger Specs - Mary Era
- CIP-25 (NFT Metadata Standard) → JackpotChain은 안 쓰지만 참고

**Bitcoin:**
- Bitcoin Developer Guide - Transactions
- BIP 141 (SegWit) - TX 구조 변경 참고
- Colored Coins Protocol

**경제 모델:**
- Token Economics 101
- Crypto Game Economy Design

---

**이전:** [12. 네트워크 보안](../phase-2-network/12-network-security.md)  
**다음:** [14. 토크노믹스](14-tokenomics.md) →
