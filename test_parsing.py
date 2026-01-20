"""제목 파싱 테스트"""
from track_detector import TrackDetector

d = TrackDetector()

tests = [
    "Enemy{Imagine Dragons x J.I.D] / 하나코 나나 COVER | YouTube Music",
    "Rainy Days | YouTube Music",
    "Dynamite - BTS | YouTube Music",
    "Shape of You (feat. Ed Sheeran) | YouTube Music",
    "MONEY - LISA | YouTube Music",
]

print("제목 파싱 테스트:")
print("=" * 60)
for t in tests:
    raw = t.replace(" | YouTube Music", "")
    title, artist = d._extract_title_artist(raw)
    print(f"입력: {t[:50]}...")
    print(f"  -> 제목: {title}")
    print(f"  -> 아티스트: {artist}")
    print()
