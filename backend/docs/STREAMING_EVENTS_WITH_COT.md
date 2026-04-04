"""
Schema/Type definitions for thinking event streaming

Add this to types.ts for frontend typing support
"""

# Python TypeScript type definition (for reference)

# Interface AgentLog extends with thinking field:
"""
interface AgentLog {
  timestamp?: string;
  step: string;
  source: 'Clarifier' | 'Search' | 'Ranker' | 'ResearchCoordinator' | 'Avatar' | 'Writer' | 'Reviewer' | 'ProactiveAgent' | string;
  message: string;
  status: 'processing' | 'completed' | 'warning' | 'error' | 'info';
  metadata?: any;
}

// Event types 
interface StreamEvent {
  type: 'thinking' | 'narration' | 'text_chunk' | 'status' | 'found' | 'log' | 'complete' | 'error' | 'start';
  data?: string;
  message?: string;
  phase?: string;
  count?: number;
  papers?: any[];
  answer?: any;
}

// Thinking event: Shows model's reasoning process
interface ThinkingEvent {
  type: 'thinking';
  data: string;  // The thinking/reasoning text
}

// Narration event: What avatar says (conversational)
interface NarrationEvent {
  type: 'narration';
  data: string;
}

// Text chunk event: Formal written content streamed word-by-word
interface TextChunkEvent {
  type: 'text_chunk';
  data: string;
}

// Status event: Processing status updates
interface StatusEvent {
  type: 'status';
  phase?: string;    // 'analyzing', 'synthesizing', etc.
  message: string;
}
"""

# ===== BACKEND PYTHON SIDE =====
# The backend now returns events like:

cot_example_events = [
    # If enabled and thinking present:
    {
        "type": "thinking",
        "data": """1. Query Understanding: User asking about transformers and attention
2. Paper relevance: Both papers [1,2] directly cover attention mechanisms
3. Evidence synthesis: Papers agree on self-attention mechanism structure
4. Confidence: High - foundational papers on the topic
5. Strategy: Explain self-attention first, then variants"""
    },
    
    # Avatar narration (always sent if present)
    {
        "type": "narration",
        "data": "So I found these fascinating papers on how transformers use attention to process sequences..."
    },
    
    # Status
    {
        "type": "status",
        "phase": "synthesizing",
        "message": "Putting together the key findings..."
    },
    
    # Formal content streamed word by word
    {
        "type": "text_chunk",
        "data": "Transformers"
    },
    {
        "type": "text_chunk",
        "data": " use"
    },
    # ... more chunks
]
