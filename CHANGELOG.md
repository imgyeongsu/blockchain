# Changelog

All notable changes to JackpotChain will be documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/)

---

## [1.0.3] - 2026-03-20

### Added
- 초보자용 Simple TUI (자동 지갑 생성, 노드 자동 시작, 채굴 자동)
- 대시보드 RECENT BLOCKS 섹션 (최근 블록 가로 배치, 로또 숫자 표시)
- History 탭 (Claims 탭 대체, 로컬 저장소 기반 결과 영구 보관)
- 미확인 잔돈 UTXO 지원 (연속 로또 커밋 가능)
- Mempool TX 의존성 체인 해결 (부모→자식 순서 보장)
- 블록 내 TX 체인 검증 (`_BlockTxTracker`)
- Orphan TX 대기열 (부모 TX 도착 시 자동 재시도)
- 피어 끊김 시 3초 후 즉시 재연결

### Fixed
- 로또 자동 지급 N+28로 변경 (N+18 블록 해시 미확정 버그)
- `payout_height` 갱신 (chain.py `_connect_block`에서 payout TX 감지)
- 시드 노드 즉시 연결 (시작 시 30초 대기 제거)
- 피어 높이 실시간 갱신 (블록 수신 시 `update_peer_height`)
- TUI 지갑 선택 시 노드 활성 지갑 동기화 (`setwallet` RPC 호출)
- Simple TUI 방화벽 팝업 차단 해결 (`CREATE_NO_WINDOW` 제거)
- PyInstaller spec 파일 갱신 (history, simple 모듈 추가)

### Changed
- Claim TX 제거 → 자동 Payout 시스템 (채굴자가 N+28 블록에 자동 포함)
- `LOTTO_PAYOUT_GAP = 28` (18 + 10블록 포크 대비)
- CLI 기본 실행 → Simple TUI, `tui` 명령 → 고급 TUI

## [1.0.2] - 2026-03-20

### Fixed
- 500개 블록 동기화 후 멈추는 버그 해결 (watchdog 추가)

### Changed
- P2P 포트 8333 → 9777, RPC 포트 8332 → 9776 (Bitcoin/Litecoin 충돌 방지)
- 도메인 jackpotchain.io → ssatto777.site
- 블록 동기화 High/Low Watermark 방식 적용 (상세: [ADVANCE.md](ADVANCE.md#블록-동기화-속도-개선-이력-2026-03-20))

## [1.0.1] - 2026-03-18

### Fixed
- TX 전파 버그 수정 (`node.py:_handle_tx` 파라미터 누락)
- 연속 commit UTXO 충돌 방지 (`_reserved_utxos` 추적)

### Added
- TUI Send 버튼 및 송금 패널

## [1.0.0] - 2026-03-17

### Added
- 초기 릴리스
- UTXO 기반 블록체인 (PoW, SHA-256)
- 온체인 로또 시스템 (Commit-Reveal)
- P2P 네트워크 (NAT traversal, 피어 발견)
- TUI 클라이언트
- Windows 인스톨러 (PyInstaller + Inno Setup)
