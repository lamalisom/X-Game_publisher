import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  trailingSlash: 'always',
  site: 'https://unanext.fans',
  integrations: [
    tailwind()
  ]
});
