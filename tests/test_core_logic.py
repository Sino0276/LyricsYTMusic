"""
LyricsYTMusic v2 통합 테스트 스크립트.
리팩토링된 아키텍처의 핵심 로직을 검증합니다.
"""

import sys
import os
import unittest
import shutil

# 프로젝트 루트를 sys.path에 추가
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TEST_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.models import TrackInfo, LyricLine
from core import constants
from settings.settings_manager import SettingsManager
from services.track_detector import TrackDetector
from services.lyrics_parser import LyricsParser
from services.lyrics_fetcher import LyricsFetcher
from ui.widgets.theme_engine import adjust_color_brightness
from app.main import create_and_run

class TestCore(unittest.TestCase):
    def test_constants(self):
        """상수 정의 확인"""
        self.assertEqual(constants.POLL_INTERVAL_MS, 500)
        self.assertIn('Chrome_WidgetWin_1', constants.BROWSER_WINDOW_CLASSES)
        self.assertTrue(len(constants.HIRAGANA_TO_HANGUL) > 0)

    def test_models(self):
        """데이터 모델 동작 확인"""
        t1 = TrackInfo("Title", "Artist", 1000)
        t2 = TrackInfo("Title", "Artist", 2000) # duration 무시하고 같아야 함? 아니, dataclass는 전체 비교
        # TrackInfo는 title과 artist만으로 동등성을 비교하도록 구현됨 (__eq__ 오버라이드)
        self.assertEqual(t1, t2)
        
        # TrackInfo는 frozen=True 일수도 있음.
        t3 = TrackInfo("Title", "Artist", 1000)
        self.assertEqual(t1, t3)

class TestServices(unittest.TestCase):
    def setUp(self):
        self.detector = TrackDetector()
        self.parser = LyricsParser()
        self.fetcher = LyricsFetcher(cache_file="test_cache.json")

    def tearDown(self):
        if os.path.exists("test_cache.json"):
            os.remove("test_cache.json")
    
    def test_track_detector_logic(self):
        """TrackDetector 타이틀 파싱 로직 검증 (사용자 케이스)"""
        cases = [
            ("Enemy{Imagine Dragons x J.I.D] / 하나코 나나 COVER", "Enemy{Imagine Dragons x J.I.D]", "하나코 나나 COVER"),
            ("Rainy Days", "Rainy Days", "Unknown Artist"),
            ("Dynamite - BTS", "Dynamite", "BTS"),
            ("Shape of You (feat. Ed Sheeran)", "Shape of You", "Ed Sheeran"),
            ("MONEY - LISA", "MONEY", "LISA"),
        ]
        
        for raw, expected_title, expected_artist in cases:
            # _extract_title_artist는 protected 메서드지만 테스트를 위해 접근
            title, artist = self.detector._extract_title_artist(raw)
            self.assertEqual(title, expected_title, f"Failed for: {raw}")
            self.assertEqual(artist, expected_artist, f"Failed for: {raw}")

    def test_lyrics_parser(self):
        """LRC 파싱 검증"""
        lrc = """
        [00:01.00] Line 1
        [00:02.50] Line 2
        """
        lines = self.parser.parse(lrc)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].timestamp_ms, 1000)
        self.assertEqual(lines[0].text, "Line 1")
        self.assertEqual(lines[1].timestamp_ms, 2500)

    def test_lyrics_fetcher_queries(self):
        """검색 쿼리 생성 로직 검증"""
        queries = self.fetcher._generate_search_queries("Title", "Artist")
        self.assertIn("Artist Title", queries)
        # 제목이 짧으면 단독 쿼리는 생성되지 않음 -> 긴 제목으로 테스트
        queries_long = self.fetcher._generate_search_queries("Long Title Name For Test", "Artist")
        self.assertIn("Long Title Name For Test", queries_long)

class TestSettings(unittest.TestCase):
    def setUp(self):
        self.filename = "test_settings.json"
        self.sm = SettingsManager(self.filename)

    def tearDown(self):
        if os.path.exists(self.filename):
            os.remove(self.filename)

    def test_defaults(self):
        """기본값 로드 검증"""
        self.assertEqual(self.sm.get("opacity"), 0.9)
        self.assertEqual(self.sm.get("font_family"), "Malgun Gothic")

    def test_save_load(self):
        """설정 저장 및 로드 검증"""
        self.sm.set("opacity", 0.5)
        
        # 새 인스턴스로 로드
        sm2 = SettingsManager(self.filename)
        self.assertEqual(sm2.get("opacity"), 0.5)

class TestUI(unittest.TestCase):
    def test_theme_engine(self):
        """색상 계산 로직 검증"""
        # 검정색 -> 밝기 조절 -> 검정색 (0 * x = 0)
        self.assertEqual(adjust_color_brightness("#000000", 1.5), "#000000")
        # 흰색 -> 0.5 -> 회색
        self.assertEqual(adjust_color_brightness("#ffffff", 0.5), "#7f7f7f")

class TestApp(unittest.TestCase):
    def test_imports(self):
        """앱 진입점 및 주요 모듈 임포트 검증"""
        import run_new
        self.assertTrue(hasattr(run_new, 'create_and_run'))

if __name__ == '__main__':
    unittest.main(verbosity=2)
