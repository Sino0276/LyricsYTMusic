import PyInstaller.__main__
import os
import shutil

from PyInstaller.utils.hooks import collect_data_files

# 데이터 파일 수집
# pykakasi 데이터 파일이 누락되는 문제 해결
datas = collect_data_files('pykakasi')
datas += collect_data_files('certifi') # SSL 인증서 파일 문제 해결

# 빌드 옵션
options = [
    'main.py',
    '--name=LyricsYTMusic',
    '--noconsole',
    '--onedir',  # 폴더 형태로 빌드 (디버깅 및 파일 관리 용이)
    '--noconfirm', # 기존 배포 폴더 삭제 시 확인 안 함
    '--clean',   # 캐시 정리
    '--icon=icon.ico', # 아이콘 추가
]

# 수집된 데이터 파일을 옵션에 추가 (--add-data "src;dest")
for source, dest in datas:
    options.append(f'--add-data={source}{os.pathsep}{dest}')

# PyInstaller 실행
print("Building LyricsYTMusic...")
PyInstaller.__main__.run(options)

# 설정 파일 복사
print("Copying configuration files...")
dist_dir = os.path.join('dist', 'LyricsYTMusic')
files_to_copy = ['settings.json', 'member_colors.json']

if not os.path.exists(dist_dir):
    print(f"Error: Build directory not found at {dist_dir}")
    exit(1)

for file in files_to_copy:
    if os.path.exists(file):
        shutil.copy2(file, dist_dir)
        print(f"Copied {file} to {dist_dir}")
    else:
        print(f"Warning: {file} not found locally.")

print("Build complete!")
print(f"Executable located at: {os.path.abspath(dist_dir)}")
