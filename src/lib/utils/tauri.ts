/**
 * Tauri API工具函数
 */

import { invoke } from '@tauri-apps/api/core';
import { open } from '@tauri-apps/plugin-dialog';

// 类型定义
export interface SongInfo {
  folder_path: string;
  folder_name: string;
  display_name: string;
  star_rating: number | null;
  sm_file: string | null;
  audio_file: string | null;
  banner_file: string | null;
}

export interface ChartData {
  info: ChartInfo;
  arrows: ArrowEvent[];
  total_duration: number;
  total_notes: number;
}

export interface ChartInfo {
  title: string;
  subtitle: string;
  artist: string;
  offset: number;
  bpm_list: [number, number][];
  display_bpm: string;
  column_count: number;
  difficulty: string;
}

export interface ArrowEvent {
  track_idx: number;
  start_sec: number;
  end_sec: number;
  arrow_type: number;
}

export interface ScanResult {
  songs: SongInfo[];
  total_scanned: number;
  elapsed_ms: number;
  errors: string[];
}

export interface AppConfig {
  scan_path: string | null;
  window_width: number;
  window_height: number;
  master_volume: number;
  scroll_speed: number;
  // ... 其他配置项
}

/**
 * 扫描歌曲目录
 */
export async function scanSongs(path: string): Promise<ScanResult> {
  return invoke<ScanResult>('scan_songs', { path });
}

/**
 * 加载谱面数据
 */
export async function loadChart(smPath: string): Promise<ChartData> {
  return invoke<ChartData>('load_chart', { smPath });
}

/**
 * 获取谱面信息
 */
export async function getChartInfo(smPath: string): Promise<ChartInfo> {
  return invoke<ChartInfo>('get_chart_info', { smPath });
}

/**
 * 播放音频
 */
export async function playAudio(path: string): Promise<void> {
  return invoke('play_audio', { path });
}

/**
 * 暂停音频
 */
export async function pauseAudio(): Promise<void> {
  return invoke('pause_audio');
}

/**
 * 恢复音频
 */
export async function resumeAudio(): Promise<void> {
  return invoke('resume_audio');
}

/**
 * 停止音频
 */
export async function stopAudio(): Promise<void> {
  return invoke('stop_audio');
}

/**
 * 设置音量
 */
export async function setVolume(volume: number): Promise<void> {
  return invoke('set_volume', { volume });
}

/**
 * 获取配置
 */
export async function getConfig(): Promise<AppConfig> {
  return invoke<AppConfig>('get_config');
}

/**
 * 保存配置
 */
export async function saveConfig(config: AppConfig): Promise<void> {
  return invoke('save_config', { newConfig: config });
}

/**
 * 设置扫描路径
 */
export async function setScanPath(path: string): Promise<void> {
  return invoke('set_scan_path', { path });
}

/**
 * 打开目录选择对话框
 */
export async function selectDirectory(title: string = '选择目录'): Promise<string | null> {
  const result = await open({
    directory: true,
    multiple: false,
    title,
  });
  return typeof result === 'string' ? result : null;
}

/**
 * 打开文件选择对话框
 */
export async function selectFile(
  title: string = '选择文件',
  filters?: { name: string; extensions: string[] }[]
): Promise<string | null> {
  const result = await open({
    directory: false,
    multiple: false,
    title,
    filters,
  });
  return typeof result === 'string' ? result : null;
}
