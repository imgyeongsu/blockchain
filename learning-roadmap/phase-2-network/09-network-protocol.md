# 09. 네트워크 프로토콜 (Network Protocol)

> **Phase 2: Network**  
> **학습 날짜:** 2025-02-19  
> **난이도:** ⭐⭐⭐☆☆  
> **예상 소요 시간:** 2-3시간  
> **선행 학습:** [08. P2P 네트워크 기초](08-p2p-basics.md)

---

## 🎯 학습 목표

이 문서를 완료하면:
- [ ] 메시지 프레임 구조를 설계할 수 있다
- [ ] JackpotChain의 메시지 타입 전체를 이해한다
- [ ] 핸드셰이크 과정을 단계별로 설명할 수 있다
- [ ] 데이터 직렬화/역직렬화 방식을 안다
- [ ] 블록/TX 전파 프로토콜 (INV/GETDATA)을 이해한다
- [ ] Mempool 동기화 방법을 안다
- [ ] 프로토콜 버전 관리와 호환성을 이해한다

---

## 1. 왜 프로토콜이 필요한가?

### 1.1 문제

**비유: 외국어 회화**
```
Alice (한국어) ↔ Bob (영어)

규칙 없이 대화:
  Alice: "블록 줘"
  Bob: "???"

규칙 있으면:
  Alice: {"type": "getblock", "hash": "0000abc..."}
  Bob: {"type": "block", "data": ...}
  
→ 서로 이해 가능!
```

**P2P 네트워크 문제:**
```
노드 A ←TCP→ 노드 B

문제 1: 메시지 경계
  TCP는 바이트 스트림
  → 어디서부터 어디까지가 한 메시지?
  
문제 2: 메시지 타입
  블록 요청? TX 전파? 핑?
  → 어떤 종류인지 구분?

문제 3: 무결성
  전송 중 데이터 깨짐
  → 올바른 데이터인지 확인?

문제 4: 호환성
  노드 버전이 다름
  → 서로 소통 가능?
```

---

### 1.2 해결: 네트워크 프로토콜

```
프로토콜 = 통신 규약

정의:
  1. 메시지 형식 (어떻게 생겼나)
  2. 메시지 타입 (무슨 종류가 있나)
  3. 교환 순서 (누가 먼저?)
  4. 에러 처리 (문제 시?)

Bitcoin 참고:
  - Bitcoin Protocol (P2P)
  - 포트 8333
  - Magic Bytes로 네트워크 구분
```

---

## 2. 메시지 프레임 (Message Frame)

### 2.1 왜 프레임이 필요한가?

**TCP 스트림 문제:**
```
TCP가 보내는 것:
  [bytes bytes bytes bytes bytes bytes bytes bytes...]
  
어디가 메시지 경계?
  [msg1???|msg2????|msg3??????]
  
→ 프레임으로 감싸서 해결!
```

---

### 2.2 JackpotChain 메시지 프레임

```
Message Frame:

┌──────────────────────────────────────────────┐
│ magic       (4 bytes)  │ 네트워크 식별       │
├──────────────────────────────────────────────┤
│ command     (12 bytes) │ 메시지 타입          │
├──────────────────────────────────────────────┤
│ length      (4 bytes)  │ 페이로드 길이        │
├──────────────────────────────────────────────┤
│ checksum    (4 bytes)  │ 페이로드 체크섬      │
├──────────────────────────────────────────────┤
│ payload     (가변)     │ 실제 데이터          │
└──────────────────────────────────────────────┘

헤더 크기: 4 + 12 + 4 + 4 = 24 bytes
총 크기: 24 + payload_length
```

---

### 2.3 각 필드 상세

#### 1. magic (4 bytes)

```
목적: 네트워크 구분 + 메시지 시작점 탐색

JackpotChain:
  메인넷: 0x4A 0x41 0x43 0x4B ("JACK" in ASCII)
  테스트넷: 0x4A 0x54 0x53 0x54 ("JTST" in ASCII)

Bitcoin 참고:
  메인넷: 0xF9BEB4D9
  테스트넷: 0x0B110907

용도:
  1. 메시지 시작점 찾기 (동기화)
  2. 잘못된 네트워크 연결 감지
  3. 데이터 스트림 복구

예:
  바이트 스트림에서 0x4A414B 발견
  → "JACK 메인넷 메시지 시작!"
```

---

#### 2. command (12 bytes)

```
목적: 메시지 종류 식별
형식: ASCII 문자열, 남은 바이트는 0x00으로 채움

예:
  "version\x00\x00\x00\x00\x00"  (12 bytes)
  "verack\x00\x00\x00\x00\x00\x00" (12 bytes)
  "inv\x00\x00\x00\x00\x00\x00\x00\x00\x00" (12 bytes)
  "tx\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" (12 bytes)
  "block\x00\x00\x00\x00\x00\x00\x00" (12 bytes)
```

---

#### 3. length (4 bytes)

```
목적: 페이로드 크기 (bytes)
형식: Little-endian uint32

예:
  페이로드 256 bytes → 0x00010000
  페이로드 0 bytes → 0x00000000 (verack 등)

제한:
  최대 4 MB (JackpotChain)
  → 4,000,000 bytes 초과 시 거부
```

---

#### 4. checksum (4 bytes)

```
목적: 페이로드 무결성 확인
계산: SHA-256(SHA-256(payload))의 처음 4 bytes

예:
  payload = [0x01, 0x02, 0x03]
  hash1 = SHA-256(payload)
  hash2 = SHA-256(hash1)
  checksum = hash2[0:4]

검증:
  수신 측에서 동일하게 계산
  → 일치하면 유효 ✅
  → 불일치면 버림 ❌

페이로드 없을 때:
  SHA-256(SHA-256("")) = 0x5DF6E0E2...
  checksum = 0x5DF6E0E2
```

---

### 2.4 메시지 파싱 의사코드

```python
class MessageFrame:
    MAGIC_MAINNET = b'\x4A\x41\x43\x4B'  # "JACK"
    MAGIC_TESTNET = b'\x4A\x54\x53\x54'  # "JTST"
    HEADER_SIZE = 24
    MAX_PAYLOAD = 4 * 1024 * 1024  # 4 MB
    
    def __init__(self, command, payload, network="mainnet"):
        self.magic = self.MAGIC_MAINNET if network == "mainnet" else self.MAGIC_TESTNET
        self.command = command
        self.payload = payload
        self.length = len(payload)
        self.checksum = self._compute_checksum(payload)
    
    @staticmethod
    def _compute_checksum(data):
        """Double SHA-256의 처음 4 bytes"""
        hash1 = sha256(data)
        hash2 = sha256(hash1)
        return hash2[:4]
    
    def serialize(self):
        """메시지를 바이트로 직렬화"""
        header = b''
        header += self.magic                            # 4 bytes
        header += self.command.ljust(12, '\x00').encode() # 12 bytes
        header += struct.pack('<I', self.length)         # 4 bytes LE
        header += self.checksum                          # 4 bytes
        return header + self.payload
    
    @classmethod
    def deserialize(cls, stream):
        """바이트 스트림에서 메시지 파싱"""
        # 1. magic 확인
        magic = stream.read(4)
        if magic not in (cls.MAGIC_MAINNET, cls.MAGIC_TESTNET):
            raise ProtocolError("잘못된 매직 바이트")
        
        # 2. command 읽기
        command = stream.read(12).rstrip(b'\x00').decode()
        
        # 3. length 읽기
        length = struct.unpack('<I', stream.read(4))[0]
        if length > cls.MAX_PAYLOAD:
            raise ProtocolError(f"페이로드 초과: {length}")
        
        # 4. checksum 읽기
        checksum = stream.read(4)
        
        # 5. payload 읽기
        payload = stream.read(length)
        
        # 6. checksum 검증
        expected = cls._compute_checksum(payload)
        if checksum != expected:
            raise ProtocolError("체크섬 불일치")
        
        return cls(command, payload)
```

---

### 2.5 스트림 동기화 (Sync)

**문제: 연결 중간에 바이트 유실**
```
전송: [JACK][msg1][JACK][msg2]
수신: [JA??][msg1][JACK][msg2]
        ↑ 깨짐!
```

**해결: Magic 바이트 스캔**
```python
def find_next_message(stream):
    """다음 유효한 메시지 시작점 찾기"""
    buffer = b''
    
    while True:
        byte = stream.read(1)
        buffer += byte
        
        # 버퍼 끝에서 magic 확인
        if buffer[-4:] == MAGIC_MAINNET:
            # 메시지 시작점 발견!
            return parse_message(stream)
        
        # 버퍼 크기 제한
        if len(buffer) > 1024:
            buffer = buffer[-4:]  # 최근 4바이트만 유지
```

---

## 3. 메시지 타입 (Message Types)

### 3.1 전체 메시지 목록

```
=== 연결 관리 ===
version    : 핸드셰이크 (내 정보 알려줌)
verack     : 핸드셰이크 응답 (알겠다)
ping       : 연결 확인
pong       : 핑 응답
reject     : 메시지 거부 (에러)

=== 데이터 교환 ===
inv        : "이런 데이터 있어" (목록 알림)
getdata    : "이 데이터 줘" (요청)
notfound   : "그 데이터 없어" (응답)

=== 블록 관련 ===
block      : 블록 데이터
getblocks  : 블록 해시 목록 요청
getheaders : 블록 헤더 목록 요청
headers    : 블록 헤더 목록 응답

=== 트랜잭션 관련 ===
tx         : 트랜잭션 데이터
mempool    : Mempool 내역 요청

=== 피어 관련 ===
getaddr    : 다른 노드 주소 요청
addr       : 노드 주소 목록 응답
```

---

### 3.2 분류

```
카테고리 1: 연결 관리
  목적: 연결 수립/유지
  빈도: 적음 (연결 시, 주기적)
  ┌──────────┬────────────────────┐
  │ version  │ 최초 연결 시 1회    │
  │ verack   │ version 응답 1회    │
  │ ping     │ 60초마다            │
  │ pong     │ ping 응답           │
  │ reject   │ 에러 시             │
  └──────────┴────────────────────┘

카테고리 2: 데이터 발견 (Discovery)
  목적: "뭐가 있는지" 알림/요청
  빈도: 매우 높음
  ┌──────────┬────────────────────┐
  │ inv      │ 새 블록/TX 알림     │
  │ getdata  │ 데이터 요청         │
  │ notfound │ 데이터 없음 응답    │
  └──────────┴────────────────────┘

카테고리 3: 데이터 전달 (Delivery)
  목적: 실제 데이터 전송
  빈도: 높음
  ┌──────────┬────────────────────┐
  │ block    │ 블록 전체 데이터    │
  │ tx       │ TX 전체 데이터      │
  │ headers  │ 블록 헤더 목록      │
  └──────────┴────────────────────┘

카테고리 4: 동기화 (Sync)
  목적: 체인 따라잡기
  빈도: 연결 초기에 집중
  ┌──────────┬────────────────────┐
  │ getblocks│ 블록 해시 목록 요청 │
  │getheaders│ 블록 헤더 목록 요청 │
  │ mempool  │ Mempool TX 목록    │
  └──────────┴────────────────────┘

카테고리 5: 피어 관리
  목적: 네트워크 발견
  빈도: 적음
  ┌──────────┬────────────────────┐
  │ getaddr  │ 피어 주소 요청      │
  │ addr     │ 피어 주소 응답      │
  └──────────┴────────────────────┘
```

---

## 4. 핸드셰이크 (Handshake)

### 4.1 왜 필요한가?

```
두 노드가 처음 만났을 때:
  1. 서로 누구인지 확인 (버전, 체인 높이)
  2. 같은 네트워크인지 확인 (메인넷? 테스트넷?)
  3. 호환 가능한지 확인 (프로토콜 버전)
  4. 시간 동기화 (timestamp)
```

---

### 4.2 핸드셰이크 과정

```
Node A (연결 시도)              Node B (연결 수락)
     │                              │
     │ ─── TCP SYN ───────────────→ │  TCP 연결
     │ ←── TCP SYN+ACK ─────────── │
     │ ─── TCP ACK ───────────────→ │
     │                              │
     │ ─── version ───────────────→ │  ① A가 자기 정보
     │ ←── version ─────────────── │  ② B도 자기 정보
     │ ←── verack ──────────────── │  ③ B가 A 수락
     │ ─── verack ────────────────→ │  ④ A가 B 수락
     │                              │
     │    === 핸드셰이크 완료 ===     │
     │                              │
     │ ─── getaddr ───────────────→ │  ⑤ 피어 목록 요청
     │ ←── addr ────────────────── │  ⑥ 피어 목록 응답
     │                              │
     │ ─── getheaders ────────────→ │  ⑦ 체인 동기화 시작
     │ ←── headers ─────────────── │
     │                              │
```

---

### 4.3 version 메시지 구조

```
Version Payload:

┌──────────────────────────────────┐
│ protocol_version  (4 bytes)      │  프로토콜 버전
├──────────────────────────────────┤
│ services          (8 bytes)      │  지원 서비스 비트
├──────────────────────────────────┤
│ timestamp         (8 bytes)      │  현재 시간
├──────────────────────────────────┤
│ addr_recv         (26 bytes)     │  상대 노드 주소
├──────────────────────────────────┤
│ addr_from         (26 bytes)     │  내 주소
├──────────────────────────────────┤
│ nonce             (8 bytes)      │  자기 연결 감지용
├──────────────────────────────────┤
│ user_agent        (가변)         │  소프트웨어 이름
├──────────────────────────────────┤
│ start_height      (4 bytes)      │  내 체인 높이
├──────────────────────────────────┤
│ relay             (1 byte)       │  TX 릴레이 여부
└──────────────────────────────────┘
```

---

### 4.4 각 필드 설명

```
protocol_version (4 bytes):
  현재: 70015 (JackpotChain v1)
  → 호환성 확인에 사용
  → 상대가 너무 낮으면 연결 거부

services (8 bytes):
  비트 플래그로 지원 기능 표시
  
  0x01: NODE_NETWORK (Full Node)
  0x02: NODE_BLOOM (블룸 필터 지원)
  0x04: NODE_MINING (채굴 노드)
  0x08: NODE_MULTIASSET (멀티에셋 지원)
  
  예:
    0x0000000000000001 → Full Node
    0x0000000000000005 → Full Node + Mining
    0x0000000000000009 → Full Node + MultiAsset

timestamp (8 bytes):
  Unix timestamp (초)
  → 시간 차이 ±2시간 이내인지 확인
  → 너무 다르면 경고

nonce (8 bytes):
  랜덤 값
  → 자기 자신에게 연결되는 것 감지
  → 내가 보낸 nonce가 돌아오면 = 자기 연결!

user_agent (가변):
  "/JackpotChain:1.0.0/"
  → 소프트웨어 식별
  → 디버깅에 유용

start_height (4 bytes):
  내가 가진 가장 높은 블록
  → 상대가 내보다 높으면 동기화 필요
  → 상대가 내보다 낮으면 내가 도와줄 수 있음

relay (1 byte):
  0x01: TX를 릴레이해 달라
  0x00: TX 릴레이 안 해도 됨 (SPV)
```

---

### 4.5 version 핸들링 의사코드

```python
class PeerConnection:
    def __init__(self, socket):
        self.socket = socket
        self.version_sent = False
        self.version_received = False
        self.verack_sent = False
        self.verack_received = False
        self.handshake_complete = False
    
    def initiate_handshake(self):
        """연결을 시도한 쪽이 호출"""
        version_msg = self._build_version()
        self.send(version_msg)
        self.version_sent = True
    
    def handle_version(self, msg):
        """version 메시지 수신 처리"""
        peer_version = msg.protocol_version
        peer_height = msg.start_height
        peer_services = msg.services
        
        # 1. 프로토콜 버전 확인
        if peer_version < MIN_PROTOCOL_VERSION:
            self.send_reject("version", "protocol too old")
            self.disconnect()
            return
        
        # 2. 같은 네트워크 확인 (magic으로 이미 확인됨)
        
        # 3. 자기 자신 연결 감지
        if msg.nonce == my_nonce:
            self.disconnect()  # 자기 자신!
            return
        
        # 4. 시간 차이 확인
        time_diff = abs(msg.timestamp - time.time())
        if time_diff > 7200:  # 2시간
            print(f"경고: 피어 시간 차이 {time_diff}초")
        
        # 5. 피어 정보 저장
        self.peer_version = peer_version
        self.peer_height = peer_height
        self.peer_services = peer_services
        self.peer_user_agent = msg.user_agent
        
        # 6. version 응답 (아직 안 보냈으면)
        if not self.version_sent:
            self.initiate_handshake()
        
        # 7. verack 전송
        self.send(Message("verack", b''))
        self.verack_sent = True
        self.version_received = True
        
        self._check_handshake_complete()
    
    def handle_verack(self):
        """verack 메시지 수신 처리"""
        self.verack_received = True
        self._check_handshake_complete()
    
    def _check_handshake_complete(self):
        """핸드셰이크 완료 확인"""
        if (self.version_sent and self.version_received 
            and self.verack_sent and self.verack_received):
            self.handshake_complete = True
            print(f"핸드셰이크 완료: {self.peer_user_agent}")
            self._post_handshake()
    
    def _post_handshake(self):
        """핸드셰이크 후 동기화 시작"""
        # 1. 피어 목록 요청
        self.send(Message("getaddr", b''))
        
        # 2. 상대가 더 긴 체인이면 동기화
        if self.peer_height > my_chain_height:
            self.start_sync()
```

---

### 4.6 자기 연결 감지 (Self-Connection Detection)

```
문제:
  노드 A가 자기 자신의 IP로 연결 시도
  → 무한 루프, 리소스 낭비

감지:
  1. 연결 시 랜덤 nonce 생성
  2. version 메시지에 nonce 포함
  3. 상대 version의 nonce가 내 것과 같으면?
     → 자기 자신!
     → 즉시 연결 해제

예:
  Node A nonce = 0x1234567890ABCDEF
  
  Node A → Node A (자기 자신):
    version.nonce = 0x1234567890ABCDEF
  
  수신한 nonce == 내 nonce
  → 자기 연결 감지! 연결 해제
```

---

## 5. 데이터 직렬화 (Serialization)

### 5.1 왜 필요한가?

```
문제:
  메모리의 구조체 → 네트워크 바이트 스트림

예:
  메모리:
    Block {
      version: 1,
      prev_hash: "0000abc...",
      timestamp: 1739369400
    }
  
  네트워크:
    01000000 0000abc123... 789ABCDE...
    ↑ 어떤 순서? 어떤 크기? 어떤 인코딩?

→ 규칙이 필요!
```

---

### 5.2 기본 타입 직렬화

**정수 (Little-Endian):**
```
JackpotChain은 Little-Endian (Bitcoin 방식)

예: 숫자 256
  Big-Endian:    00 00 01 00
  Little-Endian: 00 01 00 00  ← 이거!

타입별:
  uint8:  1 byte
  uint16: 2 bytes LE
  uint32: 4 bytes LE
  uint64: 8 bytes LE
  int32:  4 bytes LE (signed)
  int64:  8 bytes LE (signed)
```

**가변 길이 정수 (VarInt):**
```
작은 숫자는 짧게, 큰 숫자는 길게

값 범위          | 형식
───────────────┼──────────────────
0 ~ 0xFC       | 1 byte (값 그대로)
0xFD ~ 0xFFFF  | 0xFD + 2 bytes LE
0x10000 ~ 0xFFFFFFFF | 0xFE + 4 bytes LE
그 이상         | 0xFF + 8 bytes LE

예:
  값 10     → 0x0A (1 byte)
  값 255    → 0xFD FF 00 (3 bytes)
  값 70015  → 0xFE 7F 11 01 00 (5 bytes)

장점:
  TX 개수 같은 작은 숫자는 1 byte로 충분
  → 공간 절약
```

**문자열 (VarStr):**
```
VarInt(길이) + 바이트 데이터

예: "JackpotChain"
  0x0C  (12 = 길이)
  4A 61 63 6B 70 6F 74 43 68 61 69 6E  (ASCII)
```

**해시 (32 bytes):**
```
항상 32 bytes, Little-Endian 표시

예: 블록 해시
  내부 표현: 0000abc123def456...  (Big-Endian)
  직렬화:   ...456def123abc0000  (Little-Endian)
  
주의: 표시할 때는 다시 뒤집어서 Big-Endian으로!
```

---

### 5.3 복합 타입 직렬화

**Network Address (26 bytes):**
```
┌──────────────────────────────┐
│ services  (8 bytes)          │
│ ip        (16 bytes, IPv6)   │
│ port      (2 bytes, BE!)     │
└──────────────────────────────┘

IPv4 → IPv6 매핑:
  192.168.1.1 → 00000000 00000000 0000FFFF C0A80101

포트는 Big-Endian (네트워크 바이트 순서):
  8333 → 0x208D
```

**Inventory Vector (36 bytes):**
```
┌──────────────────────────────┐
│ type  (4 bytes)              │
│ hash  (32 bytes)             │
└──────────────────────────────┘

type:
  0 = ERROR
  1 = MSG_TX
  2 = MSG_BLOCK
  3 = MSG_FILTERED_BLOCK
```

---

### 5.4 TX 직렬화 예시

```python
def serialize_transaction(tx):
    """트랜잭션 직렬화"""
    result = b''
    
    # version (4 bytes LE)
    result += struct.pack('<I', tx.version)
    
    # input count (VarInt)
    result += encode_varint(len(tx.inputs))
    
    # inputs
    for inp in tx.inputs:
        result += bytes.fromhex(inp.prev_tx_id)[::-1]  # 32 bytes (LE)
        result += struct.pack('<I', inp.output_index)    # 4 bytes
        result += encode_varstr(inp.script_sig)          # 가변
        result += struct.pack('<I', inp.sequence)        # 4 bytes
    
    # output count (VarInt)
    result += encode_varint(len(tx.outputs))
    
    # outputs
    for out in tx.outputs:
        result += struct.pack('<q', out.value)           # 8 bytes (satoshi)
        result += encode_varstr(out.script_pubkey)       # 가변
        
        # JackpotChain 멀티에셋 확장
        result += encode_varint(len(out.assets))
        for asset_id, amount in out.assets.items():
            result += encode_varstr(asset_id.encode())
            result += struct.pack('<q', amount)
    
    # locktime (4 bytes LE)
    result += struct.pack('<I', tx.locktime)
    
    return result

def deserialize_transaction(data):
    """역직렬화"""
    stream = ByteStream(data)
    
    tx = Transaction()
    tx.version = stream.read_uint32()
    
    input_count = stream.read_varint()
    for _ in range(input_count):
        inp = TxInput()
        inp.prev_tx_id = stream.read(32)[::-1].hex()
        inp.output_index = stream.read_uint32()
        inp.script_sig = stream.read_varstr()
        inp.sequence = stream.read_uint32()
        tx.inputs.append(inp)
    
    output_count = stream.read_varint()
    for _ in range(output_count):
        out = TxOutput()
        out.value = stream.read_int64()
        out.script_pubkey = stream.read_varstr()
        
        # 멀티에셋
        asset_count = stream.read_varint()
        out.assets = {}
        for _ in range(asset_count):
            asset_id = stream.read_varstr().decode()
            amount = stream.read_int64()
            out.assets[asset_id] = amount
        
        tx.outputs.append(out)
    
    tx.locktime = stream.read_uint32()
    
    return tx
```

---

### 5.5 블록 직렬화

```python
def serialize_block(block):
    """블록 직렬화"""
    result = b''
    
    # === 블록 헤더 (80 bytes) ===
    result += struct.pack('<I', block.version)           # 4 bytes
    result += bytes.fromhex(block.prev_hash)[::-1]       # 32 bytes
    result += bytes.fromhex(block.merkle_root)[::-1]     # 32 bytes
    result += struct.pack('<I', block.timestamp)          # 4 bytes
    result += struct.pack('<I', block.difficulty_target)  # 4 bytes
    result += struct.pack('<I', block.nonce)              # 4 bytes
    
    # === 블록 바디 ===
    result += encode_varint(len(block.transactions))      # TX 개수
    
    for tx in block.transactions:
        result += serialize_transaction(tx)
    
    return result
```

---

## 6. INV/GETDATA 프로토콜

### 6.1 왜 이 방식인가?

```
문제: 블록이나 TX를 바로 보내면?
  Node A: "새 블록이다!" → 1 MB 전송
  Node B: "나 이미 있는데..." → 대역폭 낭비!

해결: 먼저 물어보기
  Node A: "블록 0000abc 있어" (inv, 36 bytes)
  Node B: "그거 없네, 줘" (getdata, 36 bytes)
  Node A: "여기!" (block, 1 MB)

또는:
  Node A: "블록 0000abc 있어" (inv, 36 bytes)
  Node B: "이미 있어" (무시)

→ 불필요한 전송 방지!
```

---

### 6.2 INV 메시지

```
inv (Inventory):
  "나한테 이런 데이터가 있어"

Payload:
  ┌──────────────────────────────┐
  │ count (VarInt)               │  항목 수
  ├──────────────────────────────┤
  │ inventory[] (36 bytes × N)   │  항목 목록
  │   ├─ type (4 bytes)          │  TX? Block?
  │   └─ hash (32 bytes)         │  데이터 해시
  └──────────────────────────────┘

type 값:
  1 = MSG_TX       (트랜잭션)
  2 = MSG_BLOCK    (블록)

예:
  "TX 3개, Block 1개 있어"
  count: 4
  [
    {type: 1, hash: "tx_hash_1..."},
    {type: 1, hash: "tx_hash_2..."},
    {type: 1, hash: "tx_hash_3..."},
    {type: 2, hash: "block_hash_1..."}
  ]
  
크기: 1 + (36 × 4) = 145 bytes (vs 실제 데이터 수 MB)
```

---

### 6.3 GETDATA 메시지

```
getdata:
  "이 데이터 보내줘"

Payload:
  inv와 동일한 형식
  → 원하는 항목만 골라서 요청

예:
  "tx_hash_1과 block_hash_1만 줘"
  count: 2
  [
    {type: 1, hash: "tx_hash_1..."},
    {type: 2, hash: "block_hash_1..."}
  ]
```

---

### 6.4 전체 흐름

```
=== 새 TX 전파 ===

Alice가 TX 생성 → Node A에 제출

Node A                          Node B
  │                               │
  │ ── inv (MSG_TX, tx_hash) ──→ │  "이 TX 있어"
  │                               │
  │                               │  (이미 있나 확인)
  │                               │  → Mempool에 없음
  │                               │
  │ ←── getdata (MSG_TX) ─────── │  "그 TX 줘"
  │                               │
  │ ── tx (full TX data) ──────→ │  "여기!"
  │                               │
  │                               │  (TX 검증)
  │                               │  → 유효! Mempool 추가
  │                               │
  │                               │  → Node C, D에게 inv


=== 새 블록 전파 ===

채굴자 → Node A에 새 블록

Node A                          Node B
  │                               │
  │ ── inv (MSG_BLOCK, hash) ──→ │  "이 블록 있어"
  │                               │
  │ ←── getdata (MSG_BLOCK) ──── │  "그 블록 줘"
  │                               │
  │ ── block (full block) ─────→ │  "여기!"
  │                               │
  │                               │  (블록 검증 - 02 §5.2 참조)
  │                               │  → 유효! 체인 추가
  │                               │  → UTXO Set 업데이트
  │                               │  → Node C, D에게 inv
```

---

### 6.5 중복 요청 방지

```python
class InvTracker:
    """이미 알고 있는 데이터 추적"""
    
    def __init__(self):
        self.known_tx = set()      # 알고 있는 TX 해시
        self.known_block = set()   # 알고 있는 블록 해시
        self.inflight = {}         # 요청 중인 데이터 {hash: (peer, time)}
    
    def handle_inv(self, peer, inv_items):
        """inv 메시지 처리"""
        to_request = []
        
        for item in inv_items:
            # 이미 알고 있는 데이터?
            if item.type == MSG_TX and item.hash in self.known_tx:
                continue
            if item.type == MSG_BLOCK and item.hash in self.known_block:
                continue
            
            # 이미 다른 피어에게 요청 중?
            if item.hash in self.inflight:
                continue
            
            # 요청 목록에 추가
            to_request.append(item)
            self.inflight[item.hash] = (peer, time.time())
        
        if to_request:
            peer.send(Message("getdata", serialize_inv(to_request)))
    
    def handle_data_received(self, hash):
        """데이터 수신 완료"""
        self.inflight.pop(hash, None)
    
    def check_timeouts(self):
        """타임아웃 된 요청 재시도"""
        now = time.time()
        for hash, (peer, req_time) in list(self.inflight.items()):
            if now - req_time > 30:  # 30초 타임아웃
                del self.inflight[hash]
                # 다른 피어에게 재요청
```

---

## 7. Ping/Pong (연결 유지)

### 7.1 목적

```
문제:
  TCP 연결이 살아있지만 상대가 응답 안 함
  → 좀비 연결 (리소스 낭비)

해결:
  주기적으로 ping → pong 확인
  → 응답 없으면 연결 해제
```

---

### 7.2 구조

```
ping Payload:
  ┌──────────────────────────────┐
  │ nonce (8 bytes)              │  랜덤 값
  └──────────────────────────────┘

pong Payload:
  ┌──────────────────────────────┐
  │ nonce (8 bytes)              │  ping과 동일한 값
  └──────────────────────────────┘
```

---

### 7.3 타이밍

```
JackpotChain 설정:
  ping 주기: 60초
  타임아웃: 20초
  최대 미응답: 3회

동작:
  0초:  ping (nonce=0x1234) 전송
  
  5초:  pong (nonce=0x1234) 수신 → 정상! RTT=5초
  
  60초: ping (nonce=0x5678) 전송
  80초: 응답 없음 → 경고 (1/3)
  
  120초: ping (nonce=0x9ABC) 전송
  140초: 응답 없음 → 경고 (2/3)
  
  180초: ping (nonce=0xDEF0) 전송
  200초: 응답 없음 → 연결 해제! (3/3)
```

---

### 7.4 레이턴시 측정

```python
class PingManager:
    def __init__(self, peer):
        self.peer = peer
        self.pending_pings = {}  # nonce → send_time
        self.latency_ms = 0
        self.miss_count = 0
    
    def send_ping(self):
        """ping 전송"""
        nonce = random.randint(0, 2**64 - 1)
        self.pending_pings[nonce] = time.time()
        self.peer.send(Message("ping", struct.pack('<Q', nonce)))
    
    def handle_pong(self, nonce):
        """pong 수신"""
        if nonce in self.pending_pings:
            send_time = self.pending_pings.pop(nonce)
            self.latency_ms = (time.time() - send_time) * 1000
            self.miss_count = 0  # 리셋
        
    def check_timeout(self):
        """타임아웃 확인"""
        now = time.time()
        for nonce, send_time in list(self.pending_pings.items()):
            if now - send_time > 20:  # 20초 타임아웃
                del self.pending_pings[nonce]
                self.miss_count += 1
                
                if self.miss_count >= 3:
                    self.peer.disconnect("ping timeout")
```

---

## 8. 블록 헤더 동기화 (Headers-First)

### 8.1 getheaders 메시지

```
목적: 블록 헤더 목록 요청

Payload:
  ┌──────────────────────────────────┐
  │ version         (4 bytes)        │
  │ hash_count      (VarInt)         │  Block Locator 개수
  │ block_locator[] (32 bytes × N)   │  알고 있는 블록 해시들
  │ hash_stop       (32 bytes)       │  여기까지 원함 (0=끝까지)
  └──────────────────────────────────┘

Block Locator:
  최근 블록부터 점점 간격을 넓혀서 해시 나열
  → 포크 지점을 빠르게 찾기 위함

예 (내 체인 높이 1000):
  block_locator = [
    hash(1000),   // 최신
    hash(999),    // -1
    hash(998),    // -1
    hash(997),    // -1
    hash(996),    // -1
    hash(994),    // -2
    hash(990),    // -4
    hash(982),    // -8
    hash(966),    // -16
    hash(934),    // -32
    hash(870),    // -64
    hash(742),    // -128
    hash(486),    // -256
    hash(0),      // Genesis
  ]
  
→ 최근은 촘촘, 과거는 듬성듬성
→ 포크 지점을 최소 요청으로 찾기
```

---

### 8.2 headers 응답

```
headers:
  최대 2000개 블록 헤더 반환

Payload:
  ┌──────────────────────────────────┐
  │ count (VarInt)                   │  헤더 개수 (≤ 2000)
  │ headers[] (81 bytes × N)         │  블록 헤더 + TX 카운트
  │   ├─ header (80 bytes)           │  블록 헤더
  │   └─ tx_count (VarInt, 항상 0)   │  여기선 항상 0
  └──────────────────────────────────┘

크기: 2000 × 81 = 162 KB (블록 전체 대비 아주 작음)
```

---

### 8.3 동기화 흐름

```
내 체인: [0] → [1] → ... → [100]
상대 체인: [0] → [1] → ... → [100] → [101] → ... → [5000]

Step 1: getheaders 전송
  block_locator = [hash(100), hash(99), ..., hash(0)]
  hash_stop = 0x000...000

Step 2: headers 수신
  [header(101), header(102), ..., header(2100)]
  → 2000개 수신

Step 3: 헤더 검증
  각 헤더:
    prev_hash 연결 확인
    PoW 확인 (hash < target)
    timestamp 확인
  
Step 4: 추가 요청 (2000개 이상이면)
  getheaders (block_locator = [hash(2100)])
  → headers [2101 ~ 4100]

Step 5: 반복
  headers 응답이 2000개 미만이면 끝

Step 6: 블록 바디 다운로드
  getdata로 실제 블록 요청
  → TX 포함된 전체 블록
```

---

## 9. Mempool 동기화

### 9.1 mempool 메시지

```
목적: 상대의 Mempool에 있는 TX 목록 요청

요청 (mempool):
  Payload 없음 (0 bytes)

응답 (inv):
  Mempool에 있는 TX 해시 목록
  → inv 메시지로 응답

예:
  Node A → Node B: mempool
  Node B → Node A: inv [tx1, tx2, tx3, ..., tx500]
  Node A → Node B: getdata [tx1, tx3]  (없는 것만)
  Node B → Node A: tx(tx1), tx(tx3)
```

---

### 9.2 언제 사용?

```
1. 핸드셰이크 직후
   → 상대가 알고 내가 모르는 TX 가져오기

2. 연결이 끊겼다 복구됐을 때
   → 놓친 TX 따라잡기

3. 주기적 동기화 (선택사항)
   → 네트워크 상태 확인
```

---

## 10. Reject 메시지

### 10.1 구조

```
reject:
  문제가 있는 메시지에 대한 거부 응답

Payload:
  ┌──────────────────────────────────┐
  │ message (VarStr)                 │  거부된 메시지 타입
  │ code    (1 byte)                 │  에러 코드
  │ reason  (VarStr)                 │  사람이 읽을 수 있는 이유
  │ data    (가변, 선택)             │  관련 해시 등
  └──────────────────────────────────┘

에러 코드:
  0x01: REJECT_MALFORMED     (형식 오류)
  0x10: REJECT_INVALID       (검증 실패)
  0x11: REJECT_OBSOLETE      (오래된 버전)
  0x12: REJECT_DUPLICATE     (중복)
  0x40: REJECT_NONSTANDARD   (비표준 TX)
  0x41: REJECT_DUST          (금액 너무 작음)
  0x42: REJECT_INSUFFICIENTFEE (수수료 부족)
  0x43: REJECT_CHECKPOINT    (체크포인트 불일치)
```

---

### 10.2 예시

```
잘못된 TX 수신:
  reject {
    message: "tx",
    code: 0x10 (INVALID),
    reason: "mandatory-script-verify-flag-failed",
    data: <tx_hash>
  }

프로토콜 너무 오래됨:
  reject {
    message: "version",
    code: 0x11 (OBSOLETE),
    reason: "protocol version too old, min=70015"
  }

수수료 부족:
  reject {
    message: "tx",
    code: 0x42 (INSUFFICIENTFEE),
    reason: "min fee not met, need 0.001 JACK"
  }
```

---

## 11. JackpotChain 프로토콜 확장

### 11.1 멀티에셋 관련

```
기존 Bitcoin 프로토콜에 추가:

inv type 확장:
  4 = MSG_ASSET_TX (에셋 관련 TX)

추가 메시지:
  getassets:  에셋 목록 요청
  assets:     에셋 목록 응답
  
  Payload:
    ┌──────────────────────────────┐
    │ count (VarInt)               │
    │ assets[]                     │
    │   ├─ policy_id (32 bytes)    │
    │   ├─ asset_name (VarStr)     │
    │   └─ total_supply (8 bytes)  │
    └──────────────────────────────┘
```

---

### 11.2 가챠 관련

```
Commit-Reveal TX도 일반 TX로 처리
→ 별도 메시지 불필요
→ TX type 필드로 구분

TX version 확장:
  version 1: 일반 TX
  version 2: Exchange TX (JACK → POT)
  version 3: Gacha Commit TX
  version 4: Gacha Reveal TX
```

---

### 11.3 SSAFY MVP 단순화

```
MVP에서는:
  ✅ 구현 (필수)
    - version/verack (핸드셰이크)
    - ping/pong (연결 유지)
    - inv/getdata (데이터 교환)
    - tx/block (데이터 전달)
    - getheaders/headers (동기화)
  
  ⏳ 나중에 (Phase 2)
    - mempool (Mempool 동기화)
    - getaddr/addr (피어 발견)
    - reject (에러 처리)
    - getassets/assets (멀티에셋)
  
  ❌ 스킵 가능 (최적화)
    - compact block
    - bloom filter
    - fee filter

이유:
  MVP는 6개 노드 로컬 네트워크
  → 복잡한 피어 발견 불필요
  → 직접 IP 지정
  → 핵심 기능만 먼저
```

---

## 12. 보안 고려사항

### 12.1 메시지 크기 제한

```python
MAX_MESSAGE_SIZE = 4 * 1024 * 1024  # 4 MB
MAX_INV_COUNT = 50000               # inv 최대 항목
MAX_HEADERS_COUNT = 2000            # headers 최대 개수

def validate_message(msg):
    if msg.length > MAX_MESSAGE_SIZE:
        reject("message too large")
    
    if msg.command == "inv" and msg.inv_count > MAX_INV_COUNT:
        reject("too many inv items")
    
    if msg.command == "headers" and msg.count > MAX_HEADERS_COUNT:
        reject("too many headers")
```

---

### 12.2 DoS 방어

```
Rate Limiting:
  ┌─────────────────────────┬────────────┐
  │ 메시지 타입              │ 제한       │
  ├─────────────────────────┼────────────┤
  │ version                 │ 1회/연결    │
  │ ping                    │ 1회/10초    │
  │ inv                     │ 10회/초     │
  │ getdata                 │ 10회/초     │
  │ getaddr                 │ 1회/분      │
  │ mempool                 │ 1회/분      │
  └─────────────────────────┴────────────┘

Ban 정책:
  - 잘못된 메시지 3회 → 1시간 밴
  - 체크섬 불일치 5회 → 24시간 밴
  - 핸드셰이크 전 데이터 요청 → 즉시 밴
```

---

### 12.3 핸드셰이크 전 제한

```
핸드셰이크 완료 전:
  ✅ 허용: version, verack
  ❌ 거부: 그 외 모든 메시지

이유:
  핸드셰이크 없이 데이터 요청 → 비인증 접근
  → 리소스 낭비 공격 가능

검증:
  if not peer.handshake_complete:
      if msg.command not in ("version", "verack"):
          peer.ban("pre-handshake message")
```

---

## 13. 실전 예시

### 13.1 전체 시나리오

```
=== Node A (신규) → Node B (기존, 높이 5000) ===

1. TCP 연결
   A → B: TCP SYN
   B → A: TCP SYN+ACK
   A → B: TCP ACK

2. 핸드셰이크
   A → B: version {v:70015, height:0, agent:"/JackpotChain:1.0/"}
   B → A: version {v:70015, height:5000, agent:"/JackpotChain:1.0/"}
   B → A: verack
   A → B: verack
   
   → A: "B는 5000 높이, 동기화 필요!"

3. 헤더 동기화
   A → B: getheaders {locator:[genesis_hash], stop:0}
   B → A: headers [header(1)...header(2000)]
   
   A → B: getheaders {locator:[hash(2000)], stop:0}
   B → A: headers [header(2001)...header(4000)]
   
   A → B: getheaders {locator:[hash(4000)], stop:0}
   B → A: headers [header(4001)...header(5000)]
   → 1000개 (< 2000) → 헤더 동기화 완료!

4. 블록 다운로드
   A → B: getdata [block(1), block(2), ..., block(16)]
   B → A: block(1), block(2), ..., block(16)
   
   (반복, 병렬로 여러 피어에게 요청)

5. Mempool 동기화
   A → B: mempool
   B → A: inv [tx1, tx2, ..., tx100]
   A → B: getdata [tx1, tx2, ..., tx100]
   B → A: tx(1), tx(2), ..., tx(100)

6. 정상 운영
   B → A: inv (새 블록 알림)
   A → B: getdata (블록 요청)
   B → A: block (블록 전달)
   
   A → B: inv (새 TX 알림)
   ...
```

---

## 14. 핵심 요약

### 메시지 프레임
```
[magic(4)] [command(12)] [length(4)] [checksum(4)] [payload]
→ 24 bytes 헤더 + 가변 페이로드
→ Magic으로 네트워크 구분
→ Checksum으로 무결성
```

### 핸드셰이크
```
A → B: version (내 정보)
B → A: version (상대 정보)
B → A: verack (수락)
A → B: verack (수락)
→ 4단계, 양방향 확인
```

### 데이터 교환
```
INV → GETDATA → DATA (tx/block)
→ 먼저 알리고, 필요한 것만 요청
→ 대역폭 절약
```

### 직렬화
```
Little-Endian 정수
VarInt 가변 길이
VarStr 문자열
→ Bitcoin 호환 방식
```

### 동기화
```
getheaders → headers (헤더 먼저)
getdata → block (블록 다운로드)
mempool → inv → getdata → tx (TX 동기화)
```

---

## 15. 체크리스트

이해했는지 확인:

- [ ] 메시지 프레임 4개 필드 (magic, command, length, checksum)
- [ ] Magic 바이트의 용도 (네트워크 구분, 동기화)
- [ ] 핸드셰이크 4단계 과정
- [ ] version 메시지의 주요 필드
- [ ] 자기 연결 감지 원리 (nonce)
- [ ] VarInt 인코딩 방식
- [ ] Little-Endian 직렬화
- [ ] INV/GETDATA 프로토콜 흐름
- [ ] 중복 데이터 요청 방지
- [ ] Ping/Pong 연결 유지
- [ ] Block Locator로 포크 지점 찾기
- [ ] 메시지 크기 제한과 DoS 방어

---

## 16. 다음 학습

### 학습 완료:
- ✅ P2P 네트워크 기초
- ✅ 네트워크 프로토콜

### 다음 추천:
```
→ [10. 블록 전파](10-block-propagation.md) ✅ 완료
  - Gossip Protocol 상세
  - Compact Block
  - 전파 최적화

→ [11. 동기화](11-synchronization.md)
  - Initial Block Download 상세
  - Headers-First Sync 구현
  - Orphan Block 처리
```

---

## 17. 참고 자료

**Bitcoin 프로토콜:**
- Bitcoin Developer Guide - P2P Network
- Bitcoin Wiki - Protocol Documentation
- BIP 130: sendheaders
- BIP 152: Compact Block Relay

**구현:**
- Bitcoin Core - net_processing.cpp
- btcd - wire package (Go)
- python-bitcoinlib - p2p module

**도구:**
- Wireshark Bitcoin Protocol Dissector
- bitcoin-cli getpeerinfo

---

**이전:** [08. P2P 네트워크 기초](08-p2p-basics.md)  
**다음:** [10. 블록 전파](10-block-propagation.md) →
