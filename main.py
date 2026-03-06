# -*- coding: utf-8 -*-
"""
SM Arrow Player - 主程序入口（PyQt6版本）
基于Python PyQt6的E舞成名（StepMania）谱面播放器
实现玻璃拟态UI风格的选歌和播放体验
"""

import os
import sys
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QStackedWidget, QFileDialog, QMessageBox, QSplashScreen, QLabel
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont

from config_manager import ConfigManager
from song_scanner import SongScanner
from audio_manager import AudioManager, get_audio_manager
from song_select_window import SongSelectWindow
from chart_play_window import ChartPlayWindow
from glass_ui_components import GlassColors, create_font, draw_gradient_background
from directory_parser import SongInfo


class MainWindow(QMainWindow):
    """
    主窗口 - 管理界面切换
    """

    def __init__(self):
        super().__init__()

        # 配置管理器
        self._config = ConfigManager()

        # 音频管理器
        self._audio_manager = get_audio_manager()
        self._audio_manager.set_master_volume(self._config.get_master_volume())

        # 歌曲扫描器
        self._scanner = SongScanner()
        self._scanner.scan_complete.connect(self._on_scan_complete)
        self._scanner.scan_progress.connect(self._on_scan_progress)

        # 当前组件
        self._song_select: Optional[SongSelectWindow] = None
        self._chart_play: Optional[ChartPlayWindow] = None

        # 初始化UI
        self._setup_ui()

        # 检查首次运行
        if self._config.is_first_run():
            QTimer.singleShot(100, self._show_path_dialog)
        else:
            # 加载歌曲
            scan_path = self._config.get_scan_path()
            if scan_path:
                self._scanner.set_path(scan_path)
                self._scanner.start()

    def _setup_ui(self):
        """设置UI"""
        # 窗口设置
        self.setWindowTitle("SM Arrow Player")
        w, h = self._config.get_window_size()
        self.setMinimumSize(800, 600)
        self.resize(w, h)

        # 中央栈widget
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # 创建加载页面
        self._loading_widget = self._create_loading_widget()
        self._stack.addWidget(self._loading_widget)

    def _create_loading_widget(self) -> QWidget:
        """创建加载页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 加载文字
        self._loading_label = QLabel("正在加载...")
        self._loading_label.setFont(create_font(16))
        self._loading_label.setStyleSheet(f"color: {GlassColors.TEXT_WHITE.name()};")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._loading_label)

        # 进度文字
        self._progress_label = QLabel("")
        self._progress_label.setFont(create_font(12))
        self._progress_label.setStyleSheet(f"color: {GlassColors.TEXT_GRAY.name()};")
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._progress_label)

        return widget

    def paintEvent(self, event):
        """绘制背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制渐变背景
        from glass_ui_components import draw_gradient_background, draw_neon_grid
        from PyQt6.QtCore import QRectF
        draw_gradient_background(painter, QRectF(0, 0, self.width(), self.height()))
        draw_neon_grid(painter, QRectF(0, 0, self.width(), self.height()), grid_size=60)

    def _show_path_dialog(self):
        """显示路径选择对话框"""
        initial_dir = self._config.get_scan_path()
        if not initial_dir:
            initial_dir = os.path.expanduser("~")

        path = QFileDialog.getExistingDirectory(
            self,
            "选择歌曲目录",
            initial_dir,
            QFileDialog.Option.ShowDirsOnly
        )

        if path and os.path.isdir(path):
            self._config.set_scan_path(path)
            self._config.save()

            # 开始扫描
            self._scanner.set_path(path)
            self._scanner.start()
        else:
            # 未选择目录，退出
            QMessageBox.warning(
                self,
                "提示",
                "请选择歌曲目录才能使用本程序"
            )
            self.close()

    def _on_scan_progress(self, current: int, total: int):
        """扫描进度"""
        self._loading_label.setText(f"正在扫描歌曲... {current}/{total}")
        self._progress_label.setText(f"已找到 {self._scanner.song_count} 首歌曲")

    def _on_scan_complete(self, songs):
        """扫描完成"""
        if not songs:
            self._loading_label.setText("未找到歌曲")
            self._progress_label.setText("请选择包含SM文件的歌曲目录")
            return

        self._loading_label.setText(f"扫描完成，共找到 {len(songs)} 首歌曲")

        # 显示选歌界面
        QTimer.singleShot(500, lambda: self._show_song_select(songs))

    def _show_song_select(self, songs):
        """显示选歌界面"""
        # 清理旧的选歌界面
        if self._song_select:
            self._song_select.cleanup()
            self._stack.removeWidget(self._song_select)
            self._song_select.deleteLater()

        # 创建新的选歌界面
        self._song_select = SongSelectWindow(self._config, self._audio_manager)
        self._song_select.song_selected.connect(self._on_song_selected)
        self._song_select.load_songs(songs)

        self._stack.addWidget(self._song_select)
        self._stack.setCurrentWidget(self._song_select)

    def _on_song_selected(self, song: SongInfo):
        """歌曲被选择"""
        if not song.has_sm:
            return

        # 停止预览
        self._audio_manager.stop_preview()

        # 保存状态
        self._config.set_last_sm_file(song.sm_file)
        if self._song_select:
            self._config.set_last_page(self._song_select._current_page)
        self._config.save()

        # 获取皮肤目录
        app_dir = os.path.dirname(os.path.abspath(__file__))
        skin_dir = os.path.join(app_dir, "noteskin")

        if not os.path.isdir(skin_dir):
            QMessageBox.warning(self, "错误", f"皮肤目录不存在：{skin_dir}")
            return

        # 显示播放界面
        self._show_chart_play(song, skin_dir)

    def _show_chart_play(self, song: SongInfo, skin_dir: str):
        """显示播放界面"""
        # 清理旧的播放界面
        if self._chart_play:
            self._chart_play.cleanup()
            self._stack.removeWidget(self._chart_play)
            self._chart_play.deleteLater()

        # 创建新的播放界面
        self._chart_play = ChartPlayWindow(self._config, self._audio_manager)
        if not self._chart_play.load_chart(song.sm_file, song.audio_file, skin_dir):
            QMessageBox.warning(self, "错误", "谱面加载失败")
            return

        self._chart_play.back_requested.connect(self._on_play_back)
        self._stack.addWidget(self._chart_play)
        self._stack.setCurrentWidget(self._chart_play)

        # 自动开始
        self._chart_play.start()

    def _on_play_back(self):
        """从播放界面返回"""
        # 清理播放界面
        if self._chart_play:
            self._chart_play.cleanup()
            self._stack.removeWidget(self._chart_play)
            self._chart_play.deleteLater()
            self._chart_play = None

        # 返回选歌界面
        if self._song_select:
            self._stack.setCurrentWidget(self._song_select)

    def closeEvent(self, event):
        """关闭事件"""
        # 保存配置
        self._config.set_window_size(self.width(), self.height())
        self._config.save()

        # 清理资源
        if self._song_select:
            self._song_select.cleanup()

        if self._chart_play:
            self._chart_play.cleanup()

        self._audio_manager.cleanup()

        event.accept()

    def keyPressEvent(self, event):
        """键盘事件"""
        # F11切换全屏
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        else:
            super().keyPressEvent(event)


def main():
    """程序入口"""
    # 检查Python版本
    if sys.version_info < (3, 9):
        print("错误: 需要Python 3.9或更高版本")
        sys.exit(1)

    # PyQt6默认启用高DPI，无需手动设置
    # 创建应用
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # 设置全局字体
    font = create_font(12)
    app.setFont(font)

    # 打印欢迎信息
    print("=" * 50)
    print("SM Arrow Player (PyQt6)")
    print("E舞成名谱面播放器")
    print("=" * 50)

    # 创建主窗口
    window = MainWindow()
    window.show()

    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()