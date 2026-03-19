# 제출용 파일 목록

## 필수 파일

### 핵심 소스코드
```
jackpotchain/
├── __main__.py
├── constants.py


├── gacha/                # 로또 시스템

├── asset/                # 자산 관리

├── script/               # 스크립트 시스템

├── validation/           # 검증

├── rpc/                  # JSON-RPC 서버


```

### 설정 파일
```
setup.py                  # 패키지 설정
jackpotchain/requirements.txt
jackpotchain/build.bat    # PyInstaller 빌드 스크립트
```

### Docker
```
Dockerfile
docker-compose.yml
```

### 문서
```
README.md                 # 프로젝트 소개
PROJECT_PROPOSAL.md       # 기획서
tech.md                   # 기술 스택
DEPLOYMENT.md             # 배포 가이드
NODE_FLOW.md              # 노드 실행 흐름
TODO.md                   # 할 일 목록
기능명세서.md
기능명세서-정리표.md
기술스택.md
```

### 테스트
```
jackpotchain/tests/
├── test_core.py
├── test_crypto.py
├── test_discovery.py
├── test_e2e_lotto.py
├── test_gacha.py
├── test_network.py
└── test_reorg.py
```

---

## 제외해도 되는 파일

```
.venv/                    # 가상환경 (각자 설치)
__pycache__/              # 캐시
*.pyc                     # 컴파일된 파이썬
.git/                     # Git 히스토리
.claude/                  # Claude 설정
jackpotchain.egg-info/    # 빌드 아티팩트
jackpotchain/build/       # PyInstaller 빌드 결과
*.json (지갑 파일)         # 개인 데이터
data/                     # 블록체인 데이터
```

---

## 빠른 확인용 명령어

```bash
# 패키지 설치
pip install -e .

# 테스트 실행
pytest jackpotchain/tests/ -v

# TUI 실행
python -m jackpotchain.tui

# CLI 실행
python -m jackpotchain.cli node --rpc-port 8332
```
