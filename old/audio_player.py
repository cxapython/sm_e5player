# -*- coding: utf-8 -*-
"""
音频预览模块
负责悬浮音频预览播放功能
"""

import os
import threading
import time
from typing import Optional, Callable

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False


class AudioPreviewPlayer:
    """音频预览播放器，支持悬浮自动播放"""

    def __init__(self):
        """初始化音频播放器"""
        self.current_file: Optional[str] = None
        self.is_playing: bool = False
        self.is_initialized: bool = False
        self.volume: float = 0.8
        self._preview_thread: Optional[threading.Thread] = None
        self._stop_flag: bool = False
        self._hover_timer: Optional[float] = None
        self._hover_delay: float = 0.5  # 悬停0.5秒后开始播放

        # 初始化pygame音频
        self._init_audio()

    def _init_audio(self):
        """初始化pygame音频系统"""
        if not PYGAME_AVAILABLE:
            print("[AudioPreviewPlayer] pygame不可用，音频预览功能禁用")
            return

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.is_initialized = True
        except Exception as e:
            print(f"[AudioPreviewPlayer] 音频初始化失败: {e}")
            self.is_initialized = False

    def play(self, audio_path: str) -> bool:
        """
        播放音频文件

        :param audio_path: 音频文件路径
        :return: 是否成功开始播放
        """
        if not self.is_initialized or not PYGAME_AVAILABLE:
            return False

        if not audio_path or not os.path.exists(audio_path):
            return False

        try:
            # 停止当前播放
            self.stop()

            # 加载并播放
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.set_volume(self.volume)
            pygame.mixer.music.play()

            self.current_file = audio_path
            self.is_playing = True
            return True

        except Exception as e:
            print(f"[AudioPreviewPlayer] 播放失败: {e}")
            self.is_playing = False
            return False

    def stop(self):
        """停止播放"""
        if not self.is_initialized or not PYGAME_AVAILABLE:
            return

        try:
            pygame.mixer.music.stop()
            self.is_playing = False
            self.current_file = None
        except Exception:
            pass

    def pause(self):
        """暂停播放"""
        if not self.is_initialized or not PYGAME_AVAILABLE:
            return

        try:
            pygame.mixer.music.pause()
            self.is_playing = False
        except Exception:
            pass

    def resume(self):
        """恢复播放"""
        if not self.is_initialized or not PYGAME_AVAILABLE:
            return

        try:
            pygame.mixer.music.unpause()
            self.is_playing = True
        except Exception:
            pass

    def set_volume(self, volume: float):
        """
        设置音量

        :param volume: 音量值（0.0-1.0）
        """
        self.volume = max(0.0, min(1.0, volume))

        if self.is_initialized and PYGAME_AVAILABLE:
            try:
                pygame.mixer.music.set_volume(self.volume)
            except Exception:
                pass

    def get_volume(self) -> float:
        """获取当前音量"""
        return self.volume

    def is_busy(self) -> bool:
        """检查是否正在播放"""
        if not self.is_initialized or not PYGAME_AVAILABLE:
            return False

        try:
            return pygame.mixer.music.get_busy()
        except Exception:
            return False

    def start_hover_preview(self, audio_path: str, callback: Optional[Callable] = None):
        """
        开始悬停预览计时

        :param audio_path: 音频文件路径
        :param callback: 播放开始时的回调函数
        """
        # 如果已经在播放同一首歌，不处理
        if self.current_file == audio_path and self.is_playing:
            return

        # 取消之前的计时
        self.cancel_hover_preview()

        # 记录悬停开始时间
        self._hover_timer = time.time()

        # 启动延迟播放线程
        self._stop_flag = False
        self._preview_thread = threading.Thread(
            target=self._delayed_play,
            args=(audio_path, callback),
            daemon=True
        )
        self._preview_thread.start()

    def _delayed_play(self, audio_path: str, callback: Optional[Callable] = None):
        """延迟播放（在后台线程中执行）"""
        # 等待悬停延迟
        elapsed = 0.0
        while elapsed < self._hover_delay and not self._stop_flag:
            time.sleep(0.05)
            elapsed += 0.05

        # 如果未被取消，开始播放
        if not self._stop_flag and audio_path:
            if self.play(audio_path) and callback:
                callback()

    def cancel_hover_preview(self):
        """取消悬停预览"""
        self._stop_flag = True
        self._hover_timer = None

        # 等待线程结束
        if self._preview_thread and self._preview_thread.is_alive():
            self._preview_thread.join(timeout=0.2)

        self._preview_thread = None

    def cleanup(self):
        """清理资源"""
        self.stop()
        self.cancel_hover_preview()

        if self.is_initialized and PYGAME_AVAILABLE:
            try:
                pygame.mixer.music.unload()
            except Exception:
                pass


# 全局单例
_audio_player_instance: Optional[AudioPreviewPlayer] = None


def get_audio_player() -> AudioPreviewPlayer:
    """获取全局音频播放器实例"""
    global _audio_player_instance
    if _audio_player_instance is None:
        _audio_player_instance = AudioPreviewPlayer()
    return _audio_player_instance
