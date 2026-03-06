# -*- coding: utf-8 -*-
"""
判定系统模块
负责音游的判定逻辑、分数计算、连击系统
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


class JudgeResult(Enum):
    """判定结果枚举"""
    PERFECT = "PERFECT"
    GOOD = "GOOD"
    BAD = "BAD"
    MISS = "MISS"


@dataclass
class JudgeConfig:
    """判定配置"""
    # 判定窗口（秒）
    perfect_window: float = 0.045  # ±45ms
    good_window: float = 0.090     # ±90ms
    bad_window: float = 0.135      # ±135ms

    # 分数权重
    perfect_score: int = 100
    good_score: int = 50
    bad_score: int = 10

    # 连击奖励阈值
    combo_bonus_threshold: int = 10  # 10连击开始加分

    # 判定颜色（RGB）
    perfect_color: Tuple[int, int, int] = (50, 255, 100)    # 绿色
    good_color: Tuple[int, int, int] = (255, 220, 50)       # 黄色
    bad_color: Tuple[int, int, int] = (255, 80, 80)         # 红色
    miss_color: Tuple[int, int, int] = (150, 150, 150)      # 灰色


@dataclass
class JudgeStats:
    """判定统计"""
    perfect: int = 0
    good: int = 0
    bad: int = 0
    miss: int = 0

    @property
    def total(self) -> int:
        """总判定数"""
        return self.perfect + self.good + self.bad + self.miss

    @property
    def hit_count(self) -> int:
        """命中数（不含MISS）"""
        return self.perfect + self.good + self.bad

    def to_dict(self) -> Dict[str, int]:
        """转换为字典"""
        return {
            "PERFECT": self.perfect,
            "GOOD": self.good,
            "BAD": self.bad,
            "MISS": self.miss
        }


class JudgeSystem:
    """
    独立判定系统

    支持多种判定模式：
    - PERFECT: 完美命中（±45ms内）
    - GOOD: 优秀命中（±90ms内）
    - BAD: 较差命中（±135ms内）
    - MISS: 漏击（超过BAD窗口）
    """

    def __init__(self, config: Optional[JudgeConfig] = None):
        """
        初始化判定系统

        Args:
            config: 判定配置，为None时使用默认配置
        """
        self.config = config or JudgeConfig()
        self.reset()

    def reset(self):
        """重置所有统计"""
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.stats = JudgeStats()
        self._arrow_states: Dict[int, int] = {}  # arrow_idx -> state (0=未处理, 1=已命中, 2=已miss)

    def judge(self, arrow_events: List, track_idx: int, current_sec: float) -> Tuple[Optional[JudgeResult], int]:
        """
        尝试判定指定轨道上的箭头

        Args:
            arrow_events: 箭头事件列表（ArrowEvent对象）
            track_idx: 轨道索引
            current_sec: 当前时间（秒）

        Returns:
            (判定结果, 箭头索引)，未命中返回(None, -1)
        """
        best_idx = -1
        best_diff = float('inf')

        for i, event in enumerate(arrow_events):
            # 跳过不同轨道、已处理的箭头
            if event.track_idx != track_idx:
                continue
            if i in self._arrow_states:
                continue
            # 只判定点按箭头（长按暂时简化为点按）
            time_diff = abs(event.start_sec - current_sec)

            # 在BAD窗口内才考虑
            if time_diff <= self.config.bad_window and time_diff < best_diff:
                best_diff = time_diff
                best_idx = i

        if best_idx < 0:
            return None, -1

        # 判定结果
        if best_diff <= self.config.perfect_window:
            result = JudgeResult.PERFECT
            score_add = self.config.perfect_score
            self.combo += 1
        elif best_diff <= self.config.good_window:
            result = JudgeResult.GOOD
            score_add = self.config.good_score
            self.combo += 1
        else:
            result = JudgeResult.BAD
            score_add = self.config.bad_score
            self.combo = 0

        # 更新状态
        self._arrow_states[best_idx] = 1  # 已命中

        # 计算分数（含连击奖励）
        if self.combo >= self.config.combo_bonus_threshold:
            score_add = int(score_add * 1.1)  # 10%加成

        self.score += score_add
        self.max_combo = max(self.max_combo, self.combo)

        # 更新统计
        if result == JudgeResult.PERFECT:
            self.stats.perfect += 1
        elif result == JudgeResult.GOOD:
            self.stats.good += 1
        elif result == JudgeResult.BAD:
            self.stats.bad += 1

        return result, best_idx

    def check_missed(self, arrow_events: List, current_sec: float) -> List[int]:
        """
        检测已错过判定窗口的箭头（MISS）

        Args:
            arrow_events: 箭头事件列表
            current_sec: 当前时间（秒）

        Returns:
            MISS的箭头索引列表
        """
        missed_indices = []

        for i, event in enumerate(arrow_events):
            if i in self._arrow_states:
                continue

            # 箭头已经离开BAD窗口（过了判定线太多）
            if event.start_sec < current_sec - self.config.bad_window:
                self._arrow_states[i] = 2  # 已miss
                self.stats.miss += 1
                self.combo = 0
                missed_indices.append(i)

        return missed_indices

    def get_accuracy(self) -> float:
        """
        计算准确率

        Returns:
            准确率（0.0-1.0）
        """
        total = self.stats.total
        if total == 0:
            return 1.0

        # PERFECT=100%, GOOD=70%, BAD=30%, MISS=0%
        weighted = (self.stats.perfect * 100 +
                   self.stats.good * 70 +
                   self.stats.bad * 30)
        return weighted / (total * 100)

    def get_grade(self) -> str:
        """
        获取评级

        Returns:
            评级字符串 (S/AAA/AA/A/B/C/D/F)
        """
        accuracy = self.get_accuracy()

        if accuracy >= 0.95 and self.stats.miss == 0:
            return "S"
        elif accuracy >= 0.95:
            return "AAA"
        elif accuracy >= 0.90:
            return "AA"
        elif accuracy >= 0.80:
            return "A"
        elif accuracy >= 0.70:
            return "B"
        elif accuracy >= 0.60:
            return "C"
        elif accuracy >= 0.50:
            return "D"
        else:
            return "F"

    def get_result_color(self, result: JudgeResult) -> Tuple[int, int, int]:
        """获取判定结果对应的颜色"""
        if result == JudgeResult.PERFECT:
            return self.config.perfect_color
        elif result == JudgeResult.GOOD:
            return self.config.good_color
        elif result == JudgeResult.BAD:
            return self.config.bad_color
        else:
            return self.config.miss_color

    def is_arrow_processed(self, arrow_idx: int) -> bool:
        """检查箭头是否已被处理"""
        return arrow_idx in self._arrow_states

    def get_arrow_state(self, arrow_idx: int) -> int:
        """
        获取箭头状态

        Returns:
            0=未处理, 1=已命中, 2=已miss
        """
        return self._arrow_states.get(arrow_idx, 0)

    @property
    def judge_count(self) -> Dict[str, int]:
        """获取判定计数（兼容旧接口）"""
        return self.stats.to_dict()

    def get_score(self) -> int:
        """获取当前分数"""
        return self.score

    def get_combo(self) -> int:
        """获取当前连击"""
        return self.combo

    def get_max_combo(self) -> int:
        """获取最大连击"""
        return self.max_combo


class JudgeDisplay:
    """判定结果显示管理器"""

    def __init__(self, display_duration: float = 0.8):
        """
        初始化判定显示管理器

        Args:
            display_duration: 判定文字显示时长（秒）
        """
        self.display_duration = display_duration
        self.current_result: Optional[JudgeResult] = None
        self.display_time: float = 0.0

    def show(self, result: JudgeResult):
        """显示判定结果"""
        self.current_result = result
        self.display_time = self.display_duration

    def update(self, dt: float):
        """更新显示时间"""
        if self.display_time > 0:
            self.display_time -= dt
            if self.display_time <= 0:
                self.current_result = None

    def get_alpha(self) -> float:
        """获取显示透明度（用于淡出效果）"""
        if self.display_time <= 0:
            return 0.0
        return min(1.0, self.display_time / 0.3)  # 最后0.3秒淡出

    def is_showing(self) -> bool:
        """是否正在显示"""
        return self.current_result is not None and self.display_time > 0


class HitEffect:
    """命中效果管理器"""

    def __init__(self, effect_duration: float = 0.25):
        """
        初始化命中效果管理器

        Args:
            effect_duration: 效果动画时长（秒）
        """
        self.effect_duration = effect_duration
        self._effects: Dict[int, dict] = {}  # arrow_idx -> effect_data

    def trigger(self, arrow_idx: int, track_idx: int, y_offset: float = 0.0):
        """
        触发命中效果

        Args:
            arrow_idx: 箭头索引
            track_idx: 轨道索引
            y_offset: Y偏移（相对于判定线）
        """
        self._effects[arrow_idx] = {
            "alpha": 1.0,
            "scale": 1.0,
            "time": self.effect_duration,
            "track_idx": track_idx,
            "y": y_offset
        }

    def update(self, dt: float):
        """更新所有效果状态"""
        to_remove = []
        for idx, effect in self._effects.items():
            effect["time"] -= dt
            if effect["time"] <= 0:
                to_remove.append(idx)
            else:
                # 动画进度 0->1
                progress = 1.0 - (effect["time"] / self.effect_duration)
                # 淡出 + 缩放
                effect["alpha"] = 1.0 - progress
                effect["scale"] = 1.0 + progress * 0.3  # 放大到1.3倍
                effect["y"] = effect.get("y", 0) + dt * 50  # 向上飘动效果

        for idx in to_remove:
            del self._effects[idx]

    def get_effects(self) -> Dict[int, dict]:
        """获取所有当前效果"""
        return self._effects.copy()

    def clear(self):
        """清除所有效果"""
        self._effects.clear()


class JudgeLight:
    """判定区光效管理器"""

    def __init__(self, track_count: int = 5, decay_rate: float = 2.8):
        """
        初始化判定光效管理器

        Args:
            track_count: 轨道数量
            decay_rate: 光效衰减速率（每秒衰减值）
        """
        self.track_count = track_count
        self.decay_rate = decay_rate
        self._lights: List[float] = [0.0] * track_count  # 各轨道光效强度 (0.0-1.0)

    def trigger(self, track_idx: int):
        """触发指定轨道的光效"""
        if 0 <= track_idx < self.track_count:
            self._lights[track_idx] = 1.0

    def update(self, dt: float):
        """更新光效衰减"""
        if dt <= 0:
            return
        decay = self.decay_rate * dt
        for i in range(self.track_count):
            self._lights[i] = max(0.0, self._lights[i] - decay)

    def get_light(self, track_idx: int) -> float:
        """获取指定轨道的光效强度"""
        if 0 <= track_idx < self.track_count:
            return self._lights[track_idx]
        return 0.0

    def get_all_lights(self) -> List[float]:
        """获取所有轨道的光效强度"""
        return self._lights.copy()
