"""
Wallet Widget

지갑 화면 (목업 디자인 기준)
"""

from textual.app import ComposeResult
from textual.widgets import Static, Label, Input, Button, DataTable
from textual.containers import ScrollableContainer, Horizontal, Vertical

from ..client import RPCClient
from ...crypto.address import validate_address


class WalletWidget(ScrollableContainer):
    """지갑 위젯"""

    def __init__(self, rpc: RPCClient, **kwargs):
        super().__init__(**kwargs)
        self.rpc = rpc

    def compose(self) -> ComposeResult:
        # MY WALLET 박스
        yield Vertical(
            Label("MY WALLET", classes="box-title"),
            Horizontal(
                Label("Address", classes="stat-label"),
                Label("--", id="wallet-address", classes="stat-value cyan"),
            ),
            Horizontal(
                Label("JACK Balance", classes="stat-label"),
                Label("--", id="w-jack-balance", classes="stat-value green"),
            ),
            Horizontal(
                Label("POT Balance", classes="stat-label"),
                Label("--", id="w-pot-balance", classes="stat-value yellow"),
            ),
            Horizontal(
                Label("UTXOs", classes="stat-label"),
                Label("--", id="utxo-count", classes="stat-value"),
            ),
            classes="stat-box",
        )

        # RECENT TRANSACTIONS 박스
        yield Vertical(
            Label("RECENT TRANSACTIONS", classes="box-title"),
            DataTable(id="tx-table"),
            classes="stat-box",
        )

        # ACTIONS 박스
        yield Vertical(
            Label("ACTIONS", classes="box-title"),
            Horizontal(
                Button("[S] Send", id="btn-send-modal", variant="success", classes="action-btn"),
                Button("[E] Exchange", id="btn-exchange-modal", variant="warning", classes="action-btn"),
                Button("[R] Receive", id="btn-receive", variant="primary", classes="action-btn"),
                classes="action-row",
            ),
            classes="stat-box",
        )

        # 상태 메시지
        yield Label("", id="wallet-status", classes="status-msg")

        # 숨겨진 Send/Exchange 입력 영역 (모달 대신)
        yield Vertical(
            Label("SEND JACK", classes="box-title"),
            Horizontal(
                Label("To:", classes="stat-label"),
                Input(placeholder="Address", id="send-address"),
            ),
            Horizontal(
                Label("Amount:", classes="stat-label"),
                Input(placeholder="0.00", id="send-amount"),
                Button("Send", id="btn-send", variant="success"),
            ),
            id="send-panel",
            classes="stat-box hidden",
        )

        yield Vertical(
            Label("EXCHANGE (100 JACK = 1 POT)", classes="box-title"),
            Horizontal(
                Label("JACK:", classes="stat-label"),
                Input(placeholder="100", id="exchange-amount"),
                Button("Exchange", id="btn-exchange", variant="warning"),
            ),
            id="exchange-panel",
            classes="stat-box hidden",
        )

    def on_mount(self) -> None:
        """마운트 시"""
        # 테이블 컬럼 설정
        table = self.query_one("#tx-table", DataTable)
        table.add_columns("TxID", "Amount", "Time")
        table.cursor_type = "row"

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
                self.query_one("#wallet-address", Label).update(addr)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭 처리"""
        btn_id = event.button.id

        if btn_id == "btn-send-modal":
            self._toggle_panel("send-panel")
        elif btn_id == "btn-exchange-modal":
            self._toggle_panel("exchange-panel")
        elif btn_id == "btn-receive":
            self.run_worker(self._generate_new_address())
        elif btn_id == "btn-exchange":
            self.run_worker(self._exchange_to_pot())
        elif btn_id == "btn-send":
            self.run_worker(self._send_transaction())

    def _toggle_panel(self, panel_id: str) -> None:
        """패널 토글"""
        panel = self.query_one(f"#{panel_id}")
        if panel.has_class("hidden"):
            # 다른 패널 숨기기
            for p in ["send-panel", "exchange-panel"]:
                self.query_one(f"#{p}").add_class("hidden")
            panel.remove_class("hidden")
        else:
            panel.add_class("hidden")

    async def _generate_new_address(self) -> None:
        """새 주소 생성"""
        resp = await self.rpc.get_new_address()
        if resp.success:
            self.query_one("#wallet-address", Label).update(resp.result)
            self.query_one("#wallet-status", Label).update(f"New address: {resp.result}")
        else:
            self.query_one("#wallet-status", Label).update(f"Error: {resp.error}")

    async def _send_transaction(self) -> None:
        """JACK 송금"""
        address = self.query_one("#send-address", Input).value.strip()
        amount_str = self.query_one("#send-amount", Input).value.strip()

        if not address:
            self.query_one("#wallet-status", Label).update("Enter recipient address")
            return

        if not validate_address(address):
            self.query_one("#wallet-status", Label).update("Invalid address (checksum failed)")
            return

        if not amount_str:
            self.query_one("#wallet-status", Label).update("Enter amount")
            return

        try:
            amount = float(amount_str)
            if amount <= 0:
                self.query_one("#wallet-status", Label).update("Amount must be > 0")
                return
        except ValueError:
            self.query_one("#wallet-status", Label).update("Invalid amount")
            return

        self.query_one("#wallet-status", Label).update("Sending...")

        resp = await self.rpc.send_to_address(address, amount)
        if resp.success:
            txid = resp.result
            self.query_one("#wallet-status", Label).update(
                f"Sent! TxID: {txid[:16]}..."
            )
            self.query_one("#send-address", Input).value = ""
            self.query_one("#send-amount", Input).value = ""
            self.query_one("#send-panel").add_class("hidden")
            self.refresh_data()
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
            self.query_one("#exchange-panel").add_class("hidden")
            self.refresh_data()
        else:
            self.query_one("#wallet-status", Label).update(f"Error: {resp.error}")
