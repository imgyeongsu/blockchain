"""
Dashboard Widget

메인 요약 화면
"""

from textual.app import ComposeResult
from textual.widgets import Static, Label
from textual.containers import ScrollableContainer, Horizontal, Vertical

from ..client import RPCClient


class DashboardWidget(ScrollableContainer):
    """대시보드 위젯"""

    def __init__(self, rpc: RPCClient, **kwargs):
        super().__init__(**kwargs)
        self.rpc = rpc

    def compose(self) -> ComposeResult:
        # 로고
        yield Static(
            "JACKPOT CHAIN\nUTXO Blockchain + On-chain Lottery",
            id="logo"
        )

        # 메인 그리드
        yield Horizontal(
            # 블록체인 상태
            Vertical(
                Label("BLOCKCHAIN", classes="box-title"),
                Horizontal(Label("Height", classes="stat-label"), Label("--", id="height", classes="stat-value cyan")),
                Horizontal(Label("Block Time", classes="stat-label"), Label("--", id="block-time", classes="stat-value")),
                Horizontal(Label("Status", classes="stat-label"), Label("● CONNECTING", id="sync-status", classes="stat-value yellow")),
                classes="stat-box",
            ),
            # 지갑 상태
            Vertical(
                Label("WALLET", classes="box-title"),
                Horizontal(Label("JACK", classes="stat-label"), Label("--", id="jack-balance", classes="stat-value green")),
                Horizontal(Label("POT", classes="stat-label"), Label("--", id="pot-balance", classes="stat-value yellow")),
                Horizontal(Label("Peers", classes="stat-label"), Label("--", id="peer-count", classes="stat-value")),
                classes="stat-box",
            ),
            id="main-grid",
        )

        # 잭팟 풀
        yield Vertical(
            Label("JACKPOT POOL", classes="box-title-gold"),
            Label("-- JACK", id="jackpot-pool", classes="jackpot-amount"),
            id="jackpot-box",
        )

    def on_mount(self) -> None:
        """마운트 시 데이터 로드"""
        self.refresh_data()
        self.set_interval(5, self.refresh_data)

    def refresh_data(self) -> None:
        """데이터 새로고침"""
        self.run_worker(self._load_data())

    async def _load_data(self) -> None:
        """비동기 데이터 로드"""
        # 블록체인 정보
        resp = await self.rpc.get_blockchain_info()
        if resp.success:
            data = resp.result
            height = data.get("blocks", 0)
            self.query_one("#height", Label).update(f"#{height:,}")
            self.query_one("#sync-status", Label).update("● SYNCED")
            self.query_one("#sync-status").remove_class("yellow")
            self.query_one("#sync-status").add_class("green")
        else:
            self.query_one("#sync-status", Label).update("● DISCONNECTED")
            self.query_one("#sync-status").remove_class("green")
            self.query_one("#sync-status").add_class("red")

        # 지갑 잔액
        resp = await self.rpc.get_balance()
        if resp.success:
            balance = resp.result or 0
            self.query_one("#jack-balance", Label).update(f"{balance:,.2f}")

        # 네트워크 정보
        resp = await self.rpc.get_network_info()
        if resp.success:
            data = resp.result
            peers = data.get("connections", 0)
            self.query_one("#peer-count", Label).update(f"{peers} connected")

        # 잭팟 풀
        resp = await self.rpc.get_jackpot_pool()
        if resp.success:
            data = resp.result
            pool = data.get("balance", 0)
            self.query_one("#jackpot-pool", Label).update(f"{pool:,.0f} JACK")
