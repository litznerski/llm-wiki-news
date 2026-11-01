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
    category: z.string().default('Military Operations & Battles'),
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
    event_category: z.string().optional(),
    event_sub_type: z.string().optional(),
    event_start_date: z.any().optional(),
    event_end_date: z.any().optional(),
    reported_date: z.any().optional(),
    last_updated: z.any().optional(),
    pcode: z.string().optional(),
    admiralty_rating: z.string().optional(),
    verification_status: z.string().optional(),
    reliability_score: z.number().optional(),
    fatalities_best: z.number().optional(),
    contradiction_flags: z.array(z.string()).default([]),
    tags: z.array(z.string()).default([]),
    sources: z.array(z.string()).default([]),
    aliases: z.array(z.string()).default([]),
    publish: z.boolean().optional(),
    draft: z.boolean().optional(),
    status: z.enum(['draft', 'approved']).optional(),
    compiled: z.boolean().optional(),
    compiled_at: z.any().optional(),
    speaker: z.string().optional(),
    speaker_role: z.string().optional(),
    role_title: z.string().optional(),
    affiliated_organization: z.string().nullable().optional(),
    source_outlet: z.string().optional(),
    citation_date: z.any().optional(),
    speech_act: z.string().optional(),
  }).passthrough(),
});

export const collections = { blog, wiki };
