# 06. PoW 합의 메커니즘

> **Phase 1: Core**  
> **상태:** ✅ 완료  
> **학습 날짜:** 2025-02-11  
> **예상 소요 시간:** 2-3시간  

---

## 🎯 학습 완료 체크

이 주제를 통해 학습한 내용:
- [x] PoW의 근본 원리 (퍼즐 풀기)
- [x] Target과 Difficulty 관계
- [x] 난이도 조절 알고리즘
- [x] 채굴 과정 (nonce 찾기)
- [x] Longest Chain Rule
- [x] 포크 발생과 해결
- [x] 최종 확정 (Finality)
- [x] 채굴 인센티브와 경제성
- [x] 51% 공격

---

## 📝 핵심 개념 요약

### 1. PoW 퍼즐
```
문제: hash(block + nonce) < Target

특징:
  - 찾기 어려움 (수백만 번 시도)
  - 검증 쉬움 (1번 해시)
  - 무작위 시도만 가능
```

### 2. 난이도 조절
```
JackpotChain:
  주기: 50 블록마다
  계산: Target × (실제시간 / 예상시간)
  제한: 4배 이내 변화

목적:
  채굴자 증가 → 난이도 증가
  채굴자 감소 → 난이도 감소
  → 블록 타임 15초 유지
```

### 3. Longest Chain Rule
```
규칙: 가장 긴 체인 = 진짜

포크 시:
  [999] → [1000]  vs  [1000']
           ↓
        [1001]
  
  → [1000] → [1001]이 승리 (더 김)
  → [1000'] 버려짐
```

### 4. 최종 확정
```
JackpotChain:
  1 확인 (15초): 13% 포크 위험
  6 확인 (1.5분): ~0.1% 위험
  12 확인 (3분): ~0.0001% 위험 ✅
```

### 5. 채굴 인센티브
```
보상:
  블록 보상: 50 JACK (영원히)
  수수료: TX 수수료의 50%
  
경제성:
  비용 < 수익 → 채굴 지속
  비용 > 수익 → 채굴 중단
  → 난이도 자동 균형
```

---

## 🔗 연결되는 개념

### 선행 지식:
- [01. 암호학 기초](../phase-0-foundation/01-cryptography-basics.md) - SHA-256 해시
- [04. 블록 & 블록체인](04-blocks-and-blockchain.md) - 블록 구조

### 후속 학습:
- [10. 블록 전파](../phase-2-network/10-block-propagation.md) - 채굴 후 전파
- [12. 네트워크 보안](../phase-2-network/12-network-security.md) - 51% 공격
- [14. 토크노믹스](../phase-3-advanced/14-tokenomics.md) - 블록 보상

---

## 💡 기억할 핵심

**JackpotChain PoW 파라미터:**
- 블록 타임: 15초
- 난이도 조절: 50블록 (12.5분)
- 블록 보상: 50 JACK (고정, 무제한)
- 최종 확정: 12 블록 (3분)
- 포크율: ~13% (허용 범위)

**PoW의 본질:**
```
작업 증명 = 전기 에너지 소비 증명
→ 공격 비용 = 전기료
→ 경제적 보안
```

---

## 📚 추가 학습 자료

- Bitcoin Whitepaper - Section 4 (Proof of Work)
- Bitcoin Developer Guide - Block Chain
- Mastering Bitcoin - Chapter 10 (Mining)

---

**이전:** [05. 트랜잭션 심화](05-transactions-deep-dive.md)  
**다음:** [07. UTXO Set 관리](07-utxo-set-management.md) →
