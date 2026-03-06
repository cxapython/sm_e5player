<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import { convertFileSrc } from '@tauri-apps/api/core';
  import { playerStore, accuracy, grade } from '$lib/stores/player';
  import { GlassButton, StarRating } from '$lib/components/glass';
  import { initNoteskin, getNoteskin, type Direction } from '$lib/utils/noteskin';
  import type { SongInfo } from '$lib/stores/songs';

  interface Props {
    onback?: () => void;
  }

  let { onback }: Props = $props();

  // Canvas引用
  let canvas: HTMLCanvasElement;
  let ctx: CanvasRenderingContext2D | null = null;

  // 音频
  let audioElement: HTMLAudioElement | null = null;

  // 动画状态
  let animationFrame: number | null = null;
  let lastTime = 0;

  // 游戏常量
  const TRACK_COUNT = 5;
  const JUDGE_WINDOWS = {
    PERFECT: 0.045,
    GOOD: 0.090,
    BAD: 0.135,
  };
  const KEY_MAP: Record<string, number> = {
    'KeyZ': 0, // 左下
    'KeyQ': 1, // 左上
    'KeyS': 2, // 中间
    'KeyE': 3, // 右上
    'KeyC': 4, // 右下
  };

  // 轨道索引到方向的映射
  const TRACK_DIRECTION: Direction[] = ['DownLeft', 'UpLeft', 'Center', 'UpRight', 'DownRight'];

  const margin = 20; // 布局边距

  // 判定状态
  let judgeDisplay: { result: string, time: number } | null = $state(null);

  // 轨道光效
  let trackLights: number[] = $state(new Array(TRACK_COUNT).fill(0));

  // 按键状态
  let keyPressed: boolean[] = $state(new Array(TRACK_COUNT).fill(false));

  // 处理的箭头集合
  let processedArrows: Set<number> = new Set();

  // 滚动速度
  let scrollSpeed = $derived($playerStore.scrollSpeed);

  // 初始化
  onMount(async () => {
    // 加载 noteskin
    try {
      await initNoteskin();
      console.log('[Noteskin] 加载完成');
    } catch (e) {
      console.error('[Noteskin] 加载失败:', e);
    }

    // 创建音频元素
    audioElement = new Audio();
    audioElement.volume = 0.8;

    // 加载谱面
    if ($playerStore.currentSong?.sm_file) {
      await playerStore.loadChart($playerStore.currentSong.sm_file);

      // 加载音频
      if ($playerStore.currentSong.audio_file) {
        try {
          const audioUrl = convertFileSrc($playerStore.currentSong.audio_file);
          console.log('Loading audio:', audioUrl);
          audioElement.src = audioUrl;
          await audioElement.load();
        } catch (e) {
          console.error('Failed to load audio:', e);
        }
      }

      // 开始游戏循环
      initCanvas();
      startGameLoop();
    }
  });

  onDestroy(() => {
    if (animationFrame) {
      cancelAnimationFrame(animationFrame);
    }
    if (audioElement) {
      audioElement.pause();
      audioElement.src = '';
      audioElement = null;
    }
  });

  // 初始化Canvas
  function initCanvas() {
    if (!canvas) return;

    ctx = canvas.getContext('2d');
    resizeCanvas();

    window.addEventListener('resize', resizeCanvas);
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
  }

  // 调整Canvas大小
  function resizeCanvas() {
    if (!canvas) return;

    const rect = canvas.parentElement?.getBoundingClientRect();
    if (rect) {
      canvas.width = rect.width;
      canvas.height = rect.height;
    }
  }

  // 开始游戏循环
  function startGameLoop() {
    playerStore.setGameState('playing');
    lastTime = performance.now();

    // 开始播放音频
    if (audioElement) {
      audioElement.currentTime = $playerStore.offset;
      audioElement.play().catch(e => console.error('Failed to play audio:', e));
    }

    animationFrame = requestAnimationFrame(gameLoop);
  }

  // 游戏主循环
  function gameLoop(timestamp: number) {
    const dt = (timestamp - lastTime) / 1000;
    lastTime = timestamp;

    if ($playerStore.gameState === 'playing') {
      // 从音频元素同步时间
      if (audioElement && !audioElement.paused) {
        playerStore.setCurrentTime(audioElement.currentTime);
      }

      update(dt);
      render();
    }

    animationFrame = requestAnimationFrame(gameLoop);
  }

  // 更新游戏状态
  function update(dt: number) {
    // 更新轨道光效
    for (let i = 0; i < TRACK_COUNT; i++) {
      if (trackLights[i] > 0) {
        trackLights[i] = Math.max(0, trackLights[i] - dt * 3);
      }
    }

    // 更新判定显示
    if (judgeDisplay && judgeDisplay.time > 0) {
      judgeDisplay.time -= dt;
      if (judgeDisplay.time <= 0) {
        judgeDisplay = null;
      }
    }

    // 检查MISS
    checkMissedArrows($playerStore.currentTime);

    // 检查游戏结束
    const chartData = $playerStore.chartData;
    if (chartData && $playerStore.currentTime >= chartData.total_duration) {
      endGame();
    }
  }

  // 检查错过的箭头
  function checkMissedArrows(currentTime: number) {
    const chartData = $playerStore.chartData;
    if (!chartData) return;

    for (let i = 0; i < chartData.arrows.length; i++) {
      if (processedArrows.has(i)) continue;

      const arrow = chartData.arrows[i];
      if (arrow.start_sec < currentTime - JUDGE_WINDOWS.BAD) {
        processedArrows.add(i);
        playerStore.addJudge('Miss');
        showJudge('MISS');
      }
    }
  }

  // 渲染
  function render() {
    if (!ctx || !canvas) return;

    const width = canvas.width;
    const height = canvas.height;

    // 清除画布
    ctx.clearRect(0, 0, width, height);

    // 布局参数（最大化轨道区域）
    const headerHeight = 50;  // 减少顶部高度
    const footerHeight = 30;  // 减少底部高度
    const margin = 20;
    const trackCount = 5;

    // 轨道总宽度
    const trackTotalW = Math.min(560, width - 320);  // 留更多空间给右侧
    const trackTotalWClamped = Math.max(400, trackTotalW);
    const trackStartX = (width - trackTotalWClamped) / 2 - 80;  // 稍微左偏
    const singleTrackW = trackTotalWClamped / trackCount;

    // 判定线位置：窗口高度的15%，更靠上让玩家有更多反应时间
    const judgeY = Math.floor(height * 0.15);

    const topY = 10;
    const bottomY = height - footerHeight;

    // 绘制背景
    drawBackground(width, height);

    // 绘制轨道背景
    drawTracks(trackStartX, topY, trackTotalWClamped, bottomY - topY, singleTrackW, trackCount);

    // 绘制判定线
    drawJudgeLine(trackStartX - 10, trackTotalWClamped + 20, judgeY);

    // 绘制判定区
    drawReceptors(trackStartX, singleTrackW, judgeY);

    // 绘制箭头
    drawArrows(trackStartX, singleTrackW, judgeY, bottomY, topY);

    // 绘制判定显示
    if (judgeDisplay) {
      drawJudgeDisplay(trackStartX + trackTotalWClamped / 2, judgeY);
    }

    // 绘制右侧信息面板
    drawRightPanel(trackStartX + trackTotalWClamped + 20, 20, width, height);
  }

  // 绘制背景
  function drawBackground(width: number, height: number) {
    if (!ctx) return;

    // 渐变背景
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, '#0c0c19');
    gradient.addColorStop(1, '#19233c');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);

    // 网格线
    ctx.strokeStyle = 'rgba(40, 80, 150, 0.1)';
    ctx.lineWidth = 1;
    for (let x = 0; x < width; x += 60) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = 0; y < height; y += 60) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }
  }

  // 绘制轨道
  function drawTracks(startX: number, startY: number, totalWidth: number, height: number, singleWidth: number, count: number) {
    if (!ctx) return;

    for (let i = 0; i < count; i++) {
      const x = startX + i * singleWidth;
      const alpha = 80 + (i % 2) * 15;

      // 轨道底色（带透明度）
      ctx.fillStyle = `rgba(25, 25, 35, ${alpha / 255})`;
      ctx.beginPath();
      ctx.roundRect(x + 2, startY, singleWidth - 4, height, 8);
      ctx.fill();

      // 轨道边框
      ctx.strokeStyle = 'rgba(50, 50, 65, 0.8)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect(x + 2, startY, singleWidth - 4, height, 8);
      ctx.stroke();
    }
  }

  // 绘制判定线
  function drawJudgeLine(x: number, width: number, y: number) {
    if (!ctx) return;

    // 主线
    ctx.strokeStyle = 'rgba(200, 200, 210, 0.8)';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + width, y);
    ctx.stroke();

    // 光晕
    const glowGradient = ctx.createLinearGradient(x, y - 10, x + width, y + 10);
    glowGradient.addColorStop(0, 'rgba(255, 255, 255, 0)');
    glowGradient.addColorStop(0.5, 'rgba(255, 255, 255, 0.3)');
    glowGradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
    ctx.fillStyle = glowGradient;
    ctx.fillRect(x, y - 5, width, 10);
  }

  // 绘制判定区
  function drawReceptors(startX: number, trackWidth: number, judgeY: number) {
    if (!ctx) return;

    const noteskin = getNoteskin();

    for (let i = 0; i < TRACK_COUNT; i++) {
      const x = startX + i * trackWidth + trackWidth / 2;
      // 判定区大小：轨道宽度的 0.55 倍（匹配 Python 版本）
      // 传入总宽度的一半作为 halfSize
      const receptorSize = trackWidth * 0.55 / 2;
      const light = trackLights[i];
      const direction = TRACK_DIRECTION[i];
      const pressed = keyPressed[i];

      // 光效
      if (light > 0) {
        const gradient = ctx.createRadialGradient(x, judgeY, 0, x, judgeY, trackWidth * 0.5);
        gradient.addColorStop(0, `rgba(255, 235, 185, ${light * 0.6})`);
        gradient.addColorStop(1, 'rgba(255, 235, 185, 0)');
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(x, judgeY, trackWidth * 0.5, 0, Math.PI * 2);
        ctx.fill();
      }

      // 使用 noteskin 绘制判定区
      noteskin.drawReceptor(ctx, direction, x, judgeY, receptorSize, pressed);
    }
  }

  // 绘制箭头
  function drawArrows(startX: number, trackWidth: number, judgeY: number, bottomY: number, topY: number) {
    if (!ctx || !$playerStore.chartData) return;

    const currentTime = $playerStore.currentTime;
    const arrows = $playerStore.chartData.arrows;
    const canvasHeight = canvas.height;
    const noteskin = getNoteskin();

    // 计算可见时间范围
    const visibleSec = (bottomY - judgeY) / scrollSpeed;

    // 动画帧（简单的时间动画）
    const frame = Math.floor(currentTime * 8) % 6;

    // 箭头大小：轨道宽度的 0.60 倍（匹配 Python 版本）
    const arrowSize = trackWidth * 0.30; // 0.60 / 2 因为 drawTapArrow 用 size 作为半径

    for (let i = 0; i < arrows.length; i++) {
      if (processedArrows.has(i)) continue;

      const arrow = arrows[i];
      const y = judgeY + (arrow.start_sec - currentTime) * scrollSpeed;

      // 只绘制可见区域的箭头
      if (y < topY - 50 || y > bottomY + 100) continue;

      const x = startX + arrow.track_idx * trackWidth + trackWidth / 2;
      const direction = TRACK_DIRECTION[arrow.track_idx];

      if (Math.abs(arrow.end_sec - arrow.start_sec) < 0.001) {
        // 点按箭头 - 只绘制判定线以下的
        if (y >= judgeY - 100) {
          noteskin.drawTapArrow(ctx, direction, x, y, arrowSize, frame);
        }
      } else {
        // 长按箭头
        const endY = judgeY + (arrow.end_sec - currentTime) * scrollSpeed;
        drawHoldArrow(noteskin, direction, x, y, endY, arrowSize, judgeY, canvasHeight, frame, trackWidth);
      }
    }
  }

  // 绘制长按箭头
  function drawHoldArrow(
    noteskin: ReturnType<typeof getNoteskin>,
    direction: Direction,
    x: number,
    startY: number,
    endY: number,
    arrowSize: number,
    judgeY: number,
    canvasHeight: number,
    frame: number,
    trackWidth: number
  ) {
    if (!ctx) return;

    const clippedStartY = Math.max(startY, judgeY);
    const clippedEndY = Math.min(endY, canvasHeight - 50);

    if (clippedEndY <= clippedStartY) return;

    // 长按身体宽度：轨道宽度的 0.50 倍（匹配 Python 版本）
    const bodyWidth = trackWidth * 0.50;

    // 绘制长按身体
    noteskin.drawHoldBody(ctx, direction, x, clippedStartY, bodyWidth, clippedEndY - clippedStartY, frame);

    // 头部
    if (startY >= judgeY - 100 && startY < canvasHeight - 50) {
      noteskin.drawTapArrow(ctx, direction, x, startY, arrowSize, frame);
    }

    // 尾部
    if (endY >= judgeY && endY <= canvasHeight - 50) {
      noteskin.drawHoldTail(ctx, direction, x, endY, trackWidth * 0.275, frame);
    }
  }

  // 绘制判定显示
  function drawJudgeDisplay(centerX: number, judgeY: number) {
    if (!ctx || !judgeDisplay) return;

    const alpha = Math.min(1, judgeDisplay.time / 0.3);
    let color: string;

    switch (judgeDisplay.result) {
      case 'PERFECT': color = '#32ff64'; break;
      case 'GOOD': color = '#ffdc32'; break;
      case 'BAD': color = '#ff5050'; break;
      case 'MISS': color = '#969696'; break;
      default: color = '#ffffff';
    }

    ctx.font = 'bold 48px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = color;
    ctx.globalAlpha = alpha;
    ctx.fillText(judgeDisplay.result, centerX, judgeY + 80);
    ctx.globalAlpha = 1;
  }

  // 绘制右侧信息面板
  function drawRightPanel(panelX: number, panelY: number, canvasWidth: number, canvasHeight: number) {
    if (!ctx) return;

    const panelW = Math.min(180, canvasWidth - panelX - 20);
    const panelH = canvasHeight - 40;

    // 面板背景
    ctx.fillStyle = 'rgba(15, 15, 22, 0.85)';
    ctx.beginPath();
    ctx.roundRect(panelX, panelY, panelW, panelH, 12);
    ctx.fill();

    ctx.strokeStyle = 'rgba(50, 50, 70, 0.6)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(panelX, panelY, panelW, panelH, 12);
    ctx.stroke();

    let y = panelY + 20;

    // 歌曲标题
    const title = $playerStore.chartData?.info.title || $playerStore.currentSong?.display_name || 'Unknown';
    ctx.font = 'bold 14px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.fillStyle = '#f0f0fa';
    ctx.textAlign = 'left';
    ctx.fillText(title.slice(0, 15), panelX + 10, y);
    y += 25;

    // 时间
    const currentTime = formatTime($playerStore.currentTime);
    const totalTime = formatTime($playerStore.chartData?.total_duration || 0);
    ctx.font = '13px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.fillStyle = '#96a0b0';
    ctx.fillText(`${currentTime} / ${totalTime}`, panelX + 10, y);
    y += 20;

    // 状态
    const statusStr = $playerStore.gameState === 'playing' ? '▶ 播放中' : '⏸ 已暂停';
    const statusColor = $playerStore.gameState === 'playing' ? '#64ff96' : '#ffc850';
    ctx.fillStyle = statusColor;
    ctx.fillText(statusStr, panelX + 10, y);
    y += 30;

    // 分隔线
    ctx.strokeStyle = 'rgba(80, 80, 100, 0.5)';
    ctx.beginPath();
    ctx.moveTo(panelX + 10, y);
    ctx.lineTo(panelX + panelW - 10, y);
    ctx.stroke();
    y += 20;

    // 统计标题
    ctx.font = 'bold 14px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.fillStyle = '#c8c8d8';
    ctx.fillText('统计', panelX + 10, y);
    y += 25;

    // 各判定数量
    const stats = [
      { label: 'PERFECT', count: $playerStore.stats.perfect, color: '#32ff64' },
      { label: 'GOOD', count: $playerStore.stats.good, color: '#ffdc32' },
      { label: 'BAD', count: $playerStore.stats.bad, color: '#ff6464' },
      { label: 'MISS', count: $playerStore.stats.miss, color: '#8080a0' },
    ];

    ctx.font = '12px -apple-system, BlinkMacSystemFont, sans-serif';
    stats.forEach((stat) => {
      ctx.fillStyle = stat.color;
      ctx.fillText(stat.label, panelX + 10, y);
      ctx.fillStyle = '#dcdce8';
      ctx.textAlign = 'right';
      ctx.fillText(stat.count.toString(), panelX + panelW - 10, y);
      ctx.textAlign = 'left';
      y += 22;
    });

    y += 10;

    // 分隔线
    ctx.strokeStyle = 'rgba(80, 80, 100, 0.5)';
    ctx.beginPath();
    ctx.moveTo(panelX + 10, y);
    ctx.lineTo(panelX + panelW - 10, y);
    ctx.stroke();
    y += 25;

    // 分数
    ctx.font = 'bold 28px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.fillStyle = '#ffdc32';
    ctx.textAlign = 'center';
    ctx.fillText($playerStore.score.toString(), panelX + panelW / 2, y);
    y += 35;

    // 连击
    const comboColor = $playerStore.combo > 10 ? '#64b4ff' : '#a0a0b0';
    ctx.font = 'bold 18px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.fillStyle = comboColor;
    ctx.fillText(`${$playerStore.combo} COMBO`, panelX + panelW / 2, y);
    y += 25;

    // 最大连击
    ctx.font = '12px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.fillStyle = '#8080a0';
    ctx.fillText(`Max: ${$playerStore.maxCombo}`, panelX + panelW / 2, y);
    y += 30;

    // 速度和偏移
    ctx.textAlign = 'left';
    ctx.font = '12px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.fillStyle = '#606080';
    ctx.fillText(`速度: ${Math.round(scrollSpeed)}`, panelX + 10, y);
    y += 18;
    ctx.fillText(`Offset: ${($playerStore.offset).toFixed(2)}s`, panelX + 10, y);
    y += 25;

    // 按键提示
    ctx.font = '11px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.fillStyle = '#505070';
    ctx.textAlign = 'center';
    const tips = [
      'Q/左上 W/右上 S/中间',
      'Z/左下 C/右下',
      '空格:暂停 R:重玩',
      '←/→:快退快进 [/]:速度',
      '-/=:Offset Esc:返回'
    ];
    tips.forEach((tip) => {
      ctx.fillText(tip, panelX + panelW / 2, y);
      y += 16;
    });
  }

  // 格式化时间
  function formatTime(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }

  // 显示判定
  function showJudge(result: string) {
    judgeDisplay = { result, time: 0.8 };
  }

  // 键盘按下
  function handleKeyDown(event: KeyboardEvent) {
    const trackIdx = KEY_MAP[event.code];
    if (trackIdx !== undefined && !keyPressed[trackIdx]) {
      keyPressed[trackIdx] = true;
      playerStore.setKeyPressed(trackIdx, true);

      // 判定
      judge(trackIdx);

      event.preventDefault();
    }

    // 功能键
    if (event.code === 'Space') {
      togglePause();
      event.preventDefault();
    } else if (event.code === 'Escape') {
      if ($playerStore.gameState === 'playing') {
        togglePause();
      } else if ($playerStore.gameState === 'paused') {
        onback?.();
      }
    } else if (event.code === 'KeyR') {
      restartGame();
    } else if (event.code === 'BracketLeft') {
      // 降低速度
      playerStore.setScrollSpeed(Math.max(200, $playerStore.scrollSpeed - 60));
    } else if (event.code === 'BracketRight') {
      // 增加速度
      playerStore.setScrollSpeed(Math.min(2000, $playerStore.scrollSpeed + 60));
    } else if (event.code === 'KeyT') {
      // 切换 tick_per_beat (96, 48, 192) - 暂时显示提示
      console.log('[Player] T key pressed - tick_per_beat toggle not yet implemented');
    } else if (event.code === 'KeyM') {
      // 切换映射 - 暂时显示提示
      console.log('[Player] M key pressed - mapping toggle not yet implemented');
    } else if (event.code === 'Minus' || event.code === 'NumpadSubtract') {
      // 减少 offset
      playerStore.setOffset($playerStore.offset - 0.02);
    } else if (event.code === 'Equal' || event.code === 'NumpadAdd') {
      // 增加 offset
      playerStore.setOffset($playerStore.offset + 0.02);
    } else if (event.code === 'ArrowLeft') {
      // 快退 5 秒
      seekTo($playerStore.currentTime - 5);
    } else if (event.code === 'ArrowRight') {
      // 快进 5 秒
      seekTo($playerStore.currentTime + 5);
    }
  }

  // 键盘释放
  function handleKeyUp(event: KeyboardEvent) {
    const trackIdx = KEY_MAP[event.code];
    if (trackIdx !== undefined) {
      keyPressed[trackIdx] = false;
      playerStore.setKeyPressed(trackIdx, false);
    }
  }

  // 判定逻辑
  function judge(trackIdx: number) {
    const chartData = $playerStore.chartData;
    const currentTime = $playerStore.currentTime;
    if (!chartData) return;

    let bestIdx = -1;
    let bestDiff = Infinity;

    for (let i = 0; i < chartData.arrows.length; i++) {
      if (processedArrows.has(i)) continue;

      const arrow = chartData.arrows[i];
      if (arrow.track_idx !== trackIdx) continue;

      const diff = Math.abs(arrow.start_sec - currentTime);
      if (diff <= JUDGE_WINDOWS.BAD && diff < bestDiff) {
        bestDiff = diff;
        bestIdx = i;
      }
    }

    if (bestIdx >= 0) {
      processedArrows.add(bestIdx);

      // 触发光效
      trackLights[bestIdx] = 1;

      // 判定结果
      let result: 'Perfect' | 'Good' | 'Bad';
      if (bestDiff <= JUDGE_WINDOWS.PERFECT) {
        result = 'Perfect';
      } else if (bestDiff <= JUDGE_WINDOWS.GOOD) {
        result = 'Good';
      } else {
        result = 'Bad';
      }

      playerStore.addJudge(result);
      showJudge(result.toUpperCase());
    }
  }

  // 暂停/继续
  function togglePause() {
    if ($playerStore.gameState === 'playing') {
      if (audioElement) {
        audioElement.pause();
      }
      playerStore.setGameState('paused');
    } else if ($playerStore.gameState === 'paused') {
      if (audioElement) {
        audioElement.play().catch(e => console.error('Failed to resume audio:', e));
      }
      playerStore.setGameState('playing');
    }
  }

  // 重新开始
  async function restartGame() {
    playerStore.resetGame();
    processedArrows.clear();

    if (audioElement && $playerStore.currentSong?.audio_file) {
      audioElement.currentTime = $playerStore.offset;
      await audioElement.play().catch(e => console.error('Failed to play audio:', e));
    }

    playerStore.setGameState('playing');
  }

  // 跳转到指定时间
  function seekTo(time: number) {
    const duration = $playerStore.chartData?.total_duration || 0;
    const newTime = Math.max(0, Math.min(duration, time));

    playerStore.setCurrentTime(newTime);

    if (audioElement) {
      const audioTime = newTime + $playerStore.offset;
      audioElement.currentTime = Math.max(0, audioTime);
    }

    // 重置处理过的箭头
    processedArrows.clear();
  }

  // 结束游戏
  function endGame() {
    playerStore.setGameState('finished');
    if (audioElement) {
      audioElement.pause();
    }
  }

  // 返回选歌
  function handleBack() {
    onback?.();
  }
</script>

<div class="player-view w-full h-full flex flex-col">
  <!-- Canvas -->
  <div class="flex-1 relative">
    <canvas bind:this={canvas} class="w-full h-full"></canvas>

    <!-- 暂停菜单 -->
    {#if $playerStore.gameState === 'paused'}
      <div class="pause-overlay absolute inset-0 flex items-center justify-center bg-black/50">
        <div class="glass-panel p-8 text-center scale-in">
          <h2 class="text-2xl font-bold text-text-white mb-6">暂停</h2>
          <div class="flex flex-col gap-3">
            <GlassButton text="继续" onclick={togglePause} />
            <GlassButton text="重新开始" onclick={restartGame} />
            <GlassButton text="返回选歌" onclick={handleBack} />
          </div>
        </div>
      </div>
    {/if}

    <!-- 结算界面 -->
    {#if $playerStore.gameState === 'finished'}
      <div class="result-overlay absolute inset-0 flex items-center justify-center bg-black/70">
        <div class="glass-panel p-10 text-center scale-in">
          <h2 class="text-4xl font-bold mb-2" style="color: {$grade === 'S' ? '#ffdc32' : $grade === 'AAA' ? '#ffdc32' : '#f0f0fa'}">
            {$grade}
          </h2>
          <p class="text-2xl text-text-white mb-6">{$playerStore.score}</p>

          <div class="grid grid-cols-2 gap-4 mb-6 text-left">
            <div>
              <span class="text-perfect">PERFECT</span>
              <span class="text-text-white ml-2">{$playerStore.stats.perfect}</span>
            </div>
            <div>
              <span class="text-good">GOOD</span>
              <span class="text-text-white ml-2">{$playerStore.stats.good}</span>
            </div>
            <div>
              <span class="text-bad">BAD</span>
              <span class="text-text-white ml-2">{$playerStore.stats.bad}</span>
            </div>
            <div>
              <span class="text-miss">MISS</span>
              <span class="text-text-white ml-2">{$playerStore.stats.miss}</span>
            </div>
          </div>

          <p class="text-text-gray mb-2">Max Combo: {$playerStore.maxCombo}</p>
          <p class="text-text-gray mb-6">Accuracy: {($accuracy * 100).toFixed(1)}%</p>

          <div class="flex gap-4 justify-center">
            <GlassButton text="重新开始" onclick={restartGame} />
            <GlassButton text="返回选歌" onclick={handleBack} />
          </div>
        </div>
      </div>
    {/if}
  </div>

  <!-- 底部提示 -->
  <footer class="glass-panel m-4 p-3 text-center text-text-dark text-sm">
    Z/左下 | Q/左上 | S/中间 | E/右上 | C/右下 |
    空格:暂停 | R:重玩 | [ ]:速度 | Esc:返回
  </footer>
</div>

<style>
  .pause-overlay,
  .result-overlay {
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
  }
</style>
