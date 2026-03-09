# 06. NAT Traversal 기법 (P2P 네트워크 외부 접속)

> **Phase 1: Network**  
> **학습 날짜:** 2026-03-08  
> **난이도:** ⭐⭐⭐☆☆  
> **예상 소요 시간:** 2-3시간  
> **선행 학습:** P2P 네트워크 기초, TCP/UDP 소켓

---

## 🎯 학습 목표

이 문서를 완료하면:
- [ ] NAT가 P2P 통신을 왜 방해하는지 설명할 수 있다
- [ ] NAT 유형 4가지를 구분하고 각각의 특징을 안다
- [ ] 7가지 NAT Traversal 기법의 원리와 트레이드오프를 이해한다
- [ ] 실제 블록체인(Bitcoin, Ethereum)이 어떤 방식을 쓰는지 안다
- [ ] JackpotChain에 적합한 전략을 선택하고 근거를 댈 수 있다

---

## 1. 왜 NAT Traversal이 필요한가?

### 1.1 문제 상황

**블록체인 = P2P 네트워크:**
```
이상적인 상황:
  Node A (공인 IP) ←→ Node B (공인 IP)
  → 직접 연결 가능 ✅

현실:
  Node A (192.168.0.5) → [공유기 NAT] → 인터넷 → [공유기 NAT] ← Node B (192.168.1.10)
  → 직접 연결 불가능 ❌

이유:
  - IPv4 주소 부족 (약 43억개, 전 세계 기기 수보다 적음)
  - ISP가 공유기 뒤에 여러 기기를 NAT으로 묶음
  - NAT 뒤의 기기는 외부에서 직접 접근 불가
```

**블록체인 노드에 미치는 영향:**
```
NAT 뒤 노드가 할 수 있는 것:
  ✅ 외부 노드에 먼저 접속 (아웃바운드)
  ✅ 블록/TX 요청 & 수신

NAT 뒤 노드가 할 수 없는 것:
  ❌ 외부에서 들어오는 접속 수락 (인바운드)
  ❌ 새 노드가 나를 찾아 연결
  ❌ Full Node로서 네트워크에 기여

결과:
  - 네트워크 토폴로지 편중 (공인 IP 노드에 의존)
  - 일부 노드만 인바운드 가능 → 탈중앙화 약화
  - 노드 발견(Peer Discovery) 어려움
```

---

### 1.2 NAT의 작동 원리

```
내부 → 외부 (아웃바운드):

  [PC: 192.168.0.5:12345]
       ↓
  [공유기 NAT: 매핑 생성]
    내부 192.168.0.5:12345 → 외부 203.0.113.1:54321
       ↓
  [인터넷: 203.0.113.1:54321으로 통신]
       ↓
  [상대 서버: 203.0.113.1:54321에서 온 것으로 인식]

외부 → 내부 (인바운드):

  [외부 노드: 203.0.113.1:54321로 접속 시도]
       ↓
  [공유기 NAT: 매핑 없음 → 차단! ❌]

핵심 문제:
  NAT는 아웃바운드 연결의 응답만 통과시킴
  외부에서 먼저 시작하는 연결은 차단됨
```

---

## 2. NAT 유형 분류 (RFC 3489)

### 2.1 4가지 유형

```
┌─────────────────────────────────────────────────────────┐
│                    NAT 유형 분류                         │
├──────────────┬──────────────────────┬───────────────────┤
│ 유형         │ 매핑 방식            │ 뚫기 난이도       │
├──────────────┼──────────────────────┼───────────────────┤
│ Full Cone    │ 한번 매핑되면        │ ⭐ (쉬움)         │
│              │ 누구든 접근 가능     │                   │
├──────────────┼──────────────────────┼───────────────────┤
│ Restricted   │ 이전에 통신한        │ ⭐⭐ (보통)       │
│ Cone         │ IP만 접근 가능       │                   │
├──────────────┼──────────────────────┼───────────────────┤
│ Port         │ 이전에 통신한        │ ⭐⭐⭐ (어려움)   │
│ Restricted   │ IP+Port만 접근 가능  │                   │
├──────────────┼──────────────────────┼───────────────────┤
│ Symmetric    │ 목적지마다 다른 매핑 │ ⭐⭐⭐⭐ (매우    │
│              │ 예측 불가            │ 어려움)           │
└──────────────┴──────────────────────┴───────────────────┘
```

---

### 2.2 각 유형 상세

**Full Cone NAT:**
```
내부 192.168.0.5:1234 → NAT → 외부 203.0.113.1:5678

매핑이 생기면:
  ✅ 어떤 외부 IP든 203.0.113.1:5678로 접속 가능
  
비유: 문이 한번 열리면 누구든 들어올 수 있음
→ Hole Punching 가장 쉬움
→ 가정용 공유기에 드묾
```

**Restricted Cone NAT:**
```
내부 → 서버 A (1.2.3.4)로 통신

매핑이 생기면:
  ✅ 서버 A (1.2.3.4)의 어떤 포트든 접속 가능
  ❌ 서버 B (5.6.7.8)는 접속 불가

비유: 내가 먼저 말 건 사람만 대답 가능
→ 상대방 IP를 알면 Hole Punching 가능
```

**Port Restricted Cone NAT:**
```
내부 → 서버 A (1.2.3.4:80)로 통신

매핑이 생기면:
  ✅ 서버 A의 정확히 1.2.3.4:80만 접속 가능
  ❌ 서버 A의 1.2.3.4:443은 접속 불가
  ❌ 서버 B는 당연히 불가

비유: 내가 특정 번호로 전화한 상대만 콜백 가능
→ 상대방 IP+Port를 알면 Hole Punching 가능
→ 가정용 공유기에 가장 흔함
```

**Symmetric NAT:**
```
내부 → 서버 A → NAT 매핑: 203.0.113.1:5678
내부 → 서버 B → NAT 매핑: 203.0.113.1:9999 (다른 포트!)

목적지마다 다른 외부 포트 할당
→ STUN으로 알아낸 포트가 다른 피어에겐 무의미
→ Hole Punching 거의 불가능
→ 기업 네트워크, 4G LTE에 흔함
→ Relay가 필요
```

---

### 2.3 유형별 Hole Punching 성공률

```
양쪽 NAT 유형 조합별 성공률:

           │ Full │ Restr │ Port-R │ Symmetric │
  ─────────┼──────┼───────┼────────┼───────────┤
  Full     │ 100% │ 100%  │  100%  │   100%    │
  Restr    │ 100% │ 100%  │  100%  │    ~0%    │
  Port-R   │ 100% │ 100%  │  ~90%  │    ~0%    │
  Symmetric│ 100% │  ~0%  │   ~0%  │    ~0%    │

결론:
  - Symmetric NAT가 끼면 직접 연결 거의 불가능
  - UDP Hole Punching 전체 성공률: 약 82%
  - TCP Hole Punching 전체 성공률: 약 64%
```

---

## 3. NAT Traversal 기법 총정리

### 3.1 기법 비교표

```
┌─────────────────┬──────────┬──────────┬──────────────┬──────────────┐
│ 기법            │ 난이도   │ 성공률   │ 추가 인프라   │ 지연         │
├─────────────────┼──────────┼──────────┼──────────────┼──────────────┤
│ ① UPnP         │ 쉬움     │ ~50%     │ 없음         │ 없음         │
│ ② NAT-PMP/PCP  │ 쉬움     │ ~40%     │ 없음         │ 없음         │
│ ③ STUN         │ 보통     │ ~82%     │ STUN 서버    │ 낮음         │
│ ④ Hole Punching│ 어려움   │ ~82%     │ 시그널 서버  │ 낮음         │
│ ⑤ TURN/Relay   │ 보통     │ ~100%    │ 릴레이 서버  │ 높음         │
│ ⑥ ICE          │ 어려움   │ ~95%     │ STUN+TURN    │ 자동 선택    │
│ ⑦ Tor/I2P      │ 보통     │ ~100%    │ Tor 네트워크 │ 매우 높음    │
└─────────────────┴──────────┴──────────┴──────────────┴──────────────┘
```

---

### 3.2 ① UPnP (Universal Plug and Play)

**원리:**
```
노드가 공유기에게 직접 포트 매핑 요청

과정:
  1. 노드가 로컬 네트워크에서 공유기 발견 (SSDP 프로토콜)
     → 멀티캐스트 239.255.255.250:1900으로 검색
  2. 공유기에게 "외부 포트 9333 → 내부 192.168.0.5:9333" 매핑 요청
  3. 공유기가 수락 → 외부에서 공인IP:9333으로 접속 가능

코드 개념:
  router = upnp_discover()
  router.add_port_mapping(
    protocol="TCP",
    external_port=9333,
    internal_port=9333,
    description="JackpotChain Node"
  )
```

**장점:**
```
✅ 구현 간단
✅ 추가 서버 불필요
✅ 직접 연결 (릴레이 없음)
✅ 포트 포워딩과 동일한 효과
```

**단점:**
```
❌ 공유기가 UPnP 지원해야 함 (지원율 ~50%)
❌ 보안 취약점 다수 발견됨 (miniupnpc 라이브러리)
   → Bitcoin Core v29.0에서 UPnP 지원 제거
❌ 기업 네트워크에서 대부분 비활성화
❌ 이중 NAT (공유기 뒤에 공유기) 시 실패
```

**실제 사용:**
```
Bitcoin Core: v0.x~v28.x까지 UPnP 지원 → v29.0에서 제거
btcd (Go): 여전히 UPnP 지원
libp2p: UPnP를 NAT Traversal 옵션 중 하나로 제공
```

---

### 3.3 ② NAT-PMP / PCP

**NAT-PMP (NAT Port Mapping Protocol):**
```
Apple이 UPnP 대안으로 개발 (RFC 6886)

과정:
  1. 게이트웨이 IP로 직접 요청 (SSDP 검색 불필요)
  2. UDP 패킷으로 포트 매핑 요청
  3. 응답 수신 (성공/실패)

UPnP 대비 장점:
  ✅ 프로토콜 단순 (UDP 기반, 몇 바이트)
  ✅ 공격 표면 작음 (보안 취약점 적음)
  ❌ Apple 기기 위주 지원
```

**PCP (Port Control Protocol):**
```
NAT-PMP의 후속 표준 (RFC 6887)

추가 기능:
  ✅ IPv6 핀홀링 지원
  ✅ 서드파티 매핑 (다른 기기 대신 매핑)
  ✅ NAT-PMP 하위 호환

Bitcoin Core v29.0 전략:
  PCP 먼저 시도 → 실패 시 NAT-PMP 폴백
  → UPnP 완전 제거, PCP/NAT-PMP로 대체
  → 자체 구현 (외부 라이브러리 의존 제거)
```

**코드 개념:**
```
def setup_port_mapping():
    # 1차: PCP 시도
    result = try_pcp(gateway_ip, external_port=9333)
    
    if result.success:
        return result
    
    # 2차: NAT-PMP 폴백
    result = try_natpmp(gateway_ip, external_port=9333)
    
    if result.success:
        return result
    
    # 실패: 다른 기법으로 넘어감
    return None
```

---

### 3.4 ③ STUN (Session Traversal Utilities for NAT)

**원리:**
```
"내 공인 IP:Port가 뭔지 외부 서버한테 물어보기" (RFC 5389)

과정:
  1. 노드 → STUN 서버: "내가 어떻게 보이나요?"
  2. STUN 서버 → 노드: "당신은 203.0.113.1:54321로 보입니다"
  3. 노드가 이 정보를 다른 피어에게 전달
  4. 피어가 203.0.113.1:54321로 접속 시도

시각화:
  Node A (192.168.0.5:1234)
    ↓ "내 공인 주소?"
  [STUN Server]
    ↓ "203.0.113.1:54321"
  Node A: "아, 나는 203.0.113.1:54321이구나"
    ↓ 이 정보를 Node B에게 전달
  Node B → 203.0.113.1:54321로 접속
```

**NAT 유형 감지:**
```
STUN은 NAT 유형도 알려줌:

방법:
  1. 서버 IP-1, Port-1으로 요청 → 매핑 A 확인
  2. 서버 IP-1, Port-2로 요청 → 매핑 B 확인
  3. 서버 IP-2, Port-1으로 요청 → 매핑 C 확인

판단:
  A == B == C → Full Cone
  A == B != C → Symmetric
  A != B      → Restricted/Port Restricted
```

**한계:**
```
❌ Symmetric NAT에서는 무용지물
   (STUN으로 알아낸 포트가 다른 피어에겐 다름)
❌ STUN 서버 운영 필요 (공개 서버 존재하긴 함)
```

---

### 3.5 ④ UDP/TCP Hole Punching

**핵심 아이디어:**
```
양쪽 노드가 동시에 서로에게 패킷을 보내면
NAT에 "구멍"이 뚫림

비유:
  A의 NAT: "A가 B에게 보냈으니 B의 응답은 통과시키자"
  B의 NAT: "B가 A에게 보냈으니 A의 응답은 통과시키자"
  → 양쪽 다 통과! ✅
```

**UDP Hole Punching 과정:**
```
사전 조건: 시그널링 서버 S 필요 (피어 정보 교환용)

Step 1: 양쪽이 S에 등록
  A → S: "나는 192.168.0.5:1234, 공인 203.0.113.1:54321"
  B → S: "나는 192.168.1.10:5678, 공인 198.51.100.2:12345"

Step 2: S가 상대 정보 전달
  S → A: "B는 198.51.100.2:12345"
  S → B: "A는 203.0.113.1:54321"

Step 3: 동시에 패킷 전송
  A → 198.51.100.2:12345 (B의 NAT에 도달, 처음엔 차단될 수 있음)
  B → 203.0.113.1:54321 (A의 NAT에 도달, 처음엔 차단될 수 있음)

Step 4: NAT 매핑 생성
  A의 NAT: "A가 198.51.100.2:12345에 보냈음" → 매핑 생성
  B의 NAT: "B가 203.0.113.1:54321에 보냈음" → 매핑 생성

Step 5: 양방향 통신 성립
  A ↔ B 직접 통신 가능! ✅

타이밍이 핵심:
  양쪽이 거의 동시에 보내야 성공률 높음
  → 시그널링 서버가 "지금!" 신호를 보냄
```

**TCP Hole Punching:**
```
UDP보다 어려움 (TCP는 연결 지향적)

방법: Simultaneous TCP Open
  A: connect(B의 공인 주소)
  B: connect(A의 공인 주소)
  → 양쪽 SYN이 교차하면 연결 성립

문제:
  - OS마다 동작 다름 (일부 Windows 버전 미지원)
  - 성공률 ~64% (UDP ~82%보다 낮음)
  - 타이밍 더 까다로움

대안:
  UDP로 Hole Punching → 그 위에 QUIC 프로토콜 사용
  QUIC = UDP 기반 + TCP의 신뢰성
```

---

### 3.6 ⑤ TURN / Relay

**원리:**
```
직접 연결 불가능할 때 → 중간 서버가 트래픽 중계 (RFC 5766)

A ←→ [Relay Server] ←→ B

Hole Punching 실패 시 최후의 수단
```

**과정:**
```
Step 1: A가 TURN 서버에 릴레이 주소 할당 요청
  A → TURN: "릴레이 주소 하나 주세요"
  TURN → A: "203.0.113.100:9999를 쓰세요"

Step 2: B도 TURN 서버에 연결
  B → TURN: 연결

Step 3: A의 트래픽이 TURN을 경유
  A → TURN(203.0.113.100:9999) → B
  B → TURN → A
```

**장점:**
```
✅ 100% 성공률 (어떤 NAT든 통과)
✅ Symmetric NAT도 가능
```

**단점:**
```
❌ 모든 트래픽이 릴레이 경유 → 지연 증가
❌ 릴레이 서버 대역폭 비용 발생
❌ 중앙화 요소 (릴레이 서버 의존)
❌ 블록체인에서 전체 블록 데이터를 릴레이하면 부담 큼
```

**블록체인에서의 활용:**
```
libp2p의 Circuit Relay:
  - 이미 연결된 피어가 릴레이 역할
  - 전용 서버 불필요 (피어가 자발적으로 중계)
  - 암호화되어 릴레이가 내용 못 봄
  
  A ←→ [Peer C (릴레이)] ←→ B
  
  장점:
    탈중앙화 릴레이 (특정 서버 의존 ✕)
  단점:
    릴레이 피어의 대역폭 소모
    릴레이 피어가 오프라인되면 연결 끊김
```

---

### 3.7 ⑥ ICE (Interactive Connectivity Establishment)

**원리:**
```
STUN + TURN + Hole Punching을 조합한 프레임워크 (RFC 8445)
"가능한 모든 방법을 시도하고, 최적의 경로를 선택"

WebRTC가 사용하는 표준 방식
```

**과정:**
```
Step 1: 후보(Candidate) 수집
  - Host Candidate: 로컬 IP (192.168.0.5:1234)
  - Server Reflexive: STUN으로 알아낸 공인 IP (203.0.113.1:54321)
  - Relay Candidate: TURN 릴레이 주소 (203.0.113.100:9999)

Step 2: 후보 교환
  시그널링 서버를 통해 양쪽 후보 목록 교환

Step 3: 연결성 검사 (Connectivity Check)
  모든 후보 쌍을 동시에 테스트
  
  우선순위:
    1순위: Host ↔ Host (같은 네트워크면 직접)
    2순위: Server Reflexive ↔ Server Reflexive (Hole Punching)
    3순위: Relay ↔ Relay (최후의 수단)

Step 4: 최적 경로 선택
  가장 낮은 지연의 성공한 후보 쌍 사용
```

**장점:**
```
✅ 가장 높은 성공률 (~95%)
✅ 자동으로 최적 경로 선택
✅ 표준화됨 (RFC)
✅ 다양한 NAT 조합에 대응
```

**단점:**
```
❌ 구현 복잡도 높음
❌ STUN + TURN 서버 모두 필요
❌ 연결 수립 시간 길 수 있음 (여러 후보 테스트)
```

---

### 3.8 ⑦ Tor / I2P (오버레이 네트워크)

**Tor Hidden Service (Onion Service):**
```
원리:
  - 노드가 Tor 네트워크에 .onion 주소를 등록
  - NAT 뒤에 있어도 .onion 주소로 접근 가능
  - 모든 트래픽이 Tor 릴레이를 경유

과정:
  1. 노드가 Tor 회로(3홉) 구성
  2. 랜데부 포인트에서 피어와 만남
  3. 6홉 경로로 통신 (3홉 × 2)

Bitcoin Core의 Tor 지원:
  - v22.0부터 Tor v3 전용
  - -listenonion=1 옵션으로 자동 .onion 주소 생성
  - NAT 뒤에서도 인바운드 연결 수락 가능
  - IP 주소 노출 없이 노드 운영 (프라이버시)
```

**I2P (Invisible Internet Project):**
```
원리:
  - Tor의 탈중앙화 버전 (Garlic Routing)
  - DHT 기반 피어 발견
  - 단방향 터널 사용 (Tor보다 보안 강화)

Bitcoin Core:
  - v22.0부터 I2P 지원 추가
  - -i2psam=127.0.0.1:7656 옵션
```

**장점:**
```
✅ NAT 100% 우회
✅ IP 주소 완전 은닉 (프라이버시 극대화)
✅ 검열 저항성
✅ 별도 포트 포워딩 불필요
```

**단점:**
```
❌ 지연 매우 높음 (Tor: 6홉, 수백ms~수초)
❌ 대역폭 제한 (블록 동기화 느림)
❌ 블록체인 전체 데이터를 Tor로 전송하면 비효율적
❌ Tor 네트워크 자체에 의존 (Tor 다운 시 접속 불가)
❌ Sybil 공격에 취약할 수 있음 (Eclipse Attack)
```

**블록체인 적용 전략:**
```
추천: 하이브리드 운영

  Clearnet (일반 인터넷): 블록 동기화, 성능 우선
  Tor/I2P: 프라이버시가 중요한 TX 전파

Bitcoin Core 기본 설정:
  clearnet + Tor 동시 연결
  → 네트워크 파티셔닝 방지
  → 프라이버시와 성능 균형
```

---

## 4. 실제 블록체인 프로젝트의 선택

### 4.1 Bitcoin Core

```
역사적 변천:
  v0.x ~ v28.x: UPnP 지원 (miniupnpc 라이브러리)
                → 보안 취약점 다수 발견
                → 기본값 OFF로 변경

  v22.0:        NAT-PMP 추가 (libnatpmp)
                Tor v3, I2P 지원 추가

  v29.0:        UPnP 완전 제거
                PCP + NAT-PMP 자체 구현
                외부 라이브러리 의존 제거

현재 전략 (v29.0+):
  1순위: PCP (Port Control Protocol)
  2순위: NAT-PMP (PCP 실패 시 폴백)
  3순위: Tor Onion Service (NAT 완전 우회)
  4순위: 수동 포트 포워딩 (사용자 설정)

설정:
  bitcoind -natpmp         # PCP/NAT-PMP 활성화
  bitcoind -listenonion=1  # Tor 자동 설정
```

---

### 4.2 Ethereum / libp2p 기반 체인

```
Ethereum 2.0 (Beacon Chain):
  libp2p 네트워킹 스택 사용

libp2p의 NAT Traversal 전략:
  1. AutoNAT: 자동 NAT 감지
     → 다른 피어에게 "내가 접근 가능한지" 확인 요청
  
  2. UPnP: 공유기 포트 매핑 시도
  
  3. Hole Punching: DCUtR 프로토콜
     → Direct Connection Upgrade through Relay
     → 먼저 릴레이로 연결 → Hole Punching 시도 → 성공 시 직접 연결로 전환
  
  4. Circuit Relay: 최후의 수단
     → 다른 피어가 릴레이 역할
     → 탈중앙화 (전용 서버 불필요)

discv5 (피어 발견 프로토콜):
  → UDP 기반
  → Hole Punching 제안 (WIP)
  → Rendezvous 프로토콜로 NAT 뒤 노드 연결
```

---

### 4.3 Filecoin / IPFS

```
libp2p 전체 스택 사용:
  - Kademlia DHT: 피어 발견
  - GossipSub: 메시지 전파
  - AutoRelay: 자동 릴레이 선택
  - Hole Punching: DCUtR

특이점:
  대용량 파일 전송이 많음
  → Relay 의존 시 비용 폭증
  → Hole Punching 성공률이 중요
```

---

## 5. JackpotChain 전략 수립

### 5.1 요구사항 분석

```
JackpotChain 특성:
  - 블록 타임: 15초 (빠른 전파 필요)
  - 블록 크기: 최대 1MB
  - TPS: ~33
  - 팀 규모: 6명 / 6주
  - 언어: Python → Go

NAT Traversal 요구사항:
  ✅ 최대한 많은 노드가 인바운드 가능해야 함 (탈중앙화)
  ✅ 15초 블록 타임 → 빠른 전파 필수 → 지연 최소화
  ✅ 구현 난이도 적절해야 함 (6주 제약)
  ✅ 외부 인프라 최소화 (별도 TURN 서버 운영 부담)
```

---

### 5.2 단계별 전략 (추천)

```
Phase 1 (MVP): 기본 연결
  ─────────────────────────────
  ✅ PCP / NAT-PMP 자동 포트 매핑
  ✅ 시드 노드(Seed Node) 하드코딩
  ✅ 수동 피어 추가 (-addnode 옵션)
  
  구현 난이도: 낮음
  이유: Bitcoin Core v29.0과 같은 전략
        PCP/NAT-PMP는 프로토콜이 단순

Phase 2 (확장): Hole Punching
  ─────────────────────────────
  ✅ STUN으로 NAT 유형 감지 + 공인 주소 확인
  ✅ UDP Hole Punching
  ✅ 시그널링 서버 (시드 노드가 겸임)
  
  구현 난이도: 중간
  이유: STUN은 프로토콜 단순, 공개 서버 사용 가능
        Hole Punching은 블록체인 핵심 기능

Phase 3 (프로덕션): 풀 스택
  ─────────────────────────────
  ✅ Tor Onion Service 지원
  ✅ Circuit Relay (피어 기반 릴레이)
  ✅ AutoNAT (자동 도달성 감지)
  ✅ QUIC 전송 프로토콜
  
  구현 난이도: 높음
  이유: 프라이버시 + 100% 연결 보장
```

---

### 5.3 Phase 1 구현 스케치

```python
# config.py
P2P_PORT = 9333
RPC_PORT = 9332
SEED_NODES = [
    "seed1.jackpotchain.io:9333",
    "seed2.jackpotchain.io:9333",
]

# nat.py
class NATManager:
    def __init__(self, internal_port):
        self.internal_port = internal_port
        self.external_ip = None
        self.external_port = None
        self.method = None
    
    def setup(self):
        """NAT 포트 매핑 시도 (PCP → NAT-PMP 순서)"""
        
        gateway = self._find_gateway()
        
        # 1차: PCP 시도
        result = self._try_pcp(gateway)
        if result:
            self.method = "PCP"
            return True
        
        # 2차: NAT-PMP 시도
        result = self._try_natpmp(gateway)
        if result:
            self.method = "NAT-PMP"
            return True
        
        # 실패: 아웃바운드만 가능
        print("⚠️ NAT 포트 매핑 실패. 인바운드 연결 불가.")
        print("   수동 포트 포워딩을 설정하거나,")
        print("   아웃바운드 연결만 사용합니다.")
        return False
    
    def _find_gateway(self):
        """기본 게이트웨이 IP 찾기"""
        # Linux: ip route | grep default
        # 또는 소켓으로 외부 연결 시 게이트웨이 확인
        ...
    
    def _try_pcp(self, gateway):
        """PCP 프로토콜로 포트 매핑"""
        # UDP 패킷을 gateway:5351로 전송
        # MAP 요청: 내부 포트 → 외부 포트 매핑
        ...
    
    def _try_natpmp(self, gateway):
        """NAT-PMP 프로토콜로 포트 매핑"""
        # UDP 패킷을 gateway:5351로 전송
        # 공인 IP 조회 + 포트 매핑 요청
        ...
    
    def teardown(self):
        """프로그램 종료 시 매핑 해제"""
        ...


# node.py
class Node:
    def __init__(self):
        self.nat = NATManager(P2P_PORT)
        self.server = None
    
    def start(self):
        # 1. NAT 설정
        nat_success = self.nat.setup()
        
        # 2. P2P 리스너 시작
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(("0.0.0.0", P2P_PORT))
        self.server.listen(128)
        
        if nat_success:
            print(f"✅ 인바운드 활성: {self.nat.external_ip}:{self.nat.external_port}")
            print(f"   방식: {self.nat.method}")
        
        # 3. 시드 노드에 연결
        for seed in SEED_NODES:
            self.connect_to_peer(seed)
        
        # 4. 수신 루프
        self.accept_loop()
    
    def stop(self):
        self.nat.teardown()
        self.server.close()
```

---

## 6. 심화: QUIC 프로토콜

### 6.1 왜 QUIC인가?

```
기존 블록체인: TCP 사용
문제:
  - TCP Hole Punching 성공률 낮음 (~64%)
  - TCP 핸드셰이크 오버헤드 (3-way → 지연)
  - Head-of-line blocking (멀티플렉싱 비효율)

QUIC 장점:
  ✅ UDP 기반 → Hole Punching 성공률 높음 (~82%)
  ✅ 0-RTT 연결 가능 (재연결 시)
  ✅ 스트림 멀티플렉싱 (하나 막혀도 다른 스트림 영향 없음)
  ✅ 내장 암호화 (TLS 1.3)
  ✅ 연결 마이그레이션 (IP 변경 시 연결 유지)

블록체인 적합성:
  - 블록 전파 + TX 전파를 별도 스트림으로
  - NAT 뒤에서 UDP Hole Punching 후 QUIC 사용
  - Tailscale, libp2p 등이 이미 채택
```

---

### 6.2 libp2p의 접근

```
libp2p 전략 (DCUtR = Direct Connection Upgrade through Relay):

  1. 먼저 Relay로 연결 (100% 성공)
  2. Relay 경유로 Hole Punching 조율
  3. Hole Punching 성공 → 직접 연결로 업그레이드
  4. 실패 → Relay 유지

장점:
  - "일단 연결, 나중에 최적화"
  - 사용자는 연결 방식을 신경 쓸 필요 없음
  - 점진적 개선

Go 구현 참고:
  go-libp2p에 전체 구현 있음
  JackpotChain Go 전환 시 libp2p 채택 고려
```

---

## 7. 보안 고려사항

### 7.1 NAT Traversal 관련 공격

```
Eclipse Attack:
  - 악의적 노드가 타겟의 모든 연결을 장악
  - NAT 뒤 노드는 아웃바운드만 가능 → 더 취약
  - 대응: 다양한 네트워크(clearnet + Tor)로 연결

UPnP 취약점:
  - 인증 없이 포트 매핑 가능
  - 악성 소프트웨어가 포트를 열 수 있음
  - 대응: PCP/NAT-PMP로 전환 (Bitcoin Core 방식)

릴레이 MITM:
  - 릴레이 노드가 트래픽 감시/변조
  - 대응: 엔드투엔드 암호화 (피어 간 직접 암호화)

시그널링 서버 공격:
  - STUN/시그널링 서버가 잘못된 주소 전달
  - 대응: 여러 서버 교차 검증, 피어 인증
```

---

### 7.2 방어 전략

```
JackpotChain 권장:

1. 피어 다양성 유지
   - 최소 8개 아웃바운드 연결
   - 가능하면 인바운드도 수락
   - 서로 다른 AS(자율시스템)의 피어 선호

2. 연결 인증
   - 피어 ID = 공개키 해시
   - 모든 통신 암호화 (Noise Protocol 또는 TLS)
   - 릴레이가 내용을 볼 수 없게

3. NAT 상태 모니터링
   - 주기적으로 매핑 갱신 (TTL 관리)
   - 매핑 해제 감지 → 재설정
   - 외부 도달성 자가 테스트 (AutoNAT 방식)
```

---

## 8. 핵심 요약

### 기법 선택 가이드

```
"일단 연결만 되면 돼" (개발/테스트)
  → 시드 노드 + 수동 연결

"가정용 공유기에서 노드 돌리고 싶어"
  → PCP/NAT-PMP + Hole Punching

"어떤 네트워크든 무조건 연결돼야 해"
  → ICE (STUN + TURN) 또는 Tor

"프라이버시도 중요해"
  → Tor Onion Service + Clearnet 하이브리드

"6주 안에 만들어야 해" (JackpotChain MVP)
  → PCP/NAT-PMP + 시드 노드
  → Phase 2에서 STUN + Hole Punching 추가
```

### 블록체인 업계 트렌드

```
과거: UPnP 위주 (보안 취약)
현재: PCP/NAT-PMP + Tor (Bitcoin Core v29.0)
미래: libp2p (Hole Punching + Relay + QUIC)

핵심:
  하나의 기법에 의존하지 않고
  여러 기법을 계층적으로 조합하는 것이 정답
```

---

## 9. 체크리스트

이해했는지 확인:

- [ ] NAT가 인바운드 연결을 차단하는 원리
- [ ] NAT 4가지 유형의 차이 (Full Cone ~ Symmetric)
- [ ] UPnP가 왜 보안 문제가 있는지
- [ ] PCP/NAT-PMP가 UPnP를 대체한 이유
- [ ] STUN이 공인 주소를 알아내는 과정
- [ ] Hole Punching의 "동시 전송" 원리
- [ ] Relay가 최후의 수단인 이유
- [ ] ICE가 여러 기법을 조합하는 방식
- [ ] Tor가 NAT를 100% 우회하는 원리
- [ ] Bitcoin Core v29.0의 NAT 전략

---

## 10. 참고 자료

**표준 문서:**
- RFC 5389: STUN
- RFC 5766: TURN
- RFC 8445: ICE
- RFC 6886: NAT-PMP
- RFC 6887: PCP

**블록체인 구현:**
- Bitcoin Core NAT 관련 PR: #30043 (PCP), #31130 (UPnP 제거)
- btcd upnp.go (Go 구현 참고)
- libp2p NAT Traversal 문서: docs.libp2p.io/concepts/nat/
- Ethereum devp2p: github.com/ethereum/devp2p

**학습 자료:**
- Tailscale 블로그: "How NAT traversal works"
- Bryan Ford 논문: "Peer-to-Peer Communication Across NATs"

---

**이전:** [05. 트랜잭션 심화](05-transactions-deep-dive.md)  
**다음:** P2P 네트워크 프로토콜 →
