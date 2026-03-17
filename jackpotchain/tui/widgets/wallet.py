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
            Label("내 지갑", classes="box-title", id="wallet-title"),
            Label("💰 총 잔액: -- JACK", id="total-balance", classes="stat-value green"),
            classes="stat-box",
            id="wallet-header",
        )

        # 주소 목록
        yield Vertical(
            Label("📍 주소 목록", classes="box-title"),
            ListView(id="address-list"),
            Horizontal(
                Button("+ 주소 추가", id="btn-add-address", variant="success"),
                Button("📂 지갑 전환", id="btn-switch-wallet", variant="primary"),
                Button("⚙️ 고급", id="btn-advanced", variant="default"),
                classes="action-buttons",
            ),
            classes="stat-box",
            id="address-section",
        )

        # 지갑 없을 때 표시
        yield Vertical(
            Label("지갑이 없습니다", classes="box-title"),
            Label("새 지갑을 만들거나 기존 지갑을 불러오세요.", id="no-wallet-msg"),
            Horizontal(
                Button("🆕 새 지갑 만들기", id="btn-create-wallet", variant="success"),
                Button("📂 기존 지갑 불러오기", id="btn-load-wallet", variant="primary"),
                classes="action-buttons",
            ),
            classes="stat-box",
            id="no-wallet-section",
        )

        # 지갑 생성 패널 (숨김)
        yield Vertical(
            Label("새 지갑 만들기", classes="box-title"),
            Horizontal(
                Label("지갑 이름:", classes="stat-label"),
                Input(placeholder="예: 채굴용", id="new-wallet-name"),
            ),
            Horizontal(
                Button("생성", id="btn-confirm-create", variant="success"),
                Button("취소", id="btn-cancel-create", variant="error"),
                classes="action-buttons",
            ),
            classes="stat-box hidden",
            id="create-wallet-panel",
        )

        # 지갑 선택 패널 (숨김)
        yield Vertical(
            Label("지갑 선택", classes="box-title"),
            ListView(id="wallet-file-list"),
            Horizontal(
                Button("선택", id="btn-confirm-load", variant="success"),
                Button("취소", id="btn-cancel-load", variant="error"),
                classes="action-buttons",
            ),
            classes="stat-box hidden",
            id="load-wallet-panel",
        )

        # 고급 설정 패널 (숨김)
        yield Vertical(
            Label("⚙️ 고급 설정", classes="box-title"),
            Horizontal(
                Label("개인키 가져오기:", classes="stat-label"),
                Input(placeholder="개인키 (hex)", id="import-privkey"),
                Button("가져오기", id="btn-import-key", variant="warning"),
            ),
            Horizontal(
                Label("주소만 등록:", classes="stat-label"),
                Input(placeholder="주소 (받기 전용)", id="watch-address"),
                Button("등록", id="btn-add-watch", variant="primary"),
            ),
            Horizontal(
                Button("닫기", id="btn-close-advanced", variant="default"),
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
            prefix = "● " if addr == app.selected_address else "○ "
            display = f"{prefix}{addr[:12]}...{addr[-6:]}"
            if label:
                display += f" ({label})"

            item = ListItem(Label(display), id=f"addr-{addr[:16]}")
            item.data = addr  # 전체 주소 저장
            list_view.append(item)

        # Watch-only 주소
        for addr in watch_only:
            display = f"👁 {addr[:12]}...{addr[-6:]} (감시)"
            item = ListItem(Label(display), id=f"watch-{addr[:16]}")
            item.data = addr
            list_view.append(item)

    async def _load_balance(self) -> None:
        """잔액 로드 (RPC)"""
        app = self.app
        if not app.selected_address:
            self.query_one("#total-balance", Label).update("💰 총 잔액: 0 JACK")
            return

        resp = await self.rpc.get_balance(app.selected_address)
        if resp.success:
            balance = resp.result or 0
            self.query_one("#total-balance", Label).update(f"💰 총 잔액: {balance:,.2f} JACK")
        else:
            self.query_one("#total-balance", Label).update("💰 총 잔액: -- (노드 연결 필요)")

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
            item = ListItem(Label(f"📁 {wf.name}"), id=f"wf-{wf.stem}")
            item.data = wf
            list_view.append(item)

        if not wallet_files:
            list_view.append(ListItem(Label("(지갑 파일 없음)")))

    def _create_wallet(self) -> None:
        """새 지갑 생성"""
        name = self.query_one("#new-wallet-name", Input).value.strip()
        if not name:
            self.query_one("#wallet-status", Label).update("지갑 이름을 입력하세요")
            return

        # 특수문자 제거
        safe_name = "".join(c for c in name if c.isalnum() or c in "-_")
        if not safe_name:
            self.query_one("#wallet-status", Label).update("올바른 이름을 입력하세요")
            return

        if self.app.create_wallet(safe_name):
            self.query_one("#wallet-status", Label).update(f"지갑 생성 완료: {safe_name}.json")
            self.query_one("#new-wallet-name", Input).value = ""
            self._hide_panel("create-wallet-panel")
            self._update_ui()
        else:
            self.query_one("#wallet-status", Label).update("지갑 생성 실패 (이미 존재?)")

    def _load_selected_wallet(self) -> None:
        """선택된 지갑 로드"""
        list_view = self.query_one("#wallet-file-list", ListView)
        if list_view.highlighted_child and hasattr(list_view.highlighted_child, "data"):
            wallet_path = list_view.highlighted_child.data
            if self.app.load_wallet(wallet_path):
                self.query_one("#wallet-status", Label).update(f"지갑 로드: {wallet_path.name}")
                self._hide_panel("load-wallet-panel")
                self._update_ui()
            else:
                self.query_one("#wallet-status", Label).update("지갑 로드 실패")
        else:
            self.query_one("#wallet-status", Label).update("지갑을 선택하세요")

    def _add_new_address(self) -> None:
        """새 주소 추가"""
        if not self.app.current_wallet:
            return

        new_addr = self.app.current_wallet.generate_address()
        self.app.selected_address = new_addr
        self.query_one("#wallet-status", Label).update(f"새 주소: {new_addr[:20]}...")
        self._update_address_list()

    def _import_private_key(self) -> None:
        """개인키 가져오기"""
        if not self.app.current_wallet:
            self.query_one("#wallet-status", Label).update("먼저 지갑을 만드세요")
            return

        privkey_hex = self.query_one("#import-privkey", Input).value.strip()
        if not privkey_hex:
            self.query_one("#wallet-status", Label).update("개인키를 입력하세요")
            return

        try:
            privkey = bytes.fromhex(privkey_hex)
            if len(privkey) != 32:
                raise ValueError("32바이트 필요")

            addr = self.app.current_wallet.import_private_key(privkey)
            self.app.selected_address = addr
            self.query_one("#wallet-status", Label).update(f"가져오기 완료: {addr[:20]}...")
            self.query_one("#import-privkey", Input).value = ""
            self._update_address_list()
        except Exception as e:
            self.query_one("#wallet-status", Label).update(f"오류: {e}")

    def _add_watch_only(self) -> None:
        """감시 전용 주소 추가"""
        if not self.app.current_wallet:
            self.query_one("#wallet-status", Label).update("먼저 지갑을 만드세요")
            return

        addr = self.query_one("#watch-address", Input).value.strip()
        if not addr:
            self.query_one("#wallet-status", Label).update("주소를 입력하세요")
            return

        if self.app.current_wallet.add_watch_only(addr):
            self.query_one("#wallet-status", Label).update(f"감시 주소 추가: {addr[:20]}...")
            self.query_one("#watch-address", Input).value = ""
            self._update_address_list()
        else:
            self.query_one("#wallet-status", Label).update("올바르지 않은 주소")
