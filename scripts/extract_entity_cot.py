# /// script
# dependencies = [
#     "neo4j>=5.0.0",
# ]
# ///
#!/usr/bin/env python3
"""
scripts/extract_entity_cot.py
Extracts and materializes Generation 3 Epistemic Entity Arcs (EEA) into Neo4j:
  - Micro-CoT: Classifies entity sections into canonical archetypal cognitive steps:
      * Thinker/Researcher: EPISTEMIC_ANCHOR, INTELLECTUAL_LINEAGE, DIALECTICAL_CRITIQUE,
                            CANONICAL_MODEL, PEDAGOGICAL_DEPLOYMENT, SYNTHESIS_CATALOG
      * Organization:       EPISTEMIC_ANCHOR, SYSTEMIC_FAILURE_MODE, ORGANIZATIONAL_ARCHITECTURE,
                            COALITION_ECOSYSTEM, STRATEGIC_ANALOGUE, SYNTHESIS_CATALOG
      * Software/Platform:  EPISTEMIC_ANCHOR, TECHNICAL_ARCHITECTURE, SYSTEMIC_FAILURE_MODE,
                            INTEGRATION_TOPOLOGY, OPERATIONAL_TELEMETRY, SYNTHESIS_CATALOG
  - Macro-CoT: Discovers and materializes 6 typed agency relationships in Neo4j:
      * [:ORIGINATES_THEORY]  (Researcher/Entity -> Concept)
      * [:CHAMPIONS_SOLUTION] (Researcher/Organization -> Concept)
      * [:CRITIQUES_PARADIGM] (Researcher/Organization/Software -> Concept)
      * [:OPERATIONALIZES]    (Software/Organization -> Concept)
      * [:AFFILIATED_WITH]    (Researcher/Entity -> Organization/Entity)
      * [:INTELLECTUAL_LINEAGE] (Researcher -> Researcher)
      * Inbound literature: [:AUTHORED_BY] (Source -> Researcher) and [:PUBLISHED_BY] (Source -> Organization)

Usage:
    uv run scripts/extract_entity_cot.py
    python3 scripts/extract_entity_cot.py
"""

import os
import sys
import time
import re
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

try:
    from neo4j import GraphDatabase, Driver
except ImportError:
    print("Error: The 'neo4j' Python driver is required.", file=sys.stderr)
    print("Run with uv:  uv run scripts/extract_entity_cot.py", file=sys.stderr)
    sys.exit(1)

VAULT_ROOT = Path(__file__).resolve().parent.parent

# Automatically source .env if present
_env_file = VAULT_ROOT / ".env"
if _env_file.exists():
    try:
        with open(_env_file, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k, _v = _k.strip(), _v.strip().strip("'\"")
                    if _k not in os.environ:
                        os.environ[_k] = _v
    except Exception:
        pass

DEFAULT_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
DEFAULT_USER = os.getenv("NEO4J_USER", "neo4j")
DEFAULT_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
DEFAULT_DATABASE = os.getenv("NEO4J_DATABASE")

# --- Entity Archetype Heading Patterns ---

PATTERNS_RESEARCHER = [
    (r"(related primitives|related notes|references|see also|citations)", "SYNTHESIS_CATALOG"),
    (r"(epistemic role|core thesis|thesis anchor|biographical|profile|overview|intellectual contribution|foundational ethos|background)", "EPISTEMIC_ANCHOR"),
    (r"(intellectual lineage|theoretical foundation|academic background|career|lineage|predecessors|influences|mentorship)", "INTELLECTUAL_LINEAGE"),
    (r"(contested paradigm|dialectical critique|critique|rebuttal|debates|controversies|opposition|fallacy|breakdown)", "DIALECTICAL_CRITIQUE"),
    (r"(canonical formulation|methodological model|model|principles|framework|taxonomy|laws|formulas|matrix|design model|elements|key frameworks)", "CANONICAL_MODEL"),
    (r"(pedagogical deployment|application|deployment in|role in knowledge|relevance to|modern socratic|knowledge engineering|deployment)", "PEDAGOGICAL_DEPLOYMENT"),
]

PATTERNS_ORGANIZATION = [
    (r"(related primitives|related notes|references|see also|citations)", "SYNTHESIS_CATALOG"),
    (r"(institutional mandate|target beneficiary|foundational ethos|mission|profile|overview)", "EPISTEMIC_ANCHOR"),
    (r"(structural breakdown|systemic pathology|market failure|pedagogical critique|pathology|bottleneck|divide)", "SYSTEMIC_FAILURE_MODE"),
    (r"(multi-pillar|operational architecture|comprehensive approach|open-source technology|key products|pillars|operations)", "ORGANIZATIONAL_ARCHITECTURE"),
    (r"(coalition network|strategic ecosystem|strategic supporters|coalition|partners|governance|leadership|advisory)", "COALITION_ECOSYSTEM"),
    (r"(strategic analogue|benchmark for|strategic relevance|integration with|role in knowledge|teardown strategy)", "STRATEGIC_ANALOGUE"),
]

PATTERNS_SOFTWARE = [
    (r"(related primitives|related notes|references|see also|citations)", "SYNTHESIS_CATALOG"),
    (r"(architectural identity|paradigm anchor|core capabilities|technical architecture|architectural purpose|overview)", "EPISTEMIC_ANCHOR"),
    (r"(mechanistic pipeline|execution model|system architecture|in-memory execution|capabilities|design invariants|pipeline)", "TECHNICAL_ARCHITECTURE"),
    (r"(pathologies & architectural bottlenecks|bottlenecks solved|cognitive & pedagogical alignment|controversies|economic tensions|failure)", "SYSTEMIC_FAILURE_MODE"),
    (r"(integration topology|algorithmic deployment|deployment role|integration with|role in platform|role in knowledge)", "INTEGRATION_TOPOLOGY"),
    (r"(operational telemetry|hardware & boundary|pricing|deployment tiers|performance profile|benchmarks|specs|limits)", "OPERATIONAL_TELEMETRY"),
]

def classify_entity_heading(heading_text: str, archetype: str, doc_title: str) -> str:
    """Classifies an entity section heading into its canonical Micro-CoT archetypal step."""
    if not heading_text:
        return "NARRATIVE_STEP"
    
    h_lower = heading_text.lower().strip()
    
    # Check if section title is just the entity name itself (root heading)
    if h_lower == doc_title.lower().strip():
        return "EPISTEMIC_ANCHOR"
    
    # Priority catalog check
    if re.search(r"(related primitives|related notes|references|see also)", h_lower):
        return "SYNTHESIS_CATALOG"
    
    # Check archetype-specific patterns
    patterns = PATTERNS_RESEARCHER
    if archetype == "organization":
        patterns = PATTERNS_ORGANIZATION
    elif archetype in ("software", "platform"):
        patterns = PATTERNS_SOFTWARE
        
    for pat, step_type in patterns:
        if re.search(pat, h_lower):
            return step_type
            
    # Numbered heading fallback for standard Generation 3 entities
    m = re.match(r"^(\d+)\.", h_lower)
    if m:
        num = int(m.group(1))
        if archetype == "researcher":
            mapping = {1: "EPISTEMIC_ANCHOR", 2: "INTELLECTUAL_LINEAGE", 3: "DIALECTICAL_CRITIQUE", 4: "CANONICAL_MODEL", 5: "PEDAGOGICAL_DEPLOYMENT", 6: "SYNTHESIS_CATALOG"}
            return mapping.get(num, "NARRATIVE_STEP")
        elif archetype == "organization":
            mapping = {1: "EPISTEMIC_ANCHOR", 2: "SYSTEMIC_FAILURE_MODE", 3: "ORGANIZATIONAL_ARCHITECTURE", 4: "COALITION_ECOSYSTEM", 5: "STRATEGIC_ANALOGUE", 6: "SYNTHESIS_CATALOG"}
            return mapping.get(num, "NARRATIVE_STEP")
        elif archetype in ("software", "platform"):
            mapping = {1: "EPISTEMIC_ANCHOR", 2: "TECHNICAL_ARCHITECTURE", 3: "SYSTEMIC_FAILURE_MODE", 4: "INTEGRATION_TOPOLOGY", 5: "OPERATIONAL_TELEMETRY", 6: "SYNTHESIS_CATALOG"}
            return mapping.get(num, "NARRATIVE_STEP")
            
    return "NARRATIVE_STEP"

def infer_entity_transition_warrant(cat1: str, cat2: str, archetype: str, h1: str, h2: str) -> Tuple[str, str, float]:
    """Infers transition type and deductive warrant between sequential entity sections."""
    # Syntheses / Primitives
    if cat2 == "SYNTHESIS_CATALOG":
        return ("synthesis_catalog", "Catalogs interrelated concept primitives, entities, and primary literature touchpoints.", 1.0)
        
    # Researcher Arc Transitions
    if archetype == "researcher":
        if cat1 == "EPISTEMIC_ANCHOR" and cat2 == "INTELLECTUAL_LINEAGE":
            return ("intellectual_lineage", "Traces foundational intellectual lineage, formative mentors, and theoretical precursors.", 1.0)
        if cat1 in ("EPISTEMIC_ANCHOR", "INTELLECTUAL_LINEAGE") and cat2 == "DIALECTICAL_CRITIQUE":
            return ("dialectical_critique", "Articulates dialectical critiques and contests prevailing orthodoxies or theoretical limitations.", 1.0)
        if cat1 in ("INTELLECTUAL_LINEAGE", "DIALECTICAL_CRITIQUE") and cat2 == "CANONICAL_MODEL":
            return ("canonical_formulation", "Formulates methodological models, formal laws, and concrete conceptual architectures.", 1.0)
        if cat1 == "CANONICAL_MODEL" and cat2 == "PEDAGOGICAL_DEPLOYMENT":
            return ("pedagogical_deployment", "Deploys theoretical models and diagnostic frameworks directly into Knowledge Lab learning architectures.", 1.0)

    # Organization Arc Transitions
    if archetype == "organization":
        if cat1 == "EPISTEMIC_ANCHOR" and cat2 == "SYSTEMIC_FAILURE_MODE":
            return ("systemic_pathology", "Deconstructs the systemic pathology, digital divide, or market failure addressed by the institution.", 1.0)
        if cat1 == "SYSTEMIC_FAILURE_MODE" and cat2 == "ORGANIZATIONAL_ARCHITECTURE":
            return ("operational_architecture", "Presents the multi-pillar operational architecture mobilized to resolve the systemic pathology.", 1.0)
        if cat1 == "ORGANIZATIONAL_ARCHITECTURE" and cat2 == "COALITION_ECOSYSTEM":
            return ("coalition_network", "Details the strategic ecosystem, philanthropic alliances, and distribution networks.", 1.0)
        if cat1 == "COALITION_ECOSYSTEM" and cat2 == "STRATEGIC_ANALOGUE":
            return ("strategic_benchmark", "Establishes operational transfer mechanisms and strategic benchmarks for Knowledge Lab.", 1.0)

    # Software Arc Transitions
    if archetype in ("software", "platform"):
        if cat1 == "EPISTEMIC_ANCHOR" and cat2 == "TECHNICAL_ARCHITECTURE":
            return ("mechanistic_execution", "Deconstructs the under-the-hood mechanistic pipeline, data structures, and execution runtime.", 1.0)
        if cat1 == "TECHNICAL_ARCHITECTURE" and cat2 == "SYSTEMIC_FAILURE_MODE":
            return ("bottlenecks_solved", "Analyzes cognitive alignment and architectural bottlenecks resolved by the system.", 1.0)
        if cat1 == "SYSTEMIC_FAILURE_MODE" and cat2 == "INTEGRATION_TOPOLOGY":
            return ("stack_integration", "Specifies integration topology, runtime configurations, and orchestration hooks inside the Knowledge Lab stack.", 1.0)
        if cat1 == "INTEGRATION_TOPOLOGY" and cat2 == "OPERATIONAL_TELEMETRY":
            return ("operational_telemetry", "Provides empirical operational telemetry, resource envelopes, and boundary limits.", 1.0)

    return ("sequential_progression", f"Progresses sequentially from '{h1}' into '{h2}'.", 0.7)

def extract_and_sync_entity_cot(driver: Driver, database: str = DEFAULT_DATABASE):
    start_time = time.time()
    print("=================================================================")
    print("  Knowledge Lab :: Epistemic Entity Arcs (EEA) CoT Extraction")
    print("  Materializing Micro-CoT Sections & 6 Macro-CoT Typed Predicates")
    print("=================================================================")

    session_kwargs = {"database": database} if database else {}
    with driver.session(**session_kwargs) as session:
        # -------------------------------------------------------------
        # 1. Micro-CoT: Classify Entity Sections & Progressions
        # -------------------------------------------------------------
        print("\n[1/5] Scanning Intra-Entity Sections (Micro-CoT)...")
        sec_query = """
        MATCH (e:Entity)-[:HAS*1..3]->(s:Section)
        RETURN e.title AS doc_title,
               coalesce(e.subtype, CASE
                   WHEN e:Researcher THEN 'researcher'
                   WHEN e:Organization THEN 'organization'
                   WHEN e:Platform THEN 'platform'
                   ELSE 'software'
               END) AS archetype,
               s.uri AS uri,
               coalesce(s.displayName, s.title, s.name, 'Section') AS displayName,
               coalesce(s.content, '') AS content
        """
        sections = session.run(sec_query).data()
        print(f"  → Found {len(sections)} sections across entity notes.")

        section_updates = []
        for sec in sections:
            archetype = sec["archetype"]
            h_text = sec["displayName"]
            doc_t = sec["doc_title"]
            step_type = classify_entity_heading(h_text, archetype, doc_t)
            section_updates.append({
                "uri": sec["uri"],
                "step_type": step_type,
                "entity_role": step_type,
            })

        session.run("""
            UNWIND $batch AS item
            MATCH (s:Section {uri: item.uri})
            REMOVE s:CognitiveStep
            SET s.step_type = item.step_type,
                s.entity_role = item.entity_role,
                s.cot_classified = true
        """, batch=section_updates)
        print(f"  → Tagged {len(section_updates)} entity sections with archetypal step types.")

        # Sequential transitions
        pair_query = """
        MATCH (e:Entity)-[:HAS*1..3]->(s1:Section)-[:NEXT_SECTION]->(s2:Section)
        RETURN e.title AS doc_title,
               coalesce(e.subtype, CASE
                   WHEN e:Researcher THEN 'researcher'
                   WHEN e:Organization THEN 'organization'
                   WHEN e:Platform THEN 'platform'
                   ELSE 'software'
               END) AS archetype,
               s1.uri AS s1_uri, s1.step_type AS s1_cat, coalesce(s1.displayName, '') AS s1_title,
               s2.uri AS s2_uri, s2.step_type AS s2_cat, coalesce(s2.displayName, '') AS s2_title
        """
        pairs = session.run(pair_query).data()
        transitions = []
        for p in pairs:
            t_type, warrant, conf = infer_entity_transition_warrant(
                p["s1_cat"] or "", p["s2_cat"] or "", p["archetype"], p["s1_title"], p["s2_title"]
            )
            transitions.append({
                "s1_uri": p["s1_uri"],
                "s2_uri": p["s2_uri"],
                "transition_type": t_type,
                "warrant": warrant,
                "confidence": conf
            })

        session.run("""
            UNWIND $batch AS item
            MATCH (s1:Section {uri: item.s1_uri})
            MATCH (s2:Section {uri: item.s2_uri})
            MERGE (s1)-[r:PROGRESSES_TO]->(s2)
            SET r.transition_type = item.transition_type,
                r.warrant = item.warrant,
                r.confidence = item.confidence,
                r.method = 'entity_arc_rule',
                r.updated_at = datetime()
        """, batch=transitions)
        print(f"  → Materialized {len(transitions)} intra-entity sequential [:PROGRESSES_TO] edges.")

        # -------------------------------------------------------------
        # 2. Macro-CoT: Clean Stale Entity Relationships (Idempotency)
        # -------------------------------------------------------------
        print("\n[2/5] Resetting Stale Entity Semantic Handshakes...")
        del_res = session.run("""
            MATCH ()-[r:ORIGINATES_THEORY|CHAMPIONS_SOLUTION|CRITIQUES_PARADIGM|OPERATIONALIZES|AFFILIATED_WITH|INTELLECTUAL_LINEAGE|AUTHORED_BY|PUBLISHED_BY]->()
            DELETE r
            RETURN count(r) AS deleted_count
        """).single()
        print(f"  → Cleared {del_res['deleted_count']} previous entity relationships.")

        # -------------------------------------------------------------
        # 3. Macro-CoT: Materialize Section-Driven Agency Predicates
        # -------------------------------------------------------------
        print("\n[3/5] Materializing AST & Section-Driven Macro-CoT Handshakes...")

        # 3a. [:ORIGINATES_THEORY]
        orig_res = session.run("""
            MATCH (e:Entity)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(c:Concept)
            WHERE (e:Researcher OR e.subtype = 'researcher')
              AND (s.step_type IN ['EPISTEMIC_ANCHOR', 'CANONICAL_MODEL']
                   OR toLower(s.displayName) =~ '.*(epistemic role|core thesis|intellectual contribution|canonical formulation|methodological model|theoretical foundation|framework|principle|formulation|contribution|model|axiom|thesis|key frameworks).*')
              AND NOT s.displayName IN ['Related Notes', 'Related Primitives']
            WITH e, c, collect(DISTINCT s.displayName) AS sections, count(*) AS weight
            MERGE (e)-[r:ORIGINATES_THEORY]->(c)
            SET r.weight = weight,
                r.source_sections = sections,
                r.warrant = e.title + " originated, formulated, or introduced the foundational framework " + c.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {orig_res['count']} [:ORIGINATES_THEORY] links.")

        # 3b. [:CHAMPIONS_SOLUTION]
        champ_res = session.run("""
            MATCH (e:Entity)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(c:Concept)
            WHERE (e:Researcher OR e:Organization OR e.subtype IN ['researcher', 'organization'])
              AND NOT (e)-[:ORIGINATES_THEORY]->(c)
              AND (s.step_type IN ['PEDAGOGICAL_DEPLOYMENT', 'STRATEGIC_ANALOGUE', 'PRESCRIPTIVE_SOLUTION']
                   OR toLower(s.displayName) =~ '.*(pedagogical deployment|strategic analogue|benchmark|intervention|safeguard|mitigat|remedy|solution|policy|advocacy|examination culture|assessment|pedagogical support|strategic relevance|application|deployment).*')
              AND NOT s.displayName IN ['Related Notes', 'Related Primitives']
            WITH e, c, collect(DISTINCT s.displayName) AS sections, count(*) AS weight
            MERGE (e)-[r:CHAMPIONS_SOLUTION]->(c)
            SET r.weight = weight,
                r.source_sections = sections,
                r.warrant = e.title + " champions or prescribes " + c.title + " as an educational or operational intervention",
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {champ_res['count']} [:CHAMPIONS_SOLUTION] links.")

        # 3c. [:CRITIQUES_PARADIGM]
        crit_res = session.run("""
            MATCH (e:Entity)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(c:Concept)
            WHERE (s.step_type IN ['DIALECTICAL_CRITIQUE', 'SYSTEMIC_FAILURE_MODE', 'MANIFESTATION_TRAP', 'DILEMMA_PROBLEM']
                   OR toLower(s.displayName) =~ '.*(contested paradigm|dialectical critique|critique|pathology|bottleneck|dilemma|trap|failure|controversy|resistance|tension|checkbox|fallacy|breakdown|audit).*')
              AND NOT s.displayName IN ['Related Notes', 'Related Primitives']
              AND NOT (e)-[:ORIGINATES_THEORY]->(c)
            WITH e, c, collect(DISTINCT s.displayName) AS sections, count(*) AS weight
            MERGE (e)-[r:CRITIQUES_PARADIGM]->(c)
            SET r.weight = weight,
                r.source_sections = sections,
                r.warrant = e.title + " dialectically critiques, exposes failure modes in, or challenges " + c.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {crit_res['count']} [:CRITIQUES_PARADIGM] links.")

        # 3d. [:OPERATIONALIZES]
        oper_res = session.run("""
            MATCH (e:Entity)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(c:Concept)
            WHERE (e:Software OR e:Organization OR e.subtype IN ['software', 'organization', 'platform'])
              AND NOT (e)-[:ORIGINATES_THEORY]->(c)
              AND NOT (e)-[:CRITIQUES_PARADIGM]->(c)
              AND (s.step_type IN ['TECHNICAL_ARCHITECTURE', 'ORGANIZATIONAL_ARCHITECTURE', 'INTEGRATION_TOPOLOGY', 'MECHANISTIC_DEEPEN']
                   OR toLower(s.displayName) =~ '.*(mechanistic pipeline|execution model|operational architecture|integration topology|algorithmic deployment|system capabilities|technical architecture|capabilities|architecture|system architecture|operating philosophy|open-source technology|the comprehensive approach).*')
              AND NOT s.displayName IN ['Related Notes', 'Related Primitives']
            WITH e, c, collect(DISTINCT s.displayName) AS sections, count(*) AS weight
            MERGE (e)-[r:OPERATIONALIZES]->(c)
            SET r.weight = weight,
                r.source_sections = sections,
                r.warrant = e.title + " operationalizes, executes, or provides technical infrastructure for " + c.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {oper_res['count']} [:OPERATIONALIZES] links.")

        # 3e. [:AFFILIATED_WITH]
        aff_res = session.run("""
            MATCH (e1:Entity)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(e2:Entity)
            WHERE e1 <> e2
              AND ((e1:Researcher AND e2:Organization)
                   OR toLower(s.displayName) =~ '.*(affiliation|governance|coalition|ecosystem|career|leadership|partner|institution|network|background|profile|advisory).*')
              AND NOT s.displayName IN ['Related Notes', 'Related Primitives']
            WITH e1, e2, collect(DISTINCT s.displayName) AS sections, count(*) AS weight
            MERGE (e1)-[r:AFFILIATED_WITH]->(e2)
            SET r.weight = weight,
                r.source_sections = sections,
                r.warrant = e1.title + " maintains institutional affiliation, governance, or advisory ties with " + e2.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {aff_res['count']} [:AFFILIATED_WITH] links.")

        # 3f. [:INTELLECTUAL_LINEAGE]
        lin_res = session.run("""
            MATCH (e1:Researcher)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(e2:Researcher)
            WHERE e1 <> e2
              AND (s.step_type = 'INTELLECTUAL_LINEAGE'
                   OR toLower(s.displayName) =~ '.*(intellectual lineage|lineage|theoretical foundation|predecessor|mentor|influence|collaborator|co-formulation|academic background|foundational research).*')
              AND NOT s.displayName IN ['Related Notes', 'Related Primitives']
            WITH e1, e2, collect(DISTINCT s.displayName) AS sections, count(*) AS weight
            MERGE (e1)-[r:INTELLECTUAL_LINEAGE]->(e2)
            SET r.weight = weight,
                r.source_sections = sections,
                r.warrant = e1.title + " shares intellectual lineage, collaboration, or theoretical inheritance with " + e2.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {lin_res['count']} [:INTELLECTUAL_LINEAGE] links.")

        # 3g. Inbound Literature Grounding: [:AUTHORED_BY] & [:PUBLISHED_BY]
        auth_res = session.run("""
            MATCH (src:Source)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(r:Researcher)
            WITH src, r, collect(DISTINCT s.displayName) AS sections, count(*) AS weight
            MERGE (src)-[r_rel:AUTHORED_BY]->(r)
            SET r_rel.weight = weight,
                r_rel.source_sections = sections,
                r_rel.warrant = src.title + " is authored, researched, or theorized by " + r.title,
                r_rel.updated_at = datetime()
            RETURN count(r_rel) AS count
        """).single()
        print(f"  → Materialized {auth_res['count']} [:AUTHORED_BY] links.")

        pub_res = session.run("""
            MATCH (src:Source)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(o:Organization)
            WITH src, o, collect(DISTINCT s.displayName) AS sections, count(*) AS weight
            MERGE (src)-[r_rel:PUBLISHED_BY]->(o)
            SET r_rel.weight = weight,
                r_rel.source_sections = sections,
                r_rel.warrant = src.title + " is published, hosted, or commissioned by " + o.title,
                r_rel.updated_at = datetime()
            RETURN count(r_rel) AS count
        """).single()
        print(f"  → Materialized {pub_res['count']} [:PUBLISHED_BY] links.")

        # -------------------------------------------------------------
        # 4. Related Primitives Granular Sub-Bullet Parsing
        # -------------------------------------------------------------
        print("\n[4/5] Parsing Structured Sub-Bullets in 'Related Primitives' & Notes...")
        rel_secs = session.run("""
            MATCH (e:Entity)-[:HAS*1..3]->(s:Section)
            WHERE s.displayName IN ['Related Primitives', 'Related Notes', '3. Related Primitives', '4. Related Primitives']
               OR s.content =~ '(?s).*\\*\\*(Originated Concepts|Contested Theories|Championed Methodologies|Operationalized Concepts|Collaborators & Lineage|Institutional Affiliates)\\*\\*:.*'
            RETURN e.title AS entity, labels(e) AS entity_labels, s.displayName AS sec_name, s.content AS content
        """).data()

        bullet_counts = {
            "ORIGINATES_THEORY": 0,
            "CRITIQUES_PARADIGM": 0,
            "CHAMPIONS_SOLUTION": 0,
            "OPERATIONALIZES": 0,
            "INTELLECTUAL_LINEAGE": 0,
            "AFFILIATED_WITH": 0,
        }

        bullet_specs = [
            (r"\*\*(?:Originated Concepts|Core Theories)\*\*:(.*?)(?=\n\s*-\s*\*\*|\Z)", "ORIGINATES_THEORY", "originated foundational theory"),
            (r"\*\*(?:Contested Theories|Dialectical Critiques)\*\*:(.*?)(?=\n\s*-\s*\*\*|\Z)", "CRITIQUES_PARADIGM", "dialectically critiques"),
            (r"\*\*(?:Championed Methodologies|Prescribed Solutions)\*\*:(.*?)(?=\n\s*-\s*\*\*|\Z)", "CHAMPIONS_SOLUTION", "champions prescriptive solution"),
            (r"\*\*(?:Operationalized Concepts|Engineered Products & Tools)\*\*:(.*?)(?=\n\s*-\s*\*\*|\Z)", "OPERATIONALIZES", "operationalizes"),
            (r"\*\*(?:Collaborators & Lineage|Intellectual Lineage)\*\*:(.*?)(?=\n\s*-\s*\*\*|\Z)", "INTELLECTUAL_LINEAGE", "intellectual lineage with"),
            (r"\*\*(?:Institutional Affiliates|Governing Organizations|Strategic Supporters)\*\*:(.*?)(?=\n\s*-\s*\*\*|\Z)", "AFFILIATED_WITH", "affiliated with"),
        ]

        for r_sec in rel_secs:
            e_title = r_sec["entity"]
            c_text = r_sec["content"]

            for pattern, rel_type, warrant_verb in bullet_specs:
                matches = re.findall(pattern, c_text, re.DOTALL | re.IGNORECASE)
                for chunk in matches:
                    targets = re.findall(r"\[\[([^\]\|]+)(?:\|[^\]]+)?\]\]", chunk)
                    for t in targets:
                        t_clean = t.strip()
                        # Merge relation in Neo4j
                        session.run(f"""
                            MATCH (e:Entity {{title: $e_title}})
                            MATCH (dst:Document {{title: $t_clean}})
                            MERGE (e)-[r:{rel_type}]->(dst)
                            SET r.weight = coalesce(r.weight, 0) + 1,
                                r.source_sections = CASE 
                                    WHEN r.source_sections IS NULL THEN [$sec_name]
                                    WHEN NOT $sec_name IN r.source_sections THEN r.source_sections + $sec_name
                                    ELSE r.source_sections
                                END,
                                r.warrant = e.title + ' {warrant_verb} ' + dst.title,
                                r.updated_at = datetime()
                        """, e_title=e_title, t_clean=t_clean, sec_name=r_sec["sec_name"])
                        bullet_counts[rel_type] += 1

        print(f"  → Granular bullet parsing added/reinforced:")
        for r_type, cnt in bullet_counts.items():
            if cnt > 0:
                print(f"    * [:{r_type}]: +{cnt}")

        # -------------------------------------------------------------
        # 5. Graph Verification & Summary Telemetry
        # -------------------------------------------------------------
        print("\n[5/5] Computing Entity Telemetry & Summary Distribution...")
        summary = session.run("""
            MATCH (e:Entity)-[r]->(target)
            WHERE type(r) IN ['ORIGINATES_THEORY', 'CHAMPIONS_SOLUTION', 'CRITIQUES_PARADIGM',
                              'OPERATIONALIZES', 'AFFILIATED_WITH', 'INTELLECTUAL_LINEAGE']
            RETURN type(r) AS rel_type, count(r) AS count, count(DISTINCT e) AS active_entities
            ORDER BY count DESC
        """).data()

        print("\n  ================ Active Macro-CoT Entity Predicates ================")
        print(f"  {'Relationship Predicate':<26} | {'Total Edges':<12} | {'Active Entities':<15}")
        print("  " + "-" * 60)
        total_macro = 0
        for row in summary:
            print(f"  [:{row['rel_type']:<24}] | {row['count']:<12} | {row['active_entities']:<15}")
            total_macro += row["count"]
        print("  " + "-" * 60)
        print(f"  {'Total Materialized Agency Edges':<26} | {total_macro:<12} |")
        print("  ====================================================================")

    elapsed = time.time() - start_time
    print(f"\n[✓] Epistemic Entity Arcs Extraction Complete in {elapsed:.2f}s!")

def main():
    parser = argparse.ArgumentParser(description="Extract Epistemic Entity Arcs (EEA) into Neo4j")
    parser.add_argument("--uri", default=DEFAULT_URI, help="Neo4j Bolt URI")
    parser.add_argument("--user", default=DEFAULT_USER, help="Neo4j username")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Neo4j password")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="Neo4j database name")
    args = parser.parse_args()

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password), max_connection_lifetime=60)
    try:
        extract_and_sync_entity_cot(driver, database=args.database)
    finally:
        driver.close()

if __name__ == "__main__":
    main()
