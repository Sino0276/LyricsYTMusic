"""
LRC 형식의 가사를 파싱하고 멤버 파트를 추출하는 모듈.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class LyricLine:
    """파싱된 가사 한 줄"""
    timestamp_ms: Optional[int]  # 밀리초 단위 타임스탬프, 없으면 None
    text: str                    # 가사 텍스트
    member: Optional[str]        # 멤버 이름, 없으면 None
    translation: str = ""        # 번역 (추가됨)
    romanization: str = ""       # 발음 (추가됨)
    
    @property
    def timestamp_str(self) -> str:
        """타임스탬프를 MM:SS 형식으로 반환"""
        if self.timestamp_ms is None:
            return ""
        total_seconds = self.timestamp_ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"


class LyricsParser:
    """LRC 가사 파서"""
    
    # [MM:SS.xx] 또는 [MM:SS:xx] 형식의 타임스탬프
    TIMESTAMP_PATTERN = re.compile(r'\[(\d{1,2}):(\d{2})(?:[.:])(\d{2,3})?\]')
    
    # 멤버 파트 패턴들
    # [멤버명] 가사, (멤버명) 가사, 멤버명: 가사
    MEMBER_PATTERNS = [
        re.compile(r'^\[([^\d\]]+)\]\s*(.*)$'),     # [RM] 가사
        re.compile(r'^\(([^)]+)\)\s*(.*)$'),         # (RM) 가사
        re.compile(r'^([^:]+):\s*(.+)$'),            # RM: 가사
    ]
    
    def __init__(self, known_members: Optional[set[str]] = None):
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
            파싱된 LyricLine 리스트
        """
        if not lyrics_text:
            return []
        
        lines = []
        raw_lines = lyrics_text.strip().split('\n')
        
        for raw_line in raw_lines:
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
        
        # 메타데이터 라인 무시 ([ti:], [ar:], [al:], [作詞], [作曲] 등)
        # 영문 2글자 태그 또는 일본어/중국어 메타데이터 태그
        if re.match(r'^\[[a-z]{2}:', line, re.IGNORECASE):
            return None
        
        # 일본어/중국어 메타데이터 태그 필터링
        metadata_tags = ['作詞', '作曲', '編曲', '歌手', '歌', '词', '曲', '编曲']
        for tag in metadata_tags:
            if line.startswith(f'[{tag}]') or line.startswith(f'[{tag}:'):
                return None
        
        # 타임스탬프 추출
        timestamp_ms = None
        timestamp_match = self.TIMESTAMP_PATTERN.match(line)
        
        if timestamp_match:
            minutes = int(timestamp_match.group(1))
            seconds = int(timestamp_match.group(2))
            centiseconds = int(timestamp_match.group(3) or 0)
            
            # 3자리면 밀리초, 2자리면 센티초
            if timestamp_match.group(3) and len(timestamp_match.group(3)) == 3:
                milliseconds = centiseconds
            else:
                milliseconds = centiseconds * 10
            
            timestamp_ms = (minutes * 60 + seconds) * 1000 + milliseconds
            
            # 타임스탬프 제거
            line = line[timestamp_match.end():].strip()
        
        if not line:
            return None
        
        # 멤버 파트 추출
        member, text = self._extract_member(line)
        
        return LyricLine(
            timestamp_ms=timestamp_ms,
            text=text,
            member=member
        )
    
    def _extract_member(self, text: str) -> tuple[Optional[str], str]:
        """텍스트에서 멤버 이름 추출"""
        for pattern in self.MEMBER_PATTERNS:
            match = pattern.match(text)
            if match:
                potential_member = match.group(1).strip()
                remaining_text = match.group(2).strip()
                
                # 알려진 멤버인 경우 또는 짧은 이름인 경우 멤버로 인정
                if potential_member in self.known_members or len(potential_member) <= 15:
                    # 일반적인 문장 시작이 아닌지 확인
                    if not self._is_likely_sentence_start(potential_member):
                        return potential_member, remaining_text
        
        return None, text
    
    def _is_likely_sentence_start(self, text: str) -> bool:
        """일반 문장의 시작처럼 보이는지 확인"""
        # 긴 텍스트는 멤버 이름이 아님
        if len(text) > 20:
            return True
        
        # 일반적인 문장 시작 패턴
        sentence_starters = ['i ', 'you ', 'we ', 'they ', 'he ', 'she ', 'it ', 
                            'the ', 'a ', 'an ', "i'm", "you're", "we're"]
        text_lower = text.lower()
        
        for starter in sentence_starters:
            if text_lower.startswith(starter):
                return True
        
        return False
    
    def get_current_line(self, lines: list[LyricLine], current_time_ms: int) -> Optional[int]:
        """
        현재 시간에 해당하는 가사 라인 인덱스 반환
        
        Args:
            lines: 파싱된 가사 라인 리스트
            current_time_ms: 현재 재생 시간 (밀리초)
            
        Returns:
            현재 라인의 인덱스, 없으면 None
        """
        current_idx = None
        
        for i, line in enumerate(lines):
            if line.timestamp_ms is not None and line.timestamp_ms <= current_time_ms:
                current_idx = i
            elif line.timestamp_ms is not None and line.timestamp_ms > current_time_ms:
                break
        
        return current_idx


if __name__ == "__main__":
    # 테스트
    test_lyrics = """[00:00.00] Test Song - Artist
[00:05.50] [RM] 첫 번째 가사
[00:10.00] (Jin) 두 번째 가사
[00:15.00] SUGA: 세 번째 가사
[00:20.00] 일반 가사 라인
[00:25.00] j-hope: 네 번째 가사
"""
    
    known = {"RM", "Jin", "SUGA", "j-hope", "Jimin", "V", "Jung Kook"}
    parser = LyricsParser(known_members=known)
    lines = parser.parse(test_lyrics)
    
    print("파싱 결과:")
    for line in lines:
        member_str = f"[{line.member}]" if line.member else ""
        print(f"  {line.timestamp_str} {member_str} {line.text}")
