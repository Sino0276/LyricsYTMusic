"""
설정 관리 클래스.
Observer 패턴으로 설정 변경 시 등록된 콜백에 자동 알림합니다.
기본값은 settings/defaults.py에서 임포트합니다.
"""

import json
import os
import sys
from typing import Any, Callable, Dict, List

from settings.defaults import DEFAULT_SETTINGS


class SettingsManager:
    """설정 관리 클래스 (Observer Pattern)"""

    def __init__(self, filepath: str = "settings.json") -> None:
        # PyInstaller 환경 지원: exe 실행 시 실행 파일 위치 기준
        if getattr(sys, "frozen", False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.getcwd()

        self.filepath = os.path.join(base_path, filepath)
        self._settings: Dict[str, Any] = DEFAULT_SETTINGS.copy()
        self._observers: List[Callable[[Dict[str, Any]], None]] = []
        self._load()

    # ── 파일 I/O ──────────────────────────────────────────────────────────────

    def _load(self) -> None:
        """설정 파일 로드 (누락된 키는 기본값으로 보완)"""
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, "r", encoding="utf-8") as f:
                    loaded: Dict[str, Any] = json.load(f)
                    # 기본값에 로드된 값 병합 (누락된 키 보존)
                    for key, value in loaded.items():
                        self._settings[key] = value
        except Exception as e:
            print(f"[SettingsManager] 로드 실패: {e}")

    def _save(self) -> None:
        """설정 파일 저장"""
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SettingsManager] 저장 실패: {e}")

    # ── 공개 API ──────────────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """설정값 조회"""
        return self._settings.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        """모든 설정 복사본 반환"""
        return self._settings.copy()

    def set(self, key: str, value: Any) -> None:
        """단일 설정값 변경 및 저장"""
        self._settings[key] = value
        self._save()
        self._notify_observers()

    def update(self, new_settings: Dict[str, Any]) -> None:
        """여러 설정값 일괄 업데이트 및 저장"""
        self._settings.update(new_settings)
        self._save()
        self._notify_observers()

    # ── Observer 관리 ─────────────────────────────────────────────────────────

    def add_observer(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """옵저버 등록"""
        if callback not in self._observers:
            self._observers.append(callback)

    def remove_observer(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """옵저버 제거"""
        if callback in self._observers:
            self._observers.remove(callback)

    def _notify_observers(self) -> None:
        """등록된 옵저버들에게 설정 변경 알림"""
        settings_copy = self._settings.copy()
        for callback in self._observers:
            try:
                callback(settings_copy)
            except Exception as e:
                print(f"[SettingsManager] 옵저버 알림 실패: {e}")
