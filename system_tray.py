"""
시스템 트레이 아이콘 모듈.
우클릭 메뉴로 오버레이 제어 기능 제공.
"""

import threading
from typing import Callable, Optional

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    print("[경고] pystray 또는 pillow가 설치되지 않음. 트레이 아이콘 비활성화.")


def create_icon_image(size=64, color="#4a90d9"):
    """간단한 음표 모양 아이콘 생성"""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # 배경 원
    draw.ellipse([4, 4, size-4, size-4], fill=color)
    
    # 음표 기호 (♪) 스타일
    # 음표 머리
    draw.ellipse([size//4, size//2, size//2+4, size//2+size//4], fill="white")
    # 음표 줄기
    draw.rectangle([size//2, size//4, size//2+4, size//2+size//8], fill="white")
    
    return image


class SystemTray:
    """시스템 트레이 아이콘 관리"""
    
    def __init__(self):
        self._icon: Optional[pystray.Icon] = None
        self._on_center_window: Optional[Callable] = None
        self._on_show_window: Optional[Callable] = None
        self._on_toggle_click_through: Optional[Callable] = None
        self._on_exit: Optional[Callable] = None
        self._thread: Optional[threading.Thread] = None
    
    def set_on_center_window(self, callback: Callable):
        """창 중앙 이동 콜백 설정"""
        self._on_center_window = callback
    
    def set_on_show_window(self, callback: Callable):
        """창 표시 콜백 설정"""
        self._on_show_window = callback
    
    def set_on_exit(self, callback: Callable):
        """종료 콜백 설정"""
        self._on_exit = callback
    
    def set_on_toggle_click_through(self, callback: Callable):
        """클릭 투과 토글 콜백 설정"""
        self._on_toggle_click_through = callback

    def _center_window(self, icon, item):
        """창 중앙 이동 메뉴 클릭"""
        if self._on_center_window:
            self._on_center_window()
    
    def _toggle_click_through(self, icon, item):
        """클릭 투과 토글 메뉴 클릭"""
        # 현재 내부 상태의 반대로 토글 (item.checked 무시 - 동기화 문제 방지)
        new_state = not self._click_through_state
        if self._on_toggle_click_through:
            self._on_toggle_click_through(new_state)
    
    def _show_window(self, icon, item):
        """창 표시 메뉴 클릭"""
        if self._on_show_window:
            self._on_show_window()
    
    def _exit_app(self, icon, item):
        """앱 종료"""
        if self._on_exit:
            self._on_exit()
        self.stop()
    
    def start(self, initial_click_through_state=False):
        """트레이 아이콘 시작"""
        if not TRAY_AVAILABLE:
            print("[트레이] pystray 미설치로 비활성화됨")
            return False
        
        self._click_through_state = initial_click_through_state

        def run_icon():
            icon_image = create_icon_image()
            
            menu = pystray.Menu(
                pystray.MenuItem("🎵 창 표시", self._show_window, default=True),
                pystray.MenuItem("📍 화면 중앙으로 이동", self._center_window),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("🖱️ 오버레이 클릭 투과", self._toggle_click_through, checked=lambda item: self._click_through_state),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("❌ 종료", self._exit_app),
            )
            
            self._icon = pystray.Icon(
                "lyrics_overlay",
                icon_image,
                "YouTube Music 가사",
                menu
            )
            
            print("[트레이] 시스템 트레이 아이콘 시작됨")
            self._icon.run()
        
        self._thread = threading.Thread(target=run_icon, daemon=True)
        self._thread.start()
        return True
    
    def update_click_through_state(self, enabled: bool):
        """클릭 투과 상태 업데이트 (외부에서 변경 시)"""
        self._click_through_state = enabled
        if self._icon:
            self._icon.update_menu()
    
    def stop(self):
        """트레이 아이콘 중지"""
        if self._icon:
            self._icon.stop()
            self._icon = None
            print("[트레이] 시스템 트레이 아이콘 중지됨")


if __name__ == "__main__":
    import time
    
    def on_center():
        print("창 중앙 이동 요청!")
    
    def on_show():
        print("창 표시 요청!")
    
    def on_exit():
        print("종료 요청!")
    
    tray = SystemTray()
    tray.set_on_center_window(on_center)
    tray.set_on_show_window(on_show)
    tray.set_on_exit(on_exit)
    tray.start()
    
    print("트레이 아이콘 테스트 (Ctrl+C로 종료)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        tray.stop()
        print("종료됨")
