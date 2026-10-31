"""
services/fastmcp/dail_retriever.py
DAIL-SQL Few-Shot Retrieval Engine for ArcadeDB.
Queries the TextToQueryDemo collection in ArcadeDB to fetch top-k relevant query exemplars.
"""

import re
from typing import Any, Dict, List, Optional

from .arcadedb_client import ArcadeDBHttpClient


class DAILSQLRetriever:
    """Retrieves verified few-shot Question-Query demonstrations from ArcadeDB."""

    def __init__(self, client: Optional[ArcadeDBHttpClient] = None):
        self.client = client or ArcadeDBHttpClient()

    def classify_intent(self, question: str) -> str:
        """Classifies the analytical intent of the natural language inquiry."""
        q_lower = question.lower()

        # Toulmin Argumentation Intents
        if any(term in q_lower for term in ["teachable agent", "apprentice context", "naïve apprentice", "withhold solution", "sparring mode", "without answer"]):
            return "teachable_agent_gating"
        if any(term in q_lower for term in ["why does", "how does", "causal anatomy", "underlying mechanics", "mechanism of", "warrant", "has_warrant"]):
            return "toulmin_warrant"
        if any(term in q_lower for term in ["failure modes of", "failure mode", "pathologies of", "traps of", "rebuttal", "has_rebuttal", "what breaks in", "what goes wrong"]):
            return "toulmin_rebuttal"
        if any(term in q_lower for term in ["solution warrant", "prescriptive mitigation", "counter-architecture", "how to fix", "how to remedy", "has_solution"]):
            return "toulmin_solution"
        if any(term in q_lower for term in ["definitional anchor", "empirical grounds", "data anchor", "grounds of", "has_grounds", "evidence for"]):
            return "toulmin_grounds"

        # Shortest path / navigation
        if "shortest path" in q_lower or ("path" in q_lower and "between" in q_lower):
            return "shortest_path"
        if "bridging" in q_lower or "2-hop" in q_lower or "intermediary" in q_lower:
            return "bridging_paths"

        # CoT Remedies / Mitigations
        if any(term in q_lower for term in ["remedy", "remedies", "mitigat", "countermeasure", "solve", "safeguard"]):
            if any(term in q_lower for term in ["target", "incoming", "independently"]):
                return "cot_remedy_in"
            return "cot_remedy_out"

        # Centrality & PageRank
        if "pagerank" in q_lower or "authority" in q_lower or "top ranked" in q_lower or "most prominent" in q_lower:
            if any(term in q_lower for term in ["entity", "entities", "researcher", "organization", "software"]):
                return "entity_ranking"
            return "pagerank_ranking"

        # Community clustering
        if "community" in q_lower or "cluster" in q_lower or "louvain" in q_lower:
            return "community_cluster"

        # Vector KNN & Semantic similarity
        if any(term in q_lower for term in ["vector", "knn", "nearest neighbor", "embedding", "distance"]):
            return "vector_knn"
        if "hybrid" in q_lower or ("similar" in q_lower and "parent" in q_lower):
            return "hybrid_search"

        # Micro-CoT reasoning progression
        if any(term in q_lower for term in ["progression", "reasoning step", "micro-cot", "progresses_to", "argument flow"]):
            return "cot_progression"

        # Alias resolution
        if any(term in q_lower for term in ["alias", "disambiguate", "canonical", "aliaslookup"]):
            return "alias_resolution"

        # Entity agency
        if any(term in q_lower for term in ["agency", "originate", "operationalize", "champion", "critique"]):
            return "entity_agency"

        return "general"

    def infer_dialect(self, question: str, default_dialect: str = "auto") -> str:
        """Determines target query dialect ('sql' or 'cypher')."""
        clean_q = question.strip()

        # Explicit slash commands override everything
        if clean_q.startswith("/sql"):
            return "sql"
        if clean_q.startswith("/cypher"):
            return "cypher"

        # Check explicit default valve
        if default_dialect in ("sql", "cypher"):
            return default_dialect

        # Intent-based heuristic routing
        intent = self.classify_intent(clean_q)
        sql_intents = {"vector_knn", "hybrid_search", "alias_resolution"}
        if intent in sql_intents:
            return "sql"

        # Default graph dialect for multi-hop, paths, and CoT is OpenCypher
        return "cypher"

    def retrieve_exemplars(
        self,
        question: str,
        dialect: str = "auto",
        top_k: int = 2,
    ) -> List[Dict[str, Any]]:
        """Queries TextToQueryDemo in ArcadeDB for matching exemplars."""
        clean_q = re.sub(r"^/(sql|cypher)\s*", "", question.strip())
        target_dialect = dialect if dialect in ("sql", "cypher") else self.infer_dialect(clean_q, dialect)
        intent = self.classify_intent(clean_q)

        # 1. Query by exact intent match
        sql_cmd = (
            "SELECT id, question, query, dialect, intent, complexity "
            "FROM TextToQueryDemo "
            "WHERE dialect = :dialect AND intent = :intent "
            "LIMIT :limit"
        )
        try:
            records = self.client.query(
                sql_cmd,
                language="sql",
                params={"dialect": target_dialect, "intent": intent, "limit": top_k},
            )
            if records:
                return records
        except Exception:
            pass

        # 2. Fallback: Retrieve by dialect alone
        fallback_sql = (
            "SELECT id, question, query, dialect, intent, complexity "
            "FROM TextToQueryDemo "
            "WHERE dialect = :dialect "
            "LIMIT :limit"
        )
        try:
            records = self.client.query(
                fallback_sql,
                language="sql",
                params={"dialect": target_dialect, "limit": top_k},
            )
            return records
        except Exception:
            return []

    def format_dail_prompt(
        self,
        question: str,
        dialect: str,
        exemplars: List[Dict[str, Any]],
    ) -> str:
        """Constructs an optimized DAIL-SQL generation prompt with zero schema boilerplate."""
        dialect_name = "ArcadeDB Multi-Model SQL" if dialect == "sql" else "OpenCypher 25"
        
        exemplar_blocks = []
        for idx, ex in enumerate(exemplars, 1):
            exemplar_blocks.append(
                f"-- Demonstration {idx} (Intent: {ex.get('intent', 'general')}):\n"
                f"-- Natural Language: {ex.get('question', '')}\n"
                f"{ex.get('query', '').strip()}"
            )
        
        joined_exemplars = "\n\n".join(exemplar_blocks) if exemplar_blocks else "-- No specific demonstrations found."

        rules = (
            "STRICT RULES:\n"
            "- NEVER use ANSI 'JOIN'. In ArcadeDB, relationships are traversed using out(), in(), or MATCH patterns.\n"
            "- Enforce read-only semantics. Do NOT generate CREATE, ALTER, DROP, DELETE, or UPDATE.\n"
            "- For Cypher: always use distinct property aliases in RETURN to avoid shadowing (e.g. s.title AS solution_title).\n"
            "- Output ONLY the executable query string without markdown code fences."
        )

        return (
            f"You are a specialized query generator for ArcadeDB using {dialect_name}.\n\n"
            f"{rules}\n\n"
            f"RELEVANT VERIFIED DEMONSTRATIONS:\n"
            f"{joined_exemplars}\n\n"
            f"USER INQUIRY:\n"
            f"{question}\n\n"
            f"QUERY:"
        )
