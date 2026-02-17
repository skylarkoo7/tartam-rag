export type StyleMode = "auto" | "hi" | "gu" | "en" | "hi_latn" | "gu_latn";
export type ConvertMode = "hi" | "gu" | "en" | "hi_latn" | "gu_latn" | "en_deva" | "en_gu";

export interface ChatFilters {
  granth?: string;
  prakran?: string;
}

export type UsageStage = "plan_query" | "query_embedding" | "generate_answer" | "summarize_memory" | "convert_answer" | "ocr_recovery";

export interface UsageLineItem {
  stage: UsageStage;
  provider: string;
  model: string;
  endpoint: string;
  input_tokens: number;
  cached_input_tokens: number;
  output_tokens: number;
  usd_cost: number;
  inr_cost: number;
  pricing_version: string;
  fx_rate: number;
}

export interface CostSummary {
  total_usd: number;
  total_inr: number;
  currency_local: "INR";
  fx_rate: number;
  fx_source: string;
  line_items: UsageLineItem[];
}

export interface Citation {
  citation_id: string;
  granth_name: string;
  prakran_name: string;
  chopai_number?: string | null;
  prakran_chopai_index?: number | null;
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
  cost_summary?: CostSummary | null;
  context_state?: {
    granth_name?: string | null;
    prakran_number?: number | null;
    prakran_range_start?: number | null;
    prakran_range_end?: number | null;
    chopai_number?: number | null;
  };
  available_conversions?: ConvertMode[];
  debug?: { retrieval_scores: number[] };
}

export interface ConvertRequest {
  text: string;
  target_mode: ConvertMode;
}

export interface ConvertResponse {
  text: string;
  target_mode: ConvertMode;
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
  cost_json?: string | null;
  created_at: string;
}

export interface SessionRecord {
  session_id: string;
  title: string;
  preview: string;
  last_message_at: string;
  message_count: number;
}

export interface ThreadCreateResponse {
  session_id: string;
}

export interface SessionCostResponse {
  session_id: string;
  turns: number;
  total_usd: number;
  total_inr: number;
  fx_rate: number;
  fx_source: string;
  by_model: Record<string, { usd: number; inr: number; calls: number }>;
  items: CostSummary[];
}

export interface HealthResponse {
  status: string;
  db_ready: boolean;
  vector_ready: boolean;
  indexed_chunks: number;
  llm_enabled: boolean;
  llm_provider?: string | null;
  llm_generation_error?: string | null;
  ocr_error?: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  styleTag: string;
  citations: Citation[];
  costSummary?: CostSummary | null;
  createdAt: string;
}
