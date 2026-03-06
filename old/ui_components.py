# -*- coding: utf-8 -*-
"""
UI组件模块
负责歌曲浏览器的UI组件，包括歌曲卡片和浏览器主界面
"""

import os
import tkinter as tk
from typing import List, Optional, Callable
from dataclasses import dataclass

try:
    import customtkinter as ctk
    CTk_AVAILABLE = True
except ImportError:
    CTk_AVAILABLE = False

try:
    from PIL import Image, ImageTk, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from directory_parser import SongInfo
from audio_player import get_audio_player


class SongCard(ctk.CTkFrame):
    """单个歌曲卡片组件"""

    # 卡片尺寸常量
    CARD_WIDTH = 200
    CARD_HEIGHT = 180
    BANNER_HEIGHT = 100

    def __init__(
        self,
        parent,
        song_info: SongInfo,
        on_click: Callable[[SongInfo], None],
        on_hover: Optional[Callable[[SongInfo], None]] = None,
        on_leave: Optional[Callable[[], None]] = None
    ):
        """
        初始化歌曲卡片

        :param parent: 父容器
        :param song_info: 歌曲信息
        :param on_click: 点击回调
        :param on_hover: 悬停回调（用于音频预览）
        :param on_leave: 离开回调
        """
        super().__init__(
            parent,
            width=self.CARD_WIDTH,
            height=self.CARD_HEIGHT,
            corner_radius=10,
            fg_color=("#2a2a3a", "#1a1a28"),
            border_width=2,
            border_color=("#3d5a80", "#1e3a5f")
        )

        self.song_info = song_info
        self.on_click = on_click
        self.on_hover = on_hover
        self.on_leave = on_leave

        # 鼠标悬停状态
        self._hovering = False

        # 构建UI
        self._build_ui()

        # 绑定事件
        self._bind_events()

    def _build_ui(self):
        """构建卡片UI"""
        # 封面图片区域
        self.banner_frame = ctk.CTkFrame(
            self,
            width=self.CARD_WIDTH - 10,
            height=self.BANNER_HEIGHT,
            corner_radius=8,
            fg_color=("#1a1a2e", "#0d0d1a")
        )
        self.banner_frame.pack(padx=5, pady=(5, 2))
        self.banner_frame.pack_propagate(False)

        # 加载封面图片
        self._load_banner()

        # 歌曲名称
        self.name_label = ctk.CTkLabel(
            self,
            text=self._truncate_name(self.song_info.display_name, 18),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("#ffffff", "#e0e0e0"),
            wraplength=self.CARD_WIDTH - 20
        )
        self.name_label.pack(padx=5, pady=(2, 0))

        # 星级显示区域
        if self.song_info.star_rating is not None:
            star_text = self._get_star_display(self.song_info.star_rating)
            self.star_label = ctk.CTkLabel(
                self,
                text=star_text,
                font=ctk.CTkFont(size=11),
                text_color=("#ffd700", "#ffcc00")
            )
            self.star_label.pack(padx=5, pady=(0, 2))
        else:
            self.star_label = None

        # 音频状态指示器
        self.audio_indicator = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=10),
            text_color=("#4ECDC4", "#4ECDC4")
        )
        self.audio_indicator.pack(padx=5)

    def _load_banner(self):
        """加载封面图片"""
        banner_path = self.song_info.banner_file

        if banner_path and os.path.exists(banner_path) and PIL_AVAILABLE:
            try:
                # 加载并缩放图片
                img = Image.open(banner_path)
                img = img.resize(
                    (self.CARD_WIDTH - 14, self.BANNER_HEIGHT - 4),
                    Image.Resampling.LANCZOS
                )

                # 转换为CTkImage
                self.banner_image = ctk.CTkImage(
                    light_image=img,
                    dark_image=img,
                    size=(self.CARD_WIDTH - 14, self.BANNER_HEIGHT - 4)
                )

                self.banner_label = ctk.CTkLabel(
                    self.banner_frame,
                    image=self.banner_image,
                    text=""
                )
                self.banner_label.pack(padx=2, pady=2)
                # 绑定点击事件，使封面可点击跳转
                self.banner_label.bind("<Button-1>", self._on_click)
                return

            except Exception as e:
                print(f"[SongCard] 加载封面失败: {e}")

        # 无封面时显示默认图标
        self._show_default_banner()

    def _show_default_banner(self):
        """显示默认封面"""
        # 创建一个渐变背景的默认封面
        if PIL_AVAILABLE:
            img = Image.new('RGB', (self.CARD_WIDTH - 14, self.BANNER_HEIGHT - 4), '#1a1a2e')
            draw = ImageDraw.Draw(img)

            # 绘制音符图标占位
            center_x = (self.CARD_WIDTH - 14) // 2
            center_y = (self.BANNER_HEIGHT - 4) // 2
            draw.ellipse(
                [center_x - 25, center_y - 25, center_x + 25, center_y + 25],
                fill='#3d5a80',
                outline='#4ECDC4',
                width=2
            )

            self.default_image = ctk.CTkImage(
                light_image=img,
                dark_image=img,
                size=(self.CARD_WIDTH - 14, self.BANNER_HEIGHT - 4)
            )

            self.banner_label = ctk.CTkLabel(
                self.banner_frame,
                image=self.default_image,
                text=""
            )
            self.banner_label.pack(padx=2, pady=2)
            # 绑定点击事件，使封面可点击跳转
            self.banner_label.bind("<Button-1>", self._on_click)
        else:
            # PIL不可用时显示文字
            self.banner_label = ctk.CTkLabel(
                self.banner_frame,
                text="🎵",
                font=ctk.CTkFont(size=40),
                text_color=("#4ECDC4", "#4ECDC4")
            )
            self.banner_label.pack(padx=2, pady=2)
            # 绑定点击事件，使封面可点击跳转
            self.banner_label.bind("<Button-1>", self._on_click)

    def _get_star_display(self, star: int) -> str:
        """
        生成星级显示文本

        :param star: 星级数值
        :return: 显示文本
        """
        # 根据星级选择颜色样式
        if star >= 15:
            return f"★★★★★ {star}"
        elif star >= 12:
            return f"★★★★☆ {star}"
        elif star >= 9:
            return f"★★★☆☆ {star}"
        elif star >= 6:
            return f"★★☆☆☆ {star}"
        else:
            return f"★☆☆☆☆ {star}"

    def _truncate_name(self, name: str, max_len: int) -> str:
        """截断名称"""
        if len(name) <= max_len:
            return name
        return name[:max_len - 2] + "..."

    def _bind_events(self):
        """绑定鼠标事件"""
        # 整个卡片可点击
        self.bind("<Button-1>", self._on_click)
        self.banner_frame.bind("<Button-1>", self._on_click)
        self.name_label.bind("<Button-1>", self._on_click)

        # 悬停效果
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.banner_frame.bind("<Enter>", self._on_enter)
        self.banner_frame.bind("<Leave>", self._on_leave)

        # 悬停时改变边框颜色
        for widget in [self, self.banner_frame, self.name_label]:
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)

    def _on_click(self, event):
        """点击事件处理"""
        if self.on_click:
            self.on_click(self.song_info)

    def _on_enter(self, event):
        """鼠标进入事件"""
        if not self._hovering:
            self._hovering = True
            # 高亮边框
            self.configure(border_color=("#4ECDC4", "#4ECDC4"))

            # 触发悬停回调（用于音频预览）
            if self.on_hover:
                self.on_hover(self.song_info)

    def _on_leave(self, event):
        """鼠标离开事件"""
        self._hovering = False
        # 恢复边框
        self.configure(border_color=("#3d5a80", "#1e3a5f"))

        # 触发离开回调
        if self.on_leave:
            self.on_leave()

    def set_playing_indicator(self, is_playing: bool):
        """设置播放状态指示器"""
        if is_playing:
            self.audio_indicator.configure(text="▶ 播放中...")
        else:
            self.audio_indicator.configure(text="")


class SongBrowser(ctk.CTkFrame):
    """歌曲浏览器主界面"""

    ITEMS_PER_PAGE = 8  # 每页显示8首歌（4列2行）
    COLUMNS = 4

    def __init__(
        self,
        parent,
        songs: List[SongInfo] = None,
        on_song_select: Callable[[SongInfo], None] = None
    ):
        """
        初始化歌曲浏览器

        :param parent: 父容器
        :param songs: 歌曲列表（可选，可后续通过set_songs设置）
        :param on_song_select: 歌曲选择回调
        """
        super().__init__(parent, fg_color="transparent")

        self.songs = songs or []
        self.on_song_select = on_song_select
        self.current_page = 0
        self.cards: List[SongCard] = []
        self.audio_player = get_audio_player()

        # 当前正在预览的歌曲
        self._previewing_song: Optional[SongInfo] = None

        # 回调函数
        self._refresh_callback: Optional[Callable] = None
        self._settings_callback: Optional[Callable] = None

        # 构建UI
        self._build_ui()

        # 渲染第一页（如果有歌曲）
        if self.songs:
            self.render_page(0)

    def _build_ui(self):
        """构建浏览器UI"""
        # 顶部信息栏
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=(0, 10))

        # 歌曲总数
        total_text = f"共 {len(self.songs)} 首歌曲"
        self.count_label = ctk.CTkLabel(
            self.header_frame,
            text=total_text,
            font=ctk.CTkFont(size=14),
            text_color=("gray80", "gray60")
        )
        self.count_label.pack(side="left")

        # 页码显示
        self.page_label = ctk.CTkLabel(
            self.header_frame,
            text="",
            font=ctk.CTkFont(size=14),
            text_color=("gray80", "gray60")
        )
        self.page_label.pack(side="right")

        # 卡片网格容器
        self.cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.cards_frame.pack(fill="both", expand=True)

        # 底部导航栏
        self.nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_frame.pack(fill="x", pady=(10, 0))

        # 上一页按钮
        self.prev_btn = ctk.CTkButton(
            self.nav_frame,
            text="◀ 上一页",
            width=100,
            command=self.prev_page,
            state="disabled"
        )
        self.prev_btn.pack(side="left", padx=10)

        # 页码指示器
        self.page_indicator = ctk.CTkLabel(
            self.nav_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=("gray80", "gray60")
        )
        self.page_indicator.pack(side="left", expand=True)

        # 下一页按钮
        self.next_btn = ctk.CTkButton(
            self.nav_frame,
            text="下一页 ▶",
            width=100,
            command=self.next_page,
            state="disabled"
        )
        self.next_btn.pack(side="right", padx=10)

        # 更新导航状态
        self._update_nav_state()

    def render_page(self, page: int):
        """
        渲染指定页的歌曲卡片

        :param page: 页码（从0开始）
        """
        # 清除现有卡片
        for card in self.cards:
            card.destroy()
        self.cards.clear()

        # 计算当前页的歌曲范围
        start_idx = page * self.ITEMS_PER_PAGE
        end_idx = min(start_idx + self.ITEMS_PER_PAGE, len(self.songs))

        if start_idx >= len(self.songs):
            return

        # 创建新的卡片
        for i in range(start_idx, end_idx):
            song = self.songs[i]

            # 计算行列位置
            row = (i - start_idx) // self.COLUMNS
            col = (i - start_idx) % self.COLUMNS

            card = SongCard(
                self.cards_frame,
                song,
                on_click=self._on_card_click,
                on_hover=self._on_card_hover,
                on_leave=self._on_card_leave
            )
            card.grid(
                row=row,
                column=col,
                padx=10,
                pady=10,
                sticky="nsew"
            )

            # 配置网格权重
            self.cards_frame.grid_columnconfigure(col, weight=1)
            self.cards_frame.grid_rowconfigure(row, weight=1)

            self.cards.append(card)

        # 更新当前页码
        self.current_page = page

        # 更新导航状态
        self._update_nav_state()

    def _on_card_click(self, song_info: SongInfo):
        """卡片点击处理"""
        # 停止音频预览
        self.audio_player.stop()
        self._clear_playing_indicator()

        # 调用选择回调
        if self.on_song_select:
            self.on_song_select(song_info)

    def _on_card_hover(self, song_info: SongInfo):
        """卡片悬停处理（启动音频预览）"""
        self._previewing_song = song_info

        # 如果有音频文件，启动预览
        if song_info.audio_file:
            self.audio_player.start_hover_preview(
                song_info.audio_file,
                callback=lambda: self._update_playing_indicator(song_info)
            )

    def _on_card_leave(self):
        """卡片离开处理（停止音频预览）"""
        self.audio_player.cancel_hover_preview()
        self.audio_player.stop()
        self._clear_playing_indicator()
        self._previewing_song = None

    def _update_playing_indicator(self, song_info: SongInfo):
        """更新播放指示器"""
        for card in self.cards:
            if card.song_info == song_info:
                card.set_playing_indicator(True)

    def _clear_playing_indicator(self):
        """清除播放指示器"""
        for card in self.cards:
            card.set_playing_indicator(False)

    def _update_nav_state(self):
        """更新导航按钮状态"""
        total_pages = self.get_total_pages()

        # 更新页码显示
        if total_pages > 0:
            self.page_label.configure(text=f"第 {self.current_page + 1} / {total_pages} 页")
            self.page_indicator.configure(text=f"页码: {self.current_page + 1} / {total_pages}")
        else:
            self.page_label.configure(text="无歌曲")
            self.page_indicator.configure(text="")

        # 更新按钮状态
        self.prev_btn.configure(
            state="normal" if self.current_page > 0 else "disabled"
        )
        self.next_btn.configure(
            state="normal" if self.current_page < total_pages - 1 else "disabled"
        )

    def get_total_pages(self) -> int:
        """获取总页数"""
        if not self.songs:
            return 0
        return (len(self.songs) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE

    def next_page(self):
        """下一页"""
        total_pages = self.get_total_pages()
        if self.current_page < total_pages - 1:
            self.render_page(self.current_page + 1)

    def prev_page(self):
        """上一页"""
        if self.current_page > 0:
            self.render_page(self.current_page - 1)

    def go_to_page(self, page: int):
        """跳转到指定页"""
        total_pages = self.get_total_pages()
        if 0 <= page < total_pages:
            self.render_page(page)

    def update_songs(self, songs: List[SongInfo]):
        """更新歌曲列表"""
        self.songs = songs
        self.current_page = 0
        self.render_page(0)

        # 更新歌曲总数显示
        self.count_label.configure(text=f"共 {len(songs)} 首歌曲")
        self._update_nav_state()

    def set_songs(self, songs: List[SongInfo]):
        """设置歌曲列表（update_songs的别名）"""
        self.update_songs(songs)

    def set_audio_callbacks(self, on_preview=None, on_stop=None):
        """设置音频回调（兼容接口）"""
        # 这里的音频预览由SongBrowser内部处理
        pass

    def set_refresh_callback(self, callback):
        """设置刷新回调"""
        self._refresh_callback = callback

    def set_settings_callback(self, callback):
        """设置设置回调"""
        self._settings_callback = callback

    def handle_key(self, key):
        """处理键盘事件"""
        if key == "left":
            self.prev_page()
        elif key == "right":
            self.next_page()
