"""
Network Screen

네트워크 화면
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Label, DataTable
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive

from ..client import RPCClient


class NetworkScreen(Screen):
    """네트워크 화면"""

    connections = reactive(0)
    inbound = reactive(0)
    outbound = reactive(0)

    def __init__(self, rpc: RPCClient):
        super().__init__()
        self.rpc = rpc

    def compose(self) -> ComposeResult:
        yield Container(
            # 노드 상태
            Vertical(
                Label("NODE STATUS", classes="box-title"),
                Horizontal(
                    Label("Version", classes="stat-label"),
                    Label("/JackpotChain:0.1.0/", id="node-version", classes="stat-value"),
                ),
                Horizontal(
                    Label("Connections", classes="stat-label"),
                    Label("--", id="connections", classes="stat-value cyan"),
                ),
                Horizontal(
                    Label("Inbound", classes="stat-label"),
                    Label("--", id="inbound", classes="stat-value green"),
                ),
                Horizontal(
                    Label("Outbound", classes="stat-label"),
                    Label("--", id="outbound", classes="stat-value"),
                ),
                classes="stat-box",
            ),

            # 피어 목록
            Vertical(
                Label("CONNECTED PEERS", classes="box-title"),
                DataTable(id="peers-table"),
                classes="stat-box",
            ),

            # 대역폭 (placeholder)
            Vertical(
                Label("BANDWIDTH", classes="box-title"),
                Horizontal(
                    Label("Received", classes="stat-label"),
                    Label("-- MB", id="bandwidth-recv", classes="stat-value"),
                ),
                Horizontal(
                    Label("Sent", classes="stat-label"),
                    Label("-- MB", id="bandwidth-sent", classes="stat-value"),
                ),
                classes="stat-box",
            ),

            id="network-screen",
        )

    def on_mount(self) -> None:
        """마운트 시"""
        # 테이블 설정
        table = self.query_one("#peers-table", DataTable)
        table.add_columns("Address", "Height", "Version", "Direction")

        self.refresh_data()
        self.set_interval(5, self.refresh_data)

    def refresh_data(self) -> None:
        """데이터 새로고침"""
        self.run_worker(self._load_data())

    async def _load_data(self) -> None:
        """비동기 데이터 로드"""
        # 네트워크 정보
        resp = await self.rpc.get_network_info()
        if resp.success:
            data = resp.result
            self.connections = data.get("connections", 0)
            self.inbound = data.get("connections_in", 0)
            self.outbound = data.get("connections_out", 0)

            self.query_one("#connections", Label).update(str(self.connections))
            self.query_one("#inbound", Label).update(str(self.inbound))
            self.query_one("#outbound", Label).update(str(self.outbound))

            version = data.get("subversion", "/JackpotChain:0.1.0/")
            self.query_one("#node-version", Label).update(version)

        # 피어 정보
        resp = await self.rpc.get_peer_info()
        if resp.success:
            peers = resp.result or []
            table = self.query_one("#peers-table", DataTable)
            table.clear()

            for p in peers:
                addr = p.get("addr", "unknown")
                height = p.get("startingheight", 0)
                version = p.get("subver", "")[:20]
                direction = "IN" if p.get("inbound") else "OUT"

                # 높이에 따른 상태 표시
                height_str = f"● H:{height}" if height > 0 else f"○ H:{height}"

                table.add_row(
                    addr,
                    height_str,
                    version,
                    direction,
                )
