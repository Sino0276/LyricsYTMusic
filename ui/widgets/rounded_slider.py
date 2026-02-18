"""
커스텀 슬라이더 위젯.
overlay_ui.py에서 분리된 RoundedSlider 클래스입니다.
"""

import tkinter as tk
from typing import Callable, Optional


class RoundedSlider(tk.Canvas):
    """
    둥근 트랙과 원형 핸들을 가진 커스텀 슬라이더 위젯.
    tk.Scale 대신 사용하여 더 세련된 UI를 제공합니다.
    """

    def __init__(
        self,
        parent: tk.Widget,
        from_: float = 0.0,
        to: float = 100.0,
        value: float = 0.0,
        width: int = 200,
        height: int = 20,
        bg_color: str = "#1a1a2e",
        track_color: str = "#3a3a5a",
        fill_color: str = "#e94560",
        handle_color: str = "#ffffff",
        command: Optional[Callable[[float], None]] = None,
    ) -> None:
        super().__init__(parent, width=width, height=height, bg=bg_color, highlightthickness=0)

        self._from = from_
        self._to = to
        self._value = value
        self._command = command
        self._dragging = False

        # 색상
        self._bg_color = bg_color
        self._track_color = track_color
        self._fill_color = fill_color
        self._handle_color = handle_color

        # 레이아웃 상수
        self._padding = 10
        self._track_height = 4
        self._handle_radius = 7

        self._draw()
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Map>", self._on_map)

    def _on_map(self, event):
        """위젯이 화면에 매핑될 때 다시 그리기"""
        self._draw()

    def _get_track_x(self) -> tuple[int, int]:
        """트랙 시작/끝 X 좌표 반환"""
        return self._padding, self.winfo_width() - self._padding

    def _value_to_x(self, value: float) -> int:
        """값을 X 좌표로 변환"""
        x_start, x_end = self._get_track_x()
        ratio = (value - self._from) / (self._to - self._from) if self._to != self._from else 0
        return int(x_start + ratio * (x_end - x_start))

    def _x_to_value(self, x: int) -> float:
        """X 좌표를 값으로 변환"""
        x_start, x_end = self._get_track_x()
        ratio = (x - x_start) / (x_end - x_start) if x_end != x_start else 0
        ratio = max(0.0, min(1.0, ratio))
        return self._from + ratio * (self._to - self._from)

    def _draw(self) -> None:
        """슬라이더 전체 다시 그리기"""
        self.delete("all")

        width = self.winfo_width()
        height = self.winfo_height()
        
        # 초기 렌더링 시 크기가 잡히지 않았으면 설정된 크기 사용
        if width <= 1: width = int(self["width"])
        if height <= 1: height = int(self["height"])

        cx = width // 2
        cy = height // 2

        x_start, x_end = self._padding, width - self._padding
        handle_x = self._value_to_x(self._value)

        # 배경 트랙
        self.create_rounded_rect(
            x_start, cy - self._track_height // 2,
            x_end, cy + self._track_height // 2,
            radius=self._track_height // 2,
            fill=self._track_color,
            outline="",
        )

        # 채워진 트랙 (왼쪽)
        if handle_x > x_start:
            self.create_rounded_rect(
                x_start, cy - self._track_height // 2,
                handle_x, cy + self._track_height // 2,
                radius=self._track_height // 2,
                fill=self._fill_color,
                outline="",
            )

        # 핸들 (원형)
        r = self._handle_radius
        self.create_oval(
            handle_x - r, cy - r,
            handle_x + r, cy + r,
            fill=self._handle_color,
            outline=self._fill_color,
            width=2,
        )

    def create_rounded_rect(
        self,
        x1: int, y1: int, x2: int, y2: int,
        radius: int = 5,
        **kwargs,
    ) -> int:
        """둥근 모서리 사각형 그리기"""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _on_press(self, event: tk.Event) -> None:
        self._dragging = True
        self._update_value(event.x)

    def _on_drag(self, event: tk.Event) -> None:
        if self._dragging:
            self._update_value(event.x)

    def _on_release(self, event: tk.Event) -> None:
        self._dragging = False

    def _update_value(self, x: int) -> None:
        """마우스 위치로 값 업데이트"""
        new_value = self._x_to_value(x)
        self._value = new_value
        self._draw()
        if self._command:
            self._command(new_value)

    # ── 공개 API ──────────────────────────────────────────────────────────────

    def get(self) -> float:
        """현재 값 반환"""
        return self._value

    def set(self, value: float) -> None:
        """값 설정 (콜백 호출 없음)"""
        self._value = max(self._from, min(self._to, value))
        self._draw()

    def set_colors(
        self,
        bg_color: Optional[str] = None,
        track_color: Optional[str] = None,
        fill_color: Optional[str] = None,
        handle_color: Optional[str] = None,
    ) -> None:
        """색상 업데이트"""
        if bg_color:
            self._bg_color = bg_color
            self.config(bg=bg_color)
        if track_color:
            self._track_color = track_color
        if fill_color:
            self._fill_color = fill_color
        if handle_color:
            self._handle_color = handle_color
        self._draw()

    def configure_range(self, from_: float, to: float) -> None:
        """범위 재설정"""
        self._from = from_
        self._to = to
        self._value = max(from_, min(to, self._value))
        self._draw()
