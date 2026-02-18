"""
LyricsYTMusic 새 아키텍처 진입점.
MVVM 패턴으로 리팩토링된 버전을 실행합니다.

기존 main.py는 legacy_main.py로 보존됩니다.
"""

import os
import sys

# 프로젝트 루트를 sys.path에 추가
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.main import create_and_run

if __name__ == "__main__":
    create_and_run()
