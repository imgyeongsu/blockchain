# JackpotChain 학습 로드맵

> 블록체인 개념을 체계적으로 학습하기 위한 로드맵

---

## 📚 학습 철학

**Bottom-Up 접근:**
- 기초부터 단계적으로
- 각 개념이 다음 개념의 전제
- 실습 가능한 수준으로 이해

**목표:**
- 개념 확실히 잡기
- 구현 전 설계 이해
- 팀원 온보딩 자료

---

## 🎯 전체 구조

### Phase 0: 기초 (Foundation)
블록체인을 이해하는 데 필요한 기본 개념

### Phase 1: 코어 (Core)
블록체인의 핵심 구성 요소

### Phase 2: 네트워크 (Network)
탈중앙화 네트워크 구현

### Phase 3: 고급 (Advanced)
JackpotChain만의 특수 기능

### Phase 4: 최적화 (Optimization)
성능과 보안 강화

---

## 📖 학습 순서

### Phase 0: 기초 (Foundation) - 예상 2-3일

1. **[암호학 기초](phase-0-foundation/01-cryptography-basics.md)** ⭐ START HERE
   - 해시 함수 (SHA-256)
   - 공개키 암호화 (ECDSA)
   - 서명과 검증
   - Merkle Tree
   
2. **[데이터 구조](phase-0-foundation/02-data-structures.md)**
   - 블록 구조
   - 트랜잭션 구조
   - 체인 연결 방식
   
3. **[UTXO vs Account](phase-0-foundation/03-utxo-vs-account.md)** ✅ 완료
   - 상태 모델 비교
   - 멀티에셋 UTXO
   - 잔액 추적

---

### Phase 1: 코어 (Core) - 예상 3-4일

4. **[블록 & 블록체인](phase-1-core/04-blocks-and-blockchain.md)**
   - 블록 헤더
   - Genesis Block
   - 체인 검증
   - Merkle Root 활용

5. **[트랜잭션 심화](phase-1-core/05-transactions-deep-dive.md)**
   - Input/Output 구조
   - Script 언어
   - P2PKH, P2SH
   - 서명 생성/검증
   - 멀티에셋 TX

6. **[PoW 합의](phase-1-core/06-pow-consensus.md)** ✅ 완료
   - 채굴 메커니즘
   - 난이도 조절
   - Longest Chain Rule
   - 포크 해결

7. **[UTXO Set 관리](phase-1-core/07-utxo-set-management.md)**
   - UTXO 추가/삭제
   - 인덱싱 전략
   - 잔액 조회 최적화
   - 이중 지불 방지

---

### Phase 2: 네트워크 (Network) - 예상 3-4일

8. **[P2P 네트워크 기초](phase-2-network/08-p2p-basics.md)** ✅ 완료
   - 노드 타입
   - Peer Discovery
   - 연결 관리

9. **[네트워크 프로토콜](phase-2-network/09-network-protocol.md)**
   - 메시지 타입
   - 직렬화/역직렬화
   - 핸드셰이크

10. **[블록 전파](phase-2-network/10-block-propagation.md)** ✅ 완료
    - Gossip Protocol
    - INV/GETDATA 방식
    - Compact Block

11. **[동기화](phase-2-network/11-synchronization.md)**
    - Initial Block Download
    - Headers-First Sync
    - Orphan Block 처리

12. **[네트워크 보안](phase-2-network/12-network-security.md)** ✅ 완료
    - Eclipse Attack
    - Sybil Attack
    - DDoS 방어
    - 51% Attack

---

### Phase 3: 고급 (Advanced) - 예상 4-5일

13. **[멀티에셋 시스템](phase-3-advanced/13-multi-asset-system.md)**
    - Asset Policy
    - Mint Transaction
    - Asset Registry
    - 에셋별 검증

14. **[토크노믹스](phase-3-advanced/14-tokenomics.md)**
    - 발행량 (무제한)
    - 블록 보상 (50 JACK)
    - 수수료 분배 (50/20/30)
    - 소각 메커니즘
    - 인플레이션 분석

15. **[Exchange 모듈](phase-3-advanced/15-exchange-module.md)**
    - JACK → POT 교환
    - 고정 비율 (v1)
    - AMM 방식 (v2)
    - 유동성 관리

16. **[가챠 시스템](phase-3-advanced/16-gacha-system.md)**
    - Commit-Reveal
    - 랜덤성 보장
    - 확률 검증
    - 잭팟 풀 관리

17. **[스마트 컨트랙트 (Script)](phase-3-advanced/17-script-system.md)**
    - Bitcoin Script
    - 조건부 잠금
    - MultiSig
    - Time Lock

---

### Phase 4: 최적화 (Optimization) - 예상 3-4일

18. **[성능 최적화](phase-4-optimization/18-performance-optimization.md)**
    - TPS 분석
    - 병렬 검증
    - 캐싱 전략
    - 메모리 관리

19. **[저장소 설계](phase-4-optimization/19-storage-design.md)**
    - LevelDB/RocksDB
    - 인덱싱
    - Pruning
    - State 관리

20. **[보안 강화](phase-4-optimization/20-security-hardening.md)**
    - 입력 검증
    - 에러 처리
    - Rate Limiting
    - 모니터링

21. **[테스트 전략](phase-4-optimization/21-testing-strategy.md)**
    - 단위 테스트
    - 통합 테스트
    - 포크 시나리오
    - 공격 시뮬레이션

---

## 🎓 학습 방법

### 각 주제마다:

1. **개념 학습 (30분 - 1시간)**
   - 문서 읽기
   - 다이어그램 이해
   - 의사코드 파악

2. **질문 & 토론 (20분)**
   - 이해 안 되는 부분 질문
   - 팀원과 토론
   - Claude와 심화 대화

3. **요약 정리 (10분)**
   - 핵심 개념 3가지
   - 구현 시 주의점
   - 다음 주제 연결점

4. **휴식 (10분)**
   - 커피 타임 ☕
   - 산책

---

## ✅ 진행 상황

### 완료된 주제:
- [x] P2P 네트워크 기초
- [x] 블록 전파 (Gossip)
- [x] 네트워크 보안
- [x] UTXO vs Account
- [x] PoW 합의

### 현재 학습 중:
- [ ] 학습 로드맵 세팅

### 다음 예정:
- [ ] 암호학 기초 (추천 시작점)

---

## 📅 추천 일정

### Week 1: Foundation + Core 기초
- Day 1-2: Phase 0 (암호학, 데이터 구조)
- Day 3-4: Phase 1 일부 (블록, 트랜잭션)
- Day 5: 복습 & 실습

### Week 2: Core 완성 + Network 시작
- Day 1-2: Phase 1 완성 (UTXO Set)
- Day 3-5: Phase 2 (P2P, 프로토콜, 동기화)

### Week 3: Advanced 기능
- Day 1-2: 멀티에셋, 토크노믹스
- Day 3-4: Exchange, 가챠
- Day 5: 통합 설계 리뷰

### Week 4: 구현 준비
- Day 1-2: Phase 4 (최적화, 저장소)
- Day 3-4: 전체 복습
- Day 5: 구현 계획 수립

---

## 🔗 참고 자료

### 공식 문서:
- Bitcoin Whitepaper
- Bitcoin Developer Guide
- Ethereum Yellow Paper (Account 모델 참고)
- Cardano Multi-Asset 문서

### 책:
- Mastering Bitcoin (Andreas Antonopoulos)
- Mastering Ethereum
- Programming Bitcoin (Jimmy Song)

### 코드:
- Bitcoin Core (C++)
- btcd (Go)
- parity-bitcoin (Rust)

---

## 💡 학습 팁

1. **개념 먼저, 코드는 나중에**
   - 왜 이렇게 설계했는지 이해
   - 트레이드오프 파악

2. **다이어그램 그리기**
   - 머릿속 개념을 시각화
   - 화이트보드 활용

3. **질문 목록 작성**
   - 이해 안 되는 부분 메모
   - 팀 미팅 때 공유

4. **다른 체인과 비교**
   - Bitcoin은 어떻게?
   - Ethereum은 왜 다르게?
   - JackpotChain은 어떤 선택?

5. **실제 사례 연결**
   - "만약 공격자가..."
   - "만약 채굴자가..."
   - "만약 네트워크가..."

---

## 📞 도움 요청

### 막혔을 때:
1. 해당 문서 다시 읽기
2. 참고 자료 찾아보기
3. Claude에게 질문
4. 팀원과 토론
5. 멘토에게 질문

### 질문 템플릿:
```
주제: [12-network-security.md]
섹션: [3.2 Sybil Attack]
질문: "왜 IP 주소 제한만으로는 Sybil을 막을 수 없나요?"
이해한 내용: "NAT 때문이라고 하는데..."
궁금한 점: "그럼 어떻게 구분하나요?"
```

---

**다음 단계:** [01-cryptography-basics.md](phase-0-foundation/01-cryptography-basics.md)에서 시작하세요! 🚀
