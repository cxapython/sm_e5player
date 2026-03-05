# -*- coding: utf-8 -*-
"""
SM Arrow Player - 主程序入口
基于Python Pygame的E舞成名（StepMania）谱面播放器
实现玻璃拟态UI风格的选歌和播放体验
"""

import os
import sys
import time
from enum import Enum
from typing import Optional, Dict, Any

# 检查依赖
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("错误: 缺少 pygame 库，请运行: pip install pygame>=2.0.0")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("警告: 缺少 Pillow 库，封面显示受限，请运行: pip install Pillow")

# 导入项目模块
from config_manager import ConfigManager
from directory_parser import DirectoryParser, SongInfo
from song_scanner import SongScanner
from audio_manager import AudioManager, get_audio_manager
from song_select import SongSelectScene
from chart_player import ChartPlayer


class GameState(Enum):
    """游戏状态枚举"""
    LOADING = "loading"
    PATH_SELECT = "path_select"
    SONG_SELECT = "song_select"
    PLAYING = "playing"
    ERROR = "error"


class Game:
    """
    游戏主类

    职责：
    - 初始化Pygame和核心模块
    - 管理游戏状态和界面切换
    - 处理全局事件
    - 协调各个场景
    """

    def __init__(self):
        """初始化游戏"""
        # 检查依赖
        if not PYGAME_AVAILABLE:
            raise RuntimeError("缺少必要的依赖库: pygame")

        # 配置管理器
        self.config = ConfigManager()

        # 音频管理器
        self.audio_manager = get_audio_manager()

        # 歌曲扫描器
        self.scanner = SongScanner()

        # 游戏状态
        self.state = GameState.LOADING
        self.previous_state: Optional[GameState] = None
        self.state_data: Dict[str, Any] = {}

        # Pygame
        self.screen: Optional[pygame.Surface] = None
        self.clock: Optional[pygame.time.Clock] = None
        self.fps = self.config.get_fps()

        # 场景
        self.scenes: Dict[str, Any] = {}
        self.current_scene: Optional[Any] = None

        # 错误信息
        self.error_message = ""

        # 运行标志
        self.running = False

    def init_pygame(self):
        """初始化Pygame"""
        # 启用高DPI支持（在init之前设置）
        import platform
        if platform.system() == "Darwin":  # macOS
            os.environ["SDL_HINT_VIDEO_HIGHDPI_DISABLED"] = "0"

        pygame.init()
        pygame.font.init()

        # 创建窗口
        window_size = self.config.get_window_size()
        self.screen = pygame.display.set_mode(
            window_size,
            pygame.RESIZABLE | pygame.HWSURFACE | pygame.DOUBLEBUF
        )
        pygame.display.set_caption("SM Arrow Player")

        # 时钟
        self.clock = pygame.time.Clock()

        # 设置音频
        self.audio_manager.set_master_volume(self.config.get_master_volume())

    def run(self):
        """运行游戏主循环"""
        try:
            # 初始化Pygame
            self.init_pygame()

            # 检查是否首次运行
            if self.config.is_first_run():
                self._switch_state(GameState.PATH_SELECT)
            else:
                # 加载歌曲
                self._load_songs()
                self._switch_state(GameState.SONG_SELECT)

            # 主循环
            self.running = True
            while self.running:
                dt = self.clock.tick(self.fps) / 1000.0

                # 事件处理
                self._handle_events()

                # 更新
                self._update(dt)

                # 绘制
                self._draw()

                pygame.display.flip()

        except Exception as e:
            print(f"[Game] 运行错误: {e}")
            import traceback
            traceback.print_exc()
            self._show_error(str(e))

        finally:
            self._cleanup()

    def _handle_events(self):
        """处理事件"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.VIDEORESIZE:
                self._handle_resize(event.w, event.h)

            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)

            # 传递给当前场景
            if self.current_scene and hasattr(self.current_scene, 'handle_event'):
                self.current_scene.handle_event(event)

    def _handle_keydown(self, key):
        """处理全局按键"""
        # F11切换全屏
        if key == pygame.K_F11:
            self._toggle_fullscreen()

    def _handle_resize(self, width: int, height: int):
        """处理窗口大小改变"""
        width = max(800, width)
        height = max(600, height)

        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        self.config.set_window_size(width, height, auto_save=False)

        # 通知当前场景
        if self.current_scene and hasattr(self.current_scene, 'handle_resize'):
            self.current_scene.handle_resize(width, height)

    def _toggle_fullscreen(self):
        """切换全屏"""
        if self.config.is_fullscreen():
            pygame.display.set_mode(self.config.get_window_size(), pygame.RESIZABLE)
            self.config.set_fullscreen(False)
        else:
            pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            self.config.set_fullscreen(True)

    def _update(self, dt: float):
        """更新游戏状态"""
        # 更新音频管理器
        self.audio_manager.update_spectrum()

        # 更新当前场景
        if self.current_scene and hasattr(self.current_scene, 'update'):
            self.current_scene.update(dt)

    def _draw(self):
        """绘制画面"""
        if self.current_scene and hasattr(self.current_scene, 'draw'):
            self.current_scene.draw()
        elif self.state == GameState.LOADING:
            self._draw_loading()
        elif self.state == GameState.PATH_SELECT:
            self._draw_path_select()
        elif self.state == GameState.ERROR:
            self._draw_error()

    def _draw_loading(self):
        """绘制加载界面"""
        from ui_glass import GlassRenderer, GlassColors

        # 背景
        GlassRenderer.draw_gradient_background(self.screen, GlassColors.BG_TOP, GlassColors.BG_BOTTOM)

        # 加载文字
        font = GlassRenderer.load_font(24)
        if font:
            text = font.render("正在加载...", True, GlassColors.TEXT_WHITE)
            rect = text.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2))
            self.screen.blit(text, rect)

    def _draw_path_select(self):
        """绘制路径选择界面"""
        from ui_glass import GlassRenderer, GlassColors

        # 背景
        GlassRenderer.draw_gradient_background(self.screen, GlassColors.BG_TOP, GlassColors.BG_BOTTOM)

        font_title = GlassRenderer.load_font(28)
        font_normal = GlassRenderer.load_font(18)

        # 标题
        if font_title:
            title = font_title.render("欢迎使用 SM Arrow Player", True, GlassColors.TEXT_WHITE)
            title_rect = title.get_rect(centerx=self.screen.get_width() // 2, y=100)
            self.screen.blit(title, title_rect)

        # 说明
        if font_normal:
            desc = font_normal.render("首次运行，请选择歌曲目录", True, GlassColors.TEXT_GRAY)
            desc_rect = desc.get_rect(centerx=self.screen.get_width() // 2, y=150)
            self.screen.blit(desc, desc_rect)

        # 提示
        if font_normal:
            tip = font_normal.render("点击窗口任意位置选择目录", True, GlassColors.TEXT_DARK)
            tip_rect = tip.get_rect(centerx=self.screen.get_width() // 2, y=self.screen.get_height() - 100)
            self.screen.blit(tip, tip_rect)

    def _draw_error(self):
        """绘制错误界面"""
        from ui_glass import GlassRenderer, GlassColors

        # 背景
        GlassRenderer.draw_gradient_background(self.screen, GlassColors.BG_TOP, GlassColors.BG_BOTTOM)

        font_title = GlassRenderer.load_font(24)
        font_normal = GlassRenderer.load_font(16)

        # 错误标题
        if font_title:
            title = font_title.render("出错了", True, (255, 100, 100))
            title_rect = title.get_rect(centerx=self.screen.get_width() // 2, y=100)
            self.screen.blit(title, title_rect)

        # 错误信息
        if font_normal:
            # 截断错误信息
            error_text = self.error_message[:100] + "..." if len(self.error_message) > 100 else self.error_message
            error = font_normal.render(error_text, True, GlassColors.TEXT_GRAY)
            error_rect = error.get_rect(centerx=self.screen.get_width() // 2, y=150)
            self.screen.blit(error, error_rect)

        # 提示
        if font_normal:
            tip = font_normal.render("按 ESC 退出", True, GlassColors.TEXT_DARK)
            tip_rect = tip.get_rect(centerx=self.screen.get_width() // 2, y=self.screen.get_height() - 100)
            self.screen.blit(tip, tip_rect)

    def _show_error(self, message: str):
        """显示错误"""
        self.error_message = message
        self.state = GameState.ERROR

    def _switch_state(self, new_state: GameState, **kwargs):
        """切换游戏状态"""
        self.previous_state = self.state
        self.state = new_state
        self.state_data = kwargs

        print(f"[Game] 状态切换: {self.previous_state} -> {self.state}")

        if new_state == GameState.PATH_SELECT:
            self._init_path_select()

        elif new_state == GameState.SONG_SELECT:
            self._init_song_select()

        elif new_state == GameState.PLAYING:
            self._start_playing(**kwargs)

    def _init_path_select(self):
        """初始化路径选择"""
        pass  # 简化处理，使用文件对话框

    def _init_song_select(self):
        """初始化选歌界面"""
        self.current_scene = SongSelectScene(
            self.screen,
            self.config,
            self.audio_manager
        )

        # 加载歌曲
        self.current_scene.load_songs(self.scanner.songs)

        # 恢复上次页码
        last_page = self.config.get_last_page()
        if last_page > 0:
            self.current_scene.go_to_page(last_page)

        # 设置回调
        self.current_scene.set_on_song_select(self._on_song_selected)

    def _on_song_selected(self, song: SongInfo):
        """歌曲选择回调"""
        if not song.has_sm:
            return

        # 停止预览
        self.audio_manager.stop_preview()

        # 保存状态
        self.config.set_last_sm_file(song.sm_file)
        self.config.set_last_page(self.current_scene.current_page)
        self.config.save()

        # 切换到播放状态
        self._switch_state(GameState.PLAYING, song=song)

    def _start_playing(self, song: SongInfo):
        """开始播放"""
        # 获取皮肤目录
        app_dir = os.path.dirname(os.path.abspath(__file__))
        skin_dir = os.path.join(app_dir, "noteskin")

        if not os.path.isdir(skin_dir):
            self._show_error(f"皮肤目录不存在：{skin_dir}")
            return

        # 创建播放器
        try:
            player = ChartPlayer(
                song.sm_file,
                song.audio_file,
                skin_dir,
                self.config,
                self.audio_manager
            )

            if not player.load():
                self._show_error("谱面加载失败")
                return

            player.init_pygame()

            # 运行播放器
            end_reason = player.run()

            # 播放结束，返回选歌
            self._return_to_song_select()

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._show_error(f"播放失败：{str(e)}")

    def _return_to_song_select(self):
        """返回选歌界面"""
        # 重新初始化Pygame（播放器可能已退出）
        self.init_pygame()

        # 切换到选歌状态
        self._switch_state(GameState.SONG_SELECT)

    def _load_songs(self):
        """加载歌曲列表"""
        scan_path = self.config.get_scan_path()
        if scan_path:
            self.scanner.scan_path = scan_path
            self.scanner.scan()

    def _show_path_dialog(self) -> Optional[str]:
        """显示路径选择对话框"""
        # 使用pygame实现简单的路径输入
        # 或者使用tkinter的文件对话框
        try:
            import tkinter.filedialog as fd
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()

            path = fd.askdirectory(
                title="选择歌曲目录",
                initialdir=self.config.get_scan_path() or os.path.expanduser("~")
            )

            root.destroy()
            return path if path else None

        except Exception as e:
            print(f"[Game] 文件对话框失败: {e}")
            return None

    def _cleanup(self):
        """清理资源"""
        # 保存配置
        self.config.save()

        # 清理音频
        self.audio_manager.cleanup()

        # 退出Pygame
        try:
            pygame.quit()
        except Exception:
            pass


def main():
    """程序入口"""
    # 检查Python版本
    if sys.version_info < (3, 8):
        print("错误: 需要Python 3.8或更高版本")
        sys.exit(1)

    # 打印欢迎信息
    print("=" * 50)
    print("SM Arrow Player")
    print("E舞成名谱面播放器 - Python Pygame版")
    print("=" * 50)

    # 创建游戏实例
    game = Game()

    # 检查首次运行
    if game.config.is_first_run():
        # 显示路径选择
        path = game._show_path_dialog()
        if path and os.path.isdir(path):
            game.config.set_scan_path(path)
            game.config.save()
        else:
            print("未选择目录，程序退出")
            sys.exit(0)

    # 运行游戏
    game.run()


if __name__ == "__main__":
    main()
