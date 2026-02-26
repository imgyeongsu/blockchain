# 10. 블록 전파 (Block Propagation)

> **Phase 2: Network**  
> **상태:** ✅ 완료  
> **학습 날짜:** 2025-02-19  
> **난이도:** ⭐⭐⭐☆☆  
> **예상 소요 시간:** 2-3시간  
> **선행 학습:** [09. 네트워크 프로토콜](09-network-protocol.md)

---

## 🎯 학습 목표

이 문서를 완료하면:
- [ ] Gossip Protocol의 작동 원리를 설명할 수 있다
- [ ] 블록 전파의 3가지 방식을 비교할 수 있다
- [ ] 전파 지연이 포크율에 미치는 영향을 이해한다
- [ ] Compact Block의 원리와 장점을 안다
- [ ] JackpotChain의 전파 전략을 설계할 수 있다
- [ ] TX 전파와 블록 전파의 차이를 이해한다

---

## 1. 왜 전파 속도가 중요한가?

### 1.1 전파 지연 = 포크

```
상황: 채굴자 A와 B가 거의 동시에 블록 발견

  채굴자 A (서울)         채굴자 B (부산)
      │                       │
      │ Block 1000(A) 발견    │ Block 1000(B) 발견
      │ 시각: 12:00:00.000    │ 시각: 12:00:00.200
      │                       │
      ├─→ 전파 시작            ├─→ 전파 시작
      │                       │
      │   ← 전파 지연 2초 →    │
      │                       │
  네트워크 분열!
    그룹 X: Block 1000(A)
    그룹 Y: Block 1000(B)
    
  → 포크 발생!
  → Longest Chain Rule로 해결 (06 문서 참조)
  → 해결될 때까지 1000(A) 또는 1000(B) 하나는 버려짐
```

---

### 1.2 JackpotChain에서 더 중요한 이유

```
Bitcoin:
  블록 타임: 10분 (600초)
  전파 시간: ~2초
  전파/블록 비율: 2/600 = 0.3%
  포크율: ~0.1% (매우 낮음)

JackpotChain:
  블록 타임: 15초
  전파 시간: ~2초 (목표)
  전파/블록 비율: 2/15 = 13.3%
  포크율: ~13% (허용 범위이지만 높음!)

결론:
  블록 타임이 짧을수록 전파 속도가 더 중요
  → 전파 최적화 필수!
```

---

### 1.3 전파 지연의 영향

```
전파 시간 vs 포크율 (15초 블록 타임):

  전파 시간 | 포크율  | 상태
  ─────────┼────────┼────────
  0.5초    | ~3%    | 매우 좋음
  1.0초    | ~6%    | 좋음
  2.0초    | ~13%   | 허용 범위 ✅
  3.0초    | ~18%   | 주의
  5.0초    | ~28%   | 위험!
  10초     | ~49%   | 사용 불가 ❌

계산:
  포크율 ≈ 1 - e^(-전파시간/블록타임)
  
  예: 2초 / 15초
  = 1 - e^(-0.133)
  ≈ 12.5%
```

---

## 2. Gossip Protocol

### 2.1 개념

```
비유: 소문 퍼지기

  Alice가 새 소문을 들음
    → Bob에게 말함
    → Bob이 Charlie에게 말함
    → Charlie가 Dave에게 말함
    → ...
  
  결과: 모든 사람이 소문을 알게 됨
  시간: O(log N) 홉 (N = 사람 수)
```

**블록체인에서:**
```
채굴자가 새 블록 발견
  → 연결된 피어 8개에게 알림
  → 각 피어가 자기 피어에게 알림
  → ...
  
전파 속도:
  6개 노드 (JackpotChain MVP):
    1홉이면 전체 도달 가능
    → ~100ms (로컬 네트워크)
  
  10,000개 노드 (대규모):
    ~4홉이면 대부분 도달
    → ~2-3초
```

---

### 2.2 전파 흐름

```
=== 단계별 전파 ===

Hop 0 (t=0):
  채굴자 노드가 블록 발견
  [Miner] ← 알고 있음
  
Hop 1 (t=100ms):
  Miner의 피어 8개에게 전파
  [Miner] → [A] [B] [C] [D] [E] [F] [G] [H]
  
  알고 있는 노드: 9개

Hop 2 (t=200ms):
  A~H 각각의 피어에게 전파 (중복 제외)
  최대 8 × 7 = 56개 새 노드
  
  알고 있는 노드: ~65개

Hop 3 (t=300ms):
  ~65 × 7 = ~455개 새 노드
  
  알고 있는 노드: ~520개

Hop 4 (t=400ms):
  대부분의 네트워크 도달

→ 기하급수적 확산!
→ O(log N) 시간에 전파
```

---

### 2.3 INV 기반 전파 (Legacy)

```
=== 기본 방식 (Bitcoin 초기) ===

Miner                           Node A
  │                               │
  │ ── inv (block_hash) ────────→ │  ① "이 블록 있어"
  │                               │     (36 bytes)
  │                               │
  │ ←── getdata (block_hash) ─── │  ② "그 블록 줘"
  │                               │     (36 bytes)
  │                               │
  │ ── block (full block) ──────→ │  ③ 블록 전송
  │                               │     (~1 MB)
  │                               │
  │                               │  ④ 검증 (~500ms)
  │                               │
  │                               │  ⑤ Node B에게 inv
  │                               │     (다음 홉 시작)

시간 분석 (1홉당):
  inv 전송:        ~10ms
  getdata 왕복:    ~100ms (RTT)
  블록 전송:       ~500ms (1 MB @ 2 MB/s)
  블록 검증:       ~500ms
  ────────────────────────
  총:              ~1.1초/홉

4홉이면: ~4.4초
→ JackpotChain 15초 블록에서 29% 포크율!
→ 너무 느림 ❌
```

---

### 2.4 직접 전송 방식 (Unsolicited Push)

```
=== inv 없이 바로 보내기 ===

Miner                           Node A
  │                               │
  │ ── block (full block) ──────→ │  ① 블록 바로 전송
  │                               │     (~1 MB)
  │                               │
  │                               │  ② 검증 (~500ms)
  │                               │
  │                               │  ③ Node B에게 바로 전송

시간 분석 (1홉당):
  블록 전송:       ~500ms
  블록 검증:       ~500ms
  ────────────────────────
  총:              ~1.0초/홉

장점: inv/getdata 왕복 제거
단점: 이미 있는 블록도 보냄 → 대역폭 낭비

절충안:
  첫 번째 피어: 직접 전송 (가장 빠른 피어에게)
  나머지 피어: inv 방식 (대역폭 절약)
```

---

## 3. Compact Block (BIP 152)

### 3.1 핵심 아이디어

```
관찰:
  블록의 TX 대부분은 이미 Mempool에 있음!
  
  블록: [TX1, TX2, TX3, ..., TX500]
  Mempool: [TX1, TX2, TX3, ..., TX498]
  
  겹침: 498/500 = 99.6%
  
아이디어:
  TX 전체 대신 TX ID만 보내면?
  → 수신자가 Mempool에서 직접 조립!
```

---

### 3.2 Compact Block 구조

```
일반 블록: ~1 MB
  ├─ Header: 80 bytes
  └─ TX 데이터: ~999,920 bytes

Compact Block: ~15-25 KB
  ├─ Header: 80 bytes
  ├─ nonce: 8 bytes (Short ID 계산용)
  ├─ short_ids[]: 6 bytes × N (TX ID 축약)
  ├─ prefilled_txs[]: Coinbase TX 등
  └─ 끝!

크기 비교:
  일반: 1,000,000 bytes
  Compact: ~20,000 bytes
  절감: 98%!

Short ID 계산:
  SipHash(tx_id, block_header + nonce)의 하위 6 bytes
  → 충돌 확률: 1/2^48 (매우 낮음)
```

---

### 3.3 Compact Block 전파 흐름

```
=== Low Bandwidth Mode ===

Miner                           Node A
  │                               │
  │ ── inv (MSG_CMPCT_BLOCK) ──→ │  ① "컴팩트 블록 있어"
  │                               │
  │ ←── getdata (CMPCT_BLOCK) ── │  ② "줘"
  │                               │
  │ ── cmpctblock ──────────────→ │  ③ 컴팩트 블록 (~20KB)
  │                               │
  │                               │  ④ Mempool에서 TX 조립
  │                               │     → 498/500 성공
  │                               │     → 2개 없음!
  │                               │
  │ ←── getblocktxn [idx 3, 87] ─│  ⑤ "3번, 87번 TX 줘"
  │                               │
  │ ── blocktxn [TX3, TX87] ────→ │  ⑥ 빠진 TX 전송
  │                               │
  │                               │  ⑦ 블록 조립 완료!
  │                               │     검증 시작


=== High Bandwidth Mode (HB) ===

Miner                           Node A (HB 모드)
  │                               │
  │ ── cmpctblock ──────────────→ │  ① inv 없이 바로!
  │                               │     (~20KB)
  │                               │
  │                               │  ② Mempool에서 조립
  │                               │     → 전부 있음!
  │                               │
  │                               │  ③ 블록 완성! 검증!

시간 분석 (HB, 1홉):
  컴팩트 블록 전송:  ~20ms (20KB)
  Mempool 조립:     ~50ms
  검증:             ~500ms
  ────────────────────────────
  총:               ~570ms/홉

vs 일반 블록: ~1.1초/홉
→ 약 2배 빠름!
```

---

### 3.4 Mempool 적중률의 중요성

```
적중률 = Mempool에 이미 있는 TX 비율

적중률 | 추가 요청 | 지연
──────┼──────────┼──────────
100%  | 없음     | 최소 (~20ms)
99%   | 5개 TX   | +50ms
95%   | 25개 TX  | +200ms
90%   | 50개 TX  | +500ms
50%   | 250개 TX | +3초 (거의 full block)

적중률 높이는 방법:
  1. TX를 빨리 전파 (블록보다 먼저)
  2. Mempool 동기화 잘하기
  3. 표준 TX만 중계 (비표준 제외)

JackpotChain:
  MVP 6노드 → 적중률 ~99% 기대
  (같은 로컬 네트워크, TX 전파 빠름)
```

---

### 3.5 Compact Block 의사코드

```python
class CompactBlock:
    def __init__(self, block):
        self.header = block.header
        self.nonce = random_uint64()
        
        # Short ID 생성
        self.short_ids = []
        for tx in block.transactions[1:]:  # Coinbase 제외
            sid = self._compute_short_id(tx.tx_id)
            self.short_ids.append(sid)
        
        # Coinbase TX는 항상 포함 (Mempool에 없으므로)
        self.prefilled_txs = [(0, block.transactions[0])]
    
    def _compute_short_id(self, tx_id):
        """6 bytes Short ID 계산"""
        key = sha256(self.header.serialize() + 
                     struct.pack('<Q', self.nonce))
        return siphash(key, tx_id)[:6]
    
    def serialize(self):
        result = self.header.serialize()     # 80 bytes
        result += struct.pack('<Q', self.nonce)  # 8 bytes
        result += encode_varint(len(self.short_ids))
        for sid in self.short_ids:
            result += sid                     # 6 bytes each
        result += encode_varint(len(self.prefilled_txs))
        for idx, tx in self.prefilled_txs:
            result += encode_varint(idx)
            result += tx.serialize()
        return result


class CompactBlockReceiver:
    def handle_cmpctblock(self, cmpct):
        """컴팩트 블록 수신 처리"""
        block = Block()
        block.header = cmpct.header
        
        # Prefilled TX 먼저 넣기
        for idx, tx in cmpct.prefilled_txs:
            block.transactions[idx] = tx
        
        # Mempool에서 Short ID 매칭
        missing = []
        for i, short_id in enumerate(cmpct.short_ids):
            tx = self.mempool.find_by_short_id(short_id, cmpct)
            if tx:
                block.transactions[i + 1] = tx
            else:
                missing.append(i + 1)
        
        if not missing:
            # 모든 TX 찾음! 바로 검증
            self.validate_block(block)
        else:
            # 빠진 TX 요청
            self.send(Message("getblocktxn", {
                "block_hash": cmpct.header.hash(),
                "indexes": missing
            }))
            self.pending_block = block
            self.pending_missing = missing
    
    def handle_blocktxn(self, msg):
        """빠진 TX 수신"""
        for i, tx in zip(self.pending_missing, msg.transactions):
            self.pending_block.transactions[i] = tx
        
        # 블록 완성! 검증
        self.validate_block(self.pending_block)
```

---

## 4. TX 전파 vs 블록 전파

### 4.1 차이점

```
┌───────────────┬──────────────────┬───────────────────┐
│               │ TX 전파           │ 블록 전파          │
├───────────────┼──────────────────┼───────────────────┤
│ 크기          │ ~500 bytes       │ ~1 MB             │
│ 긴급성        │ 보통             │ 매우 높음          │
│ 빈도          │ 매우 높음 (초당)  │ 15초마다 1회      │
│ 검증 비용     │ 낮음             │ 높음              │
│ 실패 영향     │ 작음 (재전송)     │ 큼 (포크!)        │
│ 전파 방식     │ inv → getdata    │ Compact / Direct  │
└───────────────┴──────────────────┴───────────────────┘
```

---

### 4.2 TX 전파 상세

```
=== TX Flooding ===

Alice가 TX 생성 → Node A에 제출

Node A:
  1. TX 검증 (형식 + Script + 서명)
  2. Mempool에 추가
  3. 연결된 피어에게 inv 전송

Node B (inv 수신):
  1. 이미 있나? → 있으면 무시
  2. 없으면 → getdata 요청
  3. TX 수신 → 검증
  4. 유효 → Mempool 추가 + 다른 피어에게 inv

특성:
  - 몇 초 안에 전체 네트워크 전파
  - 중복 inv 많음 (정상)
  - 검증 실패 TX는 전파 안 함
  - 수수료 너무 낮은 TX도 전파 안 함
```

---

### 4.3 TX 전파 제어

```python
class TxRelay:
    """TX 중계 관리"""
    
    def __init__(self):
        self.min_fee_rate = 0.001  # 최소 수수료율 (JACK/byte)
        self.relay_set = {}        # {peer: set(tx_hash)} 이미 알린 TX
    
    def should_relay(self, tx):
        """이 TX를 중계할지 결정"""
        # 수수료 확인
        fee_rate = tx.fee / tx.size
        if fee_rate < self.min_fee_rate:
            return False
        
        # 크기 확인
        if tx.size > MAX_TX_SIZE:
            return False
        
        # 표준 TX인지
        if not tx.is_standard():
            return False
        
        return True
    
    def relay_to_peer(self, peer, tx):
        """특정 피어에게 TX 알림"""
        if tx.hash in self.relay_set.get(peer.id, set()):
            return  # 이미 알림
        
        peer.send(Message("inv", [InvItem(MSG_TX, tx.hash)]))
        self.relay_set.setdefault(peer.id, set()).add(tx.hash)
```

---

## 5. 블록 전파 최적화

### 5.1 검증 파이프라이닝

```
문제:
  블록 수신 → 전체 검증 → 전파
  검증에 500ms 걸리면 전파가 500ms 늦어짐

해결: 검증과 전파를 동시에!

  기존:
    수신 → [검증 500ms] → 전파
    
  파이프라이닝:
    수신 → [헤더 검증 10ms] → 전파 시작!
                   ↓
         [전체 검증 500ms]
                   ↓
         유효: 정상
         무효: 전파 취소 + 피어에게 알림

위험:
  무효 블록을 전파할 수 있음
  → 헤더 검증 (PoW)만 통과하면 대부분 유효
  → 실제 무효 블록은 매우 드묾
```

---

### 5.2 전파 우선순위

```python
class BlockPropagation:
    """블록 전파 관리"""
    
    def on_new_block(self, block):
        """새 블록 수신/생성 시"""
        
        # 1. 헤더만 빠르게 검증
        if not self.quick_validate_header(block.header):
            return  # 무효 헤더
        
        # 2. 피어 우선순위 결정
        peers = self.get_connected_peers()
        
        # 가장 빠른 피어 3개: Compact Block (HB 모드)
        fast_peers = sorted(peers, key=lambda p: p.latency_ms)[:3]
        for peer in fast_peers:
            cmpct = CompactBlock(block)
            peer.send(Message("cmpctblock", cmpct.serialize()))
        
        # 나머지 피어: inv 방식
        rest_peers = [p for p in peers if p not in fast_peers]
        inv_msg = Message("inv", [InvItem(MSG_BLOCK, block.hash())])
        for peer in rest_peers:
            peer.send(inv_msg)
        
        # 3. 전체 검증 (병렬로)
        self.full_validate_async(block)
    
    def quick_validate_header(self, header):
        """빠른 헤더 검증"""
        # PoW 확인 (hash < target)
        if header.hash() >= header.target:
            return False
        
        # prev_hash 연결 확인
        if not self.chain.has_block(header.prev_hash):
            return False  # Orphan이면 따로 처리
        
        # timestamp 범위
        if header.timestamp > time.time() + 7200:
            return False
        
        return True
```

---

### 5.3 전파 지연 최소화 전략

```
=== 레이어별 최적화 ===

Layer 1: 네트워크
  - 피어와 지리적으로 가까운 연결 유지
  - 낮은 레이턴시 피어 우선
  - TCP Nagle 알고리즘 비활성화 (TCP_NODELAY)
  
Layer 2: 프로토콜
  - Compact Block 사용
  - High Bandwidth 모드 (inv 생략)
  - 검증 파이프라이닝
  
Layer 3: 검증
  - 헤더만 빠르게 검증 후 전파
  - 전체 검증은 병렬로
  - 서명 검증 캐싱
  - UTXO 조회 캐싱

Layer 4: 저장
  - 블록 저장과 전파를 분리
  - 메모리에서 먼저 전파
  - 디스크 쓰기는 나중에 배치
```

---

## 6. 포크와 전파의 관계

### 6.1 자연 포크 (Natural Fork)

```
=== 동시 채굴 시나리오 ===

시간  채굴자 A        네트워크        채굴자 B
────┼────────────────────────────────────────
0s   Block 1000(A)                  Block 1000(B)
     발견!                           발견!

1s   전파 중...                      전파 중...
     A→C→D                          B→E→F

2s   ┌─────────────────────────────────────┐
     │  네트워크 분열                       │
     │  그룹 X: A,C,D (1000A 지지)         │
     │  그룹 Y: B,E,F (1000B 지지)         │
     └─────────────────────────────────────┘

15s  채굴자 C가 1001 발견!
     → prev_hash = 1000(A)
     → 체인: ...→ 999 → 1000(A) → 1001

16s  1001이 전체 네트워크에 전파
     → 그룹 Y도 확인:
       1000(A) → 1001 (길이 2) vs 1000(B) (길이 1)
     → Longest Chain Rule!
     → 1000(B) 버림 (Stale Block)
     → 1000(B)의 TX는 다시 Mempool로

→ 포크 해결! (~15초 소요)
```

---

### 6.2 Stale Block 처리

```python
class ForkHandler:
    """포크 감지 및 처리"""
    
    def handle_new_block(self, block):
        """새 블록 수신"""
        tip = self.chain.get_tip()
        
        # Case 1: 체인 연장 (정상)
        if block.header.prev_hash == tip.hash():
            self.chain.append(block)
            self.update_utxo_set(block)
            return
        
        # Case 2: 같은 높이 (포크!)
        if block.height == tip.height:
            # 양쪽 다 보관
            self.chain.add_fork(block)
            print(f"포크 감지! height={block.height}")
            # 다음 블록이 결정할 것
            return
        
        # Case 3: 더 긴 체인 발견 (재조직!)
        if block.height > tip.height:
            self.reorganize(block)
            return
        
        # Case 4: 짧은 체인 (무시)
        if block.height < tip.height - 12:
            return  # 너무 오래된 블록
    
    def reorganize(self, new_tip):
        """체인 재조직 (Reorg)"""
        # 분기점 찾기
        fork_point = self.find_fork_point(self.chain.tip, new_tip)
        
        # 기존 블록들 되돌리기
        blocks_to_undo = self.chain.get_blocks_since(fork_point)
        for block in reversed(blocks_to_undo):
            self.undo_block(block)  # Undo 데이터 사용 (07 문서 참조)
        
        # 새 블록들 적용
        blocks_to_apply = self.get_chain_to(new_tip, fork_point)
        for block in blocks_to_apply:
            self.apply_block(block)
        
        # 되돌린 블록의 TX → Mempool로
        for block in blocks_to_undo:
            for tx in block.transactions[1:]:  # Coinbase 제외
                if not self.is_in_new_chain(tx):
                    self.mempool.add(tx)
```

---

### 6.3 JackpotChain 포크 관리

```
포크율 13% 의미:
  100블록 중 ~13개에서 포크 발생
  → 대부분 1블록 안에 해결 (다음 블록이 결정)
  → 2블록 이상 포크: 매우 드묾 (~1.7%)
  → 3블록 이상 포크: 거의 없음 (~0.2%)

확정성 (06 문서 복습):
  1 확인 (15초):  ~13% 위험
  6 확인 (1.5분): ~0.1% 위험
  12 확인 (3분):  ~0.0001% 위험 ✅ (권장)

MVP 실용 가이드:
  소액 TX: 1 확인이면 충분
  일반 TX: 6 확인 권장
  가챠/교환: 12 확인 권장
```

---

## 7. Orphan Block 처리

### 7.1 Orphan Block이란?

```
정의: 부모 블록이 아직 도착하지 않은 블록

상황:
  Block 999 → Block 1000 → Block 1001
  
  1001이 1000보다 먼저 도착!
  → 1001의 prev_hash가 가리키는 1000이 없음
  → 1001은 "고아 블록" (Orphan)

원인:
  - 네트워크 지연 (순서 역전)
  - 피어가 다른 경로로 전파
  - 동기화 중 빠진 블록
```

---

### 7.2 처리 방법

```python
class OrphanBlockPool:
    """고아 블록 임시 보관"""
    
    def __init__(self):
        self.orphans = {}         # {block_hash: block}
        self.by_parent = {}       # {parent_hash: [block_hash]}
        self.max_orphans = 100
    
    def add(self, block):
        """고아 블록 추가"""
        if len(self.orphans) >= self.max_orphans:
            self._evict_oldest()
        
        block_hash = block.hash()
        parent_hash = block.header.prev_hash
        
        self.orphans[block_hash] = block
        self.by_parent.setdefault(parent_hash, []).append(block_hash)
        
        # 부모 블록 요청
        self.request_block(parent_hash)
    
    def check_resolved(self, new_block_hash):
        """새 블록이 도착하면 고아가 해결되는지 확인"""
        resolved = []
        
        if new_block_hash in self.by_parent:
            for orphan_hash in self.by_parent[new_block_hash]:
                orphan = self.orphans.pop(orphan_hash)
                resolved.append(orphan)
            del self.by_parent[new_block_hash]
        
        # 연쇄 해결 (고아의 자식도 고아일 수 있음)
        for block in resolved:
            self.check_resolved(block.hash())
        
        return resolved
```

---

## 8. JackpotChain 전파 전략

### 8.1 MVP (SSAFY 로컬 네트워크)

```
환경:
  - 6개 노드 (같은 LAN)
  - 레이턴시 < 1ms
  - 대역폭 ~1 Gbps

전략:
  ┌──────────────────────────────────┐
  │ ✅ 직접 전송 (Unsolicited Push) │
  │   → 6개 노드라 대역폭 부담 없음  │
  │   → inv 왕복 생략               │
  │   → 전파 시간 ~10ms             │
  │                                  │
  │ ❌ Compact Block 불필요          │
  │   → 로컬 네트워크라 전송 빠름    │
  │   → 구현 복잡도 대비 효과 작음   │
  │                                  │
  │ ✅ 헤더 먼저 검증                │
  │   → 무효 블록 빠르게 거부        │
  └──────────────────────────────────┘

예상 전파 시간:
  블록 전송: ~10ms (1 MB @ 1 Gbps)
  검증: ~200ms
  총: ~210ms
  
  포크율: ~1.4% (매우 낮음!)
```

---

### 8.2 확장 (AWS + 외부 노드)

```
환경:
  - 6개 로컬 + AWS 브릿지 + 외부 노드
  - 레이턴시 10-100ms
  - 대역폭 가변

전략:
  ┌──────────────────────────────────┐
  │ 로컬 ↔ 로컬: 직접 전송           │
  │ 로컬 ↔ AWS: Compact Block       │
  │ AWS ↔ 외부: Compact Block + HB   │
  └──────────────────────────────────┘

피어 분류:
  Fast Peers (RTT < 10ms):
    → 직접 전송 또는 HB Compact Block
    
  Medium Peers (RTT 10-100ms):
    → Compact Block (Low Bandwidth)
    
  Slow Peers (RTT > 100ms):
    → inv 방식 (대역폭 절약)
```

---

### 8.3 구현 로드맵

```
Phase 1 (MVP):
  [x] inv/getdata 기본 전파
  [x] 직접 전송 (로컬 피어)
  [x] 기본 포크 처리
  [x] Orphan Block Pool
  
Phase 2 (최적화):
  [ ] Compact Block
  [ ] High Bandwidth 모드
  [ ] 검증 파이프라이닝
  [ ] 피어별 레이턴시 측정
  
Phase 3 (고급):
  [ ] 블록 압축
  [ ] 병렬 블록 다운로드
  [ ] 전파 경로 최적화
```

---

## 9. 전파 모니터링

### 9.1 측정 지표

```python
class PropagationMetrics:
    """전파 성능 측정"""
    
    def __init__(self):
        self.block_times = []      # 블록 수신 시간
        self.fork_count = 0
        self.orphan_count = 0
        self.stale_count = 0
    
    def on_block_received(self, block, receive_time, source_peer):
        """블록 수신 시 기록"""
        propagation_delay = receive_time - block.header.timestamp
        
        self.block_times.append({
            "height": block.height,
            "delay_ms": propagation_delay * 1000,
            "source": source_peer.id,
            "size": len(block.serialize())
        })
    
    def get_stats(self):
        """통계 반환"""
        delays = [b["delay_ms"] for b in self.block_times[-100:]]
        
        return {
            "avg_delay_ms": sum(delays) / len(delays),
            "median_delay_ms": sorted(delays)[len(delays)//2],
            "max_delay_ms": max(delays),
            "fork_rate": self.fork_count / len(self.block_times),
            "orphan_rate": self.orphan_count / len(self.block_times),
        }
```

---

### 9.2 모니터링 예시

```
=== Block Propagation Stats (최근 100블록) ===

전파 지연:
  평균:   180ms
  중앙값: 150ms
  최대:   890ms

포크:
  발생:   8/100 (8%)
  해결:   모두 1블록 안에 해결

고아 블록:
  발생:   2/100 (2%)
  해결:   모두 5초 이내

Stale Block:
  발생:   8/100 (기존 포크)
  TX 복구: 100% (모두 Mempool로 복귀)

피어별 전파 속도:
  10.0.1.101:  avg 50ms  ★ 가장 빠름
  10.0.1.102:  avg 80ms
  10.0.1.103:  avg 120ms
  10.0.1.104:  avg 150ms
  10.0.1.105:  avg 200ms
```

---

## 10. 핵심 요약

### Gossip Protocol
```
- 기하급수적 확산: O(log N) 홉
- 각 노드가 피어에게 전달
- 중복은 inv로 방지
```

### 전파 방식 비교
```
방식           | 크기    | 지연   | 복잡도
───────────────┼────────┼───────┼────────
Legacy (INV)   | 1 MB   | 높음  | 낮음
직접 전송       | 1 MB   | 중간  | 낮음
Compact Block  | 20 KB  | 낮음  | 높음
```

### JackpotChain 핵심
```
블록 타임 15초 → 전파 최적화 필수
MVP: 직접 전송 (로컬 네트워크)
확장: Compact Block + HB 모드
포크율 ~13% → 12 확인으로 확정
```

### 포크 처리
```
Longest Chain Rule로 해결
Stale Block TX → Mempool 복귀
Orphan Block → 부모 도착 시 해결
Reorg → Undo 데이터로 롤백
```

---

## 11. 체크리스트

이해했는지 확인:

- [ ] 전파 지연이 포크율에 미치는 영향
- [ ] Gossip Protocol의 O(log N) 확산
- [ ] Legacy INV 방식의 지연 구조
- [ ] Compact Block의 원리 (Short ID + Mempool 조립)
- [ ] High Bandwidth vs Low Bandwidth 모드
- [ ] Mempool 적중률의 중요성
- [ ] TX 전파와 블록 전파의 차이
- [ ] 검증 파이프라이닝 개념
- [ ] 자연 포크 발생과 해결 과정
- [ ] Orphan Block 처리 방법
- [ ] Stale Block의 TX 복구
- [ ] JackpotChain MVP 전파 전략

---

## 12. 다음 학습

### 학습 완료:
- ✅ P2P 네트워크 기초
- ✅ 네트워크 프로토콜
- ✅ 블록 전파

### 다음 추천:
```
→ [11. 동기화](11-synchronization.md)
  - Initial Block Download (IBD)
  - Headers-First Sync 상세
  - Orphan Block 처리 심화
  - 체크포인트

→ [12. 네트워크 보안](12-network-security.md) ✅ 완료
  - Eclipse Attack
  - Selfish Mining
  - Block Withholding
```

---

## 13. 참고 자료

**Bitcoin:**
- BIP 130: sendheaders
- BIP 152: Compact Block Relay
- Bitcoin Developer Guide - Block Broadcasting

**논문:**
- "Information Propagation in the Bitcoin Network" (Decker & Wattenhofer, 2013)
- "On the Security and Performance of PoW Blockchains" (Gervais et al., 2016)

**구현:**
- Bitcoin Core - net_processing.cpp (ProcessNewBlock)
- Bitcoin Core - blockencodings.cpp (Compact Block)

---

**이전:** [09. 네트워크 프로토콜](09-network-protocol.md)  
**다음:** [11. 동기화](11-synchronization.md) →
