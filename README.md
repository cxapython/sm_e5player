# SM Arrow Player

一款基于 **Rust + Tauri 2.x + Svelte 5** 构建的现代音乐节奏游戏播放器，采用 iPhone 17 风格的玻璃拟态 UI 设计。

## 技术架构

### 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 后端核心 | Rust | 1.70+ |
| 桌面框架 | Tauri | 2.x |
| 前端框架 | Svelte | 5.x |
| UI 样式 | TailwindCSS | 3.x |
| 动画库 | GSAP | 3.x |
| 构建工具 | Vite | 6.x |

### 项目结构

```
sm_e5player/
├── old/                    # 旧版 Python 代码 (已废弃)
│   ├── main.py
│   ├── sm_parser.py
│   ├── audio_manager.py
│   └── ...
├── songs/                  # 歌曲目录 (SM 谱面文件)
├── noteskin/               # 皮肤资源 (箭头贴图等)
├── src/                    # Svelte 前端源码
│   ├── lib/
│   │   ├── components/     # UI 组件
│   │   │   └── glass/      # 玻璃拟态组件
│   │   │       ├── GlassCard.svelte
│   │   │       ├── GlassButton.svelte
│   │   │       ├── GlassSearch.svelte
│   │   │       ├── StarRating.svelte
│   │   │       └── SpectrumBar.svelte
│   │   ├── stores/         # Svelte Stores (状态管理)
│   │   │   ├── config.ts   # 配置状态
│   │   │   ├── songs.ts    # 歌曲状态
│   │   │   ├── player.ts   # 播放器状态
│   │   │   └── types.ts    # 类型定义
│   │   ├── utils/          # 工具函数
│   │   │   └── noteskin.ts # Noteskin 加载和渲染
│   │   └── views/          # 页面视图
│   │       ├── SongSelectView.svelte  # 选歌界面
│   │       └── PlayerView.svelte      # 游戏界面
│   ├── app.css             # 全局样式
│   ├── App.svelte          # 根组件
│   └── main.ts             # 入口文件
├── src-tauri/              # Rust 后端源码
│   ├── src/
│   │   ├── models/         # 数据模型
│   │   │   ├── song.rs     # 歌曲信息
│   │   │   ├── chart.rs    # 谱面数据
│   │   │   ├── config.rs   # 配置结构
│   │   │   └── timeline.rs # 时间轴
│   │   ├── parser/         # 解析器模块
│   │   │   ├── sm_parser.rs   # SM 文件解析
│   │   │   └── timeline.rs    # BPM 时间轴计算
│   │   ├── scanner/        # 文件扫描
│   │   │   └── song_scanner.rs
│   │   ├── audio/          # 音频管理
│   │   │   └── audio_manager.rs
│   │   ├── judge/          # 判定系统
│   │   │   └── judge_system.rs
│   │   ├── commands/       # Tauri 命令
│   │   │   ├── config_commands.rs
│   │   │   ├── song_commands.rs
│   │   │   ├── player_commands.rs
│   │   │   └── audio_commands.rs
│   │   ├── config/         # 配置管理
│   │   │   └── config_manager.rs
│   │   ├── utils/          # 工具函数
│   │   ├── lib.rs          # 库入口
│   │   └── main.rs         # 程序入口
│   ├── icons/              # 应用图标
│   ├── Cargo.toml          # Rust 依赖
│   └── tauri.conf.json     # Tauri 配置
├── package.json            # npm 依赖
├── vite.config.ts          # Vite 配置
├── svelte.config.js        # Svelte 配置
├── tailwind.config.js      # Tailwind 配置
├── tsconfig.json           # TypeScript 配置
└── README.md
```

## 核心功能模块

### 1. SM 文件解析器 (`src-tauri/src/parser/sm_parser.rs`)

解析 StepMania 格式的谱面文件 (.sm)，支持：
- 歌曲元信息解析（标题、艺术家、BPM 等）
- 多难度谱面解析
- BPM 变化处理
- 箭头事件提取（点按、长按、滚动箭头）

### 2. 时间轴计算 (`src-tauri/src/parser/timeline.rs`)

处理 BPM 变化，计算：
- tick 与时间的相互转换
- 拍号与时间的对应关系
- 支持 BPM 渐变

### 3. 歌曲扫描器 (`src-tauri/src/scanner/song_scanner.rs`)

多线程异步扫描歌曲目录：
- 自动识别 SM 文件
- 智能匹配音频文件（支持 ogg, mp3, wav）
- 自动匹配封面图片
- 支持星级评分解析（从目录名提取）

### 4. 判定系统 (`src-tauri/src/judge/judge_system.rs`)

精确的判定逻辑：
- PERFECT: ±45ms
- GOOD: ±90ms
- BAD: ±135ms
- MISS: >135ms

### 5. 音频管理 (`src-tauri/src/audio/audio_manager.rs`)

简化的音频状态管理：
- 播放状态追踪
- 音量控制
- 实际音频播放由前端 Web Audio API 处理

### 6. 配置管理 (`src-tauri/src/config/config_manager.rs`)

持久化配置存储：
- 歌曲目录路径
- 音量设置
- 滚动速度
- UI 偏好设置

## 前端架构

### 状态管理 (Svelte Stores)

```typescript
// 歌曲状态
songsStore: {
  songs: SongInfo[],
  filteredSongs: SongInfo[],
  currentPage: number,
  isLoading: boolean,
  searchQuery: string
}

// 播放器状态
playerStore: {
  currentSong: SongInfo | null,
  chartData: ChartData | null,
  gameState: 'loading' | 'ready' | 'playing' | 'paused' | 'finished',
  currentTime: number,
  score: number,
  combo: number,
  stats: JudgeStats
}

// 配置状态
configStore: {
  scan_path: string | null,
  master_volume: number,
  scroll_speed: number,
  // ...
}
```

### UI 组件

采用玻璃拟态设计风格：
- `GlassCard` - 玻璃效果卡片
- `GlassButton` - 玻璃效果按钮
- `GlassSearch` - 搜索输入框
- `StarRating` - 星级评分显示
- `SpectrumBar` - 音频频谱可视化

## 快速开始

### 环境要求

- **Rust** 1.70+
- **Node.js** 18+
- **npm** 或 **pnpm**

### 安装依赖

```bash
# 安装前端依赖
npm install

# Rust 依赖会在构建时自动安装
```

### 开发模式

```bash
# 启动开发服务器
npm run tauri dev
```

### 构建发布

```bash
# 构建生产版本
npm run tauri build

# macOS 生成 DMG 安装包
# Windows 生成 MSI 安装包
# Linux 生成 AppImage/Deb 包
```

构建产物位于 `src-tauri/target/release/bundle/` 目录。

## 配置说明

### 应用配置 (`config.json`)

首次运行会在应用数据目录创建配置文件：

```json
{
  "scan_path": "/path/to/songs",
  "master_volume": 0.8,
  "scroll_speed": 840,
  "offset": 0,
  "star_filter_min": null,
  "star_filter_max": null,
  "card_columns_large": 4,
  "card_columns_small": 2
}
```

### 歌曲目录格式

支持标准 StepMania 歌曲目录结构：

```
songs/
├── SONG_FOLDER_NAME/
│   ├── song.sm          # SM 谱面文件
│   ├── song.ogg         # 音频文件
│   └── banner.png       # 封面图片
```

目录名支持星级格式：`PREFIX#SONG_NAME#STAR`

## 操作说明

### 选歌界面

- **鼠标点击** - 选择歌曲
- **鼠标悬停** - 预览音频
- **搜索框** - 输入关键词搜索
- **星级筛选** - 快速筛选不同难度
- **左右箭头** - 翻页

### 游戏界面

| 按键 | 功能 |
|------|------|
| Z | 左下轨道 (DownLeft) |
| Q | 左上轨道 (UpLeft) |
| S | 中间轨道 (Center) |
| W | 右上轨道 (UpRight) |
| C | 右下轨道 (DownRight) |
| 空格 | 暂停/继续 |
| R | 重新开始 |
| [ | 降低速度 |
| ] | 提高速度 |
| - | 减少 Offset |
| = | 增加 Offset |
| ← | 快退 5 秒 |
| → | 快进 5 秒 |
| Esc | 返回选歌 |

### Noteskin 皮肤

游戏支持自定义箭头皮肤，放置在 `noteskin/` 目录：

```
noteskin/
├── DownLeft Tap Note (doubleres) 3x2.png
├── DownLeft Hold Body active (doubleres) 6x1.png
├── DownLeft Hold BottomCap active (doubleres) 6x1.png
├── DownLeft Ready Receptor (doubleres) 1x3.png
├── UpLeft Tap Note (doubleres) 3x2.png
├── ... (UpLeft, Center 方向)
```

- **右侧箭头** (UpRight, DownRight) 自动通过水平翻转左侧图片实现
- 支持 3x2、6x1、1x3 等精灵图格式

## 性能优化

- **Rust 后端**：高性能 SM 解析和多线程文件扫描
- **Canvas 渲染**：60 FPS 流畅游戏体验
- **Web Audio API**：低延迟音频播放
- **虚拟列表**：大量歌曲时内存优化
- **懒加载**：按需加载谱面数据

## 开发指南

### 添加新的 Tauri 命令

1. 在 `src-tauri/src/commands/` 中定义命令函数：

```rust
#[tauri::command]
pub fn my_new_command(param: String) -> Result<MyResult, String> {
    // 实现
}
```

2. 在 `src-tauri/src/lib.rs` 中注册：

```rust
.invoke_handler(tauri::generate_handler![
    // ...
    commands::my_module::my_new_command,
])
```

### 添加新的前端组件

在 `src/lib/components/` 下创建 Svelte 组件，使用 Svelte 5 runes 语法：

```svelte
<script lang="ts">
  interface Props {
    title: string;
    onClick?: () => void;
  }

  let { title, onClick }: Props = $props();
  let count = $state(0);
</script>

<button onclick={onClick}>
  {title}: {count}
</button>
```

## 技术特点

1. **跨平台**：支持 macOS、Windows、Linux
2. **原生性能**：Rust 后端，低内存占用
3. **现代 UI**：玻璃拟态设计，流畅动画
4. **模块化**：清晰的前后端分离架构
5. **类型安全**：Rust + TypeScript 全栈类型系统

## 许可证

MIT License

## 致谢

- StepMania 社区 - SM 文件格式规范
- Tauri 团队 - 优秀的桌面应用框架
- Svelte 团队 - 响应式前端框架
