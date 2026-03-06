//! 歌曲相关命令

use crate::scanner::SongScanner;
use crate::models::{SongInfo, ScanResult};
use tauri::State;
use std::sync::Mutex;

/// 全局歌曲扫描器状态
pub struct ScannerState {
    pub scanner: Mutex<SongScanner>,
}

/// 扫描歌曲目录
#[tauri::command]
pub async fn scan_songs(path: String) -> Result<ScanResult, String> {
    // 在后台线程中执行扫描
    tokio::task::spawn_blocking(move || {
        let mut scanner = SongScanner::new();
        scanner.scan(&path)
    })
    .await
    .map_err(|e| e.to_string())?
}

/// 获取歌曲数量
#[tauri::command]
pub fn get_song_count(scanner: State<'_, ScannerState>) -> Result<usize, String> {
    let state = scanner.scanner.lock().map_err(|e| e.to_string())?;
    Ok(state.count())
}

/// 搜索歌曲
#[tauri::command]
pub fn search_songs(
    keyword: String,
    scanner: State<'_, ScannerState>,
) -> Result<Vec<SongInfo>, String> {
    let state = scanner.scanner.lock().map_err(|e| e.to_string())?;
    let results = state.search(&keyword);
    Ok(results.into_iter().cloned().collect())
}

/// 按星级筛选歌曲
#[tauri::command]
pub fn filter_by_star(
    min: Option<u8>,
    max: Option<u8>,
    scanner: State<'_, ScannerState>,
) -> Result<Vec<SongInfo>, String> {
    let state = scanner.scanner.lock().map_err(|e| e.to_string())?;
    let results = state.filter_by_star(min, max);
    Ok(results.into_iter().cloned().collect())
}
