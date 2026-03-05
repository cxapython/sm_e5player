# SM Arrow Player 项目助手

你是 SM Arrow Player 项目的开发助手。这是一个 Python + Pygame 实现的 StepMania 谱面可视化播放器。

## 项目核心架构

### 主文件结构 (sm_arrow_player.py)

```
1. 数据类定义 (33-62行)
   - SmChartInfo: 谱面基础信息
   - SmNotesBlock: NOTES区块数据
   - ArrowEvent: 播放核心数据结构

2. SM文件解析工具函数 (63-277行)
   - parse_sm_file(): 解析SM文件主入口
   - parse_sm_arrow_events(): 将NOTES转为事件表
   - build_arrow_events(): 构建播放用箭头事件列表

3. 皮肤资源类 SkinResource (454-632行)
   - get_tap_arrow(): 获取点按箭头皮肤
   - get_hold_body(): 获取长按箭身皮肤
   - get_hold_tail(): 获取长按箭尾皮肤
   - get_receptor(): 获取判定区皮肤

4. 播放器核心类 ArrowPlayer (635-1600行)
   主要方法:
   - load_sm(): 加载解析SM文件
   - init_pygame(): 初始化游戏环境
   - main_loop(): 主循环
   - draw(): 绘制画面
   - _try_judge_arrow(): 判定逻辑
   - _draw_*(): 各类绘制函数

5. 启动界面类 LauncherUI (1602-1850行)
   - 拖拽/选择文件
   - 启动播放器
```

### 关键数据流

```
SM文件 → parse_sm_file()
       → SmChartInfo (bpm, offset, title)
       → SmNotesBlock (measure_text)

NOTES文本 → parse_sm_arrow_events()
          → event_table: Dict[int, List[dict]]
          → 每个事件包含 aType, length, player

event_table → build_arrow_events()
            → List[ArrowEvent]
            → 包含 track_idx, start_sec, end_sec, aType

渲染循环:
  - 遍历 ArrowEvent
  - 根据 start_sec 计算屏幕Y坐标
  - 调用 _draw_tap_arrow / _draw_hold_arrow 绘制
```

### 坐标系统

```
窗口: window_w x window_h (默认 1100x800)

布局:
  header_h = 80        # 顶部信息栏高度
  judge_y = window_h * 0.18 + header_h  # 判定线Y坐标
  footer_h = 50        # 底部提示高度

轨道:
  track_count = 5
  track_total_w = min(620, window_w - 280)
  single_track_w = track_total_w // 5

轨道索引映射:
  0 = DownLeft (左下) - 按键 Z
  1 = UpLeft (左上)   - 按键 Q
  2 = Center (中间)   - 按键 S
  3 = UpRight (右上)  - 按键 E
  4 = DownRight (右下) - 按键 C
```

### 皮肤文件命名

```
{Direction} {Type} (doubleres) {Grid}.png

Direction: DownLeft | UpLeft | Center | UpRight | DownRight
Type:      Tap Note | Hold Body | Hold BottomCap | Ready Receptor
Grid:      3x2 | 6x1 | 1x3 (列x行)

注意: UpRight/DownRight 通过翻转 UpLeft/DownLeft 生成
```

## 常见改造任务

### 添加新判定效果
修改 `_try_judge_arrow()` 方法，在判定成功时触发效果。

### 修改滚动速度
调整 `self.scroll_speed` (默认 840.0)，单位是像素/秒。

### 添加新皮肤
1. 将PNG文件放入 noteskin/ 目录
2. 确保 PNG 格式支持透明通道
3. 遵循命名规范

### 修改判定窗口
调整以下属性:
```python
self.judge_window_perfect = 0.045  # 45ms
self.judge_window_good = 0.090     # 90ms
self.judge_window_bad = 0.135      # 135ms
```

### 添加连击音效
在 `_try_judge_arrow()` 中:
```python
# 判定成功后播放音效
if judge_result == "PERFECT":
    # pygame.mixer.Sound("perfect.wav").play()
```

## 注意事项

1. 所有时间单位为秒
2. lineNo 是基于 tick_per_beat 的时间刻度
3. 长按目前简化为点按判定，可扩展
4. 窗口大小可通过拖拽调整，UI需要自适应
