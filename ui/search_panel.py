"""
가사 수동 검색 패널.
자동 검색에 실패했을 때 사용자가 직접 검색어를 입력하여 가사를 찾습니다.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional


class SearchPanel(tk.Frame):
    """가사 수동 검색 패널"""

    def __init__(
        self,
        parent: tk.Widget,
        bg_color: str = "#1a1a2e",
        panel_color: str = "#16213e",
        text_color: str = "#e0e0e0",
        highlight_color: str = "#e94560",
        on_search: Optional[Callable[[str, str], None]] = None,
        on_apply: Optional[Callable[[str, str], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            parent,
            bg=panel_color,
            highlightthickness=1,
            highlightbackground=highlight_color,
            **kwargs
        )

        self._bg_color = bg_color
        self._panel_color = panel_color
        self._text_color = text_color
        self._highlight_color = highlight_color
        self._on_search = on_search
        self._on_apply = on_apply

        self._search_results: list[tuple[str, str]] = []  # [(provider, lrc_text), ...]

        self._create_widgets()

    def _create_widgets(self) -> None:
        """위젯 생성"""
        # 헤더
        tk.Label(
            self,
            text="🔍 가사 검색",
            bg=self._panel_color,
            fg=self._text_color,
            font=("Malgun Gothic", 10, "bold"),
        ).pack(anchor="w", padx=10, pady=(6, 2))

        # 검색 입력 행
        input_frame = tk.Frame(self, bg=self._panel_color)
        input_frame.pack(fill=tk.X, padx=10, pady=1)

        tk.Label(
            input_frame,
            text="제목:",
            bg=self._panel_color,
            fg=self._text_color,
        ).pack(side=tk.LEFT, padx=(0, 4))

        self._title_entry = tk.Entry(
            input_frame,
            bg=self._bg_color,
            fg=self._text_color,
            insertbackground=self._text_color,
            relief=tk.FLAT,
            bd=2,
        )
        self._title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        artist_frame = tk.Frame(self, bg=self._panel_color)
        artist_frame.pack(fill=tk.X, padx=10, pady=1)

        tk.Label(
            artist_frame,
            text="아티스트:",
            bg=self._panel_color,
            fg=self._text_color,
        ).pack(side=tk.LEFT, padx=(0, 4))

        self._artist_entry = tk.Entry(
            artist_frame,
            bg=self._bg_color,
            fg=self._text_color,
            insertbackground=self._text_color,
            relief=tk.FLAT,
            bd=2,
        )
        self._artist_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 검색 버튼
        btn_frame = tk.Frame(self, bg=self._panel_color)
        btn_frame.pack(fill=tk.X, padx=10, pady=(2, 4))

        self._search_btn = tk.Button(
            btn_frame,
            text="검색",
            bg=self._highlight_color,
            fg="#ffffff",
            relief=tk.FLAT,
            command=self._do_search,
        )
        self._search_btn.pack(side=tk.LEFT)

        self._status_label = tk.Label(
            btn_frame,
            text="",
            bg=self._panel_color,
            fg=self._text_color,
            font=("Malgun Gothic", 9),
        )
        self._status_label.pack(side=tk.LEFT, padx=8)

        # 결과 목록
        self._result_listbox = tk.Listbox(
            self,
            bg=self._bg_color,
            fg=self._text_color,
            selectbackground=self._highlight_color,
            relief=tk.FLAT,
            height=4,
        )
        self._result_listbox.pack(fill=tk.X, padx=10, pady=2)
        self._result_listbox.bind("<Double-Button-1>", self._on_result_double_click)

        # 적용 버튼
        self._apply_btn = tk.Button(
            self,
            text="선택한 가사 적용",
            bg=self._panel_color,
            fg=self._text_color,
            relief=tk.FLAT,
            state=tk.DISABLED,
            command=self._apply_selected,
        )
        self._apply_btn.pack(padx=10, pady=(2, 8))

        # Enter 키 바인딩
        self._title_entry.bind("<Return>", lambda e: self._do_search())
        self._artist_entry.bind("<Return>", lambda e: self._do_search())

    def set_suggestion(self, title: str, artist: str) -> None:
        """검색 제안 설정 (현재 트랙 기반)"""
        self._title_entry.delete(0, tk.END)
        self._title_entry.insert(0, title)
        self._artist_entry.delete(0, tk.END)
        self._artist_entry.insert(0, artist)

    def _do_search(self) -> None:
        """검색 실행"""
        title = self._title_entry.get().strip()
        artist = self._artist_entry.get().strip()

        if not title:
            self._status_label.config(text="제목을 입력해주세요.")
            return

        self._status_label.config(text="검색 중...")
        self._search_btn.config(state=tk.DISABLED)
        self._result_listbox.delete(0, tk.END)
        self._apply_btn.config(state=tk.DISABLED)

        if self._on_search:
            self._on_search(title, artist)

    def show_results(self, results: list[tuple[str, str]]) -> None:
        """검색 결과 표시"""
        self._search_results = results
        self._result_listbox.delete(0, tk.END)
        self._search_btn.config(state=tk.NORMAL)

        if not results:
            self._status_label.config(text="결과 없음")
            return

        self._status_label.config(text=f"{len(results)}개 결과")
        for prov, _ in results:
            self._result_listbox.insert(tk.END, f"  📄 {prov}")

        self._apply_btn.config(state=tk.NORMAL)

    def _on_result_double_click(self, event: tk.Event) -> None:
        """결과 더블클릭 시 적용"""
        self._apply_selected()

    def _apply_selected(self) -> None:
        """선택된 가사 적용"""
        selection = self._result_listbox.curselection()
        if not selection:
            if self._search_results:
                idx = 0
            else:
                return
        else:
            idx = selection[0]

        if idx < len(self._search_results):
            prov, lrc_text = self._search_results[idx]
            if self._on_apply:
                self._on_apply(lrc_text, prov)
