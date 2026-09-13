export interface DocumentItem {
  doc_id: string;
  company_name: string;
  fiscal_year: string;
  reporting_period_type: string;
  num_pages: number;
  narrative_chunks: number;
  table_chunks: number;
  table_chunks_flagged: number;
}

export interface DeleteDocumentResponse {
  deleted: boolean;
  doc_id: string;
  chunks_removed: number;
}

export interface UploadResponse {
  job_id: string;
  status: string;
}

export interface DocumentStatusResponse {
  job_id: string;
  status: "queued" | "processing" | "done" | "failed";
  doc_id?: string | null;
  company_name?: string | null;
  fiscal_year?: string | null;
  error?: string | null;
  progress_message?: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded" | "unhealthy";
  qdrant_connected: boolean;
  collection: string;
  points_count: number;
  active_generation_model: string;
  showcase_mode?: boolean;
  detail?: string | null;
}

export interface Citation {
  marker: string;
  chunk_id: string;
  doc_id: string;
  source_filename: string;
  company_name?: string | null;
  fiscal_year?: string | null;
  page_start: number;
  page_end: number;
  excerpt: string;
  table_id?: string | null;
  risk_flag?: boolean;
  risk_reasons?: string[];
}

export interface VerificationResult {
  status: "verified" | "verified_low_confidence" | "unverified" | "not_applicable";
  reason: string;
}

export interface PerEntityResult {
  entity: {
    company_name?: string | null;
    fiscal_year?: string | null;
  };
  intent: string;
  answer: string;
  verification_status: "verified" | "verified_low_confidence" | "unverified" | "not_applicable";
  verification_reason: string;
  citations: Citation[];
  numbers_extracted?: string[];
  risk_flag?: boolean;
  risk_reasons?: string[];
}

export interface EntityDeltaDetail {
  entity: {
    company_name?: string | null;
    fiscal_year?: string | null;
  };
  raw_value: string;
  parsed_numeric: number;
}

export interface DeltaComparison {
  entity_a: EntityDeltaDetail;
  entity_b: EntityDeltaDetail;
  absolute_delta: number;
  percentage_delta: number;
  direction: "increase" | "decrease" | "flat" | "divergent";
}

export interface AskResponse {
  query: string;
  intent: "narrative" | "numeric";
  answer: string;
  citations: Citation[];
  verification: VerificationResult;
  no_context_found: boolean;
  comparison: boolean;
  entities_compared?: Array<{
    company_name?: string | null;
    fiscal_year?: string | null;
  }>;
  per_entity_results?: PerEntityResult[];
  deltas?: DeltaComparison | null;
}

export interface ChatMessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  responsePayload?: AskResponse;
  isError?: boolean;
  errorMessage?: string;
}
