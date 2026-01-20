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
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(get_current_media_async())
        loop.close()
        return result
    except Exception as e:
        print(f"[MediaSession] 동기 호출 오류: {e}")
        return None


def get_playback_position_ms() -> Optional[int]:
    """현재 재생 위치만 빠르게 가져오기 (밀리초, 보정 포함)"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def get_position():
            manager = await MediaManager.request_async()
            session = manager.get_current_session()
            if session:
                return _calculate_correct_position(session)
            return None
        
        result = loop.run_until_complete(get_position())
        loop.close()
        return result
    except Exception:
        return None


def is_youtube_music(media: MediaInfo) -> bool:
    """YouTube Music에서 재생 중인지 확인"""
    source_lower = media.source_app.lower()
    # 브라우저 앱 ID에서 확인
    return any(browser in source_lower for browser in ['chrome', 'firefox', 'msedge', 'edge'])


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
