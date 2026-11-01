# 🛰️ Sudan News & OSINT Intelligence Studio

An interactive, source-grounded open-source intelligence (OSINT) and conflict analysis workbench for the **Sudan News Knowledge Graph (`llm-wiki-news`)**.

---

### Core Architecture
- **Epistemic Substrate**: Multi-model [[ArcadeDB]] (`news`) graph database indexing `Event`, `Actor`, `Location` (UN OCHA P-Codes `SD01`–`SD18`), `Theme`, `Timeline`, `Source`, and `ClaimDispute` records.
- **Middleware Engine**: [[FastMCP]] providing Two-Tier context resolution (Tier 1 Pre-Compiled Intelligence Syntheses and Tier 2 5W1H / GRaSP CoT Graph Traversal).
- **Epistemic Provenance & Contradiction Tracking**: Every claim is graded on the **NATO Admiralty Scale (`A1`–`F6`)** and cross-checked against competing narratives (`ClaimDispute`).

---

### Analyst Operating Guide
Welcome to your sovereign Sudan News & OSINT Intelligence Studio. Ingest multilingual evidence into `raw/` (`articles/`, `social/`, `videos/`, `transcripts/`, `reports/`, `satellite/`) to populate your knowledge graph.
1. **Direct 5W1H & Frontline Inquiry**: Type any question into the chat composer below (e.g., *"Who commands the Rapid Support Forces?"*, *"What is the status of North Darfur (SD02)?"*, or *"Compare SAF and RSF narratives"*).
2. **Side-Panel Graph & Contradiction Inspection**: The split-screen side panel displays live ArcadeDB Cypher queries, NATO Admiralty reliability telemetry, and 5W1H / GRaSP argumentation roles.
3. **Dialogue Valves**: Access the ⚙️ Settings menu in the chat composer to switch LLM models, toggle `General` (Direct OSINT Synthesis) vs. `Learn` (Analyst Verification Mode), or inspect live FastMCP traces.
