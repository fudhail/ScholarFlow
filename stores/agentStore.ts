/**
 * Agent Store - AI Agent State Management
 * Manages agent state, logs, and pending messages
 */

import { create } from 'zustand';
import { AgentState, type AgentLog } from '../types';

interface AgentStore {
  // State
  agentState: AgentState;
  agentLogs: AgentLog[];
  pendingMessage: string | null;
  isStreaming: boolean;

  // Actions
  setAgentState: (state: AgentState) => void;
  addAgentLog: (source: AgentLog['source'], message: string, status?: AgentLog['status']) => void;
  setPendingMessage: (message: string | null) => void;
  setIsStreaming: (streaming: boolean) => void;

  // Avatar Speech (Queue System)
  speechQueue: string[];
  isAvatarSpeaking: boolean;
  queueAvatarSpeech: (message: string) => void;
  setAvatarSpeaking: (speaking: boolean) => void;
  shiftSpeechQueue: () => void;
  
  // Deprecated/Legacy compatibility (optional, or just remove)
  avatarMessageToSpeak: string | null; 
  setAvatarMessageToSpeak: (message: string | null) => void;

  clearLogs: () => void;
  reset: () => void;
}

const initialState = {
  agentState: AgentState.IDLE,
  agentLogs: [],
  pendingMessage: null,
  isStreaming: false,
  speechQueue: [],
  isAvatarSpeaking: false,
  avatarMessageToSpeak: null,
};

export const useAgentStore = create<AgentStore>((set) => ({
  ...initialState,

  setAgentState: (state) => set({ agentState: state }),

  addAgentLog: (source, message, status = 'success') =>
    set((state) => {
      const last = state.agentLogs[state.agentLogs.length - 1];
      if (
        last
        && last.source === source
        && last.message === message
        && last.status === (status as AgentLog['status'])
      ) {
        return state;
      }

      return {
        agentLogs: [
          ...state.agentLogs,
          {
            id: Date.now().toString() + Math.random(),
            source,
            message,
            timestamp: new Date(),
            status: status as AgentLog['status'],
          },
        ],
      };
    }),

  setPendingMessage: (message) => set({ pendingMessage: message }),

  setIsStreaming: (streaming) => set({ isStreaming: streaming }),

  // Avatar Speech Queue
  queueAvatarSpeech: (message) => set((state) => ({ 
    speechQueue: [...state.speechQueue, message] 
  })),
  
  setAvatarSpeaking: (speaking) => set({ isAvatarSpeaking: speaking }),
  
  shiftSpeechQueue: () => set((state) => {
    const newQueue = [...state.speechQueue];
    newQueue.shift();
    return { speechQueue: newQueue };
  }),

  // Legacy support (redirects to queue)
  setAvatarMessageToSpeak: (message) => set((state) => {
    if (!message) return {}; // Ignore null clear calls as queue handles lifecycle
    return { speechQueue: [...state.speechQueue, message] };
  }),

  clearLogs: () => set({ agentLogs: [] }),

  reset: () => set(initialState),
}));
