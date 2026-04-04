"""
Workflow Planner Agent - Strategic Execution Planning

This agent works with the Supervisor to create intelligent execution plans
before routing to specialized agents. It analyzes:
- User intent and context
- Available papers and assets
- Current draft status
- System state and constraints

Then generates a structured plan with:
- Primary objective
- Sequential steps
- Parallel opportunities
- Resource requirements
- Estimated execution path
- Checkpoint decisions
"""

from typing import Dict, List, Optional, Literal
from dataclasses import dataclass
from enum import Enum
import logging
from app.core.ai_client import ai_client
from app.agents.state import ResearchState

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Types of execution modes based on context"""
    DISCOVERY = "discovery"           # Search, find, explore papers
    ANALYSIS = "analysis"              # Synthesize, compare, understand
    DRAFTING = "drafting"              # Write, outline, structure
    REFINEMENT = "refinement"          # Review, revise, improve
    HYBRID = "hybrid"                  # Mix of above (most common)


class TaskSequence(Enum):
    """How tasks should be sequenced"""
    SEQUENTIAL = "sequential"          # One after another
    PARALLEL = "parallel"              # Can run simultaneously
    CONDITIONAL = "conditional"        # Depends on previous result
    ITERATIVE = "iterative"            # Loop until condition met


@dataclass
class ExecutionStep:
    """Represents a single step in the execution plan"""
    order: int
    agent: str
    action: str
    input_requirements: List[str]      # What state fields needed
    output_produces: List[str]         # What state fields it creates
    description: str
    estimated_duration_ms: int
    is_parallel_safe: bool
    checkpoint: bool = False           # Should save state after this
    fallback_agent: Optional[str] = None
    success_criteria: Optional[str] = None


@dataclass
class WorkflowPlan:
    """Complete workflow execution plan"""
    objective: str
    mode: ExecutionMode
    total_estimated_ms: int
    steps: List[ExecutionStep]
    parallelizable_pairs: List[tuple]  # (step_i, step_j) that can run parallel
    critical_path: List[int]           # Step orders on critical path
    checkpoints: List[int]             # Step orders that are checkpoints
    resource_requirements: Dict[str, any]
    assumptions: List[str]
    risk_factors: List[str]
    optimization_notes: List[str]


class WorkflowPlanner:
    """
    Strategic workflow planning agent that works with Supervisor

    Usage:
        planner = WorkflowPlanner()
        plan = await planner.plan_workflow(state)

    The plan can be:
        - Executed directly by graph
        - Passed to supervisor for approval
        - Reasons about complex multi-step scenarios
    """

    def __init__(self):
        self.last_plan: Optional[WorkflowPlan] = None
        self.plan_history: List[WorkflowPlan] = []

    async def plan_workflow(
        self,
        state: ResearchState,
        verbose: bool = False
    ) -> WorkflowPlan:
        """
        Analyze current state and create strategic execution plan

        Args:
            state: Current ResearchState
            verbose: Log detailed planning reasoning

        Returns:
            Structured workflow plan with all execution steps
        """
        logger.info("🎯 Workflow Planner: Analyzing context and creating plan...")

        # 1. Analyze current context
        context = self._analyze_context(state)
        if verbose:
            logger.info(f"Context analysis: {context}")

        # 2. Determine execution mode
        mode = self._determine_execution_mode(state, context)
        logger.info(f"📋 Execution mode: {mode.value}")

        # 3. Build execution steps based on mode
        steps = await self._build_execution_steps(state, mode, context)
        logger.info(f"📍 Created {len(steps)} execution steps")

        # 4. Identify parallelization opportunities
        parallelizable = self._find_parallelizable_steps(steps)
        logger.info(f"⚡ Found {len(parallelizable)} parallelizable opportunities")

        # 5. Calculate critical path
        critical_path = self._calculate_critical_path(steps, parallelizable)

        # 6. Identify checkpoints
        checkpoints = self._identify_checkpoints(steps)

        # 7. Calculate total time
        total_ms = self._calculate_total_time(steps, parallelizable)

        # 8. Build resource requirements
        resources = self._calculate_resource_requirements(steps)

        # 9. Identify risks and optimizations
        risks = self._identify_risks(state, steps, mode)
        optimizations = self._identify_optimizations(state, steps, mode)
        assumptions = self._identify_assumptions(state, steps, mode)

        # Create plan
        plan = WorkflowPlan(
            objective=self._formulate_objective(state, mode),
            mode=mode,
            total_estimated_ms=total_ms,
            steps=steps,
            parallelizable_pairs=parallelizable,
            critical_path=critical_path,
            checkpoints=checkpoints,
            resource_requirements=resources,
            assumptions=assumptions,
            risk_factors=risks,
            optimization_notes=optimizations
        )

        # Store plan
        self.last_plan = plan
        self.plan_history.append(plan)

        logger.info(f"✅ Plan created: {len(steps)} steps, ~{total_ms}ms total")

        return plan

    def _analyze_context(self, state: ResearchState) -> Dict:
        """Analyze current state context"""
        return {
            "has_papers": len(state.get("ranked_papers", [])) > 0,
            "has_draft": bool(state.get("current_draft", {}).get("content")),
            "has_research_assets": len(state.get("research_asset_ids", [])) > 0,
            "papers_count": len(state.get("ranked_papers", [])),
            "draft_section": state.get("current_section"),
            "operation_mode": state.get("operation_mode", "research"),
            "previous_searches": state.get("search_iteration", 0),
            "previous_revisions": state.get("revision_count", 0),
            "intent": state.get("intent"),
            "query_length": len(state.get("query", "").split()),
        }

    def _determine_execution_mode(
        self,
        state: ResearchState,
        context: Dict
    ) -> ExecutionMode:
        """Determine which execution mode fits current request"""

        query = state.get("query", "").lower()
        intent = state.get("intent", "").upper()

        # Pure discovery mode
        if intent == "SEARCH" or any(kw in query for kw in ["search", "find papers", "explore"]):
            return ExecutionMode.DISCOVERY

        # Pure drafting mode
        if intent == "DRAFT" or any(kw in query for kw in ["write", "draft", "compose"]):
            return ExecutionMode.DRAFTING

        # Analysis mode
        if any(kw in query for kw in ["analyze", "compare", "synthesize", "meta-analysis"]):
            return ExecutionMode.ANALYSIS

        # Refinement mode
        if intent in ["CHAT"] and context["has_draft"]:
            return ExecutionMode.REFINEMENT

        # Default: Hybrid (most requests need multiple capabilities)
        return ExecutionMode.HYBRID

    async def _build_execution_steps(
        self,
        state: ResearchState,
        mode: ExecutionMode,
        context: Dict
    ) -> List[ExecutionStep]:
        """Build detailed execution steps based on mode"""

        steps = []
        order = 0

        # All modes start with: Supervisor → Memory
        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="supervisor",
            action="orchestration",
            input_requirements=["query", "project_id"],
            output_produces=["supervisor_decision", "active_agent"],
            description="Supervisor evaluates context and routing",
            estimated_duration_ms=100,
            is_parallel_safe=False,
            checkpoint=False
        ))

        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="memory",
            action="context_enrichment",
            input_requirements=["query", "conversation_memory"],
            output_produces=["conversation_memory", "research_insights"],
            description="Memory retrieves relevant past context",
            estimated_duration_ms=200,
            is_parallel_safe=False,
            checkpoint=False
        ))

        # ===== DISCOVERY MODE =====
        if mode == ExecutionMode.DISCOVERY:
            order = await self._add_discovery_steps(steps, state, context, order)

        # ===== DRAFTING MODE =====
        elif mode == ExecutionMode.DRAFTING:
            order = await self._add_drafting_steps(steps, state, context, order)

        # ===== ANALYSIS MODE =====
        elif mode == ExecutionMode.ANALYSIS:
            order = await self._add_analysis_steps(steps, state, context, order)

        # ===== REFINEMENT MODE =====
        elif mode == ExecutionMode.REFINEMENT:
            order = await self._add_refinement_steps(steps, state, context, order)

        # ===== HYBRID MODE (Most common) =====
        elif mode == ExecutionMode.HYBRID:
            order = await self._add_hybrid_steps(steps, state, context, order)

        # All modes end with: Proactive
        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="proactive",
            action="suggestions",
            input_requirements=["ranked_papers", "current_draft"],
            output_produces=["next_actions", "quality_feedback"],
            description="Proactive generates next action suggestions",
            estimated_duration_ms=500,
            is_parallel_safe=True,
            checkpoint=True
        ))

        return steps

    async def _add_discovery_steps(
        self,
        steps: List[ExecutionStep],
        state: ResearchState,
        context: Dict,
        order: int
    ) -> int:
        """Add steps for DISCOVERY mode (search papers)"""

        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="search",
            action="multi_api_search",
            input_requirements=["query"],
            output_produces=["found_papers"],
            description="Search papers across ArXiv, Semantic Scholar, PubMed",
            estimated_duration_ms=2500,
            is_parallel_safe=True,
            checkpoint=False,
            success_criteria="Found at least 5 papers"
        ))

        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="ranker",
            action="rank_papers",
            input_requirements=["found_papers", "query"],
            output_produces=["ranked_papers"],
            description="Rank papers by relevance",
            estimated_duration_ms=800,
            is_parallel_safe=False,
            checkpoint=False,
            success_criteria="Top paper relevance > 0.7"
        ))

        # Decision point: Should we refine?
        if context.get("papers_count", 0) < 3:
            order += 1
            steps.append(ExecutionStep(
                order=order,
                agent="research_coordinator",
                action="evaluate_results",
                input_requirements=["ranked_papers"],
                output_produces=["coordinator_decision"],
                description="Research coordinator evaluates if results are good",
                estimated_duration_ms=300,
                is_parallel_safe=False,
                checkpoint=True
            ))

            # If poor results, might add refine step
            order += 1
            steps.append(ExecutionStep(
                order=order,
                agent="refine_query",
                action="query_expansion",
                input_requirements=["query", "ranked_papers"],
                output_produces=["refined_query"],
                description="Refine search query if needed (optional)",
                estimated_duration_ms=400,
                is_parallel_safe=False,
                checkpoint=False,
                fallback_agent="search"
            ))
        else:
            order += 1
            steps.append(ExecutionStep(
                order=order,
                agent="analyzing",
                action="prepare_analysis",
                input_requirements=["ranked_papers"],
                output_produces=["analysis_status"],
                description="Preparing to analyze results (SSE status)",
                estimated_duration_ms=100,
                is_parallel_safe=False,
                checkpoint=False
            ))

        # Analysis step
        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="rag_response",
            action="generate_answer",
            input_requirements=["query", "ranked_papers"],
            output_produces=["response_text", "synthesis_summary"],
            description="Generate grounded answer from papers",
            estimated_duration_ms=1500,
            is_parallel_safe=False,
            checkpoint=True
        ))

        return order

    async def _add_drafting_steps(
        self,
        steps: List[ExecutionStep],
        state: ResearchState,
        context: Dict,
        order: int
    ) -> int:
        """Add steps for DRAFTING mode (write paper)"""

        # Step 1: Planner (create outline if no draft)
        if not context.get("has_draft"):
            order += 1
            steps.append(ExecutionStep(
                order=order,
                agent="planner",
                action="outline_generation",
                input_requirements=["query", "selected_paper_ids"],
                output_produces=["current_draft"],
                description="Planner generates manuscript outline",
                estimated_duration_ms=1200,
                is_parallel_safe=False,
                checkpoint=True,
                success_criteria="Outline has 4+ sections"
            ))

        # Step 2: Planner Reviewer
        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="planner_reviewer",
            action="plan_validation",
            input_requirements=["current_draft"],
            output_produces=["planner_review_status"],
            description="Reviewer validates plan/outline quality",
            estimated_duration_ms=500,
            is_parallel_safe=False,
            checkpoint=False,
            fallback_agent="planner"
        ))

        # Step 3: Writer (multiple iterations)
        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="writer",
            action="section_drafting",
            input_requirements=["current_draft", "current_section", "selected_paper_ids"],
            output_produces=["current_draft"],
            description="Writer drafts current section",
            estimated_duration_ms=3000,
            is_parallel_safe=False,
            checkpoint=True,
            success_criteria="Section has 200+ words"
        ))

        # Step 4: May need citations (optional parallel)
        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="citation",
            action="citation_injection",
            input_requirements=["current_draft", "ranked_papers"],
            output_produces=["citations_used"],
            description="Citation agent adds citations to draft",
            estimated_duration_ms=1000,
            is_parallel_safe=True,
            checkpoint=False
        ))

        # Step 5: Reviewer
        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="reviewer",
            action="draft_review",
            input_requirements=["current_draft"],
            output_produces=["critique_feedback", "needs_revision"],
            description="Reviewer evaluates draft quality",
            estimated_duration_ms=2000,
            is_parallel_safe=False,
            checkpoint=True,
            success_criteria="No critical issues found"
        ))

        return order

    async def _add_analysis_steps(
        self,
        steps: List[ExecutionStep],
        state: ResearchState,
        context: Dict,
        order: int
    ) -> int:
        """Add steps for ANALYSIS mode (compare/synthesize)"""

        # If no papers, search first
        if not context.get("has_papers"):
            order += 1
            steps.append(ExecutionStep(
                order=order,
                agent="search",
                action="multi_api_search",
                input_requirements=["query"],
                output_produces=["found_papers"],
                description="Search for papers to analyze",
                estimated_duration_ms=2500,
                is_parallel_safe=True,
                checkpoint=False
            ))

            order += 1
            steps.append(ExecutionStep(
                order=order,
                agent="ranker",
                action="rank_papers",
                input_requirements=["found_papers", "query"],
                output_produces=["ranked_papers"],
                description="Rank papers by relevance",
                estimated_duration_ms=800,
                is_parallel_safe=False,
                checkpoint=False
            ))

        # Main analysis steps
        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="synthesis",
            action="multi_paper_synthesis",
            input_requirements=["ranked_papers", "query"],
            output_produces=["synthesis_summary", "comparative_analysis"],
            description="Synthesis agent analyzes and compares papers",
            estimated_duration_ms=2000,
            is_parallel_safe=False,
            checkpoint=True
        ))

        # Optional: Generate written analysis
        if context.get("operation_mode") == "studio":
            order += 1
            steps.append(ExecutionStep(
                order=order,
                agent="writer",
                action="analysis_document",
                input_requirements=["synthesis_summary", "comparative_analysis"],
                output_produces=["current_draft"],
                description="Writer creates analysis document",
                estimated_duration_ms=2500,
                is_parallel_safe=False,
                checkpoint=True
            ))

        return order

    async def _add_refinement_steps(
        self,
        steps: List[ExecutionStep],
        state: ResearchState,
        context: Dict,
        order: int
    ) -> int:
        """Add steps for REFINEMENT mode (improve existing work)"""

        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="reviewer",
            action="draft_analysis",
            input_requirements=["current_draft"],
            output_produces=["critique_feedback"],
            description="Reviewer analyzes current draft",
            estimated_duration_ms=1500,
            is_parallel_safe=False,
            checkpoint=False
        ))

        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="writer",
            action="refinement",
            input_requirements=["current_draft", "critique_feedback"],
            output_produces=["current_draft"],
            description="Writer implements refinements",
            estimated_duration_ms=2000,
            is_parallel_safe=False,
            checkpoint=True
        ))

        return order

    async def _add_hybrid_steps(
        self,
        steps: List[ExecutionStep],
        state: ResearchState,
        context: Dict,
        order: int
    ) -> int:
        """Add steps for HYBRID mode (mixed discovery + drafting)"""

        # Smart hybrid: search first, then draft

        # Search phase
        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="search",
            action="multi_api_search",
            input_requirements=["query"],
            output_produces=["found_papers"],
            description="Search for papers",
            estimated_duration_ms=2500,
            is_parallel_safe=True,
            checkpoint=False
        ))

        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="ranker",
            action="rank_papers",
            input_requirements=["found_papers", "query"],
            output_produces=["ranked_papers"],
            description="Rank papers by relevance",
            estimated_duration_ms=800,
            is_parallel_safe=False,
            checkpoint=False
        ))

        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="research_coordinator",
            action="evaluate_results",
            input_requirements=["ranked_papers"],
            output_produces=["coordinator_decision"],
            description="Coordinator evaluates search results",
            estimated_duration_ms=300,
            is_parallel_safe=False,
            checkpoint=False
        ))

        # Synthesis (optional, parallel with planning)
        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="synthesis",
            action="preliminary_synthesis",
            input_requirements=["ranked_papers"],
            output_produces=["synthesis_summary"],
            description="Quick synthesis of papers",
            estimated_duration_ms=1500,
            is_parallel_safe=True,
            checkpoint=False
        ))

        # Draft phase
        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="planner",
            action="outline_generation",
            input_requirements=["query", "ranked_papers"],
            output_produces=["current_draft"],
            description="Planner creates outline based on search results",
            estimated_duration_ms=1200,
            is_parallel_safe=False,
            checkpoint=True
        ))

        order += 1
        steps.append(ExecutionStep(
            order=order,
            agent="writer",
            action="section_drafting",
            input_requirements=["current_draft", "ranked_papers"],
            output_produces=["current_draft"],
            description="Writer drafts initial section",
            estimated_duration_ms=2500,
            is_parallel_safe=False,
            checkpoint=True
        ))

        return order

    def _find_parallelizable_steps(
        self,
        steps: List[ExecutionStep]
    ) -> List[tuple]:
        """Identify which steps can run in parallel"""

        parallelizable = []

        for i, step_i in enumerate(steps):
            for j, step_j in enumerate(steps):
                if i >= j:
                    continue

                # Check if both are parallelization-safe
                if not step_i.is_parallel_safe or not step_j.is_parallel_safe:
                    continue

                # Check if they don't have dependencies
                outputs_i = set(step_i.output_produces)
                requires_j = set(step_j.input_requirements)

                outputs_j = set(step_j.output_produces)
                requires_i = set(step_i.input_requirements)

                # No cross-dependencies?
                if not (outputs_i & requires_j) and not (outputs_j & requires_i):
                    parallelizable.append((step_i.order, step_j.order))

        return parallelizable

    def _calculate_critical_path(
        self,
        steps: List[ExecutionStep],
        parallelizable: List[tuple]
    ) -> List[int]:
        """Calculate critical path (longest dependency chain)"""

        # Simple heuristic: steps that aren't parallelizable are critical
        critical = set()

        for step in steps:
            if not step.is_parallel_safe or step.checkpoint:
                critical.add(step.order)

        return sorted(list(critical))

    def _identify_checkpoints(self, steps: List[ExecutionStep]) -> List[int]:
        """Identify checkpoint steps where state should be saved"""

        checkpoints = []

        for step in steps:
            if step.checkpoint:
                checkpoints.append(step.order)

        return checkpoints

    def _calculate_total_time(
        self,
        steps: List[ExecutionStep],
        parallelizable: List[tuple]
    ) -> int:
        """Calculate total estimated execution time"""

        # Simplified: sum critical path + some parallel opportunities
        critical_time = sum(
            step.estimated_duration_ms
            for step in steps
            if step not in parallelizable
        )

        # Account for parallelization saving ~30% on average
        return int(critical_time * 0.7)

    def _calculate_resource_requirements(
        self,
        steps: List[ExecutionStep]
    ) -> Dict:
        """Calculate what resources steps need"""

        resources = {
            "ai_calls": len([s for s in steps if "write" in s.action or "review" in s.action or "generate" in s.action]),
            "api_calls": len([s for s in steps if "search" in s.action]),
            "memory": "4GB",  # Baseline
            "embeddings": len([s for s in steps if "rank" in s.action or "synthesis" in s.action]),
        }

        return resources

    def _identify_risks(
        self,
        state: ResearchState,
        steps: List[ExecutionStep],
        mode: ExecutionMode
    ) -> List[str]:
        """Identify potential execution risks"""

        risks = []

        if len(steps) > 10:
            risks.append("Complex workflow with many steps - monitor for stuck states")

        if mode == ExecutionMode.DISCOVERY and state.get("search_iteration", 0) > 2:
            risks.append("Multiple search iterations already - consider different approach")

        if mode == ExecutionMode.DRAFTING and state.get("revision_count", 0) > 2:
            risks.append("Multiple revisions already - may have quality ceiling")

        if not state.get("ranked_papers"):
            risks.append("No papers available - search results critical")

        return risks

    def _identify_optimizations(
        self,
        state: ResearchState,
        steps: List[ExecutionStep],
        mode: ExecutionMode
    ) -> List[str]:
        """Suggest execution optimizations"""

        optimizations = []

        parallelizable_count = len([s for s in steps if s.is_parallel_safe])
        if parallelizable_count > 3:
            optimizations.append(f"Run {parallelizable_count} steps in parallel for ~30% speedup")

        if state.get("search_iteration", 0) > 0:
            optimizations.append("Use cached embeddings from previous search")

        if len(state.get("ranked_papers", [])) > 5:
            optimizations.append("Consider pagination - first 5 papers may be sufficient")

        return optimizations

    def _identify_assumptions(
        self,
        state: ResearchState,
        steps: List[ExecutionStep],
        mode: ExecutionMode
    ) -> List[str]:
        """Document execution assumptions"""

        assumptions = [
            "User query is clear and specific",
            "AI model (Claude) is available",
            "Search APIs (ArXiv, Semantic Scholar) are responsive",
            "User has selected relevant papers where needed",
        ]

        if mode == ExecutionMode.DRAFTING:
            assumptions.append("User has outline or will accept AI-generated outline")

        if mode == ExecutionMode.ANALYSIS:
            assumptions.append("3+ papers available for meaningful comparison")

        return assumptions

    def _formulate_objective(
        self,
        state: ResearchState,
        mode: ExecutionMode
    ) -> str:
        """Formulate clear objective statement"""

        query = state.get("query", "")

        if mode == ExecutionMode.DISCOVERY:
            return f"Discover and rank papers relevant to: {query[:100]}"

        elif mode == ExecutionMode.DRAFTING:
            return f"Create structured paper draft for: {query[:100]}"

        elif mode == ExecutionMode.ANALYSIS:
            return f"Synthesize and compare papers for: {query[:100]}"

        elif mode == ExecutionMode.REFINEMENT:
            return f"Refine existing work: {query[:100]}"

        else:  # HYBRID
            return f"Execute hybrid workflow (search + draft): {query[:100]}"

    def get_supervisor_briefing(self, plan: WorkflowPlan) -> Dict:
        """
        Get a briefing summary for the supervisor to make final routing decision

        Supervisor can review this and approve, modify, or use differently
        """
        return {
            "objective": plan.objective,
            "mode": plan.mode.value,
            "recommended_entry_agent": plan.steps[0].agent if plan.steps else "supervisor",
            "total_steps": len(plan.steps),
            "estimated_duration_sec": plan.total_estimated_ms / 1000,
            "parallelizable_opportunities": len(plan.parallelizable_pairs),
            "key_checkpoints": plan.checkpoints,
            "estimated_ai_calls": plan.resource_requirements.get("ai_calls", 0),
            "estimated_api_calls": plan.resource_requirements.get("api_calls", 0),
            "primary_risks": plan.risk_factors[:2] if plan.risk_factors else [],
            "key_optimizations": plan.optimization_notes[:2] if plan.optimization_notes else [],
            "critical_success_factors": [
                f"Step {s.order}: {s.description}"
                for s in plan.steps
                if s.success_criteria
            ][:3]
        }

    def get_plan_summary(self, plan: Optional[WorkflowPlan] = None) -> str:
        """Get human-readable plan summary"""

        plan = plan or self.last_plan
        if not plan:
            return "No plan available"

        summary = f"""
WORKFLOW PLAN SUMMARY
═════════════════════════════════════════════
Objective: {plan.objective}
Mode: {plan.mode.value.upper()}
Estimated Time: {plan.total_estimated_ms / 1000:.1f} seconds

EXECUTION STEPS ({len(plan.steps)} total):
"""

        for step in plan.steps:
            summary += f"\n{step.order}. {step.agent.upper()}"
            summary += f"\n   Action: {step.action}"
            summary += f"\n   Duration: {step.estimated_duration_ms}ms"
            if step.success_criteria:
                summary += f"\n   Success: {step.success_criteria}"

        summary += f"\n\nPARALLELIZATION: {len(plan.parallelizable_pairs)} opportunities"
        summary += f"CRITICAL PATH: {len(plan.critical_path)} steps"
        summary += f"\nRESOURCES: {plan.resource_requirements}"

        if plan.risk_factors:
            summary += f"\n\nRISKS:\n"
            for risk in plan.risk_factors:
                summary += f"  ⚠️  {risk}\n"

        if plan.optimization_notes:
            summary += f"\nOPTIMIZATIONS:\n"
            for opt in plan.optimization_notes:
                summary += f"  ✨ {opt}\n"

        return summary


# ===== SINGLETON INSTANCES =====

_planner_instance: Optional[WorkflowPlanner] = None


def get_workflow_planner() -> WorkflowPlanner:
    """Get or create workflow planner singleton"""
    global _planner_instance
    if _planner_instance is None:
        _planner_instance = WorkflowPlanner()
    return _planner_instance
