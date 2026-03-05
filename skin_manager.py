# -*- coding: utf-8 -*-
"""
皮肤管理模块
负责加载和管理StepMania皮肤资源
"""

import os
import re
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False


# 轨道方向名
TRACK_DIRECTIONS = ["DownLeft", "UpLeft", "Center", "UpRight", "DownRight"]


@dataclass
class SkinConfig:
    """皮肤配置"""
    name: str = "default"
    hold_offset: int = -22  # 长按身体偏移


class SkinManager:
    """皮肤资源加载与管理"""

    def __init__(self, skin_dir: str):
        """
        初始化皮肤管理器

        Args:
            skin_dir: 皮肤目录路径
        """
        self.skin_dir = os.path.abspath(skin_dir)
        self.config = SkinConfig()

        # 皮肤缓存
        self._cache: Dict[str, any] = {}  # 普通皮肤缓存
        self._flip_cache: Dict[str, any] = {}  # 水平翻转缓存
        self._root_dir_cache: Optional[str] = None  # 皮肤根目录缓存

        # 预加载的皮肤Surface
        self.tap_surfs: list = [None] * 5  # 点按箭头
        self.hold_body_surfs: list = [None] * 5  # 长按箭身
        self.hold_tail_surfs: list = [None] * 5  # 长按箭尾
        self.receptor_surfs: list = [None] * 5  # 判定区

        self._initialized = False

    def open(self) -> bool:
        """
        初始化皮肤资源

        Returns:
            是否初始化成功
        """
        if not os.path.isdir(self.skin_dir):
            print(f"[SkinManager] 皮肤目录不存在: {self.skin_dir}")
            return False

        self._guess_root_dir()
        self._load_all_skins()
        self._initialized = True
        return True

    def close(self):
        """释放皮肤缓存"""
        self._cache.clear()
        self._flip_cache.clear()
        self._root_dir_cache = None
        self._initialized = False

    def _guess_root_dir(self) -> str:
        """猜测皮肤根目录"""
        if self._root_dir_cache is not None:
            return self._root_dir_cache

        if not os.path.isdir(self.skin_dir):
            self._root_dir_cache = ""
            return ""

        try:
            # 检测根目录是否有png
            for file_name in os.listdir(self.skin_dir):
                file_path = os.path.join(self.skin_dir, file_name)
                if os.path.isfile(file_path) and file_name.lower().endswith(".png"):
                    self._root_dir_cache = ""
                    return ""

            # 检测一级子目录是否有png
            for dir_name in os.listdir(self.skin_dir):
                sub_dir = os.path.join(self.skin_dir, dir_name)
                if not os.path.isdir(sub_dir):
                    continue
                for file_name in os.listdir(sub_dir):
                    file_path = os.path.join(sub_dir, file_name)
                    if os.path.isfile(file_path) and file_name.lower().endswith(".png"):
                        self._root_dir_cache = dir_name
                        return dir_name
        except Exception as e:
            print(f"[SkinManager] 检测皮肤目录失败: {e}")

        self._root_dir_cache = ""
        return ""

    @staticmethod
    def _parse_grid(file_name: str) -> Tuple[int, int]:
        """解析皮肤文件名中的网格信息，如3x2.png"""
        base_name = os.path.basename(file_name).lower()
        matches = re.findall(r"(\d+)\s*x\s*(\d+)\.png$", base_name)
        if not matches:
            return (1, 1)
        a, b = matches[-1]
        return (max(1, int(a)), max(1, int(b)))

    def _get_real_path(self, file_name: str) -> str:
        """获取皮肤文件的真实路径"""
        root = self._guess_root_dir()
        if root:
            return os.path.join(self.skin_dir, root, file_name)
        return os.path.join(self.skin_dir, file_name)

    def _read_png(self, file_name: str) -> Optional['pygame.Surface']:
        """读取PNG皮肤文件，带缓存"""
        if not PYGAME_AVAILABLE:
            return None

        cache_key = f"{self._guess_root_dir()}::{file_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        real_path = self._get_real_path(file_name)
        if not os.path.exists(real_path):
            return None

        try:
            surf = pygame.image.load(real_path).convert_alpha()
            self._cache[cache_key] = surf
            return surf
        except Exception as e:
            print(f"[SkinManager] 加载皮肤失败: {file_name} - {e}")
            return None

    def _crop_frame(self, surf: 'pygame.Surface', col: int, row: int,
                    frame_idx: int) -> 'pygame.Surface':
        """从网格图中裁切指定帧"""
        w, h = surf.get_width(), surf.get_height()
        single_w = max(1, w // col)
        single_h = max(1, h // row)
        total_frames = col * row
        frame_idx = max(0, min(total_frames - 1, frame_idx))

        row_idx = frame_idx // col
        col_idx = frame_idx % col

        rect = pygame.Rect(col_idx * single_w, row_idx * single_h, single_w, single_h)
        return surf.subsurface(rect).copy()

    def _flip_horizontal(self, surf: 'pygame.Surface', cache_key: str) -> 'pygame.Surface':
        """水平翻转图像，带缓存"""
        if cache_key in self._flip_cache:
            return self._flip_cache[cache_key]

        flip_surf = pygame.transform.flip(surf, True, False)
        self._flip_cache[cache_key] = flip_surf
        return flip_surf

    def get_tap_arrow(self, dir_name: str) -> Optional['pygame.Surface']:
        """
        获取点按箭头皮肤

        Args:
            dir_name: 方向名 (DownLeft, UpLeft, Center, UpRight, DownRight)

        Returns:
            pygame.Surface 或 None
        """
        file_name = f"{dir_name} Tap Note (doubleres) 3x2.png"
        surf = self._read_png(file_name)

        if surf:
            col, row = self._parse_grid(file_name)
            return self._crop_frame(surf, col, row, frame_idx=0)

        # 右侧箭头复用左侧并翻转
        if dir_name == "UpRight":
            left_surf = self.get_tap_arrow("UpLeft")
            return self._flip_horizontal(left_surf, "Flip:UpLeft:Tap") if left_surf else None

        if dir_name == "DownRight":
            left_surf = self.get_tap_arrow("DownLeft")
            return self._flip_horizontal(left_surf, "Flip:DownLeft:Tap") if left_surf else None

        return None

    def get_hold_body(self, dir_name: str) -> Optional['pygame.Surface']:
        """
        获取长按箭身皮肤

        Args:
            dir_name: 方向名

        Returns:
            pygame.Surface 或 None
        """
        file_name = f"{dir_name} Hold Body active (doubleres) 6x1.png"
        surf = self._read_png(file_name)

        if surf:
            col, row = self._parse_grid(file_name)
            return self._crop_frame(surf, col, row, frame_idx=0)

        if dir_name == "UpRight":
            left_surf = self.get_hold_body("UpLeft")
            return self._flip_horizontal(left_surf, "Flip:UpLeft:HoldBody") if left_surf else None

        if dir_name == "DownRight":
            left_surf = self.get_hold_body("DownLeft")
            return self._flip_horizontal(left_surf, "Flip:DownLeft:HoldBody") if left_surf else None

        return None

    def get_hold_tail(self, dir_name: str) -> Optional['pygame.Surface']:
        """
        获取长按箭尾皮肤

        Args:
            dir_name: 方向名

        Returns:
            pygame.Surface 或 None
        """
        file_name = f"{dir_name} Hold BottomCap active (doubleres) 6x1.png"
        surf = self._read_png(file_name)

        if surf:
            col, row = self._parse_grid(file_name)
            return self._crop_frame(surf, col, row, frame_idx=0)

        if dir_name == "UpRight":
            left_surf = self.get_hold_tail("UpLeft")
            return self._flip_horizontal(left_surf, "Flip:UpLeft:HoldCap") if left_surf else None

        if dir_name == "DownRight":
            left_surf = self.get_hold_tail("DownLeft")
            return self._flip_horizontal(left_surf, "Flip:DownLeft:HoldCap") if left_surf else None

        return None

    def get_receptor(self, dir_name: str) -> Optional['pygame.Surface']:
        """
        获取判定区皮肤

        Args:
            dir_name: 方向名

        Returns:
            pygame.Surface 或 None
        """
        if dir_name == "Center":
            file_name = "Center Ready Receptor (doubleres) 1x3.png"
            surf = self._read_png(file_name)
            if not surf:
                return None
            col, row = self._parse_grid(file_name)
            return self._crop_frame(surf, col, row, frame_idx=1)

        if dir_name == "UpLeft":
            file_name = "UpLeft Ready Receptor (doubleres) 1x3.png"
            surf = self._read_png(file_name)
            if not surf:
                return None
            col, row = self._parse_grid(file_name)
            return self._crop_frame(surf, col, row, frame_idx=1)

        if dir_name == "DownLeft":
            file_name = "DownLeft Ready Receptor (doubleres) 1x3.png"
            surf = self._read_png(file_name)
            if not surf:
                return None
            col, row = self._parse_grid(file_name)
            return self._crop_frame(surf, col, row, frame_idx=1)

        if dir_name == "UpRight":
            left_surf = self.get_receptor("UpLeft")
            return self._flip_horizontal(left_surf, "Flip:UpLeft:Receptor") if left_surf else None

        if dir_name == "DownRight":
            left_surf = self.get_receptor("DownLeft")
            return self._flip_horizontal(left_surf, "Flip:DownLeft:Receptor") if left_surf else None

        return None

    def _load_all_skins(self):
        """加载所有轨道的皮肤"""
        for i, dir_name in enumerate(TRACK_DIRECTIONS):
            self.tap_surfs[i] = self.get_tap_arrow(dir_name)
            self.hold_body_surfs[i] = self.get_hold_body(dir_name)
            self.hold_tail_surfs[i] = self.get_hold_tail(dir_name)
            self.receptor_surfs[i] = self.get_receptor(dir_name)

    def get_tap(self, track_idx: int) -> Optional['pygame.Surface']:
        """获取指定轨道的点按箭头"""
        if 0 <= track_idx < len(self.tap_surfs):
            return self.tap_surfs[track_idx]
        return None

    def get_hold_body_surf(self, track_idx: int) -> Optional['pygame.Surface']:
        """获取指定轨道的长按箭身"""
        if 0 <= track_idx < len(self.hold_body_surfs):
            return self.hold_body_surfs[track_idx]
        return None

    def get_hold_tail_surf(self, track_idx: int) -> Optional['pygame.Surface']:
        """获取指定轨道的长按箭尾"""
        if 0 <= track_idx < len(self.hold_tail_surfs):
            return self.hold_tail_surfs[track_idx]
        return None

    def get_receptor_surf(self, track_idx: int) -> Optional['pygame.Surface']:
        """获取指定轨道的判定区"""
        if 0 <= track_idx < len(self.receptor_surfs):
            return self.receptor_surfs[track_idx]
        return None

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    def has_skins(self) -> bool:
        """检查是否有可用的皮肤"""
        return any(self.tap_surfs) or any(self.receptor_surfs)
