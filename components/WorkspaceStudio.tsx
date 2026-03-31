import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
    Download, RefreshCw, Maximize, Minimize,
    Printer, Check, PlusCircle, Trash2,
    LayoutTemplate, ChevronDown, ChevronLeft, ChevronRight, Undo2, Redo2,
    FileText,
} from 'lucide-react';
import { Project } from '../types';
import Markdown from 'react-markdown';
import { useToastStore } from '../stores/toastStore';
import { saveDraft, loadDraft } from '../lib/api-client';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import TextAlign from '@tiptap/extension-text-align';
import Underline from '@tiptap/extension-underline';
import Placeholder from '@tiptap/extension-placeholder';
import TurndownService from 'turndown';
import { marked } from 'marked';

const turndownService = new TurndownService({ headingStyle: 'atx' });


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
const IEEE_MB_MM = 43;     // 1.69 in bottom margin
const IEEE_MS_MM = 14.32;  // 0.56 in side margins
const IEEE_BODY_H = A4_H_MM - IEEE_MT_MM - IEEE_MB_MM;
const IEEE_COL_GAP = 4.22; // 0.17 in spacing between columns

// PX per MM at 96dpi
const PX_PER_MM = 96 / 25.4;

// ─── Interfaces ───────────────────────────────────────────────────────────────
interface Block {
    id: string;
    type: 'title' | 'authors' | 'abstract' | 'keywords' | 'section';
    heading?: string;
    content: string;
}

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
    abstractIndent?: string;
    abstractStyle?: 'normal' | 'bold-italic-em'; // IEEE uses bold-italic with em dash
    sectionSize: string;
    sectionWeight: string;
    sectionAlign?: string;
    sectionVariant?: string;
    hdrStyle?: string;
    headingNumbering?: 'roman' | 'decimal'; // IEEE=roman, Springer=decimal
    showPageNumbers?: boolean;  // IEEE says yes for authors, no for publisher
    noHeaderOnFirst?: boolean;  // Springer: no header on page 1
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
        titleSize: '24pt', titleWeight: 'normal',  // IEEE: 24pt not bold
        abstractIndent: '12mm',
        abstractStyle: 'bold-italic-em',  // "Abstract—" bold-italic em dash
        sectionSize: '10pt', sectionWeight: 'bold',
        sectionAlign: 'center', sectionVariant: 'small-caps',
        hdrStyle: 'normal',
        headingNumbering: 'roman',
        showPageNumbers: false, // IEEE: publisher adds these
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
    const [activeTemplate, setActiveTemplate] = useState<string>('SPRINGER');
    const [templateMenuOpen, setTemplateMenuOpen] = useState(false);
    const [isRefactoring, setIsRefactoring] = useState(false);
    const [currentPage, setCurrentPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    // Editable running header / footer state
    const [runningHeader, setRunningHeader] = useState('');
    const [pageFooter, setPageFooter] = useState('');

    const { addToast } = useToastStore();
    const viewportRef = useRef<HTMLDivElement>(null);

    const isStreamingRef = useRef(isStreaming);
    useEffect(() => { isStreamingRef.current = isStreaming; }, [isStreaming]);

    const tmpl = TEMPLATES[activeTemplate] ?? TEMPLATES['SPRINGER'];

    // ── Parse markdown → blocks ───────────────────────────────────────────────
    useEffect(() => {
        if (!content) { setBlocks([]); return; }

        const newBlocks: Block[] = [];
        const lines = content.split('\n');
        let currentType: Block['type'] = 'title';
        let buffer: string[] = [];
        let currentHeading = '';

        const flush = (nextType?: Block['type'], nextHeading = '') => {
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
                        newBlocks.push({ id: `blk-${newBlocks.length}`, type: 'section', heading: currentHeading, content: blockContent });
                    }
                }
            }
            buffer = [];
            if (nextType) { currentType = nextType; currentHeading = nextHeading; }
        };

        lines.forEach(line => {
            if (line.match(/^##\s+Abstract/i)) flush('abstract');
            else if (line.match(/^##\s+Keywords/i)) flush('keywords');
            else if (line.match(/^##\s+/)) flush('section', line.replace(/^##\s*/, '').trim());
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
            else if (b.type === 'section') md += `## ${b.heading}\n${b.content}\n\n`;
        });
        onChange(md);
        setBlocks(updated);
    }, [onChange]);

    const handleBlockChange = (id: string, v: string) => saveBlocks(blocks.map(b => b.id === id ? { ...b, content: v } : b));
    const handleHeadingChange = (id: string, v: string) => saveBlocks(blocks.map(b => b.id === id ? { ...b, heading: v } : b));

    const addNewSection = () => {
        const nb: Block = { id: `blk-${Date.now()}`, type: 'section', heading: 'New Section', content: 'Start writing here...' };
        saveBlocks([...blocks, nb]);
    };

    const deleteBlock = (id: string) => {
        if (confirm('Delete this section?')) saveBlocks(blocks.filter(b => b.id !== id));
    };

    const insertSectionAfter = (afterId: string) => {
        const idx = blocks.findIndex(b => b.id === afterId);
        const nb: Block = { id: `blk-${Date.now()}`, type: 'section', heading: 'New Section', content: 'Start writing here...' };
        const newBlocks = [...blocks];
        newBlocks.splice(idx + 1, 0, nb);
        saveBlocks(newBlocks);
    };

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

    // Seed running header from first title/author block
    useEffect(() => {
        if (runningHeader) return;
        const authors = blocks.find(b => b.type === 'authors')?.content ?? '';
        const authorShort = authors.split('\n')[0]?.split(',')[0]?.trim() ?? '';
        if (authorShort) setRunningHeader(`${authorShort} et al.`);
    }, [blocks]);

    // ── Natural content height → page count ──────────────────────────────────
    const contentRef = useRef<HTMLDivElement>(null);
    useEffect(() => {
        const measure = () => {
            if (!contentRef.current) return;
            const h = contentRef.current.getBoundingClientRect().height / PX_PER_MM;
            setTotalPages(Math.max(1, Math.ceil(h / tmpl.bodyH)));
        };
        const ro = new ResizeObserver(measure);
        if (contentRef.current) ro.observe(contentRef.current);
        measure();
        return () => ro.disconnect();
    }, [blocks, activeTemplate]);

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
        setIsRefactoring(true);
        setTemplateMenuOpen(false);
        setTimeout(() => { setActiveTemplate(key); setIsRefactoring(false); }, 400);
    };

    // ── Render ────────────────────────────────────────────────────────────────
    const pageHeightPx = A4_H_MM * PX_PER_MM;
    const bodyHeightPx = tmpl.bodyH * PX_PER_MM;
    const marginTopPx = tmpl.mt * PX_PER_MM;
    const marginSidePx = tmpl.ms * PX_PER_MM;
    const marginBotPx = tmpl.mb * PX_PER_MM;
    const hdrTopPx = tmpl.hdrMm * PX_PER_MM;

    const title = blocks.find(b => b.type === 'title')?.content ?? activeFileName ?? 'Untitled';
    const authors = blocks.find(b => b.type === 'authors')?.content ?? '';
    const authorShort = authors.split('\n')[0]?.split(',')[0]?.trim() ?? '';
    const derivedHdrLeft = authorShort ? `${authorShort} et al.` : '';
    const derivedHdrRight = title.length > 50 ? title.slice(0, 48) + '…' : title;

    return (
        <div className="flex flex-col h-full bg-[#525659] font-sans overflow-hidden">
            <style>{`
                /* ── Tiptap base reset ── */
                .tiptap-block { outline: none; min-height: 1em; }
                .tiptap-block:focus { outline: none; }
                .tiptap-block.ProseMirror-focused { outline: none; }
                .tiptap-block p { margin-bottom: 4pt; }
                .tiptap-block p.is-editor-empty:first-child::before {
                    color: #adb5bd; content: attr(data-placeholder);
                    float: left; height: 0; pointer-events: none;
                }
                /* Tiptap wrapper focus ring (indigo dashed) */
                .ProseMirror:focus-visible { outline: none; }
                .tiptap-block:focus-within { outline: 2px dashed rgba(99,102,241,0.5); outline-offset: 2px; border-radius: 2px; }

                /* ── IEEE formatting ── */
                .ieee-format .tiptap-block { font-family: "Times New Roman", Times, serif; font-size: 10pt; line-height: 1.15; }
                .ieee-format .tiptap-block h1 { font-size: 10pt; font-weight: bold; text-align: center; font-variant: small-caps; text-transform: uppercase; margin: 10pt 0 4pt; }
                .ieee-format .tiptap-block h2 { font-size: 10pt; font-weight: normal; font-style: italic; text-align: left; margin: 8pt 0 3pt; }
                .ieee-format .tiptap-block h3 { font-size: 10pt; font-weight: normal; font-style: italic; text-align: left; margin: 6pt 0 2pt; }
                .ieee-format .tiptap-block p { text-align: justify; margin-bottom: 0; text-indent: 12pt; }
                .ieee-format .tiptap-block strong { font-weight: bold; }
                .ieee-format .tiptap-block em { font-style: italic; }

                /* ── Springer formatting ── */
                .springer-format .tiptap-block { font-family: "Times New Roman", Times, serif; font-size: 10pt; line-height: 1.2; }
                .springer-format .tiptap-block h1 { font-size: 10pt; font-weight: bold; text-align: left; margin: 12pt 0 4pt; }
                .springer-format .tiptap-block h2 { font-size: 10pt; font-weight: bold; font-style: italic; text-align: left; margin: 10pt 0 3pt; }
                .springer-format .tiptap-block h3 { font-size: 10pt; font-style: italic; text-align: left; margin: 8pt 0 2pt; }
                .springer-format .tiptap-block p { text-align: justify; margin-bottom: 4pt; }
                .springer-format .tiptap-block ul, .springer-format .tiptap-block ol { padding-left: 16pt; }

                /* ── Print ── */
                @media print {
                    .no-print { display: none !important; }
                    .paper-doc { box-shadow: none !important; }
                    .tiptap-block { outline: none !important; }
                }
            `}</style>

            {/* ── MAIN TOOLBAR ── */}
            <div className="no-print h-12 bg-white border-b border-gray-200 flex items-center justify-between px-4 shrink-0 z-30 shadow-sm">
                <div className="flex items-center gap-3">
                    <span className="font-bold text-gray-700 flex items-center gap-2">
                        <Printer className="w-4 h-4 text-indigo-600" /> Live Paper
                    </span>

                    {/* Template picker */}
                    <div className="relative">
                        <button
                            onClick={() => setTemplateMenuOpen(v => !v)}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-md text-xs font-semibold text-gray-700"
                        >
                            <LayoutTemplate className="w-3.5 h-3.5 text-gray-400" />
                            {TEMPLATES[activeTemplate]?.name ?? activeTemplate}
                            <ChevronDown className="w-3 h-3 text-gray-400" />
                        </button>
                        {templateMenuOpen && (
                            <div className="absolute top-full left-0 mt-1 w-52 bg-white border border-gray-200 rounded-lg shadow-xl z-50 py-1">
                                {Object.entries(TEMPLATES).map(([key, t]) => (
                                    <button key={key} onClick={() => handleTemplateSwitch(key)}
                                        className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between
                                            ${activeTemplate === key ? 'bg-indigo-50 text-indigo-600 font-bold' : 'hover:bg-gray-50 text-gray-700'}`}>
                                        {t.name}
                                        {activeTemplate === key && <Check className="w-3 h-3" />}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Zoom */}
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
                    <button onClick={addNewSection} className="flex items-center gap-1 px-3 py-1.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded text-xs font-bold">
                        <PlusCircle className="w-3.5 h-3.5" /> Add Section
                    </button>
                    <button onClick={() => window.print()} className="flex items-center gap-1 px-3 py-1.5 bg-gray-800 text-white hover:bg-gray-700 rounded text-xs font-bold">
                        <Download className="w-3.5 h-3.5" /> Export PDF
                    </button>
                </div>
            </div>

            {/* ── FORMAT INFO BAR ── */}
            <div className="no-print bg-gray-50 border-b border-gray-200 px-4 py-1.5 flex items-center gap-5 text-xs text-gray-500 shrink-0 font-mono">
                <span className="text-indigo-700 font-semibold font-sans">{tmpl.name}</span>
                <span>A4 • {tmpl.cols === 2 ? '2-column' : '1-column'}</span>
                <span>Body {tmpl.fontSize} / {tmpl.lineHeight}×</span>
                <span>Title {tmpl.titleSize}</span>
                <span title="Top / Bottom margins">Margins ↑{tmpl.mt}mm ↓{tmpl.mb}mm ↔{tmpl.ms}mm</span>
                <span>Headings {tmpl.headingNumbering === 'roman' ? 'I. Roman (centered)' : '1. Decimal (left)'}</span>
                <span>Abstract {tmpl.abstractStyle === 'bold-italic-em' ? 'Bold-italic em-dash (IEEE)' : 'Normal (Springer)'}</span>
                {tmpl.showPageNumbers === false && <span className="text-amber-600">No page nums (publisher adds)</span>}
            </div>

            {/* ── VIEWPORT ── */}
            <div
                ref={viewportRef}
                className="flex-1 overflow-y-scroll relative"
                style={{ background: '#525659', padding: '32px 0 80px' }}
            >
                {isRefactoring && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
                        <div className="bg-white p-6 rounded-xl shadow-2xl flex flex-col items-center gap-3">
                            <RefreshCw className="w-7 h-7 text-indigo-600 animate-spin" />
                            <p className="text-sm font-semibold">Switching to {TEMPLATES[activeTemplate]?.name}…</p>
                        </div>
                    </div>
                )}

                {/* ── Document ── */}
                <div
                    className="paper-doc"
                    style={{
                        width: `${A4_W_MM}mm`,
                        margin: '0 auto',
                        position: 'relative',
                        background: 'white',
                        boxShadow: '0 2px 16px rgba(0,0,0,0.3), 0 8px 40px rgba(0,0,0,0.2)',
                        transform: `scale(${zoom / 100})`,
                        transformOrigin: 'top center',
                        marginBottom: zoom < 100 ? `${(zoom / 100 - 1) * A4_H_MM * totalPages * 0.35}px` : 0,
                    }}
                >
                    {blocks.length === 0 ? (
                        <div style={{
                            minHeight: `${A4_H_MM}mm`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            padding: `${tmpl.mt}mm ${tmpl.ms}mm`,
                            fontFamily: tmpl.fontFamily, color: '#9ca3af',
                        }}>
                            <div style={{ textAlign: 'center' }}>
                                <FileText style={{ width: 40, height: 40, margin: '0 auto 12px', opacity: 0.3 }} />
                                <p style={{ fontSize: '10pt' }}>Your paper will appear here</p>
                                <p style={{ fontSize: '8pt', opacity: 0.6, marginTop: 4 }}>Draft sections using the Co-Author panel →</p>
                            </div>
                        </div>
                    ) : (
                        <>
                            {/* Page gap bars at each A4 boundary (like Overleaf) */}
                            {Array.from({ length: totalPages - 1 }, (_, i) => (
                                <div key={`gap-${i}`} style={{
                                    position: 'absolute',
                                    left: -32, right: -32,
                                    top: `${(i + 1) * A4_H_MM}mm`,
                                    height: `${PAGE_GAP_MM}mm`,
                                    background: 'linear-gradient(to bottom, rgba(0,0,0,0.18) 0%, #404347 15%, #404347 85%, rgba(0,0,0,0.18) 100%)',
                                    zIndex: 20,
                                    pointerEvents: 'none',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                }}>
                                    <span style={{
                                        fontSize: '7pt', color: 'rgba(255,255,255,0.45)',
                                        fontFamily: 'sans-serif', letterSpacing: '0.1em',
                                        userSelect: 'none',
                                    }}>Page {i + 2}</span>
                                </div>
                            ))}

                            {/* Running headers at each page boundary */}
                            {Array.from({ length: totalPages }, (_, i) => {
                                const skipFirst = tmpl.noHeaderOnFirst && i === 0;
                                if (skipFirst) return null;
                                return (
                                    <div key={`hdr-${i}`} style={{
                                        position: 'absolute',
                                        left: `${tmpl.ms}mm`, right: `${tmpl.ms}mm`,
                                        top: `calc(${i * A4_H_MM}mm + ${hdrTopPx}px)`,
                                        display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                                        borderBottom: '1px solid #000',
                                        paddingBottom: '2pt',
                                        fontSize: '9pt',
                                        fontFamily: tmpl.fontFamily,
                                        fontStyle: tmpl.hdrStyle === 'italic' ? 'italic' : 'normal',
                                        zIndex: 5,
                                        background: 'white',
                                    }}>
                                        {i === 0 || i === (tmpl.noHeaderOnFirst ? 1 : 0) ? (
                                            // First editable page header
                                            <>
                                                <input value={runningHeader} onChange={e => setRunningHeader(e.target.value)}
                                                    placeholder={derivedHdrLeft}
                                                    style={{ border: 'none', outline: 'none', background: 'transparent', fontStyle: 'inherit', fontFamily: 'inherit', fontSize: 'inherit', width: '60%', cursor: 'text' }} />
                                                <input value={pageFooter} onChange={e => setPageFooter(e.target.value)}
                                                    placeholder={derivedHdrRight}
                                                    style={{ border: 'none', outline: 'none', background: 'transparent', fontStyle: 'inherit', fontFamily: 'inherit', fontSize: 'inherit', textAlign: 'right', width: '40%', cursor: 'text' }} />
                                            </>
                                        ) : (
                                            <>
                                                <span>{i % 2 === 0 ? (runningHeader || derivedHdrLeft) : (pageFooter || derivedHdrRight)}</span>
                                                {tmpl.showPageNumbers !== false && <span style={{ fontStyle: 'normal' }}>{i + 1}</span>}
                                            </>
                                        )}
                                    </div>
                                );
                            })}

                            {/* Main content area — flows naturally, no clipping */}
                            <div
                                ref={contentRef}
                                className={`paper-content-area ${tmpl.name.toLowerCase()}-format`}
                                style={{
                                    marginTop: `${tmpl.mt}mm`,
                                    marginLeft: `${tmpl.ms}mm`,
                                    marginRight: `${tmpl.ms}mm`,
                                    paddingBottom: `${tmpl.mb}mm`,
                                    // For multi-column (IEEE): CSS columns fill naturally
                                    columnCount: tmpl.cols,
                                    columnGap: tmpl.colGap ? `${tmpl.colGap}mm` : undefined,
                                    columnFill: 'auto',
                                    // Height fills N pages so CSS columns flow across pages
                                    minHeight: `${tmpl.bodyH * totalPages}mm`,
                                    fontFamily: tmpl.fontFamily,
                                    fontSize: tmpl.fontSize,
                                    lineHeight: tmpl.lineHeight,
                                    textAlign: 'justify',
                                    color: '#000',
                                }}
                            >
                                <FrontMatter tmpl={tmpl} blocks={blocks} handleBlockChange={handleBlockChange} />
                                {blocks.filter(b => b.type === 'section').map((block, idx) => (
                                    <SectionBlock
                                        key={block.id}
                                        block={block}
                                        idx={idx}
                                        tmpl={tmpl}
                                        onChange={handleBlockChange}
                                        onHeadingChange={handleHeadingChange}
                                        onDelete={deleteBlock}
                                    />
                                ))}
                            </div>
                        </>
                    )}
                </div>
            </div>

            {/* ── PAGINATION PILL ── */}
            <div className="no-print absolute bottom-6 left-1/2 -translate-x-1/2 z-40">
                <div className="bg-gray-900 text-white rounded-full shadow-2xl px-4 py-2 flex items-center gap-3 text-sm font-medium border border-gray-700/50">
                    <button onClick={() => scrollToPage(currentPage - 1)} disabled={currentPage <= 1}
                        className="p-1 hover:bg-gray-700 rounded-full disabled:opacity-30">
                        <ChevronLeft className="w-4 h-4" />
                    </button>
                    <span className="text-gray-400 text-xs">Page</span>
                    <input type="number" min={1} max={totalPages} value={currentPage}
                        onChange={e => { const v = parseInt(e.target.value); if (!isNaN(v)) scrollToPage(v); }}
                        className="w-7 bg-transparent text-center focus:outline-none font-bold text-sm" />
                    <span className="text-gray-400 text-xs">of {totalPages}</span>
                    <button onClick={() => scrollToPage(currentPage + 1)} disabled={currentPage >= totalPages}
                        className="p-1 hover:bg-gray-700 rounded-full disabled:opacity-30">
                        <ChevronRight className="w-4 h-4" />
                    </button>
                </div>
            </div>
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

const getHeadingPrefix = (idx: number, numbering: 'roman' | 'decimal'): string => {
    const num = idx + 1;
    if (numbering === 'roman') {
        return toRoman(num) + '.';
    }
    return num.toString() + '.';
};

// ─── SectionBlock ─────────────────────────────────────────────────────────────
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
        <div
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={{ breakInside: 'avoid-column', pageBreakInside: 'avoid' }}
        >
            {/* Heading row: prefix + editable title + delete */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: '10pt', marginBottom: '3pt' }}>
                <span style={{
                    fontSize: tmpl.sectionSize, fontWeight: tmpl.sectionWeight,
                    fontVariant: tmpl.sectionVariant ?? 'normal', fontFamily: tmpl.fontFamily,
                    flexShrink: 0, userSelect: 'none', minWidth: '2em', textAlign: 'right',
                }}>{prefix}</span>
                <input
                    value={block.heading ?? ''}
                    onChange={e => onHeadingChange(block.id, e.target.value)}
                    style={{
                        fontSize: tmpl.sectionSize, fontWeight: tmpl.sectionWeight,
                        textAlign: (tmpl.sectionAlign ?? 'left') as any,
                        fontVariant: tmpl.sectionVariant ?? 'normal', fontFamily: tmpl.fontFamily,
                        border: 'none', outline: 'none', background: 'transparent',
                        flex: 1, cursor: 'text',
                    }}
                    placeholder="Section Title"
                />
                {hovered && (
                    <button
                        onClick={() => onDelete(block.id)}
                        style={{ color: '#f87171', flexShrink: 0, background: 'none', border: 'none', cursor: 'pointer' }}
                        title="Delete section"
                    >
                        <Trash2 style={{ width: 12, height: 12 }} />
                    </button>
                )}
            </div>

            {/* Body — always editable contentEditable */}
            <EditableBlock block={block} onChange={onChange} tmpl={tmpl} />
        </div>
    );
};

// ─── FrontMatter ──────────────────────────────────────────────────────────────
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
        <div style={{ marginBottom: '10pt', textAlign: 'center', fontFamily: tmpl.fontFamily }}>
            {titleBlock && (
                <EditableBlock block={titleBlock} onChange={handleBlockChange} tmpl={tmpl}
                    style={{ fontSize: tmpl.titleSize, fontWeight: tmpl.titleWeight, lineHeight: 1.2, marginBottom: '10pt', display: 'block', textAlign: 'center' }}
                />
            )}
            {authBlock && (
                <EditableBlock block={authBlock} onChange={handleBlockChange} tmpl={tmpl}
                    style={{ fontSize: tmpl.fontSize, marginBottom: '8pt', display: 'block', textAlign: 'center' }}
                />
            )}
            {absBlock && (
                <div style={{
                    textAlign: 'justify',
                    margin: `0 ${tmpl.abstractIndent ?? 0} 8pt`,
                    fontSize: '9pt',
                    // IEEE: entire abstract is bold
                    fontWeight: isIEEE ? 'bold' : 'normal',
                }}>
                    {isIEEE ? (
                        // IEEE: "Abstract—" bold italic, rest bold
                        <><span style={{ fontStyle: 'italic' }}>Abstract—</span>
                            <EditableBlock block={absBlock} onChange={handleBlockChange} tmpl={tmpl} inline /></>
                    ) : (
                        // Springer: "Abstract." bold text, rest normal
                        <><span style={{ fontWeight: 'bold' }}>Abstract. </span>
                            <EditableBlock block={absBlock} onChange={handleBlockChange} tmpl={tmpl} inline /></>
                    )}
                </div>
            )}
            {kwBlock && (
                <div style={{ textAlign: 'left', margin: `0 ${tmpl.abstractIndent ?? 0} 10pt`, fontSize: '9pt' }}>
                    <span style={{ fontWeight: 'bold' }}>Keywords: </span>
                    <EditableBlock block={kwBlock} onChange={handleBlockChange} tmpl={tmpl} inline />
                </div>
            )}
            <hr style={{ border: 'none', borderTop: '1px solid #ccc', margin: '8pt 0' }} />
        </div>
    );
};

// ─── TiptapBlock ──────────────────────────────────────────────────────────────
interface TiptapBlockProps {
    block: Block;
    onChange: (id: string, markdown: string) => void;
    tmpl: TemplateConfig;
    inline?: boolean;
    style?: React.CSSProperties;
    placeholder?: string;
}

// Map Markdown string -> Tiptap HTML once
const markdownToHtml = (md: string): Promise<string> =>
    Promise.resolve(marked.parse(md || ''));

const TiptapBlock: React.FC<TiptapBlockProps> = ({
    block, onChange, tmpl, inline = false, style, placeholder = 'Start writing…',
}) => {
    const lastExternalContent = useRef(block.content);

    const editor = useEditor({
        extensions: [
            StarterKit.configure({ heading: { levels: [1, 2, 3] } }),
            TextAlign.configure({ types: ['heading', 'paragraph'] }),
            Underline,
            Placeholder.configure({ placeholder }),
        ],
        editorProps: {
            attributes: {
                class: 'tiptap-block',
                spellcheck: 'true',
            },
        },
        // Fire onChange with Markdown on every edit
        onUpdate: ({ editor: ed }) => {
            const html = ed.getHTML();
            const md = turndownService.turndown(html);
            lastExternalContent.current = md;
            onChange(block.id, md);
        },
    });

    // Seed content on first mount
    useEffect(() => {
        if (!editor) return;
        markdownToHtml(block.content).then(html => {
            editor.commands.setContent(html, false);
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [editor]);

    // Sync external content updates (e.g. AI streaming) without disrupting focus
    useEffect(() => {
        if (!editor) return;
        if (block.content === lastExternalContent.current) return;
        if (editor.isFocused) return; // never interrupt the user mid-typing
        lastExternalContent.current = block.content;
        markdownToHtml(block.content).then(html => {
            const { from, to } = editor.state.selection;
            editor.commands.setContent(html, false);
            // restore cursor if practical
            try { editor.commands.setTextSelection({ from, to }); } catch { /* ignore */ }
        });
    }, [block.content, editor]);

    const containerStyle: React.CSSProperties = {
        outline: 'none',
        fontFamily: tmpl.fontFamily,
        fontSize: block.type === 'title' ? tmpl.titleSize
            : block.type === 'abstract' ? '9pt'
                : tmpl.fontSize,
        fontWeight: block.type === 'title' ? tmpl.titleWeight : 'normal',
        minHeight: '1em',
        ...style,
    };

    return inline
        ? <span style={{ display: 'inline' }}><EditorContent editor={editor} style={containerStyle} /></span>
        : <EditorContent editor={editor} style={containerStyle} />;
};

// ─── Keep legacy alias so FrontMatter/SectionBlock call sites stay unchanged ────────
// FrontMatter and SectionBlock use <EditableBlock> — alias to TiptapBlock
const EditableBlock = TiptapBlock;
