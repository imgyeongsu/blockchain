"""
Wallet Screen

지갑 화면
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Label, Input, Button, DataTable
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive

from ..client import RPCClient


class WalletScreen(Screen):
    """지갑 화면"""

    address = reactive("")
    jack_balance = reactive(0.0)
    pot_balance = reactive(0)
    utxo_count = reactive(0)

    def __init__(self, rpc: RPCClient):
        super().__init__()
        self.rpc = rpc

    def compose(self) -> ComposeResult:
        yield Container(
            # 지갑 정보
            Vertical(
                Label("MY WALLET", classes="box-title"),
                Horizontal(
                    Label("Address", classes="stat-label"),
                    Label("--", id="wallet-address", classes="stat-value cyan"),
                ),
                Horizontal(
                    Label("JACK Balance", classes="stat-label"),
                    Label("--", id="jack-balance", classes="stat-value green"),
                ),
                Horizontal(
                    Label("POT Balance", classes="stat-label"),
                    Label("--", id="pot-balance", classes="stat-value yellow"),
                ),
                Horizontal(
                    Label("UTXOs", classes="stat-label"),
                    Label("--", id="utxo-count", classes="stat-value"),
                ),
                classes="stat-box",
            ),

            # 최근 거래
            Vertical(
                Label("RECENT TRANSACTIONS", classes="box-title"),
                DataTable(id="tx-table"),
                classes="stat-box",
            ),

            # 액션 버튼
            Vertical(
                Label("ACTIONS", classes="box-title"),
                Horizontal(
                    Button("[S] Send", id="btn-send", variant="success"),
                    Button("[E] Exchange", id="btn-exchange", variant="warning"),
                    Button("[N] New Address", id="btn-new-addr", variant="primary"),
                    classes="action-buttons",
                ),
                classes="stat-box",
            ),

            # 송금 폼 (숨김)
            Vertical(
                Label("SEND JACK", classes="box-title"),
                Horizontal(
                    Label("To:", classes="input-label"),
                    Input(placeholder="Recipient address", id="send-address"),
                ),
                Horizontal(
                    Label("Amount:", classes="input-label"),
                    Input(placeholder="0.00", id="send-amount"),
                ),
                Horizontal(
                    Button("Send", id="btn-confirm-send", variant="success"),
                    Button("Cancel", id="btn-cancel-send", variant="error"),
                ),
                id="send-form",
                classes="hidden",
            ),

            # 교환 폼 (숨김)
            Vertical(
                Label("EXCHANGE JACK → POT", classes="box-title"),
                Static("Rate: 100 JACK = 1 POT", classes="info-text"),
                Horizontal(
                    Label("JACK:", classes="input-label"),
                    Input(placeholder="100", id="exchange-amount"),
                ),
                Horizontal(
                    Button("Exchange", id="btn-confirm-exchange", variant="warning"),
                    Button("Cancel", id="btn-cancel-exchange", variant="error"),
                ),
                id="exchange-form",
                classes="hidden",
            ),

            # 상태 메시지
            Label("", id="wallet-status"),

            id="wallet-screen",
        )

    def on_mount(self) -> None:
        """마운트 시"""
        # 테이블 설정
        table = self.query_one("#tx-table", DataTable)
        table.add_columns("TxID", "Amount", "Time")

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
            self.jack_balance = resp.result or 0
            self.query_one("#jack-balance", Label).update(f"{self.jack_balance:,.2f} JACK")

        # UTXO 목록
        resp = await self.rpc.list_unspent()
        if resp.success:
            utxos = resp.result or []
            self.utxo_count = len(utxos)
            self.query_one("#utxo-count", Label).update(str(self.utxo_count))

            # 첫 번째 UTXO에서 주소 추출
            if utxos and "address" in utxos[0]:
                self.address = utxos[0]["address"]
                addr_display = f"{self.address[:20]}...{self.address[-8:]}" if len(self.address) > 30 else self.address
                self.query_one("#wallet-address", Label).update(addr_display)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭 처리"""
        btn_id = event.button.id

        if btn_id == "btn-send":
            self._show_send_form()
        elif btn_id == "btn-exchange":
            self._show_exchange_form()
        elif btn_id == "btn-new-addr":
            self.run_worker(self._generate_new_address())
        elif btn_id == "btn-cancel-send":
            self._hide_send_form()
        elif btn_id == "btn-cancel-exchange":
            self._hide_exchange_form()
        elif btn_id == "btn-confirm-send":
            self.run_worker(self._send_transaction())
        elif btn_id == "btn-confirm-exchange":
            self.run_worker(self._exchange_to_pot())

    def _show_send_form(self) -> None:
        """송금 폼 표시"""
        self.query_one("#send-form").remove_class("hidden")
        self.query_one("#exchange-form").add_class("hidden")

    def _hide_send_form(self) -> None:
        """송금 폼 숨김"""
        self.query_one("#send-form").add_class("hidden")

    def _show_exchange_form(self) -> None:
        """교환 폼 표시"""
        self.query_one("#exchange-form").remove_class("hidden")
        self.query_one("#send-form").add_class("hidden")

    def _hide_exchange_form(self) -> None:
        """교환 폼 숨김"""
        self.query_one("#exchange-form").add_class("hidden")

    async def _generate_new_address(self) -> None:
        """새 주소 생성"""
        resp = await self.rpc.get_new_address()
        if resp.success:
            self.address = resp.result
            self.query_one("#wallet-address", Label).update(self.address)
            self.query_one("#wallet-status", Label).update(f"New address: {self.address}")
        else:
            self.query_one("#wallet-status", Label).update(f"Error: {resp.error}")

    async def _send_transaction(self) -> None:
        """송금 실행"""
        address = self.query_one("#send-address", Input).value
        amount_str = self.query_one("#send-amount", Input).value

        try:
            amount = float(amount_str)
        except ValueError:
            self.query_one("#wallet-status", Label).update("Invalid amount")
            return

        resp = await self.rpc.send_to_address(address, amount)
        if resp.success:
            self.query_one("#wallet-status", Label).update(f"Sent! TxID: {resp.result[:16]}...")
            self._hide_send_form()
            self.refresh_data()
        else:
            self.query_one("#wallet-status", Label).update(f"Error: {resp.error}")

    async def _exchange_to_pot(self) -> None:
        """JACK → POT 교환"""
        amount_str = self.query_one("#exchange-amount", Input).value

        try:
            amount = float(amount_str)
        except ValueError:
            self.query_one("#wallet-status", Label).update("Invalid amount")
            return

        resp = await self.rpc.exchange_to_pot(amount)
        if resp.success:
            data = resp.result
            pot = data.get("pot_received", 0)
            self.query_one("#wallet-status", Label).update(f"Exchanged! Received {pot} POT")
            self._hide_exchange_form()
            self.refresh_data()
        else:
            self.query_one("#wallet-status", Label).update(f"Error: {resp.error}")
