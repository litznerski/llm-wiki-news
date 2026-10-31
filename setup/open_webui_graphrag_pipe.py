"""
title: Deterministic Neo4j GraphRAG, Dual-Flow CoT & SAM Filter
author: Knowledge Lab
requirements: neo4j, httpx, langfuse
description: Consolidated deterministic GraphRAG filter with substep Langfuse observability, Dual-Flow CoT intent routing, SAM community continuity checking, and configurable Cypher tracing.
version: 3.0.0
"""

import os
import re
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field

try:
    import httpx
except ImportError:
    httpx = None

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None

try:
    from langfuse import Langfuse
except ImportError:
    Langfuse = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("graphrag-filter")


class Filter:
    class Valves(BaseModel):
        # Neo4j Database Connection
        NEO4J_URI: str = Field(
            default=os.getenv("NEO4J_URI", "bolt://neo4j-ki:7687"),
            description="Bolt endpoint for Neo4j (local neo4j-ki container or Aura cloud).",
        )
        NEO4J_USERNAME: str = Field(
            default=os.getenv("NEO4J_USERNAME", os.getenv("NEO4J_USER", "neo4j")),
            description="Neo4j database username.",
        )
        NEO4J_PASSWORD: str = Field(
            default=os.getenv("NEO4J_PASSWORD", "password"),
            description="Neo4j database password.",
        )

        # Ollama Embedding Services
        OLLAMA_EMBED_URL: str = Field(
            default="http://host.containers.internal:11434/api/embeddings",
            description="Ollama embeddings endpoint reachable from Open WebUI.",
        )
        EMBEDDING_MODEL: str = Field(
            default="nomic-embed-text",
            description="Ollama embedding model name.",
        )

        # Retrieval Engine & Boundaries
        ENABLE_DETERMINISTIC_ROUTER: bool = Field(
            default=True,
            description="Use fast Lucene entity resolution and pre-compiled Cypher templates before vector fallback.",
        )
        FULLTEXT_SCORE_THRESHOLD: float = Field(
            default=5.0,
            description="Minimum Lucene score required to accept an entity match.",
        )
        TOP_K: int = Field(
            default=3,
            description="Number of top sections to retrieve in vector fallback.",
        )
        VECTOR_WEIGHT: float = Field(
            default=0.7,
            description="Weight for vector similarity (0.0 to 1.0).",
        )
        AUTHORITY_WEIGHT: float = Field(
            default=0.3,
            description="Weight for GDS PageRank authority.",
        )
        ENABLE_COT_WINDOWING: bool = Field(
            default=True,
            description="Expand focal vector matches into 3-step narrative arcs (Antecedent + Focal + Subsequent).",
        )
        INCLUDE_REMEDIES: bool = Field(
            default=True,
            description="Traverse [:REMEDIES_DILEMMA] to automatically append connected solution frameworks.",
        )
        MAX_REMEDIES_COUNT: int = Field(
            default=4,
            description="Maximum number of interconnected solution concepts to inject per seed match.",
        )
        EXCERPT_CHAR_LIMIT: int = Field(
            default=900,
            description="Character ceiling for focal section text to preserve context window.",
        )

        # Follow-up Context & Community Governance (Step 2)
        SAM_COMMUNITY_STRICT_MODE: bool = Field(
            default=True,
            description="In follow-up questions, restrict context expansion strictly to nodes within the same gds_community.",
        )
        CONTEXT_SHIFT_STRATEGY: str = Field(
            default="ask_user",
            description="Strategy when follow-up query shifts to an unrelated community: 'ask_user' (interactive note) or 'adaptive_clear' (auto-clear prior context).",
        )
        ALLOW_FOLLOW_UP_GENERATION: bool = Field(
            default=False,
            description="Deactivate Open WebUI follow-up suggestion generation.",
        )

        # Consolidated Langfuse Observability
        ENABLE_LANGFUSE: bool = Field(
            default=True,
            description="Enable deep Langfuse telemetry and sub-span tracing.",
        )
        LANGFUSE_PUBLIC_KEY: str = Field(
            default="",
            description="Langfuse Public Key (starts with pk-lf-...).",
        )
        LANGFUSE_SECRET_KEY: str = Field(
            default="",
            description="Langfuse Secret Key (starts with sk-lf-...).",
        )
        LANGFUSE_HOST: str = Field(
            default="https://cloud.langfuse.com",
            description="Langfuse Host URL (https://cloud.langfuse.com for EU, https://us.cloud.langfuse.com for US).",
        )
        PROJECT_TAG: str = Field(
            default="open-webui-graphrag",
            description="Default project tag for Langfuse traces.",
        )
        LANGFUSE_LOG_CYPHER_QUERIES: bool = Field(
            default=True,
            description="Filter switch: When enabled, logs exact parameterized Cypher queries and parameters into Langfuse span inputs/metadata. When disabled, queries are suppressed to minimize trace payload size.",
        )

    # Fast-Path Weighted Regex Patterns for Dual-Flow CoT Sequence
    # Maps to: (interrogative_pattern, body_keyword_pattern, intent_name, target_step_type, target_label)
    INTENT_MAPPINGS = [
        # 1. Prescriptive Solutions & Remedies
        {
            "intent": "REMEDY",
            "step_type": "PRESCRIPTIVE_SOLUTION",
            "label": "PrescriptiveSolution",
            "interrogative": r"^(how (can|do|does|to|should|we)|what (can|should)|how do we (fix|solve)|wie (kann|lässt sich|lösen wir))\b",
            "keywords": r"\b(solve|solving|solves|solution|solutions|fix|fixes|fixing|mitigate|mitigates|mitigating|mitigation|mitigations|remedy|remedies|countermeasure|countermeasures|counter-measure|counter-measures|counter-architecture|counter-architectures|safeguard|safeguards|intervention|interventions|antidote|antidotes|overcome|overcoming|cure|beheb\w*|loes\w*|lös\w*|gegenmassnahme\w*|gegenmaßnahme\w*)\b",
        },
        # 2. Manifestation Traps & Failure Modes
        {
            "intent": "TRAP",
            "step_type": "MANIFESTATION_TRAP",
            "label": "ManifestationTrap",
            "interrogative": r"^(what (are the |are )?(\w+\s+)?(problems|traps|failures|risks|dangers|downsides|pathologies)|welche (\w+\s+)?(probleme|fallen|gefahren|risiken))\b",
            "keywords": r"\b(problem|problems|trap|traps|failure|failures|dilemma|dilemmas|pathology|pathologies|crisis|vulnerability|vulnerabilities|flaw|flaws|danger|dangers|risk|risks|downside|downsides|collapse|gefahr\w*|falle\w*|fallstrick\w*|paradox\w*)\b",
        },
        # 3. Causal Mechanics & Underlying Anatomy
        {
            "intent": "MECHANISM",
            "step_type": "MECHANISTIC_DEEPEN",
            "label": "MechanisticDeepen",
            "interrogative": r"^(why|what causes|what triggers|how come|warum|wieso|weshalb)\b|how does.*work|wie funktioniert\w*",
            "keywords": r"\b(mechanism|mechanisms|anatomy|driver|drivers|causal|causality|underlying|engine|inner workings|ursache\w*|funktionsweise\w*|wirkungsweise\w*)\b",
        },
        # 4. Empirical Boundaries & Dialectical Contradictions
        {
            "intent": "BOUNDARY",
            "step_type": "EMPIRICAL_BOUNDARY",
            "label": "EmpiricalBoundary",
            "interrogative": r"^(what (are the |are )?(\w+\s+)?(boundaries|limits|trade-offs|contradictions)|welche (\w+\s+)?grenzen)\b",
            "keywords": r"\b(boundary|boundaries|limit|limits|limitation|limitations|contradiction|contradictions|tension|tensions|trade-off|trade-offs|tradeoff|tradeoffs|exception|exceptions|grenze\w*|widerspruch\w*)\b",
        },
        # 5. Definitional Anchors & Core Thesis
        {
            "intent": "DEFINITION",
            "step_type": "DEFINITIONAL_ANCHOR",
            "label": "DefinitionalAnchor",
            "interrogative": r"^(what is|what are)\s+(the\s+)?(definition|meaning|overview|concept)\b|^(define|was ist|was sind|bedeutung von)\b",
            "keywords": r"\b(definition|meaning|overview|introduction|concept|theorie|was bedeutet|begriff|überblick|einführung)\b",
        },
    ]

    def __init__(self):
        self.valves = self.Valves()
        self._driver = None
        self._langfuse = None
        self._chat_sessions: Dict[str, Dict[str, Any]] = {}
        self._active_notices: Dict[str, str] = {}
        self._active_follow_ups: Dict[str, List[str]] = {}

    def _get_langfuse(self) -> Optional[Any]:
        if not self.valves.ENABLE_LANGFUSE or Langfuse is None:
            return None
        if not self.valves.LANGFUSE_PUBLIC_KEY or not self.valves.LANGFUSE_SECRET_KEY:
            return None
        if self._langfuse is None:
            try:
                self._langfuse = Langfuse(
                    public_key=self.valves.LANGFUSE_PUBLIC_KEY,
                    secret_key=self.valves.LANGFUSE_SECRET_KEY,
                    host=self.valves.LANGFUSE_HOST,
                )
            except Exception as e:
                logger.warning(f"Error initializing Langfuse client: {e}")
                return None
        return self._langfuse

    def _get_driver(self):
        if self._driver is None and GraphDatabase is not None:
            try:
                self._driver = GraphDatabase.driver(
                    self.valves.NEO4J_URI,
                    auth=(self.valves.NEO4J_USERNAME, self.valves.NEO4J_PASSWORD),
                    notifications_min_severity="OFF",
                )
            except Exception as e:
                logger.error(f"Error connecting to Neo4j database: {e}")
                return None
        return self._driver

    def _start_cypher_span(
        self,
        parent_obs: Any,
        span_name: str,
        cypher_query: str,
        params: dict,
        input_data: Optional[dict] = None,
    ) -> Optional[Any]:
        """Initializes a Langfuse span, conditionally embedding the raw Cypher query based on the valve switch."""
        if not parent_obs:
            return None
        payload = dict(input_data or {})
        if self.valves.LANGFUSE_LOG_CYPHER_QUERIES:
            payload["cypher_query"] = re.sub(r"\s+", " ", cypher_query.strip())
            payload["cypher_params"] = params

        try:
            return parent_obs.start_observation(
                name=span_name,
                as_type="tool",
                input=payload,
            )
        except Exception as e:
            logger.debug(f"Error starting Cypher span '{span_name}': {e}")
            return None

    def _classify_intent(self, query: str) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Fast-Path Cascading Dual-Flow CoT Classifier using weighted morphological scoring.
        Returns: (intent_name, target_step_type, target_label)
        Fallback: ('GENERAL', None, None)
        """
        q_clean = query.lower().strip()
        scores: Dict[str, float] = {m["intent"]: 0.0 for m in self.INTENT_MAPPINGS}

        for mapping in self.INTENT_MAPPINGS:
            intent = mapping["intent"]
            # Interrogative anchor at start of sentence gets primary weighting
            if re.search(mapping["interrogative"], q_clean):
                scores[intent] += 3.0
            # General keyword occurrence
            if re.search(mapping["keywords"], q_clean):
                scores[intent] += 1.5

        # Bare 'what is X' or 'what are X' without other strong intent scores DEFINITION
        if re.search(r"^(what is|what are|was ist|was sind)\b", q_clean) and max(scores.values()) == 0.0:
            scores["DEFINITION"] += 2.0

        best_intent = max(scores, key=scores.get)
        if scores[best_intent] >= 1.5:
            match = next(m for m in self.INTENT_MAPPINGS if m["intent"] == best_intent)
            return match["intent"], match["step_type"], match["label"]

        return "GENERAL", None, None


    def _resolve_entity(self, session, query_text: str, parent_obs: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Resolves concepts or entities using Neo4j's typo-resilient Lucene full-text index."""
        # Strip prompt dilution conversational prefixes
        cleaned = re.sub(
            r"^(can you|please|i want to know|tell me about|explain to me|let's discuss|what about|could you|bitte erkläre|kannst du)\s+",
            "",
            query_text.strip(),
            flags=re.IGNORECASE,
        )
        # Sanitize Lucene special query parser characters
        clean_q = re.sub(r'[\?\*\+\-\&\&\|\|\!\(\)\{\}\[\]\^\"~:\\]', ' ', cleaned).strip()
        if not clean_q or len(clean_q) < 3:
            return None

        cypher = """
        CALL db.index.fulltext.queryNodes('doc_alias_search', $q)
        YIELD node, score
        WHERE score >= $min_score AND NOT node:Ingestion
        WITH node, score, score * (CASE WHEN 'Concept' IN labels(node) THEN 1.3 WHEN 'Entity' IN labels(node) THEN 1.2 ELSE 1.0 END) AS final_score
        RETURN node.title AS title, labels(node) AS labels, node.type AS type,
               coalesce(node.gds_pagerank, 0.01) AS authority,
               coalesce(node.gds_community, 0) AS community,
               node.subtype AS subtype,
               final_score, score
        ORDER BY final_score DESC
        LIMIT 1
        """
        params = {"q": clean_q, "min_score": self.valves.FULLTEXT_SCORE_THRESHOLD}

        span = self._start_cypher_span(
            parent_obs,
            "1.2_lucene_fulltext_search",
            cypher,
            params,
            {"sanitized_query": clean_q, "raw_query": query_text},
        )

        try:
            res = session.run(cypher, **params).data()
            matched = res[0] if res else None
            if span:
                span.update(
                    output={
                        "matched_node": matched["title"] if matched else None,
                        "labels": matched["labels"] if matched else [],
                        "type": matched.get("type") if matched else None,
                        "community": matched.get("community") if matched else None,
                        "score": matched.get("score") if matched else 0.0,
                    }
                )
                span.end()
            return matched
        except Exception as e:
            logger.warning(f"Error in Lucene entity resolution: {e}")
            if span:
                span.update(output={"error": str(e)})
                span.end()
            return None

    def _query_concept_sections(
        self, session, entity: Dict[str, Any], intent: str, step_type: Optional[str], target_label: Optional[str], parent_obs: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Queries intent-targeted sections and Macro-CoT relational handshakes for a Concept node."""
        title = entity["title"]
        result = {
            "entity": title,
            "type": "concept",
            "intent": intent,
            "authority": entity.get("authority", 0.01),
            "community": entity.get("community", 0),
            "remedies": [],
            "theories": [],
            "traps": [],
            "sections": [],
        }

        if intent == "REMEDY":
            cypher = """
            MATCH (c:Concept {title: $title})
            WHERE NOT c:Ingestion
            OPTIONAL MATCH (c)-[:REMEDIES_DILEMMA]->(sol:Concept) WHERE NOT sol:Ingestion
            OPTIONAL MATCH (prob:Concept)-[:REMEDIES_DILEMMA]->(c) WHERE NOT prob:Ingestion
            OPTIONAL MATCH (c)-[:HAS*1..3]->(s:Section)
            WHERE s:PrescriptiveSolution OR s.step_type = 'PRESCRIPTIVE_SOLUTION' 
               OR toLower(coalesce(s.displayName, '')) =~ '.*(solution|mitigat|safeguard|countermeasure|remedy).*'
            RETURN c.title AS title,
                   collect(DISTINCT sol.title) AS remedies,
                   collect(DISTINCT prob.title) AS mitigates_problems,
                   collect(DISTINCT {title: coalesce(s.displayName, s.name), content: s.content})[0..3] AS sections
            """
        elif intent == "TRAP":
            cypher = """
            MATCH (c:Concept {title: $title})
            WHERE NOT c:Ingestion
            OPTIONAL MATCH (c)-[:PRECIPITATES]->(trap:Concept) WHERE NOT trap:Ingestion
            OPTIONAL MATCH (src:Concept)-[:PRECIPITATES]->(c) WHERE NOT src:Ingestion
            OPTIONAL MATCH (c)-[:HAS*1..3]->(s:Section)
            WHERE s:ManifestationTrap OR s:DilemmaProblem OR s.step_type IN ['MANIFESTATION_TRAP', 'DILEMMA_PROBLEM']
               OR toLower(coalesce(s.displayName, '')) =~ '.*(trap|failure|dilemma|pathology|crisis).*'
            RETURN c.title AS title,
                   collect(DISTINCT trap.title) AS traps,
                   collect(DISTINCT src.title) AS precipitated_by,
                   collect(DISTINCT {title: coalesce(s.displayName, s.name), content: s.content})[0..3] AS sections
            """
        elif intent == "MECHANISM":
            cypher = """
            MATCH (c:Concept {title: $title})
            WHERE NOT c:Ingestion
            OPTIONAL MATCH (c)-[:EXTENDS_THEORY]->(theory:Concept) WHERE NOT theory:Ingestion
            OPTIONAL MATCH (c)-[:PRECIPITATES]->(trap:Concept) WHERE NOT trap:Ingestion
            OPTIONAL MATCH (c)-[:HAS*1..3]->(s:Section)
            WHERE s:MechanisticDeepen OR s.step_type = 'MECHANISTIC_DEEPEN'
               OR toLower(coalesce(s.displayName, '')) =~ '.*(mechanism|anatomy|engine|underlying|pillar|foundation).*'
            RETURN c.title AS title,
                   collect(DISTINCT theory.title) AS theories,
                   collect(DISTINCT trap.title) AS traps,
                   collect(DISTINCT {title: coalesce(s.displayName, s.name), content: s.content})[0..3] AS sections
            """
        elif intent == "BOUNDARY":
            cypher = """
            MATCH (c:Concept {title: $title})
            WHERE NOT c:Ingestion
            OPTIONAL MATCH (c)-[:EMPIRICALLY_GROUNDS]-(src:Document) WHERE NOT src:Ingestion
            OPTIONAL MATCH (c)-[:HAS*1..3]->(s:Section)
            WHERE s:EmpiricalBoundary OR s.step_type = 'EMPIRICAL_BOUNDARY'
               OR toLower(coalesce(s.displayName, '')) =~ '.*(boundary|limit|contradiction|tension|trade-off).*'
            RETURN c.title AS title,
                   collect(DISTINCT src.title) AS groundings,
                   collect(DISTINCT {title: coalesce(s.displayName, s.name), content: s.content})[0..3] AS sections
            """
        else:  # DEFINITION or GENERAL
            cypher = """
            MATCH (c:Concept {title: $title})
            WHERE NOT c:Ingestion
            OPTIONAL MATCH (c)-[:HAS*1..3]->(s:Section)
            WHERE s:Summary OR s:CoreThesis OR s:DefinitionalAnchor 
               OR s.step_type IN ['DEFINITIONAL_ANCHOR', 'CORE_THESIS'] 
               OR s.headingLevel = 1 
               OR toLower(coalesce(s.displayName, '')) =~ '.*(overview|definition|anchor|thesis|introduction).*'
            WITH c, s ORDER BY CASE WHEN s:Summary THEN 0 WHEN s:CoreThesis THEN 1 ELSE 2 END
            OPTIONAL MATCH (c)-[:REMEDIES_DILEMMA]->(sol:Concept) WHERE NOT sol:Ingestion
            OPTIONAL MATCH (c)-[:CITES]->(cite:Document) WHERE NOT cite:Ingestion
            RETURN c.title AS title,
                   collect(DISTINCT sol.title)[0..4] AS remedies,
                   collect(DISTINCT cite.title)[0..5] AS citations,
                   collect(DISTINCT {title: coalesce(s.displayName, s.name), content: s.content})[0..2] AS sections
            """

        params = {"title": title}
        span = self._start_cypher_span(
            parent_obs,
            "1.4_graph_retrieval_concept",
            cypher,
            params,
            {"title": title, "intent": intent, "branch": "CONCEPT"},
        )

        try:
            data = session.run(cypher, **params).data()
            if data:
                row = data[0]
                result["remedies"] = row.get("remedies", [])
                result["mitigates_problems"] = row.get("mitigates_problems", [])
                result["theories"] = row.get("theories", [])
                result["traps"] = row.get("traps", [])
                result["sections"] = row.get("sections", [])
                result["citations"] = row.get("citations", [])

            if span:
                span.update(
                    output={
                        "sections_retrieved": len(result["sections"]),
                        "remedies_count": len(result["remedies"]),
                        "traps_count": len(result["traps"]),
                        "theories_count": len(result["theories"]),
                    }
                )
                span.end()
        except Exception as e:
            logger.error(f"Error executing Concept Cypher template: {e}")
            if span:
                span.update(output={"error": str(e)})
                span.end()

        return result

    def _query_entity_sections(self, session, entity: Dict[str, Any], parent_obs: Optional[Any] = None) -> Dict[str, Any]:
        """Loads canonical archetypal sections for an Entity node (researcher, organization, software)."""
        title = entity["title"]
        subtype = entity.get("subtype", "software")

        cypher = """
        MATCH (e:Entity {title: $title})-[:HAS*1..3]->(s:Section)
        WHERE NOT e:Ingestion
        OPTIONAL MATCH (e)-[:OPERATIONALIZES|AFFILIATED_WITH|ORIGINATES_THEORY|CHAMPIONS_SOLUTION|CRITIQUES_PARADIGM]->(target:Document)
        WHERE NOT target:Ingestion
        WITH e, s, collect(DISTINCT target.title)[0..5] AS related_targets
        ORDER BY s.headingLevel ASC
        RETURN e.title AS title,
               e.subtype AS subtype,
               coalesce(e.gds_pagerank, 0.01) AS authority,
               coalesce(e.gds_community, 0) AS community,
               related_targets,
               collect(DISTINCT {title: coalesce(s.displayName, s.name), content: s.content})[0..4] AS sections
        """
        params = {"title": title}
        span = self._start_cypher_span(
            parent_obs,
            "1.4_graph_retrieval_entity",
            cypher,
            params,
            {"title": title, "subtype": subtype, "branch": "ENTITY"},
        )

        result = {
            "entity": title,
            "type": "entity",
            "subtype": subtype,
            "authority": entity.get("authority", 0.01),
            "community": entity.get("community", 0),
            "related_targets": [],
            "sections": [],
        }

        try:
            data = session.run(cypher, **params).data()
            if data:
                row = data[0]
                result["related_targets"] = row.get("related_targets", [])
                result["sections"] = row.get("sections", [])

            if span:
                span.update(
                    output={
                        "sections_retrieved": len(result["sections"]),
                        "related_targets_count": len(result["related_targets"]),
                    }
                )
                span.end()
        except Exception as e:
            logger.error(f"Error loading Entity sections: {e}")
            if span:
                span.update(output={"error": str(e)})
                span.end()

        return result

    def _check_sam_continuity(
        self,
        session,
        curr_title: str,
        prev_titles: List[str],
        parent_obs: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates Spreading Activation Model (SAM) overlap and graph adjacency between previous nodes and current node.
        Uses tight causal and CoT handshakes (REMEDIES_DILEMMA, EXTENDS_THEORY, PRECIPITATES, ORIGINATES_THEORY,
        CHAMPIONS_SOLUTION, CRITIQUES_PARADIGM, OPERATIONALIZES) rather than loose citations/wikilinks.
        """
        cypher = """
        MATCH (curr:Document {title: $curr_title})
        WHERE NOT curr:Ingestion
        OPTIONAL MATCH (curr)-[r:REMEDIES_DILEMMA|EXTENDS_THEORY|PRECIPITATES|ORIGINATES_THEORY|CHAMPIONS_SOLUTION|CRITIQUES_PARADIGM|OPERATIONALIZES]-(prev:Document)
        WHERE prev.title IN $prev_titles AND NOT prev:Ingestion
        RETURN curr.title AS title,
               coalesce(curr.gds_community, 0) AS current_community,
               coalesce(curr.gds_pagerank, 0.01) AS current_authority,
               count(r) AS tight_cot_edges,
               collect(DISTINCT prev.title) AS overlapping_nodes
        """
        params = {"curr_title": curr_title, "prev_titles": prev_titles}
        span = self._start_cypher_span(
            parent_obs,
            "1.3_context_continuity_check",
            cypher,
            params,
            {"curr_title": curr_title, "prev_titles": prev_titles},
        )

        result = {
            "current_community": 0,
            "current_authority": 0.01,
            "tight_cot_edges": 0,
            "overlapping_nodes": [],
            "is_continuous": False,
        }

        try:
            data = session.run(cypher, **params).data()
            if data:
                row = data[0]
                result["current_community"] = row.get("current_community", 0)
                result["current_authority"] = row.get("current_authority", 0.01)
                result["tight_cot_edges"] = row.get("tight_cot_edges", 0)
                result["overlapping_nodes"] = row.get("overlapping_nodes", [])

            if span:
                span.update(output=result)
                span.end()
        except Exception as e:
            logger.warning(f"Error checking SAM continuity: {e}")
            if span:
                span.update(output={"error": str(e)})
                span.end()

        return result

    def _query_community_nodes(self, session, community_id: int, exclude_title: str) -> List[str]:
        """Queries missing high-authority concept/entity titles strictly belonging to the same gds_community."""
        cypher = """
        MATCH (d:Document)
        WHERE d.gds_community = $community_id AND d.title <> $exclude_title AND NOT d:Ingestion
        RETURN d.title AS title, coalesce(d.gds_pagerank, 0.01) AS authority
        ORDER BY authority DESC
        LIMIT 4
        """
        try:
            data = session.run(cypher, community_id=community_id, exclude_title=exclude_title).data()
            return [row["title"] for row in data if row.get("title")]
        except Exception as e:
            logger.warning(f"Error fetching community nodes: {e}")
            return []

    async def _get_embedding(self, text: str) -> Optional[List[float]]:
        if httpx is None:
            return None
        candidate_urls = [self.valves.OLLAMA_EMBED_URL]
        if "host.containers.internal" in self.valves.OLLAMA_EMBED_URL:
            candidate_urls.append(self.valves.OLLAMA_EMBED_URL.replace("host.containers.internal", "127.0.0.1"))

        for url in candidate_urls:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        url,
                        json={"model": self.valves.EMBEDDING_MODEL, "prompt": text[:2048]},
                    )
                    if resp.status_code == 200:
                        return resp.json().get("embedding")
            except Exception:
                continue
        logger.warning("Could not fetch embedding from Ollama endpoints.")
        return None

    def _hybrid_graph_search(
        self,
        session,
        q_vec: List[float],
        step_filter: Optional[str] = None,
        exclude_doc: Optional[str] = None,
        parent_obs: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Executes native Neo4j vector search combined with GDS authority and CoT windowing."""
        cypher = """
        CALL db.index.vector.queryNodes('section_vector_idx', $top_k * 3, $q_vec)
        YIELD node AS section, score AS vector_score
        WHERE ($step_filter IS NULL OR section.step_type = $step_filter)
        MATCH (doc:Document)-[:HAS*1..3]->(section)
        WHERE ($exclude_doc IS NULL OR doc.title <> $exclude_doc) AND NOT doc:Ingestion
        OPTIONAL MATCH (section)-[:LINKS_TO]->(target:Document) WHERE NOT target:Ingestion
        OPTIONAL MATCH (doc)-[:TAGGED_WITH]->(t:Tag)
        OPTIONAL MATCH (prev:Section)-[p_rel:PROGRESSES_TO]->(section)
        OPTIONAL MATCH (section)-[n_rel:PROGRESSES_TO]->(nxt:Section)
        OPTIONAL MATCH (doc)-[:REMEDIES_DILEMMA]->(sol:Concept) WHERE NOT sol:Ingestion
        WITH doc, section, vector_score,
             collect(DISTINCT target.title) AS links,
             collect(DISTINCT t.name) AS tags,
             coalesce(doc.gds_pagerank, 0.005) AS authority,
             coalesce(doc.gds_community, 0) AS community,
             head(collect(DISTINCT {title: coalesce(prev.displayName, prev.name), warrant: p_rel.warrant, excerpt: substring(prev.content, 0, 220)})) AS prev_step,
             head(collect(DISTINCT {title: coalesce(nxt.displayName, nxt.name), warrant: n_rel.warrant, excerpt: substring(nxt.content, 0, 220)})) AS next_step,
             collect(DISTINCT sol.title)[0..3] AS remedies
        WITH doc, section, vector_score, links, tags, authority, community, prev_step, next_step, remedies,
             (vector_score * $v_weight) + (authority * 10.0 * $a_weight) AS composite_rank
        RETURN doc.title AS document,
               coalesce(section.displayName, section.name) AS section_title,
               section.content AS content,
               tags AS tags,
               community AS community_id,
               authority AS authority_score,
               links AS referenced_concepts,
               prev_step,
               next_step,
               remedies,
               round(vector_score, 3) AS vector_similarity,
               round(composite_rank, 3) AS composite_score
        ORDER BY composite_rank DESC
        LIMIT $top_k
        """
        params = {
            "top_k": self.valves.TOP_K,
            "q_vec": q_vec,
            "step_filter": step_filter,
            "exclude_doc": exclude_doc,
            "v_weight": self.valves.VECTOR_WEIGHT,
            "a_weight": self.valves.AUTHORITY_WEIGHT,
        }

        span = self._start_cypher_span(
            parent_obs,
            "1.4_vector_hybrid_search",
            cypher,
            {k: (v if k != "q_vec" else f"[vector_dim_{len(q_vec)}]") for k, v in params.items()},
            {"step_filter": step_filter, "exclude_doc": exclude_doc},
        )

        try:
            results = session.run(cypher, **params).data()
            if span:
                span.update(
                    output={
                        "hits_count": len(results),
                        "top_document": results[0]["document"] if results else None,
                    }
                )
                span.end()
            return results
        except Exception as e:
            logger.error(f"Error querying Neo4j vector/graph index: {e}")
            if span:
                span.update(output={"error": str(e)})
                span.end()
            return []

    async def inlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
        __event_emitter__: Optional[Callable] = None,
    ) -> dict:
        """
        Pre-inference inlet hook: Establishes complete context before any LLM invocation.
        Executes Dual-Flow CoT intent classification, Lucene resolution, SAM continuity, and vector load.
        """
        messages = body.get("messages", [])
        if not messages:
            return body

        user_message = next((m for m in reversed(messages) if m.get("role") == "user"), None)
        if not user_message:
            return body

        query_text = user_message.get("content", "").strip()
        if not query_text or len(query_text) < 3:
            return body

        metadata = __metadata__ or {}
        chat_id = metadata.get("chat_id") or metadata.get("session_id") or body.get("chat_id") or "default_session"
        user_email = __user__.get("email", "anonymous") if __user__ else "anonymous"

        # Check if the user is answering a pending Context Transition Decision
        session_state = self._chat_sessions.get(chat_id, {})
        pending_shift = session_state.get("pending_shift")

        if pending_shift:
            # Check for Yes / Clear
            is_yes = bool(
                re.search(
                    r"^\s*(yes|clear|ja|ja, bitte|bitte löschen|clear prior context|yes, clear prior context)\b",
                    query_text,
                    re.IGNORECASE,
                )
            )
            # Check for No / Keep
            is_no = bool(
                re.search(
                    r"^\s*(no|keep|nein|behalten|keep prior context|no, keep prior context|bridge)\b",
                    query_text,
                    re.IGNORECASE,
                )
            )

            if is_yes:
                from_entity = pending_shift.get("from_entity", "Previous Topic")
                to_entity = pending_shift.get("to_entity", "New Topic")
                to_community = pending_shift.get("to_community", 0)

                # Clear pending_shift and isolate working memory to to_entity
                self._chat_sessions[chat_id] = {
                    "entity": to_entity,
                    "community": to_community,
                    "type": pending_shift.get("to_type", "unknown"),
                }

                confirmation_block = (
                    f"> [!NOTE] **Context Cleared & Isolated**\n"
                    f"> Prior context from **[[{from_entity}]]** has been cleared from active working memory.\n"
                    f"> The conversation is now isolated exclusively to **[[{to_entity}]]** (Thematic Cluster {to_community}).\n\n"
                    f"Acknowledge clearly in 1–2 sentences that the prior context from [[{from_entity}]] has been cleared and that working memory is now focused solely on [[{to_entity}]]. Briefly suggest 2–3 key inquiry directions for exploring [[{to_entity}]]."
                )

                system_msg = {"role": "system", "content": confirmation_block}
                body["messages"] = [system_msg, user_message]

                if self.valves.ENABLE_LANGFUSE:
                    lf = self._get_langfuse()
                    if lf:
                        try:
                            s_dec = lf.start_observation(
                                name="1.5_context_decision",
                                as_type="span",
                                input={"decision": "clear", "from_entity": from_entity, "to_entity": to_entity},
                            )
                            s_dec.update(output={"context_cleared": True, "active_entity": to_entity})
                            s_dec.end()
                            lf.flush()
                        except Exception:
                            pass

                return body

            elif is_no:
                from_entity = pending_shift.get("from_entity", "Previous Topic")
                to_entity = pending_shift.get("to_entity", "New Topic")
                to_community = pending_shift.get("to_community", 0)

                # Keep prior context and record bridged state
                self._chat_sessions[chat_id] = {
                    "entity": to_entity,
                    "community": to_community,
                    "bridged_with": from_entity,
                    "type": pending_shift.get("to_type", "unknown"),
                }

                bridge_block = (
                    f"> [!NOTE] **Context Retained & Bridged**\n"
                    f"> Prior context from **[[{from_entity}]]** is preserved alongside **[[{to_entity}]]**.\n\n"
                    f"Synthesize the conceptual connection between **[[{to_entity}]]** and **[[{from_entity}]]**, drawing upon the knowledge graph context from both topics to highlight theoretical touchpoints or differences."
                )

                system_msg = next((m for m in messages if m.get("role") == "system"), None)
                if system_msg:
                    system_msg["content"] = f"{bridge_block}\n\n{system_msg['content']}"
                else:
                    messages.insert(0, {"role": "system", "content": bridge_block})

                if self.valves.ENABLE_LANGFUSE:
                    lf = self._get_langfuse()
                    if lf:
                        try:
                            s_dec = lf.start_observation(
                                name="1.5_context_decision",
                                as_type="span",
                                input={"decision": "keep", "from_entity": from_entity, "to_entity": to_entity},
                            )
                            s_dec.update(output={"context_cleared": False, "bridged": True})
                            s_dec.end()
                            lf.flush()
                        except Exception:
                            pass

                return body
            else:
                # User asked a different substantive question; consume pending_shift
                session_state.pop("pending_shift", None)

        driver = self._get_driver()
        if not driver:
            logger.warning("Neo4j driver unavailable; proceeding without graph grounding.")
            return body

        # Extract multi-turn history & state
        user_turns = [m for m in messages if m.get("role") == "user"]
        is_followup = len(user_turns) > 1

        # Check in-memory session cache for previous turn's state
        prev_entities: List[str] = []
        prev_community: Optional[int] = None

        session_state = self._chat_sessions.get(chat_id)
        if session_state:
            prev_entity = session_state.get("entity")
            if prev_entity and prev_entity != "None":
                prev_entities.append(prev_entity)
            prev_community = session_state.get("community")

        # Check existing system message for active session markers as secondary check
        system_msg = next((m for m in messages if m.get("role") == "system"), None)
        if not prev_entities and system_msg and system_msg.get("content"):
            m_tag = re.search(r"<!-- ActiveSession: entity=\"([^\"]+)\" community=\"(\d+)\" -->", system_msg["content"])
            if m_tag:
                prev_entities.append(m_tag.group(1))
                prev_community = int(m_tag.group(2))

        # Initialize Root Langfuse Tracing
        lf = self._get_langfuse()
        root_obs = None

        if lf:
            try:
                root_obs = lf.start_observation(
                    name="chat_turn",
                    as_type="generation",
                    model=body.get("model", "unknown"),
                    input=query_text,
                    metadata={
                        "chat_id": chat_id,
                        "user_id": user_email,
                        "tag": self.valves.PROJECT_TAG,
                        "is_followup": is_followup,
                    },
                )
            except Exception as e:
                logger.debug(f"Langfuse root trace error: {e}")

        # 1. Dual-Flow CoT Intent Classification
        intent, target_step_type, target_label = self._classify_intent(query_text)
        logger.info(f"Dual-Flow CoT Intent: Query='{query_text}' | Intent={intent} | StepType={target_step_type}")

        if root_obs:
            try:
                s_intent = root_obs.start_observation(
                    name="1.1_intent_classification",
                    as_type="span",
                    input=query_text,
                )
                s_intent.update(
                    output={
                        "intent": intent,
                        "target_step_type": target_step_type,
                        "target_label": target_label,
                    }
                )
                s_intent.end()
            except Exception:
                pass

        context_parts = ["\n\n--- Relevant Knowledge Graph Context (Dual-Flow CoT Grounding) ---"]
        active_focal_title = None
        active_community = 0
        context_shifted = False

        with driver.session() as session:
            # Fallback: Extract previous entity from conversation history if not cached
            if is_followup and (not prev_entities or prev_community is None):
                for past_turn in reversed(user_turns[:-1]):
                    past_text = past_turn.get("content", "")
                    past_resolved = self._resolve_entity(session, past_text, parent_obs=None)
                    if past_resolved:
                        if not prev_entities:
                            prev_entities.append(past_resolved["title"])
                        if prev_community is None:
                            prev_community = past_resolved.get("community")
                        logger.info(f"Fallback extracted previous entity from history: {past_resolved['title']} (Community {prev_community})")
                        break

            # Check for explicit topic shift phrasing in user query
            explicit_shift = bool(
                re.search(
                    r"\b(switch(ing)?\s+topics?|new\s+topic|different\s+(topic|question)|change\s+(the\s+)?subject|changing\s+topics?|unrelated(\s+question)?|on\s+another\s+note|by\s+the\s+way|moving\s+on\s+to|anderes\s+thema|neues\s+thema)\b",
                    query_text,
                    re.IGNORECASE,
                )
            )

            # 2. Lucene Full-Text Search
            entity = None
            if self.valves.ENABLE_DETERMINISTIC_ROUTER:
                entity = self._resolve_entity(session, query_text, parent_obs=root_obs)

            # 3. Context Continuity / SAM Check (Step 2 Follow-up)
            if is_followup:
                if explicit_shift:
                    context_shifted = True
                    logger.info(f"Context Shift Detected via explicit user intent phrasing in query: '{query_text}'")
                elif entity and prev_entities:
                    continuity_data = self._check_sam_continuity(
                        session, entity["title"], prev_entities, parent_obs=root_obs
                    )
                    tight_cot_edges = continuity_data.get("tight_cot_edges", 0)
                    curr_comm = continuity_data.get("current_community", 0)

                    if prev_community is not None and curr_comm != prev_community and tight_cot_edges == 0:
                        context_shifted = True
                        logger.info(f"Context Shift Detected: Moved from Community {prev_community} ({prev_entities[0]}) to {curr_comm} ({entity['title']}) with {tight_cot_edges} tight CoT edges")


            # 4. Retrieval Branching: Concept vs Entity vs Vector Fallback
            if entity:
                active_focal_title = entity["title"]
                active_community = entity.get("community", 0)
                labels = entity.get("labels", [])

                if "Concept" in labels:
                    c_data = self._query_concept_sections(
                        session, entity, intent, target_step_type, target_label, parent_obs=root_obs
                    )
                    arc_lines = [
                        f"\n### [Primary Matched Concept]: [[{c_data['entity']}]]",
                        f"- **Network Authority**: {c_data['authority']:.4f} | **Thematic Cluster**: Community {c_data['community']}",
                        f"- **Epistemic Retrieval Intent**: {intent}",
                    ]
                    if c_data.get("remedies"):
                        arc_lines.append("- **Countermeasures & Remedies**: " + ", ".join(f"[[{r}]]" for r in c_data["remedies"]))
                    if c_data.get("mitigates_problems"):
                        arc_lines.append("- **Resolves Dilemmas**: " + ", ".join(f"[[{p}]]" for p in c_data["mitigates_problems"]))
                    if c_data.get("theories"):
                        arc_lines.append("- **Theoretical Foundations**: " + ", ".join(f"[[{t}]]" for t in c_data["theories"]))
                    if c_data.get("traps"):
                        arc_lines.append("- **Downstream Failure Modes**: " + ", ".join(f"[[{tr}]]" for tr in c_data["traps"]))
                    if c_data.get("citations"):
                        arc_lines.append("- **Key Citations**: " + ", ".join(f"[[{c}]]" for c in c_data["citations"]))

                    if c_data.get("sections"):
                        for sec in c_data["sections"]:
                            content = sec.get("content", "").strip()[: self.valves.EXCERPT_CHAR_LIMIT]
                            arc_lines.append(f"\n#### Section: {sec.get('title', 'Excerpt')}\n{content}")

                    # Step 2: Extend context with missing nodes from the SAME gds_community only
                    if is_followup and not context_shifted and self.valves.SAM_COMMUNITY_STRICT_MODE:
                        comm_nodes = self._query_community_nodes(session, active_community, active_focal_title)
                        if comm_nodes:
                            arc_lines.append(f"\n- **Extended Community Context (Cluster {active_community})**: " + ", ".join(f"[[{n}]]" for n in comm_nodes))

                    context_parts.append("\n".join(arc_lines) + "\n")

                else:  # Entity Branch
                    e_data = self._query_entity_sections(session, entity, parent_obs=root_obs)
                    arc_lines = [
                        f"\n### [Primary Matched Entity]: [[{e_data['entity']}]] ({e_data['subtype'].upper()})",
                        f"- **Network Authority**: {e_data['authority']:.4f} | **Thematic Cluster**: Community {e_data['community']}",
                    ]
                    if e_data.get("related_targets"):
                        arc_lines.append("- **Key Relational Primitives**: " + ", ".join(f"[[{rt}]]" for rt in e_data["related_targets"]))

                    if e_data.get("sections"):
                        for sec in e_data["sections"]:
                            content = sec.get("content", "").strip()[: self.valves.EXCERPT_CHAR_LIMIT]
                            arc_lines.append(f"\n#### Section: {sec.get('title', 'Profile')}\n{content}")

                    context_parts.append("\n".join(arc_lines) + "\n")

            # 5. Complementary or Fallback Vector Search
            vec_top_k = self.valves.TOP_K if not entity else 1
            q_vec = await self._get_embedding(query_text)
            if q_vec:
                filter_type = target_step_type if not entity else None
                hits = self._hybrid_graph_search(
                    session,
                    q_vec,
                    step_filter=filter_type,
                    exclude_doc=active_focal_title,
                    parent_obs=root_obs,
                )
                if hits:
                    header = "### [Complementary Vault Sections]" if entity else "### [Hybrid Vector & Graph Matches]"
                    context_parts.append(header)
                    for idx, h in enumerate(hits[:vec_top_k], 1):
                        tags_str = ", ".join(f"#{t}" for t in h["tags"][:5]) if h["tags"] else "None"
                        links_str = ", ".join(f"[[{l}]]" for l in h["referenced_concepts"][:5]) if h["referenced_concepts"] else "None"

                        hit_lines = [
                            f"\n#### Match {idx}: [[{h['document']}]] | Section: {h['section_title']}",
                            f"- **Tags**: {tags_str} | **Authority**: {h['authority_score']:.4f}",
                            f"- **Connected Concepts**: {links_str}",
                        ]
                        if self.valves.INCLUDE_REMEDIES and h.get("remedies"):
                            remedies_str = ", ".join(f"[[{r}]]" for r in h["remedies"][: self.valves.MAX_REMEDIES_COUNT])
                            hit_lines.append(f"- **Key Remedies**: {remedies_str}")

                        if self.valves.ENABLE_COT_WINDOWING and h.get("prev_step"):
                            prev = h["prev_step"]
                            if prev.get("title") and prev.get("title") != h["section_title"]:
                                warrant = f" [Warrant: {prev['warrant']}]" if prev.get("warrant") else ""
                                hit_lines.append(f"- **Antecedent Step** ({prev['title']}){warrant}:\n  > {prev.get('excerpt', '').strip()}...")

                        hit_lines.append(f"- **Focal Excerpt**:\n{h['content'].strip()[: self.valves.EXCERPT_CHAR_LIMIT]}")

                        if self.valves.ENABLE_COT_WINDOWING and h.get("next_step"):
                            nxt = h["next_step"]
                            if nxt.get("title") and nxt.get("title") != h["section_title"]:
                                warrant = f" [Warrant: {nxt['warrant']}]" if nxt.get("warrant") else ""
                                hit_lines.append(f"- **Subsequent Step** ({nxt['title']}){warrant}:\n  > {nxt.get('excerpt', '').strip()}...")

                        context_parts.append("\n".join(hit_lines) + "\n")

        # 6. Context Shift Handling & Notice Generation
        shift_header = ""
        if context_shifted:
            prev_name = prev_entities[0] if prev_entities else "Previous Topic"
            curr_name = active_focal_title or (entity["title"] if entity else "New Topic")
            curr_comm = active_community or (entity.get("community", 0) if entity else 0)

            # Store pending shift in session state for Yes/No resolution in the subsequent turn
            self._chat_sessions.setdefault(chat_id, {})["pending_shift"] = {
                "from_entity": prev_name,
                "from_community": prev_community,
                "to_entity": curr_name,
                "to_community": curr_comm,
                "to_type": entity.get("type", "unknown") if entity else "unknown",
            }

            chips = ["Yes, clear prior context", "No, keep prior context"]
            self._active_follow_ups[chat_id] = chips
            if query_text:
                self._active_follow_ups[f"msg_{hash(query_text[:60])}"] = chips

            notice_banner = (
                f"> [!WARNING] **Context Transition Detected**\n"
                f"> Topic shifted from **[[{prev_name}]]** (Thematic Cluster {prev_community}) to **[[{curr_name}]]** (Thematic Cluster {curr_comm}).\n"
                f">\n"
                f"> **Do you want to clear prior context from active working memory?**\n"
                f"> - **[Yes, clear prior context]** — Isolates working memory exclusively to [[{curr_name}]].\n"
                f"> - **[No, keep prior context]** — Bridges [[{prev_name}]] with [[{curr_name}]]."
            )
            self._active_notices[chat_id] = notice_banner
            if query_text:
                self._active_notices[f"msg_{hash(query_text[:60])}"] = notice_banner

            if self.valves.CONTEXT_SHIFT_STRATEGY == "ask_user":
                shift_header = (
                    f"> [!WARNING] **Context Transition Detected**\n"
                    f"> Topic shifted from **[[{prev_name}]]** (Thematic Cluster {prev_community}) to **[[{curr_name}]]** (Thematic Cluster {curr_comm}).\n"
                    f">\n"
                    f"> **Do you want to clear prior context from active working memory?**\n"
                    f"> - **[Yes, clear prior context]** — Isolates working memory exclusively to [[{curr_name}]].\n"
                    f"> - **[No, keep prior context]** — Bridges [[{prev_name}]] with [[{curr_name}]].\n\n"
                    f"IMPORTANT INSTRUCTIONS FOR ASSISTANT:\n"
                    f"1. Ground your answer strictly on the vault context for **[[{curr_name}]]** below.\n"
                    f"2. Answer the user's question about **[[{curr_name}]]** directly, concisely, and factually.\n"
                    f"3. Do NOT add conversational questions, chit-chat, or confusion about bridging at the end of your response, as the clickable UI chips above will present the choice.\n\n"
                )
            else:
                shift_header = (
                    f"> [!WARNING] **Context Transition Notice**\n"
                    f"> Switched topic from **[[{prev_name}]]** (Thematic Cluster {prev_community}) to **[[{curr_name}]]** (Thematic Cluster {curr_comm}).\n"
                    f"> Prior context has been automatically cleared from working memory. Ground your response strictly on **[[{curr_name}]]**.\n\n"
                )
            logger.info(f"Context shift: Stored notice banner and decision chips for chat_id={chat_id}")

        # 7. Stateful Context Replacement & Assembly
        session_marker = f"<!-- ActiveSession: entity=\"{active_focal_title or 'None'}\" community=\"{active_community}\" -->\n"
        context_parts.append("--- End Graph Context ---\n")
        context_block = shift_header + session_marker + "\n".join(context_parts)

        # Regex to strip legacy context blocks from prior turns to avoid prompt bloat
        context_regex = re.compile(
            r"(> \[!WARNING\] \*\*Context Transition Notice\*\*.*?\n\n)?(<!-- ActiveSession:.*?-->\n)?\n*--- Relevant Knowledge Graph Context \(Dual-Flow CoT Grounding\) ---.*?--- End Graph Context ---\n*",
            re.DOTALL,
        )

        if system_msg:
            cleaned_system = context_regex.sub("", system_msg.get("content", "")).strip()
            system_msg["content"] = f"{cleaned_system}\n\n{context_block}" if cleaned_system else context_block
        else:
            system_msg = {"role": "system", "content": context_block}
            messages.insert(0, system_msg)

        # When context shifts: Prune prior user/assistant turns from body["messages"] so the LLM does NOT extend stale context
        if context_shifted:
            current_user_turn = next((m for m in reversed(messages) if m.get("role") == "user"), None)
            messages = [m for m in [system_msg, current_user_turn] if m is not None]
            logger.info(f"Context shift: Pruned prior conversation turns from body['messages'] for chat_id={chat_id}. Payload isolated to new turn.")

        # Update in-memory session cache for subsequent turns
        self._chat_sessions[chat_id] = {
            "entity": active_focal_title or (entity["title"] if entity else "None"),
            "community": active_community or (entity.get("community", 0) if entity else 0),
            "type": entity.get("type", "unknown") if entity else "unknown",
        }

        # Close Span 1.5 Context Assembly
        if root_obs:
            try:
                s_assemble = root_obs.start_observation(
                    name="1.5_context_assembly",
                    as_type="span",
                    input={"focal_entity": active_focal_title, "community": active_community, "context_shifted": context_shifted},
                )
                s_assemble.update(output={"context_chars": len(context_block), "system_injected": True, "context_cleared": context_shifted})
                s_assemble.end()
            except Exception:
                pass

        # Deactivate follow-up question generation in Open WebUI if valve set
        if not self.valves.ALLOW_FOLLOW_UP_GENERATION:
            body["generate_follow_up"] = False

        body["messages"] = messages
        return body

    def _extract_usage(
        self,
        assistant_msg: Optional[dict],
        body: dict,
        user_msg: Optional[dict] = None,
    ) -> Tuple[Optional[dict], Optional[dict]]:
        usage = (assistant_msg.get("usage") if assistant_msg else None) or body.get("usage") or {}
        info = (assistant_msg.get("info") if assistant_msg else None) or {}

        input_tokens = (
            usage.get("input_tokens")
            or usage.get("prompt_tokens")
            or info.get("prompt_eval_count")
        )
        output_tokens = (
            usage.get("output_tokens")
            or usage.get("completion_tokens")
            or info.get("eval_count")
        )
        total_tokens = (
            usage.get("total_tokens")
            or (
                (int(input_tokens or 0) + int(output_tokens or 0))
                if (input_tokens is not None or output_tokens is not None)
                else None
            )
        )

        usage_details = None
        if input_tokens is not None or output_tokens is not None:
            usage_details = {
                "input": int(input_tokens or 0),
                "output": int(output_tokens or 0),
                "total": int(total_tokens or 0),
            }
            comp_details = usage.get("completion_tokens_details") or {}
            if "reasoning_tokens" in comp_details and comp_details["reasoning_tokens"]:
                usage_details["reasoning"] = int(comp_details["reasoning_tokens"])
        else:
            u_text = user_msg.get("content", "") if user_msg else ""
            a_text = assistant_msg.get("content", "") if assistant_msg else ""
            if u_text or a_text:
                in_est = max(1, len(u_text.split()) * 4 // 3) if u_text else 0
                out_est = max(1, len(a_text.split()) * 4 // 3) if a_text else 0
                usage_details = {
                    "input": in_est,
                    "output": out_est,
                    "total": in_est + out_est,
                }

        cost_details = None
        cost = usage.get("cost")
        if cost is not None:
            try:
                cost_details = {"total": float(cost)}
            except (ValueError, TypeError):
                pass

        return usage_details, cost_details

    async def outlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
        __event_emitter__: Optional[Callable] = None,
    ) -> dict:
        """Post-processing outlet hook: prepends transition notices, emits UI chips, and logs generation output to Langfuse."""
        messages = body.get("messages", [])
        user_msg = next((m for m in reversed(messages) if m.get("role") == "user"), None)
        assistant_msg = next((m for m in reversed(messages) if m.get("role") == "assistant"), None)

        metadata = __metadata__ or {}
        chat_id = metadata.get("chat_id") or metadata.get("session_id") or body.get("chat_id") or "default_session"

        # 1. Prepend Context Transition Notice Banner to Assistant Output
        if assistant_msg:
            notice = self._active_notices.pop(chat_id, None)
            if not notice and user_msg:
                notice = self._active_notices.pop(f"msg_{hash(user_msg.get('content', '')[:60])}", None)
            if notice:
                assistant_msg["content"] = f"{notice}\n\n{assistant_msg.get('content', '')}"

        # 2. Emit Native Interactive UI Chips (Yes / No Follow-Up Decision)
        follow_ups = self._active_follow_ups.pop(chat_id, None)
        if not follow_ups and user_msg:
            follow_ups = self._active_follow_ups.pop(f"msg_{hash(user_msg.get('content', '')[:60])}", None)

        if follow_ups:
            if assistant_msg:
                assistant_msg["follow_ups"] = follow_ups
            body["follow_ups"] = follow_ups

            if __event_emitter__:
                try:
                    await __event_emitter__({
                        "type": "chat:message:follow_ups",
                        "data": {
                            "follow_ups": follow_ups,
                        },
                    })
                except Exception as e:
                    logger.debug(f"Event emitter follow_ups error: {e}")

        # 3. Langfuse Observability & Metrics
        lf = self._get_langfuse()
        if not lf:
            return body

        try:
            if assistant_msg:
                usage_details, cost_details = self._extract_usage(assistant_msg, body, user_msg)
                gen_kwargs = {
                    "name": "assistant_generation",
                    "as_type": "generation",
                    "model": body.get("model", "unknown"),
                    "input": user_msg.get("content", "") if user_msg else None,
                    "output": assistant_msg.get("content", "")[:4000],
                    "metadata": {"chat_id": chat_id},
                }
                if usage_details:
                    gen_kwargs["usage_details"] = usage_details
                if cost_details:
                    gen_kwargs["cost_details"] = cost_details

                gen = lf.start_observation(**gen_kwargs)
                gen.end()
                lf.flush()
        except Exception as e:
            logger.debug(f"Langfuse outlet error: {e}")

        return body

