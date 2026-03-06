# -*- coding: utf-8 -*-
"""
歌曲扫描模块（PyQt6版本）
使用QThread进行后台扫描
"""

import os
from typing import List, Optional
from PyQt6.QtCore import QThread, pyqtSignal

from directory_parser import SongInfo, DirectoryParser


class SongScanner(QThread):
    """歌曲扫描器，在后台线程中扫描歌曲"""

    scan_progress = pyqtSignal(int, int)
    scan_complete = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scan_path = ""
        self._songs: List[SongInfo] = []
        self._parser = DirectoryParser()

    @property
    def scan_path(self) -> str:
        return self._scan_path

    def set_path(self, path: str):
        """设置扫描路径"""
        self._scan_path = path

    @property
    def song_count(self) -> int:
        """获取歌曲数量"""
        return len(self._songs)

    def run(self):
        """执行扫描"""
        self._songs = []

        if not self._scan_path or not os.path.isdir(self._scan_path):
            self.scan_complete.emit([])
            return

        # 获取所有子目录
        subdirs = []
        for item in os.listdir(self._scan_path):
            item_path = os.path.join(self._scan_path, item)
            if os.path.isdir(item_path):
                subdirs.append(item_path)

        total = len(subdirs)

        for i, subdir in enumerate(subdirs):
            # 发送进度
            self.scan_progress.emit(i + 1, total)

            # 解析目录
            song_info = DirectoryParser.scan_song_folder(subdir)
            if song_info and song_info.has_sm:
                self._songs.append(song_info)

        # 完成扫描
        self.scan_complete.emit(self._songs)

    def get_songs(self) -> List[SongInfo]:
        """获取扫描结果"""
        return self._songs