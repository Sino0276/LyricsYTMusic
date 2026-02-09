import pathlib

file_path = pathlib.Path('overlay_ui.py')
try:
    content = file_path.read_text(encoding='utf-8')
    # "Segoe UI"를 DEFAULT_FONT로 치환
    # 주의: DEFAULT_FONT 상수는 이미 추가되어 있어야 함 (이전 단계에서 완료)
    new_content = content.replace('"Segoe UI"', 'DEFAULT_FONT')
    
    if content == new_content:
        print("No changes made (string not found or already replaced).")
    else:
        file_path.write_text(new_content, encoding='utf-8')
        print(f"Successfully replaced font in {file_path}")
except Exception as e:
    print(f"Error: {e}")
