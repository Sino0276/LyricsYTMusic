from system_tray import create_icon_image

if __name__ == "__main__":
    # Windows 아이콘에 필요한 다양한 크기 생성
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    images = []
    
    for size in sizes:
        images.append(create_icon_image(size=size[0]))
        
    # 첫 번째 이미지를 저장하면서 나머지를 append
    images[0].save("icon.ico", format="ICO", sizes=sizes, append_images=images[1:])
    print(f"Icon saved to icon.ico with sizes: {sizes}")
