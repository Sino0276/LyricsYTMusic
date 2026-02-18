"""
메인 오버레이 창.
각 패널 컴포넌트를 조립하고 ViewModel과 연결합니다.
"""

import queue
import tkinter as tk
from typing import Callable, Optional

import win32con
import win32gui

from core.constants import DEFAULT_WINDOW_HEIGHT, DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_MARGIN_X, DEFAULT_WINDOW_MARGIN_Y
from core.models import LyricDisplayLine
from settings.settings_manager import SettingsManager
from ui.lyrics_panel import LyricsPanel
from ui.search_panel import SearchPanel
from ui.settings_panel import SettingsPanel
from ui.sync_panel import SyncPanel
from ui.title_bar import TitleBar
from ui.widgets.theme_engine import apply_theme_recursive, calculate_panel_color
from ui.widgets.resize_grip import ResizeGrip


class OverlayWindow:
    """
    메인 오버레이 창.
    항상 위에 표시되는 투명 창으로, 각 패널을 조립합니다.
    """

    def __init__(self, settings: SettingsManager) -> None:
        self._settings = settings
        self._running = True
        self._minimized = False
        self._click_through = False

        # UI 명령 큐 (스레드 안전 UI 업데이트)
        self._cmd_queue: queue.Queue = queue.Queue()

        # 콜백 (ViewModel이 등록)
        self._on_close_callback: Optional[Callable[[], None]] = None
        self._on_sync_change: Optional[Callable[[int], None]] = None
        self._on_search: Optional[Callable[[str, str], None]] = None
        self._on_apply_lyrics: Optional[Callable[[str, str], None]] = None

        self._root: Optional[tk.Tk] = None
        self._setup_window()
        self._create_panels()
        self._apply_settings(settings.get_all())
        self._process_queue()

    # ── 창 설정 ───────────────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        """Tkinter 창 초기화"""
        self._root = tk.Tk()
        self._root.title("LyricsYTMusic")
        self._root.overrideredirect(True)   # 기본 타이틀 바 제거
        self._root.wm_attributes("-topmost", True)
        self._root.wm_attributes("-alpha", self._settings.get("opacity", 0.9))

        # 초기 위치 (화면 우측 하단)
        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        x = screen_w - DEFAULT_WINDOW_WIDTH - DEFAULT_WINDOW_MARGIN_X
        y = screen_h - DEFAULT_WINDOW_HEIGHT - DEFAULT_WINDOW_MARGIN_Y
        self._root.geometry(f"{DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT}+{x}+{y}")

        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_panels(self) -> None:
        """패널 조립"""
        bg = self._settings.get("background_color", "#1a1a2e")
        panel = calculate_panel_color(bg)
        text = self._settings.get("text_color", "#e0e0e0")
        highlight = self._settings.get("highlight_color", "#e94560")
        font_family = self._settings.get("font_family", "Malgun Gothic")
        font_size = self._settings.get("font_size", 11)

        # 메인 프레임
        self._main_frame = tk.Frame(
            self._root,
            bg=bg,
            highlightbackground="#4a4a6a",
            highlightthickness=2,
        )
        self._main_frame.pack(fill=tk.BOTH, expand=True)

        # 타이틀 바
        self._title_bar = TitleBar(
            self._main_frame,
            panel_color=panel,
            text_color=text,
            highlight_color=highlight,
            on_close=self._on_close,
            on_minimize=self._toggle_minimize,
            on_toggle_sync=self._toggle_sync_panel,
            on_toggle_search=self._toggle_search_panel,
            on_toggle_settings=self._toggle_settings_panel,
        )
        self._title_bar.pack(fill=tk.X)

        # 컨텐츠 영역 (패널 스택용)
        self._content_frame = tk.Frame(self._main_frame, bg=bg)
        self._content_frame.pack(fill=tk.BOTH, expand=True)
        self._content_frame.grid_rowconfigure(0, weight=1)
        self._content_frame.grid_columnconfigure(0, weight=1)

        # 가사 패널 (Base Layer)
        self._lyrics_panel = LyricsPanel(
            self._content_frame,
            bg_color=bg,
            text_color=text,
            highlight_color=highlight,
            font_family=font_family,
            font_size=font_size,
            show_translations=self._settings.get("show_translations", True),
        )
        self._lyrics_panel.grid(row=0, column=0, sticky="nsew")

        # 싱크 패널 (Overlay)
        self._sync_panel = SyncPanel(
            self._content_frame,
            bg_color=bg,
            panel_color=panel,
            text_color=text,
            highlight_color=highlight,
            on_sync_change=self._on_sync_change_handler,
        )
        # 싱크 패널은 하단에만 표시하거나 전체를 덮을 수 있음.
        # 여기서는 하단 정렬을 위해 별도 처리 대신, 전체 오버레이 후 내부에서 정렬하거나
        # grid sticky를 s로 설정.
        # 기존대로 하단 오버레이 느낌을 주려면 grid 안에 place를 쓰거나
        # 전체 그리드를 쓰되 내부에서 하단 배치.
        # 일관성을 위해 전체 그리드 스택 사용 (배경 투명 처리 필요할 수 있음 -> SyncPanel 자체 배경이 투명이 아니면 가려짐)
        # SyncPanel 디자인 상 전체를 덮으면 가사가 안 보임.
        # 따라서 SyncPanel은 grid 대신 place로 하단 배치 유지 (content_frame 기준)
        self._sync_panel.place(relx=0, rely=0.8, relwidth=1.0, relheight=0.2)
        self._sync_panel.place_forget() # 초기 숨김

        # 검색 패널 (Overlay)
        self._search_panel = SearchPanel(
            self._content_frame,
            bg_color=bg,
            panel_color=panel,
            text_color=text,
            highlight_color=highlight,
            on_search=self._on_search_handler,
            on_apply=self._on_apply_lyrics_handler,
        )
        self._search_panel.grid(row=0, column=0, sticky="nsew")
        self._search_panel.grid_remove() # 초기 숨김

        # 설정 패널 (Overlay)
        self._settings_panel = SettingsPanel(
            self._content_frame,
            bg_color=self._settings.get("bg_color"),
            panel_color="#16213e", # 패널 색상은 고정 (또는 설정에서 가져옴)
            text_color=self._settings.get("text_color"),
            highlight_color=self._settings.get("highlight_color"),
            opacity=self._settings.get("opacity"),
            font_family=self._settings.get("font_family"),
            font_size=self._settings.get("font_size"),
            show_translations=self._settings.get("show_translations", True),
            on_save=self._on_settings_save,
            on_preview=self._on_settings_preview, # 미리보기 연결
        )
        self._settings_panel.grid(row=0, column=0, sticky="nsew")
        self._settings_panel.grid_remove() # 초기 숨김

        # 리사이즈 그립 (우측 하단)
        # 리사이즈 그립 생성 (가장 나중에 생성하여 최상단에 올림)
        self._resize_grip = ResizeGrip(
            self._main_frame,
            bg=self._settings.get("bg_color") or "#1a1a2e", # 배경색과 동일하게
            on_resize=None # 윈도우 크기 조절은 내부에서 처리됨
        )
        self._resize_grip.place(relx=1.0, rely=1.0, anchor="se")
        self._resize_grip.lift() # 최상단 보장

        # 패널 표시 상태
        self._sync_visible = False
        self._search_visible = False
        self._settings_visible = False

    # ── 패널 토글 ─────────────────────────────────────────────────────────────

    def _toggle_sync_panel(self) -> None:
        self._sync_visible = not self._sync_visible
        if self._sync_visible:
            # 하단 20% 오버레이
            self._sync_panel.place(relx=0, rely=0.8, relwidth=1.0, relheight=0.2)
            self._sync_panel.lift()
        else:
            self._sync_panel.place_forget()

    def _toggle_search_panel(self) -> None:
        self._search_visible = not self._search_visible
        if self._search_visible:
            self._search_panel.grid()
            self._search_panel.lift()
        else:
            self._search_panel.grid_remove()

    def _toggle_settings_panel(self) -> None:
        self._settings_visible = not self._settings_visible
        if self._settings_visible:
            self._settings_panel.grid()
            self._settings_panel.lift()
            # Grip도 같이 올려줘야 설정창 위에서 크기조절 가능? 
            # 아니면 설정창에서는 크기조절 막기? -> 막는게 나음 (설정창 스크롤바랑 겹침)
            # 여기서는 ResizeGrip을 숨기거나 맨 위로 올림.
            # 설정창이 꽉 차있을 때 Grip이 가리면 안보임.
            # 설정창 작업 중에는 Grip 숨기는 게 깔끔함.
            self._resize_grip.place_forget()
        else:
            self._settings_panel.grid_remove()
            if not self._minimized:
                self._resize_grip.place(relx=1.0, rely=1.0, anchor="se")
                self._resize_grip.lift()

    # ── 최소화 ────────────────────────────────────────────────────────────────

    # ── 최소화 ────────────────────────────────────────────────────────────────
    
    def _toggle_minimize(self) -> None:
        self._minimized = not self._minimized
        if self._minimized:
            self._last_geometry = self._root.geometry() # 현재 크기 저장
            self._lyrics_panel.pack_forget()
            self._resize_grip.place_forget() # 그립 숨김
            # 높이 40으로 축소 (너비는 유지)
            w = self._root.winfo_width()
            self._root.geometry(f"{w}x40")
        else:
            self._lyrics_panel.pack(fill=tk.BOTH, expand=True)
            self._resize_grip.place(relx=1.0, rely=1.0, anchor="se") # 그립 표시
            # 크기 복원
            if hasattr(self, '_last_geometry'):
                 self._root.geometry(self._last_geometry)
            else:
                 self._root.geometry(f"{DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT}")

    # ── 핸들러 ────────────────────────────────────────────────────────────────

    def _on_sync_change_handler(self, offset_ms: int) -> None:
        if self._on_sync_change:
            self._on_sync_change(offset_ms)

    def _on_search_handler(self, title: str, artist: str) -> None:
        if self._on_search:
            self._on_search(title, artist)

    def _on_apply_lyrics_handler(self, lrc_text: str, source: str) -> None:
        if self._on_apply_lyrics:
            self._on_apply_lyrics(lrc_text, source)

    def _on_settings_save(self, settings_data: dict) -> None:
        """설정 저장 핸들러"""
        self._settings.update(settings_data)
        
        # UI 즉시 적용
        self._apply_settings(settings_data)

    def _on_settings_preview(self, settings_data: dict) -> None:
        """설정 미리보기 핸들러"""
        self._apply_settings(settings_data)

    def _on_close(self) -> None:
        """창 닫기"""
        self._running = False
        if self._on_close_callback:
            self._on_close_callback()

    # ── 공개 API (ViewModel이 호출) ───────────────────────────────────────────

    def set_on_close(self, callback: Callable[[], None]) -> None:
        self._on_close_callback = callback

    def set_on_sync_change(self, callback: Callable[[int], None]) -> None:
        self._on_sync_change = callback

    def set_on_search(self, callback: Callable[[str, str], None]) -> None:
        self._on_search = callback

    def set_on_apply_lyrics(self, callback: Callable[[str, str], None]) -> None:
        self._on_apply_lyrics = callback

    def update_lyrics(self, lines: list[LyricDisplayLine]) -> None:
        """가사 업데이트 (스레드 안전)"""
        self._cmd_queue.put(("update_lyrics", lines))

    def update_track_info(self, title: str, artist: str) -> None:
        """트랙 정보 업데이트 (스레드 안전)"""
        self._cmd_queue.put(("update_track", title, artist))

    def show_loading(self, message: str) -> None:
        """로딩 메시지 표시 (스레드 안전)"""
        self._cmd_queue.put(("show_loading", message))

    def show_search_results(self, results: list) -> None:
        """검색 결과 표시 (스레드 안전)"""
        self._cmd_queue.put(("show_search_results", results))

    def set_search_suggestion(self, title: str, artist: str) -> None:
        """검색 제안 설정 (스레드 안전)"""
        self._cmd_queue.put(("set_search_suggestion", title, artist))

    def reset_sync(self) -> None:
        """싱크 초기화 (스레드 안전)"""
        self._cmd_queue.put(("reset_sync",))

    def center(self) -> None:
        """창을 화면 중앙으로 이동"""
        self._cmd_queue.put(("center",))

    def show(self) -> None:
        """창 표시"""
        self._cmd_queue.put(("show",))

    def schedule(self, ms: int, fn: Callable) -> None:
        """tkinter after() 래퍼"""
        if self._root:
            self._root.after(ms, fn)

    def is_alive(self) -> bool:
        return self._running

    def is_minimized(self) -> bool:
        return self._minimized

    # ── 명령 큐 처리 ──────────────────────────────────────────────────────────

    def _process_queue(self) -> None:
        """큐에 쌓인 UI 명령 처리 (메인 스레드에서 실행)"""
        try:
            while not self._cmd_queue.empty():
                cmd = self._cmd_queue.get_nowait()
                self._dispatch_command(cmd)
        except Exception as e:
            print(f"[UI] 큐 처리 오류: {e}")
        finally:
            if self._running and self._root:
                self._root.after(50, self._process_queue)

    def _dispatch_command(self, cmd: tuple) -> None:
        """명령 디스패치"""
        action = cmd[0]
        if action == "update_lyrics":
            self._lyrics_panel.update_lyrics(cmd[1])
        elif action == "update_track":
            self._title_bar.update_track_info(cmd[1], cmd[2])
        elif action == "show_loading":
            self._lyrics_panel.show_status(cmd[1])
        elif action == "show_search_results":
            self._search_panel.show_results(cmd[1])
        elif action == "set_search_suggestion":
            self._search_panel.set_suggestion(cmd[1], cmd[2])
        elif action == "reset_sync":
            self._sync_panel.reset()
        elif action == "center":
            self._do_center()
        elif action == "show":
            self._root.deiconify()
            self._root.lift()
        elif action == "apply_settings":
            self._apply_settings(cmd[1])

    def _do_center(self) -> None:
        """창을 화면 중앙으로 이동"""
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        x = (sw - DEFAULT_WINDOW_WIDTH) // 2
        y = (sh - DEFAULT_WINDOW_HEIGHT) // 2
        self._root.geometry(f"+{x}+{y}")

    # ── 설정 적용 ─────────────────────────────────────────────────────────────

    def _apply_settings(self, settings: dict) -> None:
        """설정값을 모든 UI 요소에 적용"""
        bg = settings.get("bg_color") or settings.get("background_color") or "#1a1a2e"
        text = settings.get("text_color") or settings.get("text_color") or "#e0e0e0"
        highlight = settings.get("highlight_color") or settings.get("highlight_color") or "#e94560"
        
        # 패널 컬러는 bg 기반으로 자동 계산
        panel = calculate_panel_color(bg)
        
        opacity = float(settings.get("opacity", 0.9))
        font_family = settings.get("font_family", "Malgun Gothic")
        font_size = int(settings.get("font_size", 11))
        show_trans = settings.get("show_translations", True)

        if self._root:
            self._root.wm_attributes("-alpha", opacity)

        apply_theme_recursive(self._main_frame, bg, panel, text, highlight)

        self._lyrics_panel.set_colors(bg, text, highlight)
        self._lyrics_panel.set_font(font_family, font_size)
        self._lyrics_panel.set_show_translations(show_trans)
        self._settings_panel.sync_from_settings(settings)

    def on_settings_changed(self, settings: dict) -> None:
        """설정 변경 시 호출 (SettingsManager 옵저버)"""
        self._cmd_queue.put(("apply_settings", settings))

    # ── 클릭 투과 ─────────────────────────────────────────────────────────────

    def set_click_through(self, enabled: bool) -> None:
        """클릭 투과 모드 설정"""
        self._click_through = enabled
        try:
            hwnd = self._root.winfo_id()
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if enabled:
                style |= win32con.WS_EX_TRANSPARENT | win32con.WS_EX_LAYERED
            else:
                style &= ~win32con.WS_EX_TRANSPARENT
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)
        except Exception as e:
            print(f"[UI] 클릭 투과 설정 오류: {e}")

    # ── 메인 루프 ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        """tkinter 메인 루프 실행"""
        self._root.mainloop()

    def quit(self) -> None:
        """앱 종료"""
        self._running = False
        if self._root:
            self._root.quit()
            self._root.destroy()
