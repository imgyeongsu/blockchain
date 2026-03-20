# Changelog

All notable changes to JackpotChain will be documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/)

---

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
