/**
 * API Client for ScholarFlow Backend
 * Axios-based client with typed API functions
 */

import axios from 'axios';
import { ProjectType } from '../types';
import type { 
  Project, 
  ProjectAsset, 
  Paper,
  OutlineSection,
  LibraryPage
} from '../types';

// Create axios instance
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 seconds
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// ===== PROJECT ENDPOINTS =====

export interface ProjectCreatePayload {
  title: string;
  description: string;
  mode: 'RESEARCH' | 'MANUSCRIPT';
  project_kind?: 'LIT_REVIEW' | 'EXPERIMENTAL' | 'MANUSCRIPT';
  methodology?: string;
  findings?: string;
}

const apiRootUrl = () => (apiClient.defaults.baseURL || '').replace(/\/api\/v1\/?$/, '');

const toProjectType = (projectKind?: string | null, mode?: string | null): ProjectType => {
  if (
    projectKind === ProjectType.LIT_REVIEW
    || projectKind === ProjectType.EXPERIMENTAL
    || projectKind === ProjectType.MANUSCRIPT
  ) {
    return projectKind as ProjectType;
  }
  return mode === 'RESEARCH' ? ProjectType.LIT_REVIEW : ProjectType.MANUSCRIPT;
};

const mapResearchAssetType = (assetType?: string): ProjectAsset['type'] => {
  switch (assetType) {
    case 'my_figure':
      return 'image';
    case 'my_code':
      return 'code';
    default:
      return 'data';
  }
};

const normalizeAssetUrl = (filePath: string) => {
  const normalized = filePath.replace(/\\/g, '/');
  const suffix = normalized.split('uploads/').pop() || '';
  return `${apiRootUrl()}/uploads/${suffix}`;
};

export const fetchProjects = async (): Promise<Project[]> => {
  const { data } = await apiClient.get('/projects');
  // Map backend response to frontend Project type
  return data.map((p: any) => ({
    id: p.id,
    title: p.title,
    description: p.description,
    type: toProjectType(p.project_kind, p.mode),
    lastModified: new Date(p.updated_at), // Convert string to Date
    wordCount: 0, // Default as backend doesn't send this yet
    papers: [], // Default
    files: [], // Default
    assets: [], // Default
    methodology: p.methodology,
    findings: p.findings
  }));
};

export const fetchProject = async (id: string): Promise<Project> => {
  const { data } = await apiClient.get(`/projects/${id}`);
  const [labAssetsResult, researchAssetsResult] = await Promise.allSettled([
    fetchLabAssets(id),
    fetchResearchAssets(id)
  ]);

  const assets: ProjectAsset[] = [
    ...(labAssetsResult.status === 'fulfilled' ? labAssetsResult.value : []),
    ...(researchAssetsResult.status === 'fulfilled' ? researchAssetsResult.value : [])
  ];

  return {
    id: data.id,
    title: data.title,
    description: data.description,
    type: toProjectType(data.project_kind, data.mode),
    lastModified: new Date(data.updated_at),
    wordCount: 0,
    papers: (data.library_items || []).map((p: any) => ({
        id: p.id,
        title: p.title,
        authors: p.authors || [],
        year: p.year,
        summary: p.abstract || '',
        tags: [],
        pdfUrl: p.pdf_path
            ? `${(apiClient.defaults.baseURL || '').replace(/\/api\/v1\/?$/, '')}/uploads/${p.pdf_path.split(/[/\\]/).pop()}`
            : (p.url || (p.arxiv_id ? `${apiClient.defaults.baseURL}/papers/pdf/proxy/${p.arxiv_id}` : undefined))
    })),
    files: [],
    assets,
    methodology: data.methodology,
    findings: data.findings
  };
};

export const fetchLibraryPage = async (
  projectId: string,
  page: number = 1,
  limit: number = 10
): Promise<LibraryPage> => {
  const { data } = await apiClient.get(`/papers/library`, {
    params: { project_id: projectId, page, limit }
  });

  const rootUrl = (apiClient.defaults.baseURL || '').replace(/\/api\/v1\/?$/, '');

  return {
    items: (data.items || []).map((p: any) => ({
      id: p.id,
      title: p.title,
      authors: p.authors || [],
      year: p.year,
      summary: p.abstract || '',
      tags: [],
      pdfUrl: p.pdf_path
        ? `${rootUrl}/uploads/${p.pdf_path.split(/[/\\]/).pop()}`
        : (p.url || (p.arxiv_id ? `${apiClient.defaults.baseURL}/papers/pdf/proxy/${p.arxiv_id}` : undefined))
    })),
    total: data.total || 0,
    page: data.page || page,
    limit: data.limit || limit,
    pages: data.pages || 1
  };
};

export const createProject = async (payload: ProjectCreatePayload): Promise<Project> => {
  const { data } = await apiClient.post('/projects', payload);
  // Map backend response
  return {
    id: data.id,
    title: data.title,
    description: data.description,
    type: toProjectType(data.project_kind, data.mode),
    lastModified: new Date(data.created_at), // Use created_at for new projects
    wordCount: 0,
    papers: [],
    files: [],
    assets: [],
    methodology: data.methodology,
    findings: data.findings
  };
};

export const generateProject = async (paperIds: string[]): Promise<Project> => {
  const { data } = await apiClient.post('/projects/generate', { paper_ids: paperIds });
  return {
    id: data.id,
    title: data.title,
    description: data.description,
    type: toProjectType(data.project_kind, data.mode),
    lastModified: new Date(data.created_at),
    wordCount: 0,
    papers: [],
    files: [],
    assets: [],
    methodology: data.methodology,
    findings: data.findings
  };
};

export const deleteProject = async (id: string): Promise<void> => {
  await apiClient.delete(`/projects/${id}`);
};

// ===== LAB ASSET ENDPOINTS =====

export const uploadLabAsset = async (
  projectId: string,
  file: File,
  name: string,
  assetType: 'image' | 'data' | 'code'
): Promise<ProjectAsset> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('name', name);
  formData.append('asset_type', assetType);

  const { data } = await apiClient.post<any>(
    `/lab/projects/${projectId}/upload`,
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
    }
  );

  // Map backend response to frontend format
  return {
    id: data.id,
    name: data.name,
    type: data.asset_type,
    kind: 'lab',
    url: data.file_path ? normalizeAssetUrl(data.file_path) : undefined,
    aiDescription: data.ai_description
  };
};

export const fetchLabAssets = async (projectId: string): Promise<ProjectAsset[]> => {
  const { data } = await apiClient.get<any[]>(`/lab/projects/${projectId}`);

  return data.map(asset => {
    return {
      id: asset.id,
      name: asset.name,
      type: asset.asset_type,
      kind: 'lab',
      url: asset.file_path ? normalizeAssetUrl(asset.file_path) : undefined,
      aiDescription: asset.ai_description
    };
  });
};

export const uploadResearchAsset = async (
  projectId: string,
  file: File,
  name: string,
  assetType: 'experiment_data' | 'my_figure' | 'my_code' | 'my_table' | 'methodology',
  options?: {
    description?: string;
    methodologyNote?: string;
    sectionHint?: string;
  }
): Promise<ProjectAsset> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('name', name);
  formData.append('asset_type', assetType);
  if (options?.description) formData.append('description', options.description);
  if (options?.methodologyNote) formData.append('methodology_note', options.methodologyNote);
  if (options?.sectionHint) formData.append('section_hint', options.sectionHint);

  const { data } = await apiClient.post<any>(
    `/research/projects/${projectId}/assets/upload`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );

  return {
    id: data.id,
    name: data.name,
    type: mapResearchAssetType(data.asset_type),
    kind: 'research',
    researchAssetType: data.asset_type,
    description: data.description,
    methodologyNote: data.methodology_note,
    sectionHint: data.section_hint,
    aiDescription: data.ai_analysis,
    url: data.file_path ? normalizeAssetUrl(data.file_path) : undefined,
  };
};

export const fetchResearchAssets = async (projectId: string): Promise<ProjectAsset[]> => {
  const { data } = await apiClient.get<any[]>(`/research/projects/${projectId}/assets`);
  return data.map(asset => ({
    id: asset.id,
    name: asset.name,
    type: mapResearchAssetType(asset.asset_type),
    kind: 'research',
    researchAssetType: asset.asset_type,
    description: asset.description,
    methodologyNote: asset.methodology_note,
    sectionHint: asset.section_hint,
    aiDescription: asset.ai_analysis,
    url: asset.file_path ? normalizeAssetUrl(asset.file_path) : undefined,
  }));
};

export const reanalyzeAsset = async (
  assetId: string,
  customPrompt?: string
): Promise<{ asset_id: string; ai_description: string }> => {
  const formData = new FormData();
  if (customPrompt) {
    formData.append('custom_prompt', customPrompt);
  }

  const { data } = await apiClient.post(
    `/lab/assets/${assetId}/reanalyze`,
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
    }
  );

  return data;
};

export const deleteLabAsset = async (assetId: string): Promise<void> => {
  await apiClient.delete(`/lab/assets/${assetId}`);
};

// ===== CHAT/WORKFLOW ENDPOINTS =====

export interface ChatStreamPayload {
  project_id: string;
  session_id?: string;
  message: string;
  selected_paper_ids: string[];
  lab_asset_ids: string[];
  research_asset_ids?: string[];
  current_section?: string;
}

/**
 * Stream chat workflow using Server-Sent Events
 * Returns an async generator that yields events
 */
export async function* streamChatWorkflow(
  payload: ChatStreamPayload
): AsyncGenerator<{
  type: string; // broadened from specific union to allow new event types
  data?: any;
  message?: string;
  count?: number; // added for 'found' event
  answer?: any;   // added for mock answer
}> {
  const response = await fetch(`${apiClient.defaults.baseURL}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by a blank line.
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      for (const rawEvent of events) {
        const dataLines = rawEvent
          .split('\n')
          .filter((line) => line.startsWith('data: '))
          .map((line) => line.slice(6));

        if (!dataLines.length) continue;

        const dataText = dataLines.join('\n');
        try {
          const data = JSON.parse(dataText);
          yield data;
        } catch (e) {
          console.warn('Failed to parse SSE data:', dataText);
        }
      }
    }

    // Flush any trailing buffered event
    if (buffer.trim()) {
      const dataLines = buffer
        .split('\n')
        .filter((line) => line.startsWith('data: '))
        .map((line) => line.slice(6));
      if (dataLines.length) {
        const dataText = dataLines.join('\n');
        try {
          const data = JSON.parse(dataText);
          yield data;
        } catch {
          // Ignore trailing partial event
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export const fetchChatHistory = async (projectId: string, sessionId?: string): Promise<any[]> => {
    try {
        const url = sessionId 
            ? `/projects/${projectId}/chat?session_id=${sessionId}`
            : `/projects/${projectId}/chat`;
            
        const { data } = await apiClient.get<any[]>(url);
        return data.map(msg => ({
            id: `msg-${Math.random()}`, // Backend doesn't store IDs per message in JSON yet
            role: msg.role === 'user' ? 'user' : 'agent',
            content: msg.content,
            sources: msg.sources || [],
            timestamp: msg.timestamp
        }));
    } catch (error) {
        console.error('Error fetching chat history:', error);
        return [];
    }
};

export const fetchChatSessions = async (projectId: string): Promise<import('../types').ChatSession[]> => {
    try {
        const { data } = await apiClient.get<import('../types').ChatSession[]>(`/projects/${projectId}/sessions`);
        return data;
    } catch (error) {
        console.error('Error fetching chat sessions:', error);
        return [];
    }
};

export const createChatSession = async (projectId: string, title: string): Promise<import('../types').ChatSession | null> => {
    try {
        const { data } = await apiClient.post<import('../types').ChatSession>(`/projects/${projectId}/sessions`, { title });
        return data;
    } catch (error) {
        console.error('Error creating chat session:', error);
        return null;
    }
};

/**
 * Stream section drafting
 */
export async function* streamSectionDraft(
  payload: ChatStreamPayload
): AsyncGenerator<{
  type: 'start' | 'text_chunk' | 'complete' | 'error' | 'log';
  data?: string;
  message?: string;
}> {
  const response = await fetch(`${apiClient.defaults.baseURL}/chat/draft-section`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      for (const rawEvent of events) {
        const dataLines = rawEvent
          .split('\n')
          .filter((line) => line.startsWith('data: '))
          .map((line) => line.slice(6));
        if (!dataLines.length) continue;

        const dataText = dataLines.join('\n');
        try {
          const data = JSON.parse(dataText);
          yield data;
        } catch (e) {
          console.warn('Failed to parse SSE data:', dataText);
        }
      }
    }

    if (buffer.trim()) {
      const dataLines = buffer
        .split('\n')
        .filter((line) => line.startsWith('data: '))
        .map((line) => line.slice(6));
      if (dataLines.length) {
        const dataText = dataLines.join('\n');
        try {
          const data = JSON.parse(dataText);
          yield data;
        } catch {
          // Ignore trailing partial event
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// ===== MOCK/PLACEHOLDER ENDPOINTS =====
// These will be implemented as backend grows

export const searchPapers = async (
  query: string,
  maxResults: number = 10
): Promise<Paper[]> => {
  try {
    const { data } = await apiClient.get('/papers/search', {
      params: {
        query,
        max_results: maxResults
      }
    });
    
    // Map backend PaperSearchResult to frontend Paper type
    return data.results.map((paper: any) => ({
      id: paper.arxiv_id || paper.doi || `paper-${Math.random().toString(36).substr(2, 9)}`,
      title: paper.title,
      authors: paper.authors || [],
      year: paper.year || new Date().getFullYear(),
      summary: paper.abstract || '',
      tags: [],
      pdfUrl: paper.url
    }));
  } catch (error) {
    console.error('Error searching papers:', error);
    // Return empty array on error instead of throwing
    return [];
  }
};

export const generateOutline = async (
  projectId: string,
  paperIds: string[],
  assetIds: string[],
  style: string = 'IEEE'
): Promise<OutlineSection[]> => {
  try {
    const { data } = await apiClient.post('/research/outline', {
      project_id: projectId,
      paper_ids: paperIds,
      asset_ids: assetIds,
      style
    }, {
      timeout: 120000
    });
    
    return (data.sections || []).map((section: any, index: number) => ({
      id: section.id || `section-${Date.now()}-${index}`,
      title: section.title || 'Section',
      description: section.description || '',
      status: section.status || 'pending',
      relevantPaperIds: section.relevantPaperIds || section.relevant_paper_ids || [],
      recommendedAssetTypes: section.recommendedAssetTypes || section.recommended_asset_types || []
    }));
  } catch (error) {
    console.error('Error generating outline:', error);
    throw error;
  }
};

export const uploadPaper = async (
  projectId: string,
  file: File
): Promise<any> => {
  const formData = new FormData();
  formData.append('file', file);

  const { data } = await apiClient.post(
    `/papers/upload?project_id=${projectId}`,
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
    }
  );

  return data;
};

export const addPaperToLibrary = async (
  projectId: string,
  paper: Paper
): Promise<any> => {
  try {
    const { data } = await apiClient.post(
      `/papers/add-to-library?project_id=${projectId}`,
      {
        id: paper.id,
        title: paper.title,
        authors: paper.authors,
        year: paper.year,
        summary: paper.summary,
        pdfUrl: paper.pdfUrl,
        arxiv_id: paper.id.includes('arxiv') ? paper.id : undefined,
        doi: paper.id.includes('doi') ? paper.id : undefined
      }
    );
    return data;
  } catch (error) {
    console.error('Error adding paper to library:', error);
    throw error;
  }
};

export const fetchPaper = async (id: string): Promise<Paper> => {
   try {
       const { data } = await apiClient.get<any>(`/papers/${id}`);
       
       // Construct PDF URL
       let pdfUrl = '';
       
       if (data.pdf_path) {
           // Local PDF file
           const filename = data.pdf_path.split('\\').pop().split('/').pop();
           const rootUrl = (apiClient.defaults.baseURL || '').replace(/\/api\/v1\/?$/, '');
           pdfUrl = `${rootUrl}/uploads/${filename}`;
       } else if (data.url) {
           // External URL (ArXiv, etc.)
           pdfUrl = data.url;
       } else if (data.arxiv_id) {
           // Use backend proxy to bypass CORS
           const rootUrl = (apiClient.defaults.baseURL || '').replace(/\/api\/v1\/?$/, '');
           const apiRoot = (apiClient.defaults.baseURL || 'http://localhost:8000/api/v1');
           pdfUrl = `${apiRoot}/papers/pdf/proxy/${data.arxiv_id}`;
       }
       
       return {
            id: data.id,
            title: data.title,
            authors: Array.isArray(data.authors) ? data.authors : [],
            year: data.year,
            summary: data.abstract || '',
            tags: [],
            pdfUrl: pdfUrl
       };
   } catch (error) {
       console.warn(`Failed to fetch paper ${id} from API:`, error);
       // Fallback
       return {
            id: id,
            title: 'Unknown Paper',
            authors: [],
            year: 2024,
            summary: 'Could not load paper details.',
            tags: [],
            pdfUrl: '' 
       };
   }
};

// ===== DRAFT PERSISTENCE =====

export const saveDraft = async (
  projectId: string,
  outline?: any[] | null,
  content?: string | null
): Promise<{ id: string; word_count: number; updated_at: string }> => {
  const { data } = await apiClient.post(`/research/draft/save`, {
    project_id: projectId,
    outline,
    content
  });
  return data;
};

export const loadDraft = async (projectId: string): Promise<{
  id: string | null;
  project_id: string;
  outline: any[] | null;
  full_content: string | null;
  word_count: number;
  created_at: string | null;
  updated_at: string | null;
}> => {
  const { data } = await apiClient.get(`/research/draft/load/${projectId}`);
  return data;
};

