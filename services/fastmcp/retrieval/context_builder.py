"""
services/fastmcp/retrieval/context_builder.py
Epistemic Structured JSON Context Assembler.
Formats retrieved Toulmin CoT windows into verified, schema-aligned JSON
wrapped in an OpenWebUI-native collapsible markdown callout with synthesis instructions.
Supports Socratic withholding for Teachable Agent / Learn mode.
"""

import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EpistemicSection(BaseModel):
    title: str = Field(..., description="Canonical section title")
    content: str = Field(..., description="Full text content of the section")
    uri: str = Field(..., description="ArcadeDB or Vault URI for the section")
    weight: float = Field(1.0, description="Salience / edge weight")
    toulmin_role: Optional[str] = Field(None, description="Toulmin argumentative role")
    diagrams: List[Dict[str, Any]] = Field(default_factory=list, description="Diagrams attached via [:HAS_DIAGRAM]")


class MacroCoTBridge(BaseModel):
    relationship: str = Field(..., description="Ontological relationship type e.g. REMEDIES_DILEMMA")
    target_concept: str = Field(..., description="Neighbor concept or entity title")
    weight: float = Field(1.0, description="Macro-CoT edge traversal weight")
    sections: List[EpistemicSection] = Field(default_factory=list, description="Sections grounding the neighbor bridge")


class EpistemicContextPayload(BaseModel):
    concept: str = Field(..., description="Primary anchor concept")
    retrieval_status: str = Field(..., description="'PERFECT_COT_WINDOW', 'PARTIAL_ROLE_COVERAGE', etc.")
    roles: Dict[str, List[EpistemicSection]] = Field(
        default_factory=dict,
        description="Sections partitioned by Toulmin role: CLAIM, GROUNDS, WARRANT, REBUTTAL, SOLUTION_WARRANT",
    )
    macro_cot_bridges: List[MacroCoTBridge] = Field(
        default_factory=list,
        description="1-hop inter-concept ontological transitions",
    )
    withheld_roles: Optional[List[str]] = Field(
        None,
        description="Roles withheld during Teachable Agent / Socratic gating",
    )
    all_expected_roles_covered: bool = Field(True, description="Whether all expected roles were present")
    roles_covered: List[str] = Field(default_factory=list, description="List of all Toulmin roles present in window")
    concepts_in_window: List[str] = Field(default_factory=list, description="All concepts represented in the window")


def build_epistemic_context(
    retrieval_result: Dict[str, Any],
    teachable_agent_mode: bool = False,
    operating_mode: str = "General",
) -> EpistemicContextPayload:
    """
    Transforms raw V3 retrieval results into a validated EpistemicContextPayload.
    Executes Socratic role withholding when teachable_agent_mode is active or operating_mode == 'Learn'.
    """
    primary_concept = retrieval_result.get("primary_concept") or "Unknown Concept"
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

        # Populate roles dictionary (all active window roles available for synthesis)
        if role not in roles:
            roles[role] = []
        roles[role].append(section_obj)

        # If inter-concept / neighbor bridge, construct MacroCoTBridge
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

    # Socratic Gating / Withholding Hook
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
    deterministic synthesis instructions and passes the original user inquiry.
    """
    context_dict = {"epistemic_context": epistemic_context.model_dump(exclude_none=True)}
    context_json_str = json.dumps(context_dict, indent=2, ensure_ascii=False)

    is_socratic = teachable_agent_mode or (operating_mode and operating_mode.lower() == "learn")
    withheld = epistemic_context.withheld_roles or []

    roles_present = list(epistemic_context.roles.keys())
    roles_seq_str = " -> ".join(roles_present) if roles_present else "CLAIM -> GROUNDS -> WARRANT"

    synthesis_rules = [
        "1. Ground your response strictly on the verified evidence in the `epistemic_context` JSON object above.",
        "2. [TURN 1 CONCISENESS & DEFINITIONAL ANCHOR]: For the initial response in General Mode, deliver a concise, focused output that does not overwhelm the learner. Render strictly the Definitional Anchor (the `CLAIM` / core thesis) of the primary concept in 2-3 sentences. Do NOT output all causal mechanics, empirical grounds, failure modes, or prescriptive solutions in the first turn.",
        "3. [CONTEXT PRESERVATION FOR SUBSEQUENT TURNS]: The full retrieved text, all Toulmin argumentation roles, and macro epistemic bridges in `epistemic_context` are preserved in context for subsequent turns. Synthesize additional sections only upon specific request.",
        "4. [NEXT-STEP FOCUS DIMENSION SELECTION]: Conclude the initial definitional anchor by offering the learner an explicit next-step selection: \"What do you want to investigate in detail?\", presenting the available dimensions (🔬 Causal Anatomy, 📊 Empirical Grounds, 🛠️ Prescriptive Mitigations, ⚖️ Defeasible Boundaries, 🌐 Epistemic Bridges: Connected knowledge pathways and theoretical transitions across the vault).",
        "5. [TURN 2+ DRILLDOWN PROCESSING]: In subsequent turns, process the learner's selected role(s) or inquiry directly based on the preserved context without fabricating ungrounded claims or repeating introductory anchors.",
        "6. If `macro_cot_bridges` are present and requested, explicitly integrate the causal connections (e.g. how the concept remedies the linked dilemma).",
        "7. Do NOT output \"Primary Vault Reference\". Preserve canonical [[wikilinks]] for all concepts and entities at the end of the response in a separate section \"Sources\".",
    ]

    if is_socratic and withheld:
        synthesis_rules.append(
            f"5. [TEACHABLE AGENT / SOCRATIC MODE ACTIVE]: The argumentative components {withheld} have been deliberately withheld. "
            "Do NOT state the underlying causal mechanisms or prescriptive answers directly. Instead, pose calibrated Socratic questions "
            "that guide the learner to induce the missing warrant and solution themselves from the provided claim and empirical grounds."
        )

    rules_str = "\n".join(synthesis_rules)

    prompt_wrapper = f"""> [!DATA]- Grounded Epistemic Knowledge Context (ArcadeDB Toulmin CoT)
```json
{context_json_str}
```

INSTRUCTION FOR MODEL SYNTHESIS:
{rules_str}

USER INQUIRY:
{user_prompt}"""

    return prompt_wrapper


def format_out_of_domain_refusal(prompt: str) -> str:
    """Returns an organic out-of-domain refusal card for queries failing domain threshold."""
    return (
        "> [!NOTE] Out of Knowledge Domain\n"
        "> The submitted inquiry does not align with indexed domains in the knowledge base "
        "(AI Literacy, Cognitive Ergonomics, EdTech Architecture, Learning Analytics).\n"
        ">\n"
        "> Please reformulate your question around these pedagogical and systems domains."
    )
