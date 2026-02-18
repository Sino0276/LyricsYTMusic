"""
LRC 형식의 가사를 파싱하는 모듈.
타임스탬프 추출, 멤버 파트 감지를 담당합니다.
"""

import re
from typing import Optional

from core.models import LyricLine


class LyricsParser:
    """LRC 가사 파서"""

    # [MM:SS.xx] 또는 [MM:SS:xx] 형식의 타임스탬프
    _TIMESTAMP_PATTERN = re.compile(r"\[(\d{1,2}):(\d{2})(?:[.:])((\d{2,3})?)\]")

    # 멤버 파트 패턴들
    _MEMBER_PATTERNS = [
        re.compile(r"^\[([^\d\]]+)\]\s*(.*)$"),    # [RM] 가사
        re.compile(r"^\(([^)]+)\)\s*(.*)$"),        # (RM) 가사
        re.compile(r"^([^:]+):\s*(.+)$"),           # RM: 가사
    ]

    # 일본어/중국어 메타데이터 태그
    _METADATA_TAGS = ["作詞", "作曲", "編曲", "歌手", "歌", "词", "曲", "编曲"]

    # 일반 문장 시작 패턴 (멤버 이름과 구분)
    _SENTENCE_STARTERS = [
        "i ", "you ", "we ", "they ", "he ", "she ", "it ",
        "the ", "a ", "an ", "i'm", "you're", "we're",
    ]

    def __init__(self, known_members: Optional[set[str]] = None) -> None:
        """
        Args:
            known_members: 알려진 멤버 이름 집합 (멤버 파트 감지 정확도 향상)
        """
        self.known_members = known_members or set()

    def parse(self, lyrics_text: str) -> list[LyricLine]:
        """
        가사 텍스트를 파싱하여 LyricLine 리스트 반환

        Args:
            lyrics_text: LRC 형식 또는 일반 가사 텍스트

        Returns:
            타임스탬프 기준 정렬된 LyricLine 리스트
        """
        if not lyrics_text:
            return []

        lines = []
        for raw_line in lyrics_text.strip().split("\n"):
            parsed = self._parse_line(raw_line)
            if parsed:
                lines.append(parsed)

        # 타임스탬프 기준 정렬
        lines.sort(key=lambda x: x.timestamp_ms if x.timestamp_ms is not None else 0)
        return lines

    def _parse_line(self, line: str) -> Optional[LyricLine]:
        """단일 라인 파싱"""
        line = line.strip()
        if not line:
            return None

        # 영문 2글자 메타데이터 태그 무시 ([ti:], [ar:] 등)
        if re.match(r"^\[[a-z]{2}:", line, re.IGNORECASE):
            return None

        # 일본어/중국어 메타데이터 태그 무시
        for tag in self._METADATA_TAGS:
            if line.startswith(f"[{tag}]") or line.startswith(f"[{tag}:"):
                return None

        # 타임스탬프 추출
        timestamp_ms: Optional[int] = None
        timestamp_match = self._TIMESTAMP_PATTERN.match(line)

        if timestamp_match:
            minutes = int(timestamp_match.group(1))
            seconds = int(timestamp_match.group(2))
            raw_sub = timestamp_match.group(3) or "0"
            centiseconds = int(raw_sub) if raw_sub else 0

            # 3자리면 밀리초, 2자리면 센티초
            if len(raw_sub) == 3:
                milliseconds = centiseconds
            else:
                milliseconds = centiseconds * 10

            timestamp_ms = (minutes * 60 + seconds) * 1000 + milliseconds
            line = line[timestamp_match.end():].strip()

        if not line:
            return None

        member, text = self._extract_member(line)
        return LyricLine(timestamp_ms=timestamp_ms, text=text, member=member)

    def _extract_member(self, text: str) -> tuple[Optional[str], str]:
        """텍스트에서 멤버 이름 추출"""
        for pattern in self._MEMBER_PATTERNS:
            match = pattern.match(text)
            if match:
                potential_member = match.group(1).strip()
                remaining_text = match.group(2).strip()

                if potential_member in self.known_members or len(potential_member) <= 15:
                    if not self._is_likely_sentence_start(potential_member):
                        return potential_member, remaining_text

        return None, text

    def _is_likely_sentence_start(self, text: str) -> bool:
        """일반 문장의 시작처럼 보이는지 확인 (멤버 이름과 구분)"""
        if len(text) > 20:
            return True

        text_lower = text.lower()
        return any(text_lower.startswith(starter) for starter in self._SENTENCE_STARTERS)

    def get_current_line(self, lines: list[LyricLine], current_time_ms: int) -> Optional[int]:
        """
        현재 시간에 해당하는 가사 라인 인덱스 반환

        Args:
            lines: 파싱된 가사 라인 리스트
            current_time_ms: 현재 재생 시간 (밀리초)

        Returns:
            현재 라인의 인덱스, 없으면 None
        """
        current_idx: Optional[int] = None
        for i, line in enumerate(lines):
            if line.timestamp_ms is not None and line.timestamp_ms <= current_time_ms:
                current_idx = i
            elif line.timestamp_ms is not None and line.timestamp_ms > current_time_ms:
                break
        return current_idx
