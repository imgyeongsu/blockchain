"""
JackpotChain TUI Main Application

textual 기반 메인 앱 (ContentSwitcher 방식)
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Static, Label, ContentSwitcher
from textual.containers import Container, Horizontal, Vertical

from .widgets.dashboard import DashboardWidget
from .widgets.wallet import WalletWidget
from .widgets.mining import MiningWidget
from .widgets.lotto import LottoWidget
from .widgets.network import NetworkWidget
from .client import RPCClient


class JackpotChainApp(App):
    """JackpotChain TUI 메인 앱"""

    CSS_PATH = "styles.tcss"
    TITLE = "JackpotChain"
    SUB_TITLE = "UTXO Blockchain + On-chain Lottery"

    BINDINGS = [
        Binding("1", "show_tab('dashboard')", "[1] Dashboard", show=True),
        Binding("2", "show_tab('wallet')", "[2] Wallet", show=True),
        Binding("3", "show_tab('mining')", "[3] Mining", show=True),
        Binding("4", "show_tab('lotto')", "[4] Lotto", show=True),
        Binding("5", "show_tab('network')", "[5] Network", show=True),
        Binding("r", "refresh", "[R] Refresh", show=True),
        Binding("q", "quit", "[Q] Quit", show=True),
    ]

    def __init__(self, host: str = "127.0.0.1", port: int = 8332):
        super().__init__()
        self.rpc = RPCClient(host, port)
        self._current_tab = "dashboard"

    def compose(self) -> ComposeResult:
        """UI 구성"""
        yield Header()

        # 탭 메뉴
        yield Horizontal(
            Static("[1] Dashboard", id="tab-dashboard", classes="tab active"),
            Static("[2] Wallet", id="tab-wallet", classes="tab"),
            Static("[3] Mining", id="tab-mining", classes="tab"),
            Static("[4] Lotto", id="tab-lotto", classes="tab"),
            Static("[5] Network", id="tab-network", classes="tab"),
            id="tab-bar",
        )

        # 컨텐츠 영역
        yield ContentSwitcher(
            DashboardWidget(self.rpc, id="dashboard"),
            WalletWidget(self.rpc, id="wallet"),
            MiningWidget(self.rpc, id="mining"),
            LottoWidget(self.rpc, id="lotto"),
            NetworkWidget(self.rpc, id="network"),
            initial="dashboard",
            id="content",
        )

        yield Footer()

    def on_mount(self) -> None:
        """앱 마운트 시"""
        self._update_tabs()

    async def on_unmount(self) -> None:
        """앱 언마운트 시"""
        await self.rpc.close()

    def action_show_tab(self, tab_name: str) -> None:
        """탭 전환"""
        self._current_tab = tab_name
        self.query_one("#content", ContentSwitcher).current = tab_name
        self._update_tabs()
        self.action_refresh()

    def _update_tabs(self) -> None:
        """탭 스타일 업데이트"""
        for tab in ["dashboard", "wallet", "mining", "lotto", "network"]:
            tab_widget = self.query_one(f"#tab-{tab}", Static)
            if tab == self._current_tab:
                tab_widget.add_class("active")
            else:
                tab_widget.remove_class("active")

    def action_refresh(self) -> None:
        """현재 탭 새로고침"""
        current = self.query_one(f"#{self._current_tab}")
        if hasattr(current, "refresh_data"):
            current.refresh_data()


def run_tui(host: str = "127.0.0.1", port: int = 8332):
    """TUI 실행"""
    app = JackpotChainApp(host, port)
    app.run()


if __name__ == "__main__":
    run_tui()
