# -*- coding: utf-8 -*-
"""
选歌预览界面模块
实现iPhone 17玻璃拟态风格的Pygame选歌界面
"""

import os
import math
import time
from typing import List, Optional, Callable, Tuple, TYPE_CHECKING
from dataclasses import dataclass

try:
    import pygame
    import pygame.gfxdraw
    PYGAME_AVAILABLE = True
except ImportError:
    pygame = None  # type: ignore
    PYGAME_AVAILABLE = False
    print("[SongSelect] pygame不可用")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[SongSelect] Pillow不可用，封面显示受限")

# 类型提示中使用的前向引用
if TYPE_CHECKING:
    import pygame

# 导入项目模块
from directory_parser import SongInfo
from config_manager import ConfigManager
from audio_manager import AudioManager, get_audio_manager
from ui_glass import GlassRenderer, GlassColors, GlassCard, GlassButton, InertialScroll, SpectrumAnalyzer


# ========================= 数据类 =========================

@dataclass
class SongCardData:
    """歌曲卡片数据"""
    song_info: SongInfo
    rect: 'pygame.Rect' = None
    hover: bool = False
    hover_time: float = 0.0
    cover_surface: 'pygame.Surface' = None
    cover_loaded: bool = False


# ========================= 选歌界面场景 =========================

class SongSelectScene:
    """
    选歌预览场景

    功能：
    - 玻璃拟态UI
    - 歌曲卡片网格布局
    - 悬停预览音频
    - 频谱可视化
    - 星级筛选
    - 搜索功能
    - 分页导航
    """

    def __init__(self, screen: 'pygame.Surface', config: ConfigManager,
                 audio_manager: AudioManager = None):
        """
        初始化选歌场景

        Args:
            screen: pygame Surface
            config: 配置管理器
            audio_manager: 音频管理器（可选）
        """
        self.screen = screen
        self.config = config
        self.audio_manager = audio_manager or get_audio_manager()

        # 窗口尺寸
        self.window_w, self.window_h = screen.get_size()

        # 歌曲列表
        self.songs: List[SongInfo] = []
        self.filtered_songs: List[SongInfo] = []
        self.cards: List[SongCardData] = []

        # 分页
        self.current_page = 0
        self.items_per_page = 8
        self.columns = 4
        self.rows = 2

        # 筛选
        self.filter_visible = False
        self.search_text = ""
        self.star_filter_min: Optional[int] = None
        self.star_filter_max: Optional[int] = None

        # 交互
        self.hover_card: Optional[SongCardData] = None
        self.hover_start_time: float = 0
        self.pressed_card: Optional[SongCardData] = None
        self.pressed_time: float = 0

        # 滚动
        self.scroll = InertialScroll(friction=8.0)

        # 频谱
        self.spectrum = SpectrumAnalyzer(bar_count=32)

        # 动画
        self.animation_time = 0.0
        self.transition_alpha = 255

        # 字体
        self.font_title = GlassRenderer.load_font(24)
        self.font_normal = GlassRenderer.load_font(16)
        self.font_small = GlassRenderer.load_font(12)

        # 回调
        self._on_song_select: Optional[Callable[[SongInfo], None]] = None

        # 静态层缓存
        self._background_cache: Optional['pygame.Surface'] = None
        self._need_redraw_background = True

        # 预览状态
        self._previewing_song: Optional[SongInfo] = None

    def set_on_song_select(self, callback: Callable[[SongInfo], None]):
        """设置歌曲选择回调"""
        self._on_song_select = callback

    def load_songs(self, songs: List[SongInfo]):
        """加载歌曲列表"""
        self.songs = songs
        self.filtered_songs = songs.copy()
        self.current_page = 0
        self._update_layout()
        self._need_redraw_background = True

    def _update_layout(self):
        """更新布局"""
        # 根据窗口大小调整布局
        if self.window_w >= self.config.get("large_screen_threshold", 1920):
            self.columns = self.config.get("card_columns_large", 4)
            self.rows = self.config.get("card_rows_large", 2)
        else:
            self.columns = self.config.get("card_columns_small", 3)
            self.rows = self.config.get("card_rows_small", 3)

        self.items_per_page = self.columns * self.rows

        # 计算卡片尺寸
        margin = 40
        gap = 20
        header_height = 80
        footer_height = 60
        filter_height = 60 if self.filter_visible else 0

        available_width = self.window_w - margin * 2
        available_height = self.window_h - header_height - footer_height - filter_height - margin * 2

        card_width = (available_width - gap * (self.columns - 1)) // self.columns
        card_height = (available_height - gap * (self.rows - 1)) // self.rows

        # 限制卡片尺寸
        card_width = min(card_width, 300)
        card_height = min(card_height, 280)

        # 封面尺寸
        self.cover_width = int(card_width - 20)
        self.cover_height = int(card_height * 0.65)

        # 重新创建卡片
        self.cards.clear()
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.filtered_songs))

        for i in range(start_idx, end_idx):
            song = self.filtered_songs[i]
            row = (i - start_idx) // self.columns
            col = (i - start_idx) % self.columns

            x = margin + col * (card_width + gap)
            y = header_height + filter_height + margin + row * (card_height + gap)

            rect = pygame.Rect(x, y, card_width, card_height)
            card_data = SongCardData(song_info=song, rect=rect)
            self.cards.append(card_data)

        # 更新滚动范围
        total_pages = max(1, (len(self.filtered_songs) + self.items_per_page - 1) // self.items_per_page)
        self.scroll.set_range(0, total_pages - 1)

    def handle_resize(self, width: int, height: int):
        """处理窗口大小改变"""
        self.window_w = width
        self.window_h = height
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        self._background_cache = None
        self._need_redraw_background = True
        self._update_layout()

    def handle_event(self, event: 'pygame.event.Event'):
        """处理事件"""
        if event.type == pygame.KEYDOWN:
            self._handle_keydown(event.key)

        elif event.type == pygame.MOUSEMOTION:
            self._handle_mouse_motion(event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._handle_mouse_down(event.pos, event.button)

        elif event.type == pygame.MOUSEBUTTONUP:
            self._handle_mouse_up(event.pos, event.button)

        elif event.type == pygame.MOUSEWHEEL:
            self._handle_mouse_wheel(event.y)

    def _handle_keydown(self, key):
        """处理键盘按下"""
        if key == pygame.K_TAB:
            # 切换筛选栏
            self.filter_visible = not self.filter_visible
            self._update_layout()
            self._need_redraw_background = True

        elif key == pygame.K_LEFT:
            # 上一页
            self._prev_page()

        elif key == pygame.K_RIGHT:
            # 下一页
            self._next_page()

        elif key == pygame.K_ESCAPE:
            # 关闭筛选栏
            if self.filter_visible:
                self.filter_visible = False
                self._update_layout()
                self._need_redraw_background = True

        elif key == pygame.K_RETURN:
            # 选择当前悬停的歌曲
            if self.hover_card:
                self._select_song(self.hover_card.song_info)

    def _handle_mouse_motion(self, pos):
        """处理鼠标移动"""
        # 检测悬停卡片
        new_hover = None
        for card in self.cards:
            if card.rect.collidepoint(pos):
                new_hover = card
                break

        if new_hover != self.hover_card:
            # 离开旧卡片
            if self.hover_card:
                self.hover_card.hover = False
                self._on_card_leave(self.hover_card)

            # 进入新卡片
            if new_hover:
                new_hover.hover = True
                new_hover.hover_time = time.time()
                self._on_card_hover(new_hover)

            self.hover_card = new_hover

    def _handle_mouse_down(self, pos, button):
        """处理鼠标按下"""
        if button == 1:  # 左键
            for card in self.cards:
                if card.rect.collidepoint(pos):
                    self.pressed_card = card
                    self.pressed_time = time.time()
                    break

    def _handle_mouse_up(self, pos, button):
        """处理鼠标释放"""
        if button == 1:
            # 检查是否点击卡片
            if self.pressed_card:
                if self.pressed_card.rect.collidepoint(pos):
                    elapsed = time.time() - self.pressed_time
                    if elapsed < 0.3:  # 短按
                        self._select_song(self.pressed_card.song_info)
                self.pressed_card = None
                return

            # 检查是否点击导航按钮
            total_pages = max(1, (len(self.filtered_songs) + self.items_per_page - 1) // self.items_per_page)

            # 上一页按钮
            prev_rect = pygame.Rect(20, self.window_h - 40, 80, 30)
            if prev_rect.collidepoint(pos) and self.current_page > 0:
                self._prev_page()
                return

            # 下一页按钮
            next_rect = pygame.Rect(self.window_w - 100, self.window_h - 40, 80, 30)
            if next_rect.collidepoint(pos) and self.current_page < total_pages - 1:
                self._next_page()
                return

    def _handle_mouse_wheel(self, direction):
        """处理鼠标滚轮"""
        if direction > 0:
            self._prev_page()
        else:
            self._next_page()

    def _on_card_hover(self, card: SongCardData):
        """卡片悬停事件"""
        song = card.song_info
        self._previewing_song = song

        # 开始音频预览
        if song.has_audio:
            self.audio_manager.start_preview(
                song.audio_file,
                duration=self.config.get("preview_duration", 10),
                callback=lambda: self._on_preview_start(song)
            )

    def _on_card_leave(self, card: SongCardData):
        """卡片离开事件"""
        card.hover = False

        # 停止预览
        if self._previewing_song == card.song_info:
            self.audio_manager.cancel_preview()
            self._previewing_song = None

    def _on_preview_start(self, song: SongInfo):
        """预览开始回调"""
        pass

    def _select_song(self, song: SongInfo):
        """选择歌曲"""
        # 停止预览
        self.audio_manager.stop_preview()

        # 触发回调
        if self._on_song_select:
            self._on_song_select(song)

    def _prev_page(self):
        """上一页"""
        if self.current_page > 0:
            self.current_page -= 1
            self._update_layout()
            self._need_redraw_background = True

            # 保存页码
            self.config.set_last_page(self.current_page)

    def _next_page(self):
        """下一页"""
        total_pages = (len(self.filtered_songs) + self.items_per_page - 1) // self.items_per_page
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._update_layout()
            self._need_redraw_background = True

            # 保存页码
            self.config.set_last_page(self.current_page)

    def go_to_page(self, page: int):
        """跳转到指定页"""
        total_pages = max(1, (len(self.filtered_songs) + self.items_per_page - 1) // self.items_per_page)
        page = max(0, min(page, total_pages - 1))
        if page != self.current_page:
            self.current_page = page
            self._update_layout()
            self._need_redraw_background = True

    def apply_search(self, keyword: str):
        """应用搜索"""
        self.search_text = keyword.lower()

        if not self.search_text:
            self.filtered_songs = self.songs.copy()
        else:
            self.filtered_songs = [
                s for s in self.songs
                if self.search_text in s.display_name.lower()
                or self.search_text in s.folder_name.lower()
            ]

        self.current_page = 0
        self._update_layout()
        self._need_redraw_background = True

    def apply_star_filter(self, min_star: Optional[int], max_star: Optional[int]):
        """应用星级筛选"""
        self.star_filter_min = min_star
        self.star_filter_max = max_star

        # 重新筛选
        self.filtered_songs = self.songs.copy()

        if self.search_text:
            self.filtered_songs = [
                s for s in self.filtered_songs
                if self.search_text in s.display_name.lower()
                or self.search_text in s.folder_name.lower()
            ]

        if min_star is not None or max_star is not None:
            filtered = []
            for song in self.filtered_songs:
                if song.star_rating is None:
                    continue
                if min_star is not None and song.star_rating < min_star:
                    continue
                if max_star is not None and song.star_rating > max_star:
                    continue
                filtered.append(song)
            self.filtered_songs = filtered

        self.current_page = 0
        self._update_layout()
        self._need_redraw_background = True

    def update(self, dt: float):
        """更新场景"""
        self.animation_time += dt

        # 更新频谱
        is_playing = self.audio_manager.is_playing
        self.spectrum.update(is_playing)

        # 加载卡片封面
        for card in self.cards:
            if not card.cover_loaded and card.song_info.has_banner:
                self._load_card_cover(card)

    def _load_card_cover(self, card: SongCardData):
        """加载卡片封面"""
        if not PIL_AVAILABLE:
            card.cover_loaded = True
            return

        banner_path = card.song_info.banner_file
        if not banner_path or not os.path.exists(banner_path):
            card.cover_loaded = True
            return

        try:
            img = Image.open(banner_path)

            # 裁剪到封面比例
            img_ratio = img.width / img.height
            target_ratio = self.cover_width / self.cover_height

            if img_ratio > target_ratio:
                # 图片更宽，裁剪宽度
                new_width = int(img.height * target_ratio)
                left = (img.width - new_width) // 2
                img = img.crop((left, 0, left + new_width, img.height))
            else:
                # 图片更高，裁剪高度
                new_height = int(img.width / target_ratio)
                top = (img.height - new_height) // 2
                img = img.crop((0, top, img.width, top + new_height))

            # 缩放
            img = img.resize((self.cover_width, self.cover_height), Image.Resampling.LANCZOS)

            # 转换为pygame Surface
            mode = img.mode
            if mode == "RGBA":
                data = img.tobytes()
                card.cover_surface = pygame.image.fromstring(data, img.size, mode)
            else:
                img = img.convert("RGBA")
                data = img.tobytes()
                card.cover_surface = pygame.image.fromstring(data, img.size, "RGBA")

        except Exception as e:
            print(f"[SongSelect] 加载封面失败: {e}")

        card.cover_loaded = True

    def draw(self):
        """绘制场景"""
        # 绘制背景
        self._draw_background()

        # 绘制频谱（在卡片下方）
        if self.audio_manager.is_playing:
            self._draw_spectrum()

        # 绘制卡片
        for card in self.cards:
            self._draw_card(card)

        # 绘制顶部信息栏
        self._draw_header()

        # 绘制筛选栏
        if self.filter_visible:
            self._draw_filter_bar()

        # 绘制底部导航
        self._draw_footer()

    def _draw_background(self):
        """绘制背景"""
        # 绘制渐变背景
        GlassRenderer.draw_gradient_background(
            self.screen,
            GlassColors.BG_TOP,
            GlassColors.BG_BOTTOM
        )

        # 绘制霓虹网格
        GlassRenderer.draw_neon_grid(
            self.screen,
            self.screen.get_rect(),
            grid_size=60,
            color=(40, 80, 150, 15)
        )

    def _draw_spectrum(self):
        """绘制频谱可视化"""
        bars = self.spectrum.get_bars()
        if not bars:
            return

        # 频谱区域（底部）
        spectrum_rect = pygame.Rect(0, self.window_h - 100, self.window_w, 80)

        # 半透明背景
        spectrum_bg = pygame.Surface((spectrum_rect.width, spectrum_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(spectrum_bg, (0, 0, 0, 50), spectrum_bg.get_rect())
        self.screen.blit(spectrum_bg, spectrum_rect.topleft)

        # 绘制频谱条
        GlassRenderer.draw_spectrum_bars(
            self.screen,
            bars,
            spectrum_rect,
            GlassColors.SPECTRUM_COLORS,
            bar_gap=3
        )

    def _draw_card(self, card: SongCardData):
        """绘制歌曲卡片"""
        rect = card.rect
        song = card.song_info

        # 玻璃卡片背景
        GlassRenderer.draw_glass_card(
            self.screen,
            rect,
            corner_radius=16,
            alpha=77,
            hover=card.hover
        )

        # 封面区域
        cover_x = rect.x + (rect.width - self.cover_width) // 2
        cover_y = rect.y + 10
        cover_rect = pygame.Rect(cover_x, cover_y, self.cover_width, self.cover_height)

        if card.cover_surface:
            # 绘制封面
            self.screen.blit(card.cover_surface, cover_rect.topleft)

            # 圆角裁剪（通过绘制遮罩实现）
            mask = pygame.Surface((self.cover_width, self.cover_height), pygame.SRCALPHA)
            pygame.draw.rect(mask, (0, 0, 0, 0), mask.get_rect(), border_radius=8)
            # 使用混合模式实现圆角
            # 这里简化处理，直接绘制
        else:
            # 绘制占位图
            pygame.draw.rect(
                self.screen,
                (40, 40, 60),
                cover_rect,
                border_radius=8
            )
            # 绘制音符图标
            if self.font_normal:
                icon_text = self.font_normal.render("♪", True, (100, 100, 120))
                icon_rect = icon_text.get_rect(center=cover_rect.center)
                self.screen.blit(icon_text, icon_rect)

        # 封面边框
        pygame.draw.rect(
            self.screen,
            GlassColors.GLASS_BORDER[:3],
            cover_rect,
            width=1,
            border_radius=8
        )

        # 歌曲名称
        name_y = cover_y + self.cover_height + 8
        name_text = self._truncate_text(song.display_name, self.font_normal, rect.width - 20)
        if name_text and self.font_normal:
            name_surface = self.font_normal.render(name_text, True, GlassColors.TEXT_WHITE)
            name_rect = name_surface.get_rect(centerx=rect.centerx, y=name_y)
            self.screen.blit(name_surface, name_rect)

        # 星级
        if song.star_rating is not None:
            star_y = name_y + 25
            GlassRenderer.draw_star_rating(
                self.screen,
                song.star_rating,
                (rect.centerx, star_y),
                size=8
            )

        # 无谱面/无音频提示
        tip_y = rect.bottom - 20
        if not song.has_sm:
            self._draw_mini_tooltip(rect, tip_y, "无谱面")
        elif not song.has_audio:
            self._draw_mini_tooltip(rect, tip_y, "无音频")

    def _draw_mini_tooltip(self, card_rect: 'pygame.Rect', y: int, text: str):
        """绘制迷你提示"""
        if not self.font_small:
            return

        tip_surface = self.font_small.render(text, True, (150, 150, 160))
        tip_rect = tip_surface.get_rect(centerx=card_rect.centerx, y=y)

        # 背景
        bg_rect = tip_rect.inflate(10, 4)
        pygame.draw.rect(
            self.screen,
            (30, 30, 40, 180),
            bg_rect,
            border_radius=4
        )

        self.screen.blit(tip_surface, tip_rect)

    def _draw_header(self):
        """绘制顶部信息栏"""
        header_rect = pygame.Rect(0, 0, self.window_w, 60)

        # 玻璃面板背景
        GlassRenderer.draw_glass_panel(
            self.screen,
            header_rect,
            corner_radius=0,
            alpha=60
        )

        # 标题
        if self.font_title:
            title_surface = self.font_title.render(
                "SM Arrow Player",
                True,
                GlassColors.TEXT_WHITE
            )
            self.screen.blit(title_surface, (20, 15))

        # 歌曲总数
        if self.font_normal:
            total_text = f"共 {len(self.filtered_songs)} 首"
            total_surface = self.font_normal.render(total_text, True, GlassColors.TEXT_GRAY)
            total_rect = total_surface.get_rect(right=self.window_w - 20, centery=30)
            self.screen.blit(total_surface, total_rect)

    def _draw_filter_bar(self):
        """绘制筛选栏"""
        filter_rect = pygame.Rect(0, 60, self.window_w, 50)

        # 玻璃面板背景
        GlassRenderer.draw_glass_panel(
            self.screen,
            filter_rect,
            corner_radius=0,
            alpha=40
        )

        # 筛选按钮
        button_width = 80
        button_height = 30
        start_x = 20

        star_ranges = [
            ("全部", None, None),
            ("1-5★", 1, 5),
            ("6-9★", 6, 9),
            ("10+★", 10, None),
        ]

        for i, (label, min_star, max_star) in enumerate(star_ranges):
            btn_rect = pygame.Rect(start_x + i * (button_width + 10), 70, button_width, button_height)
            is_active = (self.star_filter_min == min_star and self.star_filter_max == max_star)

            GlassRenderer.draw_glass_button(
                self.screen,
                btn_rect,
                label,
                self.font_small or GlassRenderer.load_font(12),
                corner_radius=15,
                hover=btn_rect.collidepoint(pygame.mouse.get_pos()),
                active=is_active
            )

        # 搜索框（简化处理，只显示提示）
        search_rect = pygame.Rect(self.window_w - 220, 70, 200, 30)
        pygame.draw.rect(
            self.screen,
            (40, 40, 60, 100),
            search_rect,
            border_radius=15
        )
        pygame.draw.rect(
            self.screen,
            GlassColors.GLASS_BORDER[:3],
            search_rect,
            width=1,
            border_radius=15
        )

        if self.font_small:
            search_text = self.search_text if self.search_text else "搜索歌曲..."
            search_surface = self.font_small.render(search_text, True, GlassColors.TEXT_GRAY)
            search_text_rect = search_surface.get_rect(
                centerx=search_rect.centerx,
                centery=search_rect.centery
            )
            self.screen.blit(search_surface, search_text_rect)

    def _draw_footer(self):
        """绘制底部导航"""
        footer_rect = pygame.Rect(0, self.window_h - 50, self.window_w, 50)

        # 玻璃面板背景
        GlassRenderer.draw_glass_panel(
            self.screen,
            footer_rect,
            corner_radius=0,
            alpha=60
        )

        total_pages = max(1, (len(self.filtered_songs) + self.items_per_page - 1) // self.items_per_page)

        # 上一页按钮
        prev_rect = pygame.Rect(20, self.window_h - 40, 80, 30)
        prev_enabled = self.current_page > 0
        GlassRenderer.draw_glass_button(
            self.screen,
            prev_rect,
            "◀ 上一页",
            self.font_small or GlassRenderer.load_font(12),
            corner_radius=15,
            hover=prev_enabled and prev_rect.collidepoint(pygame.mouse.get_pos()),
            active=False
        )

        # 页码
        if self.font_normal:
            page_text = f"第 {self.current_page + 1} / {total_pages} 页"
            page_surface = self.font_normal.render(page_text, True, GlassColors.TEXT_WHITE)
            page_rect = page_surface.get_rect(center=(self.window_w // 2, self.window_h - 25))
            self.screen.blit(page_surface, page_rect)

        # 下一页按钮
        next_rect = pygame.Rect(self.window_w - 100, self.window_h - 40, 80, 30)
        next_enabled = self.current_page < total_pages - 1
        GlassRenderer.draw_glass_button(
            self.screen,
            next_rect,
            "下一页 ▶",
            self.font_small or GlassRenderer.load_font(12),
            corner_radius=15,
            hover=next_enabled and next_rect.collidepoint(pygame.mouse.get_pos()),
            active=False
        )

        # Tab键提示
        if self.font_small:
            tip_text = "Tab: 筛选  ←→: 翻页  Enter: 选择"
            tip_surface = self.font_small.render(tip_text, True, GlassColors.TEXT_DARK)
            tip_rect = tip_surface.get_rect(centerx=self.window_w // 2, y=self.window_h - 20)
            # 不绘制，避免重叠

    def _truncate_text(self, text: str, font: 'pygame.font.Font', max_width: int) -> str:
        """截断文本"""
        if not font or not text:
            return text

        try:
            text_width = font.size(text)[0]
            if text_width <= max_width:
                return text

            # 逐字截断
            truncated = ""
            for char in text:
                test = truncated + char
                if font.size(test + "...")[0] > max_width:
                    return truncated + "..."
                truncated = test
            return text
        except Exception:
            return text[:15] + "..." if len(text) > 15 else text

    def cleanup(self):
        """清理资源"""
        # 停止预览
        self.audio_manager.stop_preview()

        # 清理封面缓存
        for card in self.cards:
            card.cover_surface = None
            card.cover_loaded = False

        # 清理背景缓存
        self._background_cache = None
