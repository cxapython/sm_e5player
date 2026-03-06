# -*- coding: utf-8 -*-
"""
皮肤管理模块（PyQt6版本）
负责加载和管理游戏皮肤资源
"""

import os
from typing import Optional, List, Dict
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt


class SkinManager:
    """皮肤管理器"""

    def __init__(self, skin_dir: str):
        """
        初始化皮肤管理器

        Args:
            skin_dir: 皮肤目录路径
        """
        self._skin_dir = skin_dir
        self._loaded = False

        # 皮肤资源
        self._tap_pixmaps: List[Optional[QPixmap]] = [None] * 5
        self._hold_body_pixmaps: List[Optional[QPixmap]] = [None] * 5
        self._hold_tail_pixmaps: List[Optional[QPixmap]] = [None] * 5
        self._receptor_pixmaps: List[Optional[QPixmap]] = [None] * 5

        # 箭头类型映射 (DownLeft, UpLeft, Center, UpRight, DownRight)
        self._arrow_names = ["DownLeft", "UpLeft", "Center", "UpRight", "DownRight"]

    def open(self) -> bool:
        """打开并加载皮肤"""
        if not self._skin_dir or not os.path.isdir(self._skin_dir):
            return False

        try:
            for i, name in enumerate(self._arrow_names):
                # 加载点按箭头
                tap_path = self._find_skin_file(name, "Tap Note")
                if tap_path:
                    self._tap_pixmaps[i] = QPixmap(tap_path)

                # 加载长按箭身
                hold_body_path = self._find_skin_file(name, "Hold Body")
                if hold_body_path:
                    self._hold_body_pixmaps[i] = QPixmap(hold_body_path)

                # 加载长按箭尾
                hold_tail_path = self._find_skin_file(name, "Hold BottomCap")
                if hold_tail_path:
                    self._hold_tail_pixmaps[i] = QPixmap(hold_tail_path)

                # 加载判定区
                receptor_path = self._find_skin_file(name, "Ready Receptor")
                if receptor_path:
                    self._receptor_pixmaps[i] = QPixmap(receptor_path)

            self._loaded = True
            return True

        except Exception as e:
            print(f"[SkinManager] 加载皮肤失败: {e}")
            return False

    def _find_skin_file(self, arrow_type: str, skin_type: str) -> Optional[str]:
        """查找皮肤文件"""
        # 可能的文件名模式
        patterns = [
            f"{arrow_type} {skin_type}",
            f"{arrow_type} {skin_type} active",
            f"{arrow_type}_{skin_type}",
            f"{arrow_type}_{skin_type}_active",
        ]

        # 遍历皮肤目录
        for root, dirs, files in os.walk(self._skin_dir):
            for file in files:
                file_lower = file.lower()
                for pattern in patterns:
                    if pattern.lower() in file_lower:
                        return os.path.join(root, file)

        return None

    def close(self):
        """关闭并释放资源"""
        self._tap_pixmaps = [None] * 5
        self._hold_body_pixmaps = [None] * 5
        self._hold_tail_pixmaps = [None] * 5
        self._receptor_pixmaps = [None] * 5
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