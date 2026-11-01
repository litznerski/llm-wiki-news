---
title: "Ingestion: 2026-10-31-unsg-spokesperson-escalating-drone-attacks-sudan"
type: "ingestion"
tags:
  - ingestion
  - audit
  - sudan
  - abyei
  - drone-warfare
  - united-nations
date: 2026-11-01
last_updated: 2026-11-01
reliability_score: 0.95
sources:
  - "[[sources/2026-10-31-unsg-spokesperson-escalating-drone-attacks-sudan]]"
source: "[[sources/2026-10-31-unsg-spokesperson-escalating-drone-attacks-sudan]]"
events_created: []
actors_created:
  - "[[Office of the Spokesperson for the Secretary-General]]"
  - "[[United Nations]]"
  - "[[Stéphane Dujarric]]"
  - "[[António Guterres]]"
locations_created: []
themes_created: []
timelines_created: []
citations_created:
  - "[[2026-10-31 Stéphane Dujarric UNSG Statement Condemning Escalating Drone Attacks in Sudan and Abyei]]"
  - "[[2026-10-31 António Guterres Appeal for Immediate Cessation of Hostilities and Good-Faith Mediation in Sudan]]"
nodes_refactored:
  - "[[2026-10 Sudan Drone Warfare Escalation]]"
  - "[[2026-10-19 Abyei Amiet Market and Todach Drone Strike]]"
  - "[[Abyei]]"
  - "[[Sudanese Armed Forces]]"
  - "[[Rapid Support Forces]]"
  - "[[Drone Proliferation and Double-Tap Strike Doctrine in Sudan]]"
  - "[[2026-10 Sudan Conflict Chronicle]]"
  - "[[Sudan Drone Warfare and Double-Tap Strike Timeline]]"
contradictions_logged:
  - "ATTRIBUTION_CONFLICT"
---

# Ingestion Audit Dossier: `2026-10-31-unsg-spokesperson-escalating-drone-attacks-sudan`

## 1. Provenance & Execution Context

| Attribute | Value |
| :--- | :--- |
| **Origin Raw File** | `raw/articles/Statement attributable to the Spokesperson for the Secretary-General - on escalating drone attacks in Sudan.md` |
| **Approved Source Note** | [[sources/2026-10-31-unsg-spokesperson-escalating-drone-attacks-sudan]] (`status: approved`, `compiled: true`) |
| **Publishing Outlet** | [[Office of the Spokesperson for the Secretary-General]] (`subtype: media_source`, `alignment: international_org`) |
| **NATO Admiralty Rating** | **`A1`** (`reliability_score: 0.95`) |
| **Publication Date ($t_{\text{reported}}$)** | `2026-10-31` |
| **Compilation Date ($t_{\text{compiled}}$)** | `2026-11-01` |
| **Pipeline Mode** | Phase 2 Approved Entity Compilation & Refactoring (`/wiki-ingest --approved`) |

---

## 2. Scoped Ingestion Manifest & Scoring

All 6 new candidate primitives and 8 refactor targets exceeded the $\ge 0.70$ News & OSINT significance threshold:
- **$E = 0$ New Events** (*Deduplicated against existing nodes [[2026-10 Sudan Drone Warfare Escalation]] and [[2026-10-19 Abyei Amiet Market and Todach Drone Strike]]*)
- **$A = 4$ New Actors** (`1` `media_source`, `1` `political_body`, `2` `person`)
- **$L = 0$ New Locations** (*Existing node [[Abyei]] refactored*)
- **$T = 0$ New Themes** (*Existing node [[Drone Proliferation and Double-Tap Strike Doctrine in Sudan]] refactored*)
- **$TL = 0$ New Timelines** (*Existing nodes [[2026-10 Sudan Conflict Chronicle]] and [[Sudan Drone Warfare and Double-Tap Strike Timeline]] refactored*)
- **$C = 2$ New Standalone Citations** (`2` `official_statement`: `1` `war_crimes_warning`, `1` `ceasefire_call`)
- **$K = 8$ Refactored Nodes**

---

## 3. Compiled Knowledge Nodes (`6` New Primitives + `1` Source)

| Domain / Type | Compiled Wiki Node | Subtype | Mechanistic & Forensic Summary |
| :--- | :--- | :--- | :--- |
| **Source** | [[sources/2026-10-31-unsg-spokesperson-escalating-drone-attacks-sudan]] | `official_communique` | Approved `A1` executive communiqué from the UN Secretary-General's Spokesperson condemning October 2026 drone attacks across Sudan and [[Abyei]]. |
| **Actor** | [[Office of the Spokesperson for the Secretary-General]] | `media_source` | Official executive communications office of the [[United Nations]] Secretary-General (`baseline_admiralty_reliability: A`). |
| **Actor** | [[United Nations]] | `political_body` | Intergovernmental organization led by [[António Guterres]] overseeing [[OHCHR]], [[UNISFA]], and Sudan mediation efforts. |
| **Actor** | [[Stéphane Dujarric]] | `person` | Spokesperson for the [[United Nations]] Secretary-General who delivered the 31 October 2026 statement on Sudan drone strikes. |
| **Actor** | [[António Guterres]] | `person` | Ninth Secretary-General of the [[United Nations]] who condemned the Sudan and [[Abyei]] drone strikes as IHL violations and called for an immediate cessation of hostilities. |
| **Citation** | [[2026-10-31 Stéphane Dujarric UNSG Statement Condemning Escalating Drone Attacks in Sudan and Abyei]] | `official_statement` | Verbatim statement delivered by [[Stéphane Dujarric]] declaring drone attacks across Sudan and [[Abyei]] killing hundreds of civilians and hitting health facilities to be IHL violations (`war_crimes_warning`, `A1`). |
| **Citation** | [[2026-10-31 António Guterres Appeal for Immediate Cessation of Hostilities and Good-Faith Mediation in Sudan]] | `official_statement` | Verbatim appeal by [[António Guterres]] calling on conflict parties to agree without delay to a cessation of hostilities and engage in good-faith mediation (`ceasefire_call`, `A1`). |

---

## 4. Refactored Nodes & Epistemic Evolution (`8` Refactored Nodes)

| Refactored Wiki Node | Domain | Epistemic & Structural Updates |
| :--- | :--- | :--- |
| [[2026-10 Sudan Drone Warfare Escalation]] | `event (campaign)` | Upgraded `admiralty_rating` from `A2` (`0.90`) to `A1` (`0.95`); added [[United Nations]] (`mediator`), `2026-10-31` UNSG IHL violation finding, and ceasefire demand. |
| [[2026-10-19 Abyei Amiet Market and Todach Drone Strike]] | `event (incident)` | Upgraded `admiralty_rating` from `A2` (`0.90`) to `A1` (`0.95`); added `2026-10-31` UNSG condemnation specifically citing drone attacks in [[Abyei]]. |
| [[Abyei]] | `location (locality_adm2)` | Upgraded `reliability_score` to `0.95`; appended `2026-10-31` UNSG IHL violation statement to Section 5 event log. |
| [[Sudanese Armed Forces]] | `actor (state_force)` | Appended `2026-10-31` UNSG condemnation of "parties to the conflict" and cessation-of-hostilities demand to Section 4 & Section 5 accountability table. |
| [[Rapid Support Forces]] | `actor (armed_group)` | Appended `2026-10-31` UNSG outrage over strikes on health facilities and cessation-of-hostilities demand to Section 3 & Section 5 accountability table. |
| [[Drone Proliferation and Double-Tap Strike Doctrine in Sudan]] | `theme (military_doctrine)` | Integrated `2026-10-31` UNSG IHL violation determination and health facility protection warnings into Sections 1, 2, 3, and 4. |
| [[2026-10 Sudan Conflict Chronicle]] | `timeline (monthly_chronicle)` | Upgraded `admiralty_rating` to `A1` (`0.95`); appended rows #9 and #10 (`2026-10-31` UNSG/Dujarric citations) to the October 2026 Bitemporal Ledger. |
| [[Sudan Drone Warfare and Double-Tap Strike Timeline]] | `timeline (thematic_timeline)` | Extended `end_date` to `2026-10-31`, upgraded `admiralty_rating` to `A1` (`0.95`), and appended rows #9 and #10 (`2026-10-31` UNSG/Dujarric citations) to the Bitemporal Ledger. |

---

## 5. Verification & Graph Telemetry

- **Formatting & Link Invariants**: Zero ASCII box art; zero backticked wikilinks; 100% escaped table pipes (`\|`); Dual-Flow Micro-CoT and Macro-CoT verified via `python3 scripts/lint_vault.py --cot`.
- **Database Synchronization**: Synchronized with `ki` (`wiki/.ki`) and ArcadeDB (`news`) via `scripts/ingest_to_arcadedb.py` and `./scripts/sync_vault_graph.sh`.
