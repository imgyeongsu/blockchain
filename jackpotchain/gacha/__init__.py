"""
로또/가챠 모듈 (자동 지급 방식)
- 잭팟 풀
- 6자리 로또 Commit + 자동 지급
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
    extract_result_digit,
    calculate_result_digits,
    count_matches,
    determine_prize,
    calculate_payout,
    get_comparison_heights,
    get_commit_status,
    CommitStore,
    # 레거시 호환
    verify_commit,
    is_claim_valid,
    blocks_until_claimable,
    blocks_until_expire,
    calculate_winning_slot,
    check_win,
    is_reveal_valid,
)
from .game import (
    LottoPlayResult,
    PayoutInfo,
    LottoGame,
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
    PendingCommit,
    GachaService,
    create_gacha_service,
)

__all__ = [
    'PoolTransaction', 'EntryDistribution', 'JackpotPool',
    'calculate_pool_contribution', 'calculate_entry_distribution',
    'CommitStatus', 'LottoPrize', 'CommitRecord',
    'generate_commit', 'verify_commit',
    'extract_result_digit', 'calculate_result_digits',
    'count_matches', 'determine_prize', 'calculate_payout',
    'get_comparison_heights', 'get_commit_status',
    'CommitStore',
    'LottoPlayResult', 'PayoutInfo', 'LottoGame',
    'GachaPlayResult', 'GachaGame',
    'GachaEvent', 'GachaEventData', 'GachaEventEmitter',
    'GachaConfig', 'GachaType', 'StandardGacha',
    'PendingCommit', 'GachaService', 'create_gacha_service',
]
