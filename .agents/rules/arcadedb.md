---
trigger: model_decision
description: "Apply these guidelines, dialect constraints, and reference documentation whenever querying, modeling, migrating, benchmarking, or integrating ArcadeDB."
---

# ArcadeDB Knowledge, Dialect Rules & Documentation Invariants

When working with **ArcadeDB** across [[Knowledge Lab]] (scripting, MCP servers, migrations, schema DDL, or Open WebUI integrations), strictly adhere to the following rules and verify syntax against the official ArcadeDB documentation (v26.x+).

---

## 1. Documentation Authority & Grounding Sources
1. **Primary Online Documentation**: Official documentation at `https://docs.arcadedb.com/`. Consult online or search web for syntax details when writing unfamiliar procedures or functions.
2. **Local Architecture & Reference Guides**:
   - Master Connection & Setup Guide: `raw/documentation/arcadedb_connection_and_integration_guide.md`
   - Native Embeddings & Tri-Target Switcher: `raw/drafts/arcadedb_native_embeddings_and_database_switcher_implementation_plan.md`
   - FastMCP & Vanna Architectural Blueprint: `raw/drafts/vanna_and_fastmcp_arcadedb_investigation.md`
   - Schema Verification & CoT Mapping: `raw/drafts/arcadedb_micro_macro_cot_schema_verification.md`
3. **Database Introspection**:
   - Inspect live schema via `arcadedb-ki` MCP tool `get_schema` or resource `arcadedb://knowledgedb/schema`.
   - Inspect server version and active languages via `server_status`.

---

## 2. Dialect Constraints & Syntax Invariants

### 2.1 The "No ANSI JOIN" Invariant
ArcadeDB SQL does NOT support ANSI relational `JOIN` syntax (`FROM TableA a JOIN TableB b ON a.id = b.a_id`).
- When using SQL: Use graph traversal operators `out('EdgeType')`, `in('EdgeType')`, `both('EdgeType')`, or `expand()`:
  ```sql
  -- Correct ArcadeDB SQL:
  SELECT expand(out('REMEDIES_DILEMMA')) FROM Concept WHERE title = 'Productive Cognitive Friction';
  ```
- When performing multi-hop pattern matching: **Always prefer OpenCypher**:
  ```cypher
  MATCH (c:Concept {title: 'Productive Cognitive Friction'})-[:REMEDIES_DILEMMA]->(d:Concept)
  RETURN d.title;
  ```

### 2.2 Graph OLAP Algorithm Execution (`algo.*`)
ArcadeDB implements native in-engine Graph OLAP procedures callable directly from Cypher:
```cypher
-- FastRP Native Embedding (Zero Ollama)
CALL algo.fastrp({dimensions: 768, iterations: 4, normalization: -0.5, direction: 'BOTH'})
YIELD node, embedding
SET node.embedding = embedding;

-- PageRank Centrality
CALL algo.pagerank({dampingFactor: 0.85, iterations: 20})
YIELD node, score
SET node.pagerank = score;

-- Louvain Community Detection
CALL algo.louvain()
YIELD node, community
SET node.community = community;
```

### 2.3 Vector Storage & Similarity Retrieval
- Declare vector properties as `LIST OF FLOAT`.
- Index with `LSM_VECTOR` using embedded JVector:
  ```sql
  CREATE INDEX ON Section (embedding) LSM_VECTOR METADATA {"dimensions": 768, "similarity": "COSINE", "quantization": "INT8"};
  ```
- Query nearest neighbors using `vectorNeighbors()`:
  ```sql
  SELECT title, path, vectorNeighbors('Section[embedding]', $query_vector, 10) AS distance
  FROM Section
  ORDER BY distance ASC
  LIMIT 10;
  ```

### 2.4 HTTP REST & Batch API Discipline
- **Read queries (SELECT, MATCH)**: Send via `POST /api/v1/query/{database}`.
- **Write/DDL commands (CREATE, INSERT, UPDATE, DELETE)**: Send via `POST /api/v1/command/{database}`.
- **Bulk data ingestion**: Send high-density NDJSON via `POST /api/v1/batch/{database}`.
