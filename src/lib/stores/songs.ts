import { writable, derived } from 'svelte/store';
import { invoke } from '@tauri-apps/api/core';

// 歌曲信息类型
export interface SongInfo {
  folder_path: string;
  folder_name: string;
  display_name: string;
  star_rating: number | null;
  sm_file: string | null;
  audio_file: string | null;
  banner_file: string | null;
}

// 歌曲存储
function createSongsStore() {
  const { subscribe, set, update } = writable<{
    songs: SongInfo[];
    filteredSongs: SongInfo[];
    isLoading: boolean;
    error: string | null;
    currentPage: number;
    pageSize: number;
    searchQuery: string;
    starFilterMin: number | null;
    starFilterMax: number | null;
  }>({
    songs: [],
    filteredSongs: [],
    isLoading: false,
    error: null,
    currentPage: 0,
    pageSize: 8,
    searchQuery: '',
    starFilterMin: null,
    starFilterMax: null,
  });

  // 过滤歌曲
  function filterSongs(
    songs: SongInfo[],
    query: string,
    min: number | null,
    max: number | null
  ): SongInfo[] {
    return songs.filter(song => {
      // 搜索过滤
      if (query) {
        const q = query.toLowerCase();
        if (!song.display_name.toLowerCase().includes(q) &&
            !song.folder_name.toLowerCase().includes(q)) {
          return false;
        }
      }

      // 星级过滤
      if (song.star_rating !== null) {
        if (min !== null && song.star_rating < min) return false;
        if (max !== null && song.star_rating > max) return false;
      } else if (min !== null && min > 0) {
        return false;
      }

      return true;
    });
  }

  return {
    subscribe,

    setSongs: (songs: SongInfo[]) => {
      update(state => ({
        ...state,
        songs,
        filteredSongs: filterSongs(
          songs,
          state.searchQuery,
          state.starFilterMin,
          state.starFilterMax
        ),
        error: null,
      }));
    },

    setScanning: (isLoading: boolean) => {
      update(state => ({ ...state, isLoading }));
    },

    setError: (error: string | null) => {
      update(state => ({ ...state, error }));
    },

    setSearchQuery: (query: string) => {
      update(state => ({
        ...state,
        searchQuery: query,
        currentPage: 0,
        filteredSongs: filterSongs(
          state.songs,
          query,
          state.starFilterMin,
          state.starFilterMax
        ),
      }));
    },

    setStarFilter: (min: number | null, max: number | null) => {
      update(state => ({
        ...state,
        starFilterMin: min,
        starFilterMax: max,
        currentPage: 0,
        filteredSongs: filterSongs(
          state.songs,
          state.searchQuery,
          min,
          max
        ),
      }));
    },

    setCurrentPage: (page: number) => {
      update(state => ({ ...state, currentPage: page }));
    },

    nextPage: () => {
      update(state => {
        const totalPages = Math.ceil(state.filteredSongs.length / state.pageSize);
        if (state.currentPage < totalPages - 1) {
          return { ...state, currentPage: state.currentPage + 1 };
        }
        return state;
      });
    },

    prevPage: () => {
      update(state => {
        if (state.currentPage > 0) {
          return { ...state, currentPage: state.currentPage - 1 };
        }
        return state;
      });
    },

    setPageSize: (size: number) => {
      update(state => ({
        ...state,
        pageSize: size,
        currentPage: 0,
      }));
    },

    refresh: async (path: string) => {
      try {
        update(state => ({ ...state, isLoading: true, error: null }));
        const result = await invoke<{ songs: SongInfo[], elapsed_ms: number }>('scan_songs', { path });
        update(state => ({
          ...state,
          songs: result.songs,
          filteredSongs: filterSongs(
            result.songs,
            state.searchQuery,
            state.starFilterMin,
            state.starFilterMax
          ),
          isLoading: false,
          currentPage: 0,
        }));
        return result.songs;
      } catch (error) {
        update(state => ({
          ...state,
          isLoading: false,
          error: String(error),
        }));
        return [];
      }
    },
  };
}

export const songsStore = createSongsStore();

// 当前页歌曲
export const currentPageSongs = derived(songsStore, $store => {
  const start = $store.currentPage * $store.pageSize;
  const end = start + $store.pageSize;
  return $store.filteredSongs.slice(start, end);
});

// 总页数
export const totalPages = derived(songsStore, $store => {
  return Math.max(1, Math.ceil($store.filteredSongs.length / $store.pageSize));
});
