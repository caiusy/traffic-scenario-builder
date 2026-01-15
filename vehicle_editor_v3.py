#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
车辆轨迹可视化编辑器 V3

新增功能：
1. ✅ 深色背景
2. ✅ 可配置的左侧留白区域
3. ✅ 文字、摄像头、车辆可拖动
4. ✅ 车辆初始可拖动定位
5. ✅ 轨迹点停留时长设置
6. ✅ 添加道路时自适应缩放视图
"""

import sys
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QGraphicsEllipseItem, QGraphicsTextItem,
    QSlider, QSpinBox, QDoubleSpinBox, QDialog, QFormLayout,
    QLineEdit, QMessageBox, QFileDialog, QListWidgetItem, QGroupBox,
    QColorDialog, QInputDialog
)
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import (
    QPixmap, QPen, QBrush, QColor, QFont, QPainter, QImage, QTransform
)
import cv2
import numpy as np


class TrajectoryPoint:
    """轨迹点（包含时间和位置）"""
    def __init__(self, x, y, time, pause_duration=0.0):
        self.x = x
        self.y = y
        self.time = time  # 到达此点的时间（秒）
        self.pause_duration = pause_duration  # 在此点停留时长（秒）


class Vehicle:
    """车辆对象"""
    def __init__(self, vehicle_id, pixmap, x=100, y=100, name="", scale=1.0):
        self.id = vehicle_id
        self.pixmap = pixmap
        self.name = name
        self.scale = scale  # 缩放比例（1.0 = 原始大小）
        # 轨迹点列表（中心点坐标）- 初始为空，用户需要手动添加
        self.trajectory = []
        
    def add_trajectory_point(self, x, y, time, pause_duration=0.0):
        """添加轨迹点"""
        self.trajectory.append(TrajectoryPoint(x, y, time, pause_duration))
        
    def get_position_at_time(self, t):
        """根据时间获取位置（线性插值，考虑停留时长）"""
        if len(self.trajectory) == 0:
            return (100, 100)
        
        if len(self.trajectory) == 1:
            return (self.trajectory[0].x, self.trajectory[0].y)
        
        if t <= 0:
            return (self.trajectory[0].x, self.trajectory[0].y)
        
        # 计算考虑停留时长的总时间
        accumulated_time = 0
        for i in range(len(self.trajectory)):
            point = self.trajectory[i]
            
            # 检查是否在当前点的停留时间内
            if i < len(self.trajectory) - 1:
                next_point = self.trajectory[i + 1]
                move_time = next_point.time - point.time
                
                if accumulated_time <= t < accumulated_time + move_time:
                    # 在移动过程中
                    if move_time > 0:
                        ratio = (t - accumulated_time) / move_time
                        x = point.x + (next_point.x - point.x) * ratio
                        y = point.y + (next_point.y - point.y) * ratio
                        return (x, y)
                    else:
                        return (point.x, point.y)
                
                accumulated_time += move_time
                
                # 检查是否在停留时间内
                if accumulated_time <= t < accumulated_time + point.pause_duration:
                    return (point.x, point.y)
                
                accumulated_time += point.pause_duration
        
        # 超出时间范围，返回最后一个点
        return (self.trajectory[-1].x, self.trajectory[-1].y)


class Camera:
    """摄像头对象"""
    def __init__(self, camera_id, pixmap, x, y):
        self.id = camera_id
        self.pixmap = pixmap
        self.x = x
        self.y = y


class TextLabel:
    """文字标注"""
    def __init__(self, text, x, y, font_size=16, color='white'):
        self.text = text
        self.x = x
        self.y = y
        self.font_size = font_size
        self.color = color


class Road:
    """道路对象"""
    def __init__(self, road_id, pixmap, x=0, y=0):
        self.id = road_id
        self.pixmap = pixmap
        self.x = x
        self.y = y


class DraggableTextItem(QGraphicsTextItem):
    """可拖动的文字项"""
    def __init__(self, text_label, editor):
        super().__init__(text_label.text)
        self.text_label = text_label
        self.editor = editor
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable)
        self.setPos(text_label.x, text_label.y)
        
    def mouseReleaseEvent(self, event):
        # 更新数据模型
        pos = self.pos()
        self.text_label.x = pos.x()
        self.text_label.y = pos.y()
        self.editor.update_status(f"文字移动到 ({pos.x():.0f}, {pos.y():.0f})")
        super().mouseReleaseEvent(event)


class DraggablePixmapItem(QGraphicsPixmapItem):
    """可拖动的图片项（用于摄像头和车辆初始位置）"""
    def __init__(self, pixmap, data_object, editor, object_type="item"):
        super().__init__(pixmap)
        self.data_object = data_object  # Camera 或 Vehicle 对象
        self.editor = editor
        self.object_type = object_type
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable)
        
    def mouseReleaseEvent(self, event):
        # 更新数据模型（中心点坐标）
        pos = self.pos()
        pixmap = self.pixmap()
        center_x = pos.x() + pixmap.width() / 2
        center_y = pos.y() + pixmap.height() / 2
        
        if self.object_type == "camera":
            self.data_object.x = center_x
            self.data_object.y = center_y
            self.editor.update_status(f"摄像头移动到 ({center_x:.0f}, {center_y:.0f})")
        elif self.object_type == "vehicle":
            # 只有在没有轨迹或只有一个初始点时才允许拖动车辆
            if len(self.data_object.trajectory) == 0:
                # 更新初始位置并创建第一个轨迹点
                self.data_object.trajectory = [TrajectoryPoint(center_x, center_y, 0.0)]
                self.editor.update_status(f"车辆初始位置设为 ({center_x:.0f}, {center_y:.0f})")
            elif len(self.data_object.trajectory) == 1:
                # 更新唯一的轨迹点
                self.data_object.trajectory[0].x = center_x
                self.data_object.trajectory[0].y = center_y
                self.editor.update_status(f"车辆位置更新到 ({center_x:.0f}, {center_y:.0f})")
        
        super().mouseReleaseEvent(event)


class EditorScene(QGraphicsScene):
    """编辑场景"""
    def __init__(self, parent):
        super().__init__(parent)
        self.editor = parent
        self.selecting_trajectory = False
        self.current_vehicle = None
        
    def mousePressEvent(self, event):
        pos = event.scenePos()
        
        if self.selecting_trajectory and self.current_vehicle:
            # 添加轨迹点（使用中心坐标）
            x, y = pos.x(), pos.y()
            
            # 弹出对话框设置时间和停留时长
            dialog = QDialog(self.editor)
            dialog.setWindowTitle("设置轨迹点参数")
            layout = QFormLayout()
            
            time_spin = QDoubleSpinBox()
            time_spin.setRange(0.0, 60.0)
            
            # 默认时间：上一个点时间 + 1秒
            if self.current_vehicle.trajectory:
                default_time = self.current_vehicle.trajectory[-1].time + 1.0
            else:
                default_time = 0.0
            
            time_spin.setValue(default_time)
            time_spin.setSuffix(" 秒")
            time_spin.setDecimals(1)
            
            pause_spin = QDoubleSpinBox()
            pause_spin.setRange(0.0, 10.0)
            pause_spin.setValue(0.0)
            pause_spin.setSuffix(" 秒")
            pause_spin.setDecimals(1)
            
            layout.addRow("到达时间:", time_spin)
            layout.addRow("停留时长:", pause_spin)
            
            btn_ok = QPushButton("确定")
            btn_ok.clicked.connect(dialog.accept)
            layout.addRow(btn_ok)
            
            dialog.setLayout(layout)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                time = time_spin.value()
                pause = pause_spin.value()
                self.current_vehicle.add_trajectory_point(x, y, time, pause)
                
                self.editor.update_status(f"添加轨迹点 ({x:.0f}, {y:.0f}) @ {time:.1f}s, 停留{pause:.1f}s")
                self.editor.redraw_scene()
        
        super().mousePressEvent(event)


class VehicleEditor(QMainWindow):
    """主编辑器窗口"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("车辆轨迹编辑器 V3")
        self.setGeometry(100, 100, 1600, 900)
        
        # 数据
        self.roads = []  # 道路列表
        self.vehicles = []
        self.cameras = []
        self.text_labels = []
        
        # 素材路径
        self.assets_dir = Path("vehicle_trajectory_editor/assets")
        self.vehicle_pixmaps = {}  # {name: pixmap}
        self.camera_pixmaps = []
        self.road_pixmaps = []
        
        # 场景设置
        self.left_margin = 200  # 左侧留白宽度（像素）
        self.background_color = QColor(30, 30, 30)  # 深色背景
        
        # 动画状态
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.current_time = 0.0
        self.max_time = 10.0
        self.is_playing = False
        self.show_trajectory = True  # 是否显示轨迹
        
        # 选择状态
        self.selected_vehicle = None
        self.selected_camera = None
        self.selected_text = None
        
        # 加载素材
        self.load_assets()
        
        # 创建UI
        self.init_ui()
        
        # 初始化场景（添加一条默认道路）
        if self.road_pixmaps:
            self.add_road(self.left_margin, 0)
        
    def load_assets(self):
        """加载素材"""
        if not self.assets_dir.exists():
            QMessageBox.warning(self, "素材缺失", 
                f"未找到素材目录: {self.assets_dir}\n\n请先运行素材准备脚本")
            return
        
        # 加载道路背景
        roads_dir = self.assets_dir / "roads"
        if roads_dir.exists():
            for road_file in sorted(roads_dir.glob("road_*.png")):
                pixmap = QPixmap(str(road_file))
                self.road_pixmaps.append(pixmap)
                print(f"✓ 加载道路: {road_file.name} ({pixmap.width()}×{pixmap.height()})")
        
        # 加载车辆素材
        vehicles_dir = self.assets_dir / "vehicles"
        if vehicles_dir.exists():
            for vehicle_file in sorted(vehicles_dir.glob("*_vehicle.png")):
                name = vehicle_file.stem.replace("_vehicle", "")
                pixmap = QPixmap(str(vehicle_file))
                self.vehicle_pixmaps[name] = pixmap
                print(f"✓ 加载车辆: {name} ({pixmap.width()}×{pixmap.height()})")
            
            # 加载摄像头
            camera_file = vehicles_dir / "camera.png"
            if camera_file.exists():
                pixmap = QPixmap(str(camera_file))
                self.camera_pixmaps.append(pixmap)
                print(f"✓ 加载摄像头 ({pixmap.width()}×{pixmap.height()})")
        
        print(f"\n素材统计:")
        print(f"  道路: {len(self.road_pixmaps)}张")
        print(f"  车辆: {len(self.vehicle_pixmaps)}种")
        print(f"  摄像头: {len(self.camera_pixmaps)}个")
    
    def init_ui(self):
        """初始化界面"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        
        # 左侧：工具栏
        left_panel = self.create_left_panel()
        left_panel.setMaximumWidth(300)
        main_layout.addWidget(left_panel)
        
        # 中间：画布
        center_panel = self.create_center_panel()
        main_layout.addWidget(center_panel, stretch=1)
        
        # 右侧：属性编辑
        right_panel = self.create_right_panel()
        right_panel.setMaximumWidth(300)
        main_layout.addWidget(right_panel)
    
    def create_left_panel(self):
        """创建左侧工具栏"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # === 道路管理 ===
        road_group = QGroupBox("道路管理")
        road_layout = QVBoxLayout()
        
        btn_add_road = QPushButton("➕ 添加道路")
        btn_add_road.clicked.connect(self.add_road_interactive)
        road_layout.addWidget(btn_add_road)
        
        self.road_list = QListWidget()
        road_layout.addWidget(self.road_list)
        
        road_group.setLayout(road_layout)
        layout.addWidget(road_group)
        
        # === 车辆素材 ===
        vehicle_group = QGroupBox("车辆素材")
        vehicle_layout = QVBoxLayout()
        
        self.vehicle_list = QListWidget()
        for name in sorted(self.vehicle_pixmaps.keys()):
            item = QListWidgetItem(f"{name.upper()} 车辆")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.vehicle_list.addItem(item)
        vehicle_layout.addWidget(self.vehicle_list)
        
        btn_add_vehicle = QPushButton("➕ 添加车辆到场景")
        btn_add_vehicle.clicked.connect(self.add_vehicle_to_scene)
        vehicle_layout.addWidget(btn_add_vehicle)
        
        vehicle_group.setLayout(vehicle_layout)
        layout.addWidget(vehicle_group)
        
        # === 摄像头素材 ===
        camera_group = QGroupBox("摄像头")
        camera_layout = QVBoxLayout()
        
        btn_add_camera = QPushButton("➕ 添加摄像头")
        btn_add_camera.clicked.connect(self.add_camera_to_scene)
        camera_layout.addWidget(btn_add_camera)
        
        camera_group.setLayout(camera_layout)
        layout.addWidget(camera_group)
        
        # === 文字标注 ===
        text_group = QGroupBox("文字标注")
        text_layout = QVBoxLayout()
        
        btn_add_text = QPushButton("➕ 添加文字")
        btn_add_text.clicked.connect(self.add_text_label)
        text_layout.addWidget(btn_add_text)
        
        text_group.setLayout(text_layout)
        layout.addWidget(text_group)
        
        layout.addStretch()
        return panel
    
    def create_center_panel(self):
        """创建中间画布区域"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 画布
        self.scene = EditorScene(self)
        self.scene.setBackgroundBrush(QBrush(self.background_color))  # 设置深色背景
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        layout.addWidget(self.view)
        
        # 时间轴控制
        control_layout = QHBoxLayout()
        
        self.btn_play = QPushButton("▶ 播放")
        self.btn_play.clicked.connect(self.toggle_play)
        control_layout.addWidget(self.btn_play)
        
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setRange(0, 1000)
        self.time_slider.setValue(0)
        self.time_slider.valueChanged.connect(self.on_time_slider_changed)
        control_layout.addWidget(self.time_slider)
        
        self.time_label = QLabel("0.0s")
        control_layout.addWidget(self.time_label)
        
        layout.addLayout(control_layout)
        
        # 状态栏
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)
        
        return panel
    
    def create_right_panel(self):
        """创建右侧属性面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # === 场景设置 ===
        scene_group = QGroupBox("场景设置")
        scene_layout = QVBoxLayout()
        
        # 左侧留白设置
        margin_layout = QHBoxLayout()
        margin_layout.addWidget(QLabel("左侧留白:"))
        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(0, 500)
        self.margin_spin.setValue(self.left_margin)
        self.margin_spin.setSuffix(" px")
        self.margin_spin.valueChanged.connect(self.on_margin_changed)
        margin_layout.addWidget(self.margin_spin)
        scene_layout.addLayout(margin_layout)
        
        scene_group.setLayout(scene_layout)
        layout.addWidget(scene_group)
        
        # === 轨迹编辑 ===
        traj_group = QGroupBox("轨迹编辑")
        traj_layout = QVBoxLayout()
        
        self.vehicle_selector = QListWidget()
        self.vehicle_selector.itemClicked.connect(self.on_vehicle_selected)
        traj_layout.addWidget(QLabel("选择车辆:"))
        traj_layout.addWidget(self.vehicle_selector)
        
        self.btn_edit_trajectory = QPushButton("✏️ 编辑轨迹")
        self.btn_edit_trajectory.setCheckable(True)
        self.btn_edit_trajectory.clicked.connect(self.toggle_trajectory_edit)
        traj_layout.addWidget(self.btn_edit_trajectory)
        
        self.btn_clear_trajectory = QPushButton("🗑️ 清除轨迹")
        self.btn_clear_trajectory.clicked.connect(self.clear_trajectory)
        traj_layout.addWidget(self.btn_clear_trajectory)
        
        # 车辆缩放控制
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("车辆大小:"))
        self.vehicle_scale_spin = QDoubleSpinBox()
        self.vehicle_scale_spin.setRange(0.1, 3.0)
        self.vehicle_scale_spin.setValue(1.0)
        self.vehicle_scale_spin.setSingleStep(0.1)
        self.vehicle_scale_spin.setDecimals(1)
        self.vehicle_scale_spin.setSuffix("x")
        self.vehicle_scale_spin.valueChanged.connect(self.on_vehicle_scale_changed)
        scale_layout.addWidget(self.vehicle_scale_spin)
        traj_layout.addLayout(scale_layout)
        
        # 移除车辆按钮
        self.btn_remove_vehicle = QPushButton("❌ 移除车辆")
        self.btn_remove_vehicle.clicked.connect(self.remove_vehicle)
        traj_layout.addWidget(self.btn_remove_vehicle)
        
        traj_group.setLayout(traj_layout)
        layout.addWidget(traj_group)
        
        # === 摄像头管理 ===
        camera_group = QGroupBox("摄像头管理")
        camera_layout = QVBoxLayout()
        
        self.camera_selector = QListWidget()
        self.camera_selector.itemClicked.connect(self.on_camera_selected)
        camera_layout.addWidget(QLabel("摄像头列表:"))
        camera_layout.addWidget(self.camera_selector)
        
        self.btn_remove_camera = QPushButton("❌ 移除摄像头")
        self.btn_remove_camera.clicked.connect(self.remove_camera)
        camera_layout.addWidget(self.btn_remove_camera)
        
        camera_group.setLayout(camera_layout)
        layout.addWidget(camera_group)
        
        # === 文字编辑 ===
        text_group = QGroupBox("文字编辑")
        text_layout = QVBoxLayout()
        
        self.text_selector = QListWidget()
        self.text_selector.itemClicked.connect(self.on_text_selected)
        text_layout.addWidget(QLabel("选择文字:"))
        text_layout.addWidget(self.text_selector)
        
        # 字体大小
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("大小:"))
        self.text_size_spin = QSpinBox()
        self.text_size_spin.setRange(8, 72)
        self.text_size_spin.setValue(16)
        self.text_size_spin.valueChanged.connect(self.on_text_size_changed)
        size_layout.addWidget(self.text_size_spin)
        text_layout.addLayout(size_layout)
        
        # 颜色
        self.btn_text_color = QPushButton("选择颜色")
        self.btn_text_color.clicked.connect(self.choose_text_color)
        text_layout.addWidget(self.btn_text_color)
        
        # 移除文字按钮
        self.btn_remove_text = QPushButton("❌ 移除文字")
        self.btn_remove_text.clicked.connect(self.remove_text)
        text_layout.addWidget(self.btn_remove_text)
        
        text_group.setLayout(text_layout)
        layout.addWidget(text_group)
        
        # === 导出 ===
        export_group = QGroupBox("导出")
        export_layout = QVBoxLayout()
        
        btn_save_json = QPushButton("💾 保存项目")
        btn_save_json.clicked.connect(self.save_project)
        export_layout.addWidget(btn_save_json)
        
        btn_export_video = QPushButton("🎬 导出视频")
        btn_export_video.clicked.connect(self.export_video)
        export_layout.addWidget(btn_export_video)
        
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)
        
        layout.addStretch()
        return panel
    
    def on_margin_changed(self, value):
        """左侧留白改变"""
        old_margin = self.left_margin
        self.left_margin = value
        
        # 调整所有道路的X坐标
        offset = value - old_margin
        for road in self.roads:
            road.x += offset
        
        self.update_status(f"左侧留白设置为 {value}px")
        self.redraw_scene()
        self.fit_scene_in_view()
    
    def add_road(self, x=0, y=0):
        """添加道路"""
        if not self.road_pixmaps:
            QMessageBox.warning(self, "错误", "没有可用的道路素材")
            return
        
        # 使用第一张道路图片
        road_id = len(self.roads)
        pixmap = self.road_pixmaps[0]
        
        road = Road(road_id, pixmap, x, y)
        self.roads.append(road)
        
        # 更新道路列表
        self.road_list.addItem(f"道路 {road_id}")
        
        self.update_status(f"添加道路 {road_id}")
        self.redraw_scene()
        self.fit_scene_in_view()
    
    def add_road_interactive(self):
        """交互式添加道路"""
        if not self.roads:
            # 第一条道路放在左侧留白之后
            self.add_road(self.left_margin, 0)
        else:
            # 后续道路放在最后一条道路下方
            last_road = self.roads[-1]
            new_y = last_road.y + last_road.pixmap.height()
            self.add_road(self.left_margin, new_y)
    
    def fit_scene_in_view(self):
        """自适应缩放视图以显示所有内容"""
        if self.roads:
            # 计算场景边界
            max_width = 0
            max_height = 0
            
            for road in self.roads:
                max_width = max(max_width, road.x + road.pixmap.width())
                max_height = max(max_height, road.y + road.pixmap.height())
            
            # 设置场景矩形
            self.scene.setSceneRect(0, 0, max_width + 100, max_height + 100)
            
            # 自适应缩放
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
    
    def add_vehicle_to_scene(self):
        """添加车辆到场景"""
        selected = self.vehicle_list.currentItem()
        if not selected:
            QMessageBox.information(self, "提示", "请先选择车辆素材")
            return
        
        vehicle_name = selected.data(Qt.ItemDataRole.UserRole)
        pixmap = self.vehicle_pixmaps[vehicle_name]
        
        # 获取放置位置（在左侧留白右侧）
        x = self.left_margin + 100 + len(self.vehicles) * 50
        y = 150
        
        vehicle_id = len(self.vehicles)
        vehicle = Vehicle(vehicle_id, pixmap, x, y, name=vehicle_name)
        self.vehicles.append(vehicle)
        
        # 更新车辆列表
        self.update_vehicle_list()
        
        self.update_status(f"添加 {vehicle_name} 车辆到场景")
        self.redraw_scene()
    
    def add_camera_to_scene(self):
        """添加摄像头"""
        if not self.camera_pixmaps:
            QMessageBox.warning(self, "错误", "没有可用的摄像头素材")
            return
        
        x = self.left_margin + 200 + len(self.cameras) * 50
        y = 100
        
        camera_id = len(self.cameras)
        camera = Camera(camera_id, self.camera_pixmaps[0], x, y)
        self.cameras.append(camera)
        
        # 更新摄像头列表
        self.update_camera_list()
        
        self.update_status(f"添加摄像头 {camera_id}")
        self.redraw_scene()
    
    def add_text_label(self):
        """添加文字标注"""
        text, ok = QInputDialog.getText(self, "添加文字", "请输入文字内容:")
        if not ok or not text:
            return
        
        x = self.left_margin + 200
        y = 50 + len(self.text_labels) * 30
        
        label = TextLabel(text, x, y)
        self.text_labels.append(label)
        
        # 更新文字列表
        self.update_text_list()
        
        self.update_status(f"添加文字标注: {text}")
        self.redraw_scene()
    
    def on_vehicle_selected(self, item):
        """选择车辆"""
        idx = self.vehicle_selector.row(item)
        if 0 <= idx < len(self.vehicles):
            self.selected_vehicle = self.vehicles[idx]
            # 更新缩放滑块
            self.vehicle_scale_spin.blockSignals(True)
            self.vehicle_scale_spin.setValue(self.selected_vehicle.scale)
            self.vehicle_scale_spin.blockSignals(False)
            self.update_status(f"选中车辆 #{idx} ({self.selected_vehicle.name})")
    
    def on_vehicle_scale_changed(self, value):
        """车辆缩放改变"""
        if self.selected_vehicle:
            self.selected_vehicle.scale = value
            self.update_status(f"车辆缩放: {value}x")
            self.redraw_scene()
    
    def remove_vehicle(self):
        """移除选中的车辆（包括轨迹）"""
        if not self.selected_vehicle:
            QMessageBox.information(self, "提示", "请先选择一个车辆")
            return
        
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除车辆 #{self.selected_vehicle.id} ({self.selected_vehicle.name}) 及其轨迹吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 从列表中移除
            self.vehicles.remove(self.selected_vehicle)
            self.selected_vehicle = None
            
            # 更新UI列表
            self.update_vehicle_list()
            
            self.update_status("车辆已移除")
            self.redraw_scene()
    
    def on_camera_selected(self, item):
        """选择摄像头"""
        idx = self.camera_selector.row(item)
        if 0 <= idx < len(self.cameras):
            self.selected_camera = self.cameras[idx]
            self.update_status(f"选中摄像头 #{idx}")
    
    def remove_camera(self):
        """移除选中的摄像头"""
        selected_item = self.camera_selector.currentItem()
        if not selected_item:
            QMessageBox.information(self, "提示", "请先选择一个摄像头")
            return
        
        idx = self.camera_selector.row(selected_item)
        
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除摄像头 #{idx} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 从列表中移除
            del self.cameras[idx]
            
            # 更新UI列表
            self.update_camera_list()
            
            self.update_status("摄像头已移除")
            self.redraw_scene()
    
    def remove_text(self):
        """移除选中的文字"""
        if not self.selected_text:
            QMessageBox.information(self, "提示", "请先选择一个文字")
            return
        
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除文字 \"{self.selected_text.text}\" 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 从列表中移除
            self.text_labels.remove(self.selected_text)
            self.selected_text = None
            
            # 更新UI列表
            self.update_text_list()
            
            self.update_status("文字已移除")
            self.redraw_scene()
    
    def update_vehicle_list(self):
        """更新车辆列表"""
        self.vehicle_selector.clear()
        for vehicle in self.vehicles:
            self.vehicle_selector.addItem(f"{vehicle.name.upper()} 车辆 #{vehicle.id}")
    
    def update_camera_list(self):
        """更新摄像头列表"""
        self.camera_selector.clear()
        for i, camera in enumerate(self.cameras):
            self.camera_selector.addItem(f"摄像头 #{i}")
    
    def update_text_list(self):
        """更新文字列表"""
        self.text_selector.clear()
        for label in self.text_labels:
            self.text_selector.addItem(f"文字: {label.text}")
    
    def toggle_trajectory_edit(self):
        """切换轨迹编辑模式"""
        if not self.selected_vehicle:
            QMessageBox.information(self, "提示", "请先选择一个车辆")
            self.btn_edit_trajectory.setChecked(False)
            return
        
        if self.btn_edit_trajectory.isChecked():
            self.scene.selecting_trajectory = True
            self.scene.current_vehicle = self.selected_vehicle
            self.update_status(f"轨迹编辑模式：点击画布添加轨迹点")
        else:
            self.scene.selecting_trajectory = False
            self.scene.current_vehicle = None
            self.update_status("退出轨迹编辑模式")
    
    def clear_trajectory(self):
        """清除选中车辆的轨迹"""
        if not self.selected_vehicle:
            QMessageBox.information(self, "提示", "请先选择一个车辆")
            return
        
        if len(self.selected_vehicle.trajectory) > 0:
            # 保留初始点
            first_point = self.selected_vehicle.trajectory[0]
            self.selected_vehicle.trajectory = [first_point]
        
        self.update_status("轨迹已清除")
        self.redraw_scene()
    
    def on_text_selected(self, item):
        """选择文字"""
        idx = self.text_selector.row(item)
        if 0 <= idx < len(self.text_labels):
            self.selected_text = self.text_labels[idx]
            self.text_size_spin.setValue(self.selected_text.font_size)
            self.update_status(f"选中文字: {self.selected_text.text}")
    
    def on_text_size_changed(self, value):
        """修改文字大小"""
        if self.selected_text:
            self.selected_text.font_size = value
            self.redraw_scene()
    
    def choose_text_color(self):
        """选择文字颜色"""
        if not self.selected_text:
            QMessageBox.information(self, "提示", "请先选择一个文字")
            return
        
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_text.color = color.name()
            self.redraw_scene()
    
    def redraw_scene(self):
        """重绘场景"""
        self.scene.clear()
        
        # 绘制道路
        for road in self.roads:
            item = QGraphicsPixmapItem(road.pixmap)
            item.setPos(road.x, road.y)
            self.scene.addItem(item)
        
        # 绘制摄像头（可拖动）
        for camera in self.cameras:
            # 使用摄像头中心点定位
            item = DraggablePixmapItem(camera.pixmap, camera, self, "camera")
            item.setPos(camera.x - camera.pixmap.width() / 2, 
                       camera.y - camera.pixmap.height() / 2)
            self.scene.addItem(item)
        
        # 绘制车辆和轨迹
        for vehicle in self.vehicles:
            # 绘制轨迹（仅在非播放状态且显示轨迹时）
            if self.show_trajectory and not self.is_playing and len(vehicle.trajectory) > 1:
                # 绘制轨迹线
                for i in range(len(vehicle.trajectory) - 1):
                    p1 = vehicle.trajectory[i]
                    p2 = vehicle.trajectory[i + 1]
                    
                    pen = QPen(QColor(255, 255, 0, 150), 2, Qt.PenStyle.DashLine)
                    self.scene.addLine(p1.x, p1.y, p2.x, p2.y, pen)
                
                # 绘制轨迹点
                for point in vehicle.trajectory:
                    dot = QGraphicsEllipseItem(point.x - 4, point.y - 4, 8, 8)
                    dot.setBrush(QBrush(QColor(255, 100, 100)))
                    dot.setPen(QPen(QColor(255, 255, 255), 1))
                    self.scene.addItem(dot)
            
            # 绘制车辆（使用中心点定位，并应用缩放）
            # 如果没有轨迹或只有一个初始点，车辆可拖动
            if len(vehicle.trajectory) <= 1:
                # 初始位置（可拖动）
                if len(vehicle.trajectory) == 1:
                    x, y = vehicle.trajectory[0].x, vehicle.trajectory[0].y
                else:
                    x, y = self.left_margin + 100 + vehicle.id * 50, 150
                
                # 应用缩放
                if vehicle.scale != 1.0:
                    scaled_pixmap = vehicle.pixmap.scaled(
                        int(vehicle.pixmap.width() * vehicle.scale),
                        int(vehicle.pixmap.height() * vehicle.scale),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    item = DraggablePixmapItem(scaled_pixmap, vehicle, self, "vehicle")
                    item.setPos(x - scaled_pixmap.width() / 2, 
                               y - scaled_pixmap.height() / 2)
                else:
                    item = DraggablePixmapItem(vehicle.pixmap, vehicle, self, "vehicle")
                    item.setPos(x - vehicle.pixmap.width() / 2, 
                               y - vehicle.pixmap.height() / 2)
                
                self.scene.addItem(item)
            else:
                # 有轨迹时按动画显示（不可拖动）
                x, y = vehicle.get_position_at_time(self.current_time)
                
                # 应用缩放
                if vehicle.scale != 1.0:
                    scaled_pixmap = vehicle.pixmap.scaled(
                        int(vehicle.pixmap.width() * vehicle.scale),
                        int(vehicle.pixmap.height() * vehicle.scale),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    item = QGraphicsPixmapItem(scaled_pixmap)
                    item.setPos(x - scaled_pixmap.width() / 2, 
                               y - scaled_pixmap.height() / 2)
                else:
                    item = QGraphicsPixmapItem(vehicle.pixmap)
                    item.setPos(x - vehicle.pixmap.width() / 2, 
                               y - vehicle.pixmap.height() / 2)
                
                self.scene.addItem(item)
        
        # 绘制文字（可拖动）
        for label in self.text_labels:
            text_item = DraggableTextItem(label, self)
            text_item.setDefaultTextColor(QColor(label.color))
            font = QFont("Arial", label.font_size)
            text_item.setFont(font)
            self.scene.addItem(text_item)
    
    def toggle_play(self):
        """播放/暂停"""
        if self.is_playing:
            self.is_playing = False
            self.animation_timer.stop()
            self.btn_play.setText("▶ 播放")
            self.show_trajectory = True  # 暂停时显示轨迹
        else:
            self.is_playing = True
            self.animation_timer.start(33)  # 30 FPS
            self.btn_play.setText("⏸ 暂停")
            self.show_trajectory = False  # 播放时隐藏轨迹
        
        self.redraw_scene()
    
    def update_animation(self):
        """更新动画"""
        self.current_time += 0.033  # 33ms
        
        # 计算最大时间
        max_t = 0
        for vehicle in self.vehicles:
            if vehicle.trajectory:
                max_t = max(max_t, vehicle.trajectory[-1].time)
        
        if max_t > 0:
            self.max_time = max_t
        
        # 循环播放
        if self.current_time > self.max_time:
            self.current_time = 0
        
        # 更新UI
        slider_value = int((self.current_time / max(self.max_time, 1)) * 1000)
        self.time_slider.blockSignals(True)
        self.time_slider.setValue(slider_value)
        self.time_slider.blockSignals(False)
        
        self.time_label.setText(f"{self.current_time:.1f}s")
        
        self.redraw_scene()
    
    def on_time_slider_changed(self, value):
        """时间轴拖动"""
        self.current_time = (value / 1000.0) * self.max_time
        self.time_label.setText(f"{self.current_time:.1f}s")
        if not self.is_playing:
            self.redraw_scene()
    
    def update_status(self, message):
        """更新状态栏"""
        self.status_label.setText(message)
        print(f"[状态] {message}")
    
    def save_project(self):
        """保存项目"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存项目", "", "JSON文件 (*.json)"
        )
        if not filename:
            return
        
        # 构建数据
        data = {
            "settings": {
                "left_margin": self.left_margin,
                "background_color": self.background_color.name()
            },
            "roads": [
                {"id": r.id, "x": r.x, "y": r.y}
                for r in self.roads
            ],
            "vehicles": [
                {
                    "id": v.id,
                    "name": v.name,
                    "scale": v.scale,
                    "trajectory": [
                        {"x": p.x, "y": p.y, "time": p.time, "pause_duration": p.pause_duration}
                        for p in v.trajectory
                    ]
                }
                for v in self.vehicles
            ],
            "cameras": [
                {"id": c.id, "x": c.x, "y": c.y}
                for c in self.cameras
            ],
            "text_labels": [
                {
                    "text": t.text,
                    "x": t.x,
                    "y": t.y,
                    "font_size": t.font_size,
                    "color": t.color
                }
                for t in self.text_labels
            ]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        self.update_status(f"项目已保存: {filename}")
        QMessageBox.information(self, "成功", f"项目已保存到:\n{filename}")
    
    def export_video(self):
        """导出视频"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出视频", "", "MP4文件 (*.mp4)"
        )
        if not filename:
            return
        
        # 设置参数
        fps = 30
        duration = self.max_time
        
        # 获取场景尺寸
        rect = self.scene.sceneRect()
        width = int(rect.width())
        height = int(rect.height())
        
        # 创建视频写入器
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
        
        # 隐藏轨迹
        original_show_trajectory = self.show_trajectory
        self.show_trajectory = False
        
        # 渲染每一帧
        total_frames = int(duration * fps)
        for frame_idx in range(total_frames):
            self.current_time = frame_idx / fps
            self.redraw_scene()
            
            # 渲染场景到图像
            image = QImage(width, height, QImage.Format.Format_RGB888)
            image.fill(self.background_color)
            
            painter = QPainter(image)
            self.scene.render(painter)
            painter.end()
            
            # 转换为OpenCV格式
            ptr = image.bits()
            ptr.setsize(image.sizeInBytes())
            arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 3))
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            
            out.write(arr)
            
            # 更新进度
            if frame_idx % 30 == 0:
                print(f"导出进度: {frame_idx}/{total_frames} 帧")
        
        out.release()
        
        # 恢复轨迹显示状态
        self.show_trajectory = original_show_trajectory
        self.current_time = 0
        self.redraw_scene()
        
        self.update_status(f"视频已导出: {filename}")
        QMessageBox.information(self, "成功", f"视频已导出到:\n{filename}")


def main():
    app = QApplication(sys.argv)
    editor = VehicleEditor()
    editor.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
