//! 音频相关命令
//!
//! 注意：实际音频播放通过前端Web Audio API实现
//! 后端仅管理状态和文件路径

use crate::audio::{AudioManager, AudioState};
use std::sync::Mutex;
use tauri::State;

/// 播放音频（设置状态）
#[tauri::command]
pub fn play_audio(
    path: String,
    audio: State<Mutex<AudioManager>>,
) -> Result<(), String> {
    let manager = audio.lock().map_err(|e| e.to_string())?;
    manager.set_current_file(Some(path));
    manager.play();
    Ok(())
}

/// 暂停音频
#[tauri::command]
pub fn pause_audio(audio: State<Mutex<AudioManager>>) -> Result<(), String> {
    let manager = audio.lock().map_err(|e| e.to_string())?;
    manager.pause();
    Ok(())
}

/// 恢复播放
#[tauri::command]
pub fn resume_audio(audio: State<Mutex<AudioManager>>) -> Result<(), String> {
    let manager = audio.lock().map_err(|e| e.to_string())?;
    manager.play();
    Ok(())
}

/// 停止音频
#[tauri::command]
pub fn stop_audio(audio: State<Mutex<AudioManager>>) -> Result<(), String> {
    let manager = audio.lock().map_err(|e| e.to_string())?;
    manager.stop();
    Ok(())
}

/// 设置音量
#[tauri::command]
pub fn set_volume(
    volume: f32,
    audio: State<Mutex<AudioManager>>,
) -> Result<(), String> {
    let manager = audio.lock().map_err(|e| e.to_string())?;
    manager.set_volume(volume);
    Ok(())
}

/// 获取音频状态
#[tauri::command]
pub fn get_audio_state(audio: State<Mutex<AudioManager>>) -> Result<String, String> {
    let manager = audio.lock().map_err(|e| e.to_string())?;
    let state = manager.get_state();
    Ok(match state {
        AudioState::Stopped => "stopped",
        AudioState::Playing => "playing",
        AudioState::Paused => "paused",
    }.to_string())
}

/// 获取当前音量
#[tauri::command]
pub fn get_volume(audio: State<Mutex<AudioManager>>) -> Result<f32, String> {
    let manager = audio.lock().map_err(|e| e.to_string())?;
    Ok(manager.get_volume())
}

/// 获取音频位置（简化版返回0）
#[tauri::command]
pub fn get_audio_position(_audio: State<Mutex<AudioManager>>) -> Result<f64, String> {
    // 实际位置由前端维护
    Ok(0.0)
}

/// 设置音频位置（简化版不做处理）
#[tauri::command]
pub fn set_audio_position(
    _position: f64,
    _audio: State<Mutex<AudioManager>>,
) -> Result<(), String> {
    // 实际位置由前端维护
    Ok(())
}
