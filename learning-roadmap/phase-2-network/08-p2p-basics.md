# 08. P2P 네트워크 기초

> **Phase 2: Network**  
> **상태:** ✅ 완료  
> **학습 날짜:** 2025-02-11  
> **예상 소요 시간:** 1-2시간  

---

## 🎯 학습 완료 체크

이 주제를 통해 학습한 내용:
- [x] P2P vs 중앙 서버 구조
- [x] 노드 타입 (Full, Light, Mining, Archive)
- [x] Peer Discovery (시드, DNS, PEX, DHT)
- [x] NAT Traversal 문제와 해결
- [x] SSAFY 환경 대응 전략

---

## 📝 핵심 개념 요약

### 1. P2P 구조
```
장점:
  - 단일 실패 지점 없음
  - 검열 저항성
  - 확장성

단점:
  - 복잡한 동기화
  - 넓은 공격 표면
  - 전파 지연
```

### 2. 노드 타입
```
Full Node:
  - 전체 블록체인 보관
  - 모든 TX 검증
  - 네트워크 보안 핵심

Light Node (SPV):
  - 헤더만 보관
  - 자기 TX만 추적
  - 모바일 지갑용

Mining Node:
  - Full Node + 채굴
  - 새 블록 생성
```

### 3. Peer Discovery
```
방법 1: 시드 노드 (하드코딩)
  - 신뢰할 수 있는 시작점
  - 약간의 중앙화

방법 2: DNS Seeds
  - IP 변경 유연
  - DNS 조작 위험

방법 3: PEX (Peer Exchange)
  - 완전 분산화
  - "너가 아는 노드 목록 줘"
```

### 4. NAT Traversal
```
문제:
  공유기 뒤 노드는 외부 연결 받기 어려움

해결:
  - 포트 포워딩 (수동)
  - UPnP (자동)
  - Hole Punching
  - 릴레이 노드
```

### 5. SSAFY 환경
```
제약:
  - Inbound 연결 불가
  - 비표준 포트 차단 가능
  - UPnP 불가능

해결:
  MVP: 로컬 네트워크만 (10.0.1.x)
  확장: AWS 브릿지 노드
```

---

## 🔗 연결되는 개념

### 선행 지식:
- 기본 네트워킹 지식 (TCP/IP)

### 후속 학습:
- [09. 네트워크 프로토콜](09-network-protocol.md) - 메시지 타입
- [10. 블록 전파](10-block-propagation.md) - Gossip
- [11. 동기화](11-synchronization.md) - Initial Sync
- [12. 네트워크 보안](12-network-security.md) - 공격 방어

---

## 💡 기억할 핵심

**JackpotChain MVP 네트워크:**
```
환경: SSAFY 로컬 네트워크
노드: 6개 (팀원 PC)
연결: 직접 IP 지정
포트: 8333
시드: 팀장 PC (10.0.1.100)

확장 계획:
  - AWS EC2 브릿지 노드
  - 외부 참여 가능
```

**연결 전략:**
```
총 8개 연결:
  - Outbound: 6개 (내가 선택)
  - Inbound: 2개 (상대 선택)

다양성:
  - 여러 IP 대역
  - 여러 ASN
  - 오래된 연결 유지
```

---

## 📚 추가 학습 자료

- Bitcoin Developer Guide - P2P Network
- Ethereum DevP2P Specification
- libp2p Documentation

---

**이전:** [07. UTXO Set 관리](../phase-1-core/07-utxo-set-management.md)  
**다음:** [09. 네트워크 프로토콜](09-network-protocol.md) →
