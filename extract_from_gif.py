#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从用户提供的GIF/PNG图片自动提取车辆和摄像头素材
"""

import cv2
import numpy as np
from pathlib import Path
import sys


def extract_assets_from_image(image_path):
    """从图片提取素材"""
    
    print("="*60)
    print("正在提取素材...")
    print("="*60)
    
    # 读取图片
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"❌ 无法读取图片: {image_path}")
        return False
    
    print(f"✓ 图片尺寸: {img.shape[1]}x{img.shape[0]} 像素")
    
    # 创建输出目录
    output_dir = Path("vehicle_assets")
    output_dir.mkdir(exist_ok=True)
    
    # 保存原图作为参考
    cv2.imwrite(str(output_dir / "original.png"), img)
    print(f"✓ 原图已保存: {output_dir}/original.png")
    
    # 转换为HSV
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # 1. 提取黄色车辆
    print("\n提取黄色车辆...")
    yellow_lower = np.array([20, 100, 100])
    yellow_upper = np.array([35, 255, 255])
    yellow_mask = cv2.inRange(hsv, yellow_lower, yellow_upper)
    
    # 形态学处理
    kernel = np.ones((3, 3), np.uint8)
    yellow_mask = cv2.morphologyEx(yellow_mask, cv2.MORPH_CLOSE, kernel)
    yellow_mask = cv2.morphologyEx(yellow_mask, cv2.MORPH_OPEN, kernel)
    
    # 找到车辆轮廓
    contours, _ = cv2.findContours(yellow_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    vehicle_count = 0
    for i, contour in enumerate(contours):
        area = cv2.contourArea(contour)
        if area > 150:  # 过滤小噪点
            x, y, w, h = cv2.boundingRect(contour)
            
            # 提取车辆（带边距）
            margin = 2
            x1 = max(0, x - margin)
            y1 = max(0, y - margin)
            x2 = min(img.shape[1], x + w + margin)
            y2 = min(img.shape[0], y + h + margin)
            
            vehicle_roi = img[y1:y2, x1:x2].copy()
            
            # 保存
            output_path = output_dir / f"vehicle_{vehicle_count}.png"
            cv2.imwrite(str(output_path), vehicle_roi)
            print(f"  ✓ 车辆 {vehicle_count}: {w}x{h} px → {output_path}")
            vehicle_count += 1
    
    # 2. 提取黑色摄像头
    print("\n提取黑色摄像头...")
    
    # 黑色范围（更宽松）
    black_lower = np.array([0, 0, 0])
    black_upper = np.array([180, 255, 100])
    black_mask = cv2.inRange(hsv, black_lower, black_upper)
    
    # 形态学处理
    black_mask = cv2.morphologyEx(black_mask, cv2.MORPH_CLOSE, kernel)
    
    # 找到摄像头轮廓
    contours, _ = cv2.findContours(black_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    camera_count = 0
    for i, contour in enumerate(contours):
        area = cv2.contourArea(contour)
        if 200 < area < 4000:  # 摄像头大小范围
            x, y, w, h = cv2.boundingRect(contour)
            
            # 长宽比检查
            aspect_ratio = w / h if h > 0 else 0
            if 0.5 < aspect_ratio < 3.0:
                # 提取摄像头
                margin = 2
                x1 = max(0, x - margin)
                y1 = max(0, y - margin)
                x2 = min(img.shape[1], x + w + margin)
                y2 = min(img.shape[0], y + h + margin)
                
                camera_roi = img[y1:y2, x1:x2].copy()
                
                # 保存
                output_path = output_dir / f"camera_{camera_count}.png"
                cv2.imwrite(str(output_path), camera_roi)
                print(f"  ✓ 摄像头 {camera_count}: {w}x{h} px → {output_path}")
                camera_count += 1
    
    # 3. 创建干净的道路背景模板（6个区域，每个3车道）
    print("\n创建道路背景...")
    
    # 提取灰色道路区域
    gray_lower = np.array([0, 0, 60])
    gray_upper = np.array([180, 50, 140])
    road_mask = cv2.inRange(hsv, gray_lower, gray_upper)
    
    # 提取白色车道线
    white_lower = np.array([0, 0, 180])
    white_upper = np.array([180, 50, 255])
    white_mask = cv2.inRange(hsv, white_lower, white_upper)
    
    # 合并
    combined_mask = cv2.bitwise_or(road_mask, white_mask)
    road_bg = cv2.bitwise_and(img, img, mask=combined_mask)
    
    cv2.imwrite(str(output_dir / "road_background.png"), road_bg)
    print(f"  ✓ 道路背景: {output_dir}/road_background.png")
    
    # 保存掩码用于调试
    cv2.imwrite(str(output_dir / "debug_yellow_mask.png"), yellow_mask)
    cv2.imwrite(str(output_dir / "debug_black_mask.png"), black_mask)
    
    print("\n" + "="*60)
    print(f"✓ 提取完成！共提取 {vehicle_count} 个车辆, {camera_count} 个摄像头")
    print(f"输出目录: {output_dir}/")
    print("="*60)
    
    return True


def main():
    """主函数"""
    
    print("\n车辆轨迹素材提取工具\n")
    
    # 检查是否有命令行参数
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        # 询问用户
        print("请提供图片路径（支持拖拽）：")
        image_path = input("> ").strip().strip("'\"")
    
    if not Path(image_path).exists():
        print(f"\n❌ 文件不存在: {image_path}")
        print("\n提示：您可以将图片拖入终端窗口")
        return 1
    
    # 提取素材
    success = extract_assets_from_image(image_path)
    
    if success:
        print("\n✓ 素材提取成功！现在可以运行编辑器了：")
        print("   python3 vehicle_editor_with_assets.py")
        return 0
    else:
        print("\n❌ 素材提取失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
