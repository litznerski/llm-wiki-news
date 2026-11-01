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

## [2026-11-01] task | Split ingestion skill | Authored Two-Phase Ingestion Skill Architecture Proposal in _input/drafts/Two-Phase Ingestion Skill Architecture Proposal.md; updated task status to done, archived task file, and moved card to Done on infrastructure board.

## [2026-11-01] refactor | Two-Phase Ingestion Pipeline | Updated AGENTS.md, .agent/skills/{wiki-ingest,wiki-scope}/SKILL.md, scripts/{lint_vault,bootstrap_arcadedb,ingest_to_arcadedb}.py, and site/src/{config/wiki.config.ts,content.config.ts} to implement Phase 1 draft source distillation (status: draft, compiled: false) and Phase 2 approved entity compilation & ArcadeDB/ki synchronization (status: approved).

## [2026-11-01] ingest-draft | 2026-10-23-un-news-sudan-drone-strikes-306-killed | Created draft source note in wiki/sources/2026-10-23-un-news-sudan-drone-strikes-306-killed.md (status: draft, admiralty_rating: A2) with scoped manifest (3 events, 4 actors, 3 locations, 1 theme, 0 refactors); awaiting approval.

## [2026-11-01] task | Extention for ingestion | Authored Direct Citations Person Actors and Source Outlet Schema Extension Plan in _input/drafts/; updated task status to done, archived task file, and moved card to Done on infrastructure board.

## [2026-11-01] refactor | Citation, Person Actor & Source Outlet Schema Extension | Created wiki/citations/; updated AGENTS.md, .agent/skills/{wiki-scope,wiki-ingest}/SKILL.md, scripts/{bootstrap_arcadedb,ingest_to_arcadedb,lint_vault}.py, site/src/{config/wiki.config.ts,content.config.ts}, and refactored wiki/sources/2026-10-23-un-news-sudan-drone-strikes-306-killed.md with UN News (media_source), 5 quoted person actors, and 5 standalone citations.

## [2026-11-01] ingest-compile | 2026-10-23-un-news-sudan-drone-strikes-306-killed | Compiled approved source into 22 notes (3 events, 10 actors, 3 locations, 1 theme, 5 citations, 0 refactors); generated dossier in wiki/ingestions/2026-11-01/; updated index, SITREP & glossary; synced ArcadeDB (210 vertices, 1263 edges, FastRP 768d vectors & PageRank/Betweenness/Louvain OLAP).

## [2026-11-01] task | Wiki Timelines | Authored Wiki Timelines Architecture and Ingestion Integration Plan in _input/drafts/; updated task status to done, archived task file, and moved card to Done on infrastructure board.

## [2026-11-01] refactor | Wiki Timelines Bitemporal Spine & Backfill | Updated AGENTS.md, .agent/skills/{wiki-scope,wiki-ingest}/SKILL.md, and scripts/{lint_vault,bootstrap_arcadedb,ingest_to_arcadedb}.py with the 5-stage Timeline Micro-CoT arc, Mandatory Monthly Chronicle rule, and (:Timeline)-[:CHRONICLES]->(:Event|:Citation) + sequential [:PRECEDES] edges; compiled wiki/timelines/{2026-10 Sudan Conflict Chronicle,Sudan Drone Warfare and Double-Tap Strike Timeline}.md and synced ArcadeDB.

## [2026-11-01] ingest-draft | 2026-10-31-unsg-spokesperson-escalating-drone-attacks-sudan | Created draft source note in wiki/sources/2026-10-31-unsg-spokesperson-escalating-drone-attacks-sudan.md (status: draft, admiralty_rating: A1) with scoped manifest (0 events, 4 actors, 0 locations, 0 themes, 0 timelines, 2 citations, 8 refactors); awaiting approval.

## [2026-11-01] ingest-compile | 2026-10-31-unsg-spokesperson-escalating-drone-attacks-sudan | Compiled approved source into 6 new notes (0 events, 4 actors, 0 locations, 0 themes, 0 timelines, 2 citations) and refactored 8 existing nodes; generated dossier in wiki/ingestions/2026-11-01/; updated index, SITREP & glossary; synced ArcadeDB.

## [2026-11-01] ingest-draft | 2026-10-28-ohchr-ffm-el-obeid-drone-warfare-repression | Created draft source note in wiki/sources/2026-10-28-ohchr-ffm-el-obeid-drone-warfare-repression.md (status: draft, admiralty_rating: A1) with scoped manifest (1 events, 4 actors, 2 locations, 1 themes, 0 timelines, 3 citations, 8 refactors); awaiting approval.

## [2026-11-01] ingest-draft | 2026-10-28-ohchr-independent-international-fact-finding-mission-sudan-portal | Created draft source note in wiki/sources/2026-10-28-ohchr-independent-international-fact-finding-mission-sudan-portal.md (status: draft, admiralty_rating: A1) with scoped manifest (0 events, 5 actors, 0 locations, 1 themes, 1 timelines, 1 citations, 2 refactors); awaiting approval.

## [2026-11-01] ingest-draft | 2026-10-31-dabanga-haiya-oil-electricity-drone-attack | Created draft source note in wiki/sources/2026-10-31-dabanga-haiya-oil-electricity-drone-attack.md (status: draft, admiralty_rating: B2) with scoped manifest (1 events, 5 actors, 3 locations, 2 themes, 0 timelines, 1 citations, 5 refactors); awaiting approval.

## [2026-02-19] ingest-draft | 2026-02-19-un-news-el-fasher-hallmarks-of-genocide | Created draft source note in wiki/sources/2026-02-19-un-news-el-fasher-hallmarks-of-genocide.md (status: draft, admiralty_rating: A1) with scoped manifest (1 events, 5 actors, 2 locations, 1 themes, 2 timelines, 3 citations, 3 refactors); awaiting approval.

## [2026-10-21] ingest-draft | 2026-10-21-un-news-geneva-peace-efforts-drone-war | Created draft source note in wiki/sources/2026-10-21-un-news-geneva-peace-efforts-drone-war.md (status: draft, admiralty_rating: A2) with scoped manifest (1 events, 3 actors, 1 locations, 1 themes, 0 timelines, 2 citations, 6 refactors); awaiting approval.

## [2026-10-30] ingest-draft | 2026-10-30-the-guardian-sudanese-diaspora-uae-un-nominee-nusseibeh | Created draft source note in wiki/sources/2026-10-30-the-guardian-sudanese-diaspora-uae-un-nominee-nusseibeh.md (status: draft, admiralty_rating: B1) with scoped manifest (1 events, 12 actors, 1 locations, 2 themes, 0 timelines, 3 citations, 3 refactors); awaiting approval.

## [2026-10-31] ingest-draft | 2026-10-31-arab-news-un-chief-appalled-drone-strikes-nyala-market | Created draft source note in wiki/sources/2026-10-31-arab-news-un-chief-appalled-drone-strikes-nyala-market.md (status: draft, admiralty_rating: B2) with scoped manifest (1 events, 2 actors, 2 locations, 0 themes, 0 timelines, 1 citations, 6 refactors); awaiting approval.

## [2026-11-01] ingest-draft | 2026-11-01-dabanga-unsg-guterres-condemns-escalating-drone-attacks | Created draft source note in wiki/sources/2026-11-01-dabanga-unsg-guterres-condemns-escalating-drone-attacks.md (status: draft, admiralty_rating: B1) with scoped manifest (0 events, 2 actors, 0 locations, 0 themes, 0 timelines, 1 citations, 5 refactors); awaiting approval.

## [2026-11-01] ingest-compile | 8 Approved Sources Vault-Wide Compilation | Compiled all 8 approved source notes (2026-10-28-ohchr-ffm-el-obeid, 2026-10-28-ohchr-portal, 2026-10-31-dabanga-haiya, 2026-02-19-un-news-el-fasher, 2026-10-21-un-news-geneva, 2026-10-30-the-guardian-uae, 2026-10-31-arab-news-nyala, 2026-11-01-dabanga-unsg) into 62 new entities (6 events, 28 actors, 10 locations, 8 themes, 3 timelines, 15 citations) and refactored core conflict nodes; authored 8 audit dossiers in wiki/ingestions/2026-11-01/; updated index.md, overview.md, and glossary.md; marked all 8 sources compiled: true.

## [2026-11-01] audit-fix | Graph Integrity & Node Materialization | Materialized 10 supporting domain nodes (International Criminal Court, Joint Darfur Force, Transitional Sovereignty Council, Emergency Response Rooms, Sudanese Resistance Committees, Kaamil Ahmed, Port Sudan, Khartoum State, Atbara, Zamzam IDP Camp); aligned 27 actor notes and 1 citation to canonical 6-stage/4-stage Micro-CoT headings; stripped backticked wikilinks across 8 ingestion dossiers; updated index.md and glossary.md; achieved 100% clean linter compliance (0 errors, 0 dead links, 0 CoT gaps).

## [2026-11-01] ingest-draft | 2026-10-28-un-hrc-crp1-el-obeid-civilian-devastation | Created draft source note in wiki/sources/2026-10-28-un-hrc-crp1-el-obeid-civilian-devastation.md (status: draft, admiralty_rating: A1) with scoped manifest (2 events, 2 actors, 2 locations, 1 themes, 1 timelines, 3 citations, 14 refactors); awaiting approval.

## [2026-11-01] ingest-compile | 2026-10-28-un-hrc-crp1-el-obeid-civilian-devastation | Compiled approved source note wiki/sources/2026-10-28-un-hrc-crp1-el-obeid-civilian-devastation.md (A/HRC/65/CRP.1, A1, reliability_score: 0.95) into 11 new domain entities (2 events: Um Badr Market Summary Executions, Jabal al-Uqaydat Airstrikes; 2 actors: Al-Baraa Ibn Malik Brigade, SPLM-N al-Hilu; 2 locations: Kurmuk, Um Badr; 1 theme: Arbitrary Detention and Custodial Torture in the Sudan War; 1 timeline: 2026-09 Sudan Conflict Chronicle; 3 citations: RSF Drone Warfare in El Obeid, SAF Detention Practices and Torture in El Obeid, Recommendation for Specialized Independent Court); refactored 14 existing domain nodes across events, actors, locations, themes, and timelines; authored ingestion audit dossier wiki/ingestions/2026-11-01/2026-10-28-un-hrc-crp1-el-obeid-civilian-devastation.md; updated index.md, overview.md, and glossary.md; marked source compiled: true.

## [2026-11-01] task | Contradiction Missing: Ingestion Analysis & Graph Edge Implementation | Reviewed all 11 previous ingestions against ArcadeDB news graph; analyzed root causes for missing ATTRIBUTION_CONFLICT edges (ingest_to_arcadedb.py omission, event frontmatter propagation drop, single-article citation contradiction pattern); authored comprehensive analysis and multi-layered implementation plan in _input/drafts/Contradiction Missing Ingestion Analysis and Implementation Plan.md; updated task status to done, archived task file, and updated Kanban board.


