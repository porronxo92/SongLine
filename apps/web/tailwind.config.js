/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: 'var(--color-primary)',
        secondary: 'var(--color-secondary)',
        accent: 'var(--color-accent)',
        'on-accent': 'var(--color-on-accent)',
        background: 'var(--color-background)',
        foreground: 'var(--color-foreground)',
        card: 'var(--color-card)',
        'muted-foreground': 'var(--color-muted-foreground)',
        destructive: 'var(--color-destructive)',
        ring: 'var(--color-ring)',
      },
      borderRadius: {
        clay: 'var(--radius-lg)',
      },
      boxShadow: {
        clay: 'var(--shadow-clay)',
      },
      fontFamily: {
        body: ['Quicksand', 'system-ui', 'sans-serif'],
        display: ['Fredoka', 'Quicksand', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
