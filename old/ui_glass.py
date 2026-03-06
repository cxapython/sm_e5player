# -*- coding: utf-8 -*-
"""
玻璃拟态UI组件模块
实现iPhone 17风格的玻璃拟态视觉效果
"""

import math
import os
from typing import List, Tuple, Optional, Callable, TYPE_CHECKING, Union
from dataclasses import dataclass

try:
    import pygame
    import pygame.gfxdraw
    PYGAME_AVAILABLE = True
except ImportError:
    pygame = None  # type: ignore
    PYGAME_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# 类型提示中使用的前向引用
if TYPE_CHECKING:
    import pygame
    SurfaceType = pygame.Surface
else:
    SurfaceType = object


# ========================= 颜色定义 =========================

class GlassColors:
    """玻璃拟态颜色方案"""

    # 背景色
    BG_TOP = (12, 12, 25)          # 深空黑
    BG_BOTTOM = (25, 35, 60)       # 深蓝

    # 玻璃卡片
    GLASS_FILL = (30, 30, 50, 77)      # 磨砂玻璃填充 RGBA
    GLASS_BORDER = (200, 200, 210, 200)  # 哑光银边框 RGBA
    GLASS_BORDER_HOVER = (220, 200, 100)  # 悬停时金色边框

    # 霓虹网格
    GRID_COLOR = (40, 80, 150, 20)     # 霓虹网格 RGBA

    # 星级颜色
    STAR_BLUE = (100, 180, 255)      # 1-5星 蓝色
    STAR_PURPLE = (180, 100, 255)    # 6-9星 紫色
    STAR_RED = (255, 100, 100)       # 10+星 红色
    STAR_GOLD = (255, 220, 50)       # 星星金色

    # 文字颜色
    TEXT_WHITE = (240, 240, 250)
    TEXT_GRAY = (180, 180, 190)
    TEXT_DARK = (100, 100, 120)

    # 频谱颜色
    SPECTRUM_COLORS = [
        (100, 180, 255),   # 蓝
        (150, 100, 255),   # 紫
        (255, 100, 150),   # 粉
        (255, 150, 50),    # 橙
        (100, 255, 150),   # 绿
    ]

    # 判定颜色
    PERFECT = (50, 255, 100)
    GOOD = (255, 220, 50)
    BAD = (255, 80, 80)
    MISS = (150, 150, 150)


# ========================= 玻璃渲染器 =========================

class GlassRenderer:
    """玻璃拟态渲染器 - 静态方法集合"""

    # Surface缓存
    _surface_cache: dict = {}

    @classmethod
    def clear_cache(cls):
        """清除Surface缓存"""
        cls._surface_cache.clear()

    @staticmethod
    def draw_gradient_background(surface: SurfaceType,
                                  top_color: Tuple[int, int, int] = None,
                                  bottom_color: Tuple[int, int, int] = None):
        """
        绘制垂直渐变背景

        Args:
            surface: 目标Surface
            top_color: 顶部颜色
            bottom_color: 底部颜色
        """
        if not PYGAME_AVAILABLE:
            return

        top_color = top_color or GlassColors.BG_TOP
        bottom_color = bottom_color or GlassColors.BG_BOTTOM

        width, height = surface.get_size()

        for y in range(height):
            progress = y / height
            r = int(top_color[0] + (bottom_color[0] - top_color[0]) * progress)
            g = int(top_color[1] + (bottom_color[1] - top_color[1]) * progress)
            b = int(top_color[2] + (bottom_color[2] - top_color[2]) * progress)
            pygame.draw.line(surface, (r, g, b), (0, y), (width, y))

    @staticmethod
    def draw_neon_grid(surface: 'pygame.Surface',
                        rect: 'pygame.Rect' = None,
                        grid_size: int = 60,
                        color: Tuple[int, int, int, int] = None):
        """
        绘制霓虹网格纹理

        Args:
            surface: 目标Surface
            rect: 绘制区域，为None时使用整个surface
            grid_size: 网格大小
            color: 网格颜色 RGBA
        """
        if not PYGAME_AVAILABLE:
            return

        color = color or GlassColors.GRID_COLOR
        rect = rect or surface.get_rect()
        width, height = rect.width, rect.height

        # 创建临时Surface
        grid_surface = pygame.Surface((width, height), pygame.SRCALPHA)

        # 垂直线
        for x in range(0, width, grid_size):
            pygame.draw.line(grid_surface, color, (x, 0), (x, height), 1)

        # 水平线
        for y in range(0, height, grid_size):
            pygame.draw.line(grid_surface, color, (0, y), (width, y), 1)

        surface.blit(grid_surface, rect.topleft)

    @staticmethod
    def draw_glass_card(surface: 'pygame.Surface',
                         rect: 'pygame.Rect',
                         corner_radius: int = 16,
                         alpha: int = 77,
                         border_width: int = 1,
                         hover: bool = False):
        """
        绘制玻璃风格卡片

        Args:
            surface: 目标Surface
            rect: 卡片区域
            corner_radius: 圆角半径
            alpha: 填充透明度 (0-255)
            border_width: 边框宽度
            hover: 是否悬停状态
        """
        if not PYGAME_AVAILABLE:
            return

        # 创建卡片Surface
        card_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)

        # 填充层
        fill_color = (30, 30, 50, alpha)
        if hover:
            fill_color = (40, 40, 60, min(255, alpha + 30))

        pygame.draw.rect(
            card_surface,
            fill_color,
            card_surface.get_rect(),
            border_radius=corner_radius
        )

        # 边框
        border_color = GlassColors.GLASS_BORDER_HOVER if hover else GlassColors.GLASS_BORDER[:3]
        border_alpha = GlassColors.GLASS_BORDER[3] if not hover else 255
        border_with_alpha = (*border_color[:3], border_alpha)

        # 绘制圆角边框
        pygame.draw.rect(
            card_surface,
            border_with_alpha,
            card_surface.get_rect(),
            width=border_width,
            border_radius=corner_radius
        )

        # 顶部高光
        highlight_rect = pygame.Rect(0, 0, rect.width, rect.height // 4)
        highlight_surface = pygame.Surface((highlight_rect.width, highlight_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(
            highlight_surface,
            (255, 255, 255, 20),
            highlight_surface.get_rect(),
            border_radius=corner_radius
        )
        card_surface.blit(highlight_surface, highlight_rect.topleft)

        surface.blit(card_surface, rect.topleft)

    @staticmethod
    def draw_glass_button(surface: 'pygame.Surface',
                           rect: 'pygame.Rect',
                           text: str,
                           font: 'pygame.font.Font',
                           corner_radius: int = 12,
                           alpha: int = 50,
                           hover: bool = False,
                           active: bool = False):
        """
        绘制玻璃风格按钮

        Args:
            surface: 目标Surface
            rect: 按钮区域
            text: 按钮文字
            font: 字体
            corner_radius: 圆角半径
            alpha: 填充透明度
            hover: 是否悬停
            active: 是否激活
        """
        if not PYGAME_AVAILABLE:
            return

        # 按钮背景
        if active:
            fill_color = (60, 100, 180, alpha + 30)
        elif hover:
            fill_color = (50, 50, 70, alpha + 20)
        else:
            fill_color = (40, 40, 60, alpha)

        button_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(
            button_surface,
            fill_color,
            button_surface.get_rect(),
            border_radius=corner_radius
        )

        # 边框
        border_color = GlassColors.GLASS_BORDER_HOVER if hover else GlassColors.GLASS_BORDER[:3]
        pygame.draw.rect(
            button_surface,
            (*border_color, 180),
            button_surface.get_rect(),
            width=1,
            border_radius=corner_radius
        )

        # 文字
        text_color = GlassColors.TEXT_WHITE if hover else GlassColors.TEXT_GRAY
        text_surface = font.render(text, True, text_color)
        text_rect = text_surface.get_rect(center=(rect.width // 2, rect.height // 2))
        button_surface.blit(text_surface, text_rect)

        surface.blit(button_surface, rect.topleft)

    @staticmethod
    def draw_spectrum_bars(surface: 'pygame.Surface',
                            bars: List[float],
                            rect: 'pygame.Rect',
                            colors: List[Tuple[int, int, int]] = None,
                            bar_gap: int = 2):
        """
        绘制音频频谱柱状图

        Args:
            surface: 目标Surface
            bars: 频谱数据列表 (0.0-1.0)
            rect: 绘制区域
            colors: 颜色列表
            bar_gap: 柱间间距
        """
        if not PYGAME_AVAILABLE or not bars:
            return

        colors = colors or GlassColors.SPECTRUM_COLORS
        num_bars = len(bars)
        if num_bars == 0:
            return

        bar_width = (rect.width - bar_gap * (num_bars - 1)) // num_bars
        max_height = rect.height

        for i, value in enumerate(bars):
            # 限制值范围
            value = max(0.0, min(1.0, value))

            # 计算柱子位置和高度
            bar_height = int(value * max_height)
            x = rect.x + i * (bar_width + bar_gap)
            y = rect.y + rect.height - bar_height

            # 选择颜色
            color_idx = i % len(colors)
            color = colors[color_idx]

            # 绘制柱子（带渐变效果）
            bar_surface = pygame.Surface((bar_width, bar_height), pygame.SRCALPHA)

            # 从底到顶渐变
            for j in range(bar_height):
                progress = j / max(bar_height, 1)
                alpha = int(255 * (0.3 + 0.7 * progress))
                pygame.draw.line(
                    bar_surface,
                    (*color, alpha),
                    (0, j),
                    (bar_width, j)
                )

            surface.blit(bar_surface, (x, y))

    @staticmethod
    def draw_star_rating(surface: 'pygame.Surface',
                          stars: int,
                          center_pos: Tuple[int, int],
                          size: int = 12,
                          animation_progress: float = 1.0):
        """
        绘制星级可视化（星星）

        Args:
            surface: 目标Surface
            stars: 星级数值
            center_pos: 中心位置
            size: 单颗星星大小
            animation_progress: 动画进度 (0.0-1.0)
        """
        if not PYGAME_AVAILABLE:
            return

        cx, cy = center_pos

        # 限制最多显示10颗星
        display_stars = min(10, max(1, stars))

        # 统一使用金色
        star_color = GlassColors.STAR_GOLD

        # 计算星星布局
        star_gap = size + 2  # 星星间距
        total_width = display_stars * size + (display_stars - 1) * (star_gap - size)
        start_x = cx - total_width // 2

        # 绘制星星
        for i in range(display_stars):
            star_x = start_x + i * star_gap
            star_y = cy
            alpha = int(255 * animation_progress)

            # 创建带透明度的星星
            GlassRenderer._draw_star_with_alpha(surface, (star_x, star_y), size, star_color, alpha)

    @staticmethod
    def _draw_star_with_alpha(surface: 'pygame.Surface',
                               center: Tuple[int, int],
                               size: int,
                               color: Tuple[int, int, int],
                               alpha: int = 255):
        """绘制带透明度的五角星"""
        cx, cy = center
        points = []

        for i in range(5):
            # 外顶点
            angle = math.radians(i * 72 - 90)
            px = cx + int(size * math.cos(angle))
            py = cy + int(size * math.sin(angle))
            points.append((px, py))

            # 内顶点
            angle = math.radians(i * 72 - 90 + 36)
            px = cx + int(size * 0.4 * math.cos(angle))
            py = cy + int(size * 0.4 * math.sin(angle))
            points.append((px, py))

        # 创建临时surface以支持透明度
        star_surface = pygame.Surface((size * 2 + 4, size * 2 + 4), pygame.SRCALPHA)
        offset_points = [(p[0] - cx + size + 2, p[1] - cy + size + 2) for p in points]
        pygame.draw.polygon(star_surface, (*color, alpha), offset_points)
        surface.blit(star_surface, (cx - size - 2, cy - size - 2))

    @staticmethod
    def _draw_star(surface: 'pygame.Surface',
                    center: Tuple[int, int],
                    size: int,
                    color: Tuple[int, int, int]):
        """绘制五角星"""
        cx, cy = center
        points = []

        for i in range(5):
            # 外顶点
            angle = math.radians(i * 72 - 90)
            px = cx + int(size * math.cos(angle))
            py = cy + int(size * math.sin(angle))
            points.append((px, py))

            # 内顶点
            angle = math.radians(i * 72 - 90 + 36)
            px = cx + int(size * 0.4 * math.cos(angle))
            py = cy + int(size * 0.4 * math.sin(angle))
            points.append((px, py))

        pygame.draw.polygon(surface, color, points)

    @staticmethod
    def draw_glass_panel(surface: 'pygame.Surface',
                          rect: 'pygame.Rect',
                          corner_radius: int = 20,
                          alpha: int = 40):
        """
        绘制玻璃面板（透明度更高的卡片）

        Args:
            surface: 目标Surface
            rect: 面板区域
            corner_radius: 圆角半径
            alpha: 填充透明度
        """
        if not PYGAME_AVAILABLE:
            return

        panel_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)

        # 填充
        pygame.draw.rect(
            panel_surface,
            (255, 255, 255, alpha),
            panel_surface.get_rect(),
            border_radius=corner_radius
        )

        # 边框
        pygame.draw.rect(
            panel_surface,
            (255, 255, 255, 60),
            panel_surface.get_rect(),
            width=1,
            border_radius=corner_radius
        )

        surface.blit(panel_surface, rect.topleft)

    @staticmethod
    def draw_tooltip(surface: 'pygame.Surface',
                      text: str,
                      rect: 'pygame.Rect',
                      font: 'pygame.font.Font',
                      corner_radius: int = 8):
        """
        绘制玻璃风格提示框

        Args:
            surface: 目标Surface
            text: 提示文字
            rect: 提示框区域
            font: 字体
            corner_radius: 圆角半径
        """
        if not PYGAME_AVAILABLE:
            return

        # 提示框背景
        tooltip_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)

        pygame.draw.rect(
            tooltip_surface,
            (40, 40, 60, 200),
            tooltip_surface.get_rect(),
            border_radius=corner_radius
        )

        pygame.draw.rect(
            tooltip_surface,
            (100, 100, 120, 150),
            tooltip_surface.get_rect(),
            width=1,
            border_radius=corner_radius
        )

        # 文字
        text_surface = font.render(text, True, GlassColors.TEXT_GRAY)
        text_rect = text_surface.get_rect(center=(rect.width // 2, rect.height // 2))
        tooltip_surface.blit(text_surface, text_rect)

        surface.blit(tooltip_surface, rect.topleft)

    @staticmethod
    def load_font(size: int) -> 'pygame.font.Font':
        """
        安全加载字体

        Args:
            size: 字体大小

        Returns:
            pygame字体对象
        """
        if not PYGAME_AVAILABLE:
            return None

        import platform
        font_path = None

        system = platform.system()
        if system == "Windows":
            font_path = r"C:\Windows\Fonts\msyh.ttc"
        elif system == "Darwin":  # macOS
            mac_fonts = [
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/STHeiti Light.ttc",
                "/System/Library/Fonts/Hiragino Sans GB.ttc",
            ]
            for fp in mac_fonts:
                if os.path.exists(fp):
                    font_path = fp
                    break
        elif system == "Linux":
            linux_fonts = [
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            ]
            for fp in linux_fonts:
                if os.path.exists(fp):
                    font_path = fp
                    break

        if font_path and os.path.exists(font_path):
            try:
                return pygame.font.Font(font_path, size)
            except Exception:
                pass

        return pygame.font.Font(None, size)


# ========================= 组件类 =========================

class GlassCard:
    """玻璃风格卡片组件"""

    def __init__(self, rect: 'pygame.Rect', data: dict = None):
        """
        初始化卡片

        Args:
            rect: 卡片区域
            data: 卡片数据
        """
        self.rect = rect
        self.data = data or {}
        self.hover = False
        self.alpha = 77
        self.corner_radius = 16
        self._click_callback: Optional[Callable] = None
        self._hover_callback: Optional[Callable] = None
        self._leave_callback: Optional[Callable] = None

    def set_click_callback(self, callback: Callable):
        """设置点击回调"""
        self._click_callback = callback

    def set_hover_callback(self, callback: Callable):
        """设置悬停回调"""
        self._hover_callback = callback

    def set_leave_callback(self, callback: Callable):
        """设置离开回调"""
        self._leave_callback = callback

    def handle_event(self, event: 'pygame.event.Event') -> bool:
        """
        处理事件

        Returns:
            是否消费了事件
        """
        if event.type == pygame.MOUSEMOTION:
            was_hover = self.hover
            self.hover = self.rect.collidepoint(event.pos)

            if self.hover and not was_hover:
                if self._hover_callback:
                    self._hover_callback(self)
            elif not self.hover and was_hover:
                if self._leave_callback:
                    self._leave_callback(self)

            return self.hover

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.hover and event.button == 1:
                if self._click_callback:
                    self._click_callback(self)
                return True

        return False

    def draw(self, surface: 'pygame.Surface'):
        """绘制卡片"""
        GlassRenderer.draw_glass_card(
            surface,
            self.rect,
            corner_radius=self.corner_radius,
            alpha=self.alpha,
            hover=self.hover
        )


class GlassButton:
    """玻璃风格按钮组件"""

    def __init__(self, rect: 'pygame.Rect', text: str, font: 'pygame.font.Font' = None):
        """
        初始化按钮

        Args:
            rect: 按钮区域
            text: 按钮文字
            font: 字体
        """
        self.rect = rect
        self.text = text
        self.font = font or GlassRenderer.load_font(14)
        self.hover = False
        self.active = False
        self.corner_radius = 12
        self._click_callback: Optional[Callable] = None

    def set_click_callback(self, callback: Callable):
        """设置点击回调"""
        self._click_callback = callback

    def handle_event(self, event: 'pygame.event.Event') -> bool:
        """处理事件"""
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
            return self.hover

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.hover and event.button == 1:
                if self._click_callback:
                    self._click_callback(self)
                return True

        return False

    def draw(self, surface: 'pygame.Surface'):
        """绘制按钮"""
        GlassRenderer.draw_glass_button(
            surface,
            self.rect,
            self.text,
            self.font,
            corner_radius=self.corner_radius,
            hover=self.hover,
            active=self.active
        )


class InertialScroll:
    """惯性滚动控制器"""

    def __init__(self, friction: float = 5.0, elasticity: float = 0.3):
        """
        初始化惯性滚动

        Args:
            friction: 摩擦系数
            elasticity: 弹性系数
        """
        self.friction = friction
        self.elasticity = elasticity
        self.velocity = 0.0
        self.position = 0.0
        self.target_position = 0.0
        self.min_position = 0.0
        self.max_position = 0.0
        self._dragging = False
        self._last_mouse_y = 0

    def set_range(self, min_pos: float, max_pos: float):
        """设置范围"""
        self.min_position = min_pos
        self.max_position = max_pos

    def add_impulse(self, delta: float):
        """添加冲量（鼠标滚轮或拖拽）"""
        self.velocity += delta

    def start_drag(self, mouse_y: int):
        """开始拖拽"""
        self._dragging = True
        self._last_mouse_y = mouse_y
        self.velocity = 0.0

    def update_drag(self, mouse_y: int):
        """更新拖拽"""
        if self._dragging:
            delta = mouse_y - self._last_mouse_y
            self.position -= delta
            self._last_mouse_y = mouse_y

    def end_drag(self):
        """结束拖拽"""
        self._dragging = False

    def update(self, dt: float):
        """
        更新位置

        Args:
            dt: 时间增量（秒）
        """
        if self._dragging:
            return

        # 应用摩擦力
        self.velocity *= (1.0 - self.friction * dt)

        # 更新位置
        self.position += self.velocity * dt * 60

        # 边界弹性
        if self.position < self.min_position:
            self.position += (self.min_position - self.position) * self.elasticity
            self.velocity *= -0.3
        elif self.position > self.max_position:
            self.position -= (self.position - self.max_position) * self.elasticity
            self.velocity *= -0.3

        # 吸附到整数页
        if abs(self.velocity) < 0.1:
            self.velocity = 0
            # 吸附逻辑由外部控制

    def snap_to_page(self, page: int, page_size: float):
        """吸附到指定页"""
        self.target_position = page * page_size
        self.position = self.target_position
        self.velocity = 0.0

    def get_current_page(self, page_size: float) -> int:
        """获取当前页"""
        return max(0, round(self.position / page_size))


class SpectrumAnalyzer:
    """简单频谱分析器（模拟效果）"""

    def __init__(self, bar_count: int = 32):
        """
        初始化频谱分析器

        Args:
            bar_count: 频谱条数
        """
        self.bar_count = bar_count
        self.bars = [0.0] * bar_count
        self.target_bars = [0.0] * bar_count
        self.decay = 0.92
        self.smoothing = 0.3

    def update(self, is_playing: bool, beat_detected: bool = False):
        """
        更新频谱数据

        Args:
            is_playing: 是否正在播放
            beat_detected: 是否检测到节拍
        """
        import random

        if not is_playing:
            # 衰减到0
            self.bars = [b * self.decay for b in self.bars]
            return

        # 模拟频谱数据
        for i in range(self.bar_count):
            if beat_detected:
                self.target_bars[i] = random.uniform(0.6, 1.0)
            else:
                self.target_bars[i] = random.uniform(0.2, 0.8)

        # 平滑过渡
        for i in range(self.bar_count):
            self.bars[i] += (self.target_bars[i] - self.bars[i]) * self.smoothing
            self.bars[i] *= self.decay
            self.bars[i] = max(0.0, min(1.0, self.bars[i]))

    def get_bars(self) -> List[float]:
        """获取频谱数据"""
        return self.bars

    def reset(self):
        """重置"""
        self.bars = [0.0] * self.bar_count
        self.target_bars = [0.0] * self.bar_count
