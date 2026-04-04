/**
 * Custom Hook for Streaming Chat/Workflow with SSE
 */

import { useState, useCallback } from 'react';
import { streamChatWorkflow, streamSectionDraft } from '../lib/api-client';
import type { ChatStreamPayload } from '../lib/api-client';
import { useAgentStore } from '../stores/agentStore';
import { AgentState } from '../types';

function dedupeParagraphs(text: string): string {
  const chunks = text
    .split(/\n\s*\n/)
    .map((c) => c.trim())
    .filter(Boolean);

  const seen = new Set<string>();
  const unique: string[] = [];
  for (const chunk of chunks) {
    const fingerprint = chunk.replace(/\s+/g, ' ').trim().toLowerCase();
    if (seen.has(fingerprint)) continue;
    seen.add(fingerprint);
    unique.push(chunk);
  }

  return unique.join('\n\n');
}

export function useStreamingChat() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const { setAgentState, addAgentLog, setIsStreaming: setStoreStreaming } = useAgentStore();

  const streamChat = useCallback(
    async (
      payload: ChatStreamPayload,
      onTextChunk?: (text: string) => void,
      onComplete?: (fullText: string) => void,
      onPapersFound?: (papers: any[]) => void,
      onStatusUpdate?: (phase: string, message: string) => void,  // For avatar status
      onNarration?: (narration: string) => void  // NEW: For avatar narration
    ) => {
      setIsStreaming(true);
      setStoreStreaming(true);
      setAgentState(AgentState.THINKING);
      setError(null);

      let accumulatedText = '';
      let hasReceivedNarration = false;
      let completed = false;

      try {
        for await (const event of streamChatWorkflow(payload)) {
          console.log('Stream Event:', event); // DEBUG: Trace all incoming events
          if (event.type === 'log' && event.data) {
            addAgentLog(
              event.data.source || 'System',
              event.data.message || '',
              event.data.status || 'success'
            );
          } else if (['analyzing', 'searching', 'ranking', 'generating'].includes(event.type)) {
             // Map backend lifecycle events to logs
             addAgentLog('System', event.message || event.type, 'info');
          } else if (event.type === 'found') {
             addAgentLog('System', `Found ${event.count} relevant papers.`, 'success');
             // NEW: Pass papers to component for display
             // @ts-ignore - papers property from backend
             if (onPapersFound && event.papers) {
               // @ts-ignore
               onPapersFound(event.papers);
             }
          } else if (event.type === 'thinking' && event.data) {
             // NEW: Chain-of-Thought reasoning - show model's thinking process
             console.log('🧠 Thinking event received:', event.data);
             // Optionally display thinking to user (collapsible section, debug output, etc.)
             addAgentLog('Thought', `Model reasoning: ${event.data.substring(0, 100)}...`, 'info');
          } else if (event.type === 'narration' && event.data) {
             // NEW: Handle narration event - avatar speaks this
             console.log('📢 Narration event received:', event.data);
             hasReceivedNarration = true;
             if (onNarration) {
               onNarration(event.data);
             }
             // Also add to logs as avatar message
             addAgentLog('Avatar', event.data, 'info');
          } else if (event.type === 'analyzed') {
             // Optional: log or just ignore, the 'thought' log covers the details
          } else if (event.type === 'text' && event.data) {
            accumulatedText = event.data;
            if (onTextChunk) {
              onTextChunk(event.data);
            }
          } else if (event.type === 'text_chunk' && event.data) {
            accumulatedText += event.data;
            if (onTextChunk) onTextChunk(accumulatedText);
          // @ts-ignore - status event has phase and message properties from backend
          } else if (event.type === 'status' && event.phase && event.message) {
             // Handle status events for avatar narration (analyzing, synthesizing)
             // This is the phase message (fallback if no narration event)
             if (!hasReceivedNarration) {
               addAgentLog('Avatar', event.message, 'info');
             }
             if (onStatusUpdate) {
               // @ts-ignore - phase property from backend
               onStatusUpdate(event.phase, event.message);
             }
          } else if (event.type === 'complete') {
            if (completed) {
              continue;
            }
            completed = true;
            setAgentState(AgentState.IDLE);
            
            // Check for structured answer from Mock Backend
            // @ts-ignore
            if (event.answer) {
                // Formatting Structured Answer to Markdown
                // @ts-ignore
                const ans = event.answer;
                let md = `### ${ans.summary}\n\n`;
                if (ans.key_points) {
                    md += `**Key Findings:**\n${ans.key_points.map((kp: string) => `- ${kp}`).join('\n')}\n\n`;
                }
                if (ans.explanation_steps) {
                    md += `**Reasoning:**\n${ans.explanation_steps.map((step: string, i: number) => `${i+1}. ${step}`).join('\n')}\n\n`;
                }
                 if (ans.recommended_actions) {
                    md += `**Recommendations:**\n${ans.recommended_actions.map((act: string) => `- ${act}`).join('\n')}\n\n`;
                }
                if (onComplete) onComplete(md);
            } else {
                // Standard Text Mode
              if (onComplete) onComplete(dedupeParagraphs(accumulatedText));
            }

          } else if (event.type === 'error') {
            setError(event.message || 'Unknown error');
            setAgentState(AgentState.IDLE);
          }
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Streaming failed';
        setError(errorMessage);
        addAgentLog('System', `Error: ${errorMessage}`, 'error');
        setAgentState(AgentState.IDLE);
      } finally {
        setIsStreaming(false);
        setStoreStreaming(false);
      }

      return accumulatedText;
    },
    [setAgentState, addAgentLog, setStoreStreaming]
  );

  return { streamChat, isStreaming, error };
}

export function useStreamingDraft() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const { setAgentState, addAgentLog, setIsStreaming: setStoreStreaming } = useAgentStore();

  /**
   * Sleep helper for word-by-word delays
   */
  const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

  /**
   * Split text into words with spacing preserved
   * Returns array of words that can be displayed one-by-one
   */
  const splitIntoWords = (text: string): string[] => {
    return text.split(/(\s+)/).filter(word => word.length > 0);
  };

  const streamDraft = useCallback(
    async (
      payload: ChatStreamPayload,
      onTextChunk?: (chunk: string) => void,
      onComplete?: (fullText: string) => void,
      wordDelay: number = 20 // milliseconds between words
    ) => {
      setIsStreaming(true);
      setStoreStreaming(true);
      setAgentState(AgentState.SPEAKING);
      setError(null);

      let accumulatedText = '';
      const wordBuffer: string[] = [];

      try {
        // Collect all text first in wordBuffer
        for await (const event of streamSectionDraft(payload)) {
          if (event.type === 'start') {
            addAgentLog('Writer', event.message || 'Starting draft...', 'pending');
          } else if (event.type === 'log' && event.data) {
            addAgentLog(
              // @ts-ignore - streamed reviewer logs use backend-provided source names
              event.data.source || 'Reviewer',
              // @ts-ignore - streamed reviewer logs include message/status payloads
              event.data.message || '',
              // @ts-ignore
              event.data.status || 'info'
            );
          } else if (event.type === 'text_chunk' && event.data) {
            // Add chunk words to buffer for word-by-word rendering
            const words = splitIntoWords(event.data);
            wordBuffer.push(...words);
          } else if (event.type === 'complete') {
            if (event.data) {
              accumulatedText = event.data;
            }
            addAgentLog('Writer', 'Draft completed', 'success');
            setAgentState(AgentState.IDLE);
            if (onComplete) {
              onComplete(accumulatedText);
            }
          } else if (event.type === 'error') {
            setError(event.message || 'Unknown error');
            setAgentState(AgentState.IDLE);
          }
        }

        // If we were able to collect text, stream it word-by-word
        // Otherwise use accumulated from chunks
        if (wordBuffer.length === 0 && accumulatedText) {
          const words = splitIntoWords(accumulatedText);
          wordBuffer.push(...words);
        }

        // Stream words one-by-one with delay for visual effect
        accumulatedText = '';
        for (const word of wordBuffer) {
          accumulatedText += word;
          if (onTextChunk) {
            onTextChunk(accumulatedText);
          }
          await sleep(wordDelay);
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Streaming failed';
        setError(errorMessage);
        addAgentLog('System', `Error: ${errorMessage}`, 'error');
        setAgentState(AgentState.IDLE);
      } finally {
        setIsStreaming(false);
        setStoreStreaming(false);
      }

      return accumulatedText;
    },
    [setAgentState, addAgentLog, setStoreStreaming]
  );

  return { streamDraft, isStreaming, error };
}
