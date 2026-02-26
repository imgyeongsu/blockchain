"""
암호학 모듈
- 해시, 서명, 주소, 머클트리
"""

from .hash import sha256, double_sha256, hash160
from .signature import generate_keypair, sign, verify, private_key_to_public_key
from .address import (
    pubkey_to_address,
    pubkey_hash_to_address,
    validate_address,
    address_to_pubkey_hash,
    is_system_address,
    is_jackpot_address,
    is_burn_address,
    JACKPOT_POOL_ADDRESS,
    BURN_ADDRESS
)
from .merkle import build_merkle_tree, get_merkle_proof, verify_merkle_proof

__all__ = [
    'sha256', 'double_sha256', 'hash160',
    'generate_keypair', 'sign', 'verify', 'private_key_to_public_key',
    'pubkey_to_address', 'pubkey_hash_to_address', 'validate_address', 'address_to_pubkey_hash',
    'is_system_address', 'is_jackpot_address', 'is_burn_address',
    'JACKPOT_POOL_ADDRESS', 'BURN_ADDRESS',
    'build_merkle_tree', 'get_merkle_proof', 'verify_merkle_proof',
]
