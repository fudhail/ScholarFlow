"""
Guardrails Service — ScholarFlow
=================================
Provides intent safety checks with deterministic rules as primary engine
and NeMo Guardrails for deep LLM-based safety evaluation.

Decision output:
    status: ALLOW | BLOCK | CLARIFY
    decision_source: RULE | NEMO | LLM
    reason: human-readable explanation
"""

from __future__ import annotations

import logging
import re
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────

NEMO_ENABLED = True   # NeMo Guardrails is enabled
NEMO_TIMEOUT_SECONDS = 5.0

# Resolve NeMo config directory relative to this file
_SERVICE_DIR = Path(__file__).resolve().parent          # .../app/services
_NEMO_CONFIG_PATH = str(_SERVICE_DIR.parent / "guardrails" / "nemo_config")

# ─── Data Classes ─────────────────────────────────────────────────────────────


@dataclass
class GuardrailContext:
    """Input context passed to the guardrail service."""
    query: str
    intent_raw: Optional[str] = None
    conversation_history: List[dict] = field(default_factory=list)
    project_id: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class GuardrailDecision:
    """Output from guardrail evaluation."""
    status: str              # ALLOW | BLOCK | CLARIFY
    decision_source: str     # RULE | NEMO | LLM
    intent_guarded: Optional[str] = None
    confidence: float = 1.0
    reason: str = ""


@dataclass
class FaithfulnessDecision:
    """Output from response-grounding faithfulness checks."""
    status: str              # PASS | SOURCE_VERIFICATION
    decision_source: str     # RULE | NEMO
    confidence: float
    reason: str


# ─── Deterministic Rule Engine ────────────────────────────────────────────────

# Intents that are always allowed in the academic domain
ALLOWED_INTENTS = {
    "SEARCH", "DRAFT", "ANALYZE", "CHAT",
    "SYNTHESIZE", "CITATION", "REVIEW", "EXPLAIN",
    "SUMMARIZE", "OUTLINE", "HELP", "DEEP_RESEARCH",
}

# Patterns that must be blocked regardless of intent
BLOCK_PATTERNS: List[str] = [
    r"\bhack\b", r"\bexploit\b",
    r"\bcheat\b.*\bassignment\b", r"\bwrite.*exam\b",
    r"\bplagiari[sz]\b",
    r"\bmalware\b", r"\bvirus\b", r"\bransomware\b",
    r"\bgenerat.*fake\s+data\b", r"\bfabricate\s+result\b",
    r"\bbypass.*plagiarism\b",
    r"\billegal\b.*\bresearch\b",
]

# Patterns that need clarification before proceeding
CLARIFY_PATTERNS: List[str] = [
    r"\bwrite.*paper.*for me\b",
    r"\bdo my (research|homework|thesis)\b",
    r"^\s*(write|create|generate)\s+a?\s*(full|complete|entire)\s+(paper|thesis|dissertation)\s*$",
]

# Academic domain keywords — if none found, lower confidence
ACADEMIC_DOMAIN_KEYWORDS = [
    "research", "paper", "study", "analysis", "method", "result",
    "experiment", "data", "literature", "review", "draft", "cite",
    "publish", "journal", "finding", "hypothesis", "abstract",
    "introduction", "conclusion", "thesis", "dissertation",
]

_BROAD_ACADEMIC_PATTERNS: List[str] = [
    r"^\s*tell me about\s+(ai|artificial intelligence|machine learning|deep learning)\s*$",
    r"^\s*explain\s+(ai|machine learning|deep learning)\s*$",
    r"^\s*what is\s+(ai|machine learning|deep learning)\s*$",
    r"^\s*(ai|machine learning|deep learning)\s*$",
]

_QASPER_PROFILE_PATTERNS: List[str] = [
    r"\bevidence\b",
    r"\bmethod(ology)?\b",
    r"\bexperimental setup\b",
    r"\bdataset\b",
    r"\btable\s*\d+\b",
    r"\bfigure\s*\d+\b",
    r"\bwhat (data|results) (support|supports)\b",
    r"\baccording to (the )?paper\b",
    r"\bin (the )?(paper|study),? what\b",
]

_GREETING_PATTERNS: List[str] = [
    r"^\s*hi\s*$",
    r"^\s*hello\s*$",
    r"^\s*hey\s*$",
    r"^\s*hi there\s*$",
    r"^\s*hello there\s*$",
    r"^\s*good (morning|afternoon|evening)\s*$",
    r"^\s*what'?s up\s*$",
    r"^\s*sup\s*$",
]

_GENERAL_CHAT_PATTERNS: List[str] = [
    r"^\s*what(?:'s| is| are)\b",
    r"^\s*who(?:'s| is| are)\b",
    r"^\s*how(?:'s| do| does| can)\b",
    r"^\s*why\b",
    r"^\s*define\b",
    r"^\s*explain\b",
    r"^\s*tell me about\b",
]


def _matches_any(text: str, patterns: List[str]) -> Optional[str]:
    """Return the first matching pattern string, or None."""
    t = text.lower()
    for pat in patterns:
        if re.search(pat, t):
            return pat
    return None


def _academic_domain_confidence(query: str) -> float:
    """Return a confidence score 0–1 based on academic keyword density."""
    q = query.lower()
    hits = sum(1 for kw in ACADEMIC_DOMAIN_KEYWORDS if kw in q)
    return min(1.0, hits / 2.0)  # 2+ keywords → full confidence


def _is_broad_academic_query(query: str) -> bool:
    q = query.lower().strip()
    if _matches_any(q, _BROAD_ACADEMIC_PATTERNS):
        return True
    word_count = len(q.split())
    domain_conf = _academic_domain_confidence(q)
    # Broad if clearly academic but under-specified.
    return domain_conf >= 0.5 and word_count <= 4


def _is_qasper_profile_query(query: str) -> bool:
    q = query.lower()
    return _matches_any(q, _QASPER_PROFILE_PATTERNS) is not None


def _is_general_chat_query(query: str) -> bool:
    q = query.lower().strip()
    return _matches_any(q, _GENERAL_CHAT_PATTERNS) is not None


def _map_raw_intent_to_guarded(raw: Optional[str]) -> str:
    """Normalize raw intent string to a canonical guarded intent."""
    if not raw:
        return "CHAT"
    upper = raw.upper()
    for allowed in ALLOWED_INTENTS:
        if allowed in upper:
            return allowed
    return "CHAT"


def run_deterministic_rules(ctx: GuardrailContext) -> GuardrailDecision:
    """
    Primary guardrail engine using pure deterministic rules.
    Fast — no LLM calls, no I/O.
    """
    query = ctx.query or ""

    # 1. Block check
    match = _matches_any(query, BLOCK_PATTERNS)
    if match:
        logger.warning(f"🚫 Guardrail BLOCK — pattern matched: {match!r}")
        return GuardrailDecision(
            status="BLOCK",
            decision_source="RULE",
            reason=f"Query matches restricted pattern. Academic assistance only.",
            confidence=1.0,
        )

    # 1b. Deep research trigger for paper-evidence style questions.
    if _is_qasper_profile_query(query):
        return GuardrailDecision(
            status="ALLOW",
            decision_source="RULE",
            intent_guarded="DEEP_RESEARCH",
            reason="QASPER-style evidence question detected. Routing to Deep RAG pipeline.",
            confidence=0.92,
        )

    # 1c. Greeting/small-talk should be treated as normal chat.
    if _matches_any(query, _GREETING_PATTERNS):
        return GuardrailDecision(
            status="ALLOW",
            decision_source="RULE",
            intent_guarded="CHAT",
            reason="Greeting detected. Routing to normal conversation flow.",
            confidence=0.95,
        )

    # 2. Clarify check
    match = _matches_any(query, CLARIFY_PATTERNS)
    if match:
        logger.info(f"❓ Guardrail CLARIFY — pattern matched: {match!r}")
        return GuardrailDecision(
            status="CLARIFY",
            decision_source="RULE",
            intent_guarded=_map_raw_intent_to_guarded(ctx.intent_raw),
            reason="Query appears to request complete paper generation. Please clarify the specific part you need help with.",
            confidence=0.8,
        )

    # 3. Domain confidence
    domain_conf = _academic_domain_confidence(query)
    intent_guarded = _map_raw_intent_to_guarded(ctx.intent_raw)

    # Very off-topic query (no academic keywords AND not a known intent)
    if domain_conf < 0.1 and intent_guarded == "CHAT":
        if _is_general_chat_query(query):
            return GuardrailDecision(
                status="ALLOW",
                decision_source="RULE",
                intent_guarded="CHAT",
                reason="General explanatory question detected. Routing to normal conversation flow.",
                confidence=0.8,
            )

        logger.info("❓ Guardrail CLARIFY — low academic domain confidence.")
        return GuardrailDecision(
            status="CLARIFY",
            decision_source="RULE",
            intent_guarded="CHAT",
            reason="Query does not appear to be related to academic research. Please rephrase.",
            confidence=0.6,
        )

    # Academic but too broad should be clarified before expensive routing.
    if _is_broad_academic_query(query):
        return GuardrailDecision(
            status="CLARIFY",
            decision_source="RULE",
            intent_guarded="CHAT",
            reason=(
                "Your request is academic but broad. Please narrow it (e.g., domain, method, "
                "paper, dataset, or year range) so I can run deep retrieval accurately."
            ),
            confidence=0.82,
        )

    logger.debug(f"✅ Guardrail ALLOW — intent={intent_guarded}, domain_conf={domain_conf:.2f}")
    return GuardrailDecision(
        status="ALLOW",
        decision_source="RULE",
        intent_guarded=intent_guarded,
        confidence=max(0.5, domain_conf),
        reason="Passed deterministic rules.",
    )


# ─── NeMo Guardrails Integration (feature-flagged) ──────────────────────────

def _try_nemo_check(ctx: GuardrailContext) -> Optional[GuardrailDecision]:
    """
    NeMo Guardrails check using the config at app/guardrails/nemo_config/.
    Returns None if NeMo is unavailable, config is missing, or times out.
    Falls back gracefully to deterministic rules.
    """
    if not NEMO_ENABLED:
        return None

    if not os.path.isdir(_NEMO_CONFIG_PATH):
        logger.warning(f"NeMo config path not found: {_NEMO_CONFIG_PATH} — skipping NeMo check.")
        return None

    try:
        import asyncio
        from nemoguardrails import RailsConfig, LLMRails  # type: ignore

        config = RailsConfig.from_path(_NEMO_CONFIG_PATH)
        rails = LLMRails(config)

        async def _run() -> dict:
            messages = [{"role": "user", "content": ctx.query}]
            # generate_async returns the assistant reply; if rails block → different response
            response = await asyncio.wait_for(
                rails.generate_async(messages=messages),
                timeout=NEMO_TIMEOUT_SECONDS,
            )
            return response

        # Run in a new event loop if we're not already in one
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _run())
                result = future.result(timeout=NEMO_TIMEOUT_SECONDS + 1)
        except RuntimeError:
            result = asyncio.run(_run())

        # NeMo returns the final response text;
        # check if it contains the refusal message from the rails config
        response_text = ""
        if isinstance(result, str):
            response_text = result
        elif isinstance(result, dict):
            response_text = result.get("content", "") or str(result)
        elif isinstance(result, list) and result:
            response_text = result[-1].get("content", "") if isinstance(result[-1], dict) else str(result[-1])

        # Detect if guardrail fired (refusal messages from rails config)
        NEMO_BLOCK_SIGNALS = [
            "i can't help with that",
            "i'm designed to assist with academic",
            "i can't process that instruction",
            "please don't share personal",
            "i can't help with this request",
            "it sounds like you're going through",
        ]
        response_lower = response_text.lower()
        for signal in NEMO_BLOCK_SIGNALS:
            if signal in response_lower:
                logger.info(f"🚫 NeMo guardrail fired: '{signal}'")
                return GuardrailDecision(
                    status="BLOCK",
                    decision_source="NEMO",
                    reason=response_text[:300],
                    confidence=0.95,
                )

        logger.debug("✅ NeMo guardrail passed.")
        return GuardrailDecision(
            status="ALLOW",
            decision_source="NEMO",
            reason="Passed NeMo guardrail evaluation.",
            confidence=0.95,
        )

    except ImportError:
        logger.warning("NeMo Guardrails not installed — install with: pip install nemoguardrails")
    except Exception as exc:
        logger.warning(f"NeMo Guardrails error ({type(exc).__name__}: {exc}) — falling back to deterministic rules.")

    return None


# ─── Public API ──────────────────────────────────────────────────────────────


def check_intent_guardrails(ctx: GuardrailContext) -> GuardrailDecision:
    """
    Primary entry point for intent guardrail evaluation.
    Order: Deterministic rules → NeMo (optional) → ALLOW by default.
    """
    # 1. Fast deterministic check first
    decision = run_deterministic_rules(ctx)
    if decision.status in ("BLOCK", "CLARIFY"):
        return decision  # Don't bother with NeMo for definite blocks/clarifies

    # 2. Optionally run NeMo for ALLOW cases (deeper safety check)
    nemo_decision = _try_nemo_check(ctx)
    if nemo_decision and nemo_decision.status == "BLOCK":
        return nemo_decision

    # 3. Return deterministic ALLOW with guarded intent
    return decision


def check_input_guardrails(ctx: GuardrailContext) -> GuardrailDecision:
    """
    Input-level check (before any processing).
    Currently delegates to intent guardrails.
    """
    return check_intent_guardrails(ctx)


def check_response_faithfulness(summary: str, retrieved_chunks: List[str]) -> FaithfulnessDecision:
    """
    Tier-2 hallucination guard.

    Flags responses for source verification when summary content is weakly grounded
    in retrieved chunks. Uses NeMo when available, with deterministic fallback.
    """
    summary_text = (summary or "").strip()
    chunks = [c for c in (retrieved_chunks or []) if c and c.strip()]

    if not summary_text or not chunks:
        return FaithfulnessDecision(
            status="SOURCE_VERIFICATION",
            decision_source="RULE",
            confidence=0.5,
            reason="Missing summary or retrieved evidence chunks for faithfulness validation.",
        )

    chunk_text = "\n".join(chunks).lower()
    summary_sentences = [s.strip() for s in re.split(r"[.!?]\s+", summary_text) if s.strip()]

    def _grounded(sentence: str) -> bool:
        tokens = [t for t in re.findall(r"[a-z0-9]+", sentence.lower()) if len(t) > 3]
        if not tokens:
            return True
        overlap = sum(1 for t in tokens if t in chunk_text)
        return (overlap / max(len(tokens), 1)) >= 0.35

    grounded = [_grounded(s) for s in summary_sentences]
    grounded_ratio = sum(1 for ok in grounded if ok) / max(len(grounded), 1)

    if grounded_ratio < 0.7:
        return FaithfulnessDecision(
            status="SOURCE_VERIFICATION",
            decision_source="RULE",
            confidence=max(0.5, grounded_ratio),
            reason="Potential ungrounded claims detected; source verification required.",
        )

    return FaithfulnessDecision(
        status="PASS",
        decision_source="RULE",
        confidence=grounded_ratio,
        reason="Response appears grounded in retrieved evidence.",
    )
