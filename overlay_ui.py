"""
가사 오버레이 UI 모듈.
tkinter를 사용하여 항상 최상위에 표시되는 투명 오버레이 창을 구현합니다.
"""

import tkinter as tk
from tkinter import font as tkfont
from typing import Optional, Callable
from dataclasses import dataclass, field


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
    
    def __init__(self, master, width=300, height=30, min_val=-3000, max_val=3000, command=None, bg="#202035"):
        super().__init__(master, width=width, height=height, bg=bg, highlightthickness=0)
        self.min_val = min_val
        self.max_val = max_val
        self.cur_val = 0
        self.command = command
        
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
            width=self.bar_h, fill="#16213e", capstyle=tk.ROUND
        )
        
        # 활성 바 (중앙 0 기준)
        center_x = self._val_to_x(0)
        curr_x = self._val_to_x(self.cur_val)
        
        if self.cur_val != 0:
            self.create_line(
                center_x, cy, curr_x, cy,
                width=self.bar_h, fill="#e94560", capstyle=tk.ROUND
            )
        
        # 핸들 (Thumb)
        r = 8
        self.create_oval(
            curr_x - r, cy - r, curr_x + r, cy + r,
            fill="#ffffff", outline="#e94560", width=2
        )

    def _update_val(self, x):
        new_val = self._x_to_val(x)
        # 100ms 단위 스냅 (선택사항)
        new_val = round(new_val / 100) * 100
        
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


class LyricsOverlay:
    """가사 오버레이 창"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("YouTube Music Lyrics")
        
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
        self.root.configure(bg="#1a1a2e")
        
        # 테두리 없음
        self.root.overrideredirect(True)
        
        # 창 닫기 이벤트
        self.root.protocol("WM_DELETE_WINDOW", self._handle_close)

    def _create_widgets(self):
        """UI 위젯 생성"""
        # 메인 프레임
        self.main_frame = tk.Frame(
            self.root,
            bg="#1a1a2e",
            highlightbackground="#4a4a6a",
            highlightthickness=2
        )
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 타이틀 바 (드래그 영역)
        self.title_bar = tk.Frame(self.main_frame, bg="#16213e", height=40)
        self.title_bar.pack(fill=tk.X)
        self.title_bar.pack_propagate(False)
        
        
        # 닫기 버튼
        self.close_btn = tk.Label(
            self.title_bar,
            text="✕",
            bg="#16213e",
            fg="#888888",
            font=("Segoe UI", 14),
            cursor="hand2"
        )
        self.close_btn.pack(side=tk.RIGHT, padx=10, pady=5)
        self.close_btn.bind("<Button-1>", lambda e: self._handle_close())
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.configure(fg="#e94560"))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.configure(fg="#888888"))
        
        # 최소화 버튼
        self.min_btn = tk.Label(
            self.title_bar,
            text="─",
            bg="#16213e",
            fg="#888888",
            font=("Segoe UI", 14),
            cursor="hand2"
        )
        self.min_btn.pack(side=tk.RIGHT, padx=5, pady=5)
        self.min_btn.bind("<Button-1>", lambda e: self._toggle_minimize())
        self.min_btn.bind("<Enter>", lambda e: self.min_btn.configure(fg="#e94560"))
        self.min_btn.bind("<Leave>", lambda e: self.min_btn.configure(fg="#888888"))
        
        # 싱크 버튼
        self.sync_btn = tk.Label(
            self.title_bar,
            text="⏱",
            bg="#16213e",
            fg="#888888",
            font=("Segoe UI", 11),
            cursor="hand2",
            activeforeground="#e94560"
        )
        self.sync_btn.pack(side=tk.RIGHT, padx=5, pady=8)
        self.sync_btn.bind("<Button-1>", lambda e: self._toggle_sync_panel())
        self.sync_btn.bind("<Enter>", lambda e: self.sync_btn.configure(fg="#e94560"))
        self.sync_btn.bind("<Leave>", lambda e: self.sync_btn.configure(fg="#888888"))
        
        # 검색 버튼
        self.search_btn = tk.Label(
            self.title_bar,
            text="🔍",
            bg="#16213e",
            fg="#888888",
            font=("Segoe UI", 11),
            cursor="hand2",
            activeforeground="#e94560"
        )
        self.search_btn.pack(side=tk.RIGHT, padx=5, pady=8)
        self.search_btn.bind("<Button-1>", lambda e: self._on_search_click())
        self.search_btn.bind("<Enter>", lambda e: self.search_btn.configure(fg="#e94560"))
        self.search_btn.bind("<Leave>", lambda e: self.search_btn.configure(fg="#888888"))
        
        # 곡 정보 레이블 (버튼 배치 후 남은 공간의 왼쪽부터 차지)
        self.title_label = tk.Label(
            self.title_bar,
            text="YouTube Music Lyrics",
            bg="#16213e",
            fg="#e94560",
            font=("Segoe UI", 11, "bold"),
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
            bg="#1a1a2e",
            fg="#888888",
            font=("Segoe UI", 9),
            anchor="w"
        )
        self.artist_label.pack(fill=tk.X, padx=15, pady=(5, 0))

        # 싱크 조절 패널 (기본 숨김)
        self.sync_frame = tk.Frame(self.main_frame, bg="#202035", height=0)
        # pack은 _toggle_sync_panel에서 처리
        
        # 커스텀 슬라이더로 교체
        self.sync_slider = RoundedSlider(
            self.sync_frame,
            min_val=-5000,
            max_val=5000,
            bg="#202035",
            command=self._on_slider_move
        )
        self.sync_slider.pack(fill=tk.X, padx=20, pady=(10, 5))
        
        self.sync_label = tk.Label(
            self.sync_frame,
            text="싱크 조절: 0.0s",
            bg="#202035",
            fg="#cccccc",
            font=("Segoe UI", 9)
        )
        self.sync_label.pack(pady=(0, 10))
        
        # 설정 패널 (기본 숨김)
        self.settings_frame = tk.Frame(self.main_frame, bg="#202035")
        # pack은 _toggle_settings_panel에서 처리
        
        # 다중 소스 검색 체크박스
        self._multi_source_var = tk.BooleanVar(value=False)
        self.multi_source_check = tk.Checkbutton(
            self.settings_frame,
            text="다중 소스 검색 (더 정확, 더 느림)",
            variable=self._multi_source_var,
            bg="#202035",
            fg="#cccccc",
            selectcolor="#16213e",
            activebackground="#202035",
            activeforeground="#e94560",
            font=("Segoe UI", 9),
            command=self._on_settings_changed
        )
        self.multi_source_check.pack(anchor="w", padx=20, pady=10)
        
        # 검색 패널 (기본 숨김)
        self.search_frame = tk.Frame(self.main_frame, bg="#202035")
        # pack은 _toggle_search_panel에서 처리
        
        # 검색 입력 필드들
        search_input_frame = tk.Frame(self.search_frame, bg="#202035")
        search_input_frame.pack(fill=tk.X, padx=15, pady=10)
        
        tk.Label(search_input_frame, text="아티스트", bg="#202035", fg="#888888", font=("Segoe UI", 8)).pack(anchor="w")
        self.search_artist_entry = tk.Entry(search_input_frame, bg="#16213e", fg="white", insertbackground="white", relief=tk.FLAT, font=("Segoe UI", 9))
        self.search_artist_entry.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(search_input_frame, text="제목", bg="#202035", fg="#888888", font=("Segoe UI", 8)).pack(anchor="w")
        self.search_title_entry = tk.Entry(search_input_frame, bg="#16213e", fg="white", insertbackground="white", relief=tk.FLAT, font=("Segoe UI", 9))
        self.search_title_entry.pack(fill=tk.X)
        
        # 검색 버튼과 상태
        search_btn_frame = tk.Frame(self.search_frame, bg="#202035")
        search_btn_frame.pack(fill=tk.X, padx=15, pady=(5, 0))
        
        self.do_search_btn = tk.Button(search_btn_frame, text="검색", bg="#e94560", fg="white", relief=tk.FLAT, font=("Segoe UI", 9), command=self._do_search)
        self.do_search_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.search_status_label = tk.Label(search_btn_frame, text="", bg="#202035", fg="#888888", font=("Segoe UI", 8))
        self.search_status_label.pack(side=tk.LEFT)
        
        # 검색 결과 리스트
        self.search_listbox = tk.Listbox(self.search_frame, bg="#16213e", fg="white", selectbackground="#e94560", relief=tk.FLAT, height=4, font=("Segoe UI", 8))
        self.search_listbox.pack(fill=tk.X, padx=15, pady=5)
        
        # 적용 버튼
        self.apply_search_btn = tk.Button(self.search_frame, text="선택한 가사 적용", bg="#202035", fg="white", relief=tk.FLAT, font=("Segoe UI", 9), command=self._apply_selected_lyrics)
        self.apply_search_btn.pack(fill=tk.X, padx=15, pady=(0, 10))

        # 가사 컨테이너
        self.lyrics_container = tk.Canvas(
            self.main_frame,
            bg="#1a1a2e",
            highlightthickness=0
        )
        self.lyrics_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 가사 내부 프레임
        self.lyrics_frame = tk.Frame(self.lyrics_container, bg="#1a1a2e")
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
            bg="#1a1a2e",
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
            bg="#1a1a2e",
            fg="#4a4a6a",
            font=("Segoe UI", 10),
            cursor="hand2"
        )
        self.settings_btn.place(relx=1.0, rely=1.0, anchor="se", x=-25)
        self.settings_btn.bind("<Button-1>", lambda e: self._on_settings_click())
        self.settings_btn.bind("<Enter>", lambda e: self.settings_btn.configure(fg="#e94560"))
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
            bg="#1a1a2e",
            fg="#888888",
            font=("Segoe UI", 12),
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
            self.lyrics_container.pack_forget()
            self.artist_label.pack_forget()
            self.root.geometry(f"{self.root.winfo_width()}x45")
        else:
            self.artist_label.pack(fill=tk.X, padx=15, pady=(5, 0))
            self.lyrics_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            self.root.geometry(f"{self.root.winfo_width()}x500")
    
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
            

            

    def _on_settings_click(self):
        """설정 버튼 클릭 시 - 패널 토글"""
        self._toggle_settings_panel()

    def _toggle_settings_panel(self):
        """설정 패널 토글"""
        # 다른 패널 닫기
        if self.search_frame.winfo_viewable():
            self.search_frame.pack_forget()
            self.search_btn.configure(fg="#888888")
        
        if self.settings_frame.winfo_viewable():
            self.settings_frame.pack_forget()
            self.settings_btn.configure(fg="#4a4a6a")
        else:
            self.settings_frame.pack(fill=tk.X, after=self.artist_label)
            self.settings_btn.configure(fg="#e94560")

    def _on_settings_changed(self):
        """설정 변경 시 콜백 호출"""
        if self._on_save_settings_callback:
            new_settings = {"multi_source_search": self._multi_source_var.get()}
            self._on_save_settings_callback(new_settings)
    
    def set_on_settings_save(self, callback: Callable[[dict], None]):
        """설정 저장 콜백 설정"""
        self._on_save_settings_callback = callback
    
    def update_settings_ui(self, settings: dict):
        """설정 UI 업데이트"""
        self._multi_source_var.set(settings.get("multi_source_search", False))

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
            font=("Segoe UI", 12, "bold"),
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
        
        # 기존 라벨 제거
        for label in self._lyric_labels:
            label.destroy()
        self._lyric_labels.clear()
        
        if not lines:
            self._show_placeholder()
            return
        
        # 폰트 설정
        normal_font = tkfont.Font(family="Segoe UI", size=11)
        highlight_font = tkfont.Font(family="Segoe UI", size=13, weight="bold")
        sub_font = tkfont.Font(family="Segoe UI", size=9)  # 번역/발음용 작은 폰트
        
        current_y = 0
        
        for i, line in enumerate(lines):
            # 현재 줄 하이라이트
            if line.is_current:
                bg_color = "#252540"
                text_font = highlight_font
            else:
                bg_color = "#1a1a2e"
                text_font = normal_font
            
            # 메인 가사 라벨
            label = tk.Label(
                self.lyrics_frame,
                text=line.text,
                bg=bg_color,
                fg=line.color,
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
            font=("Segoe UI", 11)
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
            text="😢 가사를 찾을 수 없습니다",
            bg="#1a1a2e",
            fg="#888888",
            font=("Segoe UI", 11)
        )
        not_found.pack(pady=100)
        self._lyric_labels.append(not_found)
    
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
