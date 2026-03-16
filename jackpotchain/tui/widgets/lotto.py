"""
Lotto Widget

로또 화면
"""

from textual.app import ComposeResult
from textual.widgets import Static, Label, Input, Button, DataTable
from textual.containers import Container, Horizontal, Vertical

from ..client import RPCClient


class LottoWidget(Container):
    """로또 위젯"""

    def __init__(self, rpc: RPCClient, **kwargs):
        super().__init__(**kwargs)
        self.rpc = rpc

    def compose(self) -> ComposeResult:
        # 상단: 잭팟 풀 + 새 참여 (가로 배치)
        yield Horizontal(
            # 잭팟 풀
            Vertical(
                Label("JACKPOT POOL", classes="box-title-gold"),
                Label("-- JACK", id="l-jackpot-amount", classes="jackpot-amount"),
                Label("1st Prize: -- (50%)", id="first-prize", classes="prize-info"),
                id="jackpot-box",
                classes="lotto-left",
            ),
            # 새 참여
            Vertical(
                Label("NEW ENTRY (1 POT)", classes="box-title"),
                Horizontal(
                    Input(placeholder="0", id="num-0", classes="lotto-input"),
                    Input(placeholder="0", id="num-1", classes="lotto-input"),
                    Input(placeholder="0", id="num-2", classes="lotto-input"),
                    Input(placeholder="0", id="num-3", classes="lotto-input"),
                    Input(placeholder="0", id="num-4", classes="lotto-input"),
                    Input(placeholder="0", id="num-5", classes="lotto-input"),
                    classes="lotto-numbers",
                ),
                Horizontal(
                    Button("Random", id="btn-random", variant="primary"),
                    Button("Submit", id="btn-new-entry", variant="success"),
                    classes="lotto-buttons",
                ),
                classes="stat-box lotto-right",
            ),
            classes="lotto-top",
        )

        # 상태 메시지
        yield Label("", id="lotto-status", classes="status-msg")

        # 내 커밋
        yield Vertical(
            Label("MY COMMITS", classes="box-title"),
            DataTable(id="commits-table"),
            Horizontal(
                Button("Claim Selected", id="btn-claim", variant="warning"),
                classes="lotto-buttons",
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
        # 잭팟 풀
        resp = await self.rpc.get_jackpot_pool()
        if resp.success:
            data = resp.result
            pool = data.get("balance", 0)
            prize = data.get("next_jackpot", 0)
            self.query_one("#l-jackpot-amount", Label).update(f"{pool:,.0f} JACK")
            self.query_one("#first-prize", Label).update(f"1st: {prize:,.0f} JACK")

        # 커밋 목록
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
        if event.button.id == "btn-new-entry":
            self.run_worker(self._create_commit())
        elif event.button.id == "btn-random":
            self._fill_random()
        elif event.button.id == "btn-claim":
            self.run_worker(self._claim_selected())

    def _fill_random(self) -> None:
        """랜덤 숫자"""
        import random
        for i in range(6):
            self.query_one(f"#num-{i}", Input).value = f"{random.randint(0,15):X}"
        self.query_one("#lotto-status", Label).update("Random numbers generated!")

    def _get_numbers(self) -> list:
        """입력 숫자 가져오기"""
        nums = []
        for i in range(6):
            v = self.query_one(f"#num-{i}", Input).value.strip().upper()
            if v:
                try:
                    n = int(v, 16)
                    if 0 <= n <= 15:
                        nums.append(n)
                except ValueError:
                    pass
        return nums if len(nums) == 6 else None

    async def _create_commit(self) -> None:
        """커밋 생성"""
        nums = self._get_numbers()
        if nums:
            resp = await self.rpc.lotto_commit(nums)
        else:
            resp = await self.rpc.lotto_commit()

        if resp.success:
            data = resp.result
            chosen = data.get("chosen_hex", [])
            self.query_one("#lotto-status", Label).update(
                f"Committed: {' '.join(chosen)} - Wait N+18 blocks"
            )
            # 입력 필드 초기화
            for i in range(6):
                self.query_one(f"#num-{i}", Input).value = ""
            self.refresh_data()
        else:
            self.query_one("#lotto-status", Label).update(f"Error: {resp.error}")

    async def _claim_selected(self) -> None:
        """선택된 커밋 클레임"""
        # 커밋 목록 가져오기
        resp = await self.rpc.list_lotto_commits()
        if not resp.success or not resp.result:
            self.query_one("#lotto-status", Label).update("No commits to claim")
            return

        commits = resp.result
        # claimable 상태인 첫 번째 커밋 클레임
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
                        self.query_one("#lotto-status", Label).update(
                            f"WIN! {matches} matches - {prize} - {payout} JACK"
                        )
                    else:
                        self.query_one("#lotto-status", Label).update("No matches. Try again!")
                    self.refresh_data()
                else:
                    self.query_one("#lotto-status", Label).update(f"Claim error: {claim_resp.error}")
                return

        self.query_one("#lotto-status", Label).update("No claimable commits yet")
