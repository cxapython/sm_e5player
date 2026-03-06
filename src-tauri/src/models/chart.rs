//! 谱面数据模型

use serde::{Deserialize, Serialize};

/// 谱面基本信息
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChartInfo {
    /// 标题
    pub title: String,
    /// 副标题
    pub subtitle: String,
    /// 艺术家
    pub artist: String,
    /// 音频偏移（秒）
    pub offset: f64,
    /// BPM列表 (beat, bpm)
    pub bpm_list: Vec<(f64, f64)>,
    /// 显示BPM
    pub display_bpm: String,
    /// 列数（5或10）
    pub column_count: usize,
    /// 难度描述
    pub difficulty: String,
}

impl Default for ChartInfo {
    fn default() -> Self {
        Self {
            title: String::new(),
            subtitle: String::new(),
            artist: String::new(),
            offset: 0.0,
            bpm_list: vec![(0.0, 120.0)],
            display_bpm: "120".to_string(),
            column_count: 5,
            difficulty: String::new(),
        }
    }
}

/// 箭头事件
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ArrowEvent {
    /// 轨道索引 (0-4: 左下, 左上, 中间, 右上, 右下)
    pub track_idx: u8,
    /// 开始时间（秒）
    pub start_sec: f64,
    /// 结束时间（秒），点按箭头等于开始时间
    pub end_sec: f64,
    /// 箭头类型 (0: 点按, 1: 长按头, 2: 长按身, 3: 长按尾)
    pub arrow_type: u8,
}

impl ArrowEvent {
    /// 是否为点按箭头
    pub fn is_tap(&self) -> bool {
        (self.end_sec - self.start_sec).abs() < 1e-6
    }

    /// 是否为长按箭头
    pub fn is_hold(&self) -> bool {
        !self.is_tap()
    }

    /// 长按时长（秒）
    pub fn hold_duration(&self) -> f64 {
        self.end_sec - self.start_sec
    }
}

/// 时间轴段
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimelineSegment {
    /// 开始拍
    pub start_beat: f64,
    /// 结束拍
    pub end_beat: f64,
    /// 开始时间（秒）
    pub start_sec: f64,
    /// 结束时间（秒）
    pub end_sec: f64,
    /// BPM
    pub bpm: f64,
}

/// 完整谱面数据
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChartData {
    /// 谱面信息
    pub info: ChartInfo,
    /// 箭头事件列表（按时间排序）
    pub arrows: Vec<ArrowEvent>,
    /// 总时长（秒）
    pub total_duration: f64,
    /// 箭头总数
    pub total_notes: usize,
}

impl Default for ChartData {
    fn default() -> Self {
        Self {
            info: ChartInfo::default(),
            arrows: Vec::new(),
            total_duration: 0.0,
            total_notes: 0,
        }
    }
}
