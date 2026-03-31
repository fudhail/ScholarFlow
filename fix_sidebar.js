const fs = require("fs");
const path = "c:\Users\fudha\Desktop\scholarflow\components\SidebarLeft.tsx";
let content = fs.readFileSync(path, "utf8");

const startMarker = "{/* --- STUDIO MODE: MONITOR + ACTIONS --- */}";
const endMarker = "{/* --- RESEARCH MODE: LIBRARY & CHATS --- */}";

const startIdx = content.indexOf(startMarker);
const endIdx = content.indexOf(endMarker);

if (startIdx === -1 || endIdx === -1) {
    console.error("Markers not found!", { startIdx, endIdx });
    process.exit(1);
}

const newStudioSection = `{/* --- STUDIO MODE: MONITOR + CHAT --- */}
                {isStudio && (
                    <div className="flex-1 flex flex-col min-h-0 overflow-hidden">

                        {/* Compact Monitor */}
                        <div className="shrink-0 bg-[#0a0a0a] flex flex-col items-center pt-3 pb-1 border-b border-gray-800">
                            <div className="transform scale-75 -my-3">
                                <AgentAvatar state={agentState} />
                            </div>
                            <div className="w-full h-20 overflow-y-auto px-4 py-2 font-mono text-[10px] space-y-1 mt-2">
                                {logs.length === 0 ? (
                                    <div className="text-gray-600 italic text-center opacity-50">System Idle.</div>
                                ) : (
                                    logs.map(log => (
                                        <div key={log.id} className="text-green-500/80 leading-tight border-l-2 border-green-500/20 pl-2 py-0.5">
                                            <span className="opacity-50 mr-1">[{log.source}]</span>
                                            <span className={log.source === 'Thought' ? 'text-amber-500 italic' : ''}>{log.message}</span>
                                        </div>
                                    ))
                                )}
                                <div ref={logsEndRef} />
                            </div>
                            <div className="w-full h-6 -mt-6 bg-gradient-to-t from-[#0a0a0a] to-transparent pointer-events-none relative z-10" />
                        </div>

                        {/* Chat Panel */}
                        <div className="flex-1 flex flex-col min-h-0 bg-[#0d0d0f]">
                            {/* Messages */}
                            <div className="flex-1 overflow-y-auto p-3 space-y-3">
                                {chatMessages.map((m, i) => (
                                    <div key={i} className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
                                        {m.role === 'agent' && (
                                            <div className="flex items-center gap-1 mb-1">
                                                <Sparkles className="w-3 h-3 text-indigo-400" />
                                                <span className="text-[9px] font-bold text-indigo-400 uppercase tracking-wider">Co-Author</span>
                                            </div>
                                        )}
                                        <div className={`max-w-[95%] rounded-lg px-3 py-2 text-xs leading-relaxed ${m.role === 'user' ? 'bg-indigo-900/50 text-indigo-100 border border-indigo-500/30' : 'bg-[#18181b] text-gray-300 border border-gray-800'}`}>
                                            {m.role === 'agent' ? <Markdown>{m.text}</Markdown> : m.text}
                                        </div>
                                    </div>
                                ))}
                                {isChatStreaming && (
                                    <div className="flex items-center gap-2 text-gray-500 text-xs italic pl-1">
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
                                        onChange={e => setChatInput(e.target.value)}
                                        onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
                                        placeholder="Ask Co-Author..."
                                        className="w-full bg-black border border-gray-700 rounded pl-3 pr-8 py-2 text-xs text-gray-300 focus:border-indigo-500 outline-none placeholder-gray-600"
                                    />
                                    <button
                                        onClick={() => handleSendMessage()}
                                        disabled={isChatStreaming || !chatInput.trim()}
                                        className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-indigo-400 disabled:opacity-30 transition-colors"
                                    >
                                        <Send className="w-3 h-3" />
                                    </button>
                                </div>
                            </div>
                        </div>

                    </div>
                )}

                `;

const before = content.substring(0, startIdx);
const after = content.substring(endIdx);

const newContent = before + newStudioSection + after;
fs.writeFileSync(path, newContent, "utf8");
console.log("Done! Replaced studio section successfully.");
