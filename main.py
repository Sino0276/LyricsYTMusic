"""
YouTube Music 가사 오버레이 애플리케이션
메인 진입점 - 모든 모듈을 통합하여 실행합니다.
"""

import threading
import time
import os
import sys
import re
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from settings_manager import SettingsManager
from track_detector import TrackDetector, TrackInfo
from lyrics_fetcher import LyricsFetcher
from lyrics_parser import LyricsParser, LyricLine
from overlay_ui import LyricsOverlay, LyricDisplayLine

# 재생 시간 및 타임라인
try:
    from media_session import get_playback_position_ms
    TIMELINE_AVAILABLE = True
except ImportError:
    TIMELINE_AVAILABLE = False
    get_playback_position_ms = lambda: None

# 번역 모듈 (선택적)
try:
    from translator import LyricsTranslator
    TRANSLATION_AVAILABLE = True
except ImportError:
    TRANSLATION_AVAILABLE = False
    print("[경고] 번역 모듈 로드 실패. 번역 기능이 비활성화됩니다.")

# 시스템 트레이 (선택적)
try:
    from system_tray import SystemTray, TRAY_AVAILABLE
except ImportError:
    TRAY_AVAILABLE = False
    SystemTray = None


class LyricsApp:
    """가사 오버레이 애플리케이션"""
    
    POLL_INTERVAL_MS = 500  # 곡 변경 감지 간격 (0.5초 - 빠른 감지)
    SYNC_INTERVAL_MS = 500   # 가사 동기화 간격 (0.5초)
    POLL_INTERVAL_SLOW_MS = 5000  # 최소화 시 감지 간격 (5초)
    SYNC_INTERVAL_SLOW_MS = 2000  # 최소화 시 동기화 간격 (2초)
    DEFAULT_COLOR = "#e0e0e0"  # 기본 가사 색상 (밝은 회색)
    HIGHLIGHT_COLOR = "#ff6b6b"  # 현재 가사 색상 (빨간색 계열)
    
    def __init__(self):
        # 0. UI 루트 (가장 먼저)
        self.root = tk.Tk()
        self.root.withdraw()
        
        # 1. 설정 관리자 초기화
        self.settings = SettingsManager()
        
        # 2. 모듈 초기화
        self.track_detector = TrackDetector()
        self.lyrics_fetcher = LyricsFetcher()
        self.lyrics_parser = LyricsParser()
        
        # 번역 모듈
        self.translator = LyricsTranslator() if TRANSLATION_AVAILABLE else None
        
        # 3. UI - 오버레이 생성
        self.overlay = LyricsOverlay()
        self.overlay.set_on_close(self._on_close)
        
        # 설정 변경 옵저버 등록
        self.settings.add_observer(self._on_settings_update)
        
        # 오버레이 설정 저장 연결 -> SettingsManager 업데이트
        self.overlay.set_on_settings_save(self.settings.update)
        
        # 4. 상태 변수
        # self._running은 start/stop 메서드에 의해 관리되거나 run에서 사용됨 (위치 이동)
        self._current_track: Optional[TrackInfo] = None
        self._current_lyrics: list[LyricLine] = []
        self._current_line_index: int = -1
        
        # 번역 스레드 제어용
        self._translation_thread: Optional[threading.Thread] = None
        self._stop_translation = False
        
        # 싱크 조절
        self._sync_offset = 0
        
        # 5. 시스템 트레이 초기화
        self.tray = None
        if TRAY_AVAILABLE and SystemTray:
            try:
                self.tray = SystemTray()
                self.tray.set_on_center_window(self._center_overlay)
                self.tray.set_on_show_window(self._show_overlay)
                self.tray.set_on_toggle_click_through(self._toggle_click_through)
                if hasattr(self.tray, 'set_on_exit'):
                    self.tray.set_on_exit(self.quit)
            except Exception as e:
                print(f"[메인] 트레이 초기화 실패: {e}")
        
        # 스레드 풀
        self.executor = ThreadPoolExecutor(max_workers=3)
        self._running = True
        
        # 초기 설정 적용
        self._apply_settings(self.settings.get_all())
            
    def quit(self):
        """애플리케이션 종료"""
        self._on_close()
        
    def _toggle_click_through(self, enabled: bool):
        """클릭 투과 모드 토글 콜백"""
        print(f"[메인] 클릭 투과 모드 변경: {enabled}")
        
        # 1. 오버레이에 적용 # Removed, handled by _apply_settings via SettingsManager observer
        # self.overlay.set_click_through(enabled)
            
        # 2. 설정 업데이트 및 저장
        self.settings.set("click_through_mode", enabled) # Use SettingsManager
        
        # 3. 트레이 메뉴 상태 동기화 (필요한 경우) # Removed, handled by _apply_settings via SettingsManager observer
        # if self.tray:
        #     self.tray.update_click_through_state(enabled)
    
    def _apply_settings(self, settings: dict):
        """설정을 컴포넌트에 적용 (옵저버 콜백)"""
        # 1. 색상 적용
        self.overlay.set_colors(
            bg_color=settings.get("background_color"),
            text_color=settings.get("text_color"),
            highlight_color=settings.get("highlight_color")
        )
        # 2. 오버레이 설정 UI 업데이트
        self.overlay.update_settings_ui(settings)
        
        # 3. 클릭 투과 모드 적용 (초기화 시 또는 변경 시)
        # 주의: 무한 루프 방지 (트레이 -> 설정 변경 -> 옵저버 -> 트레이 업데이트)
        click_through = settings.get("click_through_mode", False)
        self.overlay.set_click_through(click_through)
        if self.tray:
            self.tray.update_click_through_state(click_through)
            
        # 4. 투명도 적용
        opacity = settings.get("opacity", 0.9)
        self.overlay.set_opacity(opacity)
        
        # 5. 폰트 적용
        font_family = settings.get("font_family", "Malgun Gothic")
        font_size = settings.get("font_size", 11)
        self.overlay.set_font(font_family, font_size)

        
        # 5. 기타 설정 적용 (필요 시) # Kept this comment
        # multi_source_search는 사용하는 시점에 self._settings를 참조하므로 별도 조치 불필요
        
        # 4. 강제 리페인트 (색상 변경 시 가사 다시 그리기 위해) # Kept this comment
        # 현재 트랙 정보를 다시 업데이트하는 척 하여 리프레시 유도
        if hasattr(self, '_current_track') and self._current_track: # Changed self.current_track to self._current_track
             # 가사가 있다면 다시 그리기 (색상 적용)
             # overlay.update_lyrics를 직접 호출하기엔 가사 데이터가 main에 없음 (캐시에 있음)
             # 간단히: overlay가 set_colors 내부적으로 처리하거나, 여기서 유도.
             pass

    def _on_settings_update(self, settings: dict):
        """설정 변경 시 호출되는 콜백"""
        print("[메인] 설정 변경 감지됨, UI 업데이트 실행")
        self.root.after(0, lambda: self._apply_settings(settings))

    def run(self):
        """애플리케이션 실행"""
        # 초기 클릭 투과 모드 적용 # Removed, handled by _apply_settings
        # initial_click_through = self._settings.get("click_through_mode", False)
        # self.overlay.set_click_through(initial_click_through)
        
        # 초기 색상 및 설정 적용 # Removed, handled by _apply_settings
        # self._apply_settings_to_components()
        
        # 시스템 트레이 시작
        initial_click_through = self.settings.get("click_through_mode", False) # Use self.settings
        if self.tray:
            self.tray.start(initial_click_through_state=initial_click_through)
        
        # 폴링 기반 곡 감지 (이벤트 모드는 asyncio 충돌 문제로 비활성화)
        self._check_track()
        self._schedule_track_check()
        
        
        # 싱크 조절 콜백 연결
        self.overlay.set_on_sync_adjust(self._adjust_sync)
        
        # 검색 요청 콜백 연결
        self.overlay.set_on_search_request(self._on_search_request)
        
        # 검색 실행 콜백 연결
        self.overlay.set_on_do_search(self._do_search_action)
        self.overlay.set_on_apply_lyrics(self._apply_lyrics_action)
        
        if TIMELINE_AVAILABLE:
            self._schedule_lyrics_sync()
            
        self.overlay.run()
    
    def _on_track_changed_event(self, track):
        """이벤트 기반 곡 변경 처리 (즉시 호출됨)"""
        if track != self._current_track:
            self._current_track = track
            self._current_line_index = -1
            self._sync_offset = 0
            
            self._current_lyrics = []
            
            if self.overlay.is_alive():
                self.overlay.reset_sync_control()
            
            self._stop_translation = True
            
            if track:
                print(f"[이벤트감지] 곡 변경: {track.title} - {track.artist}")
                self._on_track_changed(track)
            else:
                self.overlay.update_lyrics([])
    
    def _center_overlay(self):
        """오버레이를 화면 중앙으로 이동 (트레이 메뉴에서 호출)"""
        # 스레드 안전: 명령 큐를 통해 메인 스레드에서 실행
        self.overlay.queue_command(self.overlay.center_window)
    
    def _show_overlay(self):
        """오버레이 표시 (트레이 메뉴에서 호출)"""
        def show():
            self.overlay.root.deiconify()
            self.overlay.root.lift()
            self.overlay.root.focus_force()
        
        self.overlay.queue_command(show)
            
    def _schedule_track_check(self):
        """곡 감지 스케줄"""
        if self._running and self.overlay.is_alive():
            self._check_track()
            # 최소화 시 폴링 간격 증가
            interval = self.POLL_INTERVAL_SLOW_MS if self.overlay.is_minimized() else self.POLL_INTERVAL_MS
            self.overlay.schedule(interval, self._schedule_track_check)
    
    def _schedule_lyrics_sync(self):
        """가사 동기화 스케줄"""
        if self._running and self.overlay.is_alive():
            # 최소화 시 동기화 안 함
            if not self.overlay.is_minimized():
                self._sync_lyrics()
            # 최소화 시 폴링 간격 증가
            interval = self.SYNC_INTERVAL_SLOW_MS if self.overlay.is_minimized() else self.SYNC_INTERVAL_MS
            self.overlay.schedule(interval, self._schedule_lyrics_sync)

    
    def _delayed_start_polling(self):
        """지연 폴링 시작 (이벤트 루프 충돌 방지)"""
        self._check_track()
        self._schedule_track_check()
    
    def _schedule_track_check_slow(self):
        """저속 폴링 (백업용, 이벤트 모드에서만 사용)"""
        if self._running and self.overlay.is_alive():
            # 이벤트 모드가 아니면 일반 폴링으로 전환
            if not self.track_detector.is_event_mode:
                self._schedule_track_check()
                return
            
            # 3초마다 백업 체크 (이벤트 누락 대비)
            self._check_track()
            self.overlay.schedule(3000, self._schedule_track_check_slow)
    
    def _on_search_request(self):
        """검색 패널 열릴 때 호출 - 검색 필드 업데이트"""
        if not self._current_track:
            return
            
        current_title = self._current_track.title
        current_artist = self._current_track.artist
        
        # 제목에서 원곡 아티스트 추출 시도 (괄호 내용)
        extracted_artists = re.findall(r'[\[\(\{]([^\]\)\}]+)[\]\)\}]', current_title)
        
        # 추출된 아티스트 중 원곡 정보일 가능성이 높은 것 선택
        suggested_artist = current_artist  # 기본값은 업로더
        for feat in extracted_artists:
            if ' - ' in feat:
                parts = feat.split(' - ')
                suggested_artist = parts[1].strip() if len(parts) > 1 else parts[0].strip()
                break
            elif not re.search(r'(?i)(cover|커버)', feat) and len(feat) > 2:
                suggested_artist = feat.strip()
                break
        
        # 정제된 제목 (괄호 제거)
        clean_title = re.sub(r'[\[\(\{].*?[\]\)\}]', '', current_title)
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        if ' / ' in clean_title:
            clean_title = clean_title.split(' / ')[0].strip()
        
        # 검색 필드 업데이트
        self.overlay.update_search_fields(clean_title, suggested_artist)
    
    def _do_search_action(self, title: str, artist: str):
        """검색 버튼 클릭 시 실행"""
        query = f"{artist} {title}"
        results = self.lyrics_fetcher.search_candidates(query)
        self.overlay.update_search_results(results)
    
    def _apply_lyrics_action(self, lrc_content: str, source_name: str):
        """가사 적용"""
        print(f"[수동적용] 선택된 가사 적용 (출처: {source_name})")
        
        self._current_lyrics = self.lyrics_parser.parse(lrc_content)
        self._current_line_index = -1
        self._sync_offset = 0
        self.overlay.reset_sync_control()
        
        if self.overlay.is_alive():
            self.overlay.schedule(0, self._display_lyrics)
            
        if self._current_track:
            cache_key = self.lyrics_fetcher._get_cache_key(self._current_track.title, self._current_track.artist)
            self.lyrics_fetcher._save_to_cache(cache_key, lrc_content)
        
        if self.translator and self._current_track:
            self._stop_translation = True
            threading.Thread(target=lambda: self._start_translation_delayed(self._current_track), daemon=True).start()

    def _start_translation_delayed(self, track):
        """번역 재시작 (딜레이)"""
        time.sleep(0.5)
        self._start_translation(track)
    

            
    def _check_track(self):
        """현재 곡 확인 및 업데이트"""
        track = self.track_detector.get_current_track()
        
        if track != self._current_track:
            self._current_track = track
            self._current_line_index = -1
            self._sync_offset = 0  # 싱크 오프셋 초기화
            
            # 이전 가사 즉시 초기화 (이전 곡 가사가 남아있지 않도록)
            self._current_lyrics = []
            
            if self.overlay.is_alive():
                self.overlay.reset_sync_control() # UI 슬라이더 초기화
            
            # 이전 번역 중단
            self._stop_translation = True
            
            if track:
                self._on_track_changed(track)
            else:
                self.overlay.update_lyrics([])
    
    def _on_track_changed(self, track: TrackInfo):
        """곡 변경 처리"""
        print(f"곡 변경 감지: {track.title} - {track.artist}")
        
        self.overlay.update_track_info(track.title, track.artist)
        self.overlay.show_loading_message()
        
        # 가사 검색 (백그라운드)
        def fetch_lyrics():
            # 설정에 따라 검색 수행
            multi_source = self.settings.get("multi_source_search", False)
            lyrics_text = self.lyrics_fetcher.search_lyrics(track.title, track.artist, track.duration_ms, multi_source=multi_source)
            
            if not self._running or self._current_track != track:
                return
                
            if lyrics_text:
                # 파싱
                self._current_lyrics = self.lyrics_parser.parse(lyrics_text)
                self._current_line_index = -1
                
                # 가사 먼저 표시
                if self.overlay.is_alive():
                    self.overlay.schedule(0, self._display_lyrics)
                
                # 번역 시작
                if self.translator:
                    self._start_translation(track)
            else:
                # 자동검색 실패 시 수동검색 팝업 자동 표시
                if self.overlay.is_alive():
                    print("[가사] 자동검색 실패, 수동검색 패널 표시")
                    
                    def show_manual_search():
                        # 검색 필드 업데이트
                        self._on_search_request()
                        # 검색 패널 열기
                        self.overlay.show_search_panel()
                        # "검색 실패" 메시지 표시
                        self.overlay.show_loading_message("❌ 가사를 찾을 수 없습니다. 수동으로 검색해 주세요.")
                    
                    self.overlay.schedule(0, show_manual_search)
        
        thread = threading.Thread(target=fetch_lyrics, daemon=True)
        thread.start()
    
    def _start_translation(self, track: TrackInfo):
        """번역 작업 시작"""
        self._stop_translation = False
        
        def translate_worker():
            # 1. 번역 필요 여부 확인 (전체 가사 샘플링)
            lyrics_texts = [line.text for line in self._current_lyrics if line.text]
            if not self.translator.should_translate_lyrics(lyrics_texts):
                print("[번역] 번역 불필요 (언어 감지 결과)")
                return
            
            print("[번역] 일괄 번역 작업 시작...")
            
            # 2. 일괄 번역 (10줄씩)
            texts_to_translate = [line.text for line in self._current_lyrics]
            batch_size = 10
            
            for batch_start in range(0, len(texts_to_translate), batch_size):
                if self._stop_translation or self._current_track != track:
                    print("[번역] 작업 중단됨")
                    break
                
                batch_end = min(batch_start + batch_size, len(texts_to_translate))
                batch_texts = texts_to_translate[batch_start:batch_end]
                
                try:
                    # 일괄 번역 호출
                    results = self.translator.translate_batch(batch_texts, batch_size=batch_size)
                    
                    # 결과 적용
                    for i, result in enumerate(results):
                        if result:
                            line_idx = batch_start + i
                            if line_idx < len(self._current_lyrics):
                                self._current_lyrics[line_idx].translation = result.translation
                                self._current_lyrics[line_idx].romanization = result.romanization
                    
                    # 배치마다 UI 업데이트
                    if self.overlay.is_alive():
                        self.overlay.schedule(0, self._display_lyrics)
                        
                except Exception as e:
                    print(f"[번역] 배치 처리 오류: {e}")
            
            print("[번역] 작업 완료")
            
        self._translation_thread = threading.Thread(target=translate_worker, daemon=True)
        self._translation_thread.start()
    
    def _adjust_sync(self, offset_ms: int):
        """싱크 조절 핸들러 (절대값)"""
        self._sync_offset = offset_ms
        
        # UI 피드백은 슬라이더 라벨에서 처리하므로 여기서는 토스트 생략 가능
        # 하지만 명확성을 위해 유지할 수도 있음. 슬라이더는 즉각적이므로 토스트는 끄는 게 나을 듯.
        # self.overlay.show_toast(msg) 
        
        # 즉시 반영
        self._sync_lyrics()

    def _sync_lyrics(self):
        """현재 재생 시간에 맞춰 가사 동기화"""
        if not self._current_lyrics:
            return
        
        position_ms = get_playback_position_ms()
        if position_ms is None:
            return
            
        # 오프셋 적용: 현재 재생 시간에서 오프셋을 뺌
        # 예: 오프셋 +500ms (가사 지연) -> 현재 시간 10초일 때 9.5초의 가사를 보여줌
        # 아니면, 가사 타임스탬프에 더함?
        # 보통 "싱크 +0.5초"는 "가사가 0.5초 늦게 나옴"을 의미.
        # 즉, 가사 타임스탬프 10초인 라인이 재생 시간 10.5초에 나와야 함.
        # LineTime + Offset = PlayTime
        # LineTime = PlayTime - Offset
        # 따라서 PlayTime - Offset 시간의 가사를 찾아야 함.
        
        # 하지만 사용자는 "가사 빨리", "가사 늦 게"로 판단함.
        # 오프셋이 양수(+)면 "가사를 늦게(Delay)" -> 현재 시간이 덜 된 것처럼 행동.
        effective_position = position_ms - self._sync_offset
        
        new_index = self._find_current_line(effective_position)
        
        if new_index != self._current_line_index:
            self._current_line_index = new_index
            self._display_lyrics()
    
    def _find_current_line(self, current_time_ms: int) -> int:
        """현재 시간에 해당하는 가사 라인 인덱스 찾기"""
        current_idx = -1
        for i, line in enumerate(self._current_lyrics):
            if line.timestamp_ms is not None and line.timestamp_ms <= current_time_ms:
                current_idx = i
            elif line.timestamp_ms is not None and line.timestamp_ms > current_time_ms:
                break
        return current_idx
    
    def _display_lyrics(self):
        """가사 표시 (번역 포함)"""
        if not self._current_lyrics:
            self.overlay.show_not_found()
            return
        
        display_lines = []
        for i, line in enumerate(self._current_lyrics):
            is_current = (i == self._current_line_index) if self._current_line_index >= 0 else (i == 0)
            
            display_lines.append(LyricDisplayLine(
                text=line.text,
                color=self.HIGHLIGHT_COLOR if is_current else self.DEFAULT_COLOR,
                is_current=is_current,
                translation=line.translation,
                romanization=line.romanization
            ))
        
        self.overlay.update_lyrics(display_lines)
    
    def _on_close(self):
        """종료 처리"""
        self._running = False
        self._stop_translation = True
        
        # 트레이 아이콘 정리
        if self.tray:
            self.tray.stop()
        
        print("애플리케이션 종료")
        
        # Python 프로세스 완전 종료 보장
        
        # 오버레이 창이 살아있으면 닫기
        try:
            if self.overlay.is_alive():
                self.overlay.root.destroy()
        except:
            pass
            
        # 정상적인 종료 처리
        try:
            sys.exit(0)
        except SystemExit:
            # pystray 콜백에서 SystemExit이 잡히면 os._exit 사용
            os._exit(0)


def main():
    """메인 함수"""
    print("=" * 50)
    print("  YouTube Music 가사 오버레이 (v1.2)")
    print("=" * 50)
    print()
    print("지원 기능:")
    print("  - 가사 자동 검색 (LRC)")
    print("  - 가사 시간 동기화 (Windows Media Session)")
    if TIMELINE_AVAILABLE:
        print("    [✓] 타임라인 추적 활성화")
    print("  - 스마트 번역 (외국어 감지 시 자동 번역)")
    if TRANSLATION_AVAILABLE:
        print("    [✓] 번역 모듈 활성화")
    print()
    print("브라우저에서 YouTube Music을 열고 음악을 재생하세요.")
    print()
    
    app = LyricsApp()
    app.run()


if __name__ == "__main__":
    main()
