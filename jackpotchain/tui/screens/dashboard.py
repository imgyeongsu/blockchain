"""
Dashboard Screen

메인 요약 화면
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Label
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive

from ..client import RPCClient


class StatBox(Static):
    """통계 박스"""

    def __init__(self, title: str, **kwargs):
        super().__init__(**kwargs)
        self.title = title

    def compose(self) -> ComposeResult:
        yield Label(self.title, classes="box-title")
        yield Container(id="stats-content")


class DashboardScreen(Screen):
    """대시보드 화면"""

    # 데이터 상태
    height = reactive(0)
    block_time = reactive("--")
    sync_status = reactive("CONNECTING...")
    jack_balance = reactive(0.0)
    pot_balance = reactive(0)
    peer_count = reactive(0)
    jackpot_pool = reactive(0.0)

    def __init__(self, rpc: RPCClient):
        super().__init__()
        self.rpc = rpc

    def compose(self) -> ComposeResult:
        yield Container(
            # 로고
            Static(
                "╔══════════════════════════════════════════╗\n"
                "║          JACKPOT CHAIN                   ║\n"
                "║   UTXO Blockchain + On-chain Lottery     ║\n"
                "╚══════════════════════════════════════════╝",
                id="logo"
            ),

            # 메인 그리드
            Horizontal(
                # 블록체인 상태
                Vertical(
                    Label("BLOCKCHAIN", classes="box-title"),
                    Horizontal(
                        Label("Height", classes="stat-label"),
                        Label("--", id="height", classes="stat-value cyan"),
                    ),
                    Horizontal(
                        Label("Block Time", classes="stat-label"),
                        Label("--", id="block-time", classes="stat-value green"),
                    ),
                    Horizontal(
                        Label("Status", classes="stat-label"),
                        Label("● CONNECTING...", id="sync-status", classes="stat-value yellow"),
                    ),
                    classes="stat-box",
                ),

                # 지갑 상태
                Vertical(
                    Label("WALLET", classes="box-title"),
                    Horizontal(
                        Label("JACK", classes="stat-label"),
                        Label("--", id="jack-balance", classes="stat-value green"),
                    ),
                    Horizontal(
                        Label("POT", classes="stat-label"),
                        Label("--", id="pot-balance", classes="stat-value yellow"),
                    ),
                    Horizontal(
                        Label("Peers", classes="stat-label"),
                        Label("--", id="peer-count", classes="stat-value"),
                    ),
                    classes="stat-box",
                ),
                id="main-grid",
            ),

            # 잭팟 풀
            Vertical(
                Label("JACKPOT POOL", classes="box-title"),
                Label("-- JACK", id="jackpot-pool", classes="jackpot-amount"),
                id="jackpot-box",
            ),

            # 상태 메시지
            Label("Press [1-5] to switch screens, [R] to refresh, [Q] to quit", id="status-line"),

            id="dashboard",
        )

    def on_mount(self) -> None:
        """마운트 시 데이터 로드"""
        self.refresh_data()
        # 자동 갱신 (5초마다)
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
            self.height = data.get("blocks", 0)
            self.query_one("#height", Label).update(f"#{self.height:,}")
            self.query_one("#sync-status", Label).update("● SYNCED")
            self.query_one("#sync-status", Label).remove_class("yellow")
            self.query_one("#sync-status", Label).add_class("green")
        else:
            self.query_one("#sync-status", Label).update("● DISCONNECTED")
            self.query_one("#sync-status", Label).remove_class("green")
            self.query_one("#sync-status", Label).add_class("red")

        # 지갑 잔액
        resp = await self.rpc.get_balance()
        if resp.success:
            self.jack_balance = resp.result or 0
            self.query_one("#jack-balance", Label).update(f"{self.jack_balance:,.2f}")

        # 네트워크 정보
        resp = await self.rpc.get_network_info()
        if resp.success:
            data = resp.result
            self.peer_count = data.get("connections", 0)
            self.query_one("#peer-count", Label).update(f"{self.peer_count} connected")

        # 잭팟 풀
        resp = await self.rpc.get_jackpot_pool()
        if resp.success:
            data = resp.result
            self.jackpot_pool = data.get("balance", 0)
            self.query_one("#jackpot-pool", Label).update(f"{self.jackpot_pool:,.0f} JACK")
