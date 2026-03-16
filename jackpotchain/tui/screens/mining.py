"""
Mining Screen

채굴 화면
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Label, Button, ProgressBar
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive

from ..client import RPCClient


class MiningScreen(Screen):
    """채굴 화면"""

    is_mining = reactive(False)
    hash_rate = reactive(0.0)
    blocks_mined = reactive(0)
    total_rewards = reactive(0.0)
    difficulty = reactive("")
    mempool_txs = reactive(0)

    def __init__(self, rpc: RPCClient):
        super().__init__()
        self.rpc = rpc

    def compose(self) -> ComposeResult:
        yield Container(
            # 채굴 상태
            Vertical(
                Label("MINING STATUS", classes="box-title"),
                Horizontal(
                    Label("Status", classes="stat-label"),
                    Label("⏹ STOPPED", id="mining-status", classes="stat-value red"),
                ),
                Horizontal(
                    Label("Hash Rate", classes="stat-label"),
                    Label("-- H/s", id="hash-rate", classes="stat-value"),
                ),
                Horizontal(
                    Label("Current Block", classes="stat-label"),
                    Label("--", id="current-block", classes="stat-value cyan"),
                ),
                ProgressBar(id="mining-progress", total=100, show_eta=False),
                classes="stat-box",
            ),

            # 통계
            Vertical(
                Label("STATISTICS", classes="box-title"),
                Horizontal(
                    Label("Blocks Mined", classes="stat-label"),
                    Label("--", id="blocks-mined", classes="stat-value cyan"),
                ),
                Horizontal(
                    Label("Total Rewards", classes="stat-label"),
                    Label("--", id="total-rewards", classes="stat-value green"),
                ),
                Horizontal(
                    Label("Difficulty", classes="stat-label"),
                    Label("--", id="difficulty", classes="stat-value"),
                ),
                Horizontal(
                    Label("Mempool TXs", classes="stat-label"),
                    Label("--", id="mempool-txs", classes="stat-value"),
                ),
                classes="stat-box",
            ),

            # 컨트롤
            Vertical(
                Horizontal(
                    Button("[Space] Start Mining", id="btn-toggle-mining", variant="success"),
                    classes="action-buttons",
                ),
                classes="stat-box",
            ),

            # 상태 메시지
            Label("Mining is not available in TUI mode. Use CLI miner.", id="mining-notice", classes="notice"),

            id="mining-screen",
        )

    def on_mount(self) -> None:
        """마운트 시"""
        self.refresh_data()
        self.set_interval(3, self.refresh_data)

    def refresh_data(self) -> None:
        """데이터 새로고침"""
        self.run_worker(self._load_data())

    async def _load_data(self) -> None:
        """비동기 데이터 로드"""
        # 채굴 정보
        resp = await self.rpc.get_mining_info()
        if resp.success:
            data = resp.result
            self.query_one("#current-block", Label).update(f"#{data.get('blocks', 0):,}")

            difficulty = data.get("difficulty", 0)
            if isinstance(difficulty, int):
                self.query_one("#difficulty", Label).update(f"0x{difficulty:08x}")
            else:
                self.query_one("#difficulty", Label).update(str(difficulty))

            hashps = data.get("networkhashps", 0)
            if hashps > 1_000_000:
                self.query_one("#hash-rate", Label).update(f"{hashps/1_000_000:.2f} MH/s")
            elif hashps > 1_000:
                self.query_one("#hash-rate", Label).update(f"{hashps/1_000:.2f} KH/s")
            else:
                self.query_one("#hash-rate", Label).update(f"{hashps:.0f} H/s")

            self.mempool_txs = data.get("pooledtx", 0)
            self.query_one("#mempool-txs", Label).update(str(self.mempool_txs))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭 처리"""
        if event.button.id == "btn-toggle-mining":
            # TUI에서는 채굴 직접 제어 안 함
            self.query_one("#mining-notice", Label).update(
                "Mining control not available in TUI. Use: python -m jackpotchain.cli mine"
            )
