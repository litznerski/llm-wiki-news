#!/usr/bin/env python3
"""
scripts/ingest_to_arcadedb.py
Autonomous, direct Markdown-to-ArcadeDB compilation pipeline for the Sudan News & OSINT Knowledge Graph.
  1. AST parsing of wiki/ events, actors, locations, themes, timelines, sources, and syntheses.
  2. Two-Phase Ingestion Gating: Skips wiki/sources/ notes where status: "draft" or compiled: false.
  3. Diagram extraction & decoupling into ArcadeDB's 'Diagram' vertex collection.
  4. Sudan News 6-stage Micro-CoT classification & Macro-CoT 5W1H/GRaSP edge extraction.
  5. Idempotent upsert / batch NDJSON ingestion into ArcadeDB (`news`) via /api/v1/batch/news.
  6. In-engine Graph OLAP execution (algo.fastrp 768-d embeddings, PageRank, Louvain, Betweenness).

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
from collections import defaultdict
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

ARCADEDB_URL = os.getenv("ARCADEDB_URL", "http://localhost:2481")
ARCADEDB_DATABASE = os.getenv("ARCADEDB_DATABASE", "news")
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

    def execute_command(self, command: str, language: str = "sql", params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/api/v1/command/{self.database}"
        body_dict: Dict[str, Any] = {"command": command, "language": language}
        if params:
            body_dict["params"] = params
        payload = json.dumps(body_dict).encode("utf-8")
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
            flow_summary = "Visual conflict intelligence diagram"

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
# 2. Linguistic Weight & Sudan News Section Classification
# ==============================================================================

def _strip_markdown(text: str) -> str:
    text = re.sub(r'```mermaid.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'\[\[.*?\]\]', '', text)
    text = re.sub(r'uri:wiki/.*', '', text)
    text = re.sub(r'> \[!.*?\].*?\n', '', text)
    return text


MODAL_PATTERNS = [
    (r'\b(confirmed|verified|corroborated|definitively|satellite imagery confirms|geolocated)\b', 1.0,  "CONFIRMED"),
    (r'\b(probable|reportedly|witnesses stated|multiple sources|consistently)\b',                0.85, "PROBABLE"),
    (r'\b(alleged|claimed|accused|attributed to|stated that)\b',                                 0.65, "ALLEGED"),
    (r'\b(disputed|contested|conflicting reports|contradictory|unverified)\b',                   0.45, "DISPUTED"),
    (r'\b(denied|rejected|debunked|fabricated|false)\b',                                         0.25, "DENIED_OR_DEBUNKED"),
]

STEP_TYPE_FLOOR = {
    "EVENT_ANCHOR":        0.85,
    "ACTOR_ANCHOR":        0.85,
    "LOCATION_ANCHOR":     0.85,
    "DEFINITIONAL_ANCHOR": 0.80,
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
        raw = STEP_TYPE_FLOOR.get(step_type, 0.65)
        return round(raw, 3), "NEUTRAL", []

    freq_weighted = weighted_sum / hit_count_total
    floor = STEP_TYPE_FLOOR.get(step_type, 0.0)
    raw = max(floor, round(freq_weighted, 3))
    return raw, best_cat, matched[:5]


def map_to_toulmin_role(step_type: str, doc_type: str = "event") -> str:
    mapping = {
        "EVENT_ANCHOR": "GROUNDS",
        "CHRONOLOGICAL_MECHANICS": "WARRANT",
        "CAUSAL_MOTIVES": "CLAIM",
        "IMPACT_ASSESSMENT": "SOLUTION_WARRANT",
        "CONTRADICTION_MATRIX": "REBUTTAL",
        "ACTOR_ANCHOR": "GROUNDS",
        "COMMAND_LINEAGE": "WARRANT",
        "STRATEGIC_DOCTRINE": "CLAIM",
        "ALLIANCE_NETWORK": "QUALIFIER",
        "EVENT_FOOTPRINT": "BACKING",
        "LOCATION_ANCHOR": "GROUNDS",
        "TERRITORIAL_CONTROL": "CLAIM",
        "INFRASTRUCTURE_LOGISTICS": "WARRANT",
        "HUMANITARIAN_STATUS": "REBUTTAL",
        "EVENT_LOG": "BACKING",
        "DEFINITIONAL_ANCHOR": "GROUNDS",
        "MECHANISTIC_DEEPEN": "WARRANT",
        "MANIFESTATION_TRAP": "REBUTTAL",
        "EMPIRICAL_BOUNDARY": "QUALIFIER",
        "CITATION_ANCHOR": "GROUNDS",
        "VERBATIM_EVIDENCE": "WARRANT",
        "FORENSIC_GROUNDING": "CLAIM",
        "TIMELINE_ANCHOR": "GROUNDS",
        "CHRONOLOGICAL_LEDGER": "WARRANT",
        "CAUSAL_ESCALATION": "CLAIM",
        "CUMULATIVE_TELEMETRY": "BACKING",
        "SYNTHESIS_CATALOG": "BACKING",
    }
    return mapping.get(step_type, "GROUNDS")


def classify_section(doc_title: str, doc_type: str, heading_text: str, content: str, is_lead: bool) -> Tuple[str, List[str]]:
    h_lower = (heading_text or "").lower().strip()

    if is_lead:
        if doc_type == "event":
            return "EVENT_ANCHOR", ["EventAnchor", "Summary"]
        if doc_type == "actor":
            return "ACTOR_ANCHOR", ["ActorAnchor", "Summary"]
        if doc_type == "location":
            return "LOCATION_ANCHOR", ["LocationAnchor", "Summary"]
        if doc_type == "citation":
            return "CITATION_ANCHOR", ["CitationAnchor", "Summary"]
        if doc_type == "timeline":
            return "TIMELINE_ANCHOR", ["TimelineAnchor", "Summary"]
        return "DEFINITIONAL_ANCHOR", ["DefinitionalAnchor", "Summary"]

    if re.search(r"related primitives|related notes|synthesis catalog", h_lower):
        return "SYNTHESIS_CATALOG", ["SynthesisCatalog"]

    if doc_type == "event":
        if re.search(r"1[\.\:]|event anchor|5w1h", h_lower):
            return "EVENT_ANCHOR", ["EventAnchor"]
        if re.search(r"2[\.\:]|chronological|tactical", h_lower):
            return "CHRONOLOGICAL_MECHANICS", ["ChronologicalMechanics"]
        if re.search(r"3[\.\:]|causal|motive|why", h_lower):
            return "CAUSAL_MOTIVES", ["CausalMotives"]
        if re.search(r"4[\.\:]|humanitarian|impact|territorial", h_lower):
            return "IMPACT_ASSESSMENT", ["ImpactAssessment"]
        if re.search(r"5[\.\:]|competing|narrative|contradiction|attribution", h_lower):
            return "CONTRADICTION_MATRIX", ["ContradictionMatrix"]

    elif doc_type == "actor":
        if re.search(r"1[\.\:]|identity|classification|leadership", h_lower):
            return "ACTOR_ANCHOR", ["ActorAnchor"]
        if re.search(r"2[\.\:]|lineage|faction|command", h_lower):
            return "COMMAND_LINEAGE", ["CommandLineage"]
        if re.search(r"3[\.\:]|strategic|objective|ideology|economy", h_lower):
            return "STRATEGIC_DOCTRINE", ["StrategicDoctrine"]
        if re.search(r"4[\.\:]|operational|capability|alliance|foreign", h_lower):
            return "ALLIANCE_NETWORK", ["AllianceNetwork"]
        if re.search(r"5[\.\:]|footprint|accountability|event", h_lower):
            return "EVENT_FOOTPRINT", ["EventFootprint"]

    elif doc_type == "location":
        if re.search(r"1[\.\:]|geopolitical|significance", h_lower):
            return "LOCATION_ANCHOR", ["LocationAnchor"]
        if re.search(r"2[\.\:]|territorial|control|armed presence", h_lower):
            return "TERRITORIAL_CONTROL", ["TerritorialControl"]
        if re.search(r"3[\.\:]|infrastructure|corridor|resource", h_lower):
            return "INFRASTRUCTURE_LOGISTICS", ["InfrastructureLogistics"]
        if re.search(r"4[\.\:]|humanitarian|displacement|ipc", h_lower):
            return "HUMANITARIAN_STATUS", ["HumanitarianStatus"]
        if re.search(r"5[\.\:]|chronological log|major conflict", h_lower):
            return "EVENT_LOG", ["EventLog"]

    elif doc_type == "theme":
        if re.search(r"1[\.\:]|core thesis|structural mechanism", h_lower):
            return "DEFINITIONAL_ANCHOR", ["DefinitionalAnchor"]
        if re.search(r"2[\.\:]|historical roots|political economy", h_lower):
            return "MECHANISTIC_DEEPEN", ["MechanisticDeepen"]
        if re.search(r"3[\.\:]|operational manifestation|frontline", h_lower):
            return "MANIFESTATION_TRAP", ["ManifestationTrap"]
        if re.search(r"4[\.\:]|humanitarian|regional|diplomatic|consequence", h_lower):
            return "IMPACT_ASSESSMENT", ["ImpactAssessment"]
        if re.search(r"5[\.\:]|empirical debate|uncertaint|competing", h_lower):
            return "EMPIRICAL_BOUNDARY", ["EmpiricalBoundary"]

    elif doc_type == "citation":
        if re.search(r"1[\.\:]|speaker provenance|institutional role", h_lower):
            return "CITATION_ANCHOR", ["CitationAnchor"]
        if re.search(r"2[\.\:]|verbatim|bilingual citation|forensic text", h_lower):
            return "VERBATIM_EVIDENCE", ["VerbatimEvidence"]
        if re.search(r"3[\.\:]|substantive claim|event grounding|forensic grounding", h_lower):
            return "FORENSIC_GROUNDING", ["ForensicGrounding"]

    elif doc_type == "timeline":
        if re.search(r"1[\.\:]|temporal scope|theatre coverage|periodization", h_lower):
            return "TIMELINE_ANCHOR", ["TimelineAnchor"]
        if re.search(r"2[\.\:]|chronological event|citation ledger|bitemporal", h_lower):
            return "CHRONOLOGICAL_LEDGER", ["ChronologicalLedger"]
        if re.search(r"3[\.\:]|causal escalation|turning point|tempo", h_lower):
            return "CAUSAL_ESCALATION", ["CausalEscalation"]
        if re.search(r"4[\.\:]|cumulative humanitarian|telemetry", h_lower):
            return "CUMULATIVE_TELEMETRY", ["CumulativeTelemetry"]

    return "NARRATIVE_STEP", []


def infer_transition_rule(cat1: str, cat2: str) -> Tuple[str, str, float]:
    if cat1 == "EVENT_ANCHOR" and cat2 == "CHRONOLOGICAL_MECHANICS":
        return ("tactical_unfolding", "Unpacks the 5W1H event anchor into chronological sequence and tactical mechanics.", 1.0)
    if cat1 == "CHRONOLOGICAL_MECHANICS" and cat2 == "CAUSAL_MOTIVES":
        return ("causal_explanation", "Explains the strategic motives and causal drivers behind the tactical action.", 1.0)
    if cat1 == "CAUSAL_MOTIVES" and cat2 == "IMPACT_ASSESSMENT":
        return ("impact_consequence", "Evaluates humanitarian, territorial, and geopolitical consequences.", 1.0)
    if cat2 == "CONTRADICTION_MATRIX":
        return ("narrative_dispute_audit", "Contrasts competing belligerent, monitor, and OSINT claims in a GRaSP matrix.", 1.0)
    if cat1 == "CITATION_ANCHOR" and cat2 == "VERBATIM_EVIDENCE":
        return ("verbatim_quote_grounding", "Grounds speaker identity and institutional capacity in verbatim bilingual evidence.", 1.0)
    if cat1 == "VERBATIM_EVIDENCE" and cat2 == "FORENSIC_GROUNDING":
        return ("forensic_claim_projection", "Projects verbatim testimony onto specific conflict events, actors, and IHL claims.", 1.0)
    if cat1 == "TIMELINE_ANCHOR" and cat2 == "CHRONOLOGICAL_LEDGER":
        return ("bitemporal_ledger_unfolding", "Unpacks the temporal horizon into a bitemporal chronological ledger of events and citations.", 1.0)
    if cat1 == "CHRONOLOGICAL_LEDGER" and cat2 == "CAUSAL_ESCALATION":
        return ("causal_escalation_synthesis", "Synthesizes chronological events into causal escalation chains and tempo shifts.", 1.0)
    if cat1 == "CAUSAL_ESCALATION" and cat2 == "CUMULATIVE_TELEMETRY":
        return ("cumulative_telemetry_aggregation", "Aggregates cumulative casualty bounds, territorial shifts, and attribution telemetry.", 1.0)
    if cat2 == "SYNTHESIS_CATALOG":
        return ("synthesis_catalog", "Cross-references related events, actors, locations, themes, citations, and sources.", 1.0)
    return ("narrative_progression", "Progresses conflict intelligence analysis across sections.", 0.90)


# ==============================================================================
# 3. Markdown Document Parsing
# ==============================================================================

def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter and return (metadata, body)."""
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    fm_text = parts[1]
    body = parts[2]
    meta: Dict[str, Any] = {}
    current_list_key = None

    for line in fm_text.splitlines():
        line_str = line.strip()
        if not line_str or line_str.startswith("#"):
            continue

        if current_list_key and line.startswith(("  -", "\t-", "- ")):
            item_val = re.sub(r'^\s*-\s*', '', line).strip()
            item_val = item_val.split("#", 1)[0].strip()
            item_val = re.sub(r'^[\'"]|[\'"]$', '', item_val)
            if item_val and isinstance(meta.get(current_list_key), list):
                meta[current_list_key].append(item_val)
            continue

        if ":" in line and not line.startswith(("  ", "\t")):
            k, v = line.split(":", 1)
            k = k.strip()
            # Strip inline YAML comments outside quotes
            v = re.sub(r'\s+#.*$', '', v).strip()
            current_list_key = None

            if not v:
                meta[k] = []
                current_list_key = k
            elif v.startswith("[") and v.endswith("]"):
                items = [re.sub(r'[\'"]', '', x.strip()) for x in v[1:-1].split(",") if x.strip()]
                meta[k] = items
            elif v.lower() in ("true", "false"):
                meta[k] = (v.lower() == "true")
            elif v.lower() in ("null", "none", "~"):
                meta[k] = None
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


def clean_wikilink_str(val: Any) -> str:
    """Strip [[...]] and optional alias/prefix from a frontmatter string."""
    if not val:
        return ""
    s = re.sub(r'\[\[(.*?)\]\]', r'\1', str(val)).strip()
    s = re.split(r'\\?\|', s)[0].split("#")[0].strip()
    s = re.sub(r'^(wiki/)?(events|actors|locations|themes|timelines|citations|sources|syntheses)/', '', s).replace('.md', '').strip()
    return s


def extract_wikilinks(text: str) -> List[str]:
    """Extract target note titles from [[Target|Alias]] or [[Target]]."""
    links = []
    for match in re.finditer(r'\[\[(.*?)\]\]', text):
        raw = re.split(r'\\?\|', match.group(1))[0].split("#")[0].strip()
        raw = re.sub(r'^(wiki/)?(events|actors|locations|themes|timelines|citations|sources|syntheses)/', '', raw).strip()
        if raw and raw not in links:
            links.append(raw)
    return links


def parse_sections(file_rel_path: str, body: str) -> List[Dict[str, Any]]:
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
# 4. Main Sudan News & OSINT Ingestion Engine
# ==============================================================================

FOLDER_TO_DOCTYPE = {
    "events": "event",
    "actors": "actor",
    "locations": "location",
    "themes": "theme",
    "timelines": "timeline",
    "citations": "citation",
    "sources": "source",
    "syntheses": "synthesis",
}

DOCTYPE_TO_CLASS = {
    "event": "Event",
    "actor": "Actor",
    "location": "Location",
    "theme": "Theme",
    "timeline": "Timeline",
    "citation": "Citation",
    "source": "Source",
    "synthesis": "Synthesis",
}


def ensure_section_schema(client: ArcadeDBClient):
    """Ensure Section, Citation, and Diagram properties exist alongside bootstrap_arcadedb.py DDL."""
    cmds = [
        "CREATE VERTEX TYPE Diagram IF NOT EXISTS",
        "CREATE VERTEX TYPE Synthesis IF NOT EXISTS",
        "CREATE VERTEX TYPE Citation IF NOT EXISTS",
        "CREATE PROPERTY Citation.title IF NOT EXISTS STRING",
        "CREATE PROPERTY Citation.subtype IF NOT EXISTS STRING",
        "CREATE PROPERTY Citation.speaker IF NOT EXISTS STRING",
        "CREATE PROPERTY Citation.speaker_role IF NOT EXISTS STRING",
        "CREATE PROPERTY Citation.affiliated_organization IF NOT EXISTS STRING",
        "CREATE PROPERTY Citation.source_note IF NOT EXISTS STRING",
        "CREATE PROPERTY Citation.source_outlet IF NOT EXISTS STRING",
        "CREATE PROPERTY Citation.citation_date IF NOT EXISTS STRING",
        "CREATE PROPERTY Citation.original_language IF NOT EXISTS STRING",
        "CREATE PROPERTY Citation.speech_act IF NOT EXISTS STRING",
        "CREATE PROPERTY Citation.admiralty_rating IF NOT EXISTS STRING",
        "CREATE PROPERTY Citation.reliability_score IF NOT EXISTS DOUBLE",
        "CREATE PROPERTY Citation.last_updated IF NOT EXISTS STRING",
        "CREATE INDEX IF NOT EXISTS ON Citation (title) UNIQUE",
        "CREATE PROPERTY Actor.role_title IF NOT EXISTS STRING",
        "CREATE PROPERTY Actor.affiliated_organization IF NOT EXISTS STRING",
        "CREATE PROPERTY Actor.editorial_alignment IF NOT EXISTS STRING",
        "CREATE PROPERTY Actor.baseline_admiralty_reliability IF NOT EXISTS STRING",
        "CREATE PROPERTY Source.status IF NOT EXISTS STRING",
        "CREATE PROPERTY Source.compiled IF NOT EXISTS BOOLEAN",
        "CREATE PROPERTY Source.source_outlet IF NOT EXISTS STRING",
        "CREATE PROPERTY Section.uri IF NOT EXISTS STRING",
        "CREATE PROPERTY Section.title IF NOT EXISTS STRING",
        "CREATE PROPERTY Section.display_name IF NOT EXISTS STRING",
        "CREATE PROPERTY Section.path IF NOT EXISTS STRING",
        "CREATE PROPERTY Section.heading_level IF NOT EXISTS INTEGER",
        "CREATE PROPERTY Section.content_hash IF NOT EXISTS STRING",
        "CREATE PROPERTY Section.toulmin_role IF NOT EXISTS STRING",
        "CREATE PROPERTY Section.weight IF NOT EXISTS FLOAT",
        "CREATE PROPERTY Section.modal_category IF NOT EXISTS STRING",
        "CREATE INDEX IF NOT EXISTS ON Section (uri) UNIQUE",
        "CREATE EDGE TYPE NEXT_SECTION IF NOT EXISTS",
        "CREATE EDGE TYPE HAS_DIAGRAM IF NOT EXISTS",
        "CREATE EDGE TYPE AFFILIATED_WITH IF NOT EXISTS",
        "CREATE EDGE TYPE STATED IF NOT EXISTS",
        "CREATE EDGE TYPE CONTAINS_CITATION IF NOT EXISTS",
        "CREATE EDGE TYPE TESTIFIES_TO IF NOT EXISTS",
        "CREATE EDGE TYPE PUBLISHED_BY IF NOT EXISTS",
    ]
    for cmd in cmds:
        try:
            client.execute_command(cmd, language="sql")
        except Exception:
            pass


def run_direct_ingestion(client: ArcadeDBClient, purge: bool = False, skip_olap: bool = False):
    print("\n=================================================================")
    print("  Sudan News & OSINT Markdown-to-ArcadeDB Compilation Pipeline")
    print(f"  Target Database : {client.database} @ {client.base_url}")
    print("=================================================================")

    ensure_section_schema(client)

    if purge:
        print("  [*] Purging Section, Diagram, Event, Theme, Timeline, Citation, Source, Synthesis vertices & edges (preserving seeded Actor/Location/AliasLookup/IntentAnchor)...")
        for et in [
            "PROGRESSES_TO", "NEXT_SECTION", "HAS_SECTION", "HAS_DIAGRAM", "TAGGED_WITH", "LINKS_TO", "CITES",
            "OCCURRED_AT", "LOCATED_IN", "PERPETRATED_BY", "TARGETED", "PARTICIPATED_IN", "COMMANDED_BY",
            "ALLIED_WITH", "SPONSORED_BY", "AFFILIATED_WITH", "STATED", "CONTAINS_CITATION", "TESTIFIES_TO",
            "PUBLISHED_BY", "CHRONICLES", "PRECEDES", "TRIGGERS", "RETALIATES_FOR", "PART_OF_CAMPAIGN",
            "MOTIVATED_BY", "CONTROLS_TERRITORY", "DISPLACES_POPULATION", "EMPIRICALLY_GROUNDS",
            "CORROBORATES", "CONTRADICTS_CLAIM", "ATTRIBUTES_BLAME_TO", "DEBUNKS"
        ]:
            try:
                client.execute_command(f"DELETE FROM `{et}`", language="sql")
            except Exception:
                pass
        for vt in ["Section", "Diagram", "Event", "Theme", "Timeline", "Citation", "Source", "Synthesis"]:
            try:
                client.execute_command(f"DELETE FROM `{vt}`", language="sql")
            except Exception:
                pass

    t0 = time.time()
    total_vertices = 0
    total_edges = 0
    skipped_draft_sources = 0

    # 1. Discover markdown files across Sudan News directories
    print("\n[1/5] Scanning and parsing wiki/ markdown files...")
    all_files: List[Tuple[str, Path]] = []
    for sub, default_dtype in FOLDER_TO_DOCTYPE.items():
        sub_dir = WIKI_DIR / sub
        if sub_dir.exists():
            for p in sorted(sub_dir.glob("*.md")):
                all_files.append((default_dtype, p))

    print(f"  → Discovered {len(all_files)} candidate markdown notes across wiki/.")

    tags_set: Set[str] = set()
    sections_records: List[Dict[str, Any]] = []
    diagrams_records: List[Dict[str, Any]] = []
    aliases_dict: Dict[str, str] = {}

    # Pre-load existing AliasLookup mappings seeded from glossary.md
    try:
        existing_aliases = client.query("SELECT alias, canonical_title FROM AliasLookup", language="sql")
        for row in existing_aliases:
            if row.get("alias") and row.get("canonical_title"):
                aliases_dict[row["alias"]] = row["canonical_title"]
    except Exception:
        pass

    doc_meta_map: Dict[str, Dict[str, Any]] = {}
    doc_body_map: Dict[str, str] = {}
    doc_sections_map: Dict[str, List[str]] = {}
    sec_to_doc_map: Dict[str, str] = {}
    sec_links_to: List[Tuple[str, str]] = []
    micro_cot_pairs: List[Dict[str, Any]] = []

    for default_dtype, p in all_files:
        try:
            content = p.read_text(encoding="utf-8")
        except Exception:
            continue

        rel_path = str(p.relative_to(VAULT_ROOT))
        fm, body = parse_frontmatter(content)
        title = str(fm.get("title") or p.stem)
        doc_type = str(fm.get("type") or default_dtype).lower()

        # Two-Phase Ingestion Guard: Skip draft or uncompiled source notes!
        if doc_type == "source":
            src_status = str(fm.get("status", "approved")).lower()
            src_compiled = fm.get("compiled", True)
            if src_status == "draft" or src_compiled is False or str(src_compiled).lower() == "false":
                print(f"  [SKIP] Draft/uncompiled source note awaiting Phase 2 compilation: {rel_path} (status={src_status}, compiled={src_compiled})")
                skipped_draft_sources += 1
                continue

        doc_body_map[title] = body
        doc_meta_map[title] = {
            "title": title,
            "type": doc_type,
            "subtype": str(fm.get("subtype", "")),
            "status": str(fm.get("status", "approved")),
            "compiled": bool(fm.get("compiled", True)),
            "source_outlet": clean_wikilink_str(fm.get("source_outlet", "")),
            "role_title": str(fm.get("role_title", "") or fm.get("speaker_role", "")),
            "affiliated_organization": clean_wikilink_str(fm.get("affiliated_organization", "")),
            "editorial_alignment": str(fm.get("editorial_alignment", "") or fm.get("alignment", "")),
            "baseline_admiralty_reliability": str(fm.get("baseline_admiralty_reliability", "")),
            "speaker": clean_wikilink_str(fm.get("speaker", "")),
            "speaker_role": str(fm.get("speaker_role", "")),
            "source_note": clean_wikilink_str(fm.get("source_note", "")),
            "citation_date": str(fm.get("citation_date", "")),
            "original_language": str(fm.get("original_language", "en")),
            "speech_act": str(fm.get("speech_act", "official_statement")),
            "events_referenced": [clean_wikilink_str(x) for x in (fm.get("events_referenced", []) if isinstance(fm.get("events_referenced"), list) else []) if clean_wikilink_str(x)],
            "actors_referenced": [clean_wikilink_str(x) for x in (fm.get("actors_referenced", []) if isinstance(fm.get("actors_referenced"), list) else []) if clean_wikilink_str(x)],
            "locations_referenced": [clean_wikilink_str(x) for x in (fm.get("locations_referenced", []) if isinstance(fm.get("locations_referenced"), list) else []) if clean_wikilink_str(x)],
            "themes_referenced": [clean_wikilink_str(x) for x in (fm.get("themes_referenced", []) if isinstance(fm.get("themes_referenced"), list) else []) if clean_wikilink_str(x)],
            "start_date": str(fm.get("start_date", "")),
            "end_date": str(fm.get("end_date", "")),
            "time_horizon": str(fm.get("time_horizon", "month")),
            "cumulative_fatalities_best": int(fm.get("cumulative_fatalities_best", 0) or 0),
            "events_chronicled": [clean_wikilink_str(x) for x in (fm.get("events_chronicled", []) if isinstance(fm.get("events_chronicled"), list) else []) if clean_wikilink_str(x)],
            "citations_chronicled": [clean_wikilink_str(x) for x in (fm.get("citations_chronicled", []) if isinstance(fm.get("citations_chronicled"), list) else []) if clean_wikilink_str(x)],
            "reliability_score": float(fm.get("reliability_score", 0.85)),
            "admiralty_rating": str(fm.get("admiralty_rating", "B2")),
            "pcode": str(fm.get("pcode", "")),
            "event_category": str(fm.get("event_category", "")),
            "event_sub_type": str(fm.get("event_sub_type", "")),
            "event_start_date": str(fm.get("event_start_date", "")),
            "event_end_date": str(fm.get("event_end_date", "")),
            "reported_date": str(fm.get("reported_date", "")),
            "published_date": str(fm.get("published_date", "")),
            "language": str(fm.get("language", "en")),
            "alignment": str(fm.get("alignment", "independent")),
            "verification_status": str(fm.get("verification_status", "")),
            "fatalities_best": int(fm.get("fatalities_best", 0) or 0),
            "last_updated": str(fm.get("last_updated", "2026-11-01")),
            "tags": fm.get("tags", []) if isinstance(fm.get("tags"), list) else [],
            "aliases": fm.get("aliases", []) if isinstance(fm.get("aliases"), list) else [],
            "sources": fm.get("sources", []) if isinstance(fm.get("sources"), list) else [],
            "locations": fm.get("locations", []) if isinstance(fm.get("locations"), list) else [],
            "path": rel_path,
            "slug": p.stem,
        }

        for t in doc_meta_map[title]["tags"]:
            if isinstance(t, str) and t.strip():
                tags_set.add(t.strip())

        for a in doc_meta_map[title]["aliases"]:
            if isinstance(a, str) and a.strip():
                aliases_dict[a.strip()] = title

        # Parse Sections
        raw_secs = parse_sections(rel_path, body)
        doc_sec_uris = []
        for s in raw_secs:
            sec_uri = f"{rel_path}#{s['idx']}"
            sec_title = s["title"]
            raw_sec_content = s["content"]

            clean_content, sec_diagrams = process_section_diagrams(sec_uri, sec_title, raw_sec_content)
            diagrams_records.extend(sec_diagrams)

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

            links = extract_wikilinks(clean_content)
            for target in links:
                sec_links_to.append((sec_uri, target))

        doc_sections_map[title] = doc_sec_uris

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
                "method": "sudan_news_ast"
            })

    if skipped_draft_sources > 0:
        print(f"  [i] Skipped {skipped_draft_sources} draft/uncompiled source note(s) (Phase 1 review gate active).")

    # 2. Upsert Document Vertices
    print("\n[2/5] Upserting Sudan News & OSINT document vertices into ArcadeDB...")
    for title, meta in doc_meta_map.items():
        dtype = meta["type"]
        vclass = DOCTYPE_TO_CLASS.get(dtype, "Event")
        try:
            if vclass == "Event":
                client.execute_command(
                    "UPDATE Event SET type = :type, subtype = :subtype, event_category = :ecat, "
                    "event_sub_type = :esub, event_start_date = :estart, event_end_date = :eend, "
                    "reported_date = :rep, pcode = :pcode, fatalities_best = :fat, "
                    "verification_status = :vstat, admiralty_rating = :adm, reliability_score = :rel, "
                    "last_updated = :lu UPSERT WHERE title = :title",
                    language="sql",
                    params={
                        "title": title, "type": "event", "subtype": meta["subtype"],
                        "ecat": meta["event_category"], "esub": meta["event_sub_type"],
                        "estart": meta["event_start_date"], "eend": meta["event_end_date"],
                        "rep": meta["reported_date"], "pcode": meta["pcode"],
                        "fat": meta["fatalities_best"], "vstat": meta["verification_status"],
                        "adm": meta["admiralty_rating"], "rel": meta["reliability_score"],
                        "lu": meta["last_updated"]
                    }
                )
            elif vclass == "Actor":
                client.execute_command(
                    "UPDATE Actor SET subtype = :subtype, role_title = :rtitle, "
                    "affiliated_organization = :afforg, editorial_alignment = :edalign, "
                    "baseline_admiralty_reliability = :baseadm, reliability_score = :rel, "
                    "last_updated = :lu UPSERT WHERE title = :title",
                    language="sql",
                    params={
                        "title": title, "subtype": meta["subtype"],
                        "rtitle": meta["role_title"], "afforg": meta["affiliated_organization"],
                        "edalign": meta["editorial_alignment"],
                        "baseadm": meta["baseline_admiralty_reliability"],
                        "rel": meta["reliability_score"], "lu": meta["last_updated"]
                    }
                )
            elif vclass == "Location":
                client.execute_command(
                    "UPDATE Location SET subtype = :subtype, pcode = :pcode, "
                    "reliability_score = :rel, last_updated = :lu UPSERT WHERE title = :title",
                    language="sql",
                    params={
                        "title": title, "subtype": meta["subtype"], "pcode": meta["pcode"],
                        "rel": meta["reliability_score"], "lu": meta["last_updated"]
                    }
                )
            elif vclass == "Theme":
                client.execute_command(
                    "UPDATE Theme SET subtype = :subtype, reliability_score = :rel, "
                    "last_updated = :lu UPSERT WHERE title = :title",
                    language="sql",
                    params={
                        "title": title, "subtype": meta["subtype"],
                        "rel": meta["reliability_score"], "lu": meta["last_updated"]
                    }
                )
            elif vclass == "Timeline":
                client.execute_command(
                    "UPDATE Timeline SET subtype = :subtype, start_date = :sdate, end_date = :edate, "
                    "time_horizon = :thorizon, cumulative_fatalities_best = :cfat, "
                    "admiralty_rating = :adm, reliability_score = :rel, "
                    "last_updated = :lu UPSERT WHERE title = :title",
                    language="sql",
                    params={
                        "title": title, "subtype": meta["subtype"],
                        "sdate": meta["start_date"], "edate": meta["end_date"],
                        "thorizon": meta["time_horizon"], "cfat": meta["cumulative_fatalities_best"],
                        "adm": meta["admiralty_rating"], "rel": meta["reliability_score"],
                        "lu": meta["last_updated"]
                    }
                )
            elif vclass == "Citation":
                client.execute_command(
                    "UPDATE Citation SET subtype = :subtype, speaker = :speaker, "
                    "speaker_role = :srole, affiliated_organization = :afforg, "
                    "source_note = :snote, source_outlet = :soutlet, citation_date = :cdate, "
                    "original_language = :olang, speech_act = :sact, admiralty_rating = :adm, "
                    "reliability_score = :rel, last_updated = :lu UPSERT WHERE title = :title",
                    language="sql",
                    params={
                        "title": title, "subtype": meta["subtype"], "speaker": meta["speaker"],
                        "srole": meta["speaker_role"], "afforg": meta["affiliated_organization"],
                        "snote": meta["source_note"], "soutlet": meta["source_outlet"],
                        "cdate": meta["citation_date"], "olang": meta["original_language"],
                        "sact": meta["speech_act"], "adm": meta["admiralty_rating"],
                        "rel": meta["reliability_score"], "lu": meta["last_updated"]
                    }
                )
            elif vclass == "Source":
                client.execute_command(
                    "UPDATE Source SET title = :title, subtype = :subtype, status = :status, "
                    "compiled = :compiled, source_outlet = :soutlet, language = :lang, "
                    "alignment = :align, admiralty_rating = :adm, reliability_score = :rel, "
                    "published_date = :pub UPSERT WHERE slug = :slug",
                    language="sql",
                    params={
                        "slug": meta["slug"], "title": title, "subtype": meta["subtype"],
                        "status": meta["status"], "compiled": meta["compiled"],
                        "soutlet": meta["source_outlet"], "lang": meta["language"],
                        "align": meta["alignment"], "adm": meta["admiralty_rating"],
                        "rel": meta["reliability_score"], "pub": meta["published_date"]
                    }
                )
            elif vclass == "Synthesis":
                client.execute_command(
                    "UPDATE Synthesis SET title = :title, subtype = :subtype, "
                    "reliability_score = :rel, last_updated = :lu UPSERT WHERE slug = :slug",
                    language="sql",
                    params={
                        "slug": meta["slug"], "title": title, "subtype": meta["subtype"],
                        "rel": meta["reliability_score"], "lu": meta["last_updated"]
                    }
                )
            total_vertices += 1
        except Exception as e:
            print(f"  [!] Warning upserting {vclass} '{title}': {e}")

    for t in tags_set:
        try:
            client.execute_command("UPDATE Tag SET name = :name UPSERT WHERE name = :name", language="sql", params={"name": t})
            total_vertices += 1
        except Exception:
            pass

    # 3. Ingest Sections & Diagrams
    print(f"\n[3/5] Upserting {len(sections_records)} Section vertices and {len(diagrams_records)} Diagram vertices...")
    for s in sections_records:
        try:
            client.execute_command(
                "UPDATE Section SET title = :title, display_name = :dname, path = :path, "
                "heading_level = :hlevel, heading = :heading, step_type = :stype, "
                "toulmin_role = :trole, weight = :weight, modal_category = :mcat, "
                "content = :content, content_hash = :chash UPSERT WHERE uri = :uri",
                language="sql",
                params={
                    "uri": s["uri"], "title": s["title"], "dname": s["display_name"],
                    "path": s["path"], "hlevel": s["heading_level"], "heading": s["heading"],
                    "stype": s["step_type"], "trole": s["toulmin_role"], "weight": s["weight"],
                    "mcat": s["modal_category"], "content": s["content"], "chash": s["content_hash"]
                }
            )
            total_vertices += 1
        except Exception:
            pass

    # 4. Cache RIDs for Edge Generation
    print("\n[4/5] Building in-memory RID resolution maps...")
    node_rid_map: Dict[str, str] = {}
    for vcls in ["Event", "Actor", "Location", "Theme", "Timeline", "Citation", "Source", "Synthesis"]:
        try:
            rows = client.query(f"SELECT @rid, title, slug FROM {vcls}", language="sql")
            for r in rows:
                if r.get("title"):
                    node_rid_map[r["title"]] = r["@rid"]
                if r.get("slug"):
                    node_rid_map[r["slug"]] = r["@rid"]
        except Exception:
            pass

    sec_rids = client.query("SELECT @rid, uri FROM Section", language="sql")
    section_map = {row["uri"]: row["@rid"] for row in sec_rids if "uri" in row}

    def resolve_target_rid(key: str) -> Optional[str]:
        if not key:
            return None
        canon = aliases_dict.get(key, key)
        return node_rid_map.get(canon) or node_rid_map.get(key)

    # 5. Connect Graph Relationships
    print("\n[5/5] Connecting HAS_SECTION, PROGRESSES_TO, LINKS_TO, PUBLISHED_BY, AFFILIATED_WITH, STATED, CONTAINS_CITATION, TESTIFIES_TO, CHRONICLES, PRECEDES, and EMPIRICALLY_GROUNDS edges...")
    edge_batch: List[str] = []

    for sec in sections_records:
        doc_rid = resolve_target_rid(sec["doc_title"])
        s_rid = section_map.get(sec["uri"])
        if doc_rid and s_rid:
            edge_batch.append(json.dumps({
                "@type": "edge", "@class": "HAS_SECTION",
                "@from": doc_rid, "@to": s_rid
            }))

    for pair in micro_cot_pairs:
        s1_rid = section_map.get(pair["s1_uri"])
        s2_rid = section_map.get(pair["s2_uri"])
        if s1_rid and s2_rid:
            edge_batch.append(json.dumps({
                "@type": "edge", "@class": "PROGRESSES_TO",
                "@from": s1_rid, "@to": s2_rid,
                "transition_type": pair["transition_type"],
                "warrant": pair["warrant"],
                "confidence": pair["confidence"]
            }))

    for s_uri, tgt_title in sec_links_to:
        s_rid = section_map.get(s_uri)
        tgt_rid = resolve_target_rid(tgt_title)
        if s_rid and tgt_rid:
            edge_batch.append(json.dumps({
                "@type": "edge", "@class": "LINKS_TO",
                "@from": s_rid, "@to": tgt_rid
            }))

    for title, meta in doc_meta_map.items():
        doc_rid = resolve_target_rid(title)
        if not doc_rid:
            continue

        # 1. Source -> PUBLISHED_BY -> Actor (media_source)
        if meta["type"] == "source" and meta.get("source_outlet"):
            outlet_rid = resolve_target_rid(meta["source_outlet"])
            if outlet_rid and outlet_rid != doc_rid:
                edge_batch.append(json.dumps({
                    "@type": "edge", "@class": "PUBLISHED_BY",
                    "@from": doc_rid, "@to": outlet_rid,
                    "warrant": f"Published by {meta['source_outlet']}"
                }))

        # 2. Actor (person) -> AFFILIATED_WITH -> Actor (organization)
        if meta["type"] == "actor" and meta.get("affiliated_organization"):
            org_rid = resolve_target_rid(meta["affiliated_organization"])
            if org_rid and org_rid != doc_rid:
                edge_batch.append(json.dumps({
                    "@type": "edge", "@class": "AFFILIATED_WITH",
                    "@from": doc_rid, "@to": org_rid,
                    "role_title": meta.get("role_title", ""),
                    "warrant": f"{title} serves as {meta.get('role_title', 'member')} at {meta['affiliated_organization']}"
                }))

        # 3. Timeline -> CHRONICLES -> Event/Citation & sequential Event -> PRECEDES -> Event
        if meta["type"] == "timeline":
            ev_rids: List[str] = []
            for idx, ev_name in enumerate(meta.get("events_chronicled", []), 1):
                ev_rid = resolve_target_rid(ev_name)
                if ev_rid and ev_rid != doc_rid:
                    ev_rids.append(ev_rid)
                    edge_batch.append(json.dumps({
                        "@type": "edge", "@class": "CHRONICLES",
                        "@from": doc_rid, "@to": ev_rid,
                        "sequence_order": idx
                    }))
            for idx in range(len(ev_rids) - 1):
                if ev_rids[idx] != ev_rids[idx + 1]:
                    edge_batch.append(json.dumps({
                        "@type": "edge", "@class": "PRECEDES",
                        "@from": ev_rids[idx], "@to": ev_rids[idx + 1],
                        "timeline_context": title
                    }))
            for c_idx, cit_name in enumerate(meta.get("citations_chronicled", []), 1):
                cit_rid = resolve_target_rid(cit_name)
                if cit_rid and cit_rid != doc_rid:
                    edge_batch.append(json.dumps({
                        "@type": "edge", "@class": "CHRONICLES",
                        "@from": doc_rid, "@to": cit_rid,
                        "sequence_order": c_idx
                    }))

        # 4. Citation edges: Speaker -> STATED -> Citation, Source -> CONTAINS_CITATION -> Citation, Citation -> TESTIFIES_TO -> Event/Actor/Location/Theme
        if meta["type"] == "citation":
            if meta.get("speaker"):
                spk_rid = resolve_target_rid(meta["speaker"])
                if spk_rid and spk_rid != doc_rid:
                    edge_batch.append(json.dumps({
                        "@type": "edge", "@class": "STATED",
                        "@from": spk_rid, "@to": doc_rid,
                        "speaker_role": meta.get("speaker_role", ""),
                        "citation_date": meta.get("citation_date", "")
                    }))
            if meta.get("source_note"):
                s_rid = resolve_target_rid(meta["source_note"])
                if s_rid and s_rid != doc_rid:
                    edge_batch.append(json.dumps({
                        "@type": "edge", "@class": "CONTAINS_CITATION",
                        "@from": s_rid, "@to": doc_rid
                    }))
            ref_targets = (
                meta.get("events_referenced", []) +
                meta.get("actors_referenced", []) +
                meta.get("locations_referenced", []) +
                meta.get("themes_referenced", [])
            )
            for ref_name in ref_targets:
                ref_rid = resolve_target_rid(ref_name)
                if ref_rid and ref_rid != doc_rid:
                    edge_batch.append(json.dumps({
                        "@type": "edge", "@class": "TESTIFIES_TO",
                        "@from": doc_rid, "@to": ref_rid,
                        "speech_act": meta.get("speech_act", "official_statement")
                    }))

        # 5. Source -> EMPIRICALLY_GROUNDS -> Domain Node
        for s_ref in meta.get("sources", []):
            s_clean = clean_wikilink_str(s_ref)
            src_rid = resolve_target_rid(s_clean)
            if src_rid and src_rid != doc_rid:
                edge_batch.append(json.dumps({
                    "@type": "edge", "@class": "EMPIRICALLY_GROUNDS",
                    "@from": src_rid, "@to": doc_rid,
                    "weight": meta.get("reliability_score", 0.85),
                    "warrant": f"Empirically grounds {title}"
                }))

    for i in range(0, len(edge_batch), 500):
        chunk = edge_batch[i:i + 500]
        res = client.batch_ndjson(chunk)
        total_edges += res.get("edgesCreated", len(chunk))

    elapsed = time.time() - t0
    print(f"\n[✓] Ingestion complete in {elapsed:.2f}s: {total_vertices} vertices upserted, {total_edges} edges linked.")

    if not skip_olap and len(sections_records) > 0:
        print("\n[*] Generating native in-engine embeddings via algo.fastrp...")
        try:
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
            MATCH (n:Section) WHERE elementId(n) = rid_str
            SET n.vector = embedding
            RETURN count(n) AS total_embedded
            """
            res = client.execute_command(fastrp_cypher, language="cypher")
            total_emb = res[0].get("total_embedded", 0) if res else 0
            print(f"  [✓] FastRP generated native embeddings across {total_emb} Section vertices.")
        except Exception as e:
            print(f"  [!] Note on FastRP embeddings: {e}")


def main():
    parser = argparse.ArgumentParser(description="Compile wiki/ Markdown into ArcadeDB (news)")
    parser.add_argument("--purge", action="store_true", help="Purge compiled sections/events before re-ingesting")
    parser.add_argument("--skip-olap", action="store_true", help="Skip post-ingestion FastRP / OLAP procedures")
    args = parser.parse_args()

    client = ArcadeDBClient()
    run_direct_ingestion(client, purge=args.purge, skip_olap=args.skip_olap)
    return 0


if __name__ == "__main__":
    sys.exit(main())
