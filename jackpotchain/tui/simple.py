"""
JackpotChain Simple TUI

초보자용 간편 인터페이스
- 지갑 자동 생성/로드
- 채굴 항상 자동
- 메뉴: 송금 / 로또 / 당첨확인 / 설정
"""

import os
import sys
import random
import subprocess
from pathlib import Path
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Static, Label, Button, Input, DataTable
from textual.containers import (
    ScrollableContainer, Container, Horizontal, Vertical,
)

from .client import RPCClient


class SimpleApp(App):
    """초보자용 간편 TUI"""

    TITLE = "JackpotChain"
    SUB_TITLE = "Simple Wallet"

    CSS = """
    Screen { background: #0c0c0c; }

    /* 상단 요약 */
    #summary-box {
        height: auto;
        border: solid #333;
        background: #111;
        padding: 1 2;
        margin-bottom: 1;
    }
    #summary-title {
        color: #00ff88;
        text-style: bold;
        text-align: center;
        margin-bottom: 1;
    }
    .summary-row { height: auto; }
    .summary-label { color: #888; width: 16; }
    .summary-value { color: #ddd; }
    .summary-value-green { color: #00ff88; text-style: bold; }
    .summary-value-gold { color: #ffbd2e; text-style: bold; }

    /* 네트워크 상태 바 */
    #status-bar {
        height: auto;
        padding: 0 2;
        margin-bottom: 1;
    }
    .status-dot-ok { color: #00ff88; }
    .status-dot-err { color: #ff5f56; }
    .status-text { color: #888; margin-left: 1; }

    /* 메뉴 */
    #menu-box {
        height: auto;
        padding: 1 2;
    }
    #menu-box Button {
        width: 100%;
        margin-bottom: 1;
        min-height: 3;
    }

    /* 패널 */
    .panel {
        border: solid #444;
        background: #111;
        padding: 1 2;
        margin-bottom: 1;
        height: auto;
    }
    .panel-title {
        color: #00ff88;
        text-style: bold;
        margin-bottom: 1;
    }
    .panel Input {
        margin-bottom: 1;
    }
    .panel-buttons { height: auto; }
    .panel-buttons Button { margin-right: 1; }

    /* 메시지 */
    #msg {
        color: #00d4ff;
        background: #1a1a2e;
        border: solid #444;
        padding: 1;
        margin-bottom: 1;
        height: auto;
    }

    /* 로또 번호 */
    .lotto-nums { height: auto; margin-bottom: 1; }
    .lotto-num-input {
        width: 8;
        height: 3;
        margin-right: 1;
        background: #1a1a1a;
        color: #ffbd2e;
        border: solid #ffbd2e;
        text-align: center;
    }

    /* 당첨 이력 테이블 */
    DataTable { height: 12; }
    DataTable > .datatable--header { color: #00ff88; background: #0c0c0c; }

    .hidden { display: none; }

    /* 잭팟 풀 */
    #jackpot-info {
        border: double #ffbd2e;
        background: #111;
        padding: 1 2;
        text-align: center;
        height: auto;
        margin-bottom: 1;
    }
    .jackpot-label { color: #ffbd2e; text-style: bold; }
    .jackpot-amount { color: #00ff88; text-style: bold; }
    """

    BINDINGS = [
        Binding("escape", "go_home", "Home", show=True, priority=True),
        Binding("ctrl+q", "quit", "Quit", show=True, priority=True),
    ]

    def __init__(self, host: str = "127.0.0.1", port: int = 8776):
        super().__init__()
        self.rpc = RPCClient(host, port)
        self._current_view = "home"
        self._node_process = None
        self._wallet_name, self._wallet_path, self._address = self._ensure_local_wallet()

    def _ensure_local_wallet(self) -> tuple[str, Path, str]:
        """로컬 지갑 확인 → 없으면 생성. (이름, 경로, 주소) 반환"""
        from ..wallet.wallet import Wallet
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        wallet_dir = Path(appdata) / 'JackpotChain' / 'wallets'
        wallet_dir.mkdir(parents=True, exist_ok=True)

        # 기존 지갑 있으면 첫 번째 사용
        existing = sorted(wallet_dir.glob("*.json"))
        if existing:
            w = Wallet(str(existing[0]))
            addrs = w.get_addresses()
            addr = addrs[0] if addrs else ""
            return existing[0].stem, existing[0], addr

        # 없으면 my_wallet 생성
        name = "my_wallet"
        wallet_path = wallet_dir / f"{name}.json"
        w = Wallet(str(wallet_path))
        addr = w.generate_address(label="main")
        return name, wallet_path, addr

    def _start_node(self) -> None:
        """노드 백그라운드 시작"""
        if self._node_process and self._node_process.poll() is None:
            return  # 이미 실행 중

        cmd = [
            sys.executable, "-m", "jackpotchain.cli.main",
            "node", "--mine",
            "--address", self._address,
            "--wallet-file", str(self._wallet_path),
        ]
        self._node_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def compose(self) -> ComposeResult:
        yield Header()

        with ScrollableContainer(id="main"):
            # 상단 요약
            with Container(id="summary-box"):
                yield Static("JACKPOTCHAIN WALLET", id="summary-title")
                with Horizontal(classes="summary-row"):
                    yield Static("JACK", classes="summary-label")
                    yield Static("--", id="val-jack", classes="summary-value-green")
                with Horizontal(classes="summary-row"):
                    yield Static("POT", classes="summary-label")
                    yield Static("--", id="val-pot", classes="summary-value-gold")
                with Horizontal(classes="summary-row"):
                    yield Static("Address", classes="summary-label")
                    yield Static("--", id="val-addr", classes="summary-value")

            # 네트워크 상태
            with Horizontal(id="status-bar"):
                yield Static("●", id="status-dot", classes="status-dot-err")
                yield Static("Connecting...", id="status-text", classes="status-text")

            # 메시지 영역
            yield Label("", id="msg", classes="hidden")

            # === 홈 메뉴 ===
            with Container(id="view-home"):
                with Container(id="menu-box"):
                    yield Button("💰  Send JACK", id="btn-send", variant="primary")
                    yield Button("🔄  Exchange to POT", id="btn-exchange", variant="warning")
                    yield Button("🎰  Lotto", id="btn-lotto", variant="success")
                    yield Button("📋  History", id="btn-history", variant="default")

            # === 송금 패널 ===
            with Container(id="view-send", classes="hidden"):
                with Container(classes="panel"):
                    yield Static("Send JACK", classes="panel-title")
                    yield Input(placeholder="Recipient address", id="send-addr")
                    yield Input(placeholder="Amount (JACK)", id="send-amount")
                    with Horizontal(classes="panel-buttons"):
                        yield Button("Send", id="btn-send-confirm", variant="warning")
                        yield Button("Cancel", id="btn-cancel", variant="default")

            # === 교환 패널 ===
            with Container(id="view-exchange", classes="hidden"):
                with Container(classes="panel"):
                    yield Static("Exchange JACK → POT (100:1)", classes="panel-title")
                    yield Input(placeholder="JACK amount (100 = 1 POT)", id="exchange-amount")
                    with Horizontal(classes="panel-buttons"):
                        yield Button("Exchange", id="btn-exchange-confirm", variant="warning")
                        yield Button("Cancel", id="btn-cancel2", variant="default")

            # === 로또 패널 ===
            with Container(id="view-lotto", classes="hidden"):
                with Container(id="jackpot-info"):
                    yield Static("JACKPOT POOL", classes="jackpot-label")
                    yield Static("--", id="jackpot-amount", classes="jackpot-amount")

                with Container(classes="panel"):
                    yield Static("Pick 6 numbers (0-F)", classes="panel-title")
                    with Horizontal(classes="lotto-nums"):
                        for i in range(6):
                            yield Input(
                                placeholder="0",
                                id=f"snum-{i}",
                                max_length=1,
                                classes="lotto-num-input",
                            )
                    with Horizontal(classes="panel-buttons"):
                        yield Button("🎲 Random", id="btn-random", variant="default")
                        yield Button("Submit", id="btn-lotto-confirm", variant="success")
                        yield Button("Cancel", id="btn-cancel3", variant="default")

            # === 이력 패널 ===
            with Container(id="view-history", classes="hidden"):
                with Container(classes="panel"):
                    yield Static("Lotto History", classes="panel-title")
                    yield DataTable(id="history-table")
                    with Horizontal(classes="panel-buttons"):
                        yield Button("Check Result", id="btn-check", variant="warning")
                        yield Button("Back", id="btn-cancel4", variant="default")

        yield Footer()

    async def on_mount(self) -> None:
        """마운트 시 노드 자동 시작 + 주기적 갱신"""
        self._setup_history_table()
        self._initialized = False

        # 노드 연결 확인 → 안 되면 자동 시작
        resp = await self.rpc.get_blockchain_info()
        if not resp.success:
            self._start_node()

        self.set_interval(3, self._refresh_status)
        await self._refresh_status()

    def _setup_history_table(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Numbers", "Block", "Status", "Result")

    async def _ensure_wallet(self) -> None:
        """노드에 지갑 활성화"""
        await self.rpc.set_wallet(self._wallet_name)

    async def _ensure_mining(self) -> None:
        """채굴 자동 시작"""
        resp = await self.rpc.get_mining_info()
        if resp.success and not resp.result.get("mining", False):
            await self.rpc.start_mining()

    async def _refresh_status(self) -> None:
        """상태 갱신 (노드 미연결 시 대기)"""
        # 노드 연결 확인
        info = await self.rpc.get_blockchain_info()
        if not info.success:
            dot = self.query_one("#status-dot", Static)
            dot.remove_class("status-dot-ok")
            dot.add_class("status-dot-err")
            self.query_one("#status-text", Static).update(
                "Waiting for node...  (start: jackpotchain node --mine)"
            )
            self._initialized = False
            return

        # 최초 연결 시 초기화
        if not self._initialized:
            self._initialized = True
            self._hide_msg()
            await self._ensure_wallet()
            await self._ensure_mining()

        # 잔액
        resp = await self.rpc.get_balances()
        if resp.success:
            data = resp.result
            jack = data.get("jack", 0)
            pot = data.get("pot", 0)
            addr = data.get("address", "--")
            self.query_one("#val-jack", Static).update(f"{jack:,.8f} JACK")
            self.query_one("#val-pot", Static).update(f"{pot:,.0f} POT")
            self.query_one("#val-addr", Static).update(addr)

        # 네트워크
        net = await self.rpc.get_network_info()
        height = info.result.get("blocks", 0)
        peers = net.result.get("connections", 0) if net.success else 0
        mining = ""
        m = await self.rpc.get_mining_info()
        if m.success and m.result.get("mining"):
            mining = " | Mining ⛏"
        dot = self.query_one("#status-dot", Static)
        dot.remove_class("status-dot-err")
        dot.add_class("status-dot-ok")
        self.query_one("#status-text", Static).update(
            f"Block #{height:,}  |  {peers} peers{mining}"
        )

        # 이력 탭이 열려있으면 갱신
        if self._current_view == "history":
            await self._refresh_history()

    def _show_view(self, name: str) -> None:
        """뷰 전환"""
        views = ["home", "send", "exchange", "lotto", "history"]
        for v in views:
            w = self.query_one(f"#view-{v}", Container)
            if v == name:
                w.remove_class("hidden")
            else:
                w.add_class("hidden")
        self._current_view = name

    def _show_msg(self, text: str, error: bool = False) -> None:
        """메시지 표시"""
        msg = self.query_one("#msg", Label)
        msg.update(text)
        msg.remove_class("hidden")

    def _hide_msg(self) -> None:
        msg = self.query_one("#msg", Label)
        msg.add_class("hidden")

    def action_go_home(self) -> None:
        """ESC → 홈"""
        self._hide_msg()
        self._show_view("home")

    # ==== 버튼 핸들러 ====

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn = event.button.id

        # 홈 메뉴
        if btn == "btn-send":
            self._hide_msg()
            self._show_view("send")
        elif btn == "btn-exchange":
            self._hide_msg()
            self._show_view("exchange")
        elif btn == "btn-lotto":
            self._hide_msg()
            self._show_view("lotto")
            await self._refresh_jackpot()
        elif btn == "btn-history":
            self._hide_msg()
            self._show_view("history")
            await self._refresh_history()

        # 취소
        elif btn in ("btn-cancel", "btn-cancel2", "btn-cancel3", "btn-cancel4"):
            self.action_go_home()

        # 송금 확인
        elif btn == "btn-send-confirm":
            await self._do_send()

        # 교환 확인
        elif btn == "btn-exchange-confirm":
            await self._do_exchange()

        # 로또
        elif btn == "btn-random":
            self._fill_random()
        elif btn == "btn-lotto-confirm":
            await self._do_lotto()

        # 결과 확인
        elif btn == "btn-check":
            await self._do_check()

    async def _do_send(self) -> None:
        addr = self.query_one("#send-addr", Input).value.strip()
        amount_str = self.query_one("#send-amount", Input).value.strip()
        if not addr or not amount_str:
            self._show_msg("Error: Fill in all fields")
            return
        try:
            amount = float(amount_str)
        except ValueError:
            self._show_msg("Error: Invalid amount")
            return
        resp = await self.rpc.send_to_address(addr, amount)
        if resp.success:
            self._show_msg(f"Sent {amount} JACK!")
            self.query_one("#send-addr", Input).value = ""
            self.query_one("#send-amount", Input).value = ""
            self._show_view("home")
        else:
            self._show_msg(f"Error: {resp.error}")

    async def _do_exchange(self) -> None:
        amount_str = self.query_one("#exchange-amount", Input).value.strip()
        if not amount_str:
            self._show_msg("Error: Enter amount")
            return
        try:
            amount = float(amount_str)
        except ValueError:
            self._show_msg("Error: Invalid amount")
            return
        resp = await self.rpc.exchange_to_pot(amount)
        if resp.success:
            pot = amount / 100
            self._show_msg(f"Exchanged {amount} JACK → {pot:.0f} POT!")
            self.query_one("#exchange-amount", Input).value = ""
            self._show_view("home")
        else:
            self._show_msg(f"Error: {resp.error}")

    def _fill_random(self) -> None:
        for i in range(6):
            inp = self.query_one(f"#snum-{i}", Input)
            inp.value = format(random.randint(0, 15), 'X')

    async def _do_lotto(self) -> None:
        nums = []
        for i in range(6):
            val = self.query_one(f"#snum-{i}", Input).value.strip().upper()
            if not val or val not in "0123456789ABCDEF":
                self._show_msg("Error: Enter valid hex digits (0-F)")
                return
            nums.append(int(val, 16))

        resp = await self.rpc.lotto_commit(nums)
        if resp.success:
            self._show_msg("Lotto submitted! Check results in History.")
            self._show_view("home")
        else:
            self._show_msg(f"Error: {resp.error}")

    async def _refresh_jackpot(self) -> None:
        resp = await self.rpc.get_jackpot_pool()
        if resp.success:
            amount = resp.result.get("pool_balance", 0)
            self.query_one("#jackpot-amount", Static).update(f"{amount:,.0f} JACK")

    async def _refresh_history(self) -> None:
        resp = await self.rpc.list_lotto_commits()
        if not resp.success:
            return

        table = self.query_one("#history-table", DataTable)
        table.clear()

        commits = resp.result if isinstance(resp.result, list) else []
        # 최신순
        commits.sort(key=lambda c: c.get("commit_height", 0), reverse=True)

        for c in commits:
            nums = c.get("chosen_hex", [])
            num_str = " ".join(str(n).upper() for n in nums)
            height = c.get("commit_height", 0)
            block_str = f"#{height}" if height else "#0"
            status = c.get("status", "?")
            blocks_left = c.get("blocks_until_payout", 0)

            if status == "pending_mine":
                status_str = "MINING..."
                result_str = "--"
            elif blocks_left <= 0:
                status_str = "READY"
                result_str = ">>> Check!"
            else:
                status_str = f"D-{blocks_left}"
                result_str = f"{blocks_left} blocks"

            table.add_row(num_str, block_str, status_str, result_str)

    async def _do_check(self) -> None:
        """선택된 row 결과 확인"""
        table = self.query_one("#history-table", DataTable)
        try:
            row_idx = table.cursor_row
        except Exception:
            self._show_msg("Select a row first")
            return

        # commits에서 tx_id 가져오기
        resp = await self.rpc.list_lotto_commits()
        if not resp.success:
            self._show_msg("Error: Cannot fetch commits")
            return

        commits = resp.result if isinstance(resp.result, list) else []
        commits.sort(key=lambda c: c.get("commit_height", 0), reverse=True)

        if row_idx >= len(commits):
            self._show_msg("Invalid selection")
            return

        tx_id = commits[row_idx].get("tx_id", "")
        if not tx_id:
            self._show_msg("TX not yet mined")
            return

        result = await self.rpc.lotto_check_result(tx_id)
        if not result.success:
            self._show_msg(f"Error: {result.error}")
            return

        data = result.result
        status = data.get("status", "unknown")
        if status == "pending":
            left = data.get("blocks_left", 0)
            self._show_msg(f"Not ready yet. {left} blocks remaining.")
        elif status == "win":
            prize = data.get("prize_name", "")
            amount = data.get("prize_amount", 0)
            self._show_msg(f"🎉 {prize}! Prize: {amount:,.0f} JACK")
        elif status == "lose":
            matched = data.get("matched_count", 0)
            self._show_msg(f"No prize. Matched: {matched}/6")
        else:
            self._show_msg(f"Status: {status}")

        await self._refresh_history()

    async def on_unmount(self) -> None:
        await self.rpc.close()
        # 노드 프로세스 정리
        if self._node_process and self._node_process.poll() is None:
            self._node_process.terminate()
            try:
                self._node_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._node_process.kill()


def run_simple(host: str = "127.0.0.1", port: int = 8776):
    """Simple TUI 실행"""
    app = SimpleApp(host, port)
    app.run()
