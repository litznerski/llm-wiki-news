// @ts-check
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';
import expressiveCode from 'astro-expressive-code';
import { defineConfig } from 'astro/config';
import process from 'node:process';
import { remarkReadingTime } from './src/plugins/remark-reading-time.mjs';
import { remarkObsidianWikilinks } from './src/plugins/remark-obsidian-wikilinks.mjs';

// Dynamic site URL and base path resolution
const siteUrl = process.env.URL || 'http://localhost:4322';
const basePath = '/';

// https://astro.build/config
export default defineConfig({
  site: siteUrl,
  base: basePath,
  server: {
    port: 4322,
  },
  redirects: {
    '/blog': '/wiki',
    '/blog/[...slug]': '/wiki/[...slug]',
    '/essays': '/wiki',
  },
  markdown: {
    remarkPlugins: [remarkReadingTime, remarkObsidianWikilinks],
  },
  integrations: [
    expressiveCode({
      themes: ['tokyo-night'],
      useThemedScrollbars: true,
      styleOverrides: {
        borderRadius: '1rem',
        borderWidth: '1px',
        borderColor: 'rgba(255, 255, 255, 0.15)',
        codeFontFamily: '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
        uiFontFamily: '"Space Grotesk", "Plus Jakarta Sans", system-ui, sans-serif',
      },
    }),
    mdx(),
    sitemap(),
  ],
  vite: {
    // @ts-ignore
    plugins: [tailwindcss()],
    css: {
      postcss: {
        plugins: [],
      },
    },
  },
});
