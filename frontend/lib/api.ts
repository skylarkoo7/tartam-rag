import {
  ChatRequest,
  ChatResponse,
  ConvertMode,
  ConvertResponse,
  FiltersResponse,
  HealthResponse,
  MessageRecord,
  SessionRecord
} from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api";

async function handleJson<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`API ${resp.status}: ${body || resp.statusText}`);
  }
  return (await resp.json()) as T;
}

export async function fetchFilters(): Promise<FiltersResponse> {
  const resp = await fetch(`${API_BASE}/filters`, { cache: "no-store" });
  return handleJson<FiltersResponse>(resp);
}

export async function fetchHistory(sessionId: string): Promise<MessageRecord[]> {
  const resp = await fetch(`${API_BASE}/history/${encodeURIComponent(sessionId)}`, { cache: "no-store" });
  return handleJson<MessageRecord[]>(resp);
}

export async function fetchSessions(limit = 50): Promise<SessionRecord[]> {
  const resp = await fetch(`${API_BASE}/sessions?limit=${limit}`, { cache: "no-store" });
  return handleJson<SessionRecord[]>(resp);
}

export async function fetchHealth(): Promise<HealthResponse> {
  const resp = await fetch(`${API_BASE}/health`, { cache: "no-store" });
  return handleJson<HealthResponse>(resp);
}

export async function sendChat(payload: ChatRequest): Promise<ChatResponse> {
  const resp = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return handleJson<ChatResponse>(resp);
}

export async function convertAnswer(text: string, targetMode: ConvertMode): Promise<ConvertResponse> {
  const resp = await fetch(`${API_BASE}/convert`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text,
      target_mode: targetMode
    })
  });
  return handleJson<ConvertResponse>(resp);
}

export async function triggerIngest(): Promise<{
  files_processed: number;
  chunks_created: number;
  failed_files: number;
  ocr_pages: number;
  notes: string[];
}> {
  const resp = await fetch(`${API_BASE}/ingest`, { method: "POST" });
  return handleJson(resp);
}
