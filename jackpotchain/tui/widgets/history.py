"""
History Widget

당첨 이력 화면 (자동 지급 결과 조회)
- 미확인/대기: RPC 기반 (라이브)
- 결과 확인 완료: 로컬 저장 (영구)
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from textual.app import ComposeResult
from textual.widgets import Static, Label, Button, DataTable
from textual.containers import ScrollableContainer, Horizontal, Vertical

from ..client import RPCClient


def _get_history_path() -> Path:
    """로컬 이력 파일 경로"""
    appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    path = Path(appdata) / 'JackpotChain' / 'lotto_history.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_local_history() -> Dict[str, dict]:
    """로컬 이력 로드 (tx_id → result)"""
    path = _get_history_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def _save_local_history(history: Dict[str, dict]) -> None:
    """로컬 이력 저장"""
    path = _get_history_path()
    path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding='utf-8')


class HistoryWidget(ScrollableContainer):
    """당첨 이력 위젯"""

    can_focus = False

    def __init__(self, rpc: RPCClient, **kwargs):
        super().__init__(**kwargs)
        self.rpc = rpc
        # RPC에서 가져온 라이브 데이터
        self._live_commits: List[dict] = []
        # 로컬 저장된 결과
        self._local_history: Dict[str, dict] = {}
        # 테이블에 표시된 항목 (순서대로)
        self._display_rows: List[dict] = []

    def compose(self) -> ComposeResult:
        yield Label("", id="history-status", classes="status-msg")

        yield Vertical(
            Label("LOTTO HISTORY", classes="box-title"),
            DataTable(id="history-table"),
            Horizontal(
                Button("Check Result", id="btn-check", variant="warning"),
                Button("Delete", id="btn-delete", variant="error"),
                Button("Refresh", id="btn-refresh", variant="primary"),
                classes="action-buttons",
            ),
            classes="stat-box",
        )

    def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.add_columns("Numbers", "Block", "Status", "Result")
        table.cursor_type = "row"
        self._local_history = _load_local_history()
        self.refresh_data()
        self.set_interval(5, self.refresh_data)

    def refresh_data(self) -> None:
        self.run_worker(self._load_data())

    async def _load_data(self) -> None:
        """비동기 데이터 로드 (RPC + 로컬 병합)"""
        table = self.query_one("#history-table", DataTable)

        # 스크롤 위치 & 선택 행 보존
        saved_cursor = table.cursor_row

        # 1. RPC에서 라이브 데이터 가져오기
        resp = await self.rpc.list_lotto_commits()
        self._live_commits = resp.result or [] if resp.success else []

        # 2. 표시 데이터 병합 (라이브 + 로컬)
        self._build_display_rows()

        # 3. 테이블 갱신
        table.clear()
        for row in self._display_rows:
            table.add_row(
                row["num_str"],
                row["block_str"],
                row["status_str"],
                row["result_str"],
            )

        # 스크롤 위치 복원
        if saved_cursor is not None and saved_cursor < len(self._display_rows):
            table.move_cursor(row=saved_cursor)

    def _build_display_rows(self) -> None:
        """라이브 + 로컬 데이터를 병합하여 표시 목록 생성 (최신순)"""
        rows: List[dict] = []
        seen_tx_ids = set()

        # 최근 50블록 기준 계산
        max_height = max((c.get("commit_height", 0) for c in self._live_commits), default=0)
        cutoff_height = max(max_height - 50, 0)

        # 1. RPC 라이브 커밋 처리
        for c in self._live_commits:
            tx_id = c.get("tx_id", "")
            commit_height = c.get("commit_height", 0)

            # 오래된 커밋은 스킵 (MINING 중인 건 제외)
            if commit_height > 0 and commit_height < cutoff_height:
                continue

            # 삭제된 항목 스킵
            if tx_id and tx_id in self._local_history:
                if self._local_history[tx_id].get("deleted"):
                    continue

            seen_tx_ids.add(tx_id)

            nums = c.get("chosen_hex", c.get("chosen_numbers", []))
            num_str = self._format_numbers(nums)

            # 로컬에 결과 있으면 로컬 데이터 사용
            if tx_id and tx_id in self._local_history:
                local = self._local_history[tx_id]
                rows.append(self._make_local_row(tx_id, local, commit_height))
            else:
                # 라이브 상태 표시
                status = c.get("status", "?")
                blocks_left = c.get("blocks_until_payout", 0)

                if status == "pending_mine":
                    status_str = "MINING..."
                    result_str = "--"
                elif blocks_left <= 0:
                    status_str = "READY"
                    result_str = ">>> Check!"
                elif status in ("pending", "ready"):
                    status_str = f"D-{blocks_left}"
                    result_str = f"{blocks_left} blocks"
                else:
                    status_str = status.upper()[:10]
                    result_str = "--"

                rows.append({
                    "tx_id": tx_id,
                    "num_str": num_str,
                    "block_str": f"#{commit_height}" if commit_height else "#0",
                    "status_str": status_str,
                    "result_str": result_str,
                    "commit_height": commit_height,
                    "source": "live",
                })

        # 2. 로컬 전용 (RPC에 없는 과거 결과)
        for tx_id, local in self._local_history.items():
            if tx_id in seen_tx_ids:
                continue
            if local.get("deleted"):
                continue
            commit_height = local.get("commit_height", 0)
            rows.append(self._make_local_row(tx_id, local, commit_height))

        # 최신순 정렬 (commit_height 내림차순, 0은 맨 위)
        rows.sort(key=lambda r: (
            0 if r["commit_height"] == 0 else 1,
            -r["commit_height"],
        ))

        self._display_rows = rows

    def _make_local_row(self, tx_id: str, local: dict, commit_height: int) -> dict:
        """로컬 저장된 결과로 행 생성"""
        nums = local.get("chosen_hex", local.get("chosen_numbers", []))
        num_str = self._format_numbers(nums)

        matches = local.get("matches", 0)
        prize = local.get("prize", "NONE")
        payout_jack = local.get("payout_jack", 0)
        paid = local.get("paid", False)

        if matches > 0:
            status_str = f"{prize}"
            paid_mark = "V" if paid else "?"
            result_str = f"{matches}match {payout_jack:,.0f}J [{paid_mark}]"
        else:
            status_str = "MISS"
            result_str = "No match"

        return {
            "tx_id": tx_id,
            "num_str": num_str,
            "block_str": f"#{commit_height}" if commit_height else "#?",
            "status_str": status_str,
            "result_str": result_str,
            "commit_height": commit_height,
            "source": "local",
        }

    @staticmethod
    def _format_numbers(nums) -> str:
        if not nums:
            return "--"
        if isinstance(nums[0], int):
            return " ".join(f"0x{n:X}" for n in nums)
        return " ".join(str(n).upper() for n in nums)

    # =========================================================================
    # 버튼 핸들러
    # =========================================================================

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-check":
            self.run_worker(self._check_selected())
        elif event.button.id == "btn-delete":
            self._delete_selected()
        elif event.button.id == "btn-refresh":
            self._local_history = _load_local_history()
            self.refresh_data()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """행 더블클릭 시 결과 확인"""
        self.run_worker(self._check_row(event.cursor_row))

    async def _check_selected(self) -> None:
        """선택된 커밋 결과 확인"""
        table = self.query_one("#history-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self._display_rows):
            await self._check_row(table.cursor_row)
        else:
            self.query_one("#history-status", Label).update("Select a commit first")

    async def _check_row(self, row_index: int) -> None:
        """특정 행의 결과 확인"""
        if row_index >= len(self._display_rows):
            return

        row = self._display_rows[row_index]
        tx_id = row.get("tx_id", "")

        if not tx_id:
            self.query_one("#history-status", Label).update("TX not yet mined")
            return

        # 이미 로컬에 결과 있으면 그대로 표시
        if tx_id in self._local_history:
            self._show_local_result(tx_id)
            return

        # RPC로 결과 조회
        resp = await self.rpc.lotto_check_result(tx_id)

        if not resp.success:
            self.query_one("#history-status", Label).update(f"Error: {resp.error}")
            return

        data = resp.result
        status = data.get("status", "unknown")

        if status == "pending":
            blocks = data.get("blocks_remaining", 0)
            self.query_one("#history-status", Label).update(
                f"Pending - {blocks} blocks until payout"
            )
            return

        # 결과 확정 → 로컬에 저장
        result = {
            "chosen_numbers": data.get("chosen_numbers", []),
            "chosen_hex": data.get("chosen_hex", []),
            "result_digits": data.get("result_digits", []),
            "result_hex": data.get("result_hex", []),
            "matches": data.get("matches", 0),
            "prize": data.get("prize", "NONE"),
            "prize_rank": data.get("prize_rank", 0),
            "payout_jack": data.get("payout_jack", 0),
            "payout_pot": data.get("payout_pot", 0),
            "paid": data.get("paid", False),
            "payout_block": data.get("payout_block", 0),
            "commit_height": row.get("commit_height", 0),
        }

        self._local_history[tx_id] = result
        _save_local_history(self._local_history)

        # 결과 표시
        self._show_local_result(tx_id)

        # 테이블 갱신 (상태 반영)
        self._build_display_rows()
        table = self.query_one("#history-table", DataTable)
        saved_cursor = table.cursor_row
        table.clear()
        for r in self._display_rows:
            table.add_row(r["num_str"], r["block_str"], r["status_str"], r["result_str"])
        if saved_cursor is not None and saved_cursor < len(self._display_rows):
            table.move_cursor(row=saved_cursor)

    def _show_local_result(self, tx_id: str) -> None:
        """로컬 저장된 결과를 상태 라벨에 표시"""
        local = self._local_history.get(tx_id)
        if not local:
            return

        matches = local.get("matches", 0)
        prize = local.get("prize", "NONE")
        payout_jack = local.get("payout_jack", 0)
        payout_pot = local.get("payout_pot", 0)
        paid = local.get("paid", False)

        chosen_hex = local.get("chosen_hex", [])
        result_hex = local.get("result_hex", [])
        chosen_str = " ".join(str(n).upper() for n in chosen_hex)
        result_str = " ".join(str(n).upper() for n in result_hex)

        paid_str = " (Paid)" if paid else " (Unpaid)"
        pot_str = f" + {payout_pot} POT" if payout_pot else ""

        if matches > 0:
            self.query_one("#history-status", Label).update(
                f"{matches} matches! {prize} - {payout_jack:,.0f} JACK{pot_str}{paid_str}\n"
                f"  Chosen: {chosen_str} / Result: {result_str}"
            )
        else:
            self.query_one("#history-status", Label).update(
                f"No matches{paid_str}\n"
                f"  Chosen: {chosen_str} / Result: {result_str}"
            )

    def _delete_selected(self) -> None:
        """선택된 항목 삭제 (로컬 이력만)"""
        table = self.query_one("#history-table", DataTable)
        if table.cursor_row is None or table.cursor_row >= len(self._display_rows):
            self.query_one("#history-status", Label).update("Select a row to delete")
            return

        row = self._display_rows[table.cursor_row]
        tx_id = row.get("tx_id", "")

        if tx_id:
            # 로컬이든 라이브든 deleted 플래그로 숨김
            if tx_id not in self._local_history:
                self._local_history[tx_id] = {}
            self._local_history[tx_id]["deleted"] = True
            _save_local_history(self._local_history)
            self.query_one("#history-status", Label).update("Deleted")
            self.refresh_data()
        else:
            self.query_one("#history-status", Label).update("Nothing to delete")
