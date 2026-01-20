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
        
        # 곡 정보 레이블
        self.title_label = tk.Label(
            self.title_bar,
            text="YouTube Music Lyrics",
            bg="#16213e",
            fg="#e94560",
            font=("Segoe UI", 11, "bold"),
            anchor="w"
        )
        self.title_label.pack(side=tk.LEFT, padx=10, pady=8)
        
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
        
        self.sync_slider = tk.Scale(
            self.sync_frame,
            from_=-3000,
            to=3000,
            orient=tk.HORIZONTAL,
            bg="#202035",
            fg="#e94560",
            troughcolor="#16213e",
            highlightthickness=0,
            showvalue=0, # 값은 별도 라벨로 표시
            command=self._on_slider_move
        )
        self.sync_slider.pack(fill=tk.X, padx=20, pady=(5, 0))
        
        self.sync_label = tk.Label(
            self.sync_frame,
            text="싱크 조절: 0.0s",
            bg="#202035",
            fg="#cccccc",
            font=("Segoe UI", 9)
        )
        self.sync_label.pack(pady=(0, 5))

        # 가사 컨테이너 (스크롤 가능)
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
            
    def _on_slider_move(self, value):
        """슬라이더 이동 시"""
        offset = int(value)
        sign = "+" if offset > 0 else ""
        sec = offset / 1000.0
        
        self.sync_label.configure(text=f"싱크 조절: {sign}{sec}s")
        
        if self._on_sync_adjust_callback:
            self._on_sync_adjust_callback(offset)
            
    def _on_search_click(self):
        """검색 버튼 클릭 시"""
        if self._on_search_callback:
            self._on_search_callback()

    def set_on_search_request(self, callback: Callable):
        """검색 요청 콜백 설정"""
        self._on_search_callback = callback

    def show_search_popup(self, current_title, current_artist, search_action: Callable[[str, str], list], apply_action: Callable[[str, str], None]):
        """검색 팝업 표시"""
        popup = tk.Toplevel(self.root)
        popup.title("가사 검색")
        popup.geometry("400x500")
        popup.configure(bg="#1a1a2e")
        popup.resizable(False, False)
        
        # 항상 위에
        popup.attributes('-topmost', True)
        
        # 입력 필드
        input_frame = tk.Frame(popup, bg="#1a1a2e", pady=10)
        input_frame.pack(fill=tk.X, padx=10)
        
        tk.Label(input_frame, text="아티스트", bg="#1a1a2e", fg="#888888").pack(anchor="w")
        artist_entry = tk.Entry(input_frame, bg="#16213e", fg="white", insertbackground="white", relief=tk.FLAT)
        artist_entry.insert(0, current_artist)
        artist_entry.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(input_frame, text="제목", bg="#1a1a2e", fg="#888888").pack(anchor="w")
        title_entry = tk.Entry(input_frame, bg="#16213e", fg="white", insertbackground="white", relief=tk.FLAT)
        title_entry.insert(0, current_title)
        title_entry.pack(fill=tk.X)
        
        # 검색 버튼
        def do_search():
            status_label.configure(text="검색 중...", fg="#ffff00")
            popup.update()
            
            t = title_entry.get()
            a = artist_entry.get()
            
            # 비동기 실행을 위해 스레드 사용 권장되지만, 여기선 콜백 내에서 처리
            # 메인 스레드 블로킹 방지를 위해 root.after 사용 등 고려해야 함.
            # 지금은 main.py에서 스레드로 처리하고 리스트 업데이트를 호출하는 방식이 이상적.
            # 하지만 간단하게 여기서 콜백을 호출하고 결과를 기다리는 구조로 (약간의 프리징 감수)
            
            results = search_action(t, a)
            
            listbox.delete(0, tk.END)
            self._search_results = results # 임시 저장
            
            if not results:
                status_label.configure(text="검색 결과가 없습니다.", fg="#ff6b6b")
            else:
                status_label.configure(text=f"{len(results)}개의 결과", fg="#00ff00")
                for prov, lrc in results:
                    # 미리보기 (첫 줄)
                    preview = lrc.strip().split('\n')[0][:30]
                    listbox.insert(tk.END, f"[{prov}] {preview}...")
        
        search_btn = tk.Button(input_frame, text="검색", command=do_search, bg="#e94560", fg="white", relief=tk.FLAT)
        search_btn.pack(fill=tk.X, pady=10)
        
        status_label = tk.Label(input_frame, text="", bg="#1a1a2e", fg="#888888")
        status_label.pack()
        
        # 결과 리스트
        list_frame = tk.Frame(popup, bg="#1a1a2e")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        listbox = tk.Listbox(list_frame, bg="#16213e", fg="white", selectbackground="#e94560", relief=tk.FLAT)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.config(yscrollcommand=scrollbar.set)
        
        # 적용 버튼
        def apply_selected():
            idx = listbox.curselection()
            if not idx:
                return
            
            selected_idx = idx[0]
            prov, lrc_content = self._search_results[selected_idx]
            
            # 적용
            apply_action(lrc_content, f"{prov} 검색 결과")
            popup.destroy()
            
        apply_btn = tk.Button(popup, text="선택한 가사 적용", command=apply_selected, bg="#202035", fg="white", relief=tk.FLAT)
        apply_btn.pack(fill=tk.X, padx=10, pady=10)

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
            new_val = max(-3000, min(3000, current + delta))
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
