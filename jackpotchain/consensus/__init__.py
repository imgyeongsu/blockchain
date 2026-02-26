"""
Consensus 모듈
- 난이도 조정, 채굴, 체인 관리
"""

from .difficulty import (
    compact_to_target,
    target_to_compact,
    calculate_difficulty_ratio,
    calculate_new_difficulty,
    get_next_difficulty,
    verify_difficulty,
    hash_meets_target,
)
from .miner import (
    MiningResult,
    create_coinbase_tx,
    create_block_template,
    mine_block,
    update_block_timestamp,
    estimate_mining_time,
)
from .chain import (
    ChainState,
    ChainTip,
    BlockIndex,
    Blockchain,
)

__all__ = [
    'compact_to_target', 'target_to_compact', 'calculate_difficulty_ratio',
    'calculate_new_difficulty', 'get_next_difficulty', 'verify_difficulty',
    'hash_meets_target',
    'MiningResult', 'create_coinbase_tx', 'create_block_template',
    'mine_block', 'update_block_timestamp', 'estimate_mining_time',
    'ChainState', 'ChainTip', 'BlockIndex', 'Blockchain',
]
