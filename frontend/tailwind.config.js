/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      colors: {
        // Refined corporate azure — trustworthy, legal-tech
        brand: {
          50: '#eef3ff',
          100: '#dbe5ff',
          200: '#bccfff',
          300: '#8eabff',
          400: '#5b82fb',
          500: '#3b6df6',
          600: '#2553eb',
          700: '#1d42d3',
          800: '#1e39ab',
          900: '#1e3687',
          950: '#162152',
        },
      },
      boxShadow: {
        soft: '0 1px 2px rgba(0,0,0,0.35), 0 1px 1px rgba(0,0,0,0.2)',
        card: '0 1px 3px rgba(0,0,0,0.4), 0 8px 24px -12px rgba(0,0,0,0.5)',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.25s ease-out',
      },
    },
  },
  plugins: [],
}
