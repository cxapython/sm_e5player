# -*- coding: utf-8 -*-
"""
目录解析模块
负责解析歌曲目录名称、提取星级信息、查找资源文件（SM、音频、封面）
"""

import os
from dataclasses import dataclass
from typing import Optional, List, Tuple


@dataclass
class SongInfo:
    """歌曲信息数据类"""
    folder_path: str              # 目录完整路径
    folder_name: str              # 原始目录名
    display_name: str             # 显示名称（解析后）
    star_rating: Optional[int]    # 星级（1-20），无则为None
    sm_file: Optional[str]        # SM文件路径
    json_file: Optional[str]      # JSON谱面文件路径
    audio_file: Optional[str]     # 音频文件路径
    banner_file: Optional[str]    # 封面图片路径

    @property
    def has_chart(self) -> bool:
        """是否有谱面文件（SM或JSON）"""
        return self.sm_file is not None or self.json_file is not None

    @property
    def has_sm(self) -> bool:
        """是否有SM谱面文件"""
        return self.sm_file is not None

    @property
    def has_json(self) -> bool:
        """是否有JSON谱面文件"""
        return self.json_file is not None

    @property
    def has_audio(self) -> bool:
        """是否有音频文件"""
        return self.audio_file is not None

    @property
    def has_banner(self) -> bool:
        """是否有封面图片"""
        return self.banner_file is not None

    @property
    def star_display(self) -> str:
        """星级显示文本"""
        if self.star_rating is not None:
            return f"★{self.star_rating}"
        return ""


class DirectoryParser:
    """目录解析器，处理歌曲目录的各种解析操作"""

    # 支持的音频格式（按优先级排序）
    AUDIO_EXTENSIONS = [".ogg", ".mp3", ".wav"]
    # 支持的封面图片格式
    BANNER_NAMES = ["bn.jpg", "banner.jpg", "bn.png", "banner.png",
                    "BN.jpg", "Banner.jpg", "BN.png", "Banner.png",
                    "bann.jpg", "bann.png"]

    @staticmethod
    def parse_folder_name(folder_name: str) -> Tuple[str, Optional[int]]:
        """
        解析目录名称，提取显示名称和星级

        格式规则:
        - "SPEED_DEVIL#song_name#8" -> ("song_name", 8)
        - "song_name#8" -> ("song_name", 8)
        - "自定义前缀#song_name#8" -> ("song_name", 8)
        - 只要最后一个#后面是数字(1-20)，就作为星级，倒数第二部分作为显示名
        - "普通歌名" -> ("普通歌名", None)

        :param folder_name: 目录名称
        :return: (显示名称, 星级) 元组，无星级时星级为None
        """
        # 检查是否包含#分隔符
        if '#' not in folder_name:
            return (folder_name, None)

        parts = folder_name.split('#')

        # 至少需要2部分：NAME#STAR 或 PREFIX#NAME#STAR
        if len(parts) >= 2:
            try:
                # 最后一部分尝试解析为星级
                star = int(parts[-1])
                # 星级范围检查（合理范围1-20）
                if 1 <= star <= 20:
                    # 倒数第二部分为显示名称
                    display_name = parts[-2] if len(parts) >= 2 else parts[0]
                    if display_name:
                        return (display_name, star)
            except ValueError:
                pass

        # 解析失败，返回原始名称
        return (folder_name, None)

    @staticmethod
    def find_sm_file(folder_path: str) -> Optional[str]:
        """
        在目录中查找SM谱面文件

        :param folder_path: 歌曲目录路径
        :return: SM文件路径，未找到返回None
        """
        if not os.path.isdir(folder_path):
            return None

        sm_files = []
        for file_name in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file_name)
            if os.path.isfile(file_path) and file_name.lower().endswith(".sm"):
                sm_files.append(file_path)

        if not sm_files:
            return None

        # 如果有多个SM文件，优先选择与目录名相似的
        folder_name = os.path.basename(folder_path)
        for sm_file in sm_files:
            sm_name = os.path.splitext(os.path.basename(sm_file))[0]
            if sm_name.lower() in folder_name.lower():
                return sm_file

        # 否则返回第一个找到的
        return sm_files[0]

    @staticmethod
    def find_json_file(folder_path: str) -> Optional[str]:
        """
        在目录中查找JSON谱面文件

        JSON谱面文件特征：
        - 扩展名为.json
        - 包含boards字段（谱面数据）

        :param folder_path: 歌曲目录路径
        :return: JSON文件路径，未找到返回None
        """
        import json

        if not os.path.isdir(folder_path):
            return None

        json_files = []
        for file_name in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file_name)
            if not os.path.isfile(file_path):
                continue
            if not file_name.lower().endswith(".json"):
                continue

            # 检查是否为谱面JSON（包含boards字段）
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'boards' in data or 'bpms' in data:
                        json_files.append(file_path)
            except (json.JSONDecodeError, UnicodeDecodeError, IOError):
                continue

        if not json_files:
            return None

        # 如果有多个JSON文件，优先选择与目录名相似的
        folder_name = os.path.basename(folder_path)
        for json_file in json_files:
            json_name = os.path.splitext(os.path.basename(json_file))[0]
            if json_name.lower() in folder_name.lower():
                return json_file

        # 否则返回第一个找到的
        return json_files[0]

    @staticmethod
    def find_audio_file(folder_path: str) -> Optional[str]:
        """
        在目录中查找音频文件

        优先级: ogg > mp3 > wav
        如有多个同名文件，优先选择与目录名匹配的

        :param folder_path: 歌曲目录路径
        :return: 音频文件路径，未找到返回None
        """
        if not os.path.isdir(folder_path):
            return None

        # 收集所有音频文件
        audio_candidates: List[Tuple[str, int, int]] = []  # (路径, 扩展名优先级, 名称匹配分)

        folder_name = os.path.basename(folder_path).lower()

        for file_name in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file_name)
            if not os.path.isfile(file_path):
                continue

            lower_name = file_name.lower()
            ext = os.path.splitext(lower_name)[1]

            if ext not in DirectoryParser.AUDIO_EXTENSIONS:
                continue

            # 扩展名优先级
            ext_priority = DirectoryParser.AUDIO_EXTENSIONS.index(ext)

            # 名称匹配分
            base_name = os.path.splitext(file_name)[0].lower()
            match_score = 2 if base_name in folder_name else (1 if folder_name in base_name else 0)

            audio_candidates.append((file_path, ext_priority, match_score))

        if not audio_candidates:
            return None

        # 按优先级排序：扩展名优先级（越小越好）-> 名称匹配分（越大越好）
        audio_candidates.sort(key=lambda x: (x[1], -x[2]))
        return audio_candidates[0][0]

    @staticmethod
    def find_banner_file(folder_path: str) -> Optional[str]:
        """
        在目录中查找封面图片文件

        :param folder_path: 歌曲目录路径
        :return: 封面图片路径，未找到返回None
        """
        if not os.path.isdir(folder_path):
            return None

        # 按预定义顺序查找
        for banner_name in DirectoryParser.BANNER_NAMES:
            banner_path = os.path.join(folder_path, banner_name)
            if os.path.isfile(banner_path):
                return banner_path

        # 查找其他可能的图片文件
        for file_name in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file_name)
            if os.path.isfile(file_path):
                lower_name = file_name.lower()
                if lower_name.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    # 排除太小的文件（可能是图标）
                    if os.path.getsize(file_path) > 5000:  # 大于5KB
                        return file_path

        return None

    @staticmethod
    def scan_song_folder(folder_path: str) -> Optional[SongInfo]:
        """
        扫描单个歌曲目录，提取所有信息

        :param folder_path: 歌曲目录路径
        :return: SongInfo对象，如果目录无效则返回None
        """
        if not os.path.isdir(folder_path):
            return None

        folder_name = os.path.basename(folder_path)

        # 解析目录名
        display_name, star_rating = DirectoryParser.parse_folder_name(folder_name)

        # 查找SM文件
        sm_file = DirectoryParser.find_sm_file(folder_path)

        # 查找JSON谱面文件
        json_file = DirectoryParser.find_json_file(folder_path)

        # 必须有至少一种谱面文件
        if not sm_file and not json_file:
            return None

        # 查找音频文件（可选）
        audio_file = DirectoryParser.find_audio_file(folder_path)

        # 查找封面图片（可选）
        banner_file = DirectoryParser.find_banner_file(folder_path)

        return SongInfo(
            folder_path=folder_path,
            folder_name=folder_name,
            display_name=display_name,
            star_rating=star_rating,
            sm_file=sm_file,
            json_file=json_file,
            audio_file=audio_file,
            banner_file=banner_file
        )
