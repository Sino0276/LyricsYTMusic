import json
import os
from typing import Callable, Any, Dict, List

class SettingsManager:
    """설정 관리 클래스 (Observer Pattern)"""
    
    DEFAULT_SETTINGS = {
        "multi_source_search": False,
        "click_through_mode": False,
        "background_color": "#1a1a2e",
        "text_color": "#e0e0e0",
        "highlight_color": "#e94560",
        "opacity": 0.9,
        "font_family": "Malgun Gothic",  # 기본 폰트 (맑은 고딕)
        "font_size": 11,                  # 기본 폰트 크기 (pt)
    }
    
    def __init__(self, filepath="settings.json"):
        # PyInstaller 환경 지원
        import sys
        if getattr(sys, 'frozen', False):
            # exe 실행 시
            base_path = os.path.dirname(sys.executable)
        else:
            # 일반 파이썬 실행 시
            base_path = os.getcwd() # 또는 os.path.dirname(os.path.abspath(__file__))
            
        self.filepath = os.path.join(base_path, filepath)
        self._settings = self.DEFAULT_SETTINGS.copy()
        self._observers: List[Callable[[Dict[str, Any]], None]] = []
        self._load()
        
    def _load(self):
        """설정 파일 로드"""
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # 기본값에 로드된 값 병합 (누락된 키 보존)
                    for key, value in loaded.items():
                        self._settings[key] = value
        except Exception as e:
            print(f"[SettingsManager] 로드 실패: {e}")
            
    def _save(self):
        """설정 파일 저장"""
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SettingsManager] 저장 실패: {e}")
            
    def get(self, key: str, default: Any = None) -> Any:
        """설정값 조회"""
        return self._settings.get(key, default)
        
    def get_all(self) -> Dict[str, Any]:
        """모든 설정 반환"""
        return self._settings.copy()
        
    def set(self, key: str, value: Any):
        """설정값 변경 및 저장"""
        self._settings[key] = value
        self._save()
        self._notify_observers()
        
    def update(self, new_settings: Dict[str, Any]):
        """여러 설정값 업데이트 및 저장"""
        self._settings.update(new_settings)
        self._save()
        self._notify_observers()
        
    def add_observer(self, callback: Callable[[Dict[str, Any]], None]):
        """옵저버 등록"""
        if callback not in self._observers:
            self._observers.append(callback)
            
    def remove_observer(self, callback: Callable[[Dict[str, Any]], None]):
        """옵저버 제거"""
        if callback in self._observers:
            self._observers.remove(callback)
            
    def _notify_observers(self):
        """등록된 옵저버들에게 설정 변경 알림"""
        settings_copy = self._settings.copy()
        for callback in self._observers:
            try:
                callback(settings_copy)
            except Exception as e:
                print(f"[SettingsManager] 옵저버 알림 실패: {e}")
