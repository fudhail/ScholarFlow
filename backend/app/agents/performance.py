"""
Performance optimizations for faster response times.
Includes caching, fast-path routing, and response streaming.
"""
from functools import lru_cache
from typing import Dict, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


class ResponseCache:
    """Cache for frequently accessed data and AI responses"""
    
    def __init__(self, max_size: int = 1000):
        self.cache: Dict[str, any] = {}
        self.max_size = max_size
    
    def get(self, key: str) -> Optional[any]:
        """Get cached value"""
        return self.cache.get(key)
    
    def set(self, key: str, value: any):
        """Set cached value"""
        if len(self.cache) >= self.max_size:
            # Remove oldest entry
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        self.cache[key] = value
    
    def clear(self):
        """Clear all cache"""
        self.cache.clear()


# Global cache instance
_cache = ResponseCache()


def get_cache() -> ResponseCache:
    """Get global cache instance"""
    return _cache


@lru_cache(maxsize=100)
def should_use_fast_path(query: str) -> bool:
    """
    Determine if query can use fast path (skip orchestration).
    Fast path for simple, common queries.
    """
    query_lower = query.lower()
    
    # Simple citation requests
    if len(query.split()) < 5 and "cite" in query_lower:
        return True
    
    # Quick searches
    if query.startswith("search ") or query.startswith("find "):
        return True
    
    # Direct commands
    fast_keywords = ["show", "list", "get", "view"]
    if any(query_lower.startswith(kw) for kw in fast_keywords):
        return True
    
    return False


async def fast_path_handler(query: str, state: dict) -> Optional[dict]:
    """
    Handle simple queries with fast path (skip full graph).
    Returns result immediately if possible.
    """
    query_lower = query.lower()
    
    # Fast citation lookup
    if "cite" in query_lower and len(query.split()) < 8:
        from app.agents.specialists import get_citation_agent
        citation = get_citation_agent()
        # Return immediately without full graph traversal
        return {
            "fast_path": True,
            "handler": "citation",
            "skip_nodes": ["supervisor", "memory", "router"]
        }
    
    # Fast search
    if query.startswith(("search ", "find ")):
        return {
            "fast_path": True,
            "handler": "search",
            "skip_nodes": ["supervisor", "memory", "router"]
        }
    
    return None


class StreamingResponse:
    """Stream responses to user as they're generated"""
    
    def __init__(self):
        self.chunks = []
    
    async def add_chunk(self, chunk: str):
        """Add response chunk"""
        self.chunks.append(chunk)
        # In real implementation, would yield to client
    
    def get_full_response(self) -> str:
        """Get complete response"""
        return "".join(self.chunks)


async def parallel_agent_execution(agents: list, state: dict) -> dict:
    """
    Execute multiple agents in parallel for faster results.
    Use when agents don't depend on each other.
    """
    tasks = []
    for agent in agents:
        tasks.append(agent(state))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Merge results
    merged = {}
    for result in results:
        if isinstance(result, dict):
            merged.update(result)
    
    return merged


def optimize_routing_decision(state: dict) -> str:
    """
    Make faster routing decisions by checking simple rules first.
    Avoid expensive AI calls when possible.
    """
    # Fast rules
    draft = state.get("current_draft", {})
    content = draft.get("content", "")
    
    # Immediate decisions based on content markers
    if "[CITE]" in content:
        return "citation"
    if "TODO:" in content:
        return "search"
    if draft.get("status") == "complete":
        return "reviewer"
    
    # Check iteration limits
    if state.get("search_iteration", 0) >= 3:
        return "save_to_context"
    
    if state.get("revision_count", 0) >= 3:
        return "proactive"
    
    # Otherwise use normal routing
    return None


# Pre-compute common routing paths
ROUTING_CACHE = {
    "cite_needed": "citation",
    "search_needed": "search",
    "review_needed": "reviewer",
    "synthesis_needed": "synthesis",
    "plan_needed": "planner"
}


@lru_cache(maxsize=50)
def get_optimal_path(from_agent: str, to_agent: str) -> list:
    """
    Pre-compute optimal paths between agents.
    Avoids unnecessary intermediate nodes.
    """
    # Direct paths (no intermediate nodes needed)
    direct_paths = {
        ("writer", "citation"): ["citation"],
        ("writer", "search"): ["search"],
        ("citation", "writer"): ["writer"],
        ("search", "synthesis"): ["synthesis"],
        ("synthesis", "writer"): ["writer"],
    }
    
    key = (from_agent, to_agent)
    if key in direct_paths:
        return direct_paths[key]
    
    # Default: include intermediate nodes
    return [to_agent]


class PerformanceTracker:
    """Track response times and optimize slow paths"""
    
    def __init__(self):
        self.timings = {}
        self.slow_threshold = 5.0  # seconds
    
    def record(self, agent: str, duration: float):
        """Record agent execution time"""
        if agent not in self.timings:
            self.timings[agent] = []
        self.timings[agent].append(duration)
        
        # Alert if slow
        if duration > self.slow_threshold:
            logger.warning(f"⚠️ Slow agent: {agent} took {duration:.2f}s")
    
    def get_slow_agents(self) -> list:
        """Get list of agents that are consistently slow"""
        slow_agents = []
        for agent, times in self.timings.items():
            avg = sum(times) / len(times) if times else 0
            if avg > self.slow_threshold:
                slow_agents.append((agent, avg))
        return sorted(slow_agents, key=lambda x: x[1], reverse=True)
    
    def suggest_optimizations(self) -> list:
        """Suggest optimizations based on performance data"""
        suggestions = []
        
        slow = self.get_slow_agents()
        for agent, avg_time in slow:
            if agent == "search":
                suggestions.append("Consider parallel search across multiple sources")
            elif agent == "synthesis":
                suggestions.append("Cache synthesis results for similar papers")
            elif agent == "writer":
                suggestions.append("Use streaming responses for draft generation")
        
        return suggestions


# Global performance tracker
_perf_tracker = PerformanceTracker()


def get_performance_tracker() -> PerformanceTracker:
    """Get global performance tracker"""
    return _perf_tracker
