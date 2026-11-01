---
title: "Ingestion: 2026-10-28-un-hrc-crp1-el-obeid-civilian-devastation"
type: "ingestion"
tags:
  - ingestion
  - audit
  - sudan
  - north-kordofan
  - el-obeid
  - um-badr
  - blue-nile
  - war-crimes
  - fact-finding-mission
date: 2026-11-01
last_updated: 2026-11-01
reliability_score: 0.95
sources:
  - "[[sources/2026-10-28-un-hrc-crp1-el-obeid-civilian-devastation]]"
source: "[[sources/2026-10-28-un-hrc-crp1-el-obeid-civilian-devastation]]"
events_created:
  - "[[2026-09-24 Um Badr Market Summary Executions]]"
  - "[[2026-10-10 Jabal al-Uqaydat Artisanal Gold Mine Airstrikes]]"
actors_created:
  - "[[Al-Baraa Ibn Malik Brigade]]"
  - "[[Sudan People's Liberation Movement-North (al-Hilu)]]"
locations_created:
  - "[[Kurmuk]]"
  - "[[Um Badr]]"
themes_created:
  - "[[Arbitrary Detention and Custodial Torture in the Sudan War]]"
timelines_created:
  - "[[2026-09 Sudan Conflict Chronicle]]"
citations_created:
  - "[[2026-10-28 UN FFM Finding on RSF Drone Warfare and Indiscriminate Attacks in El Obeid]]"
  - "[[2026-10-28 UN FFM Finding on SAF Detention Practices and Torture in El Obeid]]"
  - "[[2026-10-28 UN FFM Recommendation for Specialized Independent Court for Sudan]]"
nodes_refactored:
  - "[[2026-10 El Obeid Siege and Drone Warfare Escalation]]"
  - "[[2026-10 Sudan Drone Warfare Escalation]]"
  - "[[State Surveillance and Civic Space Contraction in Sudan]]"
  - "[[Drone Proliferation and Double-Tap Strike Doctrine in Sudan]]"
  - "[[International Accountability and Fact-Finding Mechanisms in Sudan]]"
  - "[[Sudanese Armed Forces]]"
  - "[[Rapid Support Forces]]"
  - "[[El Obeid]]"
  - "[[North Kordofan]]"
  - "[[Blue Nile State]]"
  - "[[Abyei]]"
  - "[[2026-10 Sudan Conflict Chronicle]]"
  - "[[Sudan Accountability and International Justice Timeline]]"
  - "[[Sudan Drone Warfare and Double-Tap Strike Timeline]]"
contradictions_logged:
  - "ATTRIBUTION_CONFLICT"
  - "TARGET_FRAMING_CONFLICT"
---

# Ingestion Audit Dossier: `2026-10-28-un-hrc-crp1-el-obeid-civilian-devastation`

## 1. Provenance & Execution Context

| Attribute | Value |
| :--- | :--- |
| **Origin Raw File** | `raw/reports/a-hrc-65-crp-1.pdf` |
| **Approved Source Note** | [[sources/2026-10-28-un-hrc-crp1-el-obeid-civilian-devastation]] (`status: approved`, `compiled: true`) |
| **Publishing Outlet** | [[Independent International Fact-Finding Mission for the Sudan]] (`subtype: media_source`, `alignment: international_org`) |
| **NATO Admiralty Rating** | **`A1`** (`reliability_score: 0.95`) |
| **Publication Date ($t_{\text{reported}}$)** | `2026-10-28` |
| **Compilation Date ($t_{\text{compiled}}$)** | `2026-11-01` |
| **Pipeline Mode** | Phase 2 Approved Entity Compilation & Refactoring (`/wiki-ingest --approved`) |

---

## 2. Scoped Ingestion Manifest & Scoring

All candidate primitives and refactor targets met or exceeded the $\ge 0.70$ News & OSINT significance threshold:
- **$E = 2$ New Events** (`2` `incident`: `2026-09-24 Um Badr Market Summary Executions`, `2026-10-10 Jabal al-Uqaydat Artisanal Gold Mine Airstrikes`)
- **$A = 2$ New Actors** (`1` `armed_group`: `Al-Baraa Ibn Malik Brigade`, `1` `armed_group`: `Sudan People's Liberation Movement-North (al-Hilu)`)
- **$L = 2$ New Locations** (`1` `locality_adm2`: `Um Badr`, `1` `city_town`: `Kurmuk`)
- **$T = 1$ New Theme** (`1` `humanitarian_driver`: `Arbitrary Detention and Custodial Torture in the Sudan War`)
- **$TL = 1$ New Timeline** (`1` `monthly_chronicle`: `2026-09 Sudan Conflict Chronicle`)
- **$C = 3$ New Standalone Citations** (`2` `forensic_finding`, `1` `diplomatic_resolution`)
- **$K = 14$ Refactored Domain Nodes**

---

## 3. Compiled Knowledge Nodes (`11` New Primitives + `1` Source)

| Domain / Type | Compiled Wiki Node | Subtype | Mechanistic & Forensic Summary |
| :--- | :--- | :--- | :--- |
| **Source** | [[sources/2026-10-28-un-hrc-crp1-el-obeid-civilian-devastation]] | `official_communique` | Approved `A1` 19-page Conference Room Paper (A/HRC/65/CRP.1) detailing civilian devastation, drone warfare, and detention practices in El Obeid. |
| **Event** | [[2026-09-24 Um Badr Market Summary Executions]] | `incident` | RSF execution of 25 bound detainees in Um Badr market, North Kordofan (`SD02005`), established as a Common Article 3 war crime. |
| **Event** | [[2026-10-10 Jabal al-Uqaydat Artisanal Gold Mine Airstrikes]] | `incident` | SAF jet airstrikes on Jabal al-Uqaydat artisanal gold-mining site near the Egyptian border, killing 72+ miners. |
| **Actor** | [[Al-Baraa Ibn Malik Brigade]] | `armed_group` | Islamist paramilitary auxiliary battalion integrated with SAF and GIS, operationalizing billets and Security Cells in El Obeid. |
| **Actor** | [[Sudan People's Liberation Movement-North (al-Hilu)]] | `armed_group` | Armed political-military movement active across the Nuba Mountains and southern Blue Nile State, maintaining presence around Kurmuk. |
| **Location** | [[Um Badr]] | `locality_adm2` | Locality and trade hub in western North Kordofan (`SD02005`), site of RSF 24 September summary executions. |
| **Location** | [[Kurmuk]] | `city_town` | Strategic border town in Blue Nile State (`SD17002`) on the Ethiopian frontier, cross-border relief transit corridor. |
| **Theme** | [[Arbitrary Detention and Custodial Torture in the Sudan War]] | `humanitarian_driver` | Structural conflict mechanism detailing the emergency "Security Cells", detention overcrowding in El Obeid Central Prison, and custodial torture. |
| **Timeline** | [[2026-09 Sudan Conflict Chronicle]] | `monthly_chronicle` | Comprehensive September 2026 bitemporal conflict ledger tracking ground counteroffensives, airstrikes, and summary executions. |
| **Citation** | [[2026-10-28 UN FFM Finding on RSF Drone Warfare and Indiscriminate Attacks in El Obeid]] | `forensic_finding` | UN FFM finding establishing RSF loitering munition attacks on schools, medical facilities, funerals, and first responders. |
| **Citation** | [[2026-10-28 UN FFM Finding on SAF Detention Practices and Torture in El Obeid]] | `forensic_finding` | UN FFM finding establishing SAF-GIS Security Cells, custodial torture, overcrowding of 2,000+ detainees, and residential co-location of billets. |
| **Citation** | [[2026-10-28 UN FFM Recommendation for Specialized Independent Court for Sudan]] | `diplomatic_resolution` | UN FFM recommendation in Para 84 calling for the establishment of a specialized independent judicial mechanism for Sudan. |

---

## 4. Refactored Nodes & Epistemic Evolution (`14` Refactored Nodes)

| Refactored Wiki Node | Domain | Epistemic & Structural Updates |
| :--- | :--- | :--- |
| [[2026-10 El Obeid Siege and Drone Warfare Escalation]] | `event (crisis)` | Enriched with full June–October chronological sequence, hospital damage (Maternity, Kuwaiti), and educational strikes (Shikan, Technical College, Dormitory). |
| [[2026-10 Sudan Drone Warfare Escalation]] | `event (campaign)` | Added Wad al-Mahi (30+ killed) and El Obeid dormitory strike (5 dead, 47 wounded) to chronological ledger and updated sources. |
| [[State Surveillance and Civic Space Contraction in Sudan]] | `theme (political_dynamic)` | Enriched with transnational repression against diaspora figures in Chad, Kenya, Uganda, and UK, and emergency Security Cell mechanics. |
| [[Drone Proliferation and Double-Tap Strike Doctrine in Sudan]] | `theme (military_doctrine)` | Added FFM Para 19 findings on repeat double-tap strikes targeting rescue workers assisting previous strike victims and funeral gatherings. |
| [[International Accountability and Fact-Finding Mechanisms in Sudan]] | `theme (political_dynamic)` | Added FFM CRP.1 findings and the landmark Para 84 recommendation for a specialized independent judicial court for Sudan. |
| [[Sudanese Armed Forces]] | `actor (state_force)` | Added [[Al-Baraa Ibn Malik Brigade]] alliance, El Obeid residential co-location findings, custodial war crimes, and Jabal al-Uqaydat airstrikes. |
| [[Rapid Support Forces]] | `actor (armed_group)` | Added North Kordofan footprint, Um Badr Common Article 3 summary executions, and systematic drone strikes on educational facilities. |
| [[El Obeid]] | `location (city_town)` | Enriched healthcare status (30% functional), water supply cutoff from Bara, Central Prison overcrowding (2,000+ inmates), and June–Oct strike log. |
| [[North Kordofan]] | `location (state_adm1)` | Updated territorial control shifts (Bara recaptured July; Sodari recaptured Sept 25; Al-Mazroub Oct 2) and Um Badr execution log. |
| [[Blue Nile State]] | `location (state_adm1)` | Added [[Kurmuk]] (`SD17002`), [[Sudan People's Liberation Movement-North (al-Hilu)]] armed contestation, and Wad al-Mahi strike. |
| [[Abyei]] | `location (locality_adm2)` | Cross-referenced FFM CRP.1 Para 39 recognition of the 19 October Amiet market strike. |
| [[2026-10 Sudan Conflict Chronicle]] | `timeline (monthly_chronicle)` | Added El Obeid dorm strike, Jabal al-Uqaydat airstrikes, Wad al-Mahi strike, and three FFM citation entries to Bitemporal Ledger; updated fatalities best to 510+. |
| [[Sudan Accountability and International Justice Timeline]] | `timeline (diplomatic_timeline)` | Added Um Badr executions, FFM findings on RSF/SAF war crimes, and specialized court recommendation to ledger and mermaid graph. |
| [[Sudan Drone Warfare and Double-Tap Strike Timeline]] | `timeline (thematic_timeline)` | Added FFM verified rescue and funeral double-tap strikes to ledger and updated Related Primitives. |

---

## 5. Verification & Graph Telemetry

- **Validation Status**: All 11 new nodes authored in full Micro-CoT / 5W1H format with valid YAML frontmatter and strict Admiralty ratings.
- **Relational Integrity**: 100% Obsidian clean wikilinks, escaped table pipes (`\|`), no backticked wikilinks.
- **Graph Updates**: Master catalogs (`wiki/index.md`, `wiki/overview.md`, `wiki/glossary.md`, `wiki/log.md`) updated, vault linting verified, and ArcadeDB multi-model graph synchronized.
