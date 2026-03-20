"""
Mining Widget

채굴 화면 + 노드 제어 (분리)
"""

import subprocess
import sys
import os
import asyncio
from pathlib import Path

from textual.app import ComposeResult
from textual.widgets import Label, Button
from textual.containers import ScrollableContainer, Horizontal, Vertical

from ..client import RPCClient


class MiningWidget(ScrollableContainer):
    """채굴 위젯 + 노드 제어 (분리)"""

    can_focus = False

    def __init__(self, rpc: RPCClient, **kwargs):
        super().__init__(**kwargs)
        self.rpc = rpc
        self.node_process: subprocess.Popen | None = None
        self.is_mining: bool = False

    def compose(self) -> ComposeResult:
        # 노드 상태
        yield Vertical(
            Label("NODE STATUS", classes="box-title"),
            Horizontal(Label("Node", classes="stat-label"), Label("OFFLINE", id="node-status", classes="stat-value red")),
            Horizontal(Label("RPC", classes="stat-label"), Label(f"{self.rpc.host}:{self.rpc.port}", id="rpc-endpoint", classes="stat-value")),
            classes="stat-box",
        )

        # 노드 컨트롤
        yield Vertical(
            Label("NODE CONTROL", classes="box-title"),
            Horizontal(
                Button("[>] Start Node", id="btn-start-node", variant="success"),
                Button("[X] Stop Node", id="btn-stop-node", variant="error"),
                classes="action-buttons",
            ),
            classes="stat-box",
        )

        # 채굴 컨트롤
        yield Vertical(
            Label("MINING CONTROL", classes="box-title"),
            Horizontal(Label("Current:", classes="stat-label"), Label("--", id="current-mining-addr", classes="stat-value cyan")),
            Horizontal(Label("Selected:", classes="stat-label"), Label("--", id="selected-addr", classes="stat-value yellow")),
            Horizontal(
                Button("[A] Apply Address", id="btn-apply-address", variant="primary"),
                Button("[M] Start Mining", id="btn-start-mining", variant="warning"),
                Button("[S] Stop Mining", id="btn-stop-mining", variant="default"),
                classes="action-buttons",
            ),
            classes="stat-box",
        )

        # 채굴 상태
        yield Vertical(
            Label("MINING STATUS", classes="box-title"),
            Horizontal(Label("Status", classes="stat-label"), Label("STOPPED", id="mining-status", classes="stat-value red")),
            Horizontal(Label("Address", classes="stat-label"), Label("--", id="mining-address", classes="stat-value cyan")),
            Horizontal(Label("Hash Rate", classes="stat-label"), Label("-- H/s", id="hash-rate", classes="stat-value")),
            Horizontal(Label("Blocks Mined", classes="stat-label"), Label("0", id="blocks-mined", classes="stat-value green")),
            classes="stat-box",
        )

        # 블록체인 정보
        yield Vertical(
            Label("BLOCKCHAIN", classes="box-title"),
            Horizontal(Label("Height", classes="stat-label"), Label("--", id="current-block", classes="stat-value cyan")),
            Horizontal(Label("Difficulty", classes="stat-label"), Label("--", id="difficulty", classes="stat-value")),
            Horizontal(Label("Mempool TXs", classes="stat-label"), Label("--", id="mempool-txs", classes="stat-value")),
            classes="stat-box",
        )

        # 상태 메시지
        yield Label("", id="mining-msg", classes="status-msg")

    def on_mount(self) -> None:
        """마운트 시"""
        self._sync_wallet_address()
        self.refresh_data()
        self.set_interval(2, self.refresh_data)

    def _sync_wallet_address(self) -> None:
        """Wallet에서 선택된 주소 동기화"""
        app = self.app
        selected_label = self.query_one("#selected-addr", Label)

        if app.selected_address:
            addr = app.selected_address
            display = f"{addr[:12]}...{addr[-6:]}" if len(addr) > 20 else addr
            selected_label.update(display)
        else:
            selected_label.update("(select in Wallet tab)")

    def refresh_data(self) -> None:
        """데이터 새로고침"""
        self._sync_wallet_address()
        self.run_worker(self._load_data())

    async def _load_data(self) -> None:
        """비동기 데이터 로드"""
        resp = await self.rpc.get_mining_info()
        node_status = self.query_one("#node-status", Label)

        if not resp.success:
            node_status.update("OFFLINE")
            node_status.remove_class("green")
            node_status.add_class("red")

            # 채굴 상태도 리셋
            status_label = self.query_one("#mining-status", Label)
            status_label.update("STOPPED")
            status_label.remove_class("green")
            status_label.add_class("red")
            self.is_mining = False
            return

        node_status.update("ONLINE")
        node_status.remove_class("red")
        node_status.add_class("green")

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
        self.is_mining = is_mining

        status_label = self.query_one("#mining-status", Label)
        if is_mining:
            status_label.update("MINING")
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
            status_label.update("STOPPED")
            status_label.remove_class("green")
            status_label.add_class("red")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭"""
        if event.button.id == "btn-start-node":
            self._start_node()
        elif event.button.id == "btn-stop-node":
            self.run_worker(self._stop_node_async())
        elif event.button.id == "btn-apply-address":
            self._apply_address()
        elif event.button.id == "btn-start-mining":
            self.run_worker(self._start_mining())
        elif event.button.id == "btn-stop-mining":
            self.run_worker(self._stop_mining())

    def _apply_address(self) -> None:
        """선택된 주소를 채굴 주소로 적용"""
        app = self.app
        if not app.selected_address:
            self.query_one("#mining-msg", Label).update("Select address in Wallet tab first!")
            return

        # 채굴 주소 저장
        addr = app.selected_address
        app.mining_address = addr

        # UI 업데이트
        display = f"{addr[:12]}...{addr[-6:]}" if len(addr) > 20 else addr
        self.query_one("#current-mining-addr", Label).update(display)
        self.query_one("#mining-msg", Label).update(f"Applied: {display}")

        # 채굴 중이면 재시작 필요 알림
        if self.is_mining:
            self.query_one("#mining-msg", Label).update(f"Applied: {display} (restart mining to take effect)")

    def _is_node_running(self) -> bool:
        """노드 프로세스 실행 중인지 확인"""
        return self.node_process is not None and self.node_process.poll() is None

    def _start_node(self) -> None:
        """노드만 시작 (채굴 X)"""
        if self._is_node_running():
            self.query_one("#mining-msg", Label).update("Node already running!")
            return

        # 지갑 파일 확인
        app = self.app
        if not app.current_wallet_file:
            self.query_one("#mining-msg", Label).update("Select wallet first! (F2)")
            return

        wallet_path = str(app.current_wallet_file.absolute())

        # 실행 파일 찾기
        if getattr(sys, 'frozen', False):
            exe_path = sys.executable
            cmd = [exe_path, "node", "--rpc-port", str(self.rpc.port), "--wallet-file", wallet_path]
        else:
            cmd = [sys.executable, "-m", "jackpotchain.cli.main", "node", "--rpc-port", str(self.rpc.port), "--wallet-file", wallet_path]

        try:
            # 디버그: 로그 파일로 출력 (APPDATA에 저장)
            appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
            log_path = os.path.join(appdata, 'JackpotChain', 'node_subprocess.log')
            log_file = open(log_path, "w", encoding="utf-8")
            log_file.write(f"CMD: {cmd}\n")
            log_file.flush()

            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUNBUFFERED"] = "1"
            self.node_process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=env,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
            )
            self.query_one("#mining-msg", Label).update(f"Node started with {app.current_wallet_file.name}")
        except Exception as e:
            self.query_one("#mining-msg", Label).update(f"Failed: {e}")

    async def _stop_node_async(self) -> None:
        """노드 중지 (채굴 중이면 먼저 중지)"""
        # 채굴 중이면 먼저 중지
        if self.is_mining:
            self.query_one("#mining-msg", Label).update("Stopping mining first...")
            await self._stop_mining()
            await asyncio.sleep(1)

        if not self.node_process:
            self.query_one("#mining-msg", Label).update("No node to stop")
            return

        if self.node_process.poll() is not None:
            self.query_one("#mining-msg", Label).update("Node already stopped")
            self.node_process = None
            return

        try:
            self.node_process.terminate()
            self.node_process.wait(timeout=5)
            self.query_one("#mining-msg", Label).update("Node stopped")
        except subprocess.TimeoutExpired:
            self.node_process.kill()
            self.query_one("#mining-msg", Label).update("Node force killed")
        finally:
            self.node_process = None

    async def _start_mining(self) -> None:
        """채굴 시작 (노드 OFF면 먼저 시작)"""
        # 주소 확인 (Apply된 주소 사용)
        address = getattr(self.app, 'mining_address', None)

        if not address:
            self.query_one("#mining-msg", Label).update("Apply address first!")
            return

        # 노드가 안 켜져 있으면 먼저 시작
        resp = await self.rpc.get_mining_info()
        if not resp.success:
            self.query_one("#mining-msg", Label).update("Starting node first...")
            self._start_node()
            # 노드 시작 대기
            for _ in range(10):
                await asyncio.sleep(1)
                resp = await self.rpc.get_mining_info()
                if resp.success:
                    break
            else:
                self.query_one("#mining-msg", Label).update("Node start timeout!")
                return

        # 채굴 시작 (RPC)
        resp = await self.rpc.start_mining(address)
        if resp.success:
            self.query_one("#mining-msg", Label).update(f"Mining started! Address: {address[:16]}...")
            self.query_one("#mining-address", Label).update(f"{address[:12]}...{address[-6:]}")
        else:
            self.query_one("#mining-msg", Label).update(f"Error: {resp.error}")

    async def _stop_mining(self) -> None:
        """채굴 중지"""
        resp = await self.rpc.stop_mining()
        if resp.success:
            self.query_one("#mining-msg", Label).update("Mining stopped")
            self.is_mining = False
        else:
            self.query_one("#mining-msg", Label).update(f"Error: {resp.error}")

    def on_unmount(self) -> None:
        """위젯 언마운트 시 노드 정리"""
        if self.node_process and self.node_process.poll() is None:
            self.node_process.terminate()
            try:
                self.node_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.node_process.kill()
