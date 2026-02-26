# 15. Exchange 모듈 (Exchange Module)

> **Phase 3: Advanced**  
> **학습 날짜:** 2025-02-19  
> **난이도:** ⭐⭐⭐☆☆  
> **예상 소요 시간:** 1.5-2시간  
> **선행 학습:** [13. 멀티에셋 시스템](13-multi-asset-system.md), [14. 토크노믹스](14-tokenomics.md)

---

## 🎯 학습 목표

이 문서를 완료하면:
- [ ] Exchange TX (version 2)의 구조를 정확히 설명할 수 있다
- [ ] 노드가 Exchange TX를 검증하는 전체 과정을 안다
- [ ] POT Mint가 허용되는 조건과 원리를 이해한다
- [ ] Exchange 소각과 Coinbase 소각의 차이를 구분할 수 있다
- [ ] 에지 케이스 (소수점, 최소량, 대량 교환)를 처리할 수 있다
- [ ] v1(고정비율)과 v2(AMM)의 차이를 설명할 수 있다
- [ ] AMM의 기본 원리 (x*y=k)를 이해한다

---

## 1. Exchange란?

### 1.1 목적

```
문제:
  가챠를 플레이하려면 POT이 필요
  POT은 채굴로 얻을 수 없음
  → JACK을 POT으로 바꿔야 함

해결:
  Exchange TX = JACK을 태워서 POT을 만드는 특수 거래

비유:
  게임 캐시 충전
    현금(JACK) → 게임 머니(POT)
    현금은 사라지고 게임 머니가 생김
    환불 불가 (일방향)
```

### 1.2 핵심 원칙

```
1. 일방향: JACK → POT (역방향 불가)
   POT → JACK 교환은 없음
   → POT은 가챠에서만 소비됨

2. 소각 기반: 교환한 JACK은 영구 소멸
   → 소각 주소로 가는 게 아니라 아예 사라짐
   → 디플레이션 효과

3. 고정 비율 (v1): 100 JACK = 1 POT
   → 변동 없음, 예측 가능
   → MVP에 적합

4. 원자적 (Atomic): 하나의 TX에서 소각+Mint 동시 발생
   → 소각만 되고 Mint 안 되는 경우 없음
   → TX 전체가 성공하거나 전체가 실패
```

---

## 2. Exchange TX 구조

### 2.1 전체 형식

```
Exchange TX:
  version: 2                    ← 일반 TX(1)와 구분!
  
  Inputs:
    [0] 유저의 JACK UTXO (교환 원금 + 수수료)
    [1] (필요하면 추가 UTXO)
    ...
  
  Outputs:
    [0] POT → 유저 (Mint된 POT + 최소 JACK)
    [1] JACK → 유저 (거스름돈, 있을 경우)
    [2] OP_RETURN (소각 기록)
  
  수수료: JACK으로 지불 (일반 TX와 동일)
```

### 2.2 구체적 예시

```
=== Alice가 1000 JACK을 10 POT으로 교환 ===

Alice 보유: UTXO (1500 JACK)

Exchange TX (version 2):
  Input[0]:
    prev_tx: "abc123..."
    output_index: 0
    value: 1500 JACK         ← Alice의 UTXO
    script_sig: <Alice 서명>

  Output[0]:                  ← POT 수령 (Mint!)
    jack_value: 0.01 JACK     (Min JACK)
    assets: { "POT": 10 }    (Mint된 POT)
    script_pubkey: <Alice>

  Output[1]:                  ← 거스름돈
    jack_value: 499.89 JACK   (1500 - 1000 - 0.01 - 0.1)
    assets: {}
    script_pubkey: <Alice>

  Output[2]:                  ← 소각 기록
    OP_RETURN <"BURN:1000">   (1000 JACK 소각됨)

정산:
  Input JACK:  1500
  Output JACK: 0.01 + 499.89 = 499.90
  수수료:      0.1 JACK
  소각:        1000 JACK
  총:          499.90 + 0.1 + 1000 = 1500 ✅

  Input POT:   0
  Output POT:  10
  Mint:        1000 ÷ 100 = 10 POT ✅
```

### 2.3 Output 구성 규칙

```
Output[0]: POT 수령 (필수)
  - Mint된 POT을 담는 UTXO
  - 최소 JACK (Min JACK = 0.01) 포함 필수
  - 유저 주소로 잠금

Output[1]: JACK 거스름돈 (선택)
  - 교환에 안 쓴 JACK 반환
  - 없을 수도 있음 (정확히 맞춰서 교환한 경우)

Output[2]: OP_RETURN (필수)
  - 소각 금액 기록
  - UTXO Set에 들어가지 않음
  - 투명한 소각 증명

Output 순서:
  POT → 거스름돈 → OP_RETURN (권장, 강제는 아님)
  검증 시에는 순서 무관하게 전체 합산으로 확인
```

---

## 3. 교환 검증 로직

### 3.1 검증 단계

```
Exchange TX 수신 시 노드가 확인하는 것:

Step 1: 기본 검증 (모든 TX 공통)
  ✅ TX 형식이 올바른가?
  ✅ Input UTXO가 존재하는가? (이중지불 아닌가?)
  ✅ 서명이 유효한가?
  ✅ 수수료 ≥ 최소 수수료?

Step 2: version 확인
  ✅ version == 2 인가?
  → 아니면 일반 TX로 처리 (POT Mint 불허)

Step 3: 소각 금액 계산
  burn_amount = Σ(Input JACK) - Σ(Output JACK) - fee
  
  ✅ burn_amount > 0 인가?
  ✅ burn_amount가 100의 배수인가? (정수 POT만 허용)
     → 또는 satoshi 단위로 나누어떨어지는가?

Step 4: POT Mint 검증
  expected_pot = burn_amount ÷ 100
  actual_pot = Σ(Output POT)
  
  ✅ actual_pot == expected_pot 인가?

Step 5: OP_RETURN 확인
  ✅ OP_RETURN Output이 존재하는가?
  ✅ 기록된 소각 금액이 burn_amount와 일치하는가?

Step 6: 최소 JACK 확인
  ✅ POT을 담는 Output에 Min JACK (0.01) 이상?

Step 7: Input에 POT 없음 확인
  ✅ Input에 POT이 포함되어 있지 않은가?
  → Exchange TX는 순수 JACK → POT 변환만
  → POT이 Input에 있으면 일반 전송과 혼동

모두 통과 → 유효! ✅
하나라도 실패 → 거부! ❌
```

### 3.2 검증 실패 사례

```
사례 1: 비율 조작
  Input: 500 JACK
  Output: 10 POT (500 ÷ 100 = 5여야 함)
  → 실패! "Mint 양 불일치" ❌

사례 2: 소각 없이 Mint
  Input: 1000 JACK
  Output: 990 JACK + 10 POT (JACK이 안 줄었음)
  → burn_amount = 1000 - 990 - fee ≈ 10
  → expected_pot = 10 ÷ 100 = 0.1 POT
  → actual_pot = 10 POT
  → 실패! "Mint 양 불일치" ❌

사례 3: version 조작
  version: 1 (일반 TX인 척)
  Output에 POT 포함
  → 일반 TX에서 POT Mint 불가! ❌
  → "일반 TX에서 새 에셋 생성 금지"

사례 4: 수수료 미지불
  Input: 1000 JACK
  Output: 10 POT + 0 JACK
  burn_amount: 1000 - 0.01(min) = 999.99
  fee: 0 (수수료 없음)
  → 실패! "최소 수수료 미충족" ❌

사례 5: 소수점 POT
  Input: 150 JACK (수수료 제외 후 소각 가능 금액: 149)
  expected_pot: 1.49 POT
  → 실패! "POT은 satoshi 단위 정수만 허용"
  → 정확히는: 149 JACK = 1 POT + 49 JACK 거스름돈으로 처리해야
```

### 3.3 소수점 처리

```
문제:
  100 JACK = 1 POT인데
  유저가 250 JACK 교환하면?
  → 2.5 POT? 소수점 POT?

해결: 정수 POT만 Mint, 나머지는 거스름돈

  Input: 250 JACK (+ 수수료용 추가)
  
  소각 가능 금액에서:
    200 JACK → 소각 → 2 POT Mint
    50 JACK → 거스름돈으로 반환
  
  Output[0]: 0.01 JACK + 2 POT → 유저
  Output[1]: 50 + α JACK → 유저 (거스름돈)
  Output[2]: OP_RETURN (200 JACK 소각)

검증:
  burn_amount = 200 (100의 배수 ✅)
  expected_pot = 200 ÷ 100 = 2
  actual_pot = 2 ✅

→ 유저 입장에서는 "250 JACK 넣으면 2 POT + 50 JACK 돌려받음"
→ 지갑 UI가 이 계산을 자동으로 해줘야 함
```

---

## 4. POT Mint 메커니즘

### 4.1 Mint란?

```
Mint = 이전에 존재하지 않던 에셋이 새로 생성되는 것

일반 TX의 규칙:
  에셋별로 Input ≥ Output (보존 법칙)
  → Input에 없는 에셋이 Output에 등장하면 거부!

Exchange TX의 예외:
  POT은 Input에 없어도 Output에 등장 가능
  → 대신 JACK 소각이 증명되어야 함
  → "무에서 유"가 아니라 "JACK을 태운 대가"

비유:
  일반 TX: 금고에서 돈을 꺼내서 다른 금고에 넣기
  Exchange TX: 지폐를 태워서 동전을 받기
               (지폐 = JACK, 동전 = POT)
```

### 4.2 왜 Exchange TX에서만 허용하나?

```
version으로 구분하는 이유:

  만약 아무 TX에서나 POT Mint가 가능하면?
    → 공격자가 JACK 소각 없이 POT 생성 시도
    → 검증 로직이 복잡해짐
    → 버그 가능성 증가

  version 2로 명시적 구분:
    → version 1: 에셋 보존 법칙 엄격 적용
    → version 2: POT Mint 허용 + 소각 검증 추가
    → 검증 로직이 깔끔하게 분리됨

노드 검증 흐름:
  TX 수신
    ├─ version 1 → 에셋 보존 확인 (Mint 금지)
    ├─ version 2 → Exchange 검증 (POT Mint 허용)
    ├─ version 3 → Gacha Commit 검증 (POT Burn)
    └─ version 4 → Gacha Reveal 검증 (잭팟 지급)
```

### 4.3 Mint의 UTXO Set 영향

```
Exchange TX 전:
  UTXO Set:
    ("abc", 0): { jack: 1500, assets: {} } (Alice)

Exchange TX 후:
  UTXO Set:
    ("abc", 0): 삭제됨 (소비됨)
    ("exch_tx", 0): { jack: 0.01, assets: {"POT": 10} } (Alice, 신규)
    ("exch_tx", 1): { jack: 499.89, assets: {} } (Alice, 거스름돈)
    
    OP_RETURN은 UTXO Set에 안 들어감

에셋 인덱스 변화:
  POT 인덱스: ("exch_tx", 0) 추가
  → 이전에 없던 POT이 시스템에 등장

전체 POT 총량:
  기존 + 10 = 새 총량
  → 모든 노드가 동일하게 계산
```

---

## 5. Exchange 소각 vs Coinbase 소각

### 5.1 비교

```
┌─────────────────┬──────────────────┬──────────────────┐
│                 │ Exchange 소각    │ Coinbase 소각    │
├─────────────────┼──────────────────┼──────────────────┤
│ 발생 시점       │ 유저가 교환할 때 │ 매 블록           │
│ 금액            │ 교환 JACK 전액   │ 수수료의 20%     │
│ 대가            │ POT 생성         │ 없음 (순수 소각)  │
│ 빈도            │ 가변 (유저 행동) │ 고정 (매 블록)   │
│ 크기            │ 클 수 있음       │ 대부분 소량      │
│ 기록 방식       │ OP_RETURN        │ OP_RETURN        │
│ UTXO 영향       │ 없음             │ 없음             │
└─────────────────┴──────────────────┴──────────────────┘

핵심 차이:
  Coinbase 소각: 네트워크 인플레이션 억제 목적
  Exchange 소각: POT 생성의 대가, 경제 순환 목적
```

### 5.2 소각 기록 형식

```
OP_RETURN 데이터 형식:

Exchange 소각:
  OP_RETURN <type:1byte> <amount:8bytes>
  type = 0x01 (Exchange 소각)
  amount = 소각된 JACK (satoshi 단위)

Coinbase 소각:
  OP_RETURN <type:1byte> <amount:8bytes>
  type = 0x02 (수수료 소각)
  amount = 소각된 JACK (satoshi 단위)

소각 총량 조회:
  블록체인의 모든 OP_RETURN을 스캔
  type별로 합산
  → 총 소각량 = Exchange 소각 + Coinbase 소각
```

---

## 6. 에지 케이스

### 6.1 최소 교환량

```
규칙: 최소 100 JACK (= 1 POT)

이유:
  100 JACK 미만이면 POT 0개 Mint
  → 의미 없는 TX (JACK만 소각되고 POT 없음)
  → 방지해야 함

검증:
  burn_amount < 100 JACK → 거부!
  "최소 교환량 미충족: 최소 100 JACK 필요"
```

### 6.2 대량 교환

```
시나리오: Alice가 100,000 JACK을 한 번에 교환

Exchange TX:
  Input: 100,000 JACK (+ 수수료)
  Output: 1,000 POT + 거스름돈
  소각: 100,000 JACK

문제 없음:
  ✅ 교환 비율 정확 (100,000 ÷ 100 = 1,000)
  ✅ 소각 기록 있음
  ✅ 단일 TX로 처리 가능

주의:
  블록 크기 제한 안에서는 문제 없음
  Output 하나에 POT 1,000개 → 정상
```

### 6.3 다중 Input 교환

```
시나리오: Alice의 JACK이 여러 UTXO에 흩어져 있음

  UTXO ①: 300 JACK
  UTXO ②: 400 JACK
  UTXO ③: 500 JACK

  총: 1200 JACK, 1000 JACK 교환하고 싶음

Exchange TX:
  Input[0]: UTXO ① (300 JACK)
  Input[1]: UTXO ② (400 JACK)
  Input[2]: UTXO ③ (500 JACK)
  
  Output[0]: 0.01 JACK + 10 POT → Alice
  Output[1]: 199.89 JACK → Alice (거스름돈)
  Output[2]: OP_RETURN (1000 JACK 소각)
  
  수수료: 0.1 JACK

검증:
  Input JACK: 300 + 400 + 500 = 1200
  Output JACK: 0.01 + 199.89 = 199.90
  수수료: 0.1
  소각: 1200 - 199.90 - 0.1 = 1000
  expected_pot = 1000 ÷ 100 = 10
  actual_pot = 10 ✅
```

### 6.4 POT이 이미 있는 UTXO로 교환

```
시나리오: Alice의 UTXO에 JACK과 POT이 섞여 있음

  UTXO: 500 JACK + 3 POT

  Alice는 200 JACK만 교환하고 싶음

문제:
  Exchange TX에 POT이 Input으로 들어옴
  → 허용할까?

설계 선택지:

Option A: 거부 (단순)
  "Exchange TX의 Input에 POT이 있으면 거부"
  → 유저가 먼저 JACK만 있는 UTXO를 분리해야 함
  → 불편하지만 검증이 단순

Option B: 허용 (편리)
  "Input의 POT은 Output으로 그대로 통과시킴"
  → POT 보존 법칙도 함께 검증
  → 검증이 약간 복잡해짐

  Input: 500 JACK + 3 POT
  Output[0]: 0.01 JACK + 2 POT + 3 POT → Alice (Mint 2 + 기존 3)
  Output[1]: 299.89 JACK → Alice
  Output[2]: OP_RETURN (200 JACK 소각)
  
  JACK: 500 = 0.01 + 299.89 + 0.1(fee) + 200(burn) ✅
  POT: Input 3 + Mint 2 = Output 5 ✅

MVP 권장: Option A (단순)
  → "Exchange TX에는 JACK만 Input으로"
  → POT이 있는 UTXO를 쓰려면 먼저 분리 TX 실행
  → 나중에 Option B로 업그레이드 가능
```

### 6.5 동일 블록 내 연속 교환

```
시나리오:
  Block #100에 Exchange TX 2개:
    TX_A: Alice 1000 JACK → 10 POT
    TX_B: Bob 2000 JACK → 20 POT

문제 없음:
  각 TX는 독립적으로 검증
  서로의 UTXO를 참조하지 않으면 충돌 없음
  같은 블록에 여러 Exchange TX 가능

주의:
  TX_A의 Output을 TX_B의 Input으로 쓰는 경우?
  → 같은 블록 내 TX 의존성
  → 블록 내 TX 순서에 따라 검증 (앞에서부터)
  → 일반적이진 않지만 허용
```

---

## 7. v1: 고정 비율

### 7.1 설계

```
v1 (MVP):
  교환 비율 = 100 JACK : 1 POT (고정)
  → 코드에 상수로 하드코딩
  → 모든 블록, 모든 시점에서 동일

  EXCHANGE_RATE = 100  // 100 JACK per 1 POT

장점:
  ✅ 구현 단순 (나누기 하나)
  ✅ 예측 가능 (유저가 비용 계산 쉬움)
  ✅ 검증 단순 (burn ÷ 100 == mint?)
  ✅ 경제 분석 쉬움

단점:
  ❌ 시장 상황 반영 못 함
  ❌ JACK 가치 변해도 가챠 비용 동일
  ❌ 유연성 없음
```

### 7.2 가챠 비용 관점

```
가챠 1회 = 1 POT = 100 JACK

채굴과의 관계:
  블록 보상 50 JACK
  → 1블록 채굴 = 가챠 0.5회
  → 2블록 채굴 = 가챠 1회
  → 시간: 약 30초 채굴 = 가챠 1회 분량

수수료와의 관계:
  TX 수수료 0.1 JACK이면
  → 가챠 1회 = TX 1000건의 수수료
  → 가챠가 상대적으로 비쌈

의미:
  가챠는 "가벼운 오락"이 아니라 "의미 있는 투자"
  → 무분별한 가챠 남발 방지
  → 당첨의 가치가 높아짐
```

---

## 8. v2: AMM 방식 (미래 확장)

### 8.1 AMM이란?

```
AMM = Automated Market Maker (자동화된 시장 조성자)

전통 거래소:
  매수자: "100 JACK에 1 POT 살게"
  매도자: "105 JACK에 1 POT 팔게"
  → 가격이 일치해야 거래 성사
  → 유동성 문제 (상대방이 없으면 거래 불가)

AMM:
  유동성 풀에 JACK과 POT을 넣어둠
  수학 공식으로 자동 가격 결정
  → 상대방 없이도 즉시 거래 가능
```

### 8.2 Constant Product Formula (x * y = k)

```
유동성 풀:
  x = 풀의 JACK 양
  y = 풀의 POT 양
  k = x × y (상수, 변하지 않음)

초기 상태:
  x = 10,000 JACK
  y = 100 POT
  k = 10,000 × 100 = 1,000,000

가격:
  1 POT의 가격 = x ÷ y = 10,000 ÷ 100 = 100 JACK
  → 초기에는 v1과 동일!
```

### 8.3 교환 시 가격 변동

```
Alice가 1000 JACK → POT 교환:

교환 전:
  x = 10,000 JACK, y = 100 POT, k = 1,000,000

JACK 투입:
  x' = 10,000 + 1,000 = 11,000

POT 계산 (k 유지):
  y' = k ÷ x' = 1,000,000 ÷ 11,000 = 90.909...
  
  Alice가 받는 POT = y - y' = 100 - 90.909 = 9.09 POT

교환 후:
  x = 11,000 JACK, y = 90.909 POT
  새 가격: 11,000 ÷ 90.909 = 121 JACK/POT

관찰:
  고정비율이면 10 POT 받았을 것
  AMM에서는 9.09 POT (슬리피지 발생!)
  교환할수록 POT이 비싸짐
  → 대량 교환에 불리 = 자연스러운 가격 조절
```

### 8.4 AMM의 특성

```
장점:
  ✅ 수요/공급 자동 반영
     POT 수요 많음 → POT 비싸짐 → 가챠 비용 증가
     POT 수요 적음 → POT 싸짐 → 가챠 유도

  ✅ 대량 교환 억제 (슬리피지)
     한 번에 많이 교환하면 불리
     → 자연스러운 분산

  ✅ 유동성 제공자 인센티브
     풀에 자금 넣으면 수수료 수익
     → 생태계 참여 동기

단점:
  ❌ 구현 복잡
     유동성 풀 관리, 가격 계산, 슬리피지 제한
  
  ❌ 초기 유동성 필요
     풀에 JACK + POT을 누가 처음에 넣나?
     → Genesis에서 시스템이 공급? 팀이 공급?
  
  ❌ 가격 조작 가능성
     풀이 작으면 소량으로 가격 크게 변동
     → Flash Loan 등 공격

  ❌ 비영구적 손실 (Impermanent Loss)
     유동성 제공자가 손해볼 수 있음
```

### 8.5 왜 MVP는 v1인가?

```
v1 (고정비율) 선택 이유:

  1. 구현 시간
     v1: 나누기 하나 = 30분
     v2: 유동성 풀 + AMM 수학 + 슬리피지 = 수일

  2. 초기 유동성 문제 없음
     v1: 풀 불필요 (비율 고정)
     v2: 누가 처음에 풀에 넣나?

  3. 경제 예측
     v1: 가챠 비용 = 항상 100 JACK (확정)
     v2: 가챠 비용 = 시장 상황에 따라 변동 (불확실)

  4. 6주 MVP
     경제 검증이 목적
     → 변수 최소화
     → v1으로 기본 루프 검증 후 v2 고려

전환 계획:
  Phase 1 (MVP): v1 고정비율
  Phase 2: 운영 데이터 수집, v2 설계
  Phase 3: v2 AMM 도입 (활성화 높이로 전환)
```

---

## 9. 유저 관점 교환 흐름

### 9.1 지갑 UI에서의 흐름

```
=== 유저 경험 ===

1. 지갑 열기
   잔액: 5,000 JACK / 0 POT

2. "Exchange" 탭 클릭

3. 교환할 JACK 입력: 1000
   → 자동 계산: "10 POT을 받습니다"
   → 수수료 표시: "수수료 0.1 JACK"
   → 총 비용: "1,000.1 JACK"

4. "교환" 버튼 클릭
   → 서명 요청
   → TX 생성 & 전파

5. 블록 확인 대기 (15초)

6. 교환 완료!
   잔액: 3,999.89 JACK / 10 POT
   (5000 - 1000 - 0.1 - 0.01(MinJACK))
```

### 9.2 TX 생성 (지갑 내부 로직)

```
유저 요청: "1000 JACK을 POT으로 교환해줘"

지갑 처리:

1. UTXO 선택
   필요 JACK: 1000 (교환) + 0.01 (MinJACK) + 0.1 (수수료) = 1000.11
   선택된 UTXO: ("abc", 0) = 5000 JACK

2. Exchange TX 구성
   version: 2
   Input[0]: ("abc", 0) - 5000 JACK
   Output[0]: 0.01 JACK + 10 POT → 내 주소 (신규)
   Output[1]: 3999.89 JACK → 내 주소 (거스름돈)
   Output[2]: OP_RETURN (1000 JACK 소각)

3. 서명
   Input[0]에 개인키로 서명

4. 전파
   피어에게 TX 전송

5. 확인 대기
   블록에 포함되면 완료
```

---

## 10. 역방향 교환 (POT → JACK)

### 10.1 왜 없나?

```
POT → JACK 역교환이 없는 이유:

  1. POT의 목적
     POT = 가챠 전용 토큰
     → 역할이 명확 (가챠에서만 소비)
     → JACK으로 돌려받을 이유 없음

  2. 경제적 이유
     역교환 있으면:
       JACK → POT → JACK 무한 순환
       → Exchange 소각 의미 없어짐
       → 디플레이션 효과 사라짐

  3. 일방향 = 단순
     교환 방향 1가지만 → 검증 단순
     양방향이면: 가격 결정, 차익 거래, 조작 등 복잡해짐

  4. 게임 캐시 비유
     현금 → 게임 머니: 가능
     게임 머니 → 현금: 보통 불가
     → 자연스러운 구조

결론:
  POT을 다시 JACK으로 바꾸고 싶다?
  → 가챠를 해서 당첨되면 JACK을 받아!
  → 이게 JackpotChain의 경제 루프
```

---

## 11. 핵심 요약

### Exchange TX
```
version 2, JACK 소각 → POT Mint
100 JACK = 1 POT (v1 고정)
일방향 (역교환 없음)
원자적 (소각+Mint 동시)
```

### 검증
```
version 2 확인
burn_amount = Input - Output - fee
expected_pot = burn ÷ 100
actual_pot == expected_pot?
OP_RETURN 소각 기록 확인
Min JACK 확인
```

### v1 vs v2
```
v1 (MVP): 고정 100:1, 단순, 예측 가능
v2 (미래): AMM (x*y=k), 수요/공급 반영, 복잡
MVP는 v1, 데이터 수집 후 v2 전환
```

### 에지 케이스
```
소수점: 정수 POT만, 나머지 거스름돈
최소: 100 JACK 이상
다중 Input: 합산해서 계산
POT 섞인 UTXO: MVP에서는 거부 (분리 후 교환)
```

---

## 12. 체크리스트

이해했는지 확인:

- [ ] Exchange TX (version 2)의 Input/Output 구조
- [ ] 교환 검증 7단계
- [ ] burn_amount 계산 방법
- [ ] POT Mint가 Exchange TX에서만 허용되는 이유
- [ ] OP_RETURN 소각 기록 형식
- [ ] Exchange 소각과 Coinbase 소각의 차이
- [ ] 소수점 POT 처리 (정수만, 거스름돈)
- [ ] 최소 교환량 (100 JACK)
- [ ] AMM의 x*y=k 공식과 슬리피지
- [ ] v1 vs v2 트레이드오프
- [ ] 역방향 교환이 없는 경제학적 이유

---

## 13. 다음 학습

### 학습 완료:
- ✅ Phase 0~2 전체
- ✅ 멀티에셋 시스템
- ✅ 토크노믹스
- ✅ Exchange 모듈

### 다음 추천:
```
→ [16. 가챠 시스템](16-gacha-system.md)
  - Commit-Reveal 전체 흐름
  - 블록 해시 랜덤 시드
  - 당첨 계산과 검증
  - 잭팟 풀 지급 메커니즘
  - 채굴자 조작 방지
  - Reveal 기한과 만료 처리
```

---

## 14. 참고 자료

**AMM:**
- Uniswap V2 Whitepaper (x*y=k)
- Constant Function Market Makers (DeFi 기초)
- Impermanent Loss Explained

**토큰 교환:**
- Atomic Swap Concepts
- Cross-Chain Exchange Protocols
- Token Bridge Designs

**게임 경제:**
- Virtual Currency Exchange Mechanics
- In-Game Economy Design
- Free-to-Play Monetization

---

**이전:** [14. 토크노믹스](14-tokenomics.md)  
**다음:** [16. 가챠 시스템](16-gacha-system.md) →
