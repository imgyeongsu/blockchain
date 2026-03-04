# JackpotChain (SSOT README)

JackpotChain은 Python 기반 UTXO 블록체인 실습/연구 프로젝트입니다.
이 README는 현재 `jackpotchain/` 실제 구현을 기준으로 작성된 SSOT입니다.

## 1. 현재 상태 요약
- 구현 범위: Core(crypto/tx/block/utxo), consensus, validation, network, sync, storage, mempool, wallet, RPC, CLI, asset, gacha
- 테스트 코드: `jackpotchain/tests` 기준 `test_*` 82개 작성
- 블록 저장: 파일 기반 영속화(`--data-dir`)
- 채굴 모드: `node --mine --address <addr>` 통합 동작

주의:
- 현재 실행 환경에서 `python`, `pytest` 명령이 없어 테스트를 실제 실행해 재검증하지는 못했습니다.

## 2. 빠른 실행

### 2.1 설치
```bash
cd jackpotchain
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt
```

### 2.2 노드 실행
```bash
python -m jackpotchain.cli.main node --port 8333 --rpc-port 8332 --data-dir ./data
```

### 2.3 노드+채굴 실행
```bash
python -m jackpotchain.cli.main wallet create
python -m jackpotchain.cli.main node --mine --address <MINER_ADDRESS> --data-dir ./data
```

### 2.4 지갑 명령
```bash
python -m jackpotchain.cli.main wallet create
python -m jackpotchain.cli.main wallet address
python -m jackpotchain.cli.main wallet balance
python -m jackpotchain.cli.main wallet send --to <ADDRESS> --amount 1.0
```

## 3. RPC 메서드(현재 코드 기준)
- Blockchain: `getblockchaininfo`, `getblock`, `getblockhash`, `getblockcount`, `getbestblockhash`
- Mempool: `getmempoolinfo`, `getrawmempool`, `sendrawtransaction`
- Wallet: `getbalance`, `getnewaddress`, `listunspent`, `sendtoaddress`
- Network: `getnetworkinfo`, `getpeerinfo`
- Mining: `getmininginfo`
- Gacha: `getgachainfo`, `getjackpotpool`, `getgachatypes`, `gachacommit`, `gachareveal`, `listgachacommits`
- Utility: `help`

## 4. 개발 현황 (DEVELOPMENT_STATUS.md 반영 + 코드 대조)

### 4.1 구현 완료/동작 중
- UTXO 모델 트랜잭션/블록/머클/서명/주소
- PoW 채굴 + 난이도 조정 + 체인 인덱스
- 파일 저장소(BlockStore) 기반 체인 로딩
- P2P 메시지 구조, 피어 관리, 노드 기본 전파
- JSON-RPC 서버
- JACK/POT 교환 트랜잭션(고정 비율 100:1)
- 가챠 Commit/Reveal 기본 플로우

### 4.2 부분 구현(기능 뼈대는 있으나 보강 필요)
- Reorg 시 UTXO 재계산 (`consensus/chain.py` TODO)
- Sync 헤더 검증/저장 (`sync/manager.py` TODO)
- Network 일부 처리(`node.py` TODO 다수)
- RPC 일부 값은 placeholder (`confirmations`, `networkhashps`)

### 4.3 코드상 즉시 수정 권장 이슈
- `rpc/server.py`의 `gachacommit`, `gachareveal`이 `mempool.add_transaction()` 호출
  - 실제 구현은 `mempool.add_tx()`라 메서드 불일치
- `setup.py` entry point가 `cli.main:main`
  - 패키지 기준 `jackpotchain.cli.main:main`이 맞음

## 5. learning-roadmap 대비 차이 (중요)

### 5.1 가챠: 로드맵 최신 Final(16-2)과 현재 구현 차이
로드맵 Final(16-2)은 "로또형 6자리 + 6개 블록 비교 + Claim(v5)" 모델이지만,
현재 코드는 기존 Commit-Reveal 모델에 가깝습니다.

현재 코드(`jackpotchain/gacha/*`, `constants.py`) 기준:
- Commit: `hash(nonce + target)` (target 0~99)
- Reveal: 최소 2블록, 최대 50블록 내 공개
- 당첨판정: `winning_slot(0~99)` 일치 여부(1%)
- 보상: 잭팟풀의 60% (`GACHA_PAYOUT_RATIO=0.60`)
- TX 버전: Commit=3, Reveal=4

로드맵 Final(16-2) 기준 요구와의 불일치:
- 불일치 1: 6자리 hex 숫자/6개 참조 블록(N+5..N+30) 비교 미구현
- 불일치 2: Claim TX(version 5) 기반 구조 미구현
- 불일치 3: 등수별 고정 보상표(1~6등) 미구현
- 불일치 4: 1등 보상을 Commit 시점 풀 스냅샷 50%로 계산하는 규칙 미구현
- 불일치 5: Claim 윈도우 N+30~N+80 규칙 미구현(현재 2~50)
- 불일치 6: 16.1 문서의 고도화된 치트억제(다중 블록 기반 경제적 억제) 미반영

### 5.2 기타 차이
- 문서상 일부 설명은 최신 코드와 다를 수 있음(예: 가챠 타입/흐름)
- 루트 `requirements.txt`와 `jackpotchain/requirements.txt`가 분리 관리 중

## 6. 앞으로 구현해야 할 항목(우선순위)

### P0 (SSOT 정합성)
1. README 기준으로 가챠 모델 확정
2. 가챠를 Final(16-2)로 갈지, 현재 Commit-Reveal로 유지할지 결정
3. 선택한 모델로 `constants`, `gacha`, `rpc`, `tests`, `learning-roadmap` 문서 동기화

### P1 (기능 안정화)
1. `mempool.add_transaction` 호출부를 `add_tx`로 정리
2. Reorg 시 UTXO disconnect/connect 구현
3. Sync 헤더 검증 및 저장 완료
4. RPC confirmations/networkhashps 실제 계산 반영

### P2 (도메인 확장)
1. Exchange/가챠 통합 시나리오 테스트 확대
2. Dashboard/TUI, 패키징(PyInstaller/Docker)
3. 다중 노드 장기 동기화 및 fork 회복 시나리오 테스트

## 7. 문서 운영 원칙
- 이 README를 SSOT로 사용합니다.
- `DEVELOPMENT_STATUS.md`는 상태 리포트 문서로 유지하되, 사실 기준은 코드 + README입니다.
- 로드맵 문서와 구현이 다르면, 반드시 README의 "차이" 섹션에 먼저 기록합니다.

