"""
History Widget

당첨 이력 화면 (자동 지급 결과 조회)
"""

from textual.app import ComposeResult
from textual.widgets import Static, Label, Button, DataTable
from textual.containers import ScrollableContainer, Horizontal, Vertical

from ..client import RPCClient


class HistoryWidget(ScrollableContainer):
    """당첨 이력 위젯"""

    def __init__(self, rpc: RPCClient, **kwargs):
        super().__init__(**kwargs)
        self.rpc = rpc
        self._commits_data = []

    def compose(self) -> ComposeResult:
        # 상태 메시지
        yield Label("", id="history-status", classes="status-msg")

        # 커밋 목록
        yield Vertical(
            Label("LOTTO HISTORY", classes="box-title"),
            DataTable(id="history-table"),
            Horizontal(
                Button("Check Result", id="btn-check", variant="warning"),
                Button("Refresh", id="btn-refresh", variant="primary"),
                classes="action-buttons",
            ),
            classes="stat-box",
        )

    def on_mount(self) -> None:
        """마운트 시"""
        table = self.query_one("#history-table", DataTable)
        table.add_columns("Numbers", "Block", "Status", "Result")
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
        else:
            commits = []

        self._commits_data = commits
        table = self.query_one("#history-table", DataTable)
        table.clear()

        for c in commits:
            nums = c.get("chosen_hex", c.get("chosen_numbers", []))
            if nums and isinstance(nums[0], int):
                num_str = " ".join(f"{n:X}" for n in nums)
            else:
                num_str = " ".join(str(n).upper() for n in nums) if nums else "--"

            status = c.get("status", "?")
            blocks_left = c.get("blocks_until_payout", 0)

            if status == "ready":
                status_str = "READY"
            elif status == "pending":
                status_str = f"D-{blocks_left}"
            elif status == "pending_mine":
                status_str = "MINING..."
            else:
                status_str = status.upper()[:10]

            # 결과 컬럼
            if status == "ready":
                result_str = ">>> Check!"
            elif status == "pending":
                result_str = f"{blocks_left} blocks"
            else:
                result_str = "--"

            table.add_row(
                num_str,
                f"#{c.get('commit_height', 0)}",
                status_str,
                result_str,
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭 처리"""
        if event.button.id == "btn-check":
            self.run_worker(self._check_selected())
        elif event.button.id == "btn-refresh":
            self.refresh_data()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """행 더블클릭 시 결과 확인"""
        self.run_worker(self._check_row(event.cursor_row))

    async def _check_selected(self) -> None:
        """선택된 커밋 결과 확인"""
        table = self.query_one("#history-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self._commits_data):
            await self._check_row(table.cursor_row)
        else:
            self.query_one("#history-status", Label).update("Select a commit first")

    async def _check_row(self, row_index: int) -> None:
        """특정 행의 결과 확인"""
        if row_index >= len(self._commits_data):
            return

        commit = self._commits_data[row_index]
        tx_id = commit.get("tx_id", "")

        if not tx_id:
            self.query_one("#history-status", Label).update("TX not yet mined")
            return

        resp = await self.rpc.lotto_check_result(tx_id)

        if resp.success:
            data = resp.result
            status = data.get("status", "unknown")

            if status == "pending":
                blocks = data.get("blocks_remaining", 0)
                self.query_one("#history-status", Label).update(
                    f"Pending - {blocks} blocks until payout"
                )
            else:
                matches = data.get("matches", 0)
                prize = data.get("prize", "NONE")
                chosen_hex = data.get("chosen_hex", [])
                result_hex = data.get("result_hex", [])
                payout = data.get("payout_jack", 0)
                paid = data.get("paid", False)

                chosen_str = " ".join(str(n).upper() for n in chosen_hex)
                result_str = " ".join(str(n).upper() for n in result_hex)
                paid_str = " (Paid)" if paid else " (Unpaid)"

                if matches > 0:
                    self.query_one("#history-status", Label).update(
                        f"{matches} matches! {prize} - {payout} JACK{paid_str}\n"
                        f"  Chosen: {chosen_str} / Result: {result_str}"
                    )
                else:
                    self.query_one("#history-status", Label).update(
                        f"No matches{paid_str}\n"
                        f"  Chosen: {chosen_str} / Result: {result_str}"
                    )
        else:
            self.query_one("#history-status", Label).update(f"Error: {resp.error}")
