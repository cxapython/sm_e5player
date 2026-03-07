# -*- coding: utf-8 -*-
"""
音频管理模块（PyQt6版本）
使用QMediaPlayer进行音频播放
"""

import os
from typing import Optional, Callable, List
from dataclasses import dataclass

from PyQt6.QtCore import QObject, QUrl, QTimer, pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput


@dataclass
class AudioConfig:
    """音频配置"""
    master_volume: float = 0.8
    music_volume: float = 1.0
    sfx_volume: float = 0.8
    preview_duration: float = 10.0
    preview_delay: float = 0.5


_audio_manager_instance: Optional['AudioManager'] = None


def get_audio_manager() -> 'AudioManager':
    """获取音频管理器单例"""
    global _audio_manager_instance
    if _audio_manager_instance is None:
        _audio_manager_instance = AudioManager()
    return _audio_manager_instance


class AudioManager(QObject):
    """音频管理器"""

    music_position_changed = pyqtSignal(int)
    music_duration_changed = pyqtSignal(int)
    music_state_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._config = AudioConfig()

        # 音乐播放器
        self._music_player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._music_player.setAudioOutput(self._audio_output)

        # 预览播放器
        self._preview_player = QMediaPlayer()
        self._preview_output = QAudioOutput()
        self._preview_player.setAudioOutput(self._preview_output)

        # 状态
        self._music_path: Optional[str] = None
        self._preview_path: Optional[str] = None

        # 连接信号
        self._music_player.positionChanged.connect(self._on_music_position_changed)
        self._music_player.durationChanged.connect(self._on_music_duration_changed)
        self._music_player.playbackStateChanged.connect(self._on_music_state_changed)

        # 设置音量
        self._audio_output.setVolume(self._config.master_volume)
        self._preview_output.setVolume(self._config.master_volume * 0.5)

    def set_master_volume(self, volume: float):
        """设置主音量"""
        self._config.master_volume = max(0.0, min(1.0, volume))
        self._audio_output.setVolume(self._config.master_volume)
        self._preview_output.setVolume(self._config.master_volume * 0.5)

    def load_music(self, path: str) -> bool:
        """加载音乐文件"""
        if not path or not os.path.exists(path):
            return False

        self._music_path = path
        url = QUrl.fromLocalFile(path)
        self._music_player.setSource(url)
        return True

    def play_music(self, start_pos: float = 0.0):
        """播放音乐"""
        if self._music_path:
            self._music_player.play()
            if start_pos > 0:
                self._music_player.setPosition(int(start_pos * 1000))

    def pause_music(self):
        """暂停音乐"""
        self._music_player.pause()

    def resume_music(self):
        """恢复音乐"""
        self._music_player.play()

    def stop_music(self):
        """停止音乐"""
        self._music_player.stop()

    def set_music_position(self, position: float):
        """设置音乐位置（秒）"""
        self._music_player.setPosition(int(position * 1000))

    def set_music_speed(self, speed: float):
        """设置音乐播放速度（0.5, 0.75, 1.0等）"""
        self._music_player.setPlaybackRate(speed)

    def get_music_position(self) -> float:
        """获取音乐位置（秒）"""
        return self._music_player.position() / 1000.0

    def get_music_duration(self) -> float:
        """获取音乐时长（秒）"""
        return self._music_player.duration() / 1000.0

    def is_music_playing(self) -> bool:
        """音乐是否正在播放"""
        return self._music_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def _on_music_position_changed(self, position: int):
        """音乐位置变化"""
        self.music_position_changed.emit(position)

    def _on_music_duration_changed(self, duration: int):
        """音乐时长变化"""
        self.music_duration_changed.emit(duration)

    def _on_music_state_changed(self, state):
        """音乐状态变化"""
        self.music_state_changed.emit(state)

    # 预览相关
    def play_preview(self, path: str, delay: float = 0.5):
        """播放预览音频"""
        self.stop_preview()

        if not path or not os.path.exists(path):
            return

        self._preview_path = path
        url = QUrl.fromLocalFile(path)
        self._preview_player.setSource(url)

        # 延迟播放
        QTimer.singleShot(int(delay * 1000), self._start_preview)

    def _start_preview(self):
        """开始预览"""
        if self._preview_path:
            self._preview_player.play()

    def start_preview(self, file_path: str, duration: float = None):
        """
        开始预览播放

        Args:
            file_path: 音频文件路径
            duration: 预览时长（秒），暂未使用
        """
        self.play_preview(file_path, delay=0.1)

    def stop_preview(self):
        """停止预览"""
        self._preview_player.stop()

    def cleanup(self):
        """清理资源"""
        self._music_player.stop()
        self._preview_player.stop()
