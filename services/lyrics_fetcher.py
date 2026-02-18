"""
가사를 검색하고 가져오는 모듈.
syncedlyrics 라이브러리를 사용하여 시간 동기화된 LRC 가사를 검색합니다.
파일 기반 캐싱을 지원하여 반복 검색 속도를 획기적으로 개선합니다.
"""

import json
import os
import re
import time as time_module
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import syncedlyrics

from core.constants import (
    LYRICS_CACHE_FILE,
    LYRICS_DURATION_TOLERANCE_MS,
    LYRICS_PROVIDERS_ALL,
    LYRICS_PROVIDERS_PRIORITY,
    LYRICS_SEARCH_MAX_WORKERS,
    LYRICS_SEARCH_TIMEOUT_SEC,
    MAX_SEARCH_ATTEMPTS,
)


class LyricsFetcher:
    """가사 검색 및 가져오기 (파일 캐싱 지원)"""

    def __init__(self, cache_file: str = LYRICS_CACHE_FILE) -> None:
        """
        Args:
            cache_file: 캐시 파일 경로 (기본값: constants에서 가져옴)
        """
        self._cache_file = cache_file
        self._cache: dict[str, str] = {}
        self._load_cache()

    # ── 캐시 관리 ─────────────────────────────────────────────────────────────

    def _load_cache(self) -> None:
        """캐시 파일 로드"""
        if os.path.exists(self._cache_file):
            try:
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
                print(f"[가사] 캐시 로드 완료 ({len(self._cache)}곡)")
            except Exception as e:
                print(f"[가사] 캐시 로드 실패: {e}")
                self._cache = {}

    def _save_cache(self) -> None:
        """캐시 파일 저장"""
        try:
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[가사] 캐시 저장 실패: {e}")

    def _get_cache_key(self, title: str, artist: str) -> str:
        """캐시 키 생성"""
        return f"{title} | {artist}".lower()

    def _load_from_cache(self, cache_key: str) -> Optional[str]:
        """캐시에서 가사 로드"""
        return self._cache.get(cache_key)

    def _save_to_cache(self, cache_key: str, lyrics: str) -> None:
        """가사를 캐시에 저장하고 파일에 덤프"""
        self._cache[cache_key] = lyrics
        self._save_cache()

    # ── 공개 API ──────────────────────────────────────────────────────────────

    def search_lyrics(
        self,
        title: str,
        artist: str,
        duration_ms: Optional[int] = None,
        multi_source: bool = False,
    ) -> Optional[str]:
        """통합 가사 검색 메서드 (단일/다중 소스 분기 처리)"""
        if multi_source:
            return self._get_lyrics_multi_source(title, artist, duration_ms)
        return self._get_lyrics(title, artist, duration_ms)

    def search_candidates(
        self, query: str, return_first: bool = False
    ) -> list[tuple[str, str]]:
        """
        주어진 쿼리로 여러 소스에서 가사 후보 검색 (병렬)

        Returns:
            [(ProviderName, LyricsText), ...]
        """
        results: list[tuple[str, str]] = []
        print(f"[검색] 쿼리: {query} (병렬 검색)")

        def search_provider(prov: str) -> Optional[tuple[str, str]]:
            try:
                lrc = syncedlyrics.search(query, providers=[prov])
                if lrc:
                    return (prov, lrc)
            except Exception as e:
                print(f"[검색] 오류 ({prov}): {e}")
            return None

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(search_provider, prov): prov for prov in LYRICS_PROVIDERS_ALL}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    prov, lrc = result
                    print(f"[검색] {prov}에서 결과 찾음!")
                    results.append(result)
                    if return_first:
                        executor.shutdown(wait=False, cancel_futures=True)
                        return results

        return results

    # ── 내부 검색 로직 ────────────────────────────────────────────────────────

    def _get_lyrics(
        self, title: str, artist: str, duration_ms: Optional[int] = None
    ) -> Optional[str]:
        """가사 검색 (LRC 형식) - 병렬 검색 + 우선순위"""
        cache_key = self._get_cache_key(title, artist)
        cached = self._load_from_cache(cache_key)

        if cached:
            if self._validate_lyrics(cached, duration_ms):
                print(f"[가사] 캐시 적중: {title} - {artist}")
                return cached
            print("[가사] 캐시된 가사 길이 불일치. 재검색 시도.")

        print(f"[가사] 병렬 검색 시작: {title} - {artist} (길이: {duration_ms}ms)")

        queries = self._generate_search_queries(title, artist) or [f"{artist} {title}"]

        # 모든 (쿼리 인덱스, 쿼리, 프로바이더) 조합 생성
        search_tasks = [
            (q_idx, query, provider)
            for q_idx, query in enumerate(queries[:MAX_SEARCH_ATTEMPTS])
            for provider in LYRICS_PROVIDERS_PRIORITY
        ]
        print(f"[가사] 총 {len(search_tasks)}개 검색 작업 병렬 실행")

        def search_single(task: tuple) -> Optional[tuple]:
            q_idx, query, provider = task
            try:
                lrc = syncedlyrics.search(query, providers=[provider])
                if lrc:
                    return (q_idx, query, provider, lrc)
            except Exception:
                pass
            return None

        valid_results: list[tuple] = []

        with ThreadPoolExecutor(max_workers=LYRICS_SEARCH_MAX_WORKERS) as executor:
            futures = {executor.submit(search_single, task): task for task in search_tasks}
            start_time = time_module.time()

            for future in as_completed(futures):
                result = future.result()
                if not result:
                    continue

                q_idx, query, provider, lrc = result

                if self._validate_lyrics(lrc, duration_ms):
                    print(f"[가사] 유효 결과 (우선순위 {q_idx + 1}, 소스: {provider})")

                    # 최우선 결과면 즉시 반환
                    if q_idx == 0:
                        print("[가사] 최우선 결과 사용! (즉시 반환)")
                        self._save_to_cache(cache_key, lrc)
                        executor.shutdown(wait=False, cancel_futures=True)
                        return lrc

                    valid_results.append(result)

                    # 타임아웃 경과 시 현재 확보된 최선 반환
                    elapsed = time_module.time() - start_time
                    if elapsed >= LYRICS_SEARCH_TIMEOUT_SEC and valid_results:
                        print("[가사] 1순위 검색 지연. 현재 확보된 차선책 사용.")
                        break

        if valid_results:
            valid_results.sort(key=lambda x: x[0])
            q_idx, query, provider, lrc = valid_results[0]
            print(f"[가사] 차선 결과 사용 (우선순위 {q_idx + 1}, 소스: {provider})")
            self._save_to_cache(cache_key, lrc)
            return lrc

        print("[가사] 가사를 찾을 수 없음")
        return None

    def _get_lyrics_multi_source(
        self, title: str, artist: str, duration_ms: Optional[int] = None
    ) -> Optional[str]:
        """여러 소스에서 병렬로 가사 검색 (더 정확하지만 느림)"""
        cache_key = self._get_cache_key(title, artist)
        cached = self._load_from_cache(cache_key)

        if cached and self._validate_lyrics(cached, duration_ms):
            print(f"[가사] 캐시 적중: {title} - {artist}")
            return cached

        print(f"[가사] 다중 소스 검색 시작: {title} - {artist}")
        queries = self._generate_search_queries(title, artist) or [f"{artist} {title}"]
        candidates = self.search_candidates(queries[0])

        for prov, lrc in candidates:
            if self._validate_lyrics(lrc, duration_ms):
                print(f"[가사] 다중 소스에서 찾음 ({prov})")
                self._save_to_cache(cache_key, lrc)
                return lrc

        # 유효성 검증 실패해도 결과가 있으면 첫 번째 반환 (완화)
        if candidates:
            prov, lrc = candidates[0]
            print(f"[가사] 유효성 검증 미통과, 첫 번째 결과 사용 ({prov})")
            self._save_to_cache(cache_key, lrc)
            return lrc

        print("[가사] 다중 소스 검색 실패")
        return None

    def _validate_lyrics(self, lrc_text: str, target_duration_ms: Optional[int]) -> bool:
        """가사 유효성 검증 (곡 길이 비교)"""
        if not target_duration_ms or target_duration_ms == 0:
            return True

        try:
            matches = re.findall(r"\[(\d+):(\d+(?:\.\d+)?)\]", lrc_text)
            if not matches:
                return True

            last_match = matches[-1]
            lrc_duration_ms = int((int(last_match[0]) * 60 + float(last_match[1])) * 1000)
            diff = abs(lrc_duration_ms - target_duration_ms)

            if diff > LYRICS_DURATION_TOLERANCE_MS:
                print(
                    f"[검증] 길이 차이 과다: LRC={lrc_duration_ms}ms, "
                    f"Track={target_duration_ms}ms (Diff: {diff}ms)"
                )
                return False

            return True
        except Exception as e:
            print(f"[검증] 오류: {e}")
            return True

    def _generate_search_queries(self, title: str, artist: str) -> list[str]:
        """최적화된 검색어 리스트 생성 (우선순위 순)"""
        queries: list[str] = []

        def remove_noise(text: str) -> str:
            keywords = ["official video", "official audio", "mv", "m/v", "flac", "hq", "lyrics", "lyric video"]
            for kw in keywords:
                text = re.sub(f"(?i){re.escape(kw)}", "", text)
            return text.strip()

        # 구분자로 분리
        separators = [" / ", " | ", " # ", " : ", " - "]
        parts = [title]
        for sep in separators:
            if sep in title:
                parts = title.split(sep)
                break

        # 커버/By 키워드가 있는 파트 제외
        clean_parts = [p for p in parts if not re.search(r"(?i)(cover|by\s|performed by)", p)]
        if not clean_parts:
            clean_parts = parts

        candidate_title = clean_parts[0].strip()

        # 괄호 안 아티스트 추출
        featured_artists = re.findall(r"[\[\(\{]([^\]\)\}]+)[\]\)\}]", candidate_title)

        # 순수 제목 (괄호 제거)
        clean_title = re.sub(r"[\[\(\{].*?[\]\)\}]", "", candidate_title)
        clean_title = remove_noise(clean_title)
        clean_title = re.sub(r"[^\w\s\-\']", " ", clean_title).strip()
        clean_title = re.sub(r"\s+", " ", clean_title).strip()

        # 전략 A: 추출된 아티스트 + 정제된 제목
        for feat in featured_artists:
            if " - " in feat:
                sub_parts = feat.split(" - ")
                queries.append(f"{sub_parts[0]} {clean_title}")
                queries.append(f"{sub_parts[1]} {clean_title}")
            else:
                queries.append(f"{feat} {clean_title}")

        # 전략 B: 업로더/채널 + 원본 제목 (커버가 아닌 경우)
        if artist and artist.lower() != "unknown artist":
            if not re.search(r"(?i)(cover|커버|歌ってみた|カバー)", title):
                queries.append(f"{artist} {title}")

        # 전략 C: 업로더 + 정제된 제목
        clean_artist = remove_noise(artist)
        if clean_artist and clean_artist.lower() != "unknown artist":
            queries.append(f"{clean_artist} {clean_title}")

        # 전략 D: 정제된 제목만 (충분히 고유한 경우)
        if len(clean_title.split()) >= 3 or len(clean_title) >= 15:
            queries.append(clean_title)

        # 중복 제거
        seen: set[str] = set()
        unique_queries: list[str] = []
        for q in queries:
            q_clean = q.lower().strip()
            if q_clean and len(q_clean) > 1 and q_clean not in seen:
                seen.add(q_clean)
                unique_queries.append(q)

        return unique_queries[:5]
