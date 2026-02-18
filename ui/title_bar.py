"""
타이틀 바 컴포넌트.
창 드래그, 최소화, 닫기, 싱크/검색 패널 토글 버튼을 포함합니다.
"""

import tkinter as tk
from typing import Callable, Optional


class TitleBar(tk.Frame):
    """오버레이 창 타이틀 바"""

    def __init__(
        self,
        parent: tk.Widget,
        panel_color: str = "#16213e",
        text_color: str = "#e0e0e0",
        highlight_color: str = "#e94560",
        on_close: Optional[Callable[[], None]] = None,
        on_minimize: Optional[Callable[[], None]] = None,
        on_toggle_sync: Optional[Callable[[], None]] = None,
        on_toggle_search: Optional[Callable[[], None]] = None,
        on_toggle_settings: Optional[Callable[[], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, bg=panel_color, height=40, **kwargs)

        self._panel_color = panel_color
        self._text_color = text_color
        self._highlight_color = highlight_color

        self._on_close = on_close
        self._on_minimize = on_minimize
        self._on_toggle_sync = on_toggle_sync
        self._on_toggle_search = on_toggle_search
        self._on_toggle_settings = on_toggle_settings

        # 드래그 상태
        self._drag_start_x: int = 0
        self._drag_start_y: int = 0

        self._create_widgets()
        self._bind_drag()

    def _create_widgets(self) -> None:
        """위젯 생성"""
        # 우측: 버튼들 (먼저 배치하여 공간 확보)
        right_frame = tk.Frame(self, bg=self._panel_color)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=4)

        # 좌측: 앱 아이콘 + 트랙 정보
        left_frame = tk.Frame(self, bg=self._panel_color)
        left_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)

        tk.Label(
            left_frame,
            text="🎵",
            bg=self._panel_color,
            fg=self._highlight_color,
            font=("", 14),
        ).pack(side=tk.LEFT)

        self._track_label = tk.Label(
            left_frame,
            text="YouTube Music",
            bg=self._panel_color,
            fg=self._text_color,
            font=("Malgun Gothic", 9),
        )
        self._track_label.pack(side=tk.LEFT, padx=4)

        btn_cfg = dict(bg=self._panel_color, fg=self._text_color, relief=tk.FLAT, padx=6, pady=4)

        # 설정 버튼
        btn_settings = tk.Label(right_frame, text="⚙", **btn_cfg)
        btn_settings.pack(side=tk.LEFT)
        btn_settings.bind("<Button-1>", lambda e: self._on_toggle_settings())
        
        # 검색 버튼
        btn_search = tk.Label(right_frame, text="🔍", **btn_cfg)
        btn_search.pack(side=tk.LEFT)
        btn_search.bind("<Button-1>", lambda e: self._on_toggle_search())

        # 싱크 버튼
        btn_sync = tk.Label(right_frame, text="⏱", **btn_cfg)
        btn_sync.pack(side=tk.LEFT)
        btn_sync.bind("<Button-1>", lambda e: self._on_toggle_sync())

        # 최소화 버튼
        btn_min = tk.Label(right_frame, text="—", **btn_cfg)
        btn_min.pack(side=tk.LEFT)
        btn_min.bind("<Button-1>", lambda e: self._on_minimize())

        # 닫기 버튼
        btn_close = tk.Label(
            right_frame, text="✕",
            bg=self._panel_color, fg=self._highlight_color,
            padx=6, pady=4
        )
        btn_close.pack(side=tk.LEFT)
        btn_close.bind("<Button-1>", lambda e: self._on_close())

    def _bind_drag(self) -> None:
        """창 드래그 바인딩"""
        self.bind("<ButtonPress-1>", self._on_drag_start)
        self.bind("<B1-Motion>", self._on_drag_motion)
        self._track_label.bind("<ButtonPress-1>", self._on_drag_start)
        self._track_label.bind("<B1-Motion>", self._on_drag_motion)

    def _on_drag_start(self, event: tk.Event) -> None:
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root

    def _on_drag_motion(self, event: tk.Event) -> None:
        root = self.winfo_toplevel()
        dx = event.x_root - self._drag_start_x
        dy = event.y_root - self._drag_start_y
        new_x = root.winfo_x() + dx
        new_y = root.winfo_y() + dy
        root.geometry(f"+{new_x}+{new_y}")
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root

    def update_track_info(self, title: str, artist: str) -> None:
        """트랙 정보 업데이트"""
        if title:
            # 텍스트는 라벨 크기에 맞춰 자동 클리핑됨
            # 필요 시 툴팁 추가 고려 가능
            display = f"{title} - {artist}" if artist else title
            self._track_label.config(text=display)
            self._track_label.config(text=display)
        else:
            self._track_label.config(text="YouTube Music")
