"""
기본 설정값 상수.
SettingsManager 클래스 내부에서 분리하여 독립적으로 관리합니다.
"""

from typing import Any

# 기존 settings.json 포맷과 완전 호환
DEFAULT_SETTINGS: dict[str, Any] = {
    "multi_source_search": False,
    "click_through_mode": False,
    "background_color": "#1a1a2e",
    "text_color": "#e0e0e0",
    "highlight_color": "#e94560",
    "opacity": 0.9,
    "font_family": "Malgun Gothic",
    "font_size": 11,
    "show_translations": True,
}
