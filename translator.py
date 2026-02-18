
"""
가사 번역 및 발음 표기 모듈.
사용자 언어가 아닌 가사에 대해 번역과 로마자/한글 발음을 제공합니다.
"""

import locale
import re
from dataclasses import dataclass
from typing import Optional
from langdetect import detect, DetectorFactory
from deep_translator import GoogleTranslator
import pykakasi
from pykakasi import kakasi as PyKakasi

# 재현성을 위한 시드 고정
DetectorFactory.seed = 0



@dataclass
class TranslatedLine:
    """번역된 가사 라인"""
    original: str           # 원본 가사
    translation: str        # 번역
    romanization: str       # 발음 (로마자/한글 표기)
    original_lang: str      # 원본 언어 코드


class LyricsTranslator:
    """가사 번역 및 발음 표기"""
    
    # 로마자 발음이 필요한 언어들 (비라틴 문자)
    NEEDS_ROMANIZATION = {'ja', 'ko', 'zh-cn', 'zh-tw', 'ar', 'he', 'th', 'ru'}
    
    # langdetect -> Google Translator 언어 코드 매핑
    LANG_MAP = {
        'zh-cn': 'zh-CN',
        'zh-tw': 'zh-TW',
    }
    
    def __init__(self, target_lang: Optional[str] = None):
        """
        Args:
            target_lang: 번역 목표 언어. None이면 Windows 시스템 언어 사용
        """
        self.target_lang = target_lang or self._get_system_language()
        self._cache: dict[str, TranslatedLine] = {}
        
        # PyKakasi 초기화 (일본어 -> 히라가나 변환용)
        self.kks = pykakasi.kakasi()
        
        print(f"[번역] 타겟 언어: {self.target_lang}")
    
    def _get_system_language(self) -> str:
        """Windows 시스템 언어 가져오기"""
        # 언어 이름 -> ISO 639-1 코드 매핑
        LANG_NAME_TO_CODE = {
            'korean': 'ko',
            'japanese': 'ja',
            'english': 'en',
            'chinese': 'zh-CN',
            'spanish': 'es',
            'french': 'fr',
            'german': 'de',
            'portuguese': 'pt',
            'russian': 'ru',
            'italian': 'it',
        }
        
        try:
            # Windows 로케일에서 언어 코드 추출
            # Python 3.11+에서 getdefaultlocale()은 deprecated
            # getlocale()을 먼저 시도하고 실패 시 fallback
            loc = locale.getlocale()[0]
            if not loc:
                # fallback: 환경 변수에서 직접 가져오기
                import os
                loc = os.environ.get('LANG', os.environ.get('LC_ALL', ''))
            if loc:
                # "Korean" -> "ko", "Korean_Korea" -> "ko"
                lang_part = loc.split('_')[0].split('-')[0].lower()
                
                # 전체 언어 이름인 경우 코드로 변환
                if lang_part in LANG_NAME_TO_CODE:
                    return LANG_NAME_TO_CODE[lang_part]
                
                # 이미 코드 형태면 그대로 반환 (예: 'ko', 'ja')
                if len(lang_part) == 2:
                    return lang_part
                    
        except Exception:
            pass
        return 'ko'  # 기본값: 한국어
    
    
    def _contains_japanese(self, text: str) -> bool:
        """일본어 문자(히라가나, 카타카나) 포함 여부 확인"""
        # 히라가나: 3040-309F
        # 카타카나: 30A0-30FF
        # 한자: 4E00-9FBF (한중일 공통이지만 맥락상 포함 고려, 단 여기선 확실한 일본어 감지를 위해 가나 위주)
        # 하지만 '君', '僕', '愛' 등 한자로만 된 가사도 있으므로 한자도 포함하되, 
        # 한국어/중국어와 구분하기 위해 가나와 혼용된 경우를 우선순위로 두는 로직은 별도 처리
        # 여기서는 단순히 문자 범위 체크
        return bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FBF]', text))

    def needs_translation(self, text: str) -> bool:
        """번역이 필요한지 확인 (타겟 언어와 다른 경우)"""
        if not text:
            return False
            
        # 일본어 문자가 포함되어 있으면 길이 1이라도 허용 (한자 등)
        is_jp = self._contains_japanese(text)
        
        if not is_jp and len(text.strip()) < 2:
            return False
        
        # 일본어 문자가 포함되어 있고 타겟이 일본어가 아니면 무조건 번역 필요
        if is_jp and self.target_lang != 'ja':
            return True
            
        try:
            detected = detect(text)
            return detected != self.target_lang and detected != 'en'
        except Exception:
            return False

    def should_translate_lyrics(self, lyrics: list[str]) -> bool:
        """
        전체 가사(또는 샘플)를 분석하여 번역이 필요한지 결정
        하나 이상의 라인이 번역 대상 언어인 경우 True 반환
        """
        sample_count = 0
        target_count = 0
        
        for line in lyrics:
            text = re.sub(r'^\[[\d:.]+\]\s*', '', line).strip()
            if not text or len(text) < 3:
                continue
            
            sample_count += 1
            if sample_count > 10:  # 최대 10줄만 샘플링
                break
                
            try:
                detected = detect(text)
                # 타겟 언어도 아니고 영어도 아니면 번역 필요
                if detected != self.target_lang and detected != 'en':
                    target_count += 1
            except Exception:
                pass
        
        # 샘플 중 30% 이상이 번역 필요 언어면 True
        # ZeroDivisionError 방지
        if sample_count == 0:
            return False
        return target_count > 0 and (target_count / sample_count) >= 0.3
    
    def translate_batch(self, texts: list[str], batch_size: int = 10) -> list[Optional[TranslatedLine]]:
        """
        여러 줄을 일괄 번역 (속도 향상)
        
        Args:
            texts: 번역할 텍스트 리스트
            batch_size: 한 번에 번역할 줄 수 (기본 10줄)
        
        Returns:
            TranslatedLine 리스트 (번역 불필요/실패 시 None)
        """
        results = [None] * len(texts)
        
        # 번역이 필요한 텍스트만 필터링
        to_translate = []  # (원본 인덱스, 정제된 텍스트)
        
        for i, text in enumerate(texts):
            if not text:
                continue
            
            clean_text = re.sub(r'^\[[\d:.]+\]\s*', '', text).strip()
            if not clean_text:
                continue
                
            # 일본어는 한 글자도 허용
            if not self._contains_japanese(clean_text) and len(clean_text) < 2:
                continue
            
            # 캐시 확인
            cache_key = clean_text.lower()
            if cache_key in self._cache:
                results[i] = self._cache[cache_key]
                continue
            
            to_translate.append((i, clean_text))
        
        if not to_translate:
            return results
        
        # 첫 번째 텍스트로 언어 감지
        try:
            # 배치 내에 일본어가 포함되어 있는지 확인 (우선순위 높음)
            has_japanese = False
            for _, text in to_translate:
                if self._contains_japanese(text):
                    has_japanese = True
                    break
            
            if has_japanese:
                source_lang = 'ja'
            else:
                sample_text = to_translate[0][1]
                source_lang = detect(sample_text)
            
            if source_lang == self.target_lang or (source_lang == 'en' and not has_japanese):
                return results
            
            src_code = self.LANG_MAP.get(source_lang, source_lang)
            dest_code = self.LANG_MAP.get(self.target_lang, self.target_lang)
            
        except Exception:
            return results
        
        # 배치 단위로 번역
        SEPARATOR = " ||| "  # 구분자
        
        for batch_start in range(0, len(to_translate), batch_size):
            batch = to_translate[batch_start:batch_start + batch_size]
            batch_texts = [item[1] for item in batch]
            
            try:
                # 여러 줄을 구분자로 합침
                combined = SEPARATOR.join(batch_texts)
                
                # 한 번에 번역
                translator = GoogleTranslator(source=src_code, target=dest_code)
                translated_combined = translator.translate(combined)
                
                # 결과 분리
                translated_parts = translated_combined.split(SEPARATOR) if translated_combined else []
                
                # 결과 매핑
                for j, (orig_idx, orig_text) in enumerate(batch):
                    translation = translated_parts[j].strip() if j < len(translated_parts) else ""
                    
                    # 발음 표기
                    romanization = ""
                    if source_lang == 'ja' and self.target_lang == 'ko':
                        romanization = self._transliterate_japanese_to_korean(orig_text)
                    
                    result = TranslatedLine(
                        original=orig_text,
                        translation=translation,
                        romanization=romanization,
                        original_lang=source_lang
                    )
                    
                    # 캐시 저장
                    cache_key = orig_text.lower()
                    self._cache[cache_key] = result
                    results[orig_idx] = result
                    
            except Exception as e:
                print(f"[번역] 배치 처리 오류: {e}")
                # 배치 실패 시 개별 번역으로 폴백
                for orig_idx, orig_text in batch:
                    result = self.translate_line(orig_text)
                    if result:
                        results[orig_idx] = result
        
        return results
    
    def translate_line(self, text: str) -> Optional[TranslatedLine]:
        """
        한 줄 번역 및 발음 표기
        
        Returns:
            TranslatedLine 또는 번역 불필요/실패 시 None
        """
        if not text:
            return None
            
        # 타임스탬프나 메타데이터 제외
        clean_text = re.sub(r'^\[[\d:.]+\]\s*', '', text).strip()
        if not clean_text:
            return None

        # 일본어는 한 글자도 허용 (君, 愛 등)
        if not self._contains_japanese(clean_text) and len(clean_text) < 2:
            return None
        
        # 캐시 확인
        cache_key = clean_text.lower()
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            # 1. 일본어 강제 감지 (언어 감지 라이브러리보다 우선)
            # langdetect는 짧은 텍스트나 한자 단독일 때 오류가 발생하거나 부정확함
            is_japanese = self._contains_japanese(clean_text)
            
            if is_japanese:
                source_lang = 'ja'
            else:
                try:
                    source_lang = detect(clean_text)
                except Exception:
                    # 감지 실패 시, 일본어 문자가 없으면 영어로 가정하거나 스킵
                    # 여기서는 안전하게 스킵
                    return None
            
            # 타겟 언어와 같거나 영어면 번역 불필요 (단, 일본어 감지된 경우는 예외 가능성 있음)
            if source_lang == self.target_lang:
                return None
            
            # 영어로 감지되었지만 일본어가 섞여있지 않은 순수 영어인 경우만 건너뜀
            if source_lang == 'en':
                return None
            
            # 언어 코드 변환
            
            # 언어 코드 변환
            src_code = self.LANG_MAP.get(source_lang, source_lang)
            dest_code = self.LANG_MAP.get(self.target_lang, self.target_lang)
            
            # 번역
            translator = GoogleTranslator(source=src_code, target=dest_code)
            translation = translator.translate(clean_text)
            
            # 발음 표기 (일본어 -> 한글)
            romanization = ""
            if source_lang == 'ja' and self.target_lang == 'ko':
                romanization = self._transliterate_japanese_to_korean(clean_text)
            elif source_lang in self.NEEDS_ROMANIZATION:
                # 다른 언어는 현재 미지원
                romanization = ""
            
            translated = TranslatedLine(
                original=clean_text,
                translation=translation or "",
                romanization=romanization,
                original_lang=source_lang
            )
            
            self._cache[cache_key] = translated
            return translated
            
        except Exception as e:
            print(f"[번역] 오류: {e}")
            return None
    
    def _transliterate_japanese_to_korean(self, text: str) -> str:
        """일본어 -> 한글 발음 변환 (PyKakasi + 매핑)"""
        # 가사에서 자주 쓰이는 인칭대명사의 읽는 법 강제 (Heuristic)
        # 또한 가사에서 자주 쓰이는 단어들의 읽는 법 고정 (Context)
        overrides = {
            "愛しい": "いとしい", # Itoshii
            "愛してる": "あいしてる",
            "愛して": "あいして",
            "愛": "あい",
            "君": "きみ",
            "僕": "ぼく",
            "俺": "おれ",
            "私": "わたし",
            "側に": "そばに",
            "側で": "そばで",
            "瞳": "ひとみ",
            "光": "ひかり",
            "闇": "やみ",
            "空": "そら",
            "風": "かぜ",
            "涙": "なみだ",
        }
        
        # 긴 단어부터 치환하여 부분 일치 문제 방지
        temp_text = text
        for key in sorted(overrides.keys(), key=len, reverse=True):
            temp_text = temp_text.replace(key, overrides[key])
        
        # 1. PyKakasi로 히라가나 변환 (한자 등 처리)
        result = self.kks.convert(temp_text)
        hiragana_text = "".join([item['hira'] for item in result])
        
        # 2. 히라가나 -> 한글 매핑
        return self._map_hiragana_to_hangul(hiragana_text)

    def _map_hiragana_to_hangul(self, text: str) -> str:
        """히라가나 문자열을 한글로 매핑 (개선된 버전)"""
        
        # 기본 히라가나 → 한글 매핑
        hiragana_map = {
            'あ': '아', 'い': '이', 'う': '우', 'え': '에', 'お': '오',
            'か': '카', 'き': '키', 'く': '쿠', 'け': '케', 'こ': '코',
            'さ': '사', 'し': '시', 'す': '스', 'せ': '세', 'そ': '소',
            'た': '타', 'ち': '치', 'つ': '츠', 'て': '테', 'と': '토',
            'な': '나', 'に': '니', 'ぬ': '누', 'ね': '네', 'の': '노',
            'は': '하', 'ひ': '히', 'ふ': '후', 'へ': '헤', 'ほ': '호',
            'ま': '마', 'み': '미', 'む': '무', 'め': '메', 'も': '모',
            'や': '야', 'ゆ': '유', 'よ': '요',
            'ら': '라', 'り': '리', 'る': '루', 'れ': '레', 'ろ': '로',
            'わ': '와', 'を': '오',
            'が': '가', 'ぎ': '기', 'ぐ': '구', 'げ': '게', 'ご': '고',
            'ざ': '자', 'じ': '지', 'ず': '즈', 'ぜ': '제', 'ぞ': '조',
            'だ': '다', 'ぢ': '지', 'づ': '즈', 'で': '데', 'ど': '도',
            'ば': '바', 'び': '비', 'ぶ': '부', 'べ': '베', 'ぼ': '보',
            'ぱ': '파', 'ぴ': '피', 'ぷ': '푸', 'ぺ': '페', 'ぽ': '포',
            # 작은 모음
            'ぁ': '아', 'ぃ': '이', 'ぅ': '우', 'ぇ': '에', 'ぉ': '오',
        }
        
        # 요음 (拗音) 조합 매핑
        youon_map = {
            'きゃ': '캬', 'きゅ': '큐', 'きょ': '쿄',
            'しゃ': '샤', 'しゅ': '슈', 'しょ': '쇼',
            'ちゃ': '챠', 'ちゅ': '츄', 'ちょ': '쵸',
            'にゃ': '냐', 'にゅ': '뉴', 'にょ': '뇨',
            'ひゃ': '햐', 'ひゅ': '휴', 'ひょ': '효',
            'みゃ': '먀', 'みゅ': '뮤', 'みょ': '묘',
            'りゃ': '랴', 'りゅ': '류', 'りょ': '료',
            'ぎゃ': '갸', 'ぎゅ': '규', 'ぎょ': '교',
            'じゃ': '쟈', 'じゅ': '쥬', 'じょ': '죠',
            'びゃ': '뱌', 'びゅ': '뷰', 'びょ': '뵤',
            'ぴゃ': '퍄', 'ぴゅ': '퓨', 'ぴょ': '표',
        }
        
        # ん 발음 규칙 (뒤따르는 글자에 따라)
        # ㅁ: ま행, ば행, ぱ행 앞
        # ㄴ: な행, た행, だ행, ら행 앞
        # ㅇ: 그 외 (か행, が행, あ행, や행, わ행, 문장 끝 등)
        n_as_m = set('まみむめもばびぶべぼぱぴぷぺぽ')
        n_as_n = set('なにぬねのたちつてとだぢづでどらりるれろ')
        
        # 모음 (장음 처리용)
        vowel_to_hangul = {'a': '아', 'i': '이', 'u': '우', 'e': '에', 'o': '오'}
        last_vowel = None  # 마지막 모음 추적
        
        result = []
        i = 0
        
        while i < len(text):
            char = text[i]
            next_char = text[i + 1] if i + 1 < len(text) else None
            
            # 카타카나 → 히라가나 변환
            if '\u30a0' <= char <= '\u30ff':
                char = chr(ord(char) - 0x60)
            if next_char and '\u30a0' <= next_char <= '\u30ff':
                next_char_hira = chr(ord(next_char) - 0x60)
            else:
                next_char_hira = next_char
            
            # 1. 요음 처리 (2글자 조합)
            if next_char_hira and next_char_hira in 'ゃゅょ':
                combo = char + next_char_hira
                if combo in youon_map:
                    result.append(youon_map[combo])
                    last_vowel = combo[-1]  # 대략적인 모음 추적
                    i += 2
                    continue
            
            # 2. ん 발음 처리 (맥락 기반)
            if char == 'ん':
                if next_char_hira and next_char_hira in n_as_m:
                    result.append('ㅁ')  # 받침으로 처리
                elif next_char_hira and next_char_hira in n_as_n:
                    result.append('ㄴ')  # 받침으로 처리
                else:
                    # 문장 끝이나 기타 등등의 경우
                    # 한국어 표기법상 받침 'ㄴ'이 표준에 가까움 (기존 'ㅇ'에서 변경)
                    # 예: じかん(지칸), みかん(미칸), きりん(기린)
                    # 단, idiomatic하게 'ㅇ'으로 들리는 경우도 있으나(스미마셍), 'ㄴ'이 더 범용적 (스미마센)
                    result.append('ㄴ')
                i += 1
                continue
            
            # 3. 촉음 (っ) 처리 - 다음 자음 앞에서 받침처럼
            if char == 'っ' or char == 'ッ':
                result.append('ッ')  # 임시 마커 (나중에 처리)
                i += 1
                continue
            
            # 4. 장음 (ー) 처리 - 앞 모음 반복 또는 '-'
            if char == 'ー' or char == 'ー':
                if result:
                    # 앞 글자의 마지막 모음을 연장
                    result.append('-')
                i += 1
                continue
            
            # 5. 기본 매핑
            if char in hiragana_map:
                result.append(hiragana_map[char])
            else:
                result.append(char)
            
            i += 1
        
        # 후처리: 촉음 마커를 받침으로 변환
        output = ''.join(result)
        
        # ッ + 자음 → 받침 + 자음
        # 예: ずっと (zutto) -> 즛토
        # 'ッ'를 'ㅅ' 받침으로 처리하는 것이 한국어 표기법에 가까움 (단, 뒤 자음에 따라 다름)
        # 여기서는 단순화를 위해 'ㅅ'으로 통일 (사이시옷 느낌)
        output = output.replace('ッ', 'ㅅ')
        
        # 받침 ㅁ, ㄴ, ㅇ를 앞 글자에 붙이기 (한글 조합)
        final_result = []
        i = 0
        chars = list(output)
        
        while i < len(chars):
            char = chars[i]
            next_char = chars[i + 1] if i + 1 < len(chars) else None
            
            # 받침 처리
            if next_char in ('ㅁ', 'ㄴ', 'ㅇ', 'ㄹ', 'ㄱ', 'ㅂ', 'ㅅ') and char >= '가' and char <= '힣':
                # 이미 받침이 없는 경우에만 추가
                char_code = ord(char) - 0xAC00
                jong = char_code % 28
                
                if jong == 0:  # 받침 없음
                    cho = char_code // 588
                    jung = (char_code % 588) // 28
                    
                    jong_map = {'ㅁ': 16, 'ㄴ': 4, 'ㅇ': 21, 'ㄹ': 8, 'ㄱ': 1, 'ㅂ': 17, 'ㅅ': 19}
                    new_jong = jong_map.get(next_char, 0)
                    
                    if new_jong != 0:
                        new_char = chr(0xAC00 + cho * 588 + jung * 28 + new_jong)
                        final_result.append(new_char)
                        i += 2
                        continue
            
            final_result.append(char)
            i += 1
        
        return ''.join(final_result)

if __name__ == "__main__":
    print("번역 테스트")
    print("=" * 50)
    
    # 한국어 타겟
    translator = LyricsTranslator(target_lang='ko')
    
    test_lines = [
        "星が降る夜に僕は願う",  # 일본어
        "Tomorrow never knows",    # 영어
    ]
    
    for line in test_lines:
        print(f"\n원본: {line}")
        result = translator.translate_line(line)
        if result:
            print(f"  언어: {result.original_lang}")
            print(f"  번역: {result.translation}")
            print(f"  발음: {result.romanization}")
        else:
            print("  (번역 불필요)")
