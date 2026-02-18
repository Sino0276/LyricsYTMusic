"""
앱 조립 및 실행 진입점.
모든 레이어를 조립하고 앱을 시작합니다.
이 파일은 앱의 의존성 주입(DI) 역할을 담당합니다.
"""

import sys
import os

# 프로젝트 루트를 sys.path에 추가 (패키지 임포트 지원)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from settings.settings_manager import SettingsManager
from services.track_detector import TrackDetector
from services.lyrics_fetcher import LyricsFetcher
from services.lyrics_parser import LyricsParser
from ui.overlay_window import OverlayWindow
from viewmodels.lyrics_viewmodel import LyricsViewModel

# 선택적 모듈
try:
    from services.translator import LyricsTranslator
    TRANSLATION_AVAILABLE = True
except ImportError:
    TRANSLATION_AVAILABLE = False
    LyricsTranslator = None

try:
    from tray.system_tray import SystemTray
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    SystemTray = None


def create_and_run() -> None:
    """앱 생성 및 실행 (의존성 주입)"""

    # ── 1. 서비스 레이어 생성 ──────────────────────────────────────────────────
    settings = SettingsManager()
    track_detector = TrackDetector()
    lyrics_fetcher = LyricsFetcher()
    lyrics_parser = LyricsParser()
    translator = LyricsTranslator() if TRANSLATION_AVAILABLE else None

    # ── 2. View 생성 ───────────────────────────────────────────────────────────
    overlay = OverlayWindow(settings)

    # ── 3. ViewModel 생성 및 콜백 연결 ────────────────────────────────────────
    viewmodel = LyricsViewModel(
        settings=settings,
        track_detector=track_detector,
        lyrics_fetcher=lyrics_fetcher,
        lyrics_parser=lyrics_parser,
        translator=translator,
    )

    # ViewModel → View 콜백 등록
    viewmodel.set_on_lyrics_updated(overlay.update_lyrics)
    viewmodel.set_on_track_updated(overlay.update_track_info)
    viewmodel.set_on_loading(overlay.show_loading)
    viewmodel.set_on_search_results(overlay.show_search_results)
    viewmodel.set_on_sync_reset(overlay.reset_sync)

    # ViewModel 스케줄러 연결
    viewmodel.set_schedule_fn(overlay.schedule)
    viewmodel.set_is_minimized_fn(overlay.is_minimized)
    viewmodel.set_is_alive_fn(overlay.is_alive)

    # View → ViewModel 콜백 등록
    overlay.set_on_close(lambda: _on_close(viewmodel, overlay, tray=None))
    overlay.set_on_sync_change(viewmodel.adjust_sync)
    overlay.set_on_search(_on_search(viewmodel, overlay))
    overlay.set_on_apply_lyrics(viewmodel.apply_lyrics)

    # 설정 변경 옵저버 등록
    settings.add_observer(overlay.on_settings_changed)
    settings.add_observer(lambda s: overlay.set_click_through(s.get("click_through_mode", False)))

    # ── 4. 시스템 트레이 생성 ──────────────────────────────────────────────────
    tray = None
    if TRAY_AVAILABLE and SystemTray:
        try:
            tray = SystemTray()
            tray.set_on_show_window(overlay.show)
            tray.set_on_center_window(overlay.center)
            tray.set_on_toggle_click_through(lambda: _toggle_click_through(settings, tray))
            # 닫기 버튼에도 tray 연결
            overlay.set_on_close(lambda: _on_close(viewmodel, overlay, tray))
            tray.set_on_exit(lambda: _on_close(viewmodel, overlay, tray))

            initial_ct = settings.get("click_through_mode", False)
            tray.start(initial_click_through_state=initial_ct)
        except Exception as e:
            print(f"[앱] 트레이 초기화 실패: {e}")

    # ── 5. 초기 설정 적용 ──────────────────────────────────────────────────────
    click_through = settings.get("click_through_mode", False)
    overlay.set_click_through(click_through)

    # ── 6. 폴링 시작 ───────────────────────────────────────────────────────────
    viewmodel.start_polling()

    # ── 7. 메인 루프 실행 ──────────────────────────────────────────────────────
    overlay.run()


def _on_search(viewmodel: LyricsViewModel, overlay: OverlayWindow):
    """검색 핸들러 팩토리"""
    import threading

    def handler(title: str, artist: str) -> None:
        # 검색 제안 설정
        suggested_title, suggested_artist = viewmodel.get_search_suggestion()
        overlay.set_search_suggestion(suggested_title, suggested_artist)

        def do_search() -> None:
            results = viewmodel.do_search(title, artist)
            overlay.show_search_results(results)

        threading.Thread(target=do_search, daemon=True).start()

    return handler


def _toggle_click_through(settings: SettingsManager, tray) -> None:
    """클릭 투과 토글"""
    current = settings.get("click_through_mode", False)
    new_value = not current
    settings.set("click_through_mode", new_value)
    if tray:
        tray.update_click_through_state(new_value)


def _on_close(viewmodel: LyricsViewModel, overlay: OverlayWindow, tray) -> None:
    """앱 종료 처리"""
    viewmodel.stop()
    if tray:
        tray.stop()
    overlay.quit()
