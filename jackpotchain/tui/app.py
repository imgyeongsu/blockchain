"""
JackpotChain TUI Main Application

textual 기반 메인 앱 (ContentSwitcher 방식)
"""

import os
from pathlib import Path
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
from ..wallet.wallet import Wallet


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

    def __init__(self, host: str = "127.0.0.1", port: int = 8332, wallet_dir: str = None):
        super().__init__()
        self.rpc = RPCClient(host, port)
        self._current_tab = "dashboard"

        # 지갑 상태 - %APPDATA%\JackpotChain\wallets 고정
        if wallet_dir is None:
            appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
            wallet_dir = os.path.join(appdata, 'JackpotChain', 'wallets')
        self.wallet_dir = Path(wallet_dir)
        self.wallet_dir.mkdir(parents=True, exist_ok=True)
        self.current_wallet: Wallet | None = None
        self.current_wallet_file: Path | None = None
        self.selected_address: str | None = None

        # 기본 지갑 로드 시도
        self._load_default_wallet()

    def _load_default_wallet(self) -> None:
        """기본 지갑 로드"""
        default_path = self.wallet_dir / "default.json"
        if default_path.exists():
            self.load_wallet(default_path)
        # 없으면 None 상태 유지 (Wallet 탭에서 생성 유도)

    def load_wallet(self, wallet_path: Path) -> bool:
        """지갑 파일 로드"""
        try:
            self.current_wallet = Wallet(str(wallet_path))
            self.current_wallet_file = wallet_path
            # 첫 번째 주소 선택
            addresses = self.current_wallet.get_addresses()
            if addresses:
                self.selected_address = addresses[0]
            return True
        except Exception:
            return False

    def create_wallet(self, wallet_name: str) -> bool:
        """새 지갑 생성"""
        wallet_path = self.wallet_dir / f"{wallet_name}.json"
        if wallet_path.exists():
            return False
        try:
            self.current_wallet = Wallet(str(wallet_path))
            self.current_wallet_file = wallet_path
            # 첫 번째 주소 자동 생성
            self.selected_address = self.current_wallet.generate_address(label="기본")
            return True
        except Exception:
            return False

    def get_wallet_files(self) -> list[Path]:
        """지갑 파일 목록"""
        return list(self.wallet_dir.glob("*.json"))

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
