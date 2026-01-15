#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
素材透明度修复工具
只让边缘背景透明，保持车身和摄像头本体不透明
"""

from PIL import Image
import numpy as np
from pathlib import Path


def make_background_transparent(image_path, output_path, bg_color_range, threshold=30):
    """
    只移除背景色，保持主体不透明
    
    Args:
        image_path: 输入图片路径
        output_path: 输出图片路径
        bg_color_range: 背景色范围 [(r_min, r_max), (g_min, g_max), (b_min, b_max)]
        threshold: 颜色匹配阈值
    """
    # 打开图片
    img = Image.open(image_path).convert('RGBA')
    data = np.array(img)
    
    # 分离颜色通道
    r, g, b, a = data[:, :, 0], data[:, :, 1], data[:, :, 2], data[:, :, 3]
    
    # 创建背景遮罩（只匹配背景色）
    if isinstance(bg_color_range, tuple) and len(bg_color_range) == 3:
        # 单一颜色范围
        (r_min, r_max), (g_min, g_max), (b_min, b_max) = bg_color_range
        mask = (
            (r >= r_min - threshold) & (r <= r_max + threshold) &
            (g >= g_min - threshold) & (g <= g_max + threshold) &
            (b >= b_min - threshold) & (b <= b_max + threshold)
        )
    else:
        # 多个颜色范围
        mask = np.zeros(r.shape, dtype=bool)
        for color_range in bg_color_range:
            (r_min, r_max), (g_min, g_max), (b_min, b_max) = color_range
            mask |= (
                (r >= r_min - threshold) & (r <= r_max + threshold) &
                (g >= g_min - threshold) & (g <= g_max + threshold) &
                (b >= b_min - threshold) & (b <= b_max + threshold)
            )
    
    # 只让背景透明
    data[mask, 3] = 0  # 背景完全透明
    
    # 保存结果
    result = Image.fromarray(data, 'RGBA')
    result.save(output_path, 'PNG')
    print(f"✓ 已处理: {image_path.name} -> {output_path.name}")
    return result


def process_vehicle(input_path, output_path):
    """
    处理车辆图片：移除灰色背景，保留车身
    """
    # 灰色背景范围（根据您提供的图片，背景是浅灰色）
    gray_bg_ranges = [
        ((150, 180), (150, 180), (150, 180)),  # 中灰色
        ((180, 200), (180, 200), (180, 200)),  # 浅灰色
        ((100, 150), (100, 150), (100, 150)),  # 深灰色
    ]
    
    make_background_transparent(
        input_path, 
        output_path, 
        gray_bg_ranges,
        threshold=40
    )


def process_camera(input_path, output_path):
    """
    处理摄像头图片：移除黑色/深色背景，保留摄像头本体
    """
    # 黑色背景范围
    dark_bg_ranges = [
        ((0, 50), (0, 50), (0, 50)),  # 纯黑到深灰
    ]
    
    make_background_transparent(
        input_path, 
        output_path, 
        dark_bg_ranges,
        threshold=30
    )


def main():
    """主处理流程"""
    source_dir = Path("assets_source")
    output_dir = Path("assets/vehicles")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("开始处理素材：只让边缘背景透明")
    print("=" * 60)
    
    # 处理车辆
    vehicle_files = {
        "red.png": "red_vehicle.png",
        "yellow.png": "yellow_vehicle.png",
    }
    
    for input_name, output_name in vehicle_files.items():
        input_path = source_dir / input_name
        output_path = output_dir / output_name
        
        if input_path.exists():
            print(f"\n处理车辆: {input_name}")
            process_vehicle(input_path, output_path)
        else:
            print(f"⚠ 未找到文件: {input_path}")
    
    # 处理摄像头
    camera_input = source_dir / "camera.png"
    camera_output = output_dir / "camera.png"
    
    if camera_input.exists():
        print(f"\n处理摄像头: camera.png")
        process_camera(camera_input, camera_output)
    else:
        print(f"⚠ 未找到文件: {camera_input}")
    
    print("\n" + "=" * 60)
    print("✅ 所有素材处理完成！")
    print(f"输出目录: {output_dir.absolute()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
