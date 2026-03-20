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
python -m jackpotchain.cli.main node --port 9777 --rpc-port 9776 --data-dir ./data
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

### 2.5 설치 파일 빌드 (Windows)

일반 사용자 배포용 설치 프로그램 생성 방법:

**사전 준비:**
- [Inno Setup](https://jrsoftware.org/isdl.php) 설치

**빌드 순서:**
```bash
# 1단계: Python → EXE 변환 (PyInstaller)
cd jackpotchain
.venv\Scripts\activate
pip install pyinstaller
pyinstaller jackpotchain.spec --clean
# 결과: dist/jackpotchain.exe (약 12MB)

# 2단계: EXE → 설치 프로그램 (Inno Setup)
# Inno Setup Compiler 실행 → installer.iss 열기 → Build > Compile (Ctrl+F9)
# 결과: installer_output/JackpotChain-Setup-1.0.0.exe
```

**설치 프로그램 기능:**
- 설치 경로 선택 (기본: `C:\Program Files\JackpotChain`)
- PATH 환경변수 자동 등록
- 시작 메뉴 바로가기 생성
- 제어판에서 프로그램 제거 지원

**사용자 경험:**
```
Setup.exe 실행 → 다음 → 설치 완료
새 터미널 열기 → jackpotchain
```

### 2.6 TUI (Terminal User Interface)

설치 후 `jackpotchain` 명령어만 입력하면 TUI가 실행됩니다.

```bash
# TUI 기본 실행 (RPC: 127.0.0.1:9776)
jackpotchain

# TUI 옵션 지정
jackpotchain tui --rpc-host 127.0.0.1 --rpc-port 9776
```

**TUI 기능:**
- **F1 Dashboard**: 블록체인 상태, 잭팟 풀 정보
- **F2 Wallet**: 지갑 잔액, 주소 관리
- **F3 Mining**: 채굴 상태 모니터링
- **F4 Lotto**: 로또 참여 (Commit)
- **F5 Claims**: 당첨 확인 및 수령 (Claim)
- **F6 Network**: 피어 연결 상태
- **Ctrl+R**: 새로고침
- **Ctrl+Q**: 종료

## 3. RPC 메서드(현재 코드 기준)
- Blockchain: `getblockchaininfo`, `getblock`, `getblockhash`, `getblockcount`, `getbestblockhash`
- Mempool: `getmempoolinfo`, `getrawmempool`, `sendrawtransaction`
- Wallet: `getbalance`, `getnewaddress`, `listunspent`, `sendtoaddress`
- Network: `getnetworkinfo`, `getpeerinfo`
- Mining: `getmininginfo`
- Lotto (16-2 Final): `getlottoinfo`, `getjackpotpool`, `lottocommit`, `lottoclaim`, `lottocheckresult`, `listlottocommits`
- Legacy (deprecated): `getgachainfo`, `gachacommit`, `gachareveal`, `listgachacommits`
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
- ~~Reorg 시 UTXO 재계산~~ → 구현 완료 (`consensus/chain.py`)
- Sync 헤더 검증/저장 (`sync/manager.py` TODO)
- Network 일부 처리(`node.py` TODO 다수)
- ~~RPC placeholder~~ → 수정 완료 (`confirmations`, `networkhashps`)

### 4.3 코드상 즉시 수정 권장 이슈
- `rpc/server.py`의 `gachacommit`, `gachareveal`이 `mempool.add_transaction()` 호출
  - 실제 구현은 `mempool.add_tx()`라 메서드 불일치
- `setup.py` entry point가 `cli.main:main`
  - 패키지 기준 `jackpotchain.cli.main:main`이 맞음

## 5. learning-roadmap 대비 차이

### 5.1 로또 시스템: 16-2 Final 동기화 완료 ✅

현재 코드는 로드맵 Final(16-2) "로또형 6자리 + 6개 블록 비교 + Claim(v5)" 모델과 동기화되었습니다.

현재 구현 (`jackpotchain/gacha/*`, `constants.py`):
- Commit: 6자리 hex 숫자 배열 [0x0~0xf] 선택
- Claim: N+18 ~ N+68 블록 내 결과 확정
- 비교 블록: N+3, N+6, N+9, N+12, N+15, N+18 해시 마지막 자리
- TX 버전: Commit=3, Claim=5

등급별 보상:
| 등급 | 일치 | 보상 |
|------|------|------|
| 1등 | 6개 | 잭팟 풀 50% (Commit 시점 스냅샷) |
| 2등 | 5개 | 100,000 JACK |
| 3등 | 4개 | 20,000 JACK |
| 4등 | 3개 | 2,000 JACK |
| 5등 | 2개 | 300 JACK |
| 6등 | 1개 | 1 POT (mint - 참가비 환불) |
| 꽝 | 0개 | 없음 |

참가비 분배:
- 80% → 잭팟 풀 적립
- 19% → 소각 (디플레이션)
- 1% → 채굴자 보상

### 5.2 기타 차이
- 문서상 일부 설명은 최신 코드와 다를 수 있음(예: 가챠 타입/흐름)
- 루트 `requirements.txt`와 `jackpotchain/requirements.txt`가 분리 관리 중

## 6. 앞으로 구현해야 할 항목(우선순위)

### P0 (SSOT 정합성) ✅ 완료
1. ~~README 기준으로 가챠 모델 확정~~ → 16-2 Final 채택
2. ~~가챠를 Final(16-2)로 갈지 결정~~ → 완료
3. ~~`constants`, `gacha`, `rpc`, `tests` 동기화~~ → 완료

### P1 (기능 안정화) ✅ 완료
1. ~~Reorg 시 UTXO disconnect/connect 구현~~ → 완료
2. ~~Sync 헤더 검증 및 저장~~ → 완료
3. ~~RPC confirmations/networkhashps 실제 계산 반영~~ → 완료
4. ~~로또 통합 테스트 실행 검증~~ → E2E 4/4 통과 (2026-03-16)

### P2 (도메인 확장)
1. ~~Exchange/로또 통합 시나리오 테스트~~ → E2E 통과
2. ~~Dashboard/TUI, 패키징(PyInstaller/Docker)~~ → 완료 (2026-03-17)
3. 다중 노드 장기 동기화 및 fork 회복 시나리오 테스트
4. 16.1 문서의 고도화된 치트억제 로깅/모니터링

## 7. 업그레이드 예정 사항

### 7.1 잭팟 풀 보안 강화 (P1)
**현재 상태**: 잭팟 풀 UTXO는 `b'JACKPOT_POOL'` 특수 스크립트 사용, LOTTO_CLAIM TX에서 서명 없이 지출 허용

**문제점**:
- 서명 없이 풀 UTXO 지출 가능 (악의적 노드가 가짜 claim 생성 가능)
- claim 데이터 검증이 TX 검증 단계에서 수행되지 않음

**개선 방안**:
1. **시스템 키페어 도입**: 잭팟 풀 전용 하드코딩 키페어 생성, 표준 P2PKH 서명 사용
2. **Claim 검증 강화**: TX 검증 시 commit_hash, nonce, numbers 정합성 체크
3. **Multi-sig 풀**: 여러 검증자 서명 필요 (탈중앙화)

**관련 파일**:
- `validation/transaction.py`: `is_jackpot_pool_script()`, claim 검증 TODO
- `gacha/service.py`: `_select_pool_utxos()`, 풀 서명 스킵 로직
- `crypto/address.py`: `JACKPOT_POOL_ADDRESS`

### 7.2 Claim 데이터 온체인 검증 ✅ 해결됨
**구현 완료** (2026-03-16):
- `validate_lotto_claim()` 함수 추가 (`validation/transaction.py`)
- Commit 인덱스로 O(1) 조회 (`consensus/chain.py`)
- commit_hash 재계산 검증, 타이밍 검증, payout 금액 검증
- ADR-001 문서화 (`docs/adr/ADR-001-claim-validation.md`)

### 7.3 POT 6등 보상 UTXO 처리 ✅ 해결됨
**해결 방안**: LOTTO_CLAIM TX에서 6등일 때 1 POT mint 허용
- Coinbase처럼 input 없이 POT 생성 가능 (6등 한정)
- validate_lotto_claim에서 prize 검증 후 POT mint 허용
- 참가비 환불 개념 유지 (1 POT = 100 JACK 교환가)

## 8. 문서 운영 원칙
- 이 README를 SSOT로 사용합니다.
- `DEVELOPMENT_STATUS.md`는 상태 리포트 문서로 유지하되, 사실 기준은 코드 + README입니다.
- 로드맵 문서와 구현이 다르면, 반드시 README의 "차이" 섹션에 먼저 기록합니다.

