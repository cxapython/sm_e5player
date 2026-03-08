# -*- coding: utf-8 -*-
"""
精灵图加载器
用于加载TexturePacker导出的精灵图资源
"""

import json
import os
from typing import Dict, Optional, Tuple
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import QRect


class SpriteLoader:
    """精灵图加载器"""

    def __init__(self, sprite_dir: str):
        """
        初始化精灵图加载器

        Args:
            sprite_dir: 精灵图目录路径
        """
        self._sprite_dir = sprite_dir
        self._cache: Dict[str, QPixmap] = {}
        self._frames: Dict[str, dict] = {}
        self._sprite_image: Optional[QImage] = None

    def load(self, sprite_name: str = "skin") -> bool:
        """
        加载精灵图

        Args:
            sprite_name: 精灵图名称（不含扩展名）

        Returns:
            是否加载成功
        """
        json_path = os.path.join(self._sprite_dir, f"{sprite_name}.json")
        png_path = os.path.join(self._sprite_dir, f"{sprite_name}.png")

        if not os.path.exists(json_path) or not os.path.exists(png_path):
            return False

        try:
            # 加载JSON配置
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 解析帧信息
            self._frames.clear()
            for frame in data.get('frames', []):
                filename = frame.get('filename', '')
                frame_info = frame.get('frame', {})
                self._frames[filename] = {
                    'x': frame_info.get('x', 0),
                    'y': frame_info.get('y', 0),
                    'w': frame_info.get('w', 0),
                    'h': frame_info.get('h', 0)
                }

            # 加载精灵图
            self._sprite_image = QImage(png_path)
            if self._sprite_image.isNull():
                return False

            # 预裁剪所有帧到缓存
            self._cache.clear()
            for filename, info in self._frames.items():
                rect = QRect(info['x'], info['y'], info['w'], info['h'])
                cropped = self._sprite_image.copy(rect)
                self._cache[filename] = QPixmap.fromImage(cropped)

            return True

        except Exception as e:
            print(f"[SpriteLoader] 加载精灵图失败: {e}")
            return False

    def get(self, name: str) -> Optional[QPixmap]:
        """
        获取指定名称的图片

        Args:
            name: 图片名称（如 "text_pf1_perfect.png"）

        Returns:
            QPixmap对象，不存在返回None
        """
        return self._cache.get(name)

    def get_frame_info(self, name: str) -> Optional[dict]:
        """
        获取帧信息

        Args:
            name: 图片名称

        Returns:
            帧信息字典
        """
        return self._frames.get(name)

    def get_size(self, name: str) -> Tuple[int, int]:
        """
        获取图片尺寸

        Args:
            name: 图片名称

        Returns:
            (width, height) 元组
        """
        info = self._frames.get(name)
        if info:
            return (info['w'], info['h'])
        return (0, 0)

    def has_sprite(self, name: str) -> bool:
        """检查是否存在指定图片"""
        return name in self._cache


class AssetManager:
    """资源管理器 - 管理所有精灵图资源"""

    def __init__(self, assets_dir: str):
        """
        初始化资源管理器

        Args:
            assets_dir: 资源目录路径
        """
        self._assets_dir = assets_dir

        # 加载器
        self._judge_loader = SpriteLoader(os.path.join(assets_dir, "judge"))
        self._blood_bar_loader = SpriteLoader(os.path.join(assets_dir, "blood_bar"))
        self._number_loader = SpriteLoader(os.path.join(assets_dir, "number"))

        # 已加载标志
        self._loaded = False

    def load_all(self) -> bool:
        """加载所有资源"""
        self._loaded = True

        # 加载判定文字精灵图
        if not self._judge_loader.load("skin"):
            print("[AssetManager] 判定文字精灵图加载失败")
            self._loaded = False

        # 加载血条精灵图
        if not self._blood_bar_loader.load("skin"):
            print("[AssetManager] 血条精灵图加载失败")
            self._loaded = False

        # 加载数字精灵图
        if not self._number_loader.load("skin"):
            print("[AssetManager] 数字精灵图加载失败")
            self._loaded = False

        return self._loaded

    def is_loaded(self) -> bool:
        """检查是否已加载"""
        return self._loaded

    @property
    def judge(self) -> SpriteLoader:
        """获取判定文字加载器"""
        return self._judge_loader

    @property
    def blood_bar(self) -> SpriteLoader:
        """获取血条加载器"""
        return self._blood_bar_loader

    @property
    def number(self) -> SpriteLoader:
        """获取数字加载器"""
        return self._number_loader

    def get_judge_text(self, judge_type: str) -> Optional[QPixmap]:
        """
        获取判定文字图片

        Args:
            judge_type: 判定类型 ("perfect", "cool", "good", "miss")

        Returns:
            QPixmap对象
        """
        name = f"text_pf1_{judge_type}.png"
        return self._judge_loader.get(name)

    def get_combo_text(self) -> Optional[QPixmap]:
        """获取COMBO文字图片"""
        return self._judge_loader.get("text_pf1_combo.png")

    def get_digit(self, digit: int) -> Optional[QPixmap]:
        """
        获取数字图片

        Args:
            digit: 数字 0-9

        Returns:
            QPixmap对象
        """
        name = f"text_pf1_{digit}.png"
        return self._number_loader.get(name)

    def get_colon(self) -> Optional[QPixmap]:
        """获取冒号图片"""
        return self._number_loader.get("text_pf1_x.png")

    def get_health_bar(self, is_danger: bool = False) -> Tuple[Optional[QPixmap], Optional[QPixmap]]:
        """
        获取血条图片

        Args:
            is_danger: 是否为危险状态（低血量）

        Returns:
            (背景图, 填充图) 元组
        """
        if is_danger:
            bg = self._blood_bar_loader.get("bb_d_bb.png")  # 危险背景
            fill = self._blood_bar_loader.get("full_d_l.png")  # 危险填充
        else:
            bg = self._blood_bar_loader.get("bb_s_lb.png")  # 正常背景
            fill = self._blood_bar_loader.get("full_s_l.png")  # 正常填充
        return (bg, fill)

    def get_health_bar_icon(self) -> Optional[QPixmap]:
        """获取血条图标背景"""
        return self._blood_bar_loader.get("icon_bg_p1.png")

    def get_stage_label(self) -> Optional[QPixmap]:
        """获取STAGE标签"""
        return self._blood_bar_loader.get("stage.png")


# 全局资源管理器实例
_asset_manager: Optional[AssetManager] = None


def get_asset_manager() -> AssetManager:
    """获取全局资源管理器实例"""
    global _asset_manager
    if _asset_manager is None:
        # 默认资源目录
        app_dir = os.path.dirname(os.path.abspath(__file__))
        assets_dir = os.path.join(app_dir, "assets")
        _asset_manager = AssetManager(assets_dir)
    return _asset_manager


def init_assets(assets_dir: str = None) -> bool:
    """
    初始化资源

    Args:
        assets_dir: 资源目录路径，为None时使用默认路径

    Returns:
        是否初始化成功
    """
    global _asset_manager
    if assets_dir is None:
        app_dir = os.path.dirname(os.path.abspath(__file__))
        assets_dir = os.path.join(app_dir, "assets")
    _asset_manager = AssetManager(assets_dir)
    return _asset_manager.load_all()
