"""
services/fastmcp/dialect_switcher.py
Three-tier Query Dialect Switcher and Semantic Intent Classifier for ArcadeDB.
Coordinates routing between OpenCypher 25 and ArcadeDB Multi-Model SQL.
"""

import re
from typing import NamedTuple, Tuple


class RouteResult(NamedTuple):
    clean_prompt: str
    dialect: str
    intent: str
    is_raw_query: bool
    routing_reason: str


class QueryDialectSwitcher:
    """Three-Tier Query Dialect Switcher & Intent Classifier."""

    COMMAND_VERBS = [
        "MATCH", "SELECT", "OPTIONAL", "CALL", "WITH", "UNWIND", "EXPLAIN", "PROFILE",
        "CREATE", "DROP", "ALTER", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "SET"
    ]

    INTENT_KEYWORDS = {
        "shortest_path": ["shortest path", "how to transition", "path between", "learning trajectory"],
        "bridging_paths": ["bridging", "2-hop", "intermediary", "bridge between", "intermediate concept"],
        "cot_remedy_out": ["remedy", "remedies", "solve", "mitigat", "countermeasure", "safeguard", "fix"],
        "cot_remedy_in": ["incoming remedy", "target remedy", "independently remedy", "address"],
        "pagerank_ranking": ["pagerank", "authority", "top ranked", "centrality", "most influential"],
        "entity_ranking": ["top entity", "top entities", "ranked researchers", "ranked organizations"],
        "community_cluster": ["community", "cluster", "louvain", "thematic group"],
        "vector_knn": ["vector", "knn", "nearest neighbor", "embedding distance", "vectorneighbors"],
        "hybrid_search": ["hybrid search", "parent document", "similar sections with parent"],
        "cot_progression": ["micro-cot", "reasoning step", "progression", "progresses_to", "argument flow"],
        "alias_resolution": ["alias lookup", "disambiguate alias", "canonical title", "pcf", "aliaslookup"],
        "entity_agency": ["agency", "originate theory", "operationalize", "champion solution", "critique paradigm"],
        # Toulmin & Epistemic Weight Intents
        "teachable_agent_gating": ["teachable agent", "apprentice context", "naïve apprentice", "withhold solution", "sparring mode", "without answer"],
        "weighted_warrants": ["weighted warrant", "epistemic weight", "warrant weight", "ranked warrants", "warrants ranked"],
        "signed_rebuttal_ranking": ["signed attack", "attack weight", "signed rebuttal", "strongest rebuttal", "strongest counter-argument", "attack surface"],
        "high_confidence_toulmin": ["high confidence", "certainty threshold", "weight threshold", "confidence above", "evidence above 0."],
        "modal_weight_distribution": ["modal distribution", "modal certainty", "linguistic weight across", "weight distribution", "certainty distribution"],
        "toulmin_warrant": ["why does", "how does", "causal anatomy", "underlying mechanics", "mechanism of", "warrant", "has_warrant"],
        "toulmin_rebuttal": ["failure modes of", "failure mode", "pathologies of", "traps of", "rebuttal", "has_rebuttal", "what breaks in", "what goes wrong"],
        "toulmin_solution": ["solution warrant", "prescriptive mitigation", "counter-architecture", "how to fix", "how to remedy", "has_solution"],
        "toulmin_grounds": ["definitional anchor", "empirical grounds", "data anchor", "grounds of", "has_grounds", "evidence for"],
        # Visualization & Diagram Intents
        "diagram_visualization": ["show diagram", "visualize", "render diagram", "mermaid diagram", "draw flowchart", "display diagram", "diagram of", "see diagram", "diagrams for"],
    }

    @classmethod
    def is_raw_command(cls, text: str) -> bool:
        """Determines whether the given string is a raw database query statement."""
        tokens = text.strip().split()
        first_token = tokens[0].upper() if tokens else ""
        return first_token in cls.COMMAND_VERBS

    @classmethod
    def classify_intent(cls, prompt: str) -> str:
        """Classifies the query intent against the calibrated analytical archetypes."""
        p_lower = prompt.lower()

        # Check in order of specificity
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["diagram_visualization"]):
            return "diagram_visualization"
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["teachable_agent_gating"]):
            return "teachable_agent_gating"
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["weighted_warrants"]):
            return "weighted_warrants"
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["signed_rebuttal_ranking"]):
            return "signed_rebuttal_ranking"
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["high_confidence_toulmin"]):
            return "high_confidence_toulmin"
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["modal_weight_distribution"]):
            return "modal_weight_distribution"
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["toulmin_warrant"]):
            return "toulmin_warrant"
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["toulmin_rebuttal"]):
            return "toulmin_rebuttal"
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["toulmin_solution"]):
            return "toulmin_solution"
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["toulmin_grounds"]):
            return "toulmin_grounds"

        if any(k in p_lower for k in cls.INTENT_KEYWORDS["bridging_paths"]):
            return "bridging_paths"
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["shortest_path"]):
            return "shortest_path"

        # CoT remedies
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["cot_remedy_in"]):
            return "cot_remedy_in"
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["cot_remedy_out"]):
            return "cot_remedy_out"

        # Rankings
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["entity_ranking"]):
            return "entity_ranking"
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["pagerank_ranking"]):
            if any(e in p_lower for e in ["entity", "researcher", "organization", "software"]):
                return "entity_ranking"
            return "pagerank_ranking"

        # Communities
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["community_cluster"]):
            return "community_cluster"

        # Vector & Hybrid
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["hybrid_search"]):
            return "hybrid_search"
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["vector_knn"]):
            return "vector_knn"

        # Progressions & Micro-CoT
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["cot_progression"]):
            return "cot_progression"

        # Aliases
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["alias_resolution"]):
            return "alias_resolution"

        # Agency
        if any(k in p_lower for k in cls.INTENT_KEYWORDS["entity_agency"]):
            return "entity_agency"

        return "general"

    @classmethod
    def route(
        cls,
        raw_message: str,
        preferred_dialect: str = "auto",
    ) -> RouteResult:
        """
        Executes 3-tier routing:
        Tier 1: Explicit user slash commands (/sql, /cypher).
        Tier 2: Model / client valve setting (if 'sql' or 'cypher').
        Tier 3: Dynamic semantic intent classifier (when 'auto').
        """
        stripped = raw_message.strip()

        # Tier 1: Slash Commands
        if stripped.startswith("/sql"):
            clean_prompt = re.sub(r"^/sql\s*", "", stripped).strip()
            intent = cls.classify_intent(clean_prompt)
            is_raw = cls.is_raw_command(clean_prompt)
            return RouteResult(
                clean_prompt=clean_prompt,
                dialect="sql",
                intent=intent,
                is_raw_query=is_raw,
                routing_reason="Tier 1: Explicit slash command /sql",
            )
        elif stripped.startswith("/cypher"):
            clean_prompt = re.sub(r"^/cypher\s*", "", stripped).strip()
            intent = cls.classify_intent(clean_prompt)
            is_raw = cls.is_raw_command(clean_prompt)
            return RouteResult(
                clean_prompt=clean_prompt,
                dialect="cypher",
                intent=intent,
                is_raw_query=is_raw,
                routing_reason="Tier 1: Explicit slash command /cypher",
            )

        # Clean prompt for Tier 2 and Tier 3
        clean_prompt = stripped
        intent = cls.classify_intent(clean_prompt)
        is_raw = cls.is_raw_command(clean_prompt)

        # Tier 2: Model Valve Setting
        pref = (preferred_dialect or "auto").lower()
        if pref in ("sql", "cypher"):
            return RouteResult(
                clean_prompt=clean_prompt,
                dialect=pref,
                intent=intent,
                is_raw_query=is_raw,
                routing_reason=f"Tier 2: Configured valve preference '{pref}'",
            )

        # Tier 3: Dynamic Intent Classification (auto)
        sql_intents = {"vector_knn", "hybrid_search", "alias_resolution", "modal_weight_distribution"}
        if is_raw:
            first_token = clean_prompt.split()[0].upper() if clean_prompt.split() else ""
            detected_dialect = "sql" if first_token in ["SELECT", "FROM"] else "cypher"
            return RouteResult(
                clean_prompt=clean_prompt,
                dialect=detected_dialect,
                intent=intent,
                is_raw_query=True,
                routing_reason=f"Tier 3: Raw query detected starting with '{first_token}'",
            )

        if intent in sql_intents:
            return RouteResult(
                clean_prompt=clean_prompt,
                dialect="sql",
                intent=intent,
                is_raw_query=False,
                routing_reason=f"Tier 3: Intent '{intent}' maps to native ArcadeDB SQL",
            )

        # Default graph dialect is OpenCypher for paths, remedies, and clusters
        return RouteResult(
            clean_prompt=clean_prompt,
            dialect="cypher",
            intent=intent,
            is_raw_query=False,
            routing_reason=f"Tier 3: Intent '{intent}' maps to OpenCypher graph traversal",
        )
