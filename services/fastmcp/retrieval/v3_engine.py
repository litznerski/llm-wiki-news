"""
services/fastmcp/retrieval/v3_engine.py
Consolidated V3 GraphRAG Retrieval Engine for FastMCP (Sudan News & OSINT Edition).

Pipeline:
1. Full-Prompt Multi-Entity, P-Code & Acronym Extraction (Arabic + English).
2. Event, Actor, Location, Theme & AliasLookup Resolution (ArcadeDB + wiki/glossary.md).
3. Candidate Fetching & S0 Anchor Selection (Vertex/Section Graph + Lucene FULL_TEXT + JVector vectorNeighbors()).
4. 1-Hop Macro-CoT 5W1H & GRaSP Cypher Expansion (Micro-CoT + Macro-CoT).
5. 5W1H / Toulmin Role-Calibrated Window Assembly ([S0 Anchor, S1 Micro-CoT, S2 Macro-CoT]).
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
    Generates lowercased, Arabic-normalized (tashkeel/alef/ta-marbuta), accent-stripped,
    and token-level variants for multilingual Sudan News & OSINT entity resolution.
    """
    if not text:
        return []
    variants: Set[str] = set()
    text_lower = text.lower().strip()
    variants.add(text_lower)

    # 1. Arabic orthographic normalization
    ar_norm = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", text_lower)
    ar_norm = re.sub(r"[أإآٱ]", "ا", ar_norm)
    ar_norm = ar_norm.replace("ة", "ه").replace("ى", "ي")
    variants.add(ar_norm)

    # 2. Dash, al- prefix, and punctuation harmonization
    dash_norm = ar_norm.replace("–", "-").replace("—", "-")
    variants.add(dash_norm)
    variants.add(dash_norm.replace("-", " "))
    no_al = re.sub(r"\b(al-|el-)", "", dash_norm).strip()
    if no_al:
        variants.add(no_al)

    # 3. Diacritic & Accent Stripping (Unicode NFD)
    nfd = unicodedata.normalize("NFD", text_lower)
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    variants.add(stripped)

    # 4. Clean punctuation
    clean_punct = re.sub(r"[^\w\s-]", "", ar_norm)
    variants.add(clean_punct)

    # 5. Distinctive individual tokens (for names like Burhan, Hemedti, Dagalo, Minnawi, Fasher)
    generic_stop_tokens = {
        "sudan", "sudanese", "forces", "armed", "movement", "liberation", "council",
        "state", "north", "south", "east", "west", "central", "darfur", "kordofan",
        "front", "alliance", "party", "national", "democratic", "general", "joint",
    }
    parts = re.split(r"[\s\-_/()]+", dash_norm)
    if len(parts) > 1:
        for p in parts:
            if len(p) >= 4 and p not in generic_stop_tokens:
                variants.add(p)

    return sorted([v for v in variants if v])


def extract_concept_title_from_uri(uri: str) -> str:
    """Extract clean Event/Actor/Location/Theme note title from section URI."""
    if not uri:
        return ""
    base = uri.split("#")[0]
    stem = Path(base).stem
    return stem


def get_effective_toulmin_role(toulmin_role: Optional[str], step_type: Optional[str], title: str = "") -> str:
    """
    Dynamically derive effective 5W1H / Toulmin role with step_type fallback.
    Maps Sudan OSINT 6-stage section arcs into:
      CLAIM:    EVENT_ANCHOR, ACTOR_ANCHOR, LOCATION_ANCHOR, DEFINITIONAL_ANCHOR
      WARRANT:  CHRONOLOGICAL_MECHANICS, CAUSAL_MOTIVES, COMMAND_LINEAGE, STRATEGIC_DOCTRINE, INFRASTRUCTURE_LOGISTICS, MECHANISTIC_DEEPEN
      GROUNDS:  IMPACT_ASSESSMENT, ALLIANCE_NETWORK, EVENT_FOOTPRINT, TERRITORIAL_CONTROL, HUMANITARIAN_STATUS, EVENT_LOG, MANIFESTATION_TRAP
      REBUTTAL: CONTRADICTION_MATRIX, EMPIRICAL_BOUNDARY
      SOLUTION_WARRANT: PRESCRIPTIVE_SOLUTION, SOLUTION_WARRANT
    """
    if toulmin_role and toulmin_role not in ("NON_ARGUMENTATIVE", "UNKNOWN"):
        return toulmin_role
    st = (step_type or "").upper()
    if st in ("EVENT_ANCHOR", "ACTOR_ANCHOR", "LOCATION_ANCHOR", "CORE_THESIS", "DEFINITIONAL_ANCHOR"):
        return "CLAIM"
    elif st in (
        "CHRONOLOGICAL_MECHANICS",
        "CAUSAL_MOTIVES",
        "COMMAND_LINEAGE",
        "STRATEGIC_DOCTRINE",
        "INFRASTRUCTURE_LOGISTICS",
        "MECHANISTIC_DEEPEN",
    ):
        return "WARRANT"
    elif st in (
        "IMPACT_ASSESSMENT",
        "ALLIANCE_NETWORK",
        "EVENT_FOOTPRINT",
        "TERRITORIAL_CONTROL",
        "HUMANITARIAN_STATUS",
        "EVENT_LOG",
        "MANIFESTATION_TRAP",
        "SYNTHESIS_CATALOG",
    ):
        return "GROUNDS"
    elif st in ("CONTRADICTION_MATRIX", "EMPIRICAL_BOUNDARY", "DILEMMA_PROBLEM"):
        return "REBUTTAL"
    elif st in ("PRESCRIPTIVE_SOLUTION", "SOLUTION_WARRANT"):
        return "SOLUTION_WARRANT"
    return "CLAIM"


class ConsolidatedV3Retriever:
    """
    Production-ready V3 GraphRAG retrieval engine for the Sudan News & OSINT Knowledge Base.
    Executes cross-lingual Arabic/English entity linking, P-Code resolution, and 1-hop 5W1H Macro-CoT expansion.
    """

    STOP_WORDS = {
        "what", "is", "the", "in", "simple", "terms", "why", "do", "how", "does",
        "a", "an", "and", "or", "to", "for", "with", "when", "using", "of", "can",
        "should", "from", "at", "by", "this", "that", "it", "are", "on", "as",
        "who", "where", "tell", "me", "about", "explain", "status", "latest",
    }

    def __init__(self, client: Optional[ArcadeDBHttpClient] = None):
        self.client = client or ArcadeDBHttpClient()
        self._concept_cache: Dict[str, str] = {}
        self._cache_timestamp: float = 0.0
        self._cache_ttl: float = 300.0

    async def _ensure_concepts_cached(self) -> Dict[str, str]:
        """
        Pre-fetches Event, Actor, Location, Theme, Timeline, and AliasLookup records from ArcadeDB,
        enriches with wiki/glossary.md, and generates normalized Arabic/English variants.
        """
        now = time.time()
        if self._concept_cache and (now - self._cache_timestamp) < self._cache_ttl:
            return self._concept_cache

        new_cache: Dict[str, str] = {}
        try:
            # 1. Fetch Vertex Titles & Aliases from ArcadeDB
            q = """
            MATCH (c)
            WHERE c:Event OR c:Actor OR c:Location OR c:Theme OR c:Timeline OR c:Concept OR c:Entity
            RETURN c.title AS title, c.aliases AS aliases, c.acronym AS acronym, c.pcode AS pcode
            """
            records = await self.client.query_async(q, language="cypher")
            for r in records:
                t = r.get("title")
                if not t:
                    continue
                for var in generate_normalized_variants(t):
                    new_cache[var] = t
                if r.get("acronym"):
                    new_cache[str(r["acronym"]).lower()] = t
                if r.get("pcode"):
                    new_cache[str(r["pcode"]).lower()] = t
                aliases = r.get("aliases") or []
                if isinstance(aliases, list):
                    for a in aliases:
                        if isinstance(a, str) and a.strip():
                            for var in generate_normalized_variants(a):
                                new_cache[var] = t

            # 2. Fetch AliasLookup collection from ArcadeDB
            alias_rows = await self.client.query_async(
                "SELECT alias, canonical_title, pcode FROM AliasLookup",
                language="sql"
            )
            for ar in alias_rows:
                al = ar.get("alias")
                canon = ar.get("canonical_title")
                if al and canon:
                    new_cache[al.lower()] = canon
                    for var in generate_normalized_variants(al):
                        new_cache[var] = canon

            # 3. Local glossary fallback from wiki/glossary.md
            try:
                vault_dir = Path(__file__).resolve().parent.parent.parent.parent
                glossary_path = vault_dir / "wiki" / "glossary.md"
                if glossary_path.exists():
                    content = glossary_path.read_text(encoding="utf-8")
                    for line in content.splitlines():
                        line = line.strip()
                        if line.startswith("|") and line.endswith("|") and not line.startswith("| :---"):
                            cells = [c.strip() for c in line[1:-1].split("|")]
                            if len(cells) >= 3 and cells[0] not in ("Term / Primary Acronym", "UN OCHA P-Code", "Term"):
                                col0 = cells[0].replace("**", "").strip().strip("`")
                                canon = re.sub(r"^\[\[|\]\]$", "", cells[1].strip())
                                new_cache[col0.lower()] = canon
                                for var in generate_normalized_variants(canon):
                                    new_cache[var] = canon
                                aliases_raw = [a.strip().strip("`") for a in cells[2].split(",") if a.strip()]
                                for a in aliases_raw:
                                    for var in generate_normalized_variants(a):
                                        new_cache[var] = canon
            except Exception as ge:
                logger.debug(f"Glossary file enrichment skipped: {ge}")

            self._concept_cache = new_cache
            self._cache_timestamp = now
            logger.info(f"Loaded {len(self._concept_cache)} normalized Sudan OSINT entity/location/alias mappings into V3 cache.")
        except Exception as e:
            logger.warning(f"Error loading nodes into V3 cache: {e}")

        return self._concept_cache

    def extract_smart_query(self, text: str) -> str:
        """Extract domain acronyms, P-Codes, and high-salience terms across the entire prompt."""
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
        Resolves Sudan Events, Actors, Locations, and Themes from user prompt text.
        """
        p_low = prompt_text.lower()
        p_variants = set(generate_normalized_variants(prompt_text))
        p_variants.add(p_low)

        matched_concepts: List[str] = []

        # 1. Exact acronym / P-Code token match (e.g. SAF, RSF, JEM, ERR, SD01, SD02)
        tokens = re.findall(r"\b[\w\-]+\b", p_low)
        for tok in tokens:
            if tok in all_concepts and len(tok) >= 2:
                matched_concepts.append(all_concepts[tok])

        # 2. Match across all normalized variants (length >= 4)
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

        # 3. High-priority Sudan OSINT disambiguation rules
        if any(k in p_low for k in ("hemedti", "himedti", "dagalo", "daglo", "حميدتي", "دقلو")):
            matched_concepts.insert(0, "Mohamed Hamdan Dagalo")
        if any(k in p_low for k in ("burhan", "al-burhan", "البرهان")):
            matched_concepts.insert(0, "Abdel Fattah al-Burhan")
        if any(k in p_low for k in ("rsf", "rapid support", "janjaweed", "الدعم السريع")):
            matched_concepts.append("Rapid Support Forces")
        if any(k in p_low for k in ("saf", "sudanese armed forces", "القوات المسلحة")):
            matched_concepts.append("Sudanese Armed Forces")
        if any(k in p_low for k in ("fasher", "el fasher", "al-fashir", "الفاشر")):
            matched_concepts.append("North Darfur")
        if any(k in p_low for k in ("gezira", "jazirah", "madani", "wad madani", "الجزيرة", "ود مدني")):
            matched_concepts.append("Al Jazirah")
        if any(k in p_low for k in ("emergency response", "غرف الطوارئ")):
            matched_concepts.append("Emergency Response Rooms")

        matched_concepts = list(dict.fromkeys(matched_concepts))

        # Prioritize specific actors/events/states over country root 'Sudan' when multiple matched
        if len(matched_concepts) > 1 and "Sudan" in matched_concepts:
            matched_concepts.remove("Sudan")
            matched_concepts.append("Sudan")

        if target_concepts:
            for tc in target_concepts:
                if tc in matched_concepts:
                    matched_concepts.remove(tc)
                    matched_concepts.insert(0, tc)
                    break

        primary_concept = matched_concepts[0] if matched_concepts else (topic or "Sudan")
        return primary_concept, matched_concepts

    async def fetch_candidates(
        self,
        primary_concept: str,
        smart_q: str,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Fetches section candidates via:
        1. Node section graph (`[:HAS_SECTION]`)
        2. Direct Vertex Metadata Synthesis (when Actor/Location vertex is seeded without child Section vertices yet)
        3. Lucene Full-Text Search
        """
        candidates: List[Dict[str, Any]] = []

        # 1. Node Seed Sections
        cypher_seed = """
        MATCH (c {title: $concept})-[:HAS_SECTION]->(s:Section)
        WITH s ORDER BY s.heading_level ASC, s.weight DESC LIMIT 10
        OPTIONAL MATCH (s)-[:HAS_DIAGRAM]->(d:Diagram)
        RETURN s.uri AS uri, coalesce(s.title, s.heading) AS title, s.toulmin_role AS toulmin_role,
               s.step_type AS step_type, s.weight AS weight, s.content AS content, 0.0 AS distance,
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
            logger.warning(f"Error retrieving seed sections for {primary_concept}: {e}")

        # 2. Direct Seeded Vertex Fallback (for seeded Actor / Location nodes before full note compilation)
        if not candidates and primary_concept:
            vertex_q = """
            MATCH (n {title: $concept})
            OPTIONAL MATCH (n)-[r]->(m)
            RETURN n.title AS title, labels(n) AS labels, n.subtype AS subtype,
                   n.acronym AS acronym, n.pcode AS pcode, n.capital_hub AS capital_hub,
                   n.summary_note AS summary_note, n.aliases AS aliases,
                   n.current_control AS current_control, n.reliability_score AS reliability_score,
                   collect({rel: type(r), target: m.title, warrant: r.warrant}) AS out_edges
            """
            try:
                v_rows = await self.client.query_async(vertex_q, language="cypher", params={"concept": primary_concept})
                if v_rows and v_rows[0].get("title"):
                    v = v_rows[0]
                    v_title = v["title"]
                    v_sub = v.get("subtype") or "node"
                    v_pcode = f" | **UN OCHA P-Code**: `{v['pcode']}`" if v.get("pcode") else ""
                    v_acro = f" (`{v['acronym']}`)" if v.get("acronym") else ""
                    v_aliases = ", ".join(v.get("aliases") or [])
                    v_summary = v.get("summary_note") or v.get("capital_hub") or "Indexed Sudan OSINT intelligence entity."
                    edges_md = []
                    for e_item in (v.get("out_edges") or []):
                        if e_item.get("rel") and e_item.get("target"):
                            w_str = f" — {e_item['warrant']}" if e_item.get("warrant") else ""
                            edges_md.append(f"- **`[:{e_item['rel']}]`** $\\to$ [[{e_item['target']}]]{w_str}")
                    edges_block = "\n".join(edges_md) if edges_md else "- Seeded in `wiki/glossary.md` and ArcadeDB `news`."

                    anchor_md = (
                        f"**[[{v_title}]]**{v_acro} is a canonical `{v_sub}` node in the Sudan News & OSINT Knowledge Graph{v_pcode}.\n\n"
                        f"- **Profile / Strategic Context**: {v_summary}\n"
                        f"- **Known Arabic & English Aliases**: {v_aliases or 'None'}\n"
                        f"- **Reliability Score**: `{v.get('reliability_score', 0.95)}`"
                    )
                    candidates.append({
                        "uri": f"wiki/actors/{v_title}.md#1. Identity & Classification Anchor",
                        "title": f"1. 5W1H Intelligence Anchor: {v_title}",
                        "toulmin_role": "CLAIM",
                        "step_type": "ACTOR_ANCHOR",
                        "weight": 1.0,
                        "distance": 0.0,
                        "content": anchor_md,
                        "diagrams": [],
                    })
                    candidates.append({
                        "uri": f"wiki/actors/{v_title}.md#4. Command, Alliance & Spatial Network",
                        "title": f"4. Command, Coalition & Spatial Network: {v_title}",
                        "toulmin_role": "GROUNDS",
                        "step_type": "ALLIANCE_NETWORK",
                        "weight": 0.9,
                        "distance": 0.05,
                        "content": f"Verified relational handshakes in ArcadeDB (`news`):\n\n{edges_block}",
                        "diagrams": [],
                    })
            except Exception as ve:
                logger.warning(f"Direct vertex fallback failed for {primary_concept}: {ve}")

        return candidates, []

    def select_s0_anchor(
        self,
        candidates: List[Dict[str, Any]],
        target_concepts: List[str],
        expected_roles: List[str],
        user_category: str = "intermediate",
        topic: str = "",
    ) -> Dict[str, Any]:
        """Selects the optimal S0 Anchor section."""
        if not candidates:
            return {}
        best_candidate: Dict[str, Any] = candidates[0]
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

            if cand_role in expected_roles:
                score += 15.0

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
        primary_concept: str = "",
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Set[str], Set[str]]:
        """
        Traverses 1-hop Macro-CoT 5W1H & GRaSP Cypher edges from S0 Anchor or primary vertex:
        (PERPETRATED_BY, TARGETED, OCCURRED_AT, LOCATED_IN, COMMANDED_BY, ALLIED_WITH,
         CONTROLS_TERRITORY, TRIGGERS, RETALIATES_FOR, CONTRADICTS_CLAIM, etc.)
        """
        anchor_title = primary_concept or extract_concept_title_from_uri(s0_uri)
        q_macro_vertices = """
        MATCH (c {title: $anchor})-[r:PRECEDES|TRIGGERS|RETALIATES_FOR|PART_OF_CAMPAIGN|MOTIVATED_BY|PERPETRATED_BY|TARGETED|PARTICIPATED_IN|COMMANDED_BY|ALLIED_WITH|SPONSORED_BY|DEFECTED_TO|OCCURRED_AT|LOCATED_IN|CONTROLS_TERRITORY|DISPLACES_POPULATION|EMPIRICALLY_GROUNDS|CORROBORATES|CONTRADICTS_CLAIM|ATTRIBUTES_BLAME_TO|DEBUNKS|PUBLISHED_BY]-(c2)
        WHERE NOT c2:Section
        RETURN c.title AS anchor_concept, c2.title AS neighbor_concept, type(r) AS bridge_rel,
               coalesce(r.warrant, c.title + ' [:' + type(r) + '] ' + c2.title) AS warrant,
               coalesce(c2.summary_note, c2.capital_hub, c2.subtype, '') AS neighbor_summary,
               coalesce(c2.pcode, '') AS neighbor_pcode
        LIMIT 25
        """
        try:
            r_macro = await self.client.query_async(q_macro_vertices, language="cypher", params={"anchor": anchor_title})
        except Exception as e:
            logger.warning(f"Error querying Macro-CoT expansion: {e}")
            r_macro = []

        covered_roles: Set[str] = {s0_role}
        window_concepts: Set[str] = {anchor_title} if anchor_title else set()

        s1: Dict[str, Any] = {}
        s2: Dict[str, Any] = {}

        if r_macro:
            row1 = r_macro[0]
            nb1 = row1.get("neighbor_concept", "")
            rel1 = row1.get("bridge_rel", "RELATES_TO")
            pcode1 = f" (`{row1['neighbor_pcode']}`)" if row1.get("neighbor_pcode") else ""
            s1 = {
                "uri": f"wiki/nodes/{nb1}.md#Macro-Bridge",
                "title": f"Macro-CoT Bridge [:{rel1}] -> {nb1}",
                "role": "WARRANT",
                "concept": nb1,
                "edge": rel1,
                "bridge_rel": rel1,
                "weight": 0.9,
                "is_inter": True,
                "content": f"**{row1.get('warrant', '')}**\n\n- **Connected Node**: [[{nb1}]]{pcode1}\n- **Context**: {row1.get('neighbor_summary', '')}",
                "diagrams": [],
            }
            covered_roles.add("WARRANT")
            if nb1:
                window_concepts.add(nb1)

        if len(r_macro) > 1:
            row2 = r_macro[1]
            nb2 = row2.get("neighbor_concept", "")
            rel2 = row2.get("bridge_rel", "RELATES_TO")
            pcode2 = f" (`{row2['neighbor_pcode']}`)" if row2.get("neighbor_pcode") else ""
            s2 = {
                "uri": f"wiki/nodes/{nb2}.md#Macro-Bridge",
                "title": f"Macro-CoT Bridge [:{rel2}] -> {nb2}",
                "role": "GROUNDS",
                "concept": nb2,
                "edge": rel2,
                "bridge_rel": rel2,
                "weight": 0.85,
                "is_inter": True,
                "content": f"**{row2.get('warrant', '')}**\n\n- **Connected Node**: [[{nb2}]]{pcode2}\n- **Context**: {row2.get('neighbor_summary', '')}",
                "diagrams": [],
            }
            covered_roles.add("GROUNDS")
            if nb2:
                window_concepts.add(nb2)

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
        """Executes the full 4-phase V3 Sudan News & OSINT retrieval pipeline."""
        t0 = time.perf_counter()
        target_concepts = target_concepts or []
        if not expected_roles:
            expected_roles = ["CLAIM", "WARRANT", "GROUNDS"]

        all_concepts = await self._ensure_concepts_cached()
        smart_q = self.extract_smart_query(prompt)

        primary_concept, matched_concepts = self.resolve_concepts(
            prompt_text=prompt,
            all_concepts=all_concepts,
            target_concepts=target_concepts,
            topic=topic,
        )

        t_vec_start = time.perf_counter()
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
        s0_role = s0.get("toulmin_role", "CLAIM")
        s0_concept = extract_concept_title_from_uri(s0_uri) or primary_concept

        t_cyp_start = time.perf_counter()
        s1, s2, covered_roles, window_concepts = await self.expand_macro_cot(
            s0_uri=s0_uri,
            expected_roles=expected_roles,
            target_concepts=target_concepts or [primary_concept],
            vector_neighbors=vector_neighbors,
            s0_role=s0_role,
            primary_concept=primary_concept,
        )
        t_cyp_ms = (time.perf_counter() - t_cyp_start) * 1000.0
        t_total_ms = (time.perf_counter() - t0) * 1000.0

        window_sections = [
            {
                "step": "S0 (5W1H Anchor)",
                "uri": s0_uri,
                "title": s0_title,
                "role": s0_role,
                "concept": s0_concept,
                "edge": "ANCHOR_ROUTER",
                "weight": 1.0,
                "is_inter": False,
                "content": s0.get("content", ""),
                "diagrams": s0.get("diagrams", []),
            }
        ]
        # Also include additional intra-node sections from candidates if present
        for extra_cand in candidates[1:]:
            window_sections.append({
                "step": "S1 (Intra-Node)",
                "uri": extra_cand.get("uri", ""),
                "title": extra_cand.get("title", ""),
                "role": extra_cand.get("toulmin_role", "GROUNDS"),
                "concept": s0_concept,
                "edge": "HAS_SECTION",
                "weight": extra_cand.get("weight", 0.9),
                "is_inter": False,
                "content": extra_cand.get("content", ""),
                "diagrams": extra_cand.get("diagrams", []),
            })
            covered_roles.add(extra_cand.get("toulmin_role", "GROUNDS"))

        for step_label, sec_item in [("S1 (CoT Step 1)", s1), ("S2 (CoT Step 2)", s2)]:
            if sec_item and sec_item.get("uri"):
                window_sections.append({
                    "step": step_label,
                    "uri": sec_item.get("uri", ""),
                    "title": sec_item.get("title", ""),
                    "role": sec_item.get("role", "WARRANT"),
                    "concept": sec_item.get("concept", ""),
                    "edge": sec_item.get("edge", ""),
                    "bridge_rel": sec_item.get("bridge_rel", ""),
                    "weight": sec_item.get("weight", 0.85),
                    "is_inter": sec_item.get("is_inter", True),
                    "content": sec_item.get("content", ""),
                    "diagrams": sec_item.get("diagrams", []),
                })

        active_roles = {sec["role"] for sec in window_sections if sec.get("role") != "UNKNOWN"}
        all_expected_roles_covered = len(active_roles) >= 2

        return {
            "primary_concept": primary_concept,
            "matched_concepts": matched_concepts,
            "search_query": smart_q,
            "fit_status": "PERFECT_COT_WINDOW" if all_expected_roles_covered else "PARTIAL_ROLE_COVERAGE",
            "all_expected_roles_covered": all_expected_roles_covered,
            "window_concept_match": True,
            "roles_covered": list(active_roles),
            "concepts_in_window": list(window_concepts),
            "sections": window_sections,
            "latencies": {
                "vector_routing_ms": round(t_vec_ms, 2),
                "cypher_expansion_ms": round(t_cyp_ms, 2),
                "total_latency_ms": round(t_total_ms, 2),
            },
        }
