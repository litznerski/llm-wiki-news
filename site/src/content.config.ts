import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';
import { glob } from 'astro/loaders';
import siteConfig from './config/site';
import { wikiPublishConfig } from './config/wiki.config';

const blog = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/blog' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    heroImage: z.string().optional(),
    heroImageAlt: z.string().optional(),
    category: z.string().default('Learning Architecture'),
    tags: z.array(z.string()).default([]),
    author: z.string().default(siteConfig.author.name),
    issueNumber: z.string().optional(),
    featured: z.boolean().default(false),
  }),
});

const wiki = defineCollection({
  loader: glob({ pattern: '**/*.md', base: wikiPublishConfig.vaultRoot }),
  schema: z.object({
    title: z.string().optional(),
    type: z.string().optional(),
    subtype: z.string().optional(),
    tags: z.array(z.string()).default([]),
    last_updated: z.any().optional(),
    sources: z.array(z.string()).default([]),
    aliases: z.array(z.string()).default([]),
    reliability_score: z.number().optional(),
    publish: z.boolean().optional(),
    draft: z.boolean().optional(),
  }).passthrough(),
});

export const collections = { blog, wiki };

