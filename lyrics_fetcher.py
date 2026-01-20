"""
가사를 검색하고 가져오는 모듈.
syncedlyrics 라이브러리를 사용하여 시간 동기화된 LRC 가사를 검색합니다.
파일 기반 캐싱을 지원하여 반복 검색 속도를 획기적으로 개선합니다.
"""

import re
import json
import os
from typing import Optional
import syncedlyrics

class LyricsFetcher:
    """가사 검색 및 가져오기 (파일 캐싱 지원)"""
    
    CACHE_FILE = "lyrics_cache.json"
    
    # 검색 시도 횟수 제한 (속도 개선을 위해 축소)
    MAX_SEARCH_ATTEMPTS = 2
    
    def __init__(self):
        self._cache = {}
        self._load_cache()

    # ... (생략된 메서드들) ...

    def search_candidates(self, query: str) -> list[tuple[str, str]]:
        """
        주어진 쿼리로 여러 소스에서 가사 후보 검색
        
        Returns:
            [(ProviderName, LyricsSnippet), ...]
        """
        results = []
        # 검색할 프로바이더 목록
        providers = [
            'musixmatch', 
            'netease', 
            'lrclib', 
            'megalobiz'
        ]
        
        print(f"[수동검색] 쿼리: {query}")
        
        # 순차 검색 (병렬 처리가 더 좋지만, winsdk 등과의 충돌 방지 및 안전성을 위해 순차)
        for prov in providers:
            try:
                print(f"[수동검색] 소스: {prov}")
                # 특정 프로바이더만 지정하여 검색
                lrc = syncedlyrics.search(query, providers=[prov])
                
                if lrc:
                    results.append((prov, lrc))
                    
            except Exception as e:
                print(f"[수동검색] 오류 ({prov}): {e}")
                
        return results

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

    def get_lyrics(self, title: str, artist: str, duration_ms: Optional[int] = None) -> Optional[str]:
        """
        가사 검색 (LRC 형식)
        
        Args:
            title: 곡 제목
            artist: 아티스트
            duration_ms: 곡 길이 (밀리초) - 유효성 검증용
        """
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
        
        print(f"[가사] 검색 시작: {title} - {artist} (길이: {duration_ms}ms)")
        
        # 검색어 생성
        queries = self._generate_search_queries(title, artist)
        
        for i, query in enumerate(queries):
            # 검색 횟수 제한 (속도 이슈)
            if i >= self.MAX_SEARCH_ATTEMPTS:
                break
                
            try:
                print(f"[가사] 검색 시도 ({i+1}/{len(queries)}): {query}")
                
                # syncedlyrics 검색
                # enhanced=True는 더 많은 provider를 사용하지만 느릴 수 있음
                lrc_content = syncedlyrics.search(query)
                
                if lrc_content:
                    # 유효성 검증
                    if self._validate_lyrics(lrc_content, duration_ms):
                        print(f"[가사] 가사 찾음 (쿼리: {query})")
                        self._save_to_cache(cache_key, lrc_content)
                        return lrc_content
                    else:
                         print(f"[가사] 가사 길이 불일치, 무시함 (쿼리: {query})")
                
                # 너무 빠른 요청 방지
                time.sleep(0.5)
                
            except Exception as e:
                print(f"[가사] 검색 오류 (쿼리: {query}): {e}")
        
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
            
            # 오차 범위: 20초 (인트로/아웃트로 차이 고려)
            diff = abs(lrc_duration_ms - target_duration_ms)
            
            if diff > 20000: # 20초 이상 차이나면 다른 곡일 확률 높음
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
        
        # 전략 A: [추출된 아티스트] + [정제된 제목] (가장 정확할 수 있음)
        for feat in featured_artists:
            # feat 안에 'x', ',' 등으로 여러 아티스트가 있을 수 있음 -> 일단 통째로 사용
            # 구분자 '-', ':' 가 포함되어 있다면 원곡 정보일 확률 높음
            if ' - ' in feat:
                # [제목 - 아티스트] 또는 [아티스트 - 제목]
                sub_parts = feat.split(' - ')
                queries.append(f"{sub_parts[1]} {sub_parts[0]}")
                queries.append(f"{sub_parts[0]} {sub_parts[1]}")
            else:
                queries.append(f"{feat} {clean_title}")
                queries.append(f"{clean_title} {feat}")

        # 전략 B: [기존 아티스트] + [정제된 제목]
        clean_artist = remove_noise(artist)
        if clean_artist and clean_artist.lower() != 'unknown artist':
            queries.append(f"{clean_artist} {clean_title}")
            queries.append(f"{clean_title} {clean_artist}")

        # 전략 C: [정제된 제목] 만
        # 정확도를 위해 단독 제목 검색은 제거하거나 조건을 강화합니다.
        # 제목이 3단어 이상이거나 길이가 15자 이상일 때만 허용
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
