"""
Claims Widget

클레임 화면 (로또 커밋 관리)
"""

from textual.app import ComposeResult
from textual.widgets import Static, Label, Button, DataTable
from textual.containers import ScrollableContainer, Horizontal, Vertical

from ..client import RPCClient


class ClaimsWidget(ScrollableContainer):
    """클레임 위젯"""

    def __init__(self, rpc: RPCClient, **kwargs):
        super().__init__(**kwargs)
        self.rpc = rpc

    def compose(self) -> ComposeResult:
        # 상태 메시지
        yield Label("", id="claims-status", classes="status-msg")

        # 커밋 목록
        yield Vertical(
            Label("MY COMMITS", classes="box-title"),
            DataTable(id="commits-table"),
            Horizontal(
                Button("Claim Selected", id="btn-claim", variant="warning"),
                Button("Refresh", id="btn-refresh", variant="primary"),
                classes="action-buttons",
            ),
            classes="stat-box",
        )

    def on_mount(self) -> None:
        """마운트 시"""
        table = self.query_one("#commits-table", DataTable)
        table.add_columns("Numbers", "Block", "Status", "Blocks Left")
        table.cursor_type = "row"
        self.refresh_data()
        self.set_interval(5, self.refresh_data)

    def refresh_data(self) -> None:
        """데이터 새로고침"""
        self.run_worker(self._load_data())

    async def _load_data(self) -> None:
        """비동기 데이터 로드"""
        resp = await self.rpc.list_lotto_commits()
        if resp.success:
            commits = resp.result or []
            table = self.query_one("#commits-table", DataTable)
            table.clear()

            for c in commits:
                nums = c.get("chosen_hex", c.get("chosen_numbers", []))
                if nums and isinstance(nums[0], int):
                    num_str = " ".join(f"{n:X}" for n in nums)
                else:
                    num_str = " ".join(str(n).upper() for n in nums) if nums else "--"

                status = c.get("status", "?")
                blocks_left = c.get("blocks_until_claimable", 0)

                if status == "claimable":
                    status_str = "CLAIMABLE"
                elif status == "pending":
                    status_str = "PENDING"
                elif status == "pending_mine":
                    status_str = "MINING..."
                else:
                    status_str = status.upper()[:10]

                table.add_row(
                    num_str,
                    f"#{c.get('commit_height', 0)}",
                    status_str,
                    str(blocks_left) if blocks_left > 0 else "-"
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭 처리"""
        if event.button.id == "btn-claim":
            self.run_worker(self._claim_selected())
        elif event.button.id == "btn-refresh":
            self.refresh_data()

    async def _claim_selected(self) -> None:
        """선택된 커밋 클레임"""
        resp = await self.rpc.list_lotto_commits()
        if not resp.success or not resp.result:
            self.query_one("#claims-status", Label).update("No commits to claim")
            return

        commits = resp.result
        for c in commits:
            if c.get("can_claim") or c.get("status") == "claimable":
                commit_hash = c.get("commit_hash")
                claim_resp = await self.rpc.lotto_claim(commit_hash)

                if claim_resp.success:
                    data = claim_resp.result
                    matches = data.get("matches", 0)
                    prize = data.get("prize", "NONE")
                    payout = data.get("payout_jack", 0)

                    if matches > 0:
                        self.query_one("#claims-status", Label).update(
                            f"WIN! {matches} matches - {prize} - {payout} JACK"
                        )
                    else:
                        self.query_one("#claims-status", Label).update("No matches. Try again!")
                    self.refresh_data()
                else:
                    self.query_one("#claims-status", Label).update(f"Error: {claim_resp.error}")
                return

        self.query_one("#claims-status", Label).update("No claimable commits yet")
