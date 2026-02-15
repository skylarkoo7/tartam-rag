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
  const [showSessions, setShowSessions] = useState(false);

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
      known = [current, ...known].slice(0, 20);
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
      setShowSessions(false);
    }
  }

  async function createNewSession() {
    const next = createSessionId();
    const updated = [next, ...sessions].slice(0, 20);
    setSessions(updated);
    window.localStorage.setItem("tartam_sessions", JSON.stringify(updated));
    await openSession(next);
    setMessages([]);
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

  if (bootLoading) {
    return (
      <main className="mx-auto max-w-6xl px-4 py-10">
        <div className="rounded-2xl bg-white/70 p-6 text-sm text-ink shadow-soft">Loading Tartam chatbot...</div>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-5 px-4 py-6">
      <header className="rounded-3xl border border-white/40 bg-white/70 p-5 shadow-soft backdrop-blur-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-ink">Tartam Multilingual RAG Chatbot</h1>
            <p className="mt-1 text-sm text-ink/70">
              Ask in Hindi, Gujarati, English, Hinglish, or Gujarati Roman. Responses stay grounded in indexed chopai.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              className="rounded-xl bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-ink/90"
              onClick={() => setShowSessions((prev) => !prev)}
              type="button"
            >
              Sessions
            </button>
            <button
              className="rounded-xl bg-vermilion px-4 py-2 text-sm font-semibold text-white transition hover:bg-vermilion/90"
              onClick={() => void createNewSession()}
              type="button"
            >
              New Session
            </button>
            <button
              className="rounded-xl bg-leaf px-4 py-2 text-sm font-semibold text-white transition hover:bg-leaf/90 disabled:opacity-60"
              onClick={onIngest}
              disabled={ingesting}
              type="button"
            >
              {ingesting ? "Indexing..." : "Run Ingestion"}
            </button>
          </div>
        </div>
      </header>

      {showSessions ? (
        <aside className="rounded-2xl border border-white/50 bg-white/70 p-3 shadow-soft backdrop-blur-sm">
          <p className="mb-2 text-sm font-semibold text-ink">Session History</p>
          <div className="max-h-48 space-y-2 overflow-y-auto">
            {sessions.map((item) => (
              <button
                key={item}
                className={`w-full rounded-lg px-3 py-2 text-left text-xs transition ${
                  item === sessionId ? "bg-saffron text-white" : "bg-sand text-ink hover:bg-sand/80"
                }`}
                onClick={() => void openSession(item)}
                type="button"
              >
                {item}
              </button>
            ))}
          </div>
        </aside>
      ) : null}

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

      {error ? (
        <div className="rounded-xl border border-vermilion/20 bg-vermilion/10 p-3 text-sm text-vermilion">{error}</div>
      ) : null}

      <section className="flex-1 rounded-3xl border border-white/50 bg-white/70 p-4 shadow-soft backdrop-blur-sm">
        <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-2">
          {messages.length === 0 ? (
            <div className="rounded-xl bg-sand p-4 text-sm text-ink/80">
              Start by indexing documents, then ask a question like: <em>kaise ho</em> or <em>kem cho</em>.
            </div>
          ) : null}

          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          <div ref={scrollRef} />
        </div>
      </section>

      <section className="rounded-3xl border border-white/50 bg-white/70 p-4 shadow-soft backdrop-blur-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-end">
          <label className="flex-1 text-sm text-ink/80">
            Ask your question
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
              placeholder="Ask about any chopai, prakran, or meaning..."
              className="mt-1 w-full resize-none rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm"
            />
          </label>

          <button
            className="h-11 rounded-xl bg-saffron px-5 text-sm font-semibold text-white transition hover:bg-saffron/90 disabled:opacity-50"
            disabled={!canSend}
            onClick={onSend}
            type="button"
          >
            {loading ? "Thinking..." : "Send"}
          </button>
        </div>
      </section>
    </main>
  );
}
