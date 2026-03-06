<script lang="ts">
  import { onMount, onDestroy } from 'svelte';

  interface Props {
    bars?: number[];
    height?: number;
    width?: number;
    gap?: number;
    colors?: string[];
  }

  let { bars = [], height = 100, width = 200, gap = 2, colors = ['#64b4ff', '#b464ff', '#ff64a0', '#ff9632', '#64ff96'] }: Props = $props();

  let canvas: HTMLCanvasElement;
  let ctx: CanvasRenderingContext2D | null = null;
  let animationFrame: number | null = null;
  let barHeights: number[] = [];
  let targetHeights: number[] = [];

  // 更新数组当bars变化时
  $effect(() => {
    const barCount = bars.length || 32;
    if (barHeights.length !== barCount) {
      barHeights = new Array(barCount).fill(0);
      targetHeights = new Array(barCount).fill(0);
    }
    // 从外部bars更新目标高度
    if (bars.length > 0) {
      targetHeights = [...bars];
    }
  });

  onMount(() => {
    ctx = canvas.getContext('2d');
    animate();
  });

  onDestroy(() => {
    if (animationFrame) {
      cancelAnimationFrame(animationFrame);
    }
  });

  function animate() {
    if (!ctx) return;

    const barCount = bars.length || 32;

    // 如果没有外部数据，使用随机动画
    if (bars.length === 0) {
      for (let i = 0; i < barCount; i++) {
        const freqFactor = 1 - (i / barCount) * 0.5;
        const baseIntensity = Math.random() * 0.3;
        targetHeights[i] = baseIntensity * freqFactor;
      }
    }

    // 平滑过渡
    const smoothing = 0.3;
    for (let i = 0; i < barCount; i++) {
      if (barHeights[i] !== undefined && targetHeights[i] !== undefined) {
        barHeights[i] += (targetHeights[i] - barHeights[i]) * smoothing;
        barHeights[i] = Math.max(0, Math.min(1, barHeights[i]));
      }
    }

    // 绘制
    draw(barCount);

    animationFrame = requestAnimationFrame(animate);
  }

  function draw(barCount: number) {
    if (!ctx) return;

    ctx.clearRect(0, 0, width, height);

    const barWidth = (width - gap * (barCount - 1)) / barCount;

    for (let i = 0; i < barCount; i++) {
      const barHeight = (barHeights[i] || 0) * height;
      const x = i * (barWidth + gap);
      const y = height - barHeight;
      const colorIndex = i % colors.length;

      if (barHeight > 1) {
        // 渐变
        const gradient = ctx.createLinearGradient(x, y + barHeight, x, y);
        gradient.addColorStop(0, colors[colorIndex] + '80'); // 50% alpha at bottom
        gradient.addColorStop(1, colors[colorIndex]);

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.roundRect(x, y, barWidth, barHeight, 2);
        ctx.fill();
      }
    }
  }
</script>

<canvas
  bind:this={canvas}
  {width}
  {height}
  class="spectrum-bars"
></canvas>

<style>
  .spectrum-bars {
    display: block;
    opacity: 0.9;
  }
</style>
