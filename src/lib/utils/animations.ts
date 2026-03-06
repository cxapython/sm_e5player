/**
 * GSAP动画工具函数
 */

import gsap from 'gsap';

// 导出GSAP
export { gsap };

/**
 * 缓动函数
 */
export const easings = {
  // 平滑缓动
  smooth: 'power2.out',
  // 弹性缓动
  bounce: 'back.out(1.7)',
  // 惯性缓动
  inertia: 'power3.out',
  // 快速进入
  quickIn: 'power4.out',
};

/**
 * 创建卡片悬停动画
 */
export function createCardHoverAnimation(element: HTMLElement) {
  const timeline = gsap.timeline({ paused: true });

  timeline.to(element, {
    y: -2,
    scale: 1.03,
    duration: 0.15,
    ease: easings.smooth,
  });

  return {
    play: () => timeline.play(),
    reverse: () => timeline.reverse(),
  };
}

/**
 * 创建淡入动画
 */
export function fadeIn(element: HTMLElement, duration: number = 0.3) {
  return gsap.fromTo(
    element,
    { opacity: 0, y: 20 },
    {
      opacity: 1,
      y: 0,
      duration,
      ease: easings.smooth,
    }
  );
}

/**
 * 创建缩放动画
 */
export function scaleIn(element: HTMLElement, duration: number = 0.2) {
  return gsap.fromTo(
    element,
    { opacity: 0, scale: 0.9 },
    {
      opacity: 1,
      scale: 1,
      duration,
      ease: easings.smooth,
    }
  );
}

/**
 * 创建滑动动画
 */
export function slideIn(
  element: HTMLElement,
  direction: 'left' | 'right' | 'up' | 'down' = 'up',
  duration: number = 0.3
) {
  const fromVars: gsap.TweenVars = { opacity: 0 };

  switch (direction) {
    case 'left':
      fromVars.x = -50;
      break;
    case 'right':
      fromVars.x = 50;
      break;
    case 'up':
      fromVars.y = 50;
      break;
    case 'down':
      fromVars.y = -50;
      break;
  }

  return gsap.fromTo(element, fromVars, {
    opacity: 1,
    x: 0,
    y: 0,
    duration,
    ease: easings.smooth,
  });
}

/**
 * 创建星级脉动动画
 */
export function starPulse(element: HTMLElement) {
  return gsap.to(element, {
    scale: 1.1,
    duration: 0.15,
    ease: easings.smooth,
    yoyo: true,
    repeat: 1,
  });
}

/**
 * 创建惯性滚动
 */
export function createInertialScroll(
  element: HTMLElement,
  options: {
    friction?: number;
    elasticity?: number;
  } = {}
) {
  const { friction = 5, elasticity = 0.3 } = options;
  let velocity = 0;
  let position = 0;
  let isDragging = false;
  let lastY = 0;

  function update() {
    if (isDragging) return;

    // 应用摩擦力
    velocity *= (1 - friction / 60);

    // 更新位置
    position += velocity;

    // 边界弹性
    // TODO: 实现边界检测
  }

  function startDrag(y: number) {
    isDragging = true;
    lastY = y;
    velocity = 0;
  }

  function updateDrag(y: number) {
    if (!isDragging) return;
    const delta = y - lastY;
    position -= delta;
    lastY = y;
  }

  function endDrag() {
    isDragging = false;
  }

  return {
    startDrag,
    updateDrag,
    endDrag,
    update,
    getPosition: () => position,
    setPosition: (p: number) => {
      position = p;
      velocity = 0;
    },
  };
}
