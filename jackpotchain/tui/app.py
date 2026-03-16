"""
JackpotChain TUI Main Application

textual 기반 메인 앱 (ContentSwitcher 방식)
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, ContentSwitcher, Static
from textual.containers import Container, Horizontal

from .widgets.dashboard import DashboardWidget
from .widgets.wallet import WalletWidget
from .widgets.mining import MiningWidget
from .widgets.lotto import LottoWidget
from .widgets.claims import ClaimsWidget
from .widgets.network import NetworkWidget
from .client import RPCClient


class JackpotChainApp(App):
    """JackpotChain TUI 메인 앱"""

    CSS_PATH = "styles.tcss"
    TITLE = "JackpotChain"
    SUB_TITLE = "UTXO Blockchain + On-chain Lottery"

    BINDINGS = [
        Binding("f1", "show_tab('dashboard')", "Dashboard", show=True, priority=True),
        Binding("f2", "show_tab('wallet')", "Wallet", show=True, priority=True),
        Binding("f3", "show_tab('mining')", "Mining", show=True, priority=True),
        Binding("f4", "show_tab('lotto')", "Lotto", show=True, priority=True),
        Binding("f5", "show_tab('claims')", "Claims", show=True, priority=True),
        Binding("f6", "show_tab('network')", "Network", show=True, priority=True),
        Binding("ctrl+r", "refresh", "Refresh", show=True, priority=True),
        Binding("ctrl+q", "quit", "Quit", show=True, priority=True),
    ]

    def __init__(self, host: str = "127.0.0.1", port: int = 8332):
        super().__init__()
        self.rpc = RPCClient(host, port)
        self._current_tab = "dashboard"

    def compose(self) -> ComposeResult:
        """UI 구성"""
        yield Header()

        # 메뉴 바
        yield Horizontal(
            Static("[1] Dashboard", id="menu-dashboard", classes="menu-item active"),
            Static("[2] Wallet", id="menu-wallet", classes="menu-item"),
            Static("[3] Mining", id="menu-mining", classes="menu-item"),
            Static("[4] Lotto", id="menu-lotto", classes="menu-item"),
            Static("[5] Claims", id="menu-claims", classes="menu-item"),
            Static("[6] Network", id="menu-network", classes="menu-item"),
            id="menu-bar",
        )

        yield ContentSwitcher(
            DashboardWidget(self.rpc, id="dashboard"),
            WalletWidget(self.rpc, id="wallet"),
            MiningWidget(self.rpc, id="mining"),
            LottoWidget(self.rpc, id="lotto"),
            ClaimsWidget(self.rpc, id="claims"),
            NetworkWidget(self.rpc, id="network"),
            initial="dashboard",
            id="content",
        )

        yield Footer()

    def on_mount(self) -> None:
        """앱 마운트 시"""
        self._update_header()
        self._update_menu()

    async def on_unmount(self) -> None:
        """앱 언마운트 시"""
        await self.rpc.close()

    def action_show_tab(self, tab_name: str) -> None:
        """탭 전환"""
        self._current_tab = tab_name
        self.query_one("#content", ContentSwitcher).current = tab_name
        self._update_header()
        self._update_menu()
        self.action_refresh()

    def _update_header(self) -> None:
        """헤더 업데이트"""
        titles = {
            "dashboard": "Dashboard",
            "wallet": "Wallet",
            "mining": "Mining",
            "lotto": "Lotto",
            "claims": "Claims",
            "network": "Network",
        }
        self.sub_title = titles.get(self._current_tab, "Dashboard")

    def _update_menu(self) -> None:
        """메뉴 바 업데이트"""
        tabs = ["dashboard", "wallet", "mining", "lotto", "claims", "network"]
        for tab in tabs:
            menu_item = self.query_one(f"#menu-{tab}", Static)
            if tab == self._current_tab:
                menu_item.add_class("active")
            else:
                menu_item.remove_class("active")

    def on_click(self, event) -> None:
        """메뉴 클릭 처리"""
        widget_id = event.widget.id
        if widget_id and widget_id.startswith("menu-"):
            tab_name = widget_id.replace("menu-", "")
            self.action_show_tab(tab_name)

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
