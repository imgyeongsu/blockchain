/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{jsx,js,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#080808',
        'primary-blue': '#007AFF',
        'warning-red': '#FF453A',
        gold: '#FFD700',
        'neon-green': '#00FF88',
        'card-bg': 'rgba(255,255,255,0.06)',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}

