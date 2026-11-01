/**
 * ==============================================================================
 * 🌟 WIKI PUBLISHING CONFIGURATION — SUDAN NEWS & OSINT KNOWLEDGE GRAPH
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
  /** Explicit note IDs to force-publish (relative to wiki/, e.g. "overview") */
  explicitIncludes: string[];
  /** Explicit note IDs to withhold */
  explicitExcludes: string[];
  /** Minimum reliability score (0.0 - 1.0) required to publish (if score is present) */
  minReliabilityScore: number;
  /** URL prefix for public wiki pages */
  urlPrefix: string;
}

export const wikiPublishConfig: WikiPublishConfig = {
  vaultRoot: '../wiki',
  includedFolders: [
    'events',
    'actors',
    'locations',
    'themes',
    'timelines',
    'syntheses',
    'sources',
  ],
  excludedFolders: [
    'ingestions',
  ],
  explicitIncludes: [
    'overview',
    'glossary',
  ],
  explicitExcludes: [],
  minReliabilityScore: 0.70,
  urlPrefix: '/wiki',
};

/**
 * Standardized slugification function converting note titles to clean URL paths.
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
 * Determines whether a wiki note qualifies for public rendering.
 */
export function isNotePublished(noteId: string, frontmatter: Record<string, any> = {}): boolean {
  if (frontmatter.publish === false || frontmatter.draft === true) {
    return false;
  }

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
 * Deterministically maps a wiki note to one of the site's primary Sudan OSINT topic domains:
 * - Military Operations & Battles
 * - Actors & Alliances
 * - Locations & Territorial Control
 * - War Economy & Humanitarian Crisis
 */
export function getWikiCategory(data: Record<string, any> = {}): string {
  if (data.category && typeof data.category === 'string') {
    const norm = data.category.toLowerCase().trim();
    if (norm.includes('military') || norm.includes('battle') || norm.includes('event')) return 'Military Operations & Battles';
    if (norm.includes('actor') || norm.includes('alliance') || norm.includes('force')) return 'Actors & Alliances';
    if (norm.includes('location') || norm.includes('territor') || norm.includes('state')) return 'Locations & Territorial Control';
    if (norm.includes('humanitarian') || norm.includes('econom') || norm.includes('theme')) return 'War Economy & Humanitarian Crisis';
    return data.category;
  }

  if (data.type === 'event' || data.type === 'timeline') return 'Military Operations & Battles';
  if (data.type === 'actor') return 'Actors & Alliances';
  if (data.type === 'location') return 'Locations & Territorial Control';
  if (data.type === 'theme' || data.type === 'synthesis' || data.type === 'source') return 'War Economy & Humanitarian Crisis';

  const tags: string[] = Array.isArray(data.tags) ? data.tags.map((t: string) => t.toLowerCase()) : [];

  const scores: Record<string, number> = {
    'Military Operations & Battles': 0,
    'Actors & Alliances': 0,
    'Locations & Territorial Control': 0,
    'War Economy & Humanitarian Crisis': 0,
  };

  const tagPatterns: Record<string, string[]> = {
    'Military Operations & Battles': [
      'battle', 'shelling', 'airstrike', 'drone', 'siege', 'offensive', 'ceasefire',
      'incident', 'campaign', 'frontline', 'combat', 'artillery', 'timeline',
    ],
    'Actors & Alliances': [
      'saf', 'rsf', 'armed-group', 'state-force', 'militia', 'coalition', 'commander',
      'political-body', 'civil-society', 'err', 'joint-force', 'taqaddum', 'sumoud',
    ],
    'Locations & Territorial Control': [
      'darfur', 'khartoum', 'kordofan', 'jazirah', 'gezira', 'port-sudan', 'el-fasher',
      'nyala', 'omdurman', 'bahri', 'sennar', 'white-nile', 'blue-nile', 'gedaref',
      'kassala', 'red-sea', 'northern', 'river-nile', 'idp-camp', 'border-crossing',
    ],
    'War Economy & Humanitarian Crisis': [
      'famine', 'ipc', 'displacement', 'humanitarian', 'war-economy', 'gold', 'arms',
      'supply-chain', 'sanctions', 'diplomacy', 'jeddah', 'geneva', 'disinformation',
    ],
  };

  for (const [cat, patterns] of Object.entries(tagPatterns)) {
    for (const tag of tags) {
      if (patterns.some((p) => tag.includes(p) || p.includes(tag))) {
        scores[cat] += 1;
      }
    }
  }

  let bestCat = 'Military Operations & Battles';
  let maxScore = 0;
  for (const [cat, score] of Object.entries(scores)) {
    if (score > maxScore) {
      maxScore = score;
      bestCat = cat;
    }
  }

  return bestCat;
}

export function getWikiCategorySlug(categoryName: string): string {
  return slugifyWikiTitle(categoryName);
}

export default wikiPublishConfig;
