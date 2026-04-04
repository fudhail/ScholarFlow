"""
Workflow Monitor - Tracks agent progress and detects issues in non-linear workflows.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
from app.agents.state import ResearchState

logger = logging.getLogger(__name__)


class WorkflowMonitor:
    """
    Monitors workflow progress, detects stuck states, and suggests re-routing.
    Critical for non-linear research workflows.
    """
    
    def __init__(self):
        self.start_time: Optional[datetime] = None
        self.checkpoints: List[Dict] = []
        self.agent_durations: Dict[str, List[float]] = {}
        self.stuck_threshold_seconds = 30
        self.max_agent_iterations = 5
    
    def start_workflow(self, state: ResearchState):
        """Initialize monitoring for a new workflow"""
        self.start_time = datetime.now()
        self.checkpoints = []
        logger.info(f"🚀 Workflow started at {self.start_time}")
    
    def checkpoint(self, agent_name: str, state: ResearchState, metadata: Optional[Dict] = None):
        """Record a checkpoint when an agent completes"""
        now = datetime.now()
        
        checkpoint = {
            "agent": agent_name,
            "timestamp": now,
            "elapsed_seconds": (now - self.start_time).total_seconds() if self.start_time else 0,
            "metadata": metadata or {}
        }
        
        self.checkpoints.append(checkpoint)
        
        # Track agent duration
        if agent_name not in self.agent_durations:
            self.agent_durations[agent_name] = []
        
        if len(self.checkpoints) > 1:
            last_checkpoint = self.checkpoints[-2]
            duration = (now - last_checkpoint["timestamp"]).total_seconds()
            self.agent_durations[agent_name].append(duration)
        
        logger.debug(f"✓ Checkpoint: {agent_name} ({checkpoint['elapsed_seconds']:.1f}s)")
    
    def is_stuck(self, state: ResearchState) -> bool:
        """
        Detect if workflow is stuck.
        
        Returns:
            True if stuck, False otherwise
        """
        if not self.checkpoints:
            return False
        
        last_checkpoint = self.checkpoints[-1]
        time_since_last = (datetime.now() - last_checkpoint["timestamp"]).total_seconds()
        
        # Check if too long since last checkpoint
        if time_since_last > self.stuck_threshold_seconds:
            logger.warning(f"⚠️  Workflow stuck: {time_since_last:.1f}s since last checkpoint")
            return True
        
        # Check if same agent running too many times
        active_agent = state.get("active_agent")
        if active_agent:
            recent_checkpoints = self.checkpoints[-self.max_agent_iterations:]
            same_agent_count = sum(1 for cp in recent_checkpoints if cp["agent"] == active_agent)
            
            if same_agent_count >= self.max_agent_iterations:
                logger.warning(f"⚠️  Agent stuck: {active_agent} ran {same_agent_count} times")
                return True
        
        return False
    
    def suggest_reroute(self, state: ResearchState) -> Optional[str]:
        """
        Suggest a different agent to route to if stuck.
        
        Returns:
            Suggested agent name, or None
        """
        if not self.is_stuck(state):
            return None
        
        active_agent = state.get("active_agent")
        intent = state.get("intent")
        
        # Suggest alternative based on current context
        suggestions = {
            "search": ["synthesis", "memory"],
            "ranker": ["search", "refine_query"],
            "writer": ["search", "planner"],
            "reviewer": ["planner", "writer"],
            "synthesis": ["writer", "citation"]
        }
        
        if active_agent in suggestions:
            recent_agents = [cp["agent"] for cp in self.checkpoints[-5:]]
            for suggestion in suggestions[active_agent]:
                if suggestion not in recent_agents:
                    logger.info(f"💡 Suggesting reroute: {active_agent} → {suggestion}")
                    return suggestion
        
        # Default: try proactive agent for suggestions
        return "proactive"
    
    def analyze_performance(self) -> Dict:
        """
        Analyze workflow performance.
        
        Returns:
            Performance statistics
        """
        if not self.checkpoints:
            return {"status": "no_data"}
        
        total_time = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        
        # Agent statistics
        agent_stats = {}
        for agent, durations in self.agent_durations.items():
            agent_stats[agent] = {
                "count": len(durations),
                "avg_duration": sum(durations) / len(durations) if durations else 0,
                "total_duration": sum(durations)
            }
        
        # Find bottlenecks
        bottlenecks = []
        for agent, stats in agent_stats.items():
            if stats["avg_duration"] > 10:  # More than 10 seconds average
                bottlenecks.append({
                    "agent": agent,
                    "avg_duration": stats["avg_duration"]
                })
        
        return {
            "status": "complete",
            "total_time": total_time,
            "total_checkpoints": len(self.checkpoints),
            "agent_stats": agent_stats,
            "bottlenecks": sorted(bottlenecks, key=lambda x: x["avg_duration"], reverse=True),
            "workflow_path": [cp["agent"] for cp in self.checkpoints]
        }
    
    def get_progress_summary(self) -> str:
        """Get human-readable progress summary"""
        if not self.checkpoints:
            return "Workflow not started"
        
        total_time = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        path = " → ".join([cp["agent"] for cp in self.checkpoints[-5:]])
        
        return f"Progress: {len(self.checkpoints)} steps, {total_time:.1f}s\nRecent: {path}"


# Global monitor instance
_monitor: Optional[WorkflowMonitor] = None


def get_workflow_monitor() -> WorkflowMonitor:
    """Get or create global workflow monitor"""
    global _monitor
    if _monitor is None:
        _monitor = WorkflowMonitor()
    return _monitor


def reset_workflow_monitor():
    """Reset monitor (for testing)"""
    global _monitor
    _monitor = None
