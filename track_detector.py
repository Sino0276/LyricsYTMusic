"""
현재 재생 중인 YouTube Music 곡 정보를 감지합니다.
1순위: Windows Media Session API (백그라운드에서도 작동)
2순위: 브라우저 창 제목 파싱
"""

import re
import win32gui
from dataclasses import dataclass
from typing import Optional, Callable

# Media Session 모듈 임포트
try:
    from media_session import get_current_media, is_youtube_music
    MEDIA_SESSION_AVAILABLE = True
except ImportError:
    MEDIA_SESSION_AVAILABLE = False


@dataclass
class TrackInfo:
    """현재 재생 중인 곡 정보"""
    title: str
    artist: str
    duration_ms: int = 0  # 곡 길이 (밀리초)
    
    def __eq__(self, other):
        if not isinstance(other, TrackInfo):
            return False
        # 제목과 아티스트가 같으면 같은 곡으로 간주 (길이는 약간 다를 수 있으므로 제외하거나 포함?)
        # 곡이 바뀌지 않았는데 길이 정보만 갱신될 수 있으므로, 식별자로는 제목+아티스트만 사용
        return self.title == other.title and self.artist == other.artist
    
    def __hash__(self):
        return hash((self.title, self.artist))


class TrackDetector:
    """YouTube Music 곡 정보를 감지"""
    
    # 지원하는 브라우저의 창 클래스명
    BROWSER_CLASSES = [
        "Chrome_WidgetWin_1",  # Chrome, Edge
        "MozillaWindowClass",  # Firefox
    ]
    
    # YouTube Music 탭 제목에서 곡 정보 부분 추출
    YT_MUSIC_PATTERN = re.compile(r"^(.+?)\s*[|]\s*YouTube Music$")
    
    def __init__(self):
        self._current_track: Optional[TrackInfo] = None
        self._callbacks: list[Callable[[TrackInfo], None]] = []
        self._use_media_session = MEDIA_SESSION_AVAILABLE
    
    def get_current_track(self) -> Optional[TrackInfo]:
        """현재 재생 중인 곡 정보 반환 (Media Session API 우선)"""
        
        # 1순위: Windows Media Session API (백그라운드 지원)
        if self._use_media_session:
            try:
                media = get_current_media()
                if media and media.title:
                    print(f"[MediaSession] 감지: {media.title} - {media.artist}")
                    return TrackInfo(
                        title=media.title,
                        artist=media.artist if media.artist else "Unknown Artist",
                        duration_ms=media.duration_ms
                    )
            except Exception as e:
                print(f"[MediaSession] 오류, 창 제목 방식으로 폴백: {e}")
        
        # 2순위: 브라우저 창 제목 파싱
        youtube_music_titles = self._find_youtube_music_windows()
        
        for title in youtube_music_titles:
            track = self._parse_title(title)
            if track:
                return track
        
        return None
    
    def _find_youtube_music_windows(self) -> list[str]:
        """모든 브라우저에서 YouTube Music 탭 찾기"""
        titles = []
        all_browser_titles = []  # 디버깅용
        
        def enum_callback(hwnd, results):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            
            try:
                class_name = win32gui.GetClassName(hwnd)
                if class_name in self.BROWSER_CLASSES:
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        all_browser_titles.append(title)
                        if "YouTube Music" in title:
                            results.append(title)
            except Exception:
                pass
            
            return True
        
        win32gui.EnumWindows(enum_callback, titles)
        
        # 디버그: YouTube Music 찾지 못한 경우
        if not titles and all_browser_titles:
            print(f"[디버그] YouTube Music 창 없음. 브라우저 창들: {all_browser_titles[:3]}")
        
        return titles
    
    def _parse_title(self, window_title: str) -> Optional[TrackInfo]:
        """창 제목에서 곡 정보 추출"""
        # "... | YouTube Music" 형식에서 곡 정보 부분 추출
        match = self.YT_MUSIC_PATTERN.match(window_title)
        if not match:
            return None
        
        raw_info = match.group(1).strip()
        
        # 곡 정보 파싱 (다양한 형식 지원)
        title, artist = self._extract_title_artist(raw_info)
        
        return TrackInfo(title=title, artist=artist)
    
    def _extract_title_artist(self, raw_info: str) -> tuple[str, str]:
        """
        다양한 형식의 곡 정보에서 제목과 아티스트 추출
        
        지원 형식:
        - "곡 제목 - 아티스트"
        - "곡 제목 / 아티스트 COVER"
        - "곡 제목 (feat. 아티스트)"
        - "곡 제목 [아티스트 x 아티스트2]"
        - "곡 제목" (아티스트 없음)
        """
        # 패턴 1: " - " 구분자 (가장 일반적)
        if " - " in raw_info:
            parts = raw_info.split(" - ", 1)
            return parts[0].strip(), parts[1].strip()
        
        # 패턴 2: " / " 구분자 (커버곡 등)
        if " / " in raw_info:
            parts = raw_info.split(" / ", 1)
            # 제목 부분에서 원곡 아티스트 정보 추출 시도
            title_part = parts[0].strip()
            cover_artist = parts[1].strip()
            
            # 제목에서 괄호/브라켓 안의 원곡 아티스트 찾기
            # 예: "Enemy{Imagine Dragons x J.I.D]" -> title="Enemy", original_artist="Imagine Dragons x J.I.D"
            original_match = re.search(r'[\[\{(]([^\]\})]+)[\]\})]', title_part)
            if original_match:
                # 원곡 아티스트가 있으면 그것 사용
                clean_title = re.sub(r'[\[\{(][^\]\})]+[\]\})]', '', title_part).strip()
                original_artist = original_match.group(1).strip()
                return clean_title, original_artist
            
            # 괄호가 없으면 커버 아티스트 사용
            return title_part, cover_artist
        
        # 패턴 3: 괄호 안에 아티스트 (feat, ft 등)
        feat_match = re.search(r'\s*[\(\[](?:feat\.?|ft\.?|featuring)\s*([^\)\]]+)[\)\]]', raw_info, re.IGNORECASE)
        if feat_match:
            # 피처링 아티스트 추출
            artist = feat_match.group(1).strip()
            title = re.sub(r'\s*[\(\[](?:feat\.?|ft\.?|featuring)[^\)\]]+[\)\]]', '', raw_info, flags=re.IGNORECASE).strip()
            return title, artist
        
        # 패턴 4: 그냥 제목만 있는 경우
        return raw_info, "Unknown Artist"
    
    def on_track_change(self, callback: Callable[[TrackInfo], None]):
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


if __name__ == "__main__":
    # 테스트 실행
    detector = TrackDetector()
    track = detector.get_current_track()
    
    if track:
        print(f"현재 재생 중: {track.title} - {track.artist}")
    else:
        print("YouTube Music에서 재생 중인 곡을 찾을 수 없습니다.")
        print("브라우저에서 YouTube Music을 열고 음악을 재생해주세요.")
