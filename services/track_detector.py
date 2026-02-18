"""
현재 재생 중인 YouTube Music 곡 정보를 감지합니다.
1순위: Windows Media Session API (폴링)
2순위: 브라우저 창 제목 파싱
"""

import re
from typing import Optional, Callable

import win32gui

from core.constants import BROWSER_WINDOW_CLASSES
from core.models import TrackInfo

# Media Session 모듈 임포트 (선택적)
try:
    from services.media_session import get_current_media, is_youtube_music
    MEDIA_SESSION_AVAILABLE = True
except ImportError:
    MEDIA_SESSION_AVAILABLE = False


class TrackDetector:
    """YouTube Music 곡 정보를 감지"""

    # YouTube Music 탭 제목에서 곡 정보 부분 추출
    _YT_MUSIC_PATTERN = re.compile(r"^(.+?)\s*[|]\s*YouTube Music$")

    def __init__(self) -> None:
        self._current_track: Optional[TrackInfo] = None
        self._callbacks: list[Callable[[TrackInfo], None]] = []
        self._use_media_session = MEDIA_SESSION_AVAILABLE

    @property
    def is_event_mode(self) -> bool:
        """이벤트 모드 활성화 여부 (현재 비활성화 - asyncio 충돌 문제)"""
        return False

    def get_current_track(self) -> Optional[TrackInfo]:
        """현재 재생 중인 곡 정보 반환 (Media Session API 우선)"""

        # 1순위: Windows Media Session API (백그라운드 재생 지원)
        if self._use_media_session:
            try:
                media = get_current_media()
                if media and media.title:
                    print(f"[MediaSession] 감지: {media.title} - {media.artist}")
                    return TrackInfo(
                        title=media.title,
                        artist=media.artist if media.artist else "Unknown Artist",
                        duration_ms=media.duration_ms,
                    )
            except Exception as e:
                print(f"[MediaSession] 오류, 창 제목 방식으로 폴백: {e}")

        # 2순위: 브라우저 창 제목 파싱
        for title in self._find_youtube_music_windows():
            track = self._parse_title(title)
            if track:
                return track

        return None

    def _find_youtube_music_windows(self) -> list[str]:
        """모든 브라우저에서 YouTube Music 탭 찾기"""
        titles: list[str] = []
        all_browser_titles: list[str] = []

        def enum_callback(hwnd: int, results: list) -> bool:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            try:
                class_name = win32gui.GetClassName(hwnd)
                if class_name in BROWSER_WINDOW_CLASSES:
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        all_browser_titles.append(title)
                        if "YouTube Music" in title:
                            results.append(title)
            except Exception:
                pass
            return True

        win32gui.EnumWindows(enum_callback, titles)

        if not titles and all_browser_titles:
            print(f"[디버그] YouTube Music 창 없음. 브라우저 창들: {all_browser_titles[:3]}")

        return titles

    def _parse_title(self, window_title: str) -> Optional[TrackInfo]:
        """창 제목에서 곡 정보 추출"""
        match = self._YT_MUSIC_PATTERN.match(window_title)
        if not match:
            return None

        raw_info = match.group(1).strip()
        title, artist = self._extract_title_artist(raw_info)
        return TrackInfo(title=title, artist=artist)

    def _extract_title_artist(self, raw_info: str) -> tuple[str, str]:
        """
        다양한 형식의 곡 정보에서 제목과 아티스트 추출

        지원 형식:
        - "곡 제목 / 아티스트 COVER" (우선 처리)
        - "곡 제목 - 아티스트"
        - "곡 제목" (아티스트 없음)
        """
        # " / " 구분자 (커버곡 등에서 자주 사용됨, " - "보다 우선순위 높음)
        if " / " in raw_info:
            parts = raw_info.split(" / ", 1)
            return parts[0].strip(), parts[1].strip()

        # " - " 구분자 (가장 일반적)
        if " - " in raw_info:
            parts = raw_info.split(" - ", 1)
            return parts[0].strip(), parts[1].strip()

        # 괄호 안에 아티스트 (feat, ft 등)
        feat_match = re.search(
            r"\s*[\(\[](?:feat\.?|ft\.?|featuring)\s*([^\)\]]+)[\)\]]",
            raw_info,
            re.IGNORECASE,
        )
        if feat_match:
            artist = feat_match.group(1).strip()
            title = re.sub(
                r"\s*[\(\[](?:feat\.?|ft\.?|featuring)[^\)\]]+[\)\]]",
                "",
                raw_info,
                flags=re.IGNORECASE,
            ).strip()
            return title, artist

        return raw_info, "Unknown Artist"

    def on_track_change(self, callback: Callable[[TrackInfo], None]) -> None:
        """곡 변경 시 호출될 콜백 등록"""
        self._callbacks.append(callback)

    def check_for_changes(self) -> bool:
        """곡 변경 확인 및 콜백 호출. 변경되었으면 True 반환"""
        new_track = self.get_current_track()
        if new_track != self._current_track:
            self._current_track = new_track
            if new_track:
                for callback in self._callbacks:
                    callback(new_track)
            return True
        return False
