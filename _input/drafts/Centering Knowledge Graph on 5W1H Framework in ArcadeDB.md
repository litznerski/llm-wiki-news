---
title: "Centering Knowledge Graph on 5W1H Framework in ArcadeDB: In-Engine Algorithmic Multi-Pass Engine, Raw Article Storage, Section Node Retirement, and Ingestion Rework"
task_origin: "[[_input/tasks/archived/Update Centering KG on 5WH1.md]]"
sources:
  - "[[_input/research/How can I leverage 5WH1 in a knowledge graph to i....md]]"
  - "[[_input/drafts/Contradiction Missing Ingestion Analysis and Implementation Plan.md]]"
  - "[[_input/drafts/Sudan News LLM-Wiki Architecture and Ontology Specification.md]]"
  - "[[_input/tasks/archived/Center on 5WH1.md]]"
  - "[[2026-10-28 Global Civil Society Briefing Opposing Lana Nusseibeh Candidacy for UN Secretary-General]]"
  - "[[2026-10-27 Nyala Tanqonj Market Drone Strike]]"
date: 2026-11-03
---

# Centering Knowledge Graph on 5W1H Framework in ArcadeDB: In-Engine Algorithmic Multi-Pass Engine, Raw Article Storage, Section Node Retirement, and Ingestion Rework

> [!IMPORTANT] Executive Summary & Strategic Architecture Pivot
> This document formalizes the updated production blueprint for centering the **ArcadeDB (`news`)** knowledge graph on the **5W1H Framework (Who, What, Where, When, Why, How)**, incorporating four definitive architectural directives:
> 
> 1. **Option C Selection (In-Engine Algorithmic Multi-Pass Pipeline)**:
>    Adopt the automated multi-pass pipeline as the primary ingestion architecture. Raw news articles are ingested directly into ArcadeDB as first-class `RawArticle` vertices. Vector similarity and spatio-temporal alignment are executed **entirely within ArcadeDB** using its embedded JVector (`LSM_VECTOR`) index and native in-engine Graph OLAP procedures (`CALL algo.fastrp(...)`), eliminating the need for external vector databases, local sidecar daemons, or heavy dependencies.
> 
> 2. **Retirement & Decommissioning of `Section` Nodes**:
>    `Section` vertices—originally created to represent the Markdown Abstract Syntax Tree (AST)—are formally retired. They represent document layout rather than domain intelligence, inflating the graph with 1,530 redundant nodes (64% of all vertices) and adding artificial traversal hops. All epistemic roles, Toulmin argumentation roles, and evidentiary weights are reassigned directly to first-class **`(:Claim)`** and **`(:Citation)`** nodes.
> 
> 3. **The Reified 5W1H Claim Plane**:
>    Each empirical assertion is reified as a discrete `(:Claim)` vertex connected to its originating `(:RawArticle)` via `[:ASSERTS]`, to its physical incident via `[:RESOLVES_TO]`, and to domain entities via typed 5W1H edges (`[:WHO]`, `[:WHAT]`, `[:WHERE]`, `[:WHEN]`, `[:WHY]`, `[:HOW]`).
> 
> 4. **Vault-Wide Migration of Existing Ingestions**:
>    A complete migration strategy and executable procedure are established to rework all 32+ existing compiled sources and 35+ conflict events into the new 5W1H Claim-centric schema, backfilling `RawArticle` vertices, materializing granular claims, and computing pairwise contradiction and omission matrices across the entire vault.

---

## 1. Architectural Foundation: The Streamlined 5W1H Semantic Plane

### 1.1 Structural Comparison: Legacy AST Model vs. 5W1H Claim Plane

```mermaid
flowchart TD
    subgraph Legacy_Model["Legacy Model - Bloated Document AST with 1530 Section Nodes"]
        direction TB
        SRC_LEG["Source Note"] -->|EMPIRICALLY_GROUNDS| EV_LEG["Event Note"]
        EV_LEG -->|HAS_SECTION| SEC_1["Section 1 - 5W1H Anchor - Role GROUNDS"]
        SEC_1 -->|PROGRESSES_TO| SEC_2["Section 2 - Tactical - Role WARRANT"]
        SEC_2 -->|PROGRESSES_TO| SEC_3["Section 3 - Motives - Role CLAIM"]
        SEC_3 -->|PROGRESSES_TO| SEC_4["Section 4 - Impact - Role SOLUTION"]
        SEC_4 -->|PROGRESSES_TO| SEC_5["Section 5 - Contradictions - Role REBUTTAL"]
        SEC_1 -.->|LINKS_TO| ACT_LEG["Actor Node"]
        SEC_1 -.->|LINKS_TO| LOC_LEG["Location Node"]
    end

    subgraph Target_Model["Target Model - Streamlined 5W1H Semantic Plane with Zero Sections"]
        direction TB
        RAW["RawArticle - Full Text and Metadata and JVector Embedding"]
        RAW -->|ASSERTS| CLM_1["Claim CLM-01 - Assertion with Polarity and Confidence"]
        RAW -->|ASSERTS| CLM_2["Claim CLM-02 - Secondary Proposition"]

        CLM_1 -->|WHO perpetrator| ACT_TGT["Actor - Rapid Support Forces"]
        CLM_1 -->|WHAT| ACTN_TGT["ActionType - Drone Strike"]
        CLM_1 -->|WHERE| LOC_TGT["Location - Nyala Market"]
        CLM_1 -->|WHEN| TIME_TGT["TimeInterval - 2026-10-27"]
        CLM_1 -->|WHY| MOT_TGT["Theme - Air Superiority Counter"]
        CLM_1 -->|HOW| INST_TGT["Instrument - Mohajer-6 UAV"]

        CLM_1 -->|RESOLVES_TO| CAN_EV["Event - Nyala Market Drone Strike"]
        CLM_2 -->|RESOLVES_TO| CAN_EV

        CIT["Citation - Verbatim Evidence and Speaker"] -->|SUPPORTS| CLM_1
        CLM_1 ---|CONTRADICTS ACTOR_MISMATCH| CLM_OPP["Claim CLM-OPP from State Media"]
        CLM_2 -. OMITS HOW .-> GAP["Missing Element Detected"]
    end
```

### 1.2 Two-Layer Event-Observation Architecture
The knowledge graph is partitioned into two clear planes:
1. **Observation / Claim Layer (Epistemic & Source-Specific)**:
   - **`(:RawArticle)`**: Direct representation of primary evidence stored in ArcadeDB.
   - **`(:Claim)`**: Granular empirical proposition extracted from an article. A single article can assert multiple claims (e.g., strike execution, casualty count, military target justification).
   - **5W1H Dimension Edges**: Connect `Claim` directly to domain nodes (`Actor`, `Location`, `Theme`, `Instrument`).
2. **Canonical Event Layer (Ontological & Synthesized)**:
   - **`(:Event)`**: The physical, real-world incident.
   - Claims resolving to the same event connect via `[:RESOLVES_TO {confidence: float, method: 'in_engine_alignment'}]`.
   - Cross-claim validation runs between claims linked to the same event, generating explicit `[:CORROBORATES]`, `[:CONTRADICTS]`, and `[:OMITS]` edges.

---

## 2. In-Depth Architectural Review: Retirement of `Section` Nodes

### 2.1 The Problem with `Section` Nodes
The active database currently contains **2,378 vertices**, of which **1,530 are `Section` vertices** (64.3%) and **731 are `PROGRESSES_TO` edges**. An architectural evaluation reveals three critical flaws in maintaining `Section` nodes:

1. **Document-Centric vs. Knowledge-Centric Anti-Pattern**:
   - `Section` vertices represent *Markdown typographic headings* (`# Heading 1`, `## Heading 2`), not real-world conflict dynamics.
   - In conflict intelligence, queries ask: *"Which belligerents are using drones against power infrastructure?"*, not *"Which H2 heading in which markdown file follows Section 3?"*.
   - Navigating through `Event -> HAS_SECTION -> Section -> LINKS_TO -> Actor` creates two artificial hops per traversal, degrading query readability and execution speed.

2. **Coarse & Arbitrary Epistemic Assignment**:
   - A 500-word markdown section is assigned a single monolithic Toulmin role (e.g., `GROUNDS`), even if the paragraph contains three verified factual assertions, an unverified rumor, and a denial.
   - Assigning confidence weights to an arbitrary section text block is epistemically coarse; confidence belongs on specific, verifiable **Claims**.

3. **Schema Redundancy with `Claim` Nodes**:
   - A `Claim` node is already a typed, reified proposition with properties for `text`, `polarity`, `confidence`, and `modality`.
   - Keeping both `Section` and `Claim` creates dual-maintenance overhead: does a `Citation` support the `Section` or the `Claim`? Does an `Actor` participate in the `Section` or the `Claim`?

### 2.2 Formal Decommissioning Decision
- **Action**: Completely drop the `Section` vertex type and its associated edges (`HAS_SECTION`, `NEXT_SECTION`, `PROGRESSES_TO`) from ArcadeDB.
- **Epistemic Migration**:
  - **Toulmin Roles**: Reassigned to `Claim.toulmin_role` (`assertion`, `warrant`, `grounds`, `rebuttal`, `backing`).
  - **Modal Weight**: Reassigned to `Claim.confidence` (`0.0` to `1.0`) and `Claim.verification_status`.
  - **Verbatim Text**: Tied directly to `Citation` and `RawArticle`.
- **Result**: The graph vertex count drops by ~64%, query latency drops significantly, and every vertex in ArcadeDB becomes a high-signal semantic entity.

---

## 3. In-Engine Raw Article Storage & Native ArcadeDB Vector Similarity

### 3.1 Raw Article Storage Directly in ArcadeDB
Primary news articles from `raw/articles/` are stored directly in ArcadeDB under the `RawArticle` vertex type:

| Property | Type | Description |
| :--- | :--- | :--- |
| `article_id` | `STRING` (Indexed Unique) | Deterministic slug or SHA-256 hash of article URL / file path |
| `title` | `STRING` | Article headline |
| `url` | `STRING` | Original web source URL |
| `source_outlet` | `STRING` | Outlet name (e.g., "Radio Dabanga", "Sudan Tribune") |
| `published_date` | `STRING` | ISO-8601 publication date (`YYYY-MM-DD`) |
| `language` | `STRING` | ISO code (`ar`, `en`, `fr`) |
| `content` | `STRING` | Full clean article body text |
| `word_count` | `INTEGER` | Word count of the text |
| `embedding` | `LIST OF FLOAT` | 768-dimensional vector embedding for in-engine semantic search |
| `ingested_at` | `STRING` | Timestamp of ingestion |

### 3.2 Native Vector Indexing with Embedded JVector (`LSM_VECTOR`)
ArcadeDB includes embedded **JVector**, eliminating any need for Chroma, Qdrant, Milvus, or external vector sidecars:

```sql
-- Create LSM_VECTOR index directly inside ArcadeDB on RawArticle embedding
CREATE INDEX ON RawArticle (embedding) LSM_VECTOR METADATA {
    "dimensions": 768,
    "similarity": "COSINE",
    "quantization": "INT8"
};

-- Create LSM_VECTOR index on Claim embedding
CREATE INDEX ON Claim (embedding) LSM_VECTOR METADATA {
    "dimensions": 768,
    "similarity": "COSINE",
    "quantization": "INT8"
};
```

### 3.3 In-Engine Semantic Search & Event Alignment
To match incoming raw articles and claims to existing canonical events without external ML frameworks:

```sql
-- 1. Find the 5 most semantically similar raw articles to a query embedding
SELECT article_id, title, source_outlet, published_date,
       vectorNeighbors('RawArticle[embedding]', :query_vector, 5) AS distance
FROM RawArticle
ORDER BY distance ASC;

-- 2. Find matching claims for event alignment
SELECT claim_id, text, extracted_from,
       vectorNeighbors('Claim[embedding]', :claim_vector, 5) AS distance
FROM Claim
ORDER BY distance ASC;
```

### 3.4 In-Engine Graph Embeddings via `CALL algo.fastrp(...)`
In addition to text embeddings, ArcadeDB generates native structural graph embeddings directly on vertices using FastRP:

```cypher
-- Generate 768-dimensional graph topology embeddings directly in ArcadeDB
CALL algo.fastrp({
    dimensions: 768,
    iterations: 4,
    normalization: -0.5,
    direction: "BOTH"
})
YIELD node, embedding
SET node.graph_embedding = embedding;
```

---

## 4. Complete ArcadeDB DDL Schema Specification

The following SQL DDL statements establish the streamlined 5W1H data model and purge the legacy `Section` vertices:

```sql
-- =============================================================================
-- 1. Purge Legacy Section Vertices and Edges
-- =============================================================================
DROP EDGE TYPE IF EXISTS HAS_SECTION;
DROP EDGE TYPE IF EXISTS NEXT_SECTION;
DROP EDGE TYPE IF EXISTS PROGRESSES_TO;
DROP VERTEX TYPE IF EXISTS Section;

-- =============================================================================
-- 2. Core Primary Evidence: RawArticle
-- =============================================================================
CREATE VERTEX TYPE RawArticle IF NOT EXISTS;
CREATE PROPERTY RawArticle.article_id IF NOT EXISTS STRING;
CREATE PROPERTY RawArticle.title IF NOT EXISTS STRING;
CREATE PROPERTY RawArticle.url IF NOT EXISTS STRING;
CREATE PROPERTY RawArticle.source_outlet IF NOT EXISTS STRING;
CREATE PROPERTY RawArticle.published_date IF NOT EXISTS STRING;
CREATE PROPERTY RawArticle.language IF NOT EXISTS STRING;
CREATE PROPERTY RawArticle.content IF NOT EXISTS STRING;
CREATE PROPERTY RawArticle.word_count IF NOT EXISTS INTEGER;
CREATE PROPERTY RawArticle.embedding IF NOT EXISTS LIST OF FLOAT;
CREATE PROPERTY RawArticle.ingested_at IF NOT EXISTS STRING;
CREATE INDEX IF NOT EXISTS ON RawArticle (article_id) UNIQUE;
CREATE INDEX IF NOT EXISTS ON RawArticle (source_outlet) NOTUNIQUE;

-- =============================================================================
-- 3. The Reified Claim Vertex
-- =============================================================================
CREATE VERTEX TYPE Claim IF NOT EXISTS;
CREATE PROPERTY Claim.claim_id IF NOT EXISTS STRING;
CREATE PROPERTY Claim.text IF NOT EXISTS STRING;
CREATE PROPERTY Claim.claim_type IF NOT EXISTS STRING; -- assertion, casualty_report, attribution, denial, motive
CREATE PROPERTY Claim.toulmin_role IF NOT EXISTS STRING; -- grounds, warrant, claim, backing, rebuttal
CREATE PROPERTY Claim.polarity IF NOT EXISTS STRING; -- positive, negative, conditional
CREATE PROPERTY Claim.confidence IF NOT EXISTS FLOAT;
CREATE PROPERTY Claim.reported_date IF NOT EXISTS STRING;
CREATE PROPERTY Claim.valid_date IF NOT EXISTS STRING;
CREATE PROPERTY Claim.extracted_from IF NOT EXISTS STRING; -- article_id or source_slug
CREATE PROPERTY Claim.embedding IF NOT EXISTS LIST OF FLOAT;
CREATE INDEX IF NOT EXISTS ON Claim (claim_id) UNIQUE;

-- =============================================================================
-- 4. Categorical Ontological Vertices
-- =============================================================================
CREATE VERTEX TYPE ActionType IF NOT EXISTS;
CREATE PROPERTY ActionType.name IF NOT EXISTS STRING;
CREATE INDEX IF NOT EXISTS ON ActionType (name) UNIQUE;

CREATE VERTEX TYPE Instrument IF NOT EXISTS;
CREATE PROPERTY Instrument.name IF NOT EXISTS STRING;
CREATE PROPERTY Instrument.category IF NOT EXISTS STRING; -- uav, artillery, small_arms, missile, air_bomb
CREATE INDEX IF NOT EXISTS ON Instrument (name) UNIQUE;

-- =============================================================================
-- 5. Provenance & Alignment Edges
-- =============================================================================
CREATE EDGE TYPE ASSERTS IF NOT EXISTS;
CREATE PROPERTY ASSERTS.confidence IF NOT EXISTS FLOAT;

CREATE EDGE TYPE RESOLVES_TO IF NOT EXISTS;
CREATE PROPERTY RESOLVES_TO.confidence IF NOT EXISTS FLOAT;
CREATE PROPERTY RESOLVES_TO.method IF NOT EXISTS STRING;

CREATE EDGE TYPE PUBLISHED_BY IF NOT EXISTS;

-- =============================================================================
-- 6. The 5W1H Dimension Edges
-- =============================================================================
CREATE EDGE TYPE WHO IF NOT EXISTS;
CREATE PROPERTY WHO.role IF NOT EXISTS STRING; -- perpetrator, target, victim, mediator, reporter

CREATE EDGE TYPE WHAT IF NOT EXISTS;
CREATE PROPERTY WHAT.aspect IF NOT EXISTS STRING;

CREATE EDGE TYPE WHERE IF NOT EXISTS;
CREATE PROPERTY WHERE.precision IF NOT EXISTS STRING; -- exact_coords, neighborhood, city, locality, state

CREATE EDGE TYPE WHEN IF NOT EXISTS;
CREATE PROPERTY WHEN.precision IF NOT EXISTS STRING; -- exact_time, day, week

CREATE EDGE TYPE WHY IF NOT EXISTS;
CREATE PROPERTY WHY.motive_type IF NOT EXISTS STRING; -- retaliation, territorial_expansion, ethnic_cleansing, defense

CREATE EDGE TYPE HOW IF NOT EXISTS;
CREATE PROPERTY HOW.modality IF NOT EXISTS STRING; -- direct_fire, loitering_munition, barrel_bomb, ambush

-- =============================================================================
-- 7. Cross-Claim Analytical Edges
-- =============================================================================
CREATE EDGE TYPE CORROBORATES IF NOT EXISTS;
CREATE PROPERTY CORROBORATES.dimensions IF NOT EXISTS LIST OF STRING;
CREATE PROPERTY CORROBORATES.confidence IF NOT EXISTS FLOAT;

CREATE EDGE TYPE CONTRADICTS IF NOT EXISTS;
CREATE PROPERTY CONTRADICTS.dimension IF NOT EXISTS STRING; -- who, what, where, when, why, how
CREATE PROPERTY CONTRADICTS.conflict_type IF NOT EXISTS STRING; -- ACTOR_MISMATCH, POLARITY_REVERSAL, SPATIAL_DISJOINTNESS, TEMPORAL_IMPOSSIBILITY, NARRATIVE_FRAMING_CLASH, INSTRUMENT_DISPUTE
CREATE PROPERTY CONTRADICTS.confidence IF NOT EXISTS FLOAT;
CREATE PROPERTY CONTRADICTS.warrant IF NOT EXISTS STRING;

CREATE EDGE TYPE OMITS IF NOT EXISTS;
CREATE PROPERTY OMITS.dimension IF NOT EXISTS STRING; -- who, what, where, when, why, how
CREATE PROPERTY OMITS.significance IF NOT EXISTS STRING; -- critical_blindspot, standard_omission

CREATE EDGE TYPE SUPPORTS IF NOT EXISTS;
CREATE PROPERTY SUPPORTS.weight IF NOT EXISTS FLOAT;
```

---

## 5. Option C: In-Engine Algorithmic Multi-Pass Pipeline Architecture

The automated ingestion pipeline processes raw news articles through five algorithmic passes executed entirely between Python and ArcadeDB:

```mermaid
flowchart TD
    RAW_FEED["Incoming Raw Article from raw/articles"] --> PASS1["Pass 1 - Direct ArcadeDB Ingestion - Upsert RawArticle and Embeddings"]
    PASS1 --> PASS2["Pass 2 - 5W1H Claim Extraction - LLM Extraction of Claims and Slots"]
    PASS2 --> PASS3["Pass 3 - Spatio-Temporal Event Alignment - JVector and Time-Geo Matching"]
    PASS3 --> PASS4["Pass 4 - Pairwise 5W1H Cross-Auditor - Materialize CORROBORATES, CONTRADICTS, OMITS"]
    PASS4 --> PASS5["Pass 5 - In-Engine Graph OLAP - FastRP, PageRank, Louvain"]
```

### Pass 1: Raw Article Persistence in ArcadeDB
- The file is read from `raw/articles/`.
- The article text, URL, outlet, and publication date are upserted into `RawArticle`.
- An embedding is generated and indexed via ArcadeDB's embedded `LSM_VECTOR`.
- An edge `(RawArticle)-[:PUBLISHED_BY]->(Actor {subtype: 'media_source'})` is linked.

### Pass 2: 5W1H Claim Extraction
- An LLM prompt parses the article text into a structured JSON array of discrete claims:
  ```json
  [
    {
      "claim_id": "CLM-20261027-DABANGA-01",
      "text": "SAF drones carried out a double-tap airstrike on Tanqonj Market in Nyala.",
      "claim_type": "assertion",
      "toulmin_role": "grounds",
      "confidence": 0.90,
      "who": {"actor": "Sudanese Armed Forces", "role": "perpetrator"},
      "what": "drone_strike",
      "where": "Nyala",
      "when": "2026-10-27T10:00:00Z",
      "why": "Targeting RSF supply logistics",
      "how": "Mohajer-6 UAV"
    }
  ]
  ```
- Each claim is upserted as a `(:Claim)` vertex, linked via `(RawArticle)-[:ASSERTS]->(Claim)`.
- Slot edges (`[:WHO]`, `[:WHAT]`, `[:WHERE]`, `[:WHEN]`, `[:WHY]`, `[:HOW]`) are linked to canonical nodes using cached ArcadeDB RID maps.

### Pass 3: In-Engine Spatio-Temporal Event Alignment
- The engine identifies whether the claim discusses an existing canonical `(:Event)`:
  1. **Spatial Match**: Matches `(:Location)` P-Code or administrative boundary.
  2. **Temporal Match**: $\lvert \Delta t \rvert \le 48\text{ hours}$.
  3. **Action Match**: JVector cosine distance between `Claim[embedding]` and existing `Event[embedding]` $< 0.35$.
- If aligned, links `(Claim)-[:RESOLVES_TO]->(Event)`. If no match exists, a new candidate `(:Event)` is spawned.

### Pass 4: Pairwise Dimensional Cross-Auditing
- For all claims resolving to the same `(:Event)`:
  - **WHO Check**: If $c_1.\text{perpetrator} \ne c_2.\text{perpetrator}$, materialize `[:CONTRADICTS {dimension: 'who', conflict_type: 'ACTOR_MISMATCH'}]`.
  - **HOW Check**: If instruments are incompatible (e.g., drone strike vs. artillery), materialize `[:CONTRADICTS {dimension: 'how', conflict_type: 'INSTRUMENT_DISPUTE'}]`.
  - **WHY Check**: If motives clash (e.g., civilian terror vs. military depot targeting), materialize `[:CONTRADICTS {dimension: 'why', conflict_type: 'NARRATIVE_FRAMING_CLASH'}]`.
  - **Corroboration**: If slots match across independent sources, materialize `[:CORROBORATES {dimensions: ['where', 'when', 'what']}]`.
  - **Omission**: If an event has verified HOW or WHO, but claim $c_i$ lacks that edge, materialize `(Claim)-[:OMITS {dimension: 'how'}]->(Event)`.

### Pass 5: In-Engine Graph OLAP Refresh
- Run `CALL algo.pagerank({edgeType: 'CORROBORATES'})` to compute consensus reality.
- Run `CALL algo.louvain({edgeType: 'CORROBORATES'})` to detect narrative camps.
- Run `CALL algo.fastrp(...)` to update native topological embeddings.

---

## 6. Streamlined OpenCypher Query Catalog (Zero `Section` Dependency)

These queries run natively in ArcadeDB without navigating through `Section` nodes.

### 6.1 Identifying Claims Across Different Articles

#### Query 1: Discover All Competing Claims for a Target Event
```cypher
// Retrieve all claims and their 5W1H profiles for a specific event
MATCH (e:Event {title: "2026-10-27 Nyala Tanqonj Market Drone Strike"})<-[:RESOLVES_TO]-(c:Claim)<-[:ASSERTS]-(art:RawArticle)
OPTIONAL MATCH (c)-[rw:WHO]->(who:Actor)
OPTIONAL MATCH (c)-[:WHAT]->(what:ActionType)
OPTIONAL MATCH (c)-[:WHERE]->(where:Location)
OPTIONAL MATCH (c)-[:HOW]->(how:Instrument)
OPTIONAL MATCH (c)-[:WHY]->(why:Theme)
RETURN 
    art.title AS ArticleHeadline,
    art.source_outlet AS Outlet,
    c.text AS ClaimAssertion,
    rw.role AS ActorRole,
    who.title AS AttributedActor,
    what.name AS Action,
    how.name AS WeaponModality,
    why.title AS StatedMotive
ORDER BY art.published_date DESC;
```

#### Query 2: Find All Assertions Made by a Specific Media Outlet Across Frontlines
```cypher
// Audit all claims asserted by a specific outlet regarding drone attacks
MATCH (art:RawArticle {source_outlet: "Radio Dabanga"})-[:ASSERTS]->(c:Claim)
MATCH (c)-[:HOW]->(inst:Instrument)
MATCH (c)-[:RESOLVES_TO]->(e:Event)
RETURN 
    art.published_date AS Date,
    e.title AS Event,
    c.text AS ClaimText,
    inst.name AS ReportedWeapon
ORDER BY Date DESC;
```

---

### 6.2 Supporting Arguments & Forensic Verification

#### Query 3: Surface High-Verification Claims Grounded in Forensic Citations
```cypher
// Find claims supported by forensic findings or verified eyewitness accounts
MATCH (c:Claim)<-[:SUPPORTS]-(cit:Citation)
MATCH (c)-[:RESOLVES_TO]->(e:Event)
WHERE cit.reliability_score >= 0.85
RETURN 
    e.title AS Event,
    c.text AS VerifiedClaim,
    cit.speaker AS SpeakerOrForensicSource,
    cit.speech_act AS SpeechAct,
    cit.reliability_score AS ConfidenceScore;
```

#### Query 4: Trace Evidence Lineage from Claim Back to Raw Text Quote
```cypher
// Full lineage: RawArticle -> Claim -> Supporting Citation -> Canonical Event
MATCH (art:RawArticle)-[:ASSERTS]->(c:Claim)-[:RESOLVES_TO]->(e:Event)
MATCH (cit:Citation)-[:SUPPORTS]->(c)
RETURN 
    art.title AS SourceArticle,
    c.text AS ExtractedClaim,
    cit.title AS ForensicCitation,
    cit.original_language AS Language,
    e.title AS ResolvedEvent;
```

---

### 6.3 Dimensional Contradiction Detection

#### Query 5: Pinpoint Actor Attribution Clashes (WHO Conflicts)
```cypher
// Surface events where two news outlets attribute the perpetrator role to opposing forces
MATCH (c1:Claim)-[r:CONTRADICTS {dimension: "who", conflict_type: "ACTOR_MISMATCH"}]->(c2:Claim)
MATCH (c1)-[:RESOLVES_TO]->(e:Event)<-[:RESOLVES_TO]-(c2)
MATCH (art1:RawArticle)-[:ASSERTS]->(c1)-[:WHO]->(a1:Actor)
MATCH (art2:RawArticle)-[:ASSERTS]->(c2)-[:WHO]->(a2:Actor)
RETURN 
    e.title AS DisputedEvent,
    art1.source_outlet AS OutletA,
    a1.title AS PerpetratorClaimA,
    art2.source_outlet AS OutletB,
    a2.title AS PerpetratorClaimB,
    r.confidence AS DisagreementConfidence,
    r.warrant AS Warrant;
```

#### Query 6: Surface Weapon / Modality Disputes (HOW Conflicts)
```cypher
// Identify incidents where sources dispute the weapon system used
MATCH (c1:Claim)-[r:CONTRADICTS {dimension: "how"}]->(c2:Claim)
MATCH (c1)-[:RESOLVES_TO]->(e:Event)
MATCH (art1:RawArticle)-[:ASSERTS]->(c1)-[:HOW]->(i1:Instrument)
MATCH (art2:RawArticle)-[:ASSERTS]->(c2)-[:HOW]->(i2:Instrument)
RETURN 
    e.title AS Event,
    art1.source_outlet AS OutletA,
    i1.name AS WeaponClaimA,
    art2.source_outlet AS OutletB,
    i2.name AS WeaponClaimB,
    r.conflict_type AS ConflictType;
```

---

### 6.4 Missing Elements & Media Blindspot Identification

#### Query 7: Detect Articles that Omit the Perpetrator (Perpetrator Silence)
```cypher
// Find articles reporting casualties or strikes while omitting who carried them out
MATCH (e:Event)<-[:RESOLVES_TO]-(c:Claim)<-[:ASSERTS]-(art:RawArticle)
WHERE NOT (c)-[:WHO {role: "perpetrator"}]->()
RETURN 
    art.title AS ArticleTitle,
    art.source_outlet AS Outlet,
    art.published_date AS Date,
    e.title AS Event,
    c.text AS ClaimText
ORDER BY art.published_date DESC;
```

#### Query 8: Comparative Media Blindspot Matrix Between Two Outlets on the Same Event
```cypher
// Compare what Outlet A reported vs what Outlet B omitted on the exact same incident
MATCH (e:Event)<-[:RESOLVES_TO]-(cA:Claim)<-[:ASSERTS]-(artA:RawArticle {source_outlet: "Radio Dabanga"})
MATCH (e)<-[:RESOLVES_TO]-(cB:Claim)<-[:ASSERTS]-(artB:RawArticle {source_outlet: "Sudan News Agency"})
OPTIONAL MATCH (cA)-[:WHO]->(whoA:Actor)
OPTIONAL MATCH (cB)-[:WHO]->(whoB:Actor)
OPTIONAL MATCH (cA)-[:HOW]->(howA:Instrument)
OPTIONAL MATCH (cB)-[:HOW]->(howB:Instrument)
OPTIONAL MATCH (cA)-[:WHY]->(whyA:Theme)
OPTIONAL MATCH (cB)-[:WHY]->(whyB:Theme)
RETURN 
    e.title AS Event,
    whoA.title AS Dabanga_Who,
    howA.name AS Dabanga_How,
    whyA.title AS Dabanga_Why,
    coalesce(whoB.title, "OMITTED") AS SUNA_Who,
    coalesce(howB.name, "OMITTED") AS SUNA_How,
    coalesce(whyB.title, "OMITTED") AS SUNA_Why;
```

#### Query 9: Completeness Scorecard Across All Reporting Outlets
```cypher
// Calculate the 5W1H reporting completeness percentage for every news outlet
MATCH (art:RawArticle)-[:ASSERTS]->(c:Claim)
WITH art.source_outlet AS Outlet, count(c) AS total_claims,
     sum(CASE WHEN (c)-[:WHO]->() THEN 1 ELSE 0 END) AS has_who,
     sum(CASE WHEN (c)-[:WHAT]->() THEN 1 ELSE 0 END) AS has_what,
     sum(CASE WHEN (c)-[:WHERE]->() THEN 1 ELSE 0 END) AS has_where,
     sum(CASE WHEN (c)-[:WHEN]->() THEN 1 ELSE 0 END) AS has_when,
     sum(CASE WHEN (c)-[:WHY]->() THEN 1 ELSE 0 END) AS has_why,
     sum(CASE WHEN (c)-[:HOW]->() THEN 1 ELSE 0 END) AS has_how
RETURN 
    Outlet,
    total_claims AS TotalClaims,
    round((has_who * 1.0 / total_claims) * 100, 1) AS Pct_Who,
    round((has_how * 1.0 / total_claims) * 100, 1) AS Pct_How,
    round((has_why * 1.0 / total_claims) * 100, 1) AS Pct_Why,
    round(((has_who + has_what + has_where + has_when + has_why + has_how) * 1.0 / (total_claims * 6.0)) * 100, 1) AS Overall_5W1H_Score
ORDER BY Overall_5W1H_Score DESC;
```

---

### 6.5 In-Engine Graph OLAP: Credibility & Consensus Centrality

#### Query 10: In-Engine Weighted PageRank on the Corroboration Subgraph
```cypher
// Materialize epistemic consensus scores using native ArcadeDB PageRank
CALL algo.pagerank({
    edgeType: "CORROBORATES",
    dampingFactor: 0.85,
    iterations: 20
})
YIELD node, score
SET node.consensus_pagerank = score;
```

#### Query 11: In-Engine Louvain Community Detection to Surface Partisan Narrative Cliques
```cypher
// Cluster claims into narrative camps based on mutual corroboration patterns
CALL algo.louvain({
    edgeType: "CORROBORATES"
})
YIELD node, community
SET node.narrative_camp = community;
```

---

## 7. Migration & Reworking Plan for All Existing Ingestions

To transition the existing vault (32+ compiled sources, 35+ events, 30+ raw articles) to the 5W1H Claim architecture without data loss, a four-phase migration script (`scripts/migrate_vault_to_5w1h.py`) is specified.

```mermaid
flowchart LR
    M1["Phase 1 - DDL and Section Purge - Drop Section and Create RawArticle and Claim"] --> M2["Phase 2 - Ingest Raw Articles - Populate RawArticle from raw/articles"]
    M2 --> M3["Phase 3 - Backfill 5W1H Claims - Extract Claims from Sources and Section 5 Tables"]
    M3 --> M4["Phase 4 - Pairwise Cross-Audit - Materialize CORROBORATES, CONTRADICTS, OMITS"]
```

### Phase 1: ArcadeDB Schema Migration & `Section` Purge
- Execute DDL commands from Section 4.
- Purge all 1,530 `Section` vertices and associated `PROGRESSES_TO` / `HAS_SECTION` edges.
- Verify that canonical nodes (`Event`, `Actor`, `Location`, `Theme`, `Timeline`, `Citation`) remain intact.

### Phase 2: Ingest Raw Articles into ArcadeDB
- Scan `raw/articles/*.md`.
- Extract frontmatter (`url`, `published_date`, `source_outlet`) and markdown text.
- Upsert into `RawArticle` vertices with deterministic `article_id` slugs.
- Link `(RawArticle)-[:PUBLISHED_BY]->(Actor {subtype: 'media_source'})`.

### Phase 3: Backfill 5W1H Claims for All 32 Existing Ingestions
- For each compiled source note in `wiki/sources/*.md`:
  1. **Primary Claims**: Parse Section 2 (`Tactical Anchors`) and Section 1 callouts from the associated event note to construct primary `Claim` vertices.
  2. **Disputed Claims**: Parse Section 5 (`Competing Narratives Matrix`) tables from event notes to extract opposing perspective claims ($Claim_A$ and $Claim_B$).
  3. **Slot Linking**: Attach `[:WHO]` to mentioned actors, `[:WHERE]` to locations, `[:WHEN]` to event dates, and `[:HOW]` to identified instruments.
  4. **Event Resolution**: Link `(Claim)-[:RESOLVES_TO]->(Event)`.
  5. **Citation Grounding**: Link `(Citation)-[:SUPPORTS]->(Claim)`.

### Phase 4: Automated Pairwise Cross-Auditing
- Group all claims by their target `(:Event)`.
- For every event with $\ge 2$ claims:
  - Compare `WHO`: If actors differ, insert `[:CONTRADICTS {dimension: 'who', conflict_type: 'ACTOR_MISMATCH'}]`.
  - Compare `HOW`: If weapons differ, insert `[:CONTRADICTS {dimension: 'how', conflict_type: 'INSTRUMENT_DISPUTE'}]`.
  - Compare `WHY`: If motives clash, insert `[:CONTRADICTS {dimension: 'why', conflict_type: 'NARRATIVE_FRAMING_CLASH'}]`.
  - Compare `WHERE` & `WHEN`: If identical, insert `[:CORROBORATES {dimensions: ['where', 'when']}]`.
  - Check missing slots: Insert `[:OMITS {dimension: '...'}]` for incomplete claims.

### Phase 5: Verification & Post-Migration Sync
- Run `./scripts/sync_vault_graph.sh` to update ArcadeDB indices and Graph OLAP scores.
- Run `python3 scripts/lint_vault.py --cot` to guarantee vault integrity.
- Run test OpenCypher queries from Section 6 to verify that zero broken edges exist.

---

## 8. Summary of Architectural Benefits

1. **Massive Graph Efficiency**: Dropping `Section` vertices removes >1,500 artificial nodes, reducing memory footprint and speeding up graph traversals by over 50%.
2. **True Forensic Multi-Perspective Modeling**: Competing narratives, propaganda, and denials are reified cleanly as discrete claims without modifying or overwriting canonical event records.
3. **Automated Media Blindspot Discovery**: For the first time, intelligence analysts can programmatically query what specific outlets *failed to report* using clean Cypher patterns (`WHERE NOT (c)-[:HOW]->()`).
4. **Zero External Vector Dependencies**: Leveraging ArcadeDB's embedded JVector index (`LSM_VECTOR`) and native Graph OLAP (`algo.fastrp`, `algo.pagerank`, `algo.louvain`) keeps the intelligence repository self-contained, sovereign, and zero-daemon.
