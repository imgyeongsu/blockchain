# 19. 저장소 설계 (Storage Design)

> **Phase 4: Optimization**  
> **학습 날짜:** 2025-02-19  
> **난이도:** ⭐⭐⭐☆☆  
> **예상 소요 시간:** 1.5-2시간  
> **선행 학습:** [07. UTXO Set 관리](../phase-1-core/07-utxo-set-management.md), [18. 성능 최적화](18-performance-optimization.md)

---

## 🎯 학습 목표

이 문서를 완료하면:
- [ ] 노드가 저장해야 하는 데이터 전체를 파악할 수 있다
- [ ] Key-Value 저장소 (LevelDB)의 특성을 이해한다
- [ ] DB 스키마 (Key 설계)를 설계할 수 있다
- [ ] 인덱싱 전략과 트레이드오프를 안다
- [ ] Pruning의 원리와 절감 효과를 계산할 수 있다
- [ ] Reorg 시 Undo 데이터의 역할을 이해한다

---

## 1. 저장 데이터 전체 목록

### 1.1 전체 그림

```
디스크에 저장하는 것:

  1. 블록 데이터 — 헤더 + 바디 (체인 전체 기록)
  2. UTXO Set — 현재 소비 가능한 모든 Output
  3. 인덱스 — 주소→UTXO, TX→블록, 높이→해시, 잭팟 풀
  4. Undo 데이터 — Reorg 롤백용 (소비된 UTXO 원본)
  5. 체인 상태 — Best Block, 난이도, 누적 Work
  6. 피어 데이터 — 주소 목록, 점수, Ban 목록

메모리에만 있는 것 (재시작 시 소멸):
  Mempool, Orphan Pool, 각종 캐시
```

### 1.2 크기 추정 (6주 MVP)

```
┌──────────────────────┬───────────┬───────────────────┐
│ 데이터               │ 크기      │ 비고              │
├──────────────────────┼───────────┼───────────────────┤
│ 블록 데이터          │ ~5 GB     │ 242K블록, 압축 후 │
│ UTXO Set             │ ~200 MB   │ 압축 후           │
│ 인덱스               │ ~200 MB   │ 주소+TX+블록      │
│ Undo 데이터          │ ~115 MB   │ 최근 288블록만    │
│ 체인 상태 + 피어     │ ~1 MB     │ 무시할 수준       │
├──────────────────────┼───────────┼───────────────────┤
│ 합계                 │ ~5.5 GB   │                   │
│ Pruning 적용 시      │ ~1 GB     │ 블록 바디 제거    │
└──────────────────────┴───────────┴───────────────────┘
```

---

## 2. Key-Value 저장소

### 2.1 왜 Key-Value인가?

```
블록체인 데이터 특성:
  대부분 "키로 조회" (해시→블록, UTXO키→UTXO)
  관계형 JOIN 불필요
  쓰기가 많음 (매 블록마다 수천 건)

관계형 DB (MySQL):
  ❌ 과도한 기능, 오버헤드, 쓰기 느림

Key-Value DB (LevelDB):
  ✅ 단순 인터페이스 (get, put, delete)
  ✅ 쓰기 최적화 (LSM Tree)
  ✅ Bitcoin Core가 사용
  ✅ 임베디드 (별도 서버 불필요)
```

### 2.2 LevelDB vs RocksDB

```
┌─────────────────┬──────────────────┬──────────────────┐
│                 │ LevelDB          │ RocksDB          │
├─────────────────┼──────────────────┼──────────────────┤
│ 개발            │ Google           │ Meta (Facebook)  │
│ 사용            │ Bitcoin Core     │ Ethereum Geth    │
│ 동시 접근       │ 단일 프로세스    │ 멀티 스레드      │
│ 성능            │ 좋음             │ 더 좋음 (대규모) │
│ 복잡도          │ 단순             │ 설정 많음        │
└─────────────────┴──────────────────┴──────────────────┘

MVP 선택: LevelDB → 단순, 가볍, 충분
→ 나중에 RocksDB로 교체 가능 (API 유사)
```

### 2.3 LSM Tree 간단 이해

```
LSM Tree = LevelDB/RocksDB의 핵심 자료구조

쓰기:
  put(key, value)
  → MemTable (메모리)에 기록
  → 가득 차면 → SSTable (디스크)로 플러시
  → SSTable 쌓이면 → 백그라운드 Compaction (병합)

읽기:
  get(key)
  → MemTable 확인 → 없으면 SSTable 순서대로 검색
  → Bloom Filter로 "확실히 없는 파일" 스킵

특성:
  쓰기 매우 빠름 (순차 쓰기)
  읽기 보통~빠름
  → 블록체인에 적합 (매 블록 수천 건 쓰기)
```

---

## 3. DB 스키마 (Key 설계)

### 3.1 설계 원칙

```
1. Prefix로 데이터 유형 구분
   'b' = 블록, 'u' = UTXO, 'a' = 주소, 't' = TX 등

2. Key는 바이트 배열 (문자열보다 효율적)

3. 관련 데이터는 Key 정렬로 묶이게
   → LevelDB는 Key 순서 정렬
   → 같은 prefix = 물리적 근접 → 범위 스캔 빠름
```

### 3.2 전체 스키마

```
=== 블록 헤더 ===
Key:   'h' + block_hash (32 bytes)
Value: 직렬화된 블록 헤더 (80 bytes)

=== 블록 바디 ===
Key:   'b' + block_hash (32 bytes)
Value: 직렬화된 TX 목록 (가변)

=== 블록 높이 → 해시 ===
Key:   'n' + block_height (4 bytes, Big-Endian)
Value: block_hash (32 bytes)
→ Big-Endian: 높이 순서 = 사전 순서 → 범위 스캔 가능

=== UTXO ===
Key:   'u' + tx_id (32 bytes) + output_index (4 bytes)
Value: jack_value + assets + script_pubkey + block_height
→ 07번 §2 참조

=== 주소 인덱스 ===
Key:   'a' + address_hash (20 bytes) + tx_id (32) + output_index (4)
Value: (빈 값 또는 1 byte flag)
→ prefix scan으로 해당 주소의 모든 UTXO 조회

=== TX 인덱스 ===
Key:   't' + tx_id (32 bytes)
Value: block_hash (32) + offset (4)
→ TX가 어떤 블록에 있는지 조회

=== 잭팟 풀 인덱스 ===
Key:   'j' + tx_id (32 bytes) + output_index (4 bytes)
Value: jack_value (8 bytes)
→ prefix scan 'j'로 풀 전체 잔액 조회

=== Undo 데이터 ===
Key:   'd' + block_hash (32 bytes)
Value: 해당 블록에서 소비된 UTXO들의 원본 목록

=== 체인 상태 ===
Key:   'c' + 'best'  → Value: block_hash + height
Key:   'c' + 'work'  → Value: total_chainwork
Key:   'c' + 'diff'  → Value: current_difficulty
```

---

## 4. 데이터베이스 분리

### 4.1 분리 전략

```
모든 데이터를 하나의 DB에 넣으면?
  → UTXO 조회와 블록 읽기가 서로 간섭
  → Compaction이 전체에 영향

MVP 분리 (2개):

  DB 1: blocks_db
    - 블록 헤더 + 바디 ('h', 'b', 'n')
    - Undo 데이터 ('d')
    → 쓰기 위주, 순차적, 크기 큼

  DB 2: state_db
    - UTXO Set ('u')
    - 체인 상태 ('c')
    - 인덱스 ('a', 't', 'j')
    → 읽기/쓰기 균형, 랜덤 접근

Bitcoin Core도 유사하게 분리:
  blocks/ → 블록 파일
  chainstate/ → UTXO Set (LevelDB)
```

---

## 5. 인덱싱 전략

### 5.1 인덱스 종류와 우선순위

```
┌────────────────┬────────────────┬──────────┬──────────────┐
│ 인덱스         │ 용도           │ 크기     │ 필수 여부    │
├────────────────┼────────────────┼──────────┼──────────────┤
│ 주소 인덱스    │ 잔액 조회      │ ~100 MB  │ ✅ 필수     │
│ 블록 높이→해시 │ 높이로 블록조회│ ~1 MB    │ ✅ 필수     │
│ 잭팟 인덱스    │ 풀 잔액 조회   │ ~5 MB    │ ✅ 필수     │
│ TX 인덱스      │ TX 검색        │ ~80 MB   │ ⬜ 선택     │
│ 에셋 인덱스    │ 에셋별 UTXO    │ ~50 MB   │ ⬜ 선택     │
└────────────────┴────────────────┴──────────┴──────────────┘

트레이드오프:
  인덱스 많으면 → 조회 빠름, 쓰기 느려짐, 디스크 더 사용
  인덱스 적으면 → 조회 느림, 쓰기 빠름, 디스크 절약

MVP: 필수만 구현
→ 07번 §6 참조 (인덱싱 전략 상세)
```

### 5.2 원자적 업데이트

```
블록 적용 시 모든 인덱스를 함께 업데이트:

  UTXO Set 변경
  + 주소 인덱스 변경
  + 잭팟 인덱스 변경
  + (TX 인덱스 변경)
  → 모두 같은 Batch Write!

왜?
  UTXO는 업데이트됐는데 인덱스가 안 되면?
  → 잔액 조회 결과가 틀림!
  → Batch Write = 전부 성공 또는 전부 실패 (원자적)
```

---

## 6. Pruning

### 6.1 개념

```
Pruning = 오래된 블록 바디를 삭제하여 디스크 절약

블록 데이터 (~5 GB) = 전체의 ~90%
하지만 TX 검증에는 UTXO Set만 있으면 됨
→ 과거 블록 바디는 "기록"일 뿐
```

### 6.2 전략

```
MVP 권장: 헤더 유지 + 바디 Pruning

보관:
  블록 헤더: 전체 (80 bytes × 121,000 = ~10 MB)
  블록 바디: 최근 288블록만 (~14 MB)
  Undo 데이터: 최근 288블록만 (~115 MB)

삭제:
  288블록보다 오래된 블록 바디

효과:
  5 GB → ~150 MB (97% 절약!)

Pruning 해도 가능:
  ✅ 새 TX/블록 검증 (UTXO Set 유지)
  ✅ 채굴
  ✅ 최근 Reorg 처리
  ✅ 헤더 체인 검증

Pruning 하면 불가:
  ❌ 과거 TX 상세 조회
  ❌ 다른 노드에게 과거 블록 전달 (IBD 지원 불가)
  ❌ 과거 시점 UTXO 재구성
```

---

## 7. Undo 데이터와 Reorg

### 7.1 Undo 데이터란?

```
Reorg 시나리오:
  현재: ... → A → B → C (Best)
  새:   ... → A → B' → C' → D' (더 긴!)
  → C를 롤백해야 함

C 롤백하려면:
  C에서 소비된 UTXO들을 복원해야 함
  → 이미 UTXO Set에서 삭제됨!
  → Undo 데이터에 저장해둔 원본으로 복원

→ 07번 §4 참조
```

### 7.2 생성과 사용

```
블록 적용 시:
  Input UTXO 삭제 전 → Undo에 원본 저장
  Key: 'd' + block_hash
  Value: [소비된 UTXO 원본들]

Reorg 시:
  1. Undo 데이터 읽기
  2. 해당 블록에서 생성된 UTXO 삭제
  3. Undo의 원본 UTXO 복원
  → UTXO Set이 이전 블록 상태로 돌아감

보관 기간:
  최근 288블록만 (288 이상 Reorg는 사실상 불가능)
  새 블록마다 → (현재 - 289)의 Undo 삭제
```

---

## 8. 디스크 레이아웃

### 8.1 디렉토리 구조

```
jackpotchain/
├── data/
│   ├── blocks/              ← DB 1: 블록 데이터
│   │   ├── 000001.ldb
│   │   ├── MANIFEST-000001
│   │   └── LOG
│   │
│   ├── state/               ← DB 2: 상태 데이터
│   │   ├── 000001.ldb
│   │   ├── MANIFEST-000001
│   │   └── LOG
│   │
│   └── peers.json           ← 피어 목록
│
├── config/
│   ├── genesis.json          ← Genesis Block 정의
│   └── config.toml           ← 노드 설정
│
└── logs/
    └── node.log
```

### 8.2 Genesis Block

```
genesis.json — 모든 노드의 동일한 시작점

{
  "version": 1,
  "prev_block_hash": "0000...0000",
  "timestamp": 1739369400,
  "difficulty_target": "0x1d00ffff",
  "nonce": 0,
  "transactions": [{
    "type": "coinbase",
    "outputs": [{
      "jack_value": 5000000000,
      "address": "<초기 채굴자 주소>"
    }]
  }]
}

같은 Genesis = 같은 네트워크
다른 Genesis = 다른 체인 (포크)
```

---

## 9. 읽기/쓰기 패턴

### 9.1 평시

```
30초마다 블록 1개:

쓰기: 블록 저장 1회, UTXO Batch 1회, 인덱스 Batch 1회
읽기: UTXO 수천 회 (대부분 캐시 히트)

패턴: 쓰기 집중 → LSM Tree에 적합
```

### 9.2 IBD

```
연속 블록 처리:

쓰기: 초당 수만 건 UTXO 업데이트
읽기: 초당 수만 건 UTXO 조회

패턴: 읽기/쓰기 동시 폭발
→ Batch flush 주기 조정이 핵심 (100블록마다)
→ 11번 §5 참조
```

### 9.3 가챠 검증

```
Reveal TX 검증 시:

읽기:
  1. Commit UTXO 조회
  2. Commit 블록 해시 조회 (높이→해시 인덱스)
  3. 잭팟 풀 잔액 조회 (잭팟 인덱스 scan)
  4. 잭팟 풀 UTXO 목록 조회

쓰기:
  당첨 시 잭팟 UTXO 소비 + 당첨금 UTXO 생성

→ 잭팟 인덱스가 없으면 풀 잔액 조회에 전체 UTXO 스캔 필요
→ 별도 인덱스의 가치가 여기서 드러남
```

---

## 10. 데이터 무결성

### 10.1 비정상 종료 대응

```
문제:
  블록 적용 도중 프로세스 크래시
  → UTXO는 일부 업데이트, 인덱스는 미업데이트
  → 불일치 상태!

방어:

  1. Batch Write (LevelDB의 원자적 쓰기)
     한 블록의 모든 변경사항을 하나의 Batch에
     → 전부 성공 또는 전부 실패
     → 중간 상태 없음

  2. WAL (Write-Ahead Log)
     LevelDB가 내부적으로 사용
     → 쓰기 전에 로그에 먼저 기록
     → 크래시 후 로그에서 복구

  3. 재시작 시 검증
     체인 상태의 Best Block 확인
     → 마지막으로 완전히 적용된 블록부터 재개
     → 불완전한 블록은 다시 적용
```

### 10.2 데이터 검증

```
주기적 무결성 확인:

  UTXO Set 검증:
    전체 UTXO를 순회하며
    → 모든 UTXO의 block_height ≤ Best Block?
    → 주소 인덱스와 일치?
    → 잭팟 인덱스와 일치?

  블록 체인 검증:
    Genesis → Best Block까지
    → prev_block_hash 연결 확인
    → 높이 인덱스 일관성

MVP: 시작 시 1회 검증, 이후 Batch Write로 일관성 보장
```

---

## 11. MVP 구현 가이드

### 11.1 구현 우선순위

```
Phase 1 (필수):
  ✅ LevelDB 셋업 (blocks_db + state_db)
  ✅ 블록 저장/조회
  ✅ UTXO Set 기본 (put, get, delete)
  ✅ 체인 상태 저장
  ✅ Genesis Block 로딩

Phase 2 (인덱스):
  ✅ 주소 인덱스 (잔액 조회)
  ✅ 블록 높이→해시 인덱스
  ✅ 잭팟 풀 인덱스
  ✅ Batch Write (원자적 업데이트)

Phase 3 (안정성):
  ✅ Undo 데이터 (Reorg 지원)
  ✅ UTXO 캐시 (LRU)
  ⬜ TX 인덱스 (선택)
  ⬜ Pruning (선택)
```

### 11.2 설정 파라미터

```
config.toml:

[storage]
  blocks_db_path = "./data/blocks"
  state_db_path = "./data/state"
  
  utxo_cache_size = 50000        # UTXO 캐시 엔트리 수
  batch_flush_interval = 1       # 몇 블록마다 flush (평시)
  ibd_flush_interval = 100       # IBD 시 flush 주기
  
  undo_keep_blocks = 288         # Undo 보관 블록 수
  pruning_enabled = false        # Pruning 활성화
  pruning_keep_blocks = 288      # Pruning 시 보관 블록 수

[index]
  address_index = true           # 주소 인덱스
  tx_index = false               # TX 인덱스 (선택)
  jackpot_index = true           # 잭팟 인덱스
```

---

## 12. 핵심 요약

### 저장 데이터
```
블록(~5GB) + UTXO(~200MB) + 인덱스(~200MB) + Undo(~115MB)
합계 ~5.5GB, Pruning 시 ~1GB
```

### Key-Value DB
```
LevelDB: 단순, 쓰기 최적화, Bitcoin과 동일
LSM Tree: 쓰기 빠름, 읽기 Bloom Filter로 보완
DB 2개 분리: blocks_db + state_db
```

### 스키마
```
'h'+hash = 헤더, 'b'+hash = 바디
'u'+txid+idx = UTXO, 'a'+addr+txid+idx = 주소 인덱스
'j'+txid+idx = 잭팟 인덱스, 'd'+hash = Undo
'c'+key = 체인 상태
```

### Pruning
```
블록 바디 삭제 → 97% 절약
헤더 + UTXO Set + Undo(최근 288) 유지
검증/채굴 가능, 과거 TX 조회 불가
```

### 무결성
```
Batch Write: 원자적 업데이트
WAL: 크래시 복구
Undo: Reorg 롤백 (최근 288블록)
```

---

## 13. 체크리스트

이해했는지 확인:

- [ ] 노드가 저장하는 6가지 데이터 종류
- [ ] Key-Value DB를 선택한 이유
- [ ] LSM Tree의 쓰기/읽기 특성
- [ ] LevelDB vs RocksDB 차이
- [ ] Key prefix 설계 원칙
- [ ] DB 2개 분리 이유 (blocks vs state)
- [ ] 필수 인덱스 3가지 (주소, 높이, 잭팟)
- [ ] Batch Write의 원자성이 중요한 이유
- [ ] Pruning의 절약 효과와 기능 제한
- [ ] Undo 데이터의 역할과 보관 기간
- [ ] Genesis Block의 역할

---

## 14. 내부 문서 참조 맵

```
07번 (UTXO Set 관리):
  §2 UTXO Set 구조 (Key-Value)
  §4 Reorg 시 롤백
  §6 인덱싱 전략 (주소, 높이, 에셋)
  §7 LevelDB 사용법, 캐싱
  §8 Batch, 압축, Pruning

11번 (동기화):
  §5 IBD 최적화 (flush 주기)

18번 (성능 최적화):
  §4 캐싱 전략
  §8 디스크 I/O 최적화
```

---

## 15. 다음 학습

### 학습 완료:
- ✅ Phase 0~3 전체
- ✅ 성능 최적화
- ✅ 저장소 설계

### 다음:
```
→ [20. 보안 강화](20-security-hardening.md)
→ [21. 테스트 전략](21-testing-strategy.md)
```

---

**이전:** [18. 성능 최적화](18-performance-optimization.md)  
**다음:** [20. 보안 강화](20-security-hardening.md) →
