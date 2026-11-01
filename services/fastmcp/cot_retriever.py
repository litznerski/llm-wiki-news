"""
services/fastmcp/cot_retriever.py
Decoupled Diagram & Dual-Mode 5W1H / Toulmin CoT Window Retriever for ArcadeDB (`news`).
Supports:
  1. Default Mode: returns clean section prose (diagrams stripped with zero replacement
     to prevent synthetic transcript noise during LLM reasoning).
  2. Visualization Mode (On-Demand): queries linked (Section)-[:HAS_DIAGRAM]->(Diagram)
     and appends raw ```mermaid ... ``` code blocks for live SVG rendering.
  3. Contradiction Matrix Hydration: retrieves linked `ClaimDispute` records for Events.
"""

import re
from typing import Any, Dict, List, Optional
from .arcadedb_client import ArcadeDBHttpClient


class CoTRetriever:
    """Retrieves Dual-Flow 5W1H & Toulmin CoT reasoning windows, diagrams, and ClaimDisputes from ArcadeDB."""

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
        Retrieves the complete 5W1H / Toulmin Argumentation Window for an Event, Actor, Location, or Theme:
        Anchor/Claim, Tactical Mechanics & Motives (Warrant), Impact & Footprint (Grounds),
        Competing Narratives & Contradictions (Rebuttal), and ClaimDispute records.
        """
        cypher = """
        MATCH (c)
        WHERE (c:Event OR c:Actor OR c:Location OR c:Theme OR c:Timeline OR c:Concept OR c:Entity)
          AND (toLower(c.title) = toLower($title) OR toLower(c.title) CONTAINS toLower($title) OR toLower($title) CONTAINS toLower(c.title))
        MATCH (c)-[e:HAS_SECTION|HAS_GROUNDS|HAS_WARRANT|HAS_CLAIM|HAS_REBUTTAL|HAS_SOLUTION|HAS_QUALIFIER|HAS_BACKING]->(s:Section)
        OPTIONAL MATCH (s)-[:HAS_DIAGRAM]->(d:Diagram)
        RETURN c.title AS concept_title,
               c.admiralty_rating AS admiralty_rating,
               c.pcode AS pcode,
               type(e) AS edge_type,
               e.weight AS edge_weight,
               e.signed_weight AS signed_weight,
               s.uri AS section_uri,
               coalesce(s.title, s.heading) AS section_title,
               s.step_type AS step_type,
               s.toulmin_role AS toulmin_role,
               s.content AS content,
               d.raw_code AS diagram_code
        ORDER BY s.heading_level ASC, e.weight DESC
        """
        records = await self.client.query_async(cypher, language="cypher", params={"title": concept_title})

        roles: Dict[str, List[Dict[str, Any]]] = {
            "CLAIM": [],
            "WARRANT": [],
            "GROUNDS": [],
            "REBUTTAL": [],
            "SOLUTION_WARRANT": [],
            "QUALIFIER": [],
            "BACKING": [],
        }

        matched_title = records[0].get("concept_title") if records else concept_title

        step_to_role = {
            "EVENT_ANCHOR": "CLAIM",
            "ACTOR_ANCHOR": "CLAIM",
            "LOCATION_ANCHOR": "CLAIM",
            "DEFINITIONAL_ANCHOR": "CLAIM",
            "CHRONOLOGICAL_MECHANICS": "WARRANT",
            "CAUSAL_MOTIVES": "WARRANT",
            "COMMAND_LINEAGE": "WARRANT",
            "STRATEGIC_DOCTRINE": "WARRANT",
            "INFRASTRUCTURE_LOGISTICS": "WARRANT",
            "MECHANISTIC_DEEPEN": "WARRANT",
            "IMPACT_ASSESSMENT": "GROUNDS",
            "ALLIANCE_NETWORK": "GROUNDS",
            "EVENT_FOOTPRINT": "GROUNDS",
            "TERRITORIAL_CONTROL": "GROUNDS",
            "HUMANITARIAN_STATUS": "GROUNDS",
            "EVENT_LOG": "GROUNDS",
            "MANIFESTATION_TRAP": "GROUNDS",
            "CONTRADICTION_MATRIX": "REBUTTAL",
            "EMPIRICAL_BOUNDARY": "REBUTTAL",
            "SYNTHESIS_CATALOG": "BACKING",
        }

        for r in records:
            st = (r.get("step_type") or "").upper()
            role = r.get("toulmin_role") or step_to_role.get(st, "WARRANT")
            content = r.get("content") or ""
            content = re.sub(
                r">\s*\[!NOTE\]\s*Architectural Diagram:[^\n]*\n(?:>\s*[^\n]*\n?)*",
                "",
                content
            ).strip()

            item = {
                "section_uri": r.get("section_uri"),
                "section_title": r.get("section_title"),
                "step_type": st,
                "edge_type": r.get("edge_type"),
                "weight": r.get("edge_weight"),
                "signed_weight": r.get("signed_weight"),
                "content": content,
            }
            if include_diagrams and r.get("diagram_code"):
                item["diagram_code"] = r.get("diagram_code")

            if role in roles:
                roles[role].append(item)

        # Fetch ClaimDispute records if any exist for this Event
        disputes = []
        try:
            disputes = await self.client.query_async(
                "SELECT conflict_type, source_a, claim_a, source_b, claim_b, resolution_status FROM ClaimDispute WHERE event_title = :title",
                language="sql",
                params={"title": matched_title},
            )
        except Exception:
            pass

        return {
            "concept_title": matched_title,
            "roles": roles,
            "claim_disputes": disputes,
            "include_diagrams": include_diagrams,
        }

    def format_toulmin_window_to_markdown(
        self,
        window_data: Dict[str, Any],
    ) -> str:
        """
        Renders the retrieved 5W1H / Toulmin Window into GitHub-Flavored Markdown.
        """
        title = window_data.get("concept_title", "Intelligence Node")
        roles = window_data.get("roles", {})
        disputes = window_data.get("claim_disputes", [])
        include_diagrams = window_data.get("include_diagrams", False)

        md = [f"## 5W1H Intelligence Window: [[{title}]]\n"]

        role_labels = [
            ("CLAIM", "1. 5W1H Intelligence Anchor & Identity"),
            ("WARRANT", "2. Tactical Mechanics, Chronology & Causal Motives (What, How & Why)"),
            ("GROUNDS", "3. Humanitarian, Territorial & Force Footprint (Where & Who)"),
            ("REBUTTAL", "4. Competing Narratives, Attribution & Contradictions (GRaSP)"),
            ("SOLUTION_WARRANT", "5. Humanitarian Response & Mediation"),
            ("BACKING", "6. Related Primitives & Source Backing"),
        ]

        for role_key, role_name in role_labels:
            sections = roles.get(role_key, [])
            if not sections:
                continue

            md.append(f"### {role_name}")
            for sec in sections:
                weight_str = f"*(Weight: {sec['weight']:.2f})*" if sec.get("weight") is not None else ""
                md.append(f"#### {sec['section_title']} {weight_str}\n")
                md.append(f"{sec['content']}\n")

                if include_diagrams and sec.get("diagram_code"):
                    md.append(f"\n{sec['diagram_code']}\n")

        if disputes:
            md.append("### Logged ClaimDispute Records (GRaSP Matrix)")
            md.append("| Conflict Type | Source A | Claim A | Source B | Claim B | Status |")
            md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for d in disputes:
                md.append(
                    f"| `{d.get('conflict_type', '')}` | {d.get('source_a', '')} | {d.get('claim_a', '')} "
                    f"| {d.get('source_b', '')} | {d.get('claim_b', '')} | `{d.get('resolution_status', '')}` |"
                )

        return "\n".join(md)
