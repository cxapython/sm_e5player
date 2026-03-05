# SM Arrow Player

一个基于 Python + Pygame 的 StepMania 谱面可视化播放器，支持直接播放 `.sm` 格式谱面文件。

## 功能特性

- **直接播放 SM 谱面**: 无需转换格式，直接解析 `.sm` 文件
- **自动音频识别**: 自动加载谱面同目录的音频文件（支持 mp3/ogg/wav）
- **封面背景支持**: 自动加载 `bn.jpg`、`banner.jpg` 等封面图片作为背景
- **可调节窗口**: 支持拖拽调整窗口大小，自适应布局
- **动态判定效果**:
  - 按键时判定区缩小动画
  - 箭头接近判定区时高亮提示
  - 命中后淡出+放大动画
- **判定系统**: 支持 PERFECT/GOOD/BAD/MISS 四级判定
- **NoteSkin 支持**: 兼容 StepMania 皮肤格式

## 快速开始

### 环境要求

- Python 3.8+
- 依赖库：`pygame`, `customtkinter`

### 安装依赖

```bash
pip install pygame customtkinter

# 可选：支持拖拽功能
pip install tkinterdnd2
```

### 运行

```bash
python sm_arrow_player.py
```

### 使用方法

1. 启动程序后，拖入 `.sm` 谱面文件到窗口，或点击"浏览文件"选择
2. 程序自动识别同目录的音频文件和封面图片
3. 按空格键开始/暂停播放

## 快捷键

| 按键 | 功能 |
|------|------|
| `空格` | 暂停/继续播放 |
| `R` | 从头重新播放 |
| `←` / `→` | 快退/快进 5 秒 |
| `[` / `]` | 降低/提高滚动速度 |
| `-` / `=` | 调整音画偏移 (offset) |
| `T` | 切换 tick/拍 设置 |
| `M` | 切换 aType 映射（轨道映射） |
| `Q/E/S/Z/C` | 游戏按键（对应五个轨道） |
| `Esc` | 退出播放 |

## 项目结构

```
sm_e5player/
├── sm_arrow_player.py      # 主程序文件（单文件架构）
├── noteskin/               # 皮肤资源目录
│   ├── Center Tap Note (doubleres) 3x2.png
│   ├── Center Hold Body active (doubleres) 6x1.png
│   ├── Center Hold BottomCap active (doubleres) 6x1.png
│   ├── Center Ready Receptor (doubleres) 1x3.png
│   ├── UpLeft ...          # 左上轨道皮肤
│   ├── UpRight ...         # 右上轨道皮肤
│   ├── DownLeft ...        # 左下轨道皮肤
│   ├── DownRight ...       # 右下轨道皮肤
│   └── metrics.ini         # 皮肤配置（可选）
├── songs/                  # 谱面目录（示例）
│   └── [歌曲名]/
│       ├── *.sm            # 谱面文件
│       ├── *.mp3/ogg/wav   # 音频文件
│       └── bn.jpg          # 封面图片（可选）
└── README.md
```

## 架构说明

### 核心类

```
┌─────────────────────────────────────────────────────────────┐
│                      LauncherUI (启动界面)                    │
│  - 拖拽/选择 SM 文件                                          │
│  - 自动查找音频和封面                                          │
│  - 启动 ArrowPlayer                                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     ArrowPlayer (播放器核心)                   │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ SM 解析模块  │  │  播放控制   │  │     渲染模块        │  │
│  │             │  │             │  │                     │  │
│  │ parse_sm    │  │ play/pause  │  │ draw()              │  │
│  │ parse_bpm   │  │ set_chart   │  │ _draw_background    │  │
│  │ parse_notes │  │ _update_*   │  │ _draw_track_*       │  │
│  └─────────────┘  └─────────────┘  │ _draw_arrows        │  │
│                                    │ _draw_receptor      │  │
│  ┌─────────────┐  ┌─────────────┐  │ _draw_judge_*       │  │
│  │ 判定系统    │  │  皮肤管理   │  └─────────────────────┘  │
│  │             │  │             │                           │
│  │ _try_judge  │  │ SkinResource│                           │
│  │ _check_miss │  │ get_tap_*   │                           │
│  │ hit_anim    │  │ get_hold_*  │                           │
│  └─────────────┘  └─────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

### 数据流

```
SM文件 → parse_sm_file() → SmChartInfo + SmNotesBlock
                                    │
                                    ▼
                    parse_sm_arrow_events() → event_table
                                    │
                                    ▼
                    build_arrow_events() → List[ArrowEvent]
                                    │
                                    ▼
                            渲染循环 (main_loop)
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              输入处理         时间更新         画面渲染
           (按键判定)      (箭头位置计算)   (皮肤+动画绘制)
```

### SM 文件解析

SM 文件解析流程：

1. **解析头部信息**: `#TITLE`, `#OFFSET`, `#BPMS` 等标签
2. **解析 NOTES 区块**: 获取小节数据
3. **符号解析**:
   - `0` = 空
   - `1` = 点按 (tap)
   - `2`/`4` = 长按开始 (hold start)
   - `3` = 长按结束 (hold end)
4. **时间转换**: 将 beat 位置转换为秒数

### 皮肤系统

皮肤文件命名规范：

```
{Direction} {Type} (doubleres) {Grid}.png

Direction: DownLeft | UpLeft | Center | UpRight | DownRight
Type:      Tap Note | Hold Body | Hold BottomCap | Ready Receptor
Grid:      3x2 | 6x1 | 1x3 (列x行)
```

皮肤加载优先级：
1. 直接加载对应方向
2. 右侧轨道自动翻转左侧轨道图片（UpRight 翻转 UpLeft）

### 判定系统

```
判定窗口:
  PERFECT: ±45ms
  GOOD:    ±90ms
  BAD:     ±135ms
  MISS:    >135ms
```

## 文件格式支持

### SM 文件格式

```sm
#TITLE:歌曲名称;
#OFFSET:-0.023;
#BPMS:0.000=150.000;
#NOTES:
dance-single:
:
Beginner:
3:
0.000,0.000,0.000,0.000,0.000:
0000
1000
0000
0000
;
```

### 封面图片

程序自动查找以下文件名作为封面背景：
- `bn.jpg`, `BN.jpg`
- `banner.jpg`, `Banner.jpg`
- `bn.png`, `bann.jpg`

## 扩展开发

### 添加新功能建议

1. **连击音效**: 在 `_try_judge_arrow()` 中添加音效播放
2. **谱面难度选择**: 解析多个 `#NOTES` 区块，添加选择界面
3. **回放功能**: 记录按键时间，支持回放
4. **分数系统**: 扩展判定权重，计算最终得分

### 自定义皮肤

1. 将皮肤文件放入 `noteskin/` 目录
2. 确保 PNG 格式，支持透明通道
3. 命名遵循 `{Direction} {Type} (doubleres) {Grid}.png` 格式

## 已知问题

- 部分 SM 文件的 BPM 变化可能解析不正确，可按 `T` 键切换 tick 设置
- 长按判定目前简化为点按处理，后续可扩展

## 依赖说明

| 库 | 用途 |
|---|------|
| pygame | 游戏引擎、渲染、音频播放 |
| customtkinter | 启动界面 UI |
| tkinterdnd2 | 拖拽文件支持（可选） |

## 许可证

MIT License

## 致谢

- StepMania 社区的 NoteSkin 格式
- E5 皮肤资源
