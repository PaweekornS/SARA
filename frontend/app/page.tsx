"use client";

import React, { useState, useEffect, useRef } from "react";
import { 
  Upload, 
  MessageSquare, 
  Send, 
  CheckCircle2, 
  AlertCircle, 
  Loader2, 
  ChevronRight, 
  FileText, 
  Plus, 
  Trash2, 
  User, 
  Calendar, 
  Mail, 
  CheckSquare, 
  Sparkles,
  FileAudio,
  ArrowRight,
  Info,
  PanelLeftClose,
  PanelLeftOpen
} from "lucide-react";

// Types matching Backend Data Models
interface ActionItem {
  task: string;
  assignee: string;
  email: string;
  due_date?: string;
}

interface SummaryData {
  executive_summary: string[];
  key_decisions: string[];
  action_items: ActionItem[];
}

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  isSummary?: boolean;
  summaryData?: SummaryData;
}

interface Session {
  id: string;
  fileName: string;
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
  summary: SummaryData | null;
  chatHistory: Message[];
  createdAt: string;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function Home() {

  
  // Sidebar visibility state
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(true);
  
  // Sessions state
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  
  // Chat typing state
  const [inputMessage, setInputMessage] = useState("");
  const [isSending, setIsSending] = useState(false);
  
  // Upload component state
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  // Auto-scroll ref
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  // Load state from localStorage on mount
  useEffect(() => {

    
    // 2. Sidebar state initialization
    const savedSidebar = localStorage.getItem("sara_sidebar_open");
    if (savedSidebar !== null) {
      setSidebarOpen(savedSidebar === "true");
    }

    // 3. Sessions initialization
    const savedSessions = localStorage.getItem("sara_sessions");
    const savedActiveId = localStorage.getItem("sara_active_session_id");

    if (savedSessions) {
      try {
        const parsed = JSON.parse(savedSessions);
        setSessions(parsed);
      } catch (e) {
        console.error("Failed to parse saved sessions", e);
      }
    }

    if (savedActiveId) {
      setActiveSessionId(savedActiveId);
    }
  }, []);



  // Save sessions to localStorage when updated
  useEffect(() => {
    if (sessions.length > 0) {
      localStorage.setItem("sara_sessions", JSON.stringify(sessions));
    } else {
      localStorage.removeItem("sara_sessions");
    }
  }, [sessions]);

  // Save activeSessionId to localStorage when updated
  useEffect(() => {
    if (activeSessionId) {
      localStorage.setItem("sara_active_session_id", activeSessionId);
    } else {
      localStorage.removeItem("sara_active_session_id");
    }
  }, [activeSessionId]);

  // Save sidebar state to localStorage
  const handleToggleSidebar = () => {
    const nextState = !sidebarOpen;
    setSidebarOpen(nextState);
    localStorage.setItem("sara_sidebar_open", String(nextState));
  };

  // Scroll to bottom of chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeSessionId, sessions]);

  // Poll status of all non-terminal sessions (PENDING / PROCESSING)
  useEffect(() => {
    const activePollingNeeded = sessions.some(s => s.status === "PENDING" || s.status === "PROCESSING");

    if (activePollingNeeded) {
      const interval = setInterval(async () => {
        let hasChanges = false;
        
        const updated = await Promise.all(
          sessions.map(async (session) => {
            if (session.status === "PENDING" || session.status === "PROCESSING") {
              try {
                const response = await fetch(`${BACKEND_URL}/meetings/${session.id}/status`);
                if (response.ok) {
                  const data = await response.json();
                  
                  if (data.status !== session.status) {
                    hasChanges = true;
                    
                    if (data.status === "COMPLETED" && data.summary) {
                      // Formulate meeting summary message to insert directly in the chat history
                      const summaryMessage: Message = {
                        role: "assistant",
                        content: "Summary generated",
                        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                        isSummary: true,
                        summaryData: data.summary
                      };

                      // Greeting message from SARA
                      const welcomeMessage: Message = {
                        role: "assistant",
                        content: `Hello! I have finished analyzing **${session.fileName}**. You can now ask me any specific questions about this meeting below.`,
                        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                      };

                      return {
                        ...session,
                        status: "COMPLETED" as const,
                        summary: data.summary,
                        chatHistory: [summaryMessage, welcomeMessage, ...session.chatHistory]
                      };
                    } else if (data.status === "FAILED") {
                      return {
                        ...session,
                        status: "FAILED" as const
                      };
                    } else {
                      return {
                        ...session,
                        status: data.status
                      };
                    }
                  }
                }
              } catch (err) {
                console.error(`Failed to poll status for meeting ${session.id}`, err);
              }
            }
            return session;
          })
        );

        if (hasChanges) {
          setSessions(updated);
        }
      }, 3000);

      return () => clearInterval(interval);
    }
  }, [sessions]);

  // Derived state for currently active session
  const activeSession = sessions.find(s => s.id === activeSessionId) || null;



  // Drag and Drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFile = e.dataTransfer.files[0];
      setFile(droppedFile);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  // File Upload trigger
  const handleStartAnalysis = async () => {
    if (!file) return;

    setIsUploading(true);
    setUploadStatus("Uploading meeting file...");
    
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${BACKEND_URL}/meetings/process`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Upload failed");
      }

      const data = await response.json();
      const newMeetingId = data.meeting_id;
      
      const newSession: Session = {
        id: newMeetingId,
        fileName: file.name,
        status: "PENDING",
        summary: null,
        chatHistory: [],
        createdAt: new Date().toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })
      };

      setSessions(prev => [newSession, ...prev]);
      setActiveSessionId(newMeetingId);
      setFile(null);
      setUploadStatus(null);
    } catch (error) {
      console.error("Upload error:", error);
      setUploadStatus("Failed to upload file. Please check if the backend is online and try again.");
    } finally {
      setIsUploading(false);
    }
  };

  // Send a chat message
  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputMessage.trim() || !activeSession || isSending) return;

    const userMessageContent = inputMessage.trim();
    setInputMessage("");
    setIsSending(true);

    const userMessage: Message = {
      role: "user",
      content: userMessageContent,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    // Update session chat history locally
    const updatedSessions = sessions.map(session => {
      if (session.id === activeSession.id) {
        return {
          ...session,
          chatHistory: [...session.chatHistory, userMessage]
        };
      }
      return session;
    });
    setSessions(updatedSessions);

    try {
      // Build payload containing the historical conversation messages (excluding rich summaries)
      const historyPayload = activeSession.chatHistory
        .filter(msg => !msg.isSummary)
        .map(msg => ({
          role: msg.role,
          content: msg.content
        }));

      const response = await fetch(`${BACKEND_URL}/meetings/${activeSession.id}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: userMessageContent,
          history: historyPayload
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to get answer");
      }

      const data = await response.json();

      const aiMessage: Message = {
        role: "assistant",
        content: data.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      // Append AI response
      setSessions(prevSessions => prevSessions.map(session => {
        if (session.id === activeSession.id) {
          return {
            ...session,
            chatHistory: [...session.chatHistory, aiMessage]
          };
        }
        return session;
      }));

    } catch (error) {
      console.error("Chat error:", error);
      const errorMessage: Message = {
        role: "assistant",
        content: "I encountered a connection error. Please ensure the backend server is running and try again.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setSessions(prevSessions => prevSessions.map(session => {
        if (session.id === activeSession.id) {
          return {
            ...session,
            chatHistory: [...session.chatHistory, errorMessage]
          };
        }
        return session;
      }));
    } finally {
      setIsSending(false);
    }
  };

  // Delete a session
  const handleDeleteSession = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const confirmed = confirm("Are you sure you want to delete this session?");
    if (!confirmed) return;

    setSessions(prev => prev.filter(s => s.id !== id));
    if (activeSessionId === id) {
      setActiveSessionId(null);
    }
  };

  // Check if file is audio
  const isAudioFile = (name: string) => {
    const ext = name.split('.').pop()?.toLowerCase();
    return ['mp3', 'wav', 'm4a', 'aac', 'ogg', 'flac'].includes(ext || '');
  };

  // Custom text formatting helper (regex-based Markdown parsing)
  const formatText = (text: string) => {
    if (!text) return "";
    
    return text.split("\n").map((line, idx) => {
      let formattedLine = line;
      
      // Match markdown bold: **text** -> <strong>text</strong>
      const boldRegex = /\*\*(.*?)\*\*/g;
      formattedLine = formattedLine.replace(boldRegex, "<strong>$1</strong>");

      // Match inline code: `code` -> <code>code</code>
      const codeRegex = /`(.*?)`/g;
      formattedLine = formattedLine.replace(codeRegex, '<code class="bg-zinc-100 dark:bg-zinc-800 text-indigo-600 dark:text-indigo-400 px-1 py-0.5 rounded text-xs font-mono">$1</code>');

      // Check if line is a bullet point
      if (line.trim().startsWith("- ") || line.trim().startsWith("* ")) {
        const content = formattedLine.trim().substring(2);
        return (
          <li key={idx} className="ml-4 list-disc text-zinc-700 dark:text-zinc-300 mb-1" dangerouslySetInnerHTML={{ __html: content }} />
        );
      }

      // Check if line is a numbered bullet
      const numMatch = line.trim().match(/^(\d+)\.\s(.*)/);
      if (numMatch) {
        const content = formattedLine.trim().substring(numMatch[1].length + 2);
        return (
          <li key={idx} className="ml-4 list-decimal text-zinc-700 dark:text-zinc-300 mb-1" dangerouslySetInnerHTML={{ __html: content }} />
        );
      }

      return (
        <p key={idx} className="mb-2 text-zinc-700 dark:text-zinc-300 leading-relaxed" dangerouslySetInnerHTML={{ __html: formattedLine }} />
      );
    });
  };

  // Render a special rich intelligence summary card in the chat viewport
  const renderSummaryCard = (summaryData: SummaryData) => {
    return (
      <div className="w-full bg-zinc-50 dark:bg-[#1E293B] border border-zinc-200 dark:border-[#334155] rounded-2xl p-6 space-y-6 shadow-sm overflow-hidden text-left">
        
        {/* Card Header */}
        <div className="flex items-center gap-2 pb-4 border-b border-zinc-200 dark:border-[#334155]">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center text-white shadow-md shadow-indigo-500/10">
            <Sparkles size={20} />
          </div>
          <div>
            <h3 className="font-semibold text-xs md:text-sm text-zinc-800 dark:text-zinc-100">SARA Intelligent Summary Report</h3>
            <p className="text-[10px] text-zinc-500 font-medium">Automatic synthesis from meeting transcription</p>
          </div>
        </div>

        {/* Executive Summary */}
        {summaryData.executive_summary && summaryData.executive_summary.length > 0 && (
          <div className="space-y-2.5">
            <h4 className="text-[11px] font-bold text-indigo-600 dark:text-indigo-400 tracking-wider uppercase flex items-center gap-2">
              <span className="w-1.5 h-3.5 rounded bg-indigo-500"></span>
              Executive Summary
            </h4>
            <ul className="space-y-2 pl-1">
              {summaryData.executive_summary.map((item, idx) => (
                <li key={idx} className="flex gap-2 items-start leading-relaxed text-xs text-zinc-600 dark:text-zinc-300">
                  <ChevronRight size={14} className="text-indigo-500 shrink-0 mt-0.5" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Key Decisions */}
        {summaryData.key_decisions && summaryData.key_decisions.length > 0 && (
          <div className="space-y-2.5 pt-4 border-t border-zinc-200 dark:border-[#334155]/60">
            <h4 className="text-[11px] font-bold text-emerald-600 dark:text-emerald-400 tracking-wider uppercase flex items-center gap-2">
              <span className="w-1.5 h-3.5 rounded bg-emerald-500"></span>
              Key Decisions
            </h4>
            <ul className="space-y-2 pl-1">
              {summaryData.key_decisions.map((item, idx) => (
                <li key={idx} className="flex gap-2.5 items-start leading-relaxed text-xs text-zinc-600 dark:text-zinc-300">
                  <span className="font-mono text-emerald-600 dark:text-emerald-400 font-bold text-[9px] shrink-0 mt-0.5 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/10">
                    DEC-{idx + 1}
                  </span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Action Items */}
        {summaryData.action_items && summaryData.action_items.length > 0 && (
          <div className="space-y-3 pt-4 border-t border-zinc-200 dark:border-[#334155]/60">
            <h4 className="text-[11px] font-bold text-amber-600 dark:text-amber-500 tracking-wider uppercase flex items-center gap-2">
              <span className="w-1.5 h-3.5 rounded bg-amber-500"></span>
              Action Items & Assignments
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {summaryData.action_items.map((item, idx) => (
                <div key={idx} className="p-3 bg-white dark:bg-[#1E293B] rounded-xl border border-zinc-200/80 dark:border-[#334155] hover:border-indigo-500/20 dark:hover:border-indigo-400/20 transition-all flex flex-col gap-2 shadow-sm">
                  <div className="flex gap-2 items-start">
                    <span className="w-4 h-4 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">
                      {idx + 1}
                    </span>
                    <p className="text-xs text-zinc-700 dark:text-zinc-200 leading-normal font-medium flex-1">{item.task}</p>
                  </div>
                  
                  <div className="flex flex-wrap gap-1.5 items-center mt-auto pt-1 border-t border-zinc-100 dark:border-zinc-900">
                    <span className="text-[9px] bg-indigo-500/10 text-indigo-600 dark:text-indigo-300 px-1.5 py-0.5 rounded flex items-center gap-1 max-w-[120px] truncate">
                      <User size={8} />
                      {item.assignee}
                    </span>
                    {item.due_date && (
                      <span className="text-[9px] bg-zinc-100 dark:bg-zinc-900 text-zinc-500 dark:text-zinc-400 px-1.5 py-0.5 rounded flex items-center gap-1">
                        <Calendar size={8} />
                        {item.due_date}
                      </span>
                    )}
                    {item.email && (
                      <span className="text-[8px] text-zinc-400 dark:text-zinc-500 flex items-center gap-1 overflow-hidden text-ellipsis w-full mt-0.5">
                        <Mail size={8} className="shrink-0" />
                        {item.email}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    );
  };

  return (
    <div className="h-screen w-screen overflow-hidden relative bg-background text-foreground">

      <div className="flex h-full w-full overflow-hidden font-sans">
        
        {/* 1. SIDEBAR: DISPLAYS SESSION FILENAMES */}
        <aside 
          className={`transition-all duration-300 ease-in-out flex flex-col h-full overflow-hidden glass shrink-0 bg-zinc-100/40 dark:bg-[#1E293B]/10 border-zinc-200 dark:border-[#1E293B] ${
            sidebarOpen ? "w-64 border-r" : "w-0 border-r-0"
          }`}
        >
          
          {/* Sidebar Header */}
          <div className="p-4 border-b border-zinc-200 dark:border-[#1E293B] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center font-bold text-sm tracking-wider text-white shadow-md shadow-indigo-500/10">
                S
              </div>
              <div>
                <h1 className="font-semibold text-xs leading-none bg-gradient-to-r from-indigo-600 dark:from-indigo-200 to-zinc-900 dark:to-white bg-clip-text text-transparent">
                  SARA AI
                </h1>
                <span className="text-[9px] text-zinc-500 font-medium">Smart secretary</span>
              </div>
            </div>
            
            {/* Sidebar toggle icon (instead of old theme toggle) */}
            <button
              onClick={handleToggleSidebar}
              title="Hide Sidebar"
              className="p-1.5 rounded-lg bg-zinc-200/50 dark:bg-zinc-800 hover:bg-zinc-200/80 dark:hover:bg-zinc-700 border border-zinc-300/40 dark:border-zinc-700 text-zinc-500 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200 transition-colors cursor-pointer"
            >
              <PanelLeftClose size={14} />
            </button>
          </div>

          {/* New Chat Button */}
          {activeSessionId !== null && (
            <div className="p-3">
              <button
                onClick={() => setActiveSessionId(null)}
                className="w-full py-2.5 px-4 rounded-xl border font-medium text-xs flex items-center justify-center gap-2 transition-all cursor-pointer shadow-sm active:scale-[0.98] bg-white dark:bg-[#1E293B] border-zinc-200 dark:border-[#1E293B] text-zinc-700 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-[#1E293B]/50"
              >
                <Plus size={14} />
                Upload New Meeting
              </button>
            </div>
          )}

          {/* Session Filenames list */}
          <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-1">
            <span className="px-3 py-1.5 text-[10px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider block">
              Meeting Sessions
            </span>
            
            {sessions.length === 0 ? (
              <p className="text-[11px] text-zinc-400 dark:text-zinc-500 px-3 py-2 italic">
                No active sessions.
              </p>
            ) : (
              sessions.map((s) => (
                <div
                  key={s.id}
                  onClick={() => setActiveSessionId(s.id)}
                  className={`group px-3 py-2.5 rounded-xl flex items-center gap-2 cursor-pointer transition-all border ${
                    activeSessionId === s.id
                      ? "bg-zinc-200/60 dark:bg-[#1E293B]/80 border-zinc-300/30 dark:border-[#334155]/50 text-indigo-600 dark:text-indigo-400"
                      : "bg-transparent border-transparent hover:bg-zinc-200/30 dark:hover:bg-[#1E293B]/30 text-zinc-600 dark:text-[#94A3B8] hover:text-zinc-900 dark:hover:text-zinc-200"
                  }`}
                >
                  {s.status === "PENDING" || s.status === "PROCESSING" ? (
                    <Loader2 size={13} className="animate-spin text-indigo-500 shrink-0" />
                  ) : s.fileName && isAudioFile(s.fileName) ? (
                    <FileAudio size={13} className="shrink-0" />
                  ) : (
                    <FileText size={13} className="shrink-0" />
                  )}

                  <div className="flex-1 min-w-0 text-left">
                    <p className="text-[11px] font-semibold truncate leading-tight">{s.fileName}</p>
                    <span className="text-[9px] text-zinc-400 dark:text-zinc-500 block leading-none mt-0.5">{s.createdAt}</span>
                  </div>

                  {/* Delete session button */}
                  <button
                    onClick={(e) => handleDeleteSession(s.id, e)}
                    className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-zinc-300/50 dark:hover:bg-zinc-700/60 text-zinc-400 hover:text-rose-500 transition-all cursor-pointer"
                    title="Delete session"
                  >
                    <Trash2 size={11} />
                  </button>
                </div>
              ))
            )}
          </div>

          {/* Sidebar Footer */}
          <div className="p-3 border-t border-zinc-200 dark:border-[#1E293B] text-[10px] text-zinc-400 dark:text-[#94A3B8] text-center font-medium">
            SARA Assistant v1.2
          </div>
        </aside>

        {/* 2. MAIN COMPONENT VIEWPORT */}
        <main className="flex-1 flex flex-col h-full bg-zinc-50 dark:bg-background relative overflow-hidden">
          
          {/* Floating Show Sidebar Button (only visible when sidebar is closed AND on upload screen) */}
          {!sidebarOpen && activeSessionId === null && (
            <div className="absolute top-4 left-4 z-50">
              <button
                onClick={handleToggleSidebar}
                title="Show Sidebar"
                className="p-2.5 rounded-xl bg-white dark:bg-[#1E293B] shadow-md border border-zinc-200 dark:border-[#334155] text-zinc-500 dark:text-[#94A3B8] hover:text-zinc-800 dark:hover:text-[#F8FAFC] hover:scale-105 active:scale-95 transition-all cursor-pointer flex items-center justify-center"
              >
                <PanelLeftOpen size={15} />
              </button>
            </div>
          )}

          {/* UPLOAD SCREEN: Shown when activeSessionId is null (IDLE / FRESH START) */}
          {activeSessionId === null && (
            <div className="flex-1 flex flex-col justify-center items-center p-8 max-w-xl mx-auto w-full">
              
              {/* Logo/Hero area */}
              <div className="text-center mb-8 space-y-3">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center font-bold text-xl tracking-wider text-white shadow-lg shadow-indigo-600/10 mx-auto transform hover:rotate-3 transition-transform duration-300">
                  S
                </div>
                <h2 className="text-xl font-bold text-zinc-900 dark:text-[#F8FAFC]">
                  Upload Meeting <span className="bg-gradient-to-r from-indigo-600 to-purple-600 dark:from-[#A855F7] dark:to-[#C084FC] bg-clip-text text-transparent">Minutes</span>
                </h2>
                <p className="text-xs text-zinc-500 dark:text-[#94A3B8] max-w-xs mx-auto">
                  Transcribe meeting audio, synthesize summary, assign action items, and ask questions.
                </p>
              </div>

              {/* Drag & Drop zone */}
              <div 
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`w-full p-8 rounded-2xl border-2 border-dashed flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-300 ${
                  isDragging 
                    ? "border-indigo-500 bg-indigo-500/5 dark:bg-[#1E293B]/40 dark:border-[#A855F7] scale-[1.01]" 
                    : "border-zinc-300 dark:border-[#475569] bg-white/50 dark:bg-[#1E293B]/30 hover:border-zinc-400 dark:hover:border-[#64748B] hover:bg-white dark:hover:bg-[#1E293B]/50"
                }`}
                onClick={() => document.getElementById("fileInput")?.click()}
              >
                <input 
                  type="file" 
                  id="fileInput" 
                  className="hidden" 
                  onChange={handleFileChange}
                  accept=".mp3,.wav,.m4a,.aac,.pdf,.txt,.doc,.docx"
                />
                
                <div className="w-10 h-10 rounded-lg bg-zinc-100 dark:bg-[#1E293B] flex items-center justify-center text-indigo-600 dark:text-[#A855F7] mb-3 border border-zinc-200 dark:border-[#334155]">
                  {file ? (
                    isAudioFile(file.name) ? <FileAudio size={18} className="dark:text-[#A855F7]" /> : <FileText size={18} className="dark:text-[#A855F7]" />
                  ) : (
                    <Upload size={18} className="dark:text-[#A855F7]" />
                  )}
                </div>

                {file ? (
                  <div className="space-y-1">
                    <p className="text-xs font-semibold text-zinc-800 dark:text-[#F8FAFC] truncate max-w-xs">{file.name}</p>
                    <p className="text-[10px] text-zinc-400 dark:text-[#94A3B8]">{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <p className="text-xs font-semibold text-zinc-600 dark:text-[#E2E8F0]">Drag and drop file here, or click to browse</p>
                    <p className="text-[10px] text-zinc-400 dark:text-[#94A3B8]">Supports Audio (MP3, WAV) and Documents (PDF, TXT)</p>
                  </div>
                )}
              </div>

              {/* Start button */}
              {file && (
                <button
                  onClick={(e) => { e.stopPropagation(); handleStartAnalysis(); }}
                  disabled={isUploading}
                  className="w-full mt-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-semibold py-3 px-6 rounded-xl shadow shadow-indigo-600/10 active:scale-[0.98] transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                >
                  {isUploading ? (
                    <>
                      <Loader2 size={14} className="animate-spin" />
                      Uploading and Parsing...
                    </>
                  ) : (
                    <>
                      Start Analysis
                      <ArrowRight size={14} />
                    </>
                  )}
                </button>
              )}

              {/* Upload Status logs */}
              {uploadStatus && (
                <div className="w-full mt-4 p-3 bg-indigo-50 dark:bg-indigo-950/20 border border-indigo-200/50 dark:border-indigo-900/40 rounded-xl flex items-start gap-2.5">
                  <Info size={14} className="text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
                  <p className="text-[11px] text-indigo-700 dark:text-indigo-300 leading-relaxed">{uploadStatus}</p>
                </div>
              )}

              {/* Info grid */}
              {!file && (
                <div className="grid grid-cols-2 gap-3 w-full mt-8">
                  <div className="p-3 bg-white dark:bg-[#1E293B] border border-zinc-200 dark:border-[#334155] rounded-xl flex flex-col gap-1">
                    <span className="text-[10px] font-bold text-zinc-400 dark:text-[#E2E8F0] uppercase tracking-wider">Audio Transcription</span>
                    <p className="text-[10px] text-zinc-500 dark:text-[#94A3B8] leading-normal">High-fidelity speech-to-text with AI4Thai Whisper API.</p>
                  </div>
                  <div className="p-3 bg-white dark:bg-[#1E293B] border border-zinc-200 dark:border-[#334155] rounded-xl flex flex-col gap-1">
                    <span className="text-[10px] font-bold text-zinc-400 dark:text-[#E2E8F0] uppercase tracking-wider">Smart Summarization</span>
                    <p className="text-[10px] text-zinc-500 dark:text-[#94A3B8] leading-normal">Extracts key decisions and concrete action items via Qwen 3.5.</p>
                  </div>
                </div>
              )}

            </div>
          )}

          {/* ACTIVE CHAT SCREEN */}
          {activeSessionId !== null && activeSession && (
            <div className="flex-1 flex flex-col h-full overflow-hidden relative">
              
              {/* Header */}
              <header className="px-6 py-4 border-b border-zinc-200 dark:border-[#1E293B] flex items-center justify-between bg-white/80 dark:bg-[#1E293B]/20 glass z-10">
                <div className="flex items-center gap-2.5">
                  {/* Inline Open Sidebar Button */}
                  {!sidebarOpen && (
                    <button
                      onClick={handleToggleSidebar}
                      title="Show Sidebar"
                      className="p-1.5 rounded-lg bg-zinc-200/50 dark:bg-zinc-800 hover:bg-zinc-200/80 dark:hover:bg-zinc-700 border border-zinc-300/40 dark:border-zinc-700 text-zinc-500 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200 transition-colors cursor-pointer mr-1"
                    >
                      <PanelLeftOpen size={14} />
                    </button>
                  )}
                  
                  {activeSession.fileName && isAudioFile(activeSession.fileName) ? (
                    <FileAudio size={15} className="text-indigo-600 dark:text-indigo-400 shrink-0" />
                  ) : (
                    <FileText size={15} className="text-indigo-600 dark:text-indigo-400 shrink-0" />
                  )}
                  <h2 className="text-xs font-bold text-zinc-800 dark:text-zinc-200 truncate max-w-[200px] sm:max-w-sm md:max-w-md">
                    {activeSession.fileName}
                  </h2>
                </div>
                <div className="flex items-center gap-2 text-[10px] text-zinc-400 dark:text-zinc-500 font-semibold">
                  <span className={`w-2 h-2 rounded-full ${
                    activeSession.status === "COMPLETED" ? "bg-emerald-500" :
                    activeSession.status === "FAILED" ? "bg-rose-500" :
                    "bg-indigo-500 animate-pulse"
                  }`}></span>
                  <span>{activeSession.status}</span>
                </div>
              </header>

              {/* Main view container */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                
                {/* 1. LOADING / PROCESSING VIEW */}
                {(activeSession.status === "PENDING" || activeSession.status === "PROCESSING") && (
                  <div className="py-12 max-w-md mx-auto text-center flex flex-col items-center">
                    <div className="w-16 h-16 rounded-full bg-white dark:bg-zinc-900 border border-indigo-500/20 dark:border-indigo-400/20 flex items-center justify-center mb-6 pulse-glow">
                      <Loader2 size={24} className="text-indigo-600 dark:text-indigo-400 animate-spin" />
                    </div>
                    <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">Analyzing Meeting Details</h3>
                    <p className="text-xs text-zinc-400 mt-2 leading-relaxed">
                      SARA is currently processing the audio recording. This includes transcribing, extracting intelligence points, and preparing the workspace.
                    </p>
                    
                    <div className="w-full mt-6 bg-white dark:bg-[#1E293B] border border-zinc-200 dark:border-[#334155] rounded-xl p-4 text-left font-mono space-y-2 glass">
                      <span className="text-[10px] text-indigo-600 dark:text-indigo-400 block font-bold uppercase tracking-wider">Pipeline Steps</span>
                      <div className="h-[1px] bg-zinc-200 dark:bg-zinc-800/60 my-2"></div>
                      <div className="text-[10px] space-y-1.5 text-zinc-500">
                        <div className="flex items-center gap-2 text-emerald-500">
                          <span>✓</span> <span>Audio uploaded successfully</span>
                        </div>
                        <div className="flex items-center gap-2 text-zinc-700 dark:text-zinc-300">
                          {activeSession.status === "PENDING" ? (
                            <span className="text-zinc-400 animate-pulse">●</span>
                          ) : (
                            <span className="text-indigo-500 animate-spin">⟳</span>
                          )}
                          <span>Speech-to-Text Transcription...</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span>○</span> <span>Semantic analysis & summary extraction</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span>○</span> <span>Dispatching actions via FastMCP server</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* 2. FAILED STATE VIEW */}
                {activeSession.status === "FAILED" && (
                  <div className="py-12 max-w-sm mx-auto text-center space-y-4">
                    <div className="w-12 h-12 rounded-full bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-500 mx-auto">
                      <AlertCircle size={24} />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">Processing Failed</h3>
                      <p className="text-xs text-zinc-400 mt-2 leading-relaxed">
                        We could not transcribe or summarize this meeting file. Please ensure it is a valid format and the backend services are functional.
                      </p>
                    </div>
                  </div>
                )}

                {/* 3. COMPLETED CHAT MESSAGES VIEW */}
                {activeSession.status === "COMPLETED" && (
                  <div className="space-y-6">
                    {activeSession.chatHistory.map((message, index) => (
                      <div 
                        key={index} 
                        className={`flex gap-4 max-w-3xl ${message.role === "user" ? "ml-auto flex-row-reverse" : "mr-auto"}`}
                      >
                        {/* Avatar */}
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 text-xs font-bold border ${
                          message.role === "user" 
                            ? "bg-white dark:bg-[#1E293B] border-zinc-200 dark:border-[#334155] text-zinc-600 dark:text-zinc-300" 
                            : "bg-gradient-to-tr from-indigo-500 to-purple-600 border-indigo-400 text-white"
                        }`}>
                          {message.role === "user" ? "U" : "S"}
                        </div>

                        {/* Message content */}
                        <div className="space-y-1 max-w-full">
                          {message.isSummary && message.summaryData ? (
                            // Render Rich Report Card
                            renderSummaryCard(message.summaryData)
                          ) : (
                            // Render Standard Message Bubble
                            <div className={`p-4 rounded-2xl text-xs leading-relaxed ${
                              message.role === "user" 
                                ? "bg-indigo-600 text-white rounded-tr-none font-medium max-w-lg shadow-sm text-left" 
                                : "bg-white dark:bg-[#1E293B] border border-zinc-200 dark:border-[#334155] rounded-tl-none max-w-xl text-zinc-800 dark:text-zinc-200 shadow-sm text-left"
                            }`}>
                              {message.role === "user" ? (
                                <p className="whitespace-pre-wrap">{message.content}</p>
                              ) : (
                                <div className="space-y-1">
                                  {formatText(message.content)}
                                </div>
                              )}
                            </div>
                          )}
                          <p className={`text-[8px] text-zinc-400 dark:text-zinc-500 px-1 ${message.role === "user" ? "text-right" : ""}`}>
                            {message.timestamp}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* AI Processing input Indicator */}
                {isSending && (
                  <div className="flex gap-4 max-w-xl mr-auto">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-indigo-500 to-purple-600 border-indigo-400 text-white flex items-center justify-center shrink-0 text-xs font-bold">
                      S
                    </div>
                    <div className="bg-white dark:bg-[#1E293B] border border-zinc-200 dark:border-[#334155] p-4 rounded-2xl rounded-tl-none flex items-center gap-2 shadow-sm">
                      <Loader2 size={13} className="animate-spin text-indigo-500" />
                      <span className="text-xs text-zinc-500 dark:text-zinc-400">SARA is formulated an answer...</span>
                    </div>
                  </div>
                )}
                
                <div ref={chatEndRef} />
              </div>

              {/* Chat Input form */}
              {activeSession.status === "COMPLETED" && (
                <footer className="p-4 border-t border-zinc-200 dark:border-[#1E293B] bg-white/80 dark:bg-[#1E293B]/40 glass z-10">
                  <form onSubmit={handleSendMessage} className="max-w-3xl mx-auto flex items-center gap-2">
                    <input
                      type="text"
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      placeholder="Ask SARA about the meeting..."
                      className="flex-1 bg-zinc-50 dark:bg-[#1E293B] border border-zinc-200 dark:border-[#334155] focus:border-indigo-500/80 text-zinc-800 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500/10 transition-all font-medium"
                      disabled={isSending}
                    />
                    <button
                      type="submit"
                      disabled={!inputMessage.trim() || isSending}
                      className="w-10 h-10 bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-100 dark:disabled:bg-[#1E293B] disabled:text-zinc-400 dark:disabled:text-zinc-600 text-white rounded-xl flex items-center justify-center transition-all cursor-pointer active:scale-[0.96] shadow-sm shadow-indigo-600/10"
                    >
                      <Send size={14} />
                    </button>
                  </form>
                </footer>
              )}

            </div>
          )}

        </main>
      </div>
    </div>
  );
}
