
export enum AppMode {
  RESEARCH = 'RESEARCH',
  STUDIO = 'STUDIO'
}

export enum ViewState {
  DASHBOARD = 'DASHBOARD',
  DISCOVERY = 'DISCOVERY',
  READING = 'READING',
  STUDIO = 'STUDIO'
}

export enum AgentState {
  IDLE = 'IDLE',
  LISTENING = 'LISTENING',
  THINKING = 'THINKING',
  SPEAKING = 'SPEAKING'
}

export interface Paper {
  id: string;
  title: string;
  authors: string[];
  year: number;
  summary: string;
  tags: string[];
  pdfUrl?: string;
}

export interface LibraryPage {
  items: Paper[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface Citation {
  paperId: string;
  pageNumber?: number;
  textSnippet?: string;
  citationKey?: string; // e.g., "[1]" or "\cite{paper1}"
}

export interface AgentLog {
  id: string;
  source: 'Router' | 'Ranker' | 'Synthesizer' | 'Co-Author' | 'System' | 'Thought' | 'Avatar' | 'Writer' | 'Reviewer';
  message: string;
  timestamp: Date;
  status?: 'pending' | 'success' | 'error' | 'info' | 'warning';
  metadata?: any; 
}

export interface Note {
  id: string;
  content: string;
  type: 'text' | 'citation';
  citationId?: string;
}

export enum ProjectType {
  LIT_REVIEW = 'LIT_REVIEW',
  EXPERIMENTAL = 'EXPERIMENTAL',
  MANUSCRIPT = 'MANUSCRIPT'
}

export interface ProjectAsset {
  id: string;
  name: string;
  type: 'image' | 'data' | 'code';
  url?: string;
  kind?: 'lab' | 'research';
  researchAssetType?: string;
  description?: string;
  methodologyNote?: string;
  sectionHint?: string;
  aiDescription?: string;
}

export interface PendingProjectAsset {
  name: string;
  type: 'image' | 'data' | 'code';
  file: File;
  kind?: 'lab' | 'research';
  description?: string;
  methodologyNote?: string;
  sectionHint?: string;
}

export interface ProjectFile {
  id: string;
  name: string;
  type: 'file' | 'folder';
  content: string; // Empty string for folders
  parentId?: string; // For nesting, null/undefined = root
  extension?: string; // .tex, .bib, .txt
}

export interface OutlineSection {
  id: string;
  title: string;
  description: string; // Internal prompt for the agent
  status: 'pending' | 'drafting' | 'completed';
  relevantPaperIds: string[]; // RAG context
  recommendedAssetTypes?: ('image' | 'data')[]; // New field for Co-Author suggestions
}

export interface Project {
  id: string;
  title: string;
  description: string;
  type: ProjectType;
  lastModified: Date;
  papers: Paper[]; // Valid Paper Objects
  files: ProjectFile[]; // Overleaf-like file system
  assets: ProjectAsset[];
  wordCount: number;
  // New fields for context
  methodology?: string;
  findings?: string;
  outline?: OutlineSection[];
}

// New Interface for Chat-based Discovery
export interface ResearchTurn {
  id: string;
  role: 'user' | 'agent';
  query?: string;
  intent?: 'QUESTION' | 'KEYWORD_SEARCH';
  status: 'idle' | 'thinking' | 'searching' | 'synthesizing' | 'completed';
  logs: string[]; // e.g. "Searching ArXiv...", "Reading 3 papers..."
  answer?: string;
  sources?: Paper[];
}

export interface ChatSession {
  id: string;
  title: string;
  updated_at: string;
  message_count: number;
}
