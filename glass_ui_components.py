# -*- coding: utf-8 -*-
"""
玻璃拟态UI组件库（PyQt6版本）
实现iPhone 17风格的玻璃拟态视觉效果
"""

import math
from typing import List, Optional, Tuple
from PyQt6.QtWidgets import (
    QWidget, QFrame, QPushButton, QLabel, QProgressBar,
    QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QPoint, QSize,
    QEasingCurve, pyqtProperty, pyqtSignal, QRectF
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient,
    QRadialGradient, QPainterPath, QFont, QPixmap, QFontMetrics
)


class GlassColors:
    """玻璃拟态颜色方案"""

    # 背景色
    BG_TOP = QColor(12, 12, 25)
    BG_BOTTOM = QColor(25, 35, 60)

    # 玻璃卡片
    GLASS_FILL = QColor(30, 30, 50, 77)
    GLASS_BORDER = QColor(200, 200, 210, 200)
    GLASS_BORDER_HOVER = QColor(220, 200, 100)

    # 霓虹网格
    GRID_COLOR = QColor(40, 80, 150, 20)

    # 星级颜色
    STAR_BLUE = QColor(100, 180, 255)
    STAR_PURPLE = QColor(180, 100, 255)
    STAR_RED = QColor(255, 100, 100)
    STAR_GOLD = QColor(255, 220, 50)

    # 文字颜色
    TEXT_WHITE = QColor(240, 240, 250)
    TEXT_GRAY = QColor(180, 180, 190)
    TEXT_DARK = QColor(100, 100, 120)

    # 频谱颜色
    SPECTRUM_COLORS = [
        QColor(100, 180, 255),   # 蓝
        QColor(150, 100, 255),   # 紫
        QColor(255, 100, 150),   # 粉
        QColor(255, 150, 50),    # 橙
        QColor(100, 255, 150),   # 绿
    ]

    # 判定颜色
    PERFECT = QColor(50, 255, 100)
    GOOD = QColor(255, 220, 50)
    BAD = QColor(255, 80, 80)
    MISS = QColor(150, 150, 150)


class GlassCard(QFrame):
    """
    玻璃风格卡片组件

    特性：
    - 半透明背景 rgba(30,30,50,0.3)
    - 16px圆角
    - 哑光银边框
    - 悬停动画效果
    """

    clicked = pyqtSignal()
    hovered = pyqtSignal()
    unhovered = pyqtSignal()

    def __init__(self, parent=None, corner_radius: int = 16):
        super().__init__(parent)
        self._corner_radius = corner_radius
        self._alpha = 77
        self._hover = False
        self._scale = 1.0

        # 启用鼠标跟踪
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 设置大小策略
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # 动画
        self._scale_animation = QPropertyAnimation(self, b"scale", self)
        self._scale_animation.setDuration(150)
        self._scale_animation.setEasingCurve(QEasingCurve.Type.OutQuad)

    def get_corner_radius(self) -> int:
        return self._corner_radius

    def set_corner_radius(self, radius: int):
        self._corner_radius = radius
        self.update()

    def get_alpha(self) -> int:
        return self._alpha

    def set_alpha(self, alpha: int):
        self._alpha = alpha
        self.update()

    def is_hover(self) -> bool:
        return self._hover

    def set_hover(self, hover: bool):
        if self._hover != hover:
            self._hover = hover
            if hover:
                self.hovered.emit()
            else:
                self.unhovered.emit()
            self.update()

    def get_scale(self) -> float:
        return self._scale

    def set_scale(self, scale: float):
        self._scale = scale
        self.update()

    scale = pyqtProperty(float, get_scale, set_scale)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.set_hover(True)
        self._animate_scale(1.03)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.set_hover(False)
        self._animate_scale(1.0)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._animate_scale(0.97)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._hover:
                self.clicked.emit()
            self._animate_scale(1.03 if self._hover else 1.0)
        super().mouseReleaseEvent(event)

    def _animate_scale(self, target: float):
        """缩放动画"""
        self._scale_animation.stop()
        self._scale_animation.setStartValue(self._scale)
        self._scale_animation.setEndValue(target)
        self._scale_animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 计算缩放后的矩形
        w = self.width()
        h = self.height()
        scale = self._scale
        sw = w * scale
        sh = h * scale
        ox = (w - sw) / 2
        oy = (h - sh) / 2

        rect = QRectF(ox, oy, sw, sh)

        # 绘制背景
        alpha = min(255, self._alpha + 30) if self._hover else self._alpha
        fill_color = QColor(30, 30, 50, alpha) if not self._hover else QColor(40, 40, 60, alpha)
        painter.setBrush(QBrush(fill_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, self._corner_radius, self._corner_radius)

        # 绘制边框
        border_color = GlassColors.GLASS_BORDER_HOVER if self._hover else GlassColors.GLASS_BORDER
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border_color, 0.8))
        painter.drawRoundedRect(rect, self._corner_radius, self._corner_radius)

        # 绘制顶部高光
        highlight_rect = QRectF(ox, oy, sw, sh * 0.25)
        highlight_gradient = QLinearGradient(ox, oy, ox, oy + sh * 0.25)
        highlight_gradient.setColorAt(0, QColor(255, 255, 255, 20))
        highlight_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(highlight_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(highlight_rect, self._corner_radius, self._corner_radius)


class GlassButton(QPushButton):
    """
    玻璃风格按钮组件

    特性：
    - 胶囊形圆角
    - 悬停变金色边框
    - 点击缩放动画
    """

    def __init__(self, text: str = "", parent=None, corner_radius: int = 12):
        super().__init__(text, parent)
        self._corner_radius = corner_radius
        self._alpha = 50
        self._hover = False
        self._active = False

        # 设置样式
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def get_corner_radius(self) -> int:
        return self._corner_radius

    def set_corner_radius(self, radius: int):
        self._corner_radius = radius
        self.update()

    def get_active(self) -> bool:
        return self._active

    def set_active(self, active: bool):
        self._active = active
        self.update()

    active = pyqtProperty(bool, get_active, set_active)

    def enterEvent(self, event):
        super().enterEvent(event)
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hover = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0, 0, self.width(), self.height())

        # 背景颜色
        if self._active:
            fill_color = QColor(60, 100, 180, self._alpha + 30)
        elif self._hover:
            fill_color = QColor(50, 50, 70, self._alpha + 20)
        else:
            fill_color = QColor(40, 40, 60, self._alpha)

        painter.setBrush(QBrush(fill_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, self._corner_radius, self._corner_radius)

        # 边框
        border_color = GlassColors.GLASS_BORDER_HOVER if self._hover or self._active else GlassColors.GLASS_BORDER
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(rect, self._corner_radius, self._corner_radius)

        # 文字
        text_color = GlassColors.TEXT_WHITE if self._hover or self._active else GlassColors.TEXT_GRAY
        painter.setPen(text_color)
        painter.setFont(self.font())
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text())


class EnergyRing(QWidget):
    """
    能量环星级显示组件

    特性：
    - 环形进度条样式
    - 颜色按星级变化
    - hover脉动动画
    """

    def __init__(self, stars: int = 1, parent=None):
        super().__init__(parent)
        self._stars = stars
        self._progress = 1.0
        self._pulse = 0.0
        self._hover = False

        # 脉动动画
        self._pulse_animation = QPropertyAnimation(self, b"pulse", self)
        self._pulse_animation.setDuration(150)
        self._pulse_animation.setEasingCurve(QEasingCurve.Type.OutQuad)

        # 设置固定大小
        self.setFixedSize(50, 50)

    def get_stars(self) -> int:
        return self._stars

    def set_stars(self, stars: int):
        self._stars = max(1, min(20, stars))
        self.update()

    def get_pulse(self) -> float:
        return self._pulse

    def set_pulse(self, pulse: float):
        self._pulse = pulse
        self.update()

    pulse = pyqtProperty(float, get_pulse, set_pulse)

    def enterEvent(self, event):
        super().enterEvent(event)
        self._hover = True
        self._pulse_animation.stop()
        self._pulse_animation.setStartValue(self._pulse)
        self._pulse_animation.setEndValue(0.2)
        self._pulse_animation.start()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hover = False
        self._pulse_animation.stop()
        self._pulse_animation.setStartValue(self._pulse)
        self._pulse_animation.setEndValue(0.0)
        self._pulse_animation.start()

    def _get_ring_color(self) -> QColor:
        """根据星级获取颜色"""
        if self._stars <= 5:
            return GlassColors.STAR_BLUE
        elif self._stars <= 9:
            return GlassColors.STAR_PURPLE
        else:
            return GlassColors.STAR_RED

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 尺寸
        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h / 2
        radius = min(w, h) / 2 - 5
        pen_width = 3

        # 背景环
        painter.setPen(QPen(QColor(60, 60, 80), pen_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPoint(int(cx), int(cy)), int(radius), int(radius))

        # 进度环
        ring_color = self._get_ring_color()
        if self._hover:
            ring_color = QColor(
                min(255, ring_color.red() + int(50 * self._pulse)),
                min(255, ring_color.green() + int(50 * self._pulse)),
                min(255, ring_color.blue() + int(50 * self._pulse))
            )

        # 计算进度（星级映射到进度，最高20星）
        progress = min(1.0, self._stars / 20.0)
        angle = int(360 * progress * 16)  # Qt用1/16度

        pen = QPen(ring_color, pen_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(
            int(cx - radius), int(cy - radius),
            int(radius * 2), int(radius * 2),
            90 * 16, -angle  # 从顶部开始
        )

        # 中心数字
        painter.setPen(GlassColors.TEXT_WHITE)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        text_rect = QRectF(0, 0, w, h)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, str(self._stars))


class GlassFilterBar(QWidget):
    """
    玻璃风格筛选栏

    特性：
    - 磨砂玻璃背景
    - 星级筛选按钮组
    - 搜索框
    """

    filterChanged = pyqtSignal(int, int)  # (min_star, max_star)
    searchChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._visible = True
        self._star_filter_min: Optional[int] = None
        self._star_filter_max: Optional[int] = None
        self._search_text = ""

        self._setup_ui()

    def _setup_ui(self):
        # 设置固定高度
        self.setFixedHeight(50)

        # 创建布局
        from PyQt6.QtWidgets import QHBoxLayout, QLineEdit
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 5, 20, 5)
        layout.setSpacing(10)

        # 星级筛选按钮
        self._star_buttons = []
        star_ranges = [
            ("全部", None, None),
            ("1-5★", 1, 5),
            ("6-9★", 6, 9),
            ("10+★", 10, None),
        ]

        for label, min_star, max_star in star_ranges:
            btn = GlassButton(label, corner_radius=15)
            btn.setFixedHeight(30)
            btn.setFixedWidth(70)
            btn.clicked.connect(lambda checked, mn=min_star, mx=max_star: self._on_star_filter(mn, mx))
            layout.addWidget(btn)
            self._star_buttons.append((btn, min_star, max_star))

        # 弹性空间
        layout.addStretch()

        # 搜索框
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索歌曲...")
        self._search_input.setFixedWidth(200)
        self._search_input.setFixedHeight(30)
        self._search_input.textChanged.connect(self._on_search_changed)
        self._style_search_input()
        layout.addWidget(self._search_input)

    def _style_search_input(self):
        """设置搜索框样式"""
        self._search_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(40, 40, 60, 100);
                border: 1px solid rgba(200, 200, 210, 180);
                border-radius: 15px;
                padding: 0 10px;
                color: rgb(180, 180, 190);
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: rgb(220, 200, 100);
            }
        """)

    def _on_star_filter(self, min_star: Optional[int], max_star: Optional[int]):
        """星级筛选按钮点击"""
        # 更新按钮状态
        for btn, mn, mx in self._star_buttons:
            btn.set_active(mn == min_star and mx == max_star)

        self._star_filter_min = min_star
        self._star_filter_max = max_star
        self.filterChanged.emit(min_star if min_star else -1, max_star if max_star else -1)

    def _on_search_changed(self, text: str):
        """搜索文本改变"""
        self._search_text = text
        self.searchChanged.emit(text)

    def toggle_visible(self):
        """切换可见性"""
        self._visible = not self._visible
        self.setVisible(self._visible)

    def is_filter_bar_visible(self) -> bool:
        return self._visible

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0, 0, self.width(), self.height())

        # 磨砂玻璃背景
        painter.setBrush(QBrush(QColor(40, 40, 60, 128)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)


class SpectrumWidget(QWidget):
    """
    频谱可视化组件

    特性：
    - 实时更新频谱条
    - 渐变颜色
    """

    def __init__(self, bar_count: int = 32, parent=None):
        super().__init__(parent)
        self._bar_count = bar_count
        self._bars = [0.0] * bar_count
        self.setFixedHeight(80)

    def set_bars(self, bars: List[float]):
        """设置频谱数据"""
        self._bars = bars[:self._bar_count]
        if len(self._bars) < self._bar_count:
            self._bars.extend([0.0] * (self._bar_count - len(self._bars)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        bar_gap = 3
        bar_width = (w - bar_gap * (self._bar_count - 1)) // self._bar_count

        for i, value in enumerate(self._bars):
            # 限制值范围
            value = max(0.0, min(1.0, value))

            # 计算柱子位置和高度
            bar_height = int(value * (h - 10))
            x = i * (bar_width + bar_gap)
            y = h - bar_height

            # 选择颜色
            color_idx = i % len(GlassColors.SPECTRUM_COLORS)
            color = GlassColors.SPECTRUM_COLORS[color_idx]

            # 绘制渐变柱子
            gradient = QLinearGradient(x, y, x, h)
            gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 255))
            gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 100))

            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(x, y, bar_width, bar_height)


class GlassPanel(QWidget):
    """玻璃风格面板"""

    def __init__(self, parent=None, corner_radius: int = 20, alpha: int = 40):
        super().__init__(parent)
        self._corner_radius = corner_radius
        self._alpha = alpha

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0, 0, self.width(), self.height())

        # 填充
        painter.setBrush(QBrush(QColor(255, 255, 255, self._alpha)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, self._corner_radius, self._corner_radius)

        # 边框
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
        painter.drawRoundedRect(rect, self._corner_radius, self._corner_radius)


class StarRating(QWidget):
    """星级显示（星星形式）"""

    def __init__(self, stars: int = 1, size: int = 12, parent=None):
        super().__init__(parent)
        self._stars = stars
        self._size = size
        self._animation_progress = 1.0

        # 计算所需大小
        max_stars = min(10, max(1, stars))
        total_width = max_stars * (size + 2)
        self.setFixedSize(total_width + 10, size + 10)

    def set_stars(self, stars: int):
        self._stars = stars
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 限制最多显示10颗星
        display_stars = min(10, max(1, self._stars))
        size = self._size
        gap = size + 2
        start_x = 5
        cy = self.height() / 2

        for i in range(display_stars):
            sx = start_x + i * gap
            alpha = int(255 * self._animation_progress)
            self._draw_star(painter, sx, cy, size, alpha)

    def _draw_star(self, painter: QPainter, cx: float, cy: float, size: int, alpha: int):
        """绘制五角星"""
        color = QColor(GlassColors.STAR_GOLD)
        color.setAlpha(alpha)

        points = []
        for i in range(5):
            # 外顶点
            angle = math.radians(i * 72 - 90)
            px = cx + size * math.cos(angle)
            py = cy + size * math.sin(angle)
            points.append(QPoint(int(px), int(py)))

            # 内顶点
            angle = math.radians(i * 72 - 90 + 36)
            px = cx + size * 0.4 * math.cos(angle)
            py = cy + size * 0.4 * math.sin(angle)
            points.append(QPoint(int(px), int(py)))

        path = QPainterPath()
        path.moveTo(points[0])
        for p in points[1:]:
            path.lineTo(p)
        path.closeSubpath()

        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)


class GlassTooltip(QLabel):
    """玻璃风格提示框"""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            QLabel {
                background-color: rgba(40, 40, 60, 230);
                border: 1px solid rgba(100, 100, 120, 150);
                border-radius: 8px;
                padding: 5px 10px;
                color: rgb(180, 180, 190);
                font-size: 12px;
            }
        """)
        self.setWindowFlags(Qt.WindowType.ToolTip)


def create_font(size: int, bold: bool = False) -> QFont:
    """
    创建字体

    Args:
        size: 字体大小
        bold: 是否粗体

    Returns:
        QFont对象
    """
    font = QFont()
    font.setPointSize(size)
    font.setBold(bold)

    # 尝试设置中文字体
    import platform
    system = platform.system()

    if system == "Darwin":  # macOS
        font_families = ["PingFang SC", "Heiti SC", "STHeiti", "Hiragino Sans GB"]
    elif system == "Windows":
        font_families = ["Microsoft YaHei", "SimHei", "STHeiti"]
    else:  # Linux
        font_families = ["WenQuanYi Micro Hei", "Noto Sans CJK SC", "Droid Sans Fallback"]

    for family in font_families:
        font.setFamily(family)
        if QFontMetrics(font).inFont('中'):
            break

    return font


def draw_gradient_background(painter: QPainter, rect: QRectF,
                             top_color: QColor = None, bottom_color: QColor = None):
    """
    绘制垂直渐变背景

    Args:
        painter: QPainter对象
        rect: 绘制区域
        top_color: 顶部颜色
        bottom_color: 底部颜色
    """
    top_color = top_color or GlassColors.BG_TOP
    bottom_color = bottom_color or GlassColors.BG_BOTTOM

    gradient = QLinearGradient(0, 0, 0, rect.height())
    gradient.setColorAt(0, top_color)
    gradient.setColorAt(1, bottom_color)

    painter.fillRect(rect, QBrush(gradient))


def draw_neon_grid(painter: QPainter, rect: QRectF, grid_size: int = 60,
                   color: QColor = None):
    """
    绘制霓虹网格纹理

    Args:
        painter: QPainter对象
        rect: 绘制区域
        grid_size: 网格大小
        color: 网格颜色
    """
    color = color or GlassColors.GRID_COLOR
    pen = QPen(color, 1)
    painter.setPen(pen)

    # 垂直线
    x = 0
    while x < rect.width():
        painter.drawLine(int(x), 0, int(x), int(rect.height()))
        x += grid_size

    # 水平线
    y = 0
    while y < rect.height():
        painter.drawLine(0, int(y), int(rect.width()), int(y))
        y += grid_size
