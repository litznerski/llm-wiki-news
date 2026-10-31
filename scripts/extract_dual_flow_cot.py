# /// script
# dependencies = [
#     "neo4j>=5.0.0",
# ]
# ///
#!/usr/bin/env python3
"""
scripts/extract_dual_flow_cot.py
Extracts and materializes Dual-Flow Chain of Thought into Neo4j:
  - Option 3: Hybrid Two-Pass Cascade (Deterministic AST heuristics + Local Ollama neural warrant extraction)
  - Micro-CoT: Augments sequential sections with epistemic labels (:Summary, :CoreThesis, :MechanisticDeepen, etc.) and [:PROGRESSES_TO {transition_type, warrant, confidence}]
  - Macro-CoT: Discovers and materializes typed reasoning handshakes between documents:
      * [:REMEDIES_DILEMMA] (from Prescriptive Solution sections to target Concepts)
      * [:EXTENDS_THEORY] (from Mechanistic Deepen sections to target Concepts)
      * [:PRECIPITATES] (from Manifestation Trap/Dilemma sections to target Concepts)
      * [:EMPIRICALLY_GROUNDS] (from Primary Sources to Concepts)

Usage:
    uv run scripts/extract_dual_flow_cot.py [--skip-neural] [--max-neural 50] [--model llama3.1-fast]
"""

import os
import sys
import time
import json
import re
import hashlib
import urllib.request
import urllib.error
import argparse
from pathlib import Path
from functools import lru_cache
from typing import Dict, List, Any, Tuple, Optional

try:
    from neo4j import GraphDatabase, Driver
except ImportError:
    print("Error: The 'neo4j' Python driver is required.", file=sys.stderr)
    print("Run with uv:  uv run scripts/extract_dual_flow_cot.py", file=sys.stderr)
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
DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1-fast")

CACHE_FILE = VAULT_ROOT / "wiki" / ".ki" / "cot_cache.json"

def map_to_toulmin_role(step_type: str, doc_type: str = "concept") -> str:
    """
    Direct mapping from epistemic step_type to Toulmin argumentation role:
    - DEFINITIONAL_ANCHOR -> 'GROUNDS'
    - CORE_THESIS -> 'CLAIM'
    - MECHANISTIC_DEEPEN -> 'WARRANT'
    - MANIFESTATION_TRAP / DILEMMA_PROBLEM -> 'REBUTTAL'
    - PRESCRIPTIVE_SOLUTION -> 'SOLUTION_WARRANT'
    - EMPIRICAL_BOUNDARY -> 'QUALIFIER'
    - SYNTHESIS_CATALOG -> 'BACKING'
    - Entity and Source sections -> 'NON_ARGUMENTATIVE'
    """
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


def _strip_markdown(text: str) -> str:
    """Remove mermaid blocks, wikilinks, callouts, URIs for clean text analysis."""
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
    "DEFINITIONAL_ANCHOR": 0.75,  # Definitions are implicitly certain
    "SYNTHESIS_CATALOG":   0.50,  # Catalogs are neutral references
    "NARRATIVE_STEP":      0.50,  # Non-argumentative
}


@lru_cache(maxsize=2048)
def compute_linguistic_weight(text: str, step_type: str = "") -> Tuple[float, str, List[str]]:
    """
    Returns (raw_weight, modal_category, matched_phrases).
    Uses frequency-weighted averaging over all detected modal patterns.
    """
    clean = _strip_markdown(text).lower()
    words = clean.split()

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

    # Frequency-weighted average, clipped to [0, 1]
    freq_weighted = weighted_sum / hit_count_total
    # Apply step_type floor
    floor = STEP_TYPE_FLOOR.get(step_type, 0.0)
    raw = max(floor, round(freq_weighted, 3))
    return raw, best_cat, matched[:5]


def classify_section(doc_title: str, doc_type: str, heading_text: str, content: str, is_lead: bool) -> Tuple[str, List[str]]:
    """
    Classifies a section into (step_type, labels).
    - Concept lead section with [!IMPORTANT] Definitional Anchor -> ('DEFINITIONAL_ANCHOR', ['DefinitionalAnchor', 'Summary'])
    - Section starting with 'Core Thesis' -> ('CORE_THESIS', ['DefinitionalAnchor', 'CoreThesis'])
    - Section 2 -> ('MECHANISTIC_DEEPEN', ['MechanisticDeepen'])
    - Section 3 -> ('MANIFESTATION_TRAP', ['ManifestationTrap'])
    - Section 4 -> ('PRESCRIPTIVE_SOLUTION', ['PrescriptiveSolution'])
    - Section 5 -> ('EMPIRICAL_BOUNDARY', ['EmpiricalBoundary'])
    - Section 6 -> ('SYNTHESIS_CATALOG', ['SynthesisCatalog'])
    """
    h_lower = (heading_text or "").lower().strip()
    
    # 1. Lead Section check (esp. for concepts)
    if is_lead or (doc_type == "concept" and h_lower == doc_title.lower().strip()) or "[!important] definitional anchor" in content.lower():
        return "DEFINITIONAL_ANCHOR", ["DefinitionalAnchor", "Summary"]

    # 2. Canonical Generation 3 concept sections
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

    # 3. Fallback semantic keywords for subheadings / unnumbered sections
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

def infer_transition_rule(cat1: str, cat2: str, heading1: str, heading2: str) -> Tuple[str, str, float]:
    """Pass 1: Deterministic heuristic inference of transition type, default warrant, and confidence."""
    # 0. Definitional Anchor (Summary) -> Core Thesis
    if cat1 == "DEFINITIONAL_ANCHOR" and cat2 == "CORE_THESIS":
        return (
            "core_thesis_elaboration",
            "Elaborates foundational definitional anchor into primary deductive core thesis and argument.",
            1.0
        )
    # 1. Any step leading to Prescriptive Solution
    if cat2 == "PRESCRIPTIVE_SOLUTION":
        return (
            "prescriptive_solution",
            "Prescribes architectural safeguards, counter-architectures, and pedagogical interventions to resolve the preceding failure mode.",
            1.0
        )
    # 2. Definitional Anchor or Core Thesis -> Mechanistic Deepening
    if cat1 in ("DEFINITIONAL_ANCHOR", "CORE_THESIS") and cat2 == "MECHANISTIC_DEEPEN":
        return (
            "mechanistic_deepen",
            "Deconstructs foundational core thesis into underlying causal cognitive mechanisms.",
            1.0
        )
    # 3. Mechanism, Anchor, or Core Thesis -> Manifestation Trap / Pathology
    if cat1 in ("MECHANISTIC_DEEPEN", "DEFINITIONAL_ANCHOR", "CORE_THESIS") and cat2 == "MANIFESTATION_TRAP":
        return (
            "manifestation_trap",
            "Traces how underlying cognitive mechanisms or unconstrained interactions precipitate observable failure modes.",
            1.0
        )
    # 4. Toward Empirical Boundary
    if cat2 == "EMPIRICAL_BOUNDARY":
        return (
            "empirical_boundary",
            "Delineates empirical boundary conditions, methodological constraints, or dialectical counter-perspectives.",
            1.0
        )
    # 5. Toward Catalogs / Related Notes
    if cat2 == "SYNTHESIS_CATALOG":
        return (
            "synthesis_catalog",
            "Indexes interconnected concepts, entities, and primary literature touchpoints.",
            1.0
        )
    # 6. Definitional Anchor or Core Thesis -> Dilemma
    if cat1 in ("DEFINITIONAL_ANCHOR", "CORE_THESIS") and cat2 == "DILEMMA_PROBLEM":
        return (
            "dilemma_problem",
            "Exposes intrinsic epistemic tensions or practical breakdowns in conventional assumptions.",
            1.0
        )
    # 7. Mechanistic Deepening Progression
    if cat1 == "MECHANISTIC_DEEPEN" and cat2 == "MECHANISTIC_DEEPEN":
        return (
            "mechanistic_deepen",
            "Elaborates nested sub-mechanisms and structural dynamics.",
            0.95
        )
    
    # Fallback to narrative progression with moderate confidence
    return (
        "causal_progression",
        f"Progresses sequentially from '{heading1}' into '{heading2}'.",
        0.6
    )

class CoTCache:
    def __init__(self, cache_path: Path):
        self.cache_path = cache_path
        self.data: Dict[str, Any] = {}
        self.load()

    def load(self):
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                print(f"  [!] Warning loading cache: {e}. Starting fresh.")
                self.data = {}

    def save(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"  [!] Warning saving cache: {e}")

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self.data.get(key)

    def set(self, key: str, val: Dict[str, Any]):
        self.data[key] = val

def query_ollama_transition(
    doc_title: str,
    s1_title: str,
    s1_content: str,
    s2_title: str,
    s2_content: str,
    ollama_url: str,
    model_name: str,
) -> Optional[Tuple[str, str]]:
    """Pass 2: Targeted neural warrant extraction via local Ollama."""
    prompt = f"""You are an epistemological parser analyzing academic concept notes in a knowledge graph.
Document: "{doc_title}"
Section 1 Heading: "{s1_title}"
Section 1 Excerpt: "{s1_content[:250].strip()}"
Section 2 Heading: "{s2_title}"
Section 2 Excerpt: "{s2_content[:250].strip()}"

Classify the cognitive transition between Section 1 and Section 2.
Choose EXACTLY one transition_type from:
- "mechanistic_deepen" (explaining how/why the concept works under the hood)
- "manifestation_trap" (describing how people fail, misuse, or misunderstand it)
- "prescriptive_solution" (providing protocols, countermeasures, or design frameworks)
- "empirical_boundary" (exceptions, limitations, or dialectical debates)
- "causal_progression" (sequential logical progression)

Respond strictly in valid JSON format:
{{"transition_type": "<type>", "warrant": "<1 concise sentence explaining the logical link>"}}"""

    payload = {
        "model": model_name,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 128}
    }
    
    req = urllib.request.Request(
        f"{ollama_url.rstrip('/')}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            parsed = json.loads(data.get("response", "{}"))
            trans_type = parsed.get("transition_type", "causal_progression")
            warrant = parsed.get("warrant", f"Progresses sequentially from '{s1_title}' into '{s2_title}'.")
            return trans_type, warrant
    except Exception:
        return None

def extract_and_sync_cot(
    driver: Driver,
    database: str = DEFAULT_DATABASE,
    skip_neural: bool = False,
    max_neural: int = 50,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    ollama_model: str = DEFAULT_OLLAMA_MODEL,
):
    start_time = time.time()
    cache = CoTCache(CACHE_FILE)
    
    print("=================================================================")
    print("  Knowledge Lab :: Dual-Flow Chain of Thought (CoT) Extraction")
    print(f"  Mode: Option 3 (Hybrid Two-Pass Cascade)")
    print(f"  Neural Fallback: {'Disabled' if skip_neural else f'Ollama ({ollama_model}, max={max_neural})'}")
    print("=================================================================")

    session_kwargs = {"database": database} if database else {}
    with driver.session(**session_kwargs) as session:
        # 1. Fetch all sections under documents and sequential section pairs
        print("\n[1/4] Scanning Intra-Document Sections (Micro-CoT)...")
        all_sections_query = """
        MATCH (d:Document)-[:HAS*1..3]->(s:Section)
        WHERE d.type IN ['concept', 'source', 'entity', 'synthesis', 'ingestion']
        RETURN d.title AS doc_title, d.type AS doc_type,
               s.uri AS s_uri, s.displayName AS s_title, coalesce(s.content, '') AS s_content,
               (d.title = s.displayName OR s.uri = d.uri OR s.content CONTAINS '[!IMPORTANT] Definitional Anchor') AS is_lead
        """
        all_sections = session.run(all_sections_query).data()
        print(f"  → Found {len(all_sections)} sections across vault notes.")

        sec_pairs_query = """
        MATCH (d:Document)-[:HAS*1..3]->(s1:Section)-[:NEXT_SECTION]->(s2:Section)
        WHERE d.type IN ['concept', 'source', 'entity', 'synthesis', 'ingestion']
        RETURN d.title AS doc_title, d.type AS doc_type,
               s1.uri AS s1_uri, s1.displayName AS s1_title, coalesce(s1.content, '') AS s1_content,
               (d.title = s1.displayName OR s1.uri = d.uri OR s1.content CONTAINS '[!IMPORTANT] Definitional Anchor') AS s1_is_lead,
               s2.uri AS s2_uri, s2.displayName AS s2_title, coalesce(s2.content, '') AS s2_content,
               (d.title = s2.displayName OR s2.uri = d.uri OR s2.content CONTAINS '[!IMPORTANT] Definitional Anchor') AS s2_is_lead
        """
        records = session.run(sec_pairs_query).data()
        print(f"  → Found {len(records)} sequential section pairs across vault notes.")

    # 2. Hybrid Two-Pass Classification
    print("\n[2/4] Executing Two-Pass Classification & Warrant Synthesis...")
    section_updates = {}  # uri -> {"uri": uri, "step_type": st, "toulmin_role": tr, "weight": w, "modal_category": mc, "labels": labels}
    for s in all_sections:
        uri = s["s_uri"]
        doc_type = s["doc_type"] or ""
        st, labels = classify_section(
            s["doc_title"] or "", doc_type, s["s_title"] or "", s["s_content"], s["is_lead"]
        )
        tr = map_to_toulmin_role(st, doc_type)
        w, mc, _ = compute_linguistic_weight(s["s_content"] or "", st)
        section_updates[uri] = {
            "uri": uri,
            "step_type": st,
            "toulmin_role": tr,
            "weight": w,
            "modal_category": mc,
            "labels": labels
        }

    micro_transitions = []
    ast_hits = 0
    cache_hits = 0
    neural_calls = 0
    neural_attempts = 0
    consecutive_errors = 0
    neural_fallbacks = 0

    for idx, r in enumerate(records):
        s1_uri = r["s1_uri"]
        s2_uri = r["s2_uri"]
        s1_title = r["s1_title"] or ""
        s2_title = r["s2_title"] or ""
        doc_title = r["doc_title"] or ""
        doc_type = r["doc_type"] or ""

        st1, l1 = classify_section(doc_title, doc_type, s1_title, r["s1_content"], r["s1_is_lead"])
        st2, l2 = classify_section(doc_title, doc_type, s2_title, r["s2_content"], r["s2_is_lead"])

        tr1 = map_to_toulmin_role(st1, doc_type)
        tr2 = map_to_toulmin_role(st2, doc_type)

        w1, mc1, _ = compute_linguistic_weight(r["s1_content"] or "", st1)
        w2, mc2, _ = compute_linguistic_weight(r["s2_content"] or "", st2)

        section_updates[s1_uri] = {
            "uri": s1_uri, "step_type": st1, "toulmin_role": tr1, "weight": w1, "modal_category": mc1, "labels": l1
        }
        section_updates[s2_uri] = {
            "uri": s2_uri, "step_type": st2, "toulmin_role": tr2, "weight": w2, "modal_category": mc2, "labels": l2
        }

        # Pass 1: Deterministic Rule Inference
        trans_type, warrant, confidence = infer_transition_rule(st1, st2, s1_title, s2_title)
        method = "ast_heuristic"

        # Pass 2: Neural cascade if ambiguous and neural enabled
        if confidence < 0.9 and not skip_neural:
            cache_key = hashlib.sha256(f"{doc_title}|{s1_title}|{s2_title}".encode("utf-8")).hexdigest()
            cached = cache.get(cache_key)
            if cached:
                trans_type = cached["transition_type"]
                warrant = cached["warrant"]
                confidence = 0.88
                method = "neural_cache"
                cache_hits += 1
            elif max_neural == -1 or neural_attempts < max_neural:
                neural_attempts += 1
                print(f"    [neural {neural_attempts}/{max_neural}] {doc_title}: '{s1_title[:25]}' -> '{s2_title[:25]}'...", flush=True)
                neural_res = query_ollama_transition(
                    doc_title, s1_title, r["s1_content"], s2_title, r["s2_content"], ollama_url, ollama_model
                )
                if neural_res:
                    trans_type, warrant = neural_res
                    confidence = 0.88
                    method = "neural_ollama"
                    cache.set(cache_key, {"transition_type": trans_type, "warrant": warrant})
                    neural_calls += 1
                    consecutive_errors = 0
                else:
                    neural_fallbacks += 1
                    consecutive_errors += 1
                    if consecutive_errors >= 3:
                        print("    [!] 3 consecutive Ollama failures; disabling neural fallback for remaining transitions.", flush=True)
                        skip_neural = True
            else:
                neural_fallbacks += 1
        else:
            ast_hits += 1

        micro_transitions.append({
            "s1_uri": s1_uri,
            "s2_uri": s2_uri,
            "transition_type": trans_type,
            "warrant": warrant,
            "confidence": confidence,
            "method": method
        })

    cache.save()
    print(f"  → Classified {len(micro_transitions)} transitions across {len(section_updates)} sections:")
    print(f"    * Deterministic AST Rules: {ast_hits}")
    print(f"    * Neural Cache Hits:       {cache_hits}")
    print(f"    * Live Neural Inferences:  {neural_calls}")
    if neural_fallbacks > 0:
        print(f"    * AST Default Fallbacks:   {neural_fallbacks}")

    # 3. Materialize Micro-CoT in Neo4j
    with driver.session() as session:
        print("\n[3/4] Materializing Micro-CoT (Epistemic Labels and [:PROGRESSES_TO])...")
        
        # Purge legacy CognitiveStep label
        session.run("MATCH (s:CognitiveStep) REMOVE s:CognitiveStep")

        # Label sections atomically in batch
        label_batch = list(section_updates.values())
        session.run("""
            UNWIND $batch AS item
            MATCH (s:Section {uri: item.uri})
            REMOVE s:DefinitionalAnchor, s:Summary, s:CoreThesis, s:MechanisticDeepen,
                   s:ManifestationTrap, s:PrescriptiveSolution, s:EmpiricalBoundary,
                   s:SynthesisCatalog, s:DilemmaProblem
            SET s.step_type = item.step_type,
                s.toulmin_role = item.toulmin_role,
                s.weight = item.weight,
                s.modal_category = item.modal_category,
                s.cot_classified = true
            WITH s, item
            WHERE size(item.labels) > 0
            CALL apoc.create.addLabels(s, item.labels) YIELD node
            RETURN count(node)
        """, batch=label_batch)
        print(f"  → Atomically stamped epistemic labels across {len(label_batch)} sections.")

        # Merge [:PROGRESSES_TO] edges
        session.run("""
            UNWIND $batch AS item
            MATCH (s1:Section {uri: item.s1_uri})
            MATCH (s2:Section {uri: item.s2_uri})
            MERGE (s1)-[r:PROGRESSES_TO]->(s2)
            SET r.transition_type = item.transition_type,
                r.warrant = item.warrant,
                r.confidence = item.confidence,
                r.method = item.method,
                r.updated_at = datetime()
        """, batch=micro_transitions)
        print(f"  → Materialized {len(micro_transitions)} [:PROGRESSES_TO] reasoning transitions.")

        # 4. Materialize Macro-CoT Typed Inter-Document Edges
        print("\n[4/4] Materializing Macro-CoT Inter-Document Reasoning Handshakes...")
        
        # Clean previous macro CoT relationships to ensure idempotency
        session.run("MATCH ()-[r:REMEDIES_DILEMMA|EXTENDS_THEORY|PRECIPITATES|EMPIRICALLY_GROUNDS]->() DELETE r")

        # A. [:REMEDIES_DILEMMA] (Solution section in d1 -> d2 Concept)
        rem_res = session.run("""
            MATCH (d1:Concept)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(d2:Concept)
            WHERE d1 <> d2
              AND (toLower(s.displayName) =~ '.*(solution|mitigat|safeguard|countermeasure|counter-architecture|counter-measure|remedy|intervention|protocol|governance|repayment|action|defense).*'
                   OR s.step_type = 'PRESCRIPTIVE_SOLUTION' OR s:PrescriptiveSolution)
            WITH d1, d2, collect(DISTINCT s.displayName) AS sections, count(*) AS weight
            MERGE (d1)-[r:REMEDIES_DILEMMA]->(d2)
            SET r.weight = weight,
                r.source_sections = sections,
                r.warrant = "Prescribes " + d2.title + " as an architectural safeguard or countermeasure against " + d1.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {rem_res['count']} [:REMEDIES_DILEMMA] links.")

        # B. [:EXTENDS_THEORY] (Mechanism section in d1 -> d2 Concept)
        ext_res = session.run("""
            MATCH (d1:Concept)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(d2:Concept)
            WHERE d1 <> d2
              AND NOT (d1)-[:REMEDIES_DILEMMA]->(d2)
              AND (toLower(s.displayName) =~ '.*(mechanism|anatomy|engine|underlying|process|driver|loop|dynamics|architecture).*'
                   OR s.step_type = 'MECHANISTIC_DEEPEN' OR s:MechanisticDeepen)
            WITH d1, d2, collect(DISTINCT s.displayName) AS sections, count(*) AS weight
            MERGE (d1)-[r:EXTENDS_THEORY]->(d2)
            SET r.weight = weight,
                r.source_sections = sections,
                r.warrant = d1.title + " incorporates foundational causal mechanics from " + d2.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {ext_res['count']} [:EXTENDS_THEORY] links.")

        # C. [:PRECIPITATES] (Trap/Pathology section in d1 -> d2 Concept)
        prec_res = session.run("""
            MATCH (d1:Concept)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(d2:Concept)
            WHERE d1 <> d2
              AND NOT (d1)-[:REMEDIES_DILEMMA]->(d2)
              AND NOT (d1)-[:EXTENDS_THEORY]->(d2)
              AND (toLower(s.displayName) =~ '.*(trap|failure|misattribution|illusion|collapse|offloading|fatigue|debt|pathology|crisis|dilemma|vulnerability).*'
                   OR s.step_type IN ['MANIFESTATION_TRAP', 'DILEMMA_PROBLEM'] OR s:ManifestationTrap OR s:DilemmaProblem)
            WITH d1, d2, collect(DISTINCT s.displayName) AS sections, count(*) AS weight
            MERGE (d1)-[r:PRECIPITATES]->(d2)
            SET r.weight = weight,
                r.source_sections = sections,
                r.warrant = d1.title + " precipitates or manifests as " + d2.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {prec_res['count']} [:PRECIPITATES] links.")

        # D. [:EMPIRICALLY_GROUNDS] (Source -> Concept)
        src_res = session.run("""
            MATCH (src:Source)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(tgt:Concept)
            WITH src, tgt, collect(DISTINCT s.displayName) AS sections, count(*) AS weight
            MERGE (src)-[r:EMPIRICALLY_GROUNDS]->(tgt)
            SET r.weight = weight,
                r.source_sections = sections,
                r.warrant = src.title + " provides primary empirical grounding and citations for " + tgt.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {src_res['count']} [:EMPIRICALLY_GROUNDS] citations.")

    elapsed = time.time() - start_time
    print("\n=================================================================")
    print(f"  [✓] Dual-Flow CoT Extraction Complete in {elapsed:.2f}s!")
    print("=================================================================")

def main():
    parser = argparse.ArgumentParser(description="Extract Dual-Flow Chain of Thought into Neo4j")
    parser.add_argument("--uri", default=DEFAULT_URI, help="Neo4j Bolt URI")
    parser.add_argument("--user", default=DEFAULT_USER, help="Neo4j username")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Neo4j password")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="Neo4j database name")
    parser.add_argument("--skip-neural", action="store_true", help="Skip Ollama neural fallback (AST heuristics only)")
    parser.add_argument("--max-neural", type=int, default=50, help="Maximum number of live neural inference calls (default: 50)")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama base URL")
    parser.add_argument("--model", default=DEFAULT_OLLAMA_MODEL, help="Ollama model for neural warrant extraction")
    args = parser.parse_args()

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password), max_connection_lifetime=60)
    try:
        extract_and_sync_cot(
            driver,
            database=args.database,
            skip_neural=args.skip_neural,
            max_neural=args.max_neural,
            ollama_url=args.ollama_url,
            ollama_model=args.model,
        )
    finally:
        driver.close()

if __name__ == "__main__":
    main()
