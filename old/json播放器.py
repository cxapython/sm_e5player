import io
import json
import os
import time
import zipfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pygame
import customtkinter as ctk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    _可用拖拽 = True
except Exception:
    _可用拖拽 = False


默认箭头皮肤zip文件名 = "E5_01.zip"


@dataclass
class 箭头事件:
    轨道序号: int
    开始秒: float
    结束秒: float
    aType: int
    原始lineNo: int
    原始length: int


def 读取_json(文件路径: str) -> dict:
    with open(文件路径, "r", encoding="utf-8") as f:
        return json.load(f)


def _清理拖拽路径(原始: str) -> str:
    s = 原始.strip()
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1]
    if " " in s:
        第一段 = s.split(" ")[0]
        if os.path.exists(第一段):
            return 第一段
    return s


def 找同目录音频(谱面json路径: str) -> Optional[str]:
    目录 = os.path.dirname(os.path.abspath(谱面json路径))
    if not os.path.isdir(目录):
        return None

    扩展优先 = [".ogg", ".mp3", ".wav"]
    全部候选: List[str] = []
    for 文件名 in os.listdir(目录):
        路径 = os.path.join(目录, 文件名)
        if not os.path.isfile(路径):
            continue
        低 = 文件名.lower()
        if any(低.endswith(ext) for ext in 扩展优先):
            全部候选.append(路径)

    if not 全部候选:
        return None

    json基名 = os.path.splitext(os.path.basename(谱面json路径))[0].lower()

    def 候选打分(路径: str) -> Tuple[int, int, int]:
        文件名 = os.path.basename(路径).lower()
        ext = os.path.splitext(文件名)[1].lower()
        ext分 = {".ogg": 3, ".mp3": 2, ".wav": 1}.get(ext, 0)
        命中分 = 2 if json基名 and json基名 in 文件名 else 0
        大小 = int(os.path.getsize(路径) / 1024)
        return (ext分, 命中分, 大小)

    全部候选.sort(key=候选打分, reverse=True)
    return 全部候选[0]


def 取最常见间隔(line列表: List[int]) -> Optional[int]:
    if len(line列表) < 3:
        return None
    排序后 = sorted(set(line列表))
    间隔计数: Dict[int, int] = {}
    for i in range(1, len(排序后)):
        d = 排序后[i] - 排序后[i - 1]
        if d <= 0:
            continue
        间隔计数[d] = 间隔计数.get(d, 0) + 1
    if not 间隔计数:
        return None
    return max(间隔计数.items(), key=lambda x: x[1])[0]


def 解析铺面基础信息(
    谱面数据: dict,
) -> Tuple[float, List[Tuple[int, float]], List[Tuple[int, int, int]]]:
    offset = float(谱面数据.get("scoreInfo", {}).get("offset", 0.0))

    bpms原始 = 谱面数据.get("bpms", []) or []
    bpm点: List[Tuple[int, float]] = []
    for b in bpms原始:
        try:
            lineNo = int(b.get("lineNo", 0))
            bpmVal = float(b.get("bpmVal", 120.0))
            bpm点.append((lineNo, bpmVal))
        except Exception:
            continue
    bpm点.sort(key=lambda x: x[0])
    if not bpm点:
        bpm点 = [(0, 120.0)]

    boards = 谱面数据.get("boards", []) or []
    if not boards:
        return offset, bpm点, []

    lineDatas = boards[0].get("lineDatas", []) or []
    音符: List[Tuple[int, int, int]] = []
    for 行 in lineDatas:
        lineNo = int(行.get("lineNo", 0))
        arrows = 行.get("arrows", []) or []
        for a in arrows:
            try:
                player = int(a.get("player", 1))
                if player != 1:
                    continue
                aType = int(a.get("aType", 0))
                length = int(a.get("length", 0))
                音符.append((lineNo, aType, length))
            except Exception:
                continue
    音符.sort(key=lambda x: x[0])
    return offset, bpm点, 音符


def 生成时间轴函数(
    bpm点: List[Tuple[int, float]], tick每拍: int
) -> List[Tuple[int, float, float]]:
    段: List[Tuple[int, float, float]] = []
    for i, (lineNo, bpm) in enumerate(bpm点):
        if i == 0:
            段.append((lineNo, 0.0, bpm))
            continue
        上lineNo, 上段起秒, 上bpm = 段[-1]
        deltaLine = lineNo - 上lineNo
        if deltaLine < 0:
            continue
        拍数 = deltaLine / float(tick每拍)
        增量秒 = 0.0 if 上bpm <= 0 else 拍数 * (60.0 / 上bpm)
        当前秒 = 上段起秒 + 增量秒
        段.append((lineNo, 当前秒, bpm))
    if not 段:
        段 = [(0, 0.0, 120.0)]
    return 段


def line转秒(lineNo: int, 段: List[Tuple[int, float, float]], tick每拍: int) -> float:
    lo, hi = 0, len(段) - 1
    idx = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if 段[mid][0] <= lineNo:
            idx = mid
            lo = mid + 1
        else:
            hi = mid - 1
    段起lineNo, 段起秒, bpm = 段[idx]
    deltaLine = lineNo - 段起lineNo
    拍数 = deltaLine / float(tick每拍)
    return 段起秒 if bpm <= 0 else 段起秒 + 拍数 * (60.0 / bpm)


def 构建箭头事件(
    音符: List[Tuple[int, int, int]],
    bpm段: List[Tuple[int, float, float]],
    tick每拍: int,
    aType映射: List[int],
) -> List[箭头事件]:
    aType到轨道: Dict[int, int] = {a: i for i, a in enumerate(aType映射)}
    事件: List[箭头事件] = []
    for lineNo, aType, length in 音符:
        if aType not in aType到轨道:
            continue
        轨 = aType到轨道[aType]
        开始 = line转秒(lineNo, bpm段, tick每拍)
        结束 = (
            line转秒(lineNo + max(0, length), bpm段, tick每拍) if length > 0 else 开始
        )
        事件.append(
            箭头事件(
                轨道序号=轨,
                开始秒=开始,
                结束秒=结束,
                aType=aType,
                原始lineNo=lineNo,
                原始length=length,
            )
        )
    事件.sort(key=lambda e: e.开始秒)
    return 事件


def 秒格式化(t: float) -> str:
    if t < 0:
        t = 0
    m = int(t // 60)
    s = t - m * 60
    return f"{m:02d}:{s:05.2f}"


def 安全加载中文字体(字号: int) -> pygame.font.Font:
    try:
        字体路径 = r"C:\Windows\Fonts\msyh.ttc"
        if os.path.exists(字体路径):
            return pygame.font.Font(字体路径, 字号)
    except Exception:
        pass
    return pygame.font.Font(None, 字号)


class 皮肤资源:
    def __init__(self, 皮肤目录: str):
        self.皮肤目录 = os.path.abspath(皮肤目录)
        self._缓存: Dict[str, pygame.Surface] = {}
        self._缓存翻转: Dict[str, pygame.Surface] = {}
        self._根目录缓存: Optional[str] = None  # 可能是 "" 或 "某个子目录"

    def 打开(self):
        # 文件夹模式无需打开资源包，这里仅做存在性检查
        if not os.path.isdir(self.皮肤目录):
            self._根目录缓存 = ""
            return
        self._猜根目录()

    def 关闭(self):
        self._缓存.clear()
        self._缓存翻转.clear()
        self._根目录缓存 = None

    def _猜根目录(self) -> str:
        """
        如果 noteskin 目录下直接有 png，就根目录为 ""；
        否则找第一个包含 png 的子目录作为根目录（只取一层）。
        """
        if self._根目录缓存 is not None:
            return self._根目录缓存

        if not os.path.isdir(self.皮肤目录):
            self._根目录缓存 = ""
            return ""

        try:
            # 1) 直接在 noteskin 下找 png
            for n in os.listdir(self.皮肤目录):
                p = os.path.join(self.皮肤目录, n)
                if os.path.isfile(p) and n.lower().endswith(".png"):
                    self._根目录缓存 = ""
                    return ""

            # 2) 找一级子目录内是否有 png
            for n in os.listdir(self.皮肤目录):
                子 = os.path.join(self.皮肤目录, n)
                if not os.path.isdir(子):
                    continue
                for f in os.listdir(子):
                    p = os.path.join(子, f)
                    if os.path.isfile(p) and f.lower().endswith(".png"):
                        self._根目录缓存 = n
                        return n
        except Exception:
            pass

        self._根目录缓存 = ""
        return ""

    @staticmethod
    def _解析网格(文件名: str) -> Tuple[int, int]:
        base = os.path.basename(文件名).lower()
        import re

        m = re.findall(r"(\d+)\s*x\s*(\d+)\.png$", base)
        if not m:
            return (1, 1)
        a, b = m[-1]
        return (max(1, int(a)), max(1, int(b)))

    def _真实路径(self, 文件名: str) -> str:
        根 = self._猜根目录()
        if 根:
            return os.path.join(self.皮肤目录, 根, 文件名)
        return os.path.join(self.皮肤目录, 文件名)

    def _读png(self, 文件名: str) -> Optional[pygame.Surface]:
        # 用“文件名(相对)”作为缓存键，避免根目录变化导致重复加载
        键 = f"{self._猜根目录()}::{文件名}"
        if 键 in self._缓存:
            return self._缓存[键]

        路径 = self._真实路径(文件名)
        if not os.path.exists(路径):
            return None

        try:
            图 = pygame.image.load(路径).convert_alpha()
            self._缓存[键] = 图
            return 图
        except Exception:
            return None

    def _裁帧(
        self, 图: pygame.Surface, 列: int, 行: int, 帧索引: int
    ) -> pygame.Surface:
        w, h = 图.get_width(), 图.get_height()
        单w = max(1, w // 列)
        单h = max(1, h // 行)
        总帧 = 列 * 行
        if 总帧 <= 1:
            rect = pygame.Rect(0, 0, 单w, 单h)
            return 图.subsurface(rect).copy()
        帧索引 = max(0, min(总帧 - 1, 帧索引))
        行号 = 帧索引 // 列
        列号 = 帧索引 % 列
        rect = pygame.Rect(列号 * 单w, 行号 * 单h, 单w, 单h)
        return 图.subsurface(rect).copy()

    def _水平翻转(self, 图: pygame.Surface, 缓存键: str) -> pygame.Surface:
        if 缓存键 in self._缓存翻转:
            return self._缓存翻转[缓存键]
        翻 = pygame.transform.flip(图, True, False)
        self._缓存翻转[缓存键] = 翻
        return 翻

    def 取点按箭头(self, 方向名: str) -> Optional[pygame.Surface]:
        文件名 = f"{方向名} Tap Note (doubleres) 3x2.png"
        图 = self._读png(文件名)
        if 图:
            列, 行 = self._解析网格(文件名)
            return self._裁帧(图, 列, 行, 帧索引=0)

        if 方向名 == "UpRight":
            左 = self.取点按箭头("UpLeft")
            return self._水平翻转(左, "Flip:UpLeft:Tap") if 左 else None
        if 方向名 == "DownRight":
            左 = self.取点按箭头("DownLeft")
            return self._水平翻转(左, "Flip:DownLeft:Tap") if 左 else None
        return None

    def 取长按身体(self, 方向名: str) -> Optional[pygame.Surface]:
        文件名 = f"{方向名} Hold Body active (doubleres) 6x1.png"
        图 = self._读png(文件名)
        if 图:
            列, 行 = self._解析网格(文件名)
            return self._裁帧(图, 列, 行, 帧索引=0)

        if 方向名 == "UpRight":
            左 = self.取长按身体("UpLeft")
            return self._水平翻转(左, "Flip:UpLeft:HoldBody") if 左 else None
        if 方向名 == "DownRight":
            左 = self.取长按身体("DownLeft")
            return self._水平翻转(左, "Flip:DownLeft:HoldBody") if 左 else None
        return None

    def 取长按尾巴(self, 方向名: str) -> Optional[pygame.Surface]:
        文件名 = f"{方向名} Hold BottomCap active (doubleres) 6x1.png"
        图 = self._读png(文件名)
        if 图:
            列, 行 = self._解析网格(文件名)
            return self._裁帧(图, 列, 行, 帧索引=0)

        if 方向名 == "UpRight":
            左 = self.取长按尾巴("UpLeft")
            return self._水平翻转(左, "Flip:UpLeft:HoldCap") if 左 else None
        if 方向名 == "DownRight":
            左 = self.取长按尾巴("DownLeft")
            return self._水平翻转(左, "Flip:DownLeft:HoldCap") if 左 else None
        return None

    def 取判定区_receptor(self, 方向名: str) -> Optional[pygame.Surface]:
        if 方向名 == "Center":
            文件名 = "Center Ready Receptor (doubleres) 1x3.png"
            图 = self._读png(文件名)
            if not 图:
                return None
            列, 行 = self._解析网格(文件名)
            return self._裁帧(图, 列, 行, 帧索引=1)

        if 方向名 == "UpLeft":
            文件名 = "UpLeft Ready Receptor (doubleres) 1x3.png"
            图 = self._读png(文件名)
            if not 图:
                return None
            列, 行 = self._解析网格(文件名)
            return self._裁帧(图, 列, 行, 帧索引=1)

        if 方向名 == "DownLeft":
            文件名 = "DownLeft Ready Receptor (doubleres) 1x3.png"
            图 = self._读png(文件名)
            if not 图:
                return None
            列, 行 = self._解析网格(文件名)
            return self._裁帧(图, 列, 行, 帧索引=1)

        if 方向名 == "UpRight":
            左 = self.取判定区_receptor("UpLeft")
            return self._水平翻转(左, "Flip:UpLeft:Receptor") if 左 else None

        if 方向名 == "DownRight":
            左 = self.取判定区_receptor("DownLeft")
            return self._水平翻转(左, "Flip:DownLeft:Receptor") if 左 else None

        return None


class 箭头播放器:
    def __init__(self, 谱面路径: str, 音频路径: Optional[str], 皮肤目录路径: str):
        self.谱面路径 = 谱面路径
        self.音频路径 = 音频路径
        self.皮肤zip路径 = ""  # 兼容旧字段（可删但不必要）
        self.皮肤目录路径 = 皮肤目录路径

        self.窗口宽 = 960
        self.窗口高 = 900
        self.fps = 60

        self.滚动速度 = 420.0 * 2.0

        self.tick每拍候选 = [96, 48, 192]
        self.tick每拍 = 96

        self.映射候选列表 = [
            [1, 2, 4, 6, 7],
            [2, 1, 4, 7, 6],
            [6, 7, 4, 1, 2],
            [7, 6, 4, 2, 1],
        ]
        self.当前映射索引 = 0

        self.轨道方向名 = ["DownLeft", "UpLeft", "Center", "UpRight", "DownRight"]

        self.offset = 0.0
        self.bpm点: List[Tuple[int, float]] = []
        self.音符: List[Tuple[int, int, int]] = []
        self.bpm段: List[Tuple[int, float, float]] = []
        self.事件: List[箭头事件] = []

        self.播放中 = False
        self.起始系统秒 = 0.0
        self.暂停时刻谱面秒 = 0.0
        self.当前谱面秒 = 0.0
        self.总时长秒 = 0.0

        self.屏幕: Optional[pygame.Surface] = None
        self.字体: Optional[pygame.font.Font] = None
        self.小字体: Optional[pygame.font.Font] = None

        # ✅ 关键：现在用文件夹皮肤
        self.皮肤 = 皮肤资源(self.皮肤目录路径)

        self.点按图: List[Optional[pygame.Surface]] = [None] * 5
        self.长按身体图: List[Optional[pygame.Surface]] = [None] * 5
        self.长按尾巴图: List[Optional[pygame.Surface]] = [None] * 5
        self.receptor图: List[Optional[pygame.Surface]] = [None] * 5

        self.判定光: List[float] = [0.0] * 5
        self.判定光衰减每秒: float = 2.8
        self.上次谱面秒: float = 0.0
        self._下一命中索引: int = 0

        self.结束原因: str = ""

    def 载入(self):
        数据 = 读取_json(self.谱面路径)
        self.offset, self.bpm点, self.音符 = 解析铺面基础信息(数据)

        line列表 = [ln for ln, _, _ in self.音符]
        最常见 = 取最常见间隔(line列表)
        if 最常见 is not None and 最常见 in self.tick每拍候选:
            self.tick每拍 = 最常见

        self.bpm段 = 生成时间轴函数(self.bpm点, self.tick每拍)

        if self.音符:
            最后_ln, _, 最后_len = self.音符[-1]
            self.总时长秒 = line转秒(
                最后_ln + max(0, 最后_len), self.bpm段, self.tick每拍
            )
        else:
            self.总时长秒 = 0.0

        self.重建事件()
        self._重置命中指针(self.当前谱面秒)

    def 重建事件(self):
        映射 = self.映射候选列表[self.当前映射索引]
        self.事件 = 构建箭头事件(self.音符, self.bpm段, self.tick每拍, 映射)

    def 初始化pygame(self):
        pygame.init()
        pygame.font.init()
        try:
            pygame.mixer.init()
        except Exception:
            self.音频路径 = None

        self.屏幕 = pygame.display.set_mode((self.窗口宽, self.窗口高))
        pygame.display.set_caption("箭头播放器")

        self.字体 = 安全加载中文字体(20)
        self.小字体 = 安全加载中文字体(16)

        self.皮肤.打开()
        self._加载皮肤图()

        if self.音频路径 and os.path.exists(self.音频路径):
            try:
                pygame.mixer.music.load(self.音频路径)
            except Exception:
                self.音频路径 = None
        else:
            self.音频路径 = None

    def _加载皮肤图(self):
        for i, 方向名 in enumerate(self.轨道方向名):
            self.点按图[i] = self.皮肤.取点按箭头(方向名)
            self.长按身体图[i] = self.皮肤.取长按身体(方向名)
            self.长按尾巴图[i] = self.皮肤.取长按尾巴(方向名)
            self.receptor图[i] = self.皮肤.取判定区_receptor(方向名)

    def 播放(self):
        if self.播放中:
            return
        self.播放中 = True
        self.起始系统秒 = time.perf_counter() - self.暂停时刻谱面秒
        self.上次谱面秒 = self.暂停时刻谱面秒
        self._重置命中指针(self.暂停时刻谱面秒)

        if self.音频路径:
            音频起点 = max(0.0, self.暂停时刻谱面秒 - self.offset)
            try:
                pygame.mixer.music.play(start=音频起点)
            except TypeError:
                pygame.mixer.music.play()

    def 暂停(self):
        if not self.播放中:
            return
        self.播放中 = False
        self.暂停时刻谱面秒 = self.当前谱面秒
        if self.音频路径:
            try:
                pygame.mixer.music.pause()
            except Exception:
                pass

    def 设定谱面时间(self, 新秒: float):
        新秒 = max(0.0, min(self.总时长秒, 新秒))
        self.当前谱面秒 = 新秒
        self.暂停时刻谱面秒 = 新秒
        self.上次谱面秒 = 新秒
        self._重置命中指针(新秒)

        if self.播放中:
            self.起始系统秒 = time.perf_counter() - 新秒
            if self.音频路径:
                try:
                    pygame.mixer.music.stop()
                    音频起点 = max(0.0, 新秒 - self.offset)
                    try:
                        pygame.mixer.music.play(start=音频起点)
                    except TypeError:
                        pygame.mixer.music.play()
                except Exception:
                    pass

    def _重置命中指针(self, 当前谱面秒: float):
        # 二分找第一个 开始秒 > 当前谱面秒 的事件索引
        lo, hi = 0, len(self.事件)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.事件[mid].开始秒 <= 当前谱面秒:
                lo = mid + 1
            else:
                hi = mid
        self._下一命中索引 = lo

    def _触发判定光(self, 轨道: int):
        if 0 <= 轨道 < len(self.判定光):
            self.判定光[轨道] = 1.0

    def _更新判定光(self, dt: float):
        if dt <= 0:
            return
        衰减 = self.判定光衰减每秒 * dt
        for i in range(len(self.判定光)):
            self.判定光[i] = max(0.0, self.判定光[i] - 衰减)

    def 主循环(self) -> str:
        """
        返回结束原因：
          - "finished": 播放结束自动退出
          - "closed": 用户关闭窗口/按ESC退出
        """
        时钟 = pygame.time.Clock()
        running = True
        self.结束原因 = ""

        while running:
            dt = 时钟.tick(self.fps) / 1000.0
            self._更新判定光(dt)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.结束原因 = "closed"
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.结束原因 = "closed"
                        running = False
                    elif event.key == pygame.K_SPACE:
                        self.暂停() if self.播放中 else self.播放()
                    elif event.key == pygame.K_r:
                        self.设定谱面时间(0.0)
                    elif event.key == pygame.K_LEFT:
                        self.设定谱面时间(self.当前谱面秒 - 5.0)
                    elif event.key == pygame.K_RIGHT:
                        self.设定谱面时间(self.当前谱面秒 + 5.0)
                    elif event.key == pygame.K_LEFTBRACKET:
                        self.滚动速度 = max(60.0, self.滚动速度 - 30.0)
                    elif event.key == pygame.K_RIGHTBRACKET:
                        self.滚动速度 = min(2000.0, self.滚动速度 + 30.0)
                    elif event.key == pygame.K_MINUS:
                        self.offset -= 0.01
                    elif event.key == pygame.K_EQUALS:
                        self.offset += 0.01
                    elif event.key == pygame.K_t:
                        idx = (
                            self.tick每拍候选.index(self.tick每拍)
                            if self.tick每拍 in self.tick每拍候选
                            else 0
                        )
                        idx = (idx + 1) % len(self.tick每拍候选)
                        self.tick每拍 = self.tick每拍候选[idx]
                        self.bpm段 = 生成时间轴函数(self.bpm点, self.tick每拍)
                        self.重建事件()
                        if self.音符:
                            最后_ln, _, 最后_len = self.音符[-1]
                            self.总时长秒 = line转秒(
                                最后_ln + max(0, 最后_len), self.bpm段, self.tick每拍
                            )
                        self.设定谱面时间(self.当前谱面秒)
                    elif event.key == pygame.K_m:
                        self.当前映射索引 = (self.当前映射索引 + 1) % len(
                            self.映射候选列表
                        )
                        self.重建事件()
                        self._重置命中指针(self.当前谱面秒)

            if self.播放中:
                self.上次谱面秒 = self.当前谱面秒
                self.当前谱面秒 = time.perf_counter() - self.起始系统秒

                # ✅ 3) 命中触发：当 t 跨过某事件开始秒，就触发该轨道光芒
                while self._下一命中索引 < len(self.事件):
                    e = self.事件[self._下一命中索引]
                    if e.开始秒 <= self.当前谱面秒:
                        self._触发判定光(e.轨道序号)
                        self._下一命中索引 += 1
                    else:
                        break

                if self.当前谱面秒 >= self.总时长秒:
                    self.当前谱面秒 = self.总时长秒
                    self.暂停()
                    self.结束原因 = "finished"
                    running = False

            self.绘制()
            pygame.display.flip()

        try:
            self.皮肤.关闭()
            pygame.quit()
        except Exception:
            pass

        if not self.结束原因:
            self.结束原因 = "closed"
        return self.结束原因

    def 绘制(self):
        assert self.屏幕 is not None
        assert self.字体 is not None
        assert self.小字体 is not None

        self.屏幕.fill((15, 15, 18))

        # 顶部区域：操作提示 + 信息
        操作提示 = "空格：暂停/继续  R：重播  ←/→：快退快进  T：切tick  M：切映射  -/=:调offset  [/]:调速度  Esc：退出"
        self.屏幕.blit(self.小字体.render(操作提示, True, (255, 220, 160)), (18, 10))

        信息区y1 = 34
        信息区y2 = 58
        信息区y3 = 80

        顶部y = 120
        判定线y = 210
        底部y = self.窗口高 - 74

        轨道数 = 5

        # ✅ 4) 整体更窄
        轨道总宽 = 620
        轨道起x = (self.窗口宽 - 轨道总宽) // 2
        单轨宽 = 轨道总宽 // 轨道数

        # 轨道背景
        for i in range(轨道数):
            x = 轨道起x + i * 单轨宽
            pygame.draw.rect(
                self.屏幕,
                (28, 28, 34),
                (x + 3, 顶部y, 单轨宽 - 6, 底部y - 顶部y),
                border_radius=14,
            )
            pygame.draw.rect(
                self.屏幕,
                (45, 45, 55),
                (x + 3, 顶部y, 单轨宽 - 6, 底部y - 顶部y),
                width=2,
                border_radius=14,
            )

        pygame.draw.line(
            self.屏幕,
            (220, 220, 220),
            (轨道起x, 判定线y),
            (轨道起x + 轨道总宽, 判定线y),
            2,
        )

        # Receptor + 判定光（叠加在 receptor 周围）
        for i in range(轨道数):
            x中心 = 轨道起x + i * 单轨宽 + 单轨宽 // 2

            # ✅ 3) 先画光（在 receptor 下面/周围）
            强度 = self.判定光[i]
            if 强度 > 0:
                光层 = pygame.Surface((单轨宽, 单轨宽), pygame.SRCALPHA)
                cx, cy = 单轨宽 // 2, 单轨宽 // 2
                # 多层光圈：半径递增，透明递减
                for k in range(5):
                    r = int(单轨宽 * (0.18 + 0.08 * k))
                    a = int(强度 * (140 - k * 22))
                    pygame.draw.circle(光层, (255, 235, 185, max(0, a)), (cx, cy), r)
                self.屏幕.blit(光层, (x中心 - 单轨宽 // 2, 判定线y - 单轨宽 // 2))

            图 = self.receptor图[i]
            if not 图:
                continue

            # ✅ 4) receptor 更窄一点
            目标宽 = int(单轨宽 * 0.60)
            比例 = 目标宽 / float(max(1, 图.get_width()))
            高 = int(图.get_height() * 比例)
            缩放图 = pygame.transform.smoothscale(图, (目标宽, 高))
            self.屏幕.blit(缩放图, (x中心 - 目标宽 // 2, 判定线y - 高 // 2))

        # 信息
        文件名 = os.path.basename(self.谱面路径)
        映射 = self.映射候选列表[self.当前映射索引]
        音频名 = os.path.basename(self.音频路径) if self.音频路径 else "（未找到音频）"
        t = self.当前谱面秒

        文本1 = f"谱面：{文件名}   音频：{音频名}"
        文本2 = f"时间：{秒格式化(t)} / {秒格式化(self.总时长秒)}   播放：{'是' if self.播放中 else '否'}"
        文本3 = f"tick/拍：{self.tick每拍}   视觉速度：{int(self.滚动速度)}px/s   offset：{self.offset:+.2f}s   映射：{映射}"

        self.屏幕.blit(self.字体.render(文本1, True, (235, 235, 235)), (18, 信息区y1))
        self.屏幕.blit(self.小字体.render(文本2, True, (200, 200, 210)), (18, 信息区y2))
        self.屏幕.blit(self.小字体.render(文本3, True, (170, 170, 190)), (18, 信息区y3))

        # 音符（✅ 2) 到判定线就消失）
        可视秒 = (底部y - 判定线y) / self.滚动速度
        提前 = 可视秒 + 1.0

        for e in self.事件:
            if e.开始秒 < t - 0.5:
                if e.结束秒 < t - 0.5:
                    continue
            if e.开始秒 > t + 提前:
                break

            x中心 = 轨道起x + e.轨道序号 * 单轨宽 + 单轨宽 // 2

            dy开始 = (e.开始秒 - t) * self.滚动速度
            y开始 = 判定线y + dy开始

            if abs(e.结束秒 - e.开始秒) < 1e-6:
                # 点按：只在判定线及其下方显示，到了线就“消失”
                if y开始 >= 判定线y:
                    self._画点按(e.轨道序号, x中心, y开始, 单轨宽, 判定线y)
            else:
                # 长按：做裁切，头到线就不往上画
                dy结束 = (e.结束秒 - t) * self.滚动速度
                y结束 = 判定线y + dy结束
                self._画长按(e.轨道序号, x中心, y开始, y结束, 单轨宽, 判定线y)

        line列表 = [ln for ln, _, _ in self.音符[:8000]]
        最常见 = 取最常见间隔(line列表)
        if 最常见 is not None and 最常见 != self.tick每拍:
            提示 = f"[疑点] 最常见 lineNo 间隔={最常见}，当前 tick/拍={self.tick每拍}。按 T 切换试试。"
            self.屏幕.blit(
                self.小字体.render(提示, True, (255, 180, 120)), (18, self.窗口高 - 34)
            )

    def _画点按(self, 轨道: int, x中心: int, y: float, 单轨宽: int, 判定线y: int):
        # ✅ 2) 判定线之上直接不画
        if y < 判定线y:
            return
        if y < 50 or y > self.窗口高 - 40:
            return

        图 = self.点按图[轨道]
        if 图:
            # ✅ 4) 箭头更窄
            目标 = int(单轨宽 * 0.60)
            目标 = max(22, 目标)
            比例 = 目标 / float(max(1, 图.get_width()))
            高 = int(图.get_height() * 比例)
            缩放图 = pygame.transform.smoothscale(图, (目标, 高))
            self.屏幕.blit(缩放图, (x中心 - 目标 // 2, int(y) - 高 // 2))
            return

        半径 = max(9, min(22, 单轨宽 // 4))
        pygame.draw.circle(self.屏幕, (240, 240, 245), (x中心, int(y)), 半径)
        pygame.draw.circle(self.屏幕, (20, 20, 25), (x中心, int(y)), 半径, 3)

    def _画长按(
        self,
        轨道: int,
        x中心: int,
        y开始: float,
        y结束: float,
        单轨宽: int,
        判定线y: int,
    ):
        # 长按：判定线以上裁切，不让它跑到线上方
        y1 = min(y开始, y结束)
        y2 = max(y开始, y结束)

        # ✅ 2) 裁切：上界至少是判定线（让它在到线时“消失”）
        y1 = max(y1, float(判定线y))

        if y2 < 50 or y1 > self.窗口高 - 40:
            return

        y1c = max(50.0, y1)
        y2c = min(float(self.窗口高 - 40), y2)
        if y2c <= y1c:
            return

        身体图 = self.长按身体图[轨道]
        尾巴图 = self.长按尾巴图[轨道]

        if 身体图:
            # ✅ 4) 身体更窄
            目标宽 = int(单轨宽 * 0.26)
            目标宽 = max(12, 目标宽)
            比例 = 目标宽 / float(max(1, 身体图.get_width()))
            单块高 = int(身体图.get_height() * 比例)
            单块高 = max(8, 单块高)
            缩放身体 = pygame.transform.smoothscale(身体图, (目标宽, 单块高))
            当前y = int(y1c)
            while 当前y < int(y2c):
                self.屏幕.blit(缩放身体, (x中心 - 目标宽 // 2, 当前y))
                当前y += 单块高
        else:
            宽 = max(9, min(16, 单轨宽 // 7))
            rect = pygame.Rect(x中心 - 宽 // 2, int(y1c), 宽, int(max(2, y2c - y1c)))
            pygame.draw.rect(self.屏幕, (220, 220, 230), rect, border_radius=6)
            pygame.draw.rect(self.屏幕, (20, 20, 25), rect, width=2, border_radius=6)

        if 尾巴图:
            # ✅ 4) 尾巴更窄
            目标宽 = int(单轨宽 * 0.40)
            比例 = 目标宽 / float(max(1, 尾巴图.get_width()))
            高 = int(尾巴图.get_height() * 比例)
            缩放尾 = pygame.transform.smoothscale(尾巴图, (目标宽, 高))
            self.屏幕.blit(缩放尾, (x中心 - 目标宽 // 2, int(y2c) - 高 // 2))

        # 头（点按）同样遵循：到判定线就消失
        if y开始 >= 判定线y:
            self._画点按(轨道, x中心, y开始, 单轨宽, 判定线y)


class 启动界面:
    def __init__(self):
        if _可用拖拽:
            self.根 = TkinterDnD.Tk()
        else:
            import tkinter as tk

            self.根 = tk.Tk()

        self.根.title("拖入谱面 JSON（自动找音频并自动播放）")
        self.根.geometry("720x500")
        self.根.resizable(False, False)

        ctk.set_appearance_mode("dark")
        self.ctk根 = ctk.CTkFrame(self.根)
        self.ctk根.pack(fill="both", expand=True, padx=14, pady=14)

        self.状态文本 = ctk.StringVar(
            value="把 .json 文件拖到下面区域，会自动开播（播放完/关闭会自动回到这里）"
        )
        self.json路径 = ctk.StringVar(value="")

        标题 = ctk.CTkLabel(
            self.ctk根,
            text="拖入谱面 JSON 自动播放",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        标题.pack(pady=(6, 10))

        self.拖拽框 = ctk.CTkFrame(self.ctk根, height=220, corner_radius=14)
        self.拖拽框.pack(fill="x", padx=10, pady=(0, 12))

        self.拖拽提示 = ctk.CTkLabel(
            self.拖拽框,
            text="把 .json 文件拖到这里\n（会自动识别同目录音频，并自动打开播放器）",
            font=ctk.CTkFont(size=16),
        )
        self.拖拽提示.place(relx=0.5, rely=0.5, anchor="center")

        if _可用拖拽:
            self.拖拽框._canvas.drop_target_register(DND_FILES)
            self.拖拽框._canvas.dnd_bind("<<Drop>>", self._处理拖拽)
        else:
            self.状态文本.set(
                "拖拽不可用：请先 pip install tkinterdnd2（也可用按钮选择 JSON）"
            )

        行1 = ctk.CTkFrame(self.ctk根)
        行1.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkEntry(
            行1, textvariable=self.json路径, placeholder_text="谱面JSON路径", width=520
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            行1,
            text="选择JSON（选择后也会自动播放）",
            width=170,
            command=self._选择json,
        ).pack(side="left")

        ctk.CTkLabel(
            self.ctk根, textvariable=self.状态文本, wraplength=680, justify="left"
        ).pack(pady=(6, 0))

        说明 = "说明：播放结束会自动关闭箭头窗口并返回；手动关闭/按Esc也会返回。"
        ctk.CTkLabel(
            self.ctk根,
            text=说明,
            wraplength=680,
            justify="left",
            font=ctk.CTkFont(size=13),
        ).pack(pady=(10, 0))

    def _处理拖拽(self, 事件):
        路径 = _清理拖拽路径(事件.data)
        self._载入并自动播放(路径)

    def _选择json(self):
        import tkinter.filedialog as fd

        路径 = fd.askopenfilename(
            title="选择谱面 JSON", filetypes=[("JSON", "*.json"), ("All", "*.*")]
        )
        if 路径:
            self._载入并自动播放(路径)

    def _载入并自动播放(self, json路径: str):
        json路径 = json路径.strip()
        if not json路径.lower().endswith(".json"):
            self.状态文本.set("拖入/选择的不是 .json")
            return
        if not os.path.exists(json路径):
            self.状态文本.set("路径不存在")
            return

        self.json路径.set(json路径)
        音频路径 = 找同目录音频(json路径)

        if 音频路径:
            self.状态文本.set(f"已载入：{json路径}\n自动找到音频：{音频路径}")
        else:
            self.状态文本.set(
                f"已载入：{json路径}\n同目录未找到 mp3/ogg/wav，将只播放箭头"
            )

        try:
            self.根.withdraw()
        except Exception:
            pass

        # ✅ 关键：相对路径 -> 程序所在目录下 noteskin
        程序目录 = os.path.dirname(os.path.abspath(__file__))
        皮肤目录路径 = os.path.join(程序目录, "noteskin")

        # 🔥 exe 打包时 __file__ 可能不是你想象的路径（尤其 PyInstaller onefile）
        # 更稳的做法是用 sys._MEIPASS 或 sys.executable 的目录：
        # 这里我直接做兼容：优先用 exe 所在目录
        try:
            import sys

            if getattr(sys, "frozen", False):
                程序目录 = os.path.dirname(sys.executable)
                皮肤目录路径 = os.path.join(程序目录, "noteskin")
        except Exception:
            pass

        if not os.path.isdir(皮肤目录路径):
            self.状态文本.set(
                f"皮肤目录不存在：{皮肤目录路径}\n请把 noteskin 文件夹放到程序同目录下。"
            )
            try:
                self.根.deiconify()
            except Exception:
                pass
            return

        播放器 = 箭头播放器(json路径, 音频路径, 皮肤目录路径)

        结束原因 = "closed"
        try:
            播放器.载入()
            播放器.初始化pygame()
            播放器.播放()
            结束原因 = 播放器.主循环()
        except Exception as e:
            self.状态文本.set(f"运行失败：{type(e).__name__}: {e}")
        finally:
            try:
                self.根.deiconify()
                self.根.lift()
                self.根.focus_force()
            except Exception:
                pass

            if 结束原因 == "finished":
                self.状态文本.set("播放结束：已自动返回主界面（可继续拖入下一个JSON）")
            else:
                if "运行失败" not in self.状态文本.get():
                    self.状态文本.set("已返回主界面（你关闭了箭头窗口或按了 Esc）")

    def 运行(self):
        self.根.mainloop()


def main():
    启动器 = 启动界面()
    启动器.运行()


if __name__ == "__main__":
    main()
