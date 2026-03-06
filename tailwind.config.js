/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './src/**/*.{html,js,svelte,ts}',
  ],
  theme: {
    extend: {
      colors: {
        // 玻璃拟态颜色
        'glass': {
          'bg': 'rgba(30, 30, 50, 0.3)',
          'border': 'rgba(200, 200, 210, 0.8)',
          'border-hover': 'rgba(220, 200, 100, 0.8)',
          'shadow': 'rgba(0, 0, 0, 0.3)',
        },
        // 背景渐变
        'bg-top': '#0c0c19',
        'bg-bottom': '#19233c',
        // 文字颜色
        'text-white': '#f0f0fa',
        'text-gray': '#b4b4be',
        'text-dark': '#646478',
        // 星级颜色
        'star-blue': '#64b4ff',
        'star-purple': '#b464ff',
        'star-red': '#ff6464',
        'star-gold': '#ffdc32',
        // 判定颜色
        'perfect': '#32ff64',
        'good': '#ffdc32',
        'bad': '#ff5050',
        'miss': '#969696',
      },
      fontFamily: {
        'sans': ['-apple-system', 'BlinkMacSystemFont', 'SF Pro Display', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      borderRadius: {
        'glass': '16px',
        'capsule': '20px',
      },
      backdropBlur: {
        'glass': '8px',
      },
      animation: {
        'pulse-star': 'pulseStar 150ms ease-out',
        'float': 'float 2s ease-in-out infinite',
        'glow': 'glow 1s ease-in-out infinite alternate',
      },
      keyframes: {
        pulseStar: {
          '0%': { transform: 'scale(1)', opacity: '1' },
          '100%': { transform: 'scale(1.1)', opacity: '0.8' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-2px)' },
        },
        glow: {
          '0%': { boxShadow: '0 0 5px rgba(100, 180, 255, 0.3)' },
          '100%': { boxShadow: '0 0 15px rgba(100, 180, 255, 0.6)' },
        },
      },
    },
  },
  plugins: [],
}
