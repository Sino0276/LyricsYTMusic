"""가사 검색 디버깅"""
from media_session import get_current_media
import syncedlyrics

print("=" * 50)
print("가사 검색 디버깅")
print("=" * 50)

m = get_current_media()
if m:
    print(f"감지된 곡:")
    print(f"  제목: {m.title}")
    print(f"  아티스트: {m.artist}")
    print()
    
    # 원래 검색어로 시도
    query1 = f"{m.title} {m.artist}"
    print(f"검색어 1: {query1}")
    result1 = syncedlyrics.search(query1)
    print(f"결과: {'찾음' if result1 else '없음'}")
    
    # 제목만으로 시도
    print(f"\n검색어 2: {m.title}")
    result2 = syncedlyrics.search(m.title)
    print(f"결과: {'찾음' if result2 else '없음'}")
    
    # 제목에서 특수문자/괄호 제거 후 시도
    import re
    clean_title = re.sub(r'[\[\](){}]', '', m.title)
    clean_title = re.sub(r'\s+', ' ', clean_title).strip()
    
    if clean_title != m.title:
        print(f"\n검색어 3 (정리): {clean_title}")
        result3 = syncedlyrics.search(clean_title)
        print(f"결과: {'찾음' if result3 else '없음'}")
    
    # 첫 번째 단어만 (곡 제목 핵심)
    first_word = m.title.split()[0] if m.title else ""
    if first_word and len(first_word) > 2:
        print(f"\n검색어 4 (첫 단어): {first_word}")
        result4 = syncedlyrics.search(first_word)
        print(f"결과: {'찾음' if result4 else '없음'}")
        
else:
    print("미디어 없음")
