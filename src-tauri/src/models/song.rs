//! 歌曲信息数据模型

use serde::{Deserialize, Serialize};

/// 歌曲信息
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SongInfo {
    /// 目录完整路径
    pub folder_path: String,
    /// 原始目录名
    pub folder_name: String,
    /// 显示名称（解析后）
    pub display_name: String,
    /// 星级（1-20），无则为None
    pub star_rating: Option<u8>,
    /// SM文件路径
    pub sm_file: Option<String>,
    /// 音频文件路径
    pub audio_file: Option<String>,
    /// 封面图片路径
    pub banner_file: Option<String>,
}

impl SongInfo {
    /// 是否有谱面文件
    pub fn has_sm(&self) -> bool {
        self.sm_file.is_some()
    }

    /// 是否有音频文件
    pub fn has_audio(&self) -> bool {
        self.audio_file.is_some()
    }

    /// 是否有封面图片
    pub fn has_banner(&self) -> bool {
        self.banner_file.is_some()
    }

    /// 星级显示文本
    pub fn star_display(&self) -> String {
        match self.star_rating {
            Some(star) => format!("★{}", star),
            None => String::new(),
        }
    }
}

/// 歌曲扫描进度
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScanProgress {
    /// 当前扫描的目录
    pub current_path: String,
    /// 已扫描数量
    pub scanned: usize,
    /// 已找到的歌曲数量
    pub found: usize,
    /// 是否完成
    pub is_complete: bool,
}

/// 歌曲扫描结果
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScanResult {
    /// 找到的歌曲列表
    pub songs: Vec<SongInfo>,
    /// 总扫描数量
    pub total_scanned: usize,
    /// 扫描耗时（毫秒）
    pub elapsed_ms: u64,
    /// 错误信息
    pub errors: Vec<String>,
}
