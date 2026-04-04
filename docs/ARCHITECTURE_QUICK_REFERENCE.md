# ScholarFlow Architecture - Visual Quick Reference

## System Layers (Top to Bottom)

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🖥️  FRONTEND (React/TypeScript)                               ┃
┃ WorkspaceStudio + Real-time SSE Streaming                     ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                              ↕
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🌐 API GATEWAY (FastAPI)                                       ┃
┃ /chat, /research, /agents, /projects, /papers, /lab           ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                              ↕
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🧠 ORCHESTRATION (LangGraph)                                  ┃
┃ ├─ Supervisor (Authority)                                     ┃
┃ ├─ Workflow Planner (Strategic Planning) ⭐ NEW              ┃
┃ ├─ Memory (Context)                                           ┃
┃ ├─ Router (Intent Dispatcher)                                 ┃
┃ ├─ Monitor (Stuck Detection)                                  ┃
┃ └─ Message Bus (Agent Communication)                          ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                              ↕
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🛡️  GUARDRAILS LAYER (PRE-PROCESSING)                         ┃
┃ ├─ Continuity Detector (Follow-up vs New)                     ┃
┃ ├─ Topic Queue Manager (2-topic safe handling)                ┃
┃ ├─ Intent Classifier Guardrails (ALLOW/BLOCK/CLARIFY)         ┃
┃ ├─ Deterministic Checks (Regex, keywords, domain)             ┃
┃ ├─ NeMo Guardrails Integration (Advanced safety)              ┃
┃ ├─ LLM Necessity Gate (Deterministic vs Model)                ┃
┃ └─ Interrupt Handler (Pause/Resume with tokens)               ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                              ↕
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🤖 SPECIALIZED AGENTS (Fully Interconnected)                  ┃
┃ ┌─────────────────────────────────────────────────────────┐   ┃
┃ │ DISCOVERY: Search → Ranker → Research Coordinator       │   ┃
┃ │           └─ Synthesis → RAG Response                   │   ┃
┃ ├─────────────────────────────────────────────────────────┤   ┃
┃ │ WRITING: Planner → Planner Review → Writer             │   ┃
┃ │          ├─ Citation (inline)                            │   ┃
┃ │          └─ Reviewer (QA loop)                           │   ┃
┃ ├─────────────────────────────────────────────────────────┤   ┃
┃ │ ANALYSIS: Lab Analyst (experimental data)               │   ┃
┃ ├─────────────────────────────────────────────────────────┤   ┃
┃ │ FEEDBACK: Proactive (suggestions)                       │   ┃
┃ │           Clarifier (ambiguity)                          │   ┃
┃ └─────────────────────────────────────────────────────────┘   ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                              ↕
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 📊 DATA LAYER                                                  ┃
┃ ├─ SQLAlchemy ORM (Projects, Papers, Sessions)                ┃
┃ ├─ Vector Store FAISS (Embeddings & RAG)                      ┃
┃ └─ File Storage (PDFs, Lab Data, Exports)                     ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                              ↕
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🔌 EXTERNAL SERVICES                                           ┃
┃ Claude API, Gemini Vision, ArXiv, PubMed, NeMo, Anam.ai       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

---

## Complete Agent Flow Graph

```
                    CONDITIONAL ENTRY POINT
                             │
        ┌────────────────┬───┴────┬────────────────┐
        ▼                ▼        ▼                ▼
    SUPERVISOR       SEARCH   WRITER            MEMORY
        │               │        │                 │
        └───────────────┴────┬───┴─────────────────┘
                             ▼
                          MEMORY
                             │
                  ┌──────────┴──────────────┐
                  │                         │
              ★ GUARDRAILS LAYER ★
              (All 7 components)
                  │                         │
        YES │ No LLM? │ NO
            │         │
            ▼         ▼
       DETERMINISTIC  ROUTER
        RESPONSE         │
            │      ┌──────┼────────┐
            │      ▼      ▼        ▼
            │   SEARCH  DRAFT   ANALYZE
            │      │      │        │
            │      │      ▼        ▼
            │      │    PLANNER  LAB ANALYST
            │      │      │        │
            │      │      ▼        ▼
            │      │   PLANNER    WRITER
            │      │   REVIEWER   (continues)
            │      │      │
            │      ▼      ▼
            │    RANKER  WRITER ◄────────┐
            │      │      │               │
            │      ▼      ├─► CITATION ──┤
            │   RESEARCH  ├─► SEARCH ────┤
            │   COORDINATOR├─► SYNTHESIS ┤
            │      │      └─► REVIEWER──┤
            │      │         │         │
            │      ▼         ▼ Loop    │
            │   ANALYZING   (REVISE)   │
            │      │                   │
            │      ▼                   │
            │   RAG RESPONSE ──────────┘
            │      │
            └──────┴──────────┬──────────┐
                             ▼          ▼
                        SYNTHESIS   PROACTIVE
                             │          │
                             ▼          ▼
                          (Routes)     GEN
                                     (END)
```

---

## Guardrails Layer - Decision Tree

```
REQUEST
  │
  ├─► CONTINUITY DETECTOR
  │   ├─ FOLLOW_UP_SAME_TOPIC
  │   ├─ FOLLOW_UP_TOPIC_SHIFT
  │   └─ NEW_QUESTION
  │
  ├─► TOPIC QUEUE MANAGER (2-slot)
  │   ├─ active_topic: Current
  │   └─ queued_topic: Paused (with resume_token)
  │
  ├─► INTENT CLASSIFIER
  │   ├─ intent_raw ──► intent_guarded
  │   └─ confidence score
  │
  ├─► DETERMINISTIC CHECKS
  │   ├─ Domain? ✓
  │   ├─ Blacklist? ✓
  │   └─ Constraints? ✓
  │
  ├─► NeMo GUARDRAILS
  │   ├─ Input safety? ✓
  │   ├─ Intent safety? ✓
  │   └─ Policy check? ✓
  │
  ├─► DECISION
  │   ├─ ALLOW ──────► Proceed
  │   ├─ BLOCK ──────► Guardrail response
  │   └─ CLARIFY ────► Ask for clarification
  │
  └─► LLM NECESSITY GATE
      ├─ needs_llm = FALSE ──► Deterministic handler
      └─ needs_llm = TRUE  ──► Route to agents
```

---

## Data Flow - Example Journey

```
USER QUERY (Search for papers)
    │
    │ POST /api/v1/chat
    │ ResearchState initialized
    │
    ▼
SUPERVISOR receives query
    │ Checks context, decides: SEARCH intent
    │
    ▼
MEMORY enriches with conversation history
    │ Adds relevant past context
    │
    ▼
★ GUARDRAILS LAYER processes ★
    │ continuity_type = NEW_QUESTION
    │ intent_guarded = SEARCH ✓ ALLOW
    │ needs_llm = true
    │
    ▼
ROUTER dispatches → SEARCH AGENT
    │ Find 45 papers
    │
    ▼
RANKER ranks papers
    │ Top 5 scores: [0.92, 0.88, 0.84, 0.81, 0.78]
    │
    ▼
RESEARCH COORDINATOR
    │ Decides: "Good papers, proceed"
    │ Routes: → ANALYZING (SSE stream)
    │
    ▼
ANALYZING (streaming "Processing...")
    │
    ▼
RAG RESPONSE generates answer
    │ "Answer text [1][2][3]"
    │
    ▼
PROACTIVE generates suggestions
    │ "Would you like to save papers?"
    │ "Explore related topics?"
    │
    ▼
Logs accumulated: [log1, log2, log3, ...]
    │ Streamed via SSE to frontend
    │
    ▼
Final state returned
    │ Response + papers + suggestions
    │
    ▼
CLIENT renders response ✅
```

---

## Multi-Topic Interrupt Handling

```
USER WRITING (state 1)
├─ active_topic: "quantum-crypto"
├─ current_draft: {intro, content, status}
└─ queued_topic: null

USER INTERRUPTS: "Search for post-quantum standards"
│
│ ★ INTERRUPT HANDLER ★
│ ├─ Detected: New topic + explicit "wait"
│ ├─ Action: Create resume_token
│ ├─ Action: Pause workflow
│ └─ interrupted = true
│
▼ (state 2)
├─ active_topic: "pq-standards" (NEW)
├─ queued_topic: "quantum-crypto" (SAVED, with resume_token)
└─ current_draft: PERSISTED (can resume exactly)

[Search workflow for pq-standards...]

USER: "Go back to writing"
│
│ ★ RESUME LOGIC ★
│ ├─ Detected: Resume request
│ ├─ Action: SWAP topics
│ └─ Resume from resume_token
│
▼ (state 3)
├─ active_topic: "quantum-crypto" (RESTORED!)
├─ queued_topic: "pq-standards" (NOW QUEUED)
├─ current_draft: RESTORED exactly
└─ Workflow continues seamlessly ✓

RESULT: Two topics safely managed, no context loss
```

---

## Component Implementation Status

```
✅ FULLY IMPLEMENTED:

Orchestration Layer:
├─ Supervisor Agent
├─ Workflow Planner Agent ⭐ NEW
├─ Memory Agent
├─ Router Node
├─ Monitor (stuck detection)
└─ Message Bus

Guardrails Layer (All 7):
├─ Continuity Detector
├─ Topic Queue Manager
├─ Intent Classifier + Guardrails
├─ Deterministic Rule Engine
├─ NeMo Integration Service
├─ LLM Necessity Gate
└─ Interrupt Handler + Resume

Discovery Agents:
├─ Search (multi-API)
├─ Ranker
├─ Research Coordinator
├─ Synthesis
└─ RAG Response

Writing Agents:
├─ Planner
├─ Planner Reviewer
├─ Writer
├─ Reviewer
└─ Citation

Support Agents:
├─ Lab Analyst
├─ Proactive
├─ Clarifier
└─ Workflow Monitor

Services:
├─ Guardrails Service
├─ Message Bus
├─ Workflow Monitor
├─ Performance Tracker
├─ Cache Layer
└─ Query Analyzer

External:
├─ Claude API
├─ Gemini Vision
├─ ArXiv/PubMed Search
├─ NeMo Guardrails
└─ Anam.ai Avatar
```

---

## Performance Characteristics

```
OPERATION                    LATENCY          NOTES
──────────────────────────────────────────────────────────────
Fast Path (help, context)    < 50ms          Skips orchestration
Guardrails pre-checks        < 1ms           Deterministic only
NeMo guardrails              < 100ms         With timeout fallback
Search (45 papers)           2-3 seconds     Parallel API calls
Ranking                      500-800ms       Embedding similarity
RAG Response generation      1-2 seconds     LLM call
Draft section (1 paragraph)  3-5 seconds     Writing + formatting
Reviewer feedback            1-2 seconds     LLM call
Complete workflow            5-20 seconds    Depends on path

Total E2E (search → answer):  3-5 seconds
Total E2E (drafting):         10-20 seconds
```

---

## Key Architectural Advantages

| Feature | Benefit |
|---------|---------|
| **Pre-guardrail layer** | Safety before expensive LLM calls |
| **Non-linear interconnection** | Agents discover gaps naturally |
| **2-topic queue** | Multi-task without context loss |
| **Resume tokens** | Interrupts don't lose progress |
| **Fast path handler** | Simple queries answer in 50ms |
| **Message bus** | Agents cooperate intelligently |
| **Monitor + stuck detection** | Automatic recovery suggestions |
| **Real-time SSE streaming** | User sees all progress |
| **Comprehensive state** | Context never lost between turns |
| **Pluggable services** | Easy to add new agents/APIs |

---

**For detailed technical documentation, see:**
- `AGENT_GUARDRAILS_ARCHITECTURE_UPDATE.md` - Design specifications
- `SYSTEM_ARCHITECTURE_DEEP_ANALYSIS.md` - Deep technical analysis
