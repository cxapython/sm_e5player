import { writable } from 'svelte/store';
import type { AppConfig } from './types';
import { defaultConfig } from './types';
import { invoke } from '@tauri-apps/api/core';

// 创建配置存储
function createConfigStore() {
  const { subscribe, set, update } = writable<AppConfig>(defaultConfig);

  return {
    subscribe,
    setConfig: (config: AppConfig) => set(config),
    updateConfig: async (config: Partial<AppConfig>) => {
      update(c => {
        const newConfig = { ...c, ...config };
        // 异步保存到后端
        invoke('save_config', { newConfig }).catch(console.error);
        return newConfig;
      });
    },
    setScanPath: async (path: string) => {
      await invoke('set_scan_path', { path });
      update(c => ({ ...c, scan_path: path }));
    },
    setVolume: (volume: number) => {
      update(c => ({ ...c, master_volume: volume }));
    },
    setScrollSpeed: (speed: number) => {
      update(c => ({ ...c, scroll_speed: speed }));
    },
    setStarFilter: (min: number | null, max: number | null) => {
      update(c => ({ ...c, star_filter_min: min, star_filter_max: max }));
    },
    reset: async () => {
      await invoke('reset_config');
      set(defaultConfig);
    },
  };
}

export const configStore = createConfigStore();
