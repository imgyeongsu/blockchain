"""
Step 6.2: JACK → POT 교환
- 100 JACK = 1 POT (일방향)
- JACK은 소각됨
"""

from typing import Tuple, Optional
from dataclasses import dataclass

from ..core.transaction import Transaction, TxInput, TxOutput
from ..script.standard import create_p2pkh_script_pubkey, create_op_return_script
from ..crypto.address import address_to_pubkey_hash, validate_address, BURN_ADDRESS, JACKPOT_POOL_ADDRESS
from ..constants import (
    EXCHANGE_RATE,
    TX_VERSION_EXCHANGE,
    COIN,
    ASSET_ID_POT,
    LOTTO_POOL_PERCENT,
    LOTTO_BURN_PERCENT,
)


@dataclass
class ExchangeResult:
    """교환 결과"""
    success: bool
    pot_amount: int = 0       # 받는 POT (satoshi 단위)
    jack_to_pool: int = 0     # 잭팟 풀 (80%)
    jack_burned: int = 0      # 소각 (19%)
    jack_change: int = 0      # 잔돈 JACK
    error: str = ""


def calculate_exchange(jack_amount: int) -> ExchangeResult:
    """
    JACK → POT 교환 계산

    분배:
    - 80% → 잭팟 풀 적립
    - 19% → 소각
    - 1% → 채굴자 (수수료로 처리)

    Args:
        jack_amount: 교환할 JACK (satoshi 단위)

    Returns:
        ExchangeResult
    """
    # 100 JACK (satoshi) = 1 POT (satoshi) at same decimal places
    # 실제로: 100 * COIN JACK satoshis = 1 * COIN POT satoshis
    exchange_unit = EXCHANGE_RATE * COIN  # 100 JACK in satoshis

    if jack_amount < exchange_unit:
        return ExchangeResult(
            success=False,
            error=f"Minimum {EXCHANGE_RATE} JACK required"
        )

    # 교환 가능한 POT 수량
    pot_amount = (jack_amount // exchange_unit) * COIN
    jack_exchanged = (pot_amount // COIN) * exchange_unit
    jack_change = jack_amount - jack_exchanged

    # 교환된 JACK 분배 (정수 연산)
    jack_to_pool = jack_exchanged * LOTTO_POOL_PERCENT // 100  # 80%
    jack_burned = jack_exchanged * LOTTO_BURN_PERCENT // 100   # 19%
    # 나머지 1%는 수수료로 채굴자에게 (TX에 포함하지 않음)

    return ExchangeResult(
        success=True,
        pot_amount=pot_amount,
        jack_to_pool=jack_to_pool,
        jack_burned=jack_burned,
        jack_change=jack_change
    )


def create_exchange_tx(
    inputs: list,           # List of (TxInput, UTXO)
    exchange_jack: int,     # 교환할 JACK
    recipient_address: str, # POT 받을 주소
    change_address: str     # JACK 잔돈 받을 주소
) -> Tuple[Optional[Transaction], str]:
    """
    교환 트랜잭션 생성

    Returns:
        (Transaction, error_message)
    """
    # 교환 계산
    result = calculate_exchange(exchange_jack)
    if not result.success:
        return None, result.error

    # 주소 유효성 검증
    if not validate_address(recipient_address):
        return None, f"Invalid recipient address: {recipient_address}"
    if not validate_address(change_address):
        return None, f"Invalid change address: {change_address}"

    # 총 입력 JACK
    total_input = sum(utxo.output.jack_value for _, utxo in inputs)
    if total_input < exchange_jack:
        return None, f"Insufficient funds: {total_input} < {exchange_jack}"

    # 입력 생성
    tx_inputs = [inp for inp, _ in inputs]

    # 출력 생성
    outputs = []

    # 1. POT 출력 (multi-asset)
    recipient_pubkey_hash = address_to_pubkey_hash(recipient_address)
    pot_output = TxOutput(
        jack_value=0,  # JACK 없음
        script_pubkey=create_p2pkh_script_pubkey(recipient_pubkey_hash),
        assets={ASSET_ID_POT: result.pot_amount}
    )
    outputs.append(pot_output)

    # 2. 잭팟 풀 (80%)
    if result.jack_to_pool > 0:
        pool_output = TxOutput(
            jack_value=result.jack_to_pool,
            script_pubkey=b'JACKPOT_POOL'  # 특수 마커 (miner.py와 동일)
        )
        outputs.append(pool_output)

    # 3. OP_RETURN (소각 기록 - 19%)
    burn_data = f"EXCHANGE:{result.jack_burned}".encode()
    burn_output = TxOutput(
        jack_value=0,
        script_pubkey=create_op_return_script(burn_data)
    )
    outputs.append(burn_output)

    # 4. JACK 잔돈 (있으면)
    # jack_exchanged = 100% (교환에 사용된 총 JACK)
    # = pool(80%) + burn(19%) + miner_fee(1%)
    # burn과 miner_fee는 출력 없음 (암시적 소각/수수료)
    jack_exchanged = (result.pot_amount // COIN) * EXCHANGE_RATE * COIN
    change_jack = total_input - jack_exchanged
    if change_jack > 0:
        change_pubkey_hash = address_to_pubkey_hash(change_address)
        change_output = TxOutput(
            jack_value=change_jack,
            script_pubkey=create_p2pkh_script_pubkey(change_pubkey_hash)
        )
        outputs.append(change_output)

    # 트랜잭션 생성
    tx = Transaction(
        version=TX_VERSION_EXCHANGE,
        inputs=tx_inputs,
        outputs=outputs,
        locktime=0
    )

    return tx, ""


def validate_exchange_tx(tx: Transaction) -> Tuple[bool, str]:
    """
    교환 트랜잭션 검증

    검증 항목:
    - 버전 확인
    - POT 출력 존재
    - 잭팟 풀 출력 존재 (80%)
    - OP_RETURN 소각 기록 (19%)
    - 금액 일치
    """
    if tx.version != TX_VERSION_EXCHANGE:
        return False, "Invalid TX version for exchange"

    # 출력 찾기
    pot_output = None
    pool_output = None
    burn_output = None

    for out in tx.outputs:
        if ASSET_ID_POT in out.assets:
            pot_output = out
        if out.script_pubkey == b'JACKPOT_POOL':
            pool_output = out
        if out.script_pubkey and len(out.script_pubkey) > 0 and out.script_pubkey[0] == 0x6a:  # OP_RETURN
            burn_output = out

    if pot_output is None:
        return False, "No POT output found"

    if pool_output is None:
        return False, "No jackpot pool output found"

    if burn_output is None:
        return False, "No burn record found"

    # 소각 기록 파싱
    try:
        from ..script.standard import extract_op_return_data
        burn_data = extract_op_return_data(burn_output.script_pubkey)
        if not burn_data or not burn_data.startswith(b'EXCHANGE:'):
            return False, "Invalid burn record format"

        burned_jack = int(burn_data[9:].decode())
    except (ValueError, UnicodeDecodeError):
        return False, "Cannot parse burn record"

    # 금액 검증 - POT
    pot_amount = pot_output.assets.get(ASSET_ID_POT, 0)
    jack_exchanged = (pot_amount // COIN) * EXCHANGE_RATE * COIN
    expected = calculate_exchange(jack_exchanged)

    if not expected.success:
        return False, "Invalid exchange amount"

    if pot_amount != expected.pot_amount:
        return False, "POT amount mismatch"

    # 금액 검증 - Pool (80%)
    if pool_output.jack_value != expected.jack_to_pool:
        return False, f"Pool amount mismatch: {pool_output.jack_value} != {expected.jack_to_pool}"

    # 금액 검증 - Burn (19%)
    if burned_jack != expected.jack_burned:
        return False, f"Burn amount mismatch: {burned_jack} != {expected.jack_burned}"

    return True, ""


def get_exchange_info(tx: Transaction) -> Optional[dict]:
    """교환 TX 정보 추출"""
    if tx.version != TX_VERSION_EXCHANGE:
        return None

    info = {
        'pot_received': 0,
        'jack_to_pool': 0,
        'jack_burned': 0,
        'jack_change': 0,
    }

    for out in tx.outputs:
        if ASSET_ID_POT in out.assets:
            info['pot_received'] = out.assets[ASSET_ID_POT]
        elif out.script_pubkey == b'JACKPOT_POOL':
            info['jack_to_pool'] = out.jack_value
        elif out.jack_value > 0:
            info['jack_change'] = out.jack_value

    # OP_RETURN에서 소각량 추출
    for out in tx.outputs:
        if out.script_pubkey and len(out.script_pubkey) > 0 and out.script_pubkey[0] == 0x6a:
            from ..script.standard import extract_op_return_data
            data = extract_op_return_data(out.script_pubkey)
            if data and data.startswith(b'EXCHANGE:'):
                try:
                    info['jack_burned'] = int(data[9:].decode())
                except ValueError:
                    pass

    return info
