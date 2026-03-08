# 21. 테스트 전략 (Testing Strategy)

> **Phase 4: Optimization**  
> **학습 날짜:** 2025-02-19  
> **난이도:** ⭐⭐⭐☆☆  
> **예상 소요 시간:** 1.5-2시간  
> **선행 학습:** Phase 0~3 전체, [20. 보안 강화](20-security-hardening.md)

---

## 🎯 학습 목표

이 문서를 완료하면:
- [ ] 블록체인 테스트의 특수성을 이해한다
- [ ] 단위/통합/시나리오 테스트의 구분과 범위를 안다
- [ ] 포크, Reorg, 이중지불 시나리오를 테스트할 수 있다
- [ ] 가챠/Exchange 특수 기능의 테스트 케이스를 설계할 수 있다
- [ ] MVP 테스트 우선순위를 판단할 수 있다

---

## 1. 블록체인 테스트의 특수성

### 1.1 일반 소프트웨어 vs 블록체인

```
일반 소프트웨어:
  버그 → 패치 배포 → 끝
  데이터 잘못됨 → DB 수정 → 끝
  
블록체인:
  버그 → 잘못된 블록이 체인에 들어감 → 되돌리기 극히 어려움
  합의 깨짐 → 네트워크 분열 → 치명적
  금액 관련 버그 → 자산 손실 → 복구 불가

핵심:
  블록체인은 "배포 후 수정"이 거의 불가능
  → 배포 전 테스트가 훨씬 중요
  → 특히 합의 규칙 관련 테스트는 필수
```

### 1.2 무엇을 테스트해야 하나?

```
블록체인 노드의 테스트 대상:

  1. 정상 동작 (Happy Path)
     → 올바른 TX가 올바르게 처리되는가?
  
  2. 거부 동작 (Rejection)
     → 잘못된 TX/블록을 올바르게 거부하는가?
     → 이게 더 중요! 거부 실패 = 보안 구멍
  
  3. 경계 조건 (Edge Case)
     → 최대/최소 값, 0, 빈 데이터, 오버플로우
  
  4. 합의 일관성 (Consensus)
     → 모든 노드가 동일한 결과를 내는가?
     → 하나라도 다르면 네트워크 분열
  
  5. 동시성 (Concurrency)
     → 동시에 블록 수신, 동시에 TX 검증
     → 레이스 컨디션 없는가?
```

---

## 2. 테스트 피라미드

### 2.1 3단계 구조

```
        ╱╲
       ╱  ╲        시나리오 테스트 (적지만 중요)
      ╱    ╲       → 포크, 공격, 전체 흐름
     ╱──────╲
    ╱        ╲     통합 테스트 (중간)
   ╱          ╲    → 모듈 간 상호작용
  ╱────────────╲
 ╱              ╲  단위 테스트 (많이)
╱                ╲ → 개별 함수/모듈
────────────────────

단위: 빠름, 많이, 개별 검증
통합: 중간, 모듈 연결 검증
시나리오: 느림, 적지만, 전체 동작 검증
```

---

## 3. 단위 테스트 (Unit Test)

### 3.1 암호학 (01번 관련)

```
=== SHA-256 ===
  test_sha256_empty_input → 빈 입력의 해시 = 알려진 값
  test_sha256_known_vector → "hello" → 알려진 해시
  test_sha256_deterministic → 같은 입력 → 항상 같은 출력

=== ECDSA ===
  test_sign_verify_valid → 서명 생성 → 검증 성공
  test_verify_wrong_key → 다른 키로 검증 → 실패
  test_verify_wrong_message → 다른 메시지로 검증 → 실패
  test_verify_corrupted_sig → 훼손된 서명 → 실패

=== 주소 생성 ===
  test_pubkey_to_address → 공개키 → 주소 변환 정확?
  test_address_checksum → 체크섬 검증 성공/실패
```

### 3.2 직렬화 (02번, 09번 관련)

```
=== TX 직렬화 ===
  test_tx_serialize_deserialize → 직렬화 → 역직렬화 → 원본과 동일
  test_tx_id_calculation → TX 해시 계산 정확?
  test_varint_encoding → VarInt 인코딩/디코딩 정확?
  test_varint_max_value → 최대값 처리
  test_varint_zero → 0 처리

=== 블록 직렬화 ===
  test_block_serialize → 블록 직렬화 정확?
  test_merkle_root → TX 목록 → Merkle Root 계산 정확?
  test_merkle_root_single_tx → TX 1개일 때
  test_merkle_root_odd_count → TX 홀수 개일 때 (복제)

=== 멀티에셋 Output ===
  test_output_with_pot → POT 포함 Output 직렬화
  test_output_jack_only → JACK만 있는 Output
  test_output_min_jack → 최소 JACK 경계값
```

### 3.3 UTXO Set (07번 관련)

```
=== 기본 CRUD ===
  test_utxo_add → UTXO 추가 후 조회 성공
  test_utxo_remove → UTXO 삭제 후 조회 실패
  test_utxo_not_found → 없는 UTXO 조회 → null

=== 이중 지불 ===
  test_double_spend_reject → 이미 소비된 UTXO → 거부
  test_mempool_double_spend → Mempool 내 이중지불 → 거부

=== 잔액 조회 ===
  test_balance_single_utxo → UTXO 1개 → 잔액 정확
  test_balance_multiple_utxo → UTXO 여러 개 → 합산 정확
  test_balance_multi_asset → JACK + POT 잔액 각각 정확
  test_jackpot_pool_balance → 잭팟 주소 잔액 정확

→ 07번 참조
```

### 3.4 TX 검증 (05번, 13번 관련)

```
=== 일반 TX (version 1) ===
  test_valid_transfer → 정상 전송 → 통과
  test_insufficient_jack → JACK 부족 → 거부
  test_insufficient_fee → 수수료 부족 → 거부
  test_negative_output → 음수 금액 → 거부
  test_overflow_output → 오버플로우 금액 → 거부
  test_empty_input → Input 없음 → 거부
  test_empty_output → Output 없음 → 거부
  test_pot_transfer → POT 전송 → JACK 보존 + POT 보존 확인
  test_pot_as_fee → POT으로 수수료 지불 시도 → 거부
  test_min_jack_output → Min JACK 미충족 Output → 거부

=== Exchange TX (version 2) ===
  test_valid_exchange → 1000 JACK → 10 POT 정상
  test_wrong_ratio → 비율 불일치 → 거부
  test_no_burn_record → OP_RETURN 없음 → 거부
  test_mint_without_burn → JACK 소각 없이 POT Mint → 거부
  test_version1_with_mint → version 1에서 POT Mint 시도 → 거부
  test_fractional_pot → 소수점 POT → 거스름돈 처리 확인
  test_minimum_exchange → 100 JACK 미만 → 거부

=== Gacha Commit TX (version 3) ===
  test_valid_commit → 정상 Commit → 통과
  test_commit_no_pot → POT 없이 Commit → 거부
  test_commit_hash_format → commit_hash 32bytes 확인
  test_duplicate_commit_hash → 동일 hash 중복 → 거부

=== Gacha Reveal TX (version 4) ===
  test_valid_reveal_lose → 정상 Reveal 꽝 → 통과
  test_valid_reveal_win → 정상 Reveal 당첨 → 당첨금 정확
  test_wrong_secret → 틀린 secret → 거부
  test_reveal_too_early → 같은 블록 → 거부
  test_reveal_expired → 50블록 초과 → 거부
  test_payout_wrong_amount → 당첨금 조작 → 거부
  test_payout_wrong_pool_time → Reveal 시점 풀 잔액 사용 → 거부
  test_jackpot_change_address → 거스름돈이 잭팟 주소로? → 확인
```

### 3.5 블록 검증 (06번 관련)

```
=== PoW ===
  test_valid_pow → 유효한 PoW → 통과
  test_invalid_pow → hash > target → 거부
  test_wrong_prev_hash → 이전 블록 해시 불일치 → 거부
  test_future_timestamp → 미래 2시간 초과 → 거부

=== Coinbase ===
  test_valid_coinbase → 보상 + 수수료 분배 정확
  test_coinbase_overpay → 초과 보상 → 거부
  test_coinbase_wrong_jackpot → 잭팟 몫 부족 → 거부
  test_coinbase_wrong_burn → 소각 몫 부족 → 거부
  test_coinbase_no_fee → 수수료 0일 때 Coinbase 형식
  test_multiple_coinbase → Coinbase 2개 → 거부

=== Merkle Root ===
  test_merkle_mismatch → 조작된 TX 목록 → 거부
```

### 3.6 Script (17번 관련)

```
=== P2PKH ===
  test_p2pkh_valid → 올바른 서명+키 → 통과
  test_p2pkh_wrong_sig → 잘못된 서명 → 실패
  test_p2pkh_wrong_pubkey → 다른 공개키 → 실패

=== Hash Lock ===
  test_hashlock_valid → 올바른 secret → 통과
  test_hashlock_wrong_secret → 잘못된 secret → 실패

=== OP_RETURN ===
  test_op_return_unspendable → OP_RETURN Output 소비 시도 → 실패
```

---

## 4. 통합 테스트 (Integration Test)

### 4.1 TX → UTXO Set 흐름

```
test_tx_applies_utxo_changes:
  1. UTXO Set에 Alice의 UTXO 추가 (100 JACK)
  2. Alice→Bob TX 생성 (80 JACK)
  3. TX 검증 + 적용
  4. 확인:
     Alice의 원래 UTXO 삭제됨?
     Bob의 새 UTXO 생성됨? (80 JACK)
     Alice의 거스름돈 UTXO 생성됨? (19.9 JACK)

test_block_applies_multiple_tx:
  1. 블록에 TX 100개 포함
  2. 블록 검증 + 적용
  3. 확인:
     모든 Input UTXO 삭제됨?
     모든 Output UTXO 생성됨?
     인덱스 일관성 유지?
```

### 4.2 Exchange → 가챠 전체 흐름

```
test_full_economic_loop:
  1. Alice: 채굴로 50 JACK 획득
  2. Alice: 1000 JACK → 10 POT 교환 (Exchange TX)
     → JACK 소각 확인, POT 생성 확인
  3. Alice: 1 POT으로 가챠 Commit
     → POT 소각 확인, Commit UTXO 생성 확인
  4. 다음 블록 채굴 (block_hash 확정)
  5. Alice: Reveal TX 전송
     → 당첨/꽝 계산 결과 확인
  6. 당첨이면:
     → 잭팟 풀 잔액 감소 확인
     → 당첨금이 Commit 시점 기준인지 확인
     → 잭팟 거스름돈 정확한지 확인
```

### 4.3 Coinbase 수수료 분배

```
test_coinbase_fee_distribution:
  1. 블록에 TX 10개, 총 수수료 10 JACK
  2. Coinbase TX 생성
  3. 확인:
     채굴자 Output: 50 + 5 = 55 JACK?
     잭팟 Output: 3 JACK?
     소각 OP_RETURN: 2 JACK?
  4. 블록 적용 후:
     잭팟 풀 잔액 3 JACK 증가?
```

### 4.4 저장소 일관성

```
test_crash_recovery:
  1. 블록 적용 도중 강제 종료 시뮬레이션
  2. 재시작
  3. 확인:
     UTXO Set이 일관된 상태?
     마지막 완전 블록부터 재개?
     인덱스와 UTXO 일치?

test_undo_reorg:
  1. 블록 A, B, C 적용
  2. 블록 C 롤백 (Undo)
  3. 확인:
     UTXO Set이 블록 B 상태로 복원?
     C에서 소비된 UTXO 복원됨?
     C에서 생성된 UTXO 삭제됨?
```

---

## 5. 시나리오 테스트 (Scenario Test)

### 5.1 포크 시나리오

```
=== 단순 포크 ===

test_simple_fork_resolution:
  1. 체인: ... → A → B (높이 100)
  2. 노드 1이 Block C 생성 (높이 101)
  3. 노드 2가 Block C' 생성 (높이 101)
  4. 두 블록 모두 유효
  5. 누군가 Block D를 C 위에 생성 (높이 102)
  6. 확인:
     모든 노드가 ...→A→B→C→D 체인 선택?
     C' 폐기됨?
     C'의 TX가 Mempool로 복귀?


=== 깊은 Reorg ===

test_deep_reorg:
  1. 체인: ... → A → B → C → D (높이 103)
  2. 대안 체인: ... → A → B' → C' → D' → E' (높이 104)
  3. 대안 체인이 더 김 → Reorg!
  4. 확인:
     B, C, D 롤백?
     B', C', D', E' 적용?
     UTXO Set 정확?
     잭팟 풀 잔액 정확?
```

### 5.2 이중 지불 시나리오

```
test_double_spend_in_fork:
  1. Alice: UTXO (100 JACK)
  2. Fork 발생:
     체인 A: Alice→Bob (100 JACK) TX 포함
     체인 B: Alice→Charlie (100 JACK) TX 포함
  3. 체인 A가 더 길어짐
  4. 확인:
     Bob이 100 JACK 받음?
     Charlie TX는 무효?
     Alice의 원래 UTXO는 소비됨?

test_double_spend_mempool:
  1. Alice: 같은 UTXO를 Input으로 쓰는 TX 2개 전송
  2. 확인:
     첫 번째 TX → Mempool 진입
     두 번째 TX → 거부 (이중지불)
```

### 5.3 가챠 시나리오

```
test_gacha_reveal_after_reorg:
  1. Block #500: Commit TX 포함
  2. Block #501: Reveal TX → 당첨!
  3. Reorg: Block #500 대체됨 (새 block_hash)
  4. 확인:
     기존 Reveal TX 무효? (block_hash 바뀜)
     새 block_hash로 재계산하면 결과 다를 수 있음?
     Commit TX가 새 블록에도 포함되면 → 새 Reveal 필요

test_gacha_timeout:
  1. Block #500: Commit TX 포함
  2. 50블록 동안 Reveal 안 함
  3. Block #551: 뒤늦은 Reveal TX 시도
  4. 확인: 거부됨?

test_gacha_payout_pool_timing:
  1. Block #500: Commit TX, 풀 = 1000 JACK
  2. Block #501~510: 수수료 유입, 풀 = 1100 JACK
  3. Block #511: Reveal → 당첨
  4. 확인: 당첨금 = 1000 × 60% = 600? (1100이 아님!)

test_gacha_consecutive_wins:
  1. 당첨 → 풀 감소
  2. 바로 다음 당첨 → 감소된 풀 기준
  3. 확인: 각 당첨금이 해당 Commit 시점 기준?
```

### 5.4 Exchange 시나리오

```
test_exchange_then_gacha:
  1. Alice: 1000 JACK → Exchange → 10 POT
  2. Alice: 1 POT → Gacha Commit
  3. 확인:
     Alice JACK 감소 정확?
     POT 감소 정확? (10 → 9)
     가챠 정상 작동?

test_exchange_jackpot_cycle:
  1. 채굴로 JACK 생성
  2. TX 수수료 발생 → 잭팟에 30% 축적
  3. Exchange → JACK 소각, POT 생성
  4. 가챠 → POT 소각
  5. 당첨 → 잭팟에서 JACK 지급
  6. 확인: 전체 루프에서 에셋 밸런스 유지?
```

---

## 6. 공격 시뮬레이션

### 6.1 네트워크 공격

```
test_invalid_block_flood:
  피어가 잘못된 블록을 100개 연속 전송
  확인: 노드 안정? 피어 점수 하락? 결국 Ban?

test_oversized_message:
  4 MB 초과 메시지 전송
  확인: 즉시 폐기? 메모리 영향 없음?

test_slow_peer:
  피어가 응답을 극도로 느리게
  확인: 타임아웃 → 다른 피어에 재요청?
```

### 6.2 TX 공격

```
test_tx_spam:
  수수료가 최소인 TX 10,000개 전송
  확인: Mempool 상한 작동? 수수료 높은 TX 우선?

test_script_bomb:
  매우 복잡한 Script (10,000 OP_CODE) TX 전송
  확인: Script 크기 제한으로 거부?

test_overflow_attack:
  Output 금액이 MAX_INT64에 가까운 TX
  확인: 오버플로우 감지하고 거부?
```

### 6.3 가챠 공격

```
test_miner_block_discard:
  채굴자가 자기 가챠에 유리한 block_hash 찾기 시도
  확인:
    폐기한 블록 수 × 50 JACK = 비용
    당첨금 < 비용이면 비경제적?

test_commit_spam:
  Commit TX를 대량 전송 (Reveal 안 함)
  확인:
    각 Commit에 1 POT 비용 → 경제적 억제?
    50블록 후 만료 → UTXO Set 정리?

test_frontrunning_attempt:
  Reveal TX의 secret을 보고 도용 시도
  확인: 서명 필요로 거부?
```

---

## 7. 합의 일관성 테스트

### 7.1 다중 노드 동일 결과

```
test_consensus_consistency:
  1. 6개 노드 모두 동일 Genesis에서 시작
  2. TX 100개 생성, 전파
  3. 블록 10개 채굴
  4. 확인:
     모든 노드의 Best Block 동일?
     모든 노드의 UTXO Set 해시 동일?
     모든 노드의 잭팟 풀 잔액 동일?

이게 가장 중요한 테스트!
→ 하나라도 다르면 합의 버그 → 네트워크 분열
```

### 7.2 검증 규칙 일관성

```
test_version_specific_rules:
  동일 TX를 모든 노드에서 독립 검증
  → 모든 노드가 동일하게 accept 또는 reject?

test_difficulty_calculation:
  50블록마다 난이도 재계산
  → 모든 노드가 동일한 새 난이도 산출?

test_gacha_result_deterministic:
  동일 secret + 동일 block_hash
  → 모든 노드가 동일한 당첨/꽝 결과?
```

---

## 8. 성능 테스트

### 8.1 벤치마크

```
bench_signature_verification:
  ECDSA 검증 10,000회 → 평균 시간 측정
  목표: < 0.15ms/회

bench_block_validation:
  TX 2,000개 블록 검증 → 시간 측정
  목표: < 1,000ms

bench_utxo_lookup:
  UTXO 10,000회 랜덤 조회 → 평균 시간
  캐시 있을 때 vs 없을 때

bench_ibd_speed:
  10,000블록 연속 검증 → 시간 측정
  목표: > 100 블록/초
```

### 8.2 부하 테스트

```
test_sustained_load:
  15초마다 TX 200개씩 30분간
  확인: 블록 처리 시간 안정적? 메모리 누수 없음?

test_mempool_pressure:
  TX 50,000개를 빠르게 전송
  확인: Mempool 상한 작동? 응답 시간 유지?
```

---

## 9. MVP 테스트 우선순위

### 9.1 필수 (출시 전 반드시)

```
Priority 1 — 자산 안전:
  □ TX 에셋 밸런스 검증 (모든 version)
  □ 이중 지불 방지
  □ 금액 오버플로우 방지
  □ Coinbase 수수료 분배 정확성

Priority 2 — 합의 안정:
  □ PoW 검증
  □ Merkle Root 검증
  □ 블록 연결 검증 (prev_hash)
  □ 포크 해결 (Longest Chain)
  □ Reorg + Undo 동작

Priority 3 — 핵심 기능:
  □ Exchange TX (JACK→POT) 정확
  □ Gacha Commit-Reveal 전체 흐름
  □ 당첨금 Commit 시점 고정
  □ Reveal 기한 만료
```

### 9.2 권장 (시간 있으면)

```
Priority 4 — 안정성:
  □ 크래시 복구 (재시작 후 일관성)
  □ 피어 점수 시스템
  □ Mempool 관리
  □ 직렬화/역직렬화 왕복

Priority 5 — 성능:
  □ 벤치마크 (서명, 블록, UTXO)
  □ IBD 속도
  □ 캐시 효과 측정
```

### 9.3 나중에 (확장 시)

```
Priority 6:
  □ 다중 노드 합의 일관성
  □ 공격 시뮬레이션
  □ 부하 테스트
  □ Pruning 후 동작
```

---

## 10. 테스트 환경 구성

### 10.1 로컬 테스트넷

```
개발용 테스트 환경:

  난이도: 극히 낮음 (즉시 채굴)
  블록 타임: 1초 (빠른 테스트)
  노드: 3개 (최소 포크 테스트 가능)
  Genesis: 테스트 전용

설정:
  [testnet]
  difficulty = 1
  block_time = 1
  min_fee = 0
  jackpot_payout_ratio = 0.60
  gacha_probability = 0.50  ← 테스트용 50% 확률!

가챠 테스트 팁:
  당첨 확률 1%로는 테스트 어려움
  → 테스트넷에서 50%로 올려서 당첨 시나리오 확인
  → 메인넷 배포 시 1%로 복원
```

### 10.2 테스트 유틸리티

```
테스트 헬퍼 함수:

  create_test_utxo(address, jack, pot)
    → UTXO Set에 테스트용 UTXO 직접 삽입

  mine_empty_block()
    → 빈 블록 즉시 생성 (시간 전진)

  create_funded_address(jack_amount)
    → 주소 생성 + JACK 넣어주기

  advance_blocks(n)
    → n블록 빈 블록 채굴 (Reveal 기한 등 테스트)

  get_all_utxos(address)
    → 특정 주소의 전체 UTXO 반환

  get_jackpot_balance()
    → 잭팟 풀 잔액 반환

  force_gacha_win(secret, block_hash)
    → 당첨되는 secret 생성 (테스트 전용)
```

---

## 11. 핵심 요약

### 테스트 특수성
```
블록체인: 배포 후 수정 극히 어려움
→ 배포 전 테스트가 핵심
→ "거부 동작"이 "정상 동작"보다 중요
```

### 3단계 테스트
```
단위: 해시, 서명, 직렬화, UTXO CRUD, TX 검증
통합: TX→UTXO 흐름, Exchange→가챠 루프, 저장소 일관성
시나리오: 포크/Reorg, 이중지불, 가챠 치트, 공격 시뮬
```

### MVP 우선순위
```
1순위: 자산 안전 (밸런스, 이중지불, 오버플로우)
2순위: 합의 안정 (PoW, Merkle, 포크 해결)
3순위: 핵심 기능 (Exchange, 가챠 전체 흐름)
```

### 합의 일관성
```
가장 중요한 테스트:
"6개 노드가 모두 동일한 결과를 내는가?"
→ 하나라도 다르면 네트워크 분열
```

---

## 12. 체크리스트

이해했는지 확인:

- [ ] 블록체인 테스트가 일반 소프트웨어와 다른 이유
- [ ] 테스트 피라미드 (단위/통합/시나리오)
- [ ] TX 검증 단위 테스트 범위 (version 1~4)
- [ ] 포크/Reorg 시나리오 테스트 방법
- [ ] 가챠 시나리오 (타임아웃, 풀 시점, 연속 당첨)
- [ ] 합의 일관성 테스트의 중요성
- [ ] MVP 테스트 우선순위 3단계
- [ ] 테스트넷 설정 (확률 50% 등)
- [ ] 테스트 헬퍼 함수의 역할

---

## 13. 내부 문서 참조 맵

```
01번 (암호학):       해시, 서명 테스트
02번 (데이터구조):   직렬화, Merkle Root
05번 (TX 심화):      서명 검증, Script
06번 (PoW):          난이도, 포크 해결
07번 (UTXO Set):     CRUD, 이중지불, 잔액
09번 (프로토콜):     메시지 형식
12번 (네트워크보안):  공격 시나리오
13번 (멀티에셋):     에셋 밸런스, version별 규칙
15번 (Exchange):     교환 검증
16번 (가챠):         Commit-Reveal 전체 흐름
19번 (저장소):       Batch, Undo, 크래시 복구
20번 (보안):         입력 검증, Rate Limiting
```

---

## 14. 마무리

```
Phase 4 완료!

전체 학습 로드맵:
  ✅ Phase 0: 기초 (암호학, 데이터 구조, UTXO)
  ✅ Phase 1: 코어 (TX, PoW, UTXO Set)
  ✅ Phase 2: 네트워크 (P2P, 프로토콜, 전파, 동기화, 보안)
  ✅ Phase 3: 고급 (멀티에셋, 토크노믹스, Exchange, 가챠, Script)
  ✅ Phase 4: 최적화 (성능, 저장소, 보안, 테스트)

이 문서들로 JackpotChain의 설계를 충분히 이해하고
6주 MVP 구현에 돌입할 수 있습니다! 🚀
```

---

**이전:** [20. 보안 강화](20-security-hardening.md)  
**처음으로:** [01. 암호학 기초](../phase-0-foundation/01-cryptography-basics.md) ←
