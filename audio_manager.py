# -*- coding: utf-8 -*-
"""
音频管理模块（增强版）
负责音频播放、预览、音效和频谱可视化
"""

import os
import threading
import time
import math
from typing import Optional, Callable, List
from dataclasses import dataclass

try:
    import pygame
    import pygame.mixer
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("[AudioManager] pygame不可用，音频功能禁用")


@dataclass
class AudioConfig:
    """音频配置"""
    master_volume: float = 0.8
    music_volume: float = 1.0
    sfx_volume: float = 0.8
    preview_duration: float = 10.0  # 预览时长（秒）
    preview_delay: float = 0.5      # 悬停延迟（秒）


class SpectrumAnalyzer:
    """频谱分析器（模拟效果，用于可视化）"""

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
        self.enabled = True

    def update(self, is_playing: bool, beat_intensity: float = 0.5):
        """
        更新频谱数据

        Args:
            is_playing: 是否正在播放
            beat_intensity: 节拍强度 (0.0-1.0)
        """
        if not self.enabled:
            self.bars = [0.0] * self.bar_count
            return

        import random

        if not is_playing:
            # 衰减到0
            self.bars = [b * self.decay for b in self.bars]
            return

        # 模拟频谱数据（随机生成，根据节拍强度变化）
        for i in range(self.bar_count):
            # 低频部分更强
            freq_factor = 1.0 - (i / self.bar_count) * 0.5
            base_intensity = beat_intensity * freq_factor

            if random.random() > 0.7:
                # 随机峰值
                self.target_bars[i] = base_intensity * random.uniform(0.7, 1.0)
            else:
                self.target_bars[i] = base_intensity * random.uniform(0.3, 0.6)

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

    def set_enabled(self, enabled: bool):
        """设置是否启用"""
        self.enabled = enabled


class AudioManager:
    """
    统一音频管理器

    功能：
    - 音乐播放控制（播放、暂停、停止、音量）
    - 预览播放（悬停延迟、限时播放）
    - 音效播放（点击音、判定音）
    - 频谱可视化（模拟效果）
    """

    # 音效类型
    SFX_GLASS_CLICK = "glass_click"
    SFX_CONFIRM = "confirm"
    SFX_PERFECT = "perfect"
    SFX_GOOD = "good"
    SFX_BAD = "bad"
    SFX_MISS = "miss"

    def __init__(self, config: AudioConfig = None):
        """
        初始化音频管理器

        Args:
            config: 音频配置
        """
        self.config = config or AudioConfig()
        self.is_initialized = False

        # 播放状态
        self.current_music: Optional[str] = None
        self.is_playing = False
        self.is_paused = False
        self.music_volume = self.config.music_volume

        # 预览状态
        self.preview_thread: Optional[threading.Thread] = None
        self.preview_stop_flag = False
        self.preview_timer: Optional[float] = None
        self.preview_delay = self.config.preview_delay

        # 频谱分析器
        self.spectrum = SpectrumAnalyzer(bar_count=32)

        # 音效缓存
        self._sfx_cache: dict = {}

        # 初始化
        self._init_audio()

    def _init_audio(self):
        """初始化音频系统"""
        if not PYGAME_AVAILABLE:
            return

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self.is_initialized = True
        except Exception as e:
            print(f"[AudioManager] 音频初始化失败: {e}")
            self.is_initialized = False

    def load_music(self, file_path: str) -> bool:
        """
        加载音乐文件

        Args:
            file_path: 音频文件路径

        Returns:
            是否成功
        """
        if not self.is_initialized or not PYGAME_AVAILABLE:
            return False

        if not file_path or not os.path.exists(file_path):
            return False

        try:
            # 停止当前播放
            self.stop_music()

            # 加载新文件
            pygame.mixer.music.load(file_path)
            self.current_music = file_path
            return True
        except Exception as e:
            print(f"[AudioManager] 加载音乐失败: {e}")
            return False

    def play_music(self, start_pos: float = 0.0, loops: int = -1):
        """
        播放音乐

        Args:
            start_pos: 起始位置（秒）
            loops: 循环次数，-1为无限循环
        """
        if not self.is_initialized or not PYGAME_AVAILABLE:
            return

        try:
            volume = self.config.master_volume * self.music_volume
            pygame.mixer.music.set_volume(volume)

            if start_pos > 0:
                pygame.mixer.music.play(loops=loops, start=start_pos)
            else:
                pygame.mixer.music.play(loops=loops)

            self.is_playing = True
            self.is_paused = False
        except Exception as e:
            print(f"[AudioManager] 播放失败: {e}")

    def pause_music(self):
        """暂停音乐"""
        if not self.is_initialized or not PYGAME_AVAILABLE:
            return

        try:
            pygame.mixer.music.pause()
            self.is_paused = True
            self.is_playing = False
        except Exception:
            pass

    def resume_music(self):
        """恢复音乐"""
        if not self.is_initialized or not PYGAME_AVAILABLE:
            return

        try:
            pygame.mixer.music.unpause()
            self.is_paused = False
            self.is_playing = True
        except Exception:
            pass

    def stop_music(self):
        """停止音乐"""
        if not self.is_initialized or not PYGAME_AVAILABLE:
            return

        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except Exception:
            pass

        self.is_playing = False
        self.is_paused = False
        self.current_music = None

    def set_music_volume(self, volume: float):
        """设置音乐音量"""
        self.music_volume = max(0.0, min(1.0, volume))

        if self.is_initialized and PYGAME_AVAILABLE and self.is_playing:
            try:
                pygame.mixer.music.set_volume(self.config.master_volume * self.music_volume)
            except Exception:
                pass

    def set_master_volume(self, volume: float):
        """设置主音量"""
        self.config.master_volume = max(0.0, min(1.0, volume))
        self.set_music_volume(self.music_volume)

    def get_position(self) -> float:
        """获取当前播放位置（秒）"""
        if not self.is_initialized or not PYGAME_AVAILABLE:
            return 0.0

        try:
            return pygame.mixer.music.get_pos() / 1000.0
        except Exception:
            return 0.0

    def is_busy(self) -> bool:
        """检查是否正在播放"""
        if not self.is_initialized or not PYGAME_AVAILABLE:
            return False

        try:
            return pygame.mixer.music.get_busy()
        except Exception:
            return False

    # === 预览功能 ===

    def start_preview(self, file_path: str, duration: float = None,
                      callback: Optional[Callable] = None):
        """
        开始预览播放（延迟后自动播放）

        Args:
            file_path: 音频文件路径
            duration: 预览时长（秒），None使用默认值
            callback: 播放开始回调
        """
        # 如果已经在播放同一首歌，不处理
        if self.current_music == file_path and self.is_playing:
            return

        # 取消之前的预览
        self.cancel_preview()

        # 加载新文件
        if not self.load_music(file_path):
            return

        # 记录预览信息
        self.preview_duration = duration or self.config.preview_duration
        self.preview_timer = time.time()

        # 启动延迟播放线程
        self.preview_stop_flag = False
        self.preview_thread = threading.Thread(
            target=self._preview_delayed_play,
            args=(callback,),
            daemon=True
        )
        self.preview_thread.start()

    def _preview_delayed_play(self, callback: Optional[Callable]):
        """延迟播放（在后台线程中执行）"""
        # 等待悬停延迟
        elapsed = 0.0
        while elapsed < self.preview_delay and not self.preview_stop_flag:
            time.sleep(0.05)
            elapsed += 0.05

        # 如果未被取消，开始播放
        if not self.preview_stop_flag and self.current_music:
            self.play_music()
            if callback:
                callback()

    def cancel_preview(self):
        """取消预览"""
        self.preview_stop_flag = True
        self.preview_timer = None

        # 等待线程结束
        if self.preview_thread and self.preview_thread.is_alive():
            self.preview_thread.join(timeout=0.2)

        self.preview_thread = None

        # 停止音乐
        self.stop_music()

    def stop_preview(self):
        """停止预览（取消+停止）"""
        self.cancel_preview()

    # === 音效功能 ===

    def play_sfx(self, sfx_type: str):
        """
        播放音效

        Args:
            sfx_type: 音效类型
        """
        if not self.is_initialized or not PYGAME_AVAILABLE:
            return

        # 如果有预加载的音效，播放
        if sfx_type in self._sfx_cache:
            try:
                sound = self._sfx_cache[sfx_type]
                sound.set_volume(self.config.master_volume * self.config.sfx_volume)
                sound.play()
            except Exception:
                pass

    def load_sfx(self, sfx_type: str, file_path: str):
        """
        加载音效

        Args:
            sfx_type: 音效类型
            file_path: 音效文件路径
        """
        if not self.is_initialized or not PYGAME_AVAILABLE:
            return

        if not os.path.exists(file_path):
            return

        try:
            sound = pygame.mixer.Sound(file_path)
            self._sfx_cache[sfx_type] = sound
        except Exception as e:
            print(f"[AudioManager] 加载音效失败: {e}")

    def generate_sfx(self):
        """
        生成内置音效（程序生成简单的提示音）

        使用pygame生成简单的波形音效，无需外部文件
        """
        if not self.is_initialized or not PYGAME_AVAILABLE:
            return

        try:
            import array

            sample_rate = 44100
            duration = 0.15  # 150ms

            # 生成玻璃点击音（高频短促音）
            for sfx_type, freq in [
                (self.SFX_GLASS_CLICK, 1200),
                (self.SFX_CONFIRM, 800),
            ]:
                samples = int(sample_rate * duration)
                buf = array.array('h')

                for i in range(samples):
                    t = i / sample_rate
                    # 指数衰减的正弦波
                    decay = math.exp(-t * 20)
                    value = int(32767 * 0.3 * decay * math.sin(2 * math.pi * freq * t))
                    buf.append(value)

                sound = pygame.mixer.Sound(buffer=buf)
                self._sfx_cache[sfx_type] = sound

            # 判定音（不同频率）
            for sfx_type, freq in [
                (self.SFX_PERFECT, 1000),
                (self.SFX_GOOD, 800),
                (self.SFX_BAD, 400),
                (self.SFX_MISS, 200),
            ]:
                samples = int(sample_rate * 0.1)  # 100ms
                buf = array.array('h')

                for i in range(samples):
                    t = i / sample_rate
                    decay = math.exp(-t * 30)
                    value = int(32767 * 0.2 * decay * math.sin(2 * math.pi * freq * t))
                    buf.append(value)

                sound = pygame.mixer.Sound(buffer=buf)
                self._sfx_cache[sfx_type] = sound

        except Exception as e:
            print(f"[AudioManager] 生成音效失败: {e}")

    # === 频谱功能 ===

    def update_spectrum(self, beat_intensity: float = 0.5):
        """
        更新频谱数据

        Args:
            beat_intensity: 节拍强度 (0.0-1.0)
        """
        self.spectrum.update(self.is_playing, beat_intensity)

    def get_spectrum_bars(self) -> List[float]:
        """获取频谱条数据"""
        return self.spectrum.get_bars()

    def enable_spectrum(self, enabled: bool):
        """启用/禁用频谱"""
        self.spectrum.set_enabled(enabled)

    # === 资源管理 ===

    def cleanup(self):
        """清理资源"""
        self.stop_music()
        self.cancel_preview()
        self._sfx_cache.clear()
        self.spectrum.reset()

        if self.is_initialized and PYGAME_AVAILABLE:
            try:
                pygame.mixer.music.unload()
            except Exception:
                pass


# 全局单例
_audio_manager_instance: Optional[AudioManager] = None


def get_audio_manager() -> AudioManager:
    """获取全局音频管理器实例"""
    global _audio_manager_instance
    if _audio_manager_instance is None:
        _audio_manager_instance = AudioManager()
        _audio_manager_instance.generate_sfx()  # 生成内置音效
    return _audio_manager_instance
