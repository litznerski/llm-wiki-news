/**
 * ==============================================================================
 * 🛰️ SUDAN NEWS & OSINT KNOWLEDGE GRAPH — SITE CONFIGURATION
 * ==============================================================================
 */

export interface SiteAuthor {
  name: string;
  role: string;
  avatar: string;
  bio: string;
  location?: string;
  status?: string;
  social: {
    twitter?: string;
    linkedin?: string;
    email?: string;
  };
}

export interface NavLink {
  text: string;
  href: string;
}

export interface CategoryInfo {
  name: string;
  desc: string;
}

export interface SiteConfig {
  name: string;
  logoLetter?: string;
  title: string;
  description: string;
  url: string;
  favicon: string;
  defaultOgImage?: string;
  author: SiteAuthor;
  hero: {
    greeting: string;
    badge: string;
    tagline: string;
    primaryButton: { text: string; href: string };
    secondaryButton: { text: string; href: string };
  };
  navLinks: NavLink[];
  categories: CategoryInfo[];
  about?: {
    philosophyTitle?: string;
    philosophyParagraphs?: string[];
    quote?: string;
    highlights?: Array<{
      icon: string;
      title: string;
      desc: string;
    }>;
    techArsenal?: Array<{
      name: string;
      desc: string;
      category: string;
    }>;
  };
  newsletter?: {
    badge?: string;
    title?: string;
    description?: string;
    placeholder?: string;
    buttonText?: string;
    successMessage?: string;
  };
  notFound?: {
    badge?: string;
    title?: string;
    description?: string;
    homeButtonText?: string;
    browseButtonText?: string;
  };
  search?: {
    modalTitle?: string;
    placeholder?: string;
  };
  ui?: {
    latestPostsBadge?: string;
    latestPostsTitle?: string;
    categoriesTitle?: string;
    tagsTitle?: string;
    shareTitle?: string;
    shareDescription?: string;
    shareCopiedMessage?: string;
    tocTitle?: string;
    authorCardTitle?: string;
    writtenByText?: string;
  };
  footer: {
    tagline: string;
    copyright: string;
    brandDescription?: string;
  };
}

export const siteConfig: SiteConfig = {
  name: "Sudan OSINT Graph",
  logoLetter: "S",
  title: "Sudan News & OSINT Knowledge Graph | 5W1H Conflict Intelligence Studio",
  description:
    "Multilingual Sudan News & Open-Source Intelligence (OSINT) Knowledge Graph powered by Obsidian, ArcadeDB, FastMCP, and Astro.",
  url: "http://localhost:4322",
  favicon: "/favicon.svg",
  defaultOgImage: "/brand/banner.png",

  author: {
    name: "OSINT Cognitive Compiler",
    role: "Conflict Intelligence & Graph Architect",
    avatar: "/brand/avatar.png",
    bio: "Compiling 5W1H conflict events, acting entities, UN OCHA P-Code locations, NATO Admiralty ratings, and GRaSP contradiction matrices.",
    location: "Sudan Theatre (SD01–SD18)",
    status: "Monitoring Active Frontlines & Humanitarian Telemetry",
    social: {
      linkedin: "",
      email: "osint@example.com",
    },
  },

  hero: {
    greeting: "5W1H Conflict Intelligence & Contradiction Compiler",
    badge: "NATO Admiralty Rated • UN OCHA P-Codes • GRaSP Matrix",
    tagline:
      "A sovereign, multilingual news and OSINT knowledge graph tracking events, acting entities, territorial control, war economy drivers, and competing narratives across Sudan.",
    primaryButton: {
      text: "Explore Intelligence Graph",
      href: "/wiki",
    },
    secondaryButton: {
      text: "OSINT Studio",
      href: "/assistant",
    },
  },

  navLinks: [
    { text: "Home", href: "/" },
    { text: "Intelligence Graph", href: "/wiki" },
    { text: "Theatres & Domains", href: "/categories" },
    { text: "Tags", href: "/tags" },
    { text: "OSINT Studio", href: "/assistant" },
  ],

  categories: [
    { name: "Military Operations & Battles", desc: "Discrete 5W1H conflict incidents, sieges, airstrikes, and chronological campaign timelines." },
    { name: "Actors & Alliances", desc: "State forces, paramilitaries, Darfur armed movements, civil society ERRs, and commanders." },
    { name: "Locations & Territorial Control", desc: "UN OCHA P-Code anchored states (SD01–SD18), cities, IDP camps, and trade corridors." },
    { name: "War Economy & Humanitarian Crisis", desc: "Structural conflict drivers, IPC food insecurity telemetry, supply chains, and source provenance." },
  ],

  about: {
    philosophyTitle: "5W1H & GRaSP Conflict Intelligence Architecture",
    philosophyParagraphs: [
      "Every incoming Arabic, English, French, or German report is distilled into structured 5W1H primitives: Event, Date & Time, Location (UN OCHA P-Code), Acting Entities, Tactical Mechanics (What?), and Strategic Motives (Why?).",
      "Rather than overwriting conflicting claims, competing narratives between belligerents and outlets are preserved side-by-side in GRaSP Contradiction Matrices graded on the NATO Admiralty Scale (A1–F6).",
    ],
    quote: "In conflict monitoring, competing narratives are primary intelligence signal—never overwrite a contradiction.",
  },

  newsletter: {
    badge: "SITREP Dispatches",
    title: "Subscribe to Sudan SITREP Updates",
    description: "Periodic dispatches on newly verified conflict events, frontline shifts, and humanitarian assessments.",
    placeholder: "analyst@example.com",
    buttonText: "Subscribe",
    successMessage: "Subscribed to SITREP alerts.",
  },

  notFound: {
    badge: "HTTP_STATUS // 404_NOT_FOUND",
    title: "Intelligence Node Not Found",
    description: "The event, actor, location, or source note you requested does not exist or has been archived.",
    homeButtonText: "Return Home",
    browseButtonText: "Browse Intelligence Graph",
  },

  search: {
    modalTitle: "Search Sudan OSINT Graph",
    placeholder: "Search events, actors, P-Codes (SD01-SD18), sources...",
  },

  ui: {
    latestPostsBadge: "Recent Intelligence",
    latestPostsTitle: "Latest Compiled Events, Actors & Syntheses",
    categoriesTitle: "Browse by Intelligence Domain",
    tagsTitle: "Active Theatre & Topic Tags",
    shareTitle: "Share Intelligence Note",
    shareDescription: "Share this verified 5W1H intelligence note with fellow analysts.",
    shareCopiedMessage: "Link copied to clipboard!",
    tocTitle: "6-Stage CoT Structure",
    authorCardTitle: "About the OSINT Compiler",
    writtenByText: "Compiled by",
  },

  footer: {
    tagline: "Sudan News & OSINT Knowledge Graph (llm-wiki-news)",
    copyright: "Sudan OSINT Graph",
    brandDescription:
      "A local-first 5W1H conflict intelligence and contradiction-tracking engine powered by Obsidian, ArcadeDB, FastMCP, and Astro.",
  },
};

export default siteConfig;
