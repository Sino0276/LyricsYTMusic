# YouTube Music 가사 오버레이

유튜브 뮤직에서 현재 재생 중인 곡의 가사를 화면에 오버레이로 표시하는 Python 애플리케이션입니다.

## ✨ 기능

- 🎵 **자동 곡 감지**: 브라우저에서 재생 중인 YouTube Music 곡 자동 감지
- 📝 **실시간 가사 표시**: 시간 동기화된 LRC 가사 지원
- 🌐 **다중 브라우저 지원**: Chrome, Edge, Firefox
- 🖱️ **드래그 & 리사이즈**: 자유로운 창 위치 및 크기 조절
- 🕛 **싱크 조절** 음악/가사 싱크 조절
- 🔎 **수동 검색** 원하는 음악 수동 검색

## 📋 요구사항

- Python 3.10 이상
- Windows OS
- Chrome, Edge, 또는 Firefox 브라우저

## 🚀 설치

```bash
cd LyricsYTMusic
pip install -r requirements.txt
```

## ▶️ 실행

```bash
python main.py
```

## 🎮 사용법

1. 브라우저에서 [YouTube Music](https://music.youtube.com)을 열어주세요
2. 음악을 재생하세요
3. 오버레이 창에 가사가 자동으로 표시됩니다

### 창 조작

| 동작 | 방법 |
|-----|-----|
| 이동 | 타이틀 바 드래그 |
| 크기 조절 | 우하단 ⋮⋮ 드래그 |
| 최소화 | ─ 버튼 |
| 닫기 | ✕ 버튼 |
| 싱크 | 우상단 시계 |
| 검색 | 우상단 돋보기 |


## 📁 프로젝트 구조

```
LyricsYTMusic/
├── main.py              # 메인 진입점
├── track_detector.py    # 곡 감지 모듈
├── lyrics_fetcher.py    # 가사 검색 모듈
├── lyrics_parser.py     # LRC 파싱 모듈
├── member_colors.json   # 색상 데이터
├── overlay_ui.py        # UI 모듈
├── requirements.txt     # 의존성
└── README.md
```

## ⚠️ 참고사항

- 가사는 외부 서비스(syncedlyrics)에서 검색되며, 모든 곡의 가사가 제공되지는 않습니다
- ~~멤버 파트 구분은 가사에 파트 정보가 포함된 경우에만 작동합니다~~
- 자동 검색이 부정확한 가사를 가져올 수도 있습니다. 
