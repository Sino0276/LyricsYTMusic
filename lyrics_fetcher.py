"""
가사를 검색하고 가져오는 모듈.
syncedlyrics 라이브러리를 사용하여 시간 동기화된 LRC 가사를 검색합니다.
파일 기반 캐싱을 지원하여 반복 검색 속도를 획기적으로 개선합니다.
"""

import re
import json
import os
import time
from typing import Optional
import syncedlyrics

class LyricsFetcher:
    """가사 검색 및 가져오기 (파일 캐싱 지원)"""
    
    CACHE_FILE = "lyrics_cache.json"
    
    # 검색 시도 횟수 제한 (신뢰성을 위해 적절히 증가)
    MAX_SEARCH_ATTEMPTS = 4
    
    def __init__(self):
        self._cache = {}
        self._load_cache()

    # ... (생략된 메서드들) ...

    def search_candidates(self, query: str, return_first: bool = False) -> list[tuple[str, str]]:
        """
        주어진 쿼리로 여러 소스에서 가사 후보 검색 (병렬)
        
        Args:
            query: 검색 쿼리
            return_first: True면 첫 결과 찾으면 즉시 반환 (더 빠름)
        
        Returns:
            [(ProviderName, LyricsSnippet), ...]
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = []
        # 검색할 프로바이더 목록
        providers = [
            'musixmatch', 
            'netease', 
            'lrclib', 
            'megalobiz'
        ]
        
        print(f"[검색] 쿼리: {query} (병렬 검색)")
        
        def search_provider(prov):
            """개별 프로바이더 검색"""
            try:
                lrc = syncedlyrics.search(query, providers=[prov])
                if lrc:
                    return (prov, lrc)
            except Exception as e:
                print(f"[검색] 오류 ({prov}): {e}")
            return None
        
        # 병렬 검색 (최대 4개 동시 실행)
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(search_provider, prov): prov for prov in providers}
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    prov, lrc = result
                    print(f"[검색] {prov}에서 결과 찾음!")
                    results.append(result)
                    
                    # 첫 결과 즉시 반환 옵션
                    if return_first:
                        executor.shutdown(wait=False, cancel_futures=True)
                        return results
        
        return results

    def get_lyrics_multi_source(self, title: str, artist: str, duration_ms: Optional[int] = None) -> Optional[str]:
        """
        여러 소스에서 병렬로 가사 검색 (더 정확하지만 느림)
        모든 소스를 검색하고 가장 먼저 유효한 결과 반환
        """
        # 캐시 확인
        cache_key = self._get_cache_key(title, artist)
        cached_lyrics = self._load_from_cache(cache_key)
        
        if cached_lyrics:
            if self._validate_lyrics(cached_lyrics, duration_ms):
                print(f"[가사] 캐시 적중: {title} - {artist}")
                return cached_lyrics
        
        print(f"[가사] 다중 소스 검색 시작: {title} - {artist}")
        
        # 검색 쿼리 생성
        queries = self._generate_search_queries(title, artist)
        if not queries:
            queries = [f"{artist} {title}"]
        
        query = queries[0]  # 첫 번째 쿼리 사용
        
        # 여러 소스에서 검색
        candidates = self.search_candidates(query)
        
        # 유효한 가사 찾기
        for prov, lrc in candidates:
            if self._validate_lyrics(lrc, duration_ms):
                print(f"[가사] 다중 소스에서 찾음 ({prov})")
                self._save_to_cache(cache_key, lrc)
                return lrc
        
        # 유효성 검증 실패해도 결과가 있으면 첫 번째 반환 (완화)
        if candidates:
            prov, lrc = candidates[0]
            print(f"[가사] 유효성 검증 통과 안 됐지만 첫 번째 결과 사용 ({prov})")
            self._save_to_cache(cache_key, lrc)
            return lrc
        
        print("[가사] 다중 소스 검색 실패")
        return None

    def _load_cache(self):
        """캐시 파일 로드"""
        if os.path.exists(self.CACHE_FILE):
            try:
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
                print(f"[가사] 캐시 로드 완료 ({len(self._cache)}곡)")
            except Exception as e:
                print(f"[가사] 캐시 로드 실패: {e}")
                self._cache = {}
    
    def _save_cache(self):
        """캐시 파일 저장"""
        try:
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
            print("[가사] 캐시 저장 완료")
        except Exception as e:
            print(f"[가사] 캐시 저장 실패: {e}")

    # Added helper methods for cache operations
    def _get_cache_key(self, title: str, artist: str) -> str:
        """캐시 키 생성"""
        return f"{title} | {artist}".lower()

    def _load_from_cache(self, cache_key: str) -> Optional[str]:
        """캐시에서 가사 로드"""
        return self._cache.get(cache_key)

    def _save_to_cache(self, cache_key: str, lyrics: Optional[str]):
        """가사를 캐시에 저장하고 파일에 덤프"""
        self._cache[cache_key] = lyrics
        self._save_cache()

    def search_lyrics(self, title: str, artist: str, duration_ms: Optional[int] = None, multi_source: bool = False) -> Optional[str]:
        """
        통합 가사 검색 메서드 (단일/다중 소스 분기 처리)
        """
        if multi_source:
             return self.get_lyrics_multi_source(title, artist, duration_ms)
        else:
             return self.get_lyrics(title, artist, duration_ms)

    def get_lyrics(self, title: str, artist: str, duration_ms: Optional[int] = None) -> Optional[str]:
        """
        가사 검색 (LRC 형식) - 병렬 검색 + 우선순위
        
        Args:
            title: 곡 제목
            artist: 아티스트
            duration_ms: 곡 길이 (밀리초) - 유효성 검증용
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
        import time as time_module
        
        # 캐시 확인
        cache_key = self._get_cache_key(title, artist)
        cached_lyrics = self._load_from_cache(cache_key)
        
        # 캐시된 데이터가 있고 유효하면 사용
        if cached_lyrics:
            if self._validate_lyrics(cached_lyrics, duration_ms):
                print(f"[가사] 캐시 적중: {title} - {artist}")
                return cached_lyrics
            else:
                print(f"[가사] 캐시된 가사 길이 불일치. 재검색 시도.")
        
        print(f"[가사] 병렬 검색 시작: {title} - {artist} (길이: {duration_ms}ms)")
        
        # 검색어 생성
        queries = self._generate_search_queries(title, artist)
        if not queries:
            queries = [f"{artist} {title}"]
        
        # 검색 프로바이더 목록 (우선순위 순)
        providers = ['musixmatch', 'lrclib', 'netease', 'megalobiz']
        
        # 모든 (쿼리 인덱스, 쿼리, 프로바이더) 조합 생성
        search_tasks = []
        for query_idx, query in enumerate(queries[:self.MAX_SEARCH_ATTEMPTS]):
            for provider in providers:
                search_tasks.append((query_idx, query, provider))
        
        print(f"[가사] 총 {len(search_tasks)}개 검색 작업 병렬 실행")
        
        def search_single(task):
            """단일 검색 작업"""
            query_idx, query, provider = task
            try:
                lrc = syncedlyrics.search(query, providers=[provider])
                if lrc:
                    return (query_idx, query, provider, lrc)
            except Exception:
                pass
            return None
        
        # 결과 수집 (우선순위별)
        valid_results = []  # (query_idx, query, provider, lrc)
        
        # 병렬 검색 (최대 8개 동시 실행)
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(search_single, task): task for task in search_tasks}
            start_time = time_module.time()
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    query_idx, query, provider, lrc = result
                    
                    # 유효성 검증
                    if self._validate_lyrics(lrc, duration_ms):
                        print(f"[가사] 유효 결과 (우선순위 {query_idx+1}, 쿼리: {query[:30]}..., 소스: {provider})")
                        
                        # 첫 번째 쿼리(우선순위 최고)의 결과면 즉시 반환
                        if query_idx == 0:
                            print(f"[가사] 최우선 결과 사용!")
                            self._save_to_cache(cache_key, lrc)
                            executor.shutdown(wait=False, cancel_futures=True)
                            return lrc
                        
                        # 그 외는 후보로 저장
                        valid_results.append(result)
                        
                        # 500ms 이상 지났고 결과가 있으면 최선의 결과 반환
                        elapsed = time_module.time() - start_time
                        if elapsed > 0.5 and valid_results:
                            break
        
        # 최우선 결과가 없었으면 후보 중 가장 높은 우선순위 선택
        if valid_results:
            # 쿼리 인덱스가 가장 낮은 것 선택 (우선순위 높은 것)
            valid_results.sort(key=lambda x: x[0])
            best = valid_results[0]
            query_idx, query, provider, lrc = best
            print(f"[가사] 차선 결과 사용 (우선순위 {query_idx+1}, 소스: {provider})")
            self._save_to_cache(cache_key, lrc)
            return lrc
        
        print("[가사] 가사를 찾을 수 없음")
        return None
    
    def _validate_lyrics(self, lrc_text: str, target_duration_ms: Optional[int]) -> bool:
        """가사 유효성 검증 (곡 길이 비교)"""
        if not target_duration_ms or target_duration_ms == 0:
            return True # 비교할 길이 정보가 없으면 통과
            
        try:
            # 마지막 타임스탬프 찾기
            # [mm:ss.xx] 형식
            matches = re.findall(r'\[(\d+):(\d+(?:\.\d+)?)\]', lrc_text)
            if not matches:
                return True # 타임스탬프가 없으면(단순 텍스트) 일단 통과하거나 실패 처리 (여기선 통과)
            
            last_match = matches[-1]
            minutes = int(last_match[0])
            seconds = float(last_match[1])
            
            lrc_duration_ms = int((minutes * 60 + seconds) * 1000)
            
            # 오차 범위: 30초 (라이브 버전, 인트로/아웃트로 차이 고려)
            diff = abs(lrc_duration_ms - target_duration_ms)
            
            if diff > 30000: # 30초 이상 차이나면 다른 곡일 확률 높음
                print(f"[검증] 길이 차이 과다: LRC={lrc_duration_ms}ms, Track={target_duration_ms}ms (Diff: {diff}ms)")
                return False
            
            return True
            
        except Exception as e:
            print(f"[검증] 오류: {e}")
            return True # 검증 중 오류나면 일단 통과 (보수적 접근)
    
    def _generate_search_queries(self, title: str, artist: str) -> list[str]:
        """
        최적화된 검색어 리스트 생성 (사용자 제안 로직 반영)
        1. 구분자(Separator) 분리
        2. 불필요한 태그 제거
        3. 우선순위 선정 (Cover 제외)
        """
        queries = []
        
        # 기본 전처리 함수
        def remove_noise(text):
            # MV, Official, Live, Lyrics 등 제거
            keywords = ['official video', 'official audio', 'mv', 'm/v', 'flac', 'hq', 'lyrics', 'lyric video']
            for kw in keywords:
                text = re.sub(f'(?i){re.escape(kw)}', '', text)
            return text.strip()

        # 1. 구분자로 분리 시도
        separators = [" / ", " | ", " # ", " : ", " - "]
        parts = []
        used_separator = False
        
        for sep in separators:
            if sep in title:
                parts = title.split(sep)
                used_separator = True
                break
        
        if not parts:
            parts = [title]

        # 2. 우선순위 선정 (Cover, By 등 포함된 쪽은 아티스트/불필요 정보일 확률 높음)
        # 커버가 아닌 쪽을 제목 후보로 선정
        clean_parts = []
        for part in parts:
            # 커버/By 키워드가 있으면 제외하거나 후순위
            if re.search(r'(?i)(cover|by\s|performed by)', part):
                continue
            clean_parts.append(part)
        
        # 만약 다 걸러져서 없으면 원래 parts 사용
        if not clean_parts:
            clean_parts = parts
            
        candidate_title = clean_parts[0].strip() # 가장 앞부분이 제목일 확률 높음
        
        # 3. Candidate Title 정제 (괄호 삭제 등)
        # 3-1. 괄호 안의 내용이 아티스트 정보일 수 있으므로 추출 시도
        # 예: Enemy [Imagine Dragons] -> Imagine Dragons Enemy
        featured_artists = re.findall(r'[\[\(\{]([^\]\)\}]+)[\]\)\}]', candidate_title)
        
        # 3-2. 순수 제목 (괄호 제거)
        clean_title = re.sub(r'[\[\(\{].*?[\]\)\}]', '', candidate_title)
        clean_title = remove_noise(clean_title)
        clean_title = re.sub(r'[^\w\s\-\']', ' ', clean_title).strip() # 특수문자 제거
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        
        # 쿼리 생성 전략
        
        # 전략 A: [추출된 아티스트] + [정제된 제목] (원곡 아티스트 최우선)
        # 제목 괄호 안에서 원곡 아티스트를 추출하여 먼저 시도
        for feat in featured_artists:
            # feat 안에 'x', ',' 등으로 여러 아티스트가 있을 수 있음 -> 일단 통째로 사용
            # 구분자 '-', ':' 가 포함되어 있다면 원곡 정보일 확률 높음
            if ' - ' in feat:
                # [제목 - 아티스트] 또는 [아티스트 - 제목]
                sub_parts = feat.split(' - ')
                queries.append(f"{sub_parts[0]} {clean_title}")  # 첫 번째 파트 + 제목
                queries.append(f"{sub_parts[1]} {clean_title}")  # 두 번째 파트 + 제목
            else:
                queries.append(f"{feat} {clean_title}")
        
        # 전략 B: [업로더/채널] + [원본 제목] (커버가 아닌 경우에 유효)
        if artist and artist.lower() != 'unknown artist':
            # 커버 관련 키워드가 제목에 없을 때만 높은 우선순위
            if not re.search(r'(?i)(cover|커버|歌ってみた|カバー)', title):
                queries.append(f"{artist} {title}")
        
        # 전략 C: [업로더] + [정제된 제목]
        clean_artist = remove_noise(artist)
        if clean_artist and clean_artist.lower() != 'unknown artist':
            queries.append(f"{clean_artist} {clean_title}")

        # 전략 D: [정제된 제목] 만 (제목이 충분히 고유한 경우)
        if len(clean_title.split()) >= 3 or len(clean_title) >= 15:
            queries.append(clean_title)

        # 전략 D: [원본 제목] (최후의 수단, 사용 안 함)
        # if title != clean_title:
        #    queries.append(title)

        # 중복 제거 및 리스트 반환
        seen = set()
        unique_queries = []
        for q in queries:
            q_clean = q.lower().strip()
            if q_clean and len(q_clean) > 1 and q_clean not in seen:
                seen.add(q_clean)
                unique_queries.append(q)
                
        return unique_queries[:5]  # 상위 5개 시도
    
    def _clean_string(self, text: str) -> str:
        """문자열 전처리 (특수문자 및 노이즈 제거)"""
        # 1. 괄호 안 내용 제거: [MV], (Official), 【Cover】 등
        text = re.sub(r'\[.*?\]', ' ', text)
        text = re.sub(r'\(.*?\)', ' ', text)
        text = re.sub(r'\{.*?\}', ' ', text)
        text = re.sub(r'【.*?】', ' ', text)
        text = re.sub(r'「.*?」', ' ', text)
        
        # 2. 특수 키워드 제거
        keywords = ['official video', 'mv', 'm/v', 'lyric video', 'lyrics', 'feat.', 'prod.', 'cover']
        text_lower = text.lower()
        for kw in keywords:
            if kw in text_lower:
                text = re.sub(f'(?i){re.escape(kw)}', '', text)
        
        # 3. 특수문자 제거 후 공백 정리
        text = re.sub(r'[^\w\s\-\']', ' ', text)  # 알파벳, 숫자, 공백, 하이픈, 따옴표 제외 제거
        return re.sub(r'\s+', ' ', text).strip()

if __name__ == "__main__":
    fetcher = LyricsFetcher()
    
    # 테스트 곡
    test_cases = [
        ("Enemy [Imagine Dragons x J.I.D] / 하나코 나나 COVER", "하나코 나나 HANAKO NANA"),
        ("비행정 [飛行艇 - King Gnu] / 하나코 나나 COVER", "하나코 나나 HANAKO NANA"),
        ("Dynamite (Official Video)", "BTS"),
    ]
    
    for title, artist in test_cases:
        print(f"\n검색 요청: {title} - {artist}")
        print("-" * 40)
        
        lyrics = fetcher.get_lyrics(title, artist)
        if lyrics:
            print(">> 가사 찾음!")
            print(lyrics[:100] + "...")
        else:
            print(">> 가사 못 찾음")
