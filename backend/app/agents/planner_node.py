"""
Workflow Planner Node - Integrates into LangGraph
This node implements the planning capability within the graph workflow
"""

import logging
from app.agents.state import ResearchState
from app.agents.workflow_planner import get_workflow_planner, ExecutionMode
import time

logger = logging.getLogger(__name__)


async def workflow_planner_node(state: ResearchState) -> dict:
    """
    Workflow Planner node - Strategic planning before execution

    This node runs early in the workflow to create an intelligent execution plan.
    The plan helps the supervisor make better routing decisions.

    Flow:
        Supervisor → Planner (this node) → Router (uses plan insights)

    Args:
        state: Current ResearchState

    Returns:
        Updated state with plan information
    """

    start_time = time.time()
    logger.info("📋 Workflow Planner: Creating execution plan...")

    planner = get_workflow_planner()

    # Create the plan
    plan = await planner.plan_workflow(state, verbose=False)

    # Extract key insights from plan
    briefing = planner.get_supervisor_briefing(plan)

    # Log the plan summary
    summary = planner.get_plan_summary(plan)
    logger.info(f"Plan created:\n{summary}")

    # Calculate execution time
    execution_time = time.time() - start_time

    # Return state updates
    return {
        "workflow_plan": {
            "objective": plan.objective,
            "mode": plan.mode.value,
            "steps_count": len(plan.steps),
            "estimated_duration_ms": plan.total_estimated_ms,
            "parallelizable_pairs": plan.parallelizable_pairs,
            "critical_path_length": len(plan.critical_path),
            "checkpoints": plan.checkpoints,
            "resource_requirements": plan.resource_requirements,
        },
        "supervisor_briefing": briefing,
        "workflow_plan_steps": [
            {
                "order": step.order,
                "agent": step.agent,
                "action": step.action,
                "duration_ms": step.estimated_duration_ms,
                "is_parallel_safe": step.is_parallel_safe,
                "success_criteria": step.success_criteria,
            }
            for step in plan.steps
        ],
        "logs": [{
            "step": "planner",
            "source": "Workflow Planner",
            "message": f"📋 Created execution plan: {len(plan.steps)} steps, {plan.total_estimated_ms}ms estimated",
            "status": "completed",
            "metadata": {
                "mode": plan.mode.value,
                "parallelizable": len(plan.parallelizable_pairs),
                "planning_time_ms": int(execution_time * 1000)
            }
        }]
    }


# Optional: Enhanced supervisor that uses the plan
async def supervisor_with_plan(state: ResearchState) -> dict:
    """
    Enhanced supervisor that uses workflow plan insights

    This is an alternative supervisor that:
    1. Runs the planner first to understand workflow
    2. Uses plan to make smarter routing decisions
    3. Can suggest optimizations to the user

    This is NOT a replacement for Supervisor - it's an optional enhancement
    """

    from app.agents.specialists import get_supervisor_agent

    logger.info("🧭 Enhanced Supervisor: Running with plan insights...")

    # Get plan
    planner = get_workflow_planner()
    plan = await planner.plan_workflow(state, verbose=False)
    briefing = planner.get_supervisor_briefing(plan)

    # Use plan insights to enhance routing
    supervisor = get_supervisor_agent()
    routing = await supervisor.route_request(state)

    # Enhance routing with plan insights
    enhanced_routing = {
        **routing,
        "plan_insights": {
            "expected_duration_sec": plan.total_estimated_ms / 1000,
            "mode": plan.mode.value,
            "parallelizable_opportunities": len(plan.parallelizable_pairs),
            "recommendation": f"Execute as {plan.mode.value} workflow with {len(plan.steps)} steps",
        }
    }

    return {
        "supervisor_decision": enhanced_routing,
        "active_agent": routing["primary_agent"],
        "workflow_plan": briefing,
        "logs": [{
            "step": "supervisor",
            "source": "Supervisor (Plan-Enhanced)",
            "message": f"🧭 Routing to {routing['primary_agent']} (via {plan.mode.value} workflow)",
            "status": "processing",
            "metadata": {
                "expected_duration": f"{plan.total_estimated_ms / 1000:.1f}s",
                "mode": plan.mode.value,
            }
        }]
    }
