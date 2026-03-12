# JackpotChain 트러블슈팅 가이드

## 목차
1. [동기화 문제](#1-동기화-문제)
2. [UTXO/잔액 문제](#2-utxo잔액-문제)
3. [네트워크 문제](#3-네트워크-문제)

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
curl -d '{"method":"getbalance","params":["X4Nqvw2Y..."],"id":1}' http://127.0.0.1:9335
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
curl -d '{"method":"getpeerinfo","params":[],"id":1}' http://127.0.0.1:9335
```

2. Node2를 Node1에 연결:
```bash
python -m jackpotchain.cli.main node \
  --mine --address <주소2> \
  --port 9336 --rpc-port 9337 \
  --data-dir ./data2 \
  --seed 127.0.0.1:9334  # Node1에 연결
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
   - 공유기 설정에서 P2P 포트 (8333 또는 9333) 열기

3. 아웃바운드 전용 모드:
   - 인바운드 연결 없이도 블록 동기화는 가능

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
curl -d '{"method":"getblockchaininfo","params":[],"id":1}' http://127.0.0.1:9335

# 피어 정보
curl -d '{"method":"getpeerinfo","params":[],"id":1}' http://127.0.0.1:9335

# 특정 높이 블록 해시
curl -d '{"method":"getblockhash","params":[100],"id":1}' http://127.0.0.1:9335
```

### 데이터 초기화
```bash
# 블록체인 데이터 삭제 후 재동기화
rm -rf ./data/blocks ./data/utxo
python -m jackpotchain.cli.main node --seed 54.116.13.57:9333
```

---

## 관련 문서
- [NODE_GUIDE.md](NODE_GUIDE.md) - 노드 실행 가이드
- [CLAUDE.md](../.claude/CLAUDE.md) - 프로젝트 컨텍스트
