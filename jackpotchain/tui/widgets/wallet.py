"""
Wallet Widget

지갑 화면
"""

from textual.app import ComposeResult
from textual.widgets import Static, Label, Input, Button, DataTable
from textual.containers import Container, Horizontal, Vertical

from ..client import RPCClient


class WalletWidget(Container):
    """지갑 위젯"""

    def __init__(self, rpc: RPCClient, **kwargs):
        super().__init__(**kwargs)
        self.rpc = rpc

    def compose(self) -> ComposeResult:
        # 지갑 정보
        yield Vertical(
            Label("MY WALLET", classes="box-title"),
            Horizontal(Label("Address", classes="stat-label"), Label("--", id="wallet-address", classes="stat-value cyan")),
            Horizontal(Label("JACK", classes="stat-label"), Label("--", id="w-jack-balance", classes="stat-value green")),
            Horizontal(Label("POT", classes="stat-label"), Label("--", id="w-pot-balance", classes="stat-value yellow")),
            Horizontal(Label("UTXOs", classes="stat-label"), Label("--", id="utxo-count", classes="stat-value")),
            classes="stat-box",
        )

        # Exchange 영역
        yield Vertical(
            Label("EXCHANGE (100 JACK = 1 POT)", classes="box-title"),
            Horizontal(
                Label("JACK:", classes="stat-label"),
                Input(placeholder="100", id="exchange-amount", classes="exchange-input"),
                Button("Exchange", id="btn-exchange", variant="warning"),
                classes="exchange-row",
            ),
            classes="stat-box",
        )

        # 상태 메시지
        yield Label("", id="wallet-status", classes="status-msg")

        # 액션 버튼
        yield Horizontal(
            Button("New Address", id="btn-new-addr", variant="primary"),
            classes="action-buttons",
        )

    def on_mount(self) -> None:
        """마운트 시"""
        self.refresh_data()
        self.set_interval(10, self.refresh_data)

    def refresh_data(self) -> None:
        """데이터 새로고침"""
        self.run_worker(self._load_data())

    async def _load_data(self) -> None:
        """비동기 데이터 로드"""
        # 잔액
        resp = await self.rpc.get_balance()
        if resp.success:
            balance = resp.result or 0
            self.query_one("#w-jack-balance", Label).update(f"{balance:,.2f} JACK")

        # UTXO 목록
        resp = await self.rpc.list_unspent()
        if resp.success:
            utxos = resp.result or []
            self.query_one("#utxo-count", Label).update(str(len(utxos)))

            # POT 잔액 계산
            pot_balance = 0
            for utxo in utxos:
                assets = utxo.get("assets", {})
                pot_balance += assets.get("POT", 0)

            if pot_balance > 0:
                self.query_one("#w-pot-balance", Label).update(f"{pot_balance / 1e8:.2f} POT")
            else:
                self.query_one("#w-pot-balance", Label).update("0 POT")

            # 첫 번째 UTXO에서 주소 추출
            if utxos and "address" in utxos[0]:
                addr = utxos[0]["address"]
                display = f"{addr[:16]}...{addr[-8:]}" if len(addr) > 26 else addr
                self.query_one("#wallet-address", Label).update(display)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭 처리"""
        btn_id = event.button.id
        if btn_id == "btn-new-addr":
            self.run_worker(self._generate_new_address())
        elif btn_id == "btn-exchange":
            self.run_worker(self._exchange_to_pot())

    async def _generate_new_address(self) -> None:
        """새 주소 생성"""
        resp = await self.rpc.get_new_address()
        if resp.success:
            self.query_one("#wallet-address", Label).update(resp.result)
            self.query_one("#wallet-status", Label).update(f"New address: {resp.result}")
        else:
            self.query_one("#wallet-status", Label).update(f"Error: {resp.error}")

    async def _exchange_to_pot(self) -> None:
        """JACK → POT 교환"""
        amount_str = self.query_one("#exchange-amount", Input).value.strip()

        if not amount_str:
            self.query_one("#wallet-status", Label).update("Enter JACK amount (min 100)")
            return

        try:
            amount = float(amount_str)
            if amount < 100:
                self.query_one("#wallet-status", Label).update("Minimum 100 JACK required")
                return
        except ValueError:
            self.query_one("#wallet-status", Label).update("Invalid amount")
            return

        self.query_one("#wallet-status", Label).update("Exchanging...")

        resp = await self.rpc.exchange_to_pot(amount)
        if resp.success:
            data = resp.result
            pot_received = data.get("pot_received", 0)
            self.query_one("#wallet-status", Label).update(
                f"Success! Received {pot_received:.2f} POT"
            )
            self.query_one("#exchange-amount", Input).value = ""
            self.refresh_data()
        else:
            self.query_one("#wallet-status", Label).update(f"Error: {resp.error}")
