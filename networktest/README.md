# JackpotChain Network Test

네트워크 기능 분리 테스트용 프로젝트

## 파일 구조

```
networktest/
├── run_node.py        # 단일 노드 실행
├── multi_node_test.py # 멀티 노드 테스트
└── README.md
```

## 단일 노드 실행

### 기본 실행

```bash
cd networktest
python run_node.py 8333
```

### 시드 노드 모드

시드 노드는 랑데부 서버를 함께 실행합니다.

```bash
python run_node.py 8333 --seed
```

### 다른 노드에 연결

```bash
python run_node.py 8335 --connect 192.168.0.10:8333
```

### NAT 비활성화

```bash
python run_node.py 8333 --no-nat
```

### 홀펀치 사용 (랑데부 시드 지정)

```bash
python run_node.py 8335 --rendezvous 192.168.0.10:8334
```

## 멀티 노드 테스트

### 기본 테스트 (3노드)

```bash
python multi_node_test.py
```

### 홀펀치 테스트

```bash
python multi_node_test.py --holepunch
```

## NAT Traversal 순서

1. **PCP** (Port Control Protocol)
2. **NAT-PMP** (NAT Port Mapping Protocol)
3. **UPnP** (Universal Plug and Play)
4. **TCP Hole Punch** (랑데부 서버 필요)
5. **Manual** (수동 포트포워딩 감지)
6. **Outbound Only** (실패 시)

## 테스트 시나리오

### 1. 로컬 테스트 (같은 PC)

```bash
# 터미널 1: 시드 노드
python run_node.py 8333 --seed

# 터미널 2: 일반 노드
python run_node.py 8335 --connect 127.0.0.1:8333

# 터미널 3: 또 다른 노드
python run_node.py 8337 --connect 127.0.0.1:8333
```

### 2. LAN 테스트 (집 네트워크)

```bash
# PC A (시드): 192.168.0.10
python run_node.py 8333 --seed

# PC B: 192.168.0.20
python run_node.py 8333 --connect 192.168.0.10:8333
```

### 3. WAN 테스트 (인터넷)

```bash
# 시드 서버 (공인 IP or 포트포워딩)
python run_node.py 8333 --seed

# 클라이언트 (NAT 뒤)
python run_node.py 8333 --connect SEED_IP:8333 --rendezvous SEED_IP:8334
```

## 출력 예시

```
============================================================
JackpotChain Network Test Node
============================================================
  Port: 8333
  Mode: SEED NODE (랑데부 서버)
  NAT:  활성
============================================================

[Starting]...
[Rendezvous] 랑데부 서버 시작 - 포트 8334
[NAT] 수동 포트포워딩 감지 - 인바운드 가능 (203.0.113.1:8333)

[Running] Ctrl+C to stop
------------------------------------------------------------

[Status] Height: 0 | Peers: 2 | External: 203.0.113.1:8333
  [IN] 192.168.0.20:54321 (ready, h=0)
  [OUT] 192.168.0.30:8333 (ready, h=0)
```

## 주의사항

- 시드 노드는 반드시 인바운드 가능해야 함
- 홀펀치는 양쪽 모두 랑데부 서버에 등록되어 있어야 작동
- Windows에서 SO_REUSEPORT 미지원으로 일부 제한
