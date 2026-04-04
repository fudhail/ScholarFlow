"""
Agent Message Bus - Enables direct agent-to-agent communication
for non-linear workflows and dynamic collaboration.
"""
from datetime import datetime
from typing import Dict, List, Callable, Optional, Any
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    """Message priority levels"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


class AgentMessage:
    """Structured message for agent communication"""
    
    def __init__(
        self,
        from_agent: str,
        to_agent: str,
        topic: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.MEDIUM
    ):
        self.from_agent = from_agent
        self.to_agent = to_agent
        self.topic = topic
        self.payload = payload
        self.priority = priority
        self.timestamp = datetime.now()
        self.processed = False
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for state storage"""
        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "topic": self.topic,
            "payload": self.payload,
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat(),
            "processed": self.processed
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentMessage':
        """Create from dictionary"""
        msg = cls(
            from_agent=data["from_agent"],
            to_agent=data["to_agent"],
            topic=data["topic"],
            payload=data["payload"],
            priority=MessagePriority(data.get("priority", 2))
        )
        msg.timestamp = datetime.fromisoformat(data["timestamp"])
        msg.processed = data.get("processed", False)
        return msg


class AgentMessageBus:
    """
    Central message bus for agent-to-agent communication.
    Enables non-linear workflows by allowing agents to communicate directly.
    """
    
    def __init__(self):
        self.messages: List[AgentMessage] = []
        self.subscriptions: Dict[str, List[Callable]] = {}
        self.handlers: Dict[str, Dict[str, Callable]] = {}
        self._lock = asyncio.Lock()
    
    async def publish(
        self,
        from_agent: str,
        topic: str,
        payload: Dict[str, Any],
        to_agent: Optional[str] = None,
        priority: MessagePriority = MessagePriority.MEDIUM
    ) -> None:
        """
        Publish a message to the bus.
        
        Args:
            from_agent: Sender agent name
            topic: Message topic/type
            payload: Message data
            to_agent: Specific recipient (optional, otherwise broadcast)
            priority: Message priority
        """
        async with self._lock:
            message = AgentMessage(
                from_agent=from_agent,
                to_agent=to_agent or "broadcast",
                topic=topic,
                payload=payload,
                priority=priority
            )
            
            self.messages.append(message)
            
            logger.info(f"📨 Message published: {from_agent} → {to_agent or 'ALL'} [{topic}]")
            
            # Notify subscribers
            await self._notify_subscribers(message)
    
    async def _notify_subscribers(self, message: AgentMessage):
        """Notify all subscribers of a topic"""
        topic = message.topic
        
        if topic in self.subscriptions:
            for callback in self.subscriptions[topic]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(message)
                    else:
                        callback(message)
                except Exception as e:
                    logger.error(f"Error in subscriber callback: {e}")
    
    def subscribe(self, topic: str, callback: Callable):
        """
        Subscribe to messages on a specific topic.
        
        Args:
            topic: Topic to subscribe to
            callback: Function to call when message received
        """
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []
        self.subscriptions[topic].append(callback)
        logger.debug(f"📡 Subscribed to topic: {topic}")
    
    def unsubscribe(self, topic: str, callback: Callable):
        """Unsubscribe from a topic"""
        if topic in self.subscriptions and callback in self.subscriptions[topic]:
            self.subscriptions[topic].remove(callback)
    
    def register_handler(self, agent_name: str, topic: str, handler: Callable):
        """
        Register a handler for specific agent/topic combination.
        
        Args:
            agent_name: Name of the agent
            topic: Topic to handle
            handler: Handler function
        """
        if agent_name not in self.handlers:
            self.handlers[agent_name] = {}
        self.handlers[agent_name][topic] = handler
        logger.debug(f"🔧 Registered handler: {agent_name} handles {topic}")
    
    async def send_to_agent(
        self,
        from_agent: str,
        to_agent: str,
        topic: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.MEDIUM
    ) -> Optional[Any]:
        """
        Send a message directly to a specific agent and get response.
        
        Args:
            from_agent: Sender
            to_agent: Recipient
            topic: Message topic
            payload: Message data
            priority: Priority level
            
        Returns:
            Response from the handler, if any
        """
        message = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            topic=topic,
            payload=payload,
            priority=priority
        )
        
        async with self._lock:
            self.messages.append(message)
        
        logger.info(f"📨 Direct message: {from_agent} → {to_agent} [{topic}]")
        
        # Call handler if registered
        if to_agent in self.handlers and topic in self.handlers[to_agent]:
            handler = self.handlers[to_agent][topic]
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(message)
                else:
                    result = handler(message)
                message.processed = True
                return result
            except Exception as e:
                logger.error(f"Error in handler: {e}")
                return None
        
        return None
    
    def get_messages(
        self,
        for_agent: Optional[str] = None,
        topic: Optional[str] = None,
        since: Optional[datetime] = None,
        unprocessed_only: bool = False
    ) -> List[AgentMessage]:
        """
        Retrieve messages from the bus.
        
        Args:
            for_agent: Filter by recipient
            topic: Filter by topic
            since: Only messages after this time
            unprocessed_only: Only unprocessed messages
            
        Returns:
            List of matching messages
        """
        messages = self.messages
        
        if for_agent:
            messages = [m for m in messages if m.to_agent == for_agent or m.to_agent == "broadcast"]
        
        if topic:
            messages = [m for m in messages if m.topic == topic]
        
        if since:
            messages = [m for m in messages if m.timestamp > since]
        
        if unprocessed_only:
            messages = [m for m in messages if not m.processed]
        
        return messages
    
    def mark_processed(self, message: AgentMessage):
        """Mark a message as processed"""
        message.processed = True
    
    def clear_old_messages(self, before: datetime):
        """Clear messages older than specified time"""
        self.messages = [m for m in self.messages if m.timestamp > before]
    
    def get_statistics(self) -> Dict:
        """Get bus statistics"""
        total = len(self.messages)
        processed = sum(1 for m in self.messages if m.processed)
        
        by_topic = {}
        for msg in self.messages:
            by_topic[msg.topic] = by_topic.get(msg.topic, 0) + 1
        
        by_agent = {}
        for msg in self.messages:
            by_agent[msg.from_agent] = by_agent.get(msg.from_agent, 0) + 1
        
        return {
            "total_messages": total,
            "processed": processed,
            "unprocessed": total - processed,
            "by_topic": by_topic,
            "by_sender": by_agent,
            "subscriptions": {topic: len(callbacks) for topic, callbacks in self.subscriptions.items()}
        }


# Global message bus instance
_message_bus: Optional[AgentMessageBus] = None


def get_message_bus() -> AgentMessageBus:
    """Get or create global message bus instance"""
    global _message_bus
    if _message_bus is None:
        _message_bus = AgentMessageBus()
    return _message_bus


def reset_message_bus():
    """Reset the message bus (for testing)"""
    global _message_bus
    _message_bus = None


# Common message topics
class MessageTopics:
    """Standard message topics for agent communication"""
    
    # Search-related
    NEW_PAPER_FOUND = "new_paper_found"
    SEARCH_COMPLETED = "search_completed"
    SEARCH_FAILED = "search_failed"
    
    # Citation-related
    CITATION_NEEDED = "citation_needed"
    CITATION_GENERATED = "citation_generated"
    CITATION_SUGGESTION = "citation_suggestion"
    
    # Writing-related
    DRAFT_STARTED = "draft_started"
    DRAFT_UPDATED = "draft_updated"
    DRAFT_COMPLETED = "draft_completed"
    KNOWLEDGE_GAP = "knowledge_gap"
    
    # Synthesis-related
    SYNTHESIS_COMPLETED = "synthesis_completed"
    CONTRADICTION_FOUND = "contradiction_found"
    GAP_IDENTIFIED = "gap_identified"
    
    # Review-related
    REVIEW_COMPLETED = "review_completed"
    REVISION_NEEDED = "revision_needed"
    QUALITY_ISSUE = "quality_issue"
    
    # Memory-related
    CONTEXT_UPDATED = "context_updated"
    INSIGHT_DISCOVERED = "insight_discovered"
    
    # Workflow control
    WORKFLOW_PAUSED = "workflow_paused"
    WORKFLOW_RESUMED = "workflow_resumed"
    AGENT_DECISION = "agent_decision"  # NEW: For coordinator/specialist decisions
    AGENT_STUCK = "agent_stuck"
    REROUTE_NEEDED = "reroute_needed"
