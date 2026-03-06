<script lang="ts">
  interface Props {
    stars: number;
    size?: number;
    showNumber?: boolean;
    animated?: boolean;
  }

  let { stars, size = 12, showNumber = true, animated = false }: Props = $props();

  let color = $derived(stars <= 5 ? 'var(--star-blue)' :
             stars <= 9 ? 'var(--star-purple)' : 'var(--star-red)');

  let displayStars = $derived(Math.min(10, Math.max(1, stars)));
</script>

<div
  class="star-rating"
  class:animated
  style="--star-color: {color}; --star-size: {size}px;"
>
  {#if showNumber}
    <div class="star-ring" style="width: {size * 2.5}px; height: {size * 2.5}px;">
      <span class="star-number" style="font-size: {size}px; color: {color};">
        {stars}
      </span>
    </div>
  {:else}
    <div class="stars">
      {#each Array(displayStars) as _, i}
        <svg
          class="star"
          width={size}
          height={size}
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
        </svg>
      {/each}
    </div>
  {/if}
</div>

<style>
  .star-rating {
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .star-ring {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    border: 2px solid var(--star-color);
    opacity: 0.9;
  }

  .star-ring::before {
    content: '';
    position: absolute;
    width: 100%;
    height: 100%;
    border-radius: 50%;
    border: 2px solid var(--star-color);
    opacity: 0.3;
  }

  .animated .star-ring::before {
    animation: pulse 150ms ease-out;
  }

  @keyframes pulse {
    0% { transform: scale(1); opacity: 0.3; }
    50% { transform: scale(1.15); opacity: 0.6; }
    100% { transform: scale(1); opacity: 0.3; }
  }

  .star-number {
    font-weight: bold;
    text-shadow: 0 0 2px rgba(0, 0, 0, 0.5);
  }

  .stars {
    display: flex;
    gap: 2px;
  }

  .star {
    color: var(--star-color);
    filter: drop-shadow(0 0 1px rgba(0, 0, 0, 0.5));
  }
</style>
