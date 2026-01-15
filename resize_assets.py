#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调整车辆和摄像头素材尺寸到标准高度（93px，匹配道路车道宽度）
"""

from PIL import Image
from pathlib import Path

def resize_to_height(image_path, output_path, target_height=93):
    """
    调整图片高度，保持宽高比
    
    Args:
        image_path: 输入图片路径
        output_path: 输出图片路径
        target_height: 目标高度（像素）
    """
    img = Image.open(image_path)
    
    # 计算新尺寸（保持宽高比）
    original_width, original_height = img.size
    aspect_ratio = original_width / original_height
    new_height = target_height
    new_width = int(target_height * aspect_ratio)
    
    # 使用高质量的重采样
    resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # 保存
    resized.save(output_path)
    
    print(f"  {original_width}×{original_height} → {new_width}×{new_height}")
    
    return resized

def main():
    assets_dir = Path("vehicle_trajectory_editor/assets/vehicles")
    
    # 处理所有车辆和摄像头
    for img_file in assets_dir.glob("*.png"):
        print(f"\n调整: {img_file.name}")
        resize_to_height(img_file, img_file, target_height=93)
        print(f"✓ 已保存")
    
    print("\n✅ 完成！所有素材已调整到93px高度")

if __name__ == "__main__":
    main()
