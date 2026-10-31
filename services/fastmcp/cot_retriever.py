"""
services/fastmcp/cot_retriever.py
Decoupled Diagram & Dual-Mode CoT Window Retriever for ArcadeDB.
Supports:
  1. Default Mode: returns clean section prose (diagrams stripped with zero replacement
     to prevent synthetic transcript noise during LLM reasoning).
  2. Visualization Mode (On-Demand): queries linked (Section)-[:HAS_DIAGRAM]->(Diagram)
     and appends raw ```mermaid ... ``` code blocks for live SVG rendering in OpenWebUI.
"""

import re
from typing import Any, Dict, List, Optional
from .arcadedb_client import ArcadeDBHttpClient


class CoTRetriever:
    """Retrieves Dual-Flow CoT reasoning windows and linked diagram assets from ArcadeDB."""

    def __init__(self, client: ArcadeDBHttpClient):
        self.client = client

    async def retrieve_section_with_diagram(
        self,
        section_uri: str,
        include_diagram: bool = False,
    ) -> Dict[str, Any]:
        """
        Retrieves an atomic section vertex.
        If include_diagram=True, fetches any linked Diagram documents via HAS_DIAGRAM edges.
        """
        base_query = """
        MATCH (s:Section {uri: $uri})
        RETURN s.uri AS uri, s.title AS title, s.display_name AS display_name,
               s.step_type AS step_type, s.toulmin_role AS toulmin_role,
               s.weight AS weight, s.modal_category AS modal_category,
               s.content AS content
        """
        records = await self.client.query_async(base_query, language="cypher", params={"uri": section_uri})
        if not records:
            return {}

        section_data = records[0]
        if section_data.get("content"):
            section_data["content"] = re.sub(
                r">\s*\[!NOTE\]\s*Architectural Diagram:[^\n]*\n(?:>\s*[^\n]*\n?)*",
                "",
                section_data["content"]
            ).strip()

        if include_diagram:
            diag_query = """
            MATCH (s:Section {uri: $uri})-[:HAS_DIAGRAM]->(d:Diagram)
            RETURN d.id AS id, d.title AS title, d.diagram_type AS diagram_type,
                   d.direction AS direction, d.raw_code AS raw_code,
                   d.order_idx AS order_idx
            ORDER BY d.order_idx ASC
            """
            diagrams = await self.client.query_async(diag_query, language="cypher", params={"uri": section_uri})
            section_data["diagrams"] = diagrams
        else:
            section_data["diagrams"] = []

        return section_data

    async def retrieve_concept_toulmin_window(
        self,
        concept_title: str,
        include_diagrams: bool = False,
    ) -> Dict[str, Any]:
        """
        Retrieves the complete Toulmin Argumentation Window for a Concept:
        Grounds, Claims, Warrants, Rebuttals (with signed weights), and Solutions.
        """
        cypher = """
        MATCH (c:Concept)
        WHERE toLower(c.title) = toLower($title) OR toLower(c.title) CONTAINS toLower($title) OR toLower($title) CONTAINS toLower(c.title)
        MATCH (c)-[e:HAS_GROUNDS|HAS_WARRANT|HAS_CLAIM|HAS_REBUTTAL|HAS_SOLUTION|HAS_QUALIFIER|HAS_BACKING]->(s:Section)
        OPTIONAL MATCH (s)-[:HAS_DIAGRAM]->(d:Diagram)
        RETURN c.title AS concept_title,
               type(e) AS edge_type,
               e.weight AS edge_weight,
               e.signed_weight AS signed_weight,
               s.uri AS section_uri,
               s.title AS section_title,
               s.step_type AS step_type,
               s.toulmin_role AS toulmin_role,
               s.content AS content,
               d.raw_code AS diagram_code
        ORDER BY s.heading_level ASC, e.weight DESC
        """
        records = await self.client.query_async(cypher, language="cypher", params={"title": concept_title})
        
        roles: Dict[str, List[Dict[str, Any]]] = {
            "GROUNDS": [],
            "CLAIM": [],
            "WARRANT": [],
            "REBUTTAL": [],
            "SOLUTION_WARRANT": [],
            "QUALIFIER": [],
            "BACKING": [],
        }

        matched_title = records[0].get("concept_title") if records else concept_title

        for r in records:
            role = r.get("toulmin_role") or "WARRANT"
            content = r.get("content") or ""
            content = re.sub(
                r">\s*\[!NOTE\]\s*Architectural Diagram:[^\n]*\n(?:>\s*[^\n]*\n?)*",
                "",
                content
            ).strip()

            item = {
                "section_uri": r.get("section_uri"),
                "section_title": r.get("section_title"),
                "edge_type": r.get("edge_type"),
                "weight": r.get("edge_weight"),
                "signed_weight": r.get("signed_weight"),
                "content": content,
            }
            if include_diagrams and r.get("diagram_code"):
                item["diagram_code"] = r.get("diagram_code")

            if role in roles:
                roles[role].append(item)

        return {
            "concept_title": matched_title,
            "roles": roles,
            "include_diagrams": include_diagrams,
        }

    def format_toulmin_window_to_markdown(
        self,
        window_data: Dict[str, Any],
    ) -> str:
        """
        Renders the retrieved Toulmin Window into GitHub-Flavored Markdown.
        In visualization mode, appends raw ```mermaid ... ``` code fences for UI rendering.
        """
        title = window_data.get("concept_title", "Concept")
        roles = window_data.get("roles", {})
        include_diagrams = window_data.get("include_diagrams", False)

        md = [f"## Toulmin Epistemic Window: [[{title}]]\n"]

        role_labels = [
            ("CLAIM", "Thesis / Claim"),
            ("GROUNDS", "Empirical Grounds & Definitional Anchor"),
            ("WARRANT", "Causal Warrants & Mechanics"),
            ("REBUTTAL", "Rebuttals & Failure Modes"),
            ("SOLUTION_WARRANT", "Prescriptive Solutions & Mitigations"),
            ("QUALIFIER", "Empirical Boundaries & Qualifiers"),
            ("BACKING", "Backing & Synthesis Catalog"),
        ]

        for role_key, role_name in role_labels:
            sections = roles.get(role_key, [])
            if not sections:
                continue

            md.append(f"### {role_name}")
            for sec in sections:
                weight_str = f"*(Weight: {sec['weight']:.2f})*" if sec.get("weight") is not None else ""
                if sec.get("signed_weight") is not None:
                    weight_str += f" *(Signed Attack: {sec['signed_weight']:.2f})*"

                md.append(f"#### {sec['section_title']} {weight_str}\n")
                md.append(f"{sec['content']}\n")

                if include_diagrams and sec.get("diagram_code"):
                    md.append(f"\n{sec['diagram_code']}\n")

        return "\n".join(md)
