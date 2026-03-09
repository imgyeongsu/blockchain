# 집에서 시드 노드 설정 가이드

## 목표
집 PC를 시드 노드로 만들어서 외부에서 연결 가능하게 하기

---

## 1. 사전 확인

```bash
# 내 내부 IP 확인
ipconfig | findstr IPv4
# 예: 192.168.0.10

# 공유기 게이트웨이 확인 (보통 192.168.0.1)
ipconfig | findstr "기본 게이트웨이"
```

---

## 2. 노드 실행 (먼저 테스트)

```bash
cd C:\Users\SSAFY\Desktop\hub\blockchain

# 지갑 주소 생성 (없으면)
python -m jackpotchain.cli.main wallet create

# 노드 + 채굴 실행
python -m jackpotchain.cli.main node --mine --address <지갑주소>
```

**확인할 것:**
```
[NAT] UPnP 매핑 성공: xxx.xxx.xxx.xxx:8333  ← 이거 나오면 자동 성공!
```

---

## 3. UPnP 성공한 경우

자동으로 포트 열림. 바로 테스트 가능.

```bash
# 외부 IP 확인 (로그에서 또는)
curl ifconfig.me
```

**싸피에서 테스트:**
```bash
python -m jackpotchain.cli.main node --seed <외부IP>:8333
```

---

## 4. UPnP 실패한 경우 (수동 포트포워딩)

### 4.1 공유기 관리 페이지 접속
```
브라우저에서: http://192.168.0.1
(또는 http://192.168.1.1)
```

### 4.2 포트포워딩 설정
| 항목 | 값 |
|------|-----|
| 외부 포트 | 8333 |
| 내부 IP | 192.168.0.10 (내 PC IP) |
| 내부 포트 | 8333 |
| 프로토콜 | TCP |

### 4.3 공유기별 메뉴 위치
- **ipTIME**: 관리도구 → 고급설정 → NAT/라우터 관리 → 포트포워드
- **KT 공유기**: 장치설정 → 트래픽관리 → 포트포워딩
- **SK 공유기**: 고급설정 → NAT설정 → 포트포워딩
- **LG U+**: 네트워크설정 → 포트포워딩

---

## 5. 외부 IP 확인

```bash
# 방법 1: 웹사이트
curl ifconfig.me

# 방법 2: 공유기 관리페이지에서 WAN IP 확인
```

---

## 6. 방화벽 설정 (Windows)

```powershell
# 관리자 권한으로 PowerShell 실행
netsh advfirewall firewall add rule name="JackpotChain P2P" dir=in action=allow protocol=tcp localport=8333
```

---

## 7. 포트 열림 확인

```bash
# 외부에서 확인 (싸피에서)
nc -zv <집외부IP> 8333

# 또는 온라인 도구
# https://www.yougetsignal.com/tools/open-ports/
```

---

## 8. discovery.py에 IP 추가 (선택)

영구적으로 시드 노드로 등록하려면:

```python
# jackpotchain/network/discovery.py

HARDCODED_SEEDS = [
    ("집외부IP", 8333),  # ← 추가
    ("127.0.0.1", DEFAULT_PORT),
]
```

---

## 9. 싸피에서 연결 테스트

```bash
# 싸피 PC에서
python -m jackpotchain.cli.main node --seed <집외부IP>:8333 --mine --address <지갑주소>
```

**성공 시 로그:**
```
[Peer] Connected to <집IP>:8333
[Sync] Syncing from height 0 to XXX
```

---

## 체크리스트

- [ ] 집 PC에서 노드 실행
- [ ] UPnP 성공 여부 확인
- [ ] (실패 시) 공유기 포트포워딩 설정
- [ ] Windows 방화벽 8333 허용
- [ ] 외부 IP 메모
- [ ] 포트 열림 테스트
- [ ] 싸피에서 연결 테스트

---

## 문제 해결

### 연결 안 됨
1. 방화벽 확인 (Windows + 공유기)
2. 포트포워딩 내부 IP가 맞는지 확인
3. 공유기 이중 NAT 확인 (ISP 공유기 + 개인 공유기)

### 이중 NAT인 경우
ISP 공유기(모뎀)에서도 포트포워딩 필요하거나, 브릿지 모드로 변경

### CGNAT (통신사 공유 IP)
일부 통신사는 공인 IP를 안 줌. 이 경우:
- 통신사에 공인 IP 요청 (유료일 수 있음)
- 또는 클라우드 서버 사용 (AWS/GCP)
