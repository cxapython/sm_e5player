# SM Arrow Player (PyQt6)

一款基于 **Python + PyQt6** 构建的 E舞成名（StepMania）谱面播放器，采用 iPhone 17 风格的玻璃拟态 UI 设计。

## 功能特性

- **谱面播放** - 支持 StepMania (.sm) 格式谱面
- **玻璃拟态 UI** - 现代化的视觉效果
- **5 轨道游戏** - 经典的 E 舞成名玩法
- **皮肤支持** - 可自定义箭头和判定区皮肤
- **精确判定** - PERFECT/GOOD/BAD/MISS 四级判定

## 技术架构

### 技术栈

| 组件 | 技术 |
|------|------|
| GUI 框架 | PyQt6 |
| 音频播放 | QMediaPlayer |
| 渲染引擎 | QPainter |
| 配置存储 | QSettings |

### 项目结构

```
sm_e5player/
├── main.py                 # 主程序入口
├── config_manager.py       # 配置管理
├── audio_manager.py        # 音频管理
├── song_scanner.py         # 歌曲扫描 (QThread)
├── directory_parser.py     # 目录解析
├── sm_parser.py            # SM 文件解析
├── skin_manager.py         # 皮肤管理
├── judge_system.py         # 判定系统
├── song_select_window.py   # 选歌界面
├── chart_play_window.py    # 谱面播放界面
├── glass_ui_components.py  # 玻璃 UI 组件
├── advanced_glass.py       # 高级玻璃效果
├── songs/                  # 歌曲目录
├── noteskin/               # 皮肤资源
└── old/                    # 旧版代码备份
```

## 快速开始

### 环境要求

- **Python** 3.9+
- **PyQt6**
- **PyQt6-Multimedia**

### 安装依赖

```bash
pip install PyQt6 PyQt6-Multimedia
```

### 运行程序

```bash
python3 main.py
```

首次运行会提示选择歌曲目录。

## 操作说明

### 选歌界面

| 操作 | 功能 |
|------|------|
| 鼠标悬停 | 预览音频 |
| 鼠标点击 | 选择歌曲 |
| 搜索框 | 搜索歌曲 |
| 星级筛选 | 筛选难度 |
| 左右箭头 | 翻页 |
| F11 | 全屏切换 |

### 游戏界面

| 按键 | 功能 |
|------|------|
| **Z** | 左下轨道 (DownLeft) |
| **Q** | 左上轨道 (UpLeft) |
| **S** | 中间轨道 (Center) |
| **E** | 右上轨道 (UpRight) |
| **C** | 右下轨道 (DownRight) |
| **空格** | 开始/暂停 |
| **ESC** | 暂停菜单/返回 |
| **R** | 重新开始 |
| **[** / **]** | 调整滚动速度 |
| **+** / **-** | 调整箭头大小 |
| **,** / **.** | 调整箭头间距 |

## 判定系统

| 判定 | 时间窗口 | 分数 |
|------|----------|------|
| PERFECT | ±45ms | 100 |
| GOOD | ±90ms | 50 |
| BAD | ±135ms | 10 |
| MISS | >135ms | 0 |

10 连击以上有 10% 分数加成。

## 歌曲目录格式

支持标准 StepMania 歌曲目录结构：

```
songs/
├── SONG_FOLDER/
│   ├── song.sm          # SM 谱面文件
│   ├── song.ogg         # 音频文件 (ogg/mp3/wav)
│   └── banner.png       # 封面图片
```

目录名支持星级格式：`PREFIX#SONG_NAME#STAR`

例如：`SPEED_DEVIL#Song_Name#10`

## 皮肤格式

皮肤文件放置在 `noteskin/` 目录：

```
noteskin/
├── DownLeft Tap Note (doubleres) 3x2.png      # 点按箭头
├── DownLeft Hold Body active (doubleres) 6x1.png   # 长按箭身
├── DownLeft Hold BottomCap active (doubleres) 6x1.png  # 长按箭尾
├── DownLeft Ready Receptor (doubleres) 1x3.png  # 判定区
├── UpLeft Tap Note (doubleres) 3x2.png
├── Center Tap Note (doubleres) 3x2.png
├── ...
```

### 皮肤命名规则

- **方向**: DownLeft, UpLeft, Center, UpRight, DownRight
- **类型**: Tap Note, Hold Body, Hold BottomCap, Ready Receptor
- **网格**: 3x2 (3列2行), 6x1 (6列1行), 1x3 (1列3行)

**右侧箭头** (UpRight, DownRight) 会自动从左侧箭头水平翻转生成。

## 配置文件

配置存储在 `config.json`：

```json
{
  "scan_path": "/path/to/songs",
  "master_volume": 0.8,
  "scroll_speed": 840,
  "tick_per_beat": 48,
  "last_sm_file": null,
  "last_page": 0
}
```

## 核心模块说明

### SM 解析器 (`sm_parser.py`)

- 解析 #TITLE, #ARTIST, #OFFSET, #BPMS 等标签
- 提取 NOTES 区块的箭头数据
- 支持 BPM 变化时间轴计算

### 判定系统 (`judge_system.py`)

- `JudgeSystem` - 判定逻辑和分数计算
- `JudgeDisplay` - 判定结果显示
- `JudgeLight` - 判定区光效
- `HitEffect` - 命中动画效果

### 皮肤管理 (`skin_manager.py`)

- 自动检测皮肤根目录
- 精灵图自动裁剪
- 右侧箭头自动镜像

### 音频管理 (`audio_manager.py`)

- QMediaPlayer 音频播放
- 音乐播放和预览播放分离
- 音量控制

## 开发说明

### 代码风格

- 使用类型注解 (type hints)
- 遵循 PEP 8 规范
- 文档字符串使用中文

### 添加新功能

1. 在相应模块中添加功能代码
2. 更新相关的 UI 组件
3. 测试所有交互功能

## 许可证

MIT License

## 致谢

- StepMania 社区 - SM 文件格式规范
- PyQt6 团队 - 优秀的 GUI 框架
