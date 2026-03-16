"""
Lotto Widget

로또 화면
"""

from textual.app import ComposeResult
from textual.widgets import Static, Label, Input, Button
from textual.containers import ScrollableContainer, Horizontal, Vertical

from ..client import RPCClient


class LottoWidget(ScrollableContainer):
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

        # 안내
        yield Label("Commits are shown in F6 Claims tab", classes="info-text")

    def on_mount(self) -> None:
        """마운트 시"""
        self.refresh_data()
        self.set_interval(10, self.refresh_data)

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭 처리"""
        if event.button.id == "btn-new-entry":
            self.run_worker(self._create_commit())
        elif event.button.id == "btn-random":
            self._fill_random()

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
