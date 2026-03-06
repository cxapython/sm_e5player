# -*- coding: utf-8 -*-
"""
SM文件解析模块
负责解析StepMania .sm谱面文件，提取歌曲信息和箭头事件
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional


# ========================= 数据类定义 =========================

@dataclass
class ChartInfo:
    """SM谱面基础信息"""
    title: str = ""
    subtitle: str = ""
    artist: str = ""
    offset: float = 0.0
    bpm_list: List[Tuple[float, float]] = field(default_factory=list)  # (beat, bpm)
    display_bpm_original: str = ""
    bpms_original: str = ""
    stops: List[Tuple[float, float]] = field(default_factory=list)  # (beat, duration)


@dataclass
class NotesBlock:
    """SM的NOTES区块数据"""
    steps_type: str = ""       # dance-single, dance-double等
    description: str = ""       # 描述
    difficulty: str = ""        # 难度名：Beginner, Easy, Medium, Hard, Challenge
    level: str = ""             # 难度等级数字
    radar: str = ""             # 雷达数据
    measure_text: str = ""      # 小节文本


@dataclass
class ArrowEvent:
    """箭头事件：播放核心数据结构"""
    track_idx: int = 0         # 轨道索引 (0-4)
    start_sec: float = 0.0     # 开始时间（秒）
    end_sec: float = 0.0       # 结束时间（秒，点按为0）
    a_type: int = 0            # 箭头类型
    original_line_no: int = 0  # 原始行号
    original_length: int = 0   # 原始长度


@dataclass
class TimelineSegment:
    """时间轴分段"""
    line_no: int = 0           # 起始行号
    start_sec: float = 0.0     # 起始秒数
    bpm: float = 120.0         # BPM


# ========================= 常量定义 =========================

# 每拍候选tick数
TICK_PER_BEAT_CANDIDATES = [96, 48, 192]

# aType映射候选列表（5轨道）
ATYPE_MAP_CANDIDATES = [
    [1, 2, 4, 6, 7],  # 标准映射
    [2, 1, 4, 7, 6],
    [6, 7, 4, 1, 2],
    [7, 6, 4, 2, 1],
]

# 轨道方向名
TRACK_DIRECTIONS = ["DownLeft", "UpLeft", "Center", "UpRight", "DownRight"]


# ========================= 工具函数 =========================

def safe_float(text: str, default: float = 0.0) -> float:
    """安全转换为浮点型，失败返回默认值"""
    try:
        return float(str(text).strip())
    except (ValueError, TypeError):
        return default


def remove_comments_whitespace(text: str) -> str:
    """移除文本中的注释和空白行"""
    line_list = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("//"):
            continue
        if "//" in line:
            line = line.split("//", 1)[0].strip()
        if line:
            line_list.append(line)
    return "\n".join(line_list)


def parse_sm_key_tag(sm_content: str, tag_name: str) -> Optional[str]:
    """解析SM文件的键值标签，如#TITLE、#OFFSET"""
    match = re.search(
        rf"#{re.escape(tag_name)}:(.*?);",
        sm_content,
        flags=re.IGNORECASE | re.DOTALL
    )
    if not match:
        return None
    return match.group(1).strip()


def parse_sm_bpms(bpms_text: str) -> List[Tuple[float, float]]:
    """解析#BPMS标签为(beat, bpm)列表"""
    result: List[Tuple[float, float]] = []
    if not bpms_text:
        return result
    for segment in bpms_text.split(","):
        segment = segment.strip()
        if not segment or "=" not in segment:
            continue
        parts = segment.split("=", 1)
        if len(parts) == 2:
            beat = safe_float(parts[0])
            bpm = safe_float(parts[1])
            if bpm > 0:
                result.append((beat, bpm))
    result.sort(key=lambda x: x[0])
    return result


def parse_sm_stops(stops_text: str) -> List[Tuple[float, float]]:
    """解析#STOPS标签为(beat, duration)列表"""
    result: List[Tuple[float, float]] = []
    if not stops_text:
        return result
    for segment in stops_text.split(","):
        segment = segment.strip()
        if not segment or "=" not in segment:
            continue
        parts = segment.split("=", 1)
        if len(parts) == 2:
            beat = safe_float(parts[0])
            duration = safe_float(parts[1])
            result.append((beat, duration))
    result.sort(key=lambda x: x[0])
    return result


def parse_sm_notes_blocks(sm_content: str) -> List[NotesBlock]:
    """解析SM文件的所有#NOTES区块"""
    block_list: List[NotesBlock] = []
    for match in re.finditer(r"#NOTES:(.*?);", sm_content, flags=re.IGNORECASE | re.DOTALL):
        block_original = match.group(1).strip()
        segments = block_original.split(":", 5)
        if len(segments) < 6:
            continue
        block_list.append(NotesBlock(
            steps_type=segments[0].strip(),
            description=segments[1].strip(),
            difficulty=segments[2].strip(),
            level=segments[3].strip(),
            radar=segments[4].strip(),
            measure_text=segments[5].strip()
        ))
    return block_list


# ========================= SM解析器类 =========================

class SmParser:
    """SM文件解析器"""

    def __init__(self, tick_per_beat: int = 96):
        """
        初始化解析器

        Args:
            tick_per_beat: 每拍tick数，默认96
        """
        self.tick_per_beat = tick_per_beat
        self.chart_info: Optional[ChartInfo] = None
        self.notes_blocks: List[NotesBlock] = []
        self.atype_map: List[int] = ATYPE_MAP_CANDIDATES[0]

    def parse_file(self, sm_path: str) -> Tuple[ChartInfo, List[NotesBlock]]:
        """
        解析SM文件

        Args:
            sm_path: SM文件路径

        Returns:
            (ChartInfo, List[NotesBlock]): 谱面信息和NOTES区块列表
        """
        if not os.path.exists(sm_path):
            raise FileNotFoundError(f"SM文件不存在: {sm_path}")

        with open(sm_path, "r", encoding="utf-8", errors="ignore") as f:
            sm_content = f.read()

        # 解析基础信息
        chart_info = ChartInfo()
        chart_info.title = parse_sm_key_tag(sm_content, "TITLE") or ""
        chart_info.subtitle = parse_sm_key_tag(sm_content, "SUBTITLE") or ""
        chart_info.artist = parse_sm_key_tag(sm_content, "ARTIST") or ""
        chart_info.offset = safe_float(parse_sm_key_tag(sm_content, "OFFSET") or "0", 0.0)
        chart_info.display_bpm_original = parse_sm_key_tag(sm_content, "DISPLAYBPM") or ""
        chart_info.bpms_original = parse_sm_key_tag(sm_content, "BPMS") or ""
        chart_info.bpm_list = parse_sm_bpms(chart_info.bpms_original)

        # 解析STOPS
        stops_text = parse_sm_key_tag(sm_content, "STOPS") or ""
        chart_info.stops = parse_sm_stops(stops_text)

        # 解析NOTES区块
        notes_blocks = parse_sm_notes_blocks(sm_content)

        self.chart_info = chart_info
        self.notes_blocks = notes_blocks

        return chart_info, notes_blocks

    def detect_column_count(self, notes_block: NotesBlock) -> int:
        """检测NOTES区块的有效列数"""
        measure_list = self.split_measure_text(notes_block.measure_text)
        first_line_len = 0
        for line_list in measure_list:
            for line in line_list:
                if not first_line_len:
                    first_line_len = len(line)
                if set(line) != {"0"}:
                    return len(line)
        return first_line_len

    def recommend_atype_map(self, column_count: int) -> Tuple[List[int], str]:
        """根据列数推荐aType映射列表"""
        if column_count == 5:
            return [1, 2, 4, 6, 7], "5列：使用标准映射"
        if column_count == 10:
            return list(range(1, 11)), "10列：连续编号兜底"
        if column_count > 0:
            return list(range(1, column_count + 1)), f"{column_count}列：连续编号兜底"
        return [1, 2, 4, 6, 7], "未检测到列数：使用5列标准映射兜底"

    @staticmethod
    def split_measure_text(measure_text: str) -> List[List[str]]:
        """将NOTES的小节文本切分为[小节[行]]的结构"""
        cleaned = remove_comments_whitespace(measure_text)
        measure_blocks = [s.strip() for s in cleaned.split(",")]
        result: List[List[str]] = []
        for single_measure in measure_blocks:
            if not single_measure:
                continue
            lines = [ln.strip() for ln in single_measure.splitlines() if ln.strip()]
            if lines:
                result.append(lines)
        return result

    @staticmethod
    def calculate_line_no(measure_idx: int, line_idx: int, measure_line_count: int,
                          tick_per_beat: int) -> int:
        """根据小节号、行号计算对应的lineNo"""
        if measure_line_count <= 0:
            return int(round(measure_idx * 4 * tick_per_beat))
        beat = (measure_idx * 4.0) + (line_idx * 4.0 / float(measure_line_count))
        return int(round(beat * tick_per_beat))

    def parse_arrow_events(self, notes_block: NotesBlock,
                           player_id: int = 1) -> Tuple[Dict[int, List[dict]], List[str]]:
        """
        解析NOTES区块为箭头事件表

        Args:
            notes_block: NOTES区块数据
            player_id: 玩家ID

        Returns:
            (event_table, warn_list): 事件表{lineNo: [箭头信息]}和警告列表
        """
        warn_list: List[str] = []
        event_table: Dict[int, List[dict]] = {}
        holding_long: Dict[int, int] = {}  # 记录进行中的长按：列号->开始lineNo
        measure_list = self.split_measure_text(notes_block.measure_text)
        total_measures = len(measure_list)
        last_line_no = int(round((total_measures * 4.0) * self.tick_per_beat))

        for measure_idx, line_list in enumerate(measure_list):
            measure_line_count = len(line_list)
            for line_idx, line_str in enumerate(line_list):
                line_no = self.calculate_line_no(
                    measure_idx, line_idx, measure_line_count, self.tick_per_beat
                )
                col_count = len(line_str)

                # 列数不匹配时的警告
                if col_count != len(self.atype_map):
                    warn_list.append(
                        f"列数不匹配：第{measure_idx+1}小节第{line_idx+1}行 "
                        f"行长度={col_count} 映射长度={len(self.atype_map)}"
                    )

                valid_col_count = min(col_count, len(self.atype_map))

                # 解析每一列的符号
                for col in range(valid_col_count):
                    symbol = line_str[col]
                    a_type = self.atype_map[col]

                    if symbol == "0":
                        continue

                    # 点按箭头
                    if symbol == "1":
                        event_table.setdefault(line_no, []).append(
                            {"aType": a_type, "length": 0, "player": player_id}
                        )
                        continue

                    # 长按开始
                    if symbol in ("2", "4"):
                        if col in holding_long:
                            warn_list.append(
                                f"重复长按开始：列{col} lineNo={line_no} "
                                f"覆盖上一段开始{holding_long[col]}"
                            )
                        holding_long[col] = line_no
                        continue

                    # 长按结束
                    if symbol == "3":
                        if col not in holding_long:
                            warn_list.append(f"长按结束无开始：列{col} lineNo={line_no}")
                            continue
                        start_line_no = holding_long.pop(col)
                        length = max(0, line_no - start_line_no)
                        event_table.setdefault(start_line_no, []).append(
                            {"aType": a_type, "length": length, "player": player_id}
                        )
                        continue

                    # 未知符号
                    warn_list.append(f"未知符号忽略：'{symbol}' lineNo={line_no} 列{col}")

        # 处理未闭合的长按
        for col, start_line_no in list(holding_long.items()):
            a_type = self.atype_map[col] if col < len(self.atype_map) else (col + 1)
            length = max(0, last_line_no - start_line_no)
            event_table.setdefault(start_line_no, []).append(
                {"aType": a_type, "length": length, "player": player_id}
            )
            warn_list.append(
                f"长按未闭合：列{col} 开始{start_line_no} "
                f"自动闭合到末尾{last_line_no} 长度{length}"
            )

        return event_table, warn_list


# ========================= 时间轴计算 =========================

def generate_timeline_segments(bpm_list: List[Tuple[float, float]],
                                tick_per_beat: int) -> List[TimelineSegment]:
    """
    根据BPM列表生成时间轴分段

    Args:
        bpm_list: BPM列表 [(beat, bpm), ...]
        tick_per_beat: 每拍tick数

    Returns:
        时间轴分段列表
    """
    segments: List[TimelineSegment] = []
    for i, (beat, bpm) in enumerate(bpm_list):
        line_no = int(round(beat * tick_per_beat))
        if i == 0:
            segments.append(TimelineSegment(line_no=line_no, start_sec=0.0, bpm=bpm))
            continue

        last_segment = segments[-1]
        delta_line = line_no - last_segment.line_no
        if delta_line < 0:
            continue

        beat_count = delta_line / float(tick_per_beat)
        delta_sec = 0.0 if last_segment.bpm <= 0 else beat_count * (60.0 / last_segment.bpm)
        current_sec = last_segment.start_sec + delta_sec
        segments.append(TimelineSegment(line_no=line_no, start_sec=current_sec, bpm=bpm))

    # 兜底：无BPM时默认120BPM
    if not segments:
        segments = [TimelineSegment(line_no=0, start_sec=0.0, bpm=120.0)]

    return segments


def line_no_to_sec(line_no: int, timeline_segments: List[TimelineSegment],
                   tick_per_beat: int) -> float:
    """
    将lineNo转换为实际的秒数

    Args:
        line_no: 行号
        timeline_segments: 时间轴分段
        tick_per_beat: 每拍tick数

    Returns:
        秒数
    """
    # 二分查找所属的时间轴分段
    lo, hi = 0, len(timeline_segments) - 1
    idx = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if timeline_segments[mid].line_no <= line_no:
            idx = mid
            lo = mid + 1
        else:
            hi = mid - 1

    segment = timeline_segments[idx]
    delta_line = line_no - segment.line_no
    beat_count = delta_line / float(tick_per_beat)
    return segment.start_sec if segment.bpm <= 0 else segment.start_sec + beat_count * (60.0 / segment.bpm)


def build_arrow_events(event_table: Dict[int, List[dict]],
                       timeline_segments: List[TimelineSegment],
                       tick_per_beat: int,
                       atype_map: List[int]) -> List[ArrowEvent]:
    """
    将SM解析的事件表转换为播放用的ArrowEvent列表

    Args:
        event_table: 事件表 {lineNo: [箭头信息]}
        timeline_segments: 时间轴分段
        tick_per_beat: 每拍tick数
        atype_map: aType映射

    Returns:
        ArrowEvent列表
    """
    atype_to_track = {a: i for i, a in enumerate(atype_map)}
    arrow_events: List[ArrowEvent] = []

    for line_no, arrow_list in sorted(event_table.items()):
        for arrow in arrow_list:
            a_type = arrow.get("aType", 0)
            length = arrow.get("length", 0)

            if a_type not in atype_to_track:
                continue

            track_idx = atype_to_track[a_type]
            start_sec = line_no_to_sec(line_no, timeline_segments, tick_per_beat)
            end_sec = (line_no_to_sec(line_no + max(0, length), timeline_segments, tick_per_beat)
                      if length > 0 else start_sec)

            arrow_events.append(ArrowEvent(
                track_idx=track_idx,
                start_sec=start_sec,
                end_sec=end_sec,
                a_type=a_type,
                original_line_no=line_no,
                original_length=length
            ))

    # 按开始时间排序
    arrow_events.sort(key=lambda e: e.start_sec)
    return arrow_events


def extract_available_bpm(display_bpm_original: str, bpms_original: str) -> Optional[float]:
    """
    从SM的DISPLAYBPM/BPMS中提取有效BPM值

    Args:
        display_bpm_original: DISPLAYBPM标签值
        bpms_original: BPMS标签值

    Returns:
        有效BPM值，无法提取时返回None
    """
    # 优先解析DISPLAYBPM
    if display_bpm_original:
        text = display_bpm_original.strip()
        if text != "*" and text.lower() != "random":
            match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
            if match:
                try:
                    val = float(match.group(0))
                    if val > 0:
                        return val
                except ValueError:
                    pass

    # 解析BPMS的=后值
    if bpms_original:
        text = bpms_original.strip()
        match = re.search(r"[-+]?\d+(?:\.\d+)?\s*=\s*([-+]?\d+(?:\.\d+)?)", text)
        if match:
            try:
                val = float(match.group(1))
                if val > 0:
                    return val
            except ValueError:
                pass

    return None


def get_most_common_interval(line_list: List[int]) -> Optional[int]:
    """
    获取lineNo列表中最常见的间隔

    Args:
        line_list: lineNo列表

    Returns:
        最常见的间隔，无法计算时返回None
    """
    if len(line_list) < 3:
        return None

    sorted_lines = sorted(set(line_list))
    interval_count: Dict[int, int] = {}

    for i in range(1, len(sorted_lines)):
        d = sorted_lines[i] - sorted_lines[i - 1]
        if d <= 0:
            continue
        interval_count[d] = interval_count.get(d, 0) + 1

    if not interval_count:
        return None

    return max(interval_count.items(), key=lambda x: x[1])[0]


def format_seconds(sec: float) -> str:
    """秒数格式化：00:00.00"""
    if sec < 0:
        sec = 0
    m = int(sec // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 100)
    return f"{m:02d}:{s:02d}.{ms:02d}"


def find_audio_in_same_dir(chart_path: str) -> Optional[str]:
    """
    在谱面文件同目录查找音频文件

    Args:
        chart_path: 谱面文件路径

    Returns:
        音频文件路径，未找到返回None
    """
    dir_path = os.path.dirname(os.path.abspath(chart_path))
    if not os.path.isdir(dir_path):
        return None

    ext_priority = [".ogg", ".mp3", ".wav"]
    all_candidates: List[Tuple[str, int, int]] = []  # (路径, 扩展名优先级, 名称匹配分)
    chart_basename = os.path.splitext(os.path.basename(chart_path))[0].lower()

    for file_name in os.listdir(dir_path):
        file_path = os.path.join(dir_path, file_name)
        if not os.path.isfile(file_path):
            continue

        lower_name = file_name.lower()
        ext = os.path.splitext(lower_name)[1]

        if ext not in ext_priority:
            continue

        ext_score = ext_priority.index(ext)
        base_name = os.path.splitext(file_name)[0].lower()
        match_score = 2 if base_name in chart_basename else (1 if chart_basename in base_name else 0)
        all_candidates.append((file_path, ext_score, match_score))

    if not all_candidates:
        return None

    # 按优先级排序
    all_candidates.sort(key=lambda x: (x[1], -x[2]))
    return all_candidates[0][0]
