/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        ws: {
          bg: '#1a1a2e',
          panel: '#16213e',
          border: '#0f3460',
          header: '#0a1628',
          selected: '#1e3a5f',
          hover: '#1c2f4a',
          accent: '#4fc3f7',
        },
        proto: {
          hci: '#5c9eff',
          l2cap: '#4caf50',
          avdtp: '#ab47bc',
          att: '#ff9800',
          smp: '#f44336',
          rfcomm: '#00bcd4',
          sdp: '#8bc34a',
          avctp: '#e91e63',
          default: '#78909c',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};
