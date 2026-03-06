import { writable, derived } from 'svelte/store';
import { invoke } from '@tauri-apps/api/core';
import type { SongInfo } from './songs';

// 箭头事件类型
export interface ArrowEvent {
  track_idx: number;
  start_sec: number;
  end_sec: number;
  arrow_type: number;
}

// 谱面信息类型
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

// 谱面数据类型
export interface ChartData {
  info: ChartInfo;
  arrows: ArrowEvent[];
  total_duration: number;
  total_notes: number;
}

// 判定结果
export type JudgeResult = 'Perfect' | 'Good' | 'Bad' | 'Miss';

// 判定统计
export interface JudgeStats {
  perfect: number;
  good: number;
  bad: number;
  miss: number;
}

// 游戏状态
export type GameState = 'loading' | 'ready' | 'playing' | 'paused' | 'finished';

// 播放器存储
function createPlayerStore() {
  const { subscribe, set, update } = writable<{
    // 当前歌曲
    currentSong: SongInfo | null;
    chartData: ChartData | null;

    // 游戏状态
    gameState: GameState;
    currentTime: number;
    scrollSpeed: number;
    offset: number;

    // 判定
    score: number;
    combo: number;
    maxCombo: number;
    stats: JudgeStats;

    // 按键状态
    keyPressed: boolean[];

    // 音频状态
    isAudioPlaying: boolean;
    volume: number;
  }>({
    currentSong: null,
    chartData: null,
    gameState: 'loading',
    currentTime: 0,
    scrollSpeed: 840,
    offset: 0,
    score: 0,
    combo: 0,
    maxCombo: 0,
    stats: { perfect: 0, good: 0, bad: 0, miss: 0 },
    keyPressed: [false, false, false, false, false],
    isAudioPlaying: false,
    volume: 0.8,
  });

  return {
    subscribe,

    setCurrentSong: (song: SongInfo | null) => {
      update(state => ({ ...state, currentSong: song }));
    },

    setChartData: (data: ChartData | null) => {
      update(state => ({ ...state, chartData: data }));
    },

    setGameState: (gameState: GameState) => {
      update(state => ({ ...state, gameState }));
    },

    setCurrentTime: (time: number) => {
      update(state => ({ ...state, currentTime: time }));
    },

    setScrollSpeed: (speed: number) => {
      update(state => ({ ...state, scrollSpeed: speed }));
    },

    setOffset: (offset: number) => {
      update(state => ({ ...state, offset }));
    },

    // 按键处理
    setKeyPressed: (trackIdx: number, pressed: boolean) => {
      update(state => {
        const newKeys = [...state.keyPressed];
        newKeys[trackIdx] = pressed;
        return { ...state, keyPressed: newKeys };
      });
    },

    // 判定更新
    addJudge: (result: JudgeResult) => {
      update(state => {
        const newStats = { ...state.stats };
        let combo = state.combo;
        let score = state.score;

        switch (result) {
          case 'Perfect':
            newStats.perfect++;
            combo++;
            score += 100 + (combo >= 10 ? 10 : 0);
            break;
          case 'Good':
            newStats.good++;
            combo++;
            score += 50 + (combo >= 10 ? 5 : 0);
            break;
          case 'Bad':
            newStats.bad++;
            combo = 0;
            score += 10;
            break;
          case 'Miss':
            newStats.miss++;
            combo = 0;
            break;
        }

        return {
          ...state,
          stats: newStats,
          combo,
          maxCombo: Math.max(state.maxCombo, combo),
          score,
        };
      });
    },

    // 重置游戏
    resetGame: () => {
      update(state => ({
        ...state,
        gameState: 'ready',
        currentTime: 0,
        score: 0,
        combo: 0,
        maxCombo: 0,
        stats: { perfect: 0, good: 0, bad: 0, miss: 0 },
        keyPressed: [false, false, false, false, false],
      }));
    },

    // 音频控制
    setAudioPlaying: (playing: boolean) => {
      update(state => ({ ...state, isAudioPlaying: playing }));
    },

    setVolume: (volume: number) => {
      update(state => ({ ...state, volume }));
      invoke('set_volume', { volume }).catch(console.error);
    },

    // 加载谱面
    loadChart: async (smPath: string) => {
      try {
        update(state => ({ ...state, gameState: 'loading' }));
        const data = await invoke<ChartData>('load_chart', { smPath });
        update(state => ({
          ...state,
          chartData: data,
          gameState: 'ready',
          offset: data.info.offset,
        }));
        return data;
      } catch (error) {
        console.error('Failed to load chart:', error);
        update(state => ({ ...state, gameState: 'loading' }));
        return null;
      }
    },

    // 播放音频
    playAudio: async (audioPath: string) => {
      try {
        await invoke('play_audio', { path: audioPath });
        update(state => ({ ...state, isAudioPlaying: true }));
      } catch (error) {
        console.error('Failed to play audio:', error);
      }
    },

    // 暂停音频
    pauseAudio: async () => {
      try {
        await invoke('pause_audio');
        update(state => ({ ...state, isAudioPlaying: false }));
      } catch (error) {
        console.error('Failed to pause audio:', error);
      }
    },

    // 恢复音频
    resumeAudio: async () => {
      try {
        await invoke('resume_audio');
        update(state => ({ ...state, isAudioPlaying: true }));
      } catch (error) {
        console.error('Failed to resume audio:', error);
      }
    },

    // 停止音频
    stopAudio: async () => {
      try {
        await invoke('stop_audio');
        update(state => ({ ...state, isAudioPlaying: false }));
      } catch (error) {
        console.error('Failed to stop audio:', error);
      }
    },
  };
}

export const playerStore = createPlayerStore();

// 准确率计算
export const accuracy = derived(playerStore, $store => {
  const total = $store.stats.perfect + $store.stats.good + $store.stats.bad + $store.stats.miss;
  if (total === 0) return 1;
  const weighted = $store.stats.perfect * 100 + $store.stats.good * 70 + $store.stats.bad * 30;
  return weighted / (total * 100);
});

// 评级计算
export const grade = derived(playerStore, $store => {
  const total = $store.stats.perfect + $store.stats.good + $store.stats.bad + $store.stats.miss;
  const accuracy = total === 0 ? 1 :
    ($store.stats.perfect * 100 + $store.stats.good * 70 + $store.stats.bad * 30) / (total * 100);

  if (accuracy >= 0.95 && $store.stats.miss === 0) return 'S';
  if (accuracy >= 0.95) return 'AAA';
  if (accuracy >= 0.90) return 'AA';
  if (accuracy >= 0.80) return 'A';
  if (accuracy >= 0.70) return 'B';
  if (accuracy >= 0.60) return 'C';
  if (accuracy >= 0.50) return 'D';
  return 'F';
});
