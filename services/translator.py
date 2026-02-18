"""
가사 번역 및 발음 표기 모듈.
사용자 언어가 아닌 가사에 대해 번역과 로마자/한글 발음을 제공합니다.
히라가나 매핑 테이블은 core/constants.py에서 임포트합니다.
"""

import locale
import os
import re
from typing import Optional

from langdetect import detect, DetectorFactory
from deep_translator import GoogleTranslator
import pykakasi

from core.constants import (
    HIRAGANA_TO_HANGUL,
    JAPANESE_READING_OVERRIDES,
    JONGSEONG_MAP,
    N_AS_M_CHARS,
    N_AS_N_CHARS,
    TRANSLATION_BATCH_SIZE,
    TRANSLATION_SAMPLE_COUNT,
    TRANSLATION_SEPARATOR,
    TRANSLATION_THRESHOLD,
    YOUON_TO_HANGUL,
)
from core.models import TranslatedLine

# 재현성을 위한 시드 고정
DetectorFactory.seed = 0


class LyricsTranslator:
    """가사 번역 및 발음 표기"""

    # 로마자 발음이 필요한 언어들 (비라틴 문자)
    NEEDS_ROMANIZATION: frozenset[str] = frozenset({"ja", "ko", "zh-cn", "zh-tw", "ar", "he", "th", "ru"})

    # langdetect → Google Translator 언어 코드 매핑
    LANG_MAP: dict[str, str] = {
        "zh-cn": "zh-CN",
        "zh-tw": "zh-TW",
    }

    # 언어 이름 → ISO 639-1 코드 매핑
    _LANG_NAME_TO_CODE: dict[str, str] = {
        "korean": "ko", "japanese": "ja", "english": "en",
        "chinese": "zh-CN", "spanish": "es", "french": "fr",
        "german": "de", "portuguese": "pt", "russian": "ru", "italian": "it",
    }

    def __init__(self, target_lang: Optional[str] = None) -> None:
        """
        Args:
            target_lang: 번역 목표 언어. None이면 Windows 시스템 언어 사용
        """
        self.target_lang = target_lang or self._get_system_language()
        self._cache: dict[str, TranslatedLine] = {}
        self.kks = pykakasi.kakasi()
        print(f"[번역] 타겟 언어: {self.target_lang}")

    # ── 시스템 언어 감지 ──────────────────────────────────────────────────────

    def _get_system_language(self) -> str:
        """Windows 시스템 언어 가져오기"""
        try:
            loc = locale.getlocale()[0]
            if not loc:
                loc = os.environ.get("LANG", os.environ.get("LC_ALL", ""))
            if loc:
                lang_part = loc.split("_")[0].split("-")[0].lower()
                if lang_part in self._LANG_NAME_TO_CODE:
                    return self._LANG_NAME_TO_CODE[lang_part]
                if len(lang_part) == 2:
                    return lang_part
        except Exception:
            pass
        return "ko"  # 기본값: 한국어

    # ── 언어 감지 ─────────────────────────────────────────────────────────────

    def _contains_japanese(self, text: str) -> bool:
        """일본어 문자(히라가나, 카타카나, 한자) 포함 여부 확인"""
        return bool(re.search(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FBF]", text))

    def needs_translation(self, text: str) -> bool:
        """번역이 필요한지 확인 (타겟 언어와 다른 경우)"""
        if not text:
            return False
        is_jp = self._contains_japanese(text)
        if not is_jp and len(text.strip()) < 2:
            return False
        if is_jp and self.target_lang != "ja":
            return True
        try:
            detected = detect(text)
            return detected != self.target_lang and detected != "en"
        except Exception:
            return False

    def should_translate_lyrics(self, lyrics: list[str]) -> bool:
        """
        전체 가사(또는 샘플)를 분석하여 번역이 필요한지 결정.
        샘플 중 TRANSLATION_THRESHOLD 이상이 번역 대상 언어이면 True 반환.
        """
        sample_count = 0
        target_count = 0

        for line in lyrics:
            text = re.sub(r"^\[[\d:.]+\]\s*", "", line).strip()
            if not text or len(text) < 3:
                continue
            sample_count += 1
            if sample_count > TRANSLATION_SAMPLE_COUNT:
                break
            try:
                detected = detect(text)
                if detected != self.target_lang and detected != "en":
                    target_count += 1
            except Exception:
                pass

        if sample_count == 0:
            return False

        # 한국어 타겟일 때, 일본어가 조금이라도 포함되어 있으면 무조건 번역 (J-Pop 로마자 표기를 위해)
        if self.target_lang == "ko":
            # 샘플링된 텍스트 중 일본어 문자가 포함되었는지 확인
            for line in lyrics[:TRANSLATION_SAMPLE_COUNT]:
                text = re.sub(r"^\[[\d:.]+\]\s*", "", line).strip()
                if self._contains_japanese(text):
                    print("[번역] 일본어 문자 감지됨 -> 번역/발음 표기 강제 활성화")
                    return True

        return target_count > 0 and (target_count / sample_count) >= TRANSLATION_THRESHOLD

    # ── 번역 ──────────────────────────────────────────────────────────────────

    def translate_batch(
        self, texts: list[str], batch_size: int = TRANSLATION_BATCH_SIZE
    ) -> list[Optional[TranslatedLine]]:
        """
        여러 줄을 일괄 번역 (속도 향상)

        Returns:
            TranslatedLine 리스트 (번역 불필요/실패 시 None)
        """
        results: list[Optional[TranslatedLine]] = [None] * len(texts)

        # 번역이 필요한 텍스트만 필터링
        to_translate: list[tuple[int, str]] = []
        for i, text in enumerate(texts):
            if not text:
                continue
            clean_text = re.sub(r"^\[[\d:.]+\]\s*", "", text).strip()
            if not clean_text:
                continue
            if not self._contains_japanese(clean_text) and len(clean_text) < 2:
                continue
            cache_key = clean_text.lower()
            if cache_key in self._cache:
                results[i] = self._cache[cache_key]
                continue
            to_translate.append((i, clean_text))

        if not to_translate:
            return results

        # 소스 언어 감지
        try:
            has_japanese = any(self._contains_japanese(t) for _, t in to_translate)
            if has_japanese:
                source_lang = "ja"
            else:
                source_lang = detect(to_translate[0][1])

            if source_lang == self.target_lang or (source_lang == "en" and not has_japanese):
                return results

            src_code = self.LANG_MAP.get(source_lang, source_lang)
            dest_code = self.LANG_MAP.get(self.target_lang, self.target_lang)
        except Exception:
            return results

        # 배치 단위로 번역
        for batch_start in range(0, len(to_translate), batch_size):
            batch = to_translate[batch_start:batch_start + batch_size]
            batch_texts = [item[1] for item in batch]

            try:
                combined = TRANSLATION_SEPARATOR.join(batch_texts)
                translator = GoogleTranslator(source=src_code, target=dest_code)
                translated_combined = translator.translate(combined)
                translated_parts = (
                    translated_combined.split(TRANSLATION_SEPARATOR)
                    if translated_combined
                    else []
                )

                for j, (orig_idx, orig_text) in enumerate(batch):
                    translation = translated_parts[j].strip() if j < len(translated_parts) else ""
                    romanization = ""
                    if source_lang == "ja" and self.target_lang == "ko":
                        romanization = self._transliterate_japanese_to_korean(orig_text)

                    result = TranslatedLine(
                        original=orig_text,
                        translation=translation,
                        romanization=romanization,
                        original_lang=source_lang,
                    )
                    self._cache[orig_text.lower()] = result
                    results[orig_idx] = result

            except Exception as e:
                print(f"[번역] 배치 처리 오류: {e}")
                for orig_idx, orig_text in batch:
                    result = self.translate_line(orig_text)
                    if result:
                        results[orig_idx] = result

        return results

    def translate_line(self, text: str) -> Optional[TranslatedLine]:
        """한 줄 번역 및 발음 표기"""
        if not text:
            return None

        clean_text = re.sub(r"^\[[\d:.]+\]\s*", "", text).strip()
        if not clean_text:
            return None
        if not self._contains_japanese(clean_text) and len(clean_text) < 2:
            return None

        cache_key = clean_text.lower()
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            is_japanese = self._contains_japanese(clean_text)
            if is_japanese:
                source_lang = "ja"
            else:
                try:
                    source_lang = detect(clean_text)
                except Exception:
                    return None

            if source_lang == self.target_lang or source_lang == "en":
                return None

            src_code = self.LANG_MAP.get(source_lang, source_lang)
            dest_code = self.LANG_MAP.get(self.target_lang, self.target_lang)

            translator = GoogleTranslator(source=src_code, target=dest_code)
            translation = translator.translate(clean_text)

            romanization = ""
            if source_lang == "ja" and self.target_lang == "ko":
                romanization = self._transliterate_japanese_to_korean(clean_text)

            translated = TranslatedLine(
                original=clean_text,
                translation=translation or "",
                romanization=romanization,
                original_lang=source_lang,
            )
            self._cache[cache_key] = translated
            return translated

        except Exception as e:
            print(f"[번역] 오류: {e}")
            return None

    # ── 일본어 → 한글 발음 변환 ───────────────────────────────────────────────

    def _transliterate_japanese_to_korean(self, text: str) -> str:
        """일본어 → 한글 발음 변환 (PyKakasi + 매핑)"""
        # 가사에서 자주 쓰이는 단어의 읽는 법 강제 (긴 단어부터 치환)
        temp_text = text
        for key in sorted(JAPANESE_READING_OVERRIDES.keys(), key=len, reverse=True):
            temp_text = temp_text.replace(key, JAPANESE_READING_OVERRIDES[key])

        # PyKakasi로 히라가나 변환
        result = self.kks.convert(temp_text)
        hiragana_text = "".join([item["hira"] for item in result])

        return self._map_hiragana_to_hangul(hiragana_text)

    def _map_hiragana_to_hangul(self, text: str) -> str:
        """히라가나 문자열을 한글로 매핑 (constants의 테이블 사용)"""
        result: list[str] = []
        i = 0

        while i < len(text):
            char = text[i]
            next_char = text[i + 1] if i + 1 < len(text) else None

            # 카타카나 → 히라가나 변환
            if "\u30a0" <= char <= "\u30ff":
                char = chr(ord(char) - 0x60)
            next_char_hira = (
                chr(ord(next_char) - 0x60)
                if next_char and "\u30a0" <= next_char <= "\u30ff"
                else next_char
            )

            # 1. 요음 처리 (2글자 조합)
            if next_char_hira and next_char_hira in "ゃゅょ":
                combo = char + next_char_hira
                if combo in YOUON_TO_HANGUL:
                    result.append(YOUON_TO_HANGUL[combo])
                    i += 2
                    continue

            # 2. ん 발음 처리 (맥락 기반)
            if char == "ん":
                if next_char_hira and next_char_hira in N_AS_M_CHARS:
                    result.append("ㅁ")
                elif next_char_hira and next_char_hira in N_AS_N_CHARS:
                    result.append("ㄴ")
                else:
                    result.append("ㄴ")
                i += 1
                continue

            # 3. 촉음 (っ) 처리 - 임시 마커
            if char in ("っ", "ッ"):
                result.append("ッ")
                i += 1
                continue

            # 4. 장음 (ー) 처리
            if char in ("ー", "ー"):
                if result:
                    result.append("-")
                i += 1
                continue

            # 5. 기본 매핑
            result.append(HIRAGANA_TO_HANGUL.get(char, char))
            i += 1

        # 후처리: 촉음 마커를 받침 ㅅ으로 변환
        output = "".join(result).replace("ッ", "ㅅ")

        # 받침 ㅁ, ㄴ, ㅇ 등을 앞 글자에 붙이기 (한글 유니코드 조합)
        final_result: list[str] = []
        chars = list(output)
        i = 0

        while i < len(chars):
            char = chars[i]
            next_char = chars[i + 1] if i + 1 < len(chars) else None

            if next_char in JONGSEONG_MAP and "가" <= char <= "힣":
                char_code = ord(char) - 0xAC00
                jong = char_code % 28

                if jong == 0:  # 받침 없음
                    cho = char_code // 588
                    jung = (char_code % 588) // 28
                    new_jong = JONGSEONG_MAP[next_char]
                    new_char = chr(0xAC00 + cho * 588 + jung * 28 + new_jong)
                    final_result.append(new_char)
                    i += 2
                    continue

            final_result.append(char)
            i += 1

        return "".join(final_result)
