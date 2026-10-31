/**
 * ==============================================================================
 * 🌟 WIKI PUBLISHING CONFIGURATION — OPTION C: TIERED HYBRID ENGINE
 * ==============================================================================
 * Controls selective publishing of compiled Obsidian knowledge vault notes
 * (wiki/) onto the Astro site without mutating raw vault markdown files.
 */

export interface WikiPublishConfig {
  /** Relative path from site/ root to the compiled knowledge vault */
  vaultRoot: string;
  /** Folders published by default */
  includedFolders: string[];
  /** Folders withheld from publishing by default */
  excludedFolders: string[];
  /** Explicit note IDs to force-publish (relative to wiki/, e.g. "sources/key-paper.md") */
  explicitIncludes: string[];
  /** Explicit note IDs to withhold (e.g. "concepts/Unfinished Idea.md") */
  explicitExcludes: string[];
  /** Minimum reliability score (0.0 - 1.0) required to publish (if score is present) */
  minReliabilityScore: number;
  /** URL prefix for public wiki pages */
  urlPrefix: string;
}

export const wikiPublishConfig: WikiPublishConfig = {
  vaultRoot: '../wiki',
  includedFolders: [
    'concepts',
    'entities',
    'syntheses',
    'sources',
  ],
  excludedFolders: [
    'ingestions',
  ],
  explicitIncludes: [],
  explicitExcludes: [],
  minReliabilityScore: 0.80,
  urlPrefix: '/wiki',
};

/**
 * Standardized slugification function converting note titles to clean URL paths.
 * Normalizes accents/umlauts and strips invalid characters.
 */
export function slugifyWikiTitle(title: string): string {
  if (!title) return '';
  return title
    .toString()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
    .replace(/\s+/g, '-')
    .replace(/[^\w-]+/g, '')
    .replace(/--+/g, '-');
}

/**
 * Determines whether a wiki note qualifies for public rendering based on Option C rules:
 * 1. Explicit `publish: false` or `draft: true` in frontmatter strictly withholds the note.
 * 2. Note in explicitExcludes is withheld.
 * 3. Note in includedFolders OR explicitIncludes OR explicit `publish: true` is included.
 * 4. Must meet minReliabilityScore (if reliability_score is defined).
 */
export function isNotePublished(noteId: string, frontmatter: Record<string, any> = {}): boolean {
  if (frontmatter.publish === false || frontmatter.draft === true) {
    return false;
  }

  // Normalize noteId (remove leading slashes or .md extension)
  const cleanId = noteId.replace(/^\.?\//, '').replace(/\.md$/, '');
  const idWithExt = `${cleanId}.md`;

  if (wikiPublishConfig.explicitExcludes.includes(cleanId) || wikiPublishConfig.explicitExcludes.includes(idWithExt)) {
    return false;
  }

  const parts = cleanId.split('/');
  const folder = parts.length > 1 ? parts[0] : '';

  const isFolderAllowed = wikiPublishConfig.includedFolders.includes(folder);
  const isExplicitInclude =
    wikiPublishConfig.explicitIncludes.includes(cleanId) ||
    wikiPublishConfig.explicitIncludes.includes(idWithExt) ||
    frontmatter.publish === true;

  if (!isFolderAllowed && !isExplicitInclude) {
    return false;
  }

  if (frontmatter.reliability_score !== undefined && typeof frontmatter.reliability_score === 'number') {
    if (frontmatter.reliability_score < wikiPublishConfig.minReliabilityScore) {
      return false;
    }
  }

  return true;
}

/**
 * Deterministically maps a wiki note to one of the site's primary topic domains:
 * - Learning Architecture
 * - Cognitive Science
 * - EdTech
 * - Architecture
 */
export function getWikiCategory(data: Record<string, any> = {}): string {
  if (data.category && typeof data.category === 'string') {
    const norm = data.category.toLowerCase().trim();
    if (norm.includes('learning')) return 'Learning Architecture';
    if (norm.includes('cognit')) return 'Cognitive Science';
    if (norm.includes('edtech') || norm.includes('education')) return 'EdTech';
    if (norm.includes('architect') || norm.includes('infra') || norm.includes('graph')) return 'Architecture';
    return data.category;
  }

  const tags: string[] = Array.isArray(data.tags) ? data.tags.map((t: string) => t.toLowerCase()) : [];

  const scores: Record<string, number> = {
    'Learning Architecture': 0,
    'Cognitive Science': 0,
    'EdTech': 0,
    'Architecture': 0,
  };

  const tagPatterns: Record<string, string[]> = {
    'Learning Architecture': [
      'learning-architecture', 'instructional-design', 'pedagogical-governance', 'socratic-ai',
      'socratic-questioning', 'addie', 'isd-models', 'pedagogy', 'pro-learner-ai', 'curriculum',
      'higher-education', 'adult-learning', 'academic-integrity', 'post-plagiarism', 'assessment',
      'instructional', 'pedagogical', 'scaffolding', 'faculty', 'teacher-education',
    ],
    'Cognitive Science': [
      'cognitive-science', 'cognitive-psychology', 'learning-theory', 'learning-sciences',
      'epistemology', 'cognitive-load', 'cognitive-friction', 'cognitive-surrender',
      'metacognition', 'memory-consolidation', 'ioed', 'synthetic-fluency', 'feynman-technique',
      'desirable-difficulties', 'psychology', 'epistemic', 'criminology', 'cognitive', 'cognitive-debt',
    ],
    'EdTech': [
      'edtech', 'educational-technology', 'generative-ai', 'ai-literacy', 'human-ai-interaction',
      'ai-governance', 'prompt-engineering', 'llm', 'intelligent-tutoring', 'ai-learning-paradox',
      'waymo-effect', 'unesco', 'generative-video', 'physics-ai', 'ai-ethics', 'latent-diffusion',
      'open-webui', 'claude', 'token-budget',
    ],
    'Architecture': [
      'architecture', 'pkm', 'graphrag', 'neo4j', 'rag', 'obsidian', 'mono-vault',
      'governed-mono-vault', 'chain-of-thought', 'information-retrieval', 'devops', 'software',
      'content-engineering', 'distribution', 'publishing', 'digital-marketing', 'seo',
      'compilation', 'platform', 'tool', 'analytics', 'database', 'graph-data-science',
    ],
  };

  for (const [cat, patterns] of Object.entries(tagPatterns)) {
    for (const tag of tags) {
      if (patterns.some((p) => tag.includes(p) || p.includes(tag))) {
        scores[cat] += 1;
      }
    }
  }

  let bestCat = 'Learning Architecture';
  let maxScore = 0;
  for (const [cat, score] of Object.entries(scores)) {
    if (score > maxScore) {
      maxScore = score;
      bestCat = cat;
    }
  }

  if (maxScore === 0) {
    if (data.type === 'source') return 'EdTech';
    if (data.subtype === 'software' || data.subtype === 'platform') return 'Architecture';
    if (data.subtype === 'researcher') return 'Cognitive Science';
    return 'Learning Architecture';
  }

  return bestCat;
}

export function getWikiCategorySlug(categoryName: string): string {
  return slugifyWikiTitle(categoryName);
}

export default wikiPublishConfig;
