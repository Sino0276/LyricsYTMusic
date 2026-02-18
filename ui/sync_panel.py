"""
싱크 조절 패널.
가사 동기화 오프셋을 슬라이더로 조절합니다.
"""

import tkinter as tk
from typing import Callable, Optional

from ui.widgets.rounded_slider import RoundedSlider


class SyncPanel(tk.Frame):
    """싱크 조절 패널 (가사 타이밍 오프셋 조절)"""

    # 오프셋 범위 (ms)
    _MIN_OFFSET_MS = -10_000
    _MAX_OFFSET_MS = 10_000

    def __init__(
        self,
        parent: tk.Widget,
        bg_color: str = "#1a1a2e",
        panel_color: str = "#16213e",
        text_color: str = "#e0e0e0",
        highlight_color: str = "#e94560",
        on_sync_change: Optional[Callable[[int], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, bg=panel_color, **kwargs)

        self._bg_color = bg_color
        self._panel_color = panel_color
        self._text_color = text_color
        self._highlight_color = highlight_color
        self._on_sync_change = on_sync_change
        self._offset_ms: int = 0

        self._create_widgets()

    def _create_widgets(self) -> None:
        """위젯 생성"""
        # 헤더
        header_frame = tk.Frame(self, bg=self._panel_color)
        header_frame.pack(fill=tk.X, padx=10, pady=(6, 2))

        tk.Label(
            header_frame,
            text="⏱ 싱크 조절",
            bg=self._panel_color,
            fg=self._text_color,
            font=("Malgun Gothic", 10, "bold"),
        ).pack(side=tk.LEFT)

        self._offset_label = tk.Label(
            header_frame,
            text="0ms",
            bg=self._panel_color,
            fg=self._highlight_color,
            font=("Malgun Gothic", 10),
        )
        self._offset_label.pack(side=tk.RIGHT)

        # 슬라이더
        self._slider = RoundedSlider(
            self,
            from_=self._MIN_OFFSET_MS,
            to=self._MAX_OFFSET_MS,
            value=0,
            bg_color=self._panel_color,
            fill_color=self._highlight_color,
            command=self._on_slider_change,
        )
        self._slider.pack(fill=tk.X, padx=10, pady=4)

        # 버튼 행
        btn_frame = tk.Frame(self, bg=self._panel_color)
        btn_frame.pack(fill=tk.X, padx=10, pady=(4, 8))

        tk.Button(
            btn_frame,
            text="◀◀ 1s",
            bg=self._panel_color,
            fg=self._text_color,
            relief=tk.FLAT,
            padx=4,
            command=lambda: self._adjust(-1000),
        ).pack(side=tk.LEFT)

        tk.Button(
            btn_frame,
            text="◀ 0.5s",
            bg=self._panel_color,
            fg=self._text_color,
            relief=tk.FLAT,
            padx=4,
            command=lambda: self._adjust(-500),
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            btn_frame,
            text="↺",
            bg=self._panel_color,
            fg=self._highlight_color,
            relief=tk.FLAT,
            padx=4,
            command=self.reset,
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            btn_frame,
            text="0.5s ▶",
            bg=self._panel_color,
            fg=self._text_color,
            relief=tk.FLAT,
            padx=4,
            command=lambda: self._adjust(500),
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            btn_frame,
            text="1s ▶▶",
            bg=self._panel_color,
            fg=self._text_color,
            relief=tk.FLAT,
            padx=4,
            command=lambda: self._adjust(1000),
        ).pack(side=tk.LEFT)

    def _on_slider_change(self, value: float) -> None:
        """슬라이더 변경 핸들러"""
        self._offset_ms = int(value)
        self._update_label()
        if self._on_sync_change:
            self._on_sync_change(self._offset_ms)

    def _adjust(self, delta_ms: int) -> None:
        """오프셋 조절 (상대값)"""
        new_offset = max(self._MIN_OFFSET_MS, min(self._MAX_OFFSET_MS, self._offset_ms + delta_ms))
        self.set_offset(new_offset)
        if self._on_sync_change:
            self._on_sync_change(self._offset_ms)

    def _update_label(self) -> None:
        """오프셋 레이블 업데이트"""
        sign = "+" if self._offset_ms > 0 else ""
        self._offset_label.config(text=f"{sign}{self._offset_ms}ms")

    def reset(self) -> None:
        """오프셋 초기화"""
        self.set_offset(0)
        if self._on_sync_change:
            self._on_sync_change(0)

    def set_offset(self, offset_ms: int) -> None:
        """오프셋 설정 (외부에서 호출)"""
        self._offset_ms = offset_ms
        self._slider.set(offset_ms)
        self._update_label()

    def get_offset(self) -> int:
        """현재 오프셋 반환"""
        return self._offset_ms
