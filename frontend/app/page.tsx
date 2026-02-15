"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { FilterBar } from "../components/FilterBar";
import { MessageBubble } from "../components/MessageBubble";
import { fetchFilters, fetchHistory, fetchSessions, sendChat, triggerIngest } from "../lib/api";
import { ChatMessage, Citation, MessageRecord, SessionRecord, StyleMode } from "../lib/types";

function createSessionId() {
  return `session_${Math.random().toString(36).slice(2)}_${Date.now()}`;
}

const SESSION_KEY = "tartam_session_id";

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

function fallbackSession(sessionId: string): SessionRecord {
  return {
    session_id: sessionId,
    title: "New chat",
    preview: "",
    last_message_at: new Date().toISOString(),
    message_count: 0
  };
}

function withCurrentSession(rows: SessionRecord[], current: string): SessionRecord[] {
  if (!current) {
    return rows;
  }
  if (rows.some((row) => row.session_id === current)) {
    return rows;
  }
  return [fallbackSession(current), ...rows];
}

function shortText(value: string, max = 56): string {
  const clean = value.trim();
  if (!clean) {
    return "";
  }
  return clean.length > max ? `${clean.slice(0, max)}...` : clean;
}

export default function HomePage() {
  const [sessionId, setSessionId] = useState("");
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
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

  async function reloadSessions(current: string) {
    try {
      const rows = await fetchSessions(50);
      setSessions(withCurrentSession(rows, current));
    } catch {
      setSessions((prev) => withCurrentSession(prev, current));
    }
  }

  useEffect(() => {
    let current = window.localStorage.getItem(SESSION_KEY);
    if (!current) {
      current = createSessionId();
      window.localStorage.setItem(SESSION_KEY, current);
    }
    setSessionId(current);

    Promise.all([fetchFilters(), fetchHistory(current), fetchSessions(50)])
      .then(([filterPayload, history, sessionRows]) => {
        setGranths(filterPayload.granths);
        setPrakrans(filterPayload.prakrans);
        setMessages(history.map(mapHistoryRow));
        setSessions(withCurrentSession(sessionRows, current));
      })
      .catch((err) => {
        setSessions(withCurrentSession([], current));
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
      await reloadSessions(sessionId);
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
    window.localStorage.setItem(SESSION_KEY, nextSessionId);
    setSessions((prev) => withCurrentSession(prev, nextSessionId));

    setBootLoading(true);
    setError(null);
    try {
      const history = await fetchHistory(nextSessionId);
      setMessages(history.map(mapHistoryRow));
      await reloadSessions(nextSessionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load session history");
    } finally {
      setBootLoading(false);
    }
  }

  async function createNewSession() {
    const next = createSessionId();
    setSessions((prev) => withCurrentSession(prev, next));
    setMessages([]);
    setSessionId(next);
    window.localStorage.setItem(SESSION_KEY, next);
    setBootLoading(false);
    setError(null);
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
    <main className="h-screen bg-[#f8f1e2] text-[#4a2e1d]">
      <div className="mx-auto flex h-full max-w-[1400px]">
        <aside className="hidden w-72 flex-col border-r border-[#d7b089] bg-[#ead9c0] p-4 md:flex">
          <h1 className="text-lg font-semibold tracking-tight">Tartam RAG</h1>
          <p className="mt-1 text-xs text-[#8b5f3c]">Scripture-grounded multilingual assistant</p>

          <div className="mt-4 flex flex-col gap-2">
            <button
              className="rounded-lg bg-[#c66a2e] px-3 py-2 text-sm font-medium text-[#fff7ef] hover:bg-[#b75f28]"
              onClick={() => void createNewSession()}
              type="button"
            >
              + New chat
            </button>
            <button
              className="rounded-lg border border-[#c89b6d] bg-[#fff8ee] px-3 py-2 text-sm font-medium text-[#6e4528] hover:bg-[#f7ebdb] disabled:opacity-50"
              onClick={onIngest}
              disabled={ingesting}
              type="button"
            >
              {ingesting ? "Indexing..." : "Re-index corpus"}
            </button>
          </div>

          <div className="mt-5 text-xs font-semibold uppercase tracking-wide text-[#8b5f3c]">Recent Sessions</div>
          <div className="mt-2 flex-1 space-y-1 overflow-y-auto pr-1">
            {sessions.map((item) => (
              <button
                key={item.session_id}
                className={`w-full rounded-lg px-3 py-2 text-left text-xs transition ${
                  item.session_id === sessionId
                    ? "bg-[#9f5729] text-[#fff7ef]"
                    : "bg-[#fff6ea] text-[#6e4528] hover:bg-[#f3e1cb]"
                }`}
                onClick={() => void openSession(item.session_id)}
                type="button"
              >
                <div className="font-medium">{shortText(item.title || "New chat", 42)}</div>
                <div className="mt-1 truncate text-[11px] opacity-80">
                  {shortText(item.preview || item.session_id, 52)}
                </div>
              </button>
            ))}
          </div>
        </aside>

        <section className="flex min-w-0 flex-1 flex-col">
          <header className="border-b border-[#d9b48b] bg-[#fff7eb]/90 px-4 py-3 backdrop-blur md:px-6">
            <div className="mx-auto flex w-full max-w-4xl items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold">Multilingual Tartam Chat</h2>
                <p className="text-xs text-[#8b5f3c]">Hindi · Gujarati · Hinglish · Gujarati Roman</p>
              </div>
              <button
                className="rounded-lg border border-[#c89b6d] bg-[#fff8ee] px-3 py-1.5 text-xs font-medium text-[#6e4528] md:hidden"
                onClick={() => void createNewSession()}
                type="button"
              >
                New chat
              </button>
            </div>
          </header>

          <div className="border-b border-[#d9b48b] bg-[#fff8ee] px-4 py-3 md:px-6">
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
                <div className="rounded-xl border border-[#d8b68f] bg-[#fff7ed] p-4 text-sm text-[#7e583a]">Loading chat...</div>
              ) : null}

              {error ? (
                <div className="rounded-xl border border-[#cc7a3a] bg-[#fff0de] p-3 text-sm text-[#8a3f1d]">{error}</div>
              ) : null}

              {!bootLoading && messages.length === 0 ? (
                <div className="rounded-xl border border-[#d8b68f] bg-[#fff7ed] p-5 text-sm text-[#7e583a]">
                  Ask anything from the corpus. Example: <em>mohajal kya hai</em> or <em>kem cho</em>.
                </div>
              ) : null}

              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              <div ref={scrollRef} />
            </div>
          </div>

          <div className="border-t border-[#d9b48b] bg-[#fff7eb] px-4 py-4 md:px-6">
            <div className="mx-auto w-full max-w-4xl">
              <div className="rounded-2xl border border-[#cfa577] bg-[#fff8ee] p-2">
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
                  className="w-full resize-none border-0 bg-transparent px-2 py-1 text-[15px] text-[#4a2e1d] outline-none placeholder:text-[#aa7a56]"
                />
                <div className="flex items-center justify-between border-t border-[#e0c3a2] pt-2">
                  <p className="px-2 text-xs text-[#8b5f3c]">Shift + Enter for newline</p>
                  <button
                    className="rounded-lg bg-[#c66a2e] px-4 py-2 text-sm font-medium text-[#fff7ef] hover:bg-[#b75f28] disabled:opacity-50"
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
