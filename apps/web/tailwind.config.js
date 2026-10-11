/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  safelist: ['btn-primary', 'btn-secondary', 'btn-accent', 'btn-danger', 'btn-ghost'],
  theme: {
    extend: {
      colors: {
        background: 'var(--color-bg)',
        foreground: 'var(--color-fg)',
        surface: 'var(--color-surface)',
        'surface-2': 'var(--color-surface-2)',
        'surface-3': 'var(--color-surface-3)',
        border: 'var(--color-border)',
        'border-strong': 'var(--color-border-strong)',
        'muted-foreground': 'var(--color-fg-2)',
        'fg-3': 'var(--color-fg-3)',
        primary: 'var(--color-primary)',
        'primary-light': 'var(--color-primary-light)',
        // `accent` ahora es el cian. El ámbar es `gold`.
        accent: 'var(--color-accent)',
        'on-accent': 'var(--color-on-accent)',
        magenta: 'var(--color-magenta)',
        'magenta-light': 'var(--color-magenta-light)',
        danger: 'var(--color-danger)',
        destructive: 'var(--color-magenta-light)',
        gold: 'var(--color-gold)',
        ring: 'var(--color-focus)',
      },
      borderRadius: {
        md2: 'var(--radius-md)',
        lg2: 'var(--radius-lg)',
      },
      boxShadow: {
        'glow-accent': 'var(--glow-accent)',
        'glow-magenta': 'var(--glow-magenta)',
        'glow-gold': 'var(--glow-gold)',
        'glow-primary': 'var(--glow-primary)',
      },
      fontFamily: {
        body: ['Outfit', 'system-ui', 'sans-serif'],
        display: ['Unbounded', 'Arial Black', 'Segoe UI', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
