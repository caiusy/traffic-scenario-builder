#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
去除车辆和摄像头PNG图片的背景色，创建透明背景
"""

from PIL import Image
import numpy as np
from pathlib import Path

def remove_background(image_path, output_path, threshold=30):
    """
    去除图片背景色
    
    Args:
        image_path: 输入图片路径
        output_path: 输出图片路径
        threshold: 颜色相似度阈值
    """
    img = Image.open(image_path).convert("RGBA")
    data = np.array(img)
    
    # 获取四个角的颜色（假设角落是背景色）
    h, w = data.shape[:2]
    corners = [
        data[0, 0],
        data[0, w-1],
        data[h-1, 0],
        data[h-1, w-1]
    ]
    
    # 使用最常见的角落颜色作为背景色
    bg_color = corners[0][:3]  # RGB部分
    
    print(f"  背景色: RGB{tuple(bg_color)}")
    
    # 创建mask：与背景色相似的像素
    r, g, b, a = data[:, :, 0], data[:, :, 1], data[:, :, 2], data[:, :, 3]
    
    # 计算与背景色的距离
    color_diff = np.sqrt(
        (r.astype(float) - bg_color[0])**2 +
        (g.astype(float) - bg_color[1])**2 +
        (b.astype(float) - bg_color[2])**2
    )
    
    # 相似度高的像素设为透明
    mask = color_diff < threshold
    data[mask, 3] = 0  # 设置alpha为0（透明）
    
    # 保存
    result = Image.fromarray(data, 'RGBA')
    result.save(output_path)
    
    transparent_pixels = np.sum(mask)
    total_pixels = h * w
    print(f"  透明像素: {transparent_pixels}/{total_pixels} ({100*transparent_pixels/total_pixels:.1f}%)")
    
    return result

def main():
    # 输入输出目录
    input_dir = Path("/Users/caius/Documents/素材")
    output_dir = Path("vehicle_trajectory_editor/assets")
    
    # 创建输出目录
    (output_dir / "vehicles").mkdir(parents=True, exist_ok=True)
    
    # 处理车辆和摄像头
    files = [
        ("yellow.png", "vehicles/yellow_vehicle.png"),
        ("red.png", "vehicles/red_vehicle.png"),
        ("camera.png", "vehicles/camera.png"),
    ]
    
    for input_name, output_name in files:
        input_path = input_dir / input_name
        output_path = output_dir / output_name
        
        if not input_path.exists():
            print(f"⚠️  跳过: {input_name} (不存在)")
            continue
        
        print(f"\n处理: {input_name}")
        
        # 尝试不同的阈值
        img = remove_background(input_path, output_path, threshold=40)
        
        print(f"✓ 保存到: {output_path}")
    
    print("\n✅ 完成！所有素材已处理为透明背景")

if __name__ == "__main__":
    main()
