/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter Variable"', 'Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
      },
      keyframes: {
        ring: {
          '0%': { boxShadow: '0 0 0 0 rgba(239,68,68,0.55)' },
          '70%': { boxShadow: '0 0 0 12px rgba(239,68,68,0)' },
          '100%': { boxShadow: '0 0 0 0 rgba(239,68,68,0)' },
        },
        fadein: { '0%': { opacity: 0, transform: 'translateY(-4px)' }, '100%': { opacity: 1, transform: 'none' } },
        pop: { '0%': { transform: 'scale(0.6)', opacity: 0 }, '60%': { transform: 'scale(1.08)' }, '100%': { transform: 'scale(1)', opacity: 1 } },
        shake: { '0%,100%': { transform: 'rotate(0)' }, '20%,60%': { transform: 'rotate(-6deg)' }, '40%,80%': { transform: 'rotate(6deg)' } },
      },
      animation: {
        ring: 'ring 1.6s ease-out infinite',
        fadein: 'fadein 0.35s ease-out',
        pop: 'pop 0.45s ease-out',
        shake: 'shake 0.8s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
