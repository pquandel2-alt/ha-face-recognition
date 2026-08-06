/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#12141a',
          raised: '#1a1d24',
          hover: '#20242e',
          header: '#0e1015',
        },
        border: {
          DEFAULT: '#2a2e37',
        },
        accent: {
          DEFAULT: '#6366f1',
          hover: '#818cf8',
        },
        success: {
          DEFAULT: '#34d399',
          bg: 'rgba(52, 211, 153, 0.12)',
          border: 'rgba(52, 211, 153, 0.35)',
        },
        warning: {
          DEFAULT: '#fbbf24',
          bg: 'rgba(251, 191, 36, 0.12)',
          border: 'rgba(251, 191, 36, 0.35)',
        },
        danger: {
          DEFAULT: '#f87171',
          bg: 'rgba(248, 113, 113, 0.12)',
          border: 'rgba(248, 113, 113, 0.35)',
        },
        info: {
          DEFAULT: '#60a5fa',
          bg: 'rgba(96, 165, 250, 0.12)',
          border: 'rgba(96, 165, 250, 0.35)',
        },
      },
    },
  },
  plugins: [],
}
