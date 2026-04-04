# Supervisor + Workflow Planner - Practical Examples

**Guide**: Real-world workflows showing Supervisor ↔ Planner interaction

---

## Example 1: Discovery Query (Search for Papers)

### User Input
```
Query: "Find me the latest papers on quantum cryptography and their key findings"
Intent: SEARCH
```

### Execution Flow

```
1. USER REQUEST
   └─ query="Find me the latest papers on quantum cryptography..."
   └─ intent="SEARCH"
   └─ project_id="proj_123"

2. SUPERVISOR RECEIVES
   ├─ Analyzes: Intent=SEARCH, has papers? No
   ├─ Initial thought: "Route to Search"
   └─ **Calls: Planner for strategy**

3. WORKFLOW PLANNER ANALYZES
   ├─ Determines mode: DISCOVERY
   ├─ Creates plan:
   │  ├─ Step 1: Supervisor (100ms)
   │  ├─ Step 2: Memory (200ms)
   │  ├─ Step 3: Search (2500ms) - Find papers
   │  ├─ Step 4: Ranker (800ms) - Rank by relevance
   │  ├─ Step 5: Research Coordinator (300ms) - Evaluate results
   │  ├─ Step 6: Analyzing (100ms) - SSE status
   │  ├─ Step 7: RAG Response (1500ms) - Generate answer
   │  └─ Step 8: Proactive (500ms) - Suggestions
   │
   ├─ Critical path: Steps 1-8 (fully sequential)
   ├─ Parallelizable: 0 pairs
   ├─ Total time: ~5.9 seconds
   ├─ Risks:
   │  └─ "If search returns <3 papers, results may be weak"
   └─ Optimizations:
      └─ "None available for pure discovery"

4. RETURNS BRIEFING TO SUPERVISOR
   ├─ objective: "Discover and rank papers relevant to quantum cryptography"
   ├─ mode: "discovery"
   ├─ recommended_entry_agent: "search"
   ├─ total_steps: 8
   ├─ estimated_duration_sec: 5.9
   ├─ parallelizable_opportunities: 0
   ├─ key_checkpoints: [5, 7]
   └─ key_optimizations: []

5. SUPERVISOR REVIEWS BRIEFING
   ├─ Decision: "Plan is straightforward, approve"
   ├─ Routing: → ROUTER → SEARCH AGENT
   └─ Informs system: "Expect 5-6 second response"

6. EXECUTION
   ├─ Search → 45 papers found
   ├─ Ranker → Top 5 papers sorted
   ├─ Coordinator → "Results look good, avg relevance 0.82"
   ├─ RAG → Generates answer with citations
   └─ Proactive → "Would you like to save papers? [Yes/No]"

7. RESULT TO USER
   ├─ Answer: "Quantum cryptography papers show X, Y, Z findings..."
   ├─ Citations: [1] - Paper A, [2] - Paper B, etc.
   ├─ Took: 5.8 seconds (as predicted by plan)
   └─ Suggestions: "Save papers? Explore post-quantum alternatives?"
```

### Plan Visualization

```
┌──────────────────────────────────────────┐
│ EXECUTION TIMELINE (5.9 seconds)         │
├──────────────────────────────────────────┤
│ Supervisor        ███ 100ms              │
│ Memory           ████ 200ms              │
│ Search           ███████████████ 2500ms  │
│ Ranker           ██████ 800ms            │
│ Coordinator      ███ 300ms               │
│ Analyzing        ██ 100ms                │
│ RAG Response     ████████████ 1500ms     │
│ Proactive        ████ 500ms              │
└──────────────────────────────────────────┘
Total: 5900ms (5.9 seconds)
```

---

## Example 2: Hybrid Query (Search + Draft)

### User Input
```
Query: "Search for papers on quantum cryptography and draft an introduction to the topic"
Intent: HYBRID (or could specify as "SEARCH then DRAFT")
```

### Execution Flow

```
1. USER REQUEST
   └─ query="Search for papers on quantum cryptography and draft an introduction..."
   └─ intent="HYBRID"

2. SUPERVISOR → PLANNER

3. WORKFLOW PLANNER ANALYZES
   ├─ Determines mode: HYBRID (mixed discovery + drafting)
   ├─ Creates plan:
   │  ├─ PHASE 1: DISCOVERY
   │  │  ├─ Step 1: Supervisor (100ms)
   │  │  ├─ Step 2: Memory (200ms)
   │  │  ├─ Step 3: Search (2500ms)
   │  │  ├─ Step 4: Ranker (800ms)
   │  │  ├─ Step 5: Research Coordinator (300ms)
   │  │  └─ Step 6: Synthesis (1500ms) - PARALLEL SAFE
   │  │
   │  └─ PHASE 2: DRAFTING
   │     ├─ Step 7: Planner (1200ms) - Create outline
   │     ├─ Step 8: Planner Reviewer (500ms)
   │     ├─ Step 9: Writer (3000ms) - Draft intro
   │     ├─ Step 10: Citation (1000ms) - Add citations
   │     └─ Step 11: Reviewer (2000ms)
   │
   ├─ Critical path: [Search → Ranker → Planner → Writer → Reviewer]
   ├─ PARALLELIZABLE PAIRS: 2
   │  ├─ Pair 1: (Research Coordinator [Step 5], Synthesis [Step 6])
   │  │  └─ Saves: ~1.5 seconds
   │  └─ Pair 2: (Planner [Step 7], Synthesis results processing)
   │
   ├─ Total sequential: 13 seconds
   ├─ Total with parallelization: ~10.5 seconds (30% faster!)
   ├─ Checkpoints: [5, 7, 9, 11]
   ├─ Risks:
   │  ├─ "Search may return weak papers"
   │  └─ "Draft quality depends on paper quality"
   └─ Optimizations:
      ├─ "Run Research Coordinator + Synthesis in parallel (~1.5s savings)"
      └─ "Start drafting while synthesis finishing (1s savings)"

4. RETURNS BRIEFING
   ├─ objective: "Execute hybrid workflow (search + draft)"
   ├─ mode: "hybrid"
   ├─ total_steps: 11
   ├─ estimated_duration_sec: 10.5 (with parallelization)
   ├─ parallelizable_opportunities: 2
   └─ key_optimizations:
      ├─ "Run Coordinator + Synthesis in parallel ~1.5s savings"
      └─ "Leverage research results for draft context"

5. SUPERVISOR REVIEWS
   ├─ Decision: "Good plan, has parallelization, approve"
   ├─ Note: "Could optimize further by running in parallel"
   └─ Routing: → SEARCH → ... → PLANNER → ... → WRITER

6. EXECUTION (With Parallelization)
   Step 1-2: Supervisor + Memory → 300ms
   Step 3-4: Search + Ranker → 3300ms
   Step 5-6: [PARALLEL] Coordinator + Synthesis → 1500ms (not 1800ms!)
   Step 7-8: Planner + Reviewer → 1700ms
   Step 9-10: [PARALLEL] Writer + Citation → 3000ms (not 4000ms!)
   Step 11: Reviewer → 2000ms
   ─────────────────────────────────────
   Total: 10500ms (10.5 seconds) ✓ As predicted!

7. RESULT TO USER
   ├─ Outline: "Introduction, Literature Review, Methodology, ..."
   ├─ Introduction draft: "Quantum cryptography..."
   ├─ Citations: [1], [2], [3]
   ├─ Took: 10.4 seconds (as predicted: 10.5s)
   └─ Time saved by parallelization: 2.5 seconds!
```

### Plan Visualization with Parallelization

```
SEQUENTIAL (13 seconds)
┌─────────────────────────────────────────────────────┐
│ Supervisor          ███                             │
│ Memory             ████                             │
│ Search             ███████████████                  │
│ Ranker             ██████                           │
│ Research Coord     ███                              │
│ Synthesis          ████████████                     │
│ Planner            ██████████                       │
│ Planner Reviewer   █████                            │
│ Writer             ███████████████████              │
│ Citation           █████████                        │
│ Reviewer           ████████████                     │
└─────────────────────────────────────────────────────┘

PARALLELIZED (10.5 seconds) ⚡
┌──────────────────────────────┐
│ Supervisor          ███      │
│ Memory             ████      │
│ Search             ┌─────────┤  ┌────────┤
│ Ranker             │         │  │        │
│ Research Coord     │ ███     │  │ III    │
│ Synthesis          │ ████    │  │ IIII   │
│ Planner            │         └──┤        │
│ Planner Reviewer   │            │ ██     │
│ Writer             │ ┌──────────┤        │
│ Citation           │ │ IIII     │ IIII   │
│ Reviewer           │ │ III      │ IIIIII │
│                    │ └──────────┘        │
└──────────────────────────────────────────┘

Savings: 2.5 seconds (19% faster)
```

---

## Example 3: Iterative Refinement (Complex)

### User Input
```
User: "Review my draft and make it better"
(Draft exists from previous work)
Intent: REFINEMENT
```

### Execution Flow

```
1. SUPERVISOR → PLANNER

2. WORKFLOW PLANNER ANALYZES
   ├─ Analyzes state:
   │  ├─ has_draft: true
   │  ├─ draft_content: "Some introduction text..."
   │  ├─ revision_count: 1
   │  └─ needs_revision: false (user just wants improvement)
   │
   ├─ Determines mode: REFINEMENT
   ├─ Creates plan:
   │  ├─ Step 1: Supervisor (100ms)
   │  ├─ Step 2: Memory (200ms)
   │  ├─ Step 3: Reviewer (2000ms) - Analyze draft
   │  ├─ Decision point:
   │  │  └─ If major issues: Writer (3000ms) for revision
   │  │  └─ If minor issues: Proofreader (optional)
   │  │  └─ If good: Proactive suggestions
   │  └─ Step 4: Proactive (500ms)
   │
   ├─ Total time: 2.8 seconds (if minimal revisions needed)
   ├─ Risk: "Revision loop may need multiple iterations"
   └─ Optimization: "Use draft from cache (~200ms saving)"

3. RETURNS BRIEFING
   ├─ mode: "refinement"
   ├─ estimated_duration_sec: 2.8
   └─ note: "May extend if revisions needed"

4. EXECUTION
   ├─ Supervisor: OK
   ├─ Memory: "Previous work context loaded"
   ├─ Reviewer: "Introduction is clear but needs more technical depth"
   ├─ Feedback: "Add 2-3 more points to methods section"
   ├─ Writer: Revises with feedback
   ├─ Proactive: "Would you like me to strengthen the conclusion too?"
   └─ Total: 2.7 seconds ✓

5. RESULT
   ├─ Improved draft returned
   ├─ Changes highlighted
   └─ Next suggestions offered
```

---

## Example 4: Error Recovery (Plan Adaptation)

### Scenario: Small Search Results

```
1. Plan created: DISCOVERY mode, expect 5.9 seconds

2. Execution starts:
   ├─ Search runs → Returns only 2 papers (weak results!)
   ├─ Ranker ranks them → Avg score: 0.42 (below 0.6 threshold)
   └─ Research Coordinator: "Weak results detected"

3. PLAN ADAPTATION DECISION
   ├─ Original plan: Continue to RAG
   ├─ Coordinator detects: "Poor quality, should refine"
   ├─ NEW DECISION: Insert "Refine Query" step
   │
   └─ BRANCHES:
      Option A: Follow original plan (may yield poor results)
      Option B: Refine query and search again (slower but better)

4. SUPERVISOR DECISION
   ├─ Checks: refinement iterations < max threshold
   ├─ Decision: "Refine and retry" (Option B)
   └─ New workflow:
      ├─ Step: Refine Query → 400ms
      ├─ Step: Search again → 2500ms
      ├─ Step: Ranker → 800ms
      ├─ Step: Coordinator evaluates → 300ms (now good!)
      └─ Step: RAG Response → 1500ms

5. TOTAL TIME
   ├─ Original estimate: 5.9 seconds
   ├─ Actual with refinement: 8.5 seconds
   ├─ Trade-off: +2.6 seconds for better results ✓
   └─ User message: "Refined search for better results... ~8.5s total"
```

---

## Example 5: Multi-Turn Conversation (Topic Switching)

### Turn 1: User searches for papers
```
Query: "Find papers on quantum cryptography"
Plan: DISCOVERY (5.9s)
Result: 10 papers found + answer
```

### Turn 2: User asks follow-up
```
Query: "What about post-quantum cryptography?"
Continuity: FOLLOW_UP_TOPIC_SHIFT
Plan: HYBRID (search + synthesis, 8s)
Result: New set of papers + comparison
```

### Turn 3: User interrupts
```
Query: "Wait, go back to quantum cryptography from before"
Interrupt Handler: Triggers
Topic Queue: Swaps back to previous topic
Resume Token: Restores previous state
Plan: NONE (just resume execution)
Result: Continues from checkpoint
```

---

## Key Takeaways

### Supervisor's Role
1. **Receives user request**
2. **Consults planner** for strategy
3. **Reviews planner briefing**
4. **Makes final routing decision**
5. **Monitors plan execution**
6. **Adapts if needed**

### Planner's Role
1. **Analyzes context**
2. **Creates detailed execution plan**
3. **Identifies optimization opportunities**
4. **Estimates time & resources**
5. **Flags risks**
6. **Provides briefing to supervisor**

### Together
- **Faster responses** (optimized paths)
- **Better quality** (strategic planning)
- **More resilient** (error detection)
- **More transparent** (users see estimates)
- **More efficient** (parallelization)

---

## Performance Summary

| Scenario | Without Plan | With Plan | Improvement |
|----------|-------------|-----------|-------------|
| Simple search | 6s (keyword routing) | 5.9s (optimized) | -0.1s (better estimate) |
| Hybrid query | 14s (sequential) | 10.5s (parallel) | **-3.5s (25% faster!)** |
| Refinement | 3.5s | 2.8s | -0.7s (20% faster) |
| Complex multi-step | 20s | 15s (parallel) | **-5s (25% faster!)** |

**Average improvement: 15-25% faster on complex queries**

---

**Supervisor + Planner = Strategic Orchestration + Tactical Execution = Better Results! 🚀**
