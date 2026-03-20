# JackpotChain 배포 가이드

## 배포 방식

### 1. Docker (권장)

Docker를 사용한 배포가 가장 간단하고 일관된 환경을 제공합니다.

#### 단일 노드 실행

```bash
# 이미지 빌드
docker build -t jackpotchain .

# 노드 실행 (채굴 없음)
docker run -d \
  --name jackpot-node \
  -p 9777:9777 \
  -p 9776:9776 \
  -v jackpot-data:/app/data \
  jackpotchain

# 채굴 노드 실행
docker run -d \
  --name jackpot-miner \
  -p 9777:9777 \
  -p 9776:9776 \
  -v jackpot-data:/app/data \
  jackpotchain \
  node --port 9777 --rpc-port 9776 --data-dir /app/data \
  --mine --address <YOUR_ADDRESS>
```

#### 멀티노드 테스트넷

```bash
# 3노드 네트워크 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 네트워크 중지
docker-compose down

# 데이터 포함 완전 삭제
docker-compose down -v
```

**포트 매핑:**
| 노드 | P2P | RPC |
|------|-----|-----|
| seed-node | 9777 | 9776 |
| node2 | 9778 | 9779 |
| node3 | 9780 | 9781 |

---

### 2. 직접 실행 (Python)

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 노드 실행
python -m jackpotchain.cli.main node \
  --port 9777 \
  --rpc-port 9776 \
  --data-dir ./data \
  --mine --address <YOUR_ADDRESS>

# 3. 시드 노드 연결
python -m jackpotchain.cli.main node \
  --port 9778 \
  --rpc-port 9779 \
  --data-dir ./data2 \
  --seed 192.168.1.100:9777
```

---

## 클라우드 배포

### AWS EC2

```bash
# 1. Ubuntu 22.04 인스턴스 생성
# 2. 보안 그룹 설정: 9777(P2P), 9776(RPC) 인바운드 허용

# Docker 설치
sudo apt update
sudo apt install -y docker.io docker-compose
sudo usermod -aG docker $USER

# 배포
git clone https://github.com/imgyeongsu/blockchain.git
cd blockchain
docker-compose up -d
```

### Google Cloud / Azure

동일한 방식으로 Docker 설치 후 배포

---

## 글로벌 네트워크 구성

### 시드 노드 설정

1. 공인 IP가 있는 서버에 시드 노드 배포
2. DNS 설정 (선택사항): `seed1.ssatto777.site`
3. 방화벽에서 9777 포트 개방

### 일반 노드 연결

```bash
# 시드 노드 지정
docker run -d \
  --name jackpot-node \
  -p 9777:9777 \
  -p 9776:9776 \
  jackpotchain \
  node --seed seed1.ssatto777.site:9777
```

### DNS 시드 업데이트

`jackpotchain/network/discovery.py`의 DNS_SEEDS 수정:
```python
DNS_SEEDS = [
    "seed1.ssatto777.site",
    "seed2.ssatto777.site",
]
```

---

## 운영 명령어

### 상태 확인

```bash
# 체인 정보
curl -X POST http://localhost:9776 -d '{"method":"getblockchaininfo","params":[],"id":1}'

# 피어 정보
curl -X POST http://localhost:9776 -d '{"method":"getpeerinfo","params":[],"id":1}'

# 멤풀 상태
curl -X POST http://localhost:9776 -d '{"method":"getmempoolinfo","params":[],"id":1}'
```

### 지갑 생성

```bash
# 컨테이너 내부에서
docker exec -it jackpot-node python -m jackpotchain.cli.main wallet create
```

### 로그 확인

```bash
docker logs -f jackpot-node
```

---

## 모니터링 (향후)

- Prometheus metrics endpoint
- Grafana 대시보드
- AlertManager 알림

---

## 문제 해결

### 피어 연결 안됨
1. 방화벽 9777 포트 확인
2. 시드 노드 주소 확인
3. `peers.json` 삭제 후 재시작

### 블록 동기화 안됨
1. 피어 연결 상태 확인 (`getpeerinfo`)
2. 체인 높이 비교 (`getblockchaininfo`)
3. 로그에서 오류 확인

### 채굴 안됨
1. `--mine` 플래그 확인
2. `--address` 유효한 주소인지 확인
3. CPU 사용량 확인
