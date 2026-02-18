"""
Windows Media Session API를 사용하여 현재 재생 중인 미디어 정보를 가져옵니다.
백그라운드에서 재생 중인 미디어도 감지할 수 있습니다.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
)

from core.models import MediaInfo

# 이벤트 루프 캐시 (매 호출마다 새 루프 생성 비용 절감)
_cached_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_or_create_loop() -> asyncio.AbstractEventLoop:
    """이벤트 루프 가져오기 또는 생성 (재사용)"""
    global _cached_loop
    try:
        if _cached_loop is None or _cached_loop.is_closed():
            _cached_loop = asyncio.new_event_loop()
        return _cached_loop
    except Exception:
        return asyncio.new_event_loop()


def _calculate_correct_position(session) -> int:
    """세션 정보를 바탕으로 현재 재생 위치 계산 (재생 중 보정 포함)"""
    try:
        timeline = session.get_timeline_properties()
        playback_info = session.get_playback_info()

        position = int(timeline.position.total_seconds() * 1000)

        # 재생 중인 경우 LastUpdatedTime을 이용하여 경과 시간 보정
        if playback_info.playback_status == PlaybackStatus.PLAYING:
            last_updated = getattr(timeline, "last_updated_time", None)
            if last_updated:
                now = datetime.now(timezone.utc)
                diff = (now - last_updated).total_seconds()
                if diff > 0:
                    position += int(diff * 1000)

        return position
    except Exception:
        return 0


async def _get_current_media_async() -> Optional[MediaInfo]:
    """비동기로 현재 재생 중인 미디어 정보 가져오기"""
    try:
        manager = await MediaManager.request_async()
        session = manager.get_current_session()

        if session is None:
            return None

        media_props = await session.try_get_media_properties_async()
        if media_props is None:
            return None

        position_ms = _calculate_correct_position(session)
        timeline = session.get_timeline_properties()
        duration_ms = int(timeline.end_time.total_seconds() * 1000)
        source_app = session.source_app_user_model_id or "Unknown"

        return MediaInfo(
            title=media_props.title or "",
            artist=media_props.artist or "",
            album=media_props.album_title or "",
            source_app=source_app,
            position_ms=position_ms,
            duration_ms=duration_ms,
        )

    except Exception as e:
        print(f"[MediaSession] 오류: {e}")
        return None


def get_current_media() -> Optional[MediaInfo]:
    """동기 함수로 현재 재생 중인 미디어 정보 가져오기"""
    try:
        loop = _get_or_create_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_get_current_media_async())
    except Exception as e:
        print(f"[MediaSession] 동기 호출 오류: {e}")
        return None


def get_playback_position_ms() -> Optional[int]:
    """현재 재생 위치만 빠르게 가져오기 (밀리초, 보정 포함)"""
    try:
        loop = _get_or_create_loop()
        asyncio.set_event_loop(loop)

        async def _get_position() -> Optional[int]:
            manager = await MediaManager.request_async()
            session = manager.get_current_session()
            if session:
                return _calculate_correct_position(session)
            return None

        return loop.run_until_complete(_get_position())
    except Exception:
        # 빈번한 호출이므로 디버그 로그 생략
        return None


def is_youtube_music(media: MediaInfo) -> bool:
    """YouTube Music에서 재생 중인지 확인 (브라우저 앱 ID 기반)"""
    source_lower = media.source_app.lower()
    return any(browser in source_lower for browser in ["chrome", "firefox", "msedge", "edge"])
