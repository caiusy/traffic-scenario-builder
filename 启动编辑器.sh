#!/bin/bash

echo "🚀 启动车辆轨迹编辑器 V2..."
echo ""
echo "✅ 功能检查："
echo "  • 文字可拖动"
echo "  • 摄像头可拖动"
echo "  • 车辆初始位置可拖动"
echo "  • 深色背景 + 可配置左侧留白"
echo "  • 轨迹点支持停留时长"
echo "  • 自动视图缩放"
echo ""
echo "📂 工作目录: $(pwd)"
echo ""

# 检查依赖
if ! python3 -c "import PyQt6" 2>/dev/null; then
    echo "❌ 错误: PyQt6 未安装"
    echo "   请运行: pip3 install PyQt6"
    exit 1
fi

if ! python3 -c "import cv2" 2>/dev/null; then
    echo "❌ 错误: OpenCV 未安装"
    echo "   请运行: pip3 install opencv-python"
    exit 1
fi

if ! python3 -c "import numpy" 2>/dev/null; then
    echo "❌ 错误: NumPy 未安装"
    echo "   请运行: pip3 install numpy"
    exit 1
fi

# 检查素材
if [ ! -d "assets" ]; then
    echo "⚠️  警告: assets 目录不存在"
    echo "   编辑器将在没有素材的情况下启动"
fi

echo "✅ 依赖检查完成"
echo ""
echo "🎬 启动编辑器..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python3 vehicle_editor_v2.py
