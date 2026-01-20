"""재생 시간 가져오기 테스트"""
import asyncio
from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
)

async def test_timeline():
    print("Media Session Timeline 테스트")
    print("=" * 50)
    
    manager = await MediaManager.request_async()
    session = manager.get_current_session()
    
    if session:
        # 타임라인 속성 가져오기
        timeline = session.get_timeline_properties()
        
        # 재생 정보 가져오기
        info = await session.try_get_media_properties_async()
        
        # 속성 확인 (last_updated_time이 있는지)
        print("\n[Timeline 속성 목록]")
        last_updated = getattr(timeline, 'last_updated_time', None)
        print(f"  last_updated_time: {last_updated} (Type: {type(last_updated)})")
        
        # 재생 상태 확인
        playback_info = session.get_playback_info()
        print(f"재생 상태: {playback_info.playback_status}")
        # GlobalSystemMediaTransportControlsSessionPlaybackStatus.Playing == 4
        
        # 날짜 연산 테스트
        if last_updated:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            diff = now - last_updated
            print(f"현재 시간(UTC): {now}")
            print(f"차이: {diff}")
            print(f"차이(초): {diff.total_seconds()}")
            
            # 보정된 위치
            if playback_info.playback_status == 4: # Playing
                corrected_pos = timeline.position.total_seconds() + diff.total_seconds()
                print(f"보정된 위치(초): {corrected_pos}")
                print(f"보정된 위치(ms): {int(corrected_pos * 1000)}")
            else:
                print("재생 중이 아님 (보정 안 함)")
        
        # datetime.timedelta 형식 → 밀리초 변환
        position_ms = int(timeline.position.total_seconds() * 1000)
        print(f"\n원본 위치 (ms): {position_ms}")
    else:
        print("미디어 세션 없음")

if __name__ == "__main__":
    asyncio.run(test_timeline())
