/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#f0f4ff',
          100: '#e0eaff',
          400: '#7c9ef8',
          500: '#4f72f5',
          600: '#3b5cf0',
          700: '#2d46d6',
          900: '#1a2a8f',
        },
        surface: {
          900: '#0d0f1a',
          800: '#131627',
          700: '#1c2036',
          600: '#242847',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
}
