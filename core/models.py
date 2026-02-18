"""
도메인 데이터 클래스 통합 모듈.
기존에 여러 파일에 분산되어 있던 데이터 클래스를 한 곳에서 관리합니다.
"""

from dataclasses import dataclass, field
from typing import Optional


# ── 미디어 세션 ───────────────────────────────────────────────────────────────

@dataclass
class MediaInfo:
    """Windows Media Session에서 가져온 미디어 정보"""
    title: str
    artist: str
    album: str
    source_app: str     # 재생 중인 앱 (chrome.exe, firefox.exe 등)
    position_ms: int = 0    # 현재 재생 위치 (밀리초)
    duration_ms: int = 0    # 전체 길이 (밀리초)


# ── 트랙 감지 ─────────────────────────────────────────────────────────────────

@dataclass
class TrackInfo:
    """현재 재생 중인 곡 정보"""
    title: str
    artist: str
    duration_ms: int = 0    # 곡 길이 (밀리초)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TrackInfo):
            return False
        return self.title == other.title and self.artist == other.artist

    def __hash__(self) -> int:
        return hash((self.title, self.artist))


# ── 가사 파싱 ─────────────────────────────────────────────────────────────────

@dataclass
class LyricLine:
    """파싱된 가사 한 줄"""
    timestamp_ms: Optional[int]     # 밀리초 단위 타임스탬프, 없으면 None
    text: str                       # 가사 텍스트
    member: Optional[str]           # 멤버 이름, 없으면 None
    translation: str = ""           # 번역 결과
    romanization: str = ""          # 발음 (로마자/한글 표기)

    @property
    def timestamp_str(self) -> str:
        """타임스탬프를 MM:SS 형식으로 반환"""
        if self.timestamp_ms is None:
            return ""
        total_seconds = self.timestamp_ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"


# ── 번역 ──────────────────────────────────────────────────────────────────────

@dataclass
class TranslatedLine:
    """번역된 가사 라인"""
    original: str           # 원본 가사
    translation: str        # 번역
    romanization: str       # 발음 (로마자/한글 표기)
    original_lang: str      # 원본 언어 코드


# ── UI 표시용 ─────────────────────────────────────────────────────────────────

@dataclass
class LyricDisplayLine:
    """화면에 표시할 가사 라인 (View에 전달되는 DTO)"""
    text: str
    color: str
    is_current: bool = False
    translation: str = ""       # 번역 (다른 언어인 경우)
    romanization: str = ""      # 발음 (로마자 표기)
