/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        primary:    '#6CABDD',
        secondary:  '#1C2C5B',
        accent:     '#FFFFFF',
        background: '#0A0F1E',
        card:       '#111827',
        surface:    '#1a2235',
        border:     '#1e2d4a',
        success:    '#22C55E',
        danger:     '#EF4444',
        warning:    '#F59E0B',
        muted:      '#8b949e',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
