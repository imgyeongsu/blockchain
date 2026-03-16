"""
Mining Widget

채굴 화면
"""

from textual.app import ComposeResult
from textual.widgets import Static, Label, Button, ProgressBar
from textual.containers import Container, Horizontal, Vertical

from ..client import RPCClient


class MiningWidget(Container):
    """채굴 위젯"""

    def __init__(self, rpc: RPCClient, **kwargs):
        super().__init__(**kwargs)
        self.rpc = rpc

    def compose(self) -> ComposeResult:
        # 채굴 상태
        yield Vertical(
            Label("MINING STATUS", classes="box-title"),
            Horizontal(Label("Status", classes="stat-label"), Label("⏹ STOPPED", id="mining-status", classes="stat-value red")),
            Horizontal(Label("Hash Rate", classes="stat-label"), Label("-- H/s", id="hash-rate", classes="stat-value")),
            Horizontal(Label("Block", classes="stat-label"), Label("--", id="current-block", classes="stat-value cyan")),
            classes="stat-box",
        )

        # 통계
        yield Vertical(
            Label("STATISTICS", classes="box-title"),
            Horizontal(Label("Difficulty", classes="stat-label"), Label("--", id="difficulty", classes="stat-value")),
            Horizontal(Label("Mempool TXs", classes="stat-label"), Label("--", id="mempool-txs", classes="stat-value")),
            classes="stat-box",
        )

        # 알림
        yield Label("Mining: Use CLI 'python -m jackpotchain.cli mine'", id="mining-notice", classes="notice")

    def on_mount(self) -> None:
        """마운트 시"""
        self.refresh_data()
        self.set_interval(3, self.refresh_data)

    def refresh_data(self) -> None:
        """데이터 새로고침"""
        self.run_worker(self._load_data())

    async def _load_data(self) -> None:
        """비동기 데이터 로드"""
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

            self.query_one("#mempool-txs", Label).update(str(data.get("pooledtx", 0)))
