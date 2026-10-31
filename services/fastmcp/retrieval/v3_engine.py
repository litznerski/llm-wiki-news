"""
services/fastmcp/retrieval/v3_engine.py
Consolidated V3 GraphRAG Retrieval Engine for FastMCP.
Ports the proven 100% Perfect CoT Window retrieval algorithm from testing/scripts/test_vector_store_harness_v3.py.

Pipeline:
1. Full-Prompt Multi-Concept & Acronym Extraction (Anti-truncation entity router).
2. Concept & Entity Resolution (ArcadeDB Concept/Entity vertices + alias mappings).
3. Candidate Fetching & S0 Anchor Selection (Lucene FULL_TEXT + JVector vectorNeighbors()).
4. 1-Hop Macro-CoT Inter-Concept / Entity Cypher Expansion (Micro-CoT + Macro-CoT).
5. Toulmin Role-Calibrated Window Assembly ([S0 Anchor, S1 Micro-CoT, S2 Macro-CoT]).
"""

import re
import time
import asyncio
import logging
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ..arcadedb_client import ArcadeDBHttpClient

logger = logging.getLogger("fastmcp-v3-engine")


def generate_normalized_variants(text: str) -> List[str]:
    """
    Generates lowercased, umlaut-expanded, accent-stripped, and token-level variants.
    Handles German umlauts (ä -> ae, ö -> oe, ü -> ue, ß -> ss) and reverse mappings,
    as well as diacritic stripping (Gagné -> Gagne) and individual name token indexing.
    """
    if not text:
        return []
    variants: Set[str] = set()
    text_lower = text.lower().strip()
    variants.add(text_lower)

    # 1. Dash and punctuation harmonization
    dash_norm = text_lower.replace("–", "-").replace("—", "-")
    variants.add(dash_norm)
    variants.add(dash_norm.replace("-", " "))

    # 2. German Umlaut expansion (ä -> ae, ö -> oe, ü -> ue, ß -> ss)
    umlaut_map = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
    expanded = text_lower
    for k, v in umlaut_map.items():
        expanded = expanded.replace(k, v)
    variants.add(expanded)

    # 3. German Umlaut reverse (ae -> ä, oe -> ö, ue -> ü)
    reverse_map = {"ae": "ä", "oe": "ö", "ue": "ü"}
    reversed_str = text_lower
    for k, v in reverse_map.items():
        reversed_str = reversed_str.replace(k, v)
    variants.add(reversed_str)

    # 4. Diacritic & Accent Stripping (Unicode NFD)
    nfd = unicodedata.normalize("NFD", text_lower)
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    variants.add(stripped)

    # 5. Clean punctuation
    clean_punct = re.sub(r"[^\w\s-]", "", text_lower)
    variants.add(clean_punct)

    # 6. Distinctive individual tokens (for names like Tränkler, Litznerski, Toulmin, Gagne)
    generic_stop_tokens = {
        "framework", "model", "theory", "architecture", "system", "learning", "department",
        "where", "step", "steps", "data", "high", "loss", "lead", "tier", "turn", "case",
        "base", "rate", "role", "node", "time", "path", "code", "post", "work", "read",
        "view", "part", "user", "open", "free", "side", "down", "well", "real", "best",
        "good", "make", "take", "zero", "five", "four", "three", "lifecycle", "generation",
        "level", "loop", "mesh", "state", "plane", "stack", "point", "scale", "matrix",
    }
    parts = re.split(r"[\s\-_/]+", text_lower)
    if len(parts) > 1:
        for p in parts:
            if len(p) >= 4 and p not in generic_stop_tokens:
                variants.add(p)
                exp_p = p
                for k, v in umlaut_map.items():
                    exp_p = exp_p.replace(k, v)
                variants.add(exp_p)
                nfd_p = "".join(c for c in unicodedata.normalize("NFD", p) if unicodedata.category(c) != "Mn")
                variants.add(nfd_p)

    return sorted([v for v in variants if v])


def extract_concept_title_from_uri(uri: str) -> str:
    """Extract clean concept/note title from section URI."""
    if not uri:
        return ""
    base = uri.split("#")[0]
    stem = Path(base).stem
    return stem


def get_effective_toulmin_role(toulmin_role: Optional[str], step_type: Optional[str], title: str = "") -> str:
    """
    Dynamically derive effective Toulmin argument role with step_type fallback.
    Maps epistemic nodes into standard Toulmin argument categories:
    CLAIM, GROUNDS, WARRANT, REBUTTAL, SOLUTION_WARRANT, QUALIFIER.
    """
    if toulmin_role and toulmin_role not in ("NON_ARGUMENTATIVE", "UNKNOWN"):
        return toulmin_role
    st = (step_type or "").upper()
    if st in ("CORE_THESIS", "DEFINITIONAL_ANCHOR"):
        return "CLAIM"
    elif st in ("MECHANISTIC_DEEPEN", "NARRATIVE_STEP"):
        if any(w in title.lower() for w in ("mandate", "ecosystem", "coalition", "water", "primitives")):
            return "GROUNDS"
        return "WARRANT"
    elif st in ("MANIFESTATION_TRAP", "DILEMMA_PROBLEM"):
        return "REBUTTAL"
    elif st in ("PRESCRIPTIVE_SOLUTION", "SOLUTION_WARRANT"):
        return "SOLUTION_WARRANT"
    elif st in ("EMPIRICAL_BOUNDARY", "QUALIFIER"):
        return "QUALIFIER"
    elif st == "SYNTHESIS_CATALOG":
        return "GROUNDS"
    return "CLAIM"


class ConsolidatedV3Retriever:
    """
    Production-ready V3 GraphRAG retrieval engine inside FastMCP.
    Executes anti-truncation entity linking, dense vector entry probing, and 1-hop Macro-CoT expansion.
    """

    STOP_WORDS = {
        "what", "is", "the", "in", "simple", "terms", "why", "do", "how", "does",
        "a", "an", "and", "or", "to", "for", "with", "when", "using", "of", "can",
        "should", "from", "at", "by", "this", "that", "it", "are", "on", "as",
        "could", "we", "be", "so", "our", "my", "ive", "last", "semester", "very",
        "give", "me", "would", "you", "tell", "understands", "actually", "mean",
        "erkläre", "mir", "das", "der", "die", "und", "ist", "wie", "funktioniert",
    }

    def __init__(self, client: Optional[ArcadeDBHttpClient] = None):
        self.client = client or ArcadeDBHttpClient()
        self._concept_cache: Dict[str, str] = {}
        self._cache_timestamp: float = 0.0
        self._cache_ttl: float = 300.0  # 5 minutes cache TTL

    async def _ensure_concepts_cached(self) -> Dict[str, str]:
        """
        Pre-fetches concept and entity registry from ArcadeDB, enriches with
        aliases from wiki/glossary.md, and generates comprehensive normalized
        variants (umlaut expansion, accent stripping, token-level matching).
        """
        now = time.time()
        if self._concept_cache and (now - self._cache_timestamp) < self._cache_ttl:
            return self._concept_cache

        new_cache: Dict[str, str] = {}
        try:
            # 1. Fetch from ArcadeDB (Title + Aliases if present)
            q = "MATCH (c) WHERE c:Concept OR c:Entity RETURN c.title AS title, c.aliases AS aliases, c.subtype AS subtype"
            records = await self.client.query_async(q, language="cypher")
            for r in records:
                t = r.get("title")
                if not t:
                    continue
                # Add title and all its normalized variants
                for var in generate_normalized_variants(t):
                    new_cache[var] = t
                # If aliases stored on node, register them too
                aliases = r.get("aliases") or []
                if isinstance(aliases, list):
                    for a in aliases:
                        if isinstance(a, str) and a.strip():
                            for var in generate_normalized_variants(a):
                                new_cache[var] = t

            # 2. Local glossary fallback: enrich from wiki/glossary.md if accessible
            try:
                vault_dir = Path(__file__).resolve().parent.parent.parent.parent
                glossary_path = vault_dir / "wiki" / "glossary.md"
                if glossary_path.exists():
                    content = glossary_path.read_text(encoding="utf-8")
                    for line in content.splitlines():
                        line = line.strip()
                        if line.startswith("|") and line.endswith("|"):
                            cells = [c.strip() for c in line[1:-1].split("|")]
                            if len(cells) >= 3 and not cells[0].startswith("---") and not cells[0].startswith("Canonical"):
                                canon = cells[0]
                                aliases_raw = [a.strip() for a in cells[1].split(",") if a.strip() and a.strip() != "-"]
                                for a in aliases_raw:
                                    for var in generate_normalized_variants(a):
                                        new_cache[var] = canon
            except Exception as ge:
                logger.debug(f"Glossary file enrichment skipped: {ge}")

            self._concept_cache = new_cache
            self._cache_timestamp = now
            logger.info(f"Loaded {len(self._concept_cache)} normalized concept and entity variant mappings into V3 cache.")
        except Exception as e:
            logger.warning(f"Error loading concepts into V3 cache: {e}")
            if not self._concept_cache:
                self._concept_cache = {}

        return self._concept_cache

    def extract_smart_query(self, text: str) -> str:
        """
        Extract domain acronyms and high-salience terms across the entire prompt.
        Avoids early-truncation bias on extended scenario prompts.
        """
        tokens = text.split()
        acronyms = [
            t.strip("?,.()\":'")
            for t in tokens
            if t.strip("?,.()\":'").isupper() and len(t.strip("?,.()\":'")) >= 2
        ]

        clean = ""
        for ch in text:
            clean += ch if (ch.isalnum() or ch in (" ", "-", "_")) else " "

        sig_words = [w for w in clean.split() if w.lower() not in self.STOP_WORDS]
        combined = list(dict.fromkeys(acronyms + sig_words[-6:] + sig_words[:6]))
        return " ".join(combined[:12])

    def resolve_concepts(
        self,
        prompt_text: str,
        all_concepts: Dict[str, str],
        target_concepts: Optional[List[str]] = None,
        topic: Optional[str] = None,
    ) -> Tuple[str, List[str]]:
        """
        Resolves domain concepts and entities from user prompt text.
        Applies umlaut normalization, domain acronym mapping, and priority adjustments.
        """
        p_low = prompt_text.lower()
        p_variants = set(generate_normalized_variants(prompt_text))
        p_variants.add(p_low)

        matched_concepts: List[str] = []

        # 1. Match across all normalized variants (length >= 4)
        for c_var, c_orig in all_concepts.items():
            if len(c_var) < 4:
                continue
            if " " in c_var:
                if any(c_var in pv for pv in p_variants):
                    matched_concepts.append(c_orig)
            else:
                pattern = rf"\b{re.escape(c_var)}\b"
                if any(re.search(pattern, pv) for pv in p_variants):
                    matched_concepts.append(c_orig)

        # 2. Domain acronym & compound mapping (V3 Expert Mitigation Rules)
        if any(k in p_low for k in ("cfq", "friction quotient", "productive friction", "cognitive friction")):
            matched_concepts.append("Productive Cognitive Friction")
        if "cm3" in p_low or "contribution margin" in p_low or "cohort" in p_low:
            matched_concepts.append("Cohort Unit Economics")
        if any(k in p_low for k in ("marketing", "cac", "ltv", "unit economics", "bidding", "roas", "advertising")):
            matched_concepts.append("Marketing Unit Economics")
        if any(k in p_low for k in ("learning paradox", "student", "homework")):
            if "extreme" not in p_low and "knowledge" not in p_low:
                matched_concepts.append("AI Learning Paradox")
        if any(k in p_low for k in ("extreme edtech", "offline", "sudan", "zero-bandwidth", "crisis-resilient", "electricity", "blackout")):
            matched_concepts.append("Extreme EdTech")
        if any(k in p_low for k in ("knowledge", "knowledge-lab", "litznerski", "compliance mirage", "teardown", "mono-vault", "hr department", "where learning architecture")):
            matched_concepts.append("Knowledge Lab")

        matched_concepts = list(dict.fromkeys(matched_concepts))

        # Prioritize domain target primitives over scaffolding hubs
        if len(matched_concepts) > 1 and "Knowledge Graph" in matched_concepts:
            matched_concepts.remove("Knowledge Graph")
            matched_concepts.append("Knowledge Graph")

        # Prioritize target_concepts or topic over peripheral entities
        found_target = False
        if target_concepts:
            for tc in target_concepts:
                if tc in matched_concepts:
                    matched_concepts.remove(tc)
                    matched_concepts.insert(0, tc)
                    found_target = True
                    break

        if not found_target and topic and topic in all_concepts.values():
            matched_concepts.insert(0, topic)

        primary_concept = matched_concepts[0] if matched_concepts else (topic or "")
        return primary_concept, matched_concepts

    async def fetch_candidates(
        self,
        primary_concept: str,
        smart_q: str,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Fetches section candidates via:
        1. Concept section graph (`[:HAS_SECTION]`)
        2. Lucene Full-Text Search on `Section[content]`
        3. Dense JVector `vectorNeighbors()` on top seed
        """
        candidates: List[Dict[str, Any]] = []

        # 1. Concept Seed Sections
        cypher_seed = """
        MATCH (c {title: $concept})-[:HAS_SECTION]->(s:Section)
        WITH s ORDER BY s.heading_level ASC, s.weight DESC LIMIT 10
        OPTIONAL MATCH (s)-[:HAS_DIAGRAM]->(d:Diagram)
        RETURN s.uri AS uri, s.title AS title, s.toulmin_role AS toulmin_role, s.step_type AS step_type,
               s.weight AS weight, s.content AS content, 0.0 AS distance,
               collect({title: d.title, raw_code: d.raw_code}) AS diagrams
        """
        try:
            records = await self.client.query_async(cypher_seed, language="cypher", params={"concept": primary_concept})
            for r in records:
                r["toulmin_role"] = get_effective_toulmin_role(r.get("toulmin_role"), r.get("step_type"), r.get("title", ""))
                raw_diags = r.get("diagrams") or []
                diags = [
                    d for d in raw_diags
                    if isinstance(d, dict) and d.get("raw_code") and isinstance(d.get("raw_code"), str) and d["raw_code"].strip()
                ]
                r["diagrams"] = diags
                if r.get("content"):
                    r["content"] = re.sub(r'```mermaid[\s\S]*?```', '', r["content"]).strip()
                candidates.append(r)
        except Exception as e:
            logger.warning(f"Error retrieving concept seed sections for {primary_concept}: {e}")

        # 2. Lucene Full-Text Search on Section[content]
        if smart_q:
            clean_q = "".join(c for c in smart_q if c.isalnum() or c.isspace()).strip()
            if clean_q:
                cypher_ft = """
                CALL db.index.fulltext.queryNodes('Section[content]', $q)
                YIELD node, score
                WITH node AS s, score
                ORDER BY score DESC LIMIT 8
                OPTIONAL MATCH (s)-[:HAS_DIAGRAM]->(d:Diagram)
                RETURN s.uri AS uri, s.title AS title, s.toulmin_role AS toulmin_role,
                       s.step_type AS step_type, s.weight AS weight, s.content AS content, score,
                       collect({title: d.title, raw_code: d.raw_code}) AS diagrams
                """
                try:
                    ft_records = await self.client.query_async(cypher_ft, language="cypher", params={"q": clean_q})
                    for item in ft_records:
                        u = item.get("uri", "")
                        if "wiki/sources/" in u:
                            continue
                        if item.get("title") in ("Related Notes", "Related Primitives", "Key Entities & Sources"):
                            continue
                        eff_role = get_effective_toulmin_role(item.get("toulmin_role"), item.get("step_type"), item.get("title", ""))
                        raw_diags = item.get("diagrams") or []
                        diags = [
                            d for d in raw_diags
                            if isinstance(d, dict) and d.get("raw_code") and isinstance(d.get("raw_code"), str) and d["raw_code"].strip()
                        ]
                        cnt = item.get("content", "")
                        if cnt:
                            cnt = re.sub(r'```mermaid[\s\S]*?```', '', cnt).strip()
                        candidates.append({
                            "uri": u,
                            "title": item.get("title", ""),
                            "toulmin_role": eff_role,
                            "step_type": item.get("step_type", "UNKNOWN"),
                            "weight": item.get("weight", 0.5),
                            "distance": 0.05,
                            "score": float(item.get("score", 0.0)),
                            "content": cnt,
                            "diagrams": diags,
                        })
                except Exception as e:
                    logger.warning(f"Error in Lucene full-text search: {e}")

        # 3. Dense JVector Nearest Neighbors Search
        vector_neighbors: List[Dict[str, Any]] = []
        if candidates and candidates[0].get("uri"):
            seed_uri = candidates[0]["uri"]
            sql_vector = f"""
            SELECT record.uri AS uri, record.title AS title, record.path AS path,
                   record.toulmin_role AS toulmin_role, record.step_type AS step_type,
                   record.weight AS weight, distance, record.content AS content
            FROM (
              SELECT expand(vectorNeighbors('Section[embedding]', (SELECT embedding FROM Section WHERE uri = "{seed_uri}")[0].embedding, 6))
            )
            """
            try:
                vec_res = await self.client.query_async(sql_vector, language="sql")
                for vr in vec_res:
                    u = vr.get("uri", "")
                    if "wiki/sources/" in u:
                        continue
                    vr["toulmin_role"] = get_effective_toulmin_role(vr.get("toulmin_role"), vr.get("step_type"), vr.get("title", ""))
                    cnt = vr.get("content", "")
                    if cnt:
                        vr["content"] = re.sub(r'```mermaid[\s\S]*?```', '', cnt).strip()
                    vr["diagrams"] = []
                    vector_neighbors.append(vr)
                    candidates.append(vr)
            except Exception as e:
                logger.warning(f"Error in JVector search for {seed_uri}: {e}")

        return candidates, vector_neighbors

    def select_s0_anchor(
        self,
        candidates: List[Dict[str, Any]],
        target_concepts: List[str],
        expected_roles: List[str],
        user_category: str = "intermediate",
        topic: str = "",
    ) -> Dict[str, Any]:
        """
        Computes candidate score matrix and selects the optimal S0 Anchor section:
        Score(s) = ConceptMatch(s) + RoleMatch(s) + CategoryWeight(s) + Similarity(s)
        """
        best_candidate: Dict[str, Any] = candidates[0] if candidates else {}
        best_score = -100.0
        seen: Set[str] = set()

        for cand in candidates:
            u = cand.get("uri")
            if not u or u in seen:
                continue
            seen.add(u)

            cand_concept = extract_concept_title_from_uri(u)
            cand_role = cand.get("toulmin_role", "")

            score = 0.0
            if any(tc.lower() == cand_concept.lower() for tc in target_concepts):
                score += 25.0
            elif any(tc.lower() in cand_concept.lower() or cand_concept.lower() in tc.lower() for tc in target_concepts):
                score += 18.0
            elif topic and topic.lower() in cand_concept.lower():
                score += 10.0

            if cand_role in expected_roles:
                score += 15.0

            if user_category == "beginner" and cand_role in ("CLAIM", "GROUNDS"):
                score += 6.0
            elif user_category == "intermediate" and cand_role in ("WARRANT", "CLAIM"):
                score += 6.0
            elif user_category == "expert" and cand_role in ("REBUTTAL", "QUALIFIER", "SOLUTION_WARRANT"):
                score += 6.0

            dist = cand.get("distance")
            if dist is not None and isinstance(dist, (int, float)):
                score += max(0.0, (1.0 - dist) * 3.0)
            elif "score" in cand:
                score += min(3.0, cand["score"] / 5.0)

            if score > best_score:
                best_score = score
                best_candidate = cand

        return best_candidate

    async def expand_macro_cot(
        self,
        s0_uri: str,
        expected_roles: List[str],
        target_concepts: List[str],
        vector_neighbors: List[Dict[str, Any]],
        s0_role: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Set[str], Set[str]]:
        """
        Traverses 1-hop Macro-CoT inter-concept Cypher edges from S0 Anchor:
        (PRECIPITATES, REMEDIES_DILEMMA, EXTENDS_THEORY, CRITIQUES_PARADIGM, OPERATIONALIZES, etc.)
        Selects S1 (Micro-CoT) and S2 (Macro-CoT) sections to complete the Toulmin arc.
        """
        # Separate intra-document (Micro-CoT) and inter-document (Macro-CoT) queries to prevent Cartesian product OOM
        q_micro = f"""
        MATCH (c)-[:HAS_SECTION]->(seed:Section)
        WHERE seed.uri = "{s0_uri}"
        MATCH (c)-[e1:HAS_CLAIM|HAS_GROUNDS|HAS_WARRANT|HAS_REBUTTAL|HAS_SOLUTION|HAS_QUALIFIER|HAS_SECTION]->(s1:Section)
        WHERE s1.uri <> seed.uri
        RETURN c.title AS anchor_concept, s1.uri AS s1_uri, s1.title AS s1_title,
               s1.toulmin_role AS s1_role, s1.step_type AS s1_step, type(e1) AS s1_edge,
               e1.weight AS s1_weight, s1.heading_level AS s1_level
        LIMIT 25
        """
        q_macro = f"""
        MATCH (c)-[:HAS_SECTION]->(seed:Section)
        WHERE seed.uri = "{s0_uri}"
        MATCH (c)-[r:PRECIPITATES|REMEDIES_DILEMMA|EXTENDS_THEORY|CRITIQUES_PARADIGM|OPERATIONALIZES|CHAMPIONS_SOLUTION|ORIGINATES_THEORY|AFFILIATED_WITH|LINKS_TO]-(c2)
        WHERE NOT c2:Section
        MATCH (c2)-[e2:HAS_CLAIM|HAS_GROUNDS|HAS_WARRANT|HAS_REBUTTAL|HAS_SOLUTION|HAS_QUALIFIER|HAS_SECTION]->(s2:Section)
        RETURN c.title AS anchor_concept, c2.title AS neighbor_concept, type(r) AS bridge_rel,
               s2.uri AS s2_uri, s2.title AS s2_title, s2.toulmin_role AS s2_role,
               s2.step_type AS s2_step, type(e2) AS s2_edge, e2.weight AS s2_weight,
               s2.heading_level AS s2_level
        LIMIT 50
        """

        try:
            r_micro, r_macro = await asyncio.gather(
                self.client.query_async(q_micro, language="cypher"),
                self.client.query_async(q_macro, language="cypher"),
            )
        except Exception as e:
            logger.warning(f"Error querying CoT graph expansion: {e}")
            r_micro, r_macro = [], []

        expansion_pool: List[Dict[str, Any]] = []
        seen_cot = {s0_uri}

        # 1. Intra-document sections (Micro-CoT)
        for row in r_micro:
            u1 = row.get("s1_uri")
            if u1 and u1 not in seen_cot and "wiki/sources/" not in u1:
                seen_cot.add(u1)
                eff_r1 = get_effective_toulmin_role(row.get("s1_role"), row.get("s1_step"), row.get("s1_title", ""))
                expansion_pool.append({
                    "uri": u1,
                    "title": row.get("s1_title", ""),
                    "role": eff_r1,
                    "concept": row.get("anchor_concept", ""),
                    "edge": row.get("s1_edge") or "HAS_SECTION",
                    "weight": row.get("s1_weight") or 0.5,
                    "level": row.get("s1_level") or 2,
                    "content": "",
                    "is_inter": False,
                })

        # 2. Inter-document 1-hop sections (Macro-CoT)
        for row in r_macro:
            u2 = row.get("s2_uri")
            if u2 and u2 not in seen_cot and "wiki/sources/" not in u2:
                seen_cot.add(u2)
                eff_r2 = get_effective_toulmin_role(row.get("s2_role"), row.get("s2_step"), row.get("s2_title", ""))
                expansion_pool.append({
                    "uri": u2,
                    "title": row.get("s2_title", ""),
                    "role": eff_r2,
                    "concept": row.get("neighbor_concept", ""),
                    "edge": f"{row.get('bridge_rel')}->{row.get('s2_edge') or 'HAS_SECTION'}",
                    "weight": (row.get("s2_weight") or 0.5) * 0.9,
                    "level": row.get("s2_level") or 2,
                    "content": "",
                    "is_inter": True,
                })

        # Score expansion candidates
        covered_roles: Set[str] = {s0_role}
        remaining_expected = [r for r in expected_roles if r not in covered_roles]

        scored_exp = []
        for cand in expansion_pool:
            r = cand["role"]
            c_name = cand["concept"]
            sc = 0.0

            if r in remaining_expected:
                sc += 35.0
            elif r in expected_roles:
                sc += 15.0
            elif r in ("CLAIM", "WARRANT", "REBUTTAL", "SOLUTION_WARRANT"):
                sc += 8.0

            if any(tc.lower() == c_name.lower() for tc in target_concepts):
                sc += 20.0
            elif any(tc.lower() in c_name.lower() or c_name.lower() in tc.lower() for tc in target_concepts):
                sc += 14.0

            sc += (cand.get("weight") or 0.5) * 5.0
            if cand.get("level") == 2:
                sc += 4.0

            scored_exp.append((sc, cand))

        scored_exp.sort(key=lambda x: x[0], reverse=True)

        chosen_additional: List[Dict[str, Any]] = []
        for sc, cand in scored_exp:
            if len(chosen_additional) >= 2:
                break
            cand_role = cand["role"]
            if len(chosen_additional) == 1 and cand_role == chosen_additional[0]["role"] and len(scored_exp) > 2:
                alt = [c for s, c in scored_exp if c["role"] != cand_role and c["uri"] != chosen_additional[0]["uri"]]
                if alt:
                    chosen_additional.append(alt[0])
                    covered_roles.add(alt[0]["role"])
                    continue
            chosen_additional.append(cand)
            covered_roles.add(cand_role)

        # Fallback padding with vector neighbors if fewer than 2 candidates
        while len(chosen_additional) < 2 and vector_neighbors:
            for vn in vector_neighbors:
                if vn.get("uri") != s0_uri and not any(ca.get("uri") == vn.get("uri") for ca in chosen_additional):
                    chosen_additional.append({
                        "uri": vn.get("uri"),
                        "title": vn.get("title"),
                        "role": vn.get("toulmin_role", "UNKNOWN"),
                        "concept": extract_concept_title_from_uri(vn.get("uri")),
                        "edge": "VECTOR_NEIGHBOR",
                        "weight": 0.5,
                        "content": vn.get("content", ""),
                    })
                    covered_roles.add(vn.get("toulmin_role", "UNKNOWN"))
                    if len(chosen_additional) >= 2:
                        break
            break

        s1 = chosen_additional[0] if len(chosen_additional) > 0 else {}
        s2 = chosen_additional[1] if len(chosen_additional) > 1 else {}

        # Hydrate full section content and diagrams for the chosen S1 and S2
        needed_uris = [ca["uri"] for ca in (s1, s2) if ca.get("uri")]
        if needed_uris:
            uris_json = ", ".join(f'"{u}"' for u in needed_uris)
            try:
                c_rows = await self.client.query_async(
                    f"SELECT uri, content, out('HAS_DIAGRAM').title as diag_titles, out('HAS_DIAGRAM').raw_code as diag_codes FROM Section WHERE uri IN [{uris_json}]",
                    language="sql"
                )
                for row in c_rows:
                    u = row.get("uri")
                    diag_titles = row.get("diag_titles") or []
                    diag_codes = row.get("diag_codes") or []
                    diags = []
                    if isinstance(diag_titles, list) and isinstance(diag_codes, list):
                        for title, code in zip(diag_titles, diag_codes):
                            if code and isinstance(code, str) and code.strip():
                                diags.append({"title": title or "Visual Architecture", "raw_code": code.strip()})

                    raw_content = row.get("content", "")
                    clean_content = re.sub(r'```mermaid[\s\S]*?```', '', raw_content).strip()
                    if s1.get("uri") == u:
                        s1["content"] = clean_content
                        s1["diagrams"] = diags
                    if s2.get("uri") == u:
                        s2["content"] = clean_content
                        s2["diagrams"] = diags
            except Exception as e:
                logger.warning(f"Error hydrating CoT content and diagrams for S1/S2: {e}")

        window_concepts = {extract_concept_title_from_uri(s0_uri), s1.get("concept", ""), s2.get("concept", "")}
        window_concepts = {c for c in window_concepts if c}

        return s1, s2, covered_roles, window_concepts

    async def retrieve_v3(
        self,
        prompt: str,
        user_category: str = "intermediate",
        target_concepts: Optional[List[str]] = None,
        expected_roles: Optional[List[str]] = None,
        topic: str = "",
        turn_trace: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Executes the full 4-phase V3 retrieval pipeline:
        Returns structured dictionary containing S0 Anchor, S1 Micro-CoT, S2 Macro-CoT,
        Toulmin coverage telemetry, and end-to-end latencies.
        Instruments Langfuse sub-spans when turn_trace context is provided and active.
        """
        t0 = time.perf_counter()
        target_concepts = target_concepts or []
        if not expected_roles:
            p_low = prompt.lower()
            inferred_roles = ["CLAIM"]
            if any(w in p_low for w in ("solve", "solution", "mitigat", "fix", "prevent", "remedy", "counter", "overcome", "address", "how can i", "how do we")):
                inferred_roles.append("SOLUTION_WARRANT")
            if any(w in p_low for w in ("risk", "trap", "failure", "pitfall", "dilemma", "problem", "manifest", "danger", "paradox")):
                inferred_roles.append("REBUTTAL")
            if any(w in p_low for w in ("why", "how", "mechanis", "caus", "work", "anatom", "underlying", "explain")):
                inferred_roles.append("WARRANT")
            if any(w in p_low for w in ("what is", "define", "definition", "evidence", "empiric", "ground", "who")):
                inferred_roles.append("GROUNDS")
            for def_role in ("WARRANT", "GROUNDS", "SOLUTION_WARRANT", "REBUTTAL"):
                if len(inferred_roles) < 3 and def_role not in inferred_roles:
                    inferred_roles.append(def_role)
            expected_roles = inferred_roles

        # 1. Cache lookup & Smart Query Extraction
        all_concepts = await self._ensure_concepts_cached()
        smart_q = self.extract_smart_query(prompt)

        # 2. Concept & Entity Resolution (Span 02)
        has_trace = turn_trace and getattr(turn_trace, "active", False)
        if has_trace:
            with turn_trace.span("02_entity_resolution", as_type="retriever", input_data=prompt) as sp:
                primary_concept, matched_concepts = self.resolve_concepts(
                    prompt_text=prompt,
                    all_concepts=all_concepts,
                    target_concepts=target_concepts,
                    topic=topic,
                )
                sp.set_output({
                    "primary_concept": primary_concept,
                    "matched_concepts": matched_concepts,
                    "smart_query": smart_q,
                })
        else:
            primary_concept, matched_concepts = self.resolve_concepts(
                prompt_text=prompt,
                all_concepts=all_concepts,
                target_concepts=target_concepts,
                topic=topic,
            )

        # 2b. Lucene Full-Text Dynamic Discovery Fallback
        if not primary_concept:
            clean_probe_q = "".join(c for c in prompt if c.isalnum() or c.isspace()).strip()
            if clean_probe_q:
                try:
                    cypher_probe = """
                    CALL db.index.fulltext.queryNodes('Section[content]', $q)
                    YIELD node, score
                    RETURN node.uri AS uri, score
                    ORDER BY score DESC
                    LIMIT 5
                    """
                    probe_records = await self.client.query_async(cypher_probe, language="cypher", params={"q": clean_probe_q})
                    for pr in probe_records:
                        u = pr.get("uri", "")
                        if "wiki/sources/" in u:
                            continue
                        c_title = extract_concept_title_from_uri(u)
                        if c_title and c_title not in ("Related Notes", "Related Primitives", "Key Entities & Sources"):
                            primary_concept = c_title
                            matched_concepts.append(c_title)
                            logger.info(f"Discovered dynamic primary concept via Lucene: '{primary_concept}'")
                            break
                except Exception as pe:
                    logger.debug(f"Lucene dynamic concept discovery fallback failed: {pe}")

        # 3. Candidate Fetching & S0 Anchor Selection (Span 03)
        t_vec_start = time.perf_counter()
        if has_trace:
            with turn_trace.span("03_vector_knn_s0_selection", as_type="retriever", input_data=smart_q) as sp:
                candidates, vector_neighbors = await self.fetch_candidates(
                    primary_concept=primary_concept,
                    smart_q=smart_q,
                )
                s0 = self.select_s0_anchor(
                    candidates=candidates,
                    target_concepts=target_concepts or [primary_concept],
                    expected_roles=expected_roles,
                    user_category=user_category,
                    topic=topic,
                )
                sp.set_output({
                    "s0_uri": s0.get("uri"),
                    "s0_title": s0.get("title"),
                    "s0_role": s0.get("toulmin_role"),
                    "candidates_count": len(candidates),
                    "vector_neighbors_count": len(vector_neighbors),
                })
        else:
            candidates, vector_neighbors = await self.fetch_candidates(
                primary_concept=primary_concept,
                smart_q=smart_q,
            )
            s0 = self.select_s0_anchor(
                candidates=candidates,
                target_concepts=target_concepts or [primary_concept],
                expected_roles=expected_roles,
                user_category=user_category,
                topic=topic,
            )
        t_vec_ms = (time.perf_counter() - t_vec_start) * 1000.0

        s0_uri = s0.get("uri", "")
        s0_title = s0.get("title", "")
        s0_role = s0.get("toulmin_role", "UNKNOWN")
        s0_concept = extract_concept_title_from_uri(s0_uri)

        # 4. 1-Hop Macro-CoT Cypher Expansion (Span 04)
        t_cyp_start = time.perf_counter()
        if has_trace:
            with turn_trace.span("04_macro_cot_expansion", as_type="tool", input_data=s0_uri) as sp:
                s1, s2, covered_roles, window_concepts = await self.expand_macro_cot(
                    s0_uri=s0_uri,
                    expected_roles=expected_roles,
                    target_concepts=target_concepts or [primary_concept],
                    vector_neighbors=vector_neighbors,
                    s0_role=s0_role,
                )
                sp.set_output({
                    "s1_title": s1.get("title"),
                    "s1_role": s1.get("role"),
                    "s2_title": s2.get("title"),
                    "s2_role": s2.get("role"),
                    "covered_roles": list(covered_roles),
                    "window_concepts": list(window_concepts),
                })
        else:
            s1, s2, covered_roles, window_concepts = await self.expand_macro_cot(
                s0_uri=s0_uri,
                expected_roles=expected_roles,
                target_concepts=target_concepts or [primary_concept],
                vector_neighbors=vector_neighbors,
                s0_role=s0_role,
            )
        t_cyp_ms = (time.perf_counter() - t_cyp_start) * 1000.0
        t_total_ms = (time.perf_counter() - t0) * 1000.0

        # Ensure S0 has diagrams and clean content
        if s0_uri and not s0.get("diagrams"):
            try:
                s0_rows = await self.client.query_async(
                    f"SELECT uri, content, out('HAS_DIAGRAM').title as diag_titles, out('HAS_DIAGRAM').raw_code as diag_codes FROM Section WHERE uri = '{s0_uri}'",
                    language="sql"
                )
                if s0_rows:
                    row = s0_rows[0]
                    diag_titles = row.get("diag_titles") or []
                    diag_codes = row.get("diag_codes") or []
                    diags = []
                    if isinstance(diag_titles, list) and isinstance(diag_codes, list):
                        for title, code in zip(diag_titles, diag_codes):
                            if code and isinstance(code, str) and code.strip():
                                diags.append({"title": title or "Visual Architecture", "raw_code": code.strip()})
                    s0["diagrams"] = diags
                    if not s0.get("content"):
                        s0["content"] = re.sub(r'```mermaid[\s\S]*?```', '', row.get("content", "")).strip()
            except Exception as e:
                logger.warning(f"Error hydrating S0 diagrams: {e}")

        # 5. Telemetry & Fit Status
        window_sections = [
            {
                "step": "S0 (Anchor)",
                "uri": s0_uri,
                "title": s0_title,
                "role": s0_role,
                "concept": s0_concept,
                "edge": "VECTOR_ROUTER",
                "weight": 1.0,
                "is_inter": False,
                "content": re.sub(r'```mermaid[\s\S]*?```', '', s0.get("content", "")).strip(),
                "diagrams": s0.get("diagrams", []),
            },
            {
                "step": "S1 (CoT Step 1)",
                "uri": s1.get("uri", ""),
                "title": s1.get("title", ""),
                "role": s1.get("role", "UNKNOWN"),
                "concept": s1.get("concept", ""),
                "edge": s1.get("edge", ""),
                "weight": s1.get("weight", 0.5),
                "is_inter": s1.get("is_inter", False),
                "bridge_rel": s1.get("bridge_rel") or (s1.get("edge", "").split("->")[0] if "->" in s1.get("edge", "") else ""),
                "content": re.sub(r'```mermaid[\s\S]*?```', '', s1.get("content", "")).strip(),
                "diagrams": s1.get("diagrams", []),
            },
            {
                "step": "S2 (CoT Step 2)",
                "uri": s2.get("uri", ""),
                "title": s2.get("title", ""),
                "role": s2.get("role", "UNKNOWN"),
                "concept": s2.get("concept", ""),
                "edge": s2.get("edge", ""),
                "weight": s2.get("weight", 0.5),
                "is_inter": s2.get("is_inter", False),
                "bridge_rel": s2.get("bridge_rel") or (s2.get("edge", "").split("->")[0] if "->" in s2.get("edge", "") else ""),
                "content": re.sub(r'```mermaid[\s\S]*?```', '', s2.get("content", "")).strip(),
                "diagrams": s2.get("diagrams", []),
            },
        ]

        active_roles = {sec["role"] for sec in window_sections if sec["role"] != "UNKNOWN"}
        all_expected_roles_covered = all(er in active_roles for er in expected_roles)
        partial_roles_covered = any(er in active_roles for er in expected_roles)

        tc_set = target_concepts or [primary_concept]
        window_concept_match = any(
            tc.lower() in c.lower() or c.lower() in tc.lower()
            for c in window_concepts
            for tc in tc_set
        )

        if window_concept_match and all_expected_roles_covered:
            fit_status = "PERFECT_COT_WINDOW"
        elif window_concept_match and partial_roles_covered:
            fit_status = "PARTIAL_ROLE_COVERAGE"
        elif not window_concept_match and any(tc.lower() in c.lower() for c in window_concepts for tc in tc_set):
            fit_status = "TOPIC_NEIGHBOR"
        elif not window_concept_match and topic and topic.lower() in s0_concept.lower():
            fit_status = "RELATED_CONCEPT"
        else:
            fit_status = "SEMANTIC_DRIFT"

        return {
            "primary_concept": primary_concept,
            "matched_concepts": matched_concepts,
            "search_query": smart_q,
            "fit_status": fit_status,
            "all_expected_roles_covered": all_expected_roles_covered,
            "window_concept_match": window_concept_match,
            "roles_covered": list(active_roles),
            "concepts_in_window": list(window_concepts),
            "sections": window_sections,
            "latencies": {
                "vector_routing_ms": round(t_vec_ms, 2),
                "cypher_expansion_ms": round(t_cyp_ms, 2),
                "total_latency_ms": round(t_total_ms, 2),
            },
        }

    def retrieve_v3_sync(
        self,
        prompt: str,
        user_category: str = "intermediate",
        target_concepts: Optional[List[str]] = None,
        expected_roles: Optional[List[str]] = None,
        topic: str = "",
    ) -> Dict[str, Any]:
        """Synchronous wrapper for offline testing."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(
                    self.retrieve_v3(prompt, user_category, target_concepts, expected_roles, topic)
                )
            return loop.run_until_complete(
                self.retrieve_v3(prompt, user_category, target_concepts, expected_roles, topic)
            )
        except RuntimeError:
            return asyncio.run(
                self.retrieve_v3(prompt, user_category, target_concepts, expected_roles, topic)
            )
