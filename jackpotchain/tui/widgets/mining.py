"""
Mining Widget

채굴 화면
"""

from textual.app import ComposeResult
from textual.widgets import Label, Button
from textual.containers import ScrollableContainer, Horizontal, Vertical

from ..client import RPCClient


class MiningWidget(ScrollableContainer):
    """채굴 위젯"""

    can_focus = False

    def __init__(self, rpc: RPCClient, **kwargs):
        super().__init__(**kwargs)
        self.rpc = rpc

    def compose(self) -> ComposeResult:
        # 채굴 상태
        yield Vertical(
            Label("MINING STATUS", classes="box-title"),
            Horizontal(Label("Status", classes="stat-label"), Label("⏹ STOPPED", id="mining-status", classes="stat-value red")),
            Horizontal(Label("Address", classes="stat-label"), Label("--", id="mining-address", classes="stat-value cyan")),
            Horizontal(Label("Hash Rate", classes="stat-label"), Label("-- H/s", id="hash-rate", classes="stat-value")),
            Horizontal(Label("Blocks Mined", classes="stat-label"), Label("0", id="blocks-mined", classes="stat-value green")),
            classes="stat-box",
        )

        # 통계
        yield Vertical(
            Label("BLOCKCHAIN", classes="box-title"),
            Horizontal(Label("Height", classes="stat-label"), Label("--", id="current-block", classes="stat-value cyan")),
            Horizontal(Label("Difficulty", classes="stat-label"), Label("--", id="difficulty", classes="stat-value")),
            Horizontal(Label("Mempool TXs", classes="stat-label"), Label("--", id="mempool-txs", classes="stat-value")),
            classes="stat-box",
        )

        # 컨트롤 버튼
        yield Vertical(
            Label("CONTROLS", classes="box-title"),
            Horizontal(
                Button("Start Mining", id="btn-start", variant="success"),
                Button("Stop Mining", id="btn-stop", variant="error"),
                classes="action-buttons",
            ),
            classes="stat-box",
        )

        # 상태 메시지
        yield Label("", id="mining-msg", classes="status-msg")

    def on_mount(self) -> None:
        """마운트 시"""
        self.refresh_data()
        self.set_interval(2, self.refresh_data)

    def refresh_data(self) -> None:
        """데이터 새로고침"""
        self.run_worker(self._load_data())

    async def _load_data(self) -> None:
        """비동기 데이터 로드"""
        resp = await self.rpc.get_mining_info()
        if resp.success:
            data = resp.result
            self.query_one("#current-block", Label).update(f"#{data.get('blocks', 0):,}")

            # 난이도
            difficulty = data.get("difficulty", 0)
            if isinstance(difficulty, int):
                self.query_one("#difficulty", Label).update(f"0x{difficulty:08x}")
            else:
                self.query_one("#difficulty", Label).update(str(difficulty))

            # Mempool
            self.query_one("#mempool-txs", Label).update(str(data.get("pooledtx", 0)))

            # 채굴 상태
            is_mining = data.get("mining", False)
            if is_mining:
                status_label = self.query_one("#mining-status", Label)
                status_label.update("⛏ MINING")
                status_label.remove_class("red")
                status_label.add_class("green")

                # 주소
                addr = data.get("mining_address", "")
                if addr:
                    display = f"{addr[:12]}...{addr[-6:]}" if len(addr) > 20 else addr
                    self.query_one("#mining-address", Label).update(display)

                # 해시레이트
                hashrate = data.get("hashrate", 0)
                if hashrate > 1_000_000:
                    self.query_one("#hash-rate", Label).update(f"{hashrate/1_000_000:.2f} MH/s")
                elif hashrate > 1_000:
                    self.query_one("#hash-rate", Label).update(f"{hashrate/1_000:.2f} KH/s")
                else:
                    self.query_one("#hash-rate", Label).update(f"{hashrate:.2f} H/s")

                # 채굴된 블록
                self.query_one("#blocks-mined", Label).update(str(data.get("blocks_mined", 0)))
            else:
                status_label = self.query_one("#mining-status", Label)
                status_label.update("⏹ STOPPED")
                status_label.remove_class("green")
                status_label.add_class("red")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭"""
        if event.button.id == "btn-start":
            self.run_worker(self._start_mining())
        elif event.button.id == "btn-stop":
            self.run_worker(self._stop_mining())

    async def _start_mining(self) -> None:
        """채굴 시작"""
        resp = await self.rpc.start_mining()
        if resp.success:
            result = resp.result
            self.query_one("#mining-msg", Label).update(
                f"Mining started! Address: {result.get('address', '')[:20]}..."
            )
        else:
            self.query_one("#mining-msg", Label).update(f"Error: {resp.error}")
        self.refresh_data()

    async def _stop_mining(self) -> None:
        """채굴 중지"""
        resp = await self.rpc.stop_mining()
        if resp.success:
            result = resp.result
            self.query_one("#mining-msg", Label).update(
                f"Mining stopped. Blocks mined: {result.get('blocks_mined', 0)}"
            )
        else:
            self.query_one("#mining-msg", Label).update(f"Error: {resp.error}")
        self.refresh_data()
