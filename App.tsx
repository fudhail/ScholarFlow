
import React, { useEffect, useRef, useCallback, useState } from 'react';
import { Menu, MessageSquare, PanelLeftOpen, PanelRightOpen, X, Upload, Activity, GripVertical } from 'lucide-react';
import { AppMode, ViewState, Project, ProjectType, ProjectAsset, Paper, AgentState, AgentLog, ProjectFile } from './types';
import { SidebarLeft } from './components/SidebarLeft';
import { SidebarRight } from './components/SidebarRight';
import { WorkspaceDiscovery } from './components/WorkspaceDiscovery';
import { WorkspaceReading } from './components/WorkspaceReading';
import { WorkspaceStudio } from './components/WorkspaceStudio';
import { Dashboard } from './components/Dashboard';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ToastContainer } from './components/Toast';
import { VIRTUAL_PROJECT_ID } from './constants';

import { useAppStore } from './stores/appStore';
import { useProjectStore } from './stores/projectStore';
import { useAgentStore } from './stores/agentStore';
import { useProjects, useCreateProject } from './hooks/useProjects';
import { useStreamingChat } from './hooks/useStreaming';
import * as api from './lib/api-client';
import { useQueryClient } from '@tanstack/react-query';

export default function App() {
    // Get React Query client for cache invalidation
    const queryClient = useQueryClient();
    // --- ZUSTAND STORES ---
    const {
        appMode, viewState, isLeftSidebarCollapsed, isRightSidebarCollapsed,
        isLeftDrawerOpen, isRightDrawerOpen, leftSidebarWidth, rightSidebarWidth,
        setAppMode, setViewState, toggleLeftSidebar, toggleRightSidebar,
        setLeftDrawerOpen, setRightDrawerOpen, setLeftSidebarWidth, setRightSidebarWidth
    } = useAppStore();

    const {
        activeProject, activeFileId, paperContent, selectedContextIds, historyStack, redoStack,
        setActiveProject, setActiveFileId, toggleContext, addFile, deleteFile,
        setPaperContent, updateSection, pushHistory, undo, redo
    } = useProjectStore();

    const {
        agentState, agentLogs, pendingMessage, isStreaming,
        setAgentState, addAgentLog, setPendingMessage
    } = useAgentStore();

    // --- REACT QUERY & HOOKS ---
    const { data: projects = [] } = useProjects();
    const createProjectMutation = useCreateProject();
    const { streamChat } = useStreamingChat();

    // --- LOCAL UI STATE (Transient) ---
    const [activePaper, setActivePaper] = useState<string | null>(null);
    const [citationContext, setCitationContext] = useState<{ page?: number; highlight?: string } | null>(null);
    const [isResizing, setIsResizing] = useState(false);
    const sidebarResizingRef = useRef({ left: false, right: false });

    // Discovery Persistence 
    // (Ideally move to a discoveryStore later, keeping local for now)
    const [discoveryTurns, setDiscoveryTurns] = useState<any[]>([]);
    const [discoverySelectedResultIds, setDiscoverySelectedResultIds] = useState<Set<string>>(new Set());
    const [activeSessionId, setActiveSessionId] = useState<string | null>(null); // NEW: Multi-chat session tracker

    // Modals State
    const [isAssetModalOpen, setIsAssetModalOpen] = useState(false);
    const [isPdfModalOpen, setIsPdfModalOpen] = useState(false);

    // Asset Modal Data
    const [importType, setImportType] = useState<'data' | 'image'>('data');
    const [importName, setImportName] = useState('');
    const [importFile, setImportFile] = useState<File | null>(null);
    const [analyzeImmediately, setAnalyzeImmediately] = useState(false);

    // PDF Modal Data
    const [pdfFile, setPdfFile] = useState<File | null>(null);

    // Manage Dark Mode
    useEffect(() => {
        const root = document.documentElement;
        if (appMode === AppMode.STUDIO && viewState !== ViewState.DASHBOARD) {
            root.classList.add('dark');
        } else {
            root.classList.remove('dark');
        }
    }, [appMode, viewState]);

    // Close sidebars on navigation
    useEffect(() => {
        if (window.innerWidth < 1024) {
            setLeftDrawerOpen(false);
            setRightDrawerOpen(false);
        }
    }, [viewState, activePaper, appMode, setLeftDrawerOpen, setRightDrawerOpen]);

    // Handle Resizing Events
    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (!sidebarResizingRef.current.left && !sidebarResizingRef.current.right) return;

            if (sidebarResizingRef.current.left) {
                const newWidth = Math.min(Math.max(e.clientX, 240), 600);
                setLeftSidebarWidth(newWidth);
            }
            if (sidebarResizingRef.current.right) {
                const newWidth = Math.min(Math.max(window.innerWidth - e.clientX, 240), 800);
                setRightSidebarWidth(newWidth);
            }
        };

        const handleMouseUp = () => {
            if (sidebarResizingRef.current.left || sidebarResizingRef.current.right) {
                sidebarResizingRef.current = { left: false, right: false };
                setIsResizing(false);
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            }
        };

        window.addEventListener('mousemove', handleMouseMove);
        window.addEventListener('mouseup', handleMouseUp);
        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };
    }, [setLeftSidebarWidth, setRightSidebarWidth]);

    const startResizingLeft = useCallback(() => {
        sidebarResizingRef.current.left = true;
        setIsResizing(true);
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
    }, []);

    const startResizingRight = useCallback(() => {
        sidebarResizingRef.current.right = true;
        setIsResizing(true);
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
    }, []);

    // Initial System Check Log
    useEffect(() => {
        if (agentLogs.length === 0) {
            const timer = setTimeout(() => {
                addAgentLog('System', 'Research Agent System Initialized.', 'success');
            }, 500);
            return () => clearTimeout(timer);
        }
    }, [agentLogs.length, addAgentLog]);

    const handleCreateProject = async (
        title: string,
        type: ProjectType,
        description: string,
        methodology?: string,
        findings?: string,
        initialAssets: ProjectAsset[] = []
    ) => {
        try {
            const newProject = await createProjectMutation.mutateAsync({
                title,
                description,
                mode: type === ProjectType.LIT_REVIEW ? 'RESEARCH' : 'MANUSCRIPT',
                methodology,
                findings
            });
            // For now client update - future use query invalidation
            handleOpenProject(newProject.id);
        } catch (e) {
            addAgentLog('System', 'Failed to create project', 'error');
        }
    };

    const handleGeneratePlanFromDiscovery = async (selectedPapers: Paper[]) => {
        if (!activeProject) return;

        addAgentLog('System', `Generating Research Plan from ${selectedPapers.length} papers...`);

        try {
            const paperIds = selectedPapers.map(p => p.id);

            // Generate outline for current project
            const outline = await api.generateOutline(activeProject.id, paperIds, [], 'IEEE');

            addAgentLog('System', 'Research Plan generated successfully.', 'success');

            // Refresh project to get updated data
            const updatedProject = await api.fetchProject(activeProject.id);
            setActiveProject(updatedProject);

            // Switch to Studio mode to view the generated plan
            setAppMode(AppMode.STUDIO);
            setViewState(ViewState.STUDIO);

        } catch (error) {
            console.error(error);
            addAgentLog('System', `Failed to generate plan: ${error}`, 'error');
        }
    };

    const handleOpenProject = (projectId: string) => {
        const project = projects.find((p: Project) => p.id === projectId);
        if (!project) return;

        setActiveProject(project);
        setActiveSessionId(null);
        setDiscoveryTurns([]);

        if (project.type === ProjectType.LIT_REVIEW) {
            setAppMode(AppMode.RESEARCH);
            setViewState(ViewState.DISCOVERY);
        } else {
            setAppMode(AppMode.STUDIO);
            setViewState(ViewState.STUDIO);
        }
    };

    // --- FILE SYSTEM ACTIONS & HISTORY ---

    const handleCreateFile = (name: string, parentId?: string) => {
        if (!activeProject) return;
        const newFile: ProjectFile = {
            id: `file-${Date.now()}-${Math.floor(Math.random() * 10000)}`,
            name: name,
            type: 'file',
            content: '',
            parentId: parentId,
            extension: name.split('.').pop()
        };
        addFile(newFile);
        setActiveFileId(newFile.id);
    };

    const handleCreateFolder = (name: string, parentId?: string) => {
        if (!activeProject) return;
        const newFolder: ProjectFile = {
            id: `folder-${Date.now()}-${Math.floor(Math.random() * 10000)}`,
            name: name,
            type: 'folder',
            content: '',
            parentId: parentId
        };
        addFile(newFolder);
    };

    const handleDeleteFile = (fileId: string) => {
        deleteFile(fileId);
    };

    // Paper content lives directly in the store — no files[] indirection.
    const activeFileContent = paperContent;

    const handleUpdateFileContent = (newContent: string, saveHistory: boolean = false) => {
        if (!activeProject) return;
        if (saveHistory) pushHistory(activeFileContent);
        setPaperContent(newContent);
    };

    const handleUndo = () => {
        const prevState = undo();
        if (prevState !== null) {
            setPaperContent(prevState);
            addAgentLog('System', 'Undoing last action.', 'success');
        }
    };

    const handleRedo = () => {
        const nextState = redo();
        if (nextState !== null) {
            setPaperContent(nextState);
            addAgentLog('System', 'Redoing action.', 'success');
        }
    };

    // --- CO-AUTHOR / AGENTIC ACTIONS ---

    const handleUpdateSection = (sectionTitle: string, content: string, mode: 'append' | 'replace' = 'append') => {
        if (!activeProject) return;
        // Write directly into paperContent — no file lookup needed
        updateSection(sectionTitle, content, mode);
    };

    // --- NAVIGATION ACTIONS ---

    const handleBackToDashboard = () => {
        setViewState(ViewState.DASHBOARD);
        setActiveProject(null);
        setAppMode(AppMode.RESEARCH);
        setDiscoveryTurns([]);
        setDiscoverySelectedResultIds(new Set());
    };

    const handleModeSwitch = (mode: AppMode) => {
        setAppMode(mode);
        if (mode === AppMode.STUDIO) {
            setViewState(ViewState.STUDIO);
        } else {
            setViewState(activePaper ? ViewState.READING : ViewState.DISCOVERY);
        }
    };

    const handleOpenPaper = (paperId: string, page?: number, highlightText?: string) => {
        setActivePaper(paperId);
        setCitationContext({ page, highlight: highlightText });
        setViewState(ViewState.READING);
    };

    const handleBackToDiscovery = () => {
        setViewState(ViewState.DISCOVERY);
        setCitationContext(null);
    };

    const handleAddToProject = async (paperId: string) => {
        if (!activeProject) return;

        // Check if paper already in project
        if (activeProject.papers.some(p => p.id === paperId)) return;

        try {
            // Fetch paper details and add to library
            const paper = await api.fetchPaper(paperId);
            await api.addPaperToLibrary(activeProject.id, paper);

            // Refresh project to get updated papers
            const updatedProject = await api.fetchProject(activeProject.id);
            setActiveProject(updatedProject);

            // Auto-select for context
            if (!selectedContextIds.has(paperId)) {
                toggleContext(paperId);
            }

            addAgentLog('System', `Added paper to library: ${paper.title}`, 'success');
        } catch (error) {
            console.error('Error adding paper:', error);
            addAgentLog('System', 'Failed to add paper to library', 'error');
        }
    };

    const handleImportAsset = (asset: ProjectAsset) => {
        if (!activeProject) return;
        const updatedProject = { ...activeProject, assets: [...activeProject.assets, asset] };
        setActiveProject(updatedProject);
        addAgentLog('System', `Imported new asset: ${asset.name}`);
    };

    const handleTriggerAgent = async (message: string) => {
        if (!activeProject) return;
        setPendingMessage(message);

        if (appMode === AppMode.STUDIO) {
            if (isRightSidebarCollapsed) toggleRightSidebar();
        }

        // Collect selected lab assets (if any are marked/selected)
        const selectedAssetIds = activeProject.assets
            ?.filter(asset => asset.id) // Filter valid assets
            .map(asset => asset.id) || [];

        await streamChat({
            project_id: activeProject.id,
            message,
            selected_paper_ids: Array.from(selectedContextIds),
            lab_asset_ids: selectedAssetIds // Collect all project assets for now
        },
            (chunk) => {
                // Optional: handle streaming text chunking for specific UI if needed
            },
            (fullText) => {
                setPendingMessage(null);
                // Refresh project to get new papers/context
                if (activeProject) {
                    api.fetchProject(activeProject.id).then(updated => setActiveProject(updated));
                }
            });
    };

    const handleAnalyzeAsset = (asset: ProjectAsset) => {
        handleTriggerAgent(`Analyze the dataset "${asset.name}". Identify key trends, outliers, and suggest how to incorporate this into the methodology section.`);
    };


    // --- MODAL SUBMISSIONS ---

    const handleAssetImportSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!importName) return;

        const newAsset: ProjectAsset = {
            id: `asset-${Date.now()}`,
            name: importName,
            type: importType,
            url: importFile ? URL.createObjectURL(importFile) : undefined
        };

        // In a real app we would use mutation here:
        // uploadAsset.mutate({ ... })

        handleImportAsset(newAsset);

        if (analyzeImmediately) {
            handleAnalyzeAsset(newAsset);
        }

        setIsAssetModalOpen(false);
        setImportName('');
        setImportFile(null);
        setAnalyzeImmediately(false);
    };

    const handlePdfImportSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!pdfFile) return;

        addAgentLog('System', `Uploading PDF: ${pdfFile.name}...`);

        try {
            await api.uploadPaper(
                activeProject ? activeProject.id : VIRTUAL_PROJECT_ID,
                pdfFile
            );
            addAgentLog('System', `Successfully added ${pdfFile.name} to Library.`, 'success');

            // Refresh projects to see new paper
            if (activeProject) {
                const updated = await api.fetchProject(activeProject.id);
                setActiveProject(updated);
            }
        } catch (error) {
            console.error(error);
            addAgentLog('System', `Failed to upload PDF: ${error}`, 'error');
        }

        setIsPdfModalOpen(false);
        setPdfFile(null);
    };

    if (viewState === ViewState.DASHBOARD) {
        return (
            <ErrorBoundary>
                <Dashboard
                    projects={projects}
                    onCreateProject={handleCreateProject}
                    onOpenProject={(id) => handleOpenProject(id)}
                />
            </ErrorBoundary>
        );
    }

    // --- DYNAMIC COMPONENT PROPS ---

    const sidebarLeftProps = {
        appMode,
        viewState,
        setAppMode: handleModeSwitch,
        onBackToDiscovery: handleBackToDiscovery,
        onBackToDashboard: handleBackToDashboard,
        activeProject: activeProject,
        onOpenPaper: handleOpenPaper,
        selectedContextIds: selectedContextIds,
        onToggleContext: toggleContext,
        // Mobile close logic depends on which side it is mounted, handled below
        onCloseMobile: () => { },
        onOpenPdfModal: () => setIsPdfModalOpen(true),
        onAnalyzeAsset: handleAnalyzeAsset,
        // Collapse logic handled in render
        onCollapse: () => { },
        isCollapsed: false,
        files: activeProject?.files || [],
        activeFileId: activeFileId,
        onFileSelect: setActiveFileId,
        onCreateFile: handleCreateFile,
        onCreateFolder: handleCreateFolder,
        onDeleteFile: handleDeleteFile,
        activeFileContent: activeFileContent, // calculated below
        onUpdateActiveFileContent: handleUpdateFileContent,
        onUpdateSection: handleUpdateSection,
        onTriggerAgent: handleTriggerAgent,
        agentState: agentState,
        setAgentState: setAgentState,
        addAgentLog: addAgentLog,
        logs: agentLogs, // Passing logs for monitor display
        pendingMessage: pendingMessage,
        onClearPendingMessage: () => setPendingMessage(null),
        activeSessionId: activeSessionId,
        onSessionSelect: (id: string | null) => {
            setActiveSessionId(id);
            setDiscoveryTurns([]);
        }
    };

    const sidebarRightProps = {
        appMode,
        viewState, // Added Prop
        activePaper, // Added Prop
        agentState,
        setAgentState,
        addAgentLog,
        logs: agentLogs,
        onCloseMobile: () => { },
        onCollapse: () => { },
        // New Props for Co-Author in Studio Mode
        activeProject,
        activeFileContent, // calculated below
        onUpdateSection: handleUpdateSection,
        onAnalyzeAsset: handleAnalyzeAsset,
        onOpenAssetModal: () => setIsAssetModalOpen(true),
        pendingMessage: pendingMessage,
        onClearPendingMessage: () => setPendingMessage(null),
        selectedContextIds // Pass selected paper IDs for context
    };

    // Helper for conditional classes vs styles
    const transitionClass = isResizing ? '' : 'transition-all duration-300 ease-in-out';
    const isStudio = appMode === AppMode.STUDIO;

    return (
        <div className={`flex h-screen w-full overflow-hidden transition-colors duration-500 ${isStudio ? 'bg-[#050505]' : 'bg-gray-50'}`}>

            {/* Mobile Header */}
            <div className="lg:hidden fixed top-0 left-0 right-0 h-14 bg-white dark:bg-academic-950 border-b border-gray-200 dark:border-gray-800 z-40 flex items-center justify-between px-4 shadow-sm">
                <button onClick={() => setLeftDrawerOpen(true)} className="p-2 -ml-2 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">
                    {isStudio ? <Activity className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                </button>
                <span className="font-semibold text-sm text-gray-900 dark:text-gray-200 tracking-tight">ScholarFlow</span>
                <button onClick={() => setRightDrawerOpen(true)} className="p-2 -mr-2 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 rounded-lg">
                    {isStudio ? <MessageSquare className="w-5 h-5" /> : <Activity className="w-5 h-5" />}
                </button>
            </div>

            {/* --- LEFT CONTAINER --- */}
            <div
                className={`
            fixed inset-y-0 left-0 z-50 bg-white dark:bg-academic-950 shadow-2xl transform lg:relative lg:translate-x-0 lg:shadow-none
            ${transitionClass}
            ${isLeftDrawerOpen ? 'translate-x-0' : '-translate-x-full'}
          `}
                style={{ width: isLeftSidebarCollapsed ? 0 : (window.innerWidth >= 1024 ? leftSidebarWidth : '18rem') }}
            >
                {!isLeftSidebarCollapsed && (
                    <div
                        className="hidden lg:block absolute top-0 right-0 bottom-0 w-1 cursor-col-resize hover:bg-indigo-500 z-50 transition-colors group"
                        onMouseDown={startResizingLeft}
                    >
                        <div className="absolute top-1/2 -translate-y-1/2 -right-2 opacity-0 group-hover:opacity-100 bg-indigo-500 text-white rounded-full p-0.5 shadow-md pointer-events-none">
                            <GripVertical className="w-3 h-3" />
                        </div>
                    </div>
                )}

                <div className="h-full w-full overflow-hidden">
                    {/* Always render SidebarLeft, it will adapt based on appMode */}
                    <SidebarLeft
                        {...sidebarLeftProps}
                        position="left"
                        onCloseMobile={() => setLeftDrawerOpen(false)}
                        onCollapse={() => toggleLeftSidebar()}
                        isCollapsed={isLeftSidebarCollapsed}
                    />
                </div>
            </div>

            {isLeftDrawerOpen && (
                <div className="fixed inset-0 bg-black/50 z-40 lg:hidden backdrop-blur-sm transition-opacity" onClick={() => setLeftDrawerOpen(false)} />
            )}

            {/* --- CENTER STAGE --- */}
            <main className="flex-1 flex flex-col relative h-full overflow-hidden pt-14 lg:pt-0">

                {/* Desktop Sidebar Toggles */}
                <div className="hidden lg:flex absolute top-3 left-3 z-50 gap-2 print:hidden">
                    {isLeftSidebarCollapsed && (
                        <button
                            onClick={() => toggleLeftSidebar()}
                            className={`p-1.5 rounded-md shadow-md border transition-all ${isStudio ? 'bg-gray-800 border-gray-700 text-gray-300 hover:text-white' : 'bg-white border-gray-200 text-gray-500 hover:text-gray-900'}`}
                            title="Expand Left"
                        >
                            <PanelLeftOpen className="w-4 h-4" />
                        </button>
                    )}
                </div>

                {/* Toggle for Right Sidebar */}
                <div className="hidden lg:flex absolute top-3 right-3 z-50 gap-2 print:hidden">
                    {isRightSidebarCollapsed && (
                        <button
                            onClick={() => toggleRightSidebar()}
                            className={`p-1.5 rounded-md shadow-md border transition-all ${isStudio ? 'bg-gray-800 border-gray-700 text-gray-300 hover:text-white' : 'bg-white border-gray-200 text-gray-500 hover:text-gray-900'}`}
                            title="Expand Right"
                        >
                            <PanelRightOpen className="w-4 h-4" />
                        </button>
                    )}
                </div>

                {
                    viewState === ViewState.DISCOVERY && (
                        <WorkspaceDiscovery
                            onOpenPaper={handleOpenPaper}
                            onGeneratePlan={handleGeneratePlanFromDiscovery}
                            onAddToProject={handleAddToProject}
                            activeProjectId={activeProject?.id || ''}
                            activeProjectPapers={activeProject?.papers.map(p => p.id) || []}
                            selectedContextIds={selectedContextIds}
                            setAgentState={setAgentState}
                            agentState={agentState}       // Passed Prop
                            logs={agentLogs}              // Passed Prop
                            addAgentLog={addAgentLog}
                            turns={discoveryTurns}
                            setTurns={setDiscoveryTurns}
                            selectedResultIds={discoverySelectedResultIds}
                            setSelectedResultIds={setDiscoverySelectedResultIds}
                            activeSessionId={activeSessionId}
                            onSessionChange={(id) => {
                                setActiveSessionId(id);
                                setDiscoveryTurns([]);
                            }}
                        />
                    )
                }
                {
                    viewState === ViewState.READING && (
                        <WorkspaceReading
                            paperId={activePaper}
                            onAddToProject={handleAddToProject}
                            isSaved={activeProject?.papers.some(p => p.id === activePaper) || false}
                            initialPage={citationContext?.page}
                            highlightText={citationContext?.highlight}
                        />
                    )
                }
                {
                    viewState === ViewState.STUDIO && (
                        <WorkspaceStudio
                            activeProject={activeProject}
                            content={activeFileContent}
                            onChange={(c) => handleUpdateFileContent(c, false)}
                            activeFileName={activeProject?.title || 'Untitled'}
                            onUndo={handleUndo}
                            onRedo={handleRedo}
                            canUndo={historyStack.length > 0}
                            canRedo={redoStack.length > 0}
                            onOpenPaper={handleOpenPaper}
                            isStreaming={isStreaming}
                        />
                    )
                }
            </main >

            {/* --- RIGHT CONTAINER --- */}
            {/* In Studio Mode, we DO show the right sidebar now (Co-Author) */}
            <div
                className={`
            fixed inset-y-0 right-0 z-50 bg-white dark:bg-academic-950 shadow-2xl transform lg:relative lg:translate-x-0 lg:shadow-none
            ${transitionClass}
            ${isRightDrawerOpen ? 'translate-x-0' : 'translate-x-full'}
        `}
                style={{ width: isRightSidebarCollapsed ? 0 : (window.innerWidth >= 1024 ? rightSidebarWidth : '18rem') }}
            >
                {!isRightSidebarCollapsed && (
                    <div
                        className="hidden lg:block absolute top-0 left-0 bottom-0 w-1 cursor-col-resize hover:bg-indigo-500 z-50 transition-colors group"
                        onMouseDown={startResizingRight}
                    >
                        <div className="absolute top-1/2 -translate-y-1/2 -left-2 opacity-0 group-hover:opacity-100 bg-indigo-500 text-white rounded-full p-0.5 shadow-md pointer-events-none">
                            <GripVertical className="w-3 h-3" />
                        </div>
                    </div>
                )}

                <div className="h-full w-full overflow-hidden">
                    <SidebarRight
                        {...sidebarRightProps}
                        position="right"
                        onCloseMobile={() => setRightDrawerOpen(false)}
                        onCollapse={() => toggleRightSidebar()}
                    />
                </div>
            </div>

            {
                isRightDrawerOpen && (
                    <div className="fixed inset-0 bg-black/50 z-40 lg:hidden backdrop-blur-sm transition-opacity" onClick={() => setRightDrawerOpen(false)} />
                )
            }

            {/* ... MODALS ... */}
            {/* (Modals code remains unchanged) */}

            <ToastContainer />

            {
                isAssetModalOpen && (
                    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
                        <div className="bg-white dark:bg-academic-900 dark:text-gray-100 rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-800 flex justify-between items-center">
                                <h3 className="font-bold text-lg">Import Project Asset</h3>
                                <button onClick={() => setIsAssetModalOpen(false)}><X className="w-5 h-5 opacity-50 hover:opacity-100" /></button>
                            </div>
                            <form onSubmit={handleAssetImportSubmit} className="p-6 space-y-4">
                                {/* ... (Import form content stays same) ... */}
                                <div>
                                    <label className="block text-xs font-bold uppercase tracking-wider mb-2 opacity-70">Asset Name</label>
                                    <input
                                        autoFocus
                                        type="text"
                                        className="w-full bg-gray-50 dark:bg-black/30 border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500"
                                        placeholder="e.g. Experiment A Results"
                                        value={importName}
                                        onChange={e => setImportName(e.target.value)}
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-bold uppercase tracking-wider mb-2 opacity-70">Type</label>
                                    <div className="flex gap-2">
                                        <button
                                            type="button"
                                            onClick={() => setImportType('data')}
                                            className={`flex-1 py-2 rounded-lg border text-sm font-medium transition-colors ${importType === 'data' ? 'bg-indigo-50 dark:bg-indigo-900/30 border-indigo-500 text-indigo-600 dark:text-indigo-400' : 'border-gray-200 dark:border-gray-700'}`}
                                        >
                                            Dataset (CSV/JSON)
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => setImportType('image')}
                                            className={`flex-1 py-2 rounded-lg border text-sm font-medium transition-colors ${importType === 'image' ? 'bg-indigo-50 dark:bg-indigo-900/30 border-indigo-500 text-indigo-600 dark:text-indigo-400' : 'border-gray-200 dark:border-gray-700'}`}
                                        >
                                            Image / Figure
                                        </button>
                                    </div>
                                </div>
                                <div>
                                    <label className="block text-xs font-bold uppercase tracking-wider mb-2 opacity-70">File</label>
                                    <div className="border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-lg p-8 flex flex-col items-center justify-center text-gray-400 hover:border-indigo-500 hover:text-indigo-500 transition-colors cursor-pointer relative">
                                        <input type="file" className="absolute inset-0 opacity-0 cursor-pointer" onChange={e => setImportFile(e.target.files?.[0] || null)} />
                                        <Upload className="w-6 h-6 mb-2" />
                                        <span className="text-xs">{importFile ? importFile.name : 'Click to Upload'}</span>
                                    </div>
                                </div>

                                <button
                                    type="submit"
                                    className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-bold shadow-lg shadow-indigo-500/20"
                                >
                                    Import Asset
                                </button>
                            </form>
                        </div>
                    </div>
                )
            }

            {/* PDF IMPORT MODAL */}
            {
                isPdfModalOpen && (
                    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
                        <div className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                            <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
                                <h3 className="font-bold text-lg text-gray-900">Upload PDF</h3>
                                <button onClick={() => setIsPdfModalOpen(false)}><X className="w-5 h-5 text-gray-500 hover:text-gray-900" /></button>
                            </div>
                            <form onSubmit={handlePdfImportSubmit} className="p-6 space-y-4">
                                <div>
                                    <label className="block text-xs font-bold uppercase tracking-wider mb-2 text-gray-500">Select PDF</label>
                                    <div className="border-2 border-dashed border-gray-200 rounded-lg p-10 flex flex-col items-center justify-center text-gray-400 hover:border-indigo-500 hover:text-indigo-500 transition-colors cursor-pointer relative">
                                        <input
                                            type="file"
                                            accept=".pdf"
                                            className="absolute inset-0 opacity-0 cursor-pointer"
                                            onChange={e => setPdfFile(e.target.files?.[0] || null)}
                                        />
                                        <Upload className="w-8 h-8 mb-2" />
                                        <span className="text-sm font-medium">{pdfFile ? pdfFile.name : 'Drop PDF here or click'}</span>
                                    </div>
                                </div>

                                <button
                                    type="submit"
                                    disabled={!pdfFile}
                                    className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-bold shadow-lg shadow-indigo-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    Add to Library
                                </button>
                            </form>
                        </div>
                    </div>
                )
            }

        </div >
    );
}
