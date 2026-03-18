"""
JackpotChain 전역 상수
"""

# =============================================================================
# 네트워크 파라미터
# =============================================================================
NETWORK_MAGIC = b'\xf9\xbe\xb4\xd9'  # 메시지 헤더 매직 바이트
DEFAULT_PORT = 8333
DEFAULT_RPC_PORT = 8332

# =============================================================================
# 블록 파라미터
# =============================================================================
BLOCK_TIME_TARGET = 30           # 목표 블록 간격 (초)
DIFFICULTY_ADJUSTMENT_INTERVAL = 50  # 난이도 조절 주기 (블록)
MAX_BLOCK_SIZE = 1_000_000       # 최대 블록 크기 (1 MB)
MAX_BLOCK_WEIGHT = 4_000_000     # SegWit 가중치 (미사용)

# 초기 난이도 (compact format)
# 0x1d00ffff = 비트코인 메인넷 (~4B 해시, ~24시간)
# 0x1e100000 = 테스트넷 (~1M 해시, ~20초)
# 0x1e200000 = 테스트넷 초기 난이도
# 0x1f00ffff = 개발용 (~65K 해시, ~1초)
INITIAL_DIFFICULTY = 0x1e200000  # 테스트넷 초기 난이도

# =============================================================================
# 보상 및 수수료
# =============================================================================
BLOCK_REWARD = 50_00_000_000     # 50 JACK (satoshi 단위)
MIN_TX_FEE = 1_000_000           # 최소 수수료 0.01 JACK
MIN_RELAY_FEE = 1_000_000        # 최소 릴레이 수수료

# 수수료 분배 비율 (백분율)
FEE_MINER_PERCENT = 50           # 채굴자 50%
FEE_JACKPOT_PERCENT = 30         # 잭팟 풀 30%
FEE_BURN_PERCENT = 20            # 소각 20%

# 수수료 분배 비율 (소수)
FEE_MINER_RATIO = 0.50           # 채굴자 50%
FEE_JACKPOT_RATIO = 0.30         # 잭팟 풀 30%
FEE_BURN_RATIO = 0.20            # 소각 20%

# =============================================================================
# 에셋 파라미터
# =============================================================================
ASSET_ID_JACK = "JACK"           # 네이티브 코인
ASSET_ID_POT = "POT"             # 가챠 토큰
JACK_ASSET_ID = ASSET_ID_JACK    # 별칭 (호환성)
POT_ASSET_ID = ASSET_ID_POT      # 별칭 (호환성)

DECIMALS_JACK = 8                # JACK 소수점 자릿수
DECIMALS_POT = 8                 # POT 소수점 자릿수

EXCHANGE_RATE = 100              # 100 JACK = 1 POT
MIN_JACK_OUTPUT = 1_000_000      # UTXO 최소 JACK (0.01 JACK)

MAX_MONEY = 21_000_000_00_000_000  # 이론적 최대값 (무제한이지만 안전 한계)
COIN = 100_000_000               # 1 JACK = 10^8 satoshi

# =============================================================================
# 로또 파라미터 (16-2 Final 기준)
# =============================================================================
# 참가비
LOTTO_COST_JACK = 100 * COIN     # 100 JACK (→ 1 POT 교환)
LOTTO_COST_POT = 1 * COIN        # 1 POT (Commit TX 참가비)
GACHA_COST_POT = LOTTO_COST_POT  # 하위 호환

# 숫자 선택
LOTTO_DIGIT_COUNT = 6            # 6자리
LOTTO_DIGIT_BASE = 16            # hex 0x0 ~ 0xf

# 비교 블록
LOTTO_BLOCK_INTERVAL = 3         # 비교 블록 간격
LOTTO_COMPARISON_OFFSETS = [3, 6, 9, 12, 15, 18]  # N+3, N+6, ..., N+18

# Claim 윈도우
LOTTO_MIN_CLAIM_GAP = 18         # N+18 이후 Claim 가능
LOTTO_MAX_CLAIM_GAP = 68         # N+68까지 Claim 가능 (50블록 여유)
GACHA_MIN_REVEAL_GAP = LOTTO_MIN_CLAIM_GAP  # 하위 호환
GACHA_MAX_REVEAL_GAP = LOTTO_MAX_CLAIM_GAP  # 하위 호환

# 참가비 분배 (100 JACK 기준) - 백분율
LOTTO_POOL_PERCENT = 80          # 80% → 잭팟 풀
LOTTO_BURN_PERCENT = 19          # 19% → 소각
LOTTO_MINER_PERCENT = 1          # 1% → 채굴자 보상

# 참가비 분배 (소수) - DEPRECATED, 호환용
LOTTO_POOL_RATIO = 0.80
LOTTO_BURN_RATIO = 0.19
LOTTO_MINER_RATIO = 0.01

# 등급별 보상
LOTTO_PRIZE_1ST_PERCENT = 50     # 1등: 잭팟 풀의 50%
LOTTO_PRIZE_1ST_RATIO = 0.50     # DEPRECATED, 호환용
LOTTO_PRIZE_2ND = 100_000 * COIN # 2등: 100,000 JACK
LOTTO_PRIZE_3RD = 20_000 * COIN  # 3등: 20,000 JACK
LOTTO_PRIZE_4TH = 2_000 * COIN   # 4등: 2,000 JACK
LOTTO_PRIZE_5TH = 300 * COIN     # 5등: 300 JACK
LOTTO_PRIZE_6TH_POT = 1 * COIN   # 6등: 1 POT (mint - 참가비 환불)
LOTTO_PRIZE_6TH_JACK = 100 * COIN # 6등 대안: 100 JACK (deprecated)

# 하위 호환 (deprecated)
GACHA_WIN_PROBABILITY = 1 / (16 ** 6)  # 1등 확률 참고용
GACHA_PAYOUT_RATIO = LOTTO_PRIZE_1ST_RATIO

# =============================================================================
# TX 버전
# =============================================================================
TX_VERSION_TRANSFER = 1          # 일반 전송
TX_VERSION_EXCHANGE = 2          # JACK → POT 교환
TX_VERSION_GACHA_COMMIT = 3      # 가챠 Commit (= 로또 Commit)
TX_VERSION_GACHA_REVEAL = 4      # 가챠 Reveal (deprecated)
TX_VERSION_LOTTO_CLAIM = 5       # 로또 Claim (신규)
TX_VERSION_COMMIT = TX_VERSION_GACHA_COMMIT   # 별칭
TX_VERSION_REVEAL = TX_VERSION_GACHA_REVEAL   # 별칭 (deprecated)
TX_VERSION_CLAIM = TX_VERSION_LOTTO_CLAIM     # 별칭

# =============================================================================
# 시퀀스 번호
# =============================================================================
SEQUENCE_FINAL = 0xFFFFFFFF      # 최종 (RBF 비활성)
SEQUENCE_LOCKTIME_DISABLE = 0xFFFFFFFF

# =============================================================================
# 시간 관련
# =============================================================================
MAX_FUTURE_BLOCK_TIME = 2 * 60 * 60  # 블록 타임스탬프 최대 미래 허용 (2시간)
MAX_BLOCK_TIME_DRIFT = MAX_FUTURE_BLOCK_TIME  # 별칭
TARGET_BLOCK_TIME = BLOCK_TIME_TARGET  # 별칭

# =============================================================================
# 난이도 관련
# =============================================================================
MAX_DIFFICULTY_CHANGE = 4        # 난이도 최대 변화율 (x4 또는 /4)

# =============================================================================
# Coinbase 관련
# =============================================================================
COINBASE_MATURITY = 100          # Coinbase 사용 가능까지 필요한 확인 수

# =============================================================================
# 네트워크 제한
# =============================================================================
MAX_OUTBOUND_CONNECTIONS = 8
MAX_INBOUND_CONNECTIONS = 32  # 시드노드는 많은 연결 수용
MAX_INV_SIZE = 50000             # INV 메시지 최대 항목
MAX_HEADERS_SIZE = 2000          # HEADERS 응답 최대 개수

# =============================================================================
# Hole Punch / Rendezvous
# =============================================================================
DEFAULT_RENDEZVOUS_PORT = DEFAULT_PORT + 1  # 8334
HOLEPUNCH_TIMEOUT = 10           # 홀펀칭 전체 타임아웃 (초)
HOLEPUNCH_RETRY_COUNT = 10       # 동시 TCP open 재시도 횟수
HOLEPUNCH_RETRY_DELAY = 0.5      # 재시도 간격 (초)
RENDEZVOUS_HEARTBEAT_INTERVAL = 30   # 하트비트 간격 (초)
RENDEZVOUS_STALE_TIMEOUT = 120       # 등록 만료 (초)

# =============================================================================
# Mempool 제한
# =============================================================================
MAX_MEMPOOL_SIZE = 300 * 1024 * 1024  # 300 MB
MAX_TX_SIZE = 100_000            # 단일 TX 최대 크기 (100 KB)

# =============================================================================
# Genesis Block
# =============================================================================
GENESIS_TIMESTAMP = 1735689600   # 2025-01-01 00:00:00 UTC
GENESIS_MESSAGE = b"JackpotChain Genesis - 2025"
GENESIS_JACKPOT_POOL_FUNDING = 1_000_000 * COIN  # 100만 JACK 잭팟풀 초기 자금

# 하드코딩된 제네시스 블록 값 (AWS 시드 노드에서 생성)
GENESIS_NONCE = 0
GENESIS_MERKLE_ROOT = bytes.fromhex("802a573854dabc3c2b7afd5bf3e80a2c0c3549125769550c260ca2509d485d74")
GENESIS_HASH = bytes.fromhex("c41d65b3c0b76dea7142202a37f5b10f8275aba8370387636e35640e30c7a0d9")
