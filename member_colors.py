"""
그룹별 멤버 색상을 관리하는 모듈.
member_colors.json 파일에서 데이터를 로드합니다.
"""

import json
import os
from pathlib import Path
from typing import Optional


class MemberColors:
    """그룹별 멤버 색상 관리"""
    
    # 기본 가사 색상 (멤버 감지 안 될 때)
    DEFAULT_COLOR = "#FFFFFF"
    
    # 멤버를 알 수 없을 때 사용할 색상들 (자동 할당용)
    FALLBACK_COLORS = [
        "#FF6B6B",  # Coral Red
        "#4ECDC4",  # Teal
        "#45B7D1",  # Sky Blue
        "#96CEB4",  # Sage Green
        "#FFEAA7",  # Pale Yellow
        "#DDA0DD",  # Plum
        "#98D8C8",  # Mint
        "#F7DC6F",  # Soft Yellow
        "#BB8FCE",  # Light Purple
        "#85C1E9",  # Light Blue
    ]
    
    def __init__(self, json_path: Optional[str] = None):
        """
        Args:
            json_path: member_colors.json 파일 경로. 
                      None이면 이 파일과 같은 디렉토리에서 찾음
        """
        if json_path is None:
            import sys
            if getattr(sys, 'frozen', False):
                # exe 실행 시
                base_path = Path(sys.executable).parent
            else:
                # 일반 파이썬 실행 시
                base_path = Path(__file__).parent
                
            json_path = base_path / "member_colors.json"
        
        self.json_path = Path(json_path)
        self._data: dict[str, dict[str, str]] = {}
        self._member_to_group: dict[str, str] = {}  # 멤버 -> 그룹 역매핑
        self._unknown_member_colors: dict[str, str] = {}  # 동적 할당된 색상
        self._fallback_index = 0
        
        self._load_data()
    
    def _load_data(self):
        """JSON 파일에서 색상 데이터 로드"""
        if self.json_path.exists():
            try:
                with open(self.json_path, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
                
                # 역매핑 생성 (대소문자 무시)
                for group, members in self._data.items():
                    for member in members:
                        self._member_to_group[member.lower()] = group
                        
            except Exception as e:
                print(f"색상 데이터 로드 오류: {e}")
                self._data = {}
    
    def get_color(self, member_name: Optional[str], group_name: Optional[str] = None) -> str:
        """
        멤버의 색상 반환
        
        Args:
            member_name: 멤버 이름
            group_name: 그룹 이름 (선택적, 정확도 향상)
            
        Returns:
            색상 코드 (예: "#FF0000")
        """
        if not member_name:
            return self.DEFAULT_COLOR
        
        member_lower = member_name.lower().strip()
        
        # 그룹이 지정된 경우
        if group_name:
            group_data = self._data.get(group_name, {})
            for member, color in group_data.items():
                if member.lower() == member_lower:
                    return color
        
        # 그룹 없이 멤버 이름만으로 검색
        if member_lower in self._member_to_group:
            group = self._member_to_group[member_lower]
            for member, color in self._data.get(group, {}).items():
                if member.lower() == member_lower:
                    return color
        
        # 알 수 없는 멤버는 자동 색상 할당
        if member_lower not in self._unknown_member_colors:
            color = self.FALLBACK_COLORS[self._fallback_index % len(self.FALLBACK_COLORS)]
            self._unknown_member_colors[member_lower] = color
            self._fallback_index += 1
        
        return self._unknown_member_colors[member_lower]
    
    def get_group_members(self, group_name: str) -> set[str]:
        """그룹의 모든 멤버 이름 반환"""
        return set(self._data.get(group_name, {}).keys())
    
    def get_all_members(self) -> set[str]:
        """모든 알려진 멤버 이름 반환"""
        members = set()
        for group_members in self._data.values():
            members.update(group_members.keys())
        return members
    
    def find_group_by_artist(self, artist: str) -> Optional[str]:
        """아티스트 문자열에서 그룹 이름 찾기"""
        artist_lower = artist.lower()
        
        for group in self._data:
            if group.lower() in artist_lower:
                return group
        
        return None
    
    def add_group(self, group_name: str, members: dict[str, str]):
        """
        새 그룹 추가 (런타임)
        
        Args:
            group_name: 그룹 이름
            members: {멤버명: 색상코드} 딕셔너리
        """
        self._data[group_name] = members
        for member in members:
            self._member_to_group[member.lower()] = group_name
    
    def save(self):
        """현재 데이터를 JSON 파일에 저장"""
        try:
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"색상 데이터 저장 오류: {e}")


if __name__ == "__main__":
    # 테스트
    colors = MemberColors()
    
    print("지원 그룹:", list(colors._data.keys()))
    print()
    
    # 테스트 케이스
    test_cases = [
        ("RM", None),
        ("Jennie", "BLACKPINK"),
        ("Minji", None),
        ("Unknown", None),
    ]
    
    for member, group in test_cases:
        color = colors.get_color(member, group)
        print(f"{member} ({group or 'auto'}): {color}")
