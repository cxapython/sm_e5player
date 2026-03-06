//! 音频管理器
//!
//! 简化版音频管理器，避免跨线程问题

use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicI32, Ordering};
use std::sync::Arc;

/// 音频状态
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum AudioState {
    Stopped,
    Playing,
    Paused,
}

/// 音频管理器（简化版，仅维护状态）
/// 实际音频播放在前端通过Web Audio API实现
pub struct AudioManager {
    state: Arc<AtomicI32>,
    volume: Arc<AtomicI32>, // 存储为整数 (0-100)
    current_file: std::sync::Mutex<Option<String>>,
}

impl Default for AudioManager {
    fn default() -> Self {
        Self::new()
    }
}

impl AudioManager {
    /// 创建新的音频管理器
    pub fn new() -> Self {
        Self {
            state: Arc::new(AtomicI32::new(AudioState::Stopped as i32)),
            volume: Arc::new(AtomicI32::new(80)),
            current_file: std::sync::Mutex::new(None),
        }
    }

    /// 设置当前文件
    pub fn set_current_file(&self, path: Option<String>) {
        if let Ok(mut file) = self.current_file.lock() {
            *file = path;
        }
    }

    /// 获取当前文件
    pub fn get_current_file(&self) -> Option<String> {
        if let Ok(file) = self.current_file.lock() {
            file.clone()
        } else {
            None
        }
    }

    /// 设置状态
    pub fn set_state(&self, state: AudioState) {
        self.state.store(state as i32, Ordering::SeqCst);
    }

    /// 获取状态
    pub fn get_state(&self) -> AudioState {
        match self.state.load(Ordering::SeqCst) {
            0 => AudioState::Stopped,
            1 => AudioState::Playing,
            2 => AudioState::Paused,
            _ => AudioState::Stopped,
        }
    }

    /// 设置音量
    ///
    /// # Arguments
    /// * `volume` - 音量 (0.0-1.0)
    pub fn set_volume(&self, volume: f32) {
        self.volume.store((volume * 100.0) as i32, Ordering::SeqCst);
    }

    /// 获取音量
    pub fn get_volume(&self) -> f32 {
        self.volume.load(Ordering::SeqCst) as f32 / 100.0
    }

    /// 播放（标记状态）
    pub fn play(&self) {
        self.set_state(AudioState::Playing);
    }

    /// 暂停（标记状态）
    pub fn pause(&self) {
        self.set_state(AudioState::Paused);
    }

    /// 停止（标记状态）
    pub fn stop(&self) {
        self.set_state(AudioState::Stopped);
        self.set_current_file(None);
    }

    /// 是否正在播放
    pub fn is_playing(&self) -> bool {
        self.get_state() == AudioState::Playing
    }

    /// 是否已暂停
    pub fn is_paused(&self) -> bool {
        self.get_state() == AudioState::Paused
    }
}

// 确保可以安全跨线程
unsafe impl Send for AudioManager {}
unsafe impl Sync for AudioManager {}
