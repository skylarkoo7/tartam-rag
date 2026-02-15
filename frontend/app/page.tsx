"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { FilterBar } from "../components/FilterBar";
import { MessageBubble } from "../components/MessageBubble";
import { fetchFilters, fetchHistory, sendChat, triggerIngest } from "../lib/api";
import { ChatMessage, Citation, MessageRecord, StyleMode } from "../lib/types";

function createSessionId() {
  return `session_${Math.random().toString(36).slice(2)}_${Date.now()}`;
}

function mapHistoryRow(row: MessageRecord): ChatMessage {
  let citations: Citation[] = [];
  if (row.citations_json) {
    try {
      citations = JSON.parse(row.citations_json) as Citation[];
    } catch {
      citations = [];
    }
  }

  return {
    id: row.message_id,
    role: row.role,
    text: row.text,
    styleTag: row.style_tag,
    citations,
    createdAt: row.created_at
  };
}

export default function HomePage() {
  const [sessionId, setSessionId] = useState("");
  const [sessions, setSessions] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [bootLoading, setBootLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [styleMode, setStyleMode] = useState<StyleMode>("auto");
  const [granth, setGranth] = useState("");
  const [prakran, setPrakran] = useState("");
  const [granths, setGranths] = useState<string[]>([]);
  const [prakrans, setPrakrans] = useState<string[]>([]);
  const [ingesting, setIngesting] = useState(false);

  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const key = "tartam_session_id";
    const sessionsKey = "tartam_sessions";
    let current = window.localStorage.getItem(key);
    if (!current) {
      current = createSessionId();
      window.localStorage.setItem(key, current);
    }

    let known: string[] = [];
    try {
      known = JSON.parse(window.localStorage.getItem(sessionsKey) ?? "[]") as string[];
    } catch {
      known = [];
    }

    if (!known.includes(current)) {
      known = [current, ...known].slice(0, 30);
      window.localStorage.setItem(sessionsKey, JSON.stringify(known));
    }

    setSessions(known);
    setSessionId(current);

    Promise.all([fetchFilters(), fetchHistory(current)])
      .then(([filterPayload, history]) => {
        setGranths(filterPayload.granths);
        setPrakrans(filterPayload.prakrans);
        setMessages(history.map(mapHistoryRow));
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load initial data");
      })
      .finally(() => {
        setBootLoading(false);
      });
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages]);

  const canSend = useMemo(() => input.trim().length > 0 && !loading && !!sessionId, [input, loading, sessionId]);

  async function onSend() {
    const message = input.trim();
    if (!message || !sessionId) {
      return;
    }

    const userMessage: ChatMessage = {
      id: `user_${Date.now()}`,
      role: "user",
      text: message,
      styleTag: styleMode,
      citations: [],
      createdAt: new Date().toISOString()
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const response = await sendChat({
        session_id: sessionId,
        message,
        style_mode: styleMode,
        filters: {
          granth: granth || undefined,
          prakran: prakran || undefined
        }
      });

      const assistantText = response.not_found && response.follow_up_question
        ? `${response.answer}\n\n${response.follow_up_question}`
        : response.answer;

      const assistant: ChatMessage = {
        id: `assistant_${Date.now()}`,
        role: "assistant",
        text: assistantText,
        styleTag: response.answer_style,
        citations: response.citations,
        createdAt: new Date().toISOString()
      };
      setMessages((prev) => [...prev, assistant]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat request failed");
    } finally {
      setLoading(false);
    }
  }

  async function openSession(nextSessionId: string) {
    if (!nextSessionId) {
      return;
    }
    setSessionId(nextSessionId);
    window.localStorage.setItem("tartam_session_id", nextSessionId);

    setBootLoading(true);
    setError(null);
    try {
      const history = await fetchHistory(nextSessionId);
      setMessages(history.map(mapHistoryRow));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load session history");
    } finally {
      setBootLoading(false);
    }
  }

  async function createNewSession() {
    const next = createSessionId();
    const updated = [next, ...sessions].slice(0, 30);
    setSessions(updated);
    window.localStorage.setItem("tartam_sessions", JSON.stringify(updated));
    setMessages([]);
    await openSession(next);
  }

  async function onIngest() {
    setIngesting(true);
    setError(null);
    try {
      const result = await triggerIngest();
      const notes = result.notes?.length ? `\nNotes: ${result.notes.join(" | ")}` : "";
      alert(
        `Ingestion complete. Files: ${result.files_processed}, chunks: ${result.chunks_created}, failed: ${result.failed_files}${notes}`
      );
      const nextFilters = await fetchFilters();
      setGranths(nextFilters.granths);
      setPrakrans(nextFilters.prakrans);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to ingest");
    } finally {
      setIngesting(false);
    }
  }

  return (
    <main className="h-screen bg-[#f6f7f4] text-zinc-900">
      <div className="mx-auto flex h-full max-w-[1400px]">
        <aside className="hidden w-72 flex-col border-r border-zinc-200 bg-[#f0f2ee] p-4 md:flex">
          <h1 className="text-lg font-semibold tracking-tight">Tartam RAG</h1>
          <p className="mt-1 text-xs text-zinc-500">Scripture-grounded multilingual assistant</p>

          <div className="mt-4 flex flex-col gap-2">
            <button
              className="rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800"
              onClick={() => void createNewSession()}
              type="button"
            >
              + New chat
            </button>
            <button
              className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
              onClick={onIngest}
              disabled={ingesting}
              type="button"
            >
              {ingesting ? "Indexing..." : "Re-index corpus"}
            </button>
          </div>

          <div className="mt-5 text-xs font-semibold uppercase tracking-wide text-zinc-500">Recent Sessions</div>
          <div className="mt-2 flex-1 space-y-1 overflow-y-auto pr-1">
            {sessions.map((item) => (
              <button
                key={item}
                className={`w-full rounded-lg px-3 py-2 text-left text-xs transition ${
                  item === sessionId ? "bg-zinc-900 text-white" : "bg-white text-zinc-700 hover:bg-zinc-100"
                }`}
                onClick={() => void openSession(item)}
                type="button"
              >
                {item}
              </button>
            ))}
          </div>
        </aside>

        <section className="flex min-w-0 flex-1 flex-col">
          <header className="border-b border-zinc-200 bg-white/80 px-4 py-3 backdrop-blur md:px-6">
            <div className="mx-auto flex w-full max-w-4xl items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold">Multilingual Tartam Chat</h2>
                <p className="text-xs text-zinc-500">Hindi · Gujarati · Hinglish · Gujarati Roman</p>
              </div>
              <button
                className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 md:hidden"
                onClick={() => void createNewSession()}
                type="button"
              >
                New chat
              </button>
            </div>
          </header>

          <div className="border-b border-zinc-200 bg-white px-4 py-3 md:px-6">
            <div className="mx-auto w-full max-w-4xl">
              <FilterBar
                styleMode={styleMode}
                onStyleMode={setStyleMode}
                granth={granth}
                prakran={prakran}
                granths={granths}
                prakrans={prakrans}
                onGranth={setGranth}
                onPrakran={setPrakran}
              />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-5 md:px-6">
            <div className="mx-auto w-full max-w-4xl space-y-5">
              {bootLoading ? (
                <div className="rounded-xl border border-zinc-200 bg-white p-4 text-sm text-zinc-600">Loading chat...</div>
              ) : null}

              {error ? (
                <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>
              ) : null}

              {!bootLoading && messages.length === 0 ? (
                <div className="rounded-xl border border-zinc-200 bg-white p-5 text-sm text-zinc-600">
                  Ask anything from the corpus. Example: <em>mohajal kya hai</em> or <em>kem cho</em>.
                </div>
              ) : null}

              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              <div ref={scrollRef} />
            </div>
          </div>

          <div className="border-t border-zinc-200 bg-white px-4 py-4 md:px-6">
            <div className="mx-auto w-full max-w-4xl">
              <div className="rounded-2xl border border-zinc-300 bg-zinc-50 p-2">
                <textarea
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      void onSend();
                    }
                  }}
                  rows={3}
                  placeholder="Message Tartam RAG..."
                  className="w-full resize-none border-0 bg-transparent px-2 py-1 text-[15px] text-zinc-900 outline-none placeholder:text-zinc-400"
                />
                <div className="flex items-center justify-between border-t border-zinc-200 pt-2">
                  <p className="px-2 text-xs text-zinc-500">Shift + Enter for newline</p>
                  <button
                    className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
                    disabled={!canSend}
                    onClick={() => void onSend()}
                    type="button"
                  >
                    {loading ? "Thinking..." : "Send"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
