# -*- coding: utf-8 -*-
"""
皮肤管理模块（PyQt6版本）
负责加载和管理游戏皮肤资源
支持精灵图裁剪和镜像翻转
"""

import os
import re
from typing import Optional, List, Dict, Tuple
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt


class SkinManager:
    """皮肤管理器"""

    # 轨道方向名映射
    TRACK_NAMES = ["DownLeft", "UpLeft", "Center", "UpRight", "DownRight"]

    def __init__(self, skin_dir: str):
        """
        初始化皮肤管理器

        Args:
            skin_dir: 皮肤目录路径
        """
        self._skin_dir = skin_dir
        self._loaded = False
        self._root_dir: str = ""  # 皮肤根目录缓存

        # 皮肤资源（5个轨道）
        self._tap_pixmaps: List[Optional[QPixmap]] = [None] * 5
        self._hold_body_pixmaps: List[Optional[QPixmap]] = [None] * 5
        self._hold_tail_pixmaps: List[Optional[QPixmap]] = [None] * 5
        self._receptor_pixmaps: List[Optional[QPixmap]] = [None] * 5

        # 缓存
        self._cache: Dict[str, QPixmap] = {}
        self._flip_cache: Dict[str, QPixmap] = {}

    def open(self) -> bool:
        """打开并加载皮肤"""
        if not self._skin_dir or not os.path.isdir(self._skin_dir):
            return False

        try:
            # 检测皮肤根目录
            self._guess_root_dir()

            # 加载各轨道皮肤
            for i, dir_name in enumerate(self.TRACK_NAMES):
                # 加载点按箭头
                self._tap_pixmaps[i] = self._get_tap_arrow(dir_name)

                # 加载长按箭身
                self._hold_body_pixmaps[i] = self._get_hold_body(dir_name)

                # 加载长按箭尾
                self._hold_tail_pixmaps[i] = self._get_hold_tail(dir_name)

                # 加载判定区
                self._receptor_pixmaps[i] = self._get_receptor(dir_name)

            self._loaded = True
            return True

        except Exception as e:
            print(f"[SkinManager] 加载皮肤失败: {e}")
            return False

    def _guess_root_dir(self) -> str:
        """猜测皮肤根目录"""
        if self._root_dir is not None:
            return self._root_dir

        if not os.path.isdir(self._skin_dir):
            self._root_dir = ""
            return ""

        try:
            # 检测根目录是否有png
            for file_name in os.listdir(self._skin_dir):
                file_path = os.path.join(self._skin_dir, file_name)
                if os.path.isfile(file_path) and file_name.lower().endswith(".png"):
                    self._root_dir = ""
                    return ""

            # 检测一级子目录是否有png
            for dir_name in os.listdir(self._skin_dir):
                sub_dir = os.path.join(self._skin_dir, dir_name)
                if not os.path.isdir(sub_dir):
                    continue
                for file_name in os.listdir(sub_dir):
                    file_path = os.path.join(sub_dir, file_name)
                    if os.path.isfile(file_path) and file_name.lower().endswith(".png"):
                        self._root_dir = dir_name
                        return dir_name
        except Exception:
            pass

        self._root_dir = ""
        return ""

    def _get_real_path(self, file_name: str) -> str:
        """获取皮肤文件的真实路径"""
        root = self._guess_root_dir()
        if root:
            return os.path.join(self._skin_dir, root, file_name)
        return os.path.join(self._skin_dir, file_name)

    @staticmethod
    def _parse_grid(file_name: str) -> Tuple[int, int]:
        """解析皮肤文件名中的网格信息，如3x2.png"""
        base_name = os.path.basename(file_name).lower()
        m = re.findall(r"(\d+)\s*x\s*(\d+)\.png$", base_name)
        if not m:
            return (1, 1)
        a, b = m[-1]
        return (max(1, int(a)), max(1, int(b)))

    def _read_png(self, file_name: str) -> Optional[QPixmap]:
        """读取PNG皮肤文件，带缓存"""
        cache_key = f"{self._root_dir}::{file_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        real_path = self._get_real_path(file_name)
        if not os.path.exists(real_path):
            return None

        try:
            pix = QPixmap(real_path)
            if pix.isNull():
                return None
            self._cache[cache_key] = pix
            return pix
        except Exception:
            return None

    def _crop_frame(self, pix: QPixmap, col: int, row: int, frame_idx: int) -> Optional[QPixmap]:
        """从网格图中裁切指定帧"""
        if pix.isNull():
            return None

        w, h = pix.width(), pix.height()
        single_w = max(1, w // col)
        single_h = max(1, h // row)
        total_frames = col * row
        frame_idx = max(0, min(total_frames - 1, frame_idx))

        row_idx = frame_idx // col
        col_idx = frame_idx % col

        # 裁剪区域
        x = col_idx * single_w
        y = row_idx * single_h

        return pix.copy(x, y, single_w, single_h)

    def _flip_horizontal(self, pix: QPixmap, cache_key: str) -> Optional[QPixmap]:
        """水平翻转图像，带缓存"""
        if cache_key in self._flip_cache:
            return self._flip_cache[cache_key]

        if pix is None or pix.isNull():
            return None

        # 使用QPixmap.mirrored进行水平翻转 (horizontal=True, vertical=False)
        flipped = pix.mirrored(True, False)
        self._flip_cache[cache_key] = flipped
        return flipped

    def _get_tap_arrow(self, dir_name: str) -> Optional[QPixmap]:
        """获取点按箭头皮肤"""
        # 尝试加载精灵图
        file_name = f"{dir_name} Tap Note (doubleres) 3x2.png"
        pix = self._read_png(file_name)
        if pix:
            col, row = self._parse_grid(file_name)
            return self._crop_frame(pix, col, row, frame_idx=0)

        # 尝试其他文件名模式
        patterns = [
            f"{dir_name} Tap Note",
            f"{dir_name}_Tap_Note",
            f"{dir_name} tap note",
        ]
        for pattern in patterns:
            for root, dirs, files in os.walk(self._skin_dir):
                for file in files:
                    if pattern.lower() in file.lower() and file.lower().endswith('.png'):
                        pix = QPixmap(os.path.join(root, file))
                        if not pix.isNull():
                            col, row = self._parse_grid(file)
                            return self._crop_frame(pix, col, row, frame_idx=0)

        # 右侧箭头复用左侧并翻转
        if dir_name == "UpRight":
            left_pix = self._get_tap_arrow("UpLeft")
            return self._flip_horizontal(left_pix, "Flip:UpLeft:Tap") if left_pix else None
        if dir_name == "DownRight":
            left_pix = self._get_tap_arrow("DownLeft")
            return self._flip_horizontal(left_pix, "Flip:DownLeft:Tap") if left_pix else None

        return None

    def _get_hold_body(self, dir_name: str) -> Optional[QPixmap]:
        """获取长按箭身皮肤"""
        file_name = f"{dir_name} Hold Body active (doubleres) 6x1.png"
        pix = self._read_png(file_name)
        if pix:
            col, row = self._parse_grid(file_name)
            return self._crop_frame(pix, col, row, frame_idx=0)

        # 尝试其他文件名模式
        patterns = [
            f"{dir_name} Hold Body",
            f"{dir_name}_Hold_Body",
            f"{dir_name} hold body",
        ]
        for pattern in patterns:
            for root, dirs, files in os.walk(self._skin_dir):
                for file in files:
                    if pattern.lower() in file.lower() and file.lower().endswith('.png'):
                        pix = QPixmap(os.path.join(root, file))
                        if not pix.isNull():
                            col, row = self._parse_grid(file)
                            return self._crop_frame(pix, col, row, frame_idx=0)

        # 右侧箭头复用左侧并翻转
        if dir_name == "UpRight":
            left_pix = self._get_hold_body("UpLeft")
            return self._flip_horizontal(left_pix, "Flip:UpLeft:HoldBody") if left_pix else None
        if dir_name == "DownRight":
            left_pix = self._get_hold_body("DownLeft")
            return self._flip_horizontal(left_pix, "Flip:DownLeft:HoldBody") if left_pix else None

        return None

    def _get_hold_tail(self, dir_name: str) -> Optional[QPixmap]:
        """获取长按箭尾皮肤"""
        file_name = f"{dir_name} Hold BottomCap active (doubleres) 6x1.png"
        pix = self._read_png(file_name)
        if pix:
            col, row = self._parse_grid(file_name)
            return self._crop_frame(pix, col, row, frame_idx=0)

        # 尝试其他文件名模式
        patterns = [
            f"{dir_name} Hold BottomCap",
            f"{dir_name}_Hold_BottomCap",
            f"{dir_name} hold bottomcap",
            f"{dir_name} Hold Tail",
        ]
        for pattern in patterns:
            for root, dirs, files in os.walk(self._skin_dir):
                for file in files:
                    if pattern.lower() in file.lower() and file.lower().endswith('.png'):
                        pix = QPixmap(os.path.join(root, file))
                        if not pix.isNull():
                            col, row = self._parse_grid(file)
                            return self._crop_frame(pix, col, row, frame_idx=0)

        # 右侧箭头复用左侧并翻转
        if dir_name == "UpRight":
            left_pix = self._get_hold_tail("UpLeft")
            return self._flip_horizontal(left_pix, "Flip:UpLeft:HoldCap") if left_pix else None
        if dir_name == "DownRight":
            left_pix = self._get_hold_tail("DownLeft")
            return self._flip_horizontal(left_pix, "Flip:DownLeft:HoldCap") if left_pix else None

        return None

    def _get_receptor(self, dir_name: str) -> Optional[QPixmap]:
        """获取判定区皮肤"""
        # Center特殊处理
        if dir_name == "Center":
            file_name = "Center Ready Receptor (doubleres) 1x3.png"
            pix = self._read_png(file_name)
            if pix:
                col, row = self._parse_grid(file_name)
                return self._crop_frame(pix, col, row, frame_idx=1)  # 使用中间帧

        # UpLeft和DownLeft
        if dir_name in ["UpLeft", "DownLeft"]:
            file_name = f"{dir_name} Ready Receptor (doubleres) 1x3.png"
            pix = self._read_png(file_name)
            if pix:
                col, row = self._parse_grid(file_name)
                return self._crop_frame(pix, col, row, frame_idx=1)  # 使用中间帧

        # 尝试其他文件名模式
        patterns = [
            f"{dir_name} Ready Receptor",
            f"{dir_name}_Ready_Receptor",
            f"{dir_name} receptor",
        ]
        for pattern in patterns:
            for root, dirs, files in os.walk(self._skin_dir):
                for file in files:
                    if pattern.lower() in file.lower() and file.lower().endswith('.png'):
                        pix = QPixmap(os.path.join(root, file))
                        if not pix.isNull():
                            col, row = self._parse_grid(file)
                            return self._crop_frame(pix, col, row, frame_idx=min(1, col * row - 1))

        # 右侧判定区复用左侧并翻转
        if dir_name == "UpRight":
            left_pix = self._get_receptor("UpLeft")
            return self._flip_horizontal(left_pix, "Flip:UpLeft:Receptor") if left_pix else None
        if dir_name == "DownRight":
            left_pix = self._get_receptor("DownLeft")
            return self._flip_horizontal(left_pix, "Flip:DownLeft:Receptor") if left_pix else None

        return None

    def close(self):
        """关闭并释放资源"""
        self._tap_pixmaps = [None] * 5
        self._hold_body_pixmaps = [None] * 5
        self._hold_tail_pixmaps = [None] * 5
        self._receptor_pixmaps = [None] * 5
        self._cache.clear()
        self._flip_cache.clear()
        self._loaded = False

    def get_tap(self, track: int) -> Optional[QPixmap]:
        """获取点按箭头"""
        if 0 <= track < 5:
            return self._tap_pixmaps[track]
        return None

    def get_hold_body_pix(self, track: int) -> Optional[QPixmap]:
        """获取长按箭身"""
        if 0 <= track < 5:
            return self._hold_body_pixmaps[track]
        return None

    def get_hold_tail_pix(self, track: int) -> Optional[QPixmap]:
        """获取长按箭尾"""
        if 0 <= track < 5:
            return self._hold_tail_pixmaps[track]
        return None

    def get_receptor_pix(self, track: int) -> Optional[QPixmap]:
        """获取判定区"""
        if 0 <= track < 5:
            return self._receptor_pixmaps[track]
        return None
