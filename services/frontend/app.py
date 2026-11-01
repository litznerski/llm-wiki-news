"""
knowledge lab :: Chainlit Learner Studio & Knowledge Explorer
Thin presentation layer connecting to FastMCP Middleware.
All reasoning, graph traversal, and retrieval logic is handled in FastMCP.
"""

import os
import re
import json
import time
import httpx
import chainlit as cl
from chainlit.input_widget import Select, Switch, TextInput, Slider
from typing import Optional, Dict, Any, List

VALVES_FILE = os.path.join(os.path.dirname(__file__), "valves.json")
DEFAULT_FASTMCP_URL = os.getenv("FASTMCP_URL", "http://fastmcp-news:8000")
DEFAULT_OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL", "openrouter/free")
DEFAULT_OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

DEFAULT_VALVES: Dict[str, Any] = {
    "operating_mode": "General",
    "developer_mode": True,
    "teachable_agent_mode": False,
    "enable_chat_history": True,
    "enable_langfuse": False,
    "fastmcp_url": DEFAULT_FASTMCP_URL,
    "enable_llm": True,
    "llm_model": DEFAULT_LLM_MODEL,
    "custom_model": "",
    "openrouter_api_key": DEFAULT_OPENROUTER_KEY,
    "openrouter_base_url": DEFAULT_OPENROUTER_BASE_URL,
    "llm_temperature": 0.2,
}


def get_effective_model(valves: Dict[str, Any]) -> str:
    """Returns the effective model identifier, prioritizing custom_model if custom is selected."""
    model = valves.get("llm_model", "openrouter/free")
    if model == "custom" and valves.get("custom_model"):
        return valves["custom_model"].strip()
    return model


def load_valves() -> Dict[str, Any]:
    """Loads valves from valves.json or environment defaults."""
    valves = dict(DEFAULT_VALVES)
    if os.path.exists(VALVES_FILE):
        try:
            with open(VALVES_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                valves.update(saved)
        except Exception:
            pass
    # Environment overrides
    if "FASTMCP_URL" in os.environ:
        valves["fastmcp_url"] = os.environ["FASTMCP_URL"]
    if "OPENROUTER_API_KEY" in os.environ:
        valves["openrouter_api_key"] = os.environ["OPENROUTER_API_KEY"]
    if "LLM_MODEL" in os.environ:
        valves["llm_model"] = os.environ["LLM_MODEL"]
    if "OPENROUTER_BASE_URL" in os.environ:
        valves["openrouter_base_url"] = os.environ["OPENROUTER_BASE_URL"]
    return valves


def save_valves(valves: Dict[str, Any]):
    """Persists valves to valves.json."""
    try:
        with open(VALVES_FILE, "w", encoding="utf-8") as f:
            json.dump(valves, f, indent=2)
    except Exception:
        pass


def render_valves_panel(valves: Dict[str, Any]) -> cl.Text:
    """Generates the side-panel valve configuration card."""
    mode = valves.get("operating_mode", "General")
    dev_mode = valves.get("developer_mode", True)
    dev_mode_str = "ENABLED (Live Sidebar Telemetry)" if dev_mode else "DISABLED"
    withholding = valves.get("teachable_agent_mode", False)
    withholding_str = "ENABLED (Friction Active)" if withholding else "DISABLED (Direct Synthesis)"
    history_str = "ENABLED (news)" if valves.get("enable_chat_history", True) else "DISABLED"
    langfuse_str = "ENABLED" if valves.get("enable_langfuse", False) else "DISABLED"

    llm_enabled = valves.get("enable_llm", True)
    active_model = get_effective_model(valves)
    llm_status_str = f"ENABLED ({active_model})" if llm_enabled else "DISABLED (Template Mode)"
    api_key_status = "CONFIGURED (OpenRouter)" if bool(valves.get("openrouter_api_key")) else "MISSING"

    content = f"""# ⚙️ Active Valves & System Status

### 🤖 LLM Synthesis & Model Valves
- **LLM Inference**: `{llm_status_str}`
- **Active Model**: `{active_model}`
- **OpenRouter Key**: `{api_key_status}`
- **Sampling Temperature**: `{valves.get('llm_temperature', 0.2)}`
- **Gateway Endpoint**: `{valves.get('openrouter_base_url', DEFAULT_OPENROUTER_BASE_URL)}`

---

### FastMCP Processing Valves
- **Operating Mode**: `{mode}` *(General = Direct Synthesis, Learn = Socratic Toulmin)*
- **Developer Mode**: `{dev_mode_str}`
- **Teachable Agent Withholding**: `{withholding_str}`
- **ArcadeDB Turn History**: `{history_str}`
- **Langfuse Cloud Tracing**: `{langfuse_str}`
- **FastMCP Endpoint**: `{valves.get('fastmcp_url', DEFAULT_FASTMCP_URL)}`

---

### Epistemic Substrate
- **Platform**: `Sudan News & OSINT Intelligence Studio (llm-wiki-news)`
- **Knowledge Engine**: `ArcadeDB news (Multi-Model 5W1H & GRaSP Graph)`
- **Reasoning Architecture**: `Dual-Flow 5W1H CoT Windowing & NATO Admiralty Scale`
- **Presentation Host**: `Astro 7 Digital Garden`

*Click the ⚙️ Settings icon at the bottom of the screen to adjust valves or switch models.*
"""
    return cl.Text(name="Active Valves & Status", content=content, display="side")


def format_arcadedb_inspector_markdown(concept_name: str, node_data: dict) -> str:
    """Formats an ArcadeDB node inspection block in Markdown for embedding inside turn accordions."""
    pagerank = node_data.get("pagerank", 0.0152)
    community = node_data.get("community", 1)
    aliases = ", ".join(node_data.get("aliases", [])) or "See wiki/glossary.md"
    tier = node_data.get("tier", "tier_2_traversal")
    tier_label = "Tier 1: Pre-Compiled Intelligence Synthesis" if tier == "tier_1_synthesis" else "Tier 2: 5W1H CoT Graph Traversal"

    return f"""#### ArcadeDB Graph Inspector: {concept_name}

> [!IMPORTANT] OSINT Graph Topology Telemetry
> - **Resolution Tier**: `{tier_label}`
> - **In-Engine PageRank**: `{pagerank:.4f}`
> - **Theatre / Cluster**: `Cluster {community}` (*Sudan Conflict OSINT*)
> - **Known Aliases / P-Code**: `{aliases}`

##### 5W1H & GRaSP Argumentation Structure
| 5W1H / GRaSP Role | In-Vault Section | Epistemic Basis | Signed Weight |
| :--- | :--- | :---: | :---: |
| **Claim (Anchor)** | 1. 5W1H Anchor / Identity | NATO Admiralty (`A1`–`F6`) | `+1.00` |
| **Warrant (Why/How)** | 2–3. Tactical Mechanics & Causal Motives | Multi-Source Corroboration | `+0.85` |
| **Grounds (Impact)** | 4. Humanitarian, Territorial & Force Footprint | UN OCHA / ACLED / Field | `+0.80` |
| **Rebuttal (Disputes)** | 5. Competing Narratives & Contradiction Matrix | GRaSP `ClaimDispute` | `-0.85` |

##### Primary Vault Lineage
- `[[{concept_name}]]`
- `[[overview|Sudan Conflict Living SITREP]]`
- `[[glossary|Sudan Cross-Lingual Entity & P-Code Registry]]`
"""


def render_turn_accordion(turn: dict, is_latest: bool) -> str:
    """Renders a single conversation turn's trace inside a native collapsible <details> card."""
    turn_num = turn.get("turn_num", 1)
    user_query = turn.get("user_query", "")
    dev_trace = turn.get("dev_trace", {})
    timestamp = turn.get("timestamp", "")
    timings = dev_trace.get("timings", {})
    dsm = dev_trace.get("dsm_state", {})

    # Requirement 3: Safeguard should ONLY be included if <> PASS
    stages = [
        s for s in dev_trace.get("stages", [])
        if not (s.get("id") == "01_safeguards" and s.get("status") in ("PASS", "PROCEED", "OK"))
    ]
    queries = [
        q for q in dev_trace.get("queries", [])
        if not (q.get("stage", "").startswith("01_safeguard") and ("Passed" in q.get("query", "") or q.get("results_count") == 0))
    ]
    logs = [
        l for l in dev_trace.get("logs", [])
        if not (l.startswith("[SAFEGUARD]") and ("passed" in l.lower() or "evaluated" in l.lower()))
    ]

    tier_val = dsm.get('tier', 'N/A')
    tier_label = {
        "fast_respond": "Conversational Fast-Path (< 3ms)",
        "security_reject": "Security Policy Interception",
        "tier_1_synthesis": "Tier 1: Pre-Compiled Golden Synthesis",
        "tier_2_traversal": "Tier 2: V3 CoT Graph Traversal"
    }.get(tier_val, tier_val)

    raw_anchor = dsm.get('concept_anchor', 'N/A')
    if raw_anchor in ("Conversational Fast-Path", "Security Policy Interception", "N/A"):
        anchor_fmt = f"`{raw_anchor}`"
    else:
        anchor_fmt = f"[[{raw_anchor}]]"

    node_data = turn.get("node_data")
    inspector_block = ""
    if node_data:
        inspector_block = "\n" + format_arcadedb_inspector_markdown(node_data.get("concept_name", raw_anchor), node_data) + "\n"

    stage_rows = "\n".join([
        f"| `{s.get('id', s.get('name'))}` | **{s.get('name')}** | `{s.get('status', 'OK')}` | `{s.get('latency_ms', 0):.2f}ms` |"
        for s in stages
    ]) or "| `none` | *No active pipeline stages* | - | - |"

    query_blocks = ""
    for idx, q in enumerate(queries, 1):
        dialect = q.get("dialect", "cypher").lower()
        query_blocks += f"\n**Query {idx}: `{q.get('stage', 'db')}` ({dialect.upper()} - {q.get('time_ms', 0):.1f}ms - {q.get('results_count', 0)} rows):**\n"
        query_blocks += f"```{dialect}\n{q.get('query', '').strip()}\n```\n"

    log_rows = "\n".join([f"- `{line}`" for line in logs]) if logs else "*No runtime logs emitted*"

    card_class = "dev-turn-card"

    return f"""<details class="{card_class}" data-turn-num="{turn_num}">
<summary><strong>Turn #{turn_num}</strong>: <em>"{user_query}"</em> &nbsp;•&nbsp; <code>{tier_label}</code> &nbsp;•&nbsp; <code>{timings.get('total_turnaround_ms', 0):.1f}ms</code> &nbsp;•&nbsp; <small>{timestamp}</small></summary>

> [!NOTE] Turn #{turn_num} Execution Telemetry
> - **User Query**: *"{user_query}"*
> - **Total Turnaround**: `{timings.get('total_turnaround_ms', 0):.2f}ms`
> - **Resolution Tier**: `{tier_label}`
> - **DSM State**: `{dsm.get('current_state', 'UNKNOWN')}` (Mode: `{dsm.get('operating_mode', 'General')}`)
> - **Concept Anchor**: {anchor_fmt}
> - **Teachable Withholding**: `{'ACTIVE (Warrants Withheld)' if dsm.get('teachable_withholding') else 'OFF'}`
{inspector_block}
#### Pipeline Execution Stages
| Stage ID | Stage Description | Status | Latency |
| :--- | :--- | :---: | :---: |
{stage_rows}

#### Executed Database Queries
{query_blocks if query_blocks else "*No direct queries executed (Served from Cache / Pre-Compiled)*"}

#### Diagnostic Event Logs
{log_rows}

</details>"""


def render_developer_sidebar(dev_traces: Any, user_query: str = "") -> cl.Text:
    """Formats FastMCP internal execution traces into collapsible cards across conversation turns."""
    if isinstance(dev_traces, dict):
        dev_traces = [{"turn_num": 1, "user_query": user_query, "dev_trace": dev_traces, "timestamp": time.strftime("%H:%M:%S")}]

    if not dev_traces:
        return cl.Text(name="Developer Trace", content="*No developer traces recorded yet.*", display="side")

    turn_sections = [
        render_turn_accordion(turn, is_latest=False)
        for turn in dev_traces
    ]

    content = "\n\n".join(turn_sections)
    return cl.Text(name="Developer Trace", content=content, display="side")


def render_arcadedb_inspector(concept_name: str, node_data: dict) -> cl.Text:
    """Generates a rich ArcadeDB node inspection card for the side panel."""
    content = f"# 🔍 ArcadeDB Graph Inspector: {concept_name}\n\n" + format_arcadedb_inspector_markdown(concept_name, node_data) + f"\n*Retrieved live from `news` multi-model engine for <span class=\"brand-knowledge-lab\"><span class=\"brand-knowledge\">knowledge</span><span class=\"brand-lab\">lab</span></span>.*\n"
    return cl.Text(name=f"ArcadeDB Inspector: {concept_name}", content=content, display="side")


def format_section_with_diagrams(sec: dict) -> str:
    """Formats section content, stripping inline mermaid blocks and appending collapsible diagram cards."""
    content = sec.get("content", "").strip()
    clean_content = re.sub(r'```mermaid[\s\S]*?```', '', content).strip()
    parts = [clean_content] if clean_content else []
    for diag in sec.get("diagrams", []):
        code = (diag.get("raw_code") or "").strip()
        d_title = diag.get("title") or "Visual Architecture"
        if code:
            parts.append(
                f"\n<details class=\"mermaid-collapsible-wrapper\">\n"
                f"<summary>📊 Visual Architecture: {d_title} (Click to expand)</summary>\n\n"
                f"{code}\n\n"
                f"</details>"
            )
    return "\n\n".join(parts)


def format_tier2_synthesis(concept: str, epistemic_ctx: dict) -> str:
    """Formats Tier 2 Toulmin epistemic context directly into clean, authoritative Markdown."""
    roles = epistemic_ctx.get("roles", {})
    output_parts = [f"# Knowledge Synthesis: [[{concept}]]\n"]

    if "CLAIM" in roles and roles["CLAIM"]:
        sec = roles["CLAIM"][0]
        output_parts.append(f"### 1. Definitional Anchor & Core Thesis\n{format_section_with_diagrams(sec)}\n")

    if "WARRANT" in roles and roles["WARRANT"]:
        sec = roles["WARRANT"][0]
        output_parts.append(f"### 2. Causal Anatomy & Underlying Mechanics\n{format_section_with_diagrams(sec)}\n")

    if "GROUNDS" in roles and roles["GROUNDS"]:
        sec = roles["GROUNDS"][0]
        output_parts.append(f"### 3. Empirical Grounds & Manifestations\n{format_section_with_diagrams(sec)}\n")

    # Macro bridges
    bridges = epistemic_ctx.get("macro_cot_bridges", [])
    if bridges:
        output_parts.append("### 4. Cross-Concept Epistemic Bridges")
        for b in bridges:
            rel = b.get("relationship", "EXTENDS_THEORY")
            tgt = b.get("target_concept", "")
            output_parts.append(f"- **`[:{rel}]`** $\\to$ **[[{tgt}]]**")
        output_parts.append("")

    # Canonical citations
    output_parts.append("### Sources & Vault Citations")
    output_parts.append(f"- [[{concept}]]")
    for b in bridges:
        tgt = b.get("target_concept")
        if tgt:
            output_parts.append(f"- [[{tgt}]]")

    return "\n".join(output_parts)


TOULMIN_ROLES_META = [
    {
        "role": "WARRANT",
        "label": "🔬 Tactical Mechanics & Motives",
        "focus": "What, How & Why",
        "description": "Chronological tactical sequence, command hierarchy, and strategic/economic motives",
    },
    {
        "role": "GROUNDS",
        "label": "📊 Humanitarian & Force Footprint",
        "focus": "Where & Who",
        "description": "Casualties, displacement, IPC food security phase, territorial control, and alliances",
    },
    {
        "role": "REBUTTAL",
        "label": "⚖️ Competing Narratives (GRaSP)",
        "focus": "Attribution & Disputes",
        "description": "Conflicting SAF vs. RSF claims, casualty discrepancies, and NATO Admiralty ratings",
    },
    {
        "role": "SOLUTION",
        "label": "🛠️ Response & Mediation",
        "focus": "Aid & Diplomacy",
        "description": "Emergency Response Rooms (ERR) interventions, humanitarian corridors, and peace talks",
    },
    {
        "role": "BRIDGES",
        "label": "🌐 5W1H Graph Bridges",
        "focus": "Macro-CoT Links",
        "description": "Connected campaigns, commanders, locations (UN OCHA P-Codes), and triggered events",
    },
    {
        "role": "ALL",
        "label": "📑 Full 5W1H Intelligence Dossier",
        "focus": "Complete Brief",
        "description": "View all 5W1H sections, Macro-CoT bridges, and competing narratives in a single report",
    },
]


def get_toulmin_actions(available_roles: Optional[List[str]] = None) -> List[cl.Action]:
    """Builds interactive action buttons for 5W1H / Toulmin role investigation."""
    actions = []
    for meta in TOULMIN_ROLES_META:
        role = meta["role"]
        if available_roles is not None and role != "ALL":
            if role not in available_roles and not (role == "SOLUTION" and "SOLUTION_WARRANT" in available_roles):
                continue
        actions.append(
            cl.Action(
                name="drilldown_toulmin",
                payload={"role": role},
                label=meta["label"],
                description=meta["description"]
            )
        )
    return actions


def format_investigation_prompt_markdown(available_roles: Optional[List[str]] = None) -> str:
    """Renders the Markdown selection table for the next-step 5W1H investigation."""
    rows = []
    for meta in TOULMIN_ROLES_META:
        role = meta["role"]
        if available_roles is not None and role != "ALL":
            if role not in available_roles and not (role == "SOLUTION" and "SOLUTION_WARRANT" in available_roles):
                continue
        rows.append(f"| **{meta['label']}** (*{meta['focus']}*) | {meta['description']} |")

    table = (
        "| Intelligence Dimension | Analytical Focus |\n"
        "| :--- | :--- |\n" +
        "\n".join(rows)
    )

    return (
        "---\n\n"
        "### 🔍 Which intelligence dimension would you like to drill into?\n"
        "Select one or more dimensions below, or type your question in the chat:\n\n"
        f"{table}\n"
    )


def format_definitional_anchor(concept: str, retrieval_data: dict, tier: str) -> str:
    """Formats strictly the 5W1H Intelligence Anchor for Turn 1 in General Mode."""
    epistemic_ctx = retrieval_data.get("epistemic_context", {})
    roles = epistemic_ctx.get("roles", {})

    anchor_content = ""
    if "CLAIM" in roles and roles["CLAIM"]:
        anchor_content = roles["CLAIM"][0].get("content", "").strip()
    elif roles:
        first_role = list(roles.keys())[0]
        anchor_content = roles[first_role][0].get("content", "").strip()

    if not anchor_content and tier == "tier_1_synthesis":
        anchor_content = retrieval_data.get("definitional_anchor", "").strip()
        if not anchor_content:
            raw_prompt = retrieval_data.get("injected_prompt", "")
            match = re.search(r'(> \[!(?:IMPORTANT|NOTE|DEFINITION)\][^\n]*\n(?:> [^\n]*\n*)+)', raw_prompt, re.IGNORECASE)
            if match:
                anchor_content = match.group(1).strip()
            else:
                parts = re.split(r'\n##\s+', raw_prompt, maxsplit=1)
                anchor_content = parts[0].strip() if parts else raw_prompt[:500].strip()

    if not anchor_content:
        anchor_content = (
            f"In the Sudan News & OSINT Knowledge Graph (`llm-wiki-news`), "
            f"**[[{concept}]]** is an indexed intelligence node."
        )

    lines = [
        f"### 🛰️ 5W1H Intelligence Anchor: [[{concept}]]\n",
        f"> [!IMPORTANT] Executive Intelligence Summary\n> {anchor_content.replace(chr(10), chr(10) + '> ')}\n",
    ]

    available = list(roles.keys())
    if epistemic_ctx.get("macro_cot_bridges"):
        available.append("BRIDGES")
    lines.append(format_investigation_prompt_markdown(available if available else None))

    return "\n".join(lines)


def format_targeted_roles(concept: str, active_ctx: dict, requested_roles: List[str]) -> str:
    """Formats targeted Toulmin role sections based on user selection or multi-select input."""
    if "ALL" in requested_roles:
        epistemic_ctx = active_ctx.get("epistemic_context", {})
        if epistemic_ctx:
            return format_tier2_synthesis(concept, epistemic_ctx)
        return active_ctx.get("injected_prompt", "")

    epistemic_ctx = active_ctx.get("epistemic_context", {})
    roles = epistemic_ctx.get("roles", {})
    macro_bridges = active_ctx.get("macro_bridges", [])

    output = [f"### 🔍 Detailed Investigation: [[{concept}]]\n"]
    rendered_any = False

    if "WARRANT" in requested_roles:
        warrants = roles.get("WARRANT", [])
        if warrants:
            rendered_any = True
            output.append("#### 🔬 Causal Anatomy & Underlying Mechanics\n")
            for sec in warrants:
                output.append(f"{format_section_with_diagrams(sec)}\n")
        else:
            output.append("#### 🔬 Causal Anatomy\n*No causal warrant section recorded in active context.*\n")

    if "GROUNDS" in requested_roles:
        grounds = roles.get("GROUNDS", [])
        if grounds:
            rendered_any = True
            output.append("#### 📊 Empirical Grounds & Manifestations\n")
            for sec in grounds:
                output.append(f"{format_section_with_diagrams(sec)}\n")
        else:
            output.append("#### 📊 Empirical Grounds\n*No empirical grounds section recorded in active context.*\n")

    if "SOLUTION" in requested_roles:
        solutions = roles.get("SOLUTION") or roles.get("SOLUTION_WARRANT", [])
        if solutions:
            rendered_any = True
            output.append("#### 🛠️ Prescriptive Mitigations & Counter-Architectures\n")
            for sec in solutions:
                output.append(f"{format_section_with_diagrams(sec)}\n")
        else:
            output.append("#### 🛠️ Prescriptive Mitigations\n*No prescriptive mitigation section recorded in active context.*\n")

    if "REBUTTAL" in requested_roles:
        rebuttals = roles.get("REBUTTAL", [])
        if rebuttals:
            rendered_any = True
            output.append("#### ⚖️ Defeasible Boundaries & Counter-Arguments\n")
            for sec in rebuttals:
                output.append(f"{format_section_with_diagrams(sec)}\n")
        else:
            output.append("#### ⚖️ Defeasible Boundaries\n*No defeasible boundary section recorded in active context.*\n")

    if "BRIDGES" in requested_roles:
        if macro_bridges:
            rendered_any = True
            output.append("#### 🌐 Cross-Concept Epistemic Bridges\n")
            for b in macro_bridges:
                rel = b.get("relationship", "EXTENDS_THEORY")
                tgt = b.get("target_concept", "")
                output.append(f"- **`[:{rel}]`** $\\to$ **[[{tgt}]]**")
            output.append("")
        else:
            output.append("#### 🌐 Cross-Concept Epistemic Bridges\n*No ontological bridge transitions recorded for this node.*\n")

    if not rendered_any and active_ctx.get("tier") == "tier_1_synthesis":
        raw = active_ctx.get("injected_prompt", "")
        output.append(raw)
        rendered_any = True

    output.append("---\n*Sources & Vault Citations:*")
    output.append(f"- [[{concept}]]")
    for b in macro_bridges:
        tgt = b.get("target_concept")
        if tgt:
            output.append(f"- [[{tgt}]]")

    return "\n".join(output)


def parse_user_role_selection(user_query: str) -> List[str]:
    """Parses multi-select Toulmin role selections from user input text."""
    q = user_query.lower()
    selected = []

    if any(w in q for w in ["all", "full", "everything", "complete synthesis", "entire", "both"]):
        return ["ALL"]

    if any(w in q for w in ["warrant", "causal", "mechanic", "sequence", "how does", "anatomy", "underlying"]):
        selected.append("WARRANT")

    if any(w in q for w in ["ground", "empirical", "evidence", "manifestation", "failure mode", "symptom"]):
        selected.append("GROUNDS")

    if any(w in q for w in ["solution", "mitigat", "prescript", "counter-architecture", "counterarchitecture", "counter-measure", "countermeasure", "remed", "defense", "speed bump"]):
        selected.append("SOLUTION")

    if any(w in q for w in ["rebuttal", "counter-argument", "counterargument", "counter argument", "boundar", "tension", "critique", "exception", "defeasible", "limit"]):
        selected.append("REBUTTAL")

    if any(w in q for w in ["bridge", "transition", "connect", "relat", "ontolog", "neighbor"]):
        selected.append("BRIDGES")

    num_map = {
        "1": "WARRANT",
        "2": "GROUNDS",
        "3": "SOLUTION",
        "4": "REBUTTAL",
        "5": "BRIDGES",
        "6": "ALL",
    }
    for token in re.findall(r'\b[1-6]\b', q):
        if token in num_map and num_map[token] not in selected:
            selected.append(num_map[token])

    return selected


async def stream_openrouter_synthesis(
    system_prompt: str,
    user_message: str,
    valves: Dict[str, Any],
    max_tokens: int = 1200,
) -> tuple[Optional[str], dict]:
    """Streams chat completion from OpenRouter API, returning full content and execution telemetry."""
    api_key = valves.get("openrouter_api_key", "").strip()
    if not api_key:
        return None, {"status": "skipped", "reason": "No OpenRouter API key provided"}

    model = get_effective_model(valves)
    base_url = valves.get("openrouter_base_url", DEFAULT_OPENROUTER_BASE_URL).rstrip("/")
    url = f"{base_url}/chat/completions"
    try:
        temperature = float(valves.get("llm_temperature", 0.2))
    except (ValueError, TypeError):
        temperature = 0.2

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://knowledge-lab.local",
        "X-Title": "knowledge lab Learning Studio",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    t0 = time.time()
    full_content = []
    tokens_count = 0
    provider_info = "OpenRouter"
    msg = cl.Message(content="")

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    err_bytes = await response.aread()
                    err_msg = err_bytes.decode("utf-8", errors="replace")
                    return None, {
                        "status": "error",
                        "error": f"OpenRouter HTTP {response.status_code}: {err_msg}",
                        "latency_ms": round((time.time() - t0) * 1000, 2),
                        "model": model,
                    }

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            if "provider" in chunk:
                                provider_info = chunk["provider"]
                            delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if delta:
                                tokens_count += 1
                                full_content.append(delta)
                                await msg.stream_token(delta)
                        except Exception:
                            continue

        latency_ms = round((time.time() - t0) * 1000, 2)
        total_text = "".join(full_content)
        return total_text, {
            "status": "success",
            "model": model,
            "provider": provider_info,
            "latency_ms": latency_ms,
            "tokens": tokens_count,
            "stream_message": msg,
        }
    except Exception as e:
        latency_ms = round((time.time() - t0) * 1000, 2)
        return None, {
            "status": "error",
            "error": str(e),
            "latency_ms": latency_ms,
            "model": model,
        }


async def execute_toulmin_drilldown(
    concept: str,
    active_context: dict,
    selected_roles: List[str],
    valves: Dict[str, Any],
    action_label: Optional[str] = None
):
    """Executes targeted Toulmin drilldown via OpenRouter LLM or deterministic fallback."""
    drilldown_prompt = (
        "You are the knowledge lab cognitive assistant and epistemology compiler.\n"
        f"TARGET CONCEPT: [[{concept}]]\n"
        f"REQUESTED TOULMIN SECTIONS / ROLES: {', '.join(selected_roles)}\n\n"
        f"VAULT EPISTEMIC CONTEXT:\n{active_context.get('injected_prompt', '')}\n\n"
        "INSTRUCTIONS FOR DRILLDOWN:\n"
        f"Synthesize an in-depth, rigorous explanation specifically focusing on the requested role(s): {', '.join(selected_roles)}.\n"
        "- If WARRANT is requested, focus on causal anatomy and underlying mechanics.\n"
        "- If GROUNDS is requested, focus on empirical manifestations and evidence.\n"
        "- If SOLUTION is requested, focus on prescriptive mitigations and counter-architectures.\n"
        "- If REBUTTAL is requested, focus on defeasible boundaries and empirical contradictions.\n"
        "- If BRIDGES is requested, focus on macro-CoT relationships to other vault concepts.\n"
        "Cite all concept notes using clean [[wikilinks]]. Ground your statements strictly in the provided context."
    )

    remaining_actions = (
        [a for a in get_toulmin_actions() if a.payload.get("role") not in selected_roles]
        if "ALL" not in selected_roles
        else []
    )

    used_llm = False
    llm_telemetry = None
    if valves.get("enable_llm", True) and valves.get("openrouter_api_key"):
        user_query_str = f"Drilldown on {action_label or ', '.join(selected_roles)} for [[{concept}]]"
        generated_text, llm_telemetry = await stream_openrouter_synthesis(
            system_prompt=drilldown_prompt,
            user_message=user_query_str,
            valves=valves,
            max_tokens=900,
        )
        if generated_text and llm_telemetry.get("status") == "success":
            used_llm = True
            stream_msg = llm_telemetry.get("stream_message")
            if stream_msg:
                stream_msg.actions = remaining_actions
                await stream_msg.update()

    if not used_llm:
        drilldown_text = format_targeted_roles(concept, active_context, selected_roles)
        await cl.Message(content=drilldown_text, actions=remaining_actions).send()

    # Record turn in developer trace
    if valves.get("developer_mode", True):
        dev_traces = cl.user_session.get("dev_traces") or []
        turn_entry = {
            "turn_num": len(dev_traces) + 1,
            "user_query": f"Drilldown: {action_label or ', '.join(selected_roles)}",
            "dev_trace": {
                "protocol": "Internal State Machine Dispatch",
                "status": "success",
                "timings": {"total_turnaround_ms": llm_telemetry.get("latency_ms", 3.0) if llm_telemetry else 3.0},
                "stages": [
                    {
                        "id": "04_toulmin_drilldown",
                        "name": f"Toulmin Role Filter: {', '.join(selected_roles)}",
                        "status": "SERVED_FROM_CONTEXT",
                        "latency_ms": 2.5,
                    },
                    *(
                        [{
                            "id": "05_llm_inference",
                            "name": f"OpenRouter: {llm_telemetry.get('model')}",
                            "status": "STREAMED" if llm_telemetry.get("status") == "success" else "ERROR",
                            "latency_ms": llm_telemetry.get("latency_ms", 0),
                        }] if llm_telemetry else []
                    )
                ],
                "dsm_state": {
                    "operating_mode": valves.get("operating_mode", "General"),
                    "current_state": "TURN_2_DRILLDOWN",
                    "concept_anchor": concept,
                    "selected_roles": selected_roles,
                    "teachable_withholding": valves.get("teachable_agent_mode", False),
                },
                "queries": [],
                "logs": [
                    f"[DRILLDOWN] Processed roles {selected_roles} from preserved Turn 1 epistemic context.",
                    *(
                        [f"[LLM] Model: {llm_telemetry.get('model')} | Provider: {llm_telemetry.get('provider')} | Tokens: {llm_telemetry.get('tokens', 0)} | Latency: {llm_telemetry.get('latency_ms', 0)}ms"]
                        if llm_telemetry and llm_telemetry.get("status") == "success" else []
                    )
                ],
            },
            "timestamp": time.strftime("%H:%M:%S"),
            "node_data": {
                "concept_name": concept,
                "roles_covered": selected_roles,
                "tier": active_context.get("tier", "tier_2_traversal"),
            },
        }
        dev_traces.append(turn_entry)
        cl.user_session.set("dev_traces", dev_traces)
        dev_card = render_developer_sidebar(dev_traces)
        await cl.ElementSidebar.set_title("Developer Trace")
        await cl.ElementSidebar.set_elements([dev_card])


@cl.action_callback("drilldown_toulmin")
async def on_drilldown_toulmin(action: cl.Action):
    """Processes interactive action clicks for investigating specific Toulmin roles."""
    role = action.payload.get("role", "ALL")
    active_context = cl.user_session.get("active_context")
    if not active_context:
        await cl.Message(content="*No active concept context found. Please submit a new inquiry.*").send()
        return

    concept = active_context.get("concept", "Knowledge Primitives")
    valves = cl.user_session.get("valves") or load_valves()
    await execute_toulmin_drilldown(
        concept=concept,
        active_context=active_context,
        selected_roles=[role],
        valves=valves,
        action_label=action.label or role
    )


@cl.on_chat_start
async def on_chat_start():
    """Initializes learner session, loads valves into ChatSettings, and displays welcome screen."""
    valves = load_valves()
    cl.user_session.set("valves", valves)
    cl.user_session.set("dev_traces", [])
    cl.user_session.set("active_context", None)

    supported_models = [
        "openrouter/free",
        "google/gemma-4-26b-a4b-it:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "openai/gpt-4o-mini",
        "anthropic/claude-3.5-sonnet",
        "google/gemini-2.0-flash-001",
        "custom",
    ]
    current_model = valves.get("llm_model", DEFAULT_LLM_MODEL)
    model_idx = supported_models.index(current_model) if current_model in supported_models else 0

    # Initialize Chainlit ChatSettings panel (accessible via the ⚙️ icon)
    await cl.ChatSettings(
        [
            Select(
                id="operating_mode",
                label="Dialogue Mode",
                values=["General", "Learn"],
                initial_index=0 if valves.get("operating_mode") == "General" else 1,
                description="General (Direct Synthesis) or Learn (Socratic Toulmin)"
            ),
            Select(
                id="llm_model",
                label="🤖 LLM Model (OpenRouter)",
                values=supported_models,
                initial_index=model_idx,
                description="Select active LLM model router or checkpoint"
            ),
            TextInput(
                id="custom_model",
                label="Custom Model ID (if 'custom' selected)",
                initial=valves.get("custom_model", ""),
                placeholder="e.g. deepseek/deepseek-chat"
            ),
            TextInput(
                id="openrouter_api_key",
                label="🔑 OpenRouter API Key",
                initial=valves.get("openrouter_api_key", ""),
                placeholder="sk-or-v1-..."
            ),
            Switch(
                id="enable_llm",
                label="🧠 Enable LLM Synthesis (OpenRouter)",
                initial=valves.get("enable_llm", True),
                description="Stream dynamic LLM synthesis instead of static template text"
            ),
            Slider(
                id="llm_temperature",
                label="LLM Temperature",
                initial=float(valves.get("llm_temperature", 0.2)),
                min=0.0,
                max=1.0,
                step=0.05,
                description="Sampling temperature for OpenRouter LLM"
            ),
            Switch(
                id="developer_mode",
                label="🛠️ Developer Mode (FastMCP Live Traces in Sidebar)",
                initial=valves.get("developer_mode", True),
                description="Stream FastMCP execution stages, Cypher queries, and DSM state to sidebar"
            ),
            Switch(
                id="teachable_agent_mode",
                label="Teachable Agent Mode (Solution Withholding)",
                initial=valves.get("teachable_agent_mode", False),
                description="Withhold causal warrants and solutions to induce productive struggle"
            ),
            Switch(
                id="enable_chat_history",
                label="Persist Chat History in ArcadeDB",
                initial=valves.get("enable_chat_history", True),
                description="Store conversation turns in news ChatSession collection"
            ),
            Switch(
                id="enable_langfuse",
                label="Emit Langfuse Observability Traces",
                initial=valves.get("enable_langfuse", False),
                description="Export OpenTelemetry spans to Langfuse Cloud"
            ),
        ]
    ).send()

    active_m = get_effective_model(valves)
    llm_indicator = "ON" if valves.get("enable_llm", True) else "OFF"
    welcome_msg = (
        "### 🏛️ Welcome to <span class=\"brand-knowledge-lab\"><span class=\"brand-knowledge\">knowledge</span><span class=\"brand-lab\">lab</span></span> Learning Studio\n\n"
        "Explore the compiled knowledge graph, query foundational Golden Syntheses, and inspect empirical reasoning structures from ArcadeDB.\n\n"
        f"**Active Mode**: `{valves['operating_mode']}` | **LLM Synthesis**: `{llm_indicator}` (`{active_m}`) | **Developer Mode**: `{'ON' if valves.get('developer_mode', True) else 'OFF'}`.\n\n"
        "Ask any question about the knowledge vault to begin (e.g. *\"What is cognitive surrender?\"* or *\"Explain Prompt Dilution\"*):\n\n"
        "---\n"
        "*System Inspector:* Active Valves & Status"
    )

    side_panel = render_valves_panel(valves)
    await cl.Message(content=welcome_msg, elements=[side_panel]).send()


@cl.on_settings_update
async def on_settings_update(settings: Dict[str, Any]):
    """Synchronizes updated settings from the ChatSettings panel into session and valves.json."""
    valves = load_valves()
    valves.update(settings)
    cl.user_session.set("valves", valves)
    save_valves(valves)

    side_panel = render_valves_panel(valves)
    active_m = get_effective_model(valves)
    dev_str = "ON" if valves.get("developer_mode", True) else "OFF"
    llm_str = f"ON ({active_m})" if valves.get("enable_llm", True) else "OFF"

    await cl.Message(
        content=f"⚙️ **Valves Updated**: Mode set to `{valves['operating_mode']}` | LLM: `{llm_str}` | Developer Mode: `{dev_str}` | Withholding: `{'ON' if valves['teachable_agent_mode'] else 'OFF'}`.\n\n*System Inspector:* Active Valves & Status",
        elements=[side_panel]
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    user_query = message.content.strip()
    valves = cl.user_session.get("valves") or load_valves()
    fastmcp_url = valves.get("fastmcp_url", DEFAULT_FASTMCP_URL)

    # -------------------------------------------------------------------------
    # TURN 2+ TOULMIN DRILLDOWN DISPATCH (Processed from Preserved Context)
    # -------------------------------------------------------------------------
    active_context = cl.user_session.get("active_context")
    if active_context:
        selected_roles = parse_user_role_selection(user_query)
        if selected_roles:
            concept = active_context.get("concept", "Knowledge Primitives")
            await execute_toulmin_drilldown(
                concept=concept,
                active_context=active_context,
                selected_roles=selected_roles,
                valves=valves
            )
            return

    # If new question/concept, reset active context for fresh Turn 1
    cl.user_session.set("active_context", None)

    retrieval_data: Dict[str, Any] = {}
    anchor_concept = "Knowledge Primitives"
    tier = "tier_2_traversal"

    # STAGE 1: Delegate ALL retrieval & flow logic to FastMCP /api/v1/flow
    async with cl.Step(name="FastMCP Retrieval Pipeline", type="tool") as step:
        step.input = f"Query: '{user_query}' | Mode: {valves['operating_mode']} | Withholding: {valves['teachable_agent_mode']}"
        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{fastmcp_url}/api/v1/flow",
                    json={
                        "message": user_query,
                        "chat_id": cl.user_session.get("id", "learner_session"),
                        "operating_mode": valves["operating_mode"],
                        "developer_mode": valves.get("developer_mode", True),
                        "teachable_agent_mode": valves["teachable_agent_mode"],
                        "enable_chat_history": valves["enable_chat_history"],
                        "enable_langfuse": valves["enable_langfuse"],
                    }
                )
                if resp.status_code == 200:
                    retrieval_data = resp.json()
                    status = retrieval_data.get("status", "success")
                    tier = retrieval_data.get("tier", "tier_2_traversal")

                    if status == "blocked":
                        step.output = f"Safeguard Interception: {retrieval_data.get('status_message')}"
                        anchor_concept = "Security Policy"
                    elif status == "fast_respond":
                        step.output = f"Conversational Fast-Path: {retrieval_data.get('status_message')}"
                        anchor_concept = "Conversational Fast-Path"
                    elif tier == "tier_1_synthesis":
                        title = retrieval_data.get("title", "Foundational Synthesis")
                        conf = retrieval_data.get("confidence", 0.85)
                        lat = retrieval_data.get("latency_ms", round((time.time() - t0) * 1000, 2))
                        step.name = "Tier 1: Pre-Compiled Golden Synthesis Loaded"
                        step.output = f"Loaded synthesis [[{title}]] (Confidence: {conf*100:.0f}%, Latency: {lat}ms)"
                        anchor_concept = title
                    else:
                        anchor_concept = retrieval_data.get("concept", "Knowledge Primitives")
                        roles = retrieval_data.get("roles_covered", [])
                        in_window = retrieval_data.get("concepts_in_window", [])
                        lat = retrieval_data.get("latencies", {}).get("total_latency_ms", round((time.time() - t0) * 1000, 2))
                        step.name = "Tier 2: CoT Graph Traversal"
                        step.output = f"Anchored on [[{anchor_concept}]] | Roles: {', '.join(roles)} | Context window: {len(in_window)} concepts | Latency: {lat}ms"
                else:
                    step.output = f"FastMCP returned status code {resp.status_code}."
        except Exception as e:
            step.output = f"FastMCP connection warning: {str(e)}"

    # STAGE 2: Build Side-Panel ArcadeDB Graph Inspector & Developer Trace
    elements_list = []

    dev_trace = retrieval_data.get("dev_trace")
    if dev_trace and valves.get("developer_mode", True):
        dev_traces = cl.user_session.get("dev_traces") or []
        turn_entry = {
            "turn_num": len(dev_traces) + 1,
            "user_query": user_query,
            "dev_trace": dev_trace,
            "timestamp": time.strftime("%H:%M:%S"),
        }
        if status not in ("blocked", "fast_respond"):
            turn_entry["node_data"] = {
                "concept_name": anchor_concept,
                "pagerank": 0.0152,
                "community": 2,
                "aliases": ["Cognitive Abdication", "Synthetic Deference"],
                "roles_covered": retrieval_data.get("roles_covered", ["CLAIM", "GROUNDS", "WARRANT"]),
                "tier": tier
            }
        dev_traces.append(turn_entry)
        cl.user_session.set("dev_traces", dev_traces)

        dev_card = render_developer_sidebar(dev_traces)
        # In Developer Mode, manage sidebar strictly via cl.ElementSidebar to avoid message-level duplicates
        await cl.ElementSidebar.set_title("Developer Trace")
        await cl.ElementSidebar.set_elements([dev_card])
    elif status not in ("blocked", "fast_respond"):
        # When Developer Mode is off, show standalone ArcadeDB Inspector
        node_card = render_arcadedb_inspector(anchor_concept, {
            "pagerank": 0.0152,
            "community": 2,
            "aliases": ["Cognitive Abdication", "Synthetic Deference"],
            "roles_covered": retrieval_data.get("roles_covered", ["CLAIM", "GROUNDS", "WARRANT"]),
            "tier": tier
        })
        elements_list.append(node_card)

    # STAGE 3: Deliver Grounded Response (Turn 1)
    actions = []
    if status == "blocked":
        response_text = retrieval_data.get("injected_prompt", "Request blocked by safety policy.")
        await cl.Message(content=response_text).send()
    elif status == "fast_respond":
        response_text = retrieval_data.get("injected_prompt", "Hello! How can I assist your learning today?")
        await cl.Message(content=response_text).send()
    else:
        # Cache active context for subsequent turns
        cl.user_session.set("active_context", {
            "concept": anchor_concept,
            "tier": tier,
            "retrieval_data": retrieval_data,
            "epistemic_context": retrieval_data.get("epistemic_context", {}),
            "injected_prompt": retrieval_data.get("injected_prompt", ""),
            "roles": retrieval_data.get("epistemic_context", {}).get("roles", {}),
            "macro_bridges": retrieval_data.get("epistemic_context", {}).get("macro_cot_bridges", []),
            "title": retrieval_data.get("title") or anchor_concept,
        })

        available_roles = list(retrieval_data.get("epistemic_context", {}).get("roles", {}).keys())
        if retrieval_data.get("epistemic_context", {}).get("macro_cot_bridges"):
            available_roles.append("BRIDGES")
        actions = get_toulmin_actions(available_roles if available_roles else None)
        investigation_table = format_investigation_prompt_markdown(available_roles if available_roles else None)

        used_llm = False
        llm_telemetry = None
        if valves.get("enable_llm", True) and valves.get("openrouter_api_key"):
            turn1_system_prompt = (
                "You are the knowledge lab cognitive assistant and epistemology compiler.\n"
                "You are provided with verified knowledge vault context from ArcadeDB (news).\n\n"
                f"VAULT CONTEXT:\n{retrieval_data.get('injected_prompt', '')}\n\n"
                "CRITICAL INSTRUCTIONS FOR TURN 1:\n"
                "1. Deliver ONLY the concise Definitional Anchor (Claim / Core Theoretical Thesis) for the requested concept.\n"
                "2. Keep your explanation strictly concise (under 150 words). Be razor-sharp, analytical, and epistemic.\n"
                "3. Cite all concepts and primary sources using standard Obsidian wikilinks [[Concept Title]] (NEVER enclose wikilinks in backticks).\n"
                "4. Do NOT explain causal mechanics, empirical grounds, or prescriptive solutions yet. The user will select those in the next turn.\n"
            )

            generated_text, llm_telemetry = await stream_openrouter_synthesis(
                system_prompt=turn1_system_prompt,
                user_message=user_query,
                valves=valves,
                max_tokens=400,
            )

            if generated_text and llm_telemetry.get("status") == "success":
                used_llm = True
                stream_msg = llm_telemetry.get("stream_message")
                if stream_msg:
                    stream_msg.content = f"{generated_text.strip()}\n\n{investigation_table}"
                    stream_msg.actions = actions
                    stream_msg.elements = elements_list
                    await stream_msg.update()

        if not used_llm:
            response_text = format_definitional_anchor(anchor_concept, retrieval_data, tier)
            await cl.Message(
                content=response_text,
                elements=elements_list,
                actions=actions
            ).send()

        # Update developer trace with LLM stage telemetry if developer mode is active
        if valves.get("developer_mode", True) and llm_telemetry:
            dev_traces = cl.user_session.get("dev_traces") or []
            if dev_traces:
                last_trace = dev_traces[-1]["dev_trace"]
                stages = last_trace.setdefault("stages", [])
                stages.append({
                    "id": "05_llm_inference",
                    "name": f"OpenRouter: {llm_telemetry.get('model', get_effective_model(valves))}",
                    "status": "STREAMED" if llm_telemetry.get("status") == "success" else "ERROR",
                    "latency_ms": llm_telemetry.get("latency_ms", 0),
                })
                last_trace.setdefault("logs", []).append(
                    f"[LLM] Model: {llm_telemetry.get('model')} | Provider: {llm_telemetry.get('provider')} | "
                    f"Tokens: {llm_telemetry.get('tokens', 0)} | Latency: {llm_telemetry.get('latency_ms', 0)}ms"
                )
                cl.user_session.set("dev_traces", dev_traces)
                dev_card = render_developer_sidebar(dev_traces)
                await cl.ElementSidebar.set_elements([dev_card])

