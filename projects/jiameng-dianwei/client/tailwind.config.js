/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#E8751A',
        'primary-dark': '#D06515',
        secondary: '#F5A623',
        'bg-warm': '#FFF8F0',
        'price-bg': '#FFF3E8',
        'text-main': '#1A1A1A',
        'text-sub': '#8C8C8C',
      },
      borderRadius: {
        card: '12px',
        btn: '8px',
      },
      boxShadow: {
        card: '0 2px 8px rgba(0,0,0,0.08)',
      },
    },
  },
  plugins: [],
}
