
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.getcwd())

try:
    from services.translator import LyricsTranslator
    print("Translator imported successfully.")
except ImportError as e:
    print(f"Failed to import LyricsTranslator: {e}")
    sys.exit(1)

translator = LyricsTranslator(target_lang="ko")

# Test Cases
test_lyrics_jp = [
    "[00:12.34] 輝く星空の下で",
    "[00:15.67] 君の手を握りしめた",
    "[00:18.90] この瞬間が永遠に",
    "[00:22.12] 続けばいいのに"
]

test_lyrics_en = [
    "[00:12.34] Under the shining starry sky",
    "[00:15.67] I held your hand tight",
    "[00:18.90] I wish this moment",
    "[00:22.12] Could last forever"
]

test_lyrics_ko = [
    "[00:12.34] 반짝이는 밤하늘 아래",
    "[00:15.67] 너의 손을 꽉 잡았어",
    "[00:18.90] 이 순간이 영원히",
    "[00:22.12] 계속되길 바래"
]

test_lyrics_mixed = [
    "[00:12.34] Yeah, check it out",
    "[00:15.67] 君想ふ夜 (Kimi Omofu Yoru)",
    "[00:18.90] So beautiful night",
    "[00:22.12] 忘れないで (Wasurenaide)"
]

test_lyrics_mostly_en_little_jp = [
    "[00:10.00] This is a song in English",
    "[00:15.00] With a lot of English lines",
    "[00:20.00] Going on and on",
    "[00:25.00] But suddenly",
    "[00:30.00] 愛してる (Aishiteru)",
    "[00:35.00] Back to English now"
]

def run_test(name, lyrics):
    print(f"\n--- Test: {name} ---")
    should = translator.should_translate_lyrics(lyrics)
    print(f"Should translate? {should}")
    
    if should:
        results = translator.translate_batch(lyrics)
        for i, res in enumerate(results):
            if res:
                print(f"[{i}] Orig: {res.original}")
                print(f"    Trans: {res.translation}")
                print(f"    Rom: {res.romanization}")
            else:
                print(f"[{i}] No translation result.")

run_test("Japanese", test_lyrics_jp)
run_test("English", test_lyrics_en)
run_test("Korean", test_lyrics_ko)
run_test("Mixed (JP+EN)", test_lyrics_mixed)
run_test("Mostly English with little JP", test_lyrics_mostly_en_little_jp)
