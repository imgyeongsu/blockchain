"""
로또/가챠 모듈 (16-2 Final)
- 잭팟 풀
- 6자리 로또 Commit-Claim
- 게임 로직
"""

from .pool import (
    PoolTransaction,
    EntryDistribution,
    JackpotPool,
    calculate_pool_contribution,
    calculate_entry_distribution,
)
from .commit_reveal import (
    CommitStatus,
    LottoPrize,
    CommitRecord,
    generate_commit,
    verify_commit,
    extract_result_digit,
    calculate_result_digits,
    count_matches,
    determine_prize,
    calculate_payout,
    get_comparison_heights,
    is_claim_valid,
    get_commit_status,
    blocks_until_claimable,
    blocks_until_expire,
    CommitStore,
    # 레거시 호환
    calculate_winning_slot,
    check_win,
    is_reveal_valid,
)
from .game import (
    LottoPlayResult,
    LottoGame,
    # 레거시 별칭
    GachaPlayResult,
    GachaGame,
)
from .service import (
    GachaEvent,
    GachaEventData,
    GachaEventEmitter,
    GachaConfig,
    GachaType,
    StandardGacha,
    HighRiskGacha,
    PendingCommit,
    GachaService,
    create_gacha_service,
)

__all__ = [
    # Pool
    'PoolTransaction', 'EntryDistribution', 'JackpotPool',
    'calculate_pool_contribution', 'calculate_entry_distribution',
    # Lotto (16-2 Final)
    'CommitStatus', 'LottoPrize', 'CommitRecord',
    'generate_commit', 'verify_commit',
    'extract_result_digit', 'calculate_result_digits',
    'count_matches', 'determine_prize', 'calculate_payout',
    'get_comparison_heights', 'is_claim_valid', 'get_commit_status',
    'blocks_until_claimable', 'blocks_until_expire', 'CommitStore',
    # Game
    'LottoPlayResult', 'LottoGame',
    'GachaPlayResult', 'GachaGame',  # 레거시 별칭
    # Service
    'GachaEvent', 'GachaEventData', 'GachaEventEmitter',
    'GachaConfig', 'GachaType', 'StandardGacha', 'HighRiskGacha',
    'PendingCommit', 'GachaService', 'create_gacha_service',
    # 레거시 호환
    'calculate_winning_slot', 'check_win', 'is_reveal_valid',
]
