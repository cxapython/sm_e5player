//! 配置管理器
//!
//! 负责应用程序配置的读取、保存和管理

use crate::models::AppConfig;

/// 配置管理器
pub struct ConfigManager {
    config: AppConfig,
}

impl ConfigManager {
    /// 创建新的配置管理器
    pub fn new() -> Self {
        Self {
            config: AppConfig::load(),
        }
    }

    /// 获取配置
    pub fn get_config(&self) -> &AppConfig {
        &self.config
    }

    /// 获取可变配置
    pub fn get_config_mut(&mut self) -> &mut AppConfig {
        &mut self.config
    }

    /// 保存配置
    pub fn save(&self) -> Result<(), String> {
        self.config.save()
    }

    /// 重置为默认配置
    pub fn reset(&mut self) {
        self.config = AppConfig::default();
    }

    /// 获取扫描路径
    pub fn get_scan_path(&self) -> Option<&str> {
        self.config.scan_path.as_deref()
    }

    /// 设置扫描路径
    pub fn set_scan_path(&mut self, path: String) -> Result<(), String> {
        let p = std::path::Path::new(&path);
        if !p.is_dir() {
            return Err(format!("路径不存在或不是目录: {}", path));
        }
        self.config.scan_path = Some(std::fs::canonicalize(p)
            .map_err(|e| format!("规范化路径失败: {}", e))?
            .to_string_lossy()
            .to_string());
        self.save()
    }

    /// 获取窗口大小
    pub fn get_window_size(&self) -> (u32, u32) {
        (self.config.window_width, self.config.window_height)
    }

    /// 设置窗口大小
    pub fn set_window_size(&mut self, width: u32, height: u32) -> Result<(), String> {
        self.config.window_width = width.max(800);
        self.config.window_height = height.max(600);
        self.save()
    }

    /// 获取音量
    pub fn get_volume(&self) -> f32 {
        self.config.master_volume
    }

    /// 设置音量
    pub fn set_volume(&mut self, volume: f32) -> Result<(), String> {
        self.config.master_volume = volume.clamp(0.0, 1.0);
        self.save()
    }

    /// 获取滚动速度
    pub fn get_scroll_speed(&self) -> f64 {
        self.config.scroll_speed
    }

    /// 设置滚动速度
    pub fn set_scroll_speed(&mut self, speed: f64) -> Result<(), String> {
        self.config.scroll_speed = speed.clamp(200.0, 2000.0);
        self.save()
    }

    /// 是否首次运行
    pub fn is_first_run(&self) -> bool {
        self.config.is_first_run()
    }
}

impl Default for ConfigManager {
    fn default() -> Self {
        Self::new()
    }
}
