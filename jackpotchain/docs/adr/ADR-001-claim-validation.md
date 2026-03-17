# ADR-001: LOTTO_CLAIM 온체인 검증 방식

## Status
Proposed

## Context

현재 LOTTO_CLAIM TX 검증 시 잭팟 풀 UTXO를 서명 없이 지출할 수 있다.
이는 악의적 노드가 가짜 claim TX를 생성해 당첨금을 탈취할 수 있는 보안 취약점이다.

검증에 필요한 정보:
1. `commit_hash`, `nonce`, `chosen_numbers` (claim TX의 OP_RETURN에서 추출)
2. 원본 commit TX의 블록 높이 (비교 블록 결정에 필요)
3. 비교 블록들의 해시 (당첨 결과 계산에 필요)

**문제**: 현재 `validate_transaction(tx, utxo_set, current_height)`는 blockchain 참조가 없어 2, 3번 정보를 얻을 수 없다.

## Decision Drivers

- 검증 정확성: 모든 claim이 정당한지 확인
- 성능: 블록 검증 속도에 미치는 영향
- 유지보수성: 코드 복잡도 및 동기화 이슈
- Reorg 안전성: 체인 재구성 시 정합성

## Options

### Option A: Commit Index (별도 인덱스)

```python
# 구조
commit_index: Dict[bytes, CommitInfo]  # commit_hash → CommitInfo

@dataclass
class CommitInfo:
    tx_id: bytes
    block_height: int
    block_hash: bytes
```

**장점:**
- O(1) 조회 - 빠른 검증
- validation 함수 시그니처 변경 불필요
- 느슨한 결합 (blockchain과 분리)
- 증분 업데이트 가능

**단점:**
- 추가 저장소 필요
- Blockchain과 동기화 필요
- Reorg 시 인덱스 재구축 필요
- 새로운 버그 가능성 (동기화 실패)

**구현 위치:**
- `storage/commit_index.py` (신규)
- `consensus/chain.py` - 블록 추가/제거 시 인덱스 업데이트

---

### Option B: Blockchain Reference (직접 참조)

```python
# 변경된 시그니처
def validate_transaction(
    tx: Transaction,
    utxo_set: UTXOSet,
    current_height: int,
    blockchain: Blockchain  # 추가
) -> TxValidationResult:
```

**장점:**
- 항상 최신 상태 (Single Source of Truth)
- 추가 저장소 불필요
- 동기화 이슈 없음
- Reorg 자동 반영

**단점:**
- O(n) 검색 - commit TX 찾기 위해 블록 순회 필요
- 함수 시그니처 변경 (하위 호환성 깨짐)
- 강한 결합 (validation ↔ blockchain)
- 순환 참조 위험 (chain → validation → chain)

**구현 위치:**
- `validation/transaction.py` - 시그니처 변경
- `validation/block.py` - 호출부 수정
- `mempool/pool.py` - 호출부 수정

---

### Option C: Hybrid (인덱스 + Lazy Loading)

```python
# Commit 인덱스를 blockchain 내부에 유지
class Blockchain:
    def __init__(self):
        self._commit_index: Dict[bytes, CommitInfo] = {}

    def get_commit_info(self, commit_hash: bytes) -> Optional[CommitInfo]:
        return self._commit_index.get(commit_hash)
```

검증 시 blockchain 참조는 전달하되, 인덱스로 O(1) 조회.

**장점:**
- O(1) 조회
- Single Source of Truth (blockchain이 인덱스 소유)
- Reorg 시 blockchain이 자동 관리
- 동기화 버그 가능성 낮음

**단점:**
- 함수 시그니처 변경 필요
- Blockchain 클래스 복잡도 증가

## Decision

**Option C: Hybrid 채택**

이유:
1. **성능**: O(1) 조회로 블록 검증 속도 유지
2. **정합성**: Blockchain이 인덱스를 소유하므로 동기화 보장
3. **Reorg 안전**: `_disconnect_block`에서 인덱스도 함께 롤백
4. **확장성**: 향후 다른 TX 타입 인덱스도 같은 패턴 적용 가능

## Implementation Plan

### Phase 1: Commit Index 추가
```python
# consensus/chain.py
@dataclass
class CommitInfo:
    tx_id: bytes
    block_height: int

class Blockchain:
    def __init__(self):
        self._commit_index: Dict[bytes, CommitInfo] = {}

    def _index_commit_tx(self, tx: Transaction, height: int):
        """Commit TX 발견 시 인덱스에 추가"""

    def _unindex_commit_tx(self, tx: Transaction):
        """Reorg 시 인덱스에서 제거"""
```

### Phase 2: Claim 검증 로직
```python
# validation/transaction.py
def validate_lotto_claim(
    tx: Transaction,
    utxo_set: UTXOSet,
    current_height: int,
    blockchain: 'Blockchain'
) -> TxValidationResult:
    # 1. OP_RETURN 파싱
    claim_data = parse_claim_script(tx)

    # 2. nonce + numbers → commit_hash 검증
    if sha256(claim_data.nonce + claim_data.numbers) != claim_data.commit_hash:
        return INVALID

    # 3. commit 인덱스 조회
    commit_info = blockchain.get_commit_info(claim_data.commit_hash)
    if not commit_info:
        return INVALID

    # 4. prize 계산
    prize = calculate_prize(claim_data, commit_info, blockchain)

    # 5. payout 검증
    if tx_payout != expected_payout(prize):
        return INVALID
```

### Phase 3: 테스트
- 정상 claim 검증 통과
- 가짜 commit_hash 거부
- nonce 위조 거부
- payout 금액 위조 거부
- Reorg 후 인덱스 정합성

## Consequences

### Positive
- 악의적 claim TX 차단
- 온체인 검증으로 신뢰 불필요
- 모든 노드가 동일한 검증 수행

### Negative
- validation 함수 시그니처 변경
- 기존 테스트 수정 필요
- 약간의 메모리 사용 증가 (인덱스)

### Risks
- 순환 import 주의 필요 (validation ↔ consensus)
  - 해결: TYPE_CHECKING 사용 또는 protocol/interface 도입

## References
- [Bitcoin BIP-141](https://github.com/bitcoin/bips/blob/master/bip-0141.mediawiki) - Witness 검증 패턴
- README.md 7.2 - Claim 데이터 온체인 검증
