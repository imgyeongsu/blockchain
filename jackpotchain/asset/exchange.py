"""
Step 6.2: JACK → POT 교환
- 100 JACK = 1 POT (일방향)
- JACK은 소각됨
"""

from typing import Tuple, Optional
from dataclasses import dataclass

from ..core.transaction import Transaction, TxInput, TxOutput
from ..script.standard import create_p2pkh_script_pubkey, create_op_return_script
from ..crypto.address import address_to_pubkey_hash, validate_address, BURN_ADDRESS
from ..constants import (
    EXCHANGE_RATE,
    TX_VERSION_EXCHANGE,
    COIN,
    ASSET_ID_POT,
)


@dataclass
class ExchangeResult:
    """교환 결과"""
    success: bool
    pot_amount: int = 0     # 받는 POT (satoshi 단위)
    jack_burned: int = 0    # 소각되는 JACK
    jack_change: int = 0    # 잔돈 JACK
    error: str = ""


def calculate_exchange(jack_amount: int) -> ExchangeResult:
    """
    JACK → POT 교환 계산

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
    jack_burned = (pot_amount // COIN) * exchange_unit
    jack_change = jack_amount - jack_burned

    return ExchangeResult(
        success=True,
        pot_amount=pot_amount,
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

    # 2. OP_RETURN (소각 기록)
    burn_data = f"EXCHANGE:{result.jack_burned}".encode()
    burn_output = TxOutput(
        jack_value=0,
        script_pubkey=create_op_return_script(burn_data)
    )
    outputs.append(burn_output)

    # 3. JACK 잔돈 (있으면)
    change_jack = total_input - result.jack_burned
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
    - OP_RETURN 소각 기록
    - 금액 일치
    """
    if tx.version != TX_VERSION_EXCHANGE:
        return False, "Invalid TX version for exchange"

    # POT 출력 찾기
    pot_output = None
    burn_output = None

    for out in tx.outputs:
        if ASSET_ID_POT in out.assets:
            pot_output = out
        if out.script_pubkey and out.script_pubkey[0] == 0x6a:  # OP_RETURN
            burn_output = out

    if pot_output is None:
        return False, "No POT output found"

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

    # 금액 검증
    pot_amount = pot_output.assets.get(ASSET_ID_POT, 0)
    expected_pot = calculate_exchange(burned_jack)

    if not expected_pot.success or pot_amount != expected_pot.pot_amount:
        return False, "Exchange amount mismatch"

    return True, ""


def get_exchange_info(tx: Transaction) -> Optional[dict]:
    """교환 TX 정보 추출"""
    if tx.version != TX_VERSION_EXCHANGE:
        return None

    info = {
        'jack_burned': 0,
        'pot_received': 0,
        'jack_change': 0,
    }

    for out in tx.outputs:
        if ASSET_ID_POT in out.assets:
            info['pot_received'] = out.assets[ASSET_ID_POT]
        elif out.jack_value > 0:
            info['jack_change'] = out.jack_value

    # OP_RETURN에서 소각량 추출
    for out in tx.outputs:
        if out.script_pubkey and out.script_pubkey[0] == 0x6a:
            from ..script.standard import extract_op_return_data
            data = extract_op_return_data(out.script_pubkey)
            if data and data.startswith(b'EXCHANGE:'):
                try:
                    info['jack_burned'] = int(data[9:].decode())
                except ValueError:
                    pass

    return info
