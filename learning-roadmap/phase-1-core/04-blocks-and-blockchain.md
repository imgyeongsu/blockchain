# 04. 블록 & 블록체인 (Blocks and Blockchain)

> **Phase 1: Core**  
> **상태:** ✅ 완료 (02-data-structures.md에 통합)  
> **학습 날짜:** 2025-02-12  
> **예상 소요 시간:** 1-2시간  
> **선행 학습:** [01. 암호학 기초](01-cryptography-basics.md), [02. 데이터 구조](02-data-structures.md)

---

## 📌 안내

이 문서의 내용은 **[02-data-structures.md](02-data-structures.md)**에 통합되어 있습니다.  
02 문서를 작성하면서 블록 구조, 체인 연결, Genesis Block, 블록 생성/검증까지 함께 다뤘기 때문에 별도 문서를 만들지 않았습니다.

---

## 🔗 참조 위치

아래 내용은 모두 `02-data-structures.md`에서 확인할 수 있습니다:

| 주제 | 02 문서 섹션 |
|------|-------------|
| 블록 헤더 구조 (80 bytes, 6개 필드) | §2. 블록 헤더 (Block Header) |
| 각 필드 상세 (version, prev_hash, merkle_root, timestamp, difficulty_target, nonce) | §2.3 각 필드 상세 |
| 헤더 해시 계산 (Double SHA-256) | §2.4 헤더 해시 계산 |
| 체인 연결 (prev_block_hash) | §4.1 체인의 핵심: prev_block_hash |
| 체인 검증 (정방향/역방향) | §4.2 체인 검증 |
| 위변조 감지 (Cascading Effect) | §4.3 위변조 감지 |
| Genesis Block (하드코딩, JackpotChain Genesis) | §4.4 Genesis Block |
| 블록 생성 과정 (채굴자 관점 6단계) | §5.1 채굴자 관점 |
| 블록 검증 과정 (검증자 관점 5단계) | §5.2 검증자 관점 |
| 실전 예시 (Block #100) | §6.1 Block #100 |

---

## 🎯 학습 목표 (02 문서에서 달성)

- [x] 블록 헤더의 6가지 필드를 설명할 수 있다
- [x] prev_block_hash가 어떻게 체인을 형성하는지 이해한다
- [x] Genesis Block의 특별함을 안다
- [x] 블록 생성 과정 (채굴자 관점)을 설명할 수 있다
- [x] 블록 검증 과정 (검증자 관점)을 이해한다
- [x] 위변조 시 연쇄 반응이 발생하는 원리를 안다
- [x] Merkle Root가 블록 헤더에서 하는 역할을 안다

---

## 💡 핵심 요약

### 블록 헤더 (80 bytes)
```
6가지 필드:
  1. version (4 bytes): 프로토콜 버전
  2. prev_block_hash (32 bytes): 체인 연결
  3. merkle_root (32 bytes): TX 요약
  4. timestamp (4 bytes): 생성 시간
  5. difficulty_target (4 bytes): PoW 난이도
  6. nonce (4 bytes): PoW 해답
```

### 체인 보안
```
위변조 → 해시 변경 → 후속 블록 전부 불일치
→ 모든 PoW 재계산 필요
→ 사실상 불가능
```

### Genesis Block
```
JackpotChain:
  timestamp: 2026-01-01 00:00:00 UTC
  prev_block_hash: "000...000"
  블록 보상: 50 JACK
  message: "JackpotChain Genesis - 2026"
```

---

## 📖 학습 경로

```
이전: [03. UTXO vs Account](03-utxo-vs-account.md)
현재: 04. 블록 & 블록체인 → 02-data-structures.md 참조
다음: [05. 트랜잭션 심화](05-transactions-deep-dive.md)
```

---

**→ [02-data-structures.md](02-data-structures.md)로 이동하여 학습하세요!**
