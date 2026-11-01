"""
services/fastmcp/retrieval/context_builder.py
Sudan News & OSINT Epistemic Structured JSON Context Assembler.
Formats retrieved 5W1H / Toulmin CoT windows into verified, schema-aligned JSON
wrapped in a collapsible markdown callout with OSINT synthesis instructions.
"""

import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EpistemicSection(BaseModel):
    title: str = Field(..., description="Canonical section title")
    content: str = Field(..., description="Full text content of the section")
    uri: str = Field(..., description="ArcadeDB or Vault URI for the section")
    weight: float = Field(1.0, description="Salience / edge weight")
    toulmin_role: Optional[str] = Field(None, description="5W1H / Toulmin argumentative role")
    diagrams: List[Dict[str, Any]] = Field(default_factory=list, description="Diagrams attached via [:HAS_DIAGRAM]")


class MacroCoTBridge(BaseModel):
    relationship: str = Field(..., description="Ontological relationship type e.g. PERPETRATED_BY, OCCURRED_AT, TRIGGERS")
    target_concept: str = Field(..., description="Neighbor Event, Actor, Location, or Theme title")
    weight: float = Field(1.0, description="Macro-CoT edge traversal weight")
    sections: List[EpistemicSection] = Field(default_factory=list, description="Sections grounding the neighbor bridge")


class EpistemicContextPayload(BaseModel):
    concept: str = Field(..., description="Primary anchor Event, Actor, Location, or Theme")
    retrieval_status: str = Field(..., description="'PERFECT_COT_WINDOW', 'PARTIAL_ROLE_COVERAGE', etc.")
    roles: Dict[str, List[EpistemicSection]] = Field(
        default_factory=dict,
        description="Sections partitioned by role: CLAIM (Anchor), WARRANT (Mechanics/Motives), GROUNDS (Impact/Footprint), REBUTTAL (Contradictions)",
    )
    macro_cot_bridges: List[MacroCoTBridge] = Field(
        default_factory=list,
        description="1-hop inter-node 5W1H and GRaSP ontological transitions",
    )
    withheld_roles: Optional[List[str]] = Field(
        None,
        description="Roles withheld during Socratic / Analyst Verification gating",
    )
    all_expected_roles_covered: bool = Field(True, description="Whether all expected roles were present")
    roles_covered: List[str] = Field(default_factory=list, description="List of all roles present in window")
    concepts_in_window: List[str] = Field(default_factory=list, description="All nodes represented in the window")


def build_epistemic_context(
    retrieval_result: Dict[str, Any],
    teachable_agent_mode: bool = False,
    operating_mode: str = "General",
) -> EpistemicContextPayload:
    """
    Transforms raw V3 retrieval results into a validated EpistemicContextPayload.
    """
    primary_concept = retrieval_result.get("primary_concept") or "Sudan Conflict SITREP"
    fit_status = retrieval_result.get("fit_status") or "UNKNOWN"
    all_roles_covered = retrieval_result.get("all_expected_roles_covered", False)
    roles_covered = retrieval_result.get("roles_covered", [])
    concepts_in_window = retrieval_result.get("concepts_in_window", [])
    raw_sections = retrieval_result.get("sections", [])

    roles: Dict[str, List[EpistemicSection]] = {}
    macro_cot_bridges: List[MacroCoTBridge] = []

    for sec in raw_sections:
        role = sec.get("role", "UNKNOWN")
        sec_concept = sec.get("concept", "")
        sec_title = sec.get("title", "")
        sec_content = sec.get("content", "")
        sec_uri = sec.get("uri", "")
        sec_weight = float(sec.get("weight", 1.0))
        is_inter = sec.get("is_inter", False) or (sec_concept and sec_concept.lower() != primary_concept.lower())

        section_obj = EpistemicSection(
            title=sec_title,
            content=sec_content,
            uri=sec_uri,
            weight=sec_weight,
            toulmin_role=role,
            diagrams=sec.get("diagrams", []),
        )

        if role not in roles:
            roles[role] = []
        roles[role].append(section_obj)

        if is_inter and sec_concept and sec_concept.lower() != primary_concept.lower():
            bridge_rel = sec.get("bridge_rel")
            if not bridge_rel:
                edge_str = sec.get("edge", "")
                if "->" in edge_str:
                    bridge_rel = edge_str.split("->")[0]
                else:
                    bridge_rel = edge_str or "RELATES_TO"
            bridge_rel = bridge_rel.strip(":[] ")

            macro_cot_bridges.append(
                MacroCoTBridge(
                    relationship=bridge_rel,
                    target_concept=sec_concept,
                    weight=sec_weight,
                    sections=[section_obj],
                )
            )

    withheld_roles: Optional[List[str]] = None
    is_socratic = teachable_agent_mode or (operating_mode and operating_mode.lower() == "learn")
    if is_socratic:
        withheld = []
        for target in ["WARRANT", "SOLUTION_WARRANT"]:
            if target in roles:
                withheld.append(target)
                del roles[target]
        if withheld:
            withheld_roles = withheld

    return EpistemicContextPayload(
        concept=primary_concept,
        retrieval_status=fit_status,
        roles=roles,
        macro_cot_bridges=macro_cot_bridges,
        withheld_roles=withheld_roles,
        all_expected_roles_covered=all_roles_covered,
        roles_covered=roles_covered,
        concepts_in_window=concepts_in_window,
    )


def wrap_epistemic_prompt(
    epistemic_context: EpistemicContextPayload,
    user_prompt: str,
    teachable_agent_mode: bool = False,
    operating_mode: str = "General",
) -> str:
    """
    Wraps the EpistemicContextPayload into a collapsible Markdown callout with
    Sudan News & OSINT synthesis instructions.
    """
    context_dict = {"epistemic_context": epistemic_context.model_dump(exclude_none=True)}
    context_json_str = json.dumps(context_dict, indent=2, ensure_ascii=False)

    is_socratic = teachable_agent_mode or (operating_mode and operating_mode.lower() == "learn")
    withheld = epistemic_context.withheld_roles or []

    synthesis_rules = [
        "1. Ground your intelligence assessment strictly on the verified evidence in the `epistemic_context` JSON object above.",
        "2. [TURN 1 5W1H EXECUTIVE ANCHOR]: For the initial response in General Mode, deliver a concise, high-signal 5W1H Intelligence Anchor (the `CLAIM` / identity / event summary) in 2-4 sentences, including NATO Admiralty ratings (`A1`–`F6`) or UN OCHA P-Codes where available.",
        "3. [CONTEXT PRESERVATION FOR SUBSEQUENT TURNS]: The full retrieved text, tactical mechanics (`WARRANT`), humanitarian/territorial impact (`GROUNDS`), competing narratives (`REBUTTAL`), and Macro-CoT bridges are preserved in context for drilldown.",
        "4. [NEXT-STEP FOCUS DIMENSION SELECTION]: Conclude the initial anchor by offering the analyst explicit drilldown dimensions (🔬 Tactical Mechanics & Causal Motives, 📊 Humanitarian & Territorial Impact, ⚖️ Competing Narratives & Contradictions, 🌐 Campaign & Actor Bridges).",
        "5. [CONTRADICTION PRESERVATION]: When competing claims exist between belligerents (e.g., [[Sudanese Armed Forces]] vs. [[Rapid Support Forces]]) or sources, explicitly present both claims and their NATO Admiralty ratings rather than collapsing them.",
        "6. Cite all events, actors, locations, themes, and sources using clean Obsidian wikilinks [[Canonical Title]] (NEVER enclose wikilinks in backticks).",
    ]

    if is_socratic and withheld:
        synthesis_rules.append(
            f"7. [ANALYST CHALLENGE MODE ACTIVE]: The components {withheld} have been deliberately withheld. "
            "Pose calibrated intelligence analysis questions guiding the analyst to infer the tactical motives or corroborate competing claims from the provided 5W1H grounds."
        )

    rules_str = "\n".join(synthesis_rules)

    prompt_wrapper = f"""> [!DATA]- Grounded OSINT Knowledge Context (ArcadeDB 5W1H & GRaSP CoT)
```json
{context_json_str}
```

INSTRUCTION FOR OSINT MODEL SYNTHESIS:
{rules_str}

ANALYST INQUIRY:
{user_prompt}"""

    return prompt_wrapper


def format_out_of_domain_refusal(prompt: str) -> str:
    """Returns an organic out-of-domain refusal card for queries failing domain threshold."""
    return (
        "> [!NOTE] Out of Intelligence Domain\n"
        "> The submitted inquiry does not align with indexed domains in the Sudan News & OSINT Knowledge Base "
        "(Sudan Armed Conflict Events, Actors, Locations/P-Codes, War Economy, Humanitarian Crises, Diplomatic Mediations).\n"
        ">\n"
        "> Please reformulate your question around Sudan news, conflict events, acting entities, or frontlines."
    )
