#!/usr/bin/env python3
"""
scripts/ingest_to_arcadedb.py
Autonomous, direct Markdown-to-ArcadeDB compilation pipeline.
Decoupled completely from Neo4j:
  1. AST parsing of wiki/ concepts, entities, sources, and syntheses.
  2. Diagram extraction & decoupling: extracts Mermaid diagrams into ArcadeDB's
     'Diagram' collection and replaces them with high-signal semantic flow transcripts.
  3. Toulmin role classification & frequency-weighted modal certainty scoring.
  4. Micro-CoT [:PROGRESSES_TO] and Macro-CoT [:REMEDIES_DILEMMA, :EXTENDS_THEORY, :PRECIPITATES] extraction.
  5. High-density batch NDJSON ingestion into ArcadeDB via /api/v1/batch/knowledgedb.
  6. In-engine Graph OLAP execution (PageRank with Toulmin edge weights, Louvain community, Betweenness).

Usage:
    python3 scripts/ingest_to_arcadedb.py [--purge] [--skip-olap]
"""

import os
import re
import sys
import time
import json
import base64
import hashlib
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from functools import lru_cache
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple, Set

VAULT_ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = VAULT_ROOT / "wiki"

# Sourcing .env
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

ARCADEDB_URL = os.getenv("ARCADEDB_URL", "http://localhost:2480")
ARCADEDB_DATABASE = os.getenv("ARCADEDB_DATABASE", "knowledgedb")
ARCADEDB_USER = os.getenv("ARCADEDB_USER", "root")
ARCADEDB_PASSWORD = os.getenv("ARCADEDB_PASSWORD", "root_secret")


class ArcadeDBClient:
    """Zero-dependency client for ArcadeDB HTTP APIs."""

    def __init__(self, base_url: str = ARCADEDB_URL, database: str = ARCADEDB_DATABASE,
                 user: str = ARCADEDB_USER, password: str = ARCADEDB_PASSWORD):
        self.base_url = base_url.rstrip("/")
        self.database = database
        self.auth_header = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()

    def query(self, command: str, language: str = "cypher") -> List[Dict[str, Any]]:
        url = f"{self.base_url}/api/v1/query/{self.database}"
        payload = json.dumps({"command": command, "language": language}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Authorization": self.auth_header, "Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                return json.loads(resp.read().decode("utf-8")).get("result", [])
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Query error {e.code}: {err}") from e

    def execute_command(self, command: str, language: str = "sql") -> List[Dict[str, Any]]:
        url = f"{self.base_url}/api/v1/command/{self.database}"
        payload = json.dumps({"command": command, "language": language}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Authorization": self.auth_header, "Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                return json.loads(resp.read().decode("utf-8")).get("result", [])
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Command error {e.code}: {err}") from e

    def batch_ndjson(self, ndjson_lines: List[str]) -> Dict[str, Any]:
        if not ndjson_lines:
            return {"verticesCreated": 0, "edgesCreated": 0, "elapsedMs": 0}
        url = f"{self.base_url}/api/v1/batch/{self.database}"
        payload = "\n".join(ndjson_lines).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Authorization": self.auth_header, "Content-Type": "application/x-ndjson"}
        )
        try:
            with urllib.request.urlopen(req, timeout=90.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Batch error {e.code}: {err}") from e


# ==============================================================================
# 1. Mermaid Extraction & Semantic Transcoding
# ==============================================================================

MERMAID_REGEX = re.compile(r'```mermaid\n(.*?)```', re.DOTALL)
NODE_LABEL_REGEX = re.compile(r'([A-Za-z0-9_\-]+)(?:\["([^"]+)"\]|\[([^\]]+)\]|\("([^"]+)"\)|\(([^)]+)\))')
HEADER_REGEX = re.compile(
    r'^\s*(flowchart|graph|sequenceDiagram|stateDiagram|classDiagram)\s*([A-Z]+)?',
    re.MULTILINE
)

def process_section_diagrams(
    section_uri: str,
    section_title: str,
    raw_content: str
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Strips raw Mermaid diagrams from content and returns:
    (clean_content_with_callouts, list_of_diagram_document_dicts)
    """
    diagrams: List[Dict[str, Any]] = []

    def replacer(match: re.Match) -> str:
        diagram_idx = len(diagrams) + 1
        raw_code = match.group(1).strip()

        hdr_match = HEADER_REGEX.search(raw_code)
        dtype = hdr_match.group(1) if hdr_match else "flowchart"
        direction = hdr_match.group(2) if hdr_match and hdr_match.group(2) else "TD"

        labels: List[str] = []
        for m in NODE_LABEL_REGEX.finditer(raw_code):
            lbl = m.group(2) or m.group(3) or m.group(4) or m.group(5)
            if lbl:
                clean_lbl = lbl.replace("<br/>", " - ").replace("<br>", " - ").strip()
                if clean_lbl and clean_lbl not in labels:
                    labels.append(clean_lbl)

        if labels:
            flow_summary = " → ".join(labels[:6])
            if len(labels) > 6:
                flow_summary += f" (and {len(labels) - 6} more steps)"
        else:
            flow_summary = "Visual conceptual architecture"

        diag_id = hashlib.sha256(
            f"{section_uri}|diag_{diagram_idx}".encode("utf-8")
        ).hexdigest()[:16]

        diagrams.append({
            "id": diag_id,
            "section_uri": section_uri,
            "title": f"{section_title} - Diagram {diagram_idx}",
            "diagram_type": dtype,
            "direction": direction,
            "raw_code": match.group(0),
            "node_labels": labels,
            "semantic_transcript": flow_summary,
            "order_idx": diagram_idx,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        })

        return ""

    clean_content = MERMAID_REGEX.sub(replacer, raw_content)
    clean_content = re.sub(r'\n{3,}', '\n\n', clean_content).strip()
    return clean_content, diagrams


# ==============================================================================
# 2. Linguistic Weight Calculation
# ==============================================================================

def _strip_markdown(text: str) -> str:
    """Strip markup for lexical modal keyword scoring."""
    text = re.sub(r'```mermaid.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'\[\[.*?\]\]', '', text)
    text = re.sub(r'uri:wiki/.*', '', text)
    text = re.sub(r'> \[!.*?\].*?\n', '', text)
    text = re.sub(r'\$.*?\$', '', text)
    return text


MODAL_PATTERNS = [
    (r'\b(necessarily|always|invariably|definitively|completely|total|zero|100%|never)\b', 1.0,  "CERTAINTY"),
    (r'\b(typically|generally|in most cases|consistently|must|will|every)\b',              0.85, "HIGH_PROB"),
    (r'\b(often|usually|tends to|frequently|regularly)\b',                                 0.65, "MODERATE_HIGH"),
    (r'\b(can|may|sometimes|in some cases|often produces|tend)\b',                         0.45, "MODERATE_LOW"),
    (r'\b(possibly|perhaps|might|could|under certain|in specific contexts)\b',             0.30, "HEDGED"),
    (r'\b(rarely|seldom|not always|only when|limited|narrow|few)\b',                       0.15, "WEAK"),
]

STEP_TYPE_FLOOR = {
    "DEFINITIONAL_ANCHOR": 0.75,
    "SYNTHESIS_CATALOG":   0.50,
    "NARRATIVE_STEP":      0.50,
}

@lru_cache(maxsize=2048)
def compute_linguistic_weight(text: str, step_type: str = "") -> Tuple[float, str, List[str]]:
    clean = _strip_markdown(text).lower()
    weighted_sum = 0.0
    hit_count_total = 0
    matched = []
    best_cat = "NEUTRAL"
    best_score = 0.0

    for pattern, score, category in MODAL_PATTERNS:
        hits = re.findall(pattern, clean)
        if hits:
            weighted_sum += score * len(hits)
            hit_count_total += len(hits)
            matched.extend(hits[:2])
            if score > best_score:
                best_score = score
                best_cat = category

    if hit_count_total == 0:
        raw = STEP_TYPE_FLOOR.get(step_type, 0.5)
        return round(raw, 3), "NEUTRAL", []

    freq_weighted = weighted_sum / hit_count_total
    floor = STEP_TYPE_FLOOR.get(step_type, 0.0)
    raw = max(floor, round(freq_weighted, 3))
    return raw, best_cat, matched[:5]


# ==============================================================================
# 3. Section Classification & Toulmin Mapping
# ==============================================================================

def map_to_toulmin_role(step_type: str, doc_type: str = "concept") -> str:
    if doc_type in ("entity", "source"):
        return "NON_ARGUMENTATIVE"

    mapping = {
        "DEFINITIONAL_ANCHOR": "GROUNDS",
        "CORE_THESIS": "CLAIM",
        "MECHANISTIC_DEEPEN": "WARRANT",
        "MANIFESTATION_TRAP": "REBUTTAL",
        "DILEMMA_PROBLEM": "REBUTTAL",
        "PRESCRIPTIVE_SOLUTION": "SOLUTION_WARRANT",
        "EMPIRICAL_BOUNDARY": "QUALIFIER",
        "SYNTHESIS_CATALOG": "BACKING",
    }
    return mapping.get(step_type, "NON_ARGUMENTATIVE")


def classify_section(doc_title: str, doc_type: str, heading_text: str, content: str, is_lead: bool) -> Tuple[str, List[str]]:
    h_lower = (heading_text or "").lower().strip()

    if is_lead or (doc_type == "concept" and h_lower == doc_title.lower().strip()) or "[!important] definitional anchor" in content.lower():
        return "DEFINITIONAL_ANCHOR", ["DefinitionalAnchor", "Summary"]

    if re.search(r"^(##\s*)?1[\.\:]\s*(core thesis|definitional anchor)", h_lower) or h_lower.startswith("1. core thesis"):
        return "CORE_THESIS", ["DefinitionalAnchor", "CoreThesis"]

    if re.search(r"^(##\s*)?2[\.\:]\s*(causal anatomy|underlying mechanics)", h_lower):
        return "MECHANISTIC_DEEPEN", ["MechanisticDeepen"]

    if re.search(r"^(##\s*)?3[\.\:]\s*(manifestations|failure modes|pathologies|traps)", h_lower):
        return "MANIFESTATION_TRAP", ["ManifestationTrap"]

    if re.search(r"^(##\s*)?4[\.\:]\s*(prescriptive mitigations|counter-architectures|solutions|remedies)", h_lower):
        return "PRESCRIPTIVE_SOLUTION", ["PrescriptiveSolution"]

    if re.search(r"^(##\s*)?5[\.\:]\s*(empirical boundaries|contradictions|limitations)", h_lower):
        return "EMPIRICAL_BOUNDARY", ["EmpiricalBoundary"]

    if re.search(r"^(##\s*)?6[\.\:]\s*(related primitives|synthesis catalog|related notes)", h_lower):
        return "SYNTHESIS_CATALOG", ["SynthesisCatalog"]

    # Fallback keyword checks
    if re.search(r"(solution|mitigat|safeguard|countermeasure|counter-architecture|counter-measure|remedy|intervention|protocol|governance|repayment|action|defense)", h_lower):
        return "PRESCRIPTIVE_SOLUTION", ["PrescriptiveSolution"]

    if re.search(r"(boundary|exception|rebuttal|contradiction|tension|debate|limitation|constraint|risk)", h_lower):
        return "EMPIRICAL_BOUNDARY", ["EmpiricalBoundary"]

    if re.search(r"(trap|failure|misattribution|illusion|collapse|offloading|fatigue|debt|pathology|symptom|manifestation|backlash)", h_lower):
        return "MANIFESTATION_TRAP", ["ManifestationTrap"]

    if re.search(r"(tension|paradox|problem|crisis|challenge|gap|dilemma|anomaly|threat|blindspot|vulnerability|friction)", h_lower):
        return "DILEMMA_PROBLEM", ["DilemmaProblem"]

    if re.search(r"(related notes|related primitives|references|see also|further reading|citations|bibliography|synthesis catalog)", h_lower):
        return "SYNTHESIS_CATALOG", ["SynthesisCatalog"]

    if re.search(r"(mechanism|anatomy|engine|underlying|process|driver|loop|dynamics|architecture|operational|structural)", h_lower):
        return "MECHANISTIC_DEEPEN", ["MechanisticDeepen"]

    if re.search(r"(definition|overview|anchor|thesis|concept|core|foundation|framework|introduction)", h_lower):
        return "DEFINITIONAL_ANCHOR", ["DefinitionalAnchor"]

    return "NARRATIVE_STEP", []


def infer_transition_rule(cat1: str, cat2: str) -> Tuple[str, str, float]:
    if cat1 == "DEFINITIONAL_ANCHOR" and cat2 == "CORE_THESIS":
        return ("core_thesis_elaboration", "Elaborates foundational definitional anchor into primary core thesis.", 1.0)
    if cat2 == "PRESCRIPTIVE_SOLUTION":
        return ("prescriptive_solution", "Prescribes architectural safeguards to resolve preceding failure mode.", 1.0)
    if cat1 in ("DEFINITIONAL_ANCHOR", "CORE_THESIS") and cat2 == "MECHANISTIC_DEEPEN":
        return ("mechanistic_deepen", "Deconstructs foundational core thesis into underlying causal mechanisms.", 1.0)
    if cat1 in ("MECHANISTIC_DEEPEN", "DEFINITIONAL_ANCHOR", "CORE_THESIS") and cat2 == "MANIFESTATION_TRAP":
        return ("manifestation_trap", "Traces how causal mechanisms precipitate observable failure modes.", 1.0)
    if cat2 == "EMPIRICAL_BOUNDARY":
        return ("empirical_boundary", "Delineates empirical boundary conditions and counter-perspectives.", 1.0)
    if cat2 == "SYNTHESIS_CATALOG":
        return ("synthesis_catalog", "Synthesizes touchpoints into broader knowledge graph.", 1.0)
    return ("narrative_progression", "Progresses deductive argumentation sequence.", 0.85)


# ==============================================================================
# 4. Markdown Document Parsing
# ==============================================================================

def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter (including block lists) and return (metadata, body)."""
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    fm_text = parts[1]
    body = parts[2]
    meta: Dict[str, Any] = {}
    current_list_key = None
    current_bracket_key = None

    for line in fm_text.splitlines():
        line_str = line.strip()
        if not line_str or line_str.startswith("#"):
            continue

        # Check for multi-line bracketed list items
        if current_bracket_key:
            if line_str == "]":
                current_bracket_key = None
                continue
            cleaned_line = line_str.rstrip(",")
            if cleaned_line.endswith("]"):
                cleaned_line = cleaned_line[:-1].rstrip(",")
                current_bracket_key = None
            for part in cleaned_line.split(","):
                val = re.sub(r'[\'"]', '', part.strip())
                if val and val != "]":
                    meta[current_bracket_key if current_bracket_key else k].append(val)
            continue

        # Check for multi-line list items (- item)
        if current_list_key and line.startswith(("  -", "\t-", "- ")):
            item_val = re.sub(r'^\s*-\s*', '', line).strip()
            item_val = re.sub(r'^[\'"]|[\'"]$', '', item_val)
            meta[current_list_key].append(item_val)
            continue

        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            current_list_key = None
            current_bracket_key = None

            if not v:
                meta[k] = []
                current_list_key = k
            elif v == "[":
                meta[k] = []
                current_bracket_key = k
            elif v.startswith("[") and v.endswith("]"):
                items = [re.sub(r'[\'"]', '', x.strip()) for x in v[1:-1].split(",") if x.strip()]
                meta[k] = items
            elif v.startswith("[") and not v.endswith("]"):
                meta[k] = []
                current_bracket_key = k
                rest = v[1:].strip()
                if rest:
                    for part in rest.rstrip(",").split(","):
                        val = re.sub(r'[\'"]', '', part.strip())
                        if val:
                            meta[k].append(val)
            elif v.lower() in ("true", "false"):
                meta[k] = (v.lower() == "true")
            elif (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                meta[k] = v[1:-1]
            else:
                try:
                    if "." in v:
                        meta[k] = float(v)
                    else:
                        meta[k] = int(v)
                except ValueError:
                    meta[k] = v
    return meta, body



def extract_wikilinks(text: str) -> List[str]:
    """Extract target note titles from [[Target|Alias]] or [[Target]]."""
    links = []
    for match in re.finditer(r'\[\[(.*?)\]\]', text):
        raw = match.group(1).split("|")[0].split("#")[0].strip()
        # Clean directory prefixes
        raw = re.sub(r'^(wiki/)?(concepts|entities|sources|syntheses)/', '', raw).strip()
        if raw and raw not in links:
            links.append(raw)
    return links


def parse_sections(file_rel_path: str, body: str) -> List[Dict[str, Any]]:
    """Split markdown body into section objects with heading, content, and line numbers."""
    lines = body.splitlines()
    sections: List[Dict[str, Any]] = []

    current_title = "Lead"
    current_level = 1
    current_lines: List[str] = []
    sec_idx = 1

    for line in lines:
        m = re.match(r'^(#{1,4})\s+(.+)$', line)
        if m:
            if current_lines or sec_idx == 1:
                sec_content = "\n".join(current_lines).strip()
                if sec_content:
                    sections.append({
                        "idx": sec_idx,
                        "title": current_title,
                        "heading_level": current_level,
                        "content": sec_content,
                        "is_lead": sec_idx == 1
                    })
                    sec_idx += 1
            current_level = len(m.group(1))
            current_title = m.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sec_content = "\n".join(current_lines).strip()
        if sec_content:
            sections.append({
                "idx": sec_idx,
                "title": current_title,
                "heading_level": current_level,
                "content": sec_content,
                "is_lead": sec_idx == 1
            })

    return sections


# ==============================================================================
# 5. Schema Setup & Main Ingestion Engine
# ==============================================================================

def init_schema(client: ArcadeDBClient):
    print("  [*] Ensuring ArcadeDB types and indexes exist...")
    vertex_types = ["Concept", "Entity", "Source", "Section", "Tag", "Diagram", "Synthesis"]
    for vt in vertex_types:
        try:
            client.execute_command(f"CREATE VERTEX TYPE {vt} IF NOT EXISTS", language="sql")
        except Exception:
            pass

    schema_commands = [
        "CREATE PROPERTY Concept.title STRING",
        "CREATE PROPERTY Concept.type STRING",
        "CREATE PROPERTY Concept.reliability_score DOUBLE",
        "CREATE PROPERTY Concept.last_updated STRING",
        "CREATE INDEX IF NOT EXISTS ON Concept (title) UNIQUE",

        "CREATE PROPERTY Entity.title STRING",
        "CREATE PROPERTY Entity.subtype STRING",
        "CREATE PROPERTY Entity.reliability_score DOUBLE",
        "CREATE INDEX IF NOT EXISTS ON Entity (title) UNIQUE",

        "CREATE PROPERTY Source.slug STRING",
        "CREATE PROPERTY Source.title STRING",
        "CREATE INDEX IF NOT EXISTS ON Source (slug) UNIQUE",

        "CREATE PROPERTY Tag.name STRING",
        "CREATE INDEX IF NOT EXISTS ON Tag (name) UNIQUE",

        "CREATE PROPERTY Section.uri STRING",
        "CREATE PROPERTY Section.title STRING",
        "CREATE PROPERTY Section.display_name STRING",
        "CREATE PROPERTY Section.path STRING",
        "CREATE PROPERTY Section.heading_level INTEGER",
        "CREATE PROPERTY Section.heading STRING",
        "CREATE PROPERTY Section.content STRING",
        "CREATE PROPERTY Section.content_hash STRING",
        "CREATE PROPERTY Section.step_type STRING",
        "CREATE PROPERTY Section.toulmin_role STRING",
        "CREATE PROPERTY Section.weight FLOAT",
        "CREATE PROPERTY Section.modal_category STRING",
        "CREATE PROPERTY Section.embedding LIST OF FLOAT",
        "CREATE INDEX IF NOT EXISTS ON Section (uri) UNIQUE",
        "CREATE INDEX IF NOT EXISTS ON Section (toulmin_role) NOTUNIQUE",

        "CREATE PROPERTY Diagram.id STRING",
        "CREATE PROPERTY Diagram.section_uri STRING",
        "CREATE PROPERTY Diagram.title STRING",
        "CREATE PROPERTY Diagram.diagram_type STRING",
        "CREATE PROPERTY Diagram.direction STRING",
        "CREATE PROPERTY Diagram.raw_code STRING",
        "CREATE PROPERTY Diagram.node_labels LIST OF STRING",
        "CREATE PROPERTY Diagram.semantic_transcript STRING",
        "CREATE PROPERTY Diagram.order_idx INTEGER",
        "CREATE PROPERTY Diagram.created_at STRING",
        "CREATE INDEX IF NOT EXISTS ON Diagram (id) UNIQUE",
        "CREATE INDEX IF NOT EXISTS ON Diagram (section_uri) NOTUNIQUE",

        "CREATE PROPERTY Synthesis.title STRING",
        "CREATE PROPERTY Synthesis.slug STRING",
        "CREATE PROPERTY Synthesis.subtype STRING",
        "CREATE PROPERTY Synthesis.last_updated STRING",
        "CREATE PROPERTY Synthesis.stale BOOLEAN",
        "CREATE PROPERTY Synthesis.stale_reason STRING",
        "CREATE PROPERTY Synthesis.reliability_score DOUBLE",
        "CREATE PROPERTY Synthesis.content STRING",
        "CREATE INDEX IF NOT EXISTS ON Synthesis (slug) UNIQUE",
        "CREATE INDEX IF NOT EXISTS ON Synthesis (title) UNIQUE",

        "CREATE DOCUMENT TYPE AliasLookup IF NOT EXISTS",
        "CREATE PROPERTY AliasLookup.alias STRING",
        "CREATE PROPERTY AliasLookup.canonical_title STRING",
        "CREATE INDEX IF NOT EXISTS ON AliasLookup (alias) UNIQUE",

        "CREATE DOCUMENT TYPE SynthesisDelta IF NOT EXISTS",
        "CREATE PROPERTY SynthesisDelta.synthesis_slug STRING",
        "CREATE PROPERTY SynthesisDelta.section_uri STRING",
        "CREATE PROPERTY SynthesisDelta.change_type STRING",
        "CREATE PROPERTY SynthesisDelta.diff_snippet STRING",
        "CREATE PROPERTY SynthesisDelta.timestamp STRING",
        "CREATE PROPERTY SynthesisDelta.resolved BOOLEAN",
        "CREATE INDEX IF NOT EXISTS ON SynthesisDelta (synthesis_slug) NOTUNIQUE",
    ]
    for cmd in schema_commands:
        try:
            client.execute_command(cmd, language="sql")
        except Exception:
            pass

    edge_types = [
        "PROGRESSES_TO", "NEXT_SECTION", "REMEDIES_DILEMMA", "EXTENDS_THEORY", "PRECIPITATES",
        "EMPIRICALLY_GROUNDS", "ORIGINATES_THEORY", "CHAMPIONS_SOLUTION",
        "CRITIQUES_PARADIGM", "OPERATIONALIZES", "AFFILIATED_WITH",
        "INTELLECTUAL_LINEAGE", "AUTHORED_BY", "PUBLISHED_BY",
        "HAS_SECTION", "TAGGED_WITH", "LINKS_TO", "CITES",
        "HAS_GROUNDS", "HAS_WARRANT", "HAS_CLAIM", "HAS_REBUTTAL",
        "HAS_SOLUTION", "HAS_QUALIFIER", "HAS_BACKING", "HAS_DIAGRAM",
        "SYNTHESIZES", "SYNTHESIZES_SECTION"
    ]
    for et in edge_types:
        try:
            client.execute_command(f"CREATE EDGE TYPE {et} IF NOT EXISTS", language="sql")
        except Exception:
            pass

    edge_props = [
        "CREATE PROPERTY PROGRESSES_TO.transition_type STRING",
        "CREATE PROPERTY PROGRESSES_TO.warrant STRING",
        "CREATE PROPERTY PROGRESSES_TO.confidence FLOAT",
        "CREATE PROPERTY PROGRESSES_TO.method STRING",
        "CREATE PROPERTY HAS_GROUNDS.weight FLOAT",
        "CREATE PROPERTY HAS_WARRANT.weight FLOAT",
        "CREATE PROPERTY HAS_REBUTTAL.weight FLOAT",
        "CREATE PROPERTY HAS_REBUTTAL.signed_weight FLOAT",
        "CREATE PROPERTY HAS_SOLUTION.weight FLOAT",
        "CREATE PROPERTY HAS_QUALIFIER.weight FLOAT",
        "CREATE PROPERTY HAS_BACKING.weight FLOAT",
        "CREATE PROPERTY HAS_CLAIM.weight FLOAT",
        "CREATE PROPERTY REMEDIES_DILEMMA.weight FLOAT",
        "CREATE PROPERTY EXTENDS_THEORY.weight FLOAT",
        "CREATE PROPERTY PRECIPITATES.weight FLOAT",
        "CREATE PROPERTY NEXT_SECTION.order_idx INTEGER",
        "CREATE PROPERTY HAS_DIAGRAM.order_idx INTEGER",
        "CREATE PROPERTY SYNTHESIZES.weight FLOAT",
        "CREATE PROPERTY SYNTHESIZES_SECTION.grounded_heading STRING",
        "CREATE PROPERTY SYNTHESIZES_SECTION.toulmin_role STRING",
        "CREATE PROPERTY SYNTHESIZES_SECTION.step_type STRING",
        "CREATE PROPERTY SYNTHESIZES_SECTION.weight FLOAT",
        "CREATE PROPERTY SYNTHESIZES_SECTION.expected_hash STRING",
        "CREATE PROPERTY SYNTHESIZES_SECTION.drift_detected BOOLEAN",
        "CREATE PROPERTY SYNTHESIZES_SECTION.last_checked STRING",
        "CREATE PROPERTY CITES.weight FLOAT",
        "CREATE PROPERTY EMPIRICALLY_GROUNDS.weight FLOAT",
        "CREATE PROPERTY EMPIRICALLY_GROUNDS.warrant STRING",
        "CREATE PROPERTY ORIGINATES_THEORY.weight FLOAT",
        "CREATE PROPERTY ORIGINATES_THEORY.warrant STRING",
        "CREATE PROPERTY CHAMPIONS_SOLUTION.weight FLOAT",
        "CREATE PROPERTY CHAMPIONS_SOLUTION.warrant STRING",
        "CREATE PROPERTY CRITIQUES_PARADIGM.weight FLOAT",
        "CREATE PROPERTY CRITIQUES_PARADIGM.warrant STRING",
        "CREATE PROPERTY OPERATIONALIZES.weight FLOAT",
        "CREATE PROPERTY OPERATIONALIZES.warrant STRING",
        "CREATE PROPERTY AFFILIATED_WITH.weight FLOAT",
        "CREATE PROPERTY AFFILIATED_WITH.warrant STRING",
        "CREATE PROPERTY INTELLECTUAL_LINEAGE.weight FLOAT",
        "CREATE PROPERTY INTELLECTUAL_LINEAGE.warrant STRING",
        "CREATE PROPERTY AUTHORED_BY.weight FLOAT",
        "CREATE PROPERTY AUTHORED_BY.warrant STRING",
        "CREATE PROPERTY PUBLISHED_BY.weight FLOAT",
        "CREATE PROPERTY PUBLISHED_BY.warrant STRING",
        "CREATE INDEX IF NOT EXISTS ON HAS_WARRANT (weight) NOTUNIQUE",
        "CREATE INDEX IF NOT EXISTS ON HAS_REBUTTAL (weight) NOTUNIQUE",
    ]
    for cmd in edge_props:
        try:
            client.execute_command(cmd, language="sql")
        except Exception:
            pass
    print("  [✓] ArcadeDB schema verified.")


def run_direct_ingestion(client: ArcadeDBClient, purge: bool = False, skip_olap: bool = False):
    print("\n=================================================================")
    print("  Direct Markdown-to-ArcadeDB Autonomous Compilation Pipeline")
    print(f"  Target Database : {client.database} @ {client.base_url}")
    print("=================================================================")

    init_schema(client)

    preserved_synth_edges = {}
    preserved_deltas = []
    preserved_synth_stale = {}

    if purge:
        print("  [*] Snapshotting synthesis delta & anchor state before purge...")
        try:
            existing_edges = client.query(
                "MATCH (s:Synthesis)-[r:SYNTHESIZES_SECTION]->(sec:Section) "
                "RETURN s.slug AS s_slug, sec.uri AS sec_uri, r.expected_hash AS expected_hash, "
                "r.drift_detected AS drift_detected, r.last_checked AS last_checked, "
                "r.grounded_heading AS grounded_heading", language="cypher"
            )
            for row in existing_edges:
                s_slug = row.get("s_slug")
                sec_uri = row.get("sec_uri")
                if s_slug and sec_uri:
                    preserved_synth_edges[(s_slug, sec_uri)] = row
                    if row.get("grounded_heading"):
                        doc_part = sec_uri.split("#")[0]
                        preserved_synth_edges[(s_slug, doc_part, row["grounded_heading"].lower().strip())] = row

            existing_synths = client.query(
                "MATCH (s:Synthesis) RETURN s.slug AS slug, s.stale AS stale, s.stale_reason AS stale_reason",
                language="cypher"
            )
            for s_row in existing_synths:
                if s_row.get("stale"):
                    preserved_synth_stale[s_row["slug"]] = (bool(s_row["stale"]), str(s_row.get("stale_reason", "")))

            existing_deltas = client.query("SELECT * FROM SynthesisDelta", language="sql")
            if isinstance(existing_deltas, list):
                preserved_deltas = existing_deltas
        except Exception:
            pass

        print("  [*] Purging legacy records from ArcadeDB...")
        purge_edges = [
            "PROGRESSES_TO", "NEXT_SECTION", "REMEDIES_DILEMMA", "EXTENDS_THEORY", "PRECIPITATES",
            "EMPIRICALLY_GROUNDS", "ORIGINATES_THEORY", "CHAMPIONS_SOLUTION",
            "CRITIQUES_PARADIGM", "OPERATIONALIZES", "AFFILIATED_WITH",
            "INTELLECTUAL_LINEAGE", "AUTHORED_BY", "PUBLISHED_BY",
            "HAS_SECTION", "TAGGED_WITH", "LINKS_TO", "CITES",
            "HAS_GROUNDS", "HAS_WARRANT", "HAS_CLAIM", "HAS_REBUTTAL",
            "HAS_SOLUTION", "HAS_QUALIFIER", "HAS_BACKING", "HAS_DIAGRAM",
            "SYNTHESIZES", "SYNTHESIZES_SECTION"
        ]
        for et in purge_edges:
            try:
                client.execute_command(f"DELETE FROM `{et}`", language="sql")
            except Exception:
                pass
        for vt in ["Concept", "Entity", "Source", "Section", "Tag", "AliasLookup", "Diagram", "Synthesis", "SynthesisDelta"]:
            try:
                client.execute_command(f"DELETE FROM `{vt}`", language="sql")
            except Exception:
                pass

    t0 = time.time()
    total_vertices = 0
    total_edges = 0

    # 1. Discover all markdown files
    print("\n[1/5] Scanning and parsing wiki/ markdown files...")
    all_files: List[Path] = []
    for sub in ["concepts", "entities", "sources", "syntheses"]:
        sub_dir = WIKI_DIR / sub
        if sub_dir.exists():
            all_files.extend(list(sub_dir.glob("*.md")))

    print(f"  → Found {len(all_files)} markdown notes to compile.")

    # Storage arrays
    concepts_batch = []
    entities_batch = []
    sources_batch = []
    syntheses_batch = []
    tags_set: Set[str] = set()
    sections_records: List[Dict[str, Any]] = []
    diagrams_records: List[Dict[str, Any]] = []
    aliases_dict: Dict[str, str] = {}

    # Intra-doc links and relationships to build after vertex ingestion
    doc_meta_map: Dict[str, Dict[str, Any]] = {}  # title -> meta
    doc_body_map: Dict[str, str] = {}             # title -> raw body
    doc_sections_map: Dict[str, List[str]] = {}   # title -> [sec_uri]
    sec_to_doc_map: Dict[str, str] = {}           # sec_uri -> doc_title
    sec_links_to: List[Tuple[str, str]] = []      # (sec_uri, target_title)
    micro_cot_pairs: List[Dict[str, Any]] = []    # (s1_uri, s2_uri, tr_type, warrant, conf)

    for p in all_files:
        try:
            content = p.read_text(encoding="utf-8")
        except Exception:
            continue

        rel_path = str(p.relative_to(VAULT_ROOT))
        fm, body = parse_frontmatter(content)
        title = fm.get("title") or p.stem
        doc_type = fm.get("type") or ("concept" if "concepts" in rel_path else "entity" if "entities" in rel_path else "synthesis" if "syntheses" in rel_path else "source")

        # Filter: Ingest only new syntheses with subtype "thematic_hub"; ignore legacy syntheses
        if doc_type == "synthesis" and fm.get("subtype") != "thematic_hub":
            continue

        doc_body_map[title] = body
        doc_meta_map[title] = {
            "title": title,
            "type": doc_type,
            "subtype": fm.get("subtype", ""),
            "reliability_score": float(fm.get("reliability_score", 1.0)),
            "last_updated": str(fm.get("last_updated", "2026-10-01")),
            "tags": fm.get("tags", []),
            "aliases": fm.get("aliases", []),
            "sources": fm.get("sources", []),
            "path": rel_path,
            "slug": p.stem,
            "stale": bool(fm.get("stale", False)),
            "concepts": fm.get("concepts", []),
            "sections": fm.get("sections", []),
        }

        for t in fm.get("tags", []):
            if isinstance(t, str) and t.strip():
                tags_set.add(t.strip())

        for a in fm.get("aliases", []):
            if isinstance(a, str) and a.strip():
                aliases_dict[a.strip()] = title

        # Vertex JSON preparation
        if doc_type == "concept":
            concepts_batch.append(json.dumps({
                "@type": "vertex",
                "@class": "Concept",
                "title": title,
                "type": "concept",
                "reliability_score": float(fm.get("reliability_score", 1.0)),
                "last_updated": str(fm.get("last_updated", "2026-10-01"))
            }))
        elif doc_type == "entity":
            entities_batch.append(json.dumps({
                "@type": "vertex",
                "@class": "Entity",
                "title": title,
                "subtype": fm.get("subtype", "organization"),
                "reliability_score": float(fm.get("reliability_score", 1.0))
            }))
        elif doc_type == "source":
            sources_batch.append(json.dumps({
                "@type": "vertex",
                "@class": "Source",
                "slug": p.stem,
                "title": title
            }))
        elif doc_type == "synthesis":
            s_slug = p.stem
            is_stale = bool(fm.get("stale", False))
            stale_reason_str = str(fm.get("stale_reason", ""))
            if s_slug in preserved_synth_stale:
                is_stale, stale_reason_str = preserved_synth_stale[s_slug]

            syntheses_batch.append(json.dumps({
                "@type": "vertex",
                "@class": "Synthesis",
                "slug": s_slug,
                "title": title,
                "subtype": fm.get("subtype", "thematic_hub"),
                "last_updated": str(fm.get("last_updated", "2026-10-01")),
                "stale": is_stale,
                "stale_reason": stale_reason_str,
                "reliability_score": float(fm.get("reliability_score", 1.0)),
                "content": body.strip()
            }))

        # Parse Sections
        raw_secs = parse_sections(rel_path, body)
        doc_sec_uris = []
        for s in raw_secs:
            sec_uri = f"{rel_path}#{s['idx']}"
            sec_title = s["title"]
            raw_sec_content = s["content"]

            # Diagram Extraction
            clean_content, sec_diagrams = process_section_diagrams(sec_uri, sec_title, raw_sec_content)
            diagrams_records.extend(sec_diagrams)

            # Step classification & weights
            st, _ = classify_section(title, doc_type, sec_title, clean_content, s["is_lead"])
            tr = map_to_toulmin_role(st, doc_type)
            w, mc, _ = compute_linguistic_weight(clean_content, st)
            sec_hash = hashlib.sha256(clean_content.encode("utf-8")).hexdigest()[:16]

            sec_record = {
                "uri": sec_uri,
                "title": sec_title,
                "display_name": sec_title,
                "path": rel_path,
                "heading_level": s["heading_level"],
                "heading": sec_title,
                "step_type": st,
                "toulmin_role": tr,
                "weight": w,
                "modal_category": mc,
                "content": clean_content[:2048],
                "content_hash": sec_hash,
                "doc_title": title,
                "doc_type": doc_type
            }
            sections_records.append(sec_record)
            doc_sec_uris.append(sec_uri)
            sec_to_doc_map[sec_uri] = title

            # Extract [[Target]] wikilinks
            links = extract_wikilinks(clean_content)
            for target in links:
                sec_links_to.append((sec_uri, target))

        doc_sections_map[title] = doc_sec_uris

        # Build sequential Micro-CoT pairs
        for i in range(len(raw_secs) - 1):
            s1 = raw_secs[i]
            s2 = raw_secs[i + 1]
            u1 = f"{rel_path}#{s1['idx']}"
            u2 = f"{rel_path}#{s2['idx']}"
            st1, _ = classify_section(title, doc_type, s1["title"], s1["content"], s1["is_lead"])
            st2, _ = classify_section(title, doc_type, s2["title"], s2["content"], s2["is_lead"])
            tr_type, warrant, conf = infer_transition_rule(st1, st2)
            micro_cot_pairs.append({
                "s1_uri": u1,
                "s2_uri": u2,
                "transition_type": tr_type,
                "warrant": warrant,
                "confidence": conf,
                "method": "heuristic_ast"
            })

    # 2. Ingest Document Vertices
    print("\n[2/5] Ingesting document & taxonomy vertices into ArcadeDB...")
    res = client.batch_ndjson(concepts_batch)
    total_vertices += res.get("verticesCreated", len(concepts_batch))
    print(f"  [+] Ingested {len(concepts_batch)} Concept vertices ({res.get('elapsedMs', 0)}ms)")

    res = client.batch_ndjson(entities_batch)
    total_vertices += res.get("verticesCreated", len(entities_batch))
    print(f"  [+] Ingested {len(entities_batch)} Entity vertices ({res.get('elapsedMs', 0)}ms)")

    res = client.batch_ndjson(sources_batch)
    total_vertices += res.get("verticesCreated", len(sources_batch))
    print(f"  [+] Ingested {len(sources_batch)} Source vertices ({res.get('elapsedMs', 0)}ms)")

    res = client.batch_ndjson(syntheses_batch)
    total_vertices += res.get("verticesCreated", len(syntheses_batch))
    print(f"  [+] Ingested {len(syntheses_batch)} Synthesis vertices ({res.get('elapsedMs', 0)}ms)")

    tags_batch = [json.dumps({"@type": "vertex", "@class": "Tag", "name": t}) for t in tags_set]
    res = client.batch_ndjson(tags_batch)
    total_vertices += res.get("verticesCreated", len(tags_batch))
    print(f"  [+] Ingested {len(tags_batch)} Tag vertices ({res.get('elapsedMs', 0)}ms)")

    # 3. Ingest Sections & Diagrams
    print(f"\n[3/5] Ingesting {len(sections_records)} Section vertices and {len(diagrams_records)} Diagram vertices...")
    sec_ndjson = []
    batch_size = 400
    for idx, s in enumerate(sections_records, 1):
        item = {
            "@type": "vertex",
            "@class": "Section",
            "uri": s["uri"],
            "title": s["title"],
            "display_name": s["display_name"],
            "path": s["path"],
            "heading_level": s["heading_level"],
            "heading": s["heading"],
            "step_type": s["step_type"],
            "toulmin_role": s["toulmin_role"],
            "weight": s["weight"],
            "modal_category": s["modal_category"],
            "content": s["content"],
            "content_hash": s["content_hash"]
        }
        sec_ndjson.append(json.dumps(item))
        if len(sec_ndjson) >= batch_size:
            res = client.batch_ndjson(sec_ndjson)
            total_vertices += res.get("verticesCreated", len(sec_ndjson))
            sec_ndjson = []

    if sec_ndjson:
        res = client.batch_ndjson(sec_ndjson)
        total_vertices += res.get("verticesCreated", len(sec_ndjson))
    print(f"  [+] Ingested {len(sections_records)} Section vertices (100% clean prose).")

    diag_ndjson = []
    for d in diagrams_records:
        diag_item = {
            "@type": "vertex",
            "@class": "Diagram",
            "id": d["id"],
            "section_uri": d["section_uri"],
            "title": d["title"],
            "diagram_type": d["diagram_type"],
            "direction": d["direction"],
            "raw_code": d["raw_code"],
            "node_labels": d["node_labels"],
            "semantic_transcript": d["semantic_transcript"],
            "order_idx": d["order_idx"],
            "created_at": d.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S")
        }
        diag_ndjson.append(json.dumps(diag_item))
        if len(diag_ndjson) >= batch_size:
            res = client.batch_ndjson(diag_ndjson)
            total_vertices += res.get("verticesCreated", len(diag_ndjson))
            diag_ndjson = []
    if diag_ndjson:
        res = client.batch_ndjson(diag_ndjson)
        total_vertices += res.get("verticesCreated", len(diag_ndjson))
    print(f"  [+] Ingested {len(diagrams_records)} decoupled Diagram vertices.")

    # Ingest AliasLookup
    alias_items = list(aliases_dict.items())
    for i in range(0, len(alias_items), 100):
        chunk = alias_items[i:i + 100]
        for a, t in chunk:
            try:
                client.execute_command(
                    f"INSERT INTO AliasLookup SET alias = '{a.replace('\'', '\\\'')}', canonical_title = '{t.replace('\'', '\\\'')}'",
                    language="sql"
                )
            except Exception:
                pass
    print(f"  [+] Ingested {len(alias_items)} AliasLookup mappings.")

    # 4. Cache RIDs for Sub-Millisecond Edge Generation
    print("\n[4/5] Building in-memory RID resolution maps...")
    c_rids = client.query("SELECT @rid, title FROM Concept", language="sql")
    concept_map = {row["title"]: row["@rid"] for row in c_rids if "title" in row}

    e_rids = client.query("SELECT @rid, title FROM Entity", language="sql")
    entity_map = {row["title"]: row["@rid"] for row in e_rids if "title" in row}

    s_rids = client.query("SELECT @rid, slug, title FROM Source", language="sql")
    source_map = {}
    for row in s_rids:
        if "slug" in row:
            source_map[row["slug"]] = row["@rid"]
        if "title" in row:
            source_map[row["title"]] = row["@rid"]

    synth_rids = client.query("SELECT @rid, slug, title FROM Synthesis", language="sql")
    synthesis_map = {}
    for row in synth_rids:
        if "slug" in row:
            synthesis_map[row["slug"]] = row["@rid"]
        if "title" in row:
            synthesis_map[row["title"]] = row["@rid"]

    t_rids = client.query("SELECT @rid, name FROM Tag", language="sql")
    tag_map = {row["name"]: row["@rid"] for row in t_rids if "name" in row}

    sec_rids = client.query("SELECT @rid, uri FROM Section", language="sql")
    section_map = {row["uri"]: row["@rid"] for row in sec_rids if "uri" in row}

    diag_rids = client.query("SELECT @rid, id FROM Diagram", language="sql")
    diagram_map = {row["id"]: row["@rid"] for row in diag_rids if "id" in row}

    def resolve_target_rid(key: str) -> Optional[str]:
        # Disambiguate via alias lookup
        canon = aliases_dict.get(key, key)
        return concept_map.get(canon) or entity_map.get(canon) or source_map.get(canon) or synthesis_map.get(canon)

    # 5. Connect Typed Graph Edges
    print("\n[5/5] Connecting graph relationships & Toulmin reasoning edges...")

    # A. HAS_SECTION & Specialized Toulmin edges
    toulmin_edge_map = {
        "GROUNDS": "HAS_GROUNDS",
        "CLAIM": "HAS_CLAIM",
        "WARRANT": "HAS_WARRANT",
        "REBUTTAL": "HAS_REBUTTAL",
        "SOLUTION_WARRANT": "HAS_SOLUTION",
        "QUALIFIER": "HAS_QUALIFIER",
        "BACKING": "HAS_BACKING",
    }
    has_edge_batch = []
    has_count = 0
    toulmin_counts: Dict[str, int] = {}

    for sec in sections_records:
        doc_rid = concept_map.get(sec["doc_title"]) or entity_map.get(sec["doc_title"]) or source_map.get(sec["doc_title"]) or synthesis_map.get(sec["doc_title"])
        s_rid = section_map.get(sec["uri"])
        if doc_rid and s_rid:
            has_edge_batch.append(json.dumps({
                "@type": "edge", "@class": "HAS_SECTION",
                "@from": doc_rid, "@to": s_rid
            }))
            has_count += 1

            if sec["doc_type"] == "concept" and sec["toulmin_role"] in toulmin_edge_map:
                t_cls = toulmin_edge_map[sec["toulmin_role"]]
                t_data: Dict[str, Any] = {
                    "@type": "edge", "@class": t_cls,
                    "@from": doc_rid, "@to": s_rid,
                    "weight": sec["weight"]
                }
                if t_cls == "HAS_REBUTTAL":
                    t_data["signed_weight"] = round(-1.0 * sec["weight"], 3)
                has_edge_batch.append(json.dumps(t_data))
                toulmin_counts[t_cls] = toulmin_counts.get(t_cls, 0) + 1

            if len(has_edge_batch) >= 500:
                client.batch_ndjson(has_edge_batch)
                has_edge_batch = []

    if has_edge_batch:
        client.batch_ndjson(has_edge_batch)
    total_edges += has_count + sum(toulmin_counts.values())
    print(f"  [+] Linked {has_count} HAS_SECTION edges and {sum(toulmin_counts.values())} Toulmin edges.")

    # B. HAS_DIAGRAM edges
    diag_edge_batch = []
    diag_edge_count = 0
    for d in diagrams_records:
        s_rid = section_map.get(d["section_uri"])
        d_rid = diagram_map.get(d["id"])
        if s_rid and d_rid:
            diag_edge_batch.append(json.dumps({
                "@type": "edge", "@class": "HAS_DIAGRAM",
                "@from": s_rid, "@to": d_rid,
                "order_idx": d["order_idx"]
            }))
            diag_edge_count += 1
            if len(diag_edge_batch) >= 500:
                client.batch_ndjson(diag_edge_batch)
                diag_edge_batch = []
    if diag_edge_batch:
        client.batch_ndjson(diag_edge_batch)
    total_edges += diag_edge_count
    print(f"  [+] Linked {diag_edge_count} HAS_DIAGRAM edges.")

    # C. NEXT_SECTION and PROGRESSES_TO edges
    seq_edge_batch = []
    seq_count = 0
    cot_count = 0
    for pair in micro_cot_pairs:
        s1_rid = section_map.get(pair["s1_uri"])
        s2_rid = section_map.get(pair["s2_uri"])
        if s1_rid and s2_rid:
            seq_edge_batch.append(json.dumps({
                "@type": "edge", "@class": "NEXT_SECTION",
                "@from": s1_rid, "@to": s2_rid
            }))
            seq_count += 1
            seq_edge_batch.append(json.dumps({
                "@type": "edge", "@class": "PROGRESSES_TO",
                "@from": s1_rid, "@to": s2_rid,
                "transition_type": pair["transition_type"],
                "warrant": pair["warrant"],
                "confidence": pair["confidence"],
                "method": pair["method"]
            }))
            cot_count += 1
            if len(seq_edge_batch) >= 500:
                client.batch_ndjson(seq_edge_batch)
                seq_edge_batch = []
    if seq_edge_batch:
        client.batch_ndjson(seq_edge_batch)
    total_edges += seq_count + cot_count
    print(f"  [+] Linked {seq_count} NEXT_SECTION and {cot_count} PROGRESSES_TO CoT edges.")

    # D. LINKS_TO & Macro-CoT Handshakes
    link_edge_batch = []
    macro_edge_batch = []
    link_count = 0
    macro_count = 0

    for s_uri, tgt_title in sec_links_to:
        s_rid = section_map.get(s_uri)
        tgt_rid = resolve_target_rid(tgt_title)
        if s_rid and tgt_rid:
            link_edge_batch.append(json.dumps({
                "@type": "edge", "@class": "LINKS_TO",
                "@from": s_rid, "@to": tgt_rid
            }))
            link_count += 1

            # Check for Macro-CoT relations
            src_doc_title = sec_to_doc_map.get(s_uri)
            if src_doc_title and src_doc_title != tgt_title:
                src_doc_rid = concept_map.get(src_doc_title)
                tgt_doc_rid = concept_map.get(tgt_title)
                if src_doc_rid and tgt_doc_rid:
                    # Look up section step_type
                    sec_meta = next((s for s in sections_records if s["uri"] == s_uri), None)
                    if sec_meta:
                        st = sec_meta["step_type"]
                        if st == "PRESCRIPTIVE_SOLUTION":
                            macro_edge_batch.append(json.dumps({
                                "@type": "edge", "@class": "REMEDIES_DILEMMA",
                                "@from": src_doc_rid, "@to": tgt_doc_rid,
                                "weight": sec_meta["weight"]
                            }))
                            macro_count += 1
                        elif st == "MECHANISTIC_DEEPEN":
                            macro_edge_batch.append(json.dumps({
                                "@type": "edge", "@class": "EXTENDS_THEORY",
                                "@from": src_doc_rid, "@to": tgt_doc_rid,
                                "weight": sec_meta["weight"]
                            }))
                            macro_count += 1
                        elif st in ("MANIFESTATION_TRAP", "DILEMMA_PROBLEM"):
                            macro_edge_batch.append(json.dumps({
                                "@type": "edge", "@class": "PRECIPITATES",
                                "@from": src_doc_rid, "@to": tgt_doc_rid,
                                "weight": sec_meta["weight"]
                            }))
                            macro_count += 1

            if len(link_edge_batch) >= 500:
                client.batch_ndjson(link_edge_batch)
                link_edge_batch = []
            if len(macro_edge_batch) >= 500:
                client.batch_ndjson(macro_edge_batch)
                macro_edge_batch = []

    if link_edge_batch:
        client.batch_ndjson(link_edge_batch)
    if macro_edge_batch:
        client.batch_ndjson(macro_edge_batch)
    total_edges += link_count + macro_count
    print(f"  [+] Linked {link_count} LINKS_TO edges and {macro_count} Macro-CoT edges.")

    # E. TAGGED_WITH edges (Document -> Tag Taxonomy)
    tag_edge_batch = []
    tag_count = 0
    for title, meta in doc_meta_map.items():
        doc_rid = concept_map.get(title) or entity_map.get(title) or source_map.get(title) or synthesis_map.get(title)
        if not doc_rid:
            continue
        for t in meta.get("tags", []):
            if not isinstance(t, str):
                continue
            clean_tag = t.strip()
            t_rid = tag_map.get(clean_tag)
            if t_rid:
                tag_edge_batch.append(json.dumps({
                    "@type": "edge", "@class": "TAGGED_WITH",
                    "@from": doc_rid, "@to": t_rid
                }))
                tag_count += 1
                if len(tag_edge_batch) >= 500:
                    client.batch_ndjson(tag_edge_batch)
                    tag_edge_batch = []
    if tag_edge_batch:
        client.batch_ndjson(tag_edge_batch)
    total_edges += tag_count
    print(f"  [+] Linked {tag_count} TAGGED_WITH edges.")

    # F. CITES macro citation edges (Document -> Document)
    cites_counts = defaultdict(int)
    for s_uri, tgt_title in sec_links_to:
        src_title = sec_to_doc_map.get(s_uri)
        tgt_canon = aliases_dict.get(tgt_title, tgt_title)
        if src_title and tgt_canon and src_title != tgt_canon:
            src_rid = resolve_target_rid(src_title)
            tgt_rid = resolve_target_rid(tgt_canon)
            if src_rid and tgt_rid:
                cites_counts[(src_rid, tgt_rid)] += 1

    cites_batch = []
    cites_count = 0
    for (src_rid, tgt_rid), w in cites_counts.items():
        cites_batch.append(json.dumps({
            "@type": "edge", "@class": "CITES",
            "@from": src_rid, "@to": tgt_rid,
            "weight": float(w)
        }))
        cites_count += 1
        if len(cites_batch) >= 500:
            client.batch_ndjson(cites_batch)
            cites_batch = []
    if cites_batch:
        client.batch_ndjson(cites_batch)
    total_edges += cites_count
    print(f"  [+] Linked {cites_count} CITES macro citation edges.")

    # G. Literature Grounding: EMPIRICALLY_GROUNDS, AUTHORED_BY, PUBLISHED_BY
    lit_edge_batch = []
    emp_count = 0
    auth_count = 0
    pub_count = 0
    emp_seen = set()

    for title, meta in doc_meta_map.items():
        d_type = meta["type"]
        doc_rid = concept_map.get(title) or entity_map.get(title)

        # 1. Concept/Entity frontmatter sources: ["[[sources/slug]]"]
        if doc_rid and d_type in ("concept", "entity"):
            for s in meta.get("sources", []):
                s_clean = re.sub(r'\[\[(.*?)\]\]', r'\1', str(s)).split('|')[0].strip()
                s_clean = re.sub(r'^(wiki/)?sources/', '', s_clean).replace('.md', '')
                src_rid = source_map.get(s_clean) or resolve_target_rid(s_clean)
                if src_rid and (src_rid, doc_rid) not in emp_seen:
                    emp_seen.add((src_rid, doc_rid))
                    lit_edge_batch.append(json.dumps({
                        "@type": "edge", "@class": "EMPIRICALLY_GROUNDS",
                        "@from": src_rid, "@to": doc_rid,
                        "weight": 1.0,
                        "warrant": f"Provides primary empirical grounding and citations for {title}"
                    }))
                    emp_count += 1

        # 2. Source note links to Concept (EMPIRICALLY_GROUNDS) and Entities (AUTHORED_BY / PUBLISHED_BY)
        if d_type == "source":
            src_rid = source_map.get(title) or source_map.get(meta.get("slug", ""))
            if not src_rid:
                continue
            src_secs = doc_sections_map.get(title, [])
            for s_uri in src_secs:
                for s_uri_link, tgt_raw in sec_links_to:
                    if s_uri_link != s_uri:
                        continue
                    tgt_canon = aliases_dict.get(tgt_raw, tgt_raw)
                    # Target is Concept -> EMPIRICALLY_GROUNDS
                    c_rid = concept_map.get(tgt_canon)
                    if c_rid and (src_rid, c_rid) not in emp_seen:
                        emp_seen.add((src_rid, c_rid))
                        lit_edge_batch.append(json.dumps({
                            "@type": "edge", "@class": "EMPIRICALLY_GROUNDS",
                            "@from": src_rid, "@to": c_rid,
                            "weight": 1.0,
                            "warrant": f"{title} provides primary empirical grounding for {tgt_canon}"
                        }))
                        emp_count += 1
                    # Target is Entity -> AUTHORED_BY (researcher) or PUBLISHED_BY (organization)
                    e_meta = doc_meta_map.get(tgt_canon)
                    if e_meta and e_meta["type"] == "entity":
                        e_rid = entity_map.get(tgt_canon)
                        if e_rid:
                            st = e_meta.get("subtype", "")
                            if st == "researcher" and (src_rid, e_rid, "AUTHORED_BY") not in emp_seen:
                                emp_seen.add((src_rid, e_rid, "AUTHORED_BY"))
                                lit_edge_batch.append(json.dumps({
                                    "@type": "edge", "@class": "AUTHORED_BY",
                                    "@from": src_rid, "@to": e_rid,
                                    "weight": 1.0,
                                    "warrant": f"{title} is authored or researched by {tgt_canon}"
                                }))
                                auth_count += 1
                            elif st in ("organization", "platform") and (src_rid, e_rid, "PUBLISHED_BY") not in emp_seen:
                                emp_seen.add((src_rid, e_rid, "PUBLISHED_BY"))
                                lit_edge_batch.append(json.dumps({
                                    "@type": "edge", "@class": "PUBLISHED_BY",
                                    "@from": src_rid, "@to": e_rid,
                                    "weight": 1.0,
                                    "warrant": f"{title} is published, hosted, or commissioned by {tgt_canon}"
                                }))
                                pub_count += 1

        if len(lit_edge_batch) >= 500:
            client.batch_ndjson(lit_edge_batch)
            lit_edge_batch = []

    if lit_edge_batch:
        client.batch_ndjson(lit_edge_batch)
    total_edges += emp_count + auth_count + pub_count
    print(f"  [+] Linked {emp_count} EMPIRICALLY_GROUNDS, {auth_count} AUTHORED_BY, and {pub_count} PUBLISHED_BY edges.")

    # H. Entity Agency Handshakes: ORIGINATES_THEORY, CHAMPIONS_SOLUTION, CRITIQUES_PARADIGM, OPERATIONALIZES, AFFILIATED_WITH, INTELLECTUAL_LINEAGE
    agency_edge_batch = []
    agency_counts = defaultdict(int)
    agency_seen = set()

    bullet_specs = [
        (r'\*\*(?:Originated Concepts|Core Theories)\*\*:(.*?)(?=\n\s*-\s*\*\*|\Z)', 'ORIGINATES_THEORY', 'originated foundational theory'),
        (r'\*\*(?:Contested Theories|Dialectical Critiques|Contested Paradigms)\*\*:(.*?)(?=\n\s*-\s*\*\*|\Z)', 'CRITIQUES_PARADIGM', 'dialectically critiques'),
        (r'\*\*(?:Championed Methodologies|Prescribed Solutions)\*\*:(.*?)(?=\n\s*-\s*\*\*|\Z)', 'CHAMPIONS_SOLUTION', 'champions prescriptive solution'),
        (r'\*\*(?:Operationalized Concepts|Engineered Products & Tools)\*\*:(.*?)(?=\n\s*-\s*\*\*|\Z)', 'OPERATIONALIZES', 'operationalizes'),
        (r'\*\*(?:Collaborators & Lineage|Intellectual Lineage)\*\*:(.*?)(?=\n\s*-\s*\*\*|\Z)', 'INTELLECTUAL_LINEAGE', 'intellectual lineage with'),
        (r'\*\*(?:Institutional Affiliates|Governing Organizations|Strategic Supporters|Institutional Context)\*\*:(.*?)(?=\n\s*-\s*\*\*|\Z)', 'AFFILIATED_WITH', 'affiliated with'),
    ]

    for title, meta in doc_meta_map.items():
        if meta["type"] != "entity":
            continue
        e_rid = entity_map.get(title)
        if not e_rid:
            continue
        body = doc_body_map.get(title, "")
        subtype = meta.get("subtype", "")

        # 1. Structured sub-bullets in Related Primitives
        for pat, rel_type, warrant_desc in bullet_specs:
            for chunk in re.findall(pat, body, re.DOTALL | re.IGNORECASE):
                targets = extract_wikilinks(chunk)
                for t in targets:
                    tgt_canon = aliases_dict.get(t, t)
                    tgt_rid = resolve_target_rid(tgt_canon)
                    if tgt_rid and tgt_rid != e_rid and (e_rid, tgt_rid, rel_type) not in agency_seen:
                        agency_seen.add((e_rid, tgt_rid, rel_type))
                        agency_edge_batch.append(json.dumps({
                            "@type": "edge", "@class": rel_type,
                            "@from": e_rid, "@to": tgt_rid,
                            "weight": 1.0,
                            "warrant": f"{title} {warrant_desc} {tgt_canon}"
                        }))
                        agency_counts[rel_type] += 1

        # 2. Section-level AST inferences
        for sec in sections_records:
            if sec["doc_title"] != title:
                continue
            sec_h_lower = sec["heading"].lower()
            st = sec["step_type"]

            for s_uri, tgt_raw in sec_links_to:
                if s_uri != sec["uri"]:
                    continue
                tgt_canon = aliases_dict.get(tgt_raw, tgt_raw)
                tgt_doc_meta = doc_meta_map.get(tgt_canon)
                tgt_rid = resolve_target_rid(tgt_canon)
                if not tgt_rid or tgt_rid == e_rid:
                    continue

                inferred_rel = None
                inferred_warrant = ""

                # Target is Concept
                if tgt_canon in concept_map:
                    if subtype == "researcher" and (st in ("EPISTEMIC_ANCHOR", "CANONICAL_MODEL") or re.search(r'epistemic role|core thesis|intellectual contribution|canonical formulation|methodological model|theoretical foundation', sec_h_lower)):
                        inferred_rel = "ORIGINATES_THEORY"
                        inferred_warrant = f"{title} originated foundational theory {tgt_canon}"
                    elif st in ("PEDAGOGICAL_DEPLOYMENT", "STRATEGIC_ANALOGUE", "PRESCRIPTIVE_SOLUTION") or re.search(r'pedagogical deployment|strategic analogue|benchmark|intervention|safeguard|mitigat|remedy|solution|policy|advocacy', sec_h_lower):
                        inferred_rel = "CHAMPIONS_SOLUTION"
                        inferred_warrant = f"{title} champions prescriptive solution {tgt_canon}"
                    elif st in ("DIALECTICAL_CRITIQUE", "SYSTEMIC_FAILURE_MODE", "MANIFESTATION_TRAP") or re.search(r'contested paradigm|dialectical critique|critique|pathology|bottleneck|dilemma|trap|failure', sec_h_lower):
                        inferred_rel = "CRITIQUES_PARADIGM"
                        inferred_warrant = f"{title} dialectically critiques {tgt_canon}"
                    elif subtype in ("software", "organization", "platform") and (st in ("TECHNICAL_ARCHITECTURE", "ORGANIZATIONAL_ARCHITECTURE", "INTEGRATION_TOPOLOGY") or re.search(r'mechanistic pipeline|execution model|operational architecture|integration topology|capabilities', sec_h_lower)):
                        inferred_rel = "OPERATIONALIZES"
                        inferred_warrant = f"{title} operationalizes {tgt_canon}"

                # Target is Entity
                elif tgt_doc_meta and tgt_doc_meta["type"] == "entity":
                    tgt_st = tgt_doc_meta.get("subtype", "")
                    if subtype == "researcher" and tgt_st == "organization":
                        inferred_rel = "AFFILIATED_WITH"
                        inferred_warrant = f"{title} maintains institutional affiliation with {tgt_canon}"
                    elif re.search(r'affiliation|governance|coalition|ecosystem|career|institution|partner', sec_h_lower):
                        inferred_rel = "AFFILIATED_WITH"
                        inferred_warrant = f"{title} affiliated with {tgt_canon}"
                    elif subtype == "researcher" and tgt_st == "researcher" and (st == "INTELLECTUAL_LINEAGE" or re.search(r'intellectual lineage|lineage|theoretical foundation|predecessor|mentor|influence', sec_h_lower)):
                        inferred_rel = "INTELLECTUAL_LINEAGE"
                        inferred_warrant = f"{title} shares intellectual lineage with {tgt_canon}"

                if inferred_rel and (e_rid, tgt_rid, inferred_rel) not in agency_seen:
                    agency_seen.add((e_rid, tgt_rid, inferred_rel))
                    agency_edge_batch.append(json.dumps({
                        "@type": "edge", "@class": inferred_rel,
                        "@from": e_rid, "@to": tgt_rid,
                        "weight": float(sec.get("weight", 1.0)),
                        "warrant": inferred_warrant
                    }))
                    agency_counts[inferred_rel] += 1

        if len(agency_edge_batch) >= 500:
            client.batch_ndjson(agency_edge_batch)
            agency_edge_batch = []

    if agency_edge_batch:
        client.batch_ndjson(agency_edge_batch)
    total_edges += sum(agency_counts.values())
    print(f"  [+] Linked {sum(agency_counts.values())} Entity Agency edges ({dict(agency_counts)}).")

    # I. Synthesis Links (SYNTHESIZES to Concept, SYNTHESIZES_SECTION to Section)
    synth_concept_batch = []
    synth_section_batch = []
    synth_c_count = 0
    synth_s_count = 0

    for title, meta in doc_meta_map.items():
        if meta["type"] != "synthesis":
            continue
        s_rid = synthesis_map.get(title) or synthesis_map.get(meta.get("slug", ""))
        if not s_rid:
            continue

        # 1. SYNTHESIZES -> Concept
        for raw_c in meta.get("concepts", []):
            clean_c = re.sub(r'\[\[(.*?)\]\]', r'\1', str(raw_c)).strip()
            clean_c = re.sub(r'^(wiki/)?(concepts|entities)/', '', clean_c).strip()
            clean_c = clean_c.split("|")[0].strip()
            c_rid = concept_map.get(clean_c) or resolve_target_rid(clean_c)
            if c_rid:
                synth_concept_batch.append(json.dumps({
                    "@type": "edge", "@class": "SYNTHESIZES",
                    "@from": s_rid, "@to": c_rid,
                    "weight": 1.0
                }))
                synth_c_count += 1

        # 2. SYNTHESIZES_SECTION -> Section
        for raw_sec in meta.get("sections", []):
            clean_sec = re.sub(r'\[\[(.*?)\]\]', r'\1', str(raw_sec)).strip()
            clean_sec = re.sub(r'^(wiki/)?(concepts|entities)/', '', clean_sec).strip()
            if "#" in clean_sec:
                doc_name, heading_ref = clean_sec.split("#", 1)
                doc_name = doc_name.strip()
                heading_ref = heading_ref.strip()
            else:
                doc_name = clean_sec.strip()
                heading_ref = ""

            doc_name_canon = aliases_dict.get(doc_name, doc_name)

            matched_sec = None
            for sec in sections_records:
                if sec["doc_title"] == doc_name or sec["doc_title"] == doc_name_canon:
                    if not heading_ref:
                        matched_sec = sec
                        break
                    sec_h = sec["heading"].strip()
                    if (heading_ref.lower() == sec_h.lower() or
                        heading_ref.lower() in sec_h.lower() or
                        sec_h.lower() in heading_ref.lower() or
                        (re.match(r'^\d+\.', heading_ref) and sec_h.startswith(heading_ref.split()[0]))):
                        matched_sec = sec
                        break

            if matched_sec:
                sec_rid = section_map.get(matched_sec["uri"])
                if sec_rid:
                    s_slug = meta.get("slug", title)
                    # Check if an expected_hash was previously anchored in ArcadeDB
                    prev_edge = (
                        preserved_synth_edges.get((s_slug, matched_sec["uri"])) or
                        preserved_synth_edges.get((s_slug, matched_sec["doc_title"], matched_sec["heading"].lower().strip()))
                    )
                    if prev_edge and prev_edge.get("expected_hash"):
                        expected_hash = prev_edge["expected_hash"]
                        drift_detected = bool(prev_edge.get("drift_detected", False))
                        last_checked = prev_edge.get("last_checked", time.strftime("%Y-%m-%dT%H:%M:%SZ"))
                    else:
                        expected_hash = matched_sec.get("content_hash", "")
                        drift_detected = False
                        last_checked = time.strftime("%Y-%m-%dT%H:%M:%SZ")

                    synth_section_batch.append(json.dumps({
                        "@type": "edge", "@class": "SYNTHESIZES_SECTION",
                        "@from": s_rid, "@to": sec_rid,
                        "grounded_heading": matched_sec["heading"],
                        "toulmin_role": matched_sec["toulmin_role"],
                        "step_type": matched_sec["step_type"],
                        "weight": matched_sec["weight"],
                        "expected_hash": expected_hash,
                        "drift_detected": drift_detected,
                        "last_checked": last_checked
                    }))
                    synth_s_count += 1

    if synth_concept_batch:
        client.batch_ndjson(synth_concept_batch)
    if synth_section_batch:
        client.batch_ndjson(synth_section_batch)

    if preserved_deltas:
        for d in preserved_deltas:
            d_clean = {k: v for k, v in d.items() if not k.startswith("@")}
            try:
                client.execute_command(f"INSERT INTO SynthesisDelta CONTENT {json.dumps(d_clean)}", language="sql")
            except Exception as e:
                print(f"  [!] Warning: Failed to restore SynthesisDelta: {e}")
    total_edges += synth_c_count + synth_s_count
    print(f"  [+] Linked {synth_c_count} SYNTHESIZES edges and {synth_s_count} SYNTHESIZES_SECTION edges.")

    elapsed = time.time() - t0
    print(f"\n[✓] Ingestion complete in {elapsed:.2f}s: {total_vertices} vertices, {total_edges} edges.")

    # 6. Post-Sync Native In-Engine Embeddings & Graph OLAP (Zero Ollama)
    if not skip_olap:
        print("\n[*] Generating native in-engine embeddings via algo.fastrp (Zero Ollama)...")
        try:
            # Ensure JVector index exists
            client.execute_command(
                'CREATE INDEX IF NOT EXISTS ON Section (embedding) LSM_VECTOR METADATA {"dimensions": 768, "similarity": "COSINE"}',
                language="sql"
            )
            fastrp_cypher = """
            CALL algo.fastrp({
              dimensions: 768,
              iterations: 4,
              normalization: -0.5,
              selfInfluence: 0.1,
              direction: 'BOTH'
            })
            YIELD node, embedding
            WITH toString(node) AS rid_str, embedding
            MATCH (n) WHERE elementId(n) = rid_str
            SET n.embedding = embedding
            RETURN count(n) AS total_embedded
            """
            res = client.execute_command(fastrp_cypher, language="cypher")
            total_emb = res[0].get("total_embedded", 0) if res else 0
            print(f"  [✓] FastRP generated native embeddings across {total_emb} vertices directly in-engine.")
        except Exception as e:
            print(f"  [!] Note on FastRP embeddings: {e}")

        print("\n[*] Executing native in-engine Graph OLAP analytics...")
        try:
            client.execute_command(
                """
                CALL algo.pagerank({dampingFactor: 0.85, maxIterations: 20, weightProperty: 'weight'})
                YIELD node, score
                WITH toString(node) AS rid_str, score
                MATCH (n) WHERE elementId(n) = rid_str
                SET n.pagerank = score
                """,
                language="cypher"
            )
            print("  [✓] Weighted PageRank materialized in ArcadeDB.")
        except Exception as e:
            print(f"  [!] Note on PageRank: {e}")

        try:
            client.execute_command(
                """
                CALL algo.betweenness()
                YIELD node, score
                WITH toString(node) AS rid_str, score
                MATCH (n) WHERE elementId(n) = rid_str
                SET n.betweenness = score
                """,
                language="cypher"
            )
            print("  [✓] Betweenness centrality materialized in ArcadeDB.")
        except Exception as e:
            print(f"  [!] Note on Betweenness: {e}")

        try:
            client.execute_command(
                """
                CALL algo.louvain()
                YIELD node, communityId
                WITH toString(node) AS rid_str, communityId
                MATCH (n) WHERE elementId(n) = rid_str
                SET n.community = communityId
                """,
                language="cypher"
            )
            print("  [✓] Louvain communities materialized in ArcadeDB.")
        except Exception as e:
            print(f"  [!] Note on Louvain: {e}")


def main():
    parser = argparse.ArgumentParser(description="Direct Markdown-to-ArcadeDB Autonomous Pipeline")
    parser.add_argument("--purge", action="store_true", help="Purge existing records before fresh ingestion")
    parser.add_argument("--skip-olap", action="store_true", help="Skip post-ingestion in-engine Graph OLAP")
    args = parser.parse_args()

    client = ArcadeDBClient()
    run_direct_ingestion(client, purge=args.purge, skip_olap=args.skip_olap)


if __name__ == "__main__":
    main()
