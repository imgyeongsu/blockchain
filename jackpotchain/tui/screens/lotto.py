"""
Lotto Screen

로또 화면
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Label, Input, Button, DataTable, ProgressBar
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive

from ..client import RPCClient


class LottoNumberBox(Static):
    """로또 숫자 박스"""

    def __init__(self, value: str = "?", **kwargs):
        super().__init__(value, **kwargs)


class LottoScreen(Screen):
    """로또 화면"""

    jackpot_pool = reactive(0.0)
    first_prize = reactive(0.0)

    def __init__(self, rpc: RPCClient):
        super().__init__()
        self.rpc = rpc

    def compose(self) -> ComposeResult:
        yield Container(
            # 잭팟 풀
            Vertical(
                Label("JACKPOT POOL", classes="box-title-gold"),
                Label("-- JACK", id="jackpot-amount", classes="jackpot-amount"),
                Label("1st Prize: -- JACK (50%)", id="first-prize", classes="prize-info"),
                id="jackpot-box",
            ),

            # 내 커밋
            Vertical(
                Label("MY COMMITS", classes="box-title"),
                DataTable(id="commits-table"),
                classes="stat-box",
            ),

            # 새 참여
            Vertical(
                Label("NEW ENTRY (1 POT)", classes="box-title"),
                Static("Choose 6 hex numbers (0-F) or leave empty for random:", classes="info-text"),
                Horizontal(
                    Input(placeholder="A", id="num-0", max_length=1, classes="lotto-input"),
                    Input(placeholder="3", id="num-1", max_length=1, classes="lotto-input"),
                    Input(placeholder="F", id="num-2", max_length=1, classes="lotto-input"),
                    Input(placeholder="7", id="num-3", max_length=1, classes="lotto-input"),
                    Input(placeholder="2", id="num-4", max_length=1, classes="lotto-input"),
                    Input(placeholder="B", id="num-5", max_length=1, classes="lotto-input"),
                    classes="lotto-numbers",
                ),
                Horizontal(
                    Button("[N] New Entry", id="btn-new-entry", variant="success"),
                    Button("[R] Random", id="btn-random", variant="primary"),
                    classes="action-buttons",
                ),
                Static("Auto-payout at N+18 block. Check results in History tab.", classes="info-text"),
                classes="stat-box",
            ),

            # 상태 메시지
            Label("", id="lotto-status"),

            id="lotto-screen",
        )

    def on_mount(self) -> None:
        """마운트 시"""
        # 테이블 설정
        table = self.query_one("#commits-table", DataTable)
        table.add_columns("Numbers", "Block", "Status", "Payout")

        self.refresh_data()
        self.set_interval(5, self.refresh_data)

    def refresh_data(self) -> None:
        """데이터 새로고침"""
        self.run_worker(self._load_data())

    async def _load_data(self) -> None:
        """비동기 데이터 로드"""
        # 잭팟 풀
        resp = await self.rpc.get_jackpot_pool()
        if resp.success:
            data = resp.result
            self.jackpot_pool = data.get("balance", 0)
            self.first_prize = data.get("next_jackpot", 0)
            self.query_one("#jackpot-amount", Label).update(f"{self.jackpot_pool:,.0f} JACK")
            self.query_one("#first-prize", Label).update(f"1st Prize: {self.first_prize:,.0f} JACK (50%)")

        # 커밋 목록
        resp = await self.rpc.list_lotto_commits()
        if resp.success:
            commits = resp.result or []
            table = self.query_one("#commits-table", DataTable)
            table.clear()

            for c in commits:
                # 숫자 표시
                numbers = c.get("chosen_hex", c.get("chosen_numbers", []))
                if isinstance(numbers[0], int) if numbers else False:
                    num_str = " ".join(f"{n:X}" for n in numbers)
                else:
                    num_str = " ".join(str(n).upper() for n in numbers)

                # 상태
                status = c.get("status", "unknown")
                blocks_left = c.get("blocks_until_payout", 0)
                if status == "ready":
                    status_str = "READY"
                elif status == "pending":
                    status_str = f"D-{blocks_left}"
                elif status == "pending_mine":
                    status_str = "MINING..."
                else:
                    status_str = status.upper()

                # 지급 블록
                payout_block = c.get("payout_block", 0)
                payout_str = f"#{payout_block}" if payout_block else "--"

                table.add_row(
                    num_str,
                    f"#{c.get('commit_height', 0)}",
                    status_str,
                    payout_str,
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭 처리"""
        btn_id = event.button.id

        if btn_id == "btn-new-entry":
            self.run_worker(self._create_commit())
        elif btn_id == "btn-random":
            self._fill_random_numbers()

    def _fill_random_numbers(self) -> None:
        """랜덤 숫자 채우기"""
        import random
        for i in range(6):
            num = random.randint(0, 15)
            self.query_one(f"#num-{i}", Input).value = f"{num:X}"

    def _get_chosen_numbers(self) -> list:
        """입력된 숫자 가져오기"""
        numbers = []
        for i in range(6):
            val = self.query_one(f"#num-{i}", Input).value.strip().upper()
            if val:
                try:
                    num = int(val, 16)
                    if 0 <= num <= 15:
                        numbers.append(num)
                except ValueError:
                    pass
        return numbers if len(numbers) == 6 else None

    async def _create_commit(self) -> None:
        """커밋 생성"""
        numbers = self._get_chosen_numbers()

        if numbers:
            resp = await self.rpc.lotto_commit(numbers)
        else:
            resp = await self.rpc.lotto_commit()

        if resp.success:
            data = resp.result
            chosen = data.get("chosen_hex", [])
            self.query_one("#lotto-status", Label).update(
                f"Committed! Numbers: {' '.join(chosen)}. Auto-payout at N+18."
            )
            self.refresh_data()
        else:
            self.query_one("#lotto-status", Label).update(f"Error: {resp.error}")
