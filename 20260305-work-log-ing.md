# 20260305 작업 로그 (진행중)

## 완료 작업

### 1. Commit TX 보안 강화
채굴자 공격 방어를 위해 Commit TX에서 숫자 제거

**변경 파일:**
- `jackpotchain/script/standard.py`
  - `create_commit_script()`: commit_hash만 포함, chosen_numbers 제거
  - `extract_commit_data()`: hash만 반환
- `jackpotchain/gacha/game.py`
  - `validate_commit_tx()`: 숫자 검증 제거
  - `process_commit()`: 빈 숫자 리스트 저장
  - `check_result()`: chosen_numbers 파라미터 추가

**보안 개선:**
```
Before: Commit TX = commit_hash + chosen_numbers (채굴자가 숫자 확인 가능)
After:  Commit TX = commit_hash only (숫자는 Claim 시 공개)
```

**테스트:** 45/45 통과

---

### 2. Docker 배포 환경 구성

**생성 파일:**
| 파일 | 설명 |
|------|------|
| `Dockerfile` | Python 3.12 기반 노드 이미지 |
| `docker-compose.yml` | 3노드 테스트넷 (seed + node2 + node3) |
| `.dockerignore` | 빌드 시 제외 파일 |
| `DEPLOYMENT.md` | 배포 가이드 문서 |

**docker-compose 구성:**
```
seed-node (8333/8332) - 채굴 O
    ├── node2 (8334/8335) - 채굴 X
    └── node3 (8336/8337) - 채굴 O
```

**실행 명령:**
```bash
docker-compose up -d      # 시작
docker-compose logs -f    # 로그
docker-compose down -v    # 종료 + 데이터 삭제
```

---

### 3. 문서 작성
- `tech.md` - 기술 스택 정리
- `PROJECT_PROPOSAL.md` - 프로젝트 기획서
- `NODE_FLOW.md` - 노드 실행 흐름도

### 4. Claude 컨텍스트 폴더
- `.CLAUDE/CLAUDE.md` - 프로젝트 컨텍스트 요약
- `.CLAUDE/DECISIONS.md` - 아키텍처 결정 사항
- `.CLAUDE/HISTORY.md` - 작업 히스토리

### 5. NAT Traversal 구현 (인바운드 연결)
Bitcoin Core v29.0 전략 적용

**생성 파일:**
- `jackpotchain/network/nat.py` - NATManager 클래스

**수정 파일:**
- `jackpotchain/network/node.py`
  - NATManager 통합
  - `start()`: 자동 포트 매핑 시도
  - `stop()`: 매핑 제거
  - `external_address` 속성 추가
  - `NodeConfig`: nat_enabled, nat_lifetime 옵션

**동작 순서:**
```
1. PCP (RFC 6887) 시도
2. NAT-PMP (RFC 6886) 시도 (PCP 실패 시)
3. 아웃바운드 전용 모드 (둘 다 실패 시)
```

---

## 커밋 내역

```
0baefc2 deploy: Docker 기반 배포 환경 구성
1f71bc4 docs: 기술스택 및 프로젝트 기획서 추가
73ff6c7 security: Commit TX에서 숫자 제거 (채굴자 공격 방어)
```

---

## 진행중 / 예정

### 글로벌 배포 준비
- [ ] Docker Desktop에서 빌드 테스트
- [ ] AWS/GCP 서버 준비
- [ ] 시드 노드 배포
- [ ] DNS 시드 설정

### 추가 작업 (선택)
- [ ] 모니터링 (Prometheus/Grafana)
- [ ] CI/CD 파이프라인
- [ ] 웹 대시보드

---

## 메모

**1주일 내 글로벌 배포 목표:**
1. Docker 이미지 완성 ✅
2. 클라우드 서버 배포
3. 공개 시드 노드 운영
4. 이후 Go/Rust 리라이트 예정
