/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  theme: {
    extend: {
      colors: {
        xblack: '#08080a',
        xdark: '#121318',
        xcard: '#1a1c24',
        xborder: '#2a2d3d',
        xorange: {
          DEFAULT: '#ff4d00',
          hover: '#ff6622',
          glow: 'rgba(255, 77, 0, 0.35)',
        },
        xcyan: {
          DEFAULT: '#00f2fe',
          hover: '#4facfe',
          glow: 'rgba(0, 242, 254, 0.35)',
        },
        xyellow: '#ffb703',
        xgreen: '#00f59b',
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
        display: ['Impact', 'Teko', 'Arial Black', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'glow-orange': '0 0 25px rgba(255, 77, 0, 0.4)',
        'glow-cyan': '0 0 25px rgba(0, 242, 254, 0.4)',
      }
    },
  },
  plugins: [],
};
