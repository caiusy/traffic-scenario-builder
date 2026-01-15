#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从road.svg生成7张道路PNG图片
使用macOS的qlmanage工具
"""

import os
import subprocess
from pathlib import Path
from PIL import Image

def generate_roads():
    """从road.svg生成7张道路图片"""
    
    source_svg = Path("/Users/caius/Documents/素材/road.svg")
    output_dir = Path("vehicle_trajectory_editor/assets/roads")
    temp_dir = Path("vehicle_trajectory_editor/temp")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    print("开始生成道路图片...")
    print(f"源文件: {source_svg}")
    print(f"输出目录: {output_dir}")
    print()
    
    if not source_svg.exists():
        print(f"❌ 错误: 找不到road.svg文件: {source_svg}")
        return False
    
    # 先将SVG转换为一张PNG
    try:
        # 使用sips (macOS内置工具)
        temp_png = temp_dir / "road_temp.png"
        
        # 方法1: 使用sips
        subprocess.run([
            'sips', '-s', 'format', 'png',
            str(source_svg),
            '--out', str(temp_png)
        ], check=True, capture_output=True)
        
        print(f"✓ SVG转换成功")
        
        # 使用PIL调整大小并复制7份
        img = Image.open(temp_png)
        # 调整到目标尺寸
        img = img.resize((2000, 420), Image.Resampling.LANCZOS)
        
        # 生成7张图片
        for i in range(7):
            output_file = output_dir / f"road_{i}.png"
            img.save(output_file, 'PNG')
            print(f"✓ 生成: {output_file.name}")
        
        print()
        print("="*50)
        print("✓ 所有道路图片生成完成！")
        print(f"共生成 7 张道路图片")
        print(f"位置: {output_dir}")
        print("="*50)
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"✗ sips转换失败: {e}")
        print("尝试备用方案...")
        
        # 备用方案：直接复制SVG文件
        print("\n使用备用方案：复制SVG文件")
        for i in range(7):
            output_file = output_dir / f"road_{i}.svg"
            subprocess.run(['cp', str(source_svg), str(output_file)], check=True)
            print(f"✓ 复制: {output_file.name}")
        
        print()
        print("="*50)
        print("✓ 已复制SVG文件")
        print(f"共生成 7 张道路SVG文件")
        print(f"位置: {output_dir}")
        print("="*50)
        
        return True
        
    except Exception as e:
        print(f"✗ 处理失败: {e}")
        return False

if __name__ == '__main__':
    generate_roads()
