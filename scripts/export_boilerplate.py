#!/usr/bin/env python3
"""
scripts/export_boilerplate.py
Automated sanitizer that exports a pristine, clean-slate GitHub template repository
from the active knowledge-lab codebase into ../llm-wiki-boilerplate.
"""

import os
import shutil
import re
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parent.parent

# 1. Directories to replicate with empty .gitkeep files
EMPTY_DIRECTORIES = [
    "raw/articles",
    "raw/papers",
    "raw/books",
    "raw/research",
    "raw/transcripts",
    "raw/tasks",
    "raw/tasks/archived",
    "raw/drafts",
    "raw/assets",
    "wiki/concepts",
    "wiki/entities",
    "wiki/sources",
    "wiki/syntheses",
    "wiki/ingestions",
    "wiki/.ki",
]

# 2. Files and directories to copy verbatim
COPY_WHITELIST = [
    ".agent",
    ".agents",
    "services/fastmcp",
    "services/frontend",
    "setup",
    "site",
    "scripts",
    "pyproject.toml",
    ".gitignore",
]

# 3. Path patterns to strictly ignore during copy
EXCLUDE_DIR_NAMES = {
    "__pycache__",
    ".venv",
    "node_modules",
    ".astro",
    "dist",
    ".chainlit",
    ".files",
    "arcadedb-ki-data",
    "arcadedb-ki-config",
    "arcadedb-data",
    "arcadedb-config",
}

EXCLUDE_FILE_PATTERNS = {
    "data-store.json",
    "valves.json",
    "*.pyc",
    ".DS_Store",
    "*.pem",
    "*.key",
}


def should_exclude(path: Path) -> bool:
    if any(part in EXCLUDE_DIR_NAMES for part in path.parts):
        return True
    if path.name.endswith(".example"):
        return False
    if path.name == ".env" or path.name.startswith(".env."):
        return True
    for pat in EXCLUDE_FILE_PATTERNS:
        if path.match(pat):
            return True
    return False


def clean_copy_tree(src: Path, dst: Path):
    if should_exclude(src):
        return
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            clean_copy_tree(item, dst / item.name)
    else:
        shutil.copy2(src, dst)


def create_scaffold(output_dir: Path):
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"🚀 Generating clean boilerplate into: {output_dir}")
    if output_dir.exists():
        print(f"  • Purging existing destination {output_dir}...")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    # 1. Copy whitelisted code & configs
    for item in COPY_WHITELIST:
        src = SOURCE_ROOT / item
        if src.exists():
            print(f"  • Copying {item}...")
            clean_copy_tree(src, output_dir / item)

    # 2. Replicate empty directory trees with .gitkeep
    for rel_path in EMPTY_DIRECTORIES:
        target_dir = output_dir / rel_path
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / ".gitkeep").touch()
    print("  • Replicated empty raw/ and wiki/ structures with .gitkeep.")

    # 3. Author pristine baseline wiki files
    (output_dir / "wiki/index.md").write_text(
        "# Knowledge Base Master Catalog\n\n"
        "## Concepts\n*No concepts ingested yet. Run `/ingest <file-path>` to compile your first concept.*\n\n"
        "## Entities\n*No entities registered yet.*\n\n"
        "## Sources\n*No primary sources distilled yet.*\n\n"
        "## Syntheses\n*No dialectical syntheses archived yet.*\n\n"
        "## Ingestions\n*No ingestion dossiers logged yet.*\n",
        encoding="utf-8"
    )

    (output_dir / "wiki/overview.md").write_text(
        "# Domain Knowledge Overview\n\n"
        "> [!NOTE] Living Domain Synthesis\n"
        "> Author your high-level domain synthesis, foundational pillars, and theoretical positions here.\n",
        encoding="utf-8"
    )

    (output_dir / "wiki/glossary.md").write_text(
        "# Knowledge Base Glossary & Disambiguation Registry\n\n"
        "## Canonical Naming Rules\n\n"
        "| Term | Canonical Entity / Concept | Aliases & Acronyms | Context / Disambiguation |\n"
        "| :--- | :--- | :--- | :--- |\n",
        encoding="utf-8"
    )

    (output_dir / "wiki/log.md").write_text(
        f"# Knowledge Base Operational Log\n\n"
        "All operations follow the format:\n"
        "`## [YYYY-MM-DD] Operation | Target | Brief summary of edits`\n\n"
        "---\n\n"
        f"## [{today}] init | vault | Initialized clean knowledge base from boilerplate template.\n",
        encoding="utf-8"
    )

    (output_dir / "wiki/.ki/vault.yaml").write_text("profile: default\n", encoding="utf-8")

    # 4. Clean site/src/content/blog/ (Replace with 1 welcome note)
    blog_dir = output_dir / "site/src/content/blog"
    if blog_dir.exists():
        shutil.rmtree(blog_dir)
    blog_dir.mkdir(parents=True, exist_ok=True)
    (blog_dir / "welcome.mdx").write_text(
        "---\n"
        "title: \"Welcome to Your Sovereign Knowledge Base\"\n"
        "description: \"Your local-first, agentic knowledge engine is ready for ingestion.\"\n"
        f"pubDate: {today}\n"
        "category: \"Architecture\"\n"
        "tags: [\"knowledge-graph\", \"socratic-ai\"]\n"
        "---\n\n"
        "# Welcome to Your Knowledge Base\n\n"
        "This platform combines an Obsidian-native knowledge graph with ArcadeDB and Socratic AI.\n"
        "Ingest your first document using `/ingest <file-path>` to begin compiling your personal knowledge base.\n",
        encoding="utf-8"
    )

    # 5. Remove site/src/pages/blog so /blog redirects cleanly to /wiki
    site_blog_pages = output_dir / "site/src/pages/blog"
    if site_blog_pages.exists():
        shutil.rmtree(site_blog_pages)

    # 6. Sanitize site/astro.config.mjs with /blog -> /wiki redirects
    astro_config_path = output_dir / "site/astro.config.mjs"
    if astro_config_path.exists():
        astro_cfg = astro_config_path.read_text(encoding="utf-8")
        astro_cfg = re.sub(
            r"redirects:\s*\{[^}]*\},",
            "redirects: {\n    '/blog': '/wiki',\n    '/blog/[...slug]': '/wiki/[...slug]',\n    '/essays': '/wiki',\n  },",
            astro_cfg,
            flags=re.DOTALL
        )
        astro_cfg = astro_cfg.replace("https://knowledge.com", "http://localhost:4321")
        astro_config_path.write_text(astro_cfg, encoding="utf-8")

    # 7. Sanitize site/package.json
    site_pkg_path = output_dir / "site/package.json"
    if site_pkg_path.exists():
        pkg_content = site_pkg_path.read_text(encoding="utf-8")
        pkg_content = pkg_content.replace('"knowledge-lab-site"', '"knowledge-lab-site"')
        pkg_content = pkg_content.replace(
            "Knowledge Lab — Where Learning Architecture meets AI. Governed Socratic friction, cognitive integrity, and offline-first educational enablement.",
            "Knowledge Lab — Sovereign Knowledge Graph & Socratic Learning Studio."
        )
        site_pkg_path.write_text(pkg_content, encoding="utf-8")

    # 8. Sanitize site/src/config/site.ts
    site_ts_path = output_dir / "site/src/config/site.ts"
    if site_ts_path.exists():
        clean_site_ts = '''/**
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
'''
        site_ts_path.write_text(clean_site_ts, encoding="utf-8")

    # 8. Sanitize site/src/pages/index.astro
    index_astro_path = output_dir / "site/src/pages/index.astro"
    if index_astro_path.exists():
        clean_index_astro = '''---
import BaseLayout from '../layouts/BaseLayout.astro';
import HeroMagazineCover from '../components/ui/HeroMagazineCover.astro';
import TagBadge from '../components/ui/TagBadge.astro';
import siteConfig from '../config/site';
import { url } from '../utils/paths';
import { getCollection } from 'astro:content';
import { ArrowRight, Sparkles, BookOpen, Network, Cpu, Compass } from 'lucide-astro';

const allPosts = await getCollection('blog');
const sortedPosts = allPosts.sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());
const featuredPost = sortedPosts[0];

const categories = siteConfig.categories.map((cat) => ({
  name: cat.name,
  desc: cat.desc,
}));

const allTags = [...new Set(sortedPosts.flatMap((p) => p.data.tags || []))];
const ui = siteConfig.ui;
---

<BaseLayout>
  <!-- Hero Section -->
  <section class="mb-10 sm:mb-14 p-6 sm:p-10 lg:p-12 kepler-card rounded-3xl relative overflow-hidden group">
    <div class="absolute -top-24 -right-24 w-96 h-96 rounded-full border border-dashed border-orange-500/20 pointer-events-none animate-[orbit-spin_35s_linear_infinite]"></div>

    <div class="relative z-10 max-w-3xl">
      <div class="kepler-chip-orange mb-4 sm:mb-5">
        <span class="w-2 h-2 rounded-full bg-orange-600 animate-pulse"></span>
        <span>{siteConfig.hero.badge}</span>
      </div>

      <h1 class="text-3xl sm:text-5xl lg:text-6xl font-extrabold font-poppins text-white tracking-tight leading-[1.15] mb-4 sm:mb-5">
        Sovereign Knowledge Base & <br class="hidden sm:inline" />
        <span class="text-orange-400">Socratic Studio.</span>
      </h1>

      <p class="text-sm sm:text-lg text-zinc-200 font-normal leading-relaxed mb-6 sm:mb-8">
        {siteConfig.hero.tagline}
      </p>

      <div class="flex flex-wrap items-center gap-3">
        <a
          href={url('/wiki')}
          class="kepler-btn-orange px-6 py-3 text-xs sm:text-sm w-full sm:w-auto"
        >
          <span>Explore Knowledge Graph</span>
          <ArrowRight class="w-4 h-4" />
        </a>

        <a
          href={url('/assistant')}
          class="kepler-btn-navy px-5 py-3 text-xs sm:text-sm w-full sm:w-auto"
        >
          <span>Launch Learning Studio</span>
        </a>
      </div>
    </div>
  </section>

  <!-- Architectural Pillars Matrix -->
  <section class="mb-14 grid grid-cols-1 md:grid-cols-3 gap-6">
    <div class="p-6 rounded-3xl kepler-card flex flex-col justify-between">
      <div>
        <div class="text-orange-400 font-mono text-xs uppercase tracking-wider mb-2 font-bold flex items-center gap-2">
          <BookOpen class="w-4 h-4" />
          <span>Obsidian IDE</span>
        </div>
        <h3 class="text-lg font-bold font-poppins text-white mb-2">Atomic Knowledge Graph</h3>
        <p class="text-sm text-zinc-200 leading-relaxed">
          Agent-managed markdown vault with strict CoT epistemic arcs across concepts, entities, and distilled sources.
        </p>
      </div>
    </div>

    <div class="p-6 rounded-3xl kepler-card flex flex-col justify-between">
      <div>
        <div class="text-orange-400 font-mono text-xs uppercase tracking-wider mb-2 font-bold flex items-center gap-2">
          <Network class="w-4 h-4" />
          <span>ArcadeDB</span>
        </div>
        <h3 class="text-lg font-bold font-poppins text-white mb-2">Multi-Model Engine</h3>
        <p class="text-sm text-zinc-200 leading-relaxed">
          High-performance graph traversals, JVector HNSW vector indexing, and Graph OLAP procedures with zero external bloat.
        </p>
      </div>
    </div>

    <div class="p-6 rounded-3xl kepler-card flex flex-col justify-between">
      <div>
        <div class="text-orange-400 font-mono text-xs uppercase tracking-wider mb-2 font-bold flex items-center gap-2">
          <Cpu class="w-4 h-4" />
          <span>FastMCP & Chainlit</span>
        </div>
        <h3 class="text-lg font-bold font-poppins text-white mb-2">Socratic Sparring Studio</h3>
        <p class="text-sm text-zinc-200 leading-relaxed">
          Two-Tier Toulmin context retrieval and Socratic dialogue valves that enforce productive friction and authentic learning.
        </p>
      </div>
    </div>
  </section>

  <!-- Featured Note / Welcome Spotlight -->
  {featuredPost && <HeroMagazineCover post={featuredPost} />}

  <!-- Categories & Tags Section -->
  <section class="my-16 grid grid-cols-1 lg:grid-cols-12 gap-8">
    <div class="lg:col-span-7 kepler-card rounded-3xl p-7 sm:p-8">
      <div class="flex items-center justify-between border-b border-white/10 pb-4 mb-6">
        <div class="flex items-center gap-2.5">
          <span class="w-2.5 h-2.5 rounded-full bg-orange-500"></span>
          <h3 class="text-lg font-bold font-poppins text-white">
            {ui?.categoriesTitle || 'Topic Domains'}
          </h3>
        </div>
        <span class="text-xs font-mono text-sky-200/80">// CATEGORIES</span>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {categories.map((cat) => (
          <a
            href={url(`/categories/${cat.name.toLowerCase()}`)}
            class="group p-5 rounded-2xl bg-[#0a1628]/60 border border-white/10 hover:border-orange-400/50 hover:shadow-[2px_2px_0_var(--color-ink)] flex flex-col justify-between transition-all"
          >
            <div class="flex items-center justify-between mb-2">
              <span class="text-base font-bold font-poppins text-white group-hover:text-orange-400 transition-colors">
                {cat.name}
              </span>
              <Compass class="w-4 h-4 text-orange-400 opacity-60 group-hover:opacity-100 transition-opacity" />
            </div>
            <p class="text-xs text-zinc-300 leading-relaxed">
              {cat.desc}
            </p>
          </a>
        ))}
      </div>
    </div>

    <div class="lg:col-span-5 kepler-card rounded-3xl p-7 sm:p-8 flex flex-col justify-between">
      <div>
        <div class="flex items-center justify-between border-b border-white/10 pb-4 mb-6">
          <div class="flex items-center gap-2.5">
            <span class="w-2.5 h-2.5 rounded-full bg-orange-500"></span>
            <h3 class="text-lg font-bold font-poppins text-white">
              {ui?.tagsTitle || 'Indexed Tags'}
            </h3>
          </div>
          <span class="font-mono text-xs text-sky-200/80">#TAGS</span>
        </div>

        <div class="flex flex-wrap gap-2">
          {allTags.length > 0 ? (
            allTags.map((tag) => <TagBadge tag={tag} size="sm" />)
          ) : (
            <span class="text-xs text-zinc-400 italic">Tags will populate as notes are ingested.</span>
          )}
        </div>
      </div>

      <div class="mt-6 pt-4 border-t border-white/10 flex justify-between items-center text-xs text-zinc-300 font-mono">
        <span>SOVEREIGN KNOWLEDGE</span>
        <a href={url('/wiki')} class="text-orange-400 hover:underline">View All Wiki Notes &rarr;</a>
      </div>
    </div>
  </section>
</BaseLayout>
'''
        index_astro_path.write_text(clean_index_astro, encoding="utf-8")

    # 9. Sanitize AGENTS.md (Neutralize project names & retain all axioms)
    agents_src = (SOURCE_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    agents_clean = agents_src.replace("Knowledge Lab", "Knowledge Lab")
    agents_clean = agents_clean.replace("knowledge-lab", "knowledge-lab")
    agents_clean = agents_clean.replace("knowledge", "knowledge")
    (output_dir / "AGENTS.md").write_text(agents_clean, encoding="utf-8")

    # 10. Sanitize setup/compose.arcadedb.yaml
    compose_arcade_path = output_dir / "setup/compose.arcadedb.yaml"
    if compose_arcade_path.exists():
        arcade_compose = """services:
  arcadedb:
    image: arcadedata/arcadedb:latest
    container_name: arcadedb-ki
    restart: unless-stopped
    ports:
      - "2480:2480" # REST API, Studio Web UI, and Built-in MCP Server (/api/v1/mcp)
      - "2424:2424" # Binary Protocol
    environment:
      - JAVA_TOOL_OPTIONS=-Xms512m -Xmx1536m
      - ARCADEDB_SETTINGS=-Darcadedb.server.rootPassword=${ARCADEDB_PASSWORD:-root_secret} -Darcadedb.server.defaultDatabases=${ARCADEDB_DATABASE:-knowledgedb} -Darcadedb.mcp.enabled=true
    volumes:
      - arcadedb-data:/home/arcadedb/databases
      - arcadedb-config:/home/arcadedb/config
    networks:
      - wiki-net
    healthcheck:
      test: ["CMD-SHELL", "wget -q --spider http://localhost:2480/api/v1/ready || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5

  fastmcp-middleware:
    build:
      context: ../services/fastmcp
      dockerfile: Dockerfile
    image: fastmcp-middleware:latest
    container_name: fastmcp-middleware
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - ARCADEDB_URL=http://arcadedb-ki:2480
      - ARCADEDB_DATABASE=${ARCADEDB_DATABASE:-knowledgedb}
      - ARCADEDB_USER=${ARCADEDB_USER:-root}
      - ARCADEDB_PASSWORD=${ARCADEDB_PASSWORD:-root_secret}
      - DEFAULT_DIALECT=auto
      - LOG_LEVEL=INFO
      - ENABLE_LANGFUSE=${ENABLE_LANGFUSE:-false}
      - LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY:-}
      - LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY:-}
      - LANGFUSE_HOST=${LANGFUSE_HOST:-https://cloud.langfuse.com}
    depends_on:
      arcadedb:
        condition: service_healthy
    networks:
      - wiki-net
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: "1.0"
        reservations:
          memory: 128M
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval: 10s
      timeout: 3s
      retries: 3

volumes:
  arcadedb-data:
    name: arcadedb-data
  arcadedb-config:
    name: arcadedb-config

networks:
  wiki-net:
    name: wiki-net
"""
        compose_arcade_path.write_text(arcade_compose, encoding="utf-8")

    # 11. Sanitize setup/compose.chainlit.yaml
    compose_chainlit_path = output_dir / "setup/compose.chainlit.yaml"
    if compose_chainlit_path.exists():
        chainlit_compose = """services:
  chainlit-frontend:
    build:
      context: ../services/frontend
      dockerfile: Dockerfile
    image: chainlit-frontend:latest
    container_name: chainlit-frontend
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ../services/frontend:/app:z
    environment:
      - FASTMCP_URL=http://fastmcp-middleware:8000
      - CHAINLIT_HOST=0.0.0.0
      - CHAINLIT_PORT=8080
      - ENABLE_LANGFUSE=false
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-}
      - LLM_MODEL=${LLM_MODEL:-openrouter/free}
    networks:
      - wiki-net
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "1.0"
        reservations:
          memory: 128M
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 3

networks:
  wiki-net:
    name: wiki-net
"""
        compose_chainlit_path.write_text(chainlit_compose, encoding="utf-8")

    # 12. Create environment template files (.env.example)
    (output_dir / "setup/.env.example").write_text(
        "# Root / Orchestration Environment Template\n"
        "ARCADEDB_PASSWORD=root_secret\n"
        "ARCADEDB_DATABASE=knowledgedb\n"
        "OPENROUTER_API_KEY=\n"
        "LLM_MODEL=openrouter/free\n"
        "ENABLE_LANGFUSE=false\n",
        encoding="utf-8"
    )

    (output_dir / "services/frontend/.env.example").write_text(
        "# services/frontend/.env.example\n"
        "FASTMCP_URL=http://fastmcp-middleware:8000\n"
        "CHAINLIT_HOST=0.0.0.0\n"
        "CHAINLIT_PORT=8080\n"
        "OPENROUTER_API_KEY=\n"
        "LLM_MODEL=openrouter/free\n"
        "ENABLE_LANGFUSE=false\n",
        encoding="utf-8"
    )

    (output_dir / "services/fastmcp/.env.example").write_text(
        "# services/fastmcp/.env.example\n"
        "ARCADEDB_URL=http://localhost:2480\n"
        "ARCADEDB_DATABASE=knowledgedb\n"
        "ARCADEDB_USER=root\n"
        "ARCADEDB_PASSWORD=root_secret\n"
        "DEFAULT_DIALECT=auto\n"
        "LOG_LEVEL=INFO\n"
        "HOST=0.0.0.0\n"
        "PORT=8000\n"
        "ENABLE_LANGFUSE=false\n",
        encoding="utf-8"
    )

    # 13. Sanitize services/frontend/app.py (Remove hardcoded API keys)
    app_py_path = output_dir / "services/frontend/app.py"
    if app_py_path.exists():
        app_code = app_py_path.read_text(encoding="utf-8")
        app_code = re.sub(
            r'DEFAULT_OPENROUTER_KEY = os\.getenv\(\s*"OPENROUTER_API_KEY",\s*"sk-or-[^"]+"\s*\)',
            'DEFAULT_OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")',
            app_code
        )
        app_code = app_code.replace("knowledge-lab", "knowledge-lab").replace("knowledge", "knowledge")
        app_py_path.write_text(app_code, encoding="utf-8")

    # 14. Sanitize services/frontend/chainlit.md
    chainlit_md_path = output_dir / "services/frontend/chainlit.md"
    chainlit_md_path.write_text(
        "# 🏛️ Sovereign Knowledge Studio\n\n"
        "An interactive, grounded learning companion for exploring your sovereign knowledge base.\n\n"
        "---\n\n"
        "### Core Architecture\n"
        "- **Epistemic Substrate**: Multi-model [[ArcadeDB]] (`knowledgedb`) graph database.\n"
        "- **Middleware Engine**: [[FastMCP]] providing Two-Tier context resolution (Tier 1 Pre-Compiled Golden Syntheses and Tier 2 Toulmin CoT Traversal).\n"
        "- **Epistemic Provenance**: Every assertion is verified against underlying primary literature and canonical concept notes.\n\n"
        "---\n\n"
        "### Operating Guide\n"
        "Welcome to your sovereign Socratic Knowledge Studio. Ingest documents into `raw/` to populate your knowledge graph and begin dialectical sparring.\n"
        "1. **Direct Conceptual Inquiry**: Type any question into the chat composer below (e.g. *\"What are the core concepts in my vault?\"*).\n"
        "2. **Side-Panel Inspection**: The split-screen side panel displays in-engine PageRank authority, Louvain community clusters, and Toulmin argumentation roles.\n"
        "3. **Dialogue Valves**: Access the ⚙️ Settings menu in the chat composer to toggle dialogue modes (`General` vs. `Learn`) or adjust Socratic solution withholding.\n",
        encoding="utf-8"
    )

    # 15. Create default sanitized valves.json for Chainlit
    (output_dir / "services/frontend/valves.json").write_text(
        "{\n"
        '  "operating_mode": "General",\n'
        '  "developer_mode": true,\n'
        '  "teachable_agent_mode": false,\n'
        '  "enable_chat_history": true,\n'
        '  "enable_langfuse": false,\n'
        '  "fastmcp_url": "http://fastmcp-middleware:8000",\n'
        '  "enable_llm": true,\n'
        '  "llm_model": "openrouter/free",\n'
        '  "custom_model": "",\n'
        '  "openrouter_api_key": "",\n'
        '  "openrouter_base_url": "https://openrouter.ai/api/v1",\n'
        '  "llm_temperature": 0.2\n'
        "}\n",
        encoding="utf-8"
    )

    # 16. Sanitize scripts, setup, fastmcp, agent rules/skills, and frontend assets
    def replace_domain_terms(path: Path):
        try:
            content = path.read_text(encoding="utf-8")
            original = content
            content = content.replace("root_secret", "root_secret")
            content = content.replace("knowledgedb", "knowledgedb")
            content = content.replace("Knowledge Lab", "Knowledge Lab")
            content = content.replace("Knowledge Lab", "Knowledge Lab")
            content = content.replace("knowledge-lab", "knowledge-lab")
            content = content.replace("knowledge", "knowledge")
            if content != original:
                path.write_text(content, encoding="utf-8")
        except Exception:
            pass

    for dir_to_sanitize in [
        output_dir / "scripts",
        output_dir / "setup",
        output_dir / ".agent",
        output_dir / ".agents",
        output_dir / "services/fastmcp",
        output_dir / "services/frontend/public",
    ]:
        if dir_to_sanitize.exists():
            for root, _, files in os.walk(dir_to_sanitize):
                for f in files:
                    if f.endswith((".py", ".md", ".sh", ".yaml", ".yml", ".json", ".js", ".css", ".html")):
                        replace_domain_terms(Path(root) / f)

    # 17. Generate root pyproject.toml for Day-0 uv sync
    (output_dir / "pyproject.toml").write_text(
        "[project]\n"
        'name = "llm-wiki-boilerplate"\n'
        'version = "0.1.0"\n'
        'description = "Sovereign LLM-Wiki, ArcadeDB, FastMCP, and Socratic Studio Boilerplate"\n'
        'readme = "README.md"\n'
        'requires-python = ">=3.11"\n'
        "dependencies = [\n"
        '    "requests>=2.31.0",\n'
        '    "pyyaml>=6.0.1",\n'
        '    "httpx>=0.27.0",\n'
        "]\n\n"
        "[tool.uv]\n"
        "package = false\n",
        encoding="utf-8"
    )

    # 18. Sanitize README.md
    (output_dir / "README.md").write_text(
        "# Sovereign LLM-Wiki Boilerplate\n\n"
        "A local-first, autonomous knowledge compiler and Socratic learning studio powered by:\n"
        "- **Obsidian IDE**: Agent-managed markdown knowledge graph.\n"
        "- **ArcadeDB**: Multi-model graph and vector storage.\n"
        "- **FastMCP**: Semantic routing and Dual-Flow Chain-of-Thought middleware.\n"
        "- **Chainlit**: Socratic Learning Studio with live streaming.\n"
        "- **Astro 5**: High-speed digital garden with Pagefind and interactive Mermaid diagrams.\n\n"
        "## Quick Start\n\n"
        "1. **Check Prerequisites**:\n"
        "   ```bash\n"
        "   ./scripts/check_prerequisites.sh\n"
        "   ```\n"
        "2. **Configure Environment**:\n"
        "   ```bash\n"
        "   cp setup/.env.example .env\n"
        "   cp services/fastmcp/.env.example services/fastmcp/.env\n"
        "   cp services/frontend/.env.example services/frontend/.env\n"
        "   ```\n"
        "3. **Install Dependencies**:\n"
        "   ```bash\n"
        "   uv sync\n"
        "   npm --prefix site install\n"
        "   ```\n"
        "4. **Start ArcadeDB & Bootstrap Schema**:\n"
        "   ```bash\n"
        "   podman-compose -f setup/compose.arcadedb.yaml up -d\n"
        "   uv run scripts/bootstrap_arcadedb.py\n"
        "   ```\n"
        "5. **Start Astro Frontend & Chainlit Studio**:\n"
        "   ```bash\n"
        "   npm --prefix site run dev\n"
        "   podman-compose -f setup/compose.chainlit.yaml up -d\n"
        "   ```\n\n"
        "See `setup/boilerplate_architecture_and_clean_clone_guide.md` for comprehensive documentation.\n",
        encoding="utf-8"
    )

    # 18. Initialize Git Repository
    print("  • Initializing fresh Git repository in destination...")
    try:
        subprocess.run(["git", "init"], cwd=output_dir, check=True, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=output_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "feat(genesis): initial boilerplate template release"],
            cwd=output_dir,
            check=True,
            capture_output=True
        )
        print("  • Created genesis Git commit.")
    except Exception as e:
        print(f"  ⚠️ Note: Git initialization skipped or encountered non-fatal notice: {e}")

    print("✅ Boilerplate export completed successfully!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export clean boilerplate repository.")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=SOURCE_ROOT.parent / "llm-wiki-boilerplate",
        help="Target output directory (default: ../llm-wiki-boilerplate)"
    )
    args = parser.parse_args()
    create_scaffold(args.output)

