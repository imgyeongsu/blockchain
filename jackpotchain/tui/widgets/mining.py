"""
Mining Widget

채굴 화면 + 노드 제어
"""

import subprocess
import sys
import os
from pathlib import Path

from textual.app import ComposeResult
from textual.widgets import Label, Button, Input
from textual.containers import ScrollableContainer, Horizontal, Vertical

from ..client import RPCClient


class MiningWidget(ScrollableContainer):
    """채굴 위젯 + 노드 제어"""

    can_focus = False

    def __init__(self, rpc: RPCClient, **kwargs):
        super().__init__(**kwargs)
        self.rpc = rpc
        self.node_process: subprocess.Popen | None = None
        self.mining_address: str = ""

    def compose(self) -> ComposeResult:
        # 노드 상태
        yield Vertical(
            Label("NODE STATUS", classes="box-title"),
            Horizontal(Label("Node", classes="stat-label"), Label("● OFFLINE", id="node-status", classes="stat-value red")),
            Horizontal(Label("RPC", classes="stat-label"), Label(f"{self.rpc.host}:{self.rpc.port}", id="rpc-endpoint", classes="stat-value")),
            classes="stat-box",
        )

        # 노드 컨트롤
        yield Vertical(
            Label("NODE CONTROL", classes="box-title"),
            Horizontal(
                Label("Miner Address:", classes="stat-label"),
                Input(placeholder="Enter wallet address...", id="input-address"),
            ),
            Horizontal(
                Button("▶ Start Node", id="btn-start-node", variant="success"),
                Button("■ Stop Node", id="btn-stop-node", variant="error"),
                classes="action-buttons",
            ),
            classes="stat-box",
        )

        # 채굴 상태
        yield Vertical(
            Label("MINING STATUS", classes="box-title"),
            Horizontal(Label("Status", classes="stat-label"), Label("⏹ STOPPED", id="mining-status", classes="stat-value red")),
            Horizontal(Label("Address", classes="stat-label"), Label("--", id="mining-address", classes="stat-value cyan")),
            Horizontal(Label("Hash Rate", classes="stat-label"), Label("-- H/s", id="hash-rate", classes="stat-value")),
            Horizontal(Label("Blocks Mined", classes="stat-label"), Label("0", id="blocks-mined", classes="stat-value green")),
            classes="stat-box",
        )

        # 통계
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
        if app.selected_address:
            address_input = self.query_one("#input-address", Input)
            if not address_input.value:  # 비어있을 때만
                address_input.value = app.selected_address

    def refresh_data(self) -> None:
        """데이터 새로고침"""
        self._sync_wallet_address()
        self.run_worker(self._load_data())

    async def _load_data(self) -> None:
        """비동기 데이터 로드"""
        # 노드 연결 상태 확인
        resp = await self.rpc.get_mining_info()
        node_status = self.query_one("#node-status", Label)

        if not resp.success:
            node_status.update("● OFFLINE")
            node_status.remove_class("green")
            node_status.add_class("red")
            return

        node_status.update("● ONLINE")
        node_status.remove_class("red")
        node_status.add_class("green")

        if resp.success:
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
            if is_mining:
                status_label = self.query_one("#mining-status", Label)
                status_label.update("⛏ MINING")
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
                status_label = self.query_one("#mining-status", Label)
                status_label.update("⏹ STOPPED")
                status_label.remove_class("green")
                status_label.add_class("red")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭"""
        if event.button.id == "btn-start-node":
            self._start_node()
        elif event.button.id == "btn-stop-node":
            self._stop_node()

    def _start_node(self) -> None:
        """노드 시작 (subprocess)"""
        if self.node_process and self.node_process.poll() is None:
            self.query_one("#mining-msg", Label).update("Node already running!")
            return

        # 주소 가져오기
        address_input = self.query_one("#input-address", Input)
        address = address_input.value.strip()

        if not address:
            self.query_one("#mining-msg", Label).update("Please enter miner address!")
            return

        self.mining_address = address

        # 실행 파일 찾기
        if getattr(sys, 'frozen', False):
            # PyInstaller로 빌드된 EXE
            exe_path = sys.executable
            cmd = [exe_path, "node", "--mine", "--address", address, "--rpc-port", str(self.rpc.port)]
        else:
            # Python 스크립트
            cmd = [sys.executable, "-m", "jackpotchain.cli.main", "node", "--mine", "--address", address, "--rpc-port", str(self.rpc.port)]

        try:
            # 노드를 백그라운드로 실행
            self.node_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
            )
            self.query_one("#mining-msg", Label).update(f"Node started! PID: {self.node_process.pid}")
            self.query_one("#mining-address", Label).update(f"{address[:12]}...{address[-6:]}")
        except Exception as e:
            self.query_one("#mining-msg", Label).update(f"Failed to start node: {e}")

    def _stop_node(self) -> None:
        """노드 중지"""
        if not self.node_process:
            self.query_one("#mining-msg", Label).update("No node running")
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

    def on_unmount(self) -> None:
        """위젯 언마운트 시 노드 정리"""
        if self.node_process and self.node_process.poll() is None:
            self.node_process.terminate()
            try:
                self.node_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.node_process.kill()
