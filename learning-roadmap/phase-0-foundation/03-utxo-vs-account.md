# 03. UTXO vs Account 모델

> **Phase 0: Foundation**  
> **상태:** ✅ 완료  
> **학습 날짜:** 2025-02-11  
> **예상 소요 시간:** 1-2시간  

---

## 🎯 학습 완료 체크

이 주제를 통해 학습한 내용:
- [x] Account 모델의 작동 원리 (은행 계좌 방식)
- [x] UTXO 모델의 작동 원리 (현금 지폐 방식)
- [x] 거스름돈 메커니즘
- [x] 멀티에셋 UTXO (Cardano 방식)
- [x] 병렬 처리 차이
- [x] 프라이버시 차이
- [x] 스마트 컨트랙트 능력 차이
- [x] JackpotChain이 UTXO를 선택한 이유

---

## 📝 핵심 개념 요약

### 1. Account 모델
```
특징: 상태 중심
데이터: {address: balance}
장점: 간단한 잔액 조회, 작은 TX 크기
단점: 병렬 처리 어려움, 낮은 프라이버시
사용: Ethereum, EVM 체인들
```

### 2. UTXO 모델
```
특징: 거래 중심
데이터: UTXO 집합 (소비/생성)
장점: 병렬 처리 쉬움, 높은 프라이버시
단점: 복잡한 잔액 조회, 큰 TX 크기
사용: Bitcoin, Cardano, JackpotChain
```

### 3. 멀티에셋 UTXO
```
JackpotChain 방식:
  UTXO = {
    JACK: 100,
    POT: 50,
    NFT#123: 1
  }

검증: 각 에셋마다 Input >= Output
```

### 4. 거스름돈
```
지불: 300 JACK
보유 UTXO: 500 JACK

Input: 500 JACK
Output:
  - 상대방: 300 JACK
  - 나에게: 200 JACK (거스름돈)
```

---

## 🔗 연결되는 개념

### 선행 지식:
- 없음 (기초 개념)

### 후속 학습:
- [07. UTXO Set 관리](../phase-1-core/07-utxo-set-management.md) - 구현 세부사항
- [05. 트랜잭션 심화](../phase-1-core/05-transactions-deep-dive.md) - TX 구조
- [13. 멀티에셋 시스템](../phase-3-advanced/13-multi-asset-system.md) - Asset Policy

---

## 💡 기억할 핵심

**JackpotChain이 UTXO를 선택한 이유:**
1. 1.5세대 (Bitcoin 확장) 컨셉
2. 멀티에셋 네이티브 지원
3. 병렬 검증 (가챠 동시 발생)
4. 프라이버시 보호
5. 6주 내 구현 가능 (EVM 불필요)

---

## 📚 추가 학습 자료

- Bitcoin Developer Guide - Transactions
- Cardano Multi-Asset Documentation
- Mastering Bitcoin - Chapter 6 (Transactions)

---

**이전:** [02. 데이터 구조](02-data-structures.md)  
**다음:** [04. 블록 & 블록체인](../phase-1-core/04-blocks-and-blockchain.md) →
