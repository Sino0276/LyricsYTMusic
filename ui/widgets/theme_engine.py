"""
테마 엔진 - 색상 계산 및 재귀적 테마 적용.
overlay_ui.py에서 분리된 테마 관련 유틸리티 함수들입니다.
"""

import colorsys
import tkinter as tk
from typing import Optional


# ── 색상 유틸리티 ─────────────────────────────────────────────────────────────

def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """HEX 색상 문자열을 RGB 튜플로 변환"""
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """RGB 값을 HEX 색상 문자열로 변환"""
    return f"#{r:02x}{g:02x}{b:02x}"


def adjust_color_brightness(hex_color: str, factor: float) -> str:
    """
    색상의 밝기를 조절합니다.

    Args:
        hex_color: HEX 색상 문자열 (#rrggbb)
        factor: 밝기 배율 (0.0 ~ 2.0, 1.0 = 변경 없음)

    Returns:
        조절된 HEX 색상 문자열
    """
    r, g, b = hex_to_rgb(hex_color)
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    new_l = max(0.0, min(1.0, l * factor))
    new_r, new_g, new_b = colorsys.hls_to_rgb(h, new_l, s)
    return rgb_to_hex(int(new_r * 255), int(new_g * 255), int(new_b * 255))


def calculate_panel_color(bg_color: str) -> str:
    """
    배경색을 기반으로 패널 배경색 계산.
    매우 어두운 배경에서도 구분이 가능하도록 최소 밝기를 보장합니다.
    """
    panel_color = adjust_color_brightness(bg_color, 0.85)
    r, g, b = hex_to_rgb(panel_color)

    # 최소 밝기 보장 (너무 어두우면 약간 밝게)
    if r < 20 and g < 20 and b < 20:
        panel_color = adjust_color_brightness(bg_color, 1.4)

    return panel_color


# ── 테마 프리셋 ───────────────────────────────────────────────────────────────

THEME_PRESETS: dict[str, dict[str, str]] = {
    "Dark Mode": {
        "bg": "#1a1a2e",
        "panel": "#16213e",
        "text": "#e0e0e0",
        "highlight": "#e94560",
    },
    "Light Mode": {
        "bg": "#f0f2f5",
        "panel": "#ffffff",
        "text": "#333333",
        "highlight": "#1877f2",
    },
    "OLED Black": {
        "bg": "#000000",
        "panel": "#000000",
        "text": "#ffffff",
        "highlight": "#1ed760",
    },
    "Ocean": {
        "bg": "#0d1b2a",
        "panel": "#1b263b",
        "text": "#e0e1dd",
        "highlight": "#00bcd4",
    },
    "Midnight": {
        "bg": "#101010",
        "panel": "#202020",
        "text": "#ffffff",
        "highlight": "#ffd700",
    },
}


# ── 재귀적 테마 적용 ──────────────────────────────────────────────────────────

def apply_theme_recursive(
    widget: tk.Widget,
    bg_color: str,
    panel_color: str,
    text_color: str,
    highlight_color: str,
    depth: int = 0,
) -> None:
    """
    위젯과 모든 자식 위젯에 재귀적으로 테마 색상을 적용합니다.

    Args:
        widget: 테마를 적용할 루트 위젯
        bg_color: 배경색
        panel_color: 패널 배경색 (배경보다 약간 밝음)
        text_color: 텍스트 색상
        highlight_color: 강조 색상
        depth: 재귀 깊이 (내부 사용)
    """
    try:
        widget_class = widget.winfo_class()

        if widget_class in ("Frame", "Toplevel"):
            widget.config(bg=bg_color)
        elif widget_class == "Label":
            widget.config(bg=bg_color, fg=text_color)
        elif widget_class == "Button":
            widget.config(bg=panel_color, fg=text_color, activebackground=highlight_color)
        elif widget_class == "Entry":
            widget.config(bg=panel_color, fg=text_color, insertbackground=text_color)
        elif widget_class == "Listbox":
            widget.config(bg=panel_color, fg=text_color, selectbackground=highlight_color)
        elif widget_class == "Canvas":
            widget.config(bg=bg_color)
        elif widget_class == "Scrollbar":
            widget.config(bg=panel_color, troughcolor=bg_color)
        elif widget_class == "Scale":
            widget.config(bg=bg_color, fg=text_color, troughcolor=panel_color)
        elif widget_class == "Checkbutton":
            widget.config(bg=bg_color, fg=text_color, selectcolor=panel_color)
        elif widget_class == "Combobox":
            pass  # ttk 위젯은 별도 스타일 적용 필요
    except tk.TclError:
        pass

    for child in widget.winfo_children():
        apply_theme_recursive(child, bg_color, panel_color, text_color, highlight_color, depth + 1)
