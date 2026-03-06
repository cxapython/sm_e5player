import io
import json
import os
import re
import time
import traceback
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pygame
import customtkinter as ctk
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _drag_available = True
except Exception:
    _drag_available = False

# 默认皮肤压缩包名
DEFAULT_SKIN_ZIP_NAME = "E5_01.zip"
# 每拍候选tick数
TICK_PER_BEAT_CANDIDATES = [96, 48, 192]
# aType映射候选列表
ATYPE_MAP_CANDIDATES = [
    [1, 2, 4, 6, 7],
    [2, 1, 4, 7, 6],
    [6, 7, 4, 1, 2],
    [7, 6, 4, 2, 1],
]
# 轨道对应方向名
TRACK_DIRECTIONS = ["DownLeft", "UpLeft", "Center", "UpRight", "DownRight"]

# ========================= SM文件解析数据类 =========================
@dataclass
class SmChartInfo:
    """SM谱面基础信息"""
    title: str = ""
    offset: float = 0.0
    bpm_list: List[Tuple[float, float]] = None  # (beat, bpm)
    display_bpm_original: str = ""
    bpms_original: str = ""

@dataclass
class SmNotesBlock:
    """SM的NOTES区块数据"""
    steps_type: str
    description: str
    difficulty: str
    level: str
    radar: str
    measure_text: str

# ========================= 播放核心数据类 =========================
@dataclass
class ArrowEvent:
    """箭头事件：播放核心数据结构"""
    track_idx: int
    start_sec: float
    end_sec: float
    a_type: int
    original_line_no: int
    original_length: int

# ========================= 工具函数（SM解析） =========================
def _safe_float(text: str, default: float = 0.0) -> float:
    """安全转换为浮点型，失败返回默认值"""
    try:
        return float(str(text).strip())
    except Exception:
        return default

def _remove_comments_whitespace(text: str) -> str:
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

def _parse_sm_key_tag(sm_content: str, tag_name: str) -> Optional[str]:
    """解析SM文件的键值标签，如#TITLE、#OFFSET"""
    match = re.search(
        rf"#{re.escape(tag_name)}:(.*?);", sm_content, flags=re.IGNORECASE | re.DOTALL
    )
    if not match:
        return None
    return match.group(1).strip()

def _parse_sm_bpms(bpms_text: str) -> List[Tuple[float, float]]:
    """解析#BPMS标签为(beat, bpm)列表"""
    result: List[Tuple[float, float]] = []
    if not bpms_text:
        return result
    for segment in bpms_text.split(","):
        segment = segment.strip()
        if not segment or "=" not in segment:
            continue
        beat, bpm = segment.split("=", 1)
        result.append((_safe_float(beat), _safe_float(bpm)))
    result.sort(key=lambda x: x[0])
    return result

def _parse_sm_notes_blocks(sm_content: str) -> List[SmNotesBlock]:
    """解析SM文件的所有#NOTES区块"""
    block_list: List[SmNotesBlock] = []
    for match in re.finditer(r"#NOTES:(.*?);", sm_content, flags=re.IGNORECASE | re.DOTALL):
        block_original = match.group(1).strip()
        segments = block_original.split(":", 5)
        if len(segments) < 6:
            continue
        block_list.append(SmNotesBlock(
            steps_type=segments[0].strip(),
            description=segments[1].strip(),
            difficulty=segments[2].strip(),
            level=segments[3].strip(),
            radar=segments[4].strip(),
            measure_text=segments[5].strip()
        ))
    return block_list

def parse_sm_file(sm_path: str) -> Tuple[SmChartInfo, List[SmNotesBlock]]:
    """解析SM文件，返回谱面信息和NOTES区块列表"""
    with open(sm_path, "r", encoding="utf-8", errors="ignore") as f:
        sm_content = f.read()
    chart_info = SmChartInfo()
    chart_info.title = _parse_sm_key_tag(sm_content, "TITLE") or ""
    chart_info.offset = _safe_float(_parse_sm_key_tag(sm_content, "OFFSET") or "0", 0.0)
    chart_info.display_bpm_original = _parse_sm_key_tag(sm_content, "DISPLAYBPM") or ""
    chart_info.bpms_original = _parse_sm_key_tag(sm_content, "BPMS") or ""
    chart_info.bpm_list = _parse_sm_bpms(chart_info.bpms_original)
    notes_blocks = _parse_sm_notes_blocks(sm_content)
    return chart_info, notes_blocks

def extract_available_bpm(display_bpm_original: str, bpms_original: str) -> Optional[float]:
    """从SM的DISPLAYBPM/BPMS中提取有效BPM值，用于兜底"""
    # 优先解析DISPLAYBPM
    if display_bpm_original:
        text = display_bpm_original.strip()
        if text != "*" and text.lower() != "random":
            m = re.search(r"[-+]?\d+(?:\.\d+)?", text)
            if m:
                try:
                    val = float(m.group(0))
                    if val > 0:
                        return val
                except Exception:
                    pass
    # 解析BPMS的=后值
    if bpms_original:
        text = bpms_original.strip()
        m = re.search(r"[-+]?\d+(?:\.\d+)?\s*=\s*([-+]?\d+(?:\.\d+)?)", text)
        if m:
            try:
                val = float(m.group(1))
                if val > 0:
                    return val
            except Exception:
                pass
    return None

def split_measure_text(measure_text: str) -> List[List[str]]:
    """将NOTES的小节文本切分为[小节[行]]的结构"""
    cleaned = _remove_comments_whitespace(measure_text)
    measure_blocks = [s.strip() for s in cleaned.split(",")]
    result: List[List[str]] = []
    for single_measure in measure_blocks:
        if not single_measure:
            continue
        lines = [ln.strip() for ln in single_measure.splitlines() if ln.strip()]
        if lines:
            result.append(lines)
    return result

def calculate_line_no(measure_idx: int, line_idx: int, measure_line_count: int, tick_per_beat: int) -> int:
    """根据小节号、行号计算对应的lineNo"""
    if measure_line_count <= 0:
        return int(round(measure_idx * 4 * tick_per_beat))
    beat = (measure_idx * 4.0) + (line_idx * 4.0 / float(measure_line_count))
    return int(round(beat * tick_per_beat))

def detect_notes_column_count(notes_block: SmNotesBlock) -> int:
    """检测NOTES区块的有效列数"""
    measure_list = split_measure_text(notes_block.measure_text)
    first_line_len = 0
    for line_list in measure_list:
        for line in line_list:
            if not first_line_len:
                first_line_len = len(line)
            if set(line) != {"0"}:
                return len(line)
    return first_line_len

def recommend_atype_map(column_count: int) -> Tuple[List[int], str]:
    """根据列数推荐aType映射列表"""
    if column_count == 5:
        return [1, 2, 4, 6, 7], "5列：使用 1,2,4,6,7 标准映射"
    if column_count == 10:
        return list(range(1, 11)), "10列：连续编号兜底（需确认引擎aType规则）"
    if column_count > 0:
        return list(range(1, column_count + 1)), f"{column_count}列：非标准列数，连续编号兜底"
    return [1, 2, 4, 6, 7], "未检测到列数：使用5列标准映射兜底"

def parse_sm_arrow_events(
    notes_block: SmNotesBlock,
    tick_per_beat: int,
    col_to_atype: List[int],
    player_id: int = 1
) -> Tuple[Dict[int, List[dict]], List[str]]:
    """解析NOTES区块为箭头事件表，返回{lineNo: [箭头信息]}和警告列表"""
    warn_list: List[str] = []
    event_table: Dict[int, List[dict]] = {}
    holding_long: Dict[int, int] = {}  # 记录进行中的长按：列号->开始lineNo
    measure_list = split_measure_text(notes_block.measure_text)
    total_measures = len(measure_list)
    last_line_no = int(round((total_measures * 4.0) * tick_per_beat))

    for measure_idx, line_list in enumerate(measure_list):
        measure_line_count = len(line_list)
        for line_idx, line_str in enumerate(line_list):
            line_no = calculate_line_no(measure_idx, line_idx, measure_line_count, tick_per_beat)
            col_count = len(line_str)
            # 列数不匹配时的警告
            if col_count != len(col_to_atype):
                warn_list.append(
                    f"列数不匹配：第{measure_idx+1}小节第{line_idx+1}行 行长度={col_count} 映射长度={len(col_to_atype)}；按最小列数处理"
                )
            valid_col_count = min(col_count, len(col_to_atype))
            # 解析每一列的符号
            for col in range(valid_col_count):
                symbol = line_str[col]
                a_type = col_to_atype[col]
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
                            f"重复长按开始：列{col} lineNo={line_no} 覆盖上一段开始{holding_long[col]}"
                        )
                    holding_long[col] = line_no
                    continue
                # 长按结束
                if symbol == "3":
                    if col not in holding_long:
                        warn_list.append(f"长按结束无开始：列{col} lineNo={line_no}（忽略）")
                        continue
                    start_line_no = holding_long.pop(col)
                    length = max(0, line_no - start_line_no)
                    event_table.setdefault(start_line_no, []).append(
                        {"aType": a_type, "length": length, "player": player_id}
                    )
                    continue
                # 未知符号
                warn_list.append(f"未知符号忽略：'{symbol}' lineNo={line_no} 列{col}")
    # 处理未闭合的长按，自动闭合到谱面末尾
    for col, start_line_no in list(holding_long.items()):
        a_type = col_to_atype[col] if col < len(col_to_atype) else (col + 1)
        length = max(0, last_line_no - start_line_no)
        event_table.setdefault(start_line_no, []).append(
            {"aType": a_type, "length": length, "player": player_id}
        )
        warn_list.append(
            f"长按未闭合：列{col} 开始{start_line_no} 自动闭合到末尾{last_line_no} 长度{length}"
        )
    return event_table, warn_list

# ========================= 工具函数（通用/播放） =========================
def clean_drag_path(original_path: str) -> str:
    """清理拖拽获取的路径，处理特殊包裹格式"""
    s = original_path.strip()
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1]
    if " " in s:
        first_part = s.split(" ")[0]
        if os.path.exists(first_part):
            return first_part
    return s

def find_audio_in_same_dir(chart_path: str) -> Optional[str]:
    """在谱面文件同目录查找音频文件，优先ogg>mp3>wav"""
    dir_path = os.path.dirname(os.path.abspath(chart_path))
    if not os.path.isdir(dir_path):
        return None
    ext_priority = [".ogg", ".mp3", ".wav"]
    all_candidates: List[str] = []
    for file_name in os.listdir(dir_path):
        file_path = os.path.join(dir_path, file_name)
        if not os.path.isfile(file_path):
            continue
        lower_name = file_name.lower()
        if any(lower_name.endswith(ext) for ext in ext_priority):
            all_candidates.append(file_path)
    if not all_candidates:
        return None
    # 按“扩展名优先级+文件名匹配”排序
    chart_basename = os.path.splitext(os.path.basename(chart_path))[0].lower()
    def candidate_score(file_path: str) -> Tuple[int, int, int]:
        file_name = os.path.basename(file_path).lower()
        ext = os.path.splitext(file_name)[1].lower()
        ext_score = {".ogg": 3, ".mp3": 2, ".wav": 1}.get(ext, 0)
        match_score = 2 if chart_basename in file_name else 0
        file_size = int(os.path.getsize(file_path) / 1024)
        return (ext_score, match_score, file_size)
    all_candidates.sort(key=candidate_score, reverse=True)
    return all_candidates[0]

def get_most_common_interval(line_list: List[int]) -> Optional[int]:
    """获取lineNo列表中最常见的间隔，用于自动匹配tick_per_beat"""
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

def generate_timeline_segments(bpm_list: List[Tuple[float, float]], tick_per_beat: int) -> List[Tuple[int, float, float]]:
    """根据BPM列表生成时间轴分段，返回[(lineNo, start_sec, bpm)]"""
    segments: List[Tuple[int, float, float]] = []
    for i, (beat, bpm) in enumerate(bpm_list):
        line_no = int(round(beat * tick_per_beat))
        if i == 0:
            segments.append((line_no, 0.0, bpm))
            continue
        last_line_no, last_start_sec, last_bpm = segments[-1]
        delta_line = line_no - last_line_no
        if delta_line < 0:
            continue
        beat_count = delta_line / float(tick_per_beat)
        delta_sec = 0.0 if last_bpm <= 0 else beat_count * (60.0 / last_bpm)
        current_sec = last_start_sec + delta_sec
        segments.append((line_no, current_sec, bpm))
    # 兜底：无BPM时默认120BPM
    if not segments:
        segments = [(0, 0.0, 120.0)]
    return segments

def line_no_to_sec(line_no: int, timeline_segments: List[Tuple[int, float, float]], tick_per_beat: int) -> float:
    """将lineNo转换为实际的秒数"""
    lo, hi = 0, len(timeline_segments) - 1
    idx = 0
    # 二分查找所属的时间轴分段
    while lo <= hi:
        mid = (lo + hi) // 2
        if timeline_segments[mid][0] <= line_no:
            idx = mid
            lo = mid + 1
        else:
            hi = mid - 1
    seg_start_line, seg_start_sec, bpm = timeline_segments[idx]
    delta_line = line_no - seg_start_line
    beat_count = delta_line / float(tick_per_beat)
    return seg_start_sec if bpm <= 0 else seg_start_sec + beat_count * (60.0 / bpm)

def build_arrow_events(
    event_table: Dict[int, List[dict]],
    timeline_segments: List[Tuple[int, float, float]],
    tick_per_beat: int,
    atype_map: List[int]
) -> List[ArrowEvent]:
    """将SM解析的事件表转换为播放用的ArrowEvent列表"""
    atype_to_track = {a: i for i, a in enumerate(atype_map)}
    arrow_events: List[ArrowEvent] = []
    # 遍历所有lineNo的事件
    for line_no, arrow_list in sorted(event_table.items()):
        for arrow in arrow_list:
            a_type = arrow.get("aType", 0)
            length = arrow.get("length", 0)
            if a_type not in atype_to_track:
                continue
            track_idx = atype_to_track[a_type]
            start_sec = line_no_to_sec(line_no, timeline_segments, tick_per_beat)
            # 计算长按结束秒数
            end_sec = line_no_to_sec(line_no + max(0, length), timeline_segments, tick_per_beat) if length > 0 else start_sec
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

def format_seconds(sec: float) -> str:
    """秒数格式化：00:00.00"""
    if sec < 0:
        sec = 0
    m = int(sec // 60)
    s = sec - m * 60
    return f"{m:02d}:{s:05.2f}"

def safe_load_chinese_font(font_size: int) -> pygame.font.Font:
    """安全加载中文字体，失败则使用pygame默认字体"""
    import platform
    font_path = None

    # 根据操作系统选择字体路径
    system = platform.system()
    if system == "Windows":
        font_path = r"C:\Windows\Fonts\msyh.ttc"
    elif system == "Darwin":  # macOS
        # Mac 中文字体优先级：苹方 > 黑体
        mac_fonts = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
        ]
        for fp in mac_fonts:
            if os.path.exists(fp):
                font_path = fp
                break
    elif system == "Linux":
        # Linux 常见中文字体
        linux_fonts = [
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]
        for fp in linux_fonts:
            if os.path.exists(fp):
                font_path = fp
                break

    # 尝试加载字体
    if font_path and os.path.exists(font_path):
        try:
            return pygame.font.Font(font_path, font_size)
        except Exception:
            pass

    # 兜底：使用pygame默认字体
    return pygame.font.Font(None, font_size)

# ========================= 皮肤资源类 =========================
class SkinResource:
    """皮肤资源加载与管理"""
    def __init__(self, skin_dir: str):
        self.skin_dir = os.path.abspath(skin_dir)
        self._cache: Dict[str, pygame.Surface] = {}  # 普通皮肤缓存
        self._flip_cache: Dict[str, pygame.Surface] = {}  # 水平翻转缓存
        self._root_dir_cache: Optional[str] = None  # 皮肤根目录缓存

    def open(self):
        """初始化皮肤资源，检测根目录"""
        if not os.path.isdir(self.skin_dir):
            self._root_dir_cache = ""
            return
        self._guess_root_dir()

    def close(self):
        """释放皮肤缓存"""
        self._cache.clear()
        self._flip_cache.clear()
        self._root_dir_cache = None

    def _guess_root_dir(self) -> str:
        """猜测皮肤根目录：优先直接有png的目录，否则找一级子目录"""
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
        except Exception:
            pass
        self._root_dir_cache = ""
        return ""

    @staticmethod
    def _parse_grid(file_name: str) -> Tuple[int, int]:
        """解析皮肤文件名中的网格信息，如3x2.png"""
        base_name = os.path.basename(file_name).lower()
        m = re.findall(r"(\d+)\s*x\s*(\d+)\.png$", base_name)
        if not m:
            return (1, 1)
        a, b = m[-1]
        return (max(1, int(a)), max(1, int(b)))

    def _get_real_path(self, file_name: str) -> str:
        """获取皮肤文件的真实路径"""
        root = self._guess_root_dir()
        if root:
            return os.path.join(self.skin_dir, root, file_name)
        return os.path.join(self.skin_dir, file_name)

    def _read_png(self, file_name: str) -> Optional[pygame.Surface]:
        """读取PNG皮肤文件，带缓存"""
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
        except Exception:
            return None

    def _crop_frame(self, surf: pygame.Surface, col: int, row: int, frame_idx: int) -> pygame.Surface:
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

    def _flip_horizontal(self, surf: pygame.Surface, cache_key: str) -> pygame.Surface:
        """水平翻转图像，带缓存"""
        if cache_key in self._flip_cache:
            return self._flip_cache[cache_key]
        flip_surf = pygame.transform.flip(surf, True, False)
        self._flip_cache[cache_key] = flip_surf
        return flip_surf

    def get_tap_arrow(self, dir_name: str) -> Optional[pygame.Surface]:
        """获取点按箭头皮肤"""
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

    def get_hold_body(self, dir_name: str) -> Optional[pygame.Surface]:
        """获取长按箭身皮肤"""
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

    def get_hold_tail(self, dir_name: str) -> Optional[pygame.Surface]:
        """获取长按箭尾皮肤"""
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

    def get_receptor(self, dir_name: str) -> Optional[pygame.Surface]:
        """获取判定区皮肤"""
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

# ========================= 箭头播放器核心类 =========================
class ArrowPlayer:
    """箭头播放器核心，处理谱面加载、音频播放、画面渲染"""
    def __init__(self, sm_path: str, audio_path: Optional[str], skin_dir: str):
        # ========== 新增：处理打包后的路径 ==========
        import sys
        def get_resource_path(relative_path):
            """获取打包后/开发时的资源路径（兼容PyInstaller）"""
            if hasattr(sys, '_MEIPASS'):
                # 打包后，资源在_MEIPASS临时目录
                return os.path.join(sys._MEIPASS, relative_path)
            # 开发时，使用当前目录
            return os.path.join(os.path.abspath("."), relative_path)
        
        # 修正皮肤目录路径（优先用打包的noteskin）
        self.skin_dir = get_resource_path("noteskin") if os.path.exists(get_resource_path("noteskin")) else skin_dir
        
        # 其他原有代码不变...
        # 基础路径
        self.sm_path = sm_path
        self.audio_path = audio_path or find_audio_in_same_dir(sm_path, AUDIO_EXT_PRIORITY)
        self.skin_dir = skin_dir
        # 窗口配置
        self.window_w = 960
        self.window_h = 900
        self.fps = 60
        self.scroll_speed = 420.0 * 2.0
        # 谱面解析配置
        self.tick_per_beat = 96
        self.cur_map_idx = 0
        # 谱面数据
        self.chart_info: Optional[SmChartInfo] = None
        self.notes_block: Optional[SmNotesBlock] = None
        self.atype_map = ATYPE_MAP_CANDIDATES[0]
        self.offset = 0.0
        self.bpm_list: List[Tuple[float, float]] = []
        self.event_table: Dict[int, List[dict]] = {}
        self.timeline_segments: List[Tuple[int, float, float]] = []
        self.arrow_events: List[ArrowEvent] = []
        # 播放状态
        self.is_playing = False
        self.start_sys_sec = 0.0
        self.pause_chart_sec = 0.0
        self.cur_chart_sec = 0.0
        self.total_chart_sec = 0.0
        self.next_hit_idx = 0
        self.end_reason = ""
        # Pygame资源
        self.screen: Optional[pygame.Surface] = None
        self.font = None
        self.small_font = None
        self.skin = SkinResource(self.skin_dir)
        # 皮肤图缓存
        self.tap_surfs: List[Optional[pygame.Surface]] = [None] * 5
        self.hold_body_surfs: List[Optional[pygame.Surface]] = [None] * 5
        self.hold_tail_surfs: List[Optional[pygame.Surface]] = [None] * 5
        self.receptor_surfs: List[Optional[pygame.Surface]] = [None] * 5
        # 判定光效果
        self.judge_light: List[float] = [0.0] * 5
        self.judge_light_decay = 2.8  # 判定光每秒衰减值
        self.last_chart_sec = 0.0

    def load_sm(self):
        """加载并解析SM文件，生成播放所需的箭头事件"""
        # 1. 解析SM文件基础信息和NOTES区块
        self.chart_info, notes_blocks = parse_sm_file(self.sm_path)
        if not notes_blocks:
            raise Exception("SM文件中未找到#NOTES区块，无法播放")
        self.notes_block = notes_blocks[0]  # 取第一个NOTES区块
        # 2. 自动检测列数并推荐aType映射
        col_count = detect_notes_column_count(self.notes_block)
        self.atype_map, _ = recommend_atype_map(col_count)
        # 3. 解析箭头事件表
        self.event_table, _ = parse_sm_arrow_events(self.notes_block, self.tick_per_beat, self.atype_map)
        # 4. 处理BPM，兜底无效BPM
        self.bpm_list = self.chart_info.bpm_list or []
        need_fallback = not self.bpm_list or any(bpm <= 0 for _, bpm in self.bpm_list)
        if need_fallback:
            fallback_bpm = extract_available_bpm(self.chart_info.display_bpm_original, self.chart_info.bpms_original) or 120.0
            self.bpm_list = [(0.0, fallback_bpm)]
        # 5. 生成时间轴分段
        self.timeline_segments = generate_timeline_segments(self.bpm_list, self.tick_per_beat)
        # 6. 构建箭头事件并计算总时长
        self.arrow_events = build_arrow_events(self.event_table, self.timeline_segments, self.tick_per_beat, self.atype_map)
        self.offset = self.chart_info.offset
        # 7. 计算谱面总时长
        if self.arrow_events:
            last_event = self.arrow_events[-1]
            self.total_chart_sec = last_event.end_sec
        else:
            self.total_chart_sec = 0.0
        # 8. 自动匹配最优tick_per_beat
        line_list = [e.original_line_no for e in self.arrow_events]
        most_common_interval = get_most_common_interval(line_list)
        if most_common_interval and most_common_interval in TICK_PER_BEAT_CANDIDATES:
            self.tick_per_beat = most_common_interval
            self.timeline_segments = generate_timeline_segments(self.bpm_list, self.tick_per_beat)
            self.arrow_events = build_arrow_events(self.event_table, self.timeline_segments, self.tick_per_beat, self.atype_map)
        # 重置命中指针
        self._reset_hit_pointer(self.cur_chart_sec)

    def rebuild_arrow_events(self):
        """重新构建箭头事件（切换映射时调用）"""
        self.atype_map = ATYPE_MAP_CANDIDATES[self.cur_map_idx]
        self.arrow_events = build_arrow_events(self.event_table, self.timeline_segments, self.tick_per_beat, self.atype_map)
        self._reset_hit_pointer(self.cur_chart_sec)

    def init_pygame(self):
        """初始化Pygame环境、音频、皮肤"""
        pygame.init()
        pygame.font.init()
        # 初始化音频，失败则禁用
        try:
            pygame.mixer.init()
        except Exception:
            self.audio_path = None
        # 创建窗口
        self.screen = pygame.display.set_mode((self.window_w, self.window_h))
        pygame.display.set_caption("SM Arrow Player (直接播放SM谱面)")
        # 加载字体
        self.font = safe_load_chinese_font(20)
        self.small_font = safe_load_chinese_font(16)
        # 加载皮肤
        self.skin.open()
        self._load_skin_surfs()
        # 加载音频
        if self.audio_path and os.path.exists(self.audio_path):
            try:
                pygame.mixer.music.load(self.audio_path)
            except Exception:
                self.audio_path = None

    def _load_skin_surfs(self):
        """加载所有轨道的皮肤图"""
        for i, dir_name in enumerate(TRACK_DIRECTIONS):
            self.tap_surfs[i] = self.skin.get_tap_arrow(dir_name)
            self.hold_body_surfs[i] = self.skin.get_hold_body(dir_name)
            self.hold_tail_surfs[i] = self.skin.get_hold_tail(dir_name)
            self.receptor_surfs[i] = self.skin.get_receptor(dir_name)

    def play(self):
        """开始播放"""
        if self.is_playing:
            return
        self.is_playing = True
        self.start_sys_sec = time.perf_counter() - self.pause_chart_sec
        self.last_chart_sec = self.pause_chart_sec
        self._reset_hit_pointer(self.pause_chart_sec)
        # 播放音频，偏移校准
        if self.audio_path:
            audio_start = max(0.0, self.pause_chart_sec - self.offset)
            try:
                pygame.mixer.music.play(start=audio_start)
            except TypeError:
                pygame.mixer.music.play()

    def pause(self):
        """暂停播放"""
        if not self.is_playing:
            return
        self.is_playing = False
        self.pause_chart_sec = self.cur_chart_sec
        if self.audio_path:
            try:
                pygame.mixer.music.pause()
            except Exception:
                pass

    def set_chart_sec(self, new_sec: float):
        """设置谱面当前播放时间"""
        new_sec = max(0.0, min(self.total_chart_sec, new_sec))
        self.cur_chart_sec = new_sec
        self.pause_chart_sec = new_sec
        self.last_chart_sec = new_sec
        self._reset_hit_pointer(new_sec)
        # 同步音频
        if self.is_playing:
            self.start_sys_sec = time.perf_counter() - new_sec
            if self.audio_path:
                try:
                    pygame.mixer.music.stop()
                    audio_start = max(0.0, new_sec - self.offset)
                    pygame.mixer.music.play(start=audio_start)
                except Exception:
                    pass

    def _reset_hit_pointer(self, current_sec: float):
        """重置下一个命中的箭头事件索引（二分查找）"""
        lo, hi = 0, len(self.arrow_events)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.arrow_events[mid].start_sec <= current_sec:
                lo = mid + 1
            else:
                hi = mid
        self.next_hit_idx = lo

    def _trigger_judge_light(self, track_idx: int):
        """触发指定轨道的判定光"""
        if 0 <= track_idx < len(self.judge_light):
            self.judge_light[track_idx] = 1.0

    def _update_judge_light(self, dt: float):
        """更新判定光衰减效果"""
        if dt <= 0:
            return
        decay = self.judge_light_decay * dt
        for i in range(len(self.judge_light)):
            self.judge_light[i] = max(0.0, self.judge_light[i] - decay)

    def main_loop(self) -> str:
        """播放器主循环，返回结束原因：finished/closed"""
        clock = pygame.time.Clock()
        running = True
        self.end_reason = ""
        while running:
            dt = clock.tick(self.fps) / 1000.0
            self._update_judge_light(dt)
            # 处理事件
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.end_reason = "closed"
                    running = False
                if event.type == pygame.KEYDOWN:
                    self._handle_keydown(event.key)
            # 播放逻辑
            if self.is_playing:
                self._update_play_state(dt)
                # 检测播放结束
                if self.cur_chart_sec >= self.total_chart_sec:
                    self.cur_chart_sec = self.total_chart_sec
                    self.pause()
                    self.end_reason = "finished"
                    running = False
            # 绘制画面
            self.draw()
            pygame.display.flip()
        # 释放资源
        try:
            self.skin.close()
            pygame.quit()
        except Exception:
            pass
        return self.end_reason or "closed"

    def _handle_keydown(self, key):
        """处理键盘按键事件"""
        if key == pygame.K_ESCAPE:
            self.end_reason = "closed"
        elif key == pygame.K_SPACE:
            self.pause() if self.is_playing else self.play()
        elif key == pygame.K_r:
            self.set_chart_sec(0.0)
        elif key == pygame.K_LEFT:
            self.set_chart_sec(self.cur_chart_sec - 5.0)
        elif key == pygame.K_RIGHT:
            self.set_chart_sec(self.cur_chart_sec + 5.0)
        elif key == pygame.K_LEFTBRACKET:
            self.scroll_speed = max(60.0, self.scroll_speed - 30.0)
        elif key == pygame.K_RIGHTBRACKET:
            self.scroll_speed = min(2000.0, self.scroll_speed + 30.0)
        elif key == pygame.K_MINUS:
            self.offset -= 0.01
        elif key == pygame.K_EQUALS:
            self.offset += 0.01
        elif key == pygame.K_t:
            # 切换每拍tick数
            cur_idx = TICK_PER_BEAT_CANDIDATES.index(self.tick_per_beat) if self.tick_per_beat in TICK_PER_BEAT_CANDIDATES else 0
            cur_idx = (cur_idx + 1) % len(TICK_PER_BEAT_CANDIDATES)
            self.tick_per_beat = TICK_PER_BEAT_CANDIDATES[cur_idx]
            self.timeline_segments = generate_timeline_segments(self.bpm_list, self.tick_per_beat)
            self.rebuild_arrow_events()
            self.total_chart_sec = self.arrow_events[-1].end_sec if self.arrow_events else 0.0
            self.set_chart_sec(self.cur_chart_sec)
        elif key == pygame.K_m:
            # 切换aType映射
            self.cur_map_idx = (self.cur_map_idx + 1) % len(ATYPE_MAP_CANDIDATES)
            self.rebuild_arrow_events()

    def _update_play_state(self, dt: float):
        """更新播放状态，计算当前时间并检测箭头命中"""
        self.last_chart_sec = self.cur_chart_sec
        self.cur_chart_sec = time.perf_counter() - self.start_sys_sec
        # 检测箭头命中，触发判定光
        while self.next_hit_idx < len(self.arrow_events):
            event = self.arrow_events[self.next_hit_idx]
            if event.start_sec <= self.cur_chart_sec:
                self._trigger_judge_light(event.track_idx)
                self.next_hit_idx += 1
            else:
                break

    def draw(self):
        """绘制播放器所有画面元素"""
        assert self.screen is not None and self.font is not None and self.small_font is not None
        # 背景色
        self.screen.fill((15, 15, 18))
        # 绘制顶部操作提示
        tip_text = "空格：暂停/继续  R：重播  ←/→：快退快进  T：切tick  M：切映射  -/=:调offset  [/]:调速度  Esc：退出"
        self.screen.blit(self.small_font.render(tip_text, True, (255, 220, 160)), (18, 10))
        # 固定坐标
        info_y1, info_y2, info_y3 = 34, 58, 80
        top_y, judge_y, bottom_y = 120, 210, self.window_h - 74
        track_count = 5
        track_total_w = 620
        track_start_x = (self.window_w - track_total_w) // 2
        single_track_w = track_total_w // track_count

        # 绘制轨道背景
        for i in range(track_count):
            x = track_start_x + i * single_track_w
            # 轨道底色
            pygame.draw.rect(
                self.screen, (28, 28, 34),
                (x + 3, top_y, single_track_w - 6, bottom_y - top_y),
                border_radius=14
            )
            # 轨道边框
            pygame.draw.rect(
                self.screen, (45, 45, 55),
                (x + 3, top_y, single_track_w - 6, bottom_y - top_y),
                width=2, border_radius=14
            )
        # 绘制判定线
        pygame.draw.line(
            self.screen, (220, 220, 220),
            (track_start_x, judge_y), (track_start_x + track_total_w, judge_y), 2
        )
        # 绘制判定区+判定光
        for i in range(track_count):
            self._draw_receptor(i, track_start_x, single_track_w, judge_y)
        # 绘制顶部信息
        self._draw_top_info(info_y1, info_y2, info_y3)
        # 绘制箭头（点按+长按）
        self._draw_arrows(track_start_x, single_track_w, judge_y, bottom_y, top_y)
        # 绘制tick匹配疑点提示
        self._draw_tick_tip(bottom_y)

    def _draw_receptor(self, track_idx: int, track_start_x: int, single_track_w: int, judge_y: int):
        """绘制指定轨道的判定区和判定光"""
        center_x = track_start_x + track_idx * single_track_w + single_track_w // 2
        # 绘制判定光
        light_strength = self.judge_light[track_idx]
        if light_strength > 0:
            light_surf = pygame.Surface((single_track_w, single_track_w), pygame.SRCALPHA)
            cx, cy = single_track_w // 2, single_track_w // 2
            # 多层光圈效果
            for k in range(5):
                r = int(single_track_w * (0.18 + 0.08 * k))
                alpha = int(light_strength * (140 - k * 22))
                pygame.draw.circle(light_surf, (255, 235, 185, max(0, alpha)), (cx, cy), r)
            self.screen.blit(light_surf, (center_x - single_track_w // 2, judge_y - single_track_w // 2))
        # 绘制判定区皮肤
        receptor_surf = self.receptor_surfs[track_idx]
        if receptor_surf:
            target_w = int(single_track_w * 0.60)
            scale = target_w / float(max(1, receptor_surf.get_width()))
            target_h = int(receptor_surf.get_height() * scale)
            scale_surf = pygame.transform.smoothscale(receptor_surf, (target_w, target_h))
            self.screen.blit(scale_surf, (center_x - target_w // 2, judge_y - target_h // 2))

    def _draw_top_info(self, y1: int, y2: int, y3: int):
        """绘制顶部谱面、播放、参数信息"""
        sm_name = os.path.basename(self.sm_path)
        audio_name = os.path.basename(self.audio_path) if self.audio_path else "（未找到音频）"
        cur_sec = self.cur_chart_sec
        # 文本1：谱面+音频
        text1 = f"谱面：{sm_name}   音频：{audio_name}"
        # 文本2：时间+播放状态
        text2 = f"时间：{format_seconds(cur_sec)} / {format_seconds(self.total_chart_sec)}   播放：{'是' if self.is_playing else '否'}"
        # 文本3：参数信息
        text3 = f"tick/拍：{self.tick_per_beat}   视觉速度：{int(self.scroll_speed)}px/s   offset：{self.offset:+.2f}s   映射：{self.atype_map}"
        # 绘制
        self.screen.blit(self.font.render(text1, True, (235, 235, 235)), (18, y1))
        self.screen.blit(self.small_font.render(text2, True, (200, 200, 210)), (18, y2))
        self.screen.blit(self.small_font.render(text3, True, (170, 170, 190)), (18, y3))

    def _draw_arrows(self, track_start_x: int, single_track_w: int, judge_y: int, bottom_y: int, top_y: int):
        """绘制所有箭头（点按+长按）"""
        visible_sec = (bottom_y - judge_y) / self.scroll_speed
        advance_sec = visible_sec + 1.0
        cur_sec = self.cur_chart_sec
        # 遍历箭头事件，只绘制可视区域内的
        for event in self.arrow_events:
            if event.start_sec < cur_sec - 0.5 and event.end_sec < cur_sec - 0.5:
                continue
            if event.start_sec > cur_sec + advance_sec:
                break
            # 计算箭头位置
            center_x = track_start_x + event.track_idx * single_track_w + single_track_w // 2
            dy_start = (event.start_sec - cur_sec) * self.scroll_speed
            y_start = judge_y + dy_start
            # 点按箭头
            if abs(event.end_sec - event.start_sec) < 1e-6:
                if y_start >= judge_y:
                    self._draw_tap_arrow(event.track_idx, center_x, y_start, single_track_w, judge_y)
            # 长按箭头
            else:
                dy_end = (event.end_sec - cur_sec) * self.scroll_speed
                y_end = judge_y + dy_end
                self._draw_hold_arrow(event.track_idx, center_x, y_start, y_end, single_track_w, judge_y)

    def _draw_tap_arrow(self, track_idx: int, center_x: int, y: float, single_track_w: int, judge_y: int):
        """
        绘制点按箭头
        :param track_idx: 轨道索引（0-4，对应DownLeft/UpLeft/Center/UpRight/DownRight）
        :param center_x: 轨道中心X坐标
        :param y: 箭头绘制的Y坐标
        :param single_track_w: 单轨道宽度
        :param judge_y: 判定线Y坐标
        """
        # 边界校验：只绘制判定线及以下、可视区域内的箭头
        if y < judge_y or y < 50 or y > self.window_h - 40:
            return
        
        # 尝试加载皮肤并绘制
        tap_surf = self.tap_surfs[track_idx]
        if tap_surf:
            # 按轨道宽度比例缩放箭头皮肤（保证不同分辨率下比例一致）
            target_w = int(single_track_w * 0.60)  # 箭头宽度为轨道宽度的60%
            target_w = max(22, target_w)  # 最小宽度限制，避免箭头过小
            scale = target_w / float(max(1, tap_surf.get_width()))  # 缩放比例
            target_h = int(tap_surf.get_height() * scale)  # 等比例计算高度
            
            # 平滑缩放皮肤（避免锯齿）
            scale_surf = pygame.transform.smoothscale(tap_surf, (target_w, target_h))
            # 绘制到箭头中心位置（居中对齐）
            self.screen.blit(scale_surf, (center_x - target_w // 2, int(y) - target_h // 2))
            return
        
        # 无皮肤时绘制默认圆形箭头（兜底方案）
        radius = max(9, min(22, single_track_w // 4))  # 半径限制在9-22px之间
        # 绘制白色填充圆（箭头主体）
        pygame.draw.circle(self.screen, (240, 240, 245), (center_x, int(y)), radius)
        # 绘制黑色描边（增强对比度）
        pygame.draw.circle(self.screen, (20, 20, 25), (center_x, int(y)), radius, 3)

    def _draw_hold_arrow(self, track_idx: int, center_x: int, y_start: float, y_end: float, single_track_w: int, judge_y: int):
        """绘制长按箭头（箭身+箭尾+箭头头部）"""
        # 裁切判定线以上的部分，避免箭头超出判定线
        y1 = min(y_start, y_end)
        y2 = max(y_start, y_end)
        y1 = max(y1, float(judge_y))
        if y2 < 50 or y1 > self.window_h - 40:
            return
        # 可视区域裁切
        y1c = max(50.0, y1)
        y2c = min(float(self.window_h - 40), y2)
        if y2c <= y1c:
            return

        # 绘制长按箭身
        hold_body_surf = self.hold_body_surfs[track_idx]
        if hold_body_surf:
            target_w = int(single_track_w * 0.26)
            target_w = max(12, target_w)
            scale = target_w / float(max(1, hold_body_surf.get_width()))
            single_h = int(hold_body_surf.get_height() * scale)
            single_h = max(8, single_h)
            scale_surf = pygame.transform.smoothscale(hold_body_surf, (target_w, single_h))
            current_y = int(y1c)
            while current_y < int(y2c):
                self.screen.blit(scale_surf, (center_x - target_w // 2, current_y))
                current_y += single_h
        else:
            # 无皮肤时绘制默认矩形箭身
            w = max(9, min(16, single_track_w // 7))
            rect = pygame.Rect(center_x - w // 2, int(y1c), w, int(max(2, y2c - y1c)))
            pygame.draw.rect(self.screen, (220, 220, 230), rect, border_radius=6)
            pygame.draw.rect(self.screen, (20, 20, 25), rect, width=2, border_radius=6)

        # 绘制长按箭尾
        hold_tail_surf = self.hold_tail_surfs[track_idx]
        if hold_tail_surf:
            target_w = int(single_track_w * 0.40)
            scale = target_w / float(max(1, hold_tail_surf.get_width()))
            target_h = int(hold_tail_surf.get_height() * scale)
            scale_surf = pygame.transform.smoothscale(hold_tail_surf, (target_w, target_h))
            self.screen.blit(scale_surf, (center_x - target_w // 2, int(y2c) - target_h // 2))

        # 绘制长按头部（点按箭头）
        if y_start >= judge_y:
            self._draw_tap_arrow(track_idx, center_x, y_start, single_track_w, judge_y)

    def _draw_tick_tip(self, bottom_y: int):
        """绘制tick匹配疑点提示"""
        line_list = [e.original_line_no for e in self.arrow_events[:8000]]
        most_common_interval = get_most_common_interval(line_list)
        if most_common_interval and most_common_interval != self.tick_per_beat:
            tip_text = f"[疑点] 最常见 lineNo 间隔={most_common_interval}，当前 tick/拍={self.tick_per_beat}。按 T 切换试试。"
            self.screen.blit(
                self.small_font.render(tip_text, True, (255, 180, 120)),
                (18, bottom_y + 10)
            )

# ========================= 启动界面类 =========================
class LauncherUI:
    """播放器启动界面，支持拖拽/选择SM文件，自动加载音频"""
    def __init__(self):
        # 初始化主窗口（支持拖拽/普通CTk）
        if _drag_available:
            self.root = TkinterDnD.Tk()
        else:
            self.root = ctk.CTk()
        # 窗口配置
        self.root.title("SM 谱面直接播放器")
        self.root.geometry("720x500")
        self.root.resizable(False, False)
        ctk.set_appearance_mode("dark")
        # 核心变量
        self.sm_path = ctk.StringVar(value="")
        self.status_text = ctk.StringVar(
            value="把 .sm 谱面文件拖到下方区域，自动加载同目录音频并播放（支持mp3/ogg/wav）"
        )
        # 构建界面
        self._build_ui()
        # 绑定拖拽事件
        if _drag_available:
            self._bind_drag()

    def _build_ui(self):
        """构建启动界面UI"""
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=14, pady=14)
        # 标题
        title_label = ctk.CTkLabel(
            main_frame, text="SM 谱面直接播放器", font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(pady=(6, 10))
        # 拖拽框
        self.drag_frame = ctk.CTkFrame(main_frame, height=220, corner_radius=14)
        self.drag_frame.pack(fill="x", padx=10, pady=(0, 12))
        drag_tip = ctk.CTkLabel(
            self.drag_frame,
            text="拖入 .sm 文件到这里\n自动识别同目录音频 + 自动播放",
            font=ctk.CTkFont(size=16)
        )
        drag_tip.place(relx=0.5, rely=0.5, anchor="center")
        # 路径输入+选择按钮
        row1 = ctk.CTkFrame(main_frame)
        row1.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkEntry(
            row1, textvariable=self.sm_path, placeholder_text="SM文件路径", width=520
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            row1, text="选择SM文件", width=170, command=self._select_sm_file
        ).pack(side="left")
        # 状态提示
        ctk.CTkLabel(
            main_frame, textvariable=self.status_text, wraplength=680, justify="left"
        ).pack(pady=(6, 0))
        # 说明文字
        desc_label = ctk.CTkLabel(
            main_frame,
            text="说明：播放结束/按Esc/关闭窗口，自动返回此界面；支持所有原快捷键操作",
            wraplength=680, justify="left", font=ctk.CTkFont(size=13)
        )
        desc_label.pack(pady=(10, 0))

    def _bind_drag(self):
        """绑定拖拽事件"""
        self.drag_frame._canvas.drop_target_register(DND_FILES)
        self.drag_frame._canvas.dnd_bind("<<Drop>>", self._handle_drag)

    def _handle_drag(self, event):
        """处理拖拽文件"""
        raw_path = clean_drag_path(event.data)
        if raw_path and raw_path.lower().endswith(".sm") and os.path.exists(raw_path):
            self._load_and_play(raw_path)
        else:
            self.status_text.set("拖入的不是有效SM文件，请重新拖入")

    def _select_sm_file(self):
        """选择SM文件"""
        import tkinter.filedialog as fd
        sm_path = fd.askopenfilename(
            title="选择SM谱面文件",
            filetypes=[("StepMania谱面", "*.sm"), ("所有文件", "*.*")]
        )
        if sm_path:
            self._load_and_play(sm_path)

    def _load_and_play(self, sm_path: str):
        """加载SM文件并启动播放"""
        # 更新状态和路径
        self.sm_path.set(sm_path)
        # 查找同目录音频
        audio_path = find_audio_in_same_dir(sm_path)
        if audio_path:
            self.status_text.set(f"已载入：{os.path.basename(sm_path)}\n自动找到音频：{os.path.basename(audio_path)}")
        else:
            self.status_text.set(f"已载入：{os.path.basename(sm_path)}\n同目录未找到音频，仅播放谱面箭头")
        # 查找皮肤目录（程序同目录的noteskin）
        try:
            import sys
            # 兼容exe打包（PyInstaller）
            if getattr(sys, "frozen", False):
                app_dir = os.path.dirname(sys.executable)
            else:
                app_dir = os.path.dirname(os.path.abspath(__file__))
            skin_dir = os.path.join(app_dir, "noteskin")
            # 检查皮肤目录是否存在
            if not os.path.isdir(skin_dir):
                self.status_text.set(f"皮肤目录不存在：{skin_dir}\n请将noteskin文件夹放到程序同目录下")
                return
            # 隐藏启动界面，启动播放器
            self.root.withdraw()
            # 初始化并播放
            player = ArrowPlayer(sm_path, audio_path, skin_dir)
            player.load_sm()
            player.init_pygame()
            player.play()
            end_reason = player.main_loop()
            # 播放结束后恢复启动界面
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            # 更新结束状态
            if end_reason == "finished":
                self.status_text.set("播放结束！可继续拖入/选择新的SM文件")
            else:
                self.status_text.set("已返回！可继续拖入/选择新的SM文件")
        except Exception as e:
            self.status_text.set(f"播放失败：{type(e).__name__}: {str(e)}")
            self.root.deiconify()
            traceback.print_exc()

    def run(self):
        """启动界面主循环"""
        self.root.mainloop()

# ========================= 主函数 =========================
def main():
    """程序入口"""
    launcher = LauncherUI()
    launcher.run()

if __name__ == "__main__":
    main()    
