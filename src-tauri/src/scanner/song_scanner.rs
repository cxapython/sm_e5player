//! 歌曲扫描器
//!
//! 多线程异步扫描歌曲目录

use crate::models::{SongInfo, ScanResult};
use std::path::Path;
use std::fs;
use walkdir::WalkDir;
use std::time::Instant;

/// 支持的音频格式（按优先级排序）
const AUDIO_EXTENSIONS: &[&str] = &["ogg", "mp3", "wav"];

/// 支持的封面文件名
const BANNER_NAMES: &[&str] = &[
    "bn.jpg", "banner.jpg", "bn.png", "banner.png",
    "BN.jpg", "Banner.jpg", "BN.png", "Banner.png",
    "bann.jpg", "bann.png",
];

/// 歌曲扫描器
pub struct SongScanner {
    songs: Vec<SongInfo>,
}

impl Default for SongScanner {
    fn default() -> Self {
        Self::new()
    }
}

impl SongScanner {
    /// 创建新的歌曲扫描器
    pub fn new() -> Self {
        Self {
            songs: Vec::new(),
        }
    }

    /// 扫描歌曲目录
    ///
    /// # Arguments
    /// * `path` - 歌曲目录路径
    ///
    /// # Returns
    /// 扫描结果
    pub fn scan(&mut self, path: &str) -> Result<ScanResult, String> {
        let start_time = Instant::now();
        let mut songs = Vec::new();
        let mut errors = Vec::new();
        let mut scanned = 0;

        let root = Path::new(path);
        if !root.is_dir() {
            return Err(format!("路径不是目录: {}", path));
        }

        // 使用walkdir进行高效遍历，最多深度2层
        for entry in WalkDir::new(root)
            .max_depth(2)
            .into_iter()
            .filter_map(|e| e.ok())
        {
            if !entry.file_type().is_dir() {
                continue;
            }

            scanned += 1;

            match Self::scan_song_folder(entry.path()) {
                Ok(Some(song)) => songs.push(song),
                Ok(None) => {} // 跳过无效目录
                Err(e) => errors.push(format!("扫描 {} 失败: {}", entry.path().display(), e)),
            }
        }

        // 按名称排序
        songs.sort_by(|a, b| a.display_name.cmp(&b.display_name));

        self.songs = songs.clone();

        let elapsed_ms = start_time.elapsed().as_millis() as u64;

        Ok(ScanResult {
            songs,
            total_scanned: scanned,
            elapsed_ms,
            errors,
        })
    }

    /// 扫描单个歌曲目录
    fn scan_song_folder(folder_path: &Path) -> Result<Option<SongInfo>, String> {
        let folder_name = folder_path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("")
            .to_string();

        // 解析目录名
        let (display_name, star_rating) = Self::parse_folder_name(&folder_name);

        // 查找SM文件（必须有）
        let sm_file = Self::find_sm_file(folder_path);
        if sm_file.is_none() {
            return Ok(None); // 没有SM文件，跳过
        }

        // 查找音频文件（可选）
        let audio_file = Self::find_audio_file(folder_path);

        // 查找封面图片（可选）
        let banner_file = Self::find_banner_file(folder_path);

        Ok(Some(SongInfo {
            folder_path: folder_path.to_string_lossy().to_string(),
            folder_name,
            display_name,
            star_rating,
            sm_file,
            audio_file,
            banner_file,
        }))
    }

    /// 解析目录名，提取显示名称和星级
    ///
    /// 格式: "PREFIX#SONG_NAME#STAR" -> ("SONG_NAME", Some(STAR))
    fn parse_folder_name(folder_name: &str) -> (String, Option<u8>) {
        if !folder_name.contains('#') {
            return (folder_name.to_string(), None);
        }

        let parts: Vec<&str> = folder_name.split('#').collect();

        if parts.len() >= 3 {
            // 尝试解析最后一部分为星级
            if let Ok(star) = parts.last().unwrap().parse::<u8>() {
                if star >= 1 && star <= 20 {
                    let display_name = parts[parts.len() - 2].to_string();
                    if !display_name.is_empty() {
                        return (display_name, Some(star));
                    }
                }
            }
        }

        (folder_name.to_string(), None)
    }

    /// 查找SM文件
    fn find_sm_file(folder_path: &Path) -> Option<String> {
        let entries = fs::read_dir(folder_path).ok()?;

        let mut sm_files: Vec<String> = Vec::new();

        for entry in entries.filter_map(|e| e.ok()) {
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str())?.to_lowercase() == "sm" {
                sm_files.push(path.to_string_lossy().to_string());
            }
        }

        if sm_files.is_empty() {
            return None;
        }

        // 如果有多个，优先选择与目录名相似的
        let folder_name = folder_path.file_name()?.to_str()?;
        for sm_file in &sm_files {
            let sm_name = Path::new(sm_file)
                .file_stem()?
                .to_str()?;
            if folder_name.to_lowercase().contains(&sm_name.to_lowercase()) {
                return Some(sm_file.clone());
            }
        }

        // 否则返回第一个
        sm_files.into_iter().next()
    }

    /// 查找音频文件
    fn find_audio_file(folder_path: &Path) -> Option<String> {
        let entries = fs::read_dir(folder_path).ok()?;

        let mut audio_candidates: Vec<(String, usize, i32)> = Vec::new(); // (路径, 扩展名优先级, 名称匹配分)
        let folder_name = folder_path.file_name()?.to_str()?.to_lowercase();

        for entry in entries.filter_map(|e| e.ok()) {
            let path = entry.path();
            let ext = path.extension().and_then(|e| e.to_str())?.to_lowercase();

            if !AUDIO_EXTENSIONS.contains(&ext.as_str()) {
                continue;
            }

            let ext_priority = AUDIO_EXTENSIONS.iter()
                .position(|&e| e == ext)
                .unwrap_or(999);

            let base_name = path.file_stem()?
                .to_str()?
                .to_lowercase();

            let match_score = if base_name.contains(&folder_name) {
                2
            } else if folder_name.contains(&base_name) {
                1
            } else {
                0
            };

            audio_candidates.push((path.to_string_lossy().to_string(), ext_priority, match_score));
        }

        if audio_candidates.is_empty() {
            return None;
        }

        // 按优先级排序：扩展名优先级（越小越好）-> 名称匹配分（越大越好）
        audio_candidates.sort_by(|a, b| {
            match a.1.cmp(&b.1) {
                std::cmp::Ordering::Equal => b.2.cmp(&a.2),
                other => other,
            }
        });

        audio_candidates.into_iter().next().map(|(p, _, _)| p)
    }

    /// 查找封面图片
    fn find_banner_file(folder_path: &Path) -> Option<String> {
        // 按预定义顺序查找
        for banner_name in BANNER_NAMES {
            let banner_path = folder_path.join(banner_name);
            if banner_path.exists() {
                return Some(banner_path.to_string_lossy().to_string());
            }
        }

        // 查找其他可能的图片文件
        let entries = fs::read_dir(folder_path).ok()?;

        for entry in entries.filter_map(|e| e.ok()) {
            let path = entry.path();
            let ext = path.extension().and_then(|e| e.to_str())?.to_lowercase();

            if !["jpg", "jpeg", "png", "gif"].contains(&ext.as_str()) {
                continue;
            }

            // 检查文件大小（大于5KB）
            if let Ok(metadata) = entry.metadata() {
                if metadata.len() > 5000 {
                    return Some(path.to_string_lossy().to_string());
                }
            }
        }

        None
    }

    /// 获取所有歌曲
    pub fn get_songs(&self) -> &[SongInfo] {
        &self.songs
    }

    /// 按星级筛选歌曲
    pub fn filter_by_star(&self, min: Option<u8>, max: Option<u8>) -> Vec<&SongInfo> {
        self.songs
            .iter()
            .filter(|song| {
                match song.star_rating {
                    Some(star) => {
                        let min_ok = min.map_or(true, |m| star >= m);
                        let max_ok = max.map_or(true, |m| star <= m);
                        min_ok && max_ok
                    }
                    None => {
                        // 无星级的歌曲，如果min为0或None则包含
                        min.is_none() || min == Some(0)
                    }
                }
            })
            .collect()
    }

    /// 搜索歌曲
    pub fn search(&self, keyword: &str) -> Vec<&SongInfo> {
        let keyword_lower = keyword.to_lowercase();
        self.songs
            .iter()
            .filter(|song| {
                song.display_name.to_lowercase().contains(&keyword_lower)
                    || song.folder_name.to_lowercase().contains(&keyword_lower)
            })
            .collect()
    }

    /// 获取歌曲数量
    pub fn count(&self) -> usize {
        self.songs.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_folder_name() {
        let (name, star) = SongScanner::parse_folder_name("SPEED_DEVIL#song_name#8");
        assert_eq!(name, "song_name");
        assert_eq!(star, Some(8));

        let (name, star) = SongScanner::parse_folder_name("普通歌名");
        assert_eq!(name, "普通歌名");
        assert_eq!(star, None);

        let (name, star) = SongScanner::parse_folder_name("PREFIX#SONG#25");
        assert_eq!(star, None); // 超出范围
    }
}
