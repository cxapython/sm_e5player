# -*- coding: utf-8 -*-
"""
配置管理模块（增强版）
负责读取和保存应用程序配置，包括扫描路径、音量、窗口、游戏设置等
"""

import json
import os
from typing import Optional, Dict, Any, Tuple


class ConfigManager:
    """配置管理器，负责配置文件的读写"""

    DEFAULT_CONFIG = {
        # === 路径配置 ===
        "scan_path": "",
        "last_played": "",
        "last_sm_file": "",
        "last_page": 0,

        # === 窗口配置 ===
        "window_width": 1280,
        "window_height": 720,
        "fullscreen": False,
        "fps": 60,

        # === 音频配置 ===
        "master_volume": 0.8,
        "music_volume": 1.0,
        "sfx_volume": 0.8,
        "preview_duration": 10,  # 预览音频时长（秒）
        "preview_delay": 0.5,    # 悬停预览延迟（秒）

        # === 游戏配置 ===
        "scroll_speed": 840.0,   # 滚动速度（像素/秒）
        "offset": 0.0,           # 音频偏移（秒）
        "tick_per_beat": 96,     # 每拍tick数

        # === 判定配置 ===
        "perfect_window": 0.045,  # PERFECT窗口（秒）
        "good_window": 0.090,     # GOOD窗口（秒）
        "bad_window": 0.135,      # BAD窗口（秒）

        # === UI配置 ===
        "glass_theme": "dark",        # 玻璃主题: dark, light
        "spectrum_enabled": True,     # 是否启用频谱可视化
        "spectrum_bars": 32,          # 频谱条数
        "card_columns_large": 4,      # 大屏卡片列数
        "card_columns_small": 3,      # 小屏卡片列数
        "card_rows_large": 2,         # 大屏卡片行数
        "card_rows_small": 3,         # 小屏卡片行数
        "large_screen_threshold": 1920,  # 大屏阈值（像素）

        # === 星级筛选配置 ===
        "star_filter_min": None,      # 最小星级
        "star_filter_max": None,      # 最大星级
    }

    def __init__(self, config_file: str = "config.json"):
        """
        初始化配置管理器

        Args:
            config_file: 配置文件路径，默认为当前目录下的config.json
        """
        self.config_file = config_file
        self.config: Dict[str, Any] = {}
        # 自动加载配置
        self.load()

    def load(self) -> Dict[str, Any]:
        """
        加载配置文件

        Returns:
            配置字典，如果文件不存在则返回默认配置
        """
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)
                    # 合并默认配置，确保所有字段都存在
                    self.config = {**self.DEFAULT_CONFIG, **loaded_config}
                    return self.config
            except (json.JSONDecodeError, IOError) as e:
                print(f"[ConfigManager] 配置文件读取失败: {e}，使用默认配置")
                self.config = self.DEFAULT_CONFIG.copy()
        else:
            self.config = self.DEFAULT_CONFIG.copy()
        return self.config

    def save(self) -> bool:
        """
        保存当前配置到文件

        Returns:
            是否保存成功
        """
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            return True
        except IOError as e:
            print(f"[ConfigManager] 配置文件保存失败: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键
            default: 默认值

        Returns:
            配置值
        """
        return self.config.get(key, default)

    def set(self, key: str, value: Any, auto_save: bool = False):
        """
        设置配置值

        Args:
            key: 配置键
            value: 配置值
            auto_save: 是否自动保存
        """
        self.config[key] = value
        if auto_save:
            self.save()

    # === 路径配置 ===

    def get_scan_path(self) -> Optional[str]:
        """获取歌曲扫描路径"""
        path = self.config.get("scan_path", "")
        if path and os.path.isdir(path):
            return path
        return None

    def set_scan_path(self, path: str) -> bool:
        """设置歌曲扫描路径"""
        if os.path.isdir(path):
            self.config["scan_path"] = os.path.abspath(path)
            return self.save()
        return False

    def get_last_played(self) -> str:
        """获取上次播放的歌曲路径"""
        return self.config.get("last_played", "")

    def set_last_played(self, song_path: str):
        """设置上次播放的歌曲路径"""
        self.config["last_played"] = song_path
        self.save()

    def get_last_sm_file(self) -> str:
        """获取上次播放的sm文件路径"""
        return self.config.get("last_sm_file", "")

    def set_last_sm_file(self, sm_file: str):
        """设置上次播放的sm文件路径"""
        self.config["last_sm_file"] = sm_file

    def get_last_page(self) -> int:
        """获取上次的页码"""
        return self.config.get("last_page", 0)

    def set_last_page(self, page: int):
        """设置页码"""
        self.config["last_page"] = page

    # === 窗口配置 ===

    def get_window_size(self) -> Tuple[int, int]:
        """获取窗口大小"""
        return (
            self.config.get("window_width", 1280),
            self.config.get("window_height", 720)
        )

    def set_window_size(self, width: int, height: int, auto_save: bool = True):
        """设置窗口大小"""
        self.config["window_width"] = width
        self.config["window_height"] = height
        if auto_save:
            self.save()

    def is_fullscreen(self) -> bool:
        """是否全屏"""
        return self.config.get("fullscreen", False)

    def set_fullscreen(self, fullscreen: bool):
        """设置全屏"""
        self.config["fullscreen"] = fullscreen
        self.save()

    def get_fps(self) -> int:
        """获取帧率"""
        return self.config.get("fps", 60)

    def set_fps(self, fps: int):
        """设置帧率"""
        self.config["fps"] = max(30, min(144, fps))
        self.save()

    # === 音频配置 ===

    def get_master_volume(self) -> float:
        """获取主音量（0.0-1.0）"""
        return self.config.get("master_volume", 0.8)

    def set_master_volume(self, volume: float):
        """设置主音量（0.0-1.0）"""
        self.config["master_volume"] = max(0.0, min(1.0, volume))
        self.save()

    def get_music_volume(self) -> float:
        """获取音乐音量（0.0-1.0）"""
        return self.config.get("music_volume", 1.0)

    def set_music_volume(self, volume: float):
        """设置音乐音量（0.0-1.0）"""
        self.config["music_volume"] = max(0.0, min(1.0, volume))
        self.save()

    def get_sfx_volume(self) -> float:
        """获取音效音量（0.0-1.0）"""
        return self.config.get("sfx_volume", 0.8)

    def set_sfx_volume(self, volume: float):
        """设置音效音量（0.0-1.0）"""
        self.config["sfx_volume"] = max(0.0, min(1.0, volume))
        self.save()

    # 兼容旧接口
    def get_volume(self) -> float:
        """获取音量设置（0.0-1.0）- 兼容旧接口"""
        return self.get_master_volume()

    def set_volume(self, volume: float):
        """设置音量（0.0-1.0）- 兼容旧接口"""
        self.set_master_volume(volume)

    # === 游戏配置 ===

    def get_scroll_speed(self) -> float:
        """获取滚动速度"""
        return self.config.get("scroll_speed", 840.0)

    def set_scroll_speed(self, speed: float):
        """设置滚动速度"""
        self.config["scroll_speed"] = max(200.0, min(2000.0, speed))

    def get_offset(self) -> float:
        """获取音频偏移"""
        return self.config.get("offset", 0.0)

    def set_offset(self, offset: float):
        """设置音频偏移"""
        self.config["offset"] = offset

    def get_tick_per_beat(self) -> int:
        """获取每拍tick数"""
        return self.config.get("tick_per_beat", 96)

    def set_tick_per_beat(self, tick: int):
        """设置每拍tick数"""
        self.config["tick_per_beat"] = tick

    # === UI配置 ===

    def get_glass_theme(self) -> str:
        """获取玻璃主题"""
        return self.config.get("glass_theme", "dark")

    def set_glass_theme(self, theme: str):
        """设置玻璃主题"""
        self.config["glass_theme"] = theme
        self.save()

    def is_spectrum_enabled(self) -> bool:
        """是否启用频谱可视化"""
        return self.config.get("spectrum_enabled", True)

    def set_spectrum_enabled(self, enabled: bool):
        """设置是否启用频谱可视化"""
        self.config["spectrum_enabled"] = enabled
        self.save()

    def get_spectrum_bars(self) -> int:
        """获取频谱条数"""
        return self.config.get("spectrum_bars", 32)

    def get_card_layout(self, window_width: int) -> Tuple[int, int]:
        """
        根据窗口宽度获取卡片布局

        Args:
            window_width: 窗口宽度

        Returns:
            (列数, 行数)
        """
        threshold = self.config.get("large_screen_threshold", 1920)
        if window_width >= threshold:
            return (
                self.config.get("card_columns_large", 4),
                self.config.get("card_rows_large", 2)
            )
        else:
            return (
                self.config.get("card_columns_small", 3),
                self.config.get("card_rows_small", 3)
            )

    # === 星级筛选 ===

    def get_star_filter(self) -> Tuple[Optional[int], Optional[int]]:
        """获取星级筛选范围"""
        return (
            self.config.get("star_filter_min"),
            self.config.get("star_filter_max")
        )

    def set_star_filter(self, min_star: Optional[int], max_star: Optional[int]):
        """设置星级筛选范围"""
        self.config["star_filter_min"] = min_star
        self.config["star_filter_max"] = max_star
        self.save()

    # === 工具方法 ===

    def is_first_run(self) -> bool:
        """检查是否首次运行"""
        scan_path = self.config.get("scan_path", "")
        return not scan_path or not os.path.isdir(scan_path)

    def reset_to_default(self):
        """重置为默认配置"""
        self.config = self.DEFAULT_CONFIG.copy()
        self.save()
