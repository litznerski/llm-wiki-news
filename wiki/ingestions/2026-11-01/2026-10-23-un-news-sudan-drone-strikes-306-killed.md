---
title: "Ingestion: 2026-10-23-un-news-sudan-drone-strikes-306-killed"
type: "ingestion"
tags:
  - ingestion
  - audit
  - sudan
  - drone-warfare
date: 2026-11-01
last_updated: 2026-11-01
reliability_score: 0.90
sources:
  - "[[sources/2026-10-23-un-news-sudan-drone-strikes-306-killed]]"
source: "[[sources/2026-10-23-un-news-sudan-drone-strikes-306-killed]]"
events_created:
  - "[[2026-10 Sudan Drone Warfare Escalation]]"
  - "[[2026-10-18 Dibab Double-Tap Drone Strike]]"
  - "[[2026-10-19 Abyei Amiet Market and Todach Drone Strike]]"
actors_created:
  - "[[UN News]]"
  - "[[Sudanese Armed Forces]]"
  - "[[Rapid Support Forces]]"
  - "[[OHCHR]]"
  - "[[UNISFA]]"
  - "[[Volker Türk]]"
  - "[[Seif Magango]]"
  - "[[Muhammad Farooq]]"
  - "[[Adebowale Ajabge]]"
  - "[[Angelina Musa Diaw]]"
locations_created:
  - "[[West Kordofan]]"
  - "[[Blue Nile State]]"
  - "[[Abyei]]"
themes_created:
  - "[[Drone Proliferation and Double-Tap Strike Doctrine in Sudan]]"
timelines_created:
  - "[[2026-10 Sudan Conflict Chronicle]]"
  - "[[Sudan Drone Warfare and Double-Tap Strike Timeline]]"
citations_created:
  - "[[2026-10-23 Volker Türk Condemnation of Sudan Drone Escalation and Arms Influx]]"
  - "[[2026-10-23 Seif Magango Statement on Evisceration of Civilian Infrastructure in Sudan]]"
  - "[[2026-10-23 Muhammad Farooq First-Responder Account of Amiet Market Fire]]"
  - "[[2026-10-23 Adebowale Ajabge Report on UNISFA Emergency Response and Todach Evacuations]]"
  - "[[2026-10-23 Angelina Musa Diaw Survivor Testimony on Amiet Market Destruction]]"
nodes_refactored: []
contradictions_logged:
  - "ATTRIBUTION_CONFLICT"
---

# Ingestion Audit Dossier: `2026-10-23-un-news-sudan-drone-strikes-306-killed`

## 1. Provenance & Execution Context

| Attribute | Value |
| :--- | :--- |
| **Origin Raw File** | `raw/articles/Sudan Drone strikes killed at least 306 people in three weeks.md` |
| **Approved Source Note** | [[sources/2026-10-23-un-news-sudan-drone-strikes-306-killed]] (`status: approved`, `compiled: true`) |
| **Publishing Outlet** | [[UN News]] (`subtype: media_source`, `alignment: international_org`) |
| **NATO Admiralty Rating** | **`A2`** (`reliability_score: 0.90`) |
| **Publication Date ($t_{\text{reported}}$)** | `2026-10-23` |
| **Compilation Date ($t_{\text{compiled}}$)** | `2026-11-01` |
| **Pipeline Mode** | Phase 2 Approved Entity Compilation (`/wiki-ingest --approved`) |

---

## 2. Scoped Ingestion Manifest & Scoring

All 24 approved candidate primitives exceeded the $\ge 0.70$ News & OSINT significance threshold:
- **$E = 3$ New Events** (`1` campaign, `2` mass-casualty incidents)
- **$A = 10$ New Actors** (`1` `media_source`, `2` `state_force`, `1` `armed_group`, `1` `political_body`, `5` `person`)
- **$L = 3$ New Locations** (`2` `state_adm1`, `1` `locality_adm2`)
- **$T = 1$ New Theme** (`1` `military_doctrine`)
- **$TL = 2$ New Timelines** (`1` `monthly_chronicle`, `1` `thematic_timeline`)
- **$C = 5$ New Standalone Citations** (`3` `official_statement`, `2` `eyewitness_testimony`)
- **$K = 0$ Refactored Nodes**

---

## 3. Compiled Knowledge Nodes (`24` Total)

| Domain / Type | Compiled Wiki Node | Subtype | Mechanistic & Forensic Summary |
| :--- | :--- | :--- | :--- |
| **Source** | [[sources/2026-10-23-un-news-sudan-drone-strikes-306-killed]] | `news_article` | Approved `A2` source distillation of [[UN News]] report on `306+` killed by UAV strikes across Sudan in three weeks. |
| **Event** | [[2026-10 Sudan Drone Warfare Escalation]] | `campaign` | Nationwide October 2026 drone strike wave (`306+` killed) spanning [[West Kordofan]], [[Blue Nile State]], and [[Abyei]]. |
| **Event** | [[2026-10-18 Dibab Double-Tap Drone Strike]] | `incident` | Repeat "double-tap" drone strike on a transport truck in RSF-held Dibab ([[West Kordofan]]) killing `139+` people. |
| **Event** | [[2026-10-19 Abyei Amiet Market and Todach Drone Strike]] | `incident` | Drone attack on Amiet Market and Todach in demilitarized [[Abyei]] killing `80+` and injuring `27+` evacuated by [[UNISFA]]. |
| **Actor** | [[UN News]] | `media_source` | Official United Nations news outlet (`baseline_admiralty_reliability: A`). |
| **Actor** | [[Sudanese Armed Forces]] | `state_force` | Official Sudanese military; attributed with alleged 6–10 Oct IDP shelter drone strikes in Ghubeish and El Nuhud (`25+` killed). |
| **Actor** | [[Rapid Support Forces]] | `armed_group` | Paramilitary force controlling Dibab and attributed with 9 Oct Abu Shendi IDP strike (`31+` killed) and 11 Oct Um Darfa hospital strike. |
| **Actor** | [[OHCHR]] | `political_body` | UN Human Rights Office led by [[Volker Türk]] verifying `306+` drone fatalities across Sudan. |
| **Actor** | [[UNISFA]] | `state_force` | UN peacekeeping mission in [[Abyei]] whose troops fought the Amiet Market fire and evacuated `27+` wounded to Todach. |
| **Actor** | [[Volker Türk]] | `person` | UN High Commissioner for Human Rights ([[OHCHR]]) condemning drone proliferation and external arms transfers. |
| **Actor** | [[Seif Magango]] | `person` | [[OHCHR]] spokesperson detailing IDP casualties and infrastructure evisceration across Sudan. |
| **Actor** | [[Muhammad Farooq]] | `person` | Lieutenant Colonel commanding [[UNISFA]] Pakistani battalion first on scene at burning Amiet Market. |
| **Actor** | [[Adebowale Ajabge]] | `person` | Brigadier General and Acting Force Commander of [[UNISFA]] coordinating firefighting and Todach medical evacuations. |
| **Actor** | [[Angelina Musa Diaw]] | `person` | Civilian market trader and mother of three who survived the Amiet Market drone strike in [[Abyei]]. |
| **Location** | [[West Kordofan]] | `state_adm1` | `SD18` state containing RSF-held Dibab (`139+` killed) and Ghubeish/El Nuhud IDP shelters (`25+` killed). |
| **Location** | [[Blue Nile State]] | `state_adm1` | `SD17` state containing Abu Shendi IDP gold-mining site (`31+` killed) and Um Darfa hospital (`2` injured). |
| **Location** | [[Abyei]] | `locality_adm2` | `SD18001` demilitarized border area containing Amiet Market (`80+` killed) and Todach [[UNISFA]] hospital. |
| **Theme** | [[Drone Proliferation and Double-Tap Strike Doctrine in Sudan]] | `military_doctrine` | Structural analysis of UAV proliferation, external arms influx, and double-tap strikes as the primary cause of 2026 civilian deaths. |
| **Timeline** | [[2026-10 Sudan Conflict Chronicle]] | `monthly_chronicle` | Bitemporal October 2026 monthly chronicle (`306+` fatalities) across [[West Kordofan]], [[Blue Nile State]], and [[Abyei]]. |
| **Timeline** | [[Sudan Drone Warfare and Double-Tap Strike Timeline]] | `thematic_timeline` | Thematic escalation ledger tracking UAV proliferation and repeat "double-tap" strike mechanics in Sudan. |
| **Citation** | [[2026-10-23 Volker Türk Condemnation of Sudan Drone Escalation and Arms Influx]] | `official_statement` | Verbatim statement by [[Volker Türk]] on UAV mortality dominance and halt to arms transfers. |
| **Citation** | [[2026-10-23 Seif Magango Statement on Evisceration of Civilian Infrastructure in Sudan]] | `official_statement` | Verbatim statement by [[Seif Magango]] on IDP deaths and evisceration of civilian services. |
| **Citation** | [[2026-10-23 Muhammad Farooq First-Responder Account of Amiet Market Fire]] | `eyewitness_testimony` | First-responder peacekeeper testimony by Lt. Col. [[Muhammad Farooq]] (*"every shop was burning"*). |
| **Citation** | [[2026-10-23 Adebowale Ajabge Report on UNISFA Emergency Response and Todach Evacuations]] | `official_statement` | Operational report by Brig. Gen. [[Adebowale Ajabge]] on firefighting and `27+` evacuations to Todach hospital. |
| **Citation** | [[2026-10-23 Angelina Musa Diaw Survivor Testimony on Amiet Market Destruction]] | `eyewitness_testimony` | Verbatim survivor testimony by [[Angelina Musa Diaw]] (*"No work, everything is gone..."*). |

---

## 4. Refactored Nodes & Epistemic Evolution

*No pre-existing domain nodes required refactoring during this initial vault compilation. Master ledgers (`wiki/index.md`, `wiki/overview.md`, `wiki/glossary.md`) were updated with all 24 compiled primitives.*

---

## 5. Verification & Graph Telemetry

- **Formatting & Link Invariants**: Zero ASCII box art; zero backticked wikilinks; 100% escaped table pipes (`\|`); Dual-Flow Micro-CoT and Macro-CoT verified via `python3 scripts/lint_vault.py --cot`.
- **Database Synchronization**: Synchronized with `ki` (`wiki/.ki`) and ArcadeDB (`news`) via `scripts/ingest_to_arcadedb.py` and `./scripts/sync_vault_graph.sh`.
