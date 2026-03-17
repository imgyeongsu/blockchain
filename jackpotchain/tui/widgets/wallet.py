"""
Wallet Widget

다중 지갑 통합 뷰 - 모든 지갑 파일을 한 화면에서 조회
"""

from pathlib import Path
from typing import Dict, List, Optional

from textual.app import ComposeResult
from textual.widgets import Static, Label, Input, Button, ListView, ListItem
from textual.containers import ScrollableContainer, Horizontal, Vertical

from ..client import RPCClient
from ...wallet.wallet import Wallet


class WalletWidget(ScrollableContainer):
    """다중 지갑 통합 위젯"""

    can_focus = False

    def __init__(self, rpc: RPCClient, **kwargs):
        super().__init__(**kwargs)
        self.rpc = rpc
        # 로드된 지갑들: {파일명: Wallet}
        self._wallets: Dict[str, Wallet] = {}
        # 주소별 잔액 캐시: {주소: 잔액}
        self._balances: Dict[str, float] = {}
        # 주소 → 지갑 매핑: {주소: 파일명}
        self._addr_to_wallet: Dict[str, str] = {}

    def compose(self) -> ComposeResult:
        # 총 잔액 헤더
        yield Vertical(
            Label("ALL WALLETS", classes="box-title"),
            Label("Total: -- JACK", id="total-balance", classes="stat-value green"),
            Label("Wallets: 0 | Addresses: 0", id="wallet-stats", classes="stat-value"),
            classes="stat-box",
        )

        # 지갑 목록 (스크롤 가능)
        yield Vertical(
            Label("WALLET LIST", classes="box-title"),
            ListView(id="wallet-list"),
            classes="stat-box",
            id="wallet-list-section",
        )

        # 액션 버튼
        yield Vertical(
            Horizontal(
                Button("[+] New Wallet", id="btn-create-wallet", variant="success"),
                Button("[R] Refresh", id="btn-refresh", variant="primary"),
                classes="action-buttons",
            ),
            classes="stat-box",
        )

        # 지갑 생성 패널 (숨김)
        yield Vertical(
            Label("CREATE NEW WALLET", classes="box-title"),
            Horizontal(
                Label("Name:", classes="stat-label"),
                Input(placeholder="e.g. mining", id="new-wallet-name"),
            ),
            Horizontal(
                Button("Create", id="btn-confirm-create", variant="success"),
                Button("Cancel", id="btn-cancel-create", variant="error"),
                classes="action-buttons",
            ),
            classes="stat-box hidden",
            id="create-wallet-panel",
        )

        # 상태 메시지
        yield Label("", id="wallet-status", classes="status-msg")

    def on_mount(self) -> None:
        """마운트 시"""
        self._load_all_wallets()
        self.refresh_data()
        self.set_interval(10, self._periodic_refresh)

    def _load_all_wallets(self) -> None:
        """모든 지갑 파일 로드"""
        self._wallets.clear()
        self._addr_to_wallet.clear()

        wallet_files = self.app.get_wallet_files()
        for wf in wallet_files:
            try:
                wallet = Wallet(str(wf))
                wallet_name = wf.stem
                self._wallets[wallet_name] = wallet

                # 주소 매핑
                for addr in wallet.get_addresses():
                    self._addr_to_wallet[addr] = wallet_name
                for addr in wallet._watch_only:
                    self._addr_to_wallet[addr] = wallet_name

            except Exception as e:
                pass  # 로드 실패한 지갑은 무시

    def refresh_data(self) -> None:
        """데이터 새로고침"""
        self._load_all_wallets()
        self._update_wallet_list()
        self.run_worker(self._load_all_balances())

    def _periodic_refresh(self) -> None:
        """주기적 새로고침 (잔액만)"""
        self.run_worker(self._load_all_balances())

    def _update_wallet_list(self) -> None:
        """지갑 목록 UI 업데이트"""
        list_view = self.query_one("#wallet-list", ListView)
        list_view.clear()

        if not self._wallets:
            list_view.append(ListItem(Label("(No wallets found)")))
            self.query_one("#wallet-stats", Label).update("Wallets: 0 | Addresses: 0")
            return

        total_addresses = 0

        for wallet_name, wallet in self._wallets.items():
            # 지갑 헤더
            addresses = wallet.get_addresses()
            watch_only = wallet._watch_only
            total_addresses += len(addresses) + len(watch_only)

            # 지갑 잔액 합계
            wallet_total = sum(
                self._balances.get(addr, 0)
                for addr in addresses
            )
            wallet_total += sum(
                self._balances.get(addr, 0)
                for addr in watch_only
            )

            header_text = f"[{wallet_name}.json] ({len(addresses)} addr) - {wallet_total:,.2f} JACK"
            header_item = ListItem(Label(header_text))
            header_item.data = {"type": "wallet", "name": wallet_name}
            list_view.append(header_item)

            # 주소들
            for addr in addresses:
                balance = self._balances.get(addr, 0)
                prefix = "[*]" if addr == self.app.selected_address else "   "
                addr_text = f"  {prefix} {addr[:16]}...{addr[-6:]} : {balance:,.2f} JACK"

                addr_item = ListItem(Label(addr_text))
                addr_item.data = {"type": "address", "address": addr, "wallet": wallet_name}
                list_view.append(addr_item)

            # Watch-only 주소
            for addr in watch_only:
                balance = self._balances.get(addr, 0)
                prefix = "[*]" if addr == self.app.selected_address else "   "
                addr_text = f"  {prefix} {addr[:16]}...{addr[-6:]} : {balance:,.2f} JACK (watch)"

                addr_item = ListItem(Label(addr_text))
                addr_item.data = {"type": "address", "address": addr, "wallet": wallet_name, "watch": True}
                list_view.append(addr_item)

        # 통계 업데이트
        self.query_one("#wallet-stats", Label).update(
            f"Wallets: {len(self._wallets)} | Addresses: {total_addresses}"
        )

    async def _load_all_balances(self) -> None:
        """모든 주소의 잔액 로드"""
        all_addresses = list(self._addr_to_wallet.keys())

        for addr in all_addresses:
            try:
                resp = await self.rpc.get_balance(addr)
                if resp.success:
                    self._balances[addr] = resp.result or 0
                else:
                    self._balances[addr] = 0
            except Exception:
                self._balances[addr] = 0

        # 총 잔액 업데이트
        total = sum(self._balances.values())
        self.query_one("#total-balance", Label).update(f"Total: {total:,.2f} JACK")

        # 목록도 업데이트 (잔액 반영)
        self._update_wallet_list()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭 처리"""
        btn_id = event.button.id

        if btn_id == "btn-create-wallet":
            self.query_one("#create-wallet-panel").remove_class("hidden")
        elif btn_id == "btn-confirm-create":
            self._create_wallet()
        elif btn_id == "btn-cancel-create":
            self.query_one("#create-wallet-panel").add_class("hidden")
        elif btn_id == "btn-refresh":
            self.refresh_data()
            self.query_one("#wallet-status", Label).update("Refreshed!")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """리스트 아이템 선택"""
        item = event.item
        if not hasattr(item, "data") or not item.data:
            return

        data = item.data

        if data.get("type") == "address":
            addr = data["address"]
            wallet_name = data["wallet"]

            # 선택된 주소 업데이트
            self.app.selected_address = addr

            # 해당 지갑도 현재 지갑으로 설정
            if wallet_name in self._wallets:
                self.app.current_wallet = self._wallets[wallet_name]
                wallet_path = self.app.wallet_dir / f"{wallet_name}.json"
                self.app.current_wallet_file = wallet_path

            self.query_one("#wallet-status", Label).update(
                f"Selected: {addr[:20]}... ({wallet_name})"
            )
            self._update_wallet_list()

    def _create_wallet(self) -> None:
        """새 지갑 생성"""
        name_input = self.query_one("#new-wallet-name", Input)
        name = name_input.value.strip()

        if not name:
            self.query_one("#wallet-status", Label).update("Enter wallet name")
            return

        # 특수문자 제거
        safe_name = "".join(c for c in name if c.isalnum() or c in "-_")
        if not safe_name:
            self.query_one("#wallet-status", Label).update("Enter valid name")
            return

        if self.app.create_wallet(safe_name):
            self.query_one("#wallet-status", Label).update(f"Created: {safe_name}.json")
            name_input.value = ""
            self.query_one("#create-wallet-panel").add_class("hidden")
            self.refresh_data()
        else:
            self.query_one("#wallet-status", Label).update("Failed (already exists?)")
