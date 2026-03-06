<script lang="ts">
  import { onMount } from 'svelte';
  import { invoke } from '@tauri-apps/api/core';
  import { open } from '@tauri-apps/plugin-dialog';

  // Stores
  import { configStore } from '$lib/stores/config';
  import { songsStore } from '$lib/stores/songs';
  import { playerStore } from '$lib/stores/player';

  // Views
  import SongSelectView from '$lib/views/SongSelectView.svelte';
  import PlayerView from '$lib/views/PlayerView.svelte';

  // State (Svelte 5 runes)
  let currentView = $state<'select' | 'player'>('select');
  let isLoading = $state(true);
  let showWelcomeDialog = $state(false);
  let debugMessage = $state('');

  // 检查是否首次运行
  onMount(async () => {
    console.log('[App] onMount triggered');
    try {
      const config = await invoke<any>('get_config');
      console.log('[App] Config loaded:', config);
      console.log('[App] scan_path:', config.scan_path);
      console.log('[App] showWelcomeDialog:', !config.scan_path);
      configStore.setConfig(config);

      if (!config.scan_path) {
        showWelcomeDialog = true;
        console.log('[App] Showing welcome dialog');
      } else {
        // 自动扫描歌曲
        console.log('[App] Auto-scanning songs from:', config.scan_path);
        await scanSongs(config.scan_path);
      }
    } catch (error) {
      console.error('[App] Failed to load config:', error);
      debugMessage = '加载配置失败: ' + String(error);
    } finally {
      isLoading = false;
      console.log('[App] Loading complete, isLoading = false');
    }
  });

  // 扫描歌曲
  async function scanSongs(path: string) {
    try {
      songsStore.setScanning(true);
      debugMessage = '正在扫描: ' + path;
      const result = await invoke<any>('scan_songs', { path });
      console.log('[App] Scan result:', result);
      console.log(`[App] Scanned ${result.songs.length} songs in ${result.elapsed_ms}ms`);

      // 打印前几首歌曲的路径信息
      if (result.songs.length > 0) {
        console.log('[App] First song:', result.songs[0]);
        debugMessage = `找到 ${result.songs.length} 首歌曲`;
      } else {
        debugMessage = '未找到歌曲';
      }

      songsStore.setSongs(result.songs);
    } catch (error) {
      console.error('[App] Failed to scan songs:', error);
      debugMessage = '扫描失败: ' + String(error);
    } finally {
      songsStore.setScanning(false);
    }
  }

  // 选择目录
  async function selectFolder() {
    try {
      const selected = await open({
        directory: true,
        multiple: false,
        title: '选择歌曲目录',
      });

      console.log('[App] Selected folder:', selected);

      if (selected && typeof selected === 'string') {
        await invoke('set_scan_path', { path: selected });
        showWelcomeDialog = false;
        await scanSongs(selected);
      }
    } catch (error) {
      console.error('[App] Failed to select folder:', error);
      debugMessage = '选择目录失败: ' + String(error);
    }
  }

  // 开始游戏
  function startGame(song: any) {
    console.log('[App] Starting game with song:', song);
    playerStore.setCurrentSong(song);
    currentView = 'player';
  }

  // 返回选歌
  function backToSelect() {
    currentView = 'select';
  }
</script>

<div class="app-container w-full h-screen overflow-hidden bg-gradient-to-b from-bg-top to-bg-bottom neon-grid">
  {#if isLoading}
    <!-- 加载界面 -->
    <div class="flex items-center justify-center w-full h-full">
      <div class="text-center">
        <div class="loading-spinner mx-auto mb-4"></div>
        <p class="text-text-gray">加载中...</p>
        {#if debugMessage}
          <p class="text-text-dark text-sm mt-2">{debugMessage}</p>
        {/if}
      </div>
    </div>
  {:else if showWelcomeDialog}
    <!-- 欢迎对话框 -->
    <div class="flex items-center justify-center w-full h-full">
      <div class="glass-panel p-8 max-w-md text-center fade-in">
        <h1 class="text-2xl font-bold text-text-white mb-4">欢迎使用 SM Arrow Player</h1>
        <p class="text-text-gray mb-6">
          请选择您的歌曲目录以开始游戏。目录应包含SM谱面文件。
        </p>
        <button
          class="glass-button px-6 py-3 text-lg"
          onclick={selectFolder}
        >
          选择歌曲目录
        </button>
        {#if debugMessage}
          <p class="text-text-dark text-sm mt-4">{debugMessage}</p>
        {/if}
      </div>
    </div>
  {:else if currentView === 'select'}
    <SongSelectView
      onstartgame={(song) => startGame(song)}
      onselectfolder={selectFolder}
    />
  {:else}
    <PlayerView
      onback={backToSelect}
    />
  {/if}
</div>
