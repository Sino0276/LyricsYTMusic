"""
YouTube Music 가사 오버레이 애플리케이션
메인 진입점 - 모든 모듈을 통합하여 실행합니다.
"""

import threading
import time
from typing import Optional

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


class LyricsApp:
    """가사 오버레이 애플리케이션"""
    
    POLL_INTERVAL_MS = 1000  # 곡 변경 감지 간격 (1초)
    SYNC_INTERVAL_MS = 500   # 가사 동기화 간격 (0.5초)
    DEFAULT_COLOR = "#e0e0e0"  # 기본 가사 색상 (밝은 회색)
    HIGHLIGHT_COLOR = "#ff6b6b"  # 현재 가사 색상 (빨간색 계열)
    
    def __init__(self):
        # 모듈 초기화
        self.track_detector = TrackDetector()
        self.lyrics_fetcher = LyricsFetcher()
        self.lyrics_parser = LyricsParser()
        
        # 번역 모듈
        self.translator = LyricsTranslator() if TRANSLATION_AVAILABLE else None
        
        # UI
        self.overlay = LyricsOverlay()
        self.overlay.set_on_close(self._on_close)
        
        # 상태
        self._running = True
        self._current_track: Optional[TrackInfo] = None
        self._current_lyrics: list[LyricLine] = []
        self._current_line_index: int = -1
        
        # 번역 스레드 제어용
        self._translation_thread: Optional[threading.Thread] = None
        self._stop_translation = False
        
        # 싱크 조절
        self._sync_offset = 0

    def run(self):
        """애플리케이션 실행"""
        self._check_track()
        self._schedule_track_check()
        
        # 싱크 조절 콜백 연결
        self.overlay.set_on_sync_adjust(self._adjust_sync)
        
        # 검색 요청 콜백 연결
        self.overlay.set_on_search_request(self._on_search_request)
        
        if TIMELINE_AVAILABLE:
            self._schedule_lyrics_sync()
            
        self.overlay.run()
    
    def _on_search_request(self):
        """검색 팝업 요청 처리"""
        if not self._current_track:
            return
            
        current_title = self._current_track.title
        current_artist = self._current_track.artist
        
        # 검색 동작
        def search_action(title, artist):
            query = f"{artist} - {title}"
            return self.lyrics_fetcher.search_candidates(query)
            
        # 적용 동작
        def apply_action(lrc_content, source_name):
            print(f"[수동적용] 선택된 가사 적용 (출처: {source_name})")
            
            # 파싱
            self._current_lyrics = self.lyrics_parser.parse(lrc_content)
            self._current_line_index = -1
            self._sync_offset = 0
            self.overlay.reset_sync_control()
            
            # 즉시 표시
            if self.overlay.is_alive():
                self.overlay.schedule(0, self._display_lyrics)
                
            # 캐시 저장 (나중을 위해)
            # lyrics_fetcher에 메서드가 없으므로 직접 접근하거나 internal 사용
            if self._current_track:
                cache_key = self.lyrics_fetcher._get_cache_key(self._current_track.title, self._current_track.artist)
                self.lyrics_fetcher._save_to_cache(cache_key, lrc_content)
            
            # 번역 재시작
            if self.translator and self._current_track:
                # 라인이 비워져 있을 수 있으므로 약간의 딜레이 후 실행하거나 상태 리셋
                self._stop_translation = True
                threading.Thread(target=lambda: self._start_translation_delayed(self._current_track), daemon=True).start()
        
        self.overlay.show_search_popup(current_title, current_artist, search_action, apply_action)

    def _start_translation_delayed(self, track):
        """번역 재시작 (딜레이)"""
        time.sleep(0.5)
        self._start_translation(track)
    
    def _schedule_track_check(self):
        """곡 감지 스케줄"""
        if self._running and self.overlay.is_alive():
            self._check_track()
            self.overlay.schedule(self.POLL_INTERVAL_MS, self._schedule_track_check)
    
    def _schedule_lyrics_sync(self):
        """가사 동기화 스케줄"""
        if self._running and self.overlay.is_alive():
            self._sync_lyrics()
            self.overlay.schedule(self.SYNC_INTERVAL_MS, self._schedule_lyrics_sync)
    
    def _check_track(self):
        """현재 곡 확인 및 업데이트"""
        track = self.track_detector.get_current_track()
        
        if track != self._current_track:
            self._current_track = track
            self._current_line_index = -1
            self._sync_offset = 0  # 싱크 오프셋 초기화
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
        self.overlay.show_loading()
        
        # 가사 검색 (백그라운드)
        def fetch_lyrics():
            lyrics_text = self.lyrics_fetcher.get_lyrics(track.title, track.artist, track.duration_ms)
            
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
                if self.overlay.is_alive():
                    self.overlay.schedule(0, self.overlay.show_not_found)
        
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
            
            print("[번역] 번역 작업 시작...")
            
            # 2. 한 줄씩 번역
            for i, line in enumerate(self._current_lyrics):
                if self._stop_translation or self._current_track != track:
                    break
                    
                if not line.text:
                    continue
                
                # 이미 번역된 경우 패스 (캐싱 등으로)
                if line.translation:
                    continue
                    
                try:
                    import time
                    # API 속도 제한 고려하여 약간의 지연
                    # time.sleep(0.05) 
                    
                    result = self.translator.translate_line(line.text)
                    if result:
                        line.translation = result.translation
                        line.romanization = result.romanization
                        
                        # UI 업데이트 (10줄마다 또는 중요 라인마다 할 수도 있지만, 일단 실시간 반영)
                        # 현재 화면에 보이는 라인이면 즉시 업데이트가 좋음
                        if self.overlay.is_alive():
                            self.overlay.schedule(0, self._display_lyrics)
                            
                except Exception as e:
                    print(f"[번역] 라인 처리 오류: {e}")
            
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
        print("애플리케이션 종료")


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
