/**
 * Project Store - Active Project State
 * Manages active project and paper content directly.
 * No virtual file-system — paper text lives in `paperContent`.
 */

import { create } from 'zustand';
import type { Project, ProjectFile } from '../types';
import { EMPTY_MARKDOWN } from '../constants';

interface ProjectStore {
  activeProject: Project | null;
  paperContent: string;
  activeFileId: string;
  selectedContextIds: Set<string>;
  historyStack: string[];
  redoStack: string[];

  setActiveProject: (project: Project | null) => void;
  updateActiveProject: (updates: Partial<Project>) => void;
  setActiveFileId: (id: string) => void;
  toggleContext: (id: string) => void;
  clearContext: () => void;

  setPaperContent: (content: string) => void;
  updateSection: (sectionTitle: string, content: string, mode: 'append' | 'replace') => void;

  updateFileContent: (fileId: string, content: string) => void;
  addFile: (file: ProjectFile) => void;
  deleteFile: (fileId: string) => void;

  pushHistory: (content: string) => void;
  undo: () => string | null;
  redo: () => string | null;

  reset: () => void;
}

const initialState = {
  activeProject: null,
  paperContent: EMPTY_MARKDOWN,
  activeFileId: 'main.md',
  selectedContextIds: new Set<string>(),
  historyStack: [],
  redoStack: [],
};

const normalizeHeading = (value: string) =>
  value
    .toLowerCase()
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

const HEADING_ALIASES: Record<string, string[]> = {
  introduction: ['introduction', 'background', 'related work', 'literature review'],
  methodology: ['methodology', 'methods', 'materials and methods', 'approach', 'proposed method'],
  results: ['results', 'experiments', 'experimental results', 'evaluation'],
  discussion: ['discussion', 'analysis', 'interpretation'],
  conclusion: ['conclusion', 'conclusions', 'future work'],
  references: ['references', 'bibliography', 'works cited', 'sources'],
};

const getHeadingCandidates = (sectionTitle: string): string[] => {
  const normalized = normalizeHeading(sectionTitle);
  for (const aliases of Object.values(HEADING_ALIASES)) {
    if (aliases.includes(normalized)) return aliases;
  }
  return [normalized];
};

type HeadingMatch = {
  headingStart: number;
  bodyStart: number;
  nextHeadingStart: number;
};

const findHeadingRange = (markdown: string, sectionTitle: string): HeadingMatch | null => {
  const headingRegex = /^(#{2,3})\s+(.+)$/gm;
  const headings: Array<{ title: string; start: number; end: number }> = [];
  let match: RegExpExecArray | null;

  while ((match = headingRegex.exec(markdown)) !== null) {
    headings.push({
      title: match[2].trim(),
      start: match.index,
      end: headingRegex.lastIndex,
    });
  }

  if (headings.length === 0) return null;

  const candidates = new Set(getHeadingCandidates(sectionTitle));
  const index = headings.findIndex((h) => candidates.has(normalizeHeading(h.title)));
  if (index === -1) return null;

  const current = headings[index];
  const next = headings[index + 1];
  return {
    headingStart: current.start,
    bodyStart: current.end,
    nextHeadingStart: next ? next.start : markdown.length,
  };
};

export const useProjectStore = create<ProjectStore>((set, get) => ({
  ...initialState,

  setActiveProject: (project) =>
    set({
      activeProject: project ?? null,
      paperContent: EMPTY_MARKDOWN,
      activeFileId: 'main.md',
      selectedContextIds: new Set(),
      historyStack: [],
      redoStack: [],
    }),

  updateActiveProject: (updates) =>
    set((state) => ({
      activeProject: state.activeProject
        ? { ...state.activeProject, ...updates }
        : null,
    })),

  setActiveFileId: (id) => set({ activeFileId: id }),

  toggleContext: (id) =>
    set((state) => {
      const newSet = new Set(state.selectedContextIds);
      if (newSet.has(id)) newSet.delete(id);
      else newSet.add(id);
      return { selectedContextIds: newSet };
    }),

  clearContext: () => set({ selectedContextIds: new Set() }),

  setPaperContent: (content) => set({ paperContent: content }),

  updateSection: (sectionTitle, content, mode) =>
    set((state) => {
      const currentContent = state.paperContent;
      const target = findHeadingRange(currentContent, sectionTitle);
      const incoming = (content || '').trim();

      let newContent = currentContent;

      if (target) {
        const existingBody = currentContent
          .slice(target.bodyStart, target.nextHeadingStart)
          .replace(/^\n+|\n+$/g, '');

        const replacementBody = mode === 'replace'
          ? incoming
          : (existingBody.trim().endsWith(incoming)
              ? existingBody
              : `${existingBody}${existingBody ? '\n\n' : ''}${incoming}`);

        newContent =
          currentContent.slice(0, target.bodyStart)
          + `\n${replacementBody}\n\n`
          + currentContent.slice(target.nextHeadingStart).replace(/^\n+/, '');
      } else {
        const referencesTarget = findHeadingRange(currentContent, 'references');
        const isReferencesUpdate = getHeadingCandidates(sectionTitle).includes('references');
        const insertBlock = `## ${sectionTitle}\n${incoming}\n\n`;

        if (referencesTarget && !isReferencesUpdate) {
          newContent =
            currentContent.slice(0, referencesTarget.headingStart).replace(/\n+$/, '\n\n')
            + insertBlock
            + currentContent.slice(referencesTarget.headingStart).replace(/^\n+/, '');
        } else {
          newContent = currentContent.replace(/\n+$/, '\n\n') + insertBlock;
        }
      }

      return { paperContent: newContent };
    }),

  updateFileContent: (fileId, content) =>
    set((state) => {
      if (!state.activeProject) return state;
      const updatedFiles = state.activeProject.files.map((f) =>
        f.id === fileId ? { ...f, content } : f
      );
      return { activeProject: { ...state.activeProject, files: updatedFiles } };
    }),

  addFile: (file) =>
    set((state) => {
      if (!state.activeProject) return state;
      return {
        activeProject: {
          ...state.activeProject,
          files: [...state.activeProject.files, file],
        },
      };
    }),

  deleteFile: (fileId) =>
    set((state) => {
      if (!state.activeProject) return state;
      const updatedFiles = state.activeProject.files.filter(
        (f) => f.id !== fileId && f.parentId !== fileId
      );
      return {
        activeProject: { ...state.activeProject, files: updatedFiles },
        activeFileId: state.activeFileId === fileId ? 'main.md' : state.activeFileId,
      };
    }),

  pushHistory: (content) =>
    set((state) => ({
      historyStack: [...state.historyStack, content].slice(-50),
      redoStack: [],
    })),

  undo: () => {
    const state = get();
    if (state.historyStack.length === 0) return null;
    const previous = state.historyStack[state.historyStack.length - 1];
    set({
      historyStack: state.historyStack.slice(0, -1),
      redoStack: [...state.redoStack, state.paperContent],
    });
    return previous;
  },

  redo: () => {
    const state = get();
    if (state.redoStack.length === 0) return null;
    const next = state.redoStack[state.redoStack.length - 1];
    set({
      historyStack: [...state.historyStack, state.paperContent],
      redoStack: state.redoStack.slice(0, -1),
    });
    return next;
  },

  reset: () => set(initialState),
}));
