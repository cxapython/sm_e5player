/**
 * Noteskin 资源加载和管理
 * 支持 StepMania 风格的箭头皮肤
 */

import { convertFileSrc } from '@tauri-apps/api/core';

// 方向定义（5轨道）
export type Direction = 'DownLeft' | 'UpLeft' | 'Center' | 'UpRight' | 'DownRight';

// 箭头类型
export type ArrowType = 'tap' | 'hold_body' | 'hold_tail' | 'receptor' | 'roll';

// 图片缓存
interface CachedImage {
  image: HTMLImageElement;
  cols: number;
  rows: number;
  frameWidth: number;
  frameHeight: number;
}

// 皮肤资源
class NoteskinResource {
  private basePath: string;
  private cache: Map<string, CachedImage> = new Map();
  private loaded: boolean = false;

  constructor(basePath: string) {
    this.basePath = basePath;
  }

  // 加载所有皮肤资源
  async load(): Promise<void> {
    if (this.loaded) return;

    // 只加载左侧和中间方向的图片（右侧通过翻转实现）
    const directions: Direction[] = ['DownLeft', 'UpLeft', 'Center'];

    // 加载所有需要的图片
    const loadPromises: Promise<void>[] = [];

    for (const dir of directions) {
      // 点按箭头 3x2
      loadPromises.push(this.loadImage(`${dir} Tap Note`, `${dir} Tap Note (doubleres) 3x2.png`, 3, 2));

      // 长按身体 6x1
      loadPromises.push(this.loadImage(`${dir} Hold Body`, `${dir} Hold Body active (doubleres) 6x1.png`, 6, 1));

      // 长按尾部 6x1
      loadPromises.push(this.loadImage(`${dir} Hold Tail`, `${dir} Hold BottomCap active (doubleres) 6x1.png`, 6, 1));

      // Roll 箭头 3x2
      loadPromises.push(this.loadImage(`${dir} Roll`, `${dir} Roll Head Active (doubleres) 3x2.png`, 3, 2));

      // 判定区 1x3
      loadPromises.push(this.loadImage(`${dir} Receptor`, `${dir} Ready Receptor (doubleres) 1x3.png`, 1, 3));
    }

    await Promise.all(loadPromises);
    this.loaded = true;
    console.log('[Noteskin] 加载完成，缓存:', Array.from(this.cache.keys()));
  }

  // 加载单个图片
  private async loadImage(key: string, filename: string, cols: number, rows: number): Promise<void> {
    return new Promise((resolve) => {
      const img = new Image();
      const fullPath = `${this.basePath}/${filename}`;
      const url = convertFileSrc(fullPath);

      img.onload = () => {
        this.cache.set(key, {
          image: img,
          cols,
          rows,
          frameWidth: img.width / cols,
          frameHeight: img.height / rows,
        });
        console.log(`[Noteskin] 加载成功: ${filename} (${img.width}x${img.height}, frames: ${cols}x${rows})`);
        resolve();
      };

      img.onerror = (e) => {
        console.warn(`[Noteskin] 加载失败: ${filename}`, e);
        resolve(); // 即使失败也继续
      };

      img.src = url;
    });
  }

  // 获取图片
  private getImage(key: string): CachedImage | null {
    return this.cache.get(key) || null;
  }

  // 绘制点按箭头
  drawTapArrow(
    ctx: CanvasRenderingContext2D,
    direction: Direction,
    x: number,
    y: number,
    halfSize: number,
    frame: number = 0
  ): void {
    // 对于右边方向，翻转左边
    let actualDir = direction;
    let flip = false;

    if (direction === 'UpRight') {
      actualDir = 'UpLeft';
      flip = true;
    } else if (direction === 'DownRight') {
      actualDir = 'DownLeft';
      flip = true;
    }

    const key = `${actualDir} Tap Note`;
    const cached = this.getImage(key);

    // halfSize 是箭头总宽度的一半
    const totalSize = halfSize * 2;

    if (cached) {
      const col = frame % cached.cols;
      const row = Math.floor(frame / cached.cols) % cached.rows;

      ctx.save();
      if (flip) {
        ctx.translate(x, y);
        ctx.scale(-1, 1);
        ctx.translate(-x, -y);
      }

      ctx.drawImage(
        cached.image,
        col * cached.frameWidth,
        row * cached.frameHeight,
        cached.frameWidth,
        cached.frameHeight,
        x - halfSize,
        y - halfSize,
        totalSize,
        totalSize
      );
      ctx.restore();
    } else {
      // 回退到简单圆形
      this.drawFallbackArrow(ctx, x, y, halfSize, direction);
    }
  }

  // 绘制长按身体
  drawHoldBody(
    ctx: CanvasRenderingContext2D,
    direction: Direction,
    x: number,
    y: number,
    width: number,
    height: number,
    frame: number = 0
  ): void {
    // 对于右边方向，翻转左边
    let actualDir = direction;
    let flip = false;

    if (direction === 'UpRight') {
      actualDir = 'UpLeft';
      flip = true;
    } else if (direction === 'DownRight') {
      actualDir = 'DownLeft';
      flip = true;
    }

    const key = `${actualDir} Hold Body`;
    const cached = this.getImage(key);

    if (cached && height > 0) {
      const col = frame % cached.cols;

      ctx.save();
      if (flip) {
        ctx.translate(x, y);
        ctx.scale(-1, 1);
        ctx.translate(-x, -y);
      }

      // 平铺绘制长按身体（类似 Python 版本）
      const singleHeight = cached.frameHeight * (width / cached.frameWidth);
      let currentY = y;

      while (currentY < y + height) {
        const remainingHeight = (y + height) - currentY;
        const drawHeight = Math.min(singleHeight, remainingHeight);

        ctx.drawImage(
          cached.image,
          col * cached.frameWidth,
          0,
          cached.frameWidth,
          cached.frameHeight * (drawHeight / singleHeight),
          x - width / 2,
          currentY,
          width,
          drawHeight
        );
        currentY += singleHeight;
      }
      ctx.restore();
    } else {
      // 回退
      this.drawFallbackHoldBody(ctx, x, y, width, height);
    }
  }

  // 绘制长按尾部
  drawHoldTail(
    ctx: CanvasRenderingContext2D,
    direction: Direction,
    x: number,
    y: number,
    halfSize: number,
    frame: number = 0
  ): void {
    // 对于右边方向，翻转左边
    let actualDir = direction;
    let flip = false;

    if (direction === 'UpRight') {
      actualDir = 'UpLeft';
      flip = true;
    } else if (direction === 'DownRight') {
      actualDir = 'DownLeft';
      flip = true;
    }

    const key = `${actualDir} Hold Tail`;
    const cached = this.getImage(key);

    const totalSize = halfSize * 2;

    if (cached) {
      const col = frame % cached.cols;

      ctx.save();
      if (flip) {
        ctx.translate(x, y);
        ctx.scale(-1, 1);
        ctx.translate(-x, -y);
      }

      ctx.drawImage(
        cached.image,
        col * cached.frameWidth,
        0,
        cached.frameWidth,
        cached.frameHeight,
        x - halfSize,
        y - halfSize * 0.3,
        totalSize,
        halfSize * 0.6
      );
      ctx.restore();
    } else {
      // 回退
      this.drawFallbackTail(ctx, x, y, halfSize);
    }
  }

  // 绘制判定区
  drawReceptor(
    ctx: CanvasRenderingContext2D,
    direction: Direction,
    x: number,
    y: number,
    halfSize: number,
    pressed: boolean = false
  ): void {
    // 对于右边方向，翻转左边
    let actualDir = direction;
    let flip = false;

    if (direction === 'UpRight') {
      actualDir = 'UpLeft';
      flip = true;
    } else if (direction === 'DownRight') {
      actualDir = 'DownLeft';
      flip = true;
    }

    const key = `${actualDir} Receptor`;
    const cached = this.getImage(key);

    // halfSize 是判定区总宽度的一半
    const totalSize = halfSize * 2;

    if (cached) {
      const row = pressed ? 2 : 0; // 1x3: 第0行是普通，第2行是按下

      ctx.save();
      if (flip) {
        ctx.translate(x, y);
        ctx.scale(-1, 1);
        ctx.translate(-x, -y);
      }

      ctx.drawImage(
        cached.image,
        0,
        row * cached.frameHeight,
        cached.frameWidth,
        cached.frameHeight,
        x - halfSize,
        y - halfSize,
        totalSize,
        totalSize
      );
      ctx.restore();
    } else {
      // 回退
      this.drawFallbackReceptor(ctx, x, y, halfSize, pressed);
    }
  }

  // 绘制 Roll 箭头
  drawRollArrow(
    ctx: CanvasRenderingContext2D,
    direction: Direction,
    x: number,
    y: number,
    halfSize: number,
    frame: number = 0
  ): void {
    // 对于右边方向，翻转左边
    let actualDir = direction;
    let flip = false;

    if (direction === 'UpRight') {
      actualDir = 'UpLeft';
      flip = true;
    } else if (direction === 'DownRight') {
      actualDir = 'DownLeft';
      flip = true;
    }

    const key = `${actualDir} Roll`;
    const cached = this.getImage(key);

    const totalSize = halfSize * 2;

    if (cached) {
      const col = frame % cached.cols;
      const row = Math.floor(frame / cached.cols) % cached.rows;

      ctx.save();
      if (flip) {
        ctx.translate(x, y);
        ctx.scale(-1, 1);
        ctx.translate(-x, -y);
      }

      ctx.drawImage(
        cached.image,
        col * cached.frameWidth,
        row * cached.frameHeight,
        cached.frameWidth,
        cached.frameHeight,
        x - halfSize,
        y - halfSize,
        totalSize,
        totalSize
      );
      ctx.restore();
    } else {
      // 回退到点按箭头
      this.drawTapArrow(ctx, direction, x, y, halfSize, frame);
    }
  }

  // 回退绘制：简单箭头
  private drawFallbackArrow(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    size: number,
    direction: Direction
  ): void {
    ctx.save();

    // 根据方向旋转
    const angles: Record<Direction, number> = {
      'DownLeft': Math.PI * 0.75,
      'UpLeft': Math.PI * 0.25,
      'Center': 0,
      'UpRight': -Math.PI * 0.25,
      'DownRight': -Math.PI * 0.75,
    };

    ctx.translate(x, y);
    if (direction !== 'Center') {
      ctx.rotate(angles[direction]);
    }

    // 绘制箭头形状
    ctx.fillStyle = 'rgba(240, 240, 245, 0.95)';
    ctx.beginPath();
    ctx.moveTo(0, -size);
    ctx.lineTo(size * 0.7, 0);
    ctx.lineTo(size * 0.3, 0);
    ctx.lineTo(size * 0.3, size);
    ctx.lineTo(-size * 0.3, size);
    ctx.lineTo(-size * 0.3, 0);
    ctx.lineTo(-size * 0.7, 0);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = 'rgba(100, 180, 255, 0.9)';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.restore();
  }

  // 回退绘制：长按身体
  private drawFallbackHoldBody(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number
  ): void {
    const gradient = ctx.createLinearGradient(x, y, x, y + height);
    gradient.addColorStop(0, 'rgba(180, 180, 200, 0.9)');
    gradient.addColorStop(1, 'rgba(140, 140, 160, 0.75)');

    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.roundRect(x - width / 2, y, width, height, 4);
    ctx.fill();

    ctx.strokeStyle = 'rgba(100, 100, 120, 0.6)';
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  // 回退绘制：长按尾部
  private drawFallbackTail(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    size: number
  ): void {
    ctx.fillStyle = 'rgba(160, 160, 180, 0.9)';
    ctx.beginPath();
    ctx.roundRect(x - size * 0.4, y - size * 0.25, size * 0.8, size * 0.25, 3);
    ctx.fill();
  }

  // 回退绘制：判定区
  private drawFallbackReceptor(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    size: number,
    pressed: boolean
  ): void {
    const radius = pressed ? size * 0.4 : size * 0.5;
    const color = pressed ? 'rgba(80, 80, 100, 0.9)' : 'rgba(60, 60, 80, 0.8)';

    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = 'rgba(100, 100, 120, 0.8)';
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  // 是否已加载
  isLoaded(): boolean {
    return this.loaded;
  }
}

// 默认 noteskin 路径
const DEFAULT_NOTESKIN_PATH = '/Users/chennan/Downloads/sm_e5player/noteskin';

// 全局 noteskin 实例
let noteskinInstance: NoteskinResource | null = null;

// 获取 noteskin 实例
export function getNoteskin(): NoteskinResource {
  if (!noteskinInstance) {
    noteskinInstance = new NoteskinResource(DEFAULT_NOTESKIN_PATH);
  }
  return noteskinInstance;
}

// 初始化 noteskin
export async function initNoteskin(path?: string): Promise<NoteskinResource> {
  if (noteskinInstance && noteskinInstance.isLoaded()) {
    return noteskinInstance;
  }

  noteskinInstance = new NoteskinResource(path || DEFAULT_NOTESKIN_PATH);
  await noteskinInstance.load();
  return noteskinInstance;
}
