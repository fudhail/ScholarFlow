import React, { useState, useRef, useEffect } from 'react';
// import { MOCK_PAPERS } from '../constants'; (Removed)
import { Highlighter, Share, ZoomIn, ZoomOut, Plus, Check, StickyNote, Copy, Loader2, BookOpen, MessageCircleQuestion, Send, X } from 'lucide-react';
import { Document, Page, pdfjs } from 'react-pdf';
import { useProjectStore } from '../stores/projectStore';
import * as api from '../lib/api-client';
import { Paper } from '../types';
import { useStreamingChat } from '../hooks/useStreaming';
import Markdown from 'react-markdown';

// Initialize Worker
import pdfWorker from 'react-pdf/node_modules/pdfjs-dist/build/pdf.worker.min.mjs?url';
pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker;

import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

interface WorkspaceReadingProps {
  paperId: string | null;
  onAddToProject?: (id: string) => void;
  isSaved?: boolean;
  initialPage?: number;
  highlightText?: string;
  onReadingPositionChange?: (paperId: string, page: number, highlightText?: string) => void;
}

export const WorkspaceReading: React.FC<WorkspaceReadingProps> = ({ 
  paperId, 
  onAddToProject, 
  isSaved = false,
  initialPage = 1,
  highlightText,
  onReadingPositionChange
}) => {
  const { activeProject } = useProjectStore();
  const [paper, setPaper] = useState<Paper | null>(null);

  // PDF Viewer State
  const [zoom, setZoom] = useState(1.0);
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [selectionMenu, setSelectionMenu] = useState<{ x: number, y: number, text: string } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  // Chat Panel State
  const [chatMessages, setChatMessages] = useState<{ role: 'user' | 'agent', text: string }[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [showChatPanel, setShowChatPanel] = useState(true);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Streaming chat hook
  const { streamChat, isStreaming: isChatStreaming } = useStreamingChat();

  useEffect(() => {
    if (!paperId) return;

    const loadPaper = async () => {
      // 1. Fetch Real Paper Metadata
      try {
        console.log('Loading paper:', paperId);
        const realPaper = await api.fetchPaper(paperId);
        console.log('Paper loaded:', realPaper.title, 'PDF URL:', realPaper.pdfUrl);
        setPaper(realPaper);
      } catch (e) {
        console.error("Failed to load paper", e);
        // Fallback UI
        setPaper({
          id: paperId,
          title: 'Error Loading Paper',
          authors: [],
          year: 2024,
          summary: 'Could not fetch metadata.',
          tags: [],
          pdfUrl: ''
        });
      }
    };

    loadPaper();
  }, [paperId]);

  // Jump to page and highlight when initialPage or highlightText changes
  useEffect(() => {
    if (initialPage && initialPage !== 1 && numPages) {
      const pageElement = pageRefs.current.get(initialPage);
      if (pageElement) {
        setTimeout(() => {
          pageElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
          setCurrentPage(initialPage);
          
          // If highlight text provided, try to find and highlight it
          if (highlightText) {
            // Simple highlighting - find text in page
            const textLayer = pageElement.querySelector('.react-pdf__Page__textContent');
            if (textLayer) {
              const walker = document.createTreeWalker(
                textLayer,
                NodeFilter.SHOW_TEXT,
                null
              );
              
              let node;
              while ((node = walker.nextNode())) {
                if (node.textContent && node.textContent.includes(highlightText.slice(0, 50))) {
                  const parent = node.parentElement;
                  if (parent) {
                    parent.style.backgroundColor = 'rgba(255, 255, 0, 0.4)';
                    parent.style.transition = 'background-color 2s ease-out';
                    setTimeout(() => {
                      parent.style.backgroundColor = '';
                    }, 3000);
                  }
                  break;
                }
              }
            }
          }
        }, 500);
      }
    }
  }, [initialPage, highlightText, numPages]);

  useEffect(() => {
    if (!paperId || !currentPage) return;
    onReadingPositionChange?.(paperId, currentPage, highlightText);
  }, [paperId, currentPage, highlightText, onReadingPositionChange]);

  // Handle Zoom
  const handleZoomIn = () => setZoom(prev => Math.min(prev + 0.1, 2.5));
  const handleZoomOut = () => setZoom(prev => Math.max(prev - 0.1, 0.6));

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
  };

  // Handle Selection for custom menu
  useEffect(() => {
    const handleSelectionChange = () => {
      const selection = window.getSelection();

      if (!selection || selection.isCollapsed || !containerRef.current?.contains(selection.anchorNode)) {
        return;
      }

      if (selection.toString().trim().length === 0) {
        setSelectionMenu(null);
        return;
      }

      const range = selection.getRangeAt(0);
      const rect = range.getBoundingClientRect();

      setSelectionMenu({
        x: rect.left + (rect.width / 2),
        y: rect.top - 10,
        text: selection.toString()
      });
    };

    const handleMouseUp = () => {
      setTimeout(handleSelectionChange, 10);
    }

    const handleScroll = () => {
      if (selectionMenu) setSelectionMenu(null);
    }

    document.addEventListener('mouseup', handleMouseUp);
    if (containerRef.current) containerRef.current.addEventListener('scroll', handleScroll);

    return () => {
      document.removeEventListener('mouseup', handleMouseUp);
      if (containerRef.current) containerRef.current.removeEventListener('scroll', handleScroll);
    };
  }, [selectionMenu]);

  const handleCopy = () => {
    if (selectionMenu) {
      navigator.clipboard.writeText(selectionMenu.text);
      setSelectionMenu(null);
      window.getSelection()?.removeAllRanges();
    }
  };

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // Handle asking about selected text
  const handleAskAboutText = () => {
    if (!selectionMenu || !paper) return;

    const excerptPreview = selectionMenu.text.slice(0, 100);
    const context = `(Page ${currentPage}) Selected text: "${excerptPreview}${selectionMenu.text.length > 100 ? '...' : ''}"`;

    // Pre-fill chat input
    setChatInput(`About this: ${context}\n\n`);
    setSelectionMenu(null);
    window.getSelection()?.removeAllRanges();

    // Focus chat input
    setTimeout(() => {
      const chatInputElement = document.querySelector('[data-pdf-chat-input]') as HTMLInputElement;
      if (chatInputElement) chatInputElement.focus();
    }, 100);
  };

  // Send PDF question via chat
  const handleSendPdfQuestion = async () => {
    const message = chatInput.trim();
    if (!message || !activeProject || !paper) return;

    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', text: message }]);

    try {
      await streamChat(
        {
          project_id: activeProject.id,
          message,
          selected_paper_ids: [paper.id],
          current_section: `page_${currentPage}`,
          lab_asset_ids: [],
          research_asset_ids: [],
          session_id: undefined
        },
        undefined,
        (fullText) => {
          setChatMessages(prev => [...prev, { role: 'agent', text: fullText }]);
        }
      );
    } catch (error) {
      console.error('Failed to send chat message:', error);
      setChatMessages(prev => [...prev, { role: 'agent', text: 'Sorry, I encountered an error. Please try again.' }]);
    }
  };

  if (!paper) return <div className="p-10 flex justify-center"><Loader2 className="animate-spin" /></div>;

  return (
    <div className="flex-1 flex flex-col bg-gray-100 h-full relative overflow-hidden">
      {/* Toolbar */}
      <div className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-4 md:px-6 shadow-sm z-20 overflow-x-auto overflow-y-hidden shrink-0">
        <div className="flex items-center gap-3 overflow-hidden mr-4">
          <div className="bg-red-50 p-1.5 rounded text-red-600">
            <BookOpen className="w-4 h-4" />
          </div>
          <div className="font-semibold text-gray-700 truncate max-w-[150px] md:max-w-md" title={paper.title}>{paper.title}</div>
        </div>

        <div className="flex items-center gap-2 shrink-0">

          <button
            onClick={() => onAddToProject && onAddToProject(paper.id)}
            disabled={isSaved}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all mr-2 ${isSaved ? 'bg-green-50 text-green-600' : 'bg-gray-800 text-white hover:bg-gray-700'}`}
          >
            {isSaved ? (
              <>
                <Check className="w-4 h-4" /> <span className="hidden sm:inline">Saved</span>
              </>
            ) : (
              <>
                <Plus className="w-4 h-4" /> <span className="hidden sm:inline">Add Context</span>
              </>
            )}
          </button>

          <div className="h-4 w-px bg-gray-300 mx-2 hidden sm:block"></div>

          {/* Page Info */}
          <div className="text-xs font-mono text-gray-500 hidden sm:block">
            {numPages ? `${numPages} Pages` : 'Loading...'}
          </div>

          <div className="h-4 w-px bg-gray-300 mx-2 hidden sm:block"></div>

          <button onClick={handleZoomOut} className="p-2 text-gray-500 hover:bg-gray-100 rounded hidden sm:block" title="Zoom Out">
            <ZoomOut className="w-4 h-4" />
          </button>
          <span className="text-xs font-mono text-gray-500 hidden sm:block w-12 text-center">{Math.round(zoom * 100)}%</span>
          <button onClick={handleZoomIn} className="p-2 text-gray-500 hover:bg-gray-100 rounded hidden sm:block" title="Zoom In">
            <ZoomIn className="w-4 h-4" />
          </button>

          <div className="h-4 w-px bg-gray-300 mx-2 hidden sm:block"></div>

          <button className="p-2 text-gray-500 hover:bg-gray-100 rounded">
            <Share className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Floating Action Menu (Text Selection) */}
      {selectionMenu && (
        <div
          className="fixed z-50 flex items-center bg-gray-900 text-white rounded-lg shadow-xl py-1 px-2 transform -translate-x-1/2 -translate-y-full animate-in fade-in zoom-in-95 duration-150"
          style={{ top: selectionMenu.y, left: selectionMenu.x }}
        >
          <button className="p-2 hover:bg-gray-700 rounded transition-colors flex flex-col items-center gap-0.5 group" title="Highlight">
            <Highlighter className="w-4 h-4 text-yellow-400" />
          </button>
          <div className="w-px h-4 bg-gray-700 mx-1" />
          <button onClick={handleAskAboutText} className="p-2 hover:bg-gray-700 rounded transition-colors flex flex-col items-center gap-0.5 group" title="Ask about this">
            <MessageCircleQuestion className="w-4 h-4 text-indigo-400" />
          </button>
          <div className="w-px h-4 bg-gray-700 mx-1" />
          <button className="p-2 hover:bg-gray-700 rounded transition-colors flex flex-col items-center gap-0.5 group" title="Add Note">
            <StickyNote className="w-4 h-4 text-blue-400" />
          </button>
          <div className="w-px h-4 bg-gray-700 mx-1" />
          <button onClick={handleCopy} className="p-2 hover:bg-gray-700 rounded transition-colors flex flex-col items-center gap-0.5 group" title="Copy Text">
            <Copy className="w-4 h-4 text-gray-300" />
          </button>
          <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-gray-900 rotate-45" />
        </div>
      )}

      {/* Main Content Area - Two Column Layout */}
      <div className="flex-1 flex flex-row min-h-0">
        {/* PDF View Area - Left Column */}
        <div ref={containerRef} className="flex-1 overflow-y-scroll p-4 md:p-8 flex justify-center bg-gray-200/50 scroll-smooth">
          <Document
            file={paper.pdfUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            className="flex flex-col items-center gap-8 outline-none"
            loading={
              <div className="flex flex-col items-center gap-6">
                <div className="w-[600px] h-[800px] bg-white flex flex-col items-center justify-center text-gray-400 gap-3 rounded-sm shadow-sm">
                  <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
                  <span>Loading Document...</span>
                </div>
              </div>
            }
            error={
              <div className="w-[600px] h-[800px] bg-white flex flex-col items-center justify-center text-red-400 gap-3 p-12 text-center rounded shadow-lg">
                <p className="font-bold">Failed to load PDF</p>
                <p className="text-sm text-gray-500">
                  {!paper.pdfUrl ? (
                    <>
                      No PDF URL available for this paper.
                      <br />
                      The paper may not have been uploaded yet.
                    </>
                  ) : (
                    <>
                      Could not load PDF from:
                      <br />
                      <span className="text-xs break-all mt-2 block font-mono bg-gray-100 p-2 rounded">{paper.pdfUrl}</span>
                      <br />
                      <span className="text-xs mt-2 block">Check if the file exists or try uploading the PDF manually.</span>
                    </>
                  )}
                </p>
              </div>
            }
          >
            {numPages && Array.from(new Array(numPages), (el, index) => (
              <div
                key={`page_${index + 1}`}
                ref={(el) => {
                  if (el) pageRefs.current.set(index + 1, el);
                }}
                className="relative"
                onMouseEnter={() => setCurrentPage(index + 1)}
              >
                <Page
                  pageNumber={index + 1}
                  scale={zoom}
                  renderTextLayer={true}
                  renderAnnotationLayer={true}
                  className="shadow-xl bg-white"
                  loading={
                    <div className="w-[600px] h-[800px] bg-white flex items-center justify-center text-gray-300 shadow-md">
                      <Loader2 className="w-6 h-6 animate-spin" />
                    </div>
                  }
                />
                <div className="text-center text-xs text-gray-400 mt-2 mb-4">Page {index + 1} of {numPages}</div>
              </div>
            ))}
          </Document>
        </div>

        {/* Chat Panel - Right Column */}
        {showChatPanel && (
          <div className="w-80 h-full flex flex-col border-l border-gray-200 bg-white">
            {/* Chat Header */}
            <div className="h-12 flex items-center justify-between px-4 border-b border-gray-200 bg-gray-50 shrink-0">
              <span className="text-sm font-semibold text-gray-700">Ask PDF</span>
              <button
                onClick={() => setShowChatPanel(false)}
                className="p-1 hover:bg-gray-200 rounded transition-colors"
                title="Close chat panel"
              >
                <X className="w-4 h-4 text-gray-500" />
              </button>
            </div>

            {/* Chat Messages Area */}
            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              {chatMessages.length === 0 ? (
                <div className="text-center text-gray-500 text-sm py-6">
                  <p className="font-medium">Select text and click the question icon</p>
                  <p className="text-xs mt-2">or type your question below</p>
                </div>
              ) : (
                chatMessages.map((msg, i) => (
                  <div key={i} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                    <div className={`max-w-[90%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-indigo-100 text-indigo-900'
                        : 'bg-gray-100 text-gray-800'
                    }`}>
                      {msg.role === 'agent' ? <Markdown>{msg.text}</Markdown> : msg.text}
                    </div>
                  </div>
                ))
              )}
              {isChatStreaming && (
                <div className="flex items-center gap-2 text-gray-500 text-xs">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  <span>Analyzing PDF...</span>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Chat Input Area */}
            <div className="h-20 flex flex-col border-t border-gray-200 bg-white shrink-0 p-3 gap-2">
              <textarea
                data-pdf-chat-input
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && e.ctrlKey) {
                    handleSendPdfQuestion();
                  }
                }}
                placeholder="Ask about this PDF..."
                className="flex-1 w-full p-2 border border-gray-300 rounded text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
              <button
                onClick={handleSendPdfQuestion}
                disabled={!chatInput.trim() || isChatStreaming}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-indigo-600 text-white rounded text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <Send className="w-4 h-4" />
                <span className="hidden sm:inline">Send</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
