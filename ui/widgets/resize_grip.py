import tkinter as tk
from typing import Callable, Optional

class ResizeGrip(tk.Frame):
    """우측 하단 크기 조절 핸들"""

    def __init__(self, parent: tk.Widget, bg: str, on_resize: Callable[[tk.Event], None], **kwargs):
        super().__init__(parent, bg=bg, cursor="size_nw_se", width=15, height=15, **kwargs)
        self.pack_propagate(False)
        self._on_resize = on_resize
        
        # 시각적 힌트를 위한 캔버스
        self._canvas = tk.Canvas(self, bg=bg,  highlightthickness=0, width=15, height=15)
        self._canvas.pack(fill="both", expand=True)
        self._draw_grip()
        
        self._bind_events()

    def _draw_grip(self):
        """그립 핸들 그리기 (:: 모양)"""
        w, h = 15, 15
        color = "#888888" # 은은한 회색
        
        # 우측 하단 대각선 점 패턴
        # (12, 12), (9, 12), (12, 9), (6, 12), (9, 9), (12, 6)
        points = [
            (12, 12), (8, 12), (12, 8),
            (4, 12), (8, 8), (12, 4) 
        ]
        
        for x, y in points:
             self._canvas.create_rectangle(x, y, x+2, y+2, fill=color, outline="")

    def _bind_events(self):
        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_motion)

    def _on_press(self, event):
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._win_start_w = self.winfo_toplevel().winfo_width()
        self._win_start_h = self.winfo_toplevel().winfo_height()

    def _on_motion(self, event):
        dx = event.x_root - self._drag_start_x
        dy = event.y_root - self._drag_start_y
        
        new_w = max(300, self._win_start_w + dx)
        new_h = max(150, self._win_start_h + dy)
        
        self.winfo_toplevel().geometry(f"{new_w}x{new_h}")
        if self._on_resize:
            self._on_resize(event)
