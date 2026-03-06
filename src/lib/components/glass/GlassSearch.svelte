<script lang="ts">
  interface Props {
    value?: string;
    placeholder?: string;
    class?: string;
    onchange?: (value: string) => void;
  }

  let { value = $bindable(''), placeholder = '搜索...', class: className = '', onchange }: Props = $props();

  function handleInput(event: Event) {
    const target = event.target as HTMLInputElement;
    value = target.value;
  }

  function handleChange(event: Event) {
    const target = event.target as HTMLInputElement;
    onchange?.(target.value);
  }
</script>

<div class="search-container {className}">
  <svg
    class="search-icon"
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
  >
    <circle cx="11" cy="11" r="8" />
    <path d="m21 21-4.35-4.35" />
  </svg>
  <input
    type="text"
    class="glass-input"
    {placeholder}
    bind:value
    oninput={handleInput}
    onchange={handleChange}
  />
</div>

<style>
  .search-container {
    position: relative;
    display: flex;
    align-items: center;
  }

  .search-icon {
    position: absolute;
    left: 12px;
    color: #646478;
    pointer-events: none;
  }

  .glass-input {
    background: rgba(40, 40, 60, 0.5);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 0.8px solid rgba(200, 200, 210, 0.8);
    border-radius: 12px;
    padding: 10px 16px 10px 36px;
    color: #f0f0fa;
    font-size: 14px;
    outline: none;
    transition: all 0.15s ease-out;
    width: 100%;
  }

  .glass-input:focus {
    border-color: rgba(220, 200, 100, 0.8);
    box-shadow: 0 0 10px rgba(220, 200, 100, 0.2);
  }

  .glass-input::placeholder {
    color: #646478;
  }
</style>
