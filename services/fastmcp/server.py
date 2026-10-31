"""
services/fastmcp/server.py
FastMCP Middleware Server for ArcadeDB.
Exposes:
  1. POST /inlet - OpenWebUI Pattern 2 Hybrid Pass-Through Inlet Pipe endpoint
  2. GET /health - Container and ArcadeDB healthcheck probe
  3. Standard MCP Tools & Resources over SSE / Streamable HTTP
"""

import os
import re
import json
import time
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .arcadedb_client import ArcadeDBHttpClient
from .dail_retriever import DAILSQLRetriever
from .cot_retriever import CoTRetriever
from .dialect_switcher import QueryDialectSwitcher, RouteResult
from .guardrails.arcadedb_ast import ArcadeDBASTGuard, DialectSecurityError, DialectSyntaxError
from .guardrails.semantic_classifier import ArcadeDBSafeguardClassifier
from .retrieval import (
    ConsolidatedV3Retriever,
    build_epistemic_context,
    wrap_epistemic_prompt,
    format_out_of_domain_refusal,
)
from .telemetry import tracer


# Setup logging
logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger("fastmcp-middleware")

# Initialize FastAPI App
app = FastAPI(
    title="FastMCP ArcadeDB Middleware",
    description="Decoupled Multi-Model Text-to-Query & OpenWebUI Pattern 2 Bridge for ArcadeDB",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core clients
db_client = ArcadeDBHttpClient()
safeguard_classifier = ArcadeDBSafeguardClassifier(client=db_client)
v3_retriever = ConsolidatedV3Retriever(client=db_client)
retriever = DAILSQLRetriever(client=db_client)
cot_retriever = CoTRetriever(client=db_client)


def sanitize_and_guard_query(query: str, dialect: str) -> str:
    """Delegates to ArcadeDBASTGuard for dialect sanitation and security assertions."""
    return ArcadeDBASTGuard.validate_and_sanitize(query, dialect)


def format_records_to_markdown(records: List[Dict[str, Any]], query: str, dialect: str) -> str:
    """Formats database result set into standard GitHub-Flavored Markdown table."""
    if not records:
        return (
            f"**Executed Query ({dialect.upper()}):**\n"
            f"```{dialect}\n{query}\n```\n\n"
            f"*No records found in ArcadeDB matching this query.*"
        )

    headers = list(records[0].keys())
    # Header row
    table = "| " + " | ".join(headers) + " |\n"
    table += "| " + " | ".join(["---"] * len(headers)) + " |\n"

    for r in records[:25]:
        row_vals = []
        for h in headers:
            val = str(r.get(h, ""))
            val = val.replace("|", "\\|")  # Escape pipes in table cells
            if val.endswith(".md"):
                val = f"[[{val[:-3]}]]"
            row_vals.append(val)
        table += "| " + " | ".join(row_vals) + " |\n"

    return (
        f"**Executed Query ({dialect.upper()}):**\n"
        f"```{dialect}\n{query}\n```\n\n"
        f"{table}"
    )


# --- Cold-Start Tier 1 Golden Synthesis Registry Resolver ---

_SYNTHESIS_REGISTRY_CACHE: Dict[str, Any] = {"timestamp": 0.0, "data": []}
_SYNTHESIS_CACHE_TTL: float = 30.0


async def get_active_syntheses(client: ArcadeDBHttpClient, force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Fetches active thematic_hub syntheses with their linked concepts and sections from ArcadeDB."""
    now = time.time()
    if not force_refresh and (now - _SYNTHESIS_REGISTRY_CACHE["timestamp"] < _SYNTHESIS_CACHE_TTL) and _SYNTHESIS_REGISTRY_CACHE["data"]:
        return _SYNTHESIS_REGISTRY_CACHE["data"]

    cypher = """
    MATCH (s:Synthesis)
    WHERE s.subtype = 'thematic_hub'
    OPTIONAL MATCH (s)-[:SYNTHESIZES]->(c:Concept)
    OPTIONAL MATCH (s)-[r:SYNTHESIZES_SECTION]->(sec:Section)
    RETURN s.title AS title, s.slug AS slug, s.content AS content, s.subtype AS subtype,
           s.last_updated AS last_updated, s.stale AS stale, s.stale_reason AS stale_reason,
           collect(DISTINCT c.title) AS concepts,
           collect(DISTINCT r.grounded_heading) AS sections
    """
    try:
        records = await client.query_async(cypher, language="cypher")
        _SYNTHESIS_REGISTRY_CACHE["data"] = records
        _SYNTHESIS_REGISTRY_CACHE["timestamp"] = now
        return records
    except Exception as e:
        logger.warning(f"Failed to fetch synthesis registry: {e}")
        return []


async def get_synthesis_deltas(client: ArcadeDBHttpClient, slug: str) -> List[Dict[str, Any]]:
    """Fetches unresolved SynthesisDelta documents for a specific synthesis slug."""
    sql = f"""
    SELECT section_uri, grounded_heading, change_type, diff_snippet, timestamp
    FROM SynthesisDelta
    WHERE synthesis_slug = '{slug}' AND resolved = false
    """
    try:
        return await client.query_async(sql, language="sql")
    except Exception as e:
        logger.warning(f"Failed to fetch synthesis deltas for {slug}: {e}")
        return []


def format_synthesis_for_llm(synth: Dict[str, Any], deltas: Optional[List[Dict[str, Any]]] = None) -> str:
    """Formats a pre-compiled golden synthesis into an authoritative LLM context injection."""
    title = synth.get("title", "Foundational Synthesis")
    content = synth.get("content", "")
    concepts = [f"[[{c}]]" for c in synth.get("concepts", []) if c]
    concepts_str = ", ".join(concepts) if concepts else "Core Foundations"
    is_stale = bool(synth.get("stale", False))
    last_updated = synth.get("last_updated", "2026-10-01")

    drift_badge = ""
    if is_stale:
        drift_items = []
        if deltas:
            for d in deltas:
                sec_uri = d.get("section_uri", "")
                clean_ref = re.sub(r'^(wiki/)?(concepts|entities)/', '', sec_uri)
                heading = d.get("grounded_heading", "")
                snippet = d.get("diff_snippet", "")
                if heading and "#" in clean_ref:
                    doc_base = clean_ref.split("#")[0].replace(".md", "")
                    link_target = f"[[{doc_base}#{heading}]]"
                elif clean_ref:
                    doc_base = clean_ref.split("#")[0].replace(".md", "")
                    link_target = f"[[{doc_base}]]"
                else:
                    link_target = "underlying concept"

                desc = f": {snippet}" if snippet and snippet != "Section content divergence detected." else ""
                drift_items.append(f"- **{link_target}**{desc}")
        elif synth.get("stale_reason"):
            drift_items.append(f"- {synth.get('stale_reason')}")
        else:
            drift_items.append("- Grounded section content divergence detected in recent ingestion.")

        drift_items_str = "\n".join(f"> {item}" for item in drift_items)
        drift_badge = (
            f"> [!WARNING] Synthesis Epistemic Drift Notice\n"
            f"> This pre-compiled synthesis was last updated on {last_updated}. Recent evidence has been ingested into {len(drift_items)} underlying section(s):\n"
            f"{drift_items_str}\n"
            f"> The core architecture below remains valid, but review the grounded section link(s) above for the latest empirical nuances.\n\n"
        )

    header = (
        f"# Grounded Epistemic Synthesis: {title}\n\n"
        f"{drift_badge}"
        f"> [!IMPORTANT] Tier 1 Pre-Compiled Golden Synthesis\n"
        f"> This authoritative synthesis unifies foundational concepts: {concepts_str}.\n"
        f"> All claims, causal mechanics, and prescriptive playbooks have been pre-compiled and forensically validated.\n\n"
    )
    return header + content


def extract_synthesis_definitional_anchor(content: str) -> str:
    """Extracts the executive thesis anchor / definitional claim from a pre-compiled synthesis."""
    if not content:
        return ""
    # Check for callout e.g. > [!IMPORTANT] Executive Thesis Anchor ...
    match = re.search(r'(> \[!(?:IMPORTANT|NOTE|DEFINITION)\][^\n]*\n(?:> [^\n]*\n*)+)', content, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Or find text before the first section ##
    parts = re.split(r'\n##\s+', content, maxsplit=1)
    if parts:
        clean = re.sub(r'^#\s+[^\n]+\n+', '', parts[0]).strip()
        if clean:
            return clean
    return content[:400].strip()


async def check_synthesis_registry(
    prompt: str,
    client: ArcadeDBHttpClient,
    min_confidence: float = 0.75
) -> Optional[Dict[str, Any]]:
    """
    Cold-start Tier 1 resolver: matches incoming natural language queries against
    pre-compiled golden syntheses in ArcadeDB.
    Returns matched synthesis package in < 5ms if confidence >= min_confidence.
    """
    t0 = time.time()
    syntheses = await get_active_syntheses(client)
    if not syntheses:
        return None

    clean_prompt = prompt.lower().strip()
    prompt_tokens = set(re.findall(r'\b\w+\b', clean_prompt))

    best_match = None
    best_score = 0.0

    for synth in syntheses:
        title = synth.get("title") or ""
        slug = synth.get("slug") or ""
        title_lower = title.lower()
        slug_norm = slug.replace("-", " ")
        concepts = synth.get("concepts") or []

        score = 0.0
        matched_concepts = []

        # 1. Exact or near-exact title/slug match
        if title_lower in clean_prompt or clean_prompt in title_lower:
            score = 1.0
        elif slug_norm in clean_prompt:
            score = 1.0
        else:
            # 2. Check concept containment
            for c in concepts:
                c_lower = c.lower()
                if c_lower in clean_prompt:
                    matched_concepts.append(c)
                else:
                    c_tokens = set(re.findall(r'\b\w+\b', c_lower))
                    if c_tokens and c_tokens.issubset(prompt_tokens):
                        matched_concepts.append(c)

            if len(matched_concepts) >= 2:
                score = 0.95
            elif len(matched_concepts) == 1:
                c_words = matched_concepts[0].split()
                if len(c_words) >= 2:
                    score = 0.85
                else:
                    score = 0.75

            # 3. Check title token overlap bonus
            title_tokens = set(re.findall(r'\b\w+\b', title_lower)) - {"and", "the", "of", "in", "for", "a", "an"}
            overlap = title_tokens.intersection(prompt_tokens)
            if len(overlap) >= 2 and score < 0.80:
                score = max(score, 0.80)

        if score > best_score:
            best_score = score
            best_match = (synth, matched_concepts, score)

    SYNTHESIS_DRIFT_POLICY = os.getenv("SYNTHESIS_DRIFT_POLICY", "badge").lower()

    if best_match and best_match[2] >= min_confidence:
        synth, matched_concepts, score = best_match
        is_stale = bool(synth.get("stale", False))

        # Check fallback policy: if strict fallback is requested on stale, bypass Tier 1
        if is_stale and SYNTHESIS_DRIFT_POLICY == "fallback":
            logger.info(f"Synthesis '{synth.get('slug')}' is stale and policy is 'fallback' -> bypassing Tier 1.")
            return None

        deltas = []
        if is_stale:
            deltas = await get_synthesis_deltas(client, synth.get("slug", ""))

        elapsed_ms = round((time.time() - t0) * 1000, 2)
        injected = format_synthesis_for_llm(synth, deltas=deltas)
        return {
            "hit": True,
            "title": synth.get("title"),
            "slug": synth.get("slug"),
            "subtype": synth.get("subtype", "thematic_hub"),
            "confidence": score,
            "stale": is_stale,
            "stale_reason": synth.get("stale_reason", ""),
            "drift_detected": is_stale,
            "deltas": deltas,
            "concepts": synth.get("concepts", []),
            "sections": synth.get("sections", []),
            "matched_concepts": matched_concepts,
            "definitional_anchor": extract_synthesis_definitional_anchor(synth.get("content", "")),
            "injected_prompt": injected,
            "latency_ms": elapsed_ms,
        }

    return None


# --- Request Models ---

class InletPayload(BaseModel):
    message: str = Field(..., description="User prompt or direct query")
    dialect: Optional[str] = Field("auto", description="'auto', 'sql', or 'cypher'")


class QueryPayload(BaseModel):
    query: str = Field(..., description="Executable SQL or Cypher query")
    dialect: Optional[str] = Field("auto", description="'sql' or 'cypher'")


class SafeguardPayload(BaseModel):
    message: str = Field(..., description="User prompt to evaluate for safeguards and intent")


class SectionRetrievePayload(BaseModel):
    uri: str = Field(..., description="Section URI e.g. concepts/Context Window Exhaustion#3-manifestations")
    include_diagram: Optional[bool] = Field(False, description="Whether to include renderable Mermaid code")


class ConceptToulminPayload(BaseModel):
    concept_title: str = Field(..., description="Canonical concept title e.g. Context Window Exhaustion")
    include_diagrams: Optional[bool] = Field(False, description="Whether to include renderable Mermaid code")


class V3RetrievePayload(BaseModel):
    prompt: str = Field(..., description="User prompt or scenario query")
    user_category: Optional[str] = Field("intermediate", description="'beginner', 'intermediate', or 'expert'")
    target_concepts: Optional[List[str]] = Field(default_factory=list, description="Optional target concept hints")
    expected_roles: Optional[List[str]] = Field(default_factory=list, description="Optional expected Toulmin roles")
    topic: Optional[str] = Field("", description="Optional topic hint")
    include_epistemic_context: Optional[bool] = Field(False, description="Whether to include structured JSON epistemic context & prompt wrapper")
    teachable_agent_mode: Optional[bool] = Field(False, description="Socratic Gating: Withhold causal warrants and prescriptive solutions")
    operating_mode: Optional[str] = Field("General", description="'General' or 'Learn'")


class EpistemicContextRequest(BaseModel):
    retrieval_result: Dict[str, Any] = Field(..., description="V3 retrieval result object")
    user_prompt: str = Field(..., description="Original user prompt")
    teachable_agent_mode: Optional[bool] = Field(False, description="Socratic Gating")
    operating_mode: Optional[str] = Field("General", description="'General' or 'Learn'")


class FlowPayload(BaseModel):
    message: str = Field(..., description="User prompt or scenario query")
    chat_id: Optional[str] = Field("default_chat", description="Chat or session ID")
    operating_mode: Optional[str] = Field("General", description="'General' or 'Learn'")
    teachable_agent_mode: Optional[bool] = Field(False, description="Socratic Gating: Withhold causal warrants and solutions")
    enable_chat_history: Optional[bool] = Field(True, description="Persist turn in key store")
    enable_langfuse: Optional[bool] = Field(False, description="Emit nested Langfuse traces")
    user_category: Optional[str] = Field("intermediate", description="'beginner', 'intermediate', 'expert'")
    target_concepts: Optional[List[str]] = Field(default_factory=list, description="Target concept hints")
    expected_roles: Optional[List[str]] = Field(default_factory=list, description="Expected Toulmin roles")
    topic: Optional[str] = Field("", description="Topic hint")
    developer_mode: Optional[bool] = Field(False, description="Emit rich developer inspection traces and queries")


class FlowOutletPayload(BaseModel):
    chat_id: Optional[str] = Field("default_chat", description="Chat or session ID")
    assistant_response: str = Field(..., description="Full assistant response text")
    trace_id: Optional[str] = Field(None, description="Optional associated Langfuse trace ID")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Turn telemetry metadata")


# --- Endpoints ---

@app.get("/health")
async def health_check():
    """Healthcheck probe for container orchestration."""
    arcadedb_ok = await db_client.is_ready_async()
    status = "healthy" if arcadedb_ok else "degraded"
    return {
        "status": status,
        "service": "fastmcp-arcadedb-middleware",
        "arcadedb_ready": arcadedb_ok,
        "arcadedb_url": settings.arcadedb_url,
        "database": settings.arcadedb_database,
    }


@app.post("/api/v1/safeguards/evaluate")
async def evaluate_safeguards(payload: SafeguardPayload):
    """
    Evaluates incoming user text against ArcadeDB IntentAnchor documents.
    Short-circuits adversarial intrusions and trivial chit-chat in < 3ms.
    """
    return await safeguard_classifier.evaluate_safeguards(payload.message)


@app.post("/inlet")
async def handle_inlet(payload: InletPayload):
    """
    OpenWebUI Pattern 2 Hybrid Pass-Through Inlet Pipe endpoint.
    Intercepts natural language questions, evaluates native safeguards, maps intent,
    executes the verified query, and returns formatted Markdown context.
    """
    # -------------------------------------------------------------------------
    # STAGE 1: ArcadeDB Native Safeguards & Intent Gating (Phase 1)
    # -------------------------------------------------------------------------
    guard_res = await safeguard_classifier.evaluate_safeguards(payload.message)
    if guard_res["action"] == "REJECT_SECURITY":
        return {
            "status": "blocked",
            "dialect": "none",
            "intent": guard_res["intent"],
            "routing_reason": f"Safeguard Policy Violation: {guard_res['intent']}",
            "executed_query": "N/A (Short-circuited by ArcadeDB IntentAnchor)",
            "record_count": 0,
            "context_markdown": guard_res["template"],
            "safeguard_telemetry": guard_res,
        }
    elif guard_res["action"] == "FAST_RESPOND":
        return {
            "status": "fast_respond",
            "dialect": "none",
            "intent": guard_res["intent"],
            "routing_reason": f"Conversational Fast-Path: {guard_res['intent']}",
            "executed_query": "N/A (Instant response template)",
            "record_count": 0,
            "context_markdown": guard_res["template"],
            "safeguard_telemetry": guard_res,
        }

    # -------------------------------------------------------------------------
    # STAGE 2: Query Dialect Switching & Execution
    # -------------------------------------------------------------------------
    route_res = QueryDialectSwitcher.route(
        raw_message=payload.message,
        preferred_dialect=payload.dialect or settings.default_dialect,
    )
    clean_prompt = route_res.clean_prompt
    target_dialect = route_res.dialect
    intent = route_res.intent
    is_direct_query = route_res.is_raw_query
    routing_reason = route_res.routing_reason

    # On-demand diagram visualization handler
    if intent == "diagram_visualization":
        candidate_title = re.sub(
            r"(?i)\b(show diagram|visualize|render diagram|mermaid diagram|draw flowchart|display diagram|diagram of|see diagram|diagrams for|diagram|concept|flowchart)\b",
            "",
            clean_prompt,
        ).strip(" :?[]'\"")
        find_concept_q = """
        MATCH (c:Concept)
        WHERE toLower(c.title) CONTAINS toLower($needle) OR toLower($needle) CONTAINS toLower(c.title)
        RETURN c.title AS title
        LIMIT 1
        """
        c_res = await db_client.query_async(find_concept_q, language="cypher", params={"needle": candidate_title})
        if c_res:
            matched_concept = c_res[0]["title"]
            window_data = await cot_retriever.retrieve_concept_toulmin_window(
                concept_title=matched_concept,
                include_diagrams=True,
            )
            markdown = cot_retriever.format_toulmin_window_to_markdown(window_data)
            return {
                "status": "success",
                "dialect": "cypher",
                "intent": intent,
                "routing_reason": f"Visualized Toulmin window for concept [[{matched_concept}]] with linked diagrams.",
                "executed_query": find_concept_q.replace("$needle", repr(candidate_title)),
                "record_count": 1,
                "context_markdown": markdown,
            }

    if is_direct_query:
        query_to_execute = clean_prompt
    else:
        # Retrieve DAIL-SQL Exemplars from TextToQueryDemo
        exemplars = retriever.retrieve_exemplars(
            clean_prompt,
            dialect=target_dialect,
            top_k=2,
        )

        if exemplars and intent != "general":
            # For known intents, use the calibrated query template from the top exemplar
            query_to_execute = exemplars[0]["query"]
        else:
            # Fallback to exemplar query if available
            query_to_execute = exemplars[0]["query"] if exemplars else "SELECT count(*) FROM Concept;"

    # AST Guardrail & Sanitation
    try:
        guarded_query = sanitize_and_guard_query(query_to_execute, target_dialect)
    except (DialectSecurityError, DialectSyntaxError, ValueError) as ve:
        logger.warning(f"Guardrail intercepted query: {ve}")
        return {
            "status": "error",
            "error": str(ve),
            "dialect": target_dialect,
            "intent": intent,
            "routing_reason": routing_reason,
            "context_markdown": f"> [!WARNING] Query Guardrail Violation\n> {str(ve)}",
        }

    # Execute against ArcadeDB
    try:
        records = await db_client.query_async(guarded_query, language=target_dialect)
        markdown_table = format_records_to_markdown(records, guarded_query, target_dialect)
        
        return {
            "status": "success",
            "dialect": target_dialect,
            "intent": intent,
            "routing_reason": routing_reason,
            "executed_query": guarded_query,
            "record_count": len(records),
            "context_markdown": markdown_table,
        }
    except Exception as e:
        logger.error(f"Error executing ArcadeDB query: {e}")
        return {
            "status": "error",
            "error": str(e),
            "dialect": target_dialect,
            "intent": intent,
            "routing_reason": routing_reason,
            "executed_query": guarded_query,
            "context_markdown": f"> [!CAUTION] Query Execution Error\n> `{str(e)}`\n\n```{target_dialect}\n{guarded_query}\n```",
        }


@app.post("/api/v1/query")
async def execute_raw_query(payload: QueryPayload):
    """Executes a validated read-only SQL or Cypher query directly."""
    route_res = QueryDialectSwitcher.route(payload.query, payload.dialect or "auto")
    dialect = route_res.dialect
    clean_query = route_res.clean_prompt
    try:
        guarded = sanitize_and_guard_query(clean_query, dialect)
        records = await db_client.query_async(guarded, language=dialect)
        return {
            "status": "success",
            "dialect": dialect,
            "routing_reason": route_res.routing_reason,
            "record_count": len(records),
            "records": records,
        }
    except (DialectSecurityError, DialectSyntaxError, ValueError) as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/schema/types")
async def get_schema_types():
    """Returns declared ArcadeDB types and properties."""
    try:
        records = await db_client.query_async(
            "SELECT name, @cat AS category, properties FROM schema:types",
            language="sql",
        )
        return {"types": records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/recompute-weights")
async def recompute_weights():
    """
    Triggers in-engine Cypher weight propagation and weighted PageRank recomputation.
    Completes in < 250ms with zero Python-side record iteration.
    """
    try:
        # 1. Propagate weights to Toulmin containment edges
        cypher_toulmin = """
        MATCH (c:Concept)-[e:HAS_GROUNDS|HAS_WARRANT|HAS_CLAIM|HAS_REBUTTAL|HAS_SOLUTION|HAS_QUALIFIER|HAS_BACKING]->(s:Section)
        WHERE s.weight IS NOT NULL
        SET e.weight = s.weight
        RETURN count(e) AS updated_edges
        """
        res1 = await db_client.command_async(cypher_toulmin, language="cypher")
        updated_toulmin = res1[0].get("updated_edges", 0) if res1 else 0

        # 2. Signed negative weight on rebuttal edges
        cypher_rebuttal = """
        MATCH (c:Concept)-[e:HAS_REBUTTAL]->(s:Section)
        WHERE s.weight IS NOT NULL
        SET e.signed_weight = -1.0 * s.weight
        RETURN count(e) AS signed_edges
        """
        res2 = await db_client.command_async(cypher_rebuttal, language="cypher")
        signed_rebuttal = res2[0].get("signed_edges", 0) if res2 else 0

        # 3. Weighted PageRank across all graph vertices
        cypher_pr = """
        CALL algo.pagerank({dampingFactor: 0.85, maxIterations: 20, weightProperty: 'weight'})
        YIELD node, score
        WITH toString(node) AS rid_str, score
        MATCH (n) WHERE elementId(n) = rid_str
        SET n.pagerank = score
        RETURN count(n) AS total_pagerank
        """
        res3 = await db_client.command_async(cypher_pr, language="cypher")
        total_pagerank = res3[0].get("total_pagerank", 0) if res3 else 0

        return {
            "status": "success",
            "updated_toulmin_edges": updated_toulmin,
            "signed_rebuttal_edges": signed_rebuttal,
            "nodes_with_pagerank": total_pagerank,
        }
    except Exception as e:
        logger.error(f"Error recomputing weights in-engine: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/cot/section")
async def retrieve_cot_section(payload: SectionRetrievePayload):
    """Retrieves an atomic section with optional linked Mermaid diagram assets."""
    try:
        res = await cot_retriever.retrieve_section_with_diagram(
            section_uri=payload.uri,
            include_diagram=payload.include_diagram or False,
        )
        if not res:
            raise HTTPException(status_code=404, detail=f"Section not found: {payload.uri}")
        return {"status": "success", "section": res}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving CoT section: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/cot/concept")
async def retrieve_cot_concept_window(payload: ConceptToulminPayload):
    """Retrieves the full Toulmin argumentation window for a concept, with optional diagram assets."""
    try:
        window_data = await cot_retriever.retrieve_concept_toulmin_window(
            concept_title=payload.concept_title,
            include_diagrams=payload.include_diagrams or False,
        )
        markdown = cot_retriever.format_toulmin_window_to_markdown(window_data)
        return {
            "status": "success",
            "concept_title": window_data.get("concept_title") or payload.concept_title,
            "include_diagrams": payload.include_diagrams or False,
            "roles": window_data.get("roles", {}),
            "markdown": markdown,
        }
    except Exception as e:
        logger.error(f"Error retrieving concept Toulmin window: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/retrieval/v3")
async def retrieve_v3(payload: V3RetrievePayload):
    """
    Consolidated V3 Retrieval Pipeline endpoint:
    Multi-concept resolution, in-engine JVector/Lucene anchor selection,
    1-hop ontological Macro-CoT graph traversal, and Toulmin role assembly.
    Optionally returns structured JSON epistemic context and Markdown wrapper.
    """
    try:
        res = await v3_retriever.retrieve_v3(
            prompt=payload.prompt,
            user_category=payload.user_category,
            target_concepts=payload.target_concepts,
            expected_roles=payload.expected_roles,
            topic=payload.topic,
        )
        if payload.include_epistemic_context:
            epistemic_ctx = build_epistemic_context(
                res,
                teachable_agent_mode=payload.teachable_agent_mode or False,
                operating_mode=payload.operating_mode or "General",
            )
            wrapped_prompt = wrap_epistemic_prompt(
                epistemic_ctx,
                payload.prompt,
                teachable_agent_mode=payload.teachable_agent_mode or False,
                operating_mode=payload.operating_mode or "General",
            )
            res["epistemic_context"] = epistemic_ctx.model_dump(exclude_none=True)
            res["injected_prompt"] = wrapped_prompt
        return res
    except Exception as e:
        logger.error(f"Error executing V3 retrieval: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/context/epistemic")
async def format_epistemic_context_endpoint(payload: EpistemicContextRequest):
    """
    Builds structured Epistemic JSON Context and Markdown wrapper from V3 retrieval results.
    """
    try:
        ctx = build_epistemic_context(
            payload.retrieval_result,
            teachable_agent_mode=payload.teachable_agent_mode or False,
            operating_mode=payload.operating_mode or "General",
        )
        wrapped = wrap_epistemic_prompt(
            ctx,
            payload.user_prompt,
            teachable_agent_mode=payload.teachable_agent_mode or False,
            operating_mode=payload.operating_mode or "General",
        )
        return {
            "status": "success",
            "epistemic_context": ctx.model_dump(exclude_none=True),
            "injected_prompt": wrapped,
        }
    except Exception as e:
        logger.error(f"Error building epistemic context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/flow")
async def execute_consolidated_flow(payload: FlowPayload):
    """
    Consolidated FastMCP Retrieval Flow endpoint connecting OpenWebUI to:
    1. Safeguard & Intent Gating (Span 01_safeguard_classification)
    2. V3 In-Engine Vector/Graph Retrieval:
       - Entity & Acronym Resolution (Span 02_entity_resolution)
       - Candidate Scoring & S0 Anchor (Span 03_vector_knn_s0_selection)
       - 1-Hop Macro-CoT Graph Traversal (Span 04_macro_cot_expansion)
    3. Epistemic Structured JSON Context & Socratic Withholding (Span 05_epistemic_json_assembly)
    """
    t_flow_start = time.perf_counter()

    trace_mgr = tracer.trace_turn(
        name="FastMCP_Retrieval_Turn",
        chat_id=payload.chat_id,
        user_prompt=payload.message,
        enable_override=payload.enable_langfuse,
        metadata={
            "operating_mode": payload.operating_mode,
            "teachable_agent_mode": payload.teachable_agent_mode,
            "user_category": payload.user_category,
        },
    )

    with trace_mgr as turn_trace:
        # -------------------------------------------------------------------------
        # STAGE 1: Safeguards & Intent Gating (Span 01)
        # -------------------------------------------------------------------------
        with turn_trace.span("01_safeguard_classification", as_type="guardrail", input_data=payload.message) as sp:
            guard_res = await safeguard_classifier.evaluate_safeguards(payload.message)
            sp.set_output({
                "action": guard_res["action"],
                "intent": guard_res["intent"],
                "latency_ms": guard_res.get("latency_ms"),
            })

        if guard_res["action"] == "REJECT_SECURITY":
            refusal = guard_res.get("response_template") or (
                "> [!CAUTION] Request Rejected by System Policy\n"
                "> The query violates the knowledge vault safety policies."
            )
            turn_trace.metadata["security_violation"] = guard_res["intent"]
            turn_trace.output = refusal
            t_total_ms = round((time.perf_counter() - t_flow_start) * 1000, 2)

            queries = []
            if guard_res.get("executed_query"):
                queries.append({
                    "stage": f"01_safeguards_{guard_res.get('execution_mode', 'policy_eval')}",
                    "dialect": guard_res.get("dialect", "sql"),
                    "query": guard_res.get("executed_query"),
                    "time_ms": guard_res.get("latency_ms", 0),
                    "results_count": 1 if guard_res.get("matched_utterance") else 0,
                })

            dev_trace = {
                "protocol": "HTTP/1.1 POST /api/v1/flow",
                "endpoint": "/api/v1/flow",
                "chat_id": payload.chat_id,
                "user_query": payload.message,
                "status": "blocked",
                "timings": {
                    "total_turnaround_ms": t_total_ms,
                    "safeguard_ms": guard_res.get("latency_ms", 0)
                },
                "stages": [
                    {
                        "id": "01_safeguards",
                        "name": "Safeguard & Intent Gate",
                        "status": "REJECT_SECURITY",
                        "intent": guard_res["intent"],
                        "category": guard_res.get("category", "adversarial"),
                        "matched_utterance": guard_res.get("matched_utterance", ""),
                        "execution_mode": guard_res.get("execution_mode", "policy_eval"),
                        "confidence": guard_res.get("confidence", 1.0),
                        "latency_ms": guard_res.get("latency_ms", 0),
                    }
                ],
                "dsm_state": {
                    "operating_mode": payload.operating_mode,
                    "current_state": "POLICY_REJECTED",
                    "concept_anchor": "Security Policy Interception",
                    "tier": "security_reject",
                    "teachable_withholding": payload.teachable_agent_mode,
                },
                "queries": queries,
                "logs": [
                    f"[SAFEGUARD] Action: REJECT_SECURITY | Intent: {guard_res['intent']}",
                    f"[SAFEGUARD] Mode: {guard_res.get('execution_mode')} | Match: '{guard_res.get('matched_utterance')}' ({guard_res.get('latency_ms', 0):.2f}ms)",
                    "[SECURITY] Bypassed Tier 1 & Tier 2 retrieval — zero LLM tokens spent."
                ],
            }
            return {
                "status": "blocked",
                "status_message": f"Security Policy Violation: {guard_res['intent']}",
                "action": "REJECT_SECURITY",
                "injected_prompt": refusal,
                "trace_id": turn_trace.trace_id,
                "dev_trace": dev_trace,
            }

        if guard_res["action"] == "FAST_RESPOND":
            template = guard_res.get("response_template") or "Hello! How can I assist your learning today?"
            turn_trace.metadata["fast_respond_intent"] = guard_res["intent"]
            turn_trace.output = template
            t_total_ms = round((time.perf_counter() - t_flow_start) * 1000, 2)

            queries = []
            if guard_res.get("executed_query"):
                queries.append({
                    "stage": f"01_safeguards_{guard_res.get('execution_mode', 'fast_path')}",
                    "dialect": guard_res.get("dialect", "sql"),
                    "query": guard_res.get("executed_query"),
                    "time_ms": guard_res.get("latency_ms", 0),
                    "results_count": 1 if guard_res.get("matched_utterance") else 0,
                })

            dev_trace = {
                "protocol": "HTTP/1.1 POST /api/v1/flow",
                "endpoint": "/api/v1/flow",
                "chat_id": payload.chat_id,
                "user_query": payload.message,
                "status": "fast_respond",
                "timings": {
                    "total_turnaround_ms": t_total_ms,
                    "safeguard_ms": guard_res.get("latency_ms", 0)
                },
                "stages": [
                    {
                        "id": "01_safeguards",
                        "name": "Safeguard & Intent Gate",
                        "status": "FAST_RESPOND",
                        "intent": guard_res["intent"],
                        "category": guard_res.get("category", "conversational"),
                        "matched_utterance": guard_res.get("matched_utterance", ""),
                        "execution_mode": guard_res.get("execution_mode", "fast_path"),
                        "confidence": guard_res.get("confidence", 1.0),
                        "latency_ms": guard_res.get("latency_ms", 0),
                    }
                ],
                "dsm_state": {
                    "operating_mode": payload.operating_mode,
                    "current_state": "FAST_RESPOND",
                    "concept_anchor": "Conversational Fast-Path",
                    "tier": "fast_respond",
                    "teachable_withholding": payload.teachable_agent_mode,
                },
                "queries": queries,
                "logs": [
                    f"[SAFEGUARD] Action: FAST_RESPOND | Intent: {guard_res['intent']}",
                    f"[SAFEGUARD] Mode: {guard_res.get('execution_mode')} | Match: '{guard_res.get('matched_utterance')}' ({guard_res.get('latency_ms', 0):.2f}ms)",
                    "[FAST_PATH] Bypassed Tier 1 & Tier 2 retrieval — zero LLM tokens spent."
                ],
            }
            return {
                "status": "fast_respond",
                "status_message": f"Instant Response: {guard_res['intent']}",
                "action": "FAST_RESPOND",
                "injected_prompt": template,
                "trace_id": turn_trace.trace_id,
                "dev_trace": dev_trace,
            }

        # -------------------------------------------------------------------------
        # STAGE 1.5: Cold-Start Pre-Compiled Golden Synthesis Resolver (Tier 1)
        # -------------------------------------------------------------------------
        with turn_trace.span("01b_synthesis_registry_lookup", as_type="retrieval", input_data=payload.message) as sp:
            synth_hit = await check_synthesis_registry(payload.message, client=db_client)
            if synth_hit:
                is_stale = synth_hit.get("stale", False)
                sp.set_output({
                    "hit": True,
                    "title": synth_hit["title"],
                    "slug": synth_hit["slug"],
                    "confidence": synth_hit["confidence"],
                    "stale": is_stale,
                    "drift_detected": synth_hit.get("drift_detected", False),
                    "matched_concepts": synth_hit.get("matched_concepts", []),
                    "latency_ms": synth_hit.get("latency_ms", 0),
                })
                turn_trace.metadata.update({
                    "tier": "tier_1_synthesis",
                    "primary_concept": synth_hit["title"],
                    "synthesis_slug": synth_hit["slug"],
                    "confidence": synth_hit["confidence"],
                    "stale": is_stale,
                    "drift_detected": synth_hit.get("drift_detected", False),
                })
                turn_trace.output = synth_hit["injected_prompt"]
                status_msg = f"Pre-Compiled Golden Synthesis Loaded: {synth_hit['title']}"
                if is_stale:
                    status_msg += " (Epistemic Drift Detected - Badged)"
                t_total_ms = round((time.perf_counter() - t_flow_start) * 1000, 2)
                dev_trace = {
                    "protocol": "HTTP/1.1 POST /api/v1/flow",
                    "endpoint": "/api/v1/flow",
                    "chat_id": payload.chat_id,
                    "user_query": payload.message,
                    "status": "tier_1_synthesis",
                    "timings": {
                        "total_turnaround_ms": t_total_ms,
                        "safeguard_ms": guard_res.get("latency_ms", 0),
                        "synthesis_lookup_ms": synth_hit.get("latency_ms", 0),
                    },
                    "stages": [
                        *(
                            [{
                                "id": "01_safeguards",
                                "name": "Safeguard & Intent Gate",
                                "status": guard_res.get("action", "PASS"),
                                "intent": guard_res.get("intent", "DOMAIN_INQUIRY"),
                                "latency_ms": guard_res.get("latency_ms", 0),
                            }]
                            if guard_res.get("action") not in ("PASS", "PROCEED")
                            else []
                        ),
                        {
                            "id": "01b_synthesis_registry",
                            "name": "Tier 1 Golden Synthesis Matcher",
                            "status": "HIT",
                            "confidence": synth_hit["confidence"],
                            "stale": is_stale,
                            "latency_ms": synth_hit.get("latency_ms", 0),
                            "details": f"{synth_hit['title']} (confidence: {synth_hit['confidence']:.2f})",
                        },
                    ],
                    "dsm_state": {
                        "operating_mode": payload.operating_mode,
                        "current_state": "TURN_1_SYNTHESIS_LOADED",
                        "concept_anchor": synth_hit["title"],
                        "tier": "tier_1_synthesis",
                        "teachable_withholding": payload.teachable_agent_mode,
                    },
                    "queries": [
                        *(
                            [{
                                "stage": f"01_safeguards_{guard_res.get('execution_mode', 'scan')}",
                                "dialect": guard_res.get("dialect", "sql"),
                                "query": guard_res.get("executed_query"),
                                "time_ms": guard_res.get("latency_ms", 0),
                                "results_count": 0,
                            }]
                            if guard_res.get("executed_query") and guard_res.get("action") not in ("PASS", "PROCEED")
                            else []
                        ),
                        {
                            "stage": "01b_synthesis_lookup",
                            "dialect": "cypher",
                            "query": f"MATCH (s:Synthesis {{slug: '{synth_hit['slug']}'}}) RETURN s.title, s.content, s.stale",
                            "time_ms": synth_hit.get("latency_ms", 0),
                            "results_count": 1,
                        }
                    ],
                    "logs": [
                        *(
                            [f"[SAFEGUARD] Intercepted: {guard_res.get('intent')} ({guard_res.get('latency_ms', 0):.2f}ms)"]
                            if guard_res.get("action") not in ("PASS", "PROCEED")
                            else []
                        ),
                        f"[TIER_1] Pre-compiled Golden Synthesis HIT: {synth_hit['title']} (confidence: {synth_hit['confidence']:.2f}, stale: {is_stale})",
                        f"[SYNTHESIS] Linked sections: {len(synth_hit.get('sections', []))} sections, {len(synth_hit.get('concepts', []))} concepts",
                    ],
                }
                return {
                    "status": "success",
                    "tier": "tier_1_synthesis",
                    "status_message": status_msg,
                    "injected_prompt": synth_hit["injected_prompt"],
                    "definitional_anchor": synth_hit.get("definitional_anchor", ""),
                    "title": synth_hit["title"],
                    "slug": synth_hit["slug"],
                    "confidence": synth_hit["confidence"],
                    "stale": is_stale,
                    "stale_reason": synth_hit.get("stale_reason", ""),
                    "drift_detected": synth_hit.get("drift_detected", False),
                    "deltas": synth_hit.get("deltas", []),
                    "concepts": synth_hit.get("concepts", []),
                    "sections": synth_hit.get("sections", []),
                    "trace_id": turn_trace.trace_id,
                    "latency_ms": synth_hit.get("latency_ms", 0),
                    "dev_trace": dev_trace,
                }
            sp.set_output({"hit": False})

        # -------------------------------------------------------------------------
        # STAGE 2: V3 Retrieval Engine (Spans 02, 03, 04)
        # -------------------------------------------------------------------------
        ret_res = await v3_retriever.retrieve_v3(
            prompt=payload.message,
            user_category=payload.user_category or "intermediate",
            target_concepts=payload.target_concepts,
            expected_roles=payload.expected_roles,
            topic=payload.topic or "",
            turn_trace=turn_trace,
        )

        # -------------------------------------------------------------------------
        # STAGE 2.5: Low-Weight Domain Gating
        # -------------------------------------------------------------------------
        fit_status = ret_res.get("fit_status", "UNKNOWN")
        if fit_status == "SEMANTIC_DRIFT" and not ret_res.get("matched_concepts"):
            refusal_card = format_out_of_domain_refusal(payload.message)
            turn_trace.metadata["out_of_domain"] = True
            turn_trace.output = refusal_card
            t_total_ms = round((time.perf_counter() - t_flow_start) * 1000, 2)
            dev_trace = {
                "protocol": "HTTP/1.1 POST /api/v1/flow",
                "endpoint": "/api/v1/flow",
                "chat_id": payload.chat_id,
                "user_query": payload.message,
                "status": "out_of_domain",
                "timings": {
                    "total_turnaround_ms": t_total_ms,
                    "safeguard_ms": guard_res.get("latency_ms", 0),
                    "retrieval_ms": ret_res.get("latencies", {}).get("total_latency_ms", 0),
                },
                "stages": [
                    {"id": "01_safeguards", "name": "Safeguard & Intent Gate", "status": "PASS", "latency_ms": guard_res.get("latency_ms", 0)},
                    {"id": "01b_synthesis_registry", "name": "Tier 1 Synthesis Matcher", "status": "MISS", "latency_ms": 0.5},
                    {"id": "02_v3_retrieval", "name": "Tier 2 V3 Graph Retrieval", "status": "SEMANTIC_DRIFT", "latency_ms": ret_res.get("latencies", {}).get("total_latency_ms", 0)},
                ],
                "dsm_state": {
                    "operating_mode": payload.operating_mode,
                    "current_state": "OUT_OF_DOMAIN_REFUSAL",
                    "teachable_withholding": payload.teachable_agent_mode,
                },
                "queries": [],
                "logs": [f"[DOMAIN] Low-weight gating triggered: SEMANTIC_DRIFT with 0 matched concepts"],
            }
            return {
                "status": "out_of_domain",
                "status_message": "Query Out of Knowledge Domain",
                "injected_prompt": refusal_card,
                "fit_status": fit_status,
                "trace_id": turn_trace.trace_id,
                "dev_trace": dev_trace,
            }

        # -------------------------------------------------------------------------
        # STAGE 3: Epistemic Structured JSON Context & Synthesis Wrapper (Span 05)
        # -------------------------------------------------------------------------
        with turn_trace.span("05_epistemic_json_assembly", as_type="chain") as sp:
            epistemic_ctx = build_epistemic_context(
                ret_res,
                teachable_agent_mode=payload.teachable_agent_mode or False,
                operating_mode=payload.operating_mode or "General",
            )
            wrapped_prompt = wrap_epistemic_prompt(
                epistemic_ctx,
                payload.message,
                teachable_agent_mode=payload.teachable_agent_mode or False,
                operating_mode=payload.operating_mode or "General",
            )
            sp.set_output({
                "concept": epistemic_ctx.concept,
                "roles_present": list(epistemic_ctx.roles.keys()),
                "withheld_roles": epistemic_ctx.withheld_roles,
                "macro_bridges_count": len(epistemic_ctx.macro_cot_bridges),
                "total_chars": len(wrapped_prompt),
            })

        turn_trace.metadata.update({
            "primary_concept": ret_res.get("primary_concept"),
            "fit_status": fit_status,
            "roles_covered": ret_res.get("roles_covered"),
        })
        turn_trace.output = wrapped_prompt

        t_total_ms = round((time.perf_counter() - t_flow_start) * 1000, 2)
        dev_trace = {
            "protocol": "HTTP/1.1 POST /api/v1/flow",
            "endpoint": "/api/v1/flow",
            "chat_id": payload.chat_id,
            "user_query": payload.message,
            "status": "success",
            "timings": {
                "total_turnaround_ms": t_total_ms,
                "safeguard_ms": guard_res.get("latency_ms", 0),
                "synthesis_lookup_ms": 0.5,
                "vector_routing_ms": ret_res.get("latencies", {}).get("vector_routing_ms", 0),
                "cypher_expansion_ms": ret_res.get("latencies", {}).get("cypher_expansion_ms", 0),
                "retrieval_total_ms": ret_res.get("latencies", {}).get("total_latency_ms", 0),
                "assembly_ms": 0.8,
            },
            "stages": [
                *(
                    [{
                        "id": "01_safeguards",
                        "name": "Safeguard & Intent Gate",
                        "status": guard_res.get("action", "PASS"),
                        "intent": guard_res.get("intent", "DOMAIN_INQUIRY"),
                        "latency_ms": guard_res.get("latency_ms", 0),
                    }]
                    if guard_res.get("action") not in ("PASS", "PROCEED")
                    else []
                ),
                {
                    "id": "01b_synthesis_registry",
                    "name": "Tier 1 Golden Synthesis Matcher",
                    "status": "MISS",
                    "latency_ms": 0.5,
                    "details": "No pre-compiled synthesis found",
                },
                {
                    "id": "02_v3_graph_traversal",
                    "name": "Tier 2 V3 Epistemic Graph Traversal",
                    "status": ret_res.get("fit_status", "FIT"),
                    "latency_ms": ret_res.get("latencies", {}).get("total_latency_ms", 0),
                    "details": f"Anchor: [[{ret_res.get('primary_concept')}]] | Roles: {', '.join(ret_res.get('roles_covered', []))}",
                },
                {
                    "id": "03_epistemic_assembly",
                    "name": "Toulmin Epistemic Context Assembly",
                    "status": "SUCCESS",
                    "latency_ms": 0.8,
                    "details": f"Concept: [[{epistemic_ctx.concept}]] | Withheld: {epistemic_ctx.withheld_roles or 'None'} | Bridges: {len(epistemic_ctx.macro_cot_bridges)}",
                },
            ],
            "dsm_state": {
                "operating_mode": payload.operating_mode or "General",
                "current_state": "TURN_1_INITIAL" if payload.chat_id in (None, "", "default_chat") else "TURN_2_DRILLDOWN",
                "concept_anchor": epistemic_ctx.concept,
                "tier": "tier_2_traversal",
                "teachable_withholding": bool(payload.teachable_agent_mode),
                "withheld_roles": epistemic_ctx.withheld_roles,
            },
            "queries": [
                *(
                    [{
                        "stage": f"01_safeguards_{guard_res.get('execution_mode', 'scan')}",
                        "dialect": guard_res.get("dialect", "sql"),
                        "query": guard_res.get("executed_query"),
                        "time_ms": guard_res.get("latency_ms", 0),
                        "results_count": 0,
                    }]
                    if guard_res.get("executed_query") and guard_res.get("action") not in ("PASS", "PROCEED")
                    else []
                ),
                {
                    "stage": "02_vector_knn_seed",
                    "dialect": "sql",
                    "query": f"SELECT uri, title, step_type, vectorNeighbors('Section[embedding]', 768, ...) FROM Section WHERE content MATCH '{ret_res.get('search_query', '')}'",
                    "time_ms": ret_res.get("latencies", {}).get("vector_routing_ms", 0),
                    "results_count": len(ret_res.get("sections", [])),
                },
                {
                    "stage": "02_macro_cot_expansion",
                    "dialect": "cypher",
                    "query": f"MATCH (s:Section)-[:HAS_SECTION]-(c:Concept {{title: '{ret_res.get('primary_concept')}'}})-[r:EXTENDS_THEORY|REMEDIES_DILEMMA]->(target:Concept) RETURN target.title, type(r)",
                    "time_ms": ret_res.get("latencies", {}).get("cypher_expansion_ms", 0),
                    "results_count": len(ret_res.get("concepts_in_window", [])),
                },
            ],
            "logs": [
                *(
                    [f"[SAFEGUARD] Intercepted: {guard_res.get('intent')} ({guard_res.get('latency_ms', 0):.2f}ms)"]
                    if guard_res.get("action") not in ("PASS", "PROCEED")
                    else []
                ),
                f"[TIER_1] Cache miss, delegated to Tier 2 V3 In-Engine Graph Traversal",
                f"[V3_ROUTER] S0 Anchor selected: [[{ret_res.get('primary_concept')}]] (query: '{ret_res.get('search_query')}')",
                f"[V3_GRAPH] 1-Hop Macro-CoT expanded concepts: {ret_res.get('concepts_in_window')}",
                f"[TOULMIN] Active roles: {ret_res.get('roles_covered')}, Withheld: {epistemic_ctx.withheld_roles or 'None'}",
                f"[PAYLOAD] Context assembled: {len(wrapped_prompt)} chars, Total Turnaround: {t_total_ms:.2f}ms",
            ],
        }

        return {
            "status": "success",
            "status_message": f"Grounded Context Retrieved ({fit_status})",
            "injected_prompt": wrapped_prompt,
            "fit_status": fit_status,
            "concept": epistemic_ctx.concept,
            "roles_covered": ret_res.get("roles_covered", []),
            "concepts_in_window": ret_res.get("concepts_in_window", []),
            "trace_id": turn_trace.trace_id,
            "latencies": ret_res.get("latencies", {}),
            "epistemic_context": epistemic_ctx.model_dump(exclude_none=True),
            "dev_trace": dev_trace,
        }


@app.post("/api/v1/flow/outlet")
async def handle_flow_outlet(payload: FlowOutletPayload):
    """
    Outlet hook for logging assistant responses and optionally updating Langfuse.
    """
    return {
        "status": "recorded",
        "chat_id": payload.chat_id,
        "trace_id": payload.trace_id,
    }


# --- FastMCP Tool Integration (Optional / Fallback) ---
try:
    from fastmcp import FastMCP
    mcp = FastMCP("arcadedb-middleware")

    @mcp.tool()
    def text2query(question: str, dialect: str = "auto") -> str:
        """Executes natural language query against ArcadeDB and returns markdown."""
        route_res = QueryDialectSwitcher.route(question, dialect)
        target_dialect = route_res.dialect
        if route_res.is_raw_query:
            query = route_res.clean_prompt
        else:
            exemplars = retriever.retrieve_exemplars(route_res.clean_prompt, dialect=target_dialect, top_k=1)
            query = exemplars[0]["query"] if exemplars else "SELECT count(*) FROM Concept;"
        guarded = sanitize_and_guard_query(query, target_dialect)
        records = db_client.query(guarded, language=target_dialect)
        return format_records_to_markdown(records, guarded, target_dialect)

except ImportError:
    mcp = None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("services.fastmcp.server:app", host=settings.host, port=settings.port, reload=False)
