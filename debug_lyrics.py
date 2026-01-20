"""가사 파싱 디버깅"""
from lyrics_fetcher import LyricsFetcher
from lyrics_parser import LyricsParser

f = LyricsFetcher()
p = LyricsParser()

# 현재 곡으로 테스트
titles = [
    ("シル・ヴ・プレジデント", "ナナホシ管弦楽団"),
    ("シルヴプレジデント", ""),
]

for title, artist in titles:
    print(f"\n{'='*50}")
    print(f"검색: {title} - {artist}")
    
    lyrics = f.get_lyrics(title, artist)
    
    if lyrics:
        print(f"가사 길이: {len(lyrics)}")
        print("원본 가사 첫 500자:")
        print(lyrics[:500])
        print("\n파싱 결과:")
        lines = p.parse(lyrics)
        print(f"총 라인 수: {len(lines)}")
        for i, line in enumerate(lines[:10]):
            print(f"  {i}: [{line.member or ''}] {line.text[:50]}...")
    else:
        print("가사 없음")
