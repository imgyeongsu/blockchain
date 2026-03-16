"""
Network Widget

네트워크 화면
"""

from textual.app import ComposeResult
from textual.widgets import Static, Label, DataTable
from textual.containers import Container, Horizontal, Vertical

from ..client import RPCClient


class NetworkWidget(Container):
    """네트워크 위젯"""

    def __init__(self, rpc: RPCClient, **kwargs):
        super().__init__(**kwargs)
        self.rpc = rpc

    def compose(self) -> ComposeResult:
        # 노드 상태
        yield Vertical(
            Label("NODE STATUS", classes="box-title"),
            Horizontal(Label("Version", classes="stat-label"), Label("/JackpotChain:0.1.0/", id="node-version", classes="stat-value")),
            Horizontal(Label("Connections", classes="stat-label"), Label("--", id="connections", classes="stat-value cyan")),
            Horizontal(Label("Inbound", classes="stat-label"), Label("--", id="inbound", classes="stat-value green")),
            Horizontal(Label("Outbound", classes="stat-label"), Label("--", id="outbound", classes="stat-value")),
            classes="stat-box",
        )

        # 피어 목록
        yield Vertical(
            Label("CONNECTED PEERS", classes="box-title"),
            DataTable(id="peers-table"),
            classes="stat-box",
        )

    def on_mount(self) -> None:
        """마운트 시"""
        table = self.query_one("#peers-table", DataTable)
        table.add_columns("Address", "Height", "Dir")
        self.refresh_data()
        self.set_interval(5, self.refresh_data)

    def refresh_data(self) -> None:
        """데이터 새로고침"""
        self.run_worker(self._load_data())

    async def _load_data(self) -> None:
        """비동기 데이터 로드"""
        resp = await self.rpc.get_network_info()
        if resp.success:
            data = resp.result
            self.query_one("#connections", Label).update(str(data.get("connections", 0)))
            self.query_one("#inbound", Label).update(str(data.get("connections_in", 0)))
            self.query_one("#outbound", Label).update(str(data.get("connections_out", 0)))
            self.query_one("#node-version", Label).update(data.get("subversion", "/JackpotChain/"))

        resp = await self.rpc.get_peer_info()
        if resp.success:
            peers = resp.result or []
            table = self.query_one("#peers-table", DataTable)
            table.clear()

            for p in peers:
                addr = p.get("addr", "?")[:25]
                height = p.get("startingheight", 0)
                direction = "IN" if p.get("inbound") else "OUT"
                table.add_row(addr, f"H:{height}", direction)
