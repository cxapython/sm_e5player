// 配置类型定义

export interface AppConfig {
  scan_path: string | null;
  last_played: string | null;
  last_sm_file: string | null;
  last_page: number;

  window_width: number;
  window_height: number;
  fullscreen: boolean;
  fps: number;

  master_volume: number;
  music_volume: number;
  sfx_volume: number;
  preview_duration: number;
  preview_delay: number;

  scroll_speed: number;
  offset: number;
  tick_per_beat: number;

  perfect_window: number;
  good_window: number;
  bad_window: number;

  glass_theme: string;
  spectrum_enabled: boolean;
  spectrum_bars: number;
  card_columns_large: number;
  card_columns_small: number;
  card_rows_large: number;
  card_rows_small: number;
  large_screen_threshold: number;

  star_filter_min: number | null;
  star_filter_max: number | null;
}

export const defaultConfig: AppConfig = {
  scan_path: null,
  last_played: null,
  last_sm_file: null,
  last_page: 0,

  window_width: 1280,
  window_height: 720,
  fullscreen: false,
  fps: 60,

  master_volume: 0.8,
  music_volume: 1.0,
  sfx_volume: 0.8,
  preview_duration: 10.0,
  preview_delay: 0.5,

  scroll_speed: 840.0,
  offset: 0.0,
  tick_per_beat: 96,

  perfect_window: 0.045,
  good_window: 0.090,
  bad_window: 0.135,

  glass_theme: 'dark',
  spectrum_enabled: true,
  spectrum_bars: 32,
  card_columns_large: 4,
  card_columns_small: 3,
  card_rows_large: 2,
  card_rows_small: 3,
  large_screen_threshold: 1920,

  star_filter_min: null,
  star_filter_max: null,
};
