# ScholarFlow — Guardrails & Planning Agent Architecture

> **Implemented:** 2026-03-31  
> **Phase coverage:** All 5 phases from `AGENT_GUARDRAILS_ARCHITECTURE_UPDATE.md`

---

## Overview

This document describes the full implementation of the agentic guardrail pipeline, continuity detection, topic queueing, interrupt handling, and planner reviewer loop for ScholarFlow.

---

## Architecture Flow

```
User Query
    │
    ▼
interrupt_handler          ← Detects: "stop", "wait", "cancel", etc.
    │ (if interrupted → END/paused)
    ▼
continuity_detector        ← Classifies: FOLLOW_UP_SAME_TOPIC | FOLLOW_UP_TOPIC_SHIFT | NEW_QUESTION
    ▼
topic_queue_manager        ← Manages 2 topic slots: active_topic + queued_topic
    ▼
intent_classifier_fast     ← Keyword-based: SEARCH | DRAFT | ANALYZE | SYNTHESIZE | CITATION | HELP | CHAT
    ▼
intent_guardrail_node      ← Safety check: ALLOW | BLOCK | CLARIFY
    │ BLOCK → guardrail_response → END
    │ CLARIFY → clarifier → END (waits for user)
    │ ALLOW ↓
    ▼
supervisor → memory
    ▼
llm_necessity_gate         ← Decides: needs LLM or deterministic?
    │ No LLM → deterministic_handler → END
    │ LLM needed ↓
    ▼
router → planner (if drafting) / search / synthesis / etc.
    ▼
planner_reviewer_node      ← Reviews plan: APPROVED | REVISE (max 3 iterations)
    │ REVISE → planner (loop)
    │ APPROVED ↓
    ▼
writer / search / synthesis / ...
```

---

## New Components

### Phase 1 — State Extensions (`state.py`)

New fields added to `ResearchState`:

| Field | Type | Description |
|---|---|---|
| `continuity_type` | str | FOLLOW_UP_SAME_TOPIC \| FOLLOW_UP_TOPIC_SHIFT \| NEW_QUESTION |
| `continuity_confidence` | float | 0.0–1.0 |
| `active_topic_id` / `active_topic_label` | str | Current topic slot |
| `queued_topic_id` / `queued_topic_label` | str | Paused topic slot |
| `resume_token` | str | UUID to identify paused state |
| `intent_raw` | str | Pre-guardrail intent |
| `intent_guarded` | str | Post-guardrail normalized intent |
| `intent_guardrail_status` | str | ALLOW \| BLOCK \| CLARIFY |
| `decision_source` | str | RULE \| NEMO \| LLM |
| `needs_llm` | bool | False = deterministic path |
| `planner_review_status` | str | APPROVED \| REVISE |
| `planner_review_iterations` | int | Guard against infinite loops |
| `interrupted` | bool | Whether user interrupted the session |
| `interrupt_saved_state` | dict | Snapshot for resume |

---

### Phase 2 — Continuity & Queue Nodes (`nodes.py`)

#### `continuity_detector`
- Fast rule-based signals (keyword detection) with LLM fallback for ambiguous cases
- Outputs: `continuity_type`, `continuity_confidence`

#### `topic_queue_manager`
- Maintains max 2 topic slots
- On `NEW_QUESTION`: moves active → queued, sets new active
- On `FOLLOW_UP_SAME_TOPIC`: no change
- On `FOLLOW_UP_TOPIC_SHIFT`: updates active label

#### `interrupt_handler`
- Detects: "stop", "wait", "pause", "cancel", "forget it", "nevermind", etc.
- Saves lightweight state snapshot and generates a `resume_token`
- Sets `workflow_state = "paused"` and `interrupted = True`

---

### Phase 3 — Guardrail Pipeline (`nodes.py` + `guardrails_service.py`)

#### `guardrails_service.py`
Full-featured guardrail engine with:
- **Deterministic rules** — regex pattern matching for blocked/clarify cases
- **Academic domain confidence** — keyword density scoring
- **NeMo Guardrails** — feature-flagged (`NEMO_ENABLED = False` by default). Enable by setting `NEMO_ENABLED = True` and installing `nemoguardrails`.
- **Graceful timeout fallback** — if NeMo times out, falls back to deterministic result

#### `intent_classifier_fast`
- Keyword-map classification across 6 intents (SEARCH, DRAFT, ANALYZE, SYNTHESIZE, CITATION, HELP)
- No LLM call needed for clearly identifiable intents
- Outputs: `intent_raw`, `intent_confidence`

#### `intent_guardrail_node`
- Calls `guardrails_service.check_intent_guardrails()`
- Routes to: ALLOW → `supervisor`, CLARIFY → `clarifier`, BLOCK → `guardrail_response`
- Block response is stored in `current_draft` for immediate frontend display

#### `llm_necessity_gate`
- Deterministic intents and query patterns bypass LLM entirely
- Examples: `"help"`, `"what is your name"`, `"queue status"`, `"resume"`
- Outputs: `needs_llm`, `llm_gate_reason`

#### `deterministic_handler`
- Returns instant responses for help, queue status, and resume commands
- No model invocation — pure Python string responses

---

### Phase 4 — Planner Reviewer Loop (`nodes.py`)

#### `planner_reviewer_node`
Validates planner JSON output for:
- Missing `goal`, `steps`, `required_tools`, `success_criteria`
- Too many steps (>20)
- Duplicate step labels (circular loop detection)

Output: `APPROVED` (proceed) or `REVISE` (loop back to planner, max 3 times).

---

### Phase 5 — Graph Wiring (`graph.py`, `routing.py`)

New edges in LangGraph:

```python
interrupt_handler → [END | continuity_detector]
continuity_detector → topic_queue_manager
topic_queue_manager → intent_classifier_fast
intent_classifier_fast → intent_guardrail
intent_guardrail → [supervisor | clarifier | guardrail_response]
guardrail_response → END
supervisor → memory → llm_necessity_gate
llm_necessity_gate → [router | deterministic_handler]
deterministic_handler → END
planner → planner_reviewer
planner_reviewer → [planner | writer | search | synthesis]
```

New routing functions in `routing.py`:
- `route_after_interrupt` — END if interrupted, else continue
- `route_after_guardrail` — BLOCK/CLARIFY/ALLOW routing
- `route_after_llm_gate` — deterministic vs LLM path
- `route_after_planner_reviewer` — REVISE/APPROVED routing

---

## NeMo Guardrails Setup (Optional)

To enable NeMo Guardrails:

1. Install: `pip install nemoguardrails`
2. Create config: `backend/app/guardrails/nemo_config/` (follow NeMo docs)
3. Set `NEMO_ENABLED = True` in `guardrails_service.py`

The system will automatically use NeMo for ALLOW cases (deeper safety check) while keeping deterministic rules for BLOCK/CLARIFY fast-path decisions.

---

## Acceptance Criteria Status

| Criteria | Status |
|---|---|
| Follow-up detector classifies 3 continuity types | ✅ Implemented |
| Two-topic queue: switch/resume/replace | ✅ Implemented |
| Guardrail node: ALLOW/BLOCK/CLARIFY | ✅ Implemented |
| `needs_llm=false` path avoids model invocation | ✅ Implemented |
| Planner reviewer catches malformed plans | ✅ Implemented (max 3 iterations) |
| Interrupt preserves resumable state | ✅ Implemented (snapshot + resume_token) |
| `supervisor → memory → router` flow preserved | ✅ Preserved (guardrail wraps, not replaces) |
| Existing specialist routing unchanged | ✅ Preserved |
