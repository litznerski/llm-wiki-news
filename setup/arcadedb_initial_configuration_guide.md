# ArcadeDB Initial Configuration & Schema Setup Guide

This guide details the step-by-step initial configuration, schema definition, and security setup for deploying **ArcadeDB** as the sovereign multi-model runtime engine for [[Knowledge Lab]].

---

## 1. Container Lifecycle & Service Endpoints

The container is orchestrated via Podman or Docker using `setup/compose.arcadedb.yaml`.

### Port Mapping & Endpoints
| Port | Protocol | Purpose | Access URL |
| :--- | :--- | :--- | :--- |
| **`2480`** | HTTP / JSON | REST API, Studio Web UI, and Built-in MCP Server | `http://localhost:2480` |
| **`2424`** | Binary | Native binary protocol / Cluster replication | `localhost:2424` |
| **`/api/v1/mcp`** | Streamable HTTP | Built-in Model Context Protocol endpoint | `http://localhost:2480/api/v1/mcp` |

### Environment Variables
ArcadeDB accepts JVM and engine settings via the `ARCADEDB_SETTINGS` environment variable:
```bash
-Darcadedb.server.rootPassword=root_secret
-Darcadedb.server.defaultDatabases=knowledgedb
-Darcadedb.mcp.enabled=true
```

---

## 2. Service Verification & Readiness Probing

Once the container is started, verify that the HTTP server and database engine are ready:

```bash
# 1. Check HTTP server readiness
curl -i http://localhost:2480/api/v1/ready

# Expected response: HTTP/1.1 204 No Content or 200 OK

# 2. Inspect Server Information (Basic Auth: root / root_secret)
curl -u root:root_secret -X GET http://localhost:2480/api/v1/server
```

---

## 3. Accessing ArcadeDB Studio (Web UI)

ArcadeDB includes a built-in browser IDE similar to Neo4j Browser:
1. Open your web browser and navigate to:
   ```
   http://localhost:2480
   ```
2. Log in with:
   - **Database**: `knowledgedb`
   - **User**: `root`
   - **Password**: `root_secret`
3. The Studio UI provides:
   - **Query Console**: Execute SQL, OpenCypher, Gremlin, or GraphQL directly.
   - **Schema Manager**: Inspect types, buckets, and indexes.
   - **Graph Visualizer**: Interactive visual node exploration.

---

## 4. Initial Schema Definition (DDL)

Unlike pure schemaless document stores, ArcadeDB supports strict or hybrid schema definitions. Execute the following SQL commands in Studio (or post to `POST /api/v1/command/knowledgedb` via `curl`) to create the core types for the knowledge vault:

### A. Create Vertex (Node) Types
```sql
-- Concept Vertices
CREATE VERTEX TYPE Concept;
CREATE PROPERTY Concept.title STRING;
CREATE PROPERTY Concept.type STRING;
CREATE PROPERTY Concept.reliability_score DOUBLE;
CREATE PROPERTY Concept.last_updated STRING;
CREATE INDEX ON Concept (title) UNIQUE;

-- Entity Vertices
CREATE VERTEX TYPE Entity;
CREATE PROPERTY Entity.title STRING;
CREATE PROPERTY Entity.subtype STRING; -- researcher | organization | software | platform
CREATE PROPERTY Entity.reliability_score DOUBLE;
CREATE INDEX ON Entity (title) UNIQUE;

-- Source Distillation Vertices
CREATE VERTEX TYPE Source;
CREATE PROPERTY Source.title STRING;
CREATE PROPERTY Source.slug STRING;
CREATE INDEX ON Source (slug) UNIQUE;

-- Section Vertices (Micro-CoT reasoning chunks)
CREATE VERTEX TYPE Section;
CREATE PROPERTY Section.heading STRING;
CREATE PROPERTY Section.content STRING;
CREATE PROPERTY Section.step_type STRING; -- DefinitionalAnchor, MechanisticDeepen, etc.
CREATE PROPERTY Section.vector LIST OF FLOAT; -- 768-dim embeddings

-- Tag Vertices
CREATE VERTEX TYPE Tag;
CREATE PROPERTY Tag.name STRING;
CREATE INDEX ON Tag (name) UNIQUE;
```

### B. Create Edge (Relationship) Types
```sql
-- Micro-CoT Intra-Document Reasoning Edge
CREATE EDGE TYPE PROGRESSES_TO;

-- Macro-CoT Inter-Document Epistemic Edges
CREATE EDGE TYPE REMEDIES_DILEMMA;
CREATE EDGE TYPE EXTENDS_THEORY;
CREATE EDGE TYPE PRECIPITATES;
CREATE EDGE TYPE EMPIRICALLY_GROUNDS;

-- Entity Agency Macro-CoT Edges
CREATE EDGE TYPE ORIGINATES_THEORY;
CREATE EDGE TYPE CHAMPIONS_SOLUTION;
CREATE EDGE TYPE CRITIQUES_PARADIGM;
CREATE EDGE TYPE OPERATIONALIZES;
CREATE EDGE TYPE AFFILIATED_WITH;
CREATE EDGE TYPE INTELLECTUAL_LINEAGE;

-- Structural Document Links
CREATE EDGE TYPE HAS_SECTION;
CREATE EDGE TYPE TAGGED_WITH;
CREATE EDGE TYPE CITES;
```

### C. Create Vector & Full-Text Indexes
ArcadeDB uses **JVector** for modern vector indexing (HNSW and Vamana DiskANN) and native Lucene for full-text search:

```sql
-- 1. Native HNSW Vector Index on Section embeddings (768 dimensions, Cosine)
CREATE INDEX ON Section (vector) LSM_VECTOR 
METADATA {
  "dimensions": 768,
  "metric": "COSINE"
};

-- 2. Full-Text Lucene Index for Concept & Entity searching
CREATE INDEX ON Concept (title) FULL_TEXT;
CREATE INDEX ON Entity (title) FULL_TEXT;
```

### D. Create Key-Value Bucket for Instant Alias Lookups
ArcadeDB allows creating direct Key-Value buckets for sub-millisecond lookups of normalized aliases and acronyms:
```sql
CREATE DOCUMENT TYPE AliasLookup;
CREATE PROPERTY AliasLookup.alias STRING;
CREATE PROPERTY AliasLookup.canonical_title STRING;
CREATE PROPERTY AliasLookup.type STRING;
CREATE INDEX ON AliasLookup (alias) UNIQUE;
```

---

## 5. Testing Query Execution Across Languages

Once types are defined, test the polyglot engine:

### OpenCypher 25 Test
```cypher
MATCH (c:Concept)
RETURN count(c) AS total_concepts;
```

### Extended Graph SQL Test
```sql
SELECT title, out('REMEDIES_DILEMMA').title AS remedies
FROM Concept;
```

---

## 6. Backups & Data Persistence
Data is persisted in the named Podman volume `arcadedb-ki-data` (or directory `./data/arcadedb`). To trigger an automated hot backup without stopping the database:
```bash
curl -u root:root_secret -X POST http://localhost:2480/api/v1/backup/knowledgedb
```
Backup archives are saved into `/home/arcadedb/backups/`.
