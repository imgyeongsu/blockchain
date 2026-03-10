"""
JackpotChain - 가챠 시스템이 내장된 블록체인

Features:
- UTXO 기반 (Bitcoin 스타일)
- 듀얼 에셋: JACK (기본), POT (가챠 토큰)
- Commit-Reveal 기반 공정한 가챠
- 30초 블록 타임
"""

__version__ = "0.1.0"
__author__ = "JackpotChain Team"

# Core exports
from .core import Transaction, Block, UTXO, UTXOSet
from .consensus import Blockchain, mine_block
from .wallet import Wallet

__all__ = [
    '__version__',
    'Transaction', 'Block', 'UTXO', 'UTXOSet',
    'Blockchain', 'mine_block',
    'Wallet',
]
