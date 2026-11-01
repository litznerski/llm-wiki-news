# Knowledge Base Operational Log

All operations follow the format:
`## [YYYY-MM-DD] Operation | Target | Brief summary of edits`

---

## [2026-10-31] init | vault | Initialized clean knowledge base from boilerplate template.

## [2026-10-31] task | Concept Change to News | Executed deep research on news, conflict & contradiction ontologies (IPTC NAR/EventsML-G2/ninjs, SEM, LODE, ACLED, PLOVER/CAMEO, NewsReader/GRaSP, NATO Admiralty Scale, UN OCHA P-Codes, TimeML); authored research dossier in raw/research/ and full Sudan News LLM-Wiki architecture proposal in raw/drafts/; updated task status to done and moved card to Done on infrastructure board.

## [2026-11-01] refactor | Phase 1: Directory & Ledger Scaffolding | Created raw/{social,videos,reports,satellite} and wiki/{events,actors,locations,themes,timelines}; moved non-news folders (books, papers, research, tasks, drafts, projects) from raw/ to _input/; initialized wiki/index.md, wiki/overview.md (Sudan Conflict SITREP), and wiki/glossary.md (Sudan actors & UN OCHA P-Code registry).

## [2026-11-01] refactor | Phase 2: Agent Constitution & Skills | Updated AGENTS.md and .agent/skills/{wiki-scope,wiki-ingest,wiki-lint,wiki-format,wiki-history,wiki-task,web-deep-research} with 5W1H Event/Actor/Location/Theme Micro-CoT and Macro-CoT schemas, 48-hour Spatio-Temporal Event Deduplication rule, NATO Admiralty rating (A1-F6), GRaSP Contradiction Matrix, and _input/ operational paths.

## [2026-11-01] refactor | Phase 3: Graph Bootstrap, Linter & CoT Extractors | Updated scripts/{bootstrap_arcadedb,lint_vault,enrich_graph,extract_dual_flow_cot,extract_entity_cot,node_history}.py for Sudan News & OSINT vertex/edge DDL, Arabic/English alias normalization, UN OCHA P-Code validation, NATO Admiralty scoring, 6-stage Micro-CoT classification, and 5W1H/GRaSP Macro-CoT edge materialization.

## [2026-11-01] refactor | Phase 4: FastMCP & Chainlit Intelligence Studio | Updated services/fastmcp/{cot_retriever.py,retrieval/v3_engine.py,retrieval/context_builder.py}, services/frontend/{app.py,chainlit.md}, and setup/safeguard_intent_anchors.md for Sudan News & OSINT 5W1H/GRaSP retrieval, Arabic/English AliasLookup & UN OCHA P-Code entity linking, ClaimDispute hydration, and Intelligence Studio UI.

## [2026-11-01] refactor | Phase 5: Astro Digital Garden Frontend | Updated site/src/config/{wiki.config.ts,site.ts}, site/src/content.config.ts, site/src/pages/wiki/index.astro, and site/src/components/ui/WikiCard.astro to publish events, actors, locations, themes, timelines, syntheses, and sources with NATO Admiralty ratings and UN OCHA P-Code badges.
