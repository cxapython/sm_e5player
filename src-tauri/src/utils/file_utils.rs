//! 文件工具函数

use std::path::Path;

/// 获取文件扩展名（小写）
pub fn get_extension(path: &str) -> Option<String> {
    Path::new(path)
        .extension()
        .and_then(|e| e.to_str())
        .map(|e| e.to_lowercase())
}

/// 检查文件是否为音频文件
pub fn is_audio_file(path: &str) -> bool {
    match get_extension(path).as_deref() {
        Some("mp3") | Some("ogg") | Some("wav") | Some("flac") | Some("aac") => true,
        _ => false,
    }
}

/// 检查文件是否为图片文件
pub fn is_image_file(path: &str) -> bool {
    match get_extension(path).as_deref() {
        Some("jpg") | Some("jpeg") | Some("png") | Some("gif") | Some("webp") | Some("bmp") => true,
        _ => false,
    }
}

/// 检查文件是否为SM文件
pub fn is_sm_file(path: &str) -> bool {
    get_extension(path).as_deref() == Some("sm")
}

/// 获取文件名（不含扩展名）
pub fn get_file_stem(path: &str) -> Option<String> {
    Path::new(path)
        .file_stem()
        .and_then(|e| e.to_str())
        .map(|e| e.to_string())
}

/// 获取文件名（含扩展名）
pub fn get_file_name(path: &str) -> Option<String> {
    Path::new(path)
        .file_name()
        .and_then(|e| e.to_str())
        .map(|e| e.to_string())
}

/// 获取父目录路径
pub fn get_parent_dir(path: &str) -> Option<String> {
    Path::new(path)
        .parent()
        .and_then(|e| e.to_str())
        .map(|e| e.to_string())
}

/// 规范化路径
pub fn canonicalize_path(path: &str) -> Option<String> {
    std::fs::canonicalize(path)
        .ok()
        .and_then(|p| p.to_str().map(|s| s.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_extension() {
        assert_eq!(get_extension("test.mp3"), Some("mp3".to_string()));
        assert_eq!(get_extension("test.OGG"), Some("ogg".to_string()));
        assert_eq!(get_extension("test"), None);
    }

    #[test]
    fn test_is_audio_file() {
        assert!(is_audio_file("test.mp3"));
        assert!(is_audio_file("test.OGG"));
        assert!(!is_audio_file("test.txt"));
    }

    #[test]
    fn test_get_file_stem() {
        assert_eq!(get_file_stem("/path/to/test.mp3"), Some("test".to_string()));
        assert_eq!(get_file_stem("test"), Some("test".to_string()));
    }
}
