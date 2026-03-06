//! SM Arrow Player 库模块
//!
//! 包含所有核心功能模块

pub mod config;
pub mod parser;
pub mod scanner;
pub mod audio;
pub mod judge;
pub mod commands;
pub mod models;
pub mod utils;

use tauri::Manager;
use std::sync::Mutex;

/// 应用程序入口
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .setup(|app| {
            // 初始化配置管理器
            let config_manager = config::ConfigManager::new();
            app.manage(Mutex::new(config_manager));

            // 初始化音频管理器
            let audio_manager = audio::AudioManager::new();
            app.manage(Mutex::new(audio_manager));

            // 初始化歌曲扫描器
            let scanner_state = commands::song_commands::ScannerState {
                scanner: Mutex::new(scanner::SongScanner::new()),
            };
            app.manage(scanner_state);

            // 检查是否首次运行
            let config = app.state::<Mutex<config::ConfigManager>>();
            let is_first_run = config.lock().unwrap().is_first_run();

            if is_first_run {
                // TODO: 显示首次启动引导
                println!("[SM Arrow Player] 首次运行，需要选择歌曲目录");
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            // 配置命令
            commands::config_commands::get_config,
            commands::config_commands::save_config,
            commands::config_commands::set_scan_path,
            commands::config_commands::reset_config,
            // 歌曲命令
            commands::song_commands::scan_songs,
            commands::song_commands::get_song_count,
            commands::song_commands::search_songs,
            commands::song_commands::filter_by_star,
            // 播放器命令
            commands::player_commands::load_chart,
            commands::player_commands::get_chart_info,
            // 音频命令
            commands::audio_commands::play_audio,
            commands::audio_commands::pause_audio,
            commands::audio_commands::resume_audio,
            commands::audio_commands::stop_audio,
            commands::audio_commands::set_volume,
            commands::audio_commands::get_audio_state,
            commands::audio_commands::get_volume,
            commands::audio_commands::get_audio_position,
            commands::audio_commands::set_audio_position,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
