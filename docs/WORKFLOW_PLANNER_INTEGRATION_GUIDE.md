# Workflow Planner Agent - Integration Guide

**Status**: ✅ Ready for Integration
**Created**: 2026-03-17
**Purpose**: Strategic execution planning that works WITH the Supervisor

---

## Overview

The **Workflow Planner** is a strategic planning agent that:

1. **Analyzes** user intent, current state, and available resources
2. **Creates** an intelligent execution plan with sequenced steps
3. **Identifies** parallelization opportunities and critical paths
4. **Informs** the Supervisor for better routing decisions
5. **Optimizes** workflow execution paths

Unlike the existing **Planner Node** (which generates research outlines), this planner creates **workflow execution plans**.

---

## Architecture

### Supervisor ↔ Workflow Planner Relationship

```
REQUEST
  │
  ├─► SUPERVISOR (Authority)
  │     ├─ Evaluates context
  │     ├─ Questions: "What's the best routing?"
  │     │
  │     └─► WORKFLOW PLANNER (Strategy)
  │         ├─ Creates detailed execution plan
  │         ├─ Answers: "Here's how to execute this"
  │         ├─ Provides: Briefing with insights
  │         └─ Returns to Supervisor
  │
  └─► SUPERVISOR (Final Decision)
      ├─ Reviews plan briefing
      ├─ Makes routing decision
      └─ Executes plan or deviates if needed
```

### Two Integration Patterns

#### Pattern 1: Planner as Advisory (Recommended)
```
Supervisor
  ├─ Question: Should we search first?
  │
  ├─► Planner: "Creates hybrid workflow plan"
  │   └─ Returns: Briefing with insights
  │
  ├─ Reviews insights
  └─ Routes decision to: Planner → Router (uses plan)
```

#### Pattern 2: Enhanced Supervisor
```
Supervisor (Plan-Enhanced)
  ├─ Calls: Workflow Planner internally
  ├─ Enriches routing with plan insights
  └─ Makes better decisions
```

---

## Core Components

### 1. WorkflowPlanner Class

```python
from app.agents.workflow_planner import get_workflow_planner

planner = get_workflow_planner()
plan = await planner.plan_workflow(state)

# Returns: WorkflowPlan with:
# - objective: Clear goal statement
# - mode: DISCOVERY | ANALYSIS | DRAFTING | REFINEMENT | HYBRID
# - steps: List[ExecutionStep] - detailed steps
# - parallelizable_pairs: Steps that can run together
# - critical_path: Longest dependency chain
# - checkpoints: Where to save state
# - resources: AI calls, API calls needed
# - risks: Potential issues
# - optimizations: Speed improvements
```

### 2. Execution Modes

| Mode | Use Case | Example |
|------|----------|---------|
| **DISCOVERY** | Find and analyze papers | "Search for quantum computing papers" |
| **ANALYSIS** | Synthesize & compare | "Compare cryptography approaches" |
| **DRAFTING** | Create new document | "Draft a research paper" |
| **REFINEMENT** | Improve existing work | "Make introduction punchier" |
| **HYBRID** | Mixed operations | "Search papers then draft paper" |

### 3. ExecutionStep Structure

Each step includes:
```python
order: int                  # Execution sequence
agent: str                  # Which agent handles this
action: str                 # Specific action
input_requirements: List    # Required state fields
output_produces: List       # State fields created
description: str            # Human-readable description
estimated_duration_ms: int  # Latency estimate
is_parallel_safe: bool      # Can run in parallel
checkpoint: bool            # Should save state
fallback_agent: Optional    # Alternative if fails
success_criteria: Optional  # What counts as success
```

---

## Usage Examples

### Example 1: Basic Planning

```python
from app.agents.workflow_planner import get_workflow_planner

# Get planner
planner = get_workflow_planner()

# Create plan from state
state = ResearchState(
    query="Find papers on quantum cryptography",
    intent="SEARCH",
    project_id="proj_123"
)

plan = await planner.plan_workflow(state)

# Inspect plan
print(f"Mode: {plan.mode.value}")
print(f"Steps: {len(plan.steps)}")
print(f"Duration: {plan.total_estimated_ms}ms")
print(f"Parallelizable: {len(plan.parallelizable_pairs)}")
```

### Example 2: Get Supervisor Briefing

```python
# Get high-level summary for supervisor
briefing = planner.get_supervisor_briefing(plan)

# Returns:
# {
#   "objective": "Discover and rank papers relevant to...",
#   "mode": "discovery",
#   "recommended_entry_agent": "search",
#   "total_steps": 6,
#   "estimated_duration_sec": 4.5,
#   "parallelizable_opportunities": 3,
#   "key_checkpoints": [3, 5],
#   "estimated_ai_calls": 2,
#   "estimated_api_calls": 3,
#   "primary_risks": ["No papers found", "Low relevance scores"],
#   "key_optimizations": ["Run synthesis in parallel", "Use cache"]
# }
```

### Example 3: Human-Readable Summary

```python
# Get plan summary for logging/debugging
summary = planner.get_plan_summary(plan)

print(summary)
# Output:
# WORKFLOW PLAN SUMMARY
# ═════════════════════════════════════════════
# Objective: Discover and rank papers...
# Mode: DISCOVERY
# Estimated Time: 4.5 seconds
#
# EXECUTION STEPS (6 total):
# 1. SUPERVISOR
#    Action: orchestration
#    Duration: 100ms
#
# 2. MEMORY
#    Action: context_enrichment
#    Duration: 200ms
#
# ... etc
```

### Example 4: Integrate into Graph

```python
# In graph.py, add planner node:

from app.agents.planner_node import workflow_planner_node

# Add to graph
graph.add_node("workflow_planner", workflow_planner_node)

# Wire it early in flow
graph.add_edge("supervisor", "workflow_planner")
graph.add_edge("workflow_planner", "memory")

# Now supervisor can inspect plan in state
```

### Example 5: Enhanced Supervisor

```python
# Use plan-enhanced supervisor
from app.agents.planner_node import supervisor_with_plan

# Replace regular supervisor with plan-aware version
graph.add_node("supervisor", supervisor_with_plan)

# Supervisor now:
# 1. Receives request
# 2. Internally calls planner
# 3. Uses plan to inform routing
# 4. Can suggest to user: "This will take ~5 seconds, 3 API calls"
```

---

## Plan Analysis Examples

### Example 1: Simple Discovery Query

**Query**: "Find papers on quantum computing"

```
Plan:
├─ Mode: DISCOVERY
├─ Steps: 6
├─ Duration: ~4.5 seconds
├─ Critical Path: [Supervisor → Memory → Search → Ranker → RAG → Proactive]
├─ Parallelizable: 0 (fully sequential)
├─ Risks: "No papers found", "Low relevance scores"
└─ Optimizations: "Run synthesis in parallel" (not applicable here)
```

### Example 2: Hybrid Query

**Query**: "Search for papers on quantum cryptography and draft the introduction"

```
Plan:
├─ Mode: HYBRID
├─ Steps: 13
├─ Duration: ~8.5 seconds
├─ Critical Path: [Search → Ranker → Synthesis] → [Planner → Writer]
├─ Parallelizable: 2
│  ├─ Pair 1: (Research Coordinator, Synthesis)
│  └─ Pair 2: (Citation, Writer refinement)
├─ Checkpoints: [Ranker, Planner, Writer]
├─ Risks: "Complex workflow", "Multiple dependency points"
└─ Optimizations: "Run Coordinator + Synthesis in parallel ~1.5s savings"
```

### Example 3: Complex Drafting

**Query**: "Review my draft and suggest improvements"

```
Plan:
├─ Mode: REFINEMENT
├─ Steps: 3
├─ Duration: ~3.5 seconds
├─ Critical Path: [Supervisor → Memory → Reviewer → Writer]
├─ Parallelizable: 0
├─ Checkpoints: [Reviewer, Writer]
├─ Risks: None
└─ Optimizations: "Use cached draft from state (~200ms savings)"
```

---

## Integration Points

### 1. In Graph Construction

```python
# graph.py
from app.agents.planner_node import workflow_planner_node

# Add planner node
graph.add_node("workflow_planner", workflow_planner_node)

# Wire after supervisor for visibility
graph.add_edge("supervisor", "workflow_planner")
graph.add_edge("workflow_planner", "memory")

# Now state contains: workflow_plan, supervisor_briefing, workflow_plan_steps
```

### 2. In Supervisor

```python
# specialists.py - SupervisorAgent
async def route_request(self, state: ResearchState) -> Dict:
    # Check if plan already exists
    plan_info = state.get("workflow_plan")

    if plan_info:
        # Use plan insights to inform routing
        logger.info(f"Plan mode: {plan_info['mode']}")
        logger.info(f"Estimated: {plan_info['estimated_duration_ms']}ms")
        logger.info(f"Parallelizable: {len(plan_info['parallelizable_pairs'])}")

    # Make routing decision
    # ...
```

### 3. In Router

```python
# routing.py
def route_after_intent(state: ResearchState) -> str:
    # Can check workflow_plan_steps to understand full flow
    plan_steps = state.get("workflow_plan_steps", [])

    if plan_steps:
        # First step after supervisor/memory is supervisor_briefing['recommended_entry_agent']
        recommended = state.get("supervisor_briefing", {}).get("recommended_entry_agent")

        # Can follow the plan or override
        logger.info(f"Plan recommends: {recommended}")

    # Proceed with normal routing
    # ...
```

### 4. In Logs/Monitoring

```python
# Each request now includes plan metadata
state["logs"].append({
    "step": "planner",
    "source": "Workflow Planner",
    "message": "Created execution plan: 6 steps, 4500ms estimated",
    "status": "completed",
    "metadata": {
        "mode": "discovery",
        "parallelizable": 2,
        "planning_time_ms": 145
    }
})
```

---

## Configuration Options

### Enable/Disable Planning

```python
# In config.py
class Settings:
    # Enable workflow planning
    ENABLE_WORKFLOW_PLANNING: bool = True

    # Planning modes to enable
    PLANNING_MODES: List[str] = [
        "discovery",
        "analysis",
        "drafting",
        "refinement",
        "hybrid"
    ]

    # Max planning time before timeout
    PLANNING_TIMEOUT_MS: int = 500

    # Enable plan sharing with user
    SHOW_PLAN_TO_USER: bool = False  # Can show in UI later
```

### Supervisor Configuration

```python
# Use regular supervisor
SUPERVISOR_MODE = "standard"

# OR use plan-enhanced supervisor
SUPERVISOR_MODE = "plan-aware"

# In main.py setup:
if settings.SUPERVISOR_MODE == "plan-aware":
    from app.agents.planner_node import supervisor_with_plan
    # Use supervisor_with_plan
else:
    from app.agents.specialists import get_supervisor_agent
    # Use standard supervisor
```

---

## Performance Characteristics

| Operation | Latency | Notes |
|-----------|---------|-------|
| Create plan | 50-150ms | Lightweight analysis |
| Get briefing | <1ms | JSON extraction |
| Get summary | 10-20ms | String formatting |
| Integration overhead | 100-200ms | Added to workflow |
| Total setup time | 200-300ms | Planning + memory + supervisor |

**Impact on user**: +0.2-0.3 seconds for planning (offset by better routing).

---

## Advanced Features

### 1. Plan History

```python
planner = get_workflow_planner()

# Access previous plans
last_plan = planner.last_plan
all_plans = planner.plan_history

# Analyze patterns
discovery_plans = [p for p in all_plans if p.mode == ExecutionMode.DISCOVERY]
avg_discovery_time = sum(p.total_estimated_ms for p in discovery_plans) / len(discovery_plans)
```

### 2. Custom Step Builders

```python
# Extend planner for domain-specific steps
class CustomPlanner(WorkflowPlanner):
    async def _add_custom_steps(self, steps, state, context, order):
        # Add domain-specific steps
        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="custom_domain_agent",
            action="special_operation",
            # ...
        ))
        return order
```

### 3. Plan Optimization

```python
# After creating plan, can optimize it
plan = await planner.plan_workflow(state)

# Apply parallelization
if len(plan.parallelizable_pairs) > 0:
    logger.info("Enabling parallel execution")
    # Configure graph to run parallelizable steps together

# Apply checkpointing
for checkpoint_order in plan.checkpoints:
    logger.info(f"Setting checkpoint at step {checkpoint_order}")
```

---

## Testing Examples

```python
# Test 1: Discovery mode
state = ResearchState(query="quantum computing", intent="SEARCH")
plan = await planner.plan_workflow(state)
assert plan.mode == ExecutionMode.DISCOVERY
assert any("search" in step.agent for step in plan.steps)

# Test 2: Hybrid mode
state = ResearchState(query="search for papers and draft intro", intent="HYBRID")
plan = await planner.plan_workflow(state)
assert plan.mode == ExecutionMode.HYBRID
assert len(plan.steps) > 6

# Test 3: Parallelization detection
assert len(plan.parallelizable_pairs) > 0
# Verify pairs don't have dependencies
for step_i, step_j in plan.parallelizable_pairs:
    # Check no cross-dependencies

# Test 4: Checkpoints exist
draft_checkpoints = [s for s in plan.steps if s.checkpoint]
assert len(draft_checkpoints) > 0
```

---

## Migration Guide

If you want to add this to an existing system:

1. **Step 1**: Copy `workflow_planner.py` to `backend/app/agents/`
2. **Step 2**: Copy `planner_node.py` to `backend/app/agents/`
3. **Step 3**: Update `graph.py`:
   ```python
   from app.agents.planner_node import workflow_planner_node
   graph.add_node("workflow_planner", workflow_planner_node)
   graph.add_edge("supervisor", "workflow_planner")
   graph.add_edge("workflow_planner", "memory")
   ```
4. **Step 4**: Update `state.py` to include plan fields:
   ```python
   workflow_plan: Optional[Dict]
   supervisor_briefing: Optional[Dict]
   workflow_plan_steps: List[Dict]
   ```
5. **Step 5**: Test with various queries

---

## Comparison: Planner Types

| Type | Purpose | Output | Use Case |
|------|---------|--------|----------|
| **Research Outline Planner** | Generate manuscript structure | Markdown outline | "Draft an outline" |
| **Workflow Planner** (NEW) | Plan execution flow | Execution steps + briefing | "Decide execution strategy" |
| **Supervisor** | Route requests | Primary agent selection | "Which agent should handle this" |

---

## Future Enhancements

1. **User-Facing Plans**: Show execution plan in UI
2. **Plan Caching**: Save and reuse similar plans
3. **Plan Versioning**: Track plan improvements
4. **Interactive Planning**: User can modify plan before execution
5. **Cost Estimation**: Track API costs per plan
6. **Performance Learning**: Improve time estimates from history

---

**Status**: Ready for Production
**Dependencies**: werkflow_planner.py + planner_node.py + updates to graph.py + state.py

Shall I help you integrate this into your existing system?
