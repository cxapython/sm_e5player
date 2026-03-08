# -*- coding: utf-8 -*-
"""
JSON谱面解析模块
负责解析JSON格式的谱面文件，转换为统一的ArrowEvent格式
"""

import json
import os
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional

from sm_parser import ArrowEvent, TimelineSegment


# ========================= 数据类定义 =========================

@dataclass
class JsonBpm:
    """JSON谱面中的BPM信息"""
    line_no: int = 0
    bpm_val: float = 120.0


@dataclass
class JsonArrow:
    """JSON谱面中的箭头信息"""
    a_type: int = 0
    player: int = 1
    length: int = 0


@dataclass
class JsonLineData:
    """JSON谱面中的一行数据"""
    line_no: int = 0
    arrows: List[JsonArrow] = field(default_factory=list)


@dataclass
class JsonBoard:
    """JSON谱面中的一个面板（玩家谱面）"""
    line_datas: List[JsonLineData] = field(default_factory=list)


@dataclass
class JsonChartInfo:
    """JSON谱面信息"""
    title: str = ""
    offset: float = 0.0
    bpms: List[JsonBpm] = field(default_factory=list)
    boards: List[JsonBoard] = field(default_factory=list)


# ========================= JSON解析器类 =========================

class JsonParser:
    """JSON谱面解析器"""

    # aType到轨道索引的映射（与SM格式兼容）
    # aType: 1=左下, 2=左上, 4=中间, 6=右上, 7=右下
    ATYPE_TO_TRACK = {
        1: 0,  # 左下 -> track 0
        2: 1,  # 左上 -> track 1
        4: 2,  # 中间 -> track 2
        6: 3,  # 右上 -> track 3
        7: 4,  # 右下 -> track 4
    }

    # 默认每拍tick数
    DEFAULT_TICK_PER_BEAT = 96

    def __init__(self, tick_per_beat: int = 96):
        """
        初始化解析器

        Args:
            tick_per_beat: 每拍tick数，默认96
        """
        self.tick_per_beat = tick_per_beat
        self.chart_info: Optional[JsonChartInfo] = None

    def parse_file(self, json_path: str) -> Tuple[JsonChartInfo, List[ArrowEvent]]:
        """
        解析JSON谱面文件

        Args:
            json_path: JSON文件路径

        Returns:
            (JsonChartInfo, List[ArrowEvent]): 谱面信息和箭头事件列表
        """
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"JSON文件不存在: {json_path}")

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 解析谱面信息
        chart_info = self._parse_chart_info(data, json_path)
        self.chart_info = chart_info

        # 解析箭头事件
        arrow_events = self._parse_arrow_events(data)

        return chart_info, arrow_events

    def _parse_chart_info(self, data: dict, json_path: str) -> JsonChartInfo:
        """解析谱面基础信息"""
        chart_info = JsonChartInfo()

        # 从文件名提取标题
        chart_info.title = os.path.splitext(os.path.basename(json_path))[0]

        # 解析scoreInfo中的offset
        score_info = data.get('scoreInfo', {})
        if isinstance(score_info, dict):
            chart_info.offset = float(score_info.get('offset', 0.0))

        # 解析BPM列表
        bpms_data = data.get('bpms', [])
        if isinstance(bpms_data, list):
            for bpm_item in bpms_data:
                if isinstance(bpm_item, dict):
                    line_no = int(bpm_item.get('lineNo', 0))
                    bpm_val = float(bpm_item.get('bpmVal', 120.0))
                    if bpm_val > 0:
                        chart_info.bpms.append(JsonBpm(line_no=line_no, bpm_val=bpm_val))

        # 如果没有BPM，添加默认BPM
        if not chart_info.bpms:
            chart_info.bpms.append(JsonBpm(line_no=0, bpm_val=120.0))

        # 解析boards（面板数据）
        boards_data = data.get('boards', [])
        if isinstance(boards_data, list):
            for board_item in boards_data:
                if isinstance(board_item, dict):
                    board = JsonBoard()
                    line_datas = board_item.get('lineDatas', [])
                    if isinstance(line_datas, list):
                        for ld_item in line_datas:
                            if isinstance(ld_item, dict):
                                line_no = int(ld_item.get('lineNo', 0))
                                arrows_data = ld_item.get('arrows', [])
                                arrows = []
                                if isinstance(arrows_data, list):
                                    for a_item in arrows_data:
                                        if isinstance(a_item, dict):
                                            arrows.append(JsonArrow(
                                                a_type=int(a_item.get('aType', 0)),
                                                player=int(a_item.get('player', 1)),
                                                length=int(a_item.get('length', 0))
                                            ))
                                if arrows:
                                    board.line_datas.append(JsonLineData(
                                        line_no=line_no,
                                        arrows=arrows
                                    ))
                    if board.line_datas:
                        chart_info.boards.append(board)

        return chart_info

    def _parse_arrow_events(self, data: dict) -> List[ArrowEvent]:
        """解析箭头事件"""
        arrow_events: List[ArrowEvent] = []

        # 生成时间轴分段
        bpm_list = [(bpm.line_no, bpm.bpm_val) for bpm in self.chart_info.bpms]
        timeline_segments = self._generate_timeline_segments(bpm_list)

        # 解析箭头事件
        boards_data = data.get('boards', [])
        if not isinstance(boards_data, list) or not boards_data:
            return arrow_events

        # 使用第一个board（单人模式）
        board_data = boards_data[0]
        line_datas = board_data.get('lineDatas', [])
        if not isinstance(line_datas, list):
            return arrow_events

        for ld_item in line_datas:
            if not isinstance(ld_item, dict):
                continue

            line_no = int(ld_item.get('lineNo', 0))
            arrows_data = ld_item.get('arrows', [])

            if not isinstance(arrows_data, list):
                continue

            for a_item in arrows_data:
                if not isinstance(a_item, dict):
                    continue

                a_type = int(a_item.get('aType', 0))
                length = int(a_item.get('length', 0))

                # 检查aType是否有效
                if a_type not in self.ATYPE_TO_TRACK:
                    continue

                track_idx = self.ATYPE_TO_TRACK[a_type]

                # 计算时间
                start_sec = self._line_no_to_sec(line_no, timeline_segments)
                end_sec = start_sec
                if length > 0:
                    end_sec = self._line_no_to_sec(line_no + length, timeline_segments)

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

    def _generate_timeline_segments(self, bpm_list: List[Tuple[int, float]]) -> List[TimelineSegment]:
        """根据BPM列表生成时间轴分段"""
        from sm_parser import generate_timeline_segments

        # 转换为sm_parser期望的格式：(beat, bpm)
        bpm_list_for_sm = [(line_no / float(self.tick_per_beat), bpm) for line_no, bpm in bpm_list]

        return generate_timeline_segments(bpm_list_for_sm, self.tick_per_beat)

    def _line_no_to_sec(self, line_no: int, timeline_segments: List[TimelineSegment]) -> float:
        """将lineNo转换为秒数"""
        from sm_parser import line_no_to_sec
        return line_no_to_sec(line_no, timeline_segments, self.tick_per_beat)

    def get_bpm_list(self) -> List[Tuple[float, float]]:
        """获取BPM列表（beat, bpm格式）"""
        if not self.chart_info:
            return [(0.0, 120.0)]

        return [(bpm.line_no / float(self.tick_per_beat), bpm.bpm_val) for bpm in self.chart_info.bpms]

    def get_total_duration(self, arrow_events: List[ArrowEvent]) -> float:
        """获取谱面总时长"""
        if not arrow_events:
            return 0.0
        # 返回最后一个事件的结束时间
        return max(e.end_sec for e in arrow_events)