
import React, { useState, useRef, useEffect } from 'react';
import {
    Settings, ArrowLeft, X, PanelRightClose, PanelLeftClose, Upload,
    BookOpen, PlusCircle, CheckSquare, Square, MoreVertical, Activity, PenTool, MessageSquarePlus, MessageSquare,
    Send, Loader2, Sparkles
} from 'lucide-react';
import { AppMode, ViewState, Project, ProjectAsset, ProjectFile, AgentState, AgentLog, ChatSession, LibraryPage } from '../types';
import { fetchChatSessions, createChatSession, fetchLibraryPage } from '../lib/api-client';
import { AgentAvatar } from './AgentAvatar';
import Markdown from 'react-markdown';
import { useStreamingChat } from '../hooks/useStreaming';

interface SidebarLeftProps {
    appMode: AppMode;
    viewState: ViewState;
    setAppMode: (mode: AppMode) => void;
    onBackToDiscovery: () => void;
    onBackToDashboard: () => void;
    activeProject: Project | null;
    onOpenPaper: (id: string) => void;
    selectedContextIds: Set<string>;
    onToggleContext: (id: string) => void;
    onCloseMobile?: () => void;

    // Modals
    onOpenPdfModal: () => void;

    onAnalyzeAsset: (asset: ProjectAsset) => void;
    onCollapse: () => void;
    isCollapsed: boolean;
    position?: 'left' | 'right';

    // File System Props
    files?: ProjectFile[];
    activeFileId?: string;
    onFileSelect?: (id: string) => void;
    onCreateFile?: (name: string, parentId?: string) => void;
    onCreateFolder?: (name: string, parentId?: string) => void;
    onDeleteFile?: (id: string) => void;

    // Agent State
    agentState?: AgentState;
    setAgentState?: (state: AgentState) => void;
    addAgentLog?: (source: AgentLog['source'], message: string, status?: AgentLog['status']) => void;
    logs?: AgentLog[];
    pendingMessage?: string | null;
    onClearPendingMessage?: () => void;
    // Session Props
    activeSessionId?: string | null;
    onSessionSelect?: (id: string | null) => void;
}

export const SidebarLeft: React.FC<SidebarLeftProps> = ({
    appMode,
    viewState,
    setAppMode,
    onBackToDashboard,
    onBackToDiscovery,
    activeProject,
    onOpenPaper,
    selectedContextIds,
    onToggleContext,
    onCloseMobile,
    onOpenPdfModal,
    onCollapse,
    position = 'left',

    agentState = AgentState.IDLE,
    addAgentLog,
    logs = [],
    activeSessionId,
    onSessionSelect
}) => {

    const isStudio = appMode === AppMode.STUDIO;
    // Use real papers from the project, initialized empty if null
    const projectPapers = activeProject?.papers || [];

    // Library pagination state
    const [libraryPage, setLibraryPage] = useState<LibraryPage | null>(null);
    const [libraryPageIndex, setLibraryPageIndex] = useState(1);
    const [isLibraryLoading, setIsLibraryLoading] = useState(false);

    // Local State
    const [sessions, setSessions] = useState<ChatSession[]>([]);
    const [sidebarTab, setSidebarTab] = useState<'library' | 'chats'>('library');
    const [libraryQuery, setLibraryQuery] = useState('');

    // Fetch Sessions on mount / project change
    useEffect(() => {
        if (activeProject) {
            fetchChatSessions(activeProject.id).then(setSessions);
        } else {
            setSessions([]);
        }
    }, [activeProject]);

    // Reset library pagination on project change
    useEffect(() => {
        setLibraryPageIndex(1);
    }, [activeProject?.id]);

    // Fetch paginated library
    useEffect(() => {
        const loadLibrary = async () => {
            if (!activeProject) {
                setLibraryPage(null);
                return;
            }

            setIsLibraryLoading(true);
            try {
                const page = await fetchLibraryPage(activeProject.id, libraryPageIndex, 10);
                setLibraryPage(page);
            } catch (error) {
                console.error('Failed to load library page:', error);
                setLibraryPage(null);
            } finally {
                setIsLibraryLoading(false);
            }
        };

        loadLibrary();
    }, [activeProject, libraryPageIndex]);

    // Create New Session Handler
    const handleNewChat = async () => {
        if (!activeProject || !onSessionSelect) return;
        const newSession = await createChatSession(activeProject.id, `New Chat ${sessions.length + 1}`);
        if (newSession) {
            setSessions(prev => [newSession, ...prev]);
            onSessionSelect(newSession.id);
            setSidebarTab('chats');
        }
    };

    // Tooltip State
    const [hoveredPaper, setHoveredPaper] = useState<{ id: string, top: number, left: number } | null>(null);
    const hoverTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
    const logsEndRef = useRef<HTMLDivElement>(null);

    // ── Co-Author Chat ────────────────────────────────────────────────────────
    const [chatMessages, setChatMessages] = useState<{ role: 'user' | 'agent', text: string }[]>([]);
    const [chatInput, setChatInput]       = useState('');
    const chatEndRef = useRef<HTMLDivElement>(null);

    const { streamChat, isStreaming: isChatStreaming } = useStreamingChat();

    // Seed greeting
    useEffect(() => {
        if (isStudio && chatMessages.length === 0) {
            setChatMessages([{ role: 'agent', text: 'Hi! I\'m your Co-Author. Ask me anything about your paper, your sources, or how to improve a section.' }]);
        }
    }, [isStudio]);

    // Auto-scroll chat
    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [chatMessages]);

    const handleSendMessage = async (textOverride?: string) => {
        const text = (textOverride || chatInput).trim();
        if (!text || !activeProject) return;
        if (!textOverride) setChatInput('');
        setChatMessages(prev => [...prev, { role: 'user', text }]);
        try {
            const paperIds = selectedContextIds && selectedContextIds.size > 0
                ? Array.from(selectedContextIds)
                : (activeProject.papers || []).map(p => p.id);
            await streamChat(
                { project_id: activeProject.id, message: text, selected_paper_ids: paperIds, lab_asset_ids: [] },
                undefined,
                (fullText) => { setChatMessages(prev => [...prev, { role: 'agent', text: fullText }]); }
            );
        } catch (e) {
            console.error(e);
        }
    };

    // Auto-scroll logs
    useEffect(() => {
        if (logsEndRef.current && isStudio) {
            logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [logs, isStudio]);

    const handleMouseEnter = (e: React.MouseEvent<HTMLDivElement>, id: string) => {
        if (hoverTimeout.current) clearTimeout(hoverTimeout.current);
        if (window.innerWidth < 1024) return;
        const rect = e.currentTarget.getBoundingClientRect();
        const left = position === 'left' ? rect.right + 12 : undefined;
        setHoveredPaper({ id, top: rect.top, left: left || 0 });
    };

    const handleMouseLeave = () => {
        hoverTimeout.current = setTimeout(() => { setHoveredPaper(null); }, 50);
    };

    // Derived Assets
    const libraryItems = libraryPage?.items || projectPapers;
    const normalizedQuery = libraryQuery.trim().toLowerCase();
    const filteredLibraryItems = libraryItems
        .filter((paper) => {
            if (!normalizedQuery) return true;
            const title = (paper.title || '').toLowerCase();
            const authors = Array.isArray(paper.authors) ? paper.authors.join(' ').toLowerCase() : '';
            const year = String(paper.year || '').toLowerCase();
            return title.includes(normalizedQuery) || authors.includes(normalizedQuery) || year.includes(normalizedQuery);
        })
        .sort((a, b) => {
            const aSelected = selectedContextIds.has(a.id) ? 1 : 0;
            const bSelected = selectedContextIds.has(b.id) ? 1 : 0;
            if (aSelected !== bSelected) return bSelected - aSelected;
            return (b.year || 0) - (a.year || 0);
        });

    const totalPapers = libraryPage?.total ?? projectPapers.length;
    const totalPages = libraryPage?.pages ?? 1;
    const activePaper = hoveredPaper ? filteredLibraryItems.find(p => p.id === hoveredPaper.id) : null;
    const activePaperSummary = activePaper?.summary || 'No summary available';

    // Dynamic Border Class based on position
    const borderClass = position === 'left' ? 'border-r' : 'border-l';

    return (
        <>
            <aside className={`h-full flex flex-col ${borderClass} transition-colors duration-500 z-20 ${isStudio ? 'bg-black border-gray-800 text-gray-300' : 'bg-gray-50 border-gray-200 text-gray-700'}`}>

                {/* Header */}
                <div className={`h-12 flex items-center justify-between px-4 border-b border-inherit gap-3 bg-inherit shrink-0 ${position === 'right' ? 'flex-row-reverse' : ''}`}>
                    <div className="flex-1 flex items-center gap-3 overflow-hidden">
                        <button
                            onClick={onBackToDashboard}
                            className="p-1.5 hover:bg-gray-200/50 dark:hover:bg-gray-800 rounded-md transition-colors group"
                            title="Back to Dashboard"
                        >
                            <ArrowLeft className="w-4 h-4 opacity-70 group-hover:opacity-100" />
                        </button>
                        <div className={`flex-1 overflow-hidden ${isStudio ? 'text-left' : 'text-right'}`}>
                            <div className="text-[10px] font-semibold opacity-50 uppercase tracking-wider truncate">
                                {isStudio ? 'AGENT MONITOR' : 'CONTEXT'}
                            </div>
                            <div className="font-bold text-xs truncate">{activeProject?.title || 'Untitled'}</div>
                        </div>
                    </div>

                    <div className="flex items-center pl-2">
                        <button onClick={onCollapse} className="hidden lg:block p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200" title="Collapse Sidebar">
                            {position === 'left' ? <PanelLeftClose className="w-4 h-4" /> : <PanelRightClose className="w-4 h-4" />}
                        </button>
                        <button
                            onClick={onCloseMobile}
                            className="lg:hidden p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>
                </div>

                {/* --- STUDIO MODE: MONITOR + CHAT --- */}
                {isStudio && (
                    <div className="flex-1 flex flex-col min-h-0 overflow-hidden">

                        {/* 1. COMPACT MONITOR SECTION */}
                        <div className="shrink-0 bg-[#0a0a0a] flex flex-col items-center pt-3 pb-1">
                            <div className="transform scale-75 -my-3">
                                <AgentAvatar state={agentState} />
                            </div>
                            {/* Compact Console Logs */}
                            <div className="w-full h-24 overflow-y-auto px-4 py-1 font-mono text-[10px] space-y-1 mt-2">
                                {logs.length === 0 ? (
                                    <div className="text-gray-600 italic text-center mt-2 opacity-50">System Idle.</div>
                                ) : (
                                    logs.map(log => (
                                        <div key={log.id} className="text-green-500/90 leading-tight border-l-2 border-green-500/20 pl-2 py-0.5">
                                            <div className={log.source === 'Thought' ? 'text-amber-500 italic' : ''}>{log.message}</div>
                                        </div>
                                    ))
                                )}
                                <div ref={logsEndRef} />
                            </div>
                            <div className="w-full h-6 -mt-6 bg-gradient-to-t from-black to-transparent pointer-events-none relative z-10" />
                        </div>

                        {/* 2. CO-AUTHOR CHAT */}
                        <div className="flex-1 flex flex-col min-h-0 bg-[#0d0d0d] border-t border-gray-800">
                            {/* Header */}
                            <div className="shrink-0 px-3 py-2 border-b border-gray-800 flex items-center gap-2">
                                <Sparkles className="w-3 h-3 text-indigo-400" />
                                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Co-Author Chat</span>
                            </div>
                            {/* Messages */}
                            <div className="flex-1 overflow-y-auto p-3 space-y-2">
                                {chatMessages.map((m, i) => (
                                    <div key={i} className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
                                        <div className={`max-w-[95%] rounded-lg px-3 py-2 text-xs leading-relaxed ${m.role === 'user' ? 'bg-indigo-900/50 text-indigo-100 border border-indigo-500/30' : 'bg-gray-800 text-gray-300'}`}>
                                            {m.role === 'agent' ? <Markdown>{m.text}</Markdown> : m.text}
                                        </div>
                                    </div>
                                ))}
                                {isChatStreaming && (
                                    <div className="flex items-center gap-2 text-gray-500 text-xs italic">
                                        <Loader2 className="w-3 h-3 animate-spin" /> Thinking...
                                    </div>
                                )}
                                <div ref={chatEndRef} />
                            </div>
                            {/* Input */}
                            <div className="p-2 border-t border-gray-800 bg-[#18181b] shrink-0">
                                <div className="relative">
                                    <input
                                        value={chatInput}
                                        onChange={(e) => setChatInput(e.target.value)}
                                        onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                                        placeholder="Ask Co-Author..."
                                        className="w-full bg-black border border-gray-700 rounded pl-3 pr-8 py-2 text-xs text-gray-300 focus:border-indigo-500 outline-none"
                                    />
                                    <button onClick={() => handleSendMessage()} disabled={isChatStreaming} className="absolute right-1.5 top-1.5 text-gray-500 hover:text-white disabled:opacity-30">
                                        <Send className="w-3 h-3" />
                                    </button>
                                </div>
                            </div>
                        </div>

                    </div>
                )}

                {/* --- RESEARCH MODE: LIBRARY & CHATS --- */}
                {!isStudio && (
                    <div className="flex-1 flex flex-col min-h-0 pt-2">

                        {/* Back to Discovery (Reading Mode Only) */}
                        {viewState === ViewState.READING && (
                            <div className="px-3 pb-2">
                                <button
                                    onClick={onBackToDiscovery}
                                    className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium bg-indigo-50 text-indigo-700 hover:bg-indigo-100 dark:bg-indigo-900/30 dark:text-indigo-300 dark:hover:bg-indigo-900/50 rounded-lg transition-colors border border-indigo-200 dark:border-indigo-800"
                                >
                                    <ArrowLeft className="w-3.5 h-3.5" />
                                    Back to Search
                                </button>
                            </div>
                        )}

                        {/* Tabs */}
                        <div className="px-3 pb-2 flex gap-1">
                            <button
                                onClick={() => setSidebarTab('library')}
                                className={`flex-1 py-1.5 text-xs font-bold uppercase tracking-wider rounded-md transition-colors ${sidebarTab === 'library' ? 'bg-indigo-50 text-indigo-700' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'}`}
                            >
                                Library
                            </button>
                            <button
                                onClick={() => setSidebarTab('chats')}
                                className={`flex-1 py-1.5 text-xs font-bold uppercase tracking-wider rounded-md transition-colors ${sidebarTab === 'chats' ? 'bg-indigo-50 text-indigo-700' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'}`}
                            >
                                Chats ({sessions.length})
                            </button>
                        </div>

                        {sidebarTab === 'library' ? (
                            <div className="flex-1 overflow-y-auto space-y-4 px-3 pb-4">
                                <div className="space-y-2 shrink-0">
                                    <button
                                        onClick={() => onOpenPdfModal()}
                                        className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-bold uppercase tracking-wide rounded-md transition-all bg-white hover:bg-gray-50 border border-gray-200 text-gray-700 hover:border-gray-300"
                                    >
                                        <Upload className="w-3 h-3" />
                                        Upload PDF
                                    </button>

                                    {/* Context Selector Header */}
                                    <div className="flex items-center justify-between px-1 pt-2 text-gray-500">
                                        <span className="font-bold text-[10px] uppercase tracking-wider">Papers ({totalPapers})</span>
                                        {selectedContextIds.size > 0 && <span className="text-[10px] bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded-full font-bold">{selectedContextIds.size} Active</span>}
                                    </div>

                                    <div className="flex items-center gap-2 mt-2">
                                        <input
                                            value={libraryQuery}
                                            onChange={(e) => setLibraryQuery(e.target.value)}
                                            placeholder="Search title, author, year..."
                                            className="flex-1 px-2.5 py-1.5 text-xs rounded-md border border-gray-200 bg-white focus:outline-none focus:ring-1 focus:ring-indigo-400"
                                        />
                                        {libraryQuery && (
                                            <button
                                                onClick={() => setLibraryQuery('')}
                                                className="px-2 py-1.5 text-[10px] font-bold rounded-md border border-gray-200 bg-white hover:bg-gray-50"
                                            >
                                                Clear
                                            </button>
                                        )}
                                    </div>

                                    {filteredLibraryItems.length > 0 && (
                                        <div className="flex items-center justify-between px-1 text-[10px] text-gray-500">
                                            <span>Showing {filteredLibraryItems.length}</span>
                                            <button
                                                onClick={() => {
                                                    filteredLibraryItems.forEach((paper) => {
                                                        if (!selectedContextIds.has(paper.id)) onToggleContext(paper.id);
                                                    });
                                                }}
                                                className="font-semibold hover:text-indigo-600"
                                            >
                                                Select Visible
                                            </button>
                                        </div>
                                    )}

                                    {isLibraryLoading ? (
                                        <div className="border border-gray-200 rounded-xl p-4 text-center mt-2 text-xs text-gray-500">
                                            Loading library...
                                        </div>
                                    ) : filteredLibraryItems.length === 0 ? (
                                        <div className="border-2 border-dashed border-gray-200 rounded-xl p-6 text-center mt-2">
                                            <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-2"><PlusCircle className="w-4 h-4 text-gray-400" /></div>
                                            <p className="text-xs text-gray-500 font-medium">No papers match this filter.</p>
                                        </div>
                                    ) : (
                                        <div className="space-y-2">
                                            {filteredLibraryItems.map(paper => {
                                                const isSelected = selectedContextIds.has(paper.id);
                                                return (
                                                    <div
                                                        key={paper.id}
                                                        onMouseEnter={(e) => handleMouseEnter(e, paper.id)}
                                                        onMouseLeave={handleMouseLeave}
                                                        className={`group relative flex items-start gap-3 p-3 rounded-xl border transition-all hover:shadow-md cursor-default ${isSelected ? 'bg-indigo-50/50 border-indigo-200' : 'bg-white border-transparent hover:border-gray-200'}`}
                                                    >
                                                        <button
                                                            onClick={(e) => { e.stopPropagation(); onToggleContext(paper.id); }}
                                                            className="mt-1 shrink-0 text-gray-300 hover:text-indigo-600 transition-colors"
                                                            title={isSelected ? "Remove from Context" : "Add to Context"}
                                                        >
                                                            {isSelected ? <CheckSquare className="w-4 h-4 text-indigo-600 fill-indigo-50" /> : <Square className="w-4 h-4" />}
                                                        </button>
                                                        <div className="flex-1 cursor-pointer min-w-0" onClick={() => { console.log('Opening paper:', paper.id, paper.title); onOpenPaper(paper.id); }}>
                                                            <div className={`font-medium text-sm leading-tight truncate ${isSelected ? 'text-indigo-900' : 'text-gray-700'}`}>{paper.title}</div>
                                                            <div className="text-xs text-gray-500 mt-1 truncate">
                                                                {Array.isArray(paper.authors) && paper.authors.length > 0 ? paper.authors[0] : 'Unknown'} • {paper.year || 'N/A'}
                                                            </div>
                                                        </div>
                                                        <button
                                                            onClick={(e) => { e.stopPropagation(); onOpenPaper(paper.id); }}
                                                            className="px-2 py-1 text-[10px] font-semibold rounded-md border border-gray-200 bg-white hover:bg-gray-50"
                                                            title="Open PDF"
                                                        >
                                                            Open
                                                        </button>
                                                        <button className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-gray-600"><MoreVertical className="w-3 h-3" /></button>
                                                        {isSelected && <div className="absolute left-0 top-3 bottom-3 w-1 bg-indigo-500 rounded-r-full" />}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}

                                    {totalPages > 1 && (
                                        <div className="flex items-center justify-between pt-3 text-[10px] text-gray-500">
                                            <button
                                                onClick={() => setLibraryPageIndex(prev => Math.max(1, prev - 1))}
                                                disabled={libraryPageIndex <= 1}
                                                className="px-2 py-1 rounded border border-gray-200 disabled:opacity-50"
                                            >
                                                Prev
                                            </button>
                                            <span className="font-semibold">Page {libraryPageIndex} of {totalPages}</span>
                                            <button
                                                onClick={() => setLibraryPageIndex(prev => Math.min(totalPages, prev + 1))}
                                                disabled={libraryPageIndex >= totalPages}
                                                className="px-2 py-1 rounded border border-gray-200 disabled:opacity-50"
                                            >
                                                Next
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ) : (
                            // CHATS TAB
                            <div className="flex-1 overflow-y-auto space-y-4 px-3 pb-4">
                                <button
                                    onClick={handleNewChat}
                                    className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-bold uppercase tracking-wide rounded-md transition-all bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-500/20"
                                >
                                    <MessageSquarePlus className="w-3.5 h-3.5" />
                                    New Chat
                                </button>

                                <div className="space-y-2">
                                    {sessions.length === 0 ? (
                                        <div className="text-center py-8 text-gray-400 text-xs">No chat sessions yet.</div>
                                    ) : (
                                        sessions.map(session => (
                                            <div
                                                key={session.id}
                                                onClick={() => onSessionSelect && onSessionSelect(session.id)}
                                                className={`group flex items-center gap-3 p-3 rounded-xl border transition-all cursor-pointer ${activeSessionId === session.id ? 'bg-indigo-50 border-indigo-200 shadow-sm' : 'bg-white border-transparent hover:border-gray-200 hover:bg-gray-50'}`}
                                            >
                                                <div className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${activeSessionId === session.id ? 'bg-indigo-100 text-indigo-600' : 'bg-gray-100 text-gray-400'}`}>
                                                    <MessageSquare className="w-4 h-4" />
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className={`font-medium text-sm truncate ${activeSessionId === session.id ? 'text-indigo-900' : 'text-gray-700'}`}>{session.title}</div>
                                                    <div className="text-[10px] text-gray-400 mt-0.5">
                                                        {new Date(session.updated_at).toLocaleDateString()} • {session.message_count || 0} msgs
                                                    </div>
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* Mode Switcher / Bottom Actions */}
                <div className="p-4 border-t border-inherit bg-inherit shrink-0">
                    <button
                        onClick={() => setAppMode(isStudio ? AppMode.RESEARCH : AppMode.STUDIO)}
                        className={`w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${isStudio
                            ? 'bg-[#18181b] text-gray-400 border border-gray-800 hover:bg-gray-800 hover:text-white hover:border-gray-700'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                            }`}
                    >
                        {isStudio ? <><BookOpen className="w-4 h-4" /> Switch to Research</> : <><PenTool className="w-4 h-4" /> Switch to Studio</>}
                    </button>
                </div>

                {/* User Profile */}
                <div className="p-4 pt-2 border-t border-transparent flex items-center gap-3 bg-inherit mb-safe shrink-0">
                    <div className="w-8 h-8 rounded-full bg-indigo-100 border border-indigo-200 flex items-center justify-center text-indigo-700 font-bold text-xs">JD</div>
                    <div className="flex-1 min-w-0">
                        <div className="text-xs font-semibold dark:text-gray-200 truncate">Jane Doe</div>
                        <div className="text-[10px] opacity-60">Pro Plan</div>
                    </div>
                    <Settings className="w-4 h-4 opacity-50 cursor-pointer hover:opacity-100" />
                </div>

            </aside>

            {/* Tooltip */}
            {hoveredPaper && activePaperSummary && (
                <div
                    className="fixed z-[100] w-72 p-4 bg-gray-900/95 backdrop-blur-sm text-white text-xs rounded-xl shadow-2xl pointer-events-none animate-in fade-in zoom-in-95 slide-in-from-left-2 duration-200 border border-white/10 hidden lg:block"
                    style={{ top: hoveredPaper.top, left: hoveredPaper.left }}
                >
                    <div className="font-bold mb-2 text-indigo-300 uppercase tracking-widest text-[10px]">Paper Summary</div>
                    <div className="leading-relaxed opacity-90 font-light">{activePaperSummary}</div>
                    <div className="absolute top-6 -left-1.5 w-3 h-3 bg-gray-900/95 border-l border-b border-white/10 rotate-45 transform" />
                </div>
            )}
        </>
    );
};
