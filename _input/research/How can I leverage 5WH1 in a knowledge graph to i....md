Leveraging **5W1H** (Who, What, Where, When, Why, How) in a knowledge graph requires shifting from standard binary triples (Subject \-\> Predicate \-\> Object) to **event-centric reification**. In this architecture, an extraction node serves as an $n$\-ary hub that binds all six dimensions to their respective entities while maintaining strict provenance back to the reporting source.  
By isolating each dimension into distinct graph edges, you transform unstructured text comparison into an algorithmic, dimension-by-dimension cross-examination of reporting variance.

### **1\. Graph Data Model: The Event-Observation Nexus**

Directly merging conflicting news into a single canonical event node destroys contradiction data. Instead, implement a **two-layer model**: an **Observation/Claim Layer** (epistemic, source-specific) and a **Canonical Event Layer** (ontological, synthesized).

\[ (:Source) \]  
      │  
  \[:REPORTED\]  
      ▼  
\[ (:Claim / Observation) \]  
      ├───\[:WHO\]───► \[ (:Entity:Person \| :Organization) \]  
      ├───\[:WHAT\]──► \[ (:Action \| :StateChange) \]  
      ├───\[:WHERE\]─► \[ (:Location:GeoNode) \]  
      ├───\[:WHEN\]──► \[ (:TimeInterval \| :Timestamp) \]  
      ├───\[:WHY\]───► \[ (:CausalFactor \| :Motive) \]  
      └───\[:HOW\]──► \[ (:Method \| :Instrument) \]  
      │  
  \[:RESOLVES\_TO\]  
      ▼  
\[ (:CanonicalEvent) \]

#### **Node & Relationship Definitions**

* **(:Source)**: Metadata about the publisher (bias rating, reliability score, country of origin, publication timestamp).  
* **(:Claim)**: The specific instance of an assertion extracted from an article.  
* **5W1H Dimension Edges**:  
  * \[:WHO\]: Role-typed edges such as \[:ACTOR\], \[:TARGET\], or \[:VICTIM\].  
  * \[:WHAT\]: Verb/action concepts normalized to an ontology (e.g., FrameNet, Wikidata Q-IDs).  
  * \[:WHERE\]: Hierarchical spatial nodes (Coordinates $\rightarrow$ City $\rightarrow$ Region $\rightarrow$ Country).  
  * \[:WHEN\]: ISO-8601 intervals, anchoring absolute time vs. relative temporal mentions.  
  * \[:WHY\]: Causal statements (often linked to prior events or stated motives).  
  * \[:HOW\]: Modality, weapons, diplomatic instruments, or logistical means.  
* **\[:RESOLVES\_TO\]**: Points candidate claims about the same real-world incident to a central (:CanonicalEvent).

### **2\. Event Alignment: Determining Co-Reference**

Before identifying support or contradiction, you must establish whether two sources are discussing the **same incident**. You cluster claims into a (:CanonicalEvent) by computing an **Anchor Overlap** across the objective dimensions:

$$MatchScore={w}_{where}\cdot GeoSim+{w}_{when}\cdot TimeSim+{w}_{what}\cdot SemanticSim(Action)$$

* **Where**: Spatial distance between locations (e.g., within 5 km or sharing the lowest administrative boundary).  
* **When**: Temporal distance (e.g., overlapping time intervals or within $\pm 6$ hours).  
* **What**: Embedding cosine similarity or shared ontological ancestor for the action (e.g., "bombarded" vs. "shelled").

Once two claims link to the same CanonicalEvent, cross-claim validation begins.

### **3\. Dimensional Contradiction & Support Matrix**

Contradictions in journalism rarely manifest as complete opposites; they usually manifest as localized disagreements on specific 5W1H slots.

| Dimension | Support Signature | Contradiction / Divergence Signature | Verification Technique |
| :---- | :---- | :---- | :---- |
| **Who** | Both sources identify identical or alias-linked actors/targets (A\_actor \== B\_actor). | **Actor Substitution:** Source A attributes action to Entity X; Source B attributes it to Entity Y. | Entity Resolution / Graph Coreference; Disjoint entity sets. |
| **What** | Same action polarity and event category (A\_action ≈ B\_action). | **Polarity Reversal:** "Captured" vs. "Repelled"; "Downed" vs. "Crashed due to malfunction." | Natural Language Inference (NLI: Entailment vs. Contradiction); Antonym/Disjoint ontology trees. |
| **Where** | Identical or hierarchically nested geo-nodes (A\_loc $\subseteq$ B\_loc). | **Spatial Disjointness:** Locations exceed feasible threshold for a single event without subordinate relation. | Geo-spatial bounding box checks / GIS topology (ST\_DWithin). |
| **When** | Overlapping or identical validity intervals. | **Temporal Impossibility:** Source B claims an event occurred hours/days before or after Source A's fixed anchor. | Temporal interval calculus (Allen's Interval Algebra). |
| **Why** | Aligned justifications (e.g., both cite "retaliation for border strike"). | **Narrative Framing Clash:** Source A cites "unprovoked aggression"; Source B cites "preemptive self-defense." | Argument mining, stance detection, and sentiment/framing classification. |
| **How** | Consistent modality/tools (e.g., both state "artillery fire"). | **Instrument Conflict:** "Suicide drone" vs. "Air-to-surface cruise missile." | Lexical/ontological taxonomy checking (e.g., checking if weapons belong to disjoint classes). |

### **4\. Graph Edge Materialization: Synthesizing Stance**

When comparing two claims (c1 and c2) attached to the same CanonicalEvent, your pipeline runs pairwise dimensional comparisons and creates explicit relationship edges between the claims:

* (c1)-\[:SUPPORTS {dimensions: \['where', 'when', 'what'\], score: 0.94}\]-\>(c2)  
* (c1)-\[:CONTRADICTS {dimension: 'who', type: 'ACTOR\_MISMATCH', confidence: 0.88}\]-\>(c2)  
* (c1)-\[:DIVERGES\_ON {dimension: 'why', issue: 'MOTIVE\_FRAMING'}\]-\>(c2)

#### **Cypher Pattern: Querying Contradictory Claims**

To surface competing narratives on a specific event in Neo4j:

Cypher  
MATCH (e:CanonicalEvent)\<-\[:RESOLVES\_TO\]-(c1:Claim)-\[rel:CONTRADICTS\]-\>(c2:Claim)-\[:RESOLVES\_TO\]-\>(e)  
MATCH (s1:Source)-\[:REPORTED\]-\>(c1)  
MATCH (s2:Source)-\[:REPORTED\]-\>(c2)  
RETURN   
    e.canonical\_title AS Event,  
    rel.dimension AS DisputedDimension,  
    s1.name AS SourceA,   
    c1.summary AS ClaimA,  
    s2.name AS SourceB,   
    c2.summary AS ClaimB,  
    rel.type AS ConflictType

### **5\. Automated Pipeline Architecture**

Raw RSS / Wire Feeds  
         │  
         ▼  
\[ LLM Information Extraction \] ──► Outputs JSON-LD 5W1H Frame  
         │  
         ▼  
\[ Entity & Geo Resolution \]    ──► Links strings to canonical DB nodes (Wikidata/GeoNames)  
         │  
         ▼  
\[ Event Alignment Engine \]     ──► Matches (Where \+ When \+ What) to CanonicalEvent  
         │  
         ▼  
\[ Dimension Cross-Auditor \]    ──► Runs NLI & Ontological checks across 5W1H slots  
         │  
         ▼  
\[ Graph Edge Insertion \]       ──► Writes \[:SUPPORTS\] / \[:CONTRADICTS\] to Knowledge Graph

> 1. **Extraction (LLM / OpenIE)**: Prompt an LLM with structured output (JSON schema) to extract raw arguments for who, what, where, when, why, and how, retaining the exact source sentence for grounding.  
> 2. **Entity & Concept Resolution**: Normalize where to a coordinate/administrative entity, when to UTC intervals, and who to a master entity registry.  
> 3. **Cross-Encoder / NLI Pass**: If the entities in a slot are not simple identifiers (e.g., complex narrative text in why or how), pass the pairs through a Natural Language Inference (NLI) cross-encoder (such as DeBERTa-v3-large-MNLI) to assign probabilities for **Entailment**, **Neutral**, or **Contradiction**.  
> 4. **Network Credibility Scoring**: Use graph centrality and source authority algorithms (e.g., PageRank or subjective logic consensus) over the \[:SUPPORTS\] and \[:CONTRADICTS\] graph to identify consensus reality versus isolated propaganda or reporting errors.