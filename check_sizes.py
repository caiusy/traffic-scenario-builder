from PIL import Image

# 检查车辆图片尺寸
yellow = Image.open('assets_source/yellow.png')
red = Image.open('assets_source/red.png')
camera = Image.open('assets_source/camera.png')

print("原始素材尺寸:")
print(f"  黄色车辆: {yellow.size[0]}x{yellow.size[1]} 像素")
print(f"  红色车辆: {red.size[0]}x{red.size[1]} 像素")
print(f"  摄像头:   {camera.size[0]}x{camera.size[1]} 像素")
print(f"\n目标车道高度: 93 像素")
print(f"需要调整车辆高度到 93px")
