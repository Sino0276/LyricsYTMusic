"""
Windows Media Session API를 사용하여 현재 재생 중인 미디어 정보를 가져옵니다.
백그라운드에서 재생 중인 미디어도 감지할 수 있습니다.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone

# Windows SDK imports
from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
    GlobalSystemMediaTransportControlsSession as MediaSession,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
)

# 이벤트 루프 캐시 (재사용을 위해)
_cached_loop = None

def _get_or_create_loop():
    """이벤트 루프 가져오기 또는 생성 (재사용)"""
    global _cached_loop
    try:
        if _cached_loop is None or _cached_loop.is_closed():
            _cached_loop = asyncio.new_event_loop()
        return _cached_loop
    except Exception:
        return asyncio.new_event_loop()


@dataclass
class MediaInfo:
    """미디어 정보"""
    title: str
    artist: str
    album: str
    source_app: str  # 재생 중인 앱 (chrome.exe, firefox.exe 등)
    position_ms: int = 0  # 현재 재생 위치 (밀리초)
    duration_ms: int = 0  # 전체 길이 (밀리초)


def _calculate_correct_position(session) -> int:
    """세션 정보를 바탕으로 현재 재생 위치 계산 (보정 포함)"""
    try:
        timeline = session.get_timeline_properties()
        playback_info = session.get_playback_info()
        
        position = int(timeline.position.total_seconds() * 1000)
        
        # 재생 중인 경우 LastUpdatedTime을 이용하여 보정
        if playback_info.playback_status == PlaybackStatus.PLAYING:
            last_updated = getattr(timeline, 'last_updated_time', None)
            if last_updated:
                # winsdk의 datetime은 파이썬 datetime과 호환됨
                now = datetime.now(timezone.utc)
                diff = (now - last_updated).total_seconds()
                
                if diff > 0:
                    position += int(diff * 1000)
        
        return position
    except Exception:
        return 0


async def get_current_media_async() -> Optional[MediaInfo]:
    """비동기로 현재 재생 중인 미디어 정보 가져오기"""
    try:
        # 미디어 세션 매니저 가져오기
        manager = await MediaManager.request_async()
        
        # 현재 세션 가져오기
        session = manager.get_current_session()
        
        if session is None:
            return None
        
        # 미디어 프로퍼티 가져오기
        media_props = await session.try_get_media_properties_async()
        
        if media_props is None:
            return None
        
        # 타임라인 정보 가져오기 (보정된 시간)
        position_ms = _calculate_correct_position(session)
        
        timeline = session.get_timeline_properties()
        duration_ms = int(timeline.end_time.total_seconds() * 1000)
        
        # 소스 앱 ID 가져오기
        source_app = session.source_app_user_model_id or "Unknown"
        
        return MediaInfo(
            title=media_props.title or "",
            artist=media_props.artist or "",
            album=media_props.album_title or "",
            source_app=source_app,
            position_ms=position_ms,
            duration_ms=duration_ms
        )
        
    except Exception as e:
        print(f"[MediaSession] 오류: {e}")
        return None


def get_current_media() -> Optional[MediaInfo]:
    """동기 함수로 현재 재생 중인 미디어 정보 가져오기"""
    try:
        loop = _get_or_create_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(get_current_media_async())
        return result
    except Exception as e:
        print(f"[MediaSession] 동기 호출 오류: {e}")
        return None


def get_playback_position_ms() -> Optional[int]:
    """현재 재생 위치만 빠르게 가져오기 (밀리초, 보정 포함)"""
    try:
        loop = _get_or_create_loop()
        asyncio.set_event_loop(loop)
        
        async def get_position():
            manager = await MediaManager.request_async()
            session = manager.get_current_session()
            if session:
                return _calculate_correct_position(session)
            return None
        
        result = loop.run_until_complete(get_position())
        return result
    except Exception as e:
        # 디버그용 로깅은 생략 (빈번한 호출)
        return None


def is_youtube_music(media: MediaInfo) -> bool:
    """YouTube Music에서 재생 중인지 확인"""
    source_lower = media.source_app.lower()
    # 브라우저 앱 ID에서 확인
    return any(browser in source_lower for browser in ['chrome', 'firefox', 'msedge', 'edge'])


class MediaSessionWatcher:
    """이벤트 기반 미디어 세션 감시 (곡 변경 즉시 감지)"""
    
    def __init__(self, on_track_changed: callable = None):
        """
        Args:
            on_track_changed: 곡 변경 시 호출될 콜백 (MediaInfo 인자)
        """
        self._on_track_changed = on_track_changed
        self._manager = None
        self._current_session = None
        self._last_media_info = None
        self._running = False
        self._loop = None
        self._session_changed_token = None
        self._media_properties_token = None
    
    async def _start_async(self):
        """비동기 감시 시작"""
        try:
            self._manager = await MediaManager.request_async()
            
            # 세션 변경 이벤트 구독
            self._session_changed_token = self._manager.add_current_session_changed(
                self._on_session_changed
            )
            
            # 초기 세션 연결
            await self._connect_session()
            
            print("[MediaWatcher] 이벤트 구독 시작됨 (즉시 감지 모드)")
            
        except Exception as e:
            print(f"[MediaWatcher] 시작 오류: {e}")
    
    def _on_session_changed(self, sender, args):
        """세션 변경 이벤트 핸들러"""
        print("[MediaWatcher] 세션 변경 감지")
        # 비동기 작업은 이벤트 루프에서 실행
        if self._loop and self._running:
            asyncio.run_coroutine_threadsafe(self._connect_session(), self._loop)
    
    async def _connect_session(self):
        """현재 세션에 연결하고 이벤트 구독"""
        try:
            # 이전 세션 이벤트 해제
            if self._current_session and self._media_properties_token:
                try:
                    self._current_session.remove_media_properties_changed(self._media_properties_token)
                except Exception:
                    pass
            
            # 새 세션 가져오기
            self._current_session = self._manager.get_current_session()
            
            if self._current_session:
                # 미디어 속성 변경 이벤트 구독
                self._media_properties_token = self._current_session.add_media_properties_changed(
                    self._on_media_properties_changed
                )
                
                # 초기 미디어 정보 가져오기
                await self._check_media()
                
        except Exception as e:
            print(f"[MediaWatcher] 세션 연결 오류: {e}")
    
    def _on_media_properties_changed(self, sender, args):
        """미디어 속성 변경 이벤트 핸들러 (곡 변경 등)"""
        print("[MediaWatcher] 미디어 속성 변경 감지")
        if self._loop and self._running:
            asyncio.run_coroutine_threadsafe(self._check_media(), self._loop)
    
    async def _check_media(self):
        """현재 미디어 정보 확인 및 콜백 호출"""
        try:
            if not self._current_session:
                return
            
            media_props = await self._current_session.try_get_media_properties_async()
            
            if not media_props or not media_props.title:
                return
            
            timeline = self._current_session.get_timeline_properties()
            duration_ms = int(timeline.end_time.total_seconds() * 1000)
            source_app = self._current_session.source_app_user_model_id or "Unknown"
            
            new_info = MediaInfo(
                title=media_props.title or "",
                artist=media_props.artist or "",
                album=media_props.album_title or "",
                source_app=source_app,
                position_ms=_calculate_correct_position(self._current_session),
                duration_ms=duration_ms
            )
            
            # 곡이 변경되었는지 확인
            is_changed = (
                self._last_media_info is None or
                self._last_media_info.title != new_info.title or
                self._last_media_info.artist != new_info.artist
            )
            
            if is_changed:
                print(f"[MediaWatcher] 곡 변경: {new_info.title} - {new_info.artist}")
                self._last_media_info = new_info
                
                if self._on_track_changed:
                    self._on_track_changed(new_info)
                    
        except Exception as e:
            print(f"[MediaWatcher] 미디어 확인 오류: {e}")
    
    def start(self):
        """감시 시작 (별도 스레드에서 이벤트 루프 실행)"""
        import threading
        
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._running = True
            
            self._loop.run_until_complete(self._start_async())
            
            # 이벤트 루프 유지
            while self._running:
                self._loop.run_until_complete(asyncio.sleep(0.1))
            
            self._loop.close()
        
        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()
        print("[MediaWatcher] 워처 스레드 시작됨")
    
    def stop(self):
        """감시 중지"""
        self._running = False
        print("[MediaWatcher] 워처 중지됨")
    
    def get_current_media(self) -> Optional[MediaInfo]:
        """현재 미디어 정보 반환 (캐시된 값)"""
        return self._last_media_info


if __name__ == "__main__":
    print("Windows Media Session 테스트")
    print("=" * 50)
    
    media = get_current_media()
    
    if media:
        print(f"제목: {media.title}")
        print(f"아티스트: {media.artist}")
        print(f"앨범: {media.album}")
        print(f"소스 앱: {media.source_app}")
    else:
        print("재생 중인 미디어 없음")
    
    # 이벤트 감시 테스트
    print("\n이벤트 감시 테스트 (Ctrl+C로 종료)")
    
    def on_change(media):
        print(f"[콜백] 곡 변경: {media.title} - {media.artist}")
    
    watcher = MediaSessionWatcher(on_track_changed=on_change)
    watcher.start()
    
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()
        print("종료")
