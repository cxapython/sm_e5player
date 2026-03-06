# -*- coding: utf-8 -*-
"""
谱面播放界面模块
实现玻璃拟态风格的Pygame音游播放器
"""

import os
import time
from typing import List, Optional, Tuple, TYPE_CHECKING
from enum import Enum
from dataclasses import dataclass

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    pygame = None  # type: ignore
    PYGAME_AVAILABLE = False
    print("[ChartPlayer] pygame不可用")

# 类型提示中使用的前向引用
if TYPE_CHECKING:
    import pygame

# 导入项目模块
from config_manager import ConfigManager
from audio_manager import AudioManager
from sm_parser import SmParser, ArrowEvent, TimelineSegment, format_seconds, generate_timeline_segments, build_arrow_events
from skin_manager import SkinManager
from judge_system import JudgeSystem, JudgeResult, JudgeDisplay, JudgeLight, HitEffect
from ui_glass import GlassRenderer, GlassColors


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


class ChartPlayer:
    """
    谱面播放器

    功能：
    - 加载并解析SM文件
    - 播放音乐和箭头下落
    - 判定系统
    - 玻璃拟态UI
    - 暂停/继续/退出
    - 结算界面
    """

    # 按键映射（使用字符键码，运行时转换为pygame键码）
    _KEY_MAP_CHARS = {
        'q': 1,   # UpLeft (左上)
        'e': 3,   # UpRight (右上)
        's': 2,   # Center (中间)
        'z': 0,   # DownLeft (左下)
        'c': 4,   # DownRight (右下)
    }

    @classmethod
    def _get_key_map(cls):
        """获取按键映射（延迟加载）"""
        if hasattr(cls, '_KEY_MAP_CACHE'):
            return cls._KEY_MAP_CACHE
        if PYGAME_AVAILABLE and pygame:
            cls._KEY_MAP_CACHE = {
                pygame.K_q: 1,
                pygame.K_e: 3,
                pygame.K_s: 2,
                pygame.K_z: 0,
                pygame.K_c: 4,
            }
        else:
            cls._KEY_MAP_CACHE = {}
        return cls._KEY_MAP_CACHE

    KEY_MAP = property(lambda self: self._get_key_map())

    def __init__(self, sm_path: str, audio_path: Optional[str],
                 skin_dir: str, config: ConfigManager,
                 audio_manager: AudioManager = None):
        """
        初始化播放器

        Args:
            sm_path: SM文件路径
            audio_path: 音频文件路径
            skin_dir: 皮肤目录
            config: 配置管理器
            audio_manager: 音频管理器
        """
        self.sm_path = sm_path
        self.audio_path = audio_path
        self.skin_dir = skin_dir
        self.config = config
        self.audio_manager = audio_manager or AudioManager()

        # 窗口
        self.window_w, self.window_h = config.get_window_size()
        self.screen: Optional[pygame.Surface] = None
        self.clock: Optional[pygame.time.Clock] = None

        # 状态
        self.game_state = GameState.LOADING
        self.end_reason = ""

        # 解析器
        self.sm_parser = SmParser(tick_per_beat=config.get_tick_per_beat())

        # 皮肤
        self.skin = SkinManager(skin_dir)

        # 判定系统
        self.judge_system = JudgeSystem()
        self.judge_display = JudgeDisplay()
        self.judge_light = JudgeLight(track_count=5)
        self.hit_effect = HitEffect()

        # 谱面数据
        self.chart_title = ""
        self.chart_offset = 0.0
        self.bpm_list: List[Tuple[float, float]] = []
        self.timeline_segments: List[TimelineSegment] = []
        self.arrow_events: List[ArrowEvent] = []

        # 播放状态
        self.current_sec = 0.0
        self.total_sec = 0.0
        self.is_playing = False
        self.start_time = 0.0
        self.pause_time = 0.0

        # 滚动速度
        self.scroll_speed = config.get_scroll_speed()

        # 皮肤Surface
        self.tap_surfs: List[Optional[pygame.Surface]] = [None] * 5
        self.hold_body_surfs: List[Optional[pygame.Surface]] = [None] * 5
        self.hold_tail_surfs: List[Optional[pygame.Surface]] = [None] * 5
        self.receptor_surfs: List[Optional[pygame.Surface]] = [None] * 5

        # 按键状态
        self.key_pressed: List[bool] = [False] * 5

        # 封面
        self.banner_surf: Optional[pygame.Surface] = None

        # 字体
        self.font_title = None
        self.font_normal = None
        self.font_small = None
        self.font_judge = None

        # 结果
        self.result: Optional[GameResult] = None

        # 结果显示计时
        self.result_display_time = 0.0

        # 暂停菜单选项
        self.pause_menu_index = 0
        self.pause_menu_options = ["继续", "重新开始", "返回选歌"]

    def load(self) -> bool:
        """
        加载谱面

        Returns:
            是否成功
        """
        try:
            # 解析SM文件
            chart_info, notes_blocks = self.sm_parser.parse_file(self.sm_path)

            if not notes_blocks:
                raise ValueError("SM文件中未找到NOTES区块")

            # 使用第一个NOTES
            notes_block = notes_blocks[0]

            # 检测列数
            col_count = self.sm_parser.detect_column_count(notes_block)
            self.sm_parser.atype_map, _ = self.sm_parser.recommend_atype_map(col_count)

            # 解析箭头事件
            event_table, _ = self.sm_parser.parse_arrow_events(notes_block)

            # 处理BPM
            self.bpm_list = chart_info.bpm_list or []
            if not self.bpm_list or any(bpm <= 0 for _, bpm in self.bpm_list):
                from sm_parser import extract_available_bpm
                fallback = extract_available_bpm(
                    chart_info.display_bpm_original,
                    chart_info.bpms_original
                ) or 120.0
                self.bpm_list = [(0.0, fallback)]

            # 生成时间轴
            self.timeline_segments = generate_timeline_segments(
                self.bpm_list,
                self.sm_parser.tick_per_beat
            )

            # 构建箭头事件
            self.arrow_events = build_arrow_events(
                event_table,
                self.timeline_segments,
                self.sm_parser.tick_per_beat,
                self.sm_parser.atype_map
            )

            # 计算总时长
            if self.arrow_events:
                self.total_sec = self.arrow_events[-1].end_sec

            self.chart_title = chart_info.title or os.path.basename(self.sm_path)
            self.chart_offset = chart_info.offset

            return True

        except Exception as e:
            print(f"[ChartPlayer] 加载谱面失败: {e}")
            return False

    def init_pygame(self):
        """初始化Pygame"""
        if not PYGAME_AVAILABLE:
            return

        import platform
        if platform.system() == "Darwin":  # macOS
            os.environ["SDL_HINT_VIDEO_HIGHDPI_DISABLED"] = "0"

        pygame.init()
        pygame.font.init()

        # 创建窗口
        self.screen = pygame.display.set_mode(
            (self.window_w, self.window_h),
            pygame.RESIZABLE | pygame.HWSURFACE | pygame.DOUBLEBUF
        )
        pygame.display.set_caption(f"SM Arrow Player - {self.chart_title}")

        # 时钟
        self.clock = pygame.time.Clock()

        # 加载字体
        self.font_title = GlassRenderer.load_font(28)
        self.font_normal = GlassRenderer.load_font(18)
        self.font_small = GlassRenderer.load_font(14)
        self.font_judge = GlassRenderer.load_font(42)

        # 加载皮肤
        self.skin.open()
        self._load_skin_surfaces()

        # 加载封面
        self._load_banner()

        # 加载音频
        if self.audio_path and os.path.exists(self.audio_path):
            self.audio_manager.load_music(self.audio_path)

        # 生成音效
        self.audio_manager.generate_sfx()

    def _load_skin_surfaces(self):
        """加载皮肤Surface"""
        for i in range(5):
            self.tap_surfs[i] = self.skin.get_tap(i)
            self.hold_body_surfs[i] = self.skin.get_hold_body_surf(i)
            self.hold_tail_surfs[i] = self.skin.get_hold_tail_surf(i)
            self.receptor_surfs[i] = self.skin.get_receptor_surf(i)

    def _load_banner(self):
        """加载封面图片"""
        if not self.sm_path:
            return

        sm_dir = os.path.dirname(os.path.abspath(self.sm_path))
        banner_names = ["bn.jpg", "banner.jpg", "BN.jpg", "Banner.jpg",
                       "bn.png", "banner.png", "bann.jpg"]

        for name in banner_names:
            banner_path = os.path.join(sm_dir, name)
            if os.path.exists(banner_path):
                try:
                    self.banner_surf = pygame.image.load(banner_path).convert_alpha()
                    return
                except Exception:
                    pass

    def play(self):
        """开始播放"""
        if self.is_playing:
            return

        self.is_playing = True
        self.game_state = GameState.PLAYING
        self.start_time = time.perf_counter() - self.pause_time

        # 播放音频
        if self.audio_path:
            audio_start = max(0.0, self.current_sec - self.chart_offset)
            self.audio_manager.play_music(start_pos=audio_start)

    def pause(self):
        """暂停播放"""
        if not self.is_playing:
            return

        self.is_playing = False
        self.game_state = GameState.PAUSED
        self.pause_time = self.current_sec

        # 暂停音频
        self.audio_manager.pause_music()

    def resume(self):
        """恢复播放"""
        if self.is_playing:
            return

        self.play()

    def restart(self):
        """重新开始"""
        self.current_sec = 0.0
        self.pause_time = 0.0
        self.is_playing = False
        self.game_state = GameState.READY

        # 重置判定系统
        self.judge_system.reset()
        self.judge_display = JudgeDisplay()
        self.judge_light = JudgeLight(track_count=5)
        self.hit_effect = HitEffect()

        # 停止音频
        self.audio_manager.stop_music()

        # 重新加载音频
        if self.audio_path and os.path.exists(self.audio_path):
            self.audio_manager.load_music(self.audio_path)

    def handle_resize(self, width: int, height: int):
        """处理窗口大小改变"""
        self.window_w = max(800, width)
        self.window_h = max(600, height)
        self.screen = pygame.display.set_mode(
            (self.window_w, self.window_h),
            pygame.RESIZABLE
        )

    def run(self) -> str:
        """
        运行播放器主循环

        Returns:
            结束原因: "finished", "quit", "back"
        """
        self.game_state = GameState.READY

        running = True
        while running:
            dt = self.clock.tick(self.config.get_fps()) / 1000.0

            # 事件处理
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.end_reason = "quit"
                    running = False

                elif event.type == pygame.VIDEORESIZE:
                    self.handle_resize(event.w, event.h)

                elif event.type == pygame.KEYDOWN:
                    self._handle_keydown(event.key)

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_mouse_click(event.pos, event.button)

                elif event.type == pygame.MOUSEMOTION:
                    self._handle_mouse_motion(event.pos)

            # 更新
            self._update(dt)

            # 绘制
            self._draw()
            pygame.display.flip()

            # 检查结束条件
            if self.game_state == GameState.FINISHED:
                running = False

        # 清理
        self._cleanup()

        return self.end_reason or "quit"

    def _handle_keydown(self, key):
        """处理键盘按下"""
        key_map = self._get_key_map()
        # 游戏按键
        if key in key_map:
            track_idx = key_map[key]
            self.key_pressed[track_idx] = True

            if self.game_state == GameState.PLAYING:
                result = self.judge_system.judge(
                    self.arrow_events,
                    track_idx,
                    self.current_sec
                )
                if result:
                    # 触发效果
                    self.judge_light.trigger(track_idx)
                    self.judge_display.show(result)
                    self.audio_manager.play_sfx(f"judge_{result.value.lower()}")
            return

        # 功能按键
        if key == pygame.K_ESCAPE:
            if self.game_state == GameState.PLAYING:
                self.pause()
            elif self.game_state == GameState.PAUSED:
                # 检查菜单选择
                if self.pause_menu_index == 0:
                    self.resume()
                elif self.pause_menu_index == 1:
                    self.restart()
                else:
                    self.end_reason = "back"
                    self.game_state = GameState.FINISHED

        elif key == pygame.K_SPACE:
            if self.game_state == GameState.PLAYING:
                self.pause()
            elif self.game_state == GameState.PAUSED:
                self.resume()
            elif self.game_state == GameState.READY:
                self.play()

        elif key == pygame.K_r:
            self.restart()

        elif key == pygame.K_UP:
            if self.game_state == GameState.PAUSED:
                self.pause_menu_index = (self.pause_menu_index - 1) % len(self.pause_menu_options)

        elif key == pygame.K_DOWN:
            if self.game_state == GameState.PAUSED:
                self.pause_menu_index = (self.pause_menu_index + 1) % len(self.pause_menu_options)

        elif key == pygame.K_RETURN:
            if self.game_state == GameState.PAUSED:
                if self.pause_menu_index == 0:
                    self.resume()
                elif self.pause_menu_index == 1:
                    self.restart()
                else:
                    self.end_reason = "back"
                    self.game_state = GameState.FINISHED
            elif self.game_state == GameState.FINISHED:
                self.end_reason = "back"
                self.game_state = GameState.FINISHED

        # 调整速度
        elif key == pygame.K_LEFTBRACKET:
            self.scroll_speed = max(200.0, self.scroll_speed - 60.0)

        elif key == pygame.K_RIGHTBRACKET:
            self.scroll_speed = min(2000.0, self.scroll_speed + 60.0)

        # 快退快进
        elif key == pygame.K_LEFT:
            if self.game_state in (GameState.PLAYING, GameState.PAUSED, GameState.READY):
                self._seek_time(-5.0)

        elif key == pygame.K_RIGHT:
            if self.game_state in (GameState.PLAYING, GameState.PAUSED, GameState.READY):
                self._seek_time(5.0)

        # 调整offset
        elif key == pygame.K_MINUS:
            self.chart_offset -= 0.01

        elif key == pygame.K_EQUALS:
            self.chart_offset += 0.01

        # 切换tick_per_beat
        elif key == pygame.K_t:
            self._toggle_tick_per_beat()

        # 切换映射
        elif key == pygame.K_m:
            self._toggle_atype_map()

    def _seek_time(self, delta: float):
        """快退快进"""
        self.current_sec = max(0.0, min(self.total_sec, self.current_sec + delta))
        self.pause_time = self.current_sec
        self.start_time = time.perf_counter() - self.pause_time
        # 重置判定系统
        self.judge_system.reset()
        self.judge_display = JudgeDisplay()
        self.hit_effect = HitEffect()
        # 同步音频
        if self.audio_path and self.audio_manager.is_music_playing:
            self.audio_manager.stop_music()
            audio_start = max(0.0, self.current_sec - self.chart_offset)
            self.audio_manager.play_music(start_pos=audio_start)

    def _toggle_tick_per_beat(self):
        """切换每拍tick数"""
        TICK_CANDIDATES = [96, 48, 192]
        cur_idx = TICK_CANDIDATES.index(self.sm_parser.tick_per_beat) if self.sm_parser.tick_per_beat in TICK_CANDIDATES else 0
        cur_idx = (cur_idx + 1) % len(TICK_CANDIDATES)
        self.sm_parser.tick_per_beat = TICK_CANDIDATES[cur_idx]

        # 重新生成时间轴和箭头事件
        from sm_parser import generate_timeline_segments, build_arrow_events
        self.timeline_segments = generate_timeline_segments(
            self.bpm_list,
            self.sm_parser.tick_per_beat
        )
        # 重新解析箭头事件
        notes_block = self.sm_parser.notes_blocks[0] if self.sm_parser.notes_blocks else None
        if notes_block:
            event_table, _ = self.sm_parser.parse_arrow_events(notes_block)
            self.arrow_events = build_arrow_events(
                event_table,
                self.timeline_segments,
                self.sm_parser.tick_per_beat,
                self.sm_parser.atype_map
            )
            if self.arrow_events:
                self.total_sec = self.arrow_events[-1].end_sec

        # 重置判定系统
        self.judge_system.reset()
        self.hit_effect = HitEffect()

    def _toggle_atype_map(self):
        """切换aType映射"""
        ATYPE_MAPS = [
            [1, 2, 4, 6, 7],
            [2, 1, 4, 7, 6],
            [6, 7, 4, 1, 2],
            [7, 6, 4, 2, 1],
        ]
        cur_idx = ATYPE_MAPS.index(self.sm_parser.atype_map) if self.sm_parser.atype_map in ATYPE_MAPS else 0
        cur_idx = (cur_idx + 1) % len(ATYPE_MAPS)
        self.sm_parser.atype_map = ATYPE_MAPS[cur_idx]

        # 重新构建箭头事件
        from sm_parser import build_arrow_events
        notes_block = self.sm_parser.notes_blocks[0] if self.sm_parser.notes_blocks else None
        if notes_block:
            event_table, _ = self.sm_parser.parse_arrow_events(notes_block)
            self.arrow_events = build_arrow_events(
                event_table,
                self.timeline_segments,
                self.sm_parser.tick_per_beat,
                self.sm_parser.atype_map
            )

        # 重置判定系统
        self.judge_system.reset()
        self.hit_effect = HitEffect()

    def _handle_mouse_click(self, pos, button):
        """处理鼠标点击"""
        if button != 1:  # 只处理左键
            return

        # 暂停菜单点击
        if self.game_state == GameState.PAUSED:
            menu_w, menu_h = 300, 250
            menu_x = (self.window_w - menu_w) // 2
            menu_y = (self.window_h - menu_h) // 2

            for i, option in enumerate(self.pause_menu_options):
                y = menu_y + 70 + i * 50
                rect = pygame.Rect(menu_x + 30, y, menu_w - 60, 40)

                if rect.collidepoint(pos):
                    if i == 0:  # 继续
                        self.resume()
                    elif i == 1:  # 重新开始
                        self.restart()
                    else:  # 返回选歌
                        self.end_reason = "back"
                        self.game_state = GameState.FINISHED
                    return

        # 结算界面点击
        elif self.game_state == GameState.FINISHED:
            self.end_reason = "back"
            self.game_state = GameState.FINISHED

        # 准备界面点击（开始游戏）
        elif self.game_state == GameState.READY:
            self.play()

    def _handle_mouse_motion(self, pos):
        """处理鼠标移动"""
        # 暂停菜单悬停
        if self.game_state == GameState.PAUSED:
            menu_w, menu_h = 300, 250
            menu_x = (self.window_w - menu_w) // 2
            menu_y = (self.window_h - menu_h) // 2

            for i in range(len(self.pause_menu_options)):
                y = menu_y + 70 + i * 50
                rect = pygame.Rect(menu_x + 30, y, menu_w - 60, 40)

                if rect.collidepoint(pos):
                    self.pause_menu_index = i
                    break

    def _update(self, dt: float):
        """更新游戏状态"""
        # 更新判定光效
        self.judge_light.update(dt)

        # 更新命中效果
        self.hit_effect.update(dt)

        # 更新判定显示
        self.judge_display.update(dt)

        # 更新按键状态
        key_map = self._get_key_map()
        keys = pygame.key.get_pressed()
        for key, track_idx in key_map.items():
            self.key_pressed[track_idx] = keys[key]

        if self.game_state == GameState.PLAYING:
            # 更新时间
            self.current_sec = time.perf_counter() - self.start_time

            # 检测MISS
            missed = self.judge_system.check_missed(self.arrow_events, self.current_sec)
            for idx in missed:
                self.judge_display.show(JudgeResult.MISS)

            # 检查结束
            if self.current_sec >= self.total_sec:
                self.current_sec = self.total_sec
                self._finish_game()

        elif self.game_state == GameState.FINISHED:
            self.result_display_time += dt

    def _finish_game(self):
        """游戏结束"""
        self.is_playing = False
        self.game_state = GameState.FINISHED
        self.end_reason = "finished"

        # 停止音频
        self.audio_manager.stop_music()

        # 生成结果
        self.result = GameResult(
            score=self.judge_system.score,
            max_combo=self.judge_system.max_combo,
            accuracy=self.judge_system.get_accuracy(),
            grade=self.judge_system.get_grade(),
            perfect=self.judge_system.stats.perfect,
            good=self.judge_system.stats.good,
            bad=self.judge_system.stats.bad,
            miss=self.judge_system.stats.miss
        )

    def _draw(self):
        """绘制画面"""
        # 绘制背景
        self._draw_background()

        if self.game_state == GameState.LOADING:
            self._draw_loading()
        elif self.game_state == GameState.READY:
            self._draw_ready()
        elif self.game_state in (GameState.PLAYING, GameState.PAUSED):
            self._draw_game()
            if self.game_state == GameState.PAUSED:
                self._draw_pause_menu()
        elif self.game_state == GameState.FINISHED:
            self._draw_game()
            self._draw_result()

    def _draw_background(self):
        """绘制背景"""
        # 封面背景
        if self.banner_surf:
            # 缩放封面
            banner_w, banner_h = self.banner_surf.get_size()
            window_ratio = self.window_w / self.window_h
            banner_ratio = banner_w / banner_h

            if window_ratio > banner_ratio:
                scale = self.window_w / banner_w
            else:
                scale = self.window_h / banner_h

            new_w = int(banner_w * scale)
            new_h = int(banner_h * scale)
            scaled_banner = pygame.transform.smoothscale(self.banner_surf, (new_w, new_h))

            # 居中绘制
            x = (self.window_w - new_w) // 2
            y = (self.window_h - new_h) // 2
            self.screen.blit(scaled_banner, (x, y))

            # 半透明遮罩
            overlay = pygame.Surface((self.window_w, self.window_h), pygame.SRCALPHA)
            overlay.fill((10, 10, 15, 200))
            self.screen.blit(overlay, (0, 0))
        else:
            # 渐变背景
            GlassRenderer.draw_gradient_background(
                self.screen,
                GlassColors.BG_TOP,
                GlassColors.BG_BOTTOM
            )

    def _draw_loading(self):
        """绘制加载界面"""
        if self.font_normal:
            text = "加载中..."
            surface = self.font_normal.render(text, True, GlassColors.TEXT_WHITE)
            rect = surface.get_rect(center=(self.window_w // 2, self.window_h // 2))
            self.screen.blit(surface, rect)

    def _draw_ready(self):
        """绘制准备界面"""
        if self.font_title:
            text = f"按空格键开始: {self.chart_title}"
            surface = self.font_title.render(text, True, GlassColors.TEXT_WHITE)
            rect = surface.get_rect(center=(self.window_w // 2, self.window_h // 2))
            self.screen.blit(surface, rect)

    def _draw_game(self):
        """绘制游戏画面"""
        # 布局计算
        margin = 20
        track_count = 5
        track_total_w = min(620, self.window_w - 280)
        track_total_w = max(400, track_total_w)
        track_start_x = (self.window_w - track_total_w) // 2
        single_track_w = track_total_w // track_count

        header_h = 80
        # 判定线位置：窗口高度的12% + header高度，更靠上让玩家有更多反应时间
        judge_y = int(self.window_h * 0.12) + header_h
        footer_h = 50

        # 绘制轨道背景
        self._draw_track_background(track_start_x, header_h, track_total_w,
                                    self.window_h - footer_h - header_h, single_track_w, track_count)

        # 绘制判定线
        self._draw_judge_line(track_start_x, track_total_w, judge_y)

        # 绘制判定区
        for i in range(track_count):
            self._draw_receptor(i, track_start_x, single_track_w, judge_y)

        # 绘制箭头
        self._draw_arrows(track_start_x, single_track_w, judge_y)

        # 绘制命中效果
        self._draw_hit_effects(track_start_x, single_track_w, judge_y)

        # 绘制判定显示
        self._draw_judge_display(judge_y)

        # 绘制顶部信息栏
        self._draw_header(header_h)

        # 绘制右侧统计面板
        self._draw_stats_panel(track_start_x + track_total_w + 15, header_h + 20)

        # 绘制底部提示
        self._draw_footer_tips(self.window_h - footer_h + 10)

    def _draw_track_background(self, start_x: int, start_y: int, width: int,
                               height: int, single_w: int, count: int):
        """绘制轨道背景"""
        for i in range(count):
            x = start_x + i * single_w
            # 轨道底色
            track_surf = pygame.Surface((single_w - 4, height), pygame.SRCALPHA)
            base_alpha = 80 + (i % 2) * 15
            track_surf.fill((25, 25, 35, base_alpha))
            self.screen.blit(track_surf, (x + 2, start_y))

            # 轨道边框
            border_color = (50, 50, 65) if i % 2 == 0 else (55, 55, 70)
            pygame.draw.rect(
                self.screen, border_color,
                (x + 2, start_y, single_w - 4, height),
                width=1, border_radius=8
            )

    def _draw_judge_line(self, track_start_x: int, track_total_w: int, judge_y: int):
        """绘制判定线"""
        # 主线
        pygame.draw.line(
            self.screen, (200, 200, 210),
            (track_start_x - 10, judge_y),
            (track_start_x + track_total_w + 10, judge_y),
            3
        )

        # 光晕
        for i in range(3):
            alpha = 60 - i * 15
            glow_surf = pygame.Surface((track_total_w + 20, 8), pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, (255, 255, 255, alpha), (0, 0, track_total_w + 20, 8))
            self.screen.blit(glow_surf, (track_start_x - 10, judge_y - 4 + i * 2))

    def _draw_receptor(self, track_idx: int, track_start_x: int,
                       single_track_w: int, judge_y: int):
        """绘制判定区"""
        center_x = track_start_x + track_idx * single_track_w + single_track_w // 2

        # 接近提示光晕 - 优化：使用索引遍历而非index()方法
        cur_sec = self.current_sec
        approaching = False
        for idx, event in enumerate(self.arrow_events):
            if self.judge_system.is_arrow_processed(idx):
                continue
            if event.track_idx != track_idx:
                continue
            time_diff = event.start_sec - cur_sec
            if -0.05 <= time_diff <= 0.15:
                approaching = True
                break

        if approaching:
            hint_surf = pygame.Surface((single_track_w, single_track_w), pygame.SRCALPHA)
            cx, cy = single_track_w // 2, single_track_w // 2
            for k in range(3):
                r = int(single_track_w * (0.25 + 0.1 * k))
                alpha = 60 - k * 15
                pygame.draw.circle(hint_surf, (100, 200, 255, max(0, alpha)), (cx, cy), r)
            self.screen.blit(hint_surf, (center_x - single_track_w // 2, judge_y - single_track_w // 2))

        # 判定光
        light_strength = self.judge_light.get_light(track_idx)
        if light_strength > 0:
            light_surf = pygame.Surface((single_track_w, single_track_w), pygame.SRCALPHA)
            cx, cy = single_track_w // 2, single_track_w // 2
            for k in range(5):
                r = int(single_track_w * (0.18 + 0.08 * k))
                alpha = int(light_strength * (140 - k * 22))
                pygame.draw.circle(light_surf, (255, 235, 185, max(0, alpha)), (cx, cy), r)
            self.screen.blit(light_surf, (center_x - single_track_w // 2, judge_y - single_track_w // 2))

        # 判定区皮肤
        receptor_surf = self.receptor_surfs[track_idx]
        if receptor_surf:
            base_w = int(single_track_w * 0.55)
            scale_factor = 0.85 if self.key_pressed[track_idx] else 1.0
            target_w = int(base_w * scale_factor)
            scale = target_w / float(max(1, receptor_surf.get_width()))
            target_h = int(receptor_surf.get_height() * scale)
            scale_surf = pygame.transform.smoothscale(receptor_surf, (target_w, target_h))
            y_offset = 3 if self.key_pressed[track_idx] else 0
            self.screen.blit(scale_surf, (center_x - target_w // 2, judge_y - target_h // 2 + y_offset))
        else:
            # 默认判定区
            radius = int(single_track_w * 0.22)
            if self.key_pressed[track_idx]:
                radius = int(radius * 0.85)
            color = (80, 80, 100) if self.key_pressed[track_idx] else (60, 60, 80)
            pygame.draw.circle(self.screen, color, (center_x, judge_y), radius)
            pygame.draw.circle(self.screen, (100, 100, 120), (center_x, judge_y), radius, 2)

    def _draw_arrows(self, track_start_x: int, single_track_w: int, judge_y: int):
        """绘制箭头"""
        bottom_y = self.window_h - 50
        top_y = 80
        visible_sec = (bottom_y - judge_y) / self.scroll_speed
        advance_sec = visible_sec + 1.0
        cur_sec = self.current_sec

        for idx, event in enumerate(self.arrow_events):
            # 跳过已处理的箭头（有命中效果的不跳过）
            if self.judge_system.is_arrow_processed(idx) and idx not in self.hit_effect._effects:
                continue

            if event.start_sec < cur_sec - 0.5 and event.end_sec < cur_sec - 0.5:
                continue
            if event.start_sec > cur_sec + advance_sec:
                break

            center_x = track_start_x + event.track_idx * single_track_w + single_track_w // 2
            dy_start = (event.start_sec - cur_sec) * self.scroll_speed
            y_start = judge_y + dy_start

            # 点按箭头
            if abs(event.end_sec - event.start_sec) < 1e-6:
                if y_start >= judge_y - 100 and y_start <= bottom_y:
                    self._draw_tap_arrow(event.track_idx, center_x, y_start, single_track_w, judge_y)
            # 长按箭头
            else:
                dy_end = (event.end_sec - cur_sec) * self.scroll_speed
                y_end = judge_y + dy_end
                self._draw_hold_arrow(event.track_idx, center_x, y_start, y_end, single_track_w, judge_y)

    def _draw_tap_arrow(self, track_idx: int, center_x: int, y: float,
                        single_track_w: int, judge_y: int):
        """绘制点按箭头"""
        if y < judge_y - 100 or y > self.window_h - 40:
            return

        tap_surf = self.tap_surfs[track_idx]
        if tap_surf:
            base_w = int(single_track_w * 0.60)
            base_w = max(22, base_w)
            target_w = base_w
            target_h = int(tap_surf.get_height() * (target_w / float(max(1, tap_surf.get_width()))))
            scale_surf = pygame.transform.smoothscale(tap_surf, (target_w, target_h))
            self.screen.blit(scale_surf, (center_x - target_w // 2, int(y) - target_h // 2))
        else:
            radius = max(9, min(22, single_track_w // 4))
            pygame.draw.circle(self.screen, (240, 240, 245), (center_x, int(y)), radius)
            pygame.draw.circle(self.screen, (20, 20, 25), (center_x, int(y)), radius, 3)

    def _draw_hold_arrow(self, track_idx: int, center_x: int, y_start: float,
                         y_end: float, single_track_w: int, judge_y: int):
        """绘制长按箭头"""
        orig_y1 = min(y_start, y_end)
        orig_y2 = max(y_start, y_end)

        y1 = max(orig_y1, float(judge_y))
        y2 = orig_y2

        if y2 < 50 or y1 > self.window_h - 40:
            return

        y1c = max(50.0, y1)
        y2c = min(float(self.window_h - 40), y2)
        if y2c <= y1c:
            return

        body_w = int(single_track_w * 0.50)
        body_w = max(20, body_w)

        # 绘制长按箭身
        hold_body_surf = self.hold_body_surfs[track_idx]
        body_height = int(y2c - y1c)
        if body_height > 0 and hold_body_surf:
            scale = body_w / float(max(1, hold_body_surf.get_width()))
            single_h = int(hold_body_surf.get_height() * scale)
            single_h = max(8, single_h)
            scale_surf = pygame.transform.smoothscale(hold_body_surf, (body_w, single_h))
            current_y = int(y1c)
            while current_y < int(y2c):
                remaining_h = int(y2c) - current_y
                if remaining_h >= single_h:
                    self.screen.blit(scale_surf, (center_x - body_w // 2, current_y))
                    current_y += single_h
                else:
                    last_surf = pygame.transform.smoothscale(hold_body_surf, (body_w, remaining_h))
                    self.screen.blit(last_surf, (center_x - body_w // 2, current_y))
                    break
        elif body_height > 0:
            rect = pygame.Rect(center_x - body_w // 2, int(y1c), body_w, body_height)
            pygame.draw.rect(self.screen, (180, 180, 200), rect, border_radius=8)
            pygame.draw.rect(self.screen, (40, 40, 50), rect, width=2, border_radius=8)

        # 绘制长按箭尾
        hold_tail_surf = self.hold_tail_surfs[track_idx]
        tail_y = min(orig_y2, float(self.window_h - 40))
        if tail_y >= judge_y and tail_y >= 50:
            if hold_tail_surf:
                tail_w = int(single_track_w * 0.55)
                tail_w = max(22, tail_w)
                scale = tail_w / float(max(1, hold_tail_surf.get_width()))
                tail_h = int(hold_tail_surf.get_height() * scale)
                tail_surf = pygame.transform.smoothscale(hold_tail_surf, (tail_w, tail_h))
                self.screen.blit(tail_surf, (center_x - tail_w // 2, int(tail_y) - tail_h // 2))
            else:
                tail_w = int(single_track_w * 0.35)
                tail_h = max(8, tail_w // 2)
                tail_rect = pygame.Rect(center_x - tail_w // 2, int(tail_y) - tail_h, tail_w, tail_h)
                pygame.draw.rect(self.screen, (160, 160, 180), tail_rect, border_radius=4)

        # 绘制长按头部
        if orig_y1 >= judge_y:
            self._draw_tap_arrow(track_idx, center_x, orig_y1, single_track_w, judge_y)

    def _draw_hit_effects(self, track_start_x: int, single_track_w: int, judge_y: int):
        """绘制命中效果"""
        for idx, effect in self.hit_effect.get_effects().items():
            if idx >= len(self.arrow_events):
                continue
            event = self.arrow_events[idx]
            center_x = track_start_x + event.track_idx * single_track_w + single_track_w // 2
            y_pos = judge_y - effect["y"] * (1 - effect["alpha"] * 0.5)
            self._draw_tap_arrow_with_effect(
                event.track_idx, center_x, y_pos,
                single_track_w, judge_y,
                effect["alpha"], effect["scale"]
            )

    def _draw_tap_arrow_with_effect(self, track_idx: int, center_x: int, y: float,
                                     single_track_w: int, judge_y: int,
                                     alpha: float, scale: float):
        """绘制带效果的点按箭头"""
        if y < judge_y - 100 or y > self.window_h - 40:
            return

        tap_surf = self.tap_surfs[track_idx]
        if tap_surf:
            base_w = int(single_track_w * 0.60)
            base_w = max(22, base_w)
            target_w = int(base_w * scale)
            target_h = int(tap_surf.get_height() * (target_w / float(max(1, tap_surf.get_width()))))
            scale_surf = pygame.transform.smoothscale(tap_surf, (target_w, target_h))

            alpha_surf = pygame.Surface((target_w, target_h), pygame.SRCALPHA)
            alpha_surf.blit(scale_surf, (0, 0))
            alpha_surf.set_alpha(int(alpha * 255))
            self.screen.blit(alpha_surf, (center_x - target_w // 2, int(y) - target_h // 2))
        else:
            radius = int(max(9, min(22, single_track_w // 4)) * scale)
            color = (240, 240, 245, int(alpha * 255))
            surf = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(surf, color, (radius + 2, radius + 2), radius)
            self.screen.blit(surf, (center_x - radius - 2, int(y) - radius - 2))

    def _draw_judge_display(self, judge_y: int):
        """绘制判定显示"""
        if not self.judge_display.is_showing():
            return

        result = self.judge_display.current_result
        if not result:
            return

        color = self.judge_system.get_result_color(result)
        alpha = self.judge_display.get_alpha()
        color = tuple(int(c * alpha) for c in color)

        if self.font_judge:
            text_surface = self.font_judge.render(result.value, True, color)
            text_rect = text_surface.get_rect(center=(self.window_w // 2, judge_y + 100))
            self.screen.blit(text_surface, text_rect)

    def _draw_header(self, header_h: int):
        """绘制顶部信息栏"""
        # 玻璃面板背景
        header_surf = pygame.Surface((self.window_w - 40, header_h - 10), pygame.SRCALPHA)
        header_surf.fill((20, 20, 28, 180))
        self.screen.blit(header_surf, (20, 10))

        # 歌曲标题
        if self.font_title:
            title_text = self.chart_title[:30] + "..." if len(self.chart_title) > 30 else self.chart_title
            title_surface = self.font_title.render(title_text, True, GlassColors.TEXT_WHITE)
            self.screen.blit(title_surface, (30, 15))

        # 时间和状态
        time_str = f"{format_seconds(self.current_sec)} / {format_seconds(self.total_sec)}"
        status_str = "播放中" if self.is_playing else "已暂停"
        status_color = GlassColors.PERFECT if self.is_playing else (255, 200, 100)

        if self.font_normal:
            time_surface = self.font_normal.render(time_str, True, GlassColors.TEXT_GRAY)
            self.screen.blit(time_surface, (30, 50))

            status_surface = self.font_normal.render(status_str, True, status_color)
            self.screen.blit(status_surface, (200, 50))

        # 右侧参数
        if self.font_small:
            params = [
                f"速度: {int(self.scroll_speed)}",
                f"Offset: {self.chart_offset:+.2f}s",
                f"Tick: {self.sm_parser.tick_per_beat}"
            ]
            for i, param in enumerate(params):
                param_surface = self.font_small.render(param, True, GlassColors.TEXT_DARK)
                self.screen.blit(param_surface, (self.window_w - 120, 18 + i * 22))

    def _draw_stats_panel(self, panel_x: int, panel_y: int):
        """绘制右侧统计面板"""
        panel_w = 130
        panel_h = 220

        # 玻璃面板背景
        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((15, 15, 22, 200))
        pygame.draw.rect(panel_surf, (50, 50, 70), (0, 0, panel_w, panel_h), border_radius=10)
        self.screen.blit(panel_surf, (panel_x, panel_y))

        # 标题
        if self.font_normal:
            title_surface = self.font_normal.render("统计", True, GlassColors.TEXT_WHITE)
            self.screen.blit(title_surface, (panel_x + 10, panel_y + 8))

        # 判定统计
        if self.font_small:
            stats = [
                ("PERFECT", self.judge_system.stats.perfect, GlassColors.PERFECT),
                ("GOOD", self.judge_system.stats.good, GlassColors.GOOD),
                ("BAD", self.judge_system.stats.bad, GlassColors.BAD),
                ("MISS", self.judge_system.stats.miss, GlassColors.MISS),
            ]
            for i, (label, count, color) in enumerate(stats):
                y = panel_y + 38 + i * 28
                label_surface = self.font_small.render(label, True, color)
                self.screen.blit(label_surface, (panel_x + 10, y))
                count_surface = self.font_small.render(str(count), True, GlassColors.TEXT_WHITE)
                self.screen.blit(count_surface, (panel_x + 90, y))

            # 分数
            score_surface = self.font_normal.render(f"{self.judge_system.score}", True, (255, 220, 100))
            self.screen.blit(score_surface, (panel_x + 10, panel_y + 150))

            # 连击
            combo_color = GlassColors.PERFECT if self.judge_system.combo > 10 else GlassColors.TEXT_GRAY
            combo_surface = self.font_small.render(f"Combo: {self.judge_system.combo}", True, combo_color)
            self.screen.blit(combo_surface, (panel_x + 10, panel_y + 175))

            # 最大连击
            max_surface = self.font_small.render(f"Max: {self.judge_system.max_combo}", True, GlassColors.TEXT_DARK)
            self.screen.blit(max_surface, (panel_x + 75, panel_y + 175))

    def _draw_footer_tips(self, y: int):
        """绘制底部提示"""
        if not self.font_small:
            return

        tips = "空格:暂停  R:重播  ←/→:快退快进  [/]:速度  -/=:Offset  T:Tick  M:映射  Esc:菜单"
        tip_surface = self.font_small.render(tips, True, GlassColors.TEXT_DARK)
        self.screen.blit(tip_surface, (20, y))

    def _draw_pause_menu(self):
        """绘制暂停菜单"""
        # 半透明遮罩
        overlay = pygame.Surface((self.window_w, self.window_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        # 菜单面板
        menu_w, menu_h = 300, 250
        menu_x = (self.window_w - menu_w) // 2
        menu_y = (self.window_h - menu_h) // 2

        GlassRenderer.draw_glass_card(
            self.screen,
            pygame.Rect(menu_x, menu_y, menu_w, menu_h),
            corner_radius=25,
            alpha=80
        )

        # 标题
        if self.font_title:
            title_surface = self.font_title.render("暂停", True, GlassColors.TEXT_WHITE)
            title_rect = title_surface.get_rect(centerx=self.window_w // 2, y=menu_y + 20)
            self.screen.blit(title_surface, title_rect)

        # 菜单选项
        for i, option in enumerate(self.pause_menu_options):
            y = menu_y + 70 + i * 50
            rect = pygame.Rect(menu_x + 30, y, menu_w - 60, 40)

            is_selected = (i == self.pause_menu_index)
            GlassRenderer.draw_glass_button(
                self.screen,
                rect,
                option,
                self.font_normal,
                corner_radius=15,
                hover=is_selected,
                active=is_selected
            )

    def _draw_result(self):
        """绘制结算界面"""
        if not self.result:
            return

        # 半透明遮罩
        overlay = pygame.Surface((self.window_w, self.window_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        # 结算面板
        panel_w, panel_h = 400, 350
        panel_x = (self.window_w - panel_w) // 2
        panel_y = (self.window_h - panel_h) // 2

        GlassRenderer.draw_glass_card(
            self.screen,
            pygame.Rect(panel_x, panel_y, panel_w, panel_h),
            corner_radius=25,
            alpha=90
        )

        # 标题
        if self.font_title:
            title_surface = self.font_title.render("结算", True, GlassColors.TEXT_WHITE)
            title_rect = title_surface.get_rect(centerx=self.window_w // 2, y=panel_y + 20)
            self.screen.blit(title_surface, title_rect)

        # 评级
        grade_colors = {
            "S": (255, 215, 0),
            "AAA": (255, 180, 0),
            "AA": (255, 150, 0),
            "A": (100, 255, 100),
            "B": (100, 200, 255),
            "C": (150, 150, 200),
            "D": (200, 150, 150),
            "F": (150, 150, 150),
        }
        grade_color = grade_colors.get(self.result.grade, GlassColors.TEXT_WHITE)

        # 评级大字
        if self.font_judge:
            grade_surface = self.font_judge.render(self.result.grade, True, grade_color)
            grade_rect = grade_surface.get_rect(centerx=self.window_w // 2, y=panel_y + 60)
            self.screen.blit(grade_surface, grade_rect)

        # 分数
        if self.font_title:
            score_text = f"Score: {self.result.score}"
            score_surface = self.font_title.render(score_text, True, GlassColors.TEXT_WHITE)
            score_rect = score_surface.get_rect(centerx=self.window_w // 2, y=panel_y + 130)
            self.screen.blit(score_surface, score_rect)

        # 判定统计
        if self.font_normal:
            stats = [
                (f"PERFECT: {self.result.perfect}", GlassColors.PERFECT),
                (f"GOOD: {self.result.good}", GlassColors.GOOD),
                (f"BAD: {self.result.bad}", GlassColors.BAD),
                (f"MISS: {self.result.miss}", GlassColors.MISS),
            ]
            for i, (text, color) in enumerate(stats):
                stat_surface = self.font_normal.render(text, True, color)
                stat_rect = stat_surface.get_rect(centerx=self.window_w // 2, y=panel_y + 170 + i * 25)
                self.screen.blit(stat_surface, stat_rect)

        # 连击和准确率
        if self.font_normal:
            combo_text = f"Max Combo: {self.result.max_combo}"
            accuracy_text = f"Accuracy: {self.result.accuracy * 100:.1f}%"

            combo_surface = self.font_normal.render(combo_text, True, GlassColors.TEXT_WHITE)
            combo_rect = combo_surface.get_rect(centerx=self.window_w // 2, y=panel_y + 280)
            self.screen.blit(combo_surface, combo_rect)

            acc_surface = self.font_normal.render(accuracy_text, True, GlassColors.TEXT_WHITE)
            acc_rect = acc_surface.get_rect(centerx=self.window_w // 2, y=panel_y + 305)
            self.screen.blit(acc_surface, acc_rect)

    def _cleanup(self):
        """清理资源"""
        # 停止音频
        self.audio_manager.stop_music()

        # 关闭皮肤
        self.skin.close()

        # 退出Pygame
        try:
            pygame.quit()
        except Exception:
            pass
