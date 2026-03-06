# -*- coding: utf-8 -*-
"""
谱面播放界面（PyQt6版本）
实现高级玻璃拟态风格的音游播放器
"""

import os
import time
import math
from typing import List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QSizePolicy, QApplication
)
from PyQt6.QtCore import (
    Qt, QTimer, QRectF, QPointF, pyqtSignal, QElapsedTimer,
    QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient,
    QRadialGradient, QPainterPath, QFont, QPixmap, QConicalGradient
)

from glass_ui_components import GlassColors, GlassPanel, GlassButton, create_font
from config_manager import ConfigManager
from audio_manager import AudioManager
from sm_parser import SmParser, ArrowEvent, TimelineSegment, generate_timeline_segments, build_arrow_events, format_seconds
from skin_manager import SkinManager
from judge_system import JudgeSystem, JudgeResult, JudgeDisplay, JudgeLight, HitEffect


class GameState(Enum):
    """游戏状态枚举"""
    LOADING = "loading"
    READY = "ready"
    PLAYING = "playing"
    PAUSED = "paused"
    FINISHED = "finished"


@dataclass
class GameResult:
    """游戏结果"""
    score: int = 0
    max_combo: int = 0
    accuracy: float = 0.0
    grade: str = "F"
    perfect: int = 0
    good: int = 0
    bad: int = 0
    miss: int = 0


class ChartPlayWindow(QWidget):
    """
    谱面播放器

    信号：
    - play_finished: 播放结束
    - back_requested: 请求返回选歌
    """

    play_finished = pyqtSignal()
    back_requested = pyqtSignal()

    # 按键映射
    KEY_MAP = {
        Qt.Key.Key_Q: 1,   # UpLeft
        Qt.Key.Key_E: 3,   # UpRight
        Qt.Key.Key_S: 2,   # Center
        Qt.Key.Key_Z: 0,   # DownLeft
        Qt.Key.Key_C: 4,   # DownRight
    }

    def __init__(self, config: ConfigManager, audio_manager: AudioManager, parent=None):
        super().__init__(parent)
        self._config = config
        self._audio_manager = audio_manager

        # 窗口设置
        self.setMinimumSize(800, 600)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)  # 启用鼠标跟踪

        # 状态
        self._game_state = GameState.LOADING
        self._sm_path: Optional[str] = None
        self._audio_path: Optional[str] = None
        self._skin_dir: Optional[str] = None

        # 谱面数据
        self._sm_parser: Optional[SmParser] = None
        self._skin: Optional[SkinManager] = None
        self._chart_title = ""
        self._chart_offset = 0.0
        self._bpm_list: List[Tuple[float, float]] = []
        self._timeline_segments: List[TimelineSegment] = []
        self._arrow_events: List[ArrowEvent] = []

        # 播放状态
        self._current_sec = 0.0
        self._total_sec = 0.0
        self._is_playing = False
        self._start_time = 0.0
        self._pause_time = 0.0

        # 滚动速度
        self._scroll_speed = config.get_scroll_speed()

        # 判定系统
        self._judge_system = JudgeSystem()
        self._judge_display = JudgeDisplay()
        self._judge_light = JudgeLight(track_count=5)
        self._hit_effect = HitEffect()

        # 皮肤
        self._tap_pixmaps: List[Optional[QPixmap]] = [None] * 5
        self._hold_body_pixmaps: List[Optional[QPixmap]] = [None] * 5
        self._hold_tail_pixmaps: List[Optional[QPixmap]] = [None] * 5
        self._receptor_pixmaps: List[Optional[QPixmap]] = [None] * 5

        # 按键状态
        self._key_pressed: List[bool] = [False] * 5

        # 封面
        self._banner_pixmap: Optional[QPixmap] = None

        # 结果
        self._result: Optional[GameResult] = None
        self._result_display_time = 0.0

        # 暂停菜单
        self._pause_menu_index = 0
        self._pause_menu_options = ["继续", "重新开始", "返回选歌"]

        # 游戏定时器
        self._game_timer = QTimer(self)
        self._game_timer.timeout.connect(self._update_game)

        # 帧率计时
        self._elapsed_timer = QElapsedTimer()

        # 设置UI
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        # 无需布局，paintEvent会处理所有绘制
        pass

    def load_chart(self, sm_path: str, audio_path: Optional[str], skin_dir: str) -> bool:
        """
        加载谱面

        Args:
            sm_path: SM文件路径
            audio_path: 音频文件路径
            skin_dir: 皮肤目录

        Returns:
            是否成功
        """
        try:
            self._sm_path = sm_path
            self._audio_path = audio_path
            self._skin_dir = skin_dir

            # 解析SM文件
            self._sm_parser = SmParser(tick_per_beat=self._config.get_tick_per_beat())
            chart_info, notes_blocks = self._sm_parser.parse_file(sm_path)

            if not notes_blocks:
                raise ValueError("SM文件中未找到NOTES区块")

            # 使用第一个NOTES
            notes_block = notes_blocks[0]

            # 检测列数
            col_count = self._sm_parser.detect_column_count(notes_block)
            self._sm_parser.atype_map, _ = self._sm_parser.recommend_atype_map(col_count)

            # 解析箭头事件
            event_table, _ = self._sm_parser.parse_arrow_events(notes_block)

            # 处理BPM
            self._bpm_list = chart_info.bpm_list or []
            if not self._bpm_list or any(bpm <= 0 for _, bpm in self._bpm_list):
                from sm_parser import extract_available_bpm
                fallback = extract_available_bpm(
                    chart_info.display_bpm_original,
                    chart_info.bpms_original
                ) or 120.0
                self._bpm_list = [(0.0, fallback)]

            # 生成时间轴
            self._timeline_segments = generate_timeline_segments(
                self._bpm_list,
                self._sm_parser.tick_per_beat
            )

            # 构建箭头事件
            self._arrow_events = build_arrow_events(
                event_table,
                self._timeline_segments,
                self._sm_parser.tick_per_beat,
                self._sm_parser.atype_map
            )

            # 计算总时长
            if self._arrow_events:
                self._total_sec = self._arrow_events[-1].end_sec

            self._chart_title = chart_info.title or os.path.basename(sm_path)
            self._chart_offset = chart_info.offset

            # 加载皮肤
            self._load_skins()

            # 加载封面
            self._load_banner()

            # 加载音频
            if self._audio_path and os.path.exists(self._audio_path):
                self._audio_manager.load_music(self._audio_path)

            self._game_state = GameState.READY
            return True

        except Exception as e:
            print(f"[ChartPlayWindow] 加载谱面失败: {e}")
            return False

    def _load_skins(self):
        """加载皮肤"""
        if not self._skin_dir or not os.path.isdir(self._skin_dir):
            return

        self._skin = SkinManager(self._skin_dir)
        if self._skin.open():
            for i in range(5):
                self._tap_pixmaps[i] = self._skin.get_tap(i)
                self._hold_body_pixmaps[i] = self._skin.get_hold_body_pix(i)
                self._hold_tail_pixmaps[i] = self._skin.get_hold_tail_pix(i)
                self._receptor_pixmaps[i] = self._skin.get_receptor_pix(i)

    def _load_banner(self):
        """加载封面图片"""
        if not self._sm_path:
            return

        sm_dir = os.path.dirname(os.path.abspath(self._sm_path))
        banner_names = ["bn.jpg", "banner.jpg", "BN.jpg", "Banner.jpg",
                       "bn.png", "banner.png", "bann.jpg"]

        for name in banner_names:
            banner_path = os.path.join(sm_dir, name)
            if os.path.exists(banner_path):
                try:
                    self._banner_pixmap = QPixmap(banner_path)
                    if not self._banner_pixmap.isNull():
                        return
                except Exception:
                    pass

    def start(self):
        """开始游戏"""
        self._is_playing = True
        self._game_state = GameState.PLAYING
        self._start_time = time.perf_counter()
        self._elapsed_timer.start()
        self._game_timer.start(16)  # ~60fps

        # 播放音频
        if self._audio_path:
            audio_start = max(0.0, self._current_sec - self._chart_offset)
            self._audio_manager.play_music(start_pos=audio_start)

    def pause(self):
        """暂停游戏"""
        if not self._is_playing:
            return

        self._is_playing = False
        self._game_state = GameState.PAUSED
        self._pause_time = self._current_sec
        self._pause_menu_index = 0  # 重置菜单选择
        self._game_timer.stop()
        self._audio_manager.pause_music()
        self.update()

    def resume(self):
        """恢复游戏"""
        if self._is_playing:
            return

        self._is_playing = True
        self._game_state = GameState.PLAYING
        self._start_time = time.perf_counter() - self._pause_time
        self._game_timer.start(16)
        self._audio_manager.resume_music()

    def restart(self):
        """重新开始"""
        self._current_sec = 0.0
        self._pause_time = 0.0
        self._is_playing = False
        self._game_state = GameState.READY
        self._game_timer.stop()

        # 重置判定系统
        self._judge_system.reset()
        self._judge_display = JudgeDisplay()
        self._judge_light = JudgeLight(track_count=5)
        self._hit_effect = HitEffect()

        # 重置按键状态
        self._key_pressed = [False] * 5

        # 停止音频
        self._audio_manager.stop_music()

        # 重新加载音频
        if self._audio_path and os.path.exists(self._audio_path):
            self._audio_manager.load_music(self._audio_path)

        self.update()

    def _update_game(self):
        """更新游戏状态"""
        dt = self._elapsed_timer.elapsed() / 1000.0
        self._elapsed_timer.restart()

        # 更新判定光效
        self._judge_light.update(dt)
        self._hit_effect.update(dt)
        self._judge_display.update(dt)

        if self._game_state == GameState.PLAYING:
            # 更新时间
            self._current_sec = time.perf_counter() - self._start_time

            # 检测MISS
            missed = self._judge_system.check_missed(self._arrow_events, self._current_sec)
            for idx in missed:
                self._judge_display.show(JudgeResult.MISS)

            # 检查结束
            if self._current_sec >= self._total_sec:
                self._current_sec = self._total_sec
                self._finish_game()

        elif self._game_state == GameState.FINISHED:
            self._result_display_time += dt

        # 更新按键状态
        keys = QApplication.keyboardModifiers()
        # Qt中需要单独检查按键状态

        self.update()

    def _finish_game(self):
        """游戏结束"""
        self._is_playing = False
        self._game_state = GameState.FINISHED
        self._game_timer.stop()
        self._audio_manager.stop_music()

        # 生成结果
        self._result = GameResult(
            score=self._judge_system.score,
            max_combo=self._judge_system.max_combo,
            accuracy=self._judge_system.get_accuracy(),
            grade=self._judge_system.get_grade(),
            perfect=self._judge_system.stats.perfect,
            good=self._judge_system.stats.good,
            bad=self._judge_system.stats.bad,
            miss=self._judge_system.stats.miss
        )

        self.update()

    def keyPressEvent(self, event):
        """键盘按下事件"""
        key = event.key()

        # 游戏按键
        if key in self.KEY_MAP:
            track_idx = self.KEY_MAP[key]
            self._key_pressed[track_idx] = True

            if self._game_state == GameState.PLAYING:
                result, arrow_idx = self._judge_system.judge(
                    self._arrow_events,
                    track_idx,
                    self._current_sec
                )
                if result:
                    self._judge_light.trigger(track_idx)
                    self._judge_display.show(result)
                    # 触发命中效果
                    self._hit_effect.trigger(arrow_idx=arrow_idx, track_idx=track_idx)
            event.accept()
            return

        # 功能按键
        if key == Qt.Key.Key_Escape:
            if self._game_state == GameState.PLAYING:
                self.pause()
            elif self._game_state == GameState.PAUSED:
                if self._pause_menu_index == 0:
                    self.resume()
                elif self._pause_menu_index == 1:
                    self.restart()
                else:
                    self.back_requested.emit()
            elif self._game_state == GameState.FINISHED:
                self.back_requested.emit()
            event.accept()
            return

        elif key == Qt.Key.Key_Space:
            if self._game_state == GameState.PLAYING:
                self.pause()
            elif self._game_state == GameState.PAUSED:
                self.resume()
            elif self._game_state == GameState.READY:
                self.start()
            elif self._game_state == GameState.FINISHED:
                self.back_requested.emit()
            event.accept()
            return

        elif key == Qt.Key.Key_R:
            if self._game_state in (GameState.READY, GameState.PLAYING, GameState.PAUSED, GameState.FINISHED):
                self.restart()
            event.accept()
            return

        elif key == Qt.Key.Key_Up:
            if self._game_state == GameState.PAUSED:
                self._pause_menu_index = (self._pause_menu_index - 1) % len(self._pause_menu_options)
                self.update()
            event.accept()
            return

        elif key == Qt.Key.Key_Down:
            if self._game_state == GameState.PAUSED:
                self._pause_menu_index = (self._pause_menu_index + 1) % len(self._pause_menu_options)
                self.update()
            event.accept()
            return

        elif key == Qt.Key.Key_Return:
            if self._game_state == GameState.PAUSED:
                if self._pause_menu_index == 0:
                    self.resume()
                elif self._pause_menu_index == 1:
                    self.restart()
                else:
                    self.back_requested.emit()
            event.accept()
            return

        # 调整速度 [ 和 ]
        elif key == Qt.Key.Key_BracketLeft:
            self._scroll_speed = max(200.0, self._scroll_speed - 60.0)
            event.accept()
            return

        elif key == Qt.Key.Key_BracketRight:
            self._scroll_speed = min(2000.0, self._scroll_speed + 60.0)
            event.accept()
            return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """键盘释放事件"""
        key = event.key()
        if key in self.KEY_MAP:
            track_idx = self.KEY_MAP[key]
            self._key_pressed[track_idx] = False
        else:
            super().keyReleaseEvent(event)

    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() != Qt.MouseButton.LeftButton:
            return

        # 暂停菜单点击
        if self._game_state == GameState.PAUSED:
            w, h = self.width(), self.height()
            menu_w, menu_h = 320, 280
            menu_x = (w - menu_w) // 2
            menu_y = (h - menu_h) // 2

            # 检查点击了哪个菜单项
            for i, option in enumerate(self._pause_menu_options):
                opt_y = menu_y + 80 + i * 55
                opt_rect = QRectF(menu_x + 25, opt_y, menu_w - 50, 45)
                if opt_rect.contains(event.position()):
                    if i == 0:  # 继续
                        self.resume()
                    elif i == 1:  # 重新开始
                        self.restart()
                    else:  # 返回选歌
                        self.back_requested.emit()
                    return

        # 结算界面点击 - 返回选歌
        elif self._game_state == GameState.FINISHED:
            self.back_requested.emit()
            return

        # 准备界面点击 - 开始游戏
        elif self._game_state == GameState.READY:
            self.start()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        # 暂停菜单悬停效果
        if self._game_state == GameState.PAUSED:
            w, h = self.width(), self.height()
            menu_w, menu_h = 320, 280
            menu_x = (w - menu_w) // 2
            menu_y = (h - menu_h) // 2

            # 检查鼠标悬停在哪个菜单项
            for i, option in enumerate(self._pause_menu_options):
                opt_y = menu_y + 80 + i * 55
                opt_rect = QRectF(menu_x + 25, opt_y, menu_w - 50, 45)
                if opt_rect.contains(event.position()):
                    if self._pause_menu_index != i:
                        self._pause_menu_index = i
                        self.update()
                    return

        super().mouseMoveEvent(event)

    def paintEvent(self, event):
        """绘制事件"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制背景
        self._draw_background(painter)

        if self._game_state == GameState.LOADING:
            self._draw_loading(painter)
        elif self._game_state == GameState.READY:
            self._draw_ready(painter)
        elif self._game_state in (GameState.PLAYING, GameState.PAUSED):
            self._draw_game(painter)
            if self._game_state == GameState.PAUSED:
                self._draw_pause_menu(painter)
        elif self._game_state == GameState.FINISHED:
            self._draw_game(painter)
            self._draw_result(painter)

    def _draw_background(self, painter: QPainter):
        """绘制玻璃风格背景"""
        w, h = self.width(), self.height()

        # 封面背景（模糊+暗色叠加）
        if self._banner_pixmap and not self._banner_pixmap.isNull():
            # 缩放封面
            banner_w, banner_h = self._banner_pixmap.width(), self._banner_pixmap.height()
            window_ratio = w / h
            banner_ratio = banner_w / banner_h

            if window_ratio > banner_ratio:
                scale = w / banner_w
            else:
                scale = h / banner_h

            new_w = int(banner_w * scale * 1.2)  # 稍微放大模拟模糊效果
            new_h = int(banner_h * scale * 1.2)

            scaled_banner = self._banner_pixmap.scaled(
                new_w, new_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            # 居中绘制
            x = (w - new_w) // 2
            y = (h - new_h) // 2
            painter.drawPixmap(x, y, scaled_banner)

            # 多层暗色叠加 - 玻璃效果
            # 第一层：主暗色
            painter.fillRect(0, 0, w, h, QColor(10, 12, 18, 220))
            # 第二层：渐变暗角
            vignette = QRadialGradient(w/2, h/2, max(w, h) * 0.8)
            vignette.setColorAt(0, QColor(0, 0, 0, 0))
            vignette.setColorAt(0.5, QColor(0, 0, 0, 30))
            vignette.setColorAt(1, QColor(0, 0, 0, 120))
            painter.fillRect(0, 0, w, h, QBrush(vignette))
        else:
            # 高级渐变背景
            gradient = QLinearGradient(0, 0, w, h)
            gradient.setColorAt(0, QColor(15, 20, 35))
            gradient.setColorAt(0.5, QColor(25, 30, 50))
            gradient.setColorAt(1, QColor(10, 15, 25))
            painter.fillRect(0, 0, w, h, QBrush(gradient))

            # 添加微妙的网格纹理
            painter.setPen(QPen(QColor(255, 255, 255, 8), 1))
            grid_size = 60
            for x in range(0, w, grid_size):
                painter.drawLine(x, 0, x, h)
            for y in range(0, h, grid_size):
                painter.drawLine(0, y, w, y)

        # 底部渐变光晕（模拟舞台灯光）
        bottom_glow = QLinearGradient(0, h * 0.7, 0, h)
        bottom_glow.setColorAt(0, QColor(80, 120, 200, 0))
        bottom_glow.setColorAt(0.5, QColor(60, 100, 180, 20))
        bottom_glow.setColorAt(1, QColor(40, 80, 160, 40))
        painter.fillRect(0, int(h * 0.7), w, int(h * 0.3), QBrush(bottom_glow))

    def _draw_loading(self, painter: QPainter):
        """绘制玻璃风格加载界面"""
        w, h = self.width(), self.height()

        # 中央玻璃卡片
        card_w, card_h = 300, 100
        card_x = (w - card_w) // 2
        card_y = (h - card_h) // 2

        # 玻璃背景
        glass_gradient = QLinearGradient(card_x, card_y, card_x, card_y + card_h)
        glass_gradient.setColorAt(0, QColor(45, 55, 75, 200))
        glass_gradient.setColorAt(1, QColor(30, 40, 60, 180))

        card_rect = QRectF(card_x, card_y, card_w, card_h)
        glass_path = QPainterPath()
        glass_path.addRoundedRect(card_rect, 20, 20)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glass_gradient))
        painter.drawPath(glass_path)

        # 边框
        painter.setPen(QPen(QColor(100, 140, 200, 100), 1))
        painter.drawPath(glass_path)

        # 加载文字
        font = create_font(18)
        painter.setFont(font)
        painter.setPen(QColor(200, 210, 230))
        painter.drawText(card_rect, Qt.AlignmentFlag.AlignCenter, "加载中...")

    def _draw_ready(self, painter: QPainter):
        """绘制玻璃风格准备界面"""
        w, h = self.width(), self.height()

        # 中央玻璃卡片
        card_w, card_h = 500, 150
        card_x = (w - card_w) // 2
        card_y = (h - card_h) // 2

        # 外发光
        for i in range(3):
            glow_rect = QRectF(card_x - i*3, card_y - i*3, card_w + i*6, card_h + i*6)
            glow_path = QPainterPath()
            glow_path.addRoundedRect(glow_rect, 25 + i*2, 25 + i*2)
            painter.setPen(QPen(QColor(80, 160, 255, 15 - i*5), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(glow_path)

        # 玻璃背景
        glass_gradient = QLinearGradient(card_x, card_y, card_x, card_y + card_h)
        glass_gradient.setColorAt(0, QColor(45, 55, 75, 220))
        glass_gradient.setColorAt(0.5, QColor(38, 48, 68, 200))
        glass_gradient.setColorAt(1, QColor(30, 40, 60, 180))

        card_rect = QRectF(card_x, card_y, card_w, card_h)
        glass_path = QPainterPath()
        glass_path.addRoundedRect(card_rect, 25, 25)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glass_gradient))
        painter.drawPath(glass_path)

        # 边框
        painter.setPen(QPen(QColor(120, 150, 200, 120), 1.5))
        painter.drawPath(glass_path)

        # 顶部高光
        highlight = QLinearGradient(card_x, card_y, card_x, card_y + card_h * 0.3)
        highlight.setColorAt(0, QColor(255, 255, 255, 25))
        highlight.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(card_x + 15, card_y + 5, card_w - 30, card_h * 0.25), QBrush(highlight))

        # 歌曲标题
        font_title = create_font(20, bold=True)
        painter.setFont(font_title)
        painter.setPen(QColor(230, 240, 255))
        title_text = self._chart_title[:40] + "..." if len(self._chart_title) > 40 else self._chart_title
        painter.drawText(QRectF(card_x, card_y + 30, card_w, 40), Qt.AlignmentFlag.AlignCenter, title_text)

        # 提示文字
        font_hint = create_font(14)
        painter.setFont(font_hint)
        painter.setPen(QColor(140, 160, 200))
        painter.drawText(QRectF(card_x, card_y + 80, card_w, 35), Qt.AlignmentFlag.AlignCenter,
                        "按 空格键 开始游戏")

    def _draw_game(self, painter: QPainter):
        """绘制游戏画面"""
        w, h = self.width(), self.height()

        # 布局计算
        margin = 20
        track_count = 5
        track_total_w = min(620, w - 280)
        track_total_w = max(400, track_total_w)
        track_start_x = (w - track_total_w) // 2
        single_track_w = track_total_w // track_count

        header_h = 80
        # 判定线位置（窗口高度的18%位置 + 顶部高度，更靠上）- 恢复原始位置
        judge_y = int(h * 0.18) + header_h
        footer_h = 50

        # 绘制轨道背景
        self._draw_track_background(painter, track_start_x, header_h,
                                   track_total_w, h - footer_h - header_h,
                                   single_track_w, track_count)

        # 绘制判定线
        self._draw_judge_line(painter, track_start_x, track_total_w, judge_y)

        # 绘制判定区
        for i in range(track_count):
            self._draw_receptor(painter, i, track_start_x, single_track_w, judge_y)

        # 绘制箭头
        self._draw_arrows(painter, track_start_x, single_track_w, judge_y)

        # 绘制命中效果
        self._draw_hit_effects(painter, track_start_x, single_track_w, judge_y)

        # 绘制判定显示
        self._draw_judge_display(painter, judge_y)

        # 绘制顶部信息栏
        self._draw_header(painter, header_h)

        # 绘制右侧统计面板
        self._draw_stats_panel(painter, track_start_x + track_total_w + 15, header_h + 20)

        # 绘制底部提示
        self._draw_footer_tips(painter, h - footer_h + 10)

    def _draw_track_background(self, painter: QPainter, start_x: int, start_y: int,
                               width: int, height: int, single_w: int, count: int):
        """绘制玻璃风格轨道背景"""
        # 整体轨道区域玻璃背景
        track_rect = QRectF(start_x - 10, start_y - 5, width + 20, height + 10)

        # 外发光
        for i in range(3):
            glow_rect = track_rect.adjusted(-i*3, -i*3, i*3, i*3)
            glow_path = QPainterPath()
            glow_path.addRoundedRect(glow_rect, 15 + i*3, 15 + i*3)
            painter.setPen(QPen(QColor(80, 140, 220, 15 - i*5), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(glow_path)

        # 主玻璃背景
        glass_gradient = QLinearGradient(start_x, start_y, start_x, start_y + height)
        glass_gradient.setColorAt(0, QColor(30, 35, 50, 120))
        glass_gradient.setColorAt(0.3, QColor(25, 30, 45, 100))
        glass_gradient.setColorAt(1, QColor(20, 25, 40, 140))

        glass_path = QPainterPath()
        glass_path.addRoundedRect(track_rect, 12, 12)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glass_gradient))
        painter.drawPath(glass_path)

        # 玻璃边框
        painter.setPen(QPen(QColor(100, 120, 160, 60), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(glass_path)

        # 顶部高光
        highlight_rect = QRectF(start_x - 10, start_y - 5, width + 20, height * 0.15)
        highlight_gradient = QLinearGradient(start_x, start_y - 5, start_x, start_y + height * 0.1)
        highlight_gradient.setColorAt(0, QColor(255, 255, 255, 25))
        highlight_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(highlight_rect, QBrush(highlight_gradient))

        # 绘制单个轨道
        for i in range(count):
            x = start_x + i * single_w

            # 轨道底色 - 交替颜色
            if i % 2 == 0:
                base_color = QColor(40, 45, 65, 60)
            else:
                base_color = QColor(35, 40, 60, 70)

            # 轨道渐变
            track_grad = QLinearGradient(x, start_y, x, start_y + height)
            track_grad.setColorAt(0, QColor(base_color.red(), base_color.green(), base_color.blue(), base_color.alpha() + 20))
            track_grad.setColorAt(0.5, base_color)
            track_grad.setColorAt(1, QColor(base_color.red(), base_color.green(), base_color.blue(), base_color.alpha() - 10))

            track_path = QPainterPath()
            track_path.addRoundedRect(x + 3, start_y, single_w - 6, height, 6, 6)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(track_grad))
            painter.drawPath(track_path)

            # 轨道分割线
            if i > 0:
                painter.setPen(QPen(QColor(60, 70, 100, 40), 1))
                painter.drawLine(x + 1, start_y + 10, x + 1, start_y + height - 10)

    def _draw_judge_line(self, painter: QPainter, track_start_x: int, track_total_w: int, judge_y: int):
        """绘制判定区效果（隐藏横向线，只保留微妙的光晕）"""
        # 只在判定位置显示微妙的光晕效果，不绘制明显的横线
        pulse_x = track_start_x + track_total_w // 2
        pulse_gradient = QRadialGradient(pulse_x, judge_y, 25)
        pulse_gradient.setColorAt(0, QColor(255, 255, 255, 30))
        pulse_gradient.setColorAt(0.5, QColor(150, 200, 255, 15))
        pulse_gradient.setColorAt(1, QColor(100, 150, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(pulse_gradient))
        painter.drawEllipse(QPointF(pulse_x, judge_y), track_total_w // 2, 15)

    def _draw_receptor(self, painter: QPainter, track_idx: int, track_start_x: int,
                       single_track_w: int, judge_y: int):
        """绘制判定区（含接近提示和判定光）"""
        center_x = track_start_x + track_idx * single_track_w + single_track_w // 2

        # 检测是否有箭头接近判定区（用于高亮提示）
        approaching_arrow = False
        for i, event in enumerate(self._arrow_events):
            if self._judge_system.is_arrow_processed(i):
                continue
            if event.track_idx != track_idx:
                continue
            # 检测箭头是否在判定区附近（±0.15秒内）
            time_diff = event.start_sec - self._current_sec
            if -0.05 <= time_diff <= 0.15:
                approaching_arrow = True
                break

        # 绘制接近提示光晕
        if approaching_arrow:
            for k in range(3):
                r = int(single_track_w * (0.25 + 0.1 * k))
                alpha = 60 - k * 15
                color = QColor(100, 200, 255, max(0, alpha))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(color))
                painter.drawEllipse(QPointF(center_x, judge_y), r, r)

        # 绘制判定光（命中时的闪光效果）
        light_strength = self._judge_light.get_light(track_idx)
        if light_strength > 0:
            for k in range(5):
                r = int(single_track_w * (0.18 + 0.08 * k))
                alpha = int(light_strength * (140 - k * 22))
                color = QColor(255, 235, 185, max(0, alpha))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(color))
                painter.drawEllipse(QPointF(center_x, judge_y), r, r)

        # 判定区皮肤
        receptor_pix = self._receptor_pixmaps[track_idx]
        if receptor_pix:
            base_w = int(single_track_w * 0.55)
            scale_factor = 0.85 if self._key_pressed[track_idx] else 1.0
            target_w = int(base_w * scale_factor)
            scale = target_w / max(1, receptor_pix.width())
            target_h = int(receptor_pix.height() * scale)

            scaled_pix = receptor_pix.scaled(target_w, target_h,
                                             Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation)
            y_offset = 3 if self._key_pressed[track_idx] else 0
            painter.drawPixmap(center_x - target_w // 2, judge_y - target_h // 2 + y_offset, scaled_pix)
        else:
            # 默认判定区
            radius = int(single_track_w * 0.22)
            if self._key_pressed[track_idx]:
                radius = int(radius * 0.85)
            color = QColor(80, 80, 100) if self._key_pressed[track_idx] else QColor(60, 60, 80)
            painter.setPen(QPen(QColor(100, 100, 120), 2))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(center_x, judge_y), radius, radius)

    def _draw_arrows(self, painter: QPainter, track_start_x: int, single_track_w: int, judge_y: int):
        """绘制箭头"""
        h = self.height()
        bottom_y = h - 50
        top_y = 80
        visible_sec = (bottom_y - judge_y) / self._scroll_speed
        advance_sec = visible_sec + 1.0
        cur_sec = self._current_sec

        for idx, event in enumerate(self._arrow_events):
            # 跳过已处理的箭头（有命中动画的不跳过，让动画显示）
            if self._judge_system.is_arrow_processed(idx) and idx not in self._hit_effect._effects:
                continue

            if event.start_sec < cur_sec - 0.5 and event.end_sec < cur_sec - 0.5:
                continue
            if event.start_sec > cur_sec + advance_sec:
                break

            # 绘制命中动画（在其他箭头之上）
            if idx in self._hit_effect._effects:
                continue  # 命中动画单独绘制

            center_x = track_start_x + event.track_idx * single_track_w + single_track_w // 2
            dy_start = (event.start_sec - cur_sec) * self._scroll_speed
            y_start = judge_y + dy_start

            # 点按箭头 - 只绘制判定线及以下的箭头（原始逻辑）
            if abs(event.end_sec - event.start_sec) < 1e-6:
                if y_start >= judge_y and y_start <= bottom_y:
                    self._draw_tap_arrow(painter, event.track_idx, center_x, y_start, single_track_w, judge_y)
            # 长按箭头
            else:
                dy_end = (event.end_sec - cur_sec) * self._scroll_speed
                y_end = judge_y + dy_end
                self._draw_hold_arrow(painter, event.track_idx, center_x, y_start, y_end, single_track_w, judge_y)

    def _draw_tap_arrow(self, painter: QPainter, track_idx: int, center_x: float, y: float,
                        single_track_w: int, judge_y: int):
        """绘制点按箭头 - 支持判定线裁剪"""
        h = self.height()
        # 不绘制完全在判定线以上或可视区域外的箭头
        if y < 50 or y > h - 40:
            return

        tap_pix = self._tap_pixmaps[track_idx]
        if tap_pix:
            # 按轨道宽度比例缩放箭头皮肤
            target_w = int(single_track_w * 0.60)
            target_w = max(22, target_w)
            target_h = int(tap_pix.height() * (target_w / max(1, tap_pix.width())))

            scaled_pix = tap_pix.scaled(target_w, target_h,
                                        Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation)

            # 计算绘制位置
            draw_x = int(center_x - target_w // 2)
            draw_y = int(y - target_h // 2)

            # 判定线裁剪：如果箭头部分在判定线以上，只显示判定线以下的部分
            arrow_top = draw_y
            arrow_bottom = draw_y + target_h

            if arrow_top < judge_y:
                # 箭头被判定线裁剪
                if arrow_bottom <= judge_y:
                    # 箭头完全在判定线以上，不绘制
                    return
                else:
                    # 裁剪显示判定线以下的部分
                    clip_top = judge_y - arrow_top  # 需要裁剪的高度
                    clip_height = target_h - clip_top

                    if clip_height > 0:
                        # 裁剪图片
                        clipped_pix = scaled_pix.copy(0, clip_top, target_w, clip_height)
                        painter.drawPixmap(draw_x, judge_y, clipped_pix)
            else:
                # 箭头完全在判定线以下，正常绘制
                painter.drawPixmap(draw_x, draw_y, scaled_pix)
        else:
            # 无皮肤时绘制默认圆形箭头
            radius = max(9, min(22, single_track_w // 4))

            # 判定线裁剪
            arrow_top = y - radius
            if arrow_top < judge_y:
                if y + radius <= judge_y:
                    return  # 完全在判定线以上
                # 绘制裁剪的下半圆
                clip_height = (y + radius) - judge_y
                if clip_height > 0:
                    painter.setBrush(QBrush(QColor(240, 240, 245)))
                    painter.setPen(QPen(QColor(20, 20, 25), 3))
                    # 绘制半圆或部分圆
                    painter.drawPie(int(center_x - radius), int(y - radius),
                                   int(radius * 2), int(radius * 2),
                                   0, -180 * 16)  # 下半圆
            else:
                painter.setBrush(QBrush(QColor(240, 240, 245)))
                painter.setPen(QPen(QColor(20, 20, 25), 3))
                painter.drawEllipse(QPointF(center_x, y), radius, radius)

    def _draw_hold_arrow(self, painter: QPainter, track_idx: int, center_x: float,
                         y_start: float, y_end: float, single_track_w: int, judge_y: int):
        """绘制长按箭头"""
        h = self.height()
        orig_y1 = min(y_start, y_end)
        orig_y2 = max(y_start, y_end)

        y1 = max(orig_y1, float(judge_y))
        y2 = orig_y2

        if y2 < 50 or y1 > h - 40:
            return

        y1c = max(50.0, y1)
        y2c = min(float(h - 40), y2)
        if y2c <= y1c:
            return

        body_w = int(single_track_w * 0.50)
        body_w = max(20, body_w)

        # 绘制长按箭身
        hold_body_pix = self._hold_body_pixmaps[track_idx]
        body_height = int(y2c - y1c)

        if body_height > 0 and hold_body_pix:
            scale = body_w / max(1, hold_body_pix.width())
            single_h = int(hold_body_pix.height() * scale)
            single_h = max(8, single_h)

            scaled_pix = hold_body_pix.scaled(body_w, single_h,
                                              Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)

            current_y = int(y1c)
            while current_y < int(y2c):
                remaining_h = int(y2c) - current_y
                if remaining_h >= single_h:
                    painter.drawPixmap(int(center_x - body_w // 2), current_y, scaled_pix)
                    current_y += single_h
                else:
                    last_pix = hold_body_pix.scaled(body_w, remaining_h,
                                                    Qt.AspectRatioMode.KeepAspectRatio,
                                                    Qt.TransformationMode.SmoothTransformation)
                    painter.drawPixmap(int(center_x - body_w // 2), current_y, last_pix)
                    break
        elif body_height > 0:
            rect = QRectF(center_x - body_w // 2, y1c, body_w, body_height)
            painter.setPen(QPen(QColor(40, 40, 50), 2))
            painter.setBrush(QBrush(QColor(180, 180, 200)))
            painter.drawRoundedRect(rect, 8, 8)

        # 绘制长按箭尾
        hold_tail_pix = self._hold_tail_pixmaps[track_idx]
        tail_y = min(orig_y2, float(h - 40))

        if tail_y >= judge_y and tail_y >= 50:
            if hold_tail_pix:
                tail_w = int(single_track_w * 0.55)
                tail_w = max(22, tail_w)
                scale = tail_w / max(1, hold_tail_pix.width())
                tail_h = int(hold_tail_pix.height() * scale)

                tail_pix = hold_tail_pix.scaled(tail_w, tail_h,
                                                Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation)
                painter.drawPixmap(int(center_x - tail_w // 2), int(tail_y - tail_h // 2), tail_pix)
            else:
                tail_w = int(single_track_w * 0.35)
                tail_h = max(8, tail_w // 2)
                rect = QRectF(center_x - tail_w // 2, tail_y - tail_h, tail_w, tail_h)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(160, 160, 180)))
                painter.drawRoundedRect(rect, 4, 4)

        # 绘制长按头部
        if orig_y1 >= judge_y:
            self._draw_tap_arrow(painter, track_idx, center_x, orig_y1, single_track_w, judge_y)

    def _draw_hit_effects(self, painter: QPainter, track_start_x: int, single_track_w: int, judge_y: int):
        """绘制命中效果（箭头命中时向上飘动的动画）"""
        for idx, effect in self._hit_effect.get_effects().items():
            track_idx = effect.get("track_idx", 0)
            center_x = track_start_x + track_idx * single_track_w + single_track_w // 2
            # 动画位置：从判定线向上飘
            y_offset = effect.get("y", 0)
            y_pos = judge_y - y_offset * (1 - effect["alpha"] * 0.5)

            # 绘制带动画效果的箭头
            alpha = int(effect["alpha"] * 255)
            scale = effect["scale"]

            tap_pix = self._tap_pixmaps[track_idx] if track_idx < len(self._tap_pixmaps) else None
            if tap_pix:
                base_w = int(single_track_w * 0.60)
                base_w = max(22, base_w)
                target_w = int(base_w * scale)
                target_h = int(tap_pix.height() * (target_w / max(1, tap_pix.width())))

                scaled_pix = tap_pix.scaled(target_w, target_h,
                                            Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
                # 设置透明度
                painter.setOpacity(effect["alpha"])
                painter.drawPixmap(int(center_x - target_w // 2), int(y_pos - target_h // 2), scaled_pix)
                painter.setOpacity(1.0)
            else:
                # 无皮肤时的动画效果
                radius = int(max(9, min(22, single_track_w // 4)) * scale)
                color = QColor(240, 240, 245, alpha)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(color))
                painter.drawEllipse(QPointF(center_x, y_pos), radius, radius)

    def _draw_judge_display(self, painter: QPainter, judge_y: int):
        """绘制判定显示"""
        if not self._judge_display.is_showing():
            return

        result = self._judge_display.current_result
        if not result:
            return

        color_tuple = self._judge_system.get_result_color(result)
        alpha = self._judge_display.get_alpha()
        color = QColor(color_tuple[0], color_tuple[1], color_tuple[2], int(alpha * 255))

        font = create_font(36, bold=True)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(QRectF(0, judge_y + 80, self.width(), 60),
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, result.value)

    def _draw_header(self, painter: QPainter, header_h: int):
        """绘制玻璃风格顶部信息栏"""
        w = self.width()
        margin = 15
        header_rect = QRectF(margin, 8, w - margin * 2, header_h - 5)

        # 玻璃背景
        glass_gradient = QLinearGradient(margin, 8, margin, header_h)
        glass_gradient.setColorAt(0, QColor(40, 45, 60, 180))
        glass_gradient.setColorAt(0.5, QColor(30, 35, 50, 160))
        glass_gradient.setColorAt(1, QColor(25, 30, 45, 140))

        glass_path = QPainterPath()
        glass_path.addRoundedRect(header_rect, 15, 15)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glass_gradient))
        painter.drawPath(glass_path)

        # 玻璃边框 - 发光效果
        painter.setPen(QPen(QColor(100, 140, 200, 80), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(glass_path)

        # 顶部高光
        highlight = QLinearGradient(margin, 8, margin, 8 + header_h * 0.4)
        highlight.setColorAt(0, QColor(255, 255, 255, 30))
        highlight.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(margin + 10, 8, w - margin * 2 - 20, header_h * 0.35), QBrush(highlight))

        # 歌曲标题
        font_title = create_font(18, bold=True)
        painter.setFont(font_title)
        painter.setPen(QColor(240, 245, 255))
        title_text = self._chart_title[:35] + "..." if len(self._chart_title) > 35 else self._chart_title
        painter.drawText(35, 38, title_text)

        # 时间
        font_normal = create_font(13)
        painter.setFont(font_normal)
        painter.setPen(QColor(160, 170, 190))
        time_str = f"{format_seconds(self._current_sec)} / {format_seconds(self._total_sec)}"
        painter.drawText(35, 58, time_str)

        # 状态 - 带颜色指示器
        status_str = "▶ 播放中" if self._is_playing else "⏸ 已暂停"
        status_color = QColor(100, 220, 150) if self._is_playing else QColor(255, 200, 100)
        painter.setPen(status_color)
        painter.drawText(220, 58, status_str)

        # 右侧参数面板
        param_x = w - 140
        param_w = 120
        param_rect = QRectF(param_x, 15, param_w, header_h - 20)

        # 参数玻璃背景
        param_gradient = QLinearGradient(param_x, 15, param_x, header_h - 5)
        param_gradient.setColorAt(0, QColor(30, 35, 50, 100))
        param_gradient.setColorAt(1, QColor(20, 25, 40, 80))
        param_path = QPainterPath()
        param_path.addRoundedRect(param_rect, 8, 8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(param_gradient))
        painter.drawPath(param_path)

        painter.setPen(QPen(QColor(80, 100, 140, 60), 1))
        painter.drawPath(param_path)

        # 参数文字
        font_small = create_font(10)
        painter.setFont(font_small)
        painter.setPen(QColor(140, 150, 170))
        params = [
            f"Speed: {int(self._scroll_speed)}",
            f"Offset: {self._chart_offset:+.2f}s",
        ]
        for i, param in enumerate(params):
            painter.drawText(param_x + 10, 32 + i * 18, param)

    def _draw_stats_panel(self, painter: QPainter, panel_x: int, panel_y: int):
        """绘制玻璃风格统计面板"""
        panel_w, panel_h = 140, 240

        # 外发光
        for i in range(3):
            glow_rect = QRectF(panel_x - i*2, panel_y - i*2, panel_w + i*4, panel_h + i*4)
            glow_path = QPainterPath()
            glow_path.addRoundedRect(glow_rect, 15 + i, 15 + i)
            painter.setPen(QPen(QColor(80, 140, 220, 12 - i*4), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(glow_path)

        # 玻璃背景
        glass_gradient = QLinearGradient(panel_x, panel_y, panel_x, panel_y + panel_h)
        glass_gradient.setColorAt(0, QColor(35, 40, 55, 200))
        glass_gradient.setColorAt(0.3, QColor(28, 33, 48, 180))
        glass_gradient.setColorAt(1, QColor(22, 27, 42, 160))

        panel_rect = QRectF(panel_x, panel_y, panel_w, panel_h)
        glass_path = QPainterPath()
        glass_path.addRoundedRect(panel_rect, 15, 15)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glass_gradient))
        painter.drawPath(glass_path)

        # 玻璃边框
        painter.setPen(QPen(QColor(100, 130, 180, 100), 1))
        painter.drawPath(glass_path)

        # 顶部高光
        highlight = QLinearGradient(panel_x, panel_y, panel_x, panel_y + panel_h * 0.25)
        highlight.setColorAt(0, QColor(255, 255, 255, 20))
        highlight.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(panel_x + 5, panel_y + 3, panel_w - 10, panel_h * 0.2), QBrush(highlight))

        # 标题
        font_title = create_font(13, bold=True)
        painter.setFont(font_title)
        painter.setPen(QColor(200, 210, 230))
        painter.drawText(panel_x + 12, panel_y + 28, "📊 统计")

        # 分割线
        painter.setPen(QPen(QColor(80, 90, 120, 60), 1))
        painter.drawLine(panel_x + 10, panel_y + 40, panel_x + panel_w - 10, panel_y + 40)

        # 判定统计
        font_normal = create_font(11)
        painter.setFont(font_normal)

        stats = [
            ("PERFECT", self._judge_system.stats.perfect, QColor(100, 255, 180)),
            ("GOOD", self._judge_system.stats.good, QColor(100, 200, 255)),
            ("BAD", self._judge_system.stats.bad, QColor(255, 180, 100)),
            ("MISS", self._judge_system.stats.miss, QColor(255, 100, 100)),
        ]

        for i, (label, count, color) in enumerate(stats):
            y = panel_y + 60 + i * 32

            # 背景条
            bar_rect = QRectF(panel_x + 10, y - 8, panel_w - 20, 24)
            bar_gradient = QLinearGradient(panel_x + 10, y - 8, panel_x + panel_w - 10, y - 8)
            bar_gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 25))
            bar_gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 8))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(bar_gradient))
            painter.drawRoundedRect(bar_rect, 4, 4)

            # 标签和数值
            painter.setPen(color)
            painter.drawText(panel_x + 15, y + 6, label)

            # 数字右对齐
            painter.setPen(QColor(240, 245, 255))
            count_str = str(count)
            painter.drawText(panel_x + panel_w - 15 - len(count_str) * 7, y + 6, count_str)

        # 分割线
        painter.setPen(QPen(QColor(80, 90, 120, 60), 1))
        painter.drawLine(panel_x + 10, panel_y + 180, panel_x + panel_w - 10, panel_y + 180)

        # 分数 - 大号发光
        font_score = create_font(22, bold=True)
        painter.setFont(font_score)

        # 分数发光效果
        score_str = f"{self._judge_system.score:,}"
        painter.setPen(QColor(255, 220, 100))
        painter.drawText(panel_x + 10, panel_y + 210, score_str)

        # 连击
        font_combo = create_font(10)
        painter.setFont(font_combo)

        combo = self._judge_system.combo
        if combo > 50:
            combo_color = QColor(255, 200, 100)
        elif combo > 10:
            combo_color = QColor(100, 255, 180)
        else:
            combo_color = QColor(140, 150, 170)
        painter.setPen(combo_color)
        painter.drawText(panel_x + 10, panel_y + 230, f"🔥 Combo: {combo}")

        painter.setPen(QColor(100, 110, 130))
        painter.drawText(panel_x + 85, panel_y + 230, f"Max: {self._judge_system.max_combo}")

    def _draw_footer_tips(self, painter: QPainter, y: int):
        """绘制底部提示"""
        # 玻璃背景条
        footer_rect = QRectF(15, y, self.width() - 30, 28)
        glass_gradient = QLinearGradient(15, y, 15, y + 28)
        glass_gradient.setColorAt(0, QColor(30, 35, 50, 100))
        glass_gradient.setColorAt(1, QColor(25, 30, 45, 80))

        glass_path = QPainterPath()
        glass_path.addRoundedRect(footer_rect, 8, 8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glass_gradient))
        painter.drawPath(glass_path)

        painter.setPen(QPen(QColor(80, 90, 120, 60), 1))
        painter.drawPath(glass_path)

        font_small = create_font(9)
        painter.setFont(font_small)
        painter.setPen(QColor(120, 130, 150))
        tips = "空格:暂停  R:重播  [/]:调速  Esc:菜单"
        painter.drawText(25, y + 18, tips)

    def _draw_pause_menu(self, painter: QPainter):
        """绘制玻璃风格暂停菜单"""
        w, h = self.width(), self.height()

        # 毛玻璃遮罩
        overlay = QRadialGradient(w/2, h/2, max(w, h) * 0.7)
        overlay.setColorAt(0, QColor(0, 0, 0, 100))
        overlay.setColorAt(0.5, QColor(0, 0, 0, 150))
        overlay.setColorAt(1, QColor(0, 0, 0, 180))
        painter.fillRect(0, 0, w, h, QBrush(overlay))

        # 菜单面板
        menu_w, menu_h = 320, 280
        menu_x = (w - menu_w) // 2
        menu_y = (h - menu_h) // 2

        # 外发光
        for i in range(4):
            glow_rect = QRectF(menu_x - i*3, menu_y - i*3, menu_w + i*6, menu_h + i*6)
            glow_path = QPainterPath()
            glow_path.addRoundedRect(glow_rect, 25 + i*2, 25 + i*2)
            painter.setPen(QPen(QColor(80, 160, 255, 15 - i*4), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(glow_path)

        # 玻璃面板背景
        glass_gradient = QLinearGradient(menu_x, menu_y, menu_x, menu_y + menu_h)
        glass_gradient.setColorAt(0, QColor(45, 55, 75, 230))
        glass_gradient.setColorAt(0.3, QColor(38, 48, 68, 220))
        glass_gradient.setColorAt(1, QColor(30, 40, 60, 210))

        menu_rect = QRectF(menu_x, menu_y, menu_w, menu_h)
        glass_path = QPainterPath()
        glass_path.addRoundedRect(menu_rect, 25, 25)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glass_gradient))
        painter.drawPath(glass_path)

        # 玻璃边框
        painter.setPen(QPen(QColor(120, 150, 200, 120), 1.5))
        painter.drawPath(glass_path)

        # 顶部高光
        highlight = QLinearGradient(menu_x, menu_y, menu_x, menu_y + menu_h * 0.3)
        highlight.setColorAt(0, QColor(255, 255, 255, 30))
        highlight.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(menu_x + 15, menu_y + 5, menu_w - 30, menu_h * 0.25), QBrush(highlight))

        # 标题
        font_title = create_font(24, bold=True)
        painter.setFont(font_title)
        painter.setPen(QColor(230, 240, 255))
        painter.drawText(QRectF(menu_x, menu_y + 25, menu_w, 45), Qt.AlignmentFlag.AlignCenter, "⏸ 暂停")

        # 菜单选项
        font_normal = create_font(14)
        painter.setFont(font_normal)

        for i, option in enumerate(self._pause_menu_options):
            opt_y = menu_y + 80 + i * 55
            opt_rect = QRectF(menu_x + 25, opt_y, menu_w - 50, 45)
            is_selected = (i == self._pause_menu_index)

            # 选项背景
            if is_selected:
                # 选中态 - 发光效果
                sel_gradient = QLinearGradient(opt_rect.x(), opt_rect.y(), opt_rect.x() + opt_rect.width(), opt_rect.y())
                sel_gradient.setColorAt(0, QColor(80, 140, 220, 60))
                sel_gradient.setColorAt(0.5, QColor(100, 160, 240, 80))
                sel_gradient.setColorAt(1, QColor(80, 140, 220, 60))

                opt_path = QPainterPath()
                opt_path.addRoundedRect(opt_rect, 12, 12)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(sel_gradient))
                painter.drawPath(opt_path)

                # 发光边框
                painter.setPen(QPen(QColor(100, 180, 255, 200), 1.5))
                painter.drawPath(opt_path)

                text_color = QColor(255, 255, 255)
            else:
                # 未选中态
                opt_path = QPainterPath()
                opt_path.addRoundedRect(opt_rect, 12, 12)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(40, 50, 70, 50)))
                painter.drawPath(opt_path)
                painter.setPen(QPen(QColor(80, 90, 110, 80), 1))
                painter.drawPath(opt_path)
                text_color = QColor(160, 170, 190)

            painter.setPen(text_color)
            painter.drawText(opt_rect, Qt.AlignmentFlag.AlignCenter, option)

    def _draw_result(self, painter: QPainter):
        """绘制玻璃风格结算界面"""
        if not self._result:
            return

        w, h = self.width(), self.height()

        # 毛玻璃遮罩
        overlay = QRadialGradient(w/2, h/2, max(w, h) * 0.7)
        overlay.setColorAt(0, QColor(0, 0, 0, 120))
        overlay.setColorAt(0.6, QColor(0, 0, 0, 170))
        overlay.setColorAt(1, QColor(0, 0, 0, 200))
        painter.fillRect(0, 0, w, h, QBrush(overlay))

        # 结算面板
        panel_w, panel_h = 420, 400
        panel_x = (w - panel_w) // 2
        panel_y = (h - panel_h) // 2

        # 外发光
        for i in range(5):
            glow_rect = QRectF(panel_x - i*3, panel_y - i*3, panel_w + i*6, panel_h + i*6)
            glow_path = QPainterPath()
            glow_path.addRoundedRect(glow_rect, 30 + i*2, 30 + i*2)
            painter.setPen(QPen(QColor(100, 180, 255, 12 - i*3), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(glow_path)

        # 玻璃面板背景
        glass_gradient = QLinearGradient(panel_x, panel_y, panel_x, panel_y + panel_h)
        glass_gradient.setColorAt(0, QColor(45, 55, 75, 240))
        glass_gradient.setColorAt(0.2, QColor(38, 48, 68, 230))
        glass_gradient.setColorAt(1, QColor(30, 40, 60, 220))

        panel_rect = QRectF(panel_x, panel_y, panel_w, panel_h)
        glass_path = QPainterPath()
        glass_path.addRoundedRect(panel_rect, 30, 30)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glass_gradient))
        painter.drawPath(glass_path)

        # 玻璃边框
        painter.setPen(QPen(QColor(120, 150, 200, 150), 1.5))
        painter.drawPath(glass_path)

        # 顶部高光
        highlight = QLinearGradient(panel_x, panel_y, panel_x, panel_y + panel_h * 0.25)
        highlight.setColorAt(0, QColor(255, 255, 255, 35))
        highlight.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(panel_x + 20, panel_y + 8, panel_w - 40, panel_h * 0.2), QBrush(highlight))

        # 标题
        font_title = create_font(22, bold=True)
        painter.setFont(font_title)
        painter.setPen(QColor(220, 230, 245))
        painter.drawText(QRectF(panel_x, panel_y + 20, panel_w, 45), Qt.AlignmentFlag.AlignCenter, "🎯 结算")

        # 评级
        grade_colors = {
            "S": QColor(255, 215, 0),
            "AAA": QColor(255, 180, 0),
            "AA": QColor(255, 150, 0),
            "A": QColor(100, 255, 100),
            "B": QColor(100, 200, 255),
            "C": QColor(150, 150, 200),
            "D": QColor(200, 150, 150),
            "F": QColor(150, 150, 150),
        }
        grade_color = grade_colors.get(self._result.grade, QColor(200, 210, 230))

        # 评级发光效果
        font_grade = create_font(56, bold=True)
        painter.setFont(font_grade)

        # 发光层
        for i in range(3):
            glow_color = QColor(grade_color.red(), grade_color.green(), grade_color.blue(), 50 - i*15)
            painter.setPen(glow_color)
            offset = i * 2
            painter.drawText(QRectF(panel_x - offset, panel_y + 60 - offset, panel_w + offset*2, 70 + offset),
                           Qt.AlignmentFlag.AlignCenter, self._result.grade)

        # 主评级
        painter.setPen(grade_color)
        painter.drawText(QRectF(panel_x, panel_y + 60, panel_w, 70), Qt.AlignmentFlag.AlignCenter, self._result.grade)

        # 分数
        font_score = create_font(20, bold=True)
        painter.setFont(font_score)
        painter.setPen(QColor(255, 230, 120))
        score_str = f"Score: {self._result.score:,}"
        painter.drawText(QRectF(panel_x, panel_y + 140, panel_w, 40), Qt.AlignmentFlag.AlignCenter, score_str)

        # 分割线
        painter.setPen(QPen(QColor(80, 90, 120, 80), 1))
        painter.drawLine(panel_x + 40, panel_y + 180, panel_x + panel_w - 40, panel_y + 180)

        # 判定统计
        font_normal = create_font(13)
        painter.setFont(font_normal)
        stats = [
            ("PERFECT", self._result.perfect, QColor(100, 255, 180)),
            ("GOOD", self._result.good, QColor(100, 200, 255)),
            ("BAD", self._result.bad, QColor(255, 180, 100)),
            ("MISS", self._result.miss, QColor(255, 100, 100)),
        ]

        for i, (label, count, color) in enumerate(stats):
            y = panel_y + 200 + i * 35

            # 背景条
            bar_rect = QRectF(panel_x + 50, y - 10, panel_w - 100, 28)
            bar_gradient = QLinearGradient(bar_rect.x(), y - 10, bar_rect.x() + bar_rect.width(), y - 10)
            bar_gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 30))
            bar_gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 10))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(bar_gradient))
            painter.drawRoundedRect(bar_rect, 5, 5)

            painter.setPen(color)
            painter.drawText(panel_x + 60, y + 6, label)

            painter.setPen(QColor(240, 245, 255))
            count_str = str(count)
            painter.drawText(panel_x + panel_w - 60 - len(count_str) * 8, y + 6, count_str)

        # 连击和准确率
        font_info = create_font(14)
        painter.setFont(font_info)

        painter.setPen(QColor(255, 200, 100))
        painter.drawText(QRectF(panel_x, panel_y + 345, panel_w, 30),
                        Qt.AlignmentFlag.AlignCenter, f"🔥 Max Combo: {self._result.max_combo}")

        # 准确率条
        acc_width = panel_w - 100
        acc_height = 8
        acc_x = panel_x + 50
        acc_y = panel_y + 375
        acc = self._result.accuracy

        # 背景
        painter.fillRect(QRectF(acc_x, acc_y, acc_width, acc_height), QColor(40, 45, 60))

        # 进度
        acc_color = QColor(100, 255, 180) if acc >= 0.9 else QColor(100, 200, 255) if acc >= 0.7 else QColor(255, 180, 100)
        painter.fillRect(QRectF(acc_x, acc_y, int(acc_width * acc), acc_height), acc_color)

        painter.setPen(QColor(200, 210, 230))
        painter.drawText(QRectF(panel_x, panel_y + 380, panel_w, 30),
                        Qt.AlignmentFlag.AlignCenter, f"Accuracy: {acc * 100:.1f}%")

    def cleanup(self):
        """清理资源"""
        self._game_timer.stop()
        self._audio_manager.stop_music()

        if self._skin:
            self._skin.close()

    def get_result(self) -> Optional[GameResult]:
        """获取游戏结果"""
        return self._result
