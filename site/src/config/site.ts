/**
 * ==============================================================================
 * 🌟 DEV.LOG — SINGLE SOURCE OF TRUTH CONFIGURATION (Knowledge Lab)
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
  name: "Knowledge Lab",
  logoLetter: "K",
  title: "Knowledge Lab | Sovereign Knowledge Graph & Socratic Studio",
  description:
    "Local-first sovereign knowledge graph and Socratic AI studio powered by Obsidian, ArcadeDB, FastMCP, and Astro 5.",
  url: "http://localhost:4321",
  favicon: "/favicon.svg",
  defaultOgImage: "/brand/banner.png",

  author: {
    name: "Knowledge Architect",
    role: "Knowledge Engineer & Researcher",
    avatar: "/brand/avatar.png",
    bio: "Compiling atomic concepts, grounded entity networks, and Socratic learning environments with local-first AI.",
    location: "Global",
    status: "Cultivating Sovereign Knowledge Graph",
    social: {
      linkedin: "",
      email: "architect@example.com",
    },
  },

  hero: {
    greeting: "Autonomous Knowledge Compiler & Socratic Studio",
    badge: "Local-First AI & Knowledge Graph",
    tagline:
      "A sovereign, agent-managed knowledge architecture combining Obsidian markdown, ArcadeDB multi-model graph storage, and FastMCP reasoning middleware.",
    primaryButton: {
      text: "Explore Knowledge Graph",
      href: "/wiki",
    },
    secondaryButton: {
      text: "Learning Studio",
      href: "/assistant",
    },
  },

  navLinks: [
    { text: "Home", href: "/" },
    { text: "Knowledge Graph", href: "/wiki" },
    { text: "Categories", href: "/categories" },
    { text: "Tags", href: "/tags" },
    { text: "Learning Studio", href: "/assistant" },
  ],

  categories: [
    { name: "Architecture", desc: "Knowledge graphs, governed mono-vaults, and systemic system design." },
    { name: "Concepts", desc: "Atomic theoretical frameworks, methodologies, and abstractions." },
    { name: "Entities", desc: "Concrete profiles across researchers, organizations, and software platforms." },
    { name: "Syntheses", desc: "Multi-document dialectical analyses and learning path roadmaps." },
  ],

  about: {
    philosophyTitle: "Sovereign Knowledge Architecture",
    philosophyParagraphs: [
      "This platform transforms an Obsidian markdown vault into an active cognitive substrate.",
      "By integrating multi-model graph traversal with ArcadeDB and FastMCP, knowledge is continuously synthesized, interconnected, and made navigable through Socratic sparring.",
    ],
    quote: "Autonomous compilation preserves deep causal models and transforms passive reading into active mastery.",
  },

  newsletter: {
    badge: "Knowledge Updates",
    title: "Subscribe to Vault Updates",
    description: "Occasional dispatches on newly compiled research and conceptual frameworks.",
    placeholder: "researcher@example.com",
    buttonText: "Subscribe",
    successMessage: "Thank you for subscribing!",
  },

  notFound: {
    badge: "HTTP_STATUS // 404_NOT_FOUND",
    title: "Page Not Found",
    description: "The note or resource you requested does not exist or has been moved.",
    homeButtonText: "Return Home",
    browseButtonText: "Browse Knowledge Graph",
  },

  search: {
    modalTitle: "Search Knowledge Base",
    placeholder: "Search concepts, entities, sources...",
  },

  ui: {
    latestPostsBadge: "Recent Notes",
    latestPostsTitle: "Latest Distillations & Syntheses",
    categoriesTitle: "Browse by Domain",
    tagsTitle: "Popular Tags",
    shareTitle: "Share This Note",
    shareDescription: "Found this note valuable? Share with fellow researchers.",
    shareCopiedMessage: "Link copied to clipboard!",
    tocTitle: "Table of Contents",
    authorCardTitle: "About the Compiler",
    writtenByText: "Compiled by",
  },

  footer: {
    tagline: "Sovereign Knowledge Base & Socratic Learning Studio",
    copyright: "Knowledge Lab",
    brandDescription:
      "A local-first, autonomous knowledge engine powered by Obsidian, ArcadeDB, FastMCP, and Astro 5.",
  },
};

export default siteConfig;
