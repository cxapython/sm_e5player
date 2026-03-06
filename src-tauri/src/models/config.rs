//! 应用配置数据模型

use serde::{Deserialize, Serialize};
use std::path::PathBuf;

/// 应用配置
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    // === 路径配置 ===
    /// 歌曲扫描路径
    pub scan_path: Option<String>,
    /// 上次播放的歌曲路径
    pub last_played: Option<String>,
    /// 上次播放的SM文件
    pub last_sm_file: Option<String>,
    /// 上次的页码
    pub last_page: usize,

    // === 窗口配置 ===
    /// 窗口宽度
    pub window_width: u32,
    /// 窗口高度
    pub window_height: u32,
    /// 是否全屏
    pub fullscreen: bool,
    /// 帧率
    pub fps: u32,

    // === 音频配置 ===
    /// 主音量 (0.0-1.0)
    pub master_volume: f32,
    /// 音乐音量 (0.0-1.0)
    pub music_volume: f32,
    /// 音效音量 (0.0-1.0)
    pub sfx_volume: f32,
    /// 预览时长（秒）
    pub preview_duration: f64,
    /// 悬停预览延迟（秒）
    pub preview_delay: f64,

    // === 游戏配置 ===
    /// 滚动速度（像素/秒）
    pub scroll_speed: f64,
    /// 音频偏移（秒）
    pub offset: f64,
    /// 每拍tick数
    pub tick_per_beat: u32,

    // === 判定配置 ===
    /// PERFECT窗口（秒）
    pub perfect_window: f64,
    /// GOOD窗口（秒）
    pub good_window: f64,
    /// BAD窗口（秒）
    pub bad_window: f64,

    // === UI配置 ===
    /// 玻璃主题
    pub glass_theme: String,
    /// 是否启用频谱可视化
    pub spectrum_enabled: bool,
    /// 频谱条数
    pub spectrum_bars: usize,
    /// 大屏卡片列数
    pub card_columns_large: usize,
    /// 小屏卡片列数
    pub card_columns_small: usize,
    /// 大屏卡片行数
    pub card_rows_large: usize,
    /// 小屏卡片行数
    pub card_rows_small: usize,
    /// 大屏阈值（像素）
    pub large_screen_threshold: u32,

    // === 星级筛选 ===
    /// 最小星级
    pub star_filter_min: Option<u8>,
    /// 最大星级
    pub star_filter_max: Option<u8>,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            scan_path: None,
            last_played: None,
            last_sm_file: None,
            last_page: 0,

            window_width: 1280,
            window_height: 720,
            fullscreen: false,
            fps: 60,

            master_volume: 0.8,
            music_volume: 1.0,
            sfx_volume: 0.8,
            preview_duration: 10.0,
            preview_delay: 0.5,

            scroll_speed: 840.0,
            offset: 0.0,
            tick_per_beat: 96,

            perfect_window: 0.045,
            good_window: 0.090,
            bad_window: 0.135,

            glass_theme: "dark".to_string(),
            spectrum_enabled: true,
            spectrum_bars: 32,
            card_columns_large: 4,
            card_columns_small: 3,
            card_rows_large: 2,
            card_rows_small: 3,
            large_screen_threshold: 1920,

            star_filter_min: None,
            star_filter_max: None,
        }
    }
}

impl AppConfig {
    /// 获取配置文件路径
    pub fn config_path() -> PathBuf {
        let mut path = dirs::config_dir().unwrap_or_else(|| PathBuf::from("."));
        path.push("sm-arrow-player");
        path.push("config.json");
        path
    }

    /// 从文件加载配置
    pub fn load() -> Self {
        let path = Self::config_path();
        if path.exists() {
            match std::fs::read_to_string(&path) {
                Ok(content) => {
                    match serde_json::from_str(&content) {
                        Ok(config) => return config,
                        Err(e) => {
                            eprintln!("[Config] 配置文件解析失败: {}, 使用默认配置", e);
                        }
                    }
                }
                Err(e) => {
                    eprintln!("[Config] 读取配置文件失败: {}, 使用默认配置", e);
                }
            }
        }
        Self::default()
    }

    /// 保存配置到文件
    pub fn save(&self) -> Result<(), String> {
        let path = Self::config_path();

        // 确保目录存在
        if let Some(parent) = path.parent() {
            if !parent.exists() {
                std::fs::create_dir_all(parent)
                    .map_err(|e| format!("创建配置目录失败: {}", e))?;
            }
        }

        let content = serde_json::to_string_pretty(self)
            .map_err(|e| format!("序列化配置失败: {}", e))?;

        std::fs::write(&path, content)
            .map_err(|e| format!("写入配置文件失败: {}", e))?;

        Ok(())
    }

    /// 获取卡片布局
    pub fn get_card_layout(&self, window_width: u32) -> (usize, usize) {
        if window_width >= self.large_screen_threshold {
            (self.card_columns_large, self.card_rows_large)
        } else {
            (self.card_columns_small, self.card_rows_small)
        }
    }

    /// 是否首次运行
    pub fn is_first_run(&self) -> bool {
        match &self.scan_path {
            Some(path) => !std::path::Path::new(path).is_dir(),
            None => true,
        }
    }
}
