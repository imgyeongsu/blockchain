# JackpotChain 트러블슈팅 가이드

## 목차
1. [동기화 문제](#1-동기화-문제)
2. [UTXO/잔액 문제](#2-utxo잔액-문제)
3. [네트워크 문제](#3-네트워크-문제)
4. [트랜잭션 문제](#4-트랜잭션-문제)
5. [코드 점검 결과 (2026-03-20)](#5-코드-점검-결과-2026-03-20)

---

## 1. 동기화 문제

### 1.1 피어 높이가 0으로 표시됨

**증상**
```
[SYNC] IBD 시작: 로컬=0, 피어=0
```
실제로 피어는 140+ 블록을 가지고 있는데 0으로 표시.

**원인**
VERACK 핸들러에서 동기화를 체크했는데, 이 시점에 피어의 VERSION 메시지가 아직 도착하지 않음.

**해결**
`_check_sync()` 메서드를 분리하고, **아웃바운드 피어**의 경우 VERSION 수신 후 호출하도록 수정.

```python
# node.py
async def _handle_version(self, msg, address):
    # ... VERSION 처리 ...

    # 아웃바운드 연결이면 동기화 체크
    if address in self.peer_manager._outbound:
        await self._check_sync(address)
```

**파일**: `jackpotchain/network/node.py`

---

### 1.2 블록이 순서대로 도착하지 않음

**증상**
```
[CHAIN] 블록 추가 실패: 이전 블록 없음
[CHAIN] 블록 추가 실패: 이전 블록 없음
```
140개 블록을 한번에 요청하면 순서가 뒤섞여 도착.

**원인**
GETDATA로 모든 블록을 한번에 요청하면 네트워크/피어 상태에 따라 순서가 보장되지 않음.

**해결**
순차 다운로드 방식 구현:
1. `_pending_blocks`: 받아야 할 블록 해시 큐
2. `_sync_peer`: 동기화 중인 피어
3. 한 번에 하나씩 요청 → 수신 → 다음 요청

```python
# node.py
async def _request_next_block(self):
    """다음 블록 하나만 요청"""
    if not self._pending_blocks:
        print("[SYNC] 동기화 완료!")
        self._sync_peer = None
        return

    next_hash = self._pending_blocks.pop(0)
    await self._send_getdata(self._sync_peer, [(1, next_hash)])
```

**파일**: `jackpotchain/network/node.py`

---

### 1.3 블록 수신 후 체인에 추가되지 않음

**증상**
```
[NET] 블록 수신: height=1
[NET] 블록 수신: height=2
```
로그는 나오지만 `getblockchaininfo` 높이는 0.

**원인**
`node.set_block_callback()`이 호출되지 않아 수신한 블록이 체인에 추가되지 않음.

**해결**
`main.py`에서 콜백 등록:

```python
# cli/main.py
def on_block_received(block, peer):
    """피어로부터 블록 수신시 처리"""
    success, msg = blockchain.add_block(block)
    if success:
        print(f"[CHAIN] 피어 블록 추가 성공: height={blockchain.get_height()}")
        for tx in block.transactions[1:]:
            mempool.remove_tx(tx.get_txid())

async def run():
    node.set_block_callback(on_block_received)  # 콜백 등록
    await node.start()
```

**파일**: `jackpotchain/cli/main.py`

---

## 2. UTXO/잔액 문제

### 2.1 모든 주소 잔액이 0

**증상**
```bash
curl -d '{"method":"getbalance","params":["X4Nqvw2Y..."],"id":1}' http://127.0.0.1:9779
# {"result": 0.0}
```
300+ 블록 채굴했는데 모든 주소 잔액이 0.

**원인**
`apply_transaction()` 호출 시 `get_address_from_script_pubkey` 콜백을 전달하지 않음.
→ UTXO는 추가되지만 주소 인덱스(`_by_address`)에는 등록되지 않음.

**해결**
모든 `apply_transaction` 호출에 콜백 전달:

```python
# consensus/chain.py
from ..script.standard import get_address_from_script_pubkey

# 블록 로드 시
for tx in block.transactions:
    self.utxo_set.apply_transaction(tx, height, get_address_from_script_pubkey)

# _connect_block
spent_utxos = self.utxo_set.apply_transaction(tx, height, get_address_from_script_pubkey)

# _disconnect_block (reorg 시)
self.utxo_set.revert_transaction(tx, spent_utxos, get_address_from_script_pubkey)
```

**파일**: `jackpotchain/consensus/chain.py`

---

### 2.2 JACKPOT_POOL 잔액이 0

**증상**
```bash
curl -d '{"method":"getbalance","params":["JACK_JACKPOT_POOL_SYSTEM"],"id":1}'
# {"result": 0.0}
```
제네시스 블록에 1,000,000 JACK 배정했는데 잔액 0.

**원인**
제네시스 블록의 잭팟풀 출력:
```python
jackpot_pool_output = TxOutput(
    jack_value=1_000_000 * COIN,
    script_pubkey=b'JACKPOT_POOL'  # 특수 마커
)
```

`get_address_from_script_pubkey()`가 P2PKH만 파싱 → `b'JACKPOT_POOL'`은 `None` 반환.

**해결**
특수 마커 매핑 추가:

```python
# script/standard.py
def get_address_from_script_pubkey(script_pubkey: bytes) -> Optional[str]:
    from ..crypto.address import JACKPOT_POOL_ADDRESS, BURN_ADDRESS

    # 특수 마커 처리 (제네시스 블록 등)
    if script_pubkey == b'JACKPOT_POOL':
        return JACKPOT_POOL_ADDRESS
    if script_pubkey == b'BURN':
        return BURN_ADDRESS

    # P2PKH 형식
    pubkey_hash = extract_p2pkh_pubkey_hash(script_pubkey)
    if pubkey_hash:
        return pubkey_hash_to_address(pubkey_hash)
    return None
```

**파일**: `jackpotchain/script/standard.py`

---

### 2.3 Coinbase 잔액이 표시되지 않음

**증상**
채굴한 지 얼마 안 된 블록의 Coinbase 보상이 잔액에 표시되지 않음.

**원인**
Coinbase 성숙도 규칙: **100블록** 후에야 사용 가능.

```python
# utxo.py
def is_mature(self, current_height: int, coinbase_maturity: int = 100) -> bool:
    if not self.is_coinbase:
        return True
    return (current_height - self.block_height) >= coinbase_maturity
```

**해결**
정상 동작. 100블록 대기 필요.

```python
# 높이별 잔액 예시
Height   0: 0.00 JACK (미성숙)
Height  99: 0.00 JACK (미성숙)
Height 100: 1,000,000.00 JACK (성숙!)
```

---

## 3. 네트워크 문제

### 3.1 두 노드가 서로 다른 체인을 채굴

**증상**
Node1과 Node2가 같은 높이에서 다른 블록 해시를 가짐.

**원인**
1. 두 노드가 서로 연결되지 않음
2. 다른 제네시스 블록 사용

**해결**
1. 피어 연결 확인:
```bash
curl -d '{"method":"getpeerinfo","params":[],"id":1}' http://127.0.0.1:9779
```

2. Node2를 Node1에 연결:
```bash
python -m jackpotchain.cli.main node \
  --mine --address <주소2> \
  --port 9780 --rpc-port 9781 \
  --data-dir ./data2 \
  --seed 127.0.0.1:9778  # Node1에 연결
```

3. 제네시스 블록 확인 (하드코딩됨):
```python
# constants.py
GENESIS_HASH = bytes.fromhex("c41d65b...")
```

---

### 3.2 NAT 뒤에서 인바운드 연결 안 됨

**증상**
다른 노드가 내 노드에 연결할 수 없음.

**원인**
NAT/방화벽이 인바운드 연결 차단.

**해결**
1. UPnP 자동 포트 매핑 (구현됨):
```python
# network/nat.py - 노드 시작 시 자동 실행
nat_result = await self.nat_manager.setup_port_mapping()
```

2. 수동 포트포워딩:
   - 공유기 설정에서 P2P 포트 (9777 또는 9777) 열기

3. 아웃바운드 전용 모드:
   - 인바운드 연결 없이도 블록 동기화는 가능

---

## 4. 트랜잭션 문제

### 4.1 서명 검증 실패

**증상**
```bash
curl -d '{"method":"sendtoaddress","params":["주소", 100],"id":1}' http://127.0.0.1:9776
# {"error": {"message": "Invalid TX: Input 0 signature verification failed"}}
```

**원인**
1. 서명 해시 계산 방식 불일치
   - 서명 시: script_sig가 비어있는 상태로 해시 계산
   - 검증 시: script_sig가 채워진 상태로 해시 계산
   - 결과: 해시 불일치 → 서명 검증 실패

2. verify() 함수 파라미터 순서 오류
   - 정의: `verify(message_hash, signature, public_key)`
   - 잘못된 호출: `verify(pubkey, tx_hash, sig)`

**해결**
Bitcoin 표준 SIGHASH_ALL 방식 구현:

```python
# core/transaction.py
def get_signature_hash(self, input_index: int, script_pubkey: bytes) -> bytes:
    """Bitcoin SIGHASH_ALL 방식 서명 해시 계산"""
    # 1. TX 복사
    # 2. 모든 input의 script_sig 비움
    # 3. 서명할 input의 script_sig를 이전 출력의 script_pubkey로 설정
    # 4. 직렬화 + SIGHASH_ALL(0x01) 4바이트 추가
    # 5. double SHA256

# interpreter.py - 파라미터 순서 수정
return verify(self.context.tx_hash, actual_sig, pubkey)  # hash, sig, pubkey 순서
```

**파일**:
- `jackpotchain/core/transaction.py` - get_signature_hash() 추가
- `jackpotchain/script/interpreter.py` - verify() 호출 순서 수정
- `jackpotchain/validation/transaction.py` - get_signature_hash() 사용
- `jackpotchain/wallet/wallet.py` - get_signature_hash() 사용

---

## 디버깅 팁

### 로그 레벨 확인
```python
# 상세 로그 출력
import logging
logging.basicConfig(level=logging.DEBUG)
```

### RPC로 상태 확인
```bash
# 블록체인 정보
curl -d '{"method":"getblockchaininfo","params":[],"id":1}' http://127.0.0.1:9779

# 피어 정보
curl -d '{"method":"getpeerinfo","params":[],"id":1}' http://127.0.0.1:9779

# 특정 높이 블록 해시
curl -d '{"method":"getblockhash","params":[100],"id":1}' http://127.0.0.1:9779
```

### 데이터 초기화
```bash
# 블록체인 데이터 삭제 후 재동기화
rm -rf ./data/blocks ./data/utxo
python -m jackpotchain.cli.main node --seed 54.116.13.57:9777
```

---

## 5. 코드 점검 결과 (2026-03-20)

### 🔴 Critical (즉시 수정 필요)

#### 5.1 Reorg 시 TX가 mempool에 복원되지 않음

**위치**: `jackpotchain/consensus/chain.py:340-341`

**원인**
`_disconnect_block()`에서 UTXO는 되돌리지만, 해당 블록에 포함되었던 TX를 mempool에 되돌려주는 코드가 없음.

**결과**
체인 재조직(reorg) 발생 시, 기존 메인 체인에만 있던 TX가 사라짐. 사용자 입장에서 송금한 TX가 증발하는 현상 발생. 새 체인에서 재채굴되지 않으면 영구 유실.

---

#### 5.2 저장소 로드 시 undo 데이터 미생성

**위치**: `jackpotchain/consensus/chain.py:121-133`

**원인**
`_load_from_store()`에서 `_add_block_internal()` + 수동 `apply_transaction()` 호출. `_connect_block()`을 안 쓰기 때문에 `_undo_data`가 채워지지 않음.

**결과**
노드 재시작 후 reorg 발생하면, `_disconnect_block()`에서 `undo_data = []`이 되어 소비된 UTXO를 복원 불가. UTXO set 영구 오염 → 이후 모든 TX 검증 실패 가능.

---

#### 5.3 Reorg 시 Claim TX 인덱스 미복원

**위치**: `jackpotchain/consensus/chain.py:394-395`

**원인**
`_disconnect_block()`에서 `_unindex_commit_tx()`는 호출하지만, Claim TX의 `claim_height` 되돌리기 없음. `_index_claim_tx()`의 역연산인 `_unindex_claim_tx()` 자체가 존재하지 않음.

**결과**
reorg로 Claim TX가 사이드 체인으로 밀려나도 `commit_index[commit_hash].claim_height`가 남아 있음. 해당 commit은 "이미 claim됨" 상태로 남아서 새 체인에서 다시 claim 불가 → 당첨금 수령 영구 불가.

---

### 🟡 Major (1주 내 수정)

#### 5.4 Sync 피어 교체 시 `_requesting` 미초기화

**위치**: `jackpotchain/network/node.py:448-449`

**원인**
새 INV 수신 시 `_pending_blocks`와 `_sync_peer`는 덮어쓰지만, 이전 피어에게 요청해둔 `_requesting` set은 그대로 유지.

**결과**
이전 피어가 응답하지 않은 블록 해시가 `_requesting`에 남아 있으면, 새 피어에게도 해당 블록을 요청하지 않음. `_request_next_block()`이 그 해시를 건너뛰어서 동기화가 영원히 멈춤.

---

#### 5.5 Sync 완료 시 `_requesting` 미초기화

**위치**: `jackpotchain/network/node.py:554-556`

**원인**
동기화 완료 후 `_sync_peer = None`, `_block_buffer.clear()`는 하지만 `_requesting.clear()`가 없음.

**결과**
다음 동기화 때 이전 요청 잔여물이 남아서 블록을 건너뜀. 재시작 전까지 특정 블록을 영영 못 받을 수 있음.

---

#### 5.6 Sync 세션 타임아웃 없음

**위치**: `jackpotchain/network/node.py:110`

**원인**
`_sync_peer` 설정 후 상대가 블록을 안 보내면 해제할 메커니즘 없음. 개별 read timeout(300s)은 있지만 전체 세션 타임아웃 없음.

**결과**
악의적/불안정 피어가 일부 블록만 보내고 멈추면, 노드가 영구 동기화 중 상태에 갇힘. `is_syncing = True`가 유지되어 다른 피어와 동기화도 불가.

---

#### 5.7 INV 메시지 TX 항목 수 무제한

**위치**: `jackpotchain/network/node.py:424-433`

**원인**
블록은 `MAX_PENDING_BLOCKS`로 제한하지만, TX는 `inv_msg.items` 전체를 무제한 처리. `MAX_INV_SIZE=50000`이 constants에 있지만 사용되지 않음.

**결과**
악의적 피어가 수만 개 TX hash가 담긴 INV를 보내면 전부 GETDATA 요청. 메모리 폭증 + 네트워크 대역폭 고갈.

---

#### 5.8 `create_commit_tx` 반환 타입 불일치

**위치**: `jackpotchain/gacha/game.py:135-137`

**원인**
정상 경로는 `(None, b'', b'', [], "에러메시지")`를 반환하지만, 주소 검증 실패 시 `[]` 대신 `0`(int)을 반환.

```python
return None, b'', b'', 0, f"Invalid player address: ..."  # ← int 0
return None, b'', b'', [], f"Insufficient POT..."          # ← list []
```

**결과**
호출부에서 `chosen_numbers`를 list로 기대하고 `len()` 등을 호출하면 TypeError 크래시. 주소가 잘못된 경우에만 발생하므로 정상 흐름에선 안 터지지만 에러 핸들링 시 문제.

---

#### 5.9 RPC `_wallet_file` 속성명 오류

**위치**: `jackpotchain/rpc/server.py:1090`

**원인**
`self.wallet._wallet_file`을 참조하지만, Wallet 클래스의 실제 속성은 `self.wallet_file` (언더스코어 없음).

```python
# server.py:1090
wallet_path = Path(self.wallet._wallet_file) if hasattr(self.wallet, '_wallet_file') else None
# wallet.py:64
self.wallet_file = Path(wallet_file)  # ← 실제 속성명
```

**결과**
`hasattr` 체크가 항상 False → `wallet_path = None` → `wallet_dir` 없을 때 기본 지갑이 `self.wallets` dict에 등록 안 됨 → `listwallets` RPC에서 기본 지갑 누락.

---

### 🟠 Moderate (개선 권장)

#### 5.10 부동소수점 → 정수 변환 오차

**위치**: `jackpotchain/rpc/server.py:989`

**원인**
`int(jack_amount * COIN)` — 예를 들어 `int(0.29 * 100_000_000)` = `int(28999999.999999996)` = `28999999` (1 사토시 손실).

**결과**
특정 금액에서 1 사토시 오차 발생. 치명적이진 않지만 교환 비율 계산에서 미세한 금액 차이 유발.

---

## 관련 문서
- [NODE_GUIDE.md](NODE_GUIDE.md) - 노드 실행 가이드
- [CLAUDE.md](../.claude/CLAUDE.md) - 프로젝트 컨텍스트
