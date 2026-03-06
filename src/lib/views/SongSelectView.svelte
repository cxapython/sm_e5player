<script lang="ts">
  import { onMount } from 'svelte';
  import { open } from '@tauri-apps/plugin-dialog';
  import { convertFileSrc } from '@tauri-apps/api/core';

  import { songsStore, currentPageSongs, totalPages } from '$lib/stores/songs';
  import { configStore } from '$lib/stores/config';
  import { GlassCard, GlassButton, StarRating, GlassSearch } from '$lib/components/glass';
  import type { SongInfo } from '$lib/stores/songs';

  // 定义事件
  interface Props {
    onstartgame?: (song: SongInfo) => void;
    onselectfolder?: () => void;
  }

  let { onstartgame, onselectfolder }: Props = $props();

  // 本地状态
  let isHovering: string | null = $state(null);
  let previewTimeout: ReturnType<typeof setTimeout> | null = null;
  let audioElement: HTMLAudioElement | null = $state(null);
  let spectrumBars: number[] = $state(new Array(32).fill(0));

  // 从store派生的值
  let songs = $derived($songsStore.songs);
  let currentPage = $derived($songsStore.currentPage);
  let isLoading = $derived($songsStore.isLoading);

  // 星级筛选
  let starFilter = $state(0); // 0 = 全部

  const starOptions = [
    { label: '全部', value: 0 },
    { label: '★1-5', value: 1 },
    { label: '★6-9', value: 2 },
    { label: '★10+', value: 3 },
  ];

  // 初始化
  onMount(() => {
    // 创建音频元素用于预览
    audioElement = new Audio();
    audioElement.volume = 0.5;

    // 加载歌曲
    if ($configStore.scan_path) {
      songsStore.refresh($configStore.scan_path);
    }

    // 清理函数
    return () => {
      stopPreview();
    };
  });

  // 初始化音频系统（懒加载，需要用户交互后才能播放）
  function ensureAudioContext() {
    // 音频上下文由浏览器自动管理，直接返回 true
    return true;
  }

  // 将本地路径转换为可访问的URL
  function getAssetUrl(path: string | null): string | null {
    if (!path) return null;
    try {
      const url = convertFileSrc(path);
      return url;
    } catch (e) {
      console.error('[getAssetUrl] 转换失败:', path, e);
      return null;
    }
  }

  // 图片加载错误处理
  function handleImageError(event: Event, song: SongInfo) {
    const img = event.target as HTMLImageElement;
    console.error('[Image] 加载失败:', song.display_name, song.banner_file, img.src);
    img.style.display = 'none';
  }

  // 图片加载成功
  function handleImageLoad(event: Event, song: SongInfo) {
    console.log('[Image] 加载成功:', song.display_name);
  }

  // 停止预览
  function stopPreview() {
    if (previewTimeout) {
      clearTimeout(previewTimeout);
      previewTimeout = null;
    }
    if (audioElement) {
      audioElement.pause();
      audioElement.currentTime = 0;
      audioElement.src = '';
    }
    spectrumBars = new Array(32).fill(0);
  }

  // 开始预览
  function startPreview(audioPath: string) {
    if (!audioElement) return;

    const url = getAssetUrl(audioPath);
    if (!url) {
      console.error('[Audio] 无法转换音频路径:', audioPath);
      return;
    }

    console.log('[Audio] 开始预览:', audioPath, '->', url);

    // 先停止当前播放，设置新的源，然后播放
    audioElement.pause();
    audioElement.src = url;
    audioElement.load();

    audioElement.play().then(() => {
      console.log('[Audio] 播放成功');
    }).catch(e => {
      if (e.name === 'AbortError') {
        console.log('[Audio] 播放被中断（切换到新歌曲）');
      } else {
        console.error('[Audio] 播放失败:', e, url);
      }
    });
  }

  // 搜索处理
  function handleSearch(value: string) {
    songsStore.setSearchQuery(value);
  }

  // 星级筛选处理
  function handleStarFilter(value: number) {
    starFilter = value;
    switch (value) {
      case 0:
        songsStore.setStarFilter(null, null);
        break;
      case 1:
        songsStore.setStarFilter(1, 5);
        break;
      case 2:
        songsStore.setStarFilter(6, 9);
        break;
      case 3:
        songsStore.setStarFilter(10, 20);
        break;
    }
  }

  // 选择文件夹
  async function handleSelectFolder() {
    try {
      const selected = await open({
        directory: true,
        multiple: false,
        title: '选择歌曲目录',
      });

      if (selected && typeof selected === 'string') {
        await configStore.setScanPath(selected);
        await songsStore.refresh(selected);
        onselectfolder?.();
      }
    } catch (error) {
      console.error('Failed to select folder:', error);
    }
  }

  // 歌曲卡片交互
  function handleCardHover(song: SongInfo) {
    isHovering = song.folder_path;

    // 悬停预览音频
    if (song.audio_file && audioElement) {
      previewTimeout = setTimeout(() => {
        startPreview(song.audio_file!);
      }, 500);
    }
  }

  function handleCardLeave() {
    isHovering = null;
    stopPreview();
  }

  function handleCardClick(song: SongInfo) {
    // 停止预览
    stopPreview();
    onstartgame?.(song);
  }

  // 翻页
  function handlePrevPage() {
    songsStore.prevPage();
  }

  function handleNextPage() {
    songsStore.nextPage();
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === 'ArrowLeft') {
      handlePrevPage();
    } else if (event.key === 'ArrowRight') {
      handleNextPage();
    }
  }
</script>

<svelte:window onkeydown={handleKeyDown} />

<div class="song-select-view w-full h-full flex flex-col">
  <!-- 顶部标题栏 -->
  <header class="glass-panel m-4 p-4 flex items-center justify-between">
    <h1 class="text-2xl font-bold text-text-white">SM Arrow Player</h1>
    <div class="flex items-center gap-4">
      <GlassButton text="选择目录" onclick={handleSelectFolder} />
    </div>
  </header>

  <!-- 筛选栏 -->
  <div class="filter-bar mx-4 mb-4 flex items-center gap-4">
    <GlassSearch
      placeholder="搜索歌曲..."
      onchange={handleSearch}
    />
    <div class="flex gap-2">
      {#each starOptions as option}
        <GlassButton
          text={option.label}
          active={starFilter === option.value}
          cornerRadius={12}
          onclick={() => handleStarFilter(option.value)}
        />
      {/each}
    </div>
  </div>

  <!-- 歌曲网格 -->
  <main class="flex-1 overflow-hidden mx-4 mb-4">
    {#if isLoading}
      <div class="flex items-center justify-center w-full h-full">
        <div class="text-center">
          <div class="loading-spinner mx-auto mb-4"></div>
          <p class="text-text-gray">扫描歌曲中...</p>
        </div>
      </div>
    {:else if $currentPageSongs.length === 0}
      <div class="flex items-center justify-center w-full h-full">
        <div class="glass-panel p-8 text-center">
          <p class="text-text-gray mb-4">未找到歌曲</p>
          <GlassButton text="选择歌曲目录" onclick={handleSelectFolder} />
        </div>
      </div>
    {:else}
      <div class="song-grid grid gap-4 h-full overflow-y-auto pr-2"
           style="grid-template-columns: repeat({$configStore.card_columns_large}, 1fr);">
        {#each $currentPageSongs as song (song.folder_path)}
          <GlassCard
            cornerRadius={16}
            onmouseenter={() => handleCardHover(song)}
            onmouseleave={handleCardLeave}
            onclick={() => handleCardClick(song)}
          >
            <div class="song-card p-4 flex flex-col h-full">
              <!-- 封面 -->
              <div class="cover-container relative mb-3"
                   style="padding-bottom: 75%; background: rgba(40, 40, 60, 0.5); border-radius: 12px;">
                {#if song.banner_file}
                  <img
                    src={getAssetUrl(song.banner_file) || ''}
                    alt={song.display_name}
                    class="cover-image absolute inset-0 w-full h-full object-cover rounded-lg"
                    onerror={(e) => handleImageError(e, song)}
                    onload={(e) => handleImageLoad(e, song)}
                  />
                {:else}
                  <div class="cover-placeholder absolute inset-0 flex items-center justify-center">
                    <svg class="w-12 h-12 text-text-dark" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/>
                    </svg>
                  </div>
                {/if}

                <!-- 封面反光效果 -->
                <div class="cover-shine absolute inset-0 rounded-lg pointer-events-none"></div>

                <!-- 星级标签 -->
                {#if song.star_rating}
                  <div class="star-badge absolute top-2 right-2">
                    <StarRating stars={song.star_rating} size={10} />
                  </div>
                {/if}
              </div>

              <!-- 歌曲信息 -->
              <div class="song-info flex-1 flex flex-col">
                <h3 class="song-name text-sm font-medium text-text-white truncate mb-1">
                  {song.display_name}
                </h3>

                <!-- 状态指示 -->
                <div class="flex items-center gap-2 text-xs text-text-dark mt-auto">
                  {#if !song.audio_file}
                    <span class="status-badge">无音频</span>
                  {/if}
                  {#if !song.sm_file}
                    <span class="status-badge">无谱面</span>
                  {/if}
                </div>
              </div>
            </div>
          </GlassCard>
        {/each}
      </div>
    {/if}
  </main>

  <!-- 底部分页 -->
  <footer class="glass-panel m-4 p-4 flex items-center justify-center gap-4">
    <GlassButton text="◀" cornerRadius={12} onclick={handlePrevPage} />
    <span class="text-text-gray">
      {$songsStore.currentPage + 1} / {$totalPages}
    </span>
    <span class="text-text-dark text-sm">
      (共 {$songsStore.filteredSongs.length} 首)
    </span>
    <GlassButton text="▶" cornerRadius={12} onclick={handleNextPage} />
  </footer>
</div>

<style>
  .song-select-view {
    user-select: none;
  }

  .cover-container {
    overflow: hidden;
  }

  .cover-image {
    transition: transform 0.3s ease;
  }

  :global(.glass-card:hover) .cover-image {
    transform: scale(1.05);
  }

  .cover-shine {
    background: linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.15) 0%,
      transparent 50%,
      transparent 100%
    );
  }

  .cover-placeholder {
    background: linear-gradient(135deg, rgba(60, 60, 80, 0.5), rgba(40, 40, 60, 0.5));
  }

  .song-name {
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
  }

  .status-badge {
    background: rgba(255, 100, 100, 0.3);
    padding: 2px 6px;
    border-radius: 4px;
    color: #ff8080;
  }

  .filter-bar :global(.glass-input) {
    width: 200px;
  }
</style>
