"""
가사 오버레이 ViewModel.
기존 main.py의 LyricsApp에서 비즈니스 로직을 추출하여 UI와 분리합니다.

책임:
- 현재 재생 트랙 상태 관리
- 가사 동기화 로직
- 번역 작업 스레드 제어
- 싱크 오프셋 관리
- 검색 쿼리 생성
- View에 변경 알림 (콜백 기반)
"""

import re
import threading
import time
from typing import Callable, Optional

from core.constants import (
    POLL_INTERVAL_MS,
    POLL_INTERVAL_SLOW_MS,
    SYNC_INTERVAL_MS,
    SYNC_INTERVAL_SLOW_MS,
)
from core.models import LyricDisplayLine, LyricLine, TrackInfo
from services.lyrics_fetcher import LyricsFetcher
from services.lyrics_parser import LyricsParser
from services.track_detector import TrackDetector
from settings.settings_manager import SettingsManager

# 선택적 모듈
try:
    from services.media_session import get_playback_position_ms
    TIMELINE_AVAILABLE = True
except ImportError:
    TIMELINE_AVAILABLE = False
    get_playback_position_ms = lambda: None  # noqa: E731

try:
    from services.translator import LyricsTranslator
    TRANSLATION_AVAILABLE = True
except ImportError:
    TRANSLATION_AVAILABLE = False
    LyricsTranslator = None  # type: ignore


# 현재 가사 색상 (설정에서 가져오지 않는 기본 색상)
_DEFAULT_LYRIC_COLOR = "#e0e0e0"
_HIGHLIGHT_LYRIC_COLOR = "#ff6b6b"


class LyricsViewModel:
    """
    가사 오버레이 ViewModel.
    View(UI)는 이 클래스의 콜백을 통해 상태 변화를 수신합니다.
    """

    def __init__(
        self,
        settings: SettingsManager,
        track_detector: TrackDetector,
        lyrics_fetcher: LyricsFetcher,
        lyrics_parser: LyricsParser,
        translator: Optional["LyricsTranslator"] = None,
    ) -> None:
        self._settings = settings
        self._track_detector = track_detector
        self._lyrics_fetcher = lyrics_fetcher
        self._lyrics_parser = lyrics_parser
        self._translator = translator

        # ── 상태 변수 ──────────────────────────────────────────────────────────
        self._current_track: Optional[TrackInfo] = None
        self._current_lyrics: list[LyricLine] = []
        self._current_line_index: int = -1
        self._sync_offset: int = 0  # 싱크 오프셋 (ms)

        # ── 번역 스레드 제어 ───────────────────────────────────────────────────
        self._translation_thread: Optional[threading.Thread] = None
        self._stop_translation: bool = False

        # ── View 콜백 (UI가 등록) ──────────────────────────────────────────────
        self._on_lyrics_updated: Optional[Callable[[list[LyricDisplayLine]], None]] = None
        self._on_track_updated: Optional[Callable[[str, str], None]] = None
        self._on_loading: Optional[Callable[[str], None]] = None
        self._on_search_results: Optional[Callable[[list], None]] = None
        self._on_sync_reset: Optional[Callable[[], None]] = None

        # ── 스케줄러 콜백 (UI가 after()로 실행) ───────────────────────────────
        self._schedule_fn: Optional[Callable[[int, Callable], None]] = None
        self._is_minimized_fn: Optional[Callable[[], bool]] = None
        self._is_alive_fn: Optional[Callable[[], bool]] = None

    # ── 콜백 등록 ─────────────────────────────────────────────────────────────

    def set_on_lyrics_updated(self, callback: Callable[[list[LyricDisplayLine]], None]) -> None:
        self._on_lyrics_updated = callback

    def set_on_track_updated(self, callback: Callable[[str, str], None]) -> None:
        self._on_track_updated = callback

    def set_on_loading(self, callback: Callable[[str], None]) -> None:
        self._on_loading = callback

    def set_on_search_results(self, callback: Callable[[list], None]) -> None:
        self._on_search_results = callback

    def set_on_sync_reset(self, callback: Callable[[], None]) -> None:
        self._on_sync_reset = callback

    def set_schedule_fn(self, fn: Callable[[int, Callable], None]) -> None:
        """UI의 after() 래퍼 함수 등록"""
        self._schedule_fn = fn

    def set_is_minimized_fn(self, fn: Callable[[], bool]) -> None:
        self._is_minimized_fn = fn

    def set_is_alive_fn(self, fn: Callable[[], bool]) -> None:
        self._is_alive_fn = fn

    # ── 스케줄링 ──────────────────────────────────────────────────────────────

    def _is_alive(self) -> bool:
        return self._is_alive_fn() if self._is_alive_fn else False

    def _is_minimized(self) -> bool:
        return self._is_minimized_fn() if self._is_minimized_fn else False

    def _schedule(self, ms: int, fn: Callable) -> None:
        if self._schedule_fn:
            self._schedule_fn(ms, fn)

    # ── 폴링 스케줄 ───────────────────────────────────────────────────────────

    def start_polling(self) -> None:
        """곡 감지 폴링 시작"""
        self._check_track()
        self._schedule_track_check()
        if TIMELINE_AVAILABLE:
            self._schedule_lyrics_sync()

    def _schedule_track_check(self) -> None:
        if not self._is_alive():
            return
        self._check_track()
        interval = POLL_INTERVAL_SLOW_MS if self._is_minimized() else POLL_INTERVAL_MS
        self._schedule(interval, self._schedule_track_check)

    def _schedule_lyrics_sync(self) -> None:
        if not self._is_alive():
            return
        if not self._is_minimized():
            self._sync_lyrics()
        interval = SYNC_INTERVAL_SLOW_MS if self._is_minimized() else SYNC_INTERVAL_MS
        self._schedule(interval, self._schedule_lyrics_sync)

    # ── 트랙 감지 ─────────────────────────────────────────────────────────────

    def _check_track(self) -> None:
        """현재 곡 확인 및 업데이트"""
        track = self._track_detector.get_current_track()
        if track != self._current_track:
            self._current_track = track
            self._current_line_index = -1
            self._sync_offset = 0
            self._current_lyrics = []
            self._stop_translation = True

            if self._on_sync_reset:
                self._on_sync_reset()

            if track:
                self._on_track_changed(track)
            elif self._on_lyrics_updated:
                self._on_lyrics_updated([])

    def _on_track_changed(self, track: TrackInfo) -> None:
        """곡 변경 처리"""
        print(f"곡 변경 감지: {track.title} - {track.artist}")

        if self._on_track_updated:
            self._on_track_updated(track.title, track.artist)
        if self._on_loading:
            self._on_loading("🎵 가사를 검색하는 중...")

        def fetch_lyrics() -> None:
            multi_source = self._settings.get("multi_source_search", False)
            lyrics_text = self._lyrics_fetcher.search_lyrics(
                track.title, track.artist, track.duration_ms, multi_source=multi_source
            )

            if not self._is_alive() or self._current_track != track:
                return

            if lyrics_text:
                self._current_lyrics = self._lyrics_parser.parse(lyrics_text)
                self._current_line_index = -1
                self._schedule(0, self._notify_lyrics_updated)

                if self._translator:
                    self._start_translation(track)
            else:
                print("[가사] 자동검색 실패, 수동검색 패널 표시")
                if self._on_loading:
                    self._schedule(0, lambda: self._on_loading("❌ 가사를 찾을 수 없습니다. 수동으로 검색해 주세요."))

        threading.Thread(target=fetch_lyrics, daemon=True).start()

    # ── 가사 동기화 ───────────────────────────────────────────────────────────

    def _sync_lyrics(self) -> None:
        """현재 재생 시간에 맞춰 가사 동기화"""
        if not self._current_lyrics:
            return

        position_ms = get_playback_position_ms()
        if position_ms is None:
            return

        # 오프셋 적용: 양수 오프셋 = 가사 지연
        effective_position = position_ms - self._sync_offset
        new_index = self._find_current_line(effective_position)

        if new_index != self._current_line_index:
            self._current_line_index = new_index
            self._notify_lyrics_updated()

    def _find_current_line(self, current_time_ms: int) -> int:
        """현재 시간에 해당하는 가사 라인 인덱스 찾기"""
        current_idx = -1
        for i, line in enumerate(self._current_lyrics):
            if line.timestamp_ms is not None and line.timestamp_ms <= current_time_ms:
                current_idx = i
            elif line.timestamp_ms is not None and line.timestamp_ms > current_time_ms:
                break
        return current_idx

    def adjust_sync(self, offset_ms: int) -> None:
        """싱크 조절 핸들러 (절대값)"""
        self._sync_offset = offset_ms
        self._sync_lyrics()

    # ── 가사 표시 ─────────────────────────────────────────────────────────────

    def get_display_lines(self) -> list[LyricDisplayLine]:
        """현재 상태를 기반으로 View에 전달할 표시용 라인 생성"""
        if not self._current_lyrics:
            return []

        # 설정에서 색상 가져오기
        highlight_color = self._settings.get("highlight_color", _HIGHLIGHT_LYRIC_COLOR)
        text_color = self._settings.get("text_color", _DEFAULT_LYRIC_COLOR)

        display_lines: list[LyricDisplayLine] = []
        for i, line in enumerate(self._current_lyrics):
            is_current = (
                (i == self._current_line_index)
                if self._current_line_index >= 0
                else (i == 0)
            )
            display_lines.append(
                LyricDisplayLine(
                    text=line.text,
                    color=highlight_color if is_current else text_color,
                    is_current=is_current,
                    translation=line.translation,
                    romanization=line.romanization,
                )
            )
        return display_lines

    def _notify_lyrics_updated(self) -> None:
        """View에 가사 업데이트 알림"""
        if self._on_lyrics_updated:
            self._on_lyrics_updated(self.get_display_lines())

    # ── 번역 ──────────────────────────────────────────────────────────────────

    def _start_translation(self, track: TrackInfo) -> None:
        """번역 작업 시작"""
        self._stop_translation = False

        def translate_worker() -> None:
            lyrics_texts = [line.text for line in self._current_lyrics if line.text]
            if not self._translator.should_translate_lyrics(lyrics_texts):
                print("[번역] 번역 불필요 (언어 감지 결과)")
                return

            print("[번역] 일괄 번역 작업 시작...")
            texts_to_translate = [line.text for line in self._current_lyrics]

            for batch_start in range(0, len(texts_to_translate), 10):
                if self._stop_translation or self._current_track != track:
                    print("[번역] 작업 중단됨")
                    break

                batch_end = min(batch_start + 10, len(texts_to_translate))
                batch_texts = texts_to_translate[batch_start:batch_end]

                try:
                    results = self._translator.translate_batch(batch_texts)
                    for i, result in enumerate(results):
                        if result:
                            line_idx = batch_start + i
                            if line_idx < len(self._current_lyrics):
                                self._current_lyrics[line_idx].translation = result.translation
                                self._current_lyrics[line_idx].romanization = result.romanization

                    if self._is_alive():
                        # UI 업데이트 알림 (Queue를 통해 메인 스레드에서 처리되므로 직접 호출 가능)
                        self._notify_lyrics_updated()
                except Exception as e:
                    print(f"[번역] 배치 처리 오류: {e}")

            print("[번역] 작업 완료")

        self._translation_thread = threading.Thread(target=translate_worker, daemon=True)
        self._translation_thread.start()

    # ── 검색 관련 ─────────────────────────────────────────────────────────────

    def get_search_suggestion(self) -> tuple[str, str]:
        """
        현재 트랙 정보를 기반으로 검색 제안 (제목, 아티스트) 반환.
        제목에서 원곡 아티스트를 추출 시도합니다.
        """
        if not self._current_track:
            return "", ""

        current_title = self._current_track.title
        current_artist = self._current_track.artist

        # 제목에서 원곡 아티스트 추출 시도 (괄호 내용)
        extracted = re.findall(r"[\[\(\{]([^\]\)\}]+)[\]\)\}]", current_title)
        suggested_artist = current_artist

        for feat in extracted:
            if " - " in feat:
                parts = feat.split(" - ")
                suggested_artist = parts[1].strip() if len(parts) > 1 else parts[0].strip()
                break
            elif not re.search(r"(?i)(cover|커버)", feat) and len(feat) > 2:
                suggested_artist = feat.strip()
                break

        # 정제된 제목 (괄호 제거)
        clean_title = re.sub(r"[\[\(\{].*?[\]\)\}]", "", current_title)
        clean_title = re.sub(r"\s+", " ", clean_title).strip()
        if " / " in clean_title:
            clean_title = clean_title.split(" / ")[0].strip()

        return clean_title, suggested_artist

    def do_search(self, title: str, artist: str) -> list:
        """가사 검색 실행 후 후보 목록 반환"""
        query = f"{artist} {title}"
        return self._lyrics_fetcher.search_candidates(query)

    def apply_lyrics(self, lrc_content: str, source_name: str) -> None:
        """수동 선택된 가사 적용"""
        print(f"[수동적용] 선택된 가사 적용 (출처: {source_name})")

        self._current_lyrics = self._lyrics_parser.parse(lrc_content)
        self._current_line_index = -1
        self._sync_offset = 0

        if self._on_sync_reset:
            self._on_sync_reset()

        self._schedule(0, self._notify_lyrics_updated)

        if self._current_track:
            cache_key = self._lyrics_fetcher._get_cache_key(
                self._current_track.title, self._current_track.artist
            )
            self._lyrics_fetcher._save_to_cache(cache_key, lrc_content)

        if self._translator and self._current_track:
            self._stop_translation = True
            threading.Thread(
                target=lambda: (time.sleep(0.5), self._start_translation(self._current_track)),
                daemon=True,
            ).start()

    # ── 종료 ──────────────────────────────────────────────────────────────────

    def stop(self) -> None:
        """ViewModel 종료 처리"""
        self._stop_translation = True
