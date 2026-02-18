"""
가사 표시 패널.
현재 재생 중인 가사를 스크롤 가능한 캔버스에 표시합니다.
"""

import tkinter as tk
from typing import Optional

from core.models import LyricDisplayLine
from ui.widgets.theme_engine import adjust_color_brightness


class LyricsPanel(tk.Frame):
    """
    가사 표시 패널.
    현재 라인을 강조하고 자동으로 스크롤합니다.
    """

    # 스크롤 관련 상수
    _SCROLL_SENSITIVITY = 2  # 마우스 휠 감도

    def __init__(
        self,
        parent: tk.Widget,
        bg_color: str = "#1a1a2e",
        text_color: str = "#e0e0e0",
        highlight_color: str = "#e94560",
        font_family: str = "Malgun Gothic",
        font_size: int = 11,
        show_translations: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(parent, bg=bg_color, **kwargs)

        self._bg_color = bg_color
        self._text_color = text_color
        self._highlight_color = highlight_color
        self._font_family = font_family
        self._font_size = font_size
        self._show_translations = show_translations

        self._all_lines: list[LyricDisplayLine] = []
        self._current_index: int = -1
        self._status_text: str = ""
        self._line_y_positions: list[int] = [] # 각 라인의 Y 좌표 캐시

        self._create_widgets()

    def _create_widgets(self) -> None:
        """위젯 생성"""
        # 스크롤바와 캔버스
        self._canvas = tk.Canvas(
            self,
            bg=self._bg_color,
            highlightthickness=0,
        )
        # 스크롤바 제거 (마우스 휠 사용)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 캔버스 크기로 scrollregion 자동 업데이트 (필요 시)
        
        self._canvas.bind("<Configure>", self._on_resize)
        # 마우스 휠 이벤트 바인딩 (Windows/Linux/Mac 대응)
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind_all("<Button-4>", self._on_mousewheel)
        self._canvas.bind_all("<Button-5>", self._on_mousewheel)

    def update_lyrics(self, lines: list[LyricDisplayLine]) -> None:
        """
        가사 라인 업데이트.
        전체 가사를 다시 렌더링하거나, 현재 재생 중인 라인만 강조를 업데이트합니다.
        
        Args:
            lines: 표시할 전체 LyricDisplayLine 리스트
        """
        # 데이터 변경 확인 (단순 길이 비교 혹은 내용 비교)
        # is_new_song 변수명은 "전체 리렌더링 필요 여부"로 이해하면 됨
        needs_full_render = False
        
        if len(lines) != len(self._all_lines):
            needs_full_render = True
        else:
            # 모든 라인의 내용(텍스트, 번역, 발음) 비교
            # is_current나 color는 제외 (이는 highlight 업데이트로 처리됨)
            for new_line, old_line in zip(lines, self._all_lines):
                if (new_line.text != old_line.text or 
                    new_line.translation != old_line.translation or 
                    new_line.romanization != old_line.romanization):
                    needs_full_render = True
                    break
        
        self._all_lines = lines
        self._status_text = ""
        
        # 현재 재생 중인 인덱스 찾기
        new_index = next((i for i, line in enumerate(lines) if line.is_current), -1)
        
        if needs_full_render:
            self._render_all() # 내용이 바뀌었으므로 전체 다시 그리기
            
        if new_index != self._current_index:
            self._current_index = new_index
            self._update_highlight() # 강조 표시 업데이트
            self._scroll_to_current() # 현재 가사로 스크롤

    def _on_resize(self, event):
        """창 크기 변경 시 리렌더링"""
        self._render_all()

    def show_status(self, message: str) -> None:
        """상태 메시지 표시 (가사 없을 때)"""
        self._status_text = message
        self._all_lines = []
        self._current_index = -1
        self._render_all()

    def _render_all(self) -> None:
        """전체 가사 렌더링"""
        self._canvas.delete("all")
        self._line_y_positions = []
        
        canvas_width = self._canvas.winfo_width() # 이벤트 전에는 1일 수 있음
        if canvas_width <= 1: canvas_width = 380

        if self._status_text:
            self._canvas.create_text(
                canvas_width // 2,
                150, # 대략 중간
                text=self._status_text,
                fill=self._text_color,
                font=(self._font_family, self._font_size),
                anchor="center",
                width=canvas_width - 20,
                justify="center",
            )
            return

        if not self._all_lines:
            return

        y = 20 # 상단 여백
        
        for i, line in enumerate(self._all_lines):
            self._line_y_positions.append(y)
            
            # 태그 부여: line_{i}
            
            # 원문
            text_item = self._canvas.create_text(
                canvas_width // 2,
                y,
                text=line.text,
                fill=self._text_color, # 기본 색상으로 먼저 그림
                font=(self._font_family, self._font_size, "normal"),
                anchor="n",  # 상단 중앙 정렬로 변경하여 높이 계산 용이하게 함
                width=canvas_width - 40, # 스크롤바 고려하여 여백 증가
                justify="center",
                tags=(f"line_{i}", "lyric_text")
            )
            
            # 실제 그려진 텍스트의 높이 계산
            bbox = self._canvas.bbox(text_item)
            text_height = (bbox[3] - bbox[1]) if bbox else self._font_size + 6
            y += text_height + 4  # 텍스트 높이 + 약간의 패딩

            # 번역/발음 표시
            if self._show_translations:
                sub_text = line.romanization or line.translation
                if sub_text:
                    sub_color = adjust_color_brightness(self._text_color, 0.7)
                    sub_item = self._canvas.create_text(
                        canvas_width // 2,
                        y,
                        text=sub_text,
                        fill=sub_color,
                        font=(self._font_family, self._font_size - 2),
                        anchor="n",
                        width=canvas_width - 40,
                        justify="center",
                        tags=(f"line_{i}_sub", "lyric_sub")
                    )
                    
                    # 서브 텍스트 높이 계산
                    sub_bbox = self._canvas.bbox(sub_item)
                    sub_height = (sub_bbox[3] - sub_bbox[1]) if sub_bbox else self._font_size
                    y += sub_height + 2
            
            y += 12 # 줄 간격

        # 스크롤 영역 설정
        self._canvas.configure(scrollregion=(0, 0, canvas_width, y + 50)) # 하단 여백 추가

        # 현재 라인 강조 복구
        self._update_highlight()
        if self._current_index >= 0:
            self._scroll_to_current()

    def _update_highlight(self) -> None:
        """현재 라인 강조 스타일 업데이트"""
        # 모든 텍스트 기본 스타일로 초기화
        self._canvas.itemconfigure("lyric_text", fill=self._text_color, font=(self._font_family, self._font_size, "normal"))
        
        if self._current_index >= 0:
            # 현재 라인 강조
            target_tag = f"line_{self._current_index}"
            
            # 색상 결정 (라인 자체 컬러 있으면 사용)
            line = self._all_lines[self._current_index]
            highlight_color = line.color if line.color else self._highlight_color
            
            self._canvas.itemconfigure(target_tag, fill=highlight_color, font=(self._font_family, self._font_size + 1, "bold"))
            
            # 서브 텍스트는 색상 유지하되 폰트만 살짝 키울 수도/안 할 수도 (여기선 유지)

    def _scroll_to_current(self) -> None:
        """현재 가사가 화면 중앙에 오도록 스크롤"""
        if self._current_index < 0 or self._current_index >= len(self._line_y_positions):
            return

        target_y = self._line_y_positions[self._current_index]
        canvas_height = self._canvas.winfo_height()
        
        # 중앙 정렬을 위한 오프셋 계산
        # 전체 scrollregion 높이
        scrollregion = self._canvas.bbox("all")
        if not scrollregion: return
        total_height = scrollregion[3]
        
        if total_height <= canvas_height:
            return

        # 목표 위치 (화면 중앙)
        # yview_moveto는 0.0 ~ 1.0 비율을 사용
        
        # 화면 중앙에 오게 하려면: (target_y - canvas_height / 2) / total_height
        fraction = (target_y - canvas_height / 3) / total_height # 약간 상단(1/3 지점)이 더 보기 좋음
        fraction = max(0.0, min(1.0, fraction))
        
        self._canvas.yview_moveto(fraction)

    def _on_mousewheel(self, event):
        """마우스 휠 스크롤"""
        if event.delta:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120) * self._SCROLL_SENSITIVITY), "units")
        elif event.num == 5: # Linux down
            self._canvas.yview_scroll(1, "units")
        elif event.num == 4: # Linux up
            self._canvas.yview_scroll(-1, "units")


    def set_show_translations(self, show: bool) -> None:
        """번역 표시 여부 설정"""
        self._show_translations = show
        self._render_all()

    def set_colors(
        self,
        bg_color: Optional[str] = None,
        text_color: Optional[str] = None,
        highlight_color: Optional[str] = None,
    ) -> None:
        """색상 업데이트"""
        if bg_color:
            self._bg_color = bg_color
            self.config(bg=bg_color)
            self._canvas.config(bg=bg_color)
        if text_color:
            self._text_color = text_color
        if highlight_color:
            self._highlight_color = highlight_color
        self._render_all()

    def set_font(self, font_family: str, font_size: int) -> None:
        """폰트 업데이트"""
        self._font_family = font_family
        self._font_size = font_size
        self._render_all()
