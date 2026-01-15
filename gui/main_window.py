"""
主窗口 - 车辆轨迹编辑器
"""

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QSpinBox, QColorDialog,
                             QLineEdit, QComboBox, QGroupBox, QMessageBox,
                             QFileDialog, QSlider, QCheckBox, QDoubleSpinBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont
from gui.road_canvas import RoadCanvas
from video_generator.exporter import VideoExporter


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.canvas = None
        self.video_exporter = None
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('车辆轨迹编辑器 - 7车道智能交通系统')
        self.setGeometry(100, 100, 1600, 900)
        
        # 主Widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # 主布局
        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)
        
        # 左侧：工具面板
        self.create_tool_panel(main_layout)
        
        # 右侧：画布
        self.canvas = RoadCanvas(lanes=7)
        main_layout.addWidget(self.canvas, stretch=3)
        
        # 状态栏
        self.statusBar().showMessage('就绪 - 请选择工具开始绘制')
        
    def create_tool_panel(self, parent_layout):
        """创建左侧工具面板"""
        tool_panel = QWidget()
        tool_layout = QVBoxLayout()
        tool_panel.setLayout(tool_layout)
        tool_panel.setMaximumWidth(350)
        
        # 标题
        title = QLabel('🎨 轨迹编辑工具')
        title.setFont(QFont('Arial', 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        tool_layout.addWidget(title)
        
        # 1. 绘制模式选择
        mode_group = QGroupBox('📍 绘制模式')
        mode_layout = QVBoxLayout()
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            '绘制真实轨迹',
            '绘制模拟轨迹',
            '添加文字标注',
            '添加车辆',
            '添加摄像头'
        ])
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        mode_group.setLayout(mode_layout)
        tool_layout.addWidget(mode_group)
        
        # 2. 轨迹设置
        trajectory_group = QGroupBox('🚗 轨迹设置')
        traj_layout = QVBoxLayout()
        
        # 车道选择
        lane_layout = QHBoxLayout()
        lane_layout.addWidget(QLabel('车道:'))
        self.lane_spin = QSpinBox()
        self.lane_spin.setRange(1, 7)
        self.lane_spin.setValue(2)
        self.lane_spin.valueChanged.connect(self.on_lane_changed)
        lane_layout.addWidget(self.lane_spin)
        traj_layout.addLayout(lane_layout)
        
        # 颜色选择
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel('轨迹颜色:'))
        self.color_btn = QPushButton('选择颜色')
        self.color_btn.clicked.connect(self.choose_color)
        self.current_color = QColor(255, 215, 0)  # 默认黄色
        self.update_color_button()
        color_layout.addWidget(self.color_btn)
        traj_layout.addLayout(color_layout)
        
        # 线条宽度
        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel('线条宽度:'))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 10)
        self.width_spin.setValue(3)
        self.width_spin.valueChanged.connect(self.on_width_changed)
        width_layout.addWidget(self.width_spin)
        traj_layout.addLayout(width_layout)
        
        # 速度设置
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel('车速(km/h):'))
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(10, 120)
        self.speed_spin.setValue(60)
        self.speed_spin.setSuffix(' km/h')
        speed_layout.addWidget(self.speed_spin)
        traj_layout.addLayout(speed_layout)
        
        trajectory_group.setLayout(traj_layout)
        tool_layout.addWidget(trajectory_group)
        
        # 3. 文字标注设置
        text_group = QGroupBox('📝 文字标注')
        text_layout = QVBoxLayout()
        
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText('输入标注文字...')
        text_layout.addWidget(self.text_input)
        
        # 字体大小
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel('字体大小:'))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(10, 50)
        self.font_size_spin.setValue(16)
        font_layout.addWidget(self.font_size_spin)
        text_layout.addLayout(font_layout)
        
        text_group.setLayout(text_layout)
        tool_layout.addWidget(text_group)
        
        # 4. 动画控制
        animation_group = QGroupBox('🎬 动画控制')
        anim_layout = QVBoxLayout()
        
        # 播放控制按钮
        play_layout = QHBoxLayout()
        self.play_btn = QPushButton('▶️ 播放')
        self.play_btn.clicked.connect(self.play_animation)
        play_layout.addWidget(self.play_btn)
        
        self.pause_btn = QPushButton('⏸️ 暂停')
        self.pause_btn.clicked.connect(self.pause_animation)
        play_layout.addWidget(self.pause_btn)
        anim_layout.addLayout(play_layout)
        
        # 速度控制
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel('播放速度:'))
        self.anim_speed_slider = QSlider(Qt.Horizontal)
        self.anim_speed_slider.setRange(1, 10)
        self.anim_speed_slider.setValue(5)
        self.anim_speed_slider.valueChanged.connect(self.on_anim_speed_changed)
        speed_layout.addWidget(self.anim_speed_slider)
        self.speed_label = QLabel('1.0x')
        speed_layout.addWidget(self.speed_label)
        anim_layout.addLayout(speed_layout)
        
        # 循环播放
        self.loop_checkbox = QCheckBox('循环播放')
        self.loop_checkbox.setChecked(True)
        anim_layout.addWidget(self.loop_checkbox)
        
        animation_group.setLayout(anim_layout)
        tool_layout.addWidget(animation_group)
        
        # 5. 操作按钮
        action_group = QGroupBox('⚙️ 操作')
        action_layout = QVBoxLayout()
        
        self.clear_btn = QPushButton('🗑️ 清空画布')
        self.clear_btn.clicked.connect(self.clear_canvas)
        action_layout.addWidget(self.clear_btn)
        
        self.undo_btn = QPushButton('↶ 撤销')
        self.undo_btn.clicked.connect(self.undo_action)
        action_layout.addWidget(self.undo_btn)
        
        self.save_btn = QPushButton('💾 保存项目')
        self.save_btn.clicked.connect(self.save_project)
        action_layout.addWidget(self.save_btn)
        
        self.load_btn = QPushButton('📂 加载项目')
        self.load_btn.clicked.connect(self.load_project)
        action_layout.addWidget(self.load_btn)
        
        action_group.setLayout(action_layout)
        tool_layout.addWidget(action_group)
        
        # 6. 视频导出
        export_group = QGroupBox('🎥 视频导出')
        export_layout = QVBoxLayout()
        
        # 帧率设置
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel('帧率:'))
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(15, 60)
        self.fps_spin.setValue(30)
        fps_layout.addWidget(self.fps_spin)
        export_layout.addLayout(fps_layout)
        
        # 时长设置
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel('时长(秒):'))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(5, 60)
        self.duration_spin.setValue(10)
        duration_layout.addWidget(self.duration_spin)
        export_layout.addLayout(duration_layout)
        
        self.export_btn = QPushButton('🎬 导出视频')
        self.export_btn.clicked.connect(self.export_video)
        export_layout.addWidget(self.export_btn)
        
        export_group.setLayout(export_layout)
        tool_layout.addWidget(export_group)
        
        # 弹性空间
        tool_layout.addStretch()
        
        parent_layout.addWidget(tool_panel, stretch=1)
        
    def on_mode_changed(self, mode):
        """模式切换"""
        self.canvas.set_draw_mode(mode)
        self.statusBar().showMessage(f'当前模式: {mode}')
        
    def on_lane_changed(self, lane):
        """车道切换"""
        self.canvas.set_current_lane(lane)
        
    def choose_color(self):
        """选择颜色"""
        color = QColorDialog.getColor(self.current_color, self, '选择轨迹颜色')
        if color.isValid():
            self.current_color = color
            self.canvas.set_trajectory_color(color)
            self.update_color_button()
            
    def update_color_button(self):
        """更新颜色按钮显示"""
        self.color_btn.setStyleSheet(
            f'background-color: {self.current_color.name()}; '
            f'color: {"white" if self.current_color.lightness() < 128 else "black"};'
        )
        
    def on_width_changed(self, width):
        """线条宽度改变"""
        self.canvas.set_line_width(width)
        
    def on_anim_speed_changed(self, value):
        """动画速度改变"""
        speed = value / 5.0
        self.speed_label.setText(f'{speed:.1f}x')
        self.canvas.set_animation_speed(speed)
        
    def play_animation(self):
        """播放动画"""
        loop = self.loop_checkbox.isChecked()
        self.canvas.play_animation(loop=loop)
        self.statusBar().showMessage('▶️ 动画播放中...')
        
    def pause_animation(self):
        """暂停动画"""
        self.canvas.pause_animation()
        self.statusBar().showMessage('⏸️ 动画已暂停')
        
    def clear_canvas(self):
        """清空画布"""
        reply = QMessageBox.question(
            self, '确认清空', 
            '确定要清空所有内容吗？',
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.canvas.clear_all()
            self.statusBar().showMessage('画布已清空')
            
    def undo_action(self):
        """撤销操作"""
        self.canvas.undo()
        self.statusBar().showMessage('撤销成功')
        
    def save_project(self):
        """保存项目"""
        filename, _ = QFileDialog.getSaveFileName(
            self, '保存项目', '', 
            'JSON文件 (*.json)'
        )
        if filename:
            self.canvas.save_to_file(filename)
            self.statusBar().showMessage(f'项目已保存: {filename}')
            
    def load_project(self):
        """加载项目"""
        filename, _ = QFileDialog.getOpenFileName(
            self, '加载项目', '', 
            'JSON文件 (*.json)'
        )
        if filename:
            self.canvas.load_from_file(filename)
            self.statusBar().showMessage(f'项目已加载: {filename}')
            
    def export_video(self):
        """导出视频"""
        filename, _ = QFileDialog.getSaveFileName(
            self, '导出视频', '', 
            'MP4文件 (*.mp4)'
        )
        if filename:
            self.statusBar().showMessage('正在生成视频...')
            fps = self.fps_spin.value()
            duration = self.duration_spin.value()
            
            if self.video_exporter is None:
                self.video_exporter = VideoExporter(self.canvas)
            
            try:
                self.video_exporter.export(filename, fps=fps, duration=duration)
                QMessageBox.information(self, '导出成功', f'视频已保存至:\n{filename}')
                self.statusBar().showMessage('✅ 视频导出完成')
            except Exception as e:
                QMessageBox.critical(self, '导出失败', f'视频导出失败:\n{str(e)}')
                self.statusBar().showMessage('❌ 视频导出失败')
