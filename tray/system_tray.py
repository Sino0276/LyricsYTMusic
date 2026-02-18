"""
시스템 트레이 아이콘 관리.
pystray를 사용하여 트레이 아이콘과 컨텍스트 메뉴를 제공합니다.
"""

import threading
from typing import Callable, Optional

import pystray
from PIL import Image, ImageDraw


def create_icon_image(size: int = 64) -> Image.Image:
    """음표 모양의 트레이 아이콘 이미지 생성"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 배경 원
    draw.ellipse([2, 2, size - 2, size - 2], fill=(26, 26, 46, 220))

    # 음표 그리기
    note_color = (233, 69, 96, 255)
    cx, cy = size // 2, size // 2

    # 음표 머리 (타원)
    draw.ellipse([cx - 10, cy + 4, cx + 2, cy + 14], fill=note_color)
    # 음표 기둥
    draw.rectangle([cx + 2, cy - 14, cx + 5, cy + 8], fill=note_color)
    # 음표 꼬리
    draw.ellipse([cx + 5, cy - 14, cx + 16, cy - 4], fill=note_color)

    return img


class SystemTray:
    """시스템 트레이 아이콘 관리"""

    def __init__(self) -> None:
        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None

        # 콜백
        self._on_show: Optional[Callable[[], None]] = None
        self._on_center: Optional[Callable[[], None]] = None
        self._on_toggle_click_through: Optional[Callable[[], None]] = None
        self._on_exit: Optional[Callable[[], None]] = None

        # 상태
        self._click_through_enabled = False

    # ── 콜백 등록 ─────────────────────────────────────────────────────────────

    def set_on_show_window(self, callback: Callable[[], None]) -> None:
        self._on_show = callback

    def set_on_center_window(self, callback: Callable[[], None]) -> None:
        self._on_center = callback

    def set_on_toggle_click_through(self, callback: Callable[[], None]) -> None:
        self._on_toggle_click_through = callback

    def set_on_exit(self, callback: Callable[[], None]) -> None:
        self._on_exit = callback

    # ── 트레이 시작 ───────────────────────────────────────────────────────────

    def start(self, initial_click_through_state: bool = False) -> None:
        """트레이 아이콘 시작 (별도 스레드)"""
        self._click_through_enabled = initial_click_through_state

        def run_icon() -> None:
            icon_image = create_icon_image()

            click_through_item = pystray.MenuItem(
                lambda item: f"{'✓ ' if self._click_through_enabled else ''}클릭 투과",
                self._handle_toggle_click_through,
            )

            menu = pystray.Menu(
                pystray.MenuItem("🎵 창 표시", self._handle_show, default=True),
                pystray.MenuItem("📍 창 중앙으로", self._handle_center),
                pystray.Menu.SEPARATOR,
                click_through_item,
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("❌ 종료", self._handle_exit),
            )

            self._icon = pystray.Icon(
                "LyricsYTMusic",
                icon_image,
                "LyricsYTMusic",
                menu=menu,
            )
            self._icon.run()

        self._thread = threading.Thread(target=run_icon, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """트레이 아이콘 종료"""
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

    def update_click_through_state(self, enabled: bool) -> None:
        """클릭 투과 상태 업데이트 (메뉴 텍스트 갱신)"""
        self._click_through_enabled = enabled
        if self._icon:
            try:
                self._icon.update_menu()
            except Exception:
                pass

    # ── 이벤트 핸들러 ─────────────────────────────────────────────────────────

    def _handle_show(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        if self._on_show:
            self._on_show()

    def _handle_center(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        if self._on_center:
            self._on_center()

    def _handle_toggle_click_through(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self._click_through_enabled = not self._click_through_enabled
        if self._on_toggle_click_through:
            self._on_toggle_click_through()
        self.update_click_through_state(self._click_through_enabled)

    def _handle_exit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self.stop()
        if self._on_exit:
            self._on_exit()
