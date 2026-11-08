import React, { useState, useRef, useEffect } from "react";
import {
  Sparkles,
  X,
  Send,
  Bot,
  User,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
  CheckCircle2,
  Trash2,
  Cpu,
  Layers,
  AlertTriangle,
} from "lucide-react";

import { Button } from "@/components/ui/Button";
import { confirmChangeRequest } from "@/services/api";
import { instrumentedFetch } from "@/lib/telemetry";
import type { ToolCallRecord } from "@/types/api";

interface ChatMessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCallRecord[];
  draftCreated?: {
    draft_id: string;
    title: string;
    affected_parts: string[];
    reason: string;
    category?: string;
    priority?: string;
  } | null;
  confirmedCrNumber?: string | null;
  isStreaming?: boolean;
}

const SUGGESTED_PROMPTS = [
  "Find obsolete parts in released BOMs",
  "What is the change impact of part PMP-0010?",
  "Compare EBOM and MBOM for PMP-0001",
  "Find duplicate parts in catalog",
  "Draft an ECR for PMP-0290 due to vibration failure",
];

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export function AiAssistantPanel() {
  const [isOpen, setIsOpen] = useState(() => {
    return new URLSearchParams(window.location.search).get("assistant") === "open";
  });
  const [inputMessage, setInputMessage] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [expandedActivity, setExpandedActivity] = useState<Record<string, boolean>>({});
  const [confirmingDraftId, setConfirmingDraftId] = useState<string | null>(null);

  const [messages, setMessages] = useState<ChatMessageItem[]>([
    {
      id: "welcome-msg",
      role: "assistant",
      content:
        "Hello! I am your **Industrial PLM AI Assistant** connected to PTC Windchill-style MCP tools.\n\n" +
        "I can audit product structures, calculate blast-radius change impacts, compare BOMs, detect redundant parts, and draft change requests.\n\n" +
        "Try clicking one of the suggested prompts below to start!",
    },
  ]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  useEffect(() => {
    const handleCustomOpen = (e: Event) => {
      const customEvent = e as CustomEvent<{ prompt?: string }>;
      setIsOpen(true);
      if (customEvent.detail?.prompt) {
        handleSendMessage(customEvent.detail.prompt);
      }
    };
    window.addEventListener("open-plm-assistant", handleCustomOpen);
    return () => window.removeEventListener("open-plm-assistant", handleCustomOpen);
  }, []);

  const handleSendMessage = async (textToSend?: string) => {
    const prompt = (textToSend || inputMessage).trim();
    if (!prompt || isStreaming) return;

    setInputMessage("");

    // Add user message to state
    const userMsgId = `user-${Date.now()}`;
    const userMsg: ChatMessageItem = {
      id: userMsgId,
      role: "user",
      content: prompt,
    };

    // Prepare placeholder assistant message
    const assistantMsgId = `assistant-${Date.now()}`;
    const initialAssistantMsg: ChatMessageItem = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      toolCalls: [],
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, initialAssistantMsg]);
    setIsStreaming(true);

    try {
      const response = await instrumentedFetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: prompt,
          history: messages
            .filter((m) => m.id !== "welcome-msg")
            .map((m) => ({ role: m.role, content: m.content })),
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP error ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      let accumulatedContent = "";
      const currentToolCalls: ToolCallRecord[] = [];
      let detectedDraft: any = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || ""; // Keep trailing partial chunk in buffer

        for (const rawEvent of events) {
          if (!rawEvent.trim()) continue;

          let eventType = "message";
          let dataStr = "";

          for (const line of rawEvent.split("\n")) {
            if (line.startsWith("event: ")) {
              eventType = line.replace("event: ", "").trim();
            } else if (line.startsWith("data: ")) {
              dataStr = line.replace("data: ", "").trim();
            }
          }

          if (!dataStr) continue;

          try {
            const data = JSON.parse(dataStr);

            if (eventType === "tool_call") {
              currentToolCalls.push({
                tool: data.tool,
                arguments: data.arguments || {},
                status: "RUNNING",
              });
              // Auto-expand activity for visibility
              setExpandedActivity((prev) => ({ ...prev, [assistantMsgId]: true }));
            } else if (eventType === "tool_result") {
              const idx = currentToolCalls.findIndex((t) => t.tool === data.tool);
              if (idx !== -1) {
                currentToolCalls[idx] = data;
              } else {
                currentToolCalls.push(data);
              }
            } else if (eventType === "draft_created") {
              detectedDraft = data;
            } else if (eventType === "content_delta") {
              accumulatedContent += data.delta;
            } else if (eventType === "done") {
              if (data.draft_created) detectedDraft = data.draft_created;
            }

            // Live update of message content
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId
                  ? {
                      ...msg,
                      content: accumulatedContent,
                      toolCalls: [...currentToolCalls],
                      draftCreated: detectedDraft,
                      isStreaming: true,
                    }
                  : msg
              )
            );
          } catch (parseErr) {
            console.error("Failed to parse SSE JSON:", parseErr, dataStr);
          }
        }
      }

      // Mark streaming complete
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? {
                ...msg,
                content: accumulatedContent,
                toolCalls: [...currentToolCalls],
                draftCreated: detectedDraft,
                isStreaming: false,
              }
            : msg
        )
      );
    } catch (err: any) {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? {
                ...msg,
                content: `An error occurred while communicating with the AI Assistant: ${err.message}`,
                isStreaming: false,
              }
            : msg
        )
      );
    } finally {
      setIsStreaming(false);
    }
  };

  const handleConfirmDraft = async (msgId: string, draftId: string) => {
    try {
      setConfirmingDraftId(draftId);
      const res = await confirmChangeRequest(draftId);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId
            ? {
                ...m,
                confirmedCrNumber: res.cr_number,
              }
            : m
        )
      );
    } catch (err: any) {
      alert(`Failed to commit change request: ${err.message}`);
    } finally {
      setConfirmingDraftId(null);
    }
  };

  const clearChat = () => {
    setMessages([
      {
        id: "welcome-msg",
        role: "assistant",
        content: "Chat history cleared. How can I assist you with your PLM structures today?",
      },
    ]);
  };

  return (
    <>
      {/* Floating Launcher Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          aria-label="Open PLM AI Assistant"
          className="fixed bottom-6 right-6 z-40 flex items-center gap-2.5 px-4 py-3 rounded-full bg-primary text-primary-foreground font-semibold shadow-2xl hover:bg-primary/90 hover:scale-105 transition-all focus:outline-none focus:ring-4 focus:ring-primary/40"
        >
          <Sparkles className="w-5 h-5 text-amber-300 animate-spin-slow" />
          <span>PLM AI Assistant</span>
          <span className="text-[10px] font-bold px-1.5 py-0.2 rounded-full bg-white/20 text-white">
            MCP
          </span>
        </button>
      )}

      {/* Slide-Over Side Drawer */}
      {isOpen && (
        <aside
          role="complementary"
          aria-label="AI Assistant Side Panel"
          className="fixed top-0 right-0 z-50 h-screen w-full sm:w-[440px] border-l border-border bg-card/95 backdrop-blur-xl shadow-2xl flex flex-col transition-transform animate-in slide-in-from-right duration-300"
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-border bg-card">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-primary/10 text-primary">
                <Bot className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5">
                  PLM AI Assistant
                  <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-primary/20 text-primary">
                    MCP Tools
                  </span>
                </h3>
                <p className="text-[11px] text-muted-foreground">Windchill-style tool calling engine</p>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                title="Clear Conversation"
                onClick={clearChat}
                className="h-8 w-8 text-muted-foreground hover:text-foreground"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Close Assistant"
                onClick={() => setIsOpen(false)}
                className="h-8 w-8 text-muted-foreground hover:text-foreground"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* Messages Container */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-3 text-sm ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                {msg.role === "assistant" && (
                  <div className="w-7 h-7 rounded-full bg-primary/10 text-primary flex items-center justify-center shrink-0 mt-0.5">
                    <Bot className="w-4 h-4" />
                  </div>
                )}

                <div
                  className={`max-w-[85%] rounded-2xl p-3.5 space-y-3 ${
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground rounded-tr-xs"
                      : "bg-muted/60 text-foreground border border-border/60 rounded-tl-xs shadow-xs"
                  }`}
                >
                  {/* Collapsible Activity Section (Tool Calls) */}
                  {msg.toolCalls && msg.toolCalls.length > 0 && (
                    <div className="border border-border/60 rounded-lg overflow-hidden bg-background/80 text-xs">
                      <button
                        onClick={() =>
                          setExpandedActivity((prev) => ({
                            ...prev,
                            [msg.id]: !prev[msg.id],
                          }))
                        }
                        className="w-full flex items-center justify-between p-2.5 bg-muted/40 hover:bg-muted/70 transition-colors font-medium text-muted-foreground text-left"
                      >
                        <span className="flex items-center gap-1.5 font-semibold text-foreground">
                          <Cpu className="w-3.5 h-3.5 text-primary" /> Activity ({msg.toolCalls.length}{" "}
                          tool {msg.toolCalls.length === 1 ? "call" : "calls"})
                        </span>
                        {expandedActivity[msg.id] ? (
                          <ChevronDown className="w-3.5 h-3.5" />
                        ) : (
                          <ChevronRight className="w-3.5 h-3.5" />
                        )}
                      </button>

                      {expandedActivity[msg.id] && (
                        <div className="p-2.5 space-y-2 divide-y divide-border/40 font-mono text-[11px]">
                          {msg.toolCalls.map((tc, idx) => (
                            <div key={idx} className={idx > 0 ? "pt-2" : ""}>
                              <div className="flex items-center justify-between">
                                <span className="font-bold text-primary">
                                  {tc.tool}
                                </span>
                                <span
                                  className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                                    tc.status === "SUCCESS"
                                      ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                                      : "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                                  }`}
                                >
                                  {tc.status}
                                </span>
                              </div>
                              {tc.arguments && Object.keys(tc.arguments).length > 0 && (
                                <div className="text-muted-foreground text-[10px] mt-0.5 truncate">
                                  args: {JSON.stringify(tc.arguments)}
                                </div>
                              )}
                              {tc.summary && (
                                <div className="text-foreground font-sans text-xs mt-1">
                                  {tc.summary}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Main Message Content */}
                  <div className="prose prose-sm dark:prose-invert max-w-none text-xs sm:text-sm leading-relaxed whitespace-pre-wrap font-sans">
                    {msg.content}
                    {msg.isStreaming && (
                      <span className="inline-block w-1.5 h-4 ml-1 bg-primary animate-pulse align-middle" />
                    )}
                  </div>

                  {/* SAFETY GATE: Interactive Confirmation Card for Drafts */}
                  {msg.draftCreated && (
                    <div className="mt-3 p-3.5 rounded-xl border border-amber-300 dark:border-amber-800 bg-amber-50/80 dark:bg-amber-950/40 text-foreground space-y-2.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-amber-200 dark:bg-amber-900/60 text-amber-900 dark:text-amber-200">
                          UNPERSISTED DRAFT: {msg.draftCreated.draft_id}
                        </span>
                        <span className="text-[10px] text-amber-800 dark:text-amber-300 font-semibold">
                          Confirm to write
                        </span>
                      </div>

                      <div className="text-xs">
                        <div className="font-semibold text-foreground">{msg.draftCreated.title}</div>
                        <div className="text-[11px] text-muted-foreground mt-0.5 font-mono">
                          Affected: {msg.draftCreated.affected_parts.join(", ")}
                        </div>
                      </div>

                      {msg.confirmedCrNumber ? (
                        <div className="flex items-center gap-1.5 p-2 rounded-lg bg-emerald-100 dark:bg-emerald-950/80 text-emerald-800 dark:text-emerald-300 text-xs font-semibold">
                          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                          <span>Committed as {msg.confirmedCrNumber} to PLM database!</span>
                        </div>
                      ) : (
                        <Button
                          size="sm"
                          onClick={() => handleConfirmDraft(msg.id, msg.draftCreated!.draft_id)}
                          isLoading={confirmingDraftId === msg.draftCreated.draft_id}
                          className="w-full bg-emerald-600 hover:bg-emerald-700 text-white text-xs gap-1.5"
                        >
                          <ShieldCheck className="w-4 h-4" /> Confirm & Commit ECR
                        </Button>
                      )}
                    </div>
                  )}
                </div>

                {msg.role === "user" && (
                  <div className="w-7 h-7 rounded-full bg-muted text-muted-foreground flex items-center justify-center shrink-0 mt-0.5">
                    <User className="w-4 h-4" />
                  </div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Suggested Prompt Chips */}
          <div className="p-3 border-t border-border/60 bg-muted/30">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground block mb-1.5">
              Suggested Prompts:
            </span>
            <div className="flex gap-1.5 overflow-x-auto pb-1 scrollbar-none">
              {SUGGESTED_PROMPTS.map((prompt, i) => (
                <button
                  key={i}
                  disabled={isStreaming}
                  onClick={() => handleSendMessage(prompt)}
                  className="px-2.5 py-1 rounded-full text-xs bg-card border border-border/80 hover:border-primary/50 text-muted-foreground hover:text-foreground whitespace-nowrap transition-colors disabled:opacity-50"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>

          {/* Input Box */}
          <div className="p-3 border-t border-border bg-card">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="flex items-center gap-2"
            >
              <input
                type="text"
                value={inputMessage}
                disabled={isStreaming}
                onChange={(e) => setInputMessage(e.target.value)}
                placeholder="Ask about parts, BOMs, impact, or draft an ECR..."
                className="flex-1 px-3.5 py-2 text-xs sm:text-sm rounded-lg bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
              />
              <Button
                type="submit"
                size="sm"
                disabled={!inputMessage.trim() || isStreaming}
                isLoading={isStreaming}
                className="h-9 px-3"
              >
                <Send className="w-4 h-4" />
              </Button>
            </form>
            <p className="text-[10px] text-muted-foreground text-center mt-1.5">
              Writes require explicit confirmation in UI • Keys secured on backend
            </p>
          </div>
        </aside>
      )}
    </>
  );
}

