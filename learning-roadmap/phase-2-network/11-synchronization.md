# 11. 동기화 (Synchronization)

> **Phase 2: Network**  
> **학습 날짜:** 2025-02-19  
> **난이도:** ⭐⭐⭐☆☆  
> **예상 소요 시간:** 2-3시간  
> **선행 학습:** [09. 네트워크 프로토콜](09-network-protocol.md), [10. 블록 전파](10-block-propagation.md)

---

## 🎯 학습 목표

이 문서를 완료하면:
- [ ] IBD (Initial Block Download)의 전체 흐름을 설명할 수 있다
- [ ] Headers-First Sync가 왜 필요한지 이해한다
- [ ] Blocks-First vs Headers-First 방식을 비교할 수 있다
- [ ] 병렬 블록 다운로드를 설계할 수 있다
- [ ] Orphan Block 처리를 구현할 수 있다
- [ ] 체크포인트의 역할과 보안 의미를 안다
- [ ] JackpotChain MVP 동기화 전략을 이해한다

---

## 1. 동기화란?

### 1.1 문제

```
신규 노드가 네트워크에 참여:
  내 체인: [Genesis]  (높이 0)
  네트워크: [Genesis] → ... → [Block 50000]  (높이 50000)
  
  → 50000개 블록을 받아야 함!
  → 어떤 순서로? 누구한테? 어떻게 검증?
```

**비유: 전학생**
```
전학생이 수학 수업 중간에 전학:
  "1학기 내용을 몰라요"
  
방법 1: 교과서 처음부터 끝까지 읽기 (느림)
방법 2: 목차 먼저 보고 → 필요한 부분만 읽기 (빠름)
방법 3: 여러 친구한테 동시에 다른 단원 물어보기 (병렬)

블록체인도 마찬가지!
```

---

### 1.2 동기화 상태 구분

```
┌──────────────────────────────────────────────┐
│ IBD (Initial Block Download)                  │
│   신규 노드가 전체 체인을 처음 받는 과정       │
│   상태: is_initial_download = true            │
│   특징: 모든 블록을 검증하며 다운로드          │
├──────────────────────────────────────────────┤
│ Normal Sync (정상 동기화)                      │
│   동기화 완료 후 새 블록만 받는 상태            │
│   상태: is_initial_download = false           │
│   특징: inv/getdata로 실시간 수신             │
├──────────────────────────────────────────────┤
│ Catch-up (따라잡기)                            │
│   잠시 오프라인 후 놓친 블록 받기               │
│   상태: tip이 최신보다 뒤처짐                   │
│   특징: IBD와 비슷하지만 범위가 작음           │
└──────────────────────────────────────────────┘

판단 기준:
  my_tip.timestamp < now() - 24시간
  → IBD 모드로 진입
  
  my_tip.timestamp >= now() - 24시간
  → Normal Sync 모드
```

---

## 2. Blocks-First 방식 (레거시)

### 2.1 흐름

```
=== 가장 단순한 방식 (Bitcoin 초기) ===

Node A (신규)                    Node B (기존, 높이 5000)
  │                               │
  │ ── getblocks ───────────────→ │  "Block Locator 보낼게"
  │    locator=[genesis]          │
  │                               │
  │ ←── inv [1,2,...,500] ─────── │  "이 블록들 있어"
  │                               │
  │ ── getdata [1,2,...,16] ────→ │  "1~16번 줘"
  │                               │
  │ ←── block(1) ─────────────── │
  │ ←── block(2) ─────────────── │
  │ ←── block(3) ─────────────── │
  │ ...                           │
  │ ←── block(16) ────────────── │
  │                               │
  │  (검증 후 다음 배치 요청)       │
  │                               │
  │ ── getdata [17,...,32] ─────→ │
  │ ...                           │
  
→ 500개 단위로 inv, 16개 단위로 다운로드
→ 5000블록이면 ~313 배치 = 5분+ 소요
```

---

### 2.2 문제점

```
문제 1: 느림
  - 순차적 다운로드 (1명한테만 요청)
  - 한 피어가 느리면 전체가 느림

문제 2: DoS 취약
  - 악의적 피어가 가짜 체인 전송 가능
  - 모든 블록을 받아서 검증해야 알 수 있음
  - 1 MB × 50000 = 50 GB 낭비 가능!

문제 3: 포크 대응 어려움
  - 받는 도중 체인이 바뀔 수 있음
  - 전부 다시 받아야 할 수도

→ Headers-First 방식이 해결!
```

---

## 3. Headers-First 방식 (현재 표준)

### 3.1 핵심 아이디어

```
2단계 접근:
  Phase 1: 헤더만 먼저 전부 받기 (빠르고 가벼움)
  Phase 2: 헤더 검증 후 블록 바디 다운로드 (병렬 가능)

왜 좋은가?
  헤더: 80 bytes × 50000 = 4 MB (금방!)
  블록: ~1 MB × 50000 = 50 GB (오래...)
  
  → 4 MB로 체인 구조를 먼저 파악
  → 가짜 체인이면 4 MB만 낭비 (vs 50 GB)
  → 진짜 체인임을 확인한 후에 블록 다운로드
```

---

### 3.2 전체 흐름

```
=== Phase 1: 헤더 동기화 ===

Node A (신규)                    Node B
  │                               │
  │ ── getheaders ──────────────→ │  locator=[genesis]
  │ ←── headers [1..2000] ─────── │  2000개 헤더 (~162 KB)
  │                               │
  │  (각 헤더 검증: PoW, prev_hash, timestamp)
  │                               │
  │ ── getheaders ──────────────→ │  locator=[2000]
  │ ←── headers [2001..4000] ──── │  2000개 더
  │                               │
  │ ── getheaders ──────────────→ │  locator=[4000]
  │ ←── headers [4001..5000] ──── │  1000개 (< 2000 = 끝!)
  │                               │
  │  === 헤더 동기화 완료 ===       │
  │  총 소요: ~500ms              │
  │  총 데이터: ~405 KB           │


=== Phase 2: 블록 다운로드 (병렬!) ===

Node A                    Node B          Node C          Node D
  │                         │               │               │
  │ ── getdata [1..100] ──→ │               │               │
  │ ── getdata [101..200] ──────────────→   │               │
  │ ── getdata [201..300] ──────────────────────────────→   │
  │                         │               │               │
  │ ←── block(1..100) ──── │               │               │
  │ ←── block(101..200) ────────────────── │               │
  │ ←── block(201..300) ────────────────────────────────── │
  │                         │               │               │
  │  (도착하는 대로 검증 & 체인 적용)
  │                         │               │               │

→ 여러 피어에게 동시 요청!
→ 다운로드 속도 N배 향상!
```

---

### 3.3 헤더 검증

```python
def validate_header_chain(headers, prev_tip):
    """헤더 체인 검증"""
    prev_header = prev_tip
    
    for header in headers:
        # 1. prev_hash 연결 확인
        if header.prev_hash != prev_header.hash():
            return False, "체인 연결 끊김"
        
        # 2. PoW 확인 (hash < target)
        if header.hash() >= header.target():
            return False, "PoW 실패"
        
        # 3. timestamp 확인
        if header.timestamp > time.time() + 7200:  # 미래 2시간 이내
            return False, "미래 타임스탬프"
        
        if header.timestamp <= get_median_time(prev_header):
            return False, "과거 타임스탬프"
        
        # 4. 난이도 확인 (50블록마다 조절)
        expected_target = calculate_next_target(prev_header)
        if header.difficulty_target != expected_target:
            return False, "난이도 불일치"
        
        prev_header = header
    
    return True, "검증 성공"

def get_median_time(header):
    """최근 11블록의 중앙값 timestamp"""
    timestamps = []
    current = header
    for _ in range(11):
        timestamps.append(current.timestamp)
        current = get_prev_header(current)
        if current is None:
            break
    timestamps.sort()
    return timestamps[len(timestamps) // 2]
```

---

### 3.4 블록 다운로드 관리자

```python
class BlockDownloadManager:
    """병렬 블록 다운로드 관리"""
    
    WINDOW_SIZE = 1024       # 동시 요청 가능 블록 수
    BATCH_SIZE = 16          # 피어당 한 번에 요청하는 블록 수
    TIMEOUT = 30             # 요청 타임아웃 (초)
    
    def __init__(self, header_chain):
        self.header_chain = header_chain  # 검증된 헤더 체인
        self.next_height = 1              # 다음 요청할 높이
        self.validated_height = 0         # 검증 완료된 높이
        self.inflight = {}                # {height: (peer, time)}
        self.received = {}                # {height: block}
    
    def assign_work(self, peer):
        """피어에게 다운로드 작업 할당"""
        blocks_to_request = []
        
        height = self.next_height
        while (len(blocks_to_request) < self.BATCH_SIZE 
               and height <= len(self.header_chain)
               and height < self.validated_height + self.WINDOW_SIZE):
            
            if height not in self.inflight and height not in self.received:
                blocks_to_request.append(height)
                self.inflight[height] = (peer, time.time())
            
            height += 1
        
        if blocks_to_request:
            self.next_height = max(self.next_height, height)
            hashes = [self.header_chain[h].hash() for h in blocks_to_request]
            peer.send(Message("getdata", 
                [InvItem(MSG_BLOCK, h) for h in hashes]))
    
    def on_block_received(self, block, peer):
        """블록 수신 처리"""
        height = self.get_height(block)
        
        # inflight에서 제거
        self.inflight.pop(height, None)
        
        # 헤더와 일치하는지 확인
        expected_hash = self.header_chain[height].hash()
        if block.hash() != expected_hash:
            peer.ban("block hash mismatch")
            return
        
        # 수신 버퍼에 저장
        self.received[height] = block
        
        # 순차적으로 검증 & 적용
        self._process_ready_blocks()
    
    def _process_ready_blocks(self):
        """순서대로 블록 검증 및 적용"""
        while self.validated_height + 1 in self.received:
            height = self.validated_height + 1
            block = self.received.pop(height)
            
            # 전체 블록 검증 (TX, Script, UTXO 등)
            if self.validate_full_block(block):
                self.chain.append(block)
                self.update_utxo_set(block)
                self.validated_height = height
                
                # 진행률 표시
                if height % 1000 == 0:
                    pct = height / len(self.header_chain) * 100
                    print(f"동기화: {height}/{len(self.header_chain)} ({pct:.1f}%)")
            else:
                # 블록 검증 실패 → 해당 피어 밴
                print(f"블록 검증 실패! height={height}")
                break
    
    def check_timeouts(self):
        """타임아웃 된 요청 재할당"""
        now = time.time()
        for height, (peer, req_time) in list(self.inflight.items()):
            if now - req_time > self.TIMEOUT:
                del self.inflight[height]
                peer.mark_slow()
                # 다른 피어에게 재요청 (assign_work에서 처리)
```

---

### 3.5 다운로드 윈도우

```
왜 윈도우가 필요한가?

문제:
  블록 5000개를 한꺼번에 요청하면?
  → 메모리 부족 (5 GB)
  → 순서 뒤바뀜 많음
  → 검증 지연

해결: 슬라이딩 윈도우
  
  [=====검증완료=====][====다운로드중====][===아직 안 요청===]
  Block 0        Block 500     Block 1524      Block 5000
                  ↑ validated    ↑ next_height
  
  윈도우 크기: 1024 블록
  → 검증 완료 지점 + 1024까지만 요청
  → 검증이 진행되면 윈도우도 이동
  
  메모리 사용: ~1 GB (윈도우 내 블록만 보관)
```

---

## 4. 블록 검증 순서

### 4.1 검증 단계

```
=== 블록 도착 순서와 검증 순서 ===

다운로드 순서 (비순차적):
  Block 3 도착 (피어 C에서)
  Block 1 도착 (피어 A에서)
  Block 5 도착 (피어 C에서)
  Block 2 도착 (피어 B에서)
  Block 4 도착 (피어 A에서)

검증 순서 (반드시 순차적):
  Block 1 → 검증 → 체인 추가 → UTXO 업데이트
  Block 2 → 검증 → 체인 추가 → UTXO 업데이트
  Block 3 → 검증 → 체인 추가 → UTXO 업데이트
  Block 4 → 검증 → 체인 추가 → UTXO 업데이트
  Block 5 → 검증 → 체인 추가 → UTXO 업데이트

이유:
  Block 2의 TX가 Block 1의 Output을 참조할 수 있음
  → Block 1의 UTXO가 먼저 Set에 있어야 함
  → 순서 보장 필수!
```

---

### 4.2 검증 최적화

```
=== IBD 중 최적화 ===

1. 서명 검증 스킵 (체크포인트 이전)
   체크포인트 높이 이전 블록:
     PoW 검증만 (헤더에서 이미 함)
     서명 검증 스킵!
   → 10배 빠름
   
   이유:
     체크포인트 = 하드코딩된 "이 블록은 진짜"
     → 서명까지 검증할 필요 없음

2. UTXO Set 배치 업데이트
   블록마다 디스크 쓰기 대신:
     100블록마다 한 번에 flush
   → 디스크 I/O 90% 감소

3. 스크립트 캐싱
   같은 패턴의 script_pubkey 반복 시:
     캐시에서 결과 가져오기
   → 30% 빠름

4. 병렬 서명 검증 (체크포인트 이후)
   각 TX의 Input은 독립적:
     8코어 → 8개 서명 동시 검증
   → 8배 빠름
```

---

## 5. Orphan Block 처리 (심화)

### 5.1 IBD 중 Orphan

```
상황:
  Headers-First에서는 Orphan이 거의 없음
  → 헤더 순서를 이미 알고 있으므로

  하지만 Normal Sync에서는 발생 가능:
  
  Block 1001이 먼저 도착
  Block 1000이 아직 안 옴
  
  → Block 1001 = Orphan
  → 임시 보관
  → Block 1000 도착 시 해결
```

---

### 5.2 Orphan 처리 흐름

```
Block 1001 도착 (prev_hash = hash(1000)):

1. 부모 확인
   chain.has(hash(1000))? → No!
   
2. Orphan Pool에 저장
   orphan_pool.add(block_1001)
   
3. 부모 요청
   peer.send(getdata(hash(1000)))

4. Block 1000 도착:
   chain.append(block_1000)
   
5. Orphan 해결 확인
   orphan_pool.check_resolved(hash(1000))
   → block_1001 발견!
   → chain.append(block_1001)
   
6. 연쇄 해결
   orphan_pool.check_resolved(hash(1001))
   → 추가 Orphan 있으면 계속
```

---

### 5.3 Orphan Pool 보안

```python
class SecureOrphanPool:
    """보안 강화된 Orphan Pool"""
    
    MAX_ORPHANS = 100          # 최대 보관 수
    MAX_ORPHAN_AGE = 600       # 10분 후 만료
    MAX_ORPHAN_SIZE = 1_000_000  # 1 MB 이하만
    
    def __init__(self):
        self.orphans = {}
        self.by_parent = {}
        self.timestamps = {}
    
    def add(self, block):
        """Orphan 추가 (보안 검사 포함)"""
        block_hash = block.hash()
        
        # 1. 크기 제한
        if len(block.serialize()) > self.MAX_ORPHAN_SIZE:
            return False
        
        # 2. PoW 검증 (가짜 블록 방지)
        if not self.quick_validate_pow(block):
            return False
        
        # 3. 이미 있는지
        if block_hash in self.orphans:
            return False
        
        # 4. 풀 크기 제한
        if len(self.orphans) >= self.MAX_ORPHANS:
            self._evict_oldest()
        
        # 5. 저장
        self.orphans[block_hash] = block
        self.timestamps[block_hash] = time.time()
        parent = block.header.prev_hash
        self.by_parent.setdefault(parent, []).append(block_hash)
        
        return True
    
    def cleanup_expired(self):
        """만료된 Orphan 제거"""
        now = time.time()
        expired = [h for h, t in self.timestamps.items() 
                   if now - t > self.MAX_ORPHAN_AGE]
        
        for block_hash in expired:
            self._remove(block_hash)
    
    def _evict_oldest(self):
        """가장 오래된 Orphan 제거"""
        if not self.timestamps:
            return
        oldest = min(self.timestamps, key=self.timestamps.get)
        self._remove(oldest)
```

---

## 6. 체크포인트 (Checkpoints)

### 6.1 개념

```
체크포인트 = 소스코드에 하드코딩된 "알려진 좋은 블록"

JackpotChain 예:
  CHECKPOINTS = {
      0:     "000000000019d6689c085ae165831e...",  # Genesis
      10000: "00000000000003b5e12a8faa0cff4e...",  # 높이 10000
      20000: "000000000000001ea32c3e4f8b3d5a...",  # 높이 20000
  }
```

---

### 6.2 역할

```
역할 1: IBD 가속
  체크포인트 이전 블록:
    PoW만 검증 (서명 스킵)
    → 속도 10배 향상
    
  체크포인트 이후 블록:
    전체 검증 (서명 포함)

역할 2: 가짜 체인 방지
  공격자가 가짜 체인을 보내면:
    체크포인트 높이의 해시가 다름
    → 즉시 거부!
    → 데이터 낭비 최소화

역할 3: 긴 Reorg 방지
  체크포인트 이전으로 Reorg 불가
    → 확정된 역사 보호
    
예:
  체크포인트 높이 20000
  현재 높이 25000
  
  공격자: "높이 19999에서 분기한 체인이 더 길어!"
  노드: "20000 체크포인트가 다르니 거부" ❌
```

---

### 6.3 체크포인트 검증

```python
CHECKPOINTS = {
    0:     "0000000000000000000000000000000000000000...",
    10000: "0000abc123def456789012345678901234567890...",
    20000: "0000def789abc123456789012345678901234567...",
}

def validate_against_checkpoints(header, height):
    """체크포인트 검증"""
    if height in CHECKPOINTS:
        expected_hash = CHECKPOINTS[height]
        actual_hash = header.hash()
        
        if actual_hash != expected_hash:
            return False, f"체크포인트 불일치! height={height}"
    
    return True, "OK"

def should_skip_scripts(height):
    """서명 검증 스킵 여부"""
    max_checkpoint = max(CHECKPOINTS.keys())
    return height <= max_checkpoint
```

---

### 6.4 체크포인트의 트레이드오프

```
장점:
  ✅ IBD 속도 향상 (10배+)
  ✅ 가짜 체인 조기 거부
  ✅ 긴 Reorg 방지

단점:
  ❌ 약간의 중앙화 (개발팀이 결정)
  ❌ 소프트웨어 업데이트 필요 (새 체크포인트 추가)
  ❌ 체크포인트 자체가 틀릴 수 있음 (이론적)

Bitcoin의 선택:
  체크포인트 사용하되, 점점 줄이는 추세
  → assumevalid (서명만 스킵, 체인 구조는 검증)

JackpotChain:
  MVP에서는 체크포인트 적극 사용
  → 팀이 운영하므로 중앙화 우려 적음
  → IBD 속도가 중요
```

---

## 7. IBD 모드 동작

### 7.1 IBD 감지

```python
class SyncManager:
    """동기화 관리자"""
    
    IBD_THRESHOLD = 86400  # 24시간 (초)
    
    def __init__(self, chain):
        self.chain = chain
        self.is_ibd = True
        self.sync_peers = []
    
    def check_ibd_status(self):
        """IBD 상태 확인"""
        tip = self.chain.get_tip()
        
        if tip is None:
            self.is_ibd = True
            return
        
        age = time.time() - tip.timestamp
        
        if age > self.IBD_THRESHOLD:
            self.is_ibd = True
        else:
            if self.is_ibd:
                print("IBD 완료! Normal Sync 모드로 전환")
            self.is_ibd = False
    
    def get_sync_behavior(self):
        """모드별 동작 설정"""
        if self.is_ibd:
            return {
                "relay_tx": False,        # TX 릴레이 안 함
                "relay_block": False,     # 블록 릴레이 안 함
                "accept_mempool": False,  # Mempool TX 안 받음
                "parallel_download": True, # 병렬 다운로드
                "skip_scripts": True,     # 체크포인트 전 서명 스킵
                "batch_utxo": True,       # UTXO 배치 업데이트
            }
        else:
            return {
                "relay_tx": True,
                "relay_block": True,
                "accept_mempool": True,
                "parallel_download": False,
                "skip_scripts": False,
                "batch_utxo": False,
            }
```

---

### 7.2 IBD 중 제한사항

```
IBD 모드에서 하지 않는 것:
  ❌ TX 릴레이
     → 아직 최신 UTXO Set이 없음
     → TX 검증 불가능
  
  ❌ 블록 릴레이
     → 아직 동기화 안 됐으므로 전파 의미 없음
  
  ❌ Mempool TX 수집
     → UTXO Set 미완성 → 검증 불가
  
  ❌ 채굴
     → 동기화 안 된 상태에서 채굴하면
     → 무효 블록 생성 가능

IBD 모드에서 하는 것:
  ✅ 헤더 다운로드
  ✅ 블록 다운로드 (병렬)
  ✅ 블록 검증 & 체인 적용
  ✅ UTXO Set 구축
  ✅ 피어 관리 (연결/해제)
```

---

### 7.3 IBD 진행률 표시

```
=== JackpotChain IBD Progress ===

Phase 1: 헤더 동기화
  [████████████████████] 100% (50000/50000 headers)
  소요: 2초 | 크기: 4.05 MB

Phase 2: 블록 다운로드 & 검증
  [████████████░░░░░░░░] 60% (30000/50000 blocks)
  소요: 45초 | 크기: 30 GB
  속도: 667 blocks/sec
  예상 잔여: 30초
  
  피어별 속도:
    10.0.1.101: 250 blocks/sec ★
    10.0.1.102: 200 blocks/sec
    10.0.1.103: 150 blocks/sec
    10.0.1.104: 67 blocks/sec (느림)

UTXO Set:
  크기: 2.1 GB (120,000 UTXOs)
  캐시 적중률: 92%
```

---

## 8. Catch-up 동기화

### 8.1 시나리오

```
노드가 1시간 동안 오프라인:
  마지막 높이: 5000
  현재 네트워크 높이: 5240 (15초 × 240 = 1시간)
  
  놓친 블록: 240개
  → IBD 불필요 (풀 다운로드 아님)
  → Catch-up 모드
```

---

### 8.2 Catch-up 흐름

```
Node A (높이 5000)              Node B (높이 5240)
  │                               │
  │ ── getheaders ──────────────→ │  locator=[5000,4999,...,0]
  │ ←── headers [5001..5240] ──── │  240개 헤더
  │                               │
  │  (헤더 검증)                    │
  │                               │
  │ ── getdata [5001..5016] ────→ │  블록 요청 (순차)
  │ ←── block(5001..5016) ─────── │
  │                               │
  │  (검증 & 적용)                  │
  │                               │
  │ ... (반복)                     │
  │                               │
  │ ── getdata [5225..5240] ────→ │  마지막 배치
  │ ←── block(5225..5240) ─────── │
  │                               │
  │  === Catch-up 완료 ===         │
  │  소요: ~5초                    │
  │  → Normal Sync 복귀            │
```

---

### 8.3 Catch-up vs IBD

```
┌───────────────┬──────────────────┬──────────────────┐
│               │ IBD              │ Catch-up         │
├───────────────┼──────────────────┼──────────────────┤
│ 블록 수       │ 수만~수십만      │ 수십~수천         │
│ TX 릴레이     │ ❌               │ ✅ (선택적)      │
│ 병렬 다운로드 │ ✅ (필수)        │ ⚡ (선택적)      │
│ 서명 스킵     │ ✅ (체크포인트)  │ ❌ (전부 검증)   │
│ UTXO 배치     │ ✅               │ ❌ (즉시 적용)   │
│ 소요 시간     │ 분~시간          │ 초~분             │
│ Mempool       │ ❌ 비움          │ ✅ 유지           │
└───────────────┴──────────────────┴──────────────────┘
```

---

## 9. JackpotChain 동기화 전략

### 9.1 MVP (SSAFY)

```
환경:
  - 6개 노드 로컬 네트워크
  - 블록 높이: 최대 ~수만 블록 (6주 운영)
  - 블록 타임: 15초
  - 대역폭: 1 Gbps

동기화 시간 추정:
  블록 수: 6주 × 7일 × 24시간 × 240블록/시간 = ~242,000 블록
  헤더: 242,000 × 80 bytes = ~19 MB (1초)
  블록: 242,000 × ~100 KB (MVP) = ~24 GB
  
  다운로드 (1 Gbps): ~3분
  검증: ~5분
  총: ~8분

전략:
  ┌──────────────────────────────────┐
  │ ✅ Headers-First (필수)          │
  │ ✅ 병렬 다운로드 (3~5 피어)      │
  │ ✅ 체크포인트 (서명 스킵)         │
  │ ✅ UTXO 배치 업데이트            │
  │ ⏳ 진행률 표시                   │
  │ ❌ Pruning (불필요, 저장 충분)    │
  └──────────────────────────────────┘
```

---

### 9.2 구현 우선순위

```
Phase 1 (MVP 필수):
  [x] getheaders/headers 기반 헤더 동기화
  [x] Block Locator 생성
  [x] 순차 블록 다운로드 (단일 피어)
  [x] 블록 검증 & 체인 적용
  [x] IBD 모드 감지
  
Phase 2 (성능):
  [ ] 병렬 블록 다운로드 (다중 피어)
  [ ] 다운로드 윈도우 관리
  [ ] 타임아웃 & 재시도
  [ ] 체크포인트 기반 서명 스킵
  [ ] UTXO 배치 flush
  
Phase 3 (고급):
  [ ] Orphan Block Pool
  [ ] Catch-up 최적화
  [ ] 진행률 UI
  [ ] assumevalid 지원
```

---

## 10. 에지 케이스

### 10.1 동기화 중 포크

```
상황:
  IBD 중에 네트워크에서 포크 발생
  
  피어 A: ...→ 999 → 1000(A) → 1001(A)
  피어 B: ...→ 999 → 1000(B)

처리:
  1. 헤더 동기화 시 가장 긴 체인 선택
  2. 피어 A의 체인이 더 길면 A 따라감
  3. 나중에 B의 체인이 더 길어지면 Reorg

방어:
  여러 피어의 헤더를 비교
  → 대다수가 동의하는 체인 선택
```

---

### 10.2 악의적 피어

```
공격 1: 느린 응답
  피어가 일부러 느리게 응답
  → 타임아웃 후 다른 피어에게 재요청
  → 느린 피어 점수 하락

공격 2: 잘못된 블록
  헤더는 맞는데 블록 바디가 다름
  → 블록 해시 불일치로 즉시 감지
  → 피어 밴

공격 3: 무한 체인
  가짜 헤더를 계속 보냄 (PoW는 쉬운 난이도)
  → 난이도 확인으로 방어
  → 50블록마다 난이도 재계산 검증

공격 4: 체크포인트 우회
  체크포인트 높이에 다른 해시
  → 즉시 거부
```

---

### 10.3 디스크 공간 부족

```python
def check_disk_space():
    """동기화 전 디스크 공간 확인"""
    available = get_free_disk_space()
    chain_height = get_network_height()
    
    estimated_size = chain_height * AVG_BLOCK_SIZE  # ~100 KB/block
    utxo_size = chain_height * 50  # 대략적 UTXO 크기
    
    needed = estimated_size + utxo_size + BUFFER_1GB
    
    if available < needed:
        print(f"경고: 디스크 공간 부족!")
        print(f"필요: {needed / 1e9:.1f} GB")
        print(f"가용: {available / 1e9:.1f} GB")
        print(f"Pruning 모드를 권장합니다")
        return False
    
    return True
```

---

## 11. 핵심 요약

### 동기화 방식
```
Blocks-First (레거시):
  순차적, 단일 피어, 느림, DoS 취약

Headers-First (현재 표준):
  헤더 먼저 → 병렬 블록 다운로드
  빠르고 안전, 가짜 체인 조기 거부
```

### IBD 흐름
```
1. 피어 연결 & 핸드셰이크
2. 헤더 전체 다운로드 (getheaders × N회)
3. 헤더 체인 검증 (PoW, 연결, 난이도)
4. 블록 병렬 다운로드 (다중 피어, 윈도우)
5. 블록 순차 검증 & 체인 적용
6. UTXO Set 구축
7. Normal Sync 전환
```

### 최적화
```
- 체크포인트: 서명 스킵 (10배 빠름)
- 병렬 다운로드: N피어 동시 요청
- UTXO 배치: 디스크 I/O 감소
- 서명 캐싱: 중복 검증 방지
```

### Orphan 처리
```
부모 없는 블록 → Orphan Pool 임시 보관
부모 도착 → 해결 (연쇄 가능)
만료/과다 → 정리
PoW 검증 → 가짜 Orphan 방지
```

---

## 12. 체크리스트

이해했는지 확인:

- [ ] IBD, Normal Sync, Catch-up의 차이
- [ ] Blocks-First의 문제점
- [ ] Headers-First의 2단계 접근
- [ ] Block Locator의 동작 원리 (09 문서 복습)
- [ ] 병렬 블록 다운로드와 윈도우
- [ ] 블록 검증이 순차적이어야 하는 이유
- [ ] 체크포인트의 역할과 트레이드오프
- [ ] IBD 모드에서의 제한사항
- [ ] Orphan Block Pool 관리
- [ ] 악의적 피어 대응
- [ ] JackpotChain MVP 동기화 전략

---

## 13. 다음 학습

### 학습 완료:
- ✅ P2P 네트워크 기초
- ✅ 네트워크 프로토콜
- ✅ 블록 전파
- ✅ 동기화

### Phase 2 완료! 다음:
```
→ [12. 네트워크 보안](12-network-security.md) ✅ 완료

→ Phase 3: 고급
  → [13. 멀티에셋 시스템](../phase-3-advanced/13-multi-asset-system.md)
    - Asset Policy
    - Mint Transaction
    - Asset Registry
  
  → [14. 토크노믹스](../phase-3-advanced/14-tokenomics.md)
    - 블록 보상, 수수료, 소각
```

---

## 14. 참고 자료

**Bitcoin:**
- Bitcoin Developer Guide - Initial Block Download
- BIP 130: sendheaders message
- Bitcoin Core - validation.cpp (ActivateBestChain)

**구현:**
- Bitcoin Core - net_processing.cpp
- btcd - blockmanager.go
- libbitcoin - block_chain_impl.cpp

**최적화:**
- assumevalid (Bitcoin Core 0.14+)
- UTXO Set Commitments
- Headers Sync Improvements

---

**이전:** [10. 블록 전파](10-block-propagation.md)  
**다음:** [12. 네트워크 보안](12-network-security.md) →
