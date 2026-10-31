"""
services/fastmcp/retrieval package initialization.
"""

from .v3_engine import ConsolidatedV3Retriever, get_effective_toulmin_role, extract_concept_title_from_uri
from .context_builder import (
    EpistemicSection,
    MacroCoTBridge,
    EpistemicContextPayload,
    build_epistemic_context,
    wrap_epistemic_prompt,
    format_out_of_domain_refusal,
)

__all__ = [
    "ConsolidatedV3Retriever",
    "get_effective_toulmin_role",
    "extract_concept_title_from_uri",
    "EpistemicSection",
    "MacroCoTBridge",
    "EpistemicContextPayload",
    "build_epistemic_context",
    "wrap_epistemic_prompt",
    "format_out_of_domain_refusal",
]
