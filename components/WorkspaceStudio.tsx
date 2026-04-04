import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
    Download, RefreshCw, Maximize, Minimize, Code2,
    Printer, Check, PlusCircle, Trash2,
    LayoutTemplate, ChevronDown, ChevronLeft, ChevronRight, Undo2, Redo2,
    FileText,
} from 'lucide-react';
import { Project } from '../types';
import Editor from '@monaco-editor/react';
import { useToastStore } from '../stores/toastStore';
import { saveDraft, loadDraft } from '../lib/api-client';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import TextAlign from '@tiptap/extension-text-align';
import Underline from '@tiptap/extension-underline';
import Placeholder from '@tiptap/extension-placeholder';
import TurndownService from 'turndown';
import { marked } from 'marked';

// IEEE template file removed - using inline fallback
const defaultIeeeTemplate = null;

const turndownService = new TurndownService({ headingStyle: 'atx' });

const exportPdfEndpoint = `${(import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1').replace(/\/$/, '')}/export/pdf`;

const sanitizeExportFilename = (value: string) =>
    (value || 'Manuscript')
        .replace(/[<>:"/\\|?*\x00-\x1F]/g, '')
        .replace(/\s+/g, '_')
        .slice(0, 120) || 'Manuscript';

const getTemplateStorageKey = (projectId?: string | null) => `workspace-studio.template.${projectId || 'default'}`;


// ─── A4 / page geometry ───────────────────────────────────────────────────────
const A4_W_MM = 210;
const A4_H_MM = 297;
const PAGE_GAP_MM = 12; // Gap between pages (visual separator)

// Springer LNCS exact margins (mm)
const SPR_HDR_MM = 15;
const SPR_MT_MM = 49;
const SPR_MB_MM = 27;
const SPR_MS_MM = 25;
const SPR_BODY_H = A4_H_MM - SPR_MT_MM - SPR_MB_MM;

// IEEE Conference exact margins (mm) for A4
const IEEE_HDR_MM = 14;
const IEEE_MT_MM = 19;     // 0.75 in top margin
const IEEE_MB_MM = 25.4;   // 1.0 in bottom margin (Standard for IEEE conference A4)
const IEEE_MS_MM = 14.32;  // 0.56 in side margins
const IEEE_BODY_H = A4_H_MM - IEEE_MT_MM - IEEE_MB_MM;
const IEEE_COL_GAP = 4.22; // 0.17 in spacing between columns
const GAP_MM = 10;         // Gap between page sheets

// PX per MM at 96dpi
const PX_PER_MM = 96 / 25.4;

// ─── Interfaces ───────────────────────────────────────────────────────────────
interface Block {
    id: string;
    type: 'title' | 'authors' | 'abstract' | 'keywords' | 'section';
    level?: number;
    heading?: string;
    content: string;
}

type SpecialBlockKind = 'equation' | 'figure' | 'table';
const SPECIAL_HEADINGS: Record<SpecialBlockKind, string> = {
    equation: '[Equation]',
    figure: '[Figure]',
    table: '[Table]',
};

const getSpecialBlockKind = (heading?: string): SpecialBlockKind | null => {
    const h = (heading || '').trim().toLowerCase();
    if (h === SPECIAL_HEADINGS.equation.toLowerCase()) return 'equation';
    if (h === SPECIAL_HEADINGS.figure.toLowerCase()) return 'figure';
    if (h === SPECIAL_HEADINGS.table.toLowerCase()) return 'table';
    return null;
};

const parseSpecialAssetContent = (content: string) => {
    const lines = (content || '').split('\n');
    let caption = '';
    let source = '';
    const bodyLines: string[] = [];

    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) {
            bodyLines.push(line);
            continue;
        }
        if (/^caption\s*:/i.test(trimmed)) {
            caption = trimmed.replace(/^caption\s*:/i, '').trim();
            continue;
        }
        if (/^(source|data\s*source)\s*:/i.test(trimmed)) {
            source = trimmed.replace(/^(source|data\s*source)\s*:/i, '').trim();
            continue;
        }
        if (!caption && !/^https?:\/\//i.test(trimmed)) {
            caption = trimmed;
            continue;
        }
        if (!source && /^https?:\/\//i.test(trimmed)) {
            source = trimmed;
            continue;
        }
        bodyLines.push(line);
    }

    return {
        caption: caption || 'Untitled',
        source,
        body: bodyLines.join('\n').trim(),
    };
};

const buildSpecialAssetContent = (caption: string, source: string, body: string = '') => {
    const lines = [`Caption: ${caption || 'Untitled'}`];
    if (source?.trim()) lines.push(`Source: ${source.trim()}`);
    if (body?.trim()) lines.push('', body.trim());
    return lines.join('\n');
};

const parseMarkdownTable = (body: string): { headers: string[]; rows: string[][] } | null => {
    const rows = (body || '')
        .split('\n')
        .map(r => r.trim())
        .filter(r => r.startsWith('|') && r.endsWith('|'))
        .map(r => r.slice(1, -1).split('|').map(c => c.trim()));
    if (rows.length < 2) return null;
    return { headers: rows[0], rows: rows.slice(2) };
};

interface TemplateConfig {
    name: string;
    mt: number; mb: number; ms: number;
    hdrMm: number;
    bodyH: number;
    cols: 1 | 2;
    colGap?: number;
    fontFamily: string;
    fontSize: string;
    lineHeight: string;
    titleSize: string;
    titleWeight: string;
    authorSize?: string;
    affiliationSize?: string;
    abstractIndent?: string;
    abstractStyle?: 'normal' | 'bold-italic-em';
    abstractFontWeight?: string;
    kwLabel?: string;
    sectionSize: string;
    sectionWeight: string;
    sectionAlign?: string;
    sectionVariant?: string;
    subSectionSize?: string;
    subSectionWeight?: string;
    subSectionStyle?: string;
    hdrStyle?: string;
    headingNumbering?: 'roman' | 'decimal';
    subHeadingNumbering?: 'alpha' | 'decimal';
    showPageNumbers?: boolean;
    noHeaderOnFirst?: boolean;
}

const TEMPLATES: Record<string, TemplateConfig> = {
    SPRINGER: {
        name: 'Springer LNCS',
        mt: SPR_MT_MM, mb: SPR_MB_MM, ms: SPR_MS_MM,
        hdrMm: SPR_HDR_MM, bodyH: SPR_BODY_H,
        cols: 1,
        fontFamily: "'Times New Roman', Times, serif",
        fontSize: '10pt', lineHeight: '1.2',
        titleSize: '14pt', titleWeight: 'bold',
        abstractIndent: '10mm',
        abstractStyle: 'normal',
        sectionSize: '10pt', sectionWeight: 'bold', sectionAlign: 'left',
        hdrStyle: 'italic',
        headingNumbering: 'decimal',
        showPageNumbers: true,
        noHeaderOnFirst: true,
    },
    IEEE: {
        name: 'IEEE Conference',
        mt: IEEE_MT_MM, mb: IEEE_MB_MM, ms: IEEE_MS_MM,
        hdrMm: IEEE_HDR_MM, bodyH: IEEE_BODY_H,
        cols: 2, colGap: IEEE_COL_GAP,
        fontFamily: "'Times New Roman', Times, serif",
        fontSize: '10pt', lineHeight: '1.15',
        titleSize: '24pt', titleWeight: 'normal',
        authorSize: '11pt',
        affiliationSize: '9pt',
        abstractIndent: '8mm',
        abstractStyle: 'bold-italic-em',
        abstractFontWeight: 'bold',
        kwLabel: 'Keywords',
        sectionSize: '10pt', sectionWeight: 'normal', // IEEE uses small-caps for sections
        sectionAlign: 'center', sectionVariant: 'small-caps',
        subSectionSize: '10pt', subSectionWeight: 'normal',
        subSectionStyle: 'italic',
        hdrStyle: 'normal',
        headingNumbering: 'roman',
        subHeadingNumbering: 'alpha',
        showPageNumbers: false,
        noHeaderOnFirst: false,
    },
};

interface WorkspaceStudioProps {
    activeProject?: Project | null;
    content: string;
    onChange: (content: string) => void;
    activeFileName?: string;
    onUndo?: () => void;
    onRedo?: () => void;
    canUndo?: boolean;
    canRedo?: boolean;
    onOpenPaper?: (paperId: string, page?: number, highlightText?: string) => void;
    isStreaming?: boolean;
}

// ─── Main component ───────────────────────────────────────────────────────────
export const WorkspaceStudio: React.FC<WorkspaceStudioProps> = ({
    activeProject,
    content,
    onChange,
    activeFileName,
    onUndo, onRedo, canUndo, canRedo,
    onOpenPaper,
    isStreaming = false,
}) => {
    const [blocks, setBlocks] = useState<Block[]>([]);
    const [zoom, setZoom] = useState(100);
    const [activeTemplate, setActiveTemplate] = useState<string>('IEEE');
    const [templateMenuOpen, setTemplateMenuOpen] = useState(false);
    const [insertMenuOpen, setInsertMenuOpen] = useState(false);
    const [isRefactoring, setIsRefactoring] = useState(false);
    const [currentPage, setCurrentPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [editorMode, setEditorMode] = useState<'visual' | 'latex'>('visual');
    const [isSplitView, setIsSplitView] = useState(false);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [rawLatex, setRawLatex] = useState('');
    const [isPreviewDirty, setIsPreviewDirty] = useState(false);
    const [dynamicCols, setDynamicCols] = useState<number | null>(null);
    const [isExporting, setIsExporting] = useState(false);
    // Editable running header / footer state
    const [runningHeader, setRunningHeader] = useState('');
    const [pageFooter, setPageFooter] = useState('');

    const { addToast } = useToastStore();
    const viewportRef = useRef<HTMLDivElement>(null);
    const clearPreview = useCallback((dirty = false) => {
        setPreviewUrl(prev => {
            if (prev) window.URL.revokeObjectURL(prev);
            return null;
        });
        setIsPreviewDirty(dirty);
    }, []);

    const isStreamingRef = useRef(isStreaming);
    useEffect(() => { isStreamingRef.current = isStreaming; }, [isStreaming]);

    const tmpl = TEMPLATES[activeTemplate] ?? TEMPLATES['SPRINGER'];

    useEffect(() => {
        if (typeof window === 'undefined') return;
        const savedTemplate = window.localStorage.getItem(getTemplateStorageKey(activeProject?.id));
        setActiveTemplate(savedTemplate && TEMPLATES[savedTemplate] ? savedTemplate : 'IEEE');
    }, [activeProject?.id]);

    useEffect(() => {
        if (typeof window === 'undefined') return;
        window.localStorage.setItem(getTemplateStorageKey(activeProject?.id), activeTemplate);
    }, [activeProject?.id, activeTemplate]);

    useEffect(() => {
        setEditorMode('visual');
        setIsSplitView(false);
        setRawLatex('');
        clearPreview(false);
    }, [activeProject?.id, clearPreview]);

    // ── Parse markdown → blocks ───────────────────────────────────────────────
    useEffect(() => {
        if (!content?.trim()) {
            setBlocks([
                { id: 'meta-title', type: 'title', content: '' },
                { id: 'meta-authors', type: 'authors', content: '' },
                { id: 'meta-abstract', type: 'abstract', heading: 'Abstract', content: '' },
                { id: 'meta-keywords', type: 'keywords', content: '' },
                { id: 'blk-introduction', type: 'section', level: 1, heading: 'Introduction', content: '' },
                { id: 'blk-methodology', type: 'section', level: 1, heading: 'Methodology', content: '' },
                { id: 'blk-results', type: 'section', level: 1, heading: 'Results', content: '' },
                { id: 'blk-discussion', type: 'section', level: 1, heading: 'Discussion', content: '' },
                { id: 'blk-conclusion', type: 'section', level: 1, heading: 'Conclusion', content: '' },
                { id: 'blk-references', type: 'section', level: 1, heading: 'References', content: '' },
            ]);
            return;
        }

        const newBlocks: Block[] = [];
        const lines = content.split('\n');
        let currentType: Block['type'] = 'title';
        let buffer: string[] = [];
        let currentHeading = '';
        let currentLevel: 1 | 2 = 1;

        const flush = (nextType?: Block['type'], nextHeading = '', nextLevel: 1 | 2 = 1) => {
            if (buffer.length > 0 || currentType === 'title') {
                if (currentType === 'title') {
                    const titleText = buffer[0]?.replace(/^#+\s*/, '') || 'Untitled';
                    newBlocks.push({ id: 'meta-title', type: 'title', content: titleText });
                    const authorIdx = buffer.findIndex(l => l.includes('**Authors:**') || l.startsWith('> '));
                    if (authorIdx !== -1) {
                        const authorText = buffer.slice(authorIdx + 1).join('\n').trim()
                            || buffer[authorIdx].replace(/^>\s*/, '').replace('**Authors:**', '').trim();
                        if (authorText) newBlocks.push({ id: 'meta-authors', type: 'authors', content: authorText });
                    }
                } else if (currentType === 'abstract') {
                    const blockContent = buffer.join('\n').trim();
                    if (blockContent) newBlocks.push({ id: 'meta-abstract', type: 'abstract', heading: 'Abstract', content: blockContent });
                } else if (currentType === 'keywords') {
                    const blockContent = buffer.join('\n').trim();
                    if (blockContent) newBlocks.push({ id: 'meta-keywords', type: 'keywords', content: blockContent });
                } else if (currentType === 'section') {
                    const blockContent = buffer.join('\n').trim();
                    if (blockContent || currentHeading) {
                        newBlocks.push({ id: `blk-${newBlocks.length}`, type: 'section', level: currentLevel, heading: currentHeading, content: blockContent });
                    }
                }
            }
            buffer = [];
            if (nextType) {
                currentType = nextType;
                currentHeading = nextHeading;
                currentLevel = nextLevel;
            }
        };

        lines.forEach(line => {
            if (line.match(/^##\s+Abstract/i)) flush('abstract');
            else if (line.match(/^##\s+Keywords/i)) flush('keywords');
            else if (line.match(/^#\s+/)) flush('title'); // Support for # Title format
            else if (line.match(/^###\s+/)) flush('section', line.replace(/^###\s*/, '').trim(), 2);
            else if (line.match(/^##\s+/)) flush('section', line.replace(/^##\s*/, '').trim(), 1);
            else buffer.push(line);
        });
        flush();
        setBlocks(newBlocks);
    }, [content]);

    // ── Reconstruct markdown from blocks ──────────────────────────────────────
    const saveBlocks = useCallback((updated: Block[]) => {
        let md = '';
        updated.forEach(b => {
            if (b.type === 'title') md += `# ${b.content}\n\n`;
            else if (b.type === 'authors') md += `**Authors:**\n${b.content}\n\n`;
            else if (b.type === 'abstract') md += `## Abstract\n${b.content}\n\n`;
            else if (b.type === 'keywords') md += `## Keywords\n${b.content}\n\n`;
            else if (b.type === 'section') md += `${b.level === 2 ? '###' : '##'} ${b.heading}\n${b.content}\n\n`;
        });
        onChange(md);
        setBlocks(updated);
    }, [onChange]);

    const handleBlockChange = (id: string, v: string) => saveBlocks(blocks.map(b => b.id === id ? { ...b, content: v } : b));
    const handleHeadingChange = (id: string, v: string) => saveBlocks(blocks.map(b => b.id === id ? { ...b, heading: v } : b));

    const insertBlock = (type: Block['type']) => {
        const id = `blk-${Date.now()}`;
        let newBlock: Block;
        if (type === 'title') newBlock = { id: 'meta-title', type: 'title', content: 'New Paper Title' };
        else if (type === 'authors') newBlock = { id: 'meta-authors', type: 'authors', content: 'Author Name\nAffiliation\nEmail' };
        else if (type === 'abstract') newBlock = { id: 'meta-abstract', type: 'abstract', heading: 'Abstract', content: 'Abstract content goes here...' };
        else if (type === 'keywords') newBlock = { id: 'meta-keywords', type: 'keywords', content: 'keyword1, keyword2' };
        else newBlock = { id, type: 'section', level: 1, heading: 'New Section', content: 'Start writing here...' };

        let newBlocks = [...blocks];

        if (type === 'title') {
            newBlocks = newBlocks.filter(b => b.type !== 'title');
            newBlocks.unshift(newBlock);
        } else if (type === 'authors') {
            newBlocks = newBlocks.filter(b => b.type !== 'authors');
            const titleIdx = newBlocks.findIndex(b => b.type === 'title');
            newBlocks.splice(titleIdx >= 0 ? titleIdx + 1 : 0, 0, newBlock);
        } else if (type === 'abstract') {
            newBlocks = newBlocks.filter(b => b.type !== 'abstract');
            const lastMetaIdx = Math.max(newBlocks.findIndex(b => b.type === 'authors'), newBlocks.findIndex(b => b.type === 'title'));
            newBlocks.splice(lastMetaIdx >= 0 ? lastMetaIdx + 1 : 0, 0, newBlock);
        } else if (type === 'keywords') {
            newBlocks = newBlocks.filter(b => b.type !== 'keywords');
            const authIdx = newBlocks.findIndex(b => b.type === 'abstract');
            newBlocks.splice(authIdx >= 0 ? authIdx + 1 : 0, 0, newBlock);
        } else {
            newBlocks.push(newBlock);
        }

        saveBlocks(newBlocks);
    };

    const deleteBlock = (id: string) => {
        if (confirm('Delete this section?')) saveBlocks(blocks.filter(b => b.id !== id));
    };

    const insertSectionAfter = (afterId: string, level: number = 1) => {
        const idx = blocks.findIndex(b => b.id === afterId);
        const nb: Block = {
            id: `blk-${Date.now()}`,
            type: 'section',
            level,
            heading: level === 1 ? 'New Section' : 'Subsection',
            content: 'Start writing here...'
        };
        const newBlocks = [...blocks];
        newBlocks.splice(idx + 1, 0, nb);
        saveBlocks(newBlocks);
    };

    const insertSpecialBlock = (kind: SpecialBlockKind) => {
        const id = `blk-${Date.now()}`;
        const placeholders: Record<SpecialBlockKind, string> = {
            equation: 'a^2 + b^2 = c^2',
            figure: 'Figure caption',
            table: 'Table caption',
        };
        const nb: Block = {
            id,
            type: 'section',
            level: 1,
            heading: SPECIAL_HEADINGS[kind],
            content: placeholders[kind],
        };
        const newBlocks = [...blocks, nb];
        saveBlocks(newBlocks);
    };

    const generateLaTeX = useCallback((blocks: Block[], tmpl: TemplateConfig, activeTemplate: string) => {
        let preamble = '';
        const cols = dynamicCols ?? tmpl.cols;

        if (activeTemplate === 'IEEE' && defaultIeeeTemplate) {
            const splitContent = defaultIeeeTemplate.split('\\begin{document}');
            let preambleText = splitContent[0];
            if (cols === 1) {
                preambleText = preambleText.replace('[conference]', '[conference,onecolumn]');
            } else {
                preambleText = preambleText.replace('onecolumn', 'twocolumn');
            }
            preamble = preambleText + '\\begin{document}\n';
        } else if (activeTemplate === 'IEEE') {
            preamble = `\\documentclass[${cols === 1 ? 'onecolumn' : 'twocolumn'},conference]{IEEEtran}
\\IEEEoverridecommandlockouts
\\usepackage[T1]{fontenc}
\\usepackage[utf8]{inputenc}
\\usepackage{cite}
\\usepackage{amsmath,amssymb,amsfonts}
\\usepackage{algorithmic}
\\usepackage{graphicx}
\\usepackage{textcomp}
\\usepackage{xcolor}
\\usepackage[hidelinks]{hyperref}
\\def\\BibTeX{{\\rm B\\kern-.05em{\\sc i\\kern-.025em b}\\kern-.08em
    T\\kern-.1667em\\lower.7ex\\hbox{E}\\kern-.125emX}}
\\begin{document}\n`;
        } else {
            preamble = `\\documentclass[10pt,a4paper]{article}
\\usepackage[T1]{fontenc}
\\usepackage[utf8]{inputenc}
\\usepackage[a4paper,top=${tmpl.mt}mm,bottom=${tmpl.mb}mm,left=${tmpl.ms}mm,right=${tmpl.ms}mm]{geometry}
\\usepackage{graphicx}
\\usepackage{amsmath,amssymb}
\\usepackage{textcomp}
\\usepackage{xcolor}
\\usepackage[hidelinks]{hyperref}
\\usepackage{times}
\\setlength{\\parindent}{1.5em}
\\setlength{\\parskip}{0.3em}
\\begin{document}\n`;
        }

        const escapeLatex = (value: string) => {
            return value
                .replace(/\\/g, '\\textbackslash{}')
                .replace(/([#$%&_{}])/g, '\\$1')
                .replace(/~/g, '\\textasciitilde{}')
                .replace(/\^/g, '\\textasciicircum{}');
        };

        const replaceWithToken = (value: string, pattern: RegExp, latex: string, tokens: string[]) =>
            value.replace(pattern, () => {
                const token = `@@LATEX_TOKEN_${tokens.length}@@`;
                tokens.push(latex);
                return token;
            });

        const inlineMdToTex = (value: string): string => {
            if (!value) return '';

            const tokens: string[] = [];
            let text = value
                .replace(/\r\n/g, '\n')
                .replace(/\u00A0/g, ' ')
                .replace(/[\u201c\u201d]/g, '"')
                .replace(/[\u2018\u2019]/g, "'")
                .replace(/\u2013/g, '--')
                .replace(/\u2014/g, '---');

            text = replaceWithToken(text, /\u2026/g, '\\ldots{}', tokens);
            text = replaceWithToken(text, /\u2264/g, '$\\le$', tokens);
            text = replaceWithToken(text, /\u2265/g, '$\\ge$', tokens);
            text = replaceWithToken(text, /\u2260/g, '$\\neq$', tokens);
            text = replaceWithToken(text, /\u00B1/g, '$\\pm$', tokens);
            text = replaceWithToken(text, /\u00D7/g, '$\\times$', tokens);
            text = replaceWithToken(text, /\u00F7/g, '$\\div$', tokens);
            text = replaceWithToken(text, /\u2192/g, '$\\rightarrow$', tokens);
            text = replaceWithToken(text, /\u2190/g, '$\\leftarrow$', tokens);
            text = replaceWithToken(text, /\u2194/g, '$\\leftrightarrow$', tokens);
            text = replaceWithToken(text, /\u21A6/g, '$\\mapsto$', tokens);

            text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label: string, href: string) => {
                const token = `@@LATEX_TOKEN_${tokens.length}@@`;
                tokens.push(`\\href{${escapeLatex(href.trim())}}{${inlineMdToTex(label)}}`);
                return token;
            });
            text = text.replace(/`([^`]+)`/g, (_, code: string) => {
                const token = `@@LATEX_TOKEN_${tokens.length}@@`;
                tokens.push(`\\texttt{${escapeLatex(code)}}`);
                return token;
            });
            text = text.replace(/\*\*([^*]+)\*\*/g, (_, bold: string) => {
                const token = `@@LATEX_TOKEN_${tokens.length}@@`;
                tokens.push(`\\textbf{${inlineMdToTex(bold)}}`);
                return token;
            });
            text = text.replace(/\*([^*]+)\*/g, (_, italic: string) => {
                const token = `@@LATEX_TOKEN_${tokens.length}@@`;
                tokens.push(`\\textit{${inlineMdToTex(italic)}}`);
                return token;
            });

            text = escapeLatex(text);
            tokens.forEach((latex, index) => {
                text = text.replace(new RegExp(`@@LATEX_TOKEN_${index}@@`, 'g'), latex);
            });
            return text;
        };

        const mdToTex = (md: string) => {
            if (!md) return '';

            const lines = md.replace(/\r\n/g, '\n').split('\n');
            const outLines: string[] = [];
            let inList = false;

            const closeList = () => {
                if (inList) {
                    outLines.push('\\end{itemize}');
                    inList = false;
                }
            };

            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed) {
                    closeList();
                    outLines.push('');
                    continue;
                }

                const subsubHeading = trimmed.match(/^###\s+(.*)$/);
                if (subsubHeading) {
                    closeList();
                    outLines.push(`\\subsubsection{${inlineMdToTex(subsubHeading[1])}}`);
                    continue;
                }

                const subHeading = trimmed.match(/^##\s+(.*)$/);
                if (subHeading) {
                    closeList();
                    outLines.push(`\\subsection{${inlineMdToTex(subHeading[1])}}`);
                    continue;
                }

                const bullet = trimmed.match(/^[*-]\s+(.*)$/);
                if (bullet) {
                    if (!inList) {
                        outLines.push('\\begin{itemize}');
                        inList = true;
                    }
                    outLines.push(`\\item ${inlineMdToTex(bullet[1])}`);
                    continue;
                }

                closeList();
                outLines.push(inlineMdToTex(line));
            }

            closeList();
            return outLines.join('\n');

            const normalizeForLatex = (value: string) => {
                return value
                    .replace(/\r\n/g, '\n')
                    .replace(/\u00A0/g, ' ')
                    .replace(/[“”]/g, '"')
                    .replace(/[‘’]/g, "'")
                    .replace(/…/g, '\\ldots{}')
                    .replace(/–/g, '--')
                    .replace(/—/g, '---')
                    .replace(/≤/g, '$\\le$')
                    .replace(/≥/g, '$\\ge$')
                    .replace(/≠/g, '$\\neq$')
                    .replace(/±/g, '$\\pm$')
                    .replace(/×/g, '$\\times$')
                    .replace(/÷/g, '$\\div$')
                    .replace(/→/g, '$\\rightarrow$')
                    .replace(/←/g, '$\\leftarrow$')
                    .replace(/↔/g, '$\\leftrightarrow$')
                    .replace(/↦/g, '$\\mapsto$')
                    .replace(/[😀-🙏🌀-🗿🚀-🛿🇠-🇿]+/gu, '');
            };

            const escapeLatex = (value: string) => {
                return value
                    .replace(/\\/g, '\\textbackslash{}')
                    .replace(/([#$%&_{}])/g, '\\$1')
                    .replace(/~/g, '\\textasciitilde{}')
                    .replace(/\^/g, '\\textasciicircum{}');
            };

            let text = normalizeForLatex(md);
            text = text.replace(/\*\*(.*?)\*\*/g, '\\textbf{$1}');
            text = text.replace(/\*(.*?)\*/g, '\\textit{$1}');

            text = escapeLatex(text);
            text = text.replace(/\\textbackslash\{\}textbf\{/g, '\\textbf{');
            text = text.replace(/\\textbackslash\{\}textit\{/g, '\\textit{');
            text = text.replace(/\\textbackslash\{\}ldots\{\}/g, '\\ldots{}');
            text = text.replace(/\\textbackslash\{\}(le|ge|neq|pm|times|div|rightarrow|leftarrow|leftrightarrow|mapsto)/g, '\\$1');

            text = text.replace(/^###\s+(.*?)$/gm, '\\subsubsection{$1}');
            text = text.replace(/^##\s+(.*?)$/gm, '\\subsection{$1}');

            if (text.match(/^[\*\-]\s+/m)) {
                const lines = text.split('\n');
                let inList = false;
                const outLines = [];
                for (let i = 0; i < lines.length; i++) {
                    const l = lines[i];
                    const isItem = l.match(/^[\*\-]\s+(.*)/);
                    if (isItem && !inList) {
                        inList = true;
                        outLines.push('\\begin{itemize}');
                    } else if (!isItem && inList && l.trim() !== '') {
                        inList = false;
                        outLines.push('\\end{itemize}');
                    }
                    if (isItem) {
                        outLines.push('\\item ' + isItem[1].trim());
                    } else {
                        outLines.push(l);
                    }
                }
                if (inList) outLines.push('\\end{itemize}');
                text = outLines.join('\n');
            }

            return text;
        };

        const isIeee = activeTemplate === 'IEEE';
        let titleBlock = 'Untitled Paper';
        let authorBlock = isIeee
            ? '\\IEEEauthorblockN{Anonymous Author}\n\\IEEEauthorblockA{\\textit{Affiliation}}'
            : 'Anonymous Author';
        let abstractBlock = '';
        let keywordsBlock = '';
        const body: string[] = [];

        for (const b of blocks) {
            if (b.type === 'title') titleBlock = inlineMdToTex(b.content);
            else if (b.type === 'authors') {
                const authorsList = b.content.split(/\n\s*\n|---/).map(author => author.trim()).filter(Boolean);
                if (isIeee) {
                    const blocksTex = authorsList.map(authorStr => {
                        const lines = authorStr.trim().split('\n').map(line => line.trim()).filter(Boolean);
                        const name = inlineMdToTex(lines[0] || 'Author');
                        const affil = lines.slice(1).map(line => inlineMdToTex(line)).join(' \\\\ ');
                        return `\\IEEEauthorblockN{${name}}\n\\IEEEauthorblockA{${affil || '\\textit{Affiliation}'}}`;
                    });
                    authorBlock = blocksTex.join('\n\\and\n');
                } else {
                    authorBlock = authorsList.map(authorStr => {
                        const lines = authorStr.trim().split('\n').map(line => line.trim()).filter(Boolean);
                        const name = inlineMdToTex(lines[0] || 'Author');
                        const affil = lines.slice(1).map(line => inlineMdToTex(line)).join(' \\\\ ');
                        return affil ? `${name}\\\\${affil}` : name;
                    }).join(' \\and ');
                }
            }
            else if (b.type === 'abstract') abstractBlock = mdToTex(b.content);
            else if (b.type === 'keywords') keywordsBlock = inlineMdToTex(b.content);
            else if (b.type === 'section') {
                const specialKind = getSpecialBlockKind(b.heading);
                if (specialKind === 'equation') {
                    const eq = (b.content || 'a^2 + b^2 = c^2').replace(/^\$\$?\s*/, '').replace(/\s*\$\$?$/, '').trim();
                    body.push(`\\begin{equation}\n${eq}\n\\end{equation}`);
                    continue;
                }
                if (specialKind === 'figure') {
                    const parsed = parseSpecialAssetContent(b.content || '');
                    const caption = inlineMdToTex(parsed.caption || 'Figure caption');
                    if (parsed.source) {
                        const sourcePath = parsed.source.trim();
                        const figureWidth = isIeee ? '0.95\\columnwidth' : '0.9\\linewidth';
                        body.push(`\\begin{figure}[t]\n\\centering\n\\includegraphics[width=${figureWidth}]{__ASSET__${sourcePath}}\n\\caption{${caption}}\n\\end{figure}`);
                    } else {
                        body.push(`\\begin{figure}[t]\n\\centering\n\\fbox{\\parbox{0.9\\linewidth}{\\centering Add figure asset here}}\n\\caption{${caption}}\n\\end{figure}`);
                    }
                    continue;
                }
                if (specialKind === 'table') {
                    const parsed = parseSpecialAssetContent(b.content || '');
                    const caption = inlineMdToTex(parsed.caption || 'Table caption');
                    const rows = parsed.body
                        .split('\n')
                        .map(r => r.trim())
                        .filter(r => r.startsWith('|') && r.endsWith('|'))
                        .map(r => r.slice(1, -1).split('|').map(c => c.trim()));

                    if (rows.length >= 2) {
                        const header = rows[0];
                        const dataRows = rows.slice(2);
                        const colSpec = `|${header.map(() => 'c').join('|')}|`;
                        const texRows = [
                            `${header.map(h => inlineMdToTex(h)).join(' & ')} \\\\ \\hline`,
                            ...dataRows.map(dr => `${dr.map(c => inlineMdToTex(c)).join(' & ')} \\\\ \\hline`),
                        ].join('\n');
                        body.push(`\\begin{table}[t]\n\\caption{${caption}}\n\\centering\n\\begin{tabular}{${colSpec}}\\hline\n${texRows}\n\\end{tabular}\n\\end{table}`);
                    } else {
                        body.push(`\\begin{table}[t]\n\\caption{${caption}}\n\\centering\n\\begin{tabular}{|c|c|}\\hline\nCol 1 & Col 2 \\\\ \\hline\nValue 1 & Value 2 \\\\ \\hline\n\\end{tabular}\n\\end{table}`);
                    }
                    continue;
                }
                if (b.heading) {
                    const cmd = (b.level === 2) ? '\\subsection' : '\\section';
                    body.push(`${cmd}{${inlineMdToTex(b.heading)}}`);
                }
                body.push(mdToTex(b.content));
            }
        }

        const absStr = abstractBlock ? `\\begin{abstract}\n${abstractBlock}\n\\end{abstract}\n` : '';
        const kwStr = keywordsBlock
            ? isIeee
                ? `\\begin{IEEEkeywords}\n${keywordsBlock}\n\\end{IEEEkeywords}\n`
                : `\\noindent\\textbf{Keywords:} ${keywordsBlock}\n`
            : '';
        const authorStr = isIeee ? `\\author{${authorBlock}}` : `\\author{${authorBlock}}\n\\date{}`;

        return `${preamble}
\\title{${titleBlock}}
${authorStr}

\\maketitle

${absStr}
${kwStr}
${body.join('\n\n')}

\\end{document}
`;
    }, [dynamicCols]);

    const getCurrentLatex = () => (
        editorMode === 'latex' ? rawLatex : generateLaTeX(blocks, tmpl, activeTemplate)
    );

    const requestPdf = async () => {
        const sourceLatex = getCurrentLatex();
        const response = await fetch(exportPdfEndpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ latex: sourceLatex, template: activeTemplate })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.detail || 'Failed to generate PDF');
        }

        return response;
    };

    const handleExportPDF = async () => {
        try {
            setIsExporting(true);
            const res = await requestPdf();

            // Create a blob from the PDF stream and trigger download
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${sanitizeExportFilename(activeProject?.title || 'Manuscript')}_${activeTemplate}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (error: any) {
            console.error(error);
            addToast(`PDF export failed: ${error.message}`, 'error');
        } finally {
            setIsExporting(false);
        }
    };

    const handleRefreshPreview = async () => {
        try {
            setIsExporting(true);
            const res = await requestPdf();
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            if (previewUrl) window.URL.revokeObjectURL(previewUrl);
            setPreviewUrl(url);
            setIsPreviewDirty(false);
        } catch (error: any) {
            console.error(error);
            addToast(`Preview failed: ${error.message}`, 'error');
        } finally {
            setIsExporting(false);
        }
    };

    // Detect columns from LaTeX source
    useEffect(() => {
        if (!rawLatex) return;
        const isOneCol = rawLatex.includes('onecolumn');
        const isTwoCol = rawLatex.includes('twocolumn') || rawLatex.includes('[conference]');
        if (isOneCol) setDynamicCols(1);
        else if (isTwoCol) setDynamicCols(2);
        else setDynamicCols(null);
    }, [rawLatex]);

    // ── Draft persistence ─────────────────────────────────────────────────────
    useEffect(() => {
        if (!activeProject?.id) return;
        loadDraft(activeProject.id).then(draft => {
            if (draft.full_content && draft.full_content !== content) onChange(draft.full_content);
        }).catch(() => { });
    }, [activeProject?.id]);

    useEffect(() => {
        if (!activeProject?.id || !content) return;
        const t = setTimeout(() => {
            saveDraft(activeProject.id, null, content).catch(() => { });
        }, 3000);
        return () => clearTimeout(t);
    }, [activeProject?.id, content]);

    useEffect(() => {
        if (editorMode !== 'latex' && isSplitView) setIsSplitView(false);
    }, [editorMode, isSplitView]);

    useEffect(() => {
        return () => {
            if (previewUrl) {
                window.URL.revokeObjectURL(previewUrl);
            }
        };
    }, [previewUrl]);

    const getGeneratedLatex = (templateKey: string = activeTemplate) => {
        const nextTemplate = TEMPLATES[templateKey] ?? tmpl;
        return generateLaTeX(blocks, nextTemplate, templateKey);
    };

    const hasUnsyncedLatexEdits = () => {
        if (editorMode !== 'latex' || !rawLatex.trim()) return false;
        return rawLatex.trim() !== getGeneratedLatex().trim();
    };

    // Seed running header from first title/author block
    useEffect(() => {
        if (runningHeader) return;
        const authors = blocks.find(b => b.type === 'authors')?.content ?? '';
        const authorShort = authors.split('\n')[0]?.split(',')[0]?.trim() ?? '';
        if (authorShort) setRunningHeader(`${authorShort} et al.`);
    }, [blocks, runningHeader]);

    // ── Natural content height → page count ──────────────────────────────────
    const contentRef = useRef<HTMLDivElement>(null);

    // ── Scroll → current page ─────────────────────────────────────────────────
    const VIEWPORT_PAD = 40;
    useEffect(() => {
        const updatePage = () => {
            if (!viewportRef.current) return;
            const zf = zoom / 100;
            const sy = (viewportRef.current.scrollTop - VIEWPORT_PAD * zf) / zf;
            const unitPx = (A4_H_MM + GAP_MM) * PX_PER_MM;
            setCurrentPage(Math.min(totalPages, Math.max(1, Math.floor(sy / unitPx) + 1)));
        };
        const vp = viewportRef.current;
        if (!vp) return;
        vp.addEventListener('scroll', updatePage);
        return () => vp.removeEventListener('scroll', updatePage);
    }, [zoom, totalPages]);

    const scrollToPage = (p: number) => {
        if (!viewportRef.current) return;
        const target = Math.max(1, Math.min(p, totalPages));
        const zf = zoom / 100;
        const unitPx = (A4_H_MM + GAP_MM) * PX_PER_MM;
        viewportRef.current.scrollTo({ top: VIEWPORT_PAD * zf + (target - 1) * unitPx * zf, behavior: 'smooth' });
    };

    const handleTemplateSwitch = (key: string) => {
        if (editorMode === 'latex' && hasUnsyncedLatexEdits()) {
            const shouldRegenerate = window.confirm('Switching templates will regenerate the LaTeX source and replace manual LaTeX edits. Continue?');
            if (!shouldRegenerate) {
                setTemplateMenuOpen(false);
                return;
            }
        }

        const nextLatex = getGeneratedLatex(key);
        setIsRefactoring(true);
        setTemplateMenuOpen(false);
        setTimeout(() => {
            setActiveTemplate(key);
            clearPreview(editorMode === 'latex');
            if (editorMode === 'latex') {
                setRawLatex(nextLatex);
            }
            setIsRefactoring(false);
        }, 400);
    };

    // ── Render ────────────────────────────────────────────────────────────────
    const title = blocks.find(b => b.type === 'title')?.content ?? activeFileName ?? 'Untitled';
    const authorsStr = blocks.find(b => b.type === 'authors')?.content ?? '';
    const authorShort = authorsStr.split('\n')[0]?.split(',')[0]?.trim() ?? '';
    const derivedHdrLeft = authorShort ? `${authorShort} et al.` : '';
    const derivedHdrRight = title.length > 50 ? title.slice(0, 48) + '…' : title;

    return (
        <div className="flex flex-col h-full bg-[#525659] font-sans overflow-hidden">
            <style>{`
                /* ── Tiptap base reset ── */
                .tiptap-block { outline: none; min-height: 1em; }
                .tiptap-block p { margin-bottom: 4pt; }
                .tiptap-block p.is-editor-empty:first-child::before {
                    color: #adb5bd; content: attr(data-placeholder);
                    float: left; height: 0; pointer-events: none;
                }
                .tiptap-block:focus-within { outline: 2px dashed rgba(99,102,241,0.5); outline-offset: 2px; border-radius: 2px; }

                /* ── IEEE formatting ── */
                .ieee-format .tiptap-block { font-family: "Times New Roman", Times, serif; font-size: 10pt; line-height: 1.15; }
                .ieee-format .tiptap-block h1 { font-size: 10pt; font-weight: bold; text-align: center; font-variant: small-caps; text-transform: uppercase; margin: 10pt 0 4pt; }
                .ieee-format .tiptap-block p { text-align: justify; margin-bottom: 0; text-indent: 12pt; }
                
                /* Page Sheets */
                .page-sheet-container { display: flex; flex-direction: column; align-items: center; padding-bottom: 100px; }
                .paper-content-area > * { break-inside: auto; page-break-inside: auto; }

                /* ── Springer formatting ── */
                .springer-format .tiptap-block { font-family: "Times New Roman", Times, serif; font-size: 10pt; line-height: 1.2; }

                /* ── Print ── */
                @media print {
                    .no-print { display: none !important; }
                    .paper-doc { box-shadow: none !important; }
                }
            `}</style>

            {/* ── MAIN TOOLBAR ── */}
            <div className="no-print h-12 bg-white border-b border-gray-200 flex items-center justify-between px-4 shrink-0 z-30 shadow-sm">
                <div className="flex items-center gap-3">
                    <span className="font-bold text-gray-700 flex items-center gap-2">
                        <Printer className="w-4 h-4 text-indigo-600" /> Live Paper
                    </span>

                    <div className="flex bg-gray-100 p-0.5 rounded-lg ml-2 border border-gray-200">
                        <button
                            onClick={() => {
                                if (hasUnsyncedLatexEdits()) {
                                    const shouldSwitch = window.confirm('Visual mode cannot import manual LaTeX edits yet. Switch anyway and keep the visual draft unchanged?');
                                    if (!shouldSwitch) return;
                                }
                                setEditorMode('visual');
                            }}
                            className={`px-3 py-1 rounded-md text-xs font-semibold flex items-center gap-1 ${editorMode === 'visual' ? 'bg-white shadow text-gray-800' : 'text-gray-500 hover:text-gray-700'}`}
                        >
                            <LayoutTemplate className="w-3.5 h-3.5" /> Visual
                        </button>
                        <button
                            onClick={() => {
                                if (editorMode !== 'latex') {
                                    setRawLatex(getGeneratedLatex());
                                    clearPreview(true);
                                    setEditorMode('latex');
                                }
                            }}
                            className={`px-3 py-1 rounded-md text-xs font-semibold flex items-center gap-1 ${editorMode === 'latex' ? 'bg-indigo-50 shadow text-indigo-700 border border-indigo-100' : 'text-gray-500 hover:text-gray-700'}`}
                        >
                            <Code2 className="w-3.5 h-3.5" /> LaTeX
                        </button>
                    </div>

                    {editorMode === 'latex' && (
                        <>
                            <button onClick={() => { const newSplit = !isSplitView; setIsSplitView(newSplit); if (newSplit && (!previewUrl || isPreviewDirty)) handleRefreshPreview(); }} className={`ml-4 px-3 py-1.5 rounded-md text-xs font-bold flex items-center gap-2 border transition-all ${isSplitView ? 'bg-indigo-600 border-indigo-600 text-white shadow-md' : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'}`}>
                                <Maximize className="w-3.5 h-3.5" /> {isSplitView ? 'Exit Split' : 'Split Preview'}
                            </button>
                            <button onClick={handleRefreshPreview} disabled={isExporting} className="px-3 py-1.5 rounded-md text-xs font-bold flex items-center gap-2 border bg-white border-gray-200 text-gray-700 hover:bg-gray-50 disabled:opacity-50">
                                <RefreshCw className={`w-3.5 h-3.5 ${isExporting ? 'animate-spin' : ''}`} /> Refresh Preview
                            </button>
                        </>
                    )}

                    <div className="relative">
                        <button onClick={() => setTemplateMenuOpen(v => !v)} className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-md text-xs font-semibold text-gray-700">
                            <LayoutTemplate className="w-3.5 h-3.5 text-gray-400" />
                            {TEMPLATES[activeTemplate]?.name ?? activeTemplate}
                            <ChevronDown className="w-3 h-3 text-gray-400" />
                        </button>
                        {templateMenuOpen && (
                            <div className="absolute top-full left-0 mt-1 w-52 bg-white border border-gray-200 rounded-lg shadow-xl z-50 py-1">
                                {Object.entries(TEMPLATES).map(([key, t]) => (
                                    <button key={key} onClick={() => handleTemplateSwitch(key)} className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between ${activeTemplate === key ? 'bg-indigo-50 text-indigo-700 font-semibold' : 'text-gray-600 hover:bg-gray-50'}`}>
                                        {t.name}
                                        {activeTemplate === key && <Check className="w-3 h-3" />}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>

                    <div className="flex items-center gap-0.5 bg-gray-100 rounded px-1">
                        <button onClick={() => setZoom(z => Math.max(40, z - 10))} className="p-1 hover:bg-white rounded text-gray-500"><Minimize className="w-3 h-3" /></button>
                        <span className="text-xs w-9 text-center font-medium">{zoom}%</span>
                        <button onClick={() => setZoom(z => Math.min(160, z + 10))} className="p-1 hover:bg-white rounded text-gray-500"><Maximize className="w-3 h-3" /></button>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    <div className="flex items-center gap-0.5 border-r border-gray-200 pr-2 mr-1">
                        <button onClick={onUndo} disabled={!canUndo} className="p-1.5 text-gray-400 hover:text-gray-800 hover:bg-gray-100 rounded disabled:opacity-30" title="Undo"><Undo2 className="w-4 h-4" /></button>
                        <button onClick={onRedo} disabled={!canRedo} className="p-1.5 text-gray-400 hover:text-gray-800 hover:bg-gray-100 rounded disabled:opacity-30" title="Redo"><Redo2 className="w-4 h-4" /></button>
                    </div>
                    <div className="relative">
                        <button onClick={() => setInsertMenuOpen(v => !v)} className="flex items-center gap-1 px-3 py-1.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded text-xs font-bold">
                            <PlusCircle className="w-3.5 h-3.5" /> Insert Block <ChevronDown className="w-3 h-3" />
                        </button>
                        {insertMenuOpen && (
                            <div className="absolute top-full right-0 mt-1 w-44 bg-white border border-gray-200 rounded-lg shadow-xl z-50 py-1">
                                <button onClick={() => { insertBlock('title'); setInsertMenuOpen(false); }} className="w-full text-left px-3 py-2 text-xs hover:bg-gray-50 text-gray-700">Title</button>
                                <button onClick={() => { insertBlock('authors'); setInsertMenuOpen(false); }} className="w-full text-left px-3 py-2 text-xs hover:bg-gray-50 text-gray-700">Authors</button>
                                <button onClick={() => { insertBlock('abstract'); setInsertMenuOpen(false); }} className="w-full text-left px-3 py-2 text-xs hover:bg-gray-50 text-gray-700">Abstract</button>
                                <button onClick={() => { insertBlock('keywords'); setInsertMenuOpen(false); }} className="w-full text-left px-3 py-2 text-xs hover:bg-gray-50 text-gray-700">Keywords</button>
                                <div className="my-1 border-t border-gray-100" />
                                <button onClick={() => { insertBlock('section'); setInsertMenuOpen(false); }} className="w-full text-left px-3 py-2 text-xs hover:bg-gray-50 text-gray-700 font-bold text-indigo-600">New Section (I.)</button>
                                <button onClick={() => {
                                    const sections = blocks.filter(b => b.type === 'section');
                                    const anchorId = sections.length > 0 ? sections[sections.length - 1].id : null;
                                    if (anchorId) insertSectionAfter(anchorId, 2);
                                    else insertBlock('section');
                                    setInsertMenuOpen(false);
                                }} className="w-full text-left px-3 py-2 text-xs hover:bg-gray-50 text-indigo-500 font-semibold">New Subsection (A.)</button>
                                <button onClick={() => { insertSpecialBlock('equation'); setInsertMenuOpen(false); }} className="w-full text-left px-3 py-2 text-xs hover:bg-gray-50 text-gray-600">Equation Block</button>
                                <button onClick={() => { insertSpecialBlock('figure'); setInsertMenuOpen(false); }} className="w-full text-left px-3 py-2 text-xs hover:bg-gray-50 text-gray-600">Figure Block</button>
                                <button onClick={() => { insertSpecialBlock('table'); setInsertMenuOpen(false); }} className="w-full text-left px-3 py-2 text-xs hover:bg-gray-50 text-gray-600">Table Block</button>
                            </div>
                        )}
                    </div>
                    <button onClick={handleExportPDF} disabled={isExporting} className="flex items-center gap-1 px-3 py-1.5 bg-gray-800 text-white hover:bg-gray-700 rounded text-xs font-bold disabled:opacity-50">
                        {isExporting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
                        {isExporting ? 'Compiling...' : 'Export PDF'}
                    </button>
                </div>
            </div>

            {editorMode === 'latex' ? (
                <div className="flex-1 w-full flex bg-[#1e1e1e] overflow-hidden">
                    <div className={`${isSplitView ? 'w-1/2 border-r border-gray-800' : 'w-full'} flex flex-col h-full`}>
                        <div className="flex items-center justify-between px-4 py-2 bg-[#252526] border-b border-gray-800 shrink-0">
                            <span className="text-[11px] text-gray-400 font-bold uppercase tracking-wider">LaTeX Source</span>
                        </div>
                        <div className="flex-1">
                            <Editor height="100%" defaultLanguage="latex" theme="vs-dark" value={rawLatex} onChange={(val) => { setRawLatex(val || ''); setIsPreviewDirty(true); }} options={{ wordWrap: 'on', minimap: { enabled: false }, fontSize: 13, padding: { top: 12, bottom: 24 } }} />
                        </div>
                    </div>
                    {isSplitView && (
                        <div className="w-1/2 h-full bg-[#525659] flex flex-col">
                            {isPreviewDirty && (
                                <div className="shrink-0 px-4 py-2 text-xs font-medium bg-amber-50 text-amber-800 border-b border-amber-200">
                                    Preview is out of date. Refresh to recompile the latest LaTeX.
                                </div>
                            )}
                            {previewUrl ? (
                                <iframe src={previewUrl} className="w-full h-full border-none" title="PDF Preview" />
                            ) : (
                                <div className="flex-1 flex items-center justify-center px-6 text-center text-sm text-gray-200">
                                    {isExporting ? 'Compiling preview...' : 'PDF preview will appear here after you refresh or open split preview.'}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            ) : (
                <>
                    <div className="no-print bg-gray-50 border-b border-gray-200 px-4 py-1.5 flex items-center gap-5 text-xs text-gray-500 shrink-0 font-mono">
                        <span className="text-indigo-700 font-semibold font-sans">{tmpl.name}</span>
                        <span>Body {tmpl.fontSize} / {tmpl.lineHeight}×</span>
                    </div>

                    <div ref={viewportRef} className="flex-1 overflow-y-scroll relative" style={{ background: '#323639' }}>
                        <div className="page-sheet-container min-h-full" style={{ transform: `scale(${zoom / 100})`, transformOrigin: 'top center', padding: '40px 0' }}>
                            <div className="paper-doc shadow-2xl relative" style={{ width: `${A4_W_MM}mm`, minHeight: `${A4_H_MM * totalPages}mm`, background: 'white', margin: '0 auto' }}>
                                {Array.from({ length: totalPages }).map((_, i) => (
                                    <React.Fragment key={`page-bg-${i}`}>
                                        <div style={{ position: 'absolute', top: `${i * A4_H_MM + tmpl.hdrMm}mm`, left: `${tmpl.ms}mm`, right: `${tmpl.ms}mm`, display: 'flex', justifyContent: 'space-between', fontSize: '9pt', fontFamily: tmpl.fontFamily, zIndex: 10, pointerEvents: 'none', borderBottom: tmpl.hdrStyle === 'line' ? '0.5pt solid #000' : 'none' }}>
                                            <span>{i % 2 === 0 ? (runningHeader || derivedHdrLeft) : (pageFooter || derivedHdrRight)}</span>
                                            {tmpl.showPageNumbers !== false && <span>{i + 1}</span>}
                                        </div>
                                        {i < totalPages - 1 && <div style={{ position: 'absolute', top: `${(i + 1) * A4_H_MM}mm`, left: '-40px', right: '-40px', height: `${PAGE_GAP_MM}mm`, background: '#323639', zIndex: 20 }} />}
                                    </React.Fragment>
                                ))}

                                {(() => {
                                    const metaTypes = ['title', 'authors', 'abstract', 'keywords'];
                                    const metaBlocks = blocks.filter(b => metaTypes.includes(b.type));
                                    const flowBlocks = blocks.filter(b => !metaTypes.includes(b.type));
                                    const isTwoCol = (dynamicCols ?? tmpl.cols) === 2;

                                    type FlowUnit =
                                        | { kind: 'section-chunk'; block: Block; chunkIndex: number; chunks: string[]; showHeading: boolean; content: string }
                                        | { kind: 'block'; block: Block };

                                    const splitIntoChunks = (text: string): string[] => {
                                        const paragraphs = (text || '').split(/\n\s*\n+/).map(s => s.trim()).filter(Boolean);
                                        if (paragraphs.length === 0) return [''];
                                        const targetChars = isTwoCol ? 850 : 1400;
                                        const packed: string[] = [];
                                        let current = '';
                                        for (const p of paragraphs) {
                                            if (!current) {
                                                current = p;
                                                continue;
                                            }
                                            if ((current.length + 2 + p.length) <= targetChars) {
                                                current += `\n\n${p}`;
                                            } else {
                                                packed.push(current);
                                                current = p;
                                            }
                                        }
                                        if (current) packed.push(current);
                                        return packed;
                                    };

                                    const flowUnits: FlowUnit[] = [];
                                    flowBlocks.forEach((b) => {
                                        if (b.type === 'section') {
                                            if (getSpecialBlockKind(b.heading)) {
                                                flowUnits.push({
                                                    kind: 'section-chunk',
                                                    block: b,
                                                    chunkIndex: 0,
                                                    chunks: [b.content || ''],
                                                    showHeading: true,
                                                    content: b.content || '',
                                                });
                                                return;
                                            }
                                            const chunks = splitIntoChunks(b.content || '');
                                            chunks.forEach((chunk, idx) => {
                                                flowUnits.push({
                                                    kind: 'section-chunk',
                                                    block: b,
                                                    chunkIndex: idx,
                                                    chunks,
                                                    showHeading: idx === 0,
                                                    content: chunk,
                                                });
                                            });
                                        } else {
                                            flowUnits.push({ kind: 'block', block: b });
                                        }
                                    });

                                    const pages: FlowUnit[][] = [];
                                    let currentPageUnits: FlowUnit[] = [];
                                    let currentHeight = 0;
                                    const bodyH_px = tmpl.bodyH * PX_PER_MM;

                                    const PAGE_BREAK_SAFETY_PX = 14 * PX_PER_MM;
                                    const estimateHeight = (() => {
                                        if (typeof document === 'undefined') {
                                            return (unit: FlowUnit) => {
                                                const b = unit.block;
                                                const chunkText = unit.kind === 'section-chunk' ? unit.content : (b.content || '');
                                                return Math.max(18, chunkText.length * (isTwoCol ? 0.22 : 0.12));
                                            };
                                        }

                                        const contentWidthMm = A4_W_MM - (tmpl.ms * 2);
                                        const colCount = (dynamicCols ?? tmpl.cols);
                                        const colGapMm = tmpl.colGap ?? 0;
                                        const colWidthMm = colCount === 2 ? ((contentWidthMm - colGapMm) / 2) : contentWidthMm;
                                        const colWidthPx = colWidthMm * PX_PER_MM;

                                        const measurer = document.createElement('div');
                                        measurer.style.position = 'absolute';
                                        measurer.style.left = '-99999px';
                                        measurer.style.top = '0';
                                        measurer.style.width = `${colWidthPx}px`;
                                        measurer.style.visibility = 'hidden';
                                        measurer.style.pointerEvents = 'none';
                                        measurer.style.fontFamily = tmpl.fontFamily;
                                        measurer.style.fontSize = tmpl.fontSize;
                                        measurer.style.lineHeight = String(tmpl.lineHeight);
                                        measurer.style.color = '#000';
                                        measurer.style.whiteSpace = 'normal';
                                        document.body.appendChild(measurer);

                                        const measure = (unit: FlowUnit) => {
                                            const block = unit.block;
                                            const text = unit.kind === 'section-chunk' ? unit.content : (block.content || '');
                                            const showHeading = unit.kind === 'section-chunk' && unit.showHeading;

                                            measurer.innerHTML = '';

                                            if (showHeading && block.heading) {
                                                const headingEl = document.createElement('div');
                                                headingEl.style.marginTop = '10pt';
                                                headingEl.style.marginBottom = '3pt';
                                                headingEl.style.fontSize = tmpl.sectionSize;
                                                headingEl.style.fontFamily = tmpl.fontFamily;
                                                headingEl.style.textAlign = (tmpl.sectionAlign ?? 'left') as any;
                                                headingEl.style.fontWeight = tmpl.sectionWeight;
                                                headingEl.style.fontVariant = (tmpl.sectionVariant ?? 'normal') as any;
                                                headingEl.textContent = block.heading;
                                                measurer.appendChild(headingEl);
                                            }

                                            const contentEl = document.createElement('div');
                                            contentEl.className = 'tiptap-block';
                                            const parsed = marked.parse(text || '');
                                            if (typeof parsed === 'string') contentEl.innerHTML = parsed;
                                            else contentEl.textContent = text || '';
                                            measurer.appendChild(contentEl);

                                            const h = Math.ceil(measurer.getBoundingClientRect().height);
                                            return Math.max(16, h);
                                        };

                                        const wrapped = (unit: FlowUnit) => measure(unit);
                                        (wrapped as any).__dispose = () => {
                                            if (measurer.parentNode) measurer.parentNode.removeChild(measurer);
                                        };
                                        return wrapped as ((unit: FlowUnit) => number) & { __dispose?: () => void };
                                    })();

                                    const fmHeight = metaBlocks.length > 0 ? 120 : 0;
                                    currentHeight = fmHeight;

                                    flowUnits.forEach(unit => {
                                        const h = estimateHeight(unit);
                                        const totalAvailableHeight = ((dynamicCols ?? tmpl.cols) === 2 ? bodyH_px * 2 : bodyH_px) - PAGE_BREAK_SAFETY_PX;
                                        if (currentHeight + h > totalAvailableHeight && currentPageUnits.length > 0) {
                                            pages.push(currentPageUnits);
                                            currentPageUnits = [unit];
                                            currentHeight = h;
                                        } else {
                                            currentPageUnits.push(unit);
                                            currentHeight += h;
                                        }
                                    });
                                    if ((estimateHeight as any).__dispose) (estimateHeight as any).__dispose();
                                    if (currentPageUnits.length > 0 || pages.length === 0) pages.push(currentPageUnits);

                                    if (totalPages !== pages.length && pages.length > 0) {
                                        setTimeout(() => setTotalPages(pages.length), 0);
                                    }

                                    return pages.map((pageUnits, pageIdx) => (
                                        <div
                                            key={`page-overlay-${pageIdx}`}
                                            className={`paper-content-area ${tmpl.name.toLowerCase()}-format`}
                                            style={{
                                                position: 'absolute',
                                                top: `${pageIdx * A4_H_MM + tmpl.mt}mm`,
                                                left: `${tmpl.ms}mm`,
                                                right: `${tmpl.ms}mm`,
                                                height: `${tmpl.bodyH}mm`,
                                                columnCount: dynamicCols ?? tmpl.cols,
                                                columnGap: tmpl.colGap ? `${tmpl.colGap}mm` : undefined,
                                                columnFill: 'auto',
                                                fontFamily: tmpl.fontFamily,
                                                fontSize: tmpl.fontSize,
                                                lineHeight: tmpl.lineHeight,
                                                textAlign: 'justify',
                                                color: '#000',
                                                zIndex: 5,
                                                overflow: 'hidden'
                                            }}
                                        >
                                            {pageIdx === 0 && <FrontMatter tmpl={tmpl} blocks={blocks} handleBlockChange={handleBlockChange} />}
                                            {pageUnits.map((unit) => {
                                                if (unit.kind === 'section-chunk') {
                                                    const block = unit.block;
                                                    const specialKind = getSpecialBlockKind(block.heading);
                                                    const updateChunk = (value: string) => {
                                                        const nextChunks = [...unit.chunks];
                                                        nextChunks[unit.chunkIndex] = value;
                                                        handleBlockChange(block.id, nextChunks.join('\n\n'));
                                                    };

                                                    if (specialKind) {
                                                        const specialBlock: Block = {
                                                            ...block,
                                                            id: `${block.id}::special`,
                                                            content: unit.content,
                                                        };
                                                        return <SpecialBlock key={`${block.id}-special`} block={specialBlock} kind={specialKind} tmpl={tmpl} onChange={(_, v) => updateChunk(v)} onDelete={deleteBlock} />;
                                                    }

                                                    if (!unit.showHeading) {
                                                        const continuationBlock: Block = {
                                                            ...block,
                                                            id: `${block.id}::${unit.chunkIndex}`,
                                                            content: unit.content,
                                                        };
                                                        return (
                                                            <div key={`${block.id}-cont-${unit.chunkIndex}`} style={{ marginTop: '0pt' }}>
                                                                <EditableBlock block={continuationBlock} onChange={(_, v) => updateChunk(v)} tmpl={tmpl} />
                                                            </div>
                                                        );
                                                    }

                                                    let hIdx = 0;
                                                    if (block.level === 1) {
                                                        hIdx = blocks.filter((b, i) => b.type === 'section' && b.level === 1 && i <= blocks.indexOf(block)).length - 1;
                                                    } else {
                                                        let parentIdx = -1;
                                                        for (let i = blocks.indexOf(block) - 1; i >= 0; i--) {
                                                            if (blocks[i].type === 'section' && blocks[i].level === 1) { parentIdx = i; break; }
                                                        }
                                                        hIdx = blocks.filter((b, i) => b.type === 'section' && b.level === 2 && i > parentIdx && i <= blocks.indexOf(block)).length - 1;
                                                    }
                                                    const headedChunkBlock: Block = { ...block, content: unit.content };
                                                    return (
                                                        <div key={block.id} className="relative group/section">
                                                            <SectionBlock block={headedChunkBlock} idx={hIdx} tmpl={tmpl} onChange={(_, v) => updateChunk(v)} onHeadingChange={handleHeadingChange} onDelete={deleteBlock} />
                                                            <div className="absolute -left-8 top-0 bottom-0 w-8 opacity-0 group-hover/section:opacity-100 flex flex-col items-center justify-center gap-1 no-print">
                                                                <button onClick={() => insertSectionAfter(block.id, 1)} title="Add Section After" className="p-1 hover:bg-gray-100 rounded text-gray-400 hover:text-indigo-600 focus:outline-none"><PlusCircle className="w-3.5 h-3.5" /></button>
                                                                <button onClick={() => insertSectionAfter(block.id, 2)} title="Add Subsection After" className="p-1 hover:bg-gray-100 rounded text-gray-400 hover:text-indigo-400 focus:outline-none"><PlusCircle className="w-3 h-3" /></button>
                                                            </div>
                                                        </div>
                                                    );
                                                }
                                                const block = unit.block;
                                                return <EditableBlock key={block.id} block={block} onChange={handleBlockChange} tmpl={tmpl} />;
                                            })}
                                        </div>
                                    ));
                                })()}
                            </div>
                        </div>
                    </div>

                    <div className="no-print absolute bottom-6 left-1/2 -translate-x-1/2 z-40">
                        <div className="bg-gray-900 text-white rounded-full shadow-2xl px-4 py-2 flex items-center gap-3 text-sm font-medium border border-gray-700/50">
                            <button onClick={() => scrollToPage(currentPage - 1)} disabled={currentPage <= 1} className="p-1 hover:bg-gray-700 rounded-full disabled:opacity-30">
                                <ChevronLeft className="w-4 h-4" />
                            </button>
                            <span className="text-gray-400 text-xs">Page</span>
                            <input type="number" min={1} max={totalPages} value={currentPage} onChange={e => { const v = parseInt(e.target.value); if (!isNaN(v)) scrollToPage(v); }} className="w-7 bg-transparent text-center focus:outline-none font-bold text-sm" />
                            <span className="text-gray-400 text-xs">of {totalPages}</span>
                            <button onClick={() => scrollToPage(currentPage + 1)} disabled={currentPage >= totalPages} className="p-1 hover:bg-gray-700 rounded-full disabled:opacity-30">
                                <ChevronRight className="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};

const toRoman = (num: number): string => {
    if (num < 1 || num > 3999) return num.toString();
    const numerals = [
        { value: 1000, symbol: 'M' }, { value: 900, symbol: 'CM' }, { value: 500, symbol: 'D' },
        { value: 400, symbol: 'CD' }, { value: 100, symbol: 'C' }, { value: 90, symbol: 'XC' },
        { value: 50, symbol: 'L' }, { value: 40, symbol: 'XL' }, { value: 10, symbol: 'X' },
        { value: 9, symbol: 'IX' }, { value: 5, symbol: 'V' }, { value: 4, symbol: 'IV' },
        { value: 1, symbol: 'I' },
    ];
    let result = '';
    for (const { value, symbol } of numerals) {
        while (num >= value) {
            result += symbol;
            num -= value;
        }
    }
    return result;
};

const getHeadingPrefix = (idx: number, numbering: 'roman' | 'decimal' | 'alpha'): string => {
    const num = idx + 1;
    if (numbering === 'roman') return toRoman(num) + '.';
    if (numbering === 'alpha') return String.fromCharCode(64 + num) + '.';
    return num.toString() + '.';
};

interface SectionBlockProps {
    block: Block;
    idx: number;
    tmpl: TemplateConfig;
    onChange: (id: string, v: string) => void;
    onHeadingChange: (id: string, v: string) => void;
    onDelete: (id: string) => void;
}

const SectionBlock: React.FC<SectionBlockProps> = ({
    block, idx, tmpl, onChange, onHeadingChange, onDelete,
}) => {
    const [hovered, setHovered] = useState(false);
    const prefix = getHeadingPrefix(idx, tmpl.headingNumbering ?? 'decimal');
    return (
        <div onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)} style={{ breakInside: 'auto', pageBreakInside: 'auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: '10pt', marginBottom: '3pt' }}>
                <span style={{ fontSize: tmpl.sectionSize, fontWeight: tmpl.sectionWeight, fontVariant: tmpl.sectionVariant ?? 'normal', fontFamily: tmpl.fontFamily, fontStyle: tmpl.sectionAlign === 'center' ? 'normal' : (tmpl.subSectionStyle ?? 'normal'), flexShrink: 0, userSelect: 'none', minWidth: '1.5em', textAlign: 'right' }}>{prefix}</span>
                <input value={block.heading ?? ''} onChange={e => onHeadingChange(block.id, e.target.value)} style={{ fontSize: tmpl.sectionSize, fontWeight: tmpl.sectionWeight, textAlign: (tmpl.sectionAlign ?? 'left') as any, fontVariant: tmpl.sectionVariant ?? 'normal', fontFamily: tmpl.fontFamily, fontStyle: tmpl.sectionAlign === 'center' ? 'normal' : (tmpl.subSectionStyle ?? 'normal'), border: 'none', outline: 'none', background: 'transparent', flex: 1, cursor: 'text' }} placeholder="Section Title" />
                {hovered && <button onClick={() => onDelete(block.id)} style={{ color: '#f87171', flexShrink: 0, background: 'none', border: 'none', cursor: 'pointer' }} title="Delete section"><Trash2 style={{ width: 12, height: 12 }} /></button>}
            </div>
            <EditableBlock block={block} onChange={onChange} tmpl={tmpl} />
        </div>
    );
};

interface FrontMatterProps {
    tmpl: TemplateConfig;
    blocks: Block[];
    handleBlockChange: (id: string, v: string) => void;
}

const FrontMatter: React.FC<FrontMatterProps> = ({ tmpl, blocks, handleBlockChange }) => {
    const titleBlock = blocks.find(b => b.type === 'title');
    const authBlock = blocks.find(b => b.type === 'authors');
    const absBlock = blocks.find(b => b.type === 'abstract');
    const kwBlock = blocks.find(b => b.type === 'keywords');
    if (!titleBlock && !authBlock && !absBlock) return null;
    const isIEEE = tmpl.abstractStyle === 'bold-italic-em';
    return (
        <div style={{ marginBottom: '10pt', textAlign: 'center', fontFamily: tmpl.fontFamily, columnSpan: 'all' }}>
            {titleBlock && <EditableBlock block={titleBlock} onChange={handleBlockChange} tmpl={tmpl} style={{ fontSize: tmpl.titleSize, fontWeight: tmpl.titleWeight, lineHeight: 1.2, marginBottom: '10pt', display: 'block', textAlign: 'center' }} />}
            {authBlock && <EditableBlock block={authBlock} onChange={handleBlockChange} tmpl={tmpl} style={{ fontSize: tmpl.authorSize ?? tmpl.fontSize, marginBottom: '8pt', display: 'block', textAlign: 'center', lineHeight: 1.4 }} />}
            {absBlock && (
                <div style={{ textAlign: 'justify', margin: `0 ${tmpl.abstractIndent ?? 0} 8pt`, fontSize: '9pt', fontWeight: tmpl.abstractFontWeight as any ?? 'normal' }}>
                    {isIEEE ? <><span style={{ fontStyle: 'italic', fontWeight: 'bold' }}>Abstract—</span><EditableBlock block={absBlock} onChange={handleBlockChange} tmpl={tmpl} inline /></> : <><span style={{ fontWeight: 'bold' }}>Abstract. </span><EditableBlock block={absBlock} onChange={handleBlockChange} tmpl={tmpl} inline /></>}
                </div>
            )}
            {kwBlock && (
                <div style={{ textAlign: 'left', margin: `0 ${tmpl.abstractIndent ?? 0} 10pt`, fontSize: '9pt' }}>
                    <span style={{ fontWeight: 'bold', fontStyle: isIEEE ? 'italic' : 'normal' }}>{tmpl.kwLabel ?? 'Keywords'}— </span>
                    <EditableBlock block={kwBlock} onChange={handleBlockChange} tmpl={tmpl} inline />
                </div>
            )}
            <hr style={{ border: 'none', borderTop: '1px solid #ccc', margin: '8pt 0' }} />
        </div>
    );
};

interface SpecialBlockProps {
    block: Block;
    kind: SpecialBlockKind;
    tmpl: TemplateConfig;
    onChange: (id: string, v: string) => void;
    onDelete: (id: string) => void;
}

const SpecialBlock: React.FC<SpecialBlockProps> = ({ block, kind, tmpl, onChange, onDelete }) => {
    const [hovered, setHovered] = useState(false);
    const labels: Record<SpecialBlockKind, string> = {
        equation: 'Equation',
        figure: 'Figure Caption',
        table: 'Table Caption',
    };

    if (kind === 'equation') {
        return (
            <div onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)} style={{ marginTop: '10pt', marginBottom: '8pt', textAlign: 'center', position: 'relative' }}>
                <div style={{ fontSize: '9pt', color: '#4b5563', marginBottom: '2pt', fontStyle: 'italic' }}>{labels[kind]}</div>
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontFamily: tmpl.fontFamily }}>$</span>
                    <EditableBlock block={block} onChange={onChange} tmpl={tmpl} style={{ minWidth: '180px', textAlign: 'center' }} placeholder="a^2 + b^2 = c^2" />
                    <span style={{ fontFamily: tmpl.fontFamily }}>$</span>
                </div>
                {hovered && <button onClick={() => onDelete(block.id)} style={{ color: '#f87171', position: 'absolute', right: 0, top: 0, background: 'none', border: 'none', cursor: 'pointer' }} title="Delete block"><Trash2 style={{ width: 12, height: 12 }} /></button>}
            </div>
        );
    }

    if (kind === 'figure') {
        const parsed = parseSpecialAssetContent(block.content || '');
        return (
            <div onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)} style={{ marginTop: '10pt', marginBottom: '8pt', position: 'relative' }}>
                <div style={{ fontSize: '9pt', color: '#4b5563', marginBottom: '2pt', fontStyle: 'italic' }}>{labels[kind]}</div>
                {parsed.source ? (
                    <div style={{ border: '1px solid #d1d5db', borderRadius: 4, padding: 6, marginBottom: 6, background: '#f9fafb' }}>
                        <img src={parsed.source} alt={parsed.caption} style={{ maxWidth: '100%', maxHeight: 220, objectFit: 'contain', margin: '0 auto', display: 'block' }} />
                    </div>
                ) : (
                    <div style={{ border: '1px dashed #9ca3af', borderRadius: 4, padding: 10, marginBottom: 6, textAlign: 'center', color: '#6b7280', fontSize: '9pt' }}>
                        No image source yet. Add a line like: Source: http://localhost:8000/uploads/.../fig.png
                    </div>
                )}
                <div style={{ display: 'grid', gap: 6 }}>
                    <input
                        value={parsed.caption}
                        onChange={(e) => onChange(block.id, buildSpecialAssetContent(e.target.value, parsed.source, parsed.body))}
                        placeholder="Figure caption"
                        style={{ border: '1px solid #d1d5db', borderRadius: 4, padding: '6px 8px', fontSize: '9pt', fontFamily: tmpl.fontFamily, outline: 'none' }}
                    />
                    <input
                        value={parsed.source}
                        onChange={(e) => onChange(block.id, buildSpecialAssetContent(parsed.caption, e.target.value, parsed.body))}
                        placeholder="Image URL (http://localhost:8000/uploads/.../file.png)"
                        style={{ border: '1px solid #d1d5db', borderRadius: 4, padding: '6px 8px', fontSize: '9pt', fontFamily: 'monospace', outline: 'none' }}
                    />
                </div>
                {hovered && <button onClick={() => onDelete(block.id)} style={{ color: '#f87171', position: 'absolute', right: 0, top: 0, background: 'none', border: 'none', cursor: 'pointer' }} title="Delete block"><Trash2 style={{ width: 12, height: 12 }} /></button>}
            </div>
        );
    }

    if (kind === 'table') {
        const parsed = parseSpecialAssetContent(block.content || '');
        const table = parseMarkdownTable(parsed.body);
        return (
            <div onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)} style={{ marginTop: '10pt', marginBottom: '8pt', position: 'relative' }}>
                <div style={{ fontSize: '9pt', color: '#4b5563', marginBottom: '2pt', fontStyle: 'italic' }}>{labels[kind]}</div>
                {table ? (
                    <div style={{ border: '1px solid #d1d5db', borderRadius: 4, padding: 6, marginBottom: 6, overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '9pt' }}>
                            <thead>
                                <tr>
                                    {table.headers.map((h, i) => <th key={i} style={{ border: '1px solid #d1d5db', padding: '4px 6px', background: '#f3f4f6' }}>{h}</th>)}
                                </tr>
                            </thead>
                            <tbody>
                                {table.rows.map((r, ri) => (
                                    <tr key={ri}>
                                        {r.map((c, ci) => <td key={ci} style={{ border: '1px solid #e5e7eb', padding: '4px 6px' }}>{c}</td>)}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div style={{ border: '1px dashed #9ca3af', borderRadius: 4, padding: 10, marginBottom: 6, textAlign: 'center', color: '#6b7280', fontSize: '9pt' }}>
                        Add markdown table rows to preview the table.
                    </div>
                )}
                <div style={{ display: 'grid', gap: 6 }}>
                    <input
                        value={parsed.caption}
                        onChange={(e) => onChange(block.id, buildSpecialAssetContent(e.target.value, parsed.source, parsed.body))}
                        placeholder="Table caption"
                        style={{ border: '1px solid #d1d5db', borderRadius: 4, padding: '6px 8px', fontSize: '9pt', fontFamily: tmpl.fontFamily, outline: 'none' }}
                    />
                    <textarea
                        value={parsed.body || '| Column A | Column B |\n|---|---|\n| value 1 | value 2 |'}
                        onChange={(e) => onChange(block.id, buildSpecialAssetContent(parsed.caption, parsed.source, e.target.value))}
                        rows={5}
                        style={{ border: '1px solid #d1d5db', borderRadius: 4, padding: '6px 8px', fontSize: '9pt', fontFamily: 'monospace', outline: 'none', resize: 'vertical' }}
                    />
                </div>
                {hovered && <button onClick={() => onDelete(block.id)} style={{ color: '#f87171', position: 'absolute', right: 0, top: 0, background: 'none', border: 'none', cursor: 'pointer' }} title="Delete block"><Trash2 style={{ width: 12, height: 12 }} /></button>}
            </div>
        );
    }

    return (
        <div onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)} style={{ marginTop: '10pt', marginBottom: '8pt', position: 'relative' }}>
            <div style={{ fontSize: '9pt', color: '#4b5563', marginBottom: '2pt', fontStyle: 'italic' }}>{labels[kind]}</div>
            <EditableBlock block={block} onChange={onChange} tmpl={tmpl} placeholder={'Caption: Table caption\nSource: http://...\n\n| Column A | Column B |\n|---|---|\n| value 1 | value 2 |'} />
            {hovered && <button onClick={() => onDelete(block.id)} style={{ color: '#f87171', position: 'absolute', right: 0, top: 0, background: 'none', border: 'none', cursor: 'pointer' }} title="Delete block"><Trash2 style={{ width: 12, height: 12 }} /></button>}
        </div>
    );
};

interface TiptapBlockProps {
    block: Block;
    onChange: (id: string, markdown: string) => void;
    tmpl: TemplateConfig;
    inline?: boolean;
    style?: React.CSSProperties;
    placeholder?: string;
}

const markdownToHtml = (md: string): Promise<string> => Promise.resolve(marked.parse(md || ''));

const TiptapBlock: React.FC<TiptapBlockProps> = ({ block, onChange, tmpl, inline = false, style, placeholder = 'Start writing…' }) => {
    const lastExternalContent = useRef(block.content);
    const editor = useEditor({
        extensions: [StarterKit.configure({ heading: { levels: [1, 2, 3] } }), TextAlign.configure({ types: ['heading', 'paragraph'] }), Underline, Placeholder.configure({ placeholder })],
        editorProps: { attributes: { class: 'tiptap-block', spellcheck: 'true' } },
        onUpdate: ({ editor: ed }) => {
            const html = ed.getHTML();
            const md = turndownService.turndown(html);
            lastExternalContent.current = md;
            onChange(block.id, md);
        },
    });

    useEffect(() => {
        if (!editor) return;
        markdownToHtml(block.content).then(html => { editor.commands.setContent(html, false); });
    }, [editor]);

    useEffect(() => {
        if (!editor || block.content === lastExternalContent.current || editor.isFocused) return;
        lastExternalContent.current = block.content;
        markdownToHtml(block.content).then(html => { editor.commands.setContent(html, false); });
    }, [block.content, editor]);

    const containerStyle: React.CSSProperties = { outline: 'none', fontFamily: tmpl.fontFamily, fontSize: block.type === 'title' ? tmpl.titleSize : block.type === 'abstract' ? '9pt' : tmpl.fontSize, fontWeight: block.type === 'title' ? tmpl.titleWeight : 'normal', minHeight: '1em', ...style };
    return inline ? <span style={{ display: 'inline' }}><EditorContent editor={editor} style={containerStyle} /></span> : <EditorContent editor={editor} style={containerStyle} />;
};

const EditableBlock = TiptapBlock;
