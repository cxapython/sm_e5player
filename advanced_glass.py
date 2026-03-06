# -*- coding: utf-8 -*-
"""
高级毛玻璃效果模块（PyQt6版本）
简化版，避免复杂的模糊效果导致崩溃
"""

import math
from typing import Optional
from PyQt6.QtWidgets import QWidget, QGraphicsBlurEffect
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QRectF, QPointF, pyqtProperty, QEasingCurve
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient,
    QPainterPath, QPixmap, QFont
)


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


class DynamicBlurCard(QWidget):
    """
    动态玻璃卡片（简化版）
    支持hover动画效果
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # 玻璃参数
        self._corner_radius = 16
        self._glass_alpha = 60
        self._hover = False
        self._hover_progress = 0.0
        self._glow_enabled = True

        # 动画
        self._hover_animation = QPropertyAnimation(self, b"hover_progress", self)
        self._hover_animation.setDuration(200)
        self._hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.setMouseTracking(True)

    def get_hover_progress(self) -> float:
        return self._hover_progress

    def set_hover_progress(self, progress: float):
        self._hover_progress = progress
        self.update()

    hover_progress = pyqtProperty(float, get_hover_progress, set_hover_progress)

    def set_corner_radius(self, radius: int):
        self._corner_radius = radius
        self.update()

    def set_glass_alpha(self, alpha: int):
        self._glass_alpha = alpha
        self.update()

    def set_glow_enabled(self, enabled: bool):
        self._glow_enabled = enabled
        self.update()

    def enterEvent(self, event):
        super().enterEvent(event)
        self._hover = True
        self._hover_animation.stop()
        self._hover_animation.setStartValue(self._hover_progress)
        self._hover_animation.setEndValue(1.0)
        self._hover_animation.start()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hover = False
        self._hover_animation.stop()
        self._hover_animation.setStartValue(self._hover_progress)
        self._hover_animation.setEndValue(0.0)
        self._hover_animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0, 0, self.width(), self.height())

        # hover缩放
        if self._hover_progress > 0:
            scale = 1.0 + 0.02 * self._hover_progress
            painter.translate(self.width() / 2, self.height() / 2)
            painter.scale(scale, scale)
            painter.translate(-self.width() / 2, -self.height() / 2)

        # 阴影
        self._draw_shadow(painter, rect)

        # 玻璃背景
        self._draw_glass(painter, rect)

        # 高光
        self._draw_highlight(painter, rect)

        # 边框
        self._draw_border(painter, rect)

        # 光晕
        if self._glow_enabled:
            self._draw_glow(painter, rect)

    def _draw_shadow(self, painter: QPainter, rect: QRectF):
        """绘制阴影"""
        shadow_color = QColor(0, 0, 0, 40 + int(30 * self._hover_progress))
        for i in range(3):
            offset = i * 3 + 3
            alpha = 40 - i * 10
            color = QColor(0, 0, 0, alpha)
            shadow_rect = QRectF(
                rect.x() + offset // 2,
                rect.y() + offset,
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
        alpha = self._glass_alpha + int(30 * self._hover_progress)
        if self._hover:
            fill_color = QColor(40, 40, 60, alpha)
        else:
            fill_color = QColor(30, 30, 50, alpha)

        path = QPainterPath()
        path.addRoundedRect(rect, self._corner_radius, self._corner_radius)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(fill_color))
        painter.drawPath(path)

    def _draw_highlight(self, painter: QPainter, rect: QRectF):
        """绘制高光"""
        highlight_height = rect.height() * 0.3
        highlight_rect = QRectF(rect.x(), rect.y(), rect.width(), highlight_height)

        gradient = QLinearGradient(0, 0, 0, highlight_height)
        intensity = 0.15 + 0.1 * self._hover_progress
        gradient.setColorAt(0, QColor(255, 255, 255, int(255 * intensity)))
        gradient.setColorAt(1, QColor(255, 255, 255, 0))

        painter.fillRect(highlight_rect, QBrush(gradient))

    def _draw_border(self, painter: QPainter, rect: QRectF):
        """绘制边框"""
        if self._hover:
            border_color = QColor(220, 200, 100, 200)
        else:
            border_color = QColor(200, 200, 210, 150)

        path = QPainterPath()
        path.addRoundedRect(rect, self._corner_radius, self._corner_radius)
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    def _draw_glow(self, painter: QPainter, rect: QRectF):
        """绘制光晕"""
        # 只在hover时显示光晕
        if not self._hover and self._hover_progress < 0.1:
            return

        glow_intensity = 0.3 + 0.4 * self._hover_progress
        glow_alpha = int(80 * glow_intensity)

        glow_color = QColor(80, 160, 255, glow_alpha)

        for i in range(3):
            alpha = glow_alpha // (i + 1)
            offset = i * 2
            glow_color.setAlpha(alpha)

            glow_rect = QRectF(
                rect.x() - offset,
                rect.y() - offset,
                rect.width() + offset * 2,
                rect.height() + offset * 2
            )

            path = QPainterPath()
            path.addRoundedRect(glow_rect, self._corner_radius + offset, self._corner_radius + offset)

            painter.setPen(QPen(glow_color, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)


class MultiLayerGlassWidget(DynamicBlurCard):
    """多层玻璃组件（继承动态卡片）"""
    pass


class FrostedGlassPanel(QWidget):
    """
    磨砂玻璃面板（简化版）
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._corner_radius = 16
        self._alpha = 120

    def set_corner_radius(self, radius: int):
        self._corner_radius = radius
        self.update()

    def set_blur_strength(self, strength: int):
        pass  # 简化版不使用模糊

    def set_tint_color(self, color: QColor):
        pass  # 简化版

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


def draw_glass_shadow(painter: QPainter, rect: QRectF, radius: int = 16,
                      shadow_offset: tuple = (0, 4), shadow_radius: int = 20,
                      shadow_color: QColor = None):
    """绘制玻璃阴影"""
    if shadow_color is None:
        shadow_color = QColor(0, 0, 0, 60)

    for i in range(4):
        alpha = int(shadow_color.alpha() * (1 - i / 4))
        offset = i * 2 + 2
        color = QColor(shadow_color.red(), shadow_color.green(), shadow_color.blue(), alpha)

        shadow_rect = QRectF(
            rect.x() + shadow_offset[0] - offset // 2,
            rect.y() + shadow_offset[1] - offset // 2,
            rect.width() + offset,
            rect.height() + offset
        )

        path = QPainterPath()
        path.addRoundedRect(shadow_rect, radius + offset, radius + offset)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPath(path)
