export type StyleMode = "auto" | "hi" | "gu" | "en" | "hi_latn" | "gu_latn";

export interface ChatFilters {
  granth?: string;
  prakran?: string;
}

export interface Citation {
  citation_id: string;
  granth_name: string;
  prakran_name: string;
  chopai_lines: string[];
  meaning_text: string;
  page_number: number;
  pdf_path: string;
  score: number;
  prev_context?: string | null;
  next_context?: string | null;
}

export interface ChatRequest {
  session_id: string;
  message: string;
  style_mode: StyleMode;
  filters?: ChatFilters;
  top_k?: number;
}

export interface ChatResponse {
  answer: string;
  answer_style: StyleMode;
  not_found: boolean;
  follow_up_question?: string;
  citations: Citation[];
  debug?: { retrieval_scores: number[] };
}

export interface FiltersResponse {
  granths: string[];
  prakrans: string[];
}

export interface MessageRecord {
  message_id: string;
  session_id: string;
  role: "user" | "assistant";
  text: string;
  style_tag: string;
  citations_json: string | null;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  styleTag: string;
  citations: Citation[];
  createdAt: string;
}
