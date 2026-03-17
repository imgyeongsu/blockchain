"""
Wallet Widget

지갑 화면 - 로컬 파일 기반 + RPC 연동
"""

from pathlib import Path

from textual.app import ComposeResult
from textual.widgets import Static, Label, Input, Button, ListView, ListItem
from textual.containers import ScrollableContainer, Horizontal, Vertical

from ..client import RPCClient


class WalletWidget(ScrollableContainer):
    """지갑 위젯 (로컬 파일 + RPC 연동)"""

    can_focus = False

    def __init__(self, rpc: RPCClient, **kwargs):
        super().__init__(**kwargs)
        self.rpc = rpc

    def compose(self) -> ComposeResult:
        # 지갑 상태에 따라 다른 UI
        yield Vertical(
            # 지갑 정보 헤더
            Label("MY WALLET", classes="box-title", id="wallet-title"),
            Label("[Balance] -- JACK", id="total-balance", classes="stat-value green"),
            classes="stat-box",
            id="wallet-header",
        )

        # 주소 목록
        yield Vertical(
            Label("ADDRESSES", classes="box-title"),
            ListView(id="address-list"),
            Horizontal(
                Button("[+] Add Address", id="btn-add-address", variant="success"),
                Button("[W] Switch Wallet", id="btn-switch-wallet", variant="primary"),
                Button("[S] Settings", id="btn-advanced", variant="default"),
                classes="action-buttons",
            ),
            classes="stat-box",
            id="address-section",
        )

        # 지갑 없을 때 표시
        yield Vertical(
            Label("NO WALLET", classes="box-title"),
            Label("Create a new wallet or load an existing one.", id="no-wallet-msg"),
            Horizontal(
                Button("[N] New Wallet", id="btn-create-wallet", variant="success"),
                Button("[L] Load Wallet", id="btn-load-wallet", variant="primary"),
                classes="action-buttons",
            ),
            classes="stat-box",
            id="no-wallet-section",
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

        # 지갑 선택 패널 (숨김)
        yield Vertical(
            Label("SELECT WALLET", classes="box-title"),
            ListView(id="wallet-file-list"),
            Horizontal(
                Button("Select", id="btn-confirm-load", variant="success"),
                Button("Cancel", id="btn-cancel-load", variant="error"),
                classes="action-buttons",
            ),
            classes="stat-box hidden",
            id="load-wallet-panel",
        )

        # 고급 설정 패널 (숨김)
        yield Vertical(
            Label("ADVANCED SETTINGS", classes="box-title"),
            Horizontal(
                Label("Import Key:", classes="stat-label"),
                Input(placeholder="Private key (hex)", id="import-privkey"),
                Button("Import", id="btn-import-key", variant="warning"),
            ),
            Horizontal(
                Label("Watch Only:", classes="stat-label"),
                Input(placeholder="Address (receive only)", id="watch-address"),
                Button("Add", id="btn-add-watch", variant="primary"),
            ),
            Horizontal(
                Button("Close", id="btn-close-advanced", variant="default"),
                classes="action-buttons",
            ),
            classes="stat-box hidden",
            id="advanced-panel",
        )

        # 상태 메시지
        yield Label("", id="wallet-status", classes="status-msg")

    def on_mount(self) -> None:
        """마운트 시"""
        self.refresh_data()
        self.set_interval(5, self._update_balance)

    def refresh_data(self) -> None:
        """데이터 새로고침"""
        self._update_ui()

    def _update_ui(self) -> None:
        """UI 상태 업데이트"""
        app = self.app

        has_wallet = app.current_wallet is not None

        # 섹션 표시/숨김
        self.query_one("#wallet-header").set_class(not has_wallet, "hidden")
        self.query_one("#address-section").set_class(not has_wallet, "hidden")
        self.query_one("#no-wallet-section").set_class(has_wallet, "hidden")

        if has_wallet:
            # 지갑 파일명 표시
            wallet_name = app.current_wallet_file.stem if app.current_wallet_file else "Unknown"
            self.query_one("#wallet-title", Label).update(f"내 지갑: {wallet_name}.json")

            # 주소 목록 업데이트
            self._update_address_list()

            # 잔액 업데이트
            self.run_worker(self._load_balance())

    def _update_address_list(self) -> None:
        """주소 목록 업데이트"""
        app = self.app
        if not app.current_wallet:
            return

        list_view = self.query_one("#address-list", ListView)
        list_view.clear()

        addresses = app.current_wallet.get_addresses()
        watch_only = app.current_wallet._watch_only

        for addr in addresses:
            info = app.current_wallet._addresses.get(addr)
            label = info.label if info and info.label else ""

            # 선택된 주소 표시
            prefix = "[*] " if addr == app.selected_address else "[ ] "
            display = f"{prefix}{addr[:12]}...{addr[-6:]}"
            if label:
                display += f" ({label})"

            item = ListItem(Label(display))
            item.data = addr  # 전체 주소 저장
            list_view.append(item)

        # Watch-only 주소
        for addr in watch_only:
            display = f"[W] {addr[:12]}...{addr[-6:]} (watch)"
            item = ListItem(Label(display))
            item.data = addr
            list_view.append(item)

    async def _load_balance(self) -> None:
        """잔액 로드 (RPC)"""
        app = self.app
        if not app.selected_address:
            self.query_one("#total-balance", Label).update("[Balance] 0 JACK")
            return

        resp = await self.rpc.get_balance(app.selected_address)
        if resp.success:
            balance = resp.result or 0
            self.query_one("#total-balance", Label).update(f"[Balance] {balance:,.2f} JACK")
        else:
            self.query_one("#total-balance", Label).update("[Balance] -- (node required)")

    def _update_balance(self) -> None:
        """주기적 잔액 업데이트"""
        if self.app.current_wallet:
            self.run_worker(self._load_balance())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """버튼 클릭 처리"""
        btn_id = event.button.id

        # 지갑 생성/불러오기
        if btn_id == "btn-create-wallet":
            self._show_panel("create-wallet-panel")
        elif btn_id == "btn-load-wallet" or btn_id == "btn-switch-wallet":
            self._show_wallet_list()
            self._show_panel("load-wallet-panel")
        elif btn_id == "btn-confirm-create":
            self._create_wallet()
        elif btn_id == "btn-cancel-create":
            self._hide_panel("create-wallet-panel")
        elif btn_id == "btn-confirm-load":
            self._load_selected_wallet()
        elif btn_id == "btn-cancel-load":
            self._hide_panel("load-wallet-panel")

        # 주소 관리
        elif btn_id == "btn-add-address":
            self._add_new_address()

        # 고급 설정
        elif btn_id == "btn-advanced":
            self._show_panel("advanced-panel")
        elif btn_id == "btn-close-advanced":
            self._hide_panel("advanced-panel")
        elif btn_id == "btn-import-key":
            self._import_private_key()
        elif btn_id == "btn-add-watch":
            self._add_watch_only()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """리스트 아이템 선택"""
        item = event.item
        if hasattr(item, "data"):
            addr = item.data
            # 주소 선택
            if event.list_view.id == "address-list":
                self.app.selected_address = addr
                self._update_address_list()
                self.query_one("#wallet-status", Label).update(f"선택됨: {addr[:20]}...")
            # 지갑 파일 선택
            elif event.list_view.id == "wallet-file-list":
                # 선택만 표시, 확인 버튼으로 로드
                pass

    def _show_panel(self, panel_id: str) -> None:
        """패널 표시"""
        # 모든 패널 숨기기
        for pid in ["create-wallet-panel", "load-wallet-panel", "advanced-panel"]:
            self.query_one(f"#{pid}").add_class("hidden")
        # 선택된 패널 표시
        self.query_one(f"#{panel_id}").remove_class("hidden")

    def _hide_panel(self, panel_id: str) -> None:
        """패널 숨기기"""
        self.query_one(f"#{panel_id}").add_class("hidden")

    def _show_wallet_list(self) -> None:
        """지갑 파일 목록 표시"""
        list_view = self.query_one("#wallet-file-list", ListView)
        list_view.clear()

        wallet_files = self.app.get_wallet_files()
        for wf in wallet_files:
            item = ListItem(Label(f"> {wf.name}"))
            item.data = wf
            list_view.append(item)

        if not wallet_files:
            list_view.append(ListItem(Label("(지갑 파일 없음)")))

    def _create_wallet(self) -> None:
        """새 지갑 생성"""
        name = self.query_one("#new-wallet-name", Input).value.strip()
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
            self.query_one("#new-wallet-name", Input).value = ""
            self._hide_panel("create-wallet-panel")
            self._update_ui()
        else:
            self.query_one("#wallet-status", Label).update("Failed (already exists?)")

    def _load_selected_wallet(self) -> None:
        """선택된 지갑 로드"""
        list_view = self.query_one("#wallet-file-list", ListView)
        if list_view.highlighted_child and hasattr(list_view.highlighted_child, "data"):
            wallet_path = list_view.highlighted_child.data
            if self.app.load_wallet(wallet_path):
                self.query_one("#wallet-status", Label).update(f"Loaded: {wallet_path.name}")
                self._hide_panel("load-wallet-panel")
                self._update_ui()
            else:
                self.query_one("#wallet-status", Label).update("Load failed")
        else:
            self.query_one("#wallet-status", Label).update("Select a wallet")

    def _add_new_address(self) -> None:
        """새 주소 추가"""
        if not self.app.current_wallet:
            return

        new_addr = self.app.current_wallet.generate_address()
        self.app.selected_address = new_addr
        self.query_one("#wallet-status", Label).update(f"New: {new_addr[:20]}...")
        self._update_address_list()

    def _import_private_key(self) -> None:
        """개인키 가져오기"""
        if not self.app.current_wallet:
            self.query_one("#wallet-status", Label).update("Create wallet first")
            return

        privkey_hex = self.query_one("#import-privkey", Input).value.strip()
        if not privkey_hex:
            self.query_one("#wallet-status", Label).update("Enter private key")
            return

        try:
            privkey = bytes.fromhex(privkey_hex)
            if len(privkey) != 32:
                raise ValueError("Need 32 bytes")

            addr = self.app.current_wallet.import_private_key(privkey)
            self.app.selected_address = addr
            self.query_one("#wallet-status", Label).update(f"Imported: {addr[:20]}...")
            self.query_one("#import-privkey", Input).value = ""
            self._update_address_list()
        except Exception as e:
            self.query_one("#wallet-status", Label).update(f"Error: {e}")

    def _add_watch_only(self) -> None:
        """감시 전용 주소 추가"""
        if not self.app.current_wallet:
            self.query_one("#wallet-status", Label).update("Create wallet first")
            return

        addr = self.query_one("#watch-address", Input).value.strip()
        if not addr:
            self.query_one("#wallet-status", Label).update("Enter address")
            return

        if self.app.current_wallet.add_watch_only(addr):
            self.query_one("#wallet-status", Label).update(f"Watch added: {addr[:20]}...")
            self.query_one("#watch-address", Input).value = ""
            self._update_address_list()
        else:
            self.query_one("#wallet-status", Label).update("Invalid address")
