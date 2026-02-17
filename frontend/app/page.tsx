"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";

import { FilterBar } from "../components/FilterBar";
import { MessageBubble } from "../components/MessageBubble";
import {
  API_BASE,
  createThread,
  fetchFilters,
  fetchHealth,
  fetchHistory,
  fetchSessionCosts,
  fetchThreads,
  sendChat,
  triggerIngest
} from "../lib/api";
import { ChatMessage, Citation, HealthResponse, MessageRecord, SessionCostResponse, SessionRecord, StyleMode } from "../lib/types";
import { scriptClassName } from "../lib/text";

const PdfSourceViewer = dynamic(
  () => import("../components/PdfSourceViewer").then((mod) => mod.PdfSourceViewer),
  { ssr: false }
);

const THREAD_KEY = "tartam_thread_id";

function mapHistoryRow(row: MessageRecord): ChatMessage {
  let citations: Citation[] = [];
  let costSummary: ChatMessage["costSummary"] = null;
  if (row.citations_json) {
    try {
      citations = JSON.parse(row.citations_json) as Citation[];
    } catch {
      citations = [];
    }
  }
  if (row.cost_json) {
    try {
      costSummary = JSON.parse(row.cost_json);
    } catch {
      costSummary = null;
    }
  }

  return {
    id: row.message_id,
    role: row.role,
    text: row.text,
    styleTag: row.style_tag,
    citations,
    costSummary,
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

function pickPreferredThreadId(stored: string | null, rows: SessionRecord[]): string | null {
  if (stored && rows.some((row) => row.session_id === stored)) {
    return stored;
  }
  if (rows.length > 0) {
    return rows[0].session_id;
  }
  return null;
}

function shortText(value: string, max = 56): string {
  const clean = value.trim();
  if (!clean) {
    return "";
  }
  return clean.length > max ? `${clean.slice(0, max)}...` : clean;
}

function pickLatestCitation(rows: ChatMessage[]): Citation | null {
  for (let idx = rows.length - 1; idx >= 0; idx -= 1) {
    const message = rows[idx];
    if (message.role === "assistant" && message.citations.length > 0) {
      return message.citations[0];
    }
  }
  return null;
}

export default function HomePage() {
  const [sessionId, setSessionId] = useState("");
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [sessionCosts, setSessionCosts] = useState<SessionCostResponse | null>(null);
  const [threadSearch, setThreadSearch] = useState("");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [sourceCollapsed, setSourceCollapsed] = useState(false);
  const [sourceWidth, setSourceWidth] = useState(38);
  const [mobileSourceOpen, setMobileSourceOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [bootLoading, setBootLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [styleMode, setStyleMode] = useState<StyleMode>("auto");
  const [granth, setGranth] = useState("");
  const [prakran, setPrakran] = useState("");
  const [granths, setGranths] = useState<string[]>([]);
  const [prakrans, setPrakrans] = useState<string[]>([]);
  const [ingesting, setIngesting] = useState(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);

  const scrollRef = useRef<HTMLDivElement | null>(null);

  async function reloadSessionCosts(targetSessionId: string) {
    if (!targetSessionId) {
      setSessionCosts(null);
      return;
    }
    try {
      const payload = await fetchSessionCosts(targetSessionId);
      setSessionCosts(payload);
    } catch {
      setSessionCosts(null);
    }
  }

  async function reloadSessions(current: string) {
    try {
      const rows = await fetchThreads(50);
      setSessions(withCurrentSession(rows, current));
    } catch {
      setSessions((prev) => withCurrentSession(prev, current));
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      try {
        const [filterPayload, threadRows, healthPayload] = await Promise.all([
          fetchFilters(),
          fetchThreads(50),
          fetchHealth()
        ]);
        if (cancelled) {
          return;
        }
        setGranths(filterPayload.granths);
        setPrakrans(filterPayload.prakrans);
        setHealth(healthPayload);

        const stored = window.localStorage.getItem(THREAD_KEY);
        let current = pickPreferredThreadId(stored, threadRows);
        let rows = threadRows;

        if (!current) {
          const created = await createThread("New chat");
          current = created.session_id;
          rows = withCurrentSession(rows, current);
        }
        if (cancelled || !current) {
          return;
        }

        window.localStorage.setItem(THREAD_KEY, current);
        setSessionId(current);
        setSessions(withCurrentSession(rows, current));

        const history = await fetchHistory(current);
        if (cancelled) {
          return;
        }
        const mapped = history.map(mapHistoryRow);
        setMessages(mapped);
        setActiveCitation(pickLatestCitation(mapped));
        await reloadSessionCosts(current);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load initial data");
        }
      } finally {
        if (!cancelled) {
          setBootLoading(false);
        }
      }
    }

    void boot();
    return () => {
      cancelled = true;
    };
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
        costSummary: response.cost_summary ?? null,
        createdAt: new Date().toISOString()
      };
      setMessages((prev) => [...prev, assistant]);
      setActiveCitation(response.citations?.[0] ?? null);
      await reloadSessions(sessionId);
      await reloadSessionCosts(sessionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat request failed");
    } finally {
      setLoading(false);
      try {
        const latestHealth = await fetchHealth();
        setHealth(latestHealth);
      } catch {
        // no-op
      }
    }
  }

  async function openSession(nextSessionId: string) {
    if (!nextSessionId) {
      return;
    }
    setSessionId(nextSessionId);
    window.localStorage.setItem(THREAD_KEY, nextSessionId);
    setSessions((prev) => withCurrentSession(prev, nextSessionId));

    setBootLoading(true);
    setError(null);
    try {
      const history = await fetchHistory(nextSessionId);
      const mapped = history.map(mapHistoryRow);
      setMessages(mapped);
      setActiveCitation(pickLatestCitation(mapped));
      await reloadSessions(nextSessionId);
      await reloadSessionCosts(nextSessionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load session history");
    } finally {
      setBootLoading(false);
    }
  }

  async function createNewSession() {
    setError(null);
    try {
      const created = await createThread("New chat");
      const next = created.session_id;
      setSessions((prev) => withCurrentSession(prev, next));
      setMessages([]);
      setActiveCitation(null);
      setSessionId(next);
      setSessionCosts(null);
      window.localStorage.setItem(THREAD_KEY, next);
      setBootLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create new thread");
    }
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

  function exportSessionCostJson() {
    if (!sessionCosts) {
      return;
    }
    const blob = new Blob([JSON.stringify(sessionCosts, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `session_costs_${sessionCosts.session_id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  const pdfSrc = useMemo(() => {
    if (!activeCitation) {
      return "";
    }
    const query = (activeCitation.chopai_lines?.[0] || "").trim();
    const search = query ? `&search=${encodeURIComponent(query.slice(0, 80))}` : "";
    return `${API_BASE}/pdf/${encodeURIComponent(activeCitation.citation_id)}#page=${activeCitation.page_number}&zoom=page-width${search}`;
  }, [activeCitation]);

  const pdfFileUrl = useMemo(() => {
    if (!activeCitation) {
      return "";
    }
    return `${API_BASE}/pdf/${encodeURIComponent(activeCitation.citation_id)}`;
  }, [activeCitation]);

  const llmReady = Boolean(health?.llm_enabled && !health?.llm_generation_error);
  const activeChopaiPreview = useMemo(
    () => ((activeCitation?.chopai_lines || []).join(" ").trim()),
    [activeCitation]
  );
  const visibleSessions = useMemo(() => {
    const needle = threadSearch.trim().toLowerCase();
    if (!needle) {
      return sessions;
    }
    return sessions.filter((item) => {
      const title = (item.title || "").toLowerCase();
      const preview = (item.preview || "").toLowerCase();
      return title.includes(needle) || preview.includes(needle) || item.session_id.toLowerCase().includes(needle);
    });
  }, [sessions, threadSearch]);
  const sourcePanelWidth = Math.max(32, Math.min(52, sourceWidth));

  return (
    <main className="h-screen bg-[#f6f1ea] text-[#2f241c]">
      <div className="mx-auto flex h-full max-w-[1780px]">
        <aside className="hidden w-80 flex-col border-r border-[#e5d6c8] bg-[#f3e7d8] p-4 md:flex">
          <h1 className="text-lg font-semibold tracking-tight">Tartam AI</h1>
          <p className="mt-1 text-xs text-[#7f5e43]">Grounded scripture chat</p>

          <div className="mt-4 flex flex-col gap-2">
            <button
              className="rounded-xl bg-[#b9632a] px-3 py-2 text-sm font-medium text-white hover:bg-[#a95622]"
              onClick={() => void createNewSession()}
              type="button"
            >
              + New chat
            </button>
            <button
              className="rounded-xl border border-[#d7b89a] bg-[#fff9f2] px-3 py-2 text-sm font-medium text-[#6a4529] hover:bg-[#fff2e2] disabled:opacity-50"
              onClick={onIngest}
              disabled={ingesting}
              type="button"
            >
              {ingesting ? "Re-indexing..." : "Re-index corpus"}
            </button>
          </div>

          <div className="mt-4 rounded-xl border border-[#e6d2bf] bg-[#fff8ef] p-3 text-xs text-[#6d4b31]">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-[#8c6749]">Session Cost</p>
            <p className="mt-1 text-sm font-semibold text-[#5a3a22]">
              ₹{(sessionCosts?.total_inr ?? 0).toFixed(2)} <span className="text-xs text-[#8b6547]">(${(sessionCosts?.total_usd ?? 0).toFixed(4)})</span>
            </p>
            <p className="mt-1 text-[11px] text-[#8b6547]">
              Turns: {sessionCosts?.turns ?? 0} · FX: {sessionCosts?.fx_rate ? sessionCosts.fx_rate.toFixed(2) : "--"} ({sessionCosts?.fx_source || "n/a"})
            </p>
            {sessionCosts && Object.keys(sessionCosts.by_model || {}).length > 0 ? (
              <details className="mt-2 rounded-lg border border-[#ebd4be] bg-white px-2 py-1">
                <summary className="cursor-pointer text-[11px] font-semibold text-[#6a4529]">Model breakdown</summary>
                <div className="mt-1 space-y-1">
                  {Object.entries(sessionCosts.by_model).map(([model, row]) => (
                    <p key={model} className="text-[11px] text-[#7b5a40]">
                      {model}: ₹{row.inr.toFixed(4)} (${row.usd.toFixed(6)}) · {row.calls} calls
                    </p>
                  ))}
                </div>
              </details>
            ) : null}
            <button
              type="button"
              onClick={exportSessionCostJson}
              className="mt-2 rounded-md border border-[#dabc9f] bg-white px-2 py-1 text-[11px] font-medium text-[#6a4529] disabled:opacity-50"
              disabled={!sessionCosts}
            >
              Export cost JSON
            </button>
          </div>

          <div className="mt-5 text-xs font-semibold uppercase tracking-wide text-[#8c6749]">Recent Threads</div>
          <input
            value={threadSearch}
            onChange={(event) => setThreadSearch(event.target.value)}
            placeholder="Search threads"
            className="mt-2 rounded-lg border border-[#ddc4ad] bg-[#fffaf5] px-3 py-2 text-xs text-[#5f3e27] outline-none focus:border-[#cb8854]"
          />
          <div className="mt-2 flex-1 space-y-2 overflow-y-auto pr-1">
            {visibleSessions.map((item) => (
              <button
                key={item.session_id}
                className={`w-full rounded-xl px-3 py-2.5 text-left text-xs transition ${
                  item.session_id === sessionId
                    ? "bg-[#a95e2d] text-[#fff6ed]"
                    : "border border-[#eadac9] bg-[#fffaf5] text-[#6a4529] hover:bg-[#fff0e1]"
                }`}
                onClick={() => void openSession(item.session_id)}
                type="button"
              >
                <div className="font-semibold leading-5">{shortText(item.title || "New chat", 46)}</div>
                <div className="mt-1 truncate text-[11px] opacity-85">{shortText(item.preview || "", 60)}</div>
              </button>
            ))}
            {visibleSessions.length === 0 ? <p className="px-1 text-xs text-[#8f6d51]">No matching threads.</p> : null}
          </div>
        </aside>

        <section className="flex min-w-0 flex-1 flex-col">
          <header className="border-b border-[#e5d7ca] bg-[#fffdf9] px-4 py-3 md:px-6">
            <div className="mx-auto flex w-full max-w-4xl items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div>
                  <h2 className="text-base font-semibold">Ask by Granth, Prakran, Chopai</h2>
                  <p className="text-xs text-[#806047]">Hindi · Gujarati · Hinglish · Gujarati Roman</p>
                </div>
                <span
                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                    llmReady
                      ? "border border-[#b8dcb9] bg-[#eefaf0] text-[#2f6d35]"
                      : "border border-[#e8c6a6] bg-[#fff6eb] text-[#8a4f24]"
                  }`}
                  title={health?.llm_generation_error || ""}
                >
                  {llmReady ? `${(health?.llm_provider || "llm").toUpperCase()} live` : "LLM check needed"}
                </span>
                <span className="hidden rounded-full border border-[#e6d1bd] bg-[#fff6ea] px-2.5 py-1 text-[11px] text-[#7e5b3f] md:inline-block">
                  {health?.indexed_chunks ?? 0} chunks
                </span>
              </div>
              <button
                className="rounded-lg border border-[#d8b99c] bg-[#fff8ef] px-3 py-1.5 text-xs font-medium text-[#6c472a] md:hidden"
                onClick={() => void createNewSession()}
                type="button"
              >
                New chat
              </button>
              <button
                className="rounded-lg border border-[#d8b99c] bg-[#fff8ef] px-3 py-1.5 text-xs font-medium text-[#6c472a] lg:hidden"
                onClick={() => setMobileSourceOpen((prev) => !prev)}
                type="button"
              >
                {mobileSourceOpen ? "Hide source" : "Show source"}
              </button>
            </div>
          </header>

          <div className="border-b border-[#eadccf] bg-[#fffaf3] px-4 py-3 md:px-6">
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

          <div className="flex-1 overflow-y-auto px-4 py-6 md:px-6">
            <div className="mx-auto w-full max-w-4xl space-y-5">
              {bootLoading ? (
                <div className="rounded-2xl border border-[#ead5c0] bg-white p-4 text-sm text-[#7b5a43]">Loading chat...</div>
              ) : null}

              {error ? (
                <div className="rounded-2xl border border-[#e6a875] bg-[#fff2e5] p-3 text-sm text-[#8e3f18]">{error}</div>
              ) : null}

              {!bootLoading && messages.length === 0 ? (
                <div className="rounded-2xl border border-[#ead5c0] bg-white p-5 text-sm text-[#6f5039]">
                  Ask anything from corpus. Example: <em>singar granth prakran 14 to 19 summary</em>.
                </div>
              ) : null}

              {messages.map((message) => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  activeCitationId={activeCitation?.citation_id ?? null}
                  onCitationSelect={(citation) => {
                    setActiveCitation(citation);
                    setMobileSourceOpen(true);
                  }}
                />
              ))}
              <div ref={scrollRef} />
            </div>
          </div>

          <div className="border-t border-[#eadccf] bg-[#fffdf9] px-4 py-4 md:px-6">
            <div className="mx-auto w-full max-w-4xl">
              <div className="rounded-2xl border border-[#e6d4c4] bg-white p-2 shadow-[0_6px_24px_rgba(72,42,19,0.05)]">
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
                  placeholder="Ask with granth/prakran/chopai references..."
                  className="w-full resize-none border-0 bg-transparent px-2 py-1 text-[15px] text-[#3f2f22] outline-none placeholder:text-[#a18066]"
                />
                <div className="flex items-center justify-between border-t border-[#f1e3d7] pt-2">
                  <p className="px-2 text-xs text-[#8a674b]">Shift + Enter for newline</p>
                  <button
                    className="rounded-lg bg-[#bc682d] px-4 py-2 text-sm font-medium text-white hover:bg-[#a95a24] disabled:opacity-50"
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

        <aside
          className={`hidden min-w-[420px] max-w-[760px] flex-col border-l border-[#e5d6c8] bg-[#f9f5ef] transition-all duration-300 lg:flex ${
            sourceCollapsed ? "w-16" : ""
          }`}
          style={sourceCollapsed ? undefined : { width: `${sourcePanelWidth}%` }}
        >
          <div className="border-b border-[#e8d9cb] px-4 py-3">
            <div className="flex items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold text-[#5d3d24]">Source Viewer</h3>
                <p className="mt-1 text-xs text-[#856248]">Click citation cards to open exact source page.</p>
              </div>
              <button
                type="button"
                className="rounded-md border border-[#dabc9f] bg-[#fff8ef] px-2 py-1 text-[11px] font-medium text-[#6a4529]"
                onClick={() => setSourceCollapsed((prev) => !prev)}
              >
                {sourceCollapsed ? "Expand" : "Collapse"}
              </button>
            </div>
            {!sourceCollapsed ? (
              <div className="mt-2 flex items-center gap-2">
                <span className="text-[11px] text-[#8a674a]">Panel width</span>
                <input
                  type="range"
                  min={32}
                  max={52}
                  value={sourcePanelWidth}
                  onChange={(event) => setSourceWidth(Number(event.target.value))}
                  className="w-36 accent-[#bc682d]"
                />
              </div>
            ) : null}
            {!llmReady && health?.llm_generation_error ? (
              <p className="mt-1 text-[11px] text-[#9a4f22]">LLM: {health.llm_generation_error}</p>
            ) : null}
          </div>

          {!sourceCollapsed ? (
            activeCitation ? (
              <div className="flex h-full flex-col">
                <div className="space-y-2 border-b border-[#e8d9cb] px-4 py-3 text-xs text-[#6d4a30]">
                  <p className="text-sm font-semibold text-[#533620]">
                    {activeCitation.granth_name} · {activeCitation.prakran_name}
                  </p>
                  <p className="flex items-center gap-2">
                    {activeCitation.prakran_chopai_index ? `Prakran Chopai ${activeCitation.prakran_chopai_index} · ` : ""}
                    {activeCitation.chopai_number ? `Raw #${activeCitation.chopai_number} · ` : ""}
                    Page {activeCitation.page_number}
                  </p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="rounded-md border border-[#dabc9f] bg-[#fff8ef] px-2.5 py-1 text-[11px] font-medium text-[#6a4529] hover:bg-[#fff1e2]"
                      onClick={() => window.open(pdfSrc, "_blank", "noopener,noreferrer")}
                    >
                      Open PDF in new tab
                    </button>
                  </div>
                </div>

                <div className="h-[50%] border-b border-[#eadaca]">
                  <PdfSourceViewer
                    key={activeCitation.citation_id}
                    fileUrl={pdfFileUrl}
                    initialPage={activeCitation.page_number}
                    highlightText={(activeCitation.chopai_lines?.[0] || "").trim()}
                  />
                </div>

                <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3 text-sm text-[#4d321f]">
                  <section className="space-y-1">
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-[#855f45]">Matched Chopai</h4>
                    <div className="rounded-xl border border-[#ecd8c3] bg-white px-3 py-2">
                      {(activeCitation.chopai_lines || []).map((line, idx) => (
                        <p key={`${activeCitation.citation_id}_${idx}`} className={`leading-6 ${scriptClassName(line)}`}>
                          {line}
                        </p>
                      ))}
                    </div>
                  </section>

                  <section className="space-y-1">
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-[#855f45]">Meaning</h4>
                    <div className={`rounded-xl border border-[#ecd8c3] bg-white px-3 py-2 leading-6 ${scriptClassName(activeCitation.meaning_text)}`}>
                      {activeCitation.meaning_text}
                    </div>
                  </section>

                  <p className={`text-xs text-[#8a674a] break-all ${scriptClassName(activeChopaiPreview)}`}>Source: {activeCitation.pdf_path}</p>
                </div>
              </div>
            ) : (
              <div className="p-4 text-sm text-[#7b5a43]">No citation selected yet.</div>
            )
          ) : (
            <div className="p-2 text-[11px] text-[#8a674a]">Source hidden</div>
          )}
        </aside>
      </div>

      {mobileSourceOpen && activeCitation ? (
        <div className="fixed inset-x-0 bottom-0 z-40 max-h-[70vh] rounded-t-2xl border-t border-[#dfc6ad] bg-[#fff9f3] shadow-[0_-10px_30px_rgba(53,32,20,0.18)] lg:hidden">
          <div className="flex items-center justify-between border-b border-[#eadccf] px-4 py-2">
            <p className="text-xs font-semibold text-[#6d4a30]">
              {activeCitation.granth_name} · {activeCitation.prakran_name} · p.{activeCitation.page_number}
            </p>
            <button
              type="button"
              onClick={() => setMobileSourceOpen(false)}
              className="rounded-md border border-[#dabc9f] bg-[#fff8ef] px-2 py-1 text-[11px] text-[#6a4529]"
            >
              Close
            </button>
          </div>
          <div className="h-[60vh]">
            <PdfSourceViewer
              key={`${activeCitation.citation_id}_mobile`}
              fileUrl={pdfFileUrl}
              initialPage={activeCitation.page_number}
              highlightText={(activeCitation.chopai_lines?.[0] || "").trim()}
            />
          </div>
        </div>
      ) : null}
    </main>
  );
}
