<script lang="ts">
  interface Props {
    hover?: boolean;
    cornerRadius?: number;
    class?: string;
    children?: import('svelte').Snippet;
    onclick?: () => void;
    onmouseenter?: () => void;
    onmouseleave?: () => void;
  }

  let { hover = false, cornerRadius = 16, class: className = '', children, onclick, onmouseenter, onmouseleave }: Props = $props();

  let isHovered = $state(false);

  function handleMouseEnter() {
    isHovered = true;
    onmouseenter?.();
  }

  function handleMouseLeave() {
    isHovered = false;
    onmouseleave?.();
  }
</script>

<div
  class="glass-card {className}"
  class:hover={isHovered}
  style="border-radius: {cornerRadius}px;"
  onclick={onclick}
  onmouseenter={handleMouseEnter}
  onmouseleave={handleMouseLeave}
  role="button"
  tabindex="0"
>
  {@render children?.()}
</div>

<style>
  .glass-card {
    background: rgba(30, 30, 50, 0.3);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 0.8px solid rgba(200, 200, 210, 0.8);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    transition: all 0.15s ease-out;
    cursor: pointer;
  }

  .glass-card:hover {
    transform: translateY(-2px) scale(1.03);
    background: rgba(40, 40, 60, 0.4);
    border-color: rgba(220, 200, 100, 0.8);
  }

  .glass-card:active {
    transform: translateY(1px) scale(0.98);
  }
</style>
