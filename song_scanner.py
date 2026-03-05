# -*- coding: utf-8 -*-
"""
歌曲扫描模块
职责：扫描指定目录下的所有歌曲文件夹，返回歌曲列表
"""

import os
from typing import List, Optional, Callable
from directory_parser import SongInfo, DirectoryParser


class SongScanner:
    """歌曲扫描器，负责扫描和管理歌曲列表"""

    def __init__(self, scan_path: str = ""):
        """
        初始化扫描器

        Args:
            scan_path: 扫描路径，可后续通过 scan() 设置
        """
        self._scan_path = scan_path
        self._songs: List[SongInfo] = []
        self._parser = DirectoryParser()

    @property
    def scan_path(self) -> str:
        """获取扫描路径"""
        return self._scan_path

    @scan_path.setter
    def scan_path(self, path: str) -> None:
        """设置扫描路径"""
        self._scan_path = path

    @property
    def songs(self) -> List[SongInfo]:
        """获取歌曲列表"""
        return self._songs

    @property
    def song_count(self) -> int:
        """获取歌曲总数"""
        return len(self._songs)

    @property
    def valid_song_count(self) -> int:
        """获取有效歌曲数（有sm文件的）"""
        return sum(1 for s in self._songs if s.has_sm)

    def scan(self, path: Optional[str] = None, progress_callback: Optional[Callable[[int, int], None]] = None) -> List[SongInfo]:
        """
        扫描指定路径下的所有歌曲文件夹

        Args:
            path: 扫描路径，为None时使用 self._scan_path
            progress_callback: 进度回调函数 (current, total)

        Returns:
            List[SongInfo]: 歌曲信息列表
        """
        if path:
            self._scan_path = path

        if not self._scan_path or not os.path.isdir(self._scan_path):
            self._songs = []
            return self._songs

        self._songs = []

        # 获取所有子目录
        try:
            entries = os.listdir(self._scan_path)
            folders = [
                os.path.join(self._scan_path, entry)
                for entry in entries
                if os.path.isdir(os.path.join(self._scan_path, entry))
                and not entry.startswith('.')  # 排除隐藏目录
            ]
        except OSError:
            return self._songs

        total = len(folders)

        # 扫描每个文件夹
        for i, folder_path in enumerate(folders):
            try:
                song_info = DirectoryParser.scan_song_folder(folder_path)
                # 只添加有谱面文件的文件夹
                if song_info.has_sm:
                    self._songs.append(song_info)
            except Exception:
                # 忽略扫描错误的文件夹
                pass

            # 进度回调
            if progress_callback:
                progress_callback(i + 1, total)

        # 按显示名称排序
        self._songs.sort(key=lambda s: s.display_name.lower())

        return self._songs

    def refresh(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> List[SongInfo]:
        """
        刷新歌曲列表（重新扫描）

        Args:
            progress_callback: 进度回调函数

        Returns:
            List[SongInfo]: 刷新后的歌曲列表
        """
        return self.scan(progress_callback=progress_callback)

    def get_page(self, page: int, per_page: int = 8) -> List[SongInfo]:
        """
        获取指定页的歌曲

        Args:
            page: 页码（从0开始）
            per_page: 每页数量

        Returns:
            List[SongInfo]: 该页的歌曲列表
        """
        start = page * per_page
        end = start + per_page
        return self._songs[start:end]

    @property
    def total_pages(self) -> int:
        """获取总页数（每页8个）"""
        return (self.song_count + 7) // 8

    def search(self, keyword: str) -> List[SongInfo]:
        """
        搜索歌曲

        Args:
            keyword: 搜索关键词

        Returns:
            List[SongInfo]: 匹配的歌曲列表
        """
        if not keyword:
            return self._songs

        keyword_lower = keyword.lower()
        return [
            s for s in self._songs
            if keyword_lower in s.display_name.lower()
            or keyword_lower in s.folder_name.lower()
        ]

    def get_by_path(self, folder_path: str) -> Optional[SongInfo]:
        """
        根据路径获取歌曲信息

        Args:
            folder_path: 文件夹路径

        Returns:
            Optional[SongInfo]: 歌曲信息，未找到返回None
        """
        for song in self._songs:
            if song.folder_path == folder_path:
                return song
        return None

    def filter_by_star(self, min_star: Optional[int] = None, max_star: Optional[int] = None) -> List[SongInfo]:
        """
        按星级筛选歌曲

        Args:
            min_star: 最小星级（None表示不限）
            max_star: 最大星级（None表示不限）

        Returns:
            List[SongInfo]: 符合条件的歌曲列表
        """
        result = []
        for song in self._songs:
            star = song.star_rating
            # 无星级的歌曲
            if star is None:
                if min_star is None and max_star is None:
                    result.append(song)
                continue

            # 星级筛选
            if min_star is not None and star < min_star:
                continue
            if max_star is not None and star > max_star:
                continue
            result.append(song)

        return result

    def get_star_range(self) -> tuple:
        """
        获取歌曲星级的范围

        Returns:
            tuple: (最小星级, 最大星级)，无星级歌曲返回 (None, None)
        """
        stars = [s.star_rating for s in self._songs if s.star_rating is not None]
        if not stars:
            return (None, None)
        return (min(stars), max(stars))
