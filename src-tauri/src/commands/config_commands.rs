//! 配置相关命令

use crate::config::ConfigManager;
use crate::models::AppConfig;
use std::sync::Mutex;
use tauri::State;

/// 获取应用配置
#[tauri::command]
pub fn get_config(config: State<Mutex<ConfigManager>>) -> Result<AppConfig, String> {
    let manager = config.lock().map_err(|e| e.to_string())?;
    Ok(manager.get_config().clone())
}

/// 保存应用配置
#[tauri::command]
pub fn save_config(
    config: State<Mutex<ConfigManager>>,
    new_config: AppConfig,
) -> Result<(), String> {
    let mut manager = config.lock().map_err(|e| e.to_string())?;
    *manager.get_config_mut() = new_config;
    manager.save()
}

/// 设置扫描路径
#[tauri::command]
pub fn set_scan_path(
    config: State<Mutex<ConfigManager>>,
    path: String,
) -> Result<(), String> {
    let mut manager = config.lock().map_err(|e| e.to_string())?;
    manager.set_scan_path(path)
}

/// 重置配置
#[tauri::command]
pub fn reset_config(config: State<Mutex<ConfigManager>>) -> Result<(), String> {
    let mut manager = config.lock().map_err(|e| e.to_string())?;
    manager.reset();
    manager.save()
}
