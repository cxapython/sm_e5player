<script lang="ts">
  interface Props {
    text?: string;
    active?: boolean;
    cornerRadius?: number;
    class?: string;
    children?: import('svelte').Snippet;
    onclick?: () => void;
  }

  let { text = '', active = false, cornerRadius = 20, class: className = '', children, onclick }: Props = $props();

  let hover = $state(false);
</script>

<button
  class="glass-button {className}"
  class:hover
  class:active
  style="border-radius: {cornerRadius}px;"
  onclick={onclick}
  onmouseenter={() => hover = true}
  onmouseleave={() => hover = false}
>
  {text}
  {@render children?.()}
</button>

<style>
  .glass-button {
    background: rgba(40, 40, 60, 0.5);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 0.8px solid rgba(200, 200, 210, 0.8);
    padding: 10px 20px;
    color: #b4b4be;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease-out;
    outline: none;
  }

  .glass-button:hover {
    transform: translateY(-2px);
    border-color: rgba(220, 200, 100, 0.8);
    color: #f0f0fa;
  }

  .glass-button:active, .glass-button.active {
    transform: translateY(0);
    background: rgba(60, 100, 180, 0.5);
  }

  .glass-button.active {
    border-color: rgba(100, 180, 255, 0.8);
    color: #f0f0fa;
  }
</style>
