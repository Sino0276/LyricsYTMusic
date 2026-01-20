
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
        try:
            # Windows 로케일에서 언어 코드 추출
            loc = locale.getdefaultlocale()[0]  # 예: 'ko_KR', 'en_US', 'ja_JP'
            if loc:
                lang_code = loc.split('_')[0]  # 'ko', 'en', 'ja'
                return lang_code
        except Exception:
            pass
        return 'ko'  # 기본값: 한국어
    
    def needs_translation(self, text: str) -> bool:
        """번역이 필요한지 확인 (타겟 언어와 다른 경우)"""
        if not text or len(text.strip()) < 3:
            return False
        
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
        return target_count > 0 and (target_count / sample_count) >= 0.3
    
    def translate_line(self, text: str) -> Optional[TranslatedLine]:
        """
        한 줄 번역 및 발음 표기
        
        Returns:
            TranslatedLine 또는 번역 불필요/실패 시 None
        """
        if not text or len(text.strip()) < 2:
            return None
        
        # 타임스탬프나 메타데이터 제외
        clean_text = re.sub(r'^\[[\d:.]+\]\s*', '', text).strip()
        if not clean_text:
            return None
        
        # 캐시 확인
        cache_key = clean_text.lower()
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            # 언어 감지
            source_lang = detect(clean_text)
            
            # 타겟 언어와 같거나 영어면 번역 불필요
            if source_lang == self.target_lang or source_lang == 'en':
                return None
            
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
        # 1. PyKakasi로 히라가나 변환 (한자 등 처리)
        result = self.kks.convert(text)
        hiragana_text = "".join([item['hira'] for item in result])
        
        # 2. 히라가나 -> 한글 매핑
        return self._map_hiragana_to_hangul(hiragana_text)

    def _map_hiragana_to_hangul(self, text: str) -> str:
        """히라가나 문자열을 한글로 매핑"""
        hiragana_map = {
            'あ': '아', 'い': '이', 'う': '우', 'え': '에', 'お': '오',
            'か': '카', 'き': '키', 'く': '쿠', 'け': '케', 'こ': '코',
            'さ': '사', 'し': '시', 'す': '스', 'せ': '세', 'そ': '소',
            'た': '타', 'ち': '치', 'つ': '츠', 'て': '테', 'と': '토',
            'な': '나', 'に': '니', 'ぬ': '누', 'ね': '네', 'の': '노',
            'は': '하', 'ひ': '히', 'ふ': '후', 'へ': '헤', 'ほ': '호',
            'ま': '마', 'み': '미', 'む': '무', 'め': '메', '모': '모',
            'や': '야', 'ゆ': '유', 'よ': '요',
            'ら': '라', 'り': '리', 'る': '루', 'れ': '레', 'ろ': '로',
            'わ': '와', 'を': '오', 'ん': '응',
            'が': '가', 'ぎ': '기', 'ぐ': '구', 'げ': '게', 'ご': '고',
            'ざ': '자', 'じ': '지', 'ず': '즈', 'ぜ': '제', 'ぞ': '조',
            'だ': '다', 'ぢ': '지', 'づ': '즈', 'で': '데', 'ど': '도',
            'ば': '바', 'び': '비', 'ぶ': '부', 'べ': '베', 'ぼ': '보',
            'ぱ': '파', 'ぴ': '피', 'ぷ': '푸', 'ぺ': '페', 'ぽ': '포',
            # 작은 카타카나/히라가나
            'ぁ': '아', 'ぃ': '이', 'ぅ': '우', 'ぇ': '에', 'ぉ': '오',
            'っ': '읏',
            'ゃ': '야', 'ゅ': '유', 'ょ': '요',
            # 장음 등
            'ー': '', # 장음은 보통 생략하거나 앞 모음 연장인데 여기선 생략
        }
        
        result = []
        skip_next = False
        
        for i, char in enumerate(text):
            if skip_next:
                skip_next = False
                continue
                
            # 요음 처리 (예: きゃ -> 캬) - 단순화를 위해 뒷글자 위주로 처리하거나
            # 여기서는 PyKakasi가 히라가나로 분리해줬으므로 단순 매핑 시도
            # 더 정교한 요음 처리가 필요하지만 일단 1:1 매핑
            
            if char in hiragana_map:
                result.append(hiragana_map[char])
            elif '\u30a0' <= char <= '\u30ff':  # 카타카나
                hira = chr(ord(char) - 0x60)
                if hira in hiragana_map:
                    result.append(hiragana_map[hira])
                elif char == 'ッ':
                     result.append('읏')
                else:
                    result.append(char)
            else:
                result.append(char)
        
        return "".join(result)

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
