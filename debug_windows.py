"""브라우저 창 제목 디버그 스크립트"""
import win32gui

print("=" * 60)
print("브라우저 창 제목 디버깅")
print("=" * 60)

def enum_callback(hwnd, results):
    if not win32gui.IsWindowVisible(hwnd):
        return True
    
    class_name = win32gui.GetClassName(hwnd)
    title = win32gui.GetWindowText(hwnd)
    
    # 브라우저 창만 필터링
    if class_name in ["Chrome_WidgetWin_1", "MozillaWindowClass"] and title:
        results.append((class_name, title))
    
    return True

windows = []
win32gui.EnumWindows(enum_callback, windows)

print(f"\n찾은 브라우저 창 ({len(windows)}개):\n")
for class_name, title in windows:
    browser = "Firefox" if "Mozilla" in class_name else "Chrome/Edge"
    print(f"[{browser}] {title}")
    
    # YouTube Music 관련 체크
    if "youtube" in title.lower():
        print(f"  ⬆️ YouTube 관련 창 발견!")

print("\n" + "=" * 60)
