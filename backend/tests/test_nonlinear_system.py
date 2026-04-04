"""
Test script for non-linear multi-agent research system
Run with: python -m pytest backend/tests/test_nonlinear_system.py -v
"""

import pytest
import asyncio
from app.agents.state import create_initial_state, ResearchState
from app.agents.routing import (
    route_from_writer,
    route_from_synthesis,
    route_from_citation,
    determine_entry_node,
    check_workflow_status
)
from app.agents.message_bus import get_message_bus, reset_message_bus, MessageTopics, MessagePriority
from app.agents.workflow_monitor import get_workflow_monitor, reset_workflow_monitor


class TestNonLinearRouting:
    """Test dynamic routing functions"""
    
    def test_writer_to_citation_route(self):
        """Writer should route to citation when [CITE] detected"""
        state = create_initial_state("test query", "proj1")
        state["current_draft"] = {
            "content": "Transformers are powerful [CITE]",
            "status": "in_progress"
        }
        
        next_agent = route_from_writer(state)
        assert next_agent == "citation"
    
    def test_writer_to_search_route(self):
        """Writer should route to search when TODO detected"""
        state = create_initial_state("test query", "proj1")
        state["current_draft"] = {
            "content": "TODO: Research attention mechanism",
            "status": "in_progress"
        }
        
        next_agent = route_from_writer(state)
        assert next_agent == "search"
    
    def test_synthesis_gap_triggers_search(self):
        """Synthesis should route to search when gaps found"""
        state = create_initial_state("test query", "proj1")
        state["synthesis_summary"] = "Found a research gap in the literature"
        
        next_agent = route_from_synthesis(state)
        assert next_agent == "search"
    
    def test_synthesis_contradiction_triggers_search(self):
        """Synthesis should route to search when contradictions found"""
        state = create_initial_state("test query", "proj1")
        state["synthesis_summary"] = "Papers show conflicting results"
        
        next_agent = route_from_synthesis(state)
        assert next_agent == "search"
    
    def test_conditional_entry_citation(self):
        """Direct citation task should enter at citation agent"""
        state = create_initial_state("add citation to section 3", "proj1")
        
        entry = determine_entry_node(state)
        assert entry == "citation"
    
    def test_conditional_entry_search(self):
        """Search task should enter at search agent"""
        state = create_initial_state("find papers on transformers", "proj1")
        state["intent"] = "SEARCH"
        
        entry = determine_entry_node(state)
        assert entry == "search"
    
    def test_workflow_status_reroute_on_stuck(self):
        """Should reroute when too many iterations"""
        state = create_initial_state("test", "proj1")
        state["revision_count"] = 4
        
        status = check_workflow_status(state)
        assert status == "reroute"


class TestMessageBus:
    """Test agent message bus functionality"""
    
    def setup_method(self):
        """Reset message bus before each test"""
        reset_message_bus()
    
    @pytest.mark.asyncio
    async def test_publish_and_retrieve(self):
        """Should publish and retrieve messages"""
        bus = get_message_bus()
        
        await bus.publish(
            from_agent="writer",
            topic=MessageTopics.CITATION_NEEDED,
            payload={"text": "test"}
        )
        
        messages = bus.get_messages(topic=MessageTopics.CITATION_NEEDED)
        assert len(messages) == 1
        assert messages[0].from_agent == "writer"
    
    @pytest.mark.asyncio
    async def test_subscription(self):
        """Should notify subscribers"""
        bus = get_message_bus()
        received = []
        
        def callback(msg):
            received.append(msg)
        
        bus.subscribe(MessageTopics.CITATION_GENERATED, callback)
        
        await bus.publish(
            from_agent="citation",
            topic=MessageTopics.CITATION_GENERATED,
            payload={"citation": "[1]"}
        )
        
        assert len(received) == 1
    
    @pytest.mark.asyncio
    async def test_direct_agent_communication(self):
        """Should send direct messages between agents"""
        bus = get_message_bus()
        
        result = await bus.send_to_agent(
            from_agent="writer",
            to_agent="citation",
            topic=MessageTopics.CITATION_NEEDED,
            payload={"paper_id": "123"}
        )
        
        messages = bus.get_messages(for_agent="citation")
        assert len(messages) == 1
        assert messages[0].to_agent == "citation"


class TestWorkflowMonitor:
    """Test workflow monitoring functionality"""
    
    def setup_method(self):
        """Reset monitor before each test"""
        reset_workflow_monitor()
    
    def test_workflow_start(self):
        """Should initialize monitoring"""
        monitor = get_workflow_monitor()
        state = create_initial_state("test", "proj1")
        
        monitor.start_workflow(state)
        
        assert monitor.start_time is not None
        assert len(monitor.checkpoints) == 0
    
    def test_checkpoint_recording(self):
        """Should record checkpoints"""
        monitor = get_workflow_monitor()
        state = create_initial_state("test", "proj1")
        
        monitor.start_workflow(state)
        monitor.checkpoint("search", state)
        monitor.checkpoint("ranker", state)
        
        assert len(monitor.checkpoints) == 2
        assert monitor.checkpoints[0]["agent"] == "search"
        assert monitor.checkpoints[1]["agent"] == "ranker"
    
    def test_stuck_detection(self):
        """Should detect stuck workflows"""
        monitor = get_workflow_monitor()
        state = create_initial_state("test", "proj1")
        state["active_agent"] = "writer"
        
        monitor.start_workflow(state)
        
        # Simulate same agent running 5 times
        for _ in range(5):
            monitor.checkpoint("writer", state)
        
        assert monitor.is_stuck(state) == True
    
    def test_reroute_suggestion(self):
        """Should suggest alternative agent when stuck"""
        monitor = get_workflow_monitor()
        state = create_initial_state("test", "proj1")
        state["active_agent"] = "writer"
        
        monitor.start_workflow(state)
        
        # Make it stuck
        for _ in range(5):
            monitor.checkpoint("writer", state)
        
        suggestion = monitor.suggest_reroute(state)
        assert suggestion is not None
        assert suggestion != "writer"  # Should suggest different agent


class TestEndToEndScenarios:
    """Test complete workflow scenarios"""
    
    def test_mid_draft_citation_flow(self):
        """Test writer → citation → writer flow"""
        # Writer detects citation needed
        state = create_initial_state("write intro", "proj1")
        state["current_draft"] = {
            "content": "Transformers [CITE]",
            "status": "in_progress"
        }
        
        step1 = route_from_writer(state)
        assert step1 == "citation"
        
        # After citation added, back to writer
        state["citations_used"] = {"paper1": 1}
        state["current_draft"]["content"] = "Transformers [1]"
        
        step2 = route_from_citation(state)
        assert step2 == "writer"
    
    def test_synthesis_gap_search_flow(self):
        """Test synthesis → search → synthesis flow"""
        # Synthesis finds gap
        state = create_initial_state("analyze papers", "proj1")
        state["synthesis_summary"] = "Identified research gap in X"
        
        step1 = route_from_synthesis(state)
        assert step1 == "search"
        
        # After search, back to synthesis
        state["found_papers"] = [{"title": "Paper 1"}, {"title": "Paper 2"}]
        state["ranked_papers"] = [{"title": "Paper 1", "relevance_score": 0.9}]
        
        # Would need to simulate search routing back to synthesis
        # This demonstrates the non-linear capability


def test_graph_structure():
    """Test that graph can be created without errors"""
    from app.agents.graph import create_research_graph
    
    graph = create_research_graph()
    assert graph is not None


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
