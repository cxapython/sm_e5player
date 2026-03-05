# -*- coding: utf-8 -*-
"""
配置管理模块
负责读取和保存应用程序配置（扫描路径、音量等）
"""

import json
import os
from typing import Optional, Dict, Any


class ConfigManager:
    """配置管理器，负责配置文件的读写"""

    DEFAULT_CONFIG = {
        "scan_path": "",
        "last_played": "",
        "volume": 0.8,
        "window_width": 1000,
        "window_height": 700
    }

    def __init__(self, config_file: str = "config.json"):
        """
        初始化配置管理器
        :param config_file: 配置文件路径，默认为当前目录下的config.json
        """
        self.config_file = config_file
        self.config: Dict[str, Any] = {}
        # 自动加载配置
        self.load()

    def load(self) -> Dict[str, Any]:
        """
        加载配置文件
        :return: 配置字典，如果文件不存在则返回默认配置
        """
        # 尝试读取配置文件
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
        :return: 是否保存成功
        """
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            return True
        except IOError as e:
            print(f"[ConfigManager] 配置文件保存失败: {e}")
            return False

    def get_scan_path(self) -> Optional[str]:
        """
        获取歌曲扫描路径
        :return: 扫描路径，未设置则返回None
        """
        path = self.config.get("scan_path", "")
        if path and os.path.isdir(path):
            return path
        return None

    def set_scan_path(self, path: str) -> bool:
        """
        设置歌曲扫描路径
        :param path: 扫描路径
        :return: 是否设置成功
        """
        if os.path.isdir(path):
            self.config["scan_path"] = os.path.abspath(path)
            return self.save()
        return False

    def get_volume(self) -> float:
        """获取音量设置（0.0-1.0）"""
        return self.config.get("volume", 0.8)

    def set_volume(self, volume: float):
        """设置音量（0.0-1.0）"""
        self.config["volume"] = max(0.0, min(1.0, volume))
        self.save()

    def get_last_played(self) -> str:
        """获取上次播放的歌曲路径"""
        return self.config.get("last_played", "")

    def set_last_played(self, song_path: str):
        """设置上次播放的歌曲路径"""
        self.config["last_played"] = song_path
        self.save()

    def get_window_size(self) -> tuple:
        """获取窗口大小"""
        return (
            self.config.get("window_width", 1000),
            self.config.get("window_height", 700)
        )

    def set_window_size(self, width: int, height: int):
        """设置窗口大小"""
        self.config["window_width"] = width
        self.config["window_height"] = height
        self.save()

    def is_first_run(self) -> bool:
        """
        检查是否首次运行
        :return: 如果没有设置扫描路径则返回True
        """
        scan_path = self.config.get("scan_path", "")
        return not scan_path or not os.path.isdir(scan_path)

    def get_last_sm_file(self) -> str:
        """获取上次播放的sm文件路径"""
        return self.config.get("last_sm_file", "")

    def set_last_sm_file(self, sm_file: str):
        """设置上次播放的sm文件路径"""
        self.config["last_sm_file"] = sm_file
        # 不立即保存，由调用者决定何时保存

    def get_last_page(self) -> int:
        """获取上次的页码"""
        return self.config.get("last_page", 0)

    def set_last_page(self, page: int):
        """设置页码"""
        self.config["last_page"] = page
        # 不立即保存，由调用者决定何时保存
