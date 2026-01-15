#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
车辆轨迹可视化编辑器 - 使用真实素材版本

功能：
- 加载提取的车辆、摄像头、道路背景素材
- 支持拖放添加车辆和摄像头
- 车辆支持轨迹编辑（时间、速度控制）
- 文字标注自由添加
- 动画预览与视频导出
"""

import sys
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QGraphicsEllipseItem, QGraphicsTextItem,
    QSlider, QSpinBox, QDoubleSpinBox, QDialog, QFormLayout,
    QLineEdit, QMessageBox, QFileDialog, QListWidgetItem, QGroupBox
)
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import (
    QPixmap, QPen, QBrush, QColor, QFont, QPainter, QImage
)
import cv2
import numpy as np


class TrajectoryPoint:
    """轨迹点（包含时间和位置）"""
    def __init__(self, x, y, time):
        self.x = x
        self.y = y
        self.time = time  # 到达此点的时间（秒）


class Vehicle:
    """车辆对象"""
    def __init__(self, vehicle_id, pixmap, x=100, y=100):
        self.id = vehicle_id
        self.pixmap = pixmap
        self.trajectory = [TrajectoryPoint(x, y, 0.0)]  # 初始点
        self.current_pos_index = 0
        self.current_time = 0.0
        
    def add_trajectory_point(self, x, y, time):
        """添加轨迹点"""
        self.trajectory.append(TrajectoryPoint(x, y, time))
        
    def get_position_at_time(self, t):
        """根据时间获取位置（线性插值）"""
        if t <= 0:
            return (self.trajectory[0].x, self.trajectory[0].y)
        
        if t >= self.trajectory[-1].time:
            return (self.trajectory[-1].x, self.trajectory[-1].y)
        
        # 找到时间区间
        for i in range(len(self.trajectory) - 1):
            p1 = self.trajectory[i]
            p2 = self.trajectory[i + 1]
            
            if p1.time <= t <= p2.time:
                # 线性插值
                if p2.time - p1.time == 0:
                    return (p1.x, p1.y)
                
                ratio = (t - p1.time) / (p2.time - p1.time)
                x = p1.x + (p2.x - p1.x) * ratio
                y = p1.y + (p2.y - p1.y) * ratio
                return (x, y)
        
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
            # 添加轨迹点
            x, y = pos.x(), pos.y()
            
            # 弹出对话框设置时间
            dialog = QDialog(self.editor)
            dialog.setWindowTitle("设置轨迹点时间")
            layout = QFormLayout()
            
            time_spin = QDoubleSpinBox()
            time_spin.setRange(0.0, 60.0)
            time_spin.setValue(len(self.current_vehicle.trajectory) * 1.0)
            time_spin.setSuffix(" 秒")
            time_spin.setDecimals(1)
            
            layout.addRow("到达时间:", time_spin)
            
            btn_ok = QPushButton("确定")
            btn_ok.clicked.connect(dialog.accept)
            layout.addRow(btn_ok)
            
            dialog.setLayout(layout)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                time = time_spin.value()
                self.current_vehicle.add_trajectory_point(x, y, time)
                
                # 绘制轨迹点（调试用）
                point_item = QGraphicsEllipseItem(x - 3, y - 3, 6, 6)
                point_item.setBrush(QBrush(QColor(255, 0, 0)))
                self.addItem(point_item)
                
                self.editor.update_status(f"添加轨迹点 ({x:.0f}, {y:.0f}) @ {time:.1f}s")
        
        super().mousePressEvent(event)


class VehicleEditor(QMainWindow):
    """主编辑器窗口"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("车辆轨迹编辑器")
        self.setGeometry(100, 100, 1400, 900)
        
        # 数据
        self.vehicles = []
        self.cameras = []
        self.text_labels = []
        self.vehicle_items = {}  # 车辆图形对象
        self.camera_items = {}   # 摄像头图形对象
        self.text_items = {}     # 文字对象
        
        # 素材路径
        self.assets_dir = Path("vehicle_trajectory_editor/assets")
        self.background_pixmap = None
        self.vehicle_pixmaps = []
        self.camera_pixmaps = []
        self.road_pixmaps = []  # 多张道路背景
        
        # 动画
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.current_time = 0.0
        self.max_time = 10.0
        self.is_playing = False
        
        # 加载素材
        self.load_assets()
        
        # 创建UI
        self.init_ui()
        
    def load_assets(self):
        """加载素材"""
        if not self.assets_dir.exists():
            QMessageBox.warning(self, "素材缺失", 
                f"未找到素材目录: {self.assets_dir}\n\n请先运行素材准备脚本")
            return
        
        # 加载7张道路背景
        for i in range(7):
            road_path = self.assets_dir / "roads" / f"road_{i}.png"
            if road_path.exists():
                pixmap = QPixmap(str(road_path))
                self.road_pixmaps.append(pixmap)
                print(f"✓ 加载道路 {i}: {road_path.name}")
            else:
                print(f"⚠ 缺失道路素材: {road_path}")
        
        # 加载车辆素材（黄色和红色）
        vehicle_files = ["yellow_vehicle.png", "red_vehicle.png"]
        for vehicle_file in vehicle_files:
            vehicle_path = self.assets_dir / "vehicles" / vehicle_file
            if vehicle_path.exists():
                pixmap = QPixmap(str(vehicle_path))
                self.vehicle_pixmaps.append(pixmap)
                print(f"✓ 加载车辆: {vehicle_file}")
            else:
                print(f"⚠ 缺失车辆素材: {vehicle_path}")
        
        # 加载摄像头素材
        camera_path = self.assets_dir / "vehicles" / "camera.png"
        if camera_path.exists():
            pixmap = QPixmap(str(camera_path))
            self.camera_pixmaps.append(pixmap)
            print(f"✓ 加载摄像头: {camera_path.name}")
        else:
            print(f"⚠ 缺失摄像头素材: {camera_path}")
        
        # 设置默认背景为第一张道路图片
        if self.road_pixmaps:
            self.background_pixmap = self.road_pixmaps[0]
        
        if not self.vehicle_pixmaps:
            print("⚠ 未找到车辆素材")
        if not self.camera_pixmaps:
            print("⚠ 未找到摄像头素材")
    
    def init_ui(self):
        """初始化界面"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        
        # 左侧：工具栏
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(280)
        
        # === 素材库 ===
        assets_group = QGroupBox("素材库")
        assets_layout = QVBoxLayout()
        
        # 车辆列表
        QLabel("车辆素材:").setParent(assets_group)
        assets_layout.addWidget(QLabel("车辆素材:"))
        self.vehicle_list = QListWidget()
        for i, pixmap in enumerate(self.vehicle_pixmaps):
            item = QListWidgetItem(f"车辆 {i}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.vehicle_list.addItem(item)
        assets_layout.addWidget(self.vehicle_list)
        
        btn_add_vehicle = QPushButton("➕ 添加车辆到场景")
        btn_add_vehicle.clicked.connect(self.add_vehicle_to_scene)
        assets_layout.addWidget(btn_add_vehicle)
        
        # 摄像头列表
        assets_layout.addWidget(QLabel("摄像头素材:"))
        self.camera_list = QListWidget()
        for i, pixmap in enumerate(self.camera_pixmaps):
            item = QListWidgetItem(f"摄像头 {i}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.camera_list.addItem(item)
        assets_layout.addWidget(self.camera_list)
        
        btn_add_camera = QPushButton("➕ 添加摄像头到场景")
        btn_add_camera.clicked.connect(self.add_camera_to_scene)
        assets_layout.addWidget(btn_add_camera)
        
        assets_group.setLayout(assets_layout)
        left_layout.addWidget(assets_group)
        
        # === 轨迹编辑 ===
        traj_group = QGroupBox("轨迹编辑")
        traj_layout = QVBoxLayout()
        
        self.vehicle_scene_list = QListWidget()
        traj_layout.addWidget(QLabel("场景中的车辆:"))
        traj_layout.addWidget(self.vehicle_scene_list)
        
        btn_edit_traj = QPushButton("📍 编辑轨迹（点击场景添加点）")
        btn_edit_traj.clicked.connect(self.start_trajectory_edit)
        traj_layout.addWidget(btn_edit_traj)
        
        btn_stop_traj = QPushButton("⏹ 停止编辑")
        btn_stop_traj.clicked.connect(self.stop_trajectory_edit)
        traj_layout.addWidget(btn_stop_traj)
        
        traj_group.setLayout(traj_layout)
        left_layout.addWidget(traj_group)
        
        # === 文字标注 ===
        text_group = QGroupBox("文字标注")
        text_layout = QVBoxLayout()
        
        btn_add_text = QPushButton("📝 添加文字")
        btn_add_text.clicked.connect(self.add_text_label)
        text_layout.addWidget(btn_add_text)
        
        text_group.setLayout(text_layout)
        left_layout.addWidget(text_group)
        
        # === 动画控制 ===
        anim_group = QGroupBox("动画控制")
        anim_layout = QVBoxLayout()
        
        self.btn_play = QPushButton("▶ 播放")
        self.btn_play.clicked.connect(self.toggle_play)
        anim_layout.addWidget(self.btn_play)
        
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setRange(0, 1000)
        self.time_slider.valueChanged.connect(self.slider_changed)
        anim_layout.addWidget(self.time_slider)
        
        self.time_label = QLabel("时间: 0.0 / 10.0 秒")
        anim_layout.addWidget(self.time_label)
        
        max_time_layout = QHBoxLayout()
        max_time_layout.addWidget(QLabel("总时长:"))
        self.max_time_spin = QDoubleSpinBox()
        self.max_time_spin.setRange(1.0, 60.0)
        self.max_time_spin.setValue(10.0)
        self.max_time_spin.setSuffix(" 秒")
        self.max_time_spin.valueChanged.connect(self.max_time_changed)
        max_time_layout.addWidget(self.max_time_spin)
        anim_layout.addLayout(max_time_layout)
        
        anim_group.setLayout(anim_layout)
        left_layout.addWidget(anim_group)
        
        # === 导出 ===
        export_group = QGroupBox("导出")
        export_layout = QVBoxLayout()
        
        btn_export = QPushButton("🎬 导出视频")
        btn_export.clicked.connect(self.export_video)
        export_layout.addWidget(btn_export)
        
        btn_save = QPushButton("💾 保存项目")
        btn_save.clicked.connect(self.save_project)
        export_layout.addWidget(btn_save)
        
        btn_load = QPushButton("📂 加载项目")
        btn_load.clicked.connect(self.load_project)
        export_layout.addWidget(btn_load)
        
        export_group.setLayout(export_layout)
        left_layout.addWidget(export_group)
        
        left_layout.addStretch()
        
        # 状态栏
        self.status_label = QLabel("就绪")
        left_layout.addWidget(self.status_label)
        
        main_layout.addWidget(left_panel)
        
        # 右侧：场景视图
        self.scene = EditorScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 设置背景
        if self.background_pixmap:
            bg_item = QGraphicsPixmapItem(self.background_pixmap)
            self.scene.addItem(bg_item)
            self.scene.setSceneRect(bg_item.boundingRect())
        else:
            self.scene.setSceneRect(0, 0, 1200, 800)
        
        main_layout.addWidget(self.view, 1)
    
    def add_vehicle_to_scene(self):
        """添加车辆到场景"""
        current = self.vehicle_list.currentItem()
        if not current:
            QMessageBox.warning(self, "提示", "请先选择一个车辆素材")
            return
        
        idx = current.data(Qt.ItemDataRole.UserRole)
        pixmap = self.vehicle_pixmaps[idx]
        
        # 创建车辆对象
        vehicle = Vehicle(len(self.vehicles), pixmap, 100, 100 + len(self.vehicles) * 50)
        self.vehicles.append(vehicle)
        
        # 添加到场景
        vehicle_item = QGraphicsPixmapItem(pixmap)
        vehicle_item.setPos(vehicle.trajectory[0].x, vehicle.trajectory[0].y)
        vehicle_item.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable)
        vehicle_item.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable)
        self.scene.addItem(vehicle_item)
        self.vehicle_items[vehicle.id] = vehicle_item
        
        # 添加到列表
        item = QListWidgetItem(f"车辆 {vehicle.id}")
        item.setData(Qt.ItemDataRole.UserRole, vehicle.id)
        self.vehicle_scene_list.addItem(item)
        
        self.update_status(f"添加车辆 {vehicle.id}")
    
    def add_camera_to_scene(self):
        """添加摄像头到场景"""
        current = self.camera_list.currentItem()
        if not current:
            QMessageBox.warning(self, "提示", "请先选择一个摄像头素材")
            return
        
        idx = current.data(Qt.ItemDataRole.UserRole)
        pixmap = self.camera_pixmaps[idx]
        
        # 创建摄像头对象
        camera = Camera(len(self.cameras), pixmap, 200, 100 + len(self.cameras) * 50)
        self.cameras.append(camera)
        
        # 添加到场景
        camera_item = QGraphicsPixmapItem(pixmap)
        camera_item.setPos(camera.x, camera.y)
        camera_item.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable)
        camera_item.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable)
        self.scene.addItem(camera_item)
        self.camera_items[camera.id] = camera_item
        
        self.update_status(f"添加摄像头 {camera.id}")
    
    def add_text_label(self):
        """添加文字标注"""
        dialog = QDialog(self)
        dialog.setWindowTitle("添加文字")
        layout = QFormLayout()
        
        text_edit = QLineEdit()
        text_edit.setText("标注文字")
        layout.addRow("文字内容:", text_edit)
        
        x_spin = QSpinBox()
        x_spin.setRange(0, 2000)
        x_spin.setValue(300)
        layout.addRow("X 坐标:", x_spin)
        
        y_spin = QSpinBox()
        y_spin.setRange(0, 2000)
        y_spin.setValue(300)
        layout.addRow("Y 坐标:", y_spin)
        
        size_spin = QSpinBox()
        size_spin.setRange(8, 72)
        size_spin.setValue(16)
        layout.addRow("字体大小:", size_spin)
        
        btn_ok = QPushButton("确定")
        btn_ok.clicked.connect(dialog.accept)
        layout.addRow(btn_ok)
        
        dialog.setLayout(layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            text_label = TextLabel(
                text_edit.text(),
                x_spin.value(),
                y_spin.value(),
                size_spin.value()
            )
            self.text_labels.append(text_label)
            
            # 添加到场景
            text_item = QGraphicsTextItem(text_label.text)
            text_item.setPos(text_label.x, text_label.y)
            font = QFont("Arial", text_label.font_size)
            text_item.setFont(font)
            text_item.setDefaultTextColor(QColor("white"))
            text_item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable)
            text_item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable)
            self.scene.addItem(text_item)
            
            self.text_items[len(self.text_labels) - 1] = text_item
            
            self.update_status(f"添加文字: {text_label.text}")
    
    def start_trajectory_edit(self):
        """开始编辑轨迹"""
        current = self.vehicle_scene_list.currentItem()
        if not current:
            QMessageBox.warning(self, "提示", "请先选择一个车辆")
            return
        
        vehicle_id = current.data(Qt.ItemDataRole.UserRole)
        vehicle = self.vehicles[vehicle_id]
        
        self.scene.selecting_trajectory = True
        self.scene.current_vehicle = vehicle
        
        self.update_status(f"正在编辑车辆 {vehicle_id} 的轨迹，点击场景添加轨迹点")
    
    def stop_trajectory_edit(self):
        """停止编辑轨迹"""
        self.scene.selecting_trajectory = False
        self.scene.current_vehicle = None
        self.update_status("停止轨迹编辑")
    
    def toggle_play(self):
        """播放/暂停"""
        if self.is_playing:
            self.animation_timer.stop()
            self.btn_play.setText("▶ 播放")
            self.is_playing = False
        else:
            self.animation_timer.start(33)  # 30 FPS
            self.btn_play.setText("⏸ 暂停")
            self.is_playing = True
    
    def update_animation(self):
        """更新动画"""
        self.current_time += 0.033
        
        if self.current_time >= self.max_time:
            self.current_time = 0.0  # 循环
        
        # 更新滑块
        progress = int((self.current_time / self.max_time) * 1000)
        self.time_slider.blockSignals(True)
        self.time_slider.setValue(progress)
        self.time_slider.blockSignals(False)
        
        self.time_label.setText(f"时间: {self.current_time:.1f} / {self.max_time:.1f} 秒")
        
        # 更新车辆位置
        for vehicle in self.vehicles:
            if vehicle.id in self.vehicle_items:
                x, y = vehicle.get_position_at_time(self.current_time)
                self.vehicle_items[vehicle.id].setPos(x, y)
    
    def slider_changed(self, value):
        """滑块变化"""
        if not self.is_playing:
            self.current_time = (value / 1000.0) * self.max_time
            self.time_label.setText(f"时间: {self.current_time:.1f} / {self.max_time:.1f} 秒")
            
            # 更新车辆位置
            for vehicle in self.vehicles:
                if vehicle.id in self.vehicle_items:
                    x, y = vehicle.get_position_at_time(self.current_time)
                    self.vehicle_items[vehicle.id].setPos(x, y)
    
    def max_time_changed(self, value):
        """最大时间改变"""
        self.max_time = value
        self.time_label.setText(f"时间: {self.current_time:.1f} / {self.max_time:.1f} 秒")
    
    def export_video(self):
        """导出视频"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存视频", "output.mp4", "MP4 Files (*.mp4)"
        )
        
        if not filename:
            return
        
        self.update_status("正在导出视频...")
        
        # 获取场景尺寸
        rect = self.scene.sceneRect()
        width = int(rect.width())
        height = int(rect.height())
        
        # 创建视频写入器
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(filename, fourcc, 30.0, (width, height))
        
        # 暂停动画
        was_playing = self.is_playing
        if was_playing:
            self.toggle_play()
        
        # 渲染每一帧
        fps = 30
        total_frames = int(self.max_time * fps)
        
        for frame_num in range(total_frames):
            t = (frame_num / fps)
            
            # 更新车辆位置
            for vehicle in self.vehicles:
                if vehicle.id in self.vehicle_items:
                    x, y = vehicle.get_position_at_time(t)
                    self.vehicle_items[vehicle.id].setPos(x, y)
            
            # 渲染场景到图像
            image = QImage(width, height, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.black)
            
            painter = QPainter(image)
            self.scene.render(painter)
            painter.end()
            
            # 转换为 OpenCV 格式
            ptr = image.bits()
            ptr.setsize(image.sizeInBytes())
            arr = np.array(ptr).reshape(height, width, 4)
            frame = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
            
            out.write(frame)
            
            if frame_num % 30 == 0:
                self.update_status(f"导出进度: {frame_num}/{total_frames}")
        
        out.release()
        
        # 恢复动画
        if was_playing:
            self.toggle_play()
        
        self.update_status(f"视频已导出: {filename}")
        QMessageBox.information(self, "成功", f"视频已保存到:\n{filename}")
    
    def save_project(self):
        """保存项目"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存项目", "project.json", "JSON Files (*.json)"
        )
        
        if not filename:
            return
        
        data = {
            'vehicles': [],
            'cameras': [],
            'text_labels': [],
            'max_time': self.max_time
        }
        
        for vehicle in self.vehicles:
            data['vehicles'].append({
                'id': vehicle.id,
                'pixmap_index': 0,  # TODO: 记录使用的素材索引
                'trajectory': [(p.x, p.y, p.time) for p in vehicle.trajectory]
            })
        
        for camera in self.cameras:
            data['cameras'].append({
                'id': camera.id,
                'pixmap_index': 0,
                'x': camera.x,
                'y': camera.y
            })
        
        for label in self.text_labels:
            data['text_labels'].append({
                'text': label.text,
                'x': label.x,
                'y': label.y,
                'font_size': label.font_size,
                'color': label.color
            })
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        self.update_status(f"项目已保存: {filename}")
    
    def load_project(self):
        """加载项目"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "加载项目", "", "JSON Files (*.json)"
        )
        
        if not filename:
            return
        
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 清空场景
        self.vehicles.clear()
        self.cameras.clear()
        self.text_labels.clear()
        
        for item in list(self.vehicle_items.values()):
            self.scene.removeItem(item)
        for item in list(self.camera_items.values()):
            self.scene.removeItem(item)
        for item in list(self.text_items.values()):
            self.scene.removeItem(item)
        
        self.vehicle_items.clear()
        self.camera_items.clear()
        self.text_items.clear()
        self.vehicle_scene_list.clear()
        
        # 加载数据
        self.max_time = data.get('max_time', 10.0)
        self.max_time_spin.setValue(self.max_time)
        
        # TODO: 实现完整的加载逻辑
        
        self.update_status(f"项目已加载: {filename}")
    
    def update_status(self, msg):
        """更新状态栏"""
        self.status_label.setText(msg)
        print(msg)


def main():
    app = QApplication(sys.argv)
    editor = VehicleEditor()
    editor.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
