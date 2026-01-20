"""Media Session 진단 스크립트"""
import asyncio
import time
from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
     GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
)

async def diagnose_media_session():
    print("Media Session 진단 시작 (5초간 모니터링)")
    print("=" * 60)
    
    manager = await MediaManager.request_async()
    
    for i in range(5):
        session = manager.get_current_session()
        print(f"\n[Time {i+1}]")
        
        if session:
            # 소스 앱 ID
            app_id = session.source_app_user_model_id
            print(f"  Source App: {app_id}")
            
            # 재생 상태
            pb_info = session.get_playback_info()
            status = pb_info.playback_status
            print(f"  Status: {status} (Playing=4, Paused=5)")
            
            # 미디어 속성
            try:
                props = await session.try_get_media_properties_async()
                if props:
                    print(f"  Title: {props.title}")
                    print(f"  Artist: {props.artist}")
                    print(f"  Album: {props.album_title}")
                else:
                    print("  (미디어 속성 없음)")
            except Exception as e:
                print(f"  속성 가져오기 실패: {e}")
                
            # 타임라인
            timeline = session.get_timeline_properties()
            pos = timeline.position.total_seconds()
            last_updated = getattr(timeline, 'last_updated_time', 'N/A')
            print(f"  Position: {pos:.2f}s")
            print(f"  LastUpdated: {last_updated}")
            
        else:
            print("  (활성 세션 없음 - 음악을 재생 중인지 확인하세요)")
            
        time.sleep(1)

if __name__ == "__main__":
    asyncio.run(diagnose_media_session())
