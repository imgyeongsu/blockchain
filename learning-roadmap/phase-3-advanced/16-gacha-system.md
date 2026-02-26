# 16. 가챠 시스템 (Gacha System)

> **Phase 3: Advanced**  
> **학습 날짜:** 2025-02-19  
> **난이도:** ⭐⭐⭐⭐⭐  
> **예상 소요 시간:** 3-4시간  
> **선행 학습:** [13. 멀티에셋](13-multi-asset-system.md), [14. 토크노믹스](14-tokenomics.md), [15. Exchange](15-exchange-module.md)

---

## 🎯 학습 목표

이 문서를 완료하면:
- [ ] 블록체인에서 랜덤이 왜 어려운지 설명할 수 있다
- [ ] V0~V3 각 단계의 문제점과 해결책을 설명할 수 있다
- [ ] Commit-Reveal 패턴의 작동 원리를 안다
- [ ] 채굴자 조작의 한계를 경제학적으로 분석할 수 있다
- [ ] 당첨금 지급 메커니즘과 치트 방지를 이해한다
- [ ] JackpotChain 가챠의 "충분히 공정한" 근거를 설명할 수 있다

---

## 1. 근본 문제: 블록체인 × 랜덤

### 1.1 모순

```
가챠에 필요한 것:
  "예측 불가능한 랜덤 값"
  → 아무도 결과를 미리 몰라야 함
  → 조작 불가능해야 함

블록체인의 특성:
  "모든 것이 결정론적이고 투명"
  → 모든 노드가 같은 결과를 계산해야 함
  → 모든 데이터가 공개됨

모순!
  랜덤이 필요한데 모든 게 공개되어 있음
  비밀이 필요한데 비밀을 둘 곳이 없음
  → 이것이 "온체인 랜덤"의 근본적 어려움
```

### 1.2 왜 외부 랜덤을 안 쓰나?

```
방법 1: 서버에서 랜덤 생성
  문제: 서버 운영자가 조작 가능
  → 탈중앙화 아님!

방법 2: 오라클 (Chainlink VRF 등)
  장점: 검증 가능한 랜덤
  문제: 외부 의존성, 구현 복잡, MVP 범위 초과

방법 3: 온체인 데이터로 랜덤 생성
  장점: 외부 의존 없음, 검증 가능
  문제: 조작 가능성 존재
  → 하지만 "충분히 어렵게" 만들 수 있음!
  → JackpotChain의 선택
```

---

## 2. V0: 순진한 랜덤 (최초 시도)

### 2.1 설계

```
가장 단순한 아이디어:
  "블록 해시를 랜덤 시드로 쓰자!"

가챠 TX:
  Input: 1 POT
  랜덤 시드: 이 TX가 포함된 블록의 해시
  당첨 여부: SHA256(tx_id + block_hash) < threshold

흐름:
  유저: "가챠 TX 보낸다!" → 네트워크에 전파
  채굴자: 블록에 포함 → 블록 해시 확정
  결과: 블록 해시 + TX로 당첨 계산
  → 즉시 결과 확인!
```

### 2.2 문제: 채굴자 완전 조작

```
채굴자의 힘:
  블록 해시 = 채굴자가 nonce를 바꿔가며 결정
  → 수백만 가지 블록 해시 중 하나를 "선택"하는 것

조작 시나리오:
  채굴자가 자기 가챠 TX를 블록에 넣음
  
  nonce 1 → block_hash_A → SHA256(tx + hash_A) → 꽝
  nonce 2 → block_hash_B → SHA256(tx + hash_B) → 꽝
  nonce 3 → block_hash_C → SHA256(tx + hash_C) → 당첨! ✅
  
  → nonce 3을 채택!
  → 100% 당첨 가능!

비용:
  추가 비용 0 (어차피 채굴하면서 nonce 돌리는 중)
  → 공짜로 조작 가능!

결론:
  V0은 완전히 깨진 설계 ❌
  채굴자가 마음대로 당첨/꽝을 결정할 수 있음
```

### 2.3 교훈

```
문제의 핵심:
  랜덤 시드(블록 해시)를 결정하는 사람 = 채굴자
  가챠를 하는 사람 = 채굴자 (본인도 가능)
  → 심판이 곧 선수!

필요한 것:
  랜덤 시드를 "아무도 단독으로 결정할 수 없는" 구조
  → V1에서 해결 시도
```

---

## 3. V1: Commit-Reveal 도입

### 3.1 핵심 아이디어

```
Commit-Reveal = "약속 후 공개" 패턴

비유: 가위바위보
  
  동시에 내면? → 상대 걸 보고 바꿀 수 있음 (부정)
  
  Commit-Reveal 방식:
    1. 둘 다 종이에 적어서 봉투에 넣기 (Commit)
    2. 동시에 봉투 열기 (Reveal)
    → 상대 걸 보고 바꿀 수 없음!

가챠 적용:
  1. 유저가 secret을 정하고, hash(secret)만 공개 (Commit)
  2. 나중에 secret을 공개 (Reveal)
  3. secret으로 당첨 계산
  → secret을 알아야 결과를 계산할 수 있는데
  → Commit 시점에는 hash만 공개되어 있으므로
  → 아무도 결과를 미리 모름!
```

### 3.2 흐름

```
=== Step 1: 유저가 secret 생성 ===

  secret = 랜덤 32바이트 (유저의 지갑이 생성)
  commit_hash = SHA256(secret)
  
  유저만 secret을 알고 있음
  commit_hash는 공개해도 secret을 역추적 불가능


=== Step 2: Commit TX (version 3) ===

  Input: 1 POT (가챠 비용) + JACK (수수료)
  Output: Commit UTXO
    - commit_hash 포함
    - POT은 소각됨 (Burn)
  
  → 블록에 포함됨
  → 이 시점에서 아무도 결과를 모름 (secret이 비밀)


=== Step 3: Reveal TX (version 4) ===

  Input: Commit UTXO
  데이터: secret (원본 공개!)
  
  검증:
    SHA256(secret) == commit_hash? ✅
  
  당첨 계산:
    result = SHA256(secret)
    당첨 = result < threshold


=== 결과 ===
  당첨 → 잭팟 풀에서 JACK 지급
  꽝 → 끝 (POT은 이미 소각됨)
```

### 3.3 해결된 것

```
유저 조작 방지: ✅

  유저가 당첨되는 secret을 골라서 Commit?
  → 가능!
  
  하지만:
    result = SHA256(secret)
    → secret을 바꾸면 result도 바뀜
    → 당첨되는 secret을 찾으려면?
    → SHA256을 역추산해야 함
    → 불가능! (해시 함수의 특성)
  
  유저가 할 수 있는 것:
    secret을 무작위로 많이 생성해서
    당첨되는 것을 고르기?
    → 매번 1 POT 비용 발생
    → 당첨 확률 1%면 100번 시도 = 100 POT
    → 당첨금보다 비용이 클 수 있음
    → 경제적으로 비합리적
```

### 3.4 남은 문제

```
채굴자 조작: 여전히 가능! ⚠️

  V1에서 랜덤 시드 = SHA256(secret)
  → secret은 유저가 결정
  → 채굴자는 secret을 모르니까 조작 못 하지 않나?

  맞아! 채굴자는 secret을 모름.
  하지만 다른 공격이 가능:

  공격: "Reveal TX 검열"
    채굴자가 Reveal TX를 블록에 안 넣기
    → 유저가 당첨인 걸 알고 Reveal을 보냈는데
    → 채굴자가 "이 TX는 블록에 안 넣을래" 
    → 당첨 무효화!
  
  또 다른 문제: 랜덤 시드가 유저에게만 의존
    secret만으로 결과가 결정되면:
    → 유저가 오프라인에서 수백만 개 secret 생성
    → 당첨되는 secret만 골라서 Commit
    → Commit 비용만 내면 100% 당첨!
    
    이건 큰 문제! → V2에서 해결
```

---

## 4. V2: 블록 해시를 시드에 혼합

### 4.1 핵심 아이디어

```
V1의 문제:
  result = SHA256(secret)
  → 유저가 secret만으로 결과를 미리 계산 가능

V2의 해결:
  result = SHA256(secret + block_hash)
  → block_hash = Commit TX가 포함된 블록의 해시
  
  유저가 Commit을 보낼 때:
    "내 TX가 어떤 블록에 들어갈지 모름"
    → block_hash를 모름
    → result를 미리 계산 불가능!
  
  채굴자가 블록을 만들 때:
    "이 블록에 들어있는 Commit TX의 secret을 모름"
    → secret을 모름
    → result를 자기에게 유리하게 조작 불가능!

핵심:
  유저는 block_hash를 모르고
  채굴자는 secret을 모르고
  → 둘 다 단독으로 결과를 조작할 수 없음!
```

### 4.2 상세 흐름

```
=== Step 1: Commit ===

  유저: secret 생성 (32바이트 랜덤)
  commit_hash = SHA256(secret)
  
  Commit TX (version 3):
    Input: 1 POT + JACK(수수료)
    Output: Commit UTXO (commit_hash 포함)
  
  → 네트워크에 전파
  → 이 시점: 유저만 secret 알고 있음
  → block_hash는 아직 미확정


=== Step 2: Commit TX가 블록에 포함 ===

  Block #500에 Commit TX 포함
  Block #500의 해시: 0x7a3f...b2c1
  
  → 이 시점: block_hash 확정!
  → 하지만 secret은 아직 비밀
  → 누구도 결과를 모름 (secret + block_hash 둘 다 필요)


=== Step 3: Reveal (Block #501 이후) ===

  유저: secret 공개

  Reveal TX (version 4):
    Input: Commit UTXO
    데이터: secret

  노드 검증:
    1. SHA256(secret) == commit_hash? ✅
    2. Commit TX의 블록 높이 확인 → Block #500
    3. Block #500의 해시 조회 → 0x7a3f...b2c1
    4. result = SHA256(secret + 0x7a3f...b2c1)
    5. 당첨? = result < threshold

  핵심: 모든 노드가 동일하게 계산 가능 (결정론적!)


=== 타임라인 정리 ===

  시점         │ 유저가 아는 것    │ 채굴자가 아는 것
  ─────────────┼──────────────────┼──────────────────
  Commit 전    │ secret           │ (없음)
  Commit 후    │ secret           │ commit_hash
  블록 포함 후 │ secret, block_hash│ commit_hash, block_hash
  Reveal       │ 전부             │ 전부
  
  조작 가능 시점:
    유저: Commit 전에 secret 선택 → 하지만 block_hash 모름
    채굴자: 블록 만들 때 hash 선택 → 하지만 secret 모름
    → 어느 시점에도 한쪽이 전체를 통제할 수 없음!
```

### 4.3 해결된 것

```
유저 조작 방지: ✅ (V1에서 해결)
  secret을 미리 골라도 block_hash를 모르니 결과 예측 불가

채굴자 단독 조작 방지: ✅ (V2에서 해결)
  block_hash를 조작해도 secret을 모르니 결과 예측 불가

제3자 조작 방지: ✅
  secret도 block_hash도 모르니 결과 예측 불가

투명성: ✅
  Reveal 후 모든 노드가 결과를 동일하게 검증 가능
```

### 4.4 남은 문제: 채굴자의 "블록 폐기" 공격

```
시나리오:
  채굴자가 자기 가챠의 Commit TX를 포함한 블록을 채굴

  이 채굴자는 secret을 알고 있음 (자기 가챠니까)
  
  블록 채굴 성공!
    block_hash 확정
    result = SHA256(secret + block_hash)
    
    if 당첨:
      → 블록 공개! (당첨 확정)
    
    if 꽝:
      → 블록 폐기! (이 블록을 안 냄)
      → 다른 nonce로 다시 채굴
      → 다른 block_hash로 다시 계산
      → 당첨 나올 때까지 반복!

  이렇게 하면:
    채굴자 = 당첨될 때까지 블록을 계속 다시 만드는 것
    → 확률 조작 가능!
```

---

## 5. V3: 경제적 억제

### 5.1 핵심 아이디어

```
V2의 남은 문제:
  채굴자가 블록을 폐기하면서 유리한 해시를 찾을 수 있음

V3의 통찰:
  블록 폐기 = 블록 보상 포기!
  
  채굴자가 블록을 버리면:
    50 JACK 블록 보상을 포기하는 것
    + 수수료도 포기
    
  조작이 이득이 되려면:
    당첨금 > 포기한 블록 보상들의 합

  → 조작을 "불가능"하게 만든 건 아니지만
  → "비경제적"으로 만들 수 있음!
```

### 5.2 경제학적 분석

```
=== 조작 비용 계산 ===

블록 보상: 50 JACK
당첨 확률: 1%
잭팟 풀: P JACK
당첨금: P × 60%

채굴자의 조작:
  블록을 채굴할 때마다 당첨 여부 확인
  꽝이면 블록 폐기 → 50 JACK 포기
  
  당첨 나올 확률 1%
  → 평균 100블록 만들어야 1번 당첨
  → 99블록 폐기 = 99 × 50 = 4,950 JACK 포기

손익 분석:
  이득: P × 60%
  비용: ~4,950 JACK

  이득 > 비용 조건:
    P × 60% > 4,950
    P > 8,250 JACK
    
  즉: 잭팟 풀이 8,250 JACK 이상이어야 조작이 이득

MVP 현실:
  6주 운영, 잭팟 풀 ~72,000 JACK (당첨 0일 때 최대)
  당첨이 1~2번 있었다면 ~10,000~30,000 JACK

  풀이 30,000이면:
    이득: 30,000 × 60% = 18,000 JACK
    비용: ~4,950 JACK
    → 이득! 조작 동기 있음 ⚠️

  하지만 추가 고려사항:
    1. 채굴자가 블록을 폐기하면 다른 채굴자가 먼저 채굴
       → 경쟁 환경에서는 블록 폐기 비용이 더 큼
    2. MVP 6노드 = 팀원 → 신뢰 기반
    3. 모든 가챠 기록이 온체인 → 패턴 감지 가능
```

### 5.3 추가 억제 메커니즘

```
억제 1: Commit과 Reveal 사이 간격 강제

  Commit: Block #500
  Reveal: Block #502 이후 (최소 2블록 간격)
  
  왜?
    Commit이 포함된 블록의 채굴자 ≠ Reveal 시점의 채굴자 (대부분)
    → Commit 블록 해시를 조작해도
    → 그 채굴자가 Reveal 블록도 채굴할 확률 낮음
    → 조작 연계가 어려워짐


억제 2: 여러 블록의 해시 혼합

  기본:   result = SHA256(secret + block_hash_N)
  강화:   result = SHA256(secret + block_hash_N + block_hash_N+1)
  
  N = Commit 블록, N+1 = 다음 블록
  
  → 채굴자가 Block N을 조작해도
  → Block N+1의 해시는 다른 채굴자가 결정
  → 두 블록을 모두 조작하려면 연속 2블록 채굴해야 함
  → 해시파워 50% 미만이면 매우 어려움


억제 3: 당첨금 상한

  당첨금 = min(풀 잔액 × 60%, 상한금액)
  
  예: 상한 10,000 JACK
  → 풀이 아무리 커도 1회 당첨 최대 10,000 JACK
  → 조작 이득에 상한 설정
  → 조작 비용이 상한보다 크면 항상 비경제적
```

### 5.4 정리: V0 → V3 진화

```
┌──────┬────────────────┬──────────────┬──────────────────┐
│ 버전 │ 설계           │ 해결한 것    │ 남은 문제        │
├──────┼────────────────┼──────────────┼──────────────────┤
│ V0   │ 블록 해시만    │ (없음)       │ 채굴자 완전 조작 │
│      │               │              │ (비용 0)         │
├──────┼────────────────┼──────────────┼──────────────────┤
│ V1   │ Commit-Reveal  │ 유저 조작    │ 유저가 secret을  │
│      │ (secret만)     │ 방지         │ 미리 골라서 당첨 │
├──────┼────────────────┼──────────────┼──────────────────┤
│ V2   │ Commit-Reveal  │ 유저+채굴자  │ 채굴자 블록 폐기 │
│      │ + 블록 해시    │ 단독 조작    │ 로 확률 편향     │
│      │               │ 방지         │                  │
├──────┼────────────────┼──────────────┼──────────────────┤
│ V3   │ V2 + 경제적    │ 조작을       │ 잭팟이 극도로    │
│      │ 억제           │ 비경제적으로 │ 크면 이론적으로  │
│      │               │ 만듦         │ 조작 가능        │
└──────┴────────────────┴──────────────┴──────────────────┘

V3 = JackpotChain MVP의 선택
→ 완전무결은 아니지만 "충분히 공정"
→ 조작 비용 > 이득이면 합리적 행위자는 조작 안 함
```

---

## 6. Commit TX 상세

### 6.1 TX 구조

```
Gacha Commit TX (version 3):
  
  Input[0]: 유저의 UTXO
    - JACK (수수료용)
    - POT (가챠 비용, 1 POT)
  
  Output[0]: 유저 거스름돈
    - 남은 JACK
    - 남은 POT (있으면)
  
  Output[1]: Commit UTXO
    - jack_value: 0 (또는 Min JACK)
    - 데이터: commit_hash (32 bytes)
    - script_pubkey: 특수 (Reveal 조건)
  
  수수료: JACK
  POT 소각: 1 POT (Burn)
```

### 6.2 예시

```
Alice가 가챠 플레이:

secret = 0xa7b3c9d1e5f2... (32 bytes, 지갑이 생성)
commit_hash = SHA256(secret) = 0x3f8a1b...

Commit TX (version 3):
  Input[0]: Alice UTXO (10 JACK + 5 POT)
  
  Output[0]: 9.89 JACK + 4 POT → Alice (거스름돈)
  Output[1]: 0.01 JACK → Commit UTXO
    데이터: commit_hash = 0x3f8a1b...
  
  수수료: 0.1 JACK
  POT 소각: 1 POT

정산:
  JACK: 10 = 9.89 + 0.01 + 0.1(fee) ✅
  POT:  5 = 4 + 1(burn) ✅
```

### 6.3 Commit UTXO의 잠금 조건

```
Commit UTXO는 일반 P2PKH가 아닌 특수 Script:

  "commit_hash의 원상(secret)을 제시하고
   Commit한 유저의 서명이 있어야 소비 가능"

의미:
  1. secret을 알아야 함 (= Commit한 유저만)
  2. 유저의 서명도 필요 (= 다른 사람이 secret을 알아도 못 씀)
  → 이중 보호

왜 서명도 필요한가?
  secret이 Reveal TX에 공개되면 누구나 볼 수 있음
  만약 서명 없이 secret만으로 소비 가능하면?
  → Reveal TX가 Mempool에 있을 때 누군가 가로채기 가능!
  → 서명이 있으면 유저만 소비 가능
```

---

## 7. Reveal TX 상세

### 7.1 TX 구조

```
Gacha Reveal TX (version 4):

  Input[0]: Commit UTXO
    - secret 제시 (script_sig에 포함)
    - 유저 서명
  
  Input[1~N]: 잭팟 풀 UTXO (당첨 시에만)
  
  Output[0]: 당첨금 → 유저 (당첨 시)
  Output[1]: 잭팟 풀 거스름돈 (당첨 시)
  
  수수료: JACK (Commit UTXO의 Min JACK에서)
```

### 7.2 당첨 계산

```
Step 1: 재료 수집
  secret: Reveal TX에서 제공
  block_hash: Commit TX가 포함된 블록의 해시

Step 2: 결과 계산
  result = SHA256(secret + block_hash)
  
  result는 256비트 숫자 (0 ~ 2^256-1)

Step 3: 당첨 판정
  threshold = 2^256 × 당첨확률
  
  당첨확률 1%:
    threshold = 2^256 × 0.01
    ≈ 1.157 × 10^75
  
  당첨 조건:
    result < threshold → 당첨! 🎉
    result ≥ threshold → 꽝 💨

Step 4: 모든 노드가 동일하게 계산
  secret (공개됨) + block_hash (공개됨)
  → 결정론적 결과
  → 합의 가능
```

### 7.3 꽝인 경우

```
Reveal TX (꽝):
  Input[0]: Commit UTXO (소비)
  
  Output[0]: 잔여 JACK → 유저
    (Commit UTXO에 있던 Min JACK - 수수료)
  
  잭팟 풀: 변화 없음
  → 단순히 Commit UTXO를 정리하는 TX
```

### 7.4 당첨인 경우

```
잭팟 풀 잔액 (Commit 블록 시점): 10,000 JACK
당첨금 비율: 60%
당첨금: 6,000 JACK

Reveal TX (당첨):
  Input[0]: Commit UTXO
  Input[1]: 잭팟 풀 UTXO ① (3,000 JACK)
  Input[2]: 잭팟 풀 UTXO ② (2,500 JACK)
  Input[3]: 잭팟 풀 UTXO ③ (1,000 JACK)
  → 합: 6,500 JACK (당첨금 6,000 이상)
  
  Output[0]: 6,000 JACK → 당첨자
  Output[1]: 500 JACK → 잭팟 풀 주소 (거스름돈)
  
  수수료: Commit UTXO의 Min JACK에서 차감

검증:
  ✅ 당첨 계산 결과가 실제로 당첨인가?
  ✅ 당첨금 = Commit 블록 시점 풀 잔액 × 60%?
  ✅ 잭팟 풀 UTXO가 실제로 잭팟 주소의 것인가?
  ✅ 거스름돈이 잭팟 주소로 돌아가는가?
```

---

## 8. 치트 방지

### 8.1 지연 치트 방지 (Commit 시점 고정)

```
공격:
  당첨자가 Reveal을 늦춰서 풀이 더 쌓인 후 수령

방어:
  당첨금 = Commit 블록 시점의 풀 잔액 기준

  Commit: Block #500 (풀 잔액 10,000 JACK)
  Reveal: Block #700 (풀 잔액 15,000 JACK)
  
  당첨금: 10,000 × 60% = 6,000 JACK (Block #500 기준!)
  → 15,000 × 60% = 9,000이 아님!
  → 지연 이득 제로

구현:
  Reveal TX 검증 시:
    1. Commit TX의 블록 높이 확인 → Block #500
    2. Block #500 시점 잭팟 주소의 UTXO 합산
    3. 이 금액 기준으로 당첨금 계산
```

### 8.2 Reveal 기한 (Timeout)

```
규칙:
  Commit 후 50블록(~12.5분) 이내에 Reveal 해야 함

  Commit: Block #500
  Reveal 가능: Block #502 ~ #550
    (#501은 불가 — 최소 1블록 간격)
    (#550 이후 불가 — 기한 만료)

기한 만료 시:
  Commit UTXO가 "만료" 상태
  → 아무도 소비 불가
  → POT은 이미 소각됨 (돌려받기 없음)
  → 당첨 권리 소멸

왜 기한이 필요한가?

  1. 상태 정리
     기한 없으면 Commit UTXO가 영원히 남음
     → UTXO Set 비대화

  2. 스팸 방지
     Commit만 하고 Reveal 안 하는 공격
     → 의미 없는 UTXO 증가
     → 기한 있으면 자동 정리

  3. 풀 잔액 예측성
     당첨이 언제 확정될지 모르면 풀 관리 어려움
     → 기한 내 미확정 → 무효 → 예측 가능
```

### 8.3 Commit-Reveal 동일 블록 방지

```
규칙:
  Commit TX와 Reveal TX는 같은 블록에 들어갈 수 없음
  → 최소 1블록 간격 필수

이유:
  같은 블록이면 채굴자가:
    1. 자기 Commit TX + Reveal TX를 준비
    2. 블록 해시(nonce)를 바꿔가며 시도
    3. 당첨되는 조합을 찾으면 그 블록 제출
    → V0과 동일한 조작!

방어:
  Reveal TX 검증 시:
    commit_block_height = Commit TX의 블록 높이
    reveal_block_height = 현재 블록 높이
    
    if reveal_block_height <= commit_block_height:
      거부! "Commit과 Reveal은 다른 블록이어야 함"
    
    if reveal_block_height <= commit_block_height + 1:
      거부! "최소 2블록 간격 필요" (선택적 강화)
```

### 8.4 프론트러닝 방지

```
공격:
  유저의 Reveal TX가 Mempool에 보임
  → 공격자가 secret을 읽음
  → 공격자가 같은 secret으로 자기 TX를 만들어서 먼저 제출?

방어:
  Commit UTXO에 유저 서명이 필요
  → secret을 알아도 유저의 개인키 없이 소비 불가
  → 프론트러닝 불가능!

추가:
  Reveal TX가 Mempool에서 보여도:
    secret + block_hash로 결과 미리 계산 가능
    → 하지만 결과를 바꿀 수 없음 (이미 확정됨)
    → 보는 것과 조작하는 것은 다름
```

---

## 9. 전체 가챠 흐름 (통합)

### 9.1 정상 플레이 (꽝)

```
1. Alice: secret 생성
   secret = 0xa7b3...
   commit_hash = SHA256(secret) = 0x3f8a...

2. Alice: Commit TX 전파
   Input: 10 JACK + 5 POT
   Output: 9.89 JACK + 4 POT (거스름돈) + Commit UTXO
   POT 소각: 1 POT

3. Block #500에 Commit TX 포함
   block_hash = 0x7a3f...

4. Alice: Reveal TX 전파 (Block #502)
   secret = 0xa7b3... 공개

5. 노드 검증:
   SHA256(0xa7b3...) == 0x3f8a...? ✅
   result = SHA256(0xa7b3... + 0x7a3f...)
   result ≥ threshold → 꽝!

6. Reveal TX Output:
   잔여 JACK → Alice
   → 끝! Alice는 1 POT을 잃었지만 꽝.
```

### 9.2 정상 플레이 (당첨!)

```
1~3. (꽝과 동일)

4. Alice: Reveal TX 전파 (Block #503)

5. 노드 검증:
   result = SHA256(secret + block_hash)
   result < threshold → 당첨! 🎉

6. 당첨금 계산:
   Block #500 시점 잭팟 풀: 10,000 JACK
   당첨금: 10,000 × 60% = 6,000 JACK

7. Reveal TX:
   Input: Commit UTXO + 잭팟 UTXO들
   Output: 6,000 JACK → Alice + 잭팟 거스름돈

8. Block #503에 Reveal TX 포함
   → Alice: 6,000 JACK 수령!
   → 잭팟 풀: 10,000 - 6,000 = 4,000 JACK 잔여
```

### 9.3 기한 만료

```
1~3. (동일)

4. Alice가 Reveal을 안 함 (잊어버림, 오프라인 등)

5. Block #550 도달 (기한 만료)

6. Commit UTXO 상태: 만료
   → 누구도 소비 불가
   → POT 1개: 이미 소각됨 (복구 불가)
   → 당첨 권리: 소멸

7. UTXO Set 정리:
   만료된 Commit UTXO → 노드가 알아서 정리
   (또는 일정 시간 후 Pruning)
```

---

## 10. 보안 분석 요약

### 10.1 공격 벡터별 방어 상태

```
┌──────────────────────┬───────┬────────────────────────┐
│ 공격                 │ 방어  │ 방어 수단              │
├──────────────────────┼───────┼────────────────────────┤
│ 유저: secret 미리    │ ✅    │ block_hash 혼합        │
│ 계산해서 당첨 고르기 │       │ (Commit 시점에 모름)   │
├──────────────────────┼───────┼────────────────────────┤
│ 채굴자: block_hash   │ ✅    │ secret을 모름          │
│ 조작으로 당첨 결정   │       │ (Commit-Reveal 분리)   │
├──────────────────────┼───────┼────────────────────────┤
│ 채굴자: 블록 폐기로  │ ⚠️    │ 블록 보상 포기 비용    │
│ 유리한 hash 찾기     │       │ (경제적 억제)          │
├──────────────────────┼───────┼────────────────────────┤
│ 지연 치트:           │ ✅    │ Commit 블록 시점       │
│ 풀 쌓인 후 Reveal    │       │ 잔액 기준 고정         │
├──────────────────────┼───────┼────────────────────────┤
│ Reveal 검열:         │ ⚠️    │ 다른 채굴자가 포함     │
│ 채굴자가 안 넣기     │       │ 기한 내 여러 번 시도   │
├──────────────────────┼───────┼────────────────────────┤
│ 프론트러닝:          │ ✅    │ 서명 필요              │
│ secret 가로채기      │       │ (개인키 없이 소비 불가)│
├──────────────────────┼───────┼────────────────────────┤
│ Commit 스팸          │ ✅    │ POT 소각 비용          │
│                      │       │ + Reveal 기한 만료     │
├──────────────────────┼───────┼────────────────────────┤
│ Commit-Reveal        │ ✅    │ 최소 블록 간격 강제    │
│ 동일 블록            │       │                        │
└──────────────────────┴───────┴────────────────────────┘

✅ = 구조적으로 방어됨
⚠️ = 경제적으로 억제됨 (완전 방어는 아님)
```

### 10.2 "충분히 공정"의 근거

```
JackpotChain MVP 환경에서:

  1. 채굴자 = 팀원 (6명)
     → 악의적 조작 동기 극히 낮음

  2. 잭팟 풀 규모 소형
     → 조작 이득 < 블록 보상 포기 비용 (대부분 경우)

  3. 모든 기록이 온체인
     → 비정상 패턴 (연속 당첨 등) 즉시 감지
     → 사후 감사 가능

  4. 경제적 억제
     → 합리적 행위자는 조작 안 함
     → 비합리적 행위자도 비용 부담

완전무결은 아니지만:
  → 중앙 서버 가챠보다 투명
  → 확률 조작 불가능 (모든 노드가 검증)
  → 조작 시도의 비용이 명확
  → "누군가 조작했는지" 사후 검증 가능

이것이 탈중앙화 가챠의 가치:
  "조작이 불가능"이 아니라
  "조작했는지 누구나 확인할 수 있다"
```

### 10.3 미래 개선 (MVP 이후)

```
Level 1 (현재): V3 — Commit-Reveal + 경제적 억제
  → MVP에 충분

Level 2: 다중 블록 해시 혼합
  result = SHA256(secret + hash_N + hash_N+1 + hash_N+2)
  → 연속 3블록 조작 필요 = 매우 어려움

Level 3: VRF (Verifiable Random Function)
  → 채굴자가 검증 가능한 랜덤 생성
  → 조작 불가 + 증명 가능
  → 구현 복잡 (Cardano Ouroboros 참조)

Level 4: 외부 오라클 연동
  → Chainlink VRF 등
  → 완전한 외부 랜덤
  → 외부 의존성 발생
```

---

## 11. MVP 구현 가이드

### 11.1 구현 우선순위

```
Phase 1 (필수):
  ✅ Commit TX (version 3) 생성/검증
  ✅ Reveal TX (version 4) 생성/검증
  ✅ SHA256(secret + block_hash) 랜덤 계산
  ✅ 당첨 판정 (result < threshold)
  ✅ POT Burn (Commit 시)
  ✅ Commit-Reveal 블록 간격 검증

Phase 2 (치트 방지):
  ✅ 당첨금 Commit 블록 시점 고정
  ✅ Reveal 기한 (50블록)
  ✅ 잭팟 풀 UTXO 소비 + 거스름돈 처리
  ✅ 서명 검증 (프론트러닝 방지)

Phase 3 (모니터링):
  ⬜ 가챠 통계 로깅
  ⬜ 비정상 패턴 감지
  ⬜ 풀 잔액 실시간 표시
```

### 11.2 파라미터

```
GACHA_COST = 1 POT
WIN_PROBABILITY = 0.01 (1%)
PAYOUT_RATIO = 0.60 (60%)
MIN_REVEAL_GAP = 2 blocks
MAX_REVEAL_GAP = 50 blocks
RANDOM_SEED = SHA256(secret + block_hash)
```

---

## 12. 핵심 요약

### 진화 과정
```
V0: 블록 해시만 → 채굴자 완전 조작 가능
V1: Commit-Reveal → 유저 조작 방지, 채굴자 여전히 문제
V2: + 블록 해시 혼합 → 단독 조작 방지
V3: + 경제적 억제 → 조작 비경제적으로 만듦
→ 완전무결은 아니지만 "충분히 공정"
```

### Commit-Reveal
```
Commit: hash(secret) 공개, secret 비밀
블록 포함: block_hash 확정
Reveal: secret 공개, 결과 계산
→ 어느 시점에도 단독 조작 불가
```

### 치트 방지
```
지연 치트: Commit 블록 시점 풀 잔액 고정
기한 만료: 50블록 내 Reveal 필수
동일 블록: 최소 2블록 간격 강제
프론트러닝: 서명 필수
스팸: POT 소각 비용
```

### 탈중앙화 가챠의 가치
```
"조작이 불가능"이 아니라
"조작했는지 누구나 확인할 수 있다"
= 투명성 + 검증 가능성
```

---

## 13. 체크리스트

이해했는지 확인:

- [ ] 블록체인에서 랜덤이 왜 어려운지
- [ ] V0의 문제 (채굴자 완전 조작)
- [ ] V1 Commit-Reveal의 원리와 한계
- [ ] V2 블록 해시 혼합의 효과
- [ ] V3 경제적 억제의 비용/이득 분석
- [ ] Commit TX와 Reveal TX의 구조
- [ ] 당첨 계산 방법 (SHA256 + threshold)
- [ ] 지연 치트 방지 (Commit 시점 고정)
- [ ] Reveal 기한과 만료 처리
- [ ] 프론트러닝 방지 (서명 필요)
- [ ] 채굴자 블록 폐기 공격의 경제학
- [ ] "충분히 공정"의 근거

---

## 14. 다음 학습

### Phase 3 완료!
```
✅ 13. 멀티에셋 시스템
✅ 14. 토크노믹스
✅ 15. Exchange 모듈
✅ 16. 가챠 시스템
```

### 다음 추천:
```
→ [17. 스마트 컨트랙트 (Script)](17-script-system.md)
  - Bitcoin Script 확장
  - Commit-Reveal Script 구현
  - 잭팟 풀 Script
  - MultiSig, TimeLock

→ Phase 4: 최적화
  - 성능 최적화
  - 저장소 설계
  - 보안 강화
  - 테스트 전략
```

---

## 15. 참고 자료

**온체인 랜덤:**
- Commit-Reveal Schemes in Blockchain
- "On Bitcoin as a public randomness source" (Bonneau et al., 2015)
- Randao: Decentralized Random Number Generation

**VRF:**
- Cardano Ouroboros VRF
- Chainlink VRF Documentation
- "Verifiable Random Functions" (Micali et al., 1999)

**가챠/확률:**
- Game Gacha Mechanics Design
- Provably Fair Gaming (Casino)
- "Fairness in Online Games" (Survey)

**경제적 보안:**
- Miner Extractable Value (MEV)
- Flashbots and Transaction Ordering
- Economic Security of Consensus Protocols

---

**이전:** [15. Exchange 모듈](15-exchange-module.md)  
**다음:** [17. 스마트 컨트랙트 (Script)](17-script-system.md) →
