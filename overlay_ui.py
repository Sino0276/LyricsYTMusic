"""
가사 오버레이 UI 모듈.
tkinter를 사용하여 항상 최상위에 표시되는 투명 오버레이 창을 구현합니다.
"""

import tkinter as tk
from tkinter import font as tkfont
from tkinter import colorchooser
from typing import Optional, Callable
from dataclasses import dataclass, field
import win32gui
import win32con
import colorsys

DEFAULT_FONT = "Malgun Gothic"

# 테마 프리셋 정의
THEME_PRESETS = [
    {
        "name": "기본 (Dark)",
        "bg": "#1a1a2e",
        "text": "#e0e0e0",
        "highlight": "#e94560"
    },
    {
        "name": "라이트 (Light)",
        "bg": "#f5f5f5",
        "text": "#333333",
        "highlight": "#ff4757"
    },
    {
        "name": "딥 블랙 (OLED)",
        "bg": "#000000",
        "text": "#cccccc",
        "highlight": "#00d2d3"
    }
]

def adjust_color_brightness(hex_color, factor):
    """
    HEX 색상의 밝기를 조절합니다.
    :param hex_color: "#RRGGBB" 형식의 문자열
    :param factor: 1.0보다 크면 밝게, 작으면 어둡게 (예: 1.2 = 20% 밝게)
    :return: 조절된 HEX 색상
    """
    if not hex_color or not hex_color.startswith('#'):
        return hex_color
        
    try:
        # HEX -> RGB
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        
        # RGB -> HSV
        h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
        
        # 밝기(Value) 조절
        v = max(0.0, min(1.0, v * factor))
        
        # HSV -> RGB
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        
        # RGB -> HEX
        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
    except Exception:
        return hex_color

@dataclass
class LyricDisplayLine:
    """화면에 표시할 가사 라인"""
    text: str
    color: str
    is_current: bool = False
    translation: str = ""      # 번역 (다른 언어인 경우)
    romanization: str = ""     # 발음 (로마자 표기)



class RoundedSlider(tk.Canvas):
    """둥근 디자인의 커스텀 슬라이더"""
    
    def __init__(self, master, width=300, height=30, min_val=-3000, max_val=3000, command=None, bg="#202035", snap_val=None):
        super().__init__(master, width=width, height=height, bg=bg, highlightthickness=0)
        self.min_val = min_val
        self.max_val = max_val
        self.cur_val = 0
        self.command = command
        self.snap_val = snap_val
        
        # 색상 설정
        self.bar_bg_color = "#16213e" # 바 배경 (어두운 색) - 이것도 bg_color에 맞춰? 일단 고정
        self.highlight_color = "#e94560"
        
        self.w = width
        self.h = height
        self.pad = 10  # 좌우 여백
        self.bar_h = 6 # 바 두께
        
        # 이벤트 바인딩
        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<Configure>", self._on_resize)
        
        self._draw()

    def _on_resize(self, event):
        self.w = event.width
        self.h = event.height
        self._draw()

    def _val_to_x(self, val):
        usable_w = self.w - 2 * self.pad
        percent = (val - self.min_val) / (self.max_val - self.min_val)
        return self.pad + percent * usable_w

    def _x_to_val(self, x):
        usable_w = self.w - 2 * self.pad
        if usable_w <= 0: return self.min_val
        
        rel_x = x - self.pad
        percent = max(0, min(1, rel_x / usable_w))
        return int(self.min_val + percent * (self.max_val - self.min_val))

    def _draw(self):
        self.delete("all")
        
        # 중앙선 (배경)
        cy = self.h / 2
        
        # 바 배경 (둥근 캡)
        self.create_line(
            self.pad, cy, self.w - self.pad, cy,
            width=self.bar_h, fill=self.bar_bg_color, capstyle=tk.ROUND
        )
        
        # 활성 바 (중앙 0 기준)
        center_x = self._val_to_x(0)
        curr_x = self._val_to_x(self.cur_val)
        
        if self.cur_val != 0:
            self.create_line(
                center_x, cy, curr_x, cy,
                width=self.bar_h, fill=self.highlight_color, capstyle=tk.ROUND
            )
        
        # 핸들 (Thumb)
        r = 8
        self.create_oval(
            curr_x - r, cy - r, curr_x + r, cy + r,
            fill="#ffffff", outline=self.highlight_color, width=2
        )

    def _update_val(self, x):
        new_val = self._x_to_val(x)
        # 스냅 적용
        if self.snap_val:
            new_val = round(new_val / self.snap_val) * self.snap_val
        else:
            new_val = int(new_val)
        
        if self.cur_val != new_val:
            self.cur_val = new_val
            self._draw()
            if self.command:
                self.command(self.cur_val)

    def set(self, val):
        self.cur_val = max(self.min_val, min(self.max_val, val))
        self._draw()

    def get(self):
        return self.cur_val
    
    def _on_click(self, event):
        self._update_val(event.x)
        
    def _on_drag(self, event):
        self._update_val(event.x)
        
    def config_colors(self, bg_color=None, highlight_color=None):
        """색상 설정 업데이트"""
        if bg_color:
            self.configure(bg=bg_color)
        
        # 캔버스 아이템 색상 변경은 다시 그리기 필요
        # _draw 메서드에서 색상을 아예 인스턴스 변수로 관리하는 게 좋음
        # 하지만 간단하게 redraw 유도 (색상 변수는 없지만 highlight_color를 인자로 받을 수 있게 구조 변경 필요하거나,
        # _draw에서 self.master.cget('bg') 등을 참조할 수 없음)
        
        # 여기서는 단순히 다시 그리기 (색상 파라미터가 없으므로 _draw 수정 필요)
        # _draw를 수정하여 색상을 파라미터로 받거나 클래스 변수로 저장해야 함.
        # 일단 highlight_color를 저장하는 속성 추가
        if highlight_color:
            self.highlight_color = highlight_color
        self._draw() 

# RoundedSlider 클래스 수정 필요: __init__에서 색상 저장하고 _draw에서 사용하도록.


class LyricsOverlay:
    """가사 오버레이 창"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("YouTube Music Lyrics")
        
        # 스레드 안전 명령 큐 (트레이 등에서 사용)
        import queue
        self._command_queue = queue.Queue()
        
        # 창 설정
        self._setup_window()
        
        # UI 요소 생성
        self._create_widgets()
        
        # 드래그 상태
        self._drag_data = {"x": 0, "y": 0}
        
        # 콜백
        self._on_close: Optional[Callable] = None
        self._on_sync_adjust_callback: Optional[Callable] = None
        self._on_search_callback: Optional[Callable] = None
        self._on_settings_callback: Optional[Callable] = None
        self._on_save_settings_callback: Optional[Callable] = None
        self._on_do_search_callback: Optional[Callable] = None
        self._on_apply_lyrics_callback: Optional[Callable] = None
        
        # 현재 표시 중인 곡 정보
        self._current_title = ""
        self._current_artist = ""
        
        # 최소화 상태
        self._is_minimized = False
        self._pre_minimize_geometry = None
        
        # 명령 큐 처리 시작
        self._process_command_queue()
    
    def _process_command_queue(self):
        """명령 큐에서 명령 처리 (스레드 안전)"""
        try:
            while True:
                try:
                    cmd = self._command_queue.get_nowait()
                    if callable(cmd):
                        cmd()
                except:
                    break
        except:
            pass
        
        # 100ms마다 큐 확인
        self.root.after(100, self._process_command_queue)
    
    def queue_command(self, cmd: Callable):
        """명령 큐에 추가 (다른 스레드에서 호출 가능)"""
        self._command_queue.put(cmd)

    
    def _setup_window(self):
        """창 기본 설정"""
        # 창 크기 및 위치
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        window_width = 400
        window_height = 500
        
        # 화면 오른쪽 하단에 배치
        x = screen_width - window_width - 50
        y = screen_height - window_height - 100
        
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # 항상 최상위
        self.root.attributes("-topmost", True)
        
        # 반투명 설정 (Windows)
        self.root.attributes("-alpha", 0.9)
        
        # 배경색 (다크 테마)
        self._bg_color = "#1a1a2e"
        self._text_color = "#e0e0e0"
        self._highlight_color = "#e94560"  # 빨간색 계열
        
        # 초기 패널 색상 계산 (톤온톤 - 배경보다 진하게/어둡게)
        # 1.2(밝게) -> 0.85(어둡게)로 변경하여 무게감을 줌
        self._panel_color = adjust_color_brightness(self._bg_color, 0.85)
        
        self.root.configure(bg=self._bg_color)
        
        # 클릭 투과 상태
        self._click_through_enabled = False
        
    def set_colors(self, bg_color=None, text_color=None, highlight_color=None):
        """UI 색상 설정"""
        if bg_color:
            self._bg_color = bg_color
            
        if text_color:
            self._text_color = text_color
            
        if highlight_color:
            self._highlight_color = highlight_color
            
        # 1. 패널 색상 계산 (자동 톤온톤)
        # 배경보다 약간 어둡게 처리하여 "진한" 느낌을 주고 가독성 확보
        panel_color = adjust_color_brightness(self._bg_color, 0.85) # 15% 어둡게
        
        # 만약 배경이 너무 어두워서(블랙에 가까움) 더 어두워질 수 없다면? 
        # -> 오히려 밝게 해야 할 수도 있음.
        try:
             # 간단한 밝기 판별
            r = int(self._bg_color[1:3], 16)
            g = int(self._bg_color[3:5], 16)
            b = int(self._bg_color[5:7], 16)
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            
            # 너무 어두운 배경(예: #000000)이면 패널을 밝게
            if brightness < 30: 
                panel_color = adjust_color_brightness(self._bg_color, 1.3) # 30% 밝게
            # 너무 밝은 배경이면 더 어둡게
            elif brightness > 200:
                panel_color = adjust_color_brightness(self._bg_color, 0.9)
        except Exception:
            pass
            
        self._panel_color = panel_color

        # 2. 모든 위젯에 테마 재귀적 적용
        self._apply_theme_recursive(self.root, self._bg_color, self._panel_color, self._text_color, self._highlight_color)
        
        # RoundedSlider 색상 업데이트
        if hasattr(self, 'sync_slider'):
            self.sync_slider.configure(bg=self._panel_color) # 슬라이더는 패널 위에 있으므로 패널색 따름
            self.sync_slider.config_colors(bg_color=self._panel_color, highlight_color=self._highlight_color)
        
        if hasattr(self, 'opacity_slider'):
            self.opacity_slider.configure(bg=self._panel_color)
            self.opacity_slider.config_colors(bg_color=self._panel_color, highlight_color=self._highlight_color)

    def set_opacity(self, opacity: float):
        """투명도 설정 (0.1 ~ 1.0)"""
        # 최소값 보장 (너무 투명해서 안 보이는 것 방지)
        opacity = max(0.1, min(1.0, opacity))
        self.root.attributes("-alpha", opacity)

    def _apply_theme_recursive(self, widget, current_bg, panel_color, text_color, highlight_color):
        """
        위젯 트리 전체에 테마 적용 (재귀)
        :param widget: 대상 위젯
        :param current_bg: 현재 컨텍스트의 배경색 (부모로부터 상속)
        :param panel_color: 패널용 배경색 (패널 진입 시 current_bg가 됨)
        """
        try:
            # 이 위젯이 패널 시작점인지 확인
            next_bg = current_bg
            
            panels = [
                getattr(self, 'settings_frame', None),
                getattr(self, 'search_frame', None),
                getattr(self, 'sync_frame', None),
                getattr(self, 'title_bar', None)
            ]
            
            # 패널 자체이거나, 패널 내부의 특정 프레임(header 등)인 경우?
            # 일단 패널 객체 자체를 만나면 배경색을 변경
            if widget in panels and widget is not None:
                next_bg = panel_color
            
            # -- 색상 적용 --
            
            if isinstance(widget, (tk.Frame, tk.Canvas, tk.Toplevel)):
                widget.configure(bg=next_bg)
                
            elif isinstance(widget, tk.Label):
                # 아이콘 버튼 등 예외 처리
                icons = [getattr(self, 'close_btn', None), getattr(self, 'min_btn', None), getattr(self, 'sync_btn', None), getattr(self, 'search_btn', None)]
                
                if widget in icons:
                    widget.configure(bg=next_bg)
                elif widget == getattr(self, 'title_label', None):
                    # 제목은 강조색 사용
                    widget.configure(bg=next_bg, fg=highlight_color)
                elif widget == getattr(self, 'artist_label', None):
                    # 아티스트는 회색 유지 (테마에 따라 가독성 이슈가 있다면 text_color를 따르되 어둡게 해야겠지만 일단 고정)
                    widget.configure(bg=next_bg, fg="#888888")
                else:
                    widget.configure(bg=next_bg, fg=text_color)
            
            elif isinstance(widget, tk.Button):
                if widget == getattr(self, 'do_search_btn', None):
                    widget.configure(bg=highlight_color, fg="#ffffff", activebackground=highlight_color)
                else:
                    widget.configure(bg=next_bg, fg=text_color, activebackground=next_bg, activeforeground=highlight_color)
            
            elif isinstance(widget, tk.Entry):
                # 입력창은 약간 더 어둡게? 아니면 패널색?
                # 가독성을 위해 패널색보다 좀 더 어두운/밝은 색을 주면 좋지만
                # 여기서는 입력창 배경을 next_bg로 하되 테두리나 구분 필요
                # 일단 next_bg 사용
                widget.configure(bg=next_bg, fg=text_color, insertbackground=text_color)
            
            elif isinstance(widget, tk.Listbox):
                widget.configure(bg=next_bg, fg=text_color, selectbackground=highlight_color)
                
            elif isinstance(widget, tk.Checkbutton):
                 widget.configure(bg=next_bg, fg=text_color, selectcolor=next_bg, activebackground=next_bg, activeforeground=text_color)
            
            # 자식 순회 (변경된 bg 전달)
            for child in widget.winfo_children():
                self._apply_theme_recursive(child, next_bg, panel_color, text_color, highlight_color)
                
        except Exception:
            pass
        
    def set_click_through(self, enabled: bool):
        """클릭 투과 모드 설정 (마우스 이벤트를 뒤로 전달)"""
        self._click_through_enabled = enabled
        # 현재 이 기능이 오버레이 표시 문제를 일으켜 임시 비활성화함
        # 추후 안정적인 방법으로 재구현 필요
        pass
        
        # 테두리 없음
        self.root.overrideredirect(True)
        
        # 창 닫기 이벤트
        self.root.protocol("WM_DELETE_WINDOW", self._handle_close)

    def _create_widgets(self):
        """UI 위젯 생성"""
        # 메인 프레임
        self.main_frame = tk.Frame(
            self.root,
            bg=self._bg_color,
            highlightbackground="#4a4a6a",
            highlightthickness=2
        )
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 타이틀 바 (패널 색상 적용)
        self.title_bar = tk.Frame(self.main_frame, bg=self._panel_color, height=40)
        self.title_bar.pack(fill=tk.X)
        self.title_bar.pack_propagate(False)
        
        
        # 닫기 버튼
        self.close_btn = tk.Label(
            self.title_bar,
            text="✕",
            bg=self._panel_color,
            fg="#888888",
            font=(DEFAULT_FONT, 14),
            cursor="hand2"
        )
        self.close_btn.pack(side=tk.RIGHT, padx=10, pady=5)
        self.close_btn.bind("<Button-1>", lambda e: self._handle_close())
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.configure(fg=self._highlight_color))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.configure(fg="#888888"))
        
        # 최소화 버튼
        self.min_btn = tk.Label(
            self.title_bar,
            text="─",
            bg=self._panel_color,
            fg="#888888",
            font=(DEFAULT_FONT, 14),
            cursor="hand2"
        )
        self.min_btn.pack(side=tk.RIGHT, padx=5, pady=5)
        self.min_btn.bind("<Button-1>", lambda e: self._toggle_minimize())
        self.min_btn.bind("<Enter>", lambda e: self.min_btn.configure(fg=self._highlight_color))
        self.min_btn.bind("<Leave>", lambda e: self.min_btn.configure(fg="#888888"))
        
        # 싱크 버튼
        self.sync_btn = tk.Label(
            self.title_bar,
            text="⏱",
            bg=self._panel_color,
            fg="#888888",
            font=(DEFAULT_FONT, 11),
            cursor="hand2",
            activeforeground=self._highlight_color
        )
        self.sync_btn.pack(side=tk.RIGHT, padx=5, pady=8)
        self.sync_btn.bind("<Button-1>", lambda e: self._toggle_sync_panel())
        self.sync_btn.bind("<Enter>", lambda e: self.sync_btn.configure(fg=self._highlight_color))
        self.sync_btn.bind("<Leave>", lambda e: self.sync_btn.configure(fg="#888888"))
        
        # 검색 버튼
        self.search_btn = tk.Label(
            self.title_bar,
            text="🔍",
            bg=self._panel_color,
            fg="#888888",
            font=(DEFAULT_FONT, 11),
            cursor="hand2",
            activeforeground=self._highlight_color
        )
        self.search_btn.pack(side=tk.RIGHT, padx=5, pady=8)
        self.search_btn.bind("<Button-1>", lambda e: self._on_search_click())
        self.search_btn.bind("<Enter>", lambda e: self.search_btn.configure(fg=self._highlight_color))
        self.search_btn.bind("<Leave>", lambda e: self.search_btn.configure(fg="#888888"))
        
        # 곡 정보 레이블
        self.title_label = tk.Label(
            self.title_bar,
            text="YouTube Music Lyrics",
            bg=self._panel_color,
            fg=self._highlight_color,
            font=(DEFAULT_FONT, 11, "bold"),
            anchor="w"
        )
        self.title_label.pack(side=tk.LEFT, padx=10, pady=8, fill=tk.X, expand=True)
        
        # 드래그 바인딩
        self.title_bar.bind("<Button-1>", self._start_drag)
        self.title_bar.bind("<B1-Motion>", self._on_drag)
        self.title_label.bind("<Button-1>", self._start_drag)
        self.title_label.bind("<B1-Motion>", self._on_drag)
        
        # 아티스트 레이블
        self.artist_label = tk.Label(
            self.main_frame,
            text="",
            bg=self._bg_color,
            fg="#888888",
            font=(DEFAULT_FONT, 9),
            anchor="w"
        )
        self.artist_label.pack(fill=tk.X, padx=15, pady=(5, 0))

        # 싱크 조절 패널
        self.sync_frame = tk.Frame(self.main_frame, bg=self._panel_color, height=0)
        
        # 커스텀 슬라이더
        self.sync_slider = RoundedSlider(
            self.sync_frame,
            min_val=-5000,
            max_val=5000,
            bg=self._panel_color,
            command=self._on_slider_move,
            snap_val=100
        )
        self.sync_slider.pack(fill=tk.X, padx=20, pady=(10, 5))
        
        self.sync_label = tk.Label(
            self.sync_frame,
            text="싱크 조절: 0.0s",
            bg=self._panel_color,
            fg=self._text_color,
            font=(DEFAULT_FONT, 9)
        )
        self.sync_label.pack(pady=(0, 10))
        
        # 설정 패널
        self.settings_frame = tk.Frame(self.main_frame, bg=self._panel_color, width=250)
        self._settings_panel_visible = False
        self._settings_panel_animating = False
        
        # 다중 소스 검색 체크박스 (IntVar 사용 - Checkbutton 토글 버그 회피)
        self._multi_source_var = tk.IntVar(value=0)
        self.multi_source_check = tk.Checkbutton(
            self.settings_frame,
            text="다중 소스 검색 (더 정확, 더 느림)",
            variable=self._multi_source_var,
            bg=self._panel_color,
            fg=self._text_color,
            selectcolor=self._panel_color,
            activebackground=self._panel_color,
            activeforeground=self._highlight_color,
            font=(DEFAULT_FONT, 9),
            command=self._on_settings_changed
        )
        self.multi_source_check.pack(anchor="w", padx=20, pady=(10, 5))
        
        # 색상 설정 섹션 - 헤더 프레임
        color_header_frame = tk.Frame(self.settings_frame, bg=self._panel_color)
        color_header_frame.pack(fill=tk.X, padx=20, pady=(10, 5))
        
        tk.Label(color_header_frame, text="🎨 테마 설정", bg=self._panel_color, fg="#888888", font=(DEFAULT_FONT, 9, "bold")).pack(side=tk.LEFT)
        
        # 초기화 버튼
        tk.Button(
            color_header_frame,
            text="↺ 초기화",
            bg=self._panel_color,
            fg="#888888",
            activebackground=self._panel_color,
            activeforeground=self._highlight_color,
            relief=tk.FLAT,
            font=(DEFAULT_FONT, 8),
            command=self._reset_colors
        ).pack(side=tk.RIGHT)
        
        # 프리셋 버튼 영역
        preset_frame = tk.Frame(self.settings_frame, bg=self._panel_color)
        preset_frame.pack(fill=tk.X, padx=20, pady=5)
        
        tk.Label(preset_frame, text="프리셋:", bg=self._panel_color, fg="#888888", font=(DEFAULT_FONT, 9), width=10, anchor="w").pack(side=tk.LEFT)
        
        # 프리셋 버튼 생성 헬퍼
        def create_preset_btn(idx, label):
            btn = tk.Button(
                preset_frame,
                text=label,
                bg=self._panel_color,
                fg=self._text_color,
                activebackground=self._panel_color,
                activeforeground=self._highlight_color,
                relief=tk.SOLID,
                borderwidth=1,
                font=(DEFAULT_FONT, 8),
                width=2,
                command=lambda: self._apply_preset(idx)
            )
            btn.pack(side=tk.LEFT, padx=3)
            return btn
            
        create_preset_btn(0, "1")
        create_preset_btn(1, "2")
        create_preset_btn(2, "3")
        
        # 투명도 슬라이더
        opacity_frame = tk.Frame(self.settings_frame, bg=self._panel_color)
        opacity_frame.pack(fill=tk.X, padx=20, pady=5)
        
        tk.Label(opacity_frame, text="투명도", bg=self._panel_color, fg=self._text_color, font=(DEFAULT_FONT, 9), width=10, anchor="w").pack(side=tk.LEFT)
        
        self.opacity_val_label = tk.Label(opacity_frame, text="90%", bg=self._panel_color, fg="#888888", font=(DEFAULT_FONT, 9), width=4, anchor="e")
        self.opacity_val_label.pack(side=tk.RIGHT)
        
        # 슬라이더 (20~100)
        self.opacity_slider = RoundedSlider(
            self.settings_frame,
            width=160,
            height=20,
            min_val=20,
            max_val=100,
            bg=self._panel_color,
            command=self._on_opacity_change,
            snap_val=1
        )
        self.opacity_slider.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        color_frame = tk.Frame(self.settings_frame, bg=self._panel_color)
        color_frame.pack(fill=tk.X, padx=20, pady=5)
        
        def create_color_picker(label_text, color_key):
            frame = tk.Frame(color_frame, bg=self._panel_color)
            frame.pack(fill=tk.X, pady=2)
            
            tk.Label(frame, text=label_text, bg=self._panel_color, fg=self._text_color, font=(DEFAULT_FONT, 9), width=10, anchor="w").pack(side=tk.LEFT)
            
            # 색상 프리뷰/버튼
            btn = tk.Button(
                frame, 
                text="변경", 
                width=4,
                font=(DEFAULT_FONT, 8),
                relief=tk.FLAT,
                command=lambda: self._open_color_picker(color_key)
            )
            btn.pack(side=tk.RIGHT)
            
            preview = tk.Label(frame, width=3, relief=tk.SOLID, borderwidth=1)
            preview.pack(side=tk.RIGHT, padx=5)
            
            return preview
            
        self.bg_color_preview = create_color_picker("배경색", "background_color")
        self.text_color_preview = create_color_picker("가사색", "text_color")
        self.highlight_color_preview = create_color_picker("강조색", "highlight_color")
        
        # 검색 패널
        self.search_frame = tk.Frame(self.main_frame, bg=self._panel_color)
        
        # 검색 입력 필드들
        search_input_frame = tk.Frame(self.search_frame, bg=self._panel_color)
        search_input_frame.pack(fill=tk.X, padx=15, pady=10)
        
        tk.Label(search_input_frame, text="아티스트", bg=self._panel_color, fg="#888888", font=(DEFAULT_FONT, 8)).pack(anchor="w")
        self.search_artist_entry = tk.Entry(search_input_frame, bg=self._panel_color, fg=self._text_color, insertbackground=self._text_color, relief=tk.FLAT, font=(DEFAULT_FONT, 9))
        self.search_artist_entry.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(search_input_frame, text="제목", bg=self._panel_color, fg="#888888", font=(DEFAULT_FONT, 8)).pack(anchor="w")
        self.search_title_entry = tk.Entry(search_input_frame, bg=self._panel_color, fg=self._text_color, insertbackground=self._text_color, relief=tk.FLAT, font=(DEFAULT_FONT, 9))
        self.search_title_entry.pack(fill=tk.X)
        
        # 검색 버튼과 상태
        search_btn_frame = tk.Frame(self.search_frame, bg=self._panel_color)
        search_btn_frame.pack(fill=tk.X, padx=15, pady=(5, 0))
        
        self.do_search_btn = tk.Button(search_btn_frame, text="검색", bg=self._highlight_color, fg="white", relief=tk.FLAT, font=(DEFAULT_FONT, 9), command=self._do_search)
        self.do_search_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.search_status_label = tk.Label(search_btn_frame, text="", bg=self._panel_color, fg="#888888", font=(DEFAULT_FONT, 8))
        self.search_status_label.pack(side=tk.LEFT)
        
        # 검색 결과 리스트
        self.search_listbox = tk.Listbox(self.search_frame, bg=self._panel_color, fg=self._text_color, selectbackground=self._highlight_color, relief=tk.FLAT, height=4, font=(DEFAULT_FONT, 8))
        self.search_listbox.pack(fill=tk.X, padx=15, pady=5)
        
        # 적용 버튼
        self.apply_search_btn = tk.Button(self.search_frame, text="선택한 가사 적용", bg=self._panel_color, fg=self._text_color, relief=tk.FLAT, font=(DEFAULT_FONT, 9), command=self._apply_selected_lyrics)
        self.apply_search_btn.pack(fill=tk.X, padx=15, pady=(0, 10))

        # 가사 컨테이너
        self.lyrics_container = tk.Canvas(
            self.main_frame,
            bg=self._bg_color,
            highlightthickness=0
        )
        self.lyrics_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 가사 내부 프레임
        self.lyrics_frame = tk.Frame(self.lyrics_container, bg=self._bg_color)
        self.lyrics_window = self.lyrics_container.create_window(
            (0, 0),
            window=self.lyrics_frame,
            anchor="nw"
        )
        
        # 스크롤 설정
        self.lyrics_frame.bind("<Configure>", self._on_lyrics_frame_configure)
        self.lyrics_container.bind("<Configure>", self._on_canvas_configure)
        
        # 마우스 휠 스크롤
        self.lyrics_container.bind("<MouseWheel>", self._on_mousewheel)
        self.lyrics_frame.bind("<MouseWheel>", self._on_mousewheel)
        
        # 리사이즈 핸들
        self.resize_handle = tk.Label(
            self.main_frame,
            text="⋮⋮",
            bg=self._bg_color,
            fg="#4a4a6a",
            cursor="sizing"
        )
        self.resize_handle.place(relx=1.0, rely=1.0, anchor="se")
        self.resize_handle.bind("<Button-1>", self._start_resize)
        self.resize_handle.bind("<B1-Motion>", self._on_resize)
        
        # 설정 버튼 (우측 하단, 리사이즈 핸들 옆)
        self.settings_btn = tk.Label(
            self.main_frame,
            text="⚙",
            bg=self._bg_color,
            fg="#4a4a6a",
            font=(DEFAULT_FONT, 10),
            cursor="hand2"
        )
        self.settings_btn.place(relx=1.0, rely=1.0, anchor="se", x=-25)
        self.settings_btn.bind("<Button-1>", lambda e: self._on_settings_click())
        self.settings_btn.bind("<Enter>", lambda e: self.settings_btn.configure(fg=self._highlight_color))
        self.settings_btn.bind("<Leave>", lambda e: self.settings_btn.configure(fg="#4a4a6a"))
        
        # 가사 라인 위젯들
        self._lyric_labels: list[tk.Label] = []
        
        # 플레이스홀더 메시지
        self._show_placeholder()
    
    def _show_placeholder(self):
        """플레이스홀더 메시지 표시"""
        placeholder = tk.Label(
            self.lyrics_frame,
            text="🎵 YouTube Music에서\n음악을 재생하세요",
            bg=self._bg_color,
            fg=self._text_color,
            font=(DEFAULT_FONT, 12),
            justify=tk.CENTER
        )
        placeholder.pack(pady=100)
        self._lyric_labels.append(placeholder)
    
    def _start_drag(self, event):
        """드래그 시작"""
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
    
    def _on_drag(self, event):
        """드래그 중"""
        delta_x = event.x - self._drag_data["x"]
        delta_y = event.y - self._drag_data["y"]
        
        x = self.root.winfo_x() + delta_x
        y = self.root.winfo_y() + delta_y
        
        self.root.geometry(f"+{x}+{y}")
    
    def _start_resize(self, event):
        """리사이즈 시작"""
        self._drag_data["x"] = event.x_root
        self._drag_data["y"] = event.y_root
        self._drag_data["width"] = self.root.winfo_width()
        self._drag_data["height"] = self.root.winfo_height()
    
    def _on_resize(self, event):
        """리사이즈 중"""
        delta_x = event.x_root - self._drag_data["x"]
        delta_y = event.y_root - self._drag_data["y"]
        
        new_width = max(250, self._drag_data["width"] + delta_x)
        new_height = max(200, self._drag_data["height"] + delta_y)
        
        self.root.geometry(f"{new_width}x{new_height}")
    
    def _toggle_minimize(self):
        """최소화 토글"""
        # 가사 영역만 숨기기/보이기
        if self.lyrics_container.winfo_viewable():
            self._pre_minimize_geometry = self.root.geometry()
            self.lyrics_container.pack_forget()
            self.artist_label.pack_forget()
            self.root.geometry(f"{self.root.winfo_width()}x45")
            self._is_minimized = True
            print("[UI] 창 최소화 (리소스 절약 모드)")
        else:
            self.artist_label.pack(fill=tk.X, padx=15, pady=(5, 0))
            self.lyrics_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            if self._pre_minimize_geometry:
                self.root.geometry(self._pre_minimize_geometry)
            else:
                self.root.geometry(f"{self.root.winfo_width()}x500")
            self._is_minimized = False
            print("[UI] 창 복원 (정상 모드)")
    
    def is_minimized(self) -> bool:
        """최소화 상태 확인"""
        return self._is_minimized
    
    def _on_lyrics_frame_configure(self, event):
        """가사 프레임 크기 변경 시"""
        self.lyrics_container.configure(scrollregion=self.lyrics_container.bbox("all"))
    
    def _on_canvas_configure(self, event):
        """캔버스 크기 변경 시"""
        self.lyrics_container.itemconfig(self.lyrics_window, width=event.width)
    
    def _on_mousewheel(self, event):
        """마우스 휠 스크롤"""
        self.lyrics_container.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def _handle_close(self):
        """닫기 처리"""
        if self._on_close:
            self._on_close()
        self.root.destroy()
    
    def center_window(self):
        """창을 화면 중앙으로 이동"""
        self.root.update_idletasks()
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()
        
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.root.geometry(f"+{x}+{y}")
        self.root.deiconify()  # 혹시 숨겨져 있으면 표시
        self.root.lift()  # 최상위로
        self.root.focus_force()  # 포커스
        print(f"[UI] 창을 화면 중앙으로 이동 ({x}, {y})")
    
    def _toggle_sync_panel(self):
        """싱크 패널 토글"""
        if self.sync_frame.winfo_viewable():
            self.sync_frame.pack_forget()
            self.sync_btn.configure(fg="#888888")
        else:
            self.sync_frame.pack(fill=tk.X, after=self.artist_label)
            self.sync_btn.configure(fg="#e94560")
            
    def _on_slider_move(self, value):
        """슬라이더 이동 시"""
        offset = int(value)
        sign = "+" if offset > 0 else ""
        sec = offset / 1000.0
        
        self.sync_label.configure(text=f"싱크 조절: {sign}{sec}s")
        
        if self._on_sync_adjust_callback:
            self._on_sync_adjust_callback(offset)
            

            

            
    def _open_color_picker(self, color_key):
        """색상 선택기 열기"""
        current_color = None
        if color_key == "background_color":
            current_color = self._bg_color
        elif color_key == "text_color":
            current_color = self._text_color
        elif color_key == "highlight_color":
            current_color = self._highlight_color
            
        color = colorchooser.askcolor(color=current_color, title=f"{color_key} 선택")[1]
        
        if color:
            # 설정 업데이트
            new_settings = {color_key: color}
            
            # 콜백 호출 (메인에서 처리)
            if self._on_save_settings_callback:
                self._on_save_settings_callback(new_settings)

    def _reset_colors(self):
        """색상 설정 초기화"""
        defaults = {
            "background_color": "#1a1a2e",
            "text_color": "#e0e0e0",
            "highlight_color": "#e94560",
            "opacity": 0.9
        }
        
        # 콜백 호출 (메인에서 처리 - 설정 병합 및 저장)
        if self._on_save_settings_callback:
            self._on_save_settings_callback(defaults)

    def _apply_preset(self, index):
        """테마 프리셋 적용"""
        if 0 <= index < len(THEME_PRESETS):
            preset = THEME_PRESETS[index]
            new_settings = {
                "background_color": preset["bg"],
                "text_color": preset["text"],
                "highlight_color": preset["highlight"]
            }
            
            # 콜백 호출 (메인에서 처리)
            if self._on_save_settings_callback:
                self._on_save_settings_callback(new_settings)

    def _on_settings_click(self):
        """설정 버튼 클릭 시 - 패널 토글"""
        self._toggle_settings_panel()

    def _toggle_settings_panel(self):
        """설정 패널 토글 (오른쪽에서 슬라이드)"""
        # 애니메이션 중이면 무시
        if self._settings_panel_animating:
            return
            
        # 다른 패널 닫기
        if self.search_frame.winfo_viewable():
            self.search_frame.pack_forget()
            self.search_btn.configure(fg="#888888")
        
        if self._settings_panel_visible:
            # 닫기 애니메이션 (왼쪽 -> 오른쪽으로 사라짐)
            self._animate_settings_panel(show=False)
            self.settings_btn.configure(fg="#4a4a6a")
        else:
            # 열기 애니메이션 (오른쪽 -> 왼쪽으로 나타남)
            self._animate_settings_panel(show=True)
            self.settings_btn.configure(fg="#e94560")
    
    def _animate_settings_panel(self, show: bool):
        """설정 패널 슬라이드 애니메이션"""
        self._settings_panel_animating = True
        
        panel_width = 250  # 패널 너비
        right_margin = 5   # 오른쪽 여백 (테두리 보이게)
        parent_width = self.main_frame.winfo_width()
        parent_height = self.main_frame.winfo_height()
        
        # 패널 높이 (타이틀바 아래부터 창 하단까지 - 리사이즈 핸들 위)
        title_bar_height = 40
        bottom_margin = 30 # 하단 여백 (리사이즈 핸들 등 표시)
        panel_height = parent_height - title_bar_height - bottom_margin
        
        if show:
            # 시작: 화면 밖 오른쪽
            start_x = parent_width
            end_x = parent_width - panel_width - right_margin
            self.settings_frame.place(x=start_x, y=title_bar_height, width=panel_width, height=panel_height)
            self.settings_frame.lift()  # 패널을 위로
            
            # 설정 버튼과 리사이즈 핸들이 패널 위에 보이도록 순서 조정
            self.settings_btn.lift()
            self.resize_handle.lift()
        else:
            # 시작: 현재 위치, 끝: 화면 밖 오른쪽
            start_x = parent_width - panel_width - right_margin
            end_x = parent_width
        
        # 애니메이션 파라미터
        duration = 150  # ms
        steps = 10
        step_delay = duration // steps
        step_distance = (end_x - start_x) / steps
        current_step = [0]
        current_x = [start_x]
        
        def animate_step():
            if current_step[0] >= steps:
                # 애니메이션 완료
                self._settings_panel_animating = False
                self._settings_panel_visible = show
                if not show:
                    self.settings_frame.place_forget()
                return
            
            current_x[0] += step_distance
            self.settings_frame.place(x=int(current_x[0]), y=title_bar_height, width=panel_width, height=panel_height)
            
            # 애니메이션 중에도 버튼이 계속 위에 있도록
            if show:
                self.settings_btn.lift()
                self.resize_handle.lift()
                
            current_step[0] += 1
            self.root.after(step_delay, animate_step)
        
        animate_step()

    def _on_settings_changed(self):
        """설정 변경 시 콜백 호출 (수동 토글)"""
        # Checkbutton이 자동 토글하지 않으므로 수동으로 토글
        current_int = self._multi_source_var.get()
        new_int = 0 if current_int == 1 else 1
        self._multi_source_var.set(new_int)
        
        bool_value = bool(new_int)
        if self._on_save_settings_callback:
            self._on_save_settings_callback({"multi_source_search": bool_value})
    
    def set_on_settings_save(self, callback: Callable[[dict], None]):
        """설정 저장 콜백 설정"""
        self._on_save_settings_callback = callback
    
    def _on_opacity_change(self, val):
        """투명도 슬라이더 변경 콜백"""
        opacity = val / 100.0
        self.set_opacity(opacity)
        self.opacity_val_label.configure(text=f"{int(val)}%")
        
        # 설정 저장 (디바운싱 없이 즉시 저장하면 파일 I/O 과부하 우려가 있지만,
        # SettingsManager가 알아서 하거나 일단 기능 구현 우선)
        if self._on_save_settings_callback: # Changed from self.on_settings_save to self._on_save_settings_callback
            self._on_save_settings_callback({"opacity": opacity})

    def update_settings_ui(self, settings: dict):
        """설정 UI 업데이트"""
        if "multi_source_search" in settings:
            bool_value = settings["multi_source_search"]
            int_value = 1 if bool_value else 0
            current_int = self._multi_source_var.get()
            
            if current_int != int_value:
                self._multi_source_var.set(int_value)
                # Checkbutton 시각 상태 강제 동기화
                if int_value == 1:
                    self.multi_source_check.select()
                else:
                    self.multi_source_check.deselect()
            
        if "opacity" in settings and hasattr(self, 'opacity_slider'):
            opacity = settings["opacity"]
            val = int(opacity * 100)
            # 슬라이더 값 강제 설정 (RoundedSlider에 set_value 메서드가 있다면)
            # 현재 RoundedSlider는 cur_val을 직접 수정하고 redraw해야 함
            self.opacity_slider.cur_val = max(20, min(100, val))
            self.opacity_slider._draw()
            self.opacity_val_label.configure(text=f"{val}%")
            
        # 색상 프리뷰 업데이트
        if hasattr(self, 'bg_color_preview'): # UI가 생성된 경우에만
            bg_color = settings.get("background_color", self._bg_color)
            text_color = settings.get("text_color", self._text_color)
            highlight_color = settings.get("highlight_color", self._highlight_color)
            
            try:
                self.bg_color_preview.configure(bg=bg_color)
                self.text_color_preview.configure(bg=text_color)
                self.highlight_color_preview.configure(bg=highlight_color)
            except:
                pass

    def _on_search_click(self):
        """검색 버튼 클릭 시 - 패널 토글"""
        self._toggle_search_panel()
        if self._on_search_callback:
            self._on_search_callback()

    def _toggle_search_panel(self):
        """검색 패널 토글"""
        # 다른 패널 닫기
        if self.settings_frame.winfo_viewable():
            self.settings_frame.pack_forget()
            self.settings_btn.configure(fg="#4a4a6a")
        
        if self.search_frame.winfo_viewable():
            self.search_frame.pack_forget()
            self.search_btn.configure(fg="#888888")
        else:
            self.search_frame.pack(fill=tk.X, after=self.artist_label)
            self.search_btn.configure(fg="#e94560")
    
    def show_search_panel(self):
        """검색 패널 열기 (이미 열려있으면 유지)"""
        # 다른 패널 닫기
        if self.settings_frame.winfo_viewable():
            self.settings_frame.pack_forget()
            self.settings_btn.configure(fg="#4a4a6a")
        
        # 검색 패널이 닫혀있으면 열기
        if not self.search_frame.winfo_viewable():
            self.search_frame.pack(fill=tk.X, after=self.artist_label)
            self.search_btn.configure(fg="#e94560")
    
    def update_search_fields(self, title: str, artist: str):
        """검색 필드 업데이트"""
        self.search_artist_entry.delete(0, tk.END)
        self.search_artist_entry.insert(0, artist)
        self.search_title_entry.delete(0, tk.END)
        self.search_title_entry.insert(0, title)
        self.search_listbox.delete(0, tk.END)
        self.search_status_label.configure(text="")
    
    def _do_search(self):
        """검색 실행"""
        if self._on_do_search_callback:
            title = self.search_title_entry.get()
            artist = self.search_artist_entry.get()
            self.search_status_label.configure(text="검색 중...", fg="#ffff00")
            self.root.update()
            self._on_do_search_callback(title, artist)
    
    def set_on_do_search(self, callback: Callable[[str, str], None]):
        """검색 실행 콜백 설정"""
        self._on_do_search_callback = callback
    
    def update_search_results(self, results: list[tuple[str, str]]):
        """검색 결과 업데이트"""
        self._search_results = results
        self.search_listbox.delete(0, tk.END)
        
        if not results:
            self.search_status_label.configure(text="검색 결과 없음", fg="#ff6b6b")
        else:
            self.search_status_label.configure(text=f"{len(results)}개 결과", fg="#00ff00")
            for prov, lrc in results:
                preview = lrc.strip().split('\n')[0][:25]
                self.search_listbox.insert(tk.END, f"[{prov}] {preview}...")
    
    def _apply_selected_lyrics(self):
        """선택한 가사 적용"""
        idx = self.search_listbox.curselection()
        if not idx or not hasattr(self, '_search_results'):
            return
        
        selected_idx = idx[0]
        prov, lrc_content = self._search_results[selected_idx]
        
        if self._on_apply_lyrics_callback:
            self._on_apply_lyrics_callback(lrc_content, f"{prov}")
        
        # 패널 닫기
        self.search_frame.pack_forget()
        self.search_btn.configure(fg="#888888")
    
    def set_on_apply_lyrics(self, callback: Callable[[str, str], None]):
        """가사 적용 콜백 설정"""
        self._on_apply_lyrics_callback = callback

    def set_on_search_request(self, callback: Callable):
        """검색 요청 콜백 설정 (패널 열릴 때 호출)"""
        self._on_search_callback = callback

    def reset_sync_control(self):
        """싱크 컨트롤 초기화"""
        self.sync_slider.set(0)
        self.sync_label.configure(text="싱크 조절: 0.0s")

    def set_on_close(self, callback: Callable):
        """닫기 콜백 설정"""
        self._on_close = callback

    def set_on_sync_adjust(self, callback: Callable[[int], None]):
        """싱크 조절 콜백 설정"""
        self._on_sync_adjust_callback = callback
        
        # 키보드 단축키도 유지 (슬라이더 값 변경)
        def adjust_by_key(delta):
            current = self.sync_slider.get()
            new_val = max(-5000, min(5000, current + delta))
            self.sync_slider.set(new_val) # _on_slider_move 트리거됨
            
        self.root.bind("<Left>", lambda e: adjust_by_key(-500))
        self.root.bind("<Right>", lambda e: adjust_by_key(500))
        self.root.bind("<Up>", lambda e: adjust_by_key(100))
        self.root.bind("<Down>", lambda e: adjust_by_key(-100))
    
    def show_toast(self, message: str):
        """일시적인 메시지 표시 (토스트) - 슬라이더 사용 시에는 불필요할 수 있으나 유지"""
        toast = tk.Label(
            self.root,
            text=message,
            bg="#333333",
            fg="#ffffff",
            font=(DEFAULT_FONT, 12, "bold"),
            padx=20,
            pady=10,
            relief=tk.FLAT
        )
        # 화면 중앙 하단에 배치
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()
        toast.place(x=window_width//2, y=window_height - 100, anchor="center")
        
        # 1.5초 후 제거
        self.root.after(1500, toast.destroy)
    
    def show_loading_message(self, message: str = "🔍 가사 검색 중..."):
        """로딩 메시지 표시"""
        # 기존 가사 내용 지우고 로딩 메시지 표시
        for widget in self.lyrics_frame.winfo_children():
            widget.destroy()
        
        loading_label = tk.Label(
            self.lyrics_frame,
            text=message,
            bg=self._bg_color,  # 가사 프레임 배경색과 일치
            fg=self._text_color # 텍스트 색상 사용
            if self._text_color else "#888888", # 안전장치
            font=(DEFAULT_FONT, 12),
            wraplength=350,  # 긴 메시지 줄바꿈
            justify="center",
            pady=50
        )
        loading_label.pack(expand=True, fill='both')
    
    def update_track_info(self, title: str, artist: str):
        """곡 정보 업데이트"""
        self._current_title = title
        self._current_artist = artist
        
        # 타이틀 바 업데이트
        display_title = title[:30] + "..." if len(title) > 30 else title
        self.title_label.configure(text=display_title)
        self.artist_label.configure(text=artist)
    
    def update_lyrics(self, lines: list[LyricDisplayLine]):
        """가사 표시 업데이트"""
        # 인덱스 매핑 (가사 라인 인덱스 -> 메인 라벨 위젯)
        self._line_map: dict[int, tk.Label] = {}
        
        # 기존 lyrics_frame 자식 모두 제거 (로딩 메시지 포함)
        for widget in self.lyrics_frame.winfo_children():
            widget.destroy()
        self._lyric_labels.clear()
        
        if not lines:
            self._show_placeholder()
            return
        
        # 폰트 설정
        normal_font = tkfont.Font(family=DEFAULT_FONT, size=11)
        highlight_font = tkfont.Font(family=DEFAULT_FONT, size=13, weight="bold")
        sub_font = tkfont.Font(family=DEFAULT_FONT, size=9)  # 번역/발음용 작은 폰트
        
        current_y = 0
        
        for i, line in enumerate(lines):
            # 현재 줄 하이라이트
            if line.is_current:
                # 하이라이트 배경은 사용자 지정이 어려울 수 있으니, 배경색보다 조금 밝게 자동 계산하거나
                # 일단은 고정값 사용하되, 텍스트 색상을 강조색으로
                # 여기서는 가독성을 위해 기존 로직 유지하되 색상 변수 활용
                 
                # 배경색을 약간 밝게 조정 (임시) - 색상 연산 로직이 없으므로 고정값 사용
                # 만약 self._bg_color가 바뀌면 이 부분도 바뀌어야 자연스러움.
                # 일단은 텍스트 색상만 확실하게 반영
                bg_color = "#252540" # 하이라이트 배경 (약간 밝음)
                # 만약 배경이 바뀌었다면? -> 배경색과 동일하게 가고 글자색만 바꿈 (심플)
                # 또는 투명도만 조절? tkinter는 불가능.
                
                # 심플하게: 하이라이트 시 배경은 그대로 두고, 글자색과 폰트만 강조
                # 하지만 기존 디자인(박스 형태)을 선호할 수 있음.
                # 타협안: 기본 배경색과 동일하게 하고 폰트/색상 강조
                bg_color = self._bg_color 
                text_font = highlight_font
                fg_color = self._highlight_color 
            else:
                bg_color = self._bg_color
                text_font = normal_font
                fg_color = self._text_color # 기본 가사색 사용 (기존 line.color 무시/오버라이드)
                # 주의: line.color는 파서가 주는 값일 수도 있음 (듀엣 곡 등).
                # 사용자 설정이 우선이라면 덮어쓰기.
                
            
            # 메인 가사 라벨
            label = tk.Label(
                self.lyrics_frame,
                text=line.text,
                bg=bg_color,
                fg=fg_color,
                font=text_font,
                wraplength=360,
                justify=tk.LEFT,
                anchor="w",
                padx=10,
                pady=4
            )
            label.pack(fill=tk.X, pady=(1, 0))
            label.bind("<MouseWheel>", self._on_mousewheel)
            self._lyric_labels.append(label)
            
            # 맵핑 저장
            self._line_map[i] = label
            
            # 발음 표시 (있는 경우)
            if line.romanization:
                rom_label = tk.Label(
                    self.lyrics_frame,
                    text=f"    {line.romanization}",
                    bg=bg_color,
                    fg="#7a7a9a",  # 회색빛 보라
                    font=sub_font,
                    wraplength=360,
                    justify=tk.LEFT,
                    anchor="w",
                    padx=10,
                    pady=0
                )
                rom_label.pack(fill=tk.X, pady=0)
                rom_label.bind("<MouseWheel>", self._on_mousewheel)
                self._lyric_labels.append(rom_label)
            
            # 번역 표시 (있는 경우)
            if line.translation:
                trans_label = tk.Label(
                    self.lyrics_frame,
                    text=f"    {line.translation}",
                    bg=bg_color,
                    fg="#5a5a7a",  # 더 어두운 회색
                    font=sub_font,
                    wraplength=360,
                    justify=tk.LEFT,
                    anchor="w",
                    padx=10,
                    pady=2
                )
                trans_label.pack(fill=tk.X, pady=1)
                trans_label.bind("<MouseWheel>", self._on_mousewheel)
                self._lyric_labels.append(trans_label)
            
            # 현재 줄로 스크롤
            if line.is_current and i > 3:
                # 약간의 지연 후 스크롤 (위젯 배치가 완료된 후)
                self.root.after(100, lambda idx=i: self._scroll_to_line(idx))
    
    def _scroll_to_line(self, line_index: int):
        """특정 라인으로 스크롤"""
        if line_index not in self._line_map:
            return
        
        # 해당 라인이 중앙에 오도록 스크롤
        label = self._line_map[line_index]
        
        # 위젯의 정확한 Y 좌표 얻기 (update_idletasks 필요할 수 있음)
        # self.lyrics_frame.update_idletasks() # 성능 저하 가능성 있으므로 생략 시도
        label_y = label.winfo_y()
        
        canvas_height = self.lyrics_container.winfo_height()
        scroll_region = self.lyrics_container.bbox("all")
        
        if scroll_region:
            total_height = scroll_region[3] - scroll_region[1]
            if total_height > canvas_height:
                # 중앙 정렬을 위해 캔버스 높이의 절반만큼 보정
                # target_y는 뷰포트의 상단이 되어야 할 컨텐츠의 y좌표
                target_y = max(0, label_y - canvas_height / 3) # 1/3 지점에 오도록 (가사가 좀 더 위에 보이게)
                fraction = target_y / total_height
                self.lyrics_container.yview_moveto(fraction)
    
    def show_loading(self):
        """로딩 메시지 표시"""
        for label in self._lyric_labels:
            label.destroy()
        self._lyric_labels.clear()
        
        loading = tk.Label(
            self.lyrics_frame,
            text="🔍 가사 검색 중...",
            bg="#1a1a2e",
            fg="#888888",
            font=(DEFAULT_FONT, 11)
        )
        loading.pack(pady=100)
        self._lyric_labels.append(loading)
    
    def show_not_found(self):
        """가사 없음 메시지 표시"""
        for label in self._lyric_labels:
            label.destroy()
        self._lyric_labels.clear()
        
        not_found = tk.Label(
            self.lyrics_frame,
            text="가사를 찾을 수 없습니다.\n수동으로 검색해주세요",
            bg=self._bg_color,
            fg=self._text_color,
            font=(DEFAULT_FONT, 11),
            justify="center"
        )
        not_found.pack(pady=(50, 10))
        self._lyric_labels.append(not_found)
        
        # 수동 검색 버튼 (UX 개선)
        manual_search_btn = tk.Button(
            self.lyrics_frame,
            text="수동 검색 열기",
            bg=self._bg_color,
            fg=self._highlight_color,
            activebackground=self._bg_color,
            activeforeground=self._text_color,
            relief=tk.FLAT,
            font=(DEFAULT_FONT, 10, "underline"),
            cursor="hand2",
            command=self._on_search_click
        )
        manual_search_btn.pack(pady=5)
        self._lyric_labels.append(manual_search_btn)
    
    def run(self):
        """메인 루프 시작"""
        self.root.mainloop()
    
    def schedule(self, delay_ms: int, callback: Callable):
        """콜백 예약"""
        self.root.after(delay_ms, callback)
    
    def is_alive(self) -> bool:
        """창이 살아있는지 확인"""
        try:
            return self.root.winfo_exists()
        except tk.TclError:
            return False


if __name__ == "__main__":
    # 테스트
    overlay = LyricsOverlay()
    overlay.update_track_info("Dynamite", "BTS")
    
    # 테스트 가사
    test_lines = [
        LyricDisplayLine("Cause I-I-I'm in the stars tonight", "#6A0DAD", False),
        LyricDisplayLine("So watch me bring the fire", "#EC6BAE", False),
        LyricDisplayLine("And set the night alight", "#A3D3E8", True),
        LyricDisplayLine("Shining through the city", "#41A85F", False),
        LyricDisplayLine("With a little funk and soul", "#FFD700", False),
    ]
    
    overlay.update_lyrics(test_lines)
    overlay.run()
