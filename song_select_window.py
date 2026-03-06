# -*- coding: utf-8 -*-
"""
选歌预览界面（PyQt6版本）
实现iPhone 17高级玻璃拟态风格的选歌界面
"""

import math
from typing import List, Optional
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QScrollArea, QLineEdit
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    QRectF, QPointF, pyqtProperty, pyqtSignal
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient,
    QRadialGradient, QPainterPath, QPixmap, QFont
)

from config_manager import ConfigManager
from audio_manager import AudioManager, get_audio_manager
from directory_parser import SongInfo


class AdvancedColors:
    """高级玻璃配色方案"""
    # 背景
    BG_TOP = QColor(8, 8, 18)
    BG_BOTTOM = QColor(18, 28, 50)

    # 玻璃
    GLASS_BASE = QColor(30, 30, 50)
    GLASS_HIGHLIGHT = QColor(255, 255, 255)
    GLASS_BORDER = QColor(200, 200, 210)

    # 文字
    TEXT_WHITE = QColor(240, 240, 250)
    TEXT_GRAY = QColor(160, 160, 175)
    TEXT_DARK = QColor(100, 100, 120)

    # 发光色
    GLOW_BLUE = QColor(80, 160, 255)
    GLOW_PURPLE = QColor(160, 80, 255)
    GLOW_PINK = QColor(255, 80, 160)

    # 星级
    STAR_BLUE = QColor(80, 160, 255)
    STAR_PURPLE = QColor(160, 80, 255)
    STAR_RED = QColor(255, 80, 80)
    STAR_GOLD = QColor(255, 200, 50)


def create_font(size: int, bold: bool = False) -> QFont:
    """创建字体"""
    font = QFont()
    font.setPointSize(size)
    font.setBold(bold)

    import platform
    system = platform.system()
    if system == "Darwin":
        families = ["PingFang SC", "Heiti SC", "STHeiti"]
    elif system == "Windows":
        families = ["Microsoft YaHei", "SimHei"]
    else:
        families = ["WenQuanYi Micro Hei", "Noto Sans CJK SC"]

    for family in families:
        font.setFamily(family)
        break

    return font


class FrostedGlassPanel(QWidget):
    """磨砂玻璃面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._corner_radius = 16
        self._alpha = 120

    def set_corner_radius(self, radius: int):
        self._corner_radius = radius
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0, 0, self.width(), self.height())

        # 玻璃背景
        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0, QColor(40, 40, 60, self._alpha))
        gradient.setColorAt(1, QColor(30, 30, 50, self._alpha + 30))

        path = QPainterPath()
        path.addRoundedRect(rect, self._corner_radius, self._corner_radius)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawPath(path)

        # 边框
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)


class AdvancedSongCard(QWidget):
    """
    高级歌曲卡片组件
    带动态hover效果
    """

    song_clicked = pyqtSignal(object)
    song_hovered = pyqtSignal(object)
    song_unhovered = pyqtSignal(object)

    def __init__(self, song_info: SongInfo, parent=None):
        super().__init__(parent)
        self._song_info = song_info
        self._cover_pixmap: Optional[QPixmap] = None
        self._cover_loaded = False
        self._hover = False
        self._hover_progress = 0.0
        self._corner_radius = 20

        # 呼吸动画相位
        self._breath_phase = 0.0
        self._breath_timer = QTimer(self)
        self._breath_timer.timeout.connect(self._update_breath)
        self._breath_timer.start(30)  # ~33fps

        # hover动画
        self._hover_animation = QPropertyAnimation(self, b"hover_progress", self)
        self._hover_animation.setDuration(250)
        self._hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.setFixedSize(200, 280)
        self._cover_rect = QRectF(10, 10, 180, 180)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _update_breath(self):
        """更新呼吸动画"""
        if self._hover:
            self._breath_phase += 0.08
            if self._breath_phase > 2 * math.pi:
                self._breath_phase -= 2 * math.pi
            self.update()

    def get_hover_progress(self) -> float:
        return self._hover_progress

    def set_hover_progress(self, progress: float):
        self._hover_progress = progress
        self.update()

    hover_progress = pyqtProperty(float, get_hover_progress, set_hover_progress)

    def get_song_info(self) -> SongInfo:
        return self._song_info

    def load_cover(self):
        """加载封面图片"""
        if self._cover_loaded:
            return
        self._cover_loaded = True

        # 尝试加载封面
        if self._song_info.has_banner:
            self._load_cover_image(self._song_info.banner_file)

    def _load_cover_image(self, path: str):
        """加载封面图片"""
        try:
            from PIL import Image
            img = Image.open(path)

            # 裁剪到正方形
            size = min(img.width, img.height)
            left = (img.width - size) // 2
            top = (img.height - size) // 2
            img = img.crop((left, top, left + size, top + size))

            # 缩放
            img = img.resize((180, 180), Image.Resampling.LANCZOS)

            # 转换为QPixmap
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            data = img.tobytes("raw", "RGBA")
            from PyQt6.QtGui import QImage
            qimg = QImage(data, img.width, img.height, img.width * 4, QImage.Format.Format_RGBA8888)
            self._cover_pixmap = QPixmap.fromImage(qimg)
            self.update()

        except Exception as e:
            print(f"[SongCard] 加载封面失败: {e}")
            self._cover_pixmap = None

    def enterEvent(self, event):
        super().enterEvent(event)
        self._hover = True
        self._hover_animation.stop()
        self._hover_animation.setStartValue(self._hover_progress)
        self._hover_animation.setEndValue(1.0)
        self._hover_animation.start()
        self.song_hovered.emit(self._song_info)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hover = False
        self._hover_animation.stop()
        self._hover_animation.setStartValue(self._hover_progress)
        self._hover_animation.setEndValue(0.0)
        self._hover_animation.start()
        self.song_unhovered.emit(self._song_info)

    def paintEvent(self, event):
        """绘制卡片"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = QRectF(0, 0, self.width(), self.height())

        # hover缩放 - 更明显的缩放效果
        if self._hover_progress > 0:
            scale = 1.0 + 0.05 * self._hover_progress
            painter.translate(self.width() / 2, self.height() / 2)
            painter.scale(scale, scale)
            painter.translate(-self.width() / 2, -self.height() / 2)

        # 绘制动态阴影
        self._draw_shadow(painter, rect)

        # 绘制玻璃背景
        self._draw_glass(painter, rect)

        # 绘制封面
        self._draw_cover(painter)

        # 绘制歌曲信息
        self._draw_info(painter, rect)

        # 绘制星级
        self._draw_star_rating(painter, rect)

        # 绘制边框
        self._draw_border(painter, rect)

        # 绘制动态光晕
        self._draw_glow(painter, rect)

        # 绘制播放按钮覆盖层
        if self._hover_progress > 0.3:
            self._draw_play_overlay(painter)

    def _draw_shadow(self, painter: QPainter, rect: QRectF):
        """绘制动态阴影"""
        # hover时阴影更深更大
        shadow_scale = 1.0 + 0.3 * self._hover_progress
        base_alpha = 40 + int(25 * self._hover_progress)

        for i in range(4):
            offset = (i * 3 + 3) * shadow_scale
            alpha = base_alpha - i * 10
            if alpha <= 0:
                continue
            color = QColor(0, 0, 0, alpha)
            shadow_rect = QRectF(
                rect.x() + offset / 2,
                rect.y() + offset * 1.2,
                rect.width(),
                rect.height()
            )
            path = QPainterPath()
            path.addRoundedRect(shadow_rect, self._corner_radius, self._corner_radius)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawPath(path)

    def _draw_glass(self, painter: QPainter, rect: QRectF):
        """绘制玻璃背景"""
        alpha = 50 + int(40 * self._hover_progress)
        if self._hover:
            # hover时背景更亮
            fill_color = QColor(45, 50, 75, alpha)
        else:
            fill_color = QColor(30, 30, 50, alpha)

        path = QPainterPath()
        path.addRoundedRect(rect, self._corner_radius, self._corner_radius)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(fill_color))
        painter.drawPath(path)

        # 高光 - hover时更亮
        highlight_height = rect.height() * 0.35
        highlight_rect = QRectF(rect.x(), rect.y(), rect.width(), highlight_height)
        gradient = QLinearGradient(0, 0, 0, highlight_height)
        intensity = 0.12 + 0.15 * self._hover_progress
        gradient.setColorAt(0, QColor(255, 255, 255, int(255 * intensity)))
        gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(highlight_rect, QBrush(gradient))

    def _draw_border(self, painter: QPainter, rect: QRectF):
        """绘制动态边框"""
        if self._hover:
            # 呼吸发光边框
            breath = 0.5 + 0.5 * math.sin(self._breath_phase)
            r = int(200 + 55 * breath)
            g = int(180 + 40 * breath)
            b = int(80 + 30 * breath)
            border_color = QColor(r, g, b, int(200 + 55 * breath))
            border_width = 1.5 + 0.5 * breath
        else:
            border_color = QColor(200, 200, 210, 120)
            border_width = 1

        path = QPainterPath()
        path.addRoundedRect(rect, self._corner_radius, self._corner_radius)
        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    def _draw_glow(self, painter: QPainter, rect: QRectF):
        """绘制呼吸光晕"""
        if self._hover_progress < 0.1 and not self._hover:
            return

        # 呼吸效果
        breath = 0.6 + 0.4 * math.sin(self._breath_phase) if self._hover else 1.0
        glow_intensity = (0.4 + 0.4 * self._hover_progress) * breath
        glow_alpha = int(100 * glow_intensity)

        # 多层光晕
        colors = [
            QColor(80, 160, 255, glow_alpha),    # 蓝色
            QColor(120, 100, 255, glow_alpha // 2),  # 紫色
        ]

        for i, glow_color in enumerate(colors):
            alpha = glow_alpha // (i + 1)
            offset = (i + 1) * 3
            glow_color.setAlpha(alpha)

            glow_rect = QRectF(
                rect.x() - offset,
                rect.y() - offset,
                rect.width() + offset * 2,
                rect.height() + offset * 2
            )

            path = QPainterPath()
            path.addRoundedRect(glow_rect, self._corner_radius + offset, self._corner_radius + offset)
            painter.setPen(QPen(glow_color, 2 - i * 0.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

    def _draw_play_overlay(self, painter: QPainter):
        """绘制播放按钮覆盖层"""
        # 半透明黑色遮罩
        overlay_alpha = int(80 * self._hover_progress)
        overlay_rect = self._cover_rect

        painter.save()
        clip_path = QPainterPath()
        clip_path.addRoundedRect(overlay_rect, 12, 12)
        painter.setClipPath(clip_path)
        painter.fillRect(overlay_rect, QColor(0, 0, 0, overlay_alpha))

        # 播放按钮 - 呼吸缩放
        center_x = overlay_rect.center().x()
        center_y = overlay_rect.center().y()
        breath_scale = 1.0 + 0.1 * math.sin(self._breath_phase)
        radius = 30 * breath_scale

        # 播放按钮背景圆
        gradient = QRadialGradient(center_x, center_y, radius)
        btn_alpha = int(200 * self._hover_progress)
        gradient.setColorAt(0, QColor(80, 160, 255, btn_alpha))
        gradient.setColorAt(0.7, QColor(60, 120, 200, btn_alpha))
        gradient.setColorAt(1, QColor(40, 80, 160, btn_alpha))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(QPointF(center_x, center_y), radius, radius)

        # 播放三角形
        triangle_size = 12 * breath_scale
        triangle_points = [
            QPointF(center_x - triangle_size * 0.4, center_y - triangle_size),
            QPointF(center_x - triangle_size * 0.4, center_y + triangle_size),
            QPointF(center_x + triangle_size * 1.2, center_y),
        ]
        path = QPainterPath()
        path.moveTo(triangle_points[0])
        for pt in triangle_points[1:]:
            path.lineTo(pt)
        path.closeSubpath()

        painter.setBrush(QBrush(QColor(255, 255, 255, int(230 * self._hover_progress))))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)

        painter.restore()

    def _draw_cover(self, painter: QPainter):
        """绘制封面 - 带hover效果"""
        cover_rect = self._cover_rect

        # hover时封面轻微放大
        if self._hover_progress > 0:
            scale = 1.0 + 0.03 * self._hover_progress
            cx = cover_rect.center().x()
            cy = cover_rect.center().y()
            new_w = cover_rect.width() * scale
            new_h = cover_rect.height() * scale
            cover_rect = QRectF(cx - new_w/2, cy - new_h/2, new_w, new_h)

        # 保存 painter 状态
        painter.save()

        # 设置圆角裁剪路径
        clip_path = QPainterPath()
        clip_path.addRoundedRect(cover_rect, 12, 12)
        painter.setClipPath(clip_path)

        if self._cover_pixmap and not self._cover_pixmap.isNull():
            # 绘制封面图片
            painter.drawPixmap(cover_rect.toRect(), self._cover_pixmap)

            # hover时增加亮度
            if self._hover_progress > 0:
                brightness = int(30 * self._hover_progress)
                painter.fillRect(cover_rect, QColor(255, 255, 255, brightness))
        else:
            # 绘制占位图
            gradient = QLinearGradient(cover_rect.topLeft(), cover_rect.bottomRight())
            gradient.setColorAt(0, QColor(40, 40, 60))
            gradient.setColorAt(1, QColor(50, 50, 70))
            painter.fillRect(cover_rect, QBrush(gradient))

            # 绘制音符图标
            painter.setClipping(False)
            painter.setPen(QColor(80, 80, 100))
            painter.setFont(create_font(48))
            painter.drawText(cover_rect, Qt.AlignmentFlag.AlignCenter, "♪")

        # 恢复 painter 状态（取消裁剪）
        painter.restore()

        # 封面顶部反光
        highlight_rect = QRectF(cover_rect.x(), cover_rect.y(), cover_rect.width(), cover_rect.height() * 0.35)
        highlight_gradient = QLinearGradient(highlight_rect.topLeft(), highlight_rect.bottomLeft())
        highlight_intensity = 40 + int(30 * self._hover_progress)
        highlight_gradient.setColorAt(0, QColor(255, 255, 255, highlight_intensity))
        highlight_gradient.setColorAt(1, QColor(255, 255, 255, 0))

        painter.save()
        clip_path = QPainterPath()
        clip_path.addRoundedRect(cover_rect, 12, 12)
        painter.setClipPath(clip_path)
        painter.fillRect(highlight_rect, QBrush(highlight_gradient))
        painter.restore()

    def _draw_info(self, painter: QPainter, rect: QRectF):
        """绘制歌曲信息"""
        # 歌曲名称背景 - hover时更明显
        name_rect = QRectF(10, 195, 180, 40)
        bg_alpha = 60 + int(40 * self._hover_progress)
        painter.fillRect(name_rect, QColor(0, 0, 0, bg_alpha))

        # 名称文字 - hover时更亮
        text_alpha = 240 + int(15 * self._hover_progress)
        painter.setPen(QColor(240, 240, 250, text_alpha))
        font = create_font(12, bold=self._hover)
        painter.setFont(font)

        # 文字截断
        name = self._song_info.display_name
        metrics = painter.fontMetrics()
        elided_name = metrics.elidedText(name, Qt.TextElideMode.ElideRight, 170)
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, elided_name)

        # 无音频提示
        if not self._song_info.has_audio:
            painter.setPen(QColor(160, 160, 175, 200))
            painter.setFont(create_font(9))
            painter.drawText(QRectF(10, 235, 180, 15), Qt.AlignmentFlag.AlignCenter, "无音频")

    def _draw_star_rating(self, painter: QPainter, rect: QRectF):
        """绘制星级 - 带呼吸效果"""
        if self._song_info.star_rating is None:
            return

        stars = self._song_info.star_rating

        # 根据星级选择颜色
        if stars <= 5:
            base_color = AdvancedColors.STAR_BLUE
        elif stars <= 9:
            base_color = AdvancedColors.STAR_PURPLE
        else:
            base_color = AdvancedColors.STAR_RED

        # hover时呼吸效果
        breath = 1.0
        if self._hover:
            breath = 0.85 + 0.15 * math.sin(self._breath_phase * 2)

        # 绘制能量环
        center_x = rect.width() - 25
        center_y = 25
        radius = 18

        # 背景环
        bg_alpha = int(80 * breath)
        painter.setPen(QPen(QColor(60, 60, 80, bg_alpha), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(center_x, center_y), radius, radius)

        # 进度环
        progress = min(1.0, stars / 20.0)
        angle = int(360 * progress * 16)

        # 呼吸发光
        glow_alpha = int((180 + 75 * math.sin(self._breath_phase)) * breath) if self._hover else 200
        ring_color = QColor(base_color.red(), base_color.green(), base_color.blue(), glow_alpha)
        painter.setPen(QPen(ring_color, 3))
        painter.drawArc(
            int(center_x - radius), int(center_y - radius),
            int(radius * 2), int(radius * 2),
            90 * 16, -angle
        )

        # hover时外圈光晕
        if self._hover:
            glow_color = QColor(base_color.red(), base_color.green(), base_color.blue(), int(60 * breath))
            painter.setPen(QPen(glow_color, 6))
            painter.drawEllipse(QPointF(center_x, center_y), radius + 2, radius + 2)

        # 数字
        text_alpha = int((200 + 55 * breath) if self._hover else 240)
        painter.setPen(QColor(240, 240, 250, text_alpha))
        font = create_font(10, bold=True)
        painter.setFont(font)
        text_rect = QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, str(stars))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.song_clicked.emit(self._song_info)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        super().enterEvent(event)
        self._hover = True
        self._hover_animation.stop()
        self._hover_animation.setStartValue(self._hover_progress)
        self._hover_animation.setEndValue(1.0)
        self._hover_animation.start()
        self.song_hovered.emit(self._song_info)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hover = False
        self._hover_animation.stop()
        self._hover_animation.setStartValue(self._hover_progress)
        self._hover_animation.setEndValue(0.0)
        self._hover_animation.start()
        self.song_unhovered.emit(self._song_info)


class SongSelectWindow(QMainWindow):
    """高级选歌主窗口"""

    song_selected = pyqtSignal(object)

    def __init__(self, config: ConfigManager, audio_manager: AudioManager = None, parent=None):
        super().__init__(parent)
        self._config = config
        self._audio_manager = audio_manager or get_audio_manager()

        # 歌曲列表
        self._songs: List[SongInfo] = []
        self._filtered_songs: List[SongInfo] = []
        self._cards: List[AdvancedSongCard] = []

        # 分页 - 固定4列，根据高度自动计算行数
        self._current_page = 0
        self._items_per_page = 12
        self._columns = 4  # 固定4列
        self._rows = 3

        # 筛选
        self._search_text = ""
        self._star_filter_min: Optional[int] = None
        self._star_filter_max: Optional[int] = None

        # 预览
        self._previewing_song: Optional[SongInfo] = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._start_preview)

        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle("SM Arrow Player - 选歌")
        w, h = self._config.get_window_size()
        self.setMinimumSize(1000, 700)
        self.resize(w, h)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 顶部信息栏（包含星级筛选）
        self._header = self._create_header()
        main_layout.addWidget(self._header)

        # 卡片区域
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: rgba(20, 20, 35, 150);
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(100, 100, 120, 180);
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(120, 120, 140, 200);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self._card_container = QWidget()
        self._card_container.setStyleSheet("background: transparent;")
        self._card_layout = QGridLayout(self._card_container)
        self._card_layout.setSpacing(20)
        self._card_layout.setContentsMargins(30, 20, 30, 20)
        self._scroll_area.setWidget(self._card_container)
        main_layout.addWidget(self._scroll_area, 1)

        # 底部导航
        self._footer = self._create_footer()
        main_layout.addWidget(self._footer)

    def _create_header(self) -> QWidget:
        """创建顶部栏"""
        header = FrostedGlassPanel()
        header.set_corner_radius(0)
        header.setFixedHeight(100)

        main_layout = QVBoxLayout(header)
        main_layout.setContentsMargins(20, 8, 20, 8)
        main_layout.setSpacing(8)

        # 第一行：标题和歌曲数量
        row1 = QHBoxLayout()
        row1.setSpacing(15)

        # 标题
        title = QLabel("SM Arrow Player")
        title.setFont(create_font(20, bold=True))
        title.setStyleSheet("color: rgb(240, 240, 250); background: transparent;")
        row1.addWidget(title)

        # 歌曲数量
        self._count_label = QLabel("共 0 首")
        self._count_label.setFont(create_font(12))
        self._count_label.setStyleSheet("color: rgb(160, 160, 175); background: transparent;")
        row1.addWidget(self._count_label)

        row1.addStretch()

        # 页码
        self._page_label_header = QLabel("第 1 / 1 页")
        self._page_label_header.setFont(create_font(12))
        self._page_label_header.setStyleSheet("color: rgb(200, 200, 210); background: transparent;")
        row1.addWidget(self._page_label_header)

        main_layout.addLayout(row1)

        # 第二行：星级筛选按钮
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        # 星级筛选标签
        star_label = QLabel("星级:")
        star_label.setFont(create_font(11))
        star_label.setStyleSheet("color: rgb(160, 160, 175); background: transparent;")
        row2.addWidget(star_label)

        # 星级筛选按钮
        self._star_buttons = []
        star_ranges = [
            ("全部", None, None),
            ("1-3★", 1, 3),
            ("4-6★", 4, 6),
            ("7-9★", 7, 9),
            ("10-12★", 10, 12),
            ("13-15★", 13, 15),
            ("16+★", 16, None),
        ]

        for label, min_star, max_star in star_ranges:
            btn = QLabel(label)
            btn.setFont(create_font(11))
            btn.setFixedHeight(28)
            btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            btn.setStyleSheet("""
                QLabel {
                    background-color: rgba(40, 40, 60, 150);
                    border: 1px solid rgba(200, 200, 210, 80);
                    border-radius: 14px;
                    padding: 2px 12px;
                    color: rgb(180, 180, 190);
                }
                QLabel:hover {
                    background-color: rgba(60, 80, 120, 180);
                    border-color: rgba(100, 160, 255, 180);
                    color: rgb(240, 240, 250);
                }
            """)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.min_star = min_star
            btn.max_star = max_star
            btn.mousePressEvent = lambda e, btn=btn: self._on_star_click(btn)
            row2.addWidget(btn)
            self._star_buttons.append(btn)

        row2.addStretch()

        # 搜索框
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索歌曲...")
        self._search_input.setFixedWidth(180)
        self._search_input.setFixedHeight(28)
        self._search_input.setFont(create_font(11))
        self._search_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(40, 40, 60, 150);
                border: 1px solid rgba(200, 200, 210, 80);
                border-radius: 14px;
                padding: 0 12px;
                color: rgb(200, 200, 210);
            }
            QLineEdit:focus {
                border-color: rgba(80, 160, 255, 200);
                background-color: rgba(50, 50, 70, 180);
            }
            QLineEdit::placeholder {
                color: rgba(140, 140, 155, 180);
            }
        """)
        self._search_input.textChanged.connect(self._on_search_changed)
        row2.addWidget(self._search_input)

        main_layout.addLayout(row2)

        return header

    def _on_star_click(self, btn):
        """星级筛选点击"""
        # 重置所有按钮样式
        for b in self._star_buttons:
            b.setStyleSheet("""
                QLabel {
                    background-color: rgba(40, 40, 60, 150);
                    border: 1px solid rgba(200, 200, 210, 80);
                    border-radius: 14px;
                    padding: 2px 12px;
                    color: rgb(180, 180, 190);
                }
                QLabel:hover {
                    background-color: rgba(60, 80, 120, 180);
                    border-color: rgba(100, 160, 255, 180);
                    color: rgb(240, 240, 250);
                }
            """)

        # 高亮选中按钮
        btn.setStyleSheet("""
            QLabel {
                background-color: rgba(80, 140, 220, 200);
                border: 1px solid rgba(100, 180, 255, 220);
                border-radius: 14px;
                padding: 2px 12px;
                color: rgb(255, 255, 255);
            }
        """)

        # 应用筛选
        min_star = btn.min_star if btn.min_star else -1
        max_star = btn.max_star if btn.max_star else -1
        self._star_filter_min = min_star if min_star >= 0 else None
        self._star_filter_max = max_star if max_star >= 0 else None
        self._apply_filter()

    def _create_footer(self) -> QWidget:
        """创建底部导航"""
        footer = FrostedGlassPanel()
        footer.set_corner_radius(0)
        footer.setFixedHeight(60)

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(30, 15, 30, 15)

        # 上一页
        prev_label = QLabel("◀ 上一页")
        prev_label.setFont(create_font(13))
        prev_label.setStyleSheet("""
            QLabel {
                background-color: rgba(40, 40, 60, 120);
                border: 1px solid rgba(200, 200, 210, 100);
                border-radius: 15px;
                padding: 8px 20px;
                color: rgb(180, 180, 190);
            }
            QLabel:hover {
                background-color: rgba(50, 50, 70, 150);
                border-color: rgb(220, 200, 100);
                color: rgb(240, 240, 250);
            }
        """)
        prev_label.setCursor(Qt.CursorShape.PointingHandCursor)
        prev_label.mousePressEvent = lambda e: self._prev_page()
        layout.addWidget(prev_label)
        self._prev_label = prev_label

        layout.addStretch()

        # 页码
        self._page_label = QLabel("第 1 / 1 页")
        self._page_label.setFont(create_font(14))
        self._page_label.setStyleSheet("color: rgb(240, 240, 250); background: transparent;")
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._page_label)

        layout.addStretch()

        # 下一页
        next_label = QLabel("下一页 ▶")
        next_label.setFont(create_font(13))
        next_label.setStyleSheet("""
            QLabel {
                background-color: rgba(40, 40, 60, 120);
                border: 1px solid rgba(200, 200, 210, 100);
                border-radius: 15px;
                padding: 8px 20px;
                color: rgb(180, 180, 190);
            }
            QLabel:hover {
                background-color: rgba(50, 50, 70, 150);
                border-color: rgb(220, 200, 100);
                color: rgb(240, 240, 250);
            }
        """)
        next_label.setCursor(Qt.CursorShape.PointingHandCursor)
        next_label.mousePressEvent = lambda e: self._next_page()
        layout.addWidget(next_label)
        self._next_label = next_label

        return footer

    def load_songs(self, songs: List[SongInfo]):
        """加载歌曲列表"""
        self._songs = songs
        self._filtered_songs = songs.copy()
        self._current_page = 0

        last_page = self._config.get_last_page()
        if last_page > 0:
            total_pages = max(1, (len(self._filtered_songs) + self._items_per_page - 1) // self._items_per_page)
            self._current_page = min(last_page, total_pages - 1)

        self._update_layout()
        self._update_cards()

    def _update_layout(self):
        """更新布局 - 固定4列"""
        self._columns = 4
        # 根据窗口高度计算行数
        h = self.height()
        if h >= 900:
            self._rows = 4
        elif h >= 750:
            self._rows = 3
        else:
            self._rows = 2
        self._items_per_page = self._columns * self._rows

    def _update_cards(self):
        """更新卡片显示"""
        # 清除旧卡片
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()

        # 当前页歌曲
        start_idx = self._current_page * self._items_per_page
        end_idx = min(start_idx + self._items_per_page, len(self._filtered_songs))
        page_songs = self._filtered_songs[start_idx:end_idx]

        # 创建卡片
        for i, song in enumerate(page_songs):
            row = i // self._columns
            col = i % self._columns

            card = AdvancedSongCard(song)
            card.song_clicked.connect(self._on_song_clicked)
            card.song_hovered.connect(self._on_song_hovered)
            card.song_unhovered.connect(self._on_song_unhovered)
            card.load_cover()  # 加载封面

            self._card_layout.addWidget(card, row, col, Qt.AlignmentFlag.AlignCenter)
            self._cards.append(card)

        # 更新页码
        total_pages = max(1, (len(self._filtered_songs) + self._items_per_page - 1) // self._items_per_page)
        self._page_label.setText(f"第 {self._current_page + 1} / {total_pages} 页")
        self._page_label_header.setText(f"第 {self._current_page + 1} / {total_pages} 页")
        self._count_label.setText(f"共 {len(self._filtered_songs)} 首")

    def _on_song_clicked(self, song: SongInfo):
        if not song.has_sm:
            return
        self._stop_preview()
        self._config.set_last_sm_file(song.sm_file)
        self._config.set_last_page(self._current_page)
        self._config.save()
        self.song_selected.emit(song)

    def _on_song_hovered(self, song: SongInfo):
        self._previewing_song = song
        preview_delay = self._config.get("preview_delay", 0.5)
        self._preview_timer.start(int(preview_delay * 1000))

    def _on_song_unhovered(self, song: SongInfo):
        if self._previewing_song == song:
            self._stop_preview()

    def _start_preview(self):
        if not self._previewing_song:
            return
        song = self._previewing_song
        if song.has_audio:
            preview_duration = self._config.get("preview_duration", 10)
            self._audio_manager.start_preview(song.audio_file, duration=preview_duration)

    def _stop_preview(self):
        self._preview_timer.stop()
        self._audio_manager.stop_preview()
        self._previewing_song = None

    def _prev_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._stop_preview()
            self._update_cards()
            self._config.set_last_page(self._current_page)

    def _next_page(self):
        total_pages = max(1, (len(self._filtered_songs) + self._items_per_page - 1) // self._items_per_page)
        if self._current_page < total_pages - 1:
            self._current_page += 1
            self._stop_preview()
            self._update_cards()
            self._config.set_last_page(self._current_page)

    def _on_search_changed(self, text: str):
        self._search_text = text
        self._apply_filter()

    def _apply_filter(self):
        filtered = self._songs.copy()

        if self._search_text:
            filtered = [
                s for s in filtered
                if self._search_text in s.display_name.lower()
                or self._search_text in s.folder_name.lower()
            ]

        if self._star_filter_min is not None or self._star_filter_max is not None:
            result = []
            for song in filtered:
                if song.star_rating is None:
                    continue
                if self._star_filter_min is not None and song.star_rating < self._star_filter_min:
                    continue
                if self._star_filter_max is not None and song.star_rating > self._star_filter_max:
                    continue
                result.append(song)
            filtered = result

        self._filtered_songs = filtered
        self._current_page = 0
        self._update_cards()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Left:
            self._prev_page()
        elif key == Qt.Key.Key_Right:
            self._next_page()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_layout()
        self._update_cards()
        self._config.set_window_size(self.width(), self.height(), auto_save=False)

    def cleanup(self):
        self._stop_preview()
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()

    def paintEvent(self, event):
        """绘制背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0, 0, self.width(), self.height())

        # 渐变背景
        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0, AdvancedColors.BG_TOP)
        gradient.setColorAt(1, AdvancedColors.BG_BOTTOM)
        painter.fillRect(rect, QBrush(gradient))

        # 霓虹网格
        self._draw_neon_grid(painter, rect)

    def _draw_neon_grid(self, painter: QPainter, rect: QRectF):
        """绘制霓虹网格"""
        grid_size = 80
        color = QColor(40, 60, 100, 25)
        painter.setPen(QPen(color, 1))

        x = 0
        while x < rect.width():
            painter.drawLine(int(x), 0, int(x), int(rect.height()))
            x += grid_size

        y = 0
        while y < rect.height():
            painter.drawLine(0, int(y), int(rect.width()), int(y))
            y += grid_size
