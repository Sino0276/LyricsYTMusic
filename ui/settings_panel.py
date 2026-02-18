"""
설정 패널.
색상, 폰트, 투명도 등 앱 외관을 커스터마이징하는 패널입니다.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from ui.widgets.rounded_slider import RoundedSlider
from ui.widgets.theme_engine import THEME_PRESETS, adjust_color_brightness


class SettingsPanel(tk.Frame):
    """앱 외관 설정 패널"""

    # 사용 가능한 폰트 목록
    _FONT_FAMILIES = [
        "Malgun Gothic", "나눔고딕", "나눔바른고딕", "맑은 고딕",
        "Arial", "Segoe UI", "Consolas",
    ]

    # 폰트 크기 범위
    _MIN_FONT_SIZE = 8
    _MAX_FONT_SIZE = 24

    def __init__(
        self,
        parent: tk.Widget,
        bg_color: str = "#1a1a2e",
        panel_color: str = "#16213e",
        text_color: str = "#e0e0e0",
        highlight_color: str = "#e94560",
        opacity: float = 0.9,
        font_family: str = "Malgun Gothic",
        font_size: int = 11,
        show_translations: bool = True,
        on_save: Optional[Callable[[dict], None]] = None,
        on_preview: Optional[Callable[[dict], None]] = None, # 미리보기 콜백 추가
        **kwargs,
    ) -> None:
        super().__init__(
            parent, 
            bg=panel_color, 
            highlightthickness=1, 
            highlightbackground=highlight_color,
            **kwargs
        )

        self._bg_color = bg_color or "#1a1a2e"
        self._panel_color = panel_color or "#16213e"
        self._text_color = text_color or "#e0e0e0"
        self._highlight_color = highlight_color or "#e94560"
        self._opacity = opacity
        self._font_family = font_family
        self._font_size = font_size
        self._show_translations = show_translations
        self._on_save = on_save
        self._on_preview = on_preview

        # 임시 색상 변수 (저장 전 미리보기용)
        self._temp_bg = bg_color
        self._temp_text = text_color
        self._temp_highlight = highlight_color

        self._create_scrollable_area()
        self._create_widgets()

    def _create_scrollable_area(self) -> None:
        """스크롤 가능한 영역 생성 (스크롤바 시각적 제거)"""
        self._canvas = tk.Canvas(
            self,
            bg=self._panel_color,
            highlightthickness=0,
        )
        # 스크롤바 위젯 제거 (마우스 휠로만 조작)
        
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._scrollable_frame = tk.Frame(self._canvas, bg=self._panel_color)
        
        # 캔버스 윈도우 생성
        self._canvas_window = self._canvas.create_window(
            (0, 0),
            window=self._scrollable_frame,
            anchor="nw",
        )

        self._scrollable_frame.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # 마우스 휠 바인딩
        self._bind_mouse_wheel(self._canvas)
        self._bind_mouse_wheel(self._scrollable_frame)

    def _on_canvas_configure(self, event):
        """캔버스 크기 변경 시 스크롤 영역 및 내부 프레임 너비 조정"""
        canvas_width = event.width
        self._canvas.itemconfig(self._canvas_window, width=canvas_width)
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _bind_mouse_wheel(self, widget):
        widget.bind("<Enter>", lambda e: self.master.bind_all("<MouseWheel>", self._on_mouse_wheel))
        widget.bind("<Leave>", lambda e: self.master.unbind_all("<MouseWheel>"))

    def _on_mouse_wheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _create_widgets(self) -> None:
        """위젯 생성 (scrollable_frame 안에 배치)"""
        parent = self._scrollable_frame
        
        # 헤더
        tk.Label(
            parent,
            text="⚙ 설정",
            bg=self._panel_color,
            fg=self._text_color,
            font=("Malgun Gothic", 10, "bold"),
        ).pack(anchor="w", padx=10, pady=(6, 2))

        # ── 테마 프리셋 ────────────────────────────────────────────────────────
        self._add_section("테마 프리셋", parent)
        preset_frame = tk.Frame(parent, bg=self._panel_color)
        preset_frame.pack(fill=tk.X, padx=10, pady=2)

        for preset_name in THEME_PRESETS:
            btn = tk.Button(
                preset_frame,
                text=preset_name,
                bg=self._panel_color,
                fg=self._text_color,
                relief=tk.FLAT,
                padx=6,
                command=lambda n=preset_name: self._apply_preset(n),
            )
            btn.pack(side=tk.LEFT, padx=2)

        # ── 색상 설정 ──────────────────────────────────────────────────────────
        self._add_section("색상", parent)

        self._bg_entry = self._add_color_row("배경색", self._bg_color, parent)
        self._text_entry = self._add_color_row("텍스트색", self._text_color, parent)
        self._highlight_entry = self._add_color_row("강조색", self._highlight_color, parent)

        # ── 투명도 ─────────────────────────────────────────────────────────────
        self._add_section("투명도", parent)
        opacity_frame = tk.Frame(parent, bg=self._panel_color)
        opacity_frame.pack(fill=tk.X, padx=10, pady=1)

        self._opacity_slider = RoundedSlider(
            opacity_frame,
            from_=0.1,
            to=1.0,
            value=self._opacity,
            bg_color=self._panel_color,
            fill_color=self._highlight_color,
            command=self._on_opacity_change,
        )
        self._opacity_slider.pack(fill=tk.X, expand=True, side=tk.LEFT)

        self._opacity_label = tk.Label(
            opacity_frame,
            text=f"{int(self._opacity * 100)}%",
            bg=self._panel_color,
            fg=self._text_color,
            width=5,
        )
        self._opacity_label.pack(side=tk.LEFT, padx=4)

        # ── 폰트 ───────────────────────────────────────────────────────────────
        self._add_section("폰트", parent)
        font_frame = tk.Frame(parent, bg=self._panel_color)
        font_frame.pack(fill=tk.X, padx=10, pady=2)

        self._font_family_var = tk.StringVar(value=self._font_family)
        self._font_combo = ttk.Combobox(
            font_frame,
            textvariable=self._font_family_var,
            values=self._FONT_FAMILIES,
            state="readonly",
            width=18,
        )
        self._font_combo.pack(side=tk.LEFT)
        self._font_combo.bind("<<ComboboxSelected>>", self._trigger_preview)

        tk.Label(font_frame, text="크기:", bg=self._panel_color, fg=self._text_color).pack(
            side=tk.LEFT, padx=(8, 2)
        )

        self._font_size_slider = RoundedSlider(
            font_frame,
            from_=self._MIN_FONT_SIZE,
            to=self._MAX_FONT_SIZE,
            value=self._font_size,
            width=100,
            bg_color=self._panel_color,
            fill_color=self._highlight_color,
            command=self._on_font_size_change,
        )
        self._font_size_slider.pack(side=tk.LEFT, padx=4)

        self._font_size_label = tk.Label(
            font_frame,
            text=f"{self._font_size}pt",
            bg=self._panel_color,
            fg=self._text_color,
            width=5,
        )
        self._font_size_label.pack(side=tk.LEFT)
        
        # ── 기타 설정 ──────────────────────────────────────────────────────────
        self._add_section("기타", parent)
        misc_frame = tk.Frame(parent, bg=self._panel_color)
        misc_frame.pack(fill=tk.X, padx=10, pady=2)
        
        self._show_trans_var = tk.BooleanVar(value=self._show_translations)
        tk.Checkbutton(
            misc_frame,
            text="번역/발음 표시",
            variable=self._show_trans_var,
            bg=self._panel_color,
            fg=self._text_color,
            selectcolor=self._panel_color,
            activebackground=self._panel_color,
            activeforeground=self._text_color,
            command=self._trigger_preview
        ).pack(side=tk.LEFT)

        # ── 저장 버튼 ──────────────────────────────────────────────────────────
        btn_frame = tk.Frame(parent, bg=self._panel_color)
        btn_frame.pack(fill=tk.X, padx=10, pady=(8, 10))

        tk.Button(
            btn_frame,
            text="저장",
            bg=self._highlight_color,
            fg="#ffffff",
            relief=tk.FLAT,
            padx=16,
            command=self._save,
        ).pack(side=tk.RIGHT)

        tk.Button(
            btn_frame,
            text="초기화",
            bg=self._panel_color,
            fg=self._text_color,
            relief=tk.FLAT,
            command=self._reset_defaults,
        ).pack(side=tk.RIGHT, padx=4)

    def _add_section(self, title: str, parent: tk.Widget) -> None:
        """섹션 구분 레이블 추가"""
        tk.Label(
            parent,
            text=title,
            bg=self._panel_color,
            fg=adjust_color_brightness(self._text_color, 0.7),
            font=("Malgun Gothic", 9),
        ).pack(anchor="w", padx=10, pady=(4, 0))

    def _add_color_row(self, label: str, initial_color: str, parent: tk.Widget) -> tk.Entry:
        """색상 입력 행 추가"""
        row = tk.Frame(parent, bg=self._panel_color)
        row.pack(fill=tk.X, padx=10, pady=1)

        tk.Label(row, text=label, bg=self._panel_color, fg=self._text_color, width=8).pack(
            side=tk.LEFT
        )

        entry = tk.Entry(
            row,
            bg=self._bg_color,
            fg=self._text_color,
            insertbackground=self._text_color,
            relief=tk.FLAT,
            bd=2,
            width=10,
        )
        if initial_color:
            entry.insert(0, initial_color)
        entry.pack(side=tk.LEFT, padx=4)

        # 색상 미리보기 박스
        preview = tk.Label(row, bg=initial_color, width=3, relief=tk.FLAT)
        preview.pack(side=tk.LEFT)

        def on_entry_change(event, e=entry, p=preview) -> None:
            try:
                color = e.get().strip()
                if color.startswith("#") and len(color) in (4, 7):
                    p.config(bg=color)
                    self._trigger_preview() # 미리보기
            except Exception:
                pass

        entry.bind("<KeyRelease>", on_entry_change)
        return entry

    def _on_opacity_change(self, value: float) -> None:
        """투명도 변경 핸들러"""
        self._opacity_label.config(text=f"{int(value * 100)}%")
        self._trigger_preview() # 미리보기

    def _on_font_size_change(self, value: float) -> None:
        """폰트 크기 변경 핸들러"""
        self._font_size_label.config(text=f"{int(value)}pt")
        self._trigger_preview() # 미리보기

    def _apply_preset(self, preset_name: str) -> None:
        """프리셋 적용"""
        if preset_name not in THEME_PRESETS:
            return

        preset = THEME_PRESETS[preset_name]
        # UI 업데이트
        self._bg_entry.delete(0, tk.END)
        self._bg_entry.insert(0, preset["bg"])
        self._text_entry.delete(0, tk.END)
        self._text_entry.insert(0, preset["text"])
        self._highlight_entry.delete(0, tk.END)
        self._highlight_entry.insert(0, preset["highlight"])
        
        self._trigger_preview() # 미리보기

    def _trigger_preview(self, event=None) -> None:
        """현재 설정값으로 미리보기 트리거"""
        if not self._on_preview:
            return
            
        try:
            settings = {
                "bg_color": self._bg_entry.get(),
                "text_color": self._text_entry.get(),
                "highlight_color": self._highlight_entry.get(),
                "opacity": self._opacity_slider.get(),
                "font_family": self._font_family_var.get(),
                "font_size": int(self._font_size_slider.get()),
                "show_translations": self._show_trans_var.get(),
                "panel_color": self._panel_color # 패널 컬러는 변경 불가 (현재 구조상)
            }
            self._on_preview(settings)
        except ValueError:
            pass # 입력값 오류 시 무시

    def _save(self) -> None:
        """설정 저장"""
        bg = self._bg_entry.get()
        text = self._text_entry.get()
        highlight = self._highlight_entry.get()
        opacity = self._opacity_slider.get()
        font_family = self._font_family_var.get()
        font_size = int(self._font_size_slider.get())

        if self._on_save:
            self._on_save({
                "bg_color": bg,
                "text_color": text,
                "highlight_color": highlight,
                "opacity": opacity,
                "font_family": font_family,
                "font_size": font_size,
                "show_translations": self._show_trans_var.get(),
            })

    def _reset_defaults(self) -> None:
        """기본값으로 초기화"""
        from settings.defaults import DEFAULT_SETTINGS
        self._bg_entry.delete(0, tk.END)
        self._bg_entry.insert(0, DEFAULT_SETTINGS["background_color"])
        self._text_entry.delete(0, tk.END)
        self._text_entry.insert(0, DEFAULT_SETTINGS["text_color"])
        self._highlight_entry.delete(0, tk.END)
        self._highlight_entry.insert(0, DEFAULT_SETTINGS["highlight_color"])
        self._opacity_slider.set(DEFAULT_SETTINGS["opacity"])
        self._font_family_var.set(DEFAULT_SETTINGS["font_family"])
        self._font_size_slider.set(DEFAULT_SETTINGS["font_size"])
        self._show_trans_var.set(DEFAULT_SETTINGS["show_translations"])

    def sync_from_settings(self, settings: dict) -> None:
        """외부 설정값으로 패널 동기화"""
        if "background_color" in settings:
            self._bg_entry.delete(0, tk.END)
            self._bg_entry.insert(0, settings["background_color"])
        if "text_color" in settings:
            self._text_entry.delete(0, tk.END)
            self._text_entry.insert(0, settings["text_color"])
        if "highlight_color" in settings:
            self._highlight_entry.delete(0, tk.END)
            self._highlight_entry.insert(0, settings["highlight_color"])
        if "opacity" in settings:
            self._opacity_slider.set(settings["opacity"])
        if "font_family" in settings:
            self._font_family_var.set(settings["font_family"])
        if "font_size" in settings:
            self._font_size_slider.set(settings["font_size"])
        if "show_translations" in settings:
            self._show_trans_var.set(settings["show_translations"])
