import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

// https://astro.build/config
export default defineConfig({
  site: 'https://xgame-radar.pages.dev',
  integrations: [
    tailwind({
      applyBaseStyles: true,
    })
  ]
});
