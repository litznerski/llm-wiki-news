"""
services/fastmcp/guardrails/semantic_classifier.py
ArcadeDB-Native Safeguard & Semantic Intent Gating Engine for FastMCP.
Implements Phase 1 of the Consolidated FastMCP Retrieval Flow.

Features:
1. Deterministic Fast-Path Pre-Scan (< 0.2ms):
   - Regex-based assertion for prompt injection, jailbreaks, and syntax exploits.
   - Microsecond lookup for common colloquial chit-chat, greetings, and acknowledgments.
2. In-Engine ArcadeDB IntentAnchor Query (< 2.0ms):
   - Parameterized SQL exact and containment match on IntentAnchor documents.
   - In-engine Lucene full-text search via OpenCypher db.index.fulltext.queryNodes.
3. Zero External Embedding Dependencies:
   - 100% native execution within ArcadeDB (Lucene FULL_TEXT + algo.fastrp).
   - Zero Ollama or external API dependencies.
"""

import re
import time
import logging
from typing import Any, Dict, List, Optional

from ..arcadedb_client import ArcadeDBHttpClient

logger = logging.getLogger("fastmcp-safeguards")


class ArcadeDBSafeguardClassifier:
    """
    ArcadeDB-native safeguard classifier and intent gating engine.
    Short-circuits adversarial intrusions and trivial chit-chat before any LLM tokens are spent.
    """

    # Deterministic greetings (English and German)
    FAST_GREETINGS = {
        "hi", "hello", "hey", "hello there", "good morning", "good afternoon",
        "good evening", "hallo", "guten morgen", "guten tag", "servus", "moin",
        "grüß gott", "hi there", "hey there",
    }

    # Deterministic gratitude / politeness
    FAST_GRATITUDE = {
        "thanks", "thank you", "thank you so much", "thanks a lot", "many thanks",
        "danke", "vielen dank", "danke dir", "perfekt danke", "super danke",
        "appreciate it", "appreciate your explanation",
    }

    # Deterministic farewells
    FAST_FAREWELLS = {
        "bye", "goodbye", "see you", "see you later", "talk to you later",
        "tschüss", "auf wiedersehen", "bis bald", "bis zum nächsten mal",
        "that's all for today", "thats all for today", "i'm done for now",
    }

    # Deterministic assistant identity / capability questions
    FAST_CAPABILITIES = {
        "what can you do", "who are you", "what is Knowledge Lab", "what is knowledge-lab",
        "how do i use this system", "what are your capabilities", "was kannst du",
        "wer bist du", "was ist Knowledge Lab", "help me understand what you can do",
    }

    # Deterministic high-risk injection and jailbreak patterns
    INJECTION_PATTERNS = [
        r"(?i)\bignore\s+(all\s+)?(previous|prior)\s+(instructions|prompts|directives)\b",
        r"(?i)\bdisregard\s+(all\s+)?(system|previous|prior)\s+(instructions|directives|rules)\b",
        r"(?i)\b(system\s+prompt\s+override|override\s+system\s+instructions)\b",
        r"(?i)\b(you\s+are\s+now\s+dan|act\s+as\s+dan|pretend\s+you\s+are\s+dan)\b",
        r"(?i)\b(enable\s+developer\s+mode|unconstrained\s+mode|switch\s+to\s+unconstrained)\b",
        r"(?i)\b(print|output|reveal|leak|repeat)\s+(your\s+)?(system\s+prompt|initialization\s+message|hidden\s+prompt)\b",
        r"(?i)\b(drop\s+table|alter\s+type|truncate\s+table|drop\s+database)\b",
        r"(?i)\b(create\s+(a\s+)?(malware|ransomware|keylogger)|stolen\s+credit\s+card|ddos\s+a\s+website)\b",
    ]

    # Standard callout templates
    DEFAULT_SECURITY_TEMPLATE = (
        "> [!WARNING] Security Policy Violation\n"
        "> Adversarial instruction detected. The request has been blocked to protect system integrity."
    )
    DEFAULT_CONFIG_TEMPLATE = (
        "> [!WARNING] Protected System Configuration\n"
        "> Internal system instructions and configuration parameters are protected and cannot be disclosed."
    )
    DEFAULT_GREETING_TEMPLATE = (
        "Hello! I am Knowledge Lab's knowledge guide. Which concept or problem in AI literacy, "
        "cognitive ergonomics, or educational technology would you like to explore today?"
    )
    DEFAULT_GRATITUDE_TEMPLATE = (
        "You are very welcome! Feel free to ask a follow-up question, explore related concepts "
        "in the graph, or examine counter-evidence."
    )
    DEFAULT_FAREWELL_TEMPLATE = (
        "Goodbye! Your learning trajectory and session state have been saved. See you next time in [[Knowledge Lab]]!"
    )
    DEFAULT_CAPABILITIES_TEMPLATE = (
        "I am the autonomous cognitive assistant for [[Knowledge Lab]]. I provide grounded knowledge "
        "on AI Literacy, Socratic pedagogy, and cognitive ergonomics backed by an ArcadeDB graph. "
        "You can ask conceptual questions, request architecture diagrams, or explore learning progressions."
    )

    def __init__(self, client: Optional[ArcadeDBHttpClient] = None):
        self.client = client or ArcadeDBHttpClient()
        self._compiled_regexes = [re.compile(p) for p in self.INJECTION_PATTERNS]

    def _deterministic_fast_path(self, clean_text: str) -> Optional[Dict[str, Any]]:
        """
        Executes zero-IO regex and set-membership checks (< 0.2ms).
        """
        lower = clean_text.lower().strip()
        # Strip trailing punctuation for greeting/chit-chat comparison
        norm = re.sub(r"[?!.,;:]+$", "", lower).strip()

        # 1. Deterministic Injection Regex Scan
        for rx in self._compiled_regexes:
            if rx.search(lower):
                return {
                    "action": "REJECT_SECURITY",
                    "intent": "prompt_injection",
                    "category": "adversarial",
                    "confidence": 1.0,
                    "template": self.DEFAULT_SECURITY_TEMPLATE,
                    "matched_utterance": rx.pattern,
                    "execution_mode": "deterministic_fast_path",
                }

        # 2. Instant Greetings
        if norm in self.FAST_GREETINGS:
            return {
                "action": "FAST_RESPOND",
                "intent": "chitchat_greeting",
                "category": "conversational",
                "confidence": 1.0,
                "template": self.DEFAULT_GREETING_TEMPLATE,
                "matched_utterance": norm,
                "execution_mode": "deterministic_fast_path",
            }

        # 3. Instant Gratitude
        if norm in self.FAST_GRATITUDE:
            return {
                "action": "FAST_RESPOND",
                "intent": "chitchat_gratitude",
                "category": "conversational",
                "confidence": 1.0,
                "template": self.DEFAULT_GRATITUDE_TEMPLATE,
                "matched_utterance": norm,
                "execution_mode": "deterministic_fast_path",
            }

        # 4. Instant Farewells
        if norm in self.FAST_FAREWELLS:
            return {
                "action": "FAST_RESPOND",
                "intent": "chitchat_farewell",
                "category": "conversational",
                "confidence": 1.0,
                "template": self.DEFAULT_FAREWELL_TEMPLATE,
                "matched_utterance": norm,
                "execution_mode": "deterministic_fast_path",
            }

        # 5. Instant Capabilities
        if norm in self.FAST_CAPABILITIES:
            return {
                "action": "FAST_RESPOND",
                "intent": "meta_capabilities",
                "category": "conversational",
                "confidence": 1.0,
                "template": self.DEFAULT_CAPABILITIES_TEMPLATE,
                "matched_utterance": norm,
                "execution_mode": "deterministic_fast_path",
            }

        return None

    async def evaluate_safeguards(self, user_text: str) -> Dict[str, Any]:
        """
        Asynchronously evaluates user prompt against ArcadeDB IntentAnchors.
        Returns:
            action: 'REJECT_SECURITY' | 'FAST_RESPOND' | 'PROCEED'
            intent: str
            category: str ('adversarial' | 'conversational' | 'policy_violation' | 'domain')
            confidence: float
            template: Optional[str]
            matched_utterance: Optional[str]
            execution_mode: str
            latency_ms: float
        """
        t0 = time.perf_counter()
        clean = (user_text or "").strip()

        if not clean:
            return {
                "action": "PROCEED",
                "intent": "empty_prompt",
                "category": "domain",
                "confidence": 1.0,
                "template": None,
                "matched_utterance": None,
                "execution_mode": "empty_bypass",
                "latency_ms": 0.0,
            }

        # Stage 1A: Deterministic Fast-Path Pre-Scan (< 0.2ms)
        fast_res = self._deterministic_fast_path(clean)
        if fast_res:
            fast_res["latency_ms"] = round((time.perf_counter() - t0) * 1000, 3)
            fast_res["dialect"] = "regex_fast_path"
            fast_res["executed_query"] = (
                f"# Deterministic Fast-Path Pre-Scan (< 0.2ms)\n"
                f"Rule: Microsecond zero-IO regex and dictionary lookup\n"
                f"Matched: '{fast_res.get('matched_utterance')}' (Intent: {fast_res.get('intent')})\n"
                f"Action: {fast_res.get('action')} | Zero database I/O"
            )
            return fast_res

        lower = clean.lower()

        # Stage 1B: ArcadeDB Native In-Engine IntentAnchor Query (< 2.0ms)
        try:
            # 1. Exact match on IntentAnchor.utterance
            exact_sql = """
            SELECT intent, category, action, utterance, response_template
            FROM IntentAnchor
            WHERE utterance.toLowerCase() = :lower
            LIMIT 1;
            """
            records = await self.client.query_async(exact_sql, language="sql", params={"lower": lower})
            if records:
                top = records[0]
                elapsed = (time.perf_counter() - t0) * 1000
                return {
                    "action": top.get("action", "PROCEED"),
                    "intent": top.get("intent", "intent_match"),
                    "category": top.get("category", "conversational"),
                    "confidence": 1.0,
                    "template": top.get("response_template"),
                    "matched_utterance": top.get("utterance"),
                    "execution_mode": "sql_exact",
                    "dialect": "sql",
                    "executed_query": exact_sql.strip().replace(":lower", f"'{lower}'"),
                    "latency_ms": round(elapsed, 3),
                }

            # 2. Utterance containment check in ArcadeDB SQL
            containment_sql = """
            SELECT intent, category, action, utterance, response_template
            FROM IntentAnchor
            WHERE :lower.indexOf(utterance.toLowerCase()) >= 0
            ORDER BY utterance.length() DESC
            LIMIT 5;
            """
            records = await self.client.query_async(containment_sql, language="sql", params={"lower": lower})
            for rec in records:
                utt = rec.get("utterance", "").strip()
                utt_lower = utt.lower()
                # For single-word utterances, require a strict word-boundary match to prevent substring false positives
                # (e.g. 'hi' inside 'architectures', 'this', or 'his')
                if len(utt.split()) == 1:
                    if not re.search(rf"\b{re.escape(utt_lower)}\b", lower):
                        continue

                elapsed = (time.perf_counter() - t0) * 1000
                return {
                    "action": rec.get("action", "PROCEED"),
                    "intent": rec.get("intent", "intent_match"),
                    "category": rec.get("category", "conversational"),
                    "confidence": 0.95,
                    "template": rec.get("response_template"),
                    "matched_utterance": utt,
                    "execution_mode": "sql_containment",
                    "dialect": "sql",
                    "executed_query": containment_sql.strip().replace(":lower", f"'{lower}'"),
                    "latency_ms": round(elapsed, 3),
                }

            # 3. High-relevance Lucene Full-Text Search in ArcadeDB Cypher
            clean_tokens = "".join(c for c in clean if c.isalnum() or c.isspace()).strip()
            if clean_tokens:
                cypher_lucene = """
                CALL db.index.fulltext.queryNodes('IntentAnchor[utterance]', $q)
                YIELD node, score
                WHERE (node.category IN ['adversarial', 'policy_violation'] AND score >= 8.0) OR score >= 12.0
                RETURN node.intent AS intent, node.category AS category, node.action AS action,
                       node.utterance AS utterance, node.response_template AS response_template, score
                ORDER BY score DESC
                LIMIT 1;
                """
                records = await self.client.query_async(cypher_lucene, language="cypher", params={"q": clean_tokens})
                if records:
                    top = records[0]
                    utt_words = set(re.findall(r'\b\w+\b', top.get("utterance", "").lower())) - {
                        "how", "do", "i", "what", "is", "a", "an", "the", "can", "you", "to", "for", "in", "of", "and", "me", "this", "it"
                    }
                    user_words = set(re.findall(r'\b\w+\b', lower))
                    if utt_words and not (utt_words & user_words):
                        # Disregard false positive caused by shared generic question words (e.g. "How do I...")
                        pass
                    else:
                        elapsed = (time.perf_counter() - t0) * 1000
                        return {
                            "action": top.get("action", "PROCEED"),
                            "intent": top.get("intent", "intent_match"),
                            "category": top.get("category", "adversarial"),
                            "confidence": round(float(top.get("score", 1.0)), 2),
                            "template": top.get("response_template"),
                            "matched_utterance": top.get("utterance"),
                            "execution_mode": "cypher_lucene",
                            "dialect": "cypher",
                            "executed_query": cypher_lucene.strip().replace("$q", f"'{clean_tokens}'"),
                            "latency_ms": round(elapsed, 3),
                        }

        except Exception as e:
            logger.warning(f"Safeguard evaluation exception in ArcadeDB: {e}. Falling back to clean pass.")

        # Stage 1C: Clean Pass-Through to Stage 2
        elapsed = (time.perf_counter() - t0) * 1000
        return {
            "action": "PROCEED",
            "intent": "valid_query",
            "category": "domain",
            "confidence": 0.0,
            "template": None,
            "matched_utterance": None,
            "execution_mode": "clean_pass",
            "dialect": "sql",
            "executed_query": f"-- Safeguards Passed: Clean pass through IntentAnchor queries (< 2.0ms) for prompt: '{clean}'",
            "latency_ms": round(elapsed, 3),
        }

    async def evaluate(self, user_text: str) -> Dict[str, Any]:
        """Convenience alias for evaluate_safeguards."""
        return await self.evaluate_safeguards(user_text)

    def evaluate_sync(self, user_text: str) -> Dict[str, Any]:
        """Synchronous wrapper for offline evaluation or test harnesses."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(self.evaluate_safeguards(user_text))
            return loop.run_until_complete(self.evaluate_safeguards(user_text))
        except RuntimeError:
            return asyncio.run(self.evaluate_safeguards(user_text))
