//! 播放器相关命令

use crate::parser::SmParser;
use crate::models::{ChartInfo, ChartData};

/// 加载谱面数据
#[tauri::command]
pub async fn load_chart(sm_path: String) -> Result<ChartData, String> {
    // 在后台线程中执行解析
    tokio::task::spawn_blocking(move || {
        let parser = SmParser::new();
        let (_, chart_data) = parser.parse_file(&sm_path)?;
        Ok(chart_data)
    })
    .await
    .map_err(|e| e.to_string())?
}

/// 获取谱面信息（不包含箭头数据，用于快速预览）
#[tauri::command]
pub async fn get_chart_info(sm_path: String) -> Result<ChartInfo, String> {
    tokio::task::spawn_blocking(move || {
        let parser = SmParser::new();
        let (info, _) = parser.parse_file(&sm_path)?;
        Ok(info)
    })
    .await
    .map_err(|e| e.to_string())?
}
