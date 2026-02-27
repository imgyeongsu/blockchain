"""
Gacha 모듈
- 잭팟 풀
- Commit-Reveal 난수
- 게임 로직
"""

from .pool import (
    PoolTransaction,
    JackpotPool,
    calculate_pool_contribution,
)
from .commit_reveal import (
    CommitStatus,
    CommitRecord,
    generate_commit,
    verify_commit,
    calculate_winning_slot,
    check_win,
    is_reveal_valid,
    get_commit_status,
    blocks_until_reveal,
    blocks_until_expire,
    CommitStore,
)
from .game import (
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
    'PoolTransaction', 'JackpotPool', 'calculate_pool_contribution',
    'CommitStatus', 'CommitRecord',
    'generate_commit', 'verify_commit', 'calculate_winning_slot',
    'check_win', 'is_reveal_valid', 'get_commit_status',
    'blocks_until_reveal', 'blocks_until_expire', 'CommitStore',
    'GachaPlayResult', 'GachaGame',
    # Service
    'GachaEvent', 'GachaEventData', 'GachaEventEmitter',
    'GachaConfig', 'GachaType', 'StandardGacha', 'HighRiskGacha',
    'PendingCommit', 'GachaService', 'create_gacha_service',
]
