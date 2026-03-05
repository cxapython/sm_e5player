# SM Arrow Player

一个基于 Python + Pygame 的 StepMania 谱面可视化播放器，支持直接播放 `.sm` 格式谱面文件。

## 功能特性

- **歌曲浏览器界面**: 相册式左右滑动浏览，每页显示8首歌曲
- **悬浮音频预览**: 鼠标悬停自动播放歌曲预览
- **封面图片展示**: 自动加载 bn.jpg/banner.jpg 等封面图片
- **星级显示**: 解析目录名中的星级信息（格式：`前缀#歌名#星级`）
- **路径记忆**: 首次指定扫描路径后自动保存，后续启动自动加载
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
- 依赖库：`pygame`, `customtkinter`, `Pillow`

### 安装依赖

```bash
pip install pygame customtkinter Pillow

# 可选：支持拖拽功能
pip install tkinterdnd2
```

### 运行

```bash
python main.py
```

或使用歌曲选择界面：

```bash
python main.py
```

直接播放单个谱面文件：

```bash
python sm_arrow_player.py
```

### 使用方法

1. 启动程序后，首次运行会提示选择歌曲目录
2. 在歌曲浏览器中，鼠标悬停可预览音频，点击封面可进入谱面播放
3. 使用左右按钮或键盘左右键切换页面
4. 播放器中按空格键开始/暂停播放

## 快捷键

### 歌曲浏览器

| 按键 | 功能 |
|------|------|
| `←` / `→` | 上一页/下一页 |
| 鼠标悬停 | 预览音频 |
| 点击封面 | 进入谱面播放 |

### 谱面播放器

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
├── main.py                  # 主程序入口（歌曲浏览器）
├── config_manager.py        # 配置管理模块
├── directory_parser.py      # 目录/资源解析模块
├── song_scanner.py          # 歌曲扫描模块
├── ui_components.py         # UI组件模块
├── audio_player.py          # 音频预览模块
├── sm_arrow_player.py       # 谱面播放器核心
├── config.json              # 配置文件（自动生成）
├── noteskin/                # 皮肤资源目录
│   ├── Center Tap Note (doubleres) 3x2.png
│   ├── Center Hold Body active (doubleres) 6x1.png
│   ├── Center Hold BottomCap active (doubleres) 6x1.png
│   ├── Center Ready Receptor (doubleres) 1x3.png
│   ├── UpLeft ...           # 左上轨道皮肤
│   ├── UpRight ...          # 右上轨道皮肤
│   ├── DownLeft ...         # 左下轨道皮肤
│   ├── DownRight ...        # 右下轨道皮肤
│   └── metrics.ini          # 皮肤配置（可选）
├── songs/                   # 谱面目录
│   └── [歌曲名]/
│       ├── *.sm             # 谱面文件
│       ├── *.mp3/ogg/wav    # 音频文件
│       └── bn.jpg           # 封面图片（可选）
└── README.md
```

## 模块说明

| 模块 | 职责 |
|------|------|
| `main.py` | 程序入口，整合所有模块，实现歌曲浏览和播放功能 |
| `config_manager.py` | 配置文件读写，保存路径、音量、页码等设置 |
| `directory_parser.py` | 解析目录名称、提取星级信息、查找资源文件 |
| `song_scanner.py` | 扫描指定目录下的所有歌曲文件夹 |
| `ui_components.py` | UI组件，包括歌曲卡片和浏览器主界面 |
| `audio_player.py` | 音频预览播放，支持悬停延迟播放 |
| `sm_arrow_player.py` | 谱面播放器核心，解析SM文件并渲染游戏画面 |

## 架构说明

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      SMPlayerApp (主应用)                     │
│  - 首次运行路径选择                                            │
│  - 歌曲浏览器界面                                              │
│  - 播放器启动                                                  │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
     ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
     │ConfigManager│  │ SongScanner │  │AudioPreview │
     │  配置管理    │  │  歌曲扫描    │  │  音频预览   │
     └─────────────┘  └─────────────┘  └─────────────┘
                              │
                              ▼
                     ┌─────────────┐
                     │ SongBrowser │
                     │  歌曲浏览器  │
                     │  (UI组件)   │
                     └─────────────┘
                              │
                              ▼
                     ┌─────────────┐
                     │ ArrowPlayer │
                     │  谱面播放器  │
                     └─────────────┘
```

### 谱面播放器核心类

```
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

### 目录命名规范

歌曲目录名支持 `#` 分隔格式，用于显示星级：

```
SPEED_DEVIL#PLAY_js_2106#8
     ↑           ↑        ↑
   前缀        歌名     星级

显示效果：PLAY_js_2106  ★☆☆☆☆ 8
```

无 `#` 分隔的目录名则直接显示，不显示星级。

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
| customtkinter | 歌曲浏览器 UI |
| Pillow | 封面图片处理 |
| tkinterdnd2 | 拖拽文件支持（可选） |

## 许可证

MIT License

## 致谢

- StepMania 社区的 NoteSkin 格式
- E5 皮肤资源
