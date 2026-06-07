export interface Claim {
  id: string;
  title: string;
  claimant_name?: string | null;
  incident_type?: string | null;
  incident_date?: string | null;
  location?: string | null;
  status: string;
  created_at: string;
}

export interface ClaimDocument {
  id: string;
  claim_id: string;
  filename: string;
  content_type?: string | null;
  source_type: string;
  page_count?: number | null;
  ocr_confidence?: number | null;
  status: string;
  created_at: string;
}

export interface UploadResponse {
  document: ClaimDocument;
  chunks_created: number;
}

export interface Citation {
  index: number;
  chunk_id: string;
  document_id: string;
  filename: string;
  source_type: string;
  page_number?: number | null;
  snippet: string;
  score: number;
}

export interface QAResponse {
  question: string;
  answer: string;
  provider: string;
  citations: Citation[];
  latency_ms: number;
}

export interface ProviderStatus {
  llm: string;
  embeddings: string;
  ocr: string;
}

export interface ClaimPacket {
  id: string;
  claim_id: string;
  agent_run_id?: string | null;
  markdown: string;
  confidence?: number | null;
  needs_review: boolean;
  status: string;
  citations: unknown[];
  gaps: { source_type: string; description: string; status: string }[];
  verification?: {
    verified?: boolean;
    summary?: string;
    [k: string]: unknown;
  } | null;
  has_pdf: boolean;
  created_at: string;
}

export interface AgentRun {
  id: string;
  claim_id: string;
  workflow: string;
  status: string;
  error?: string | null;
  latency_ms?: number | null;
  created_at: string;
  packet?: ClaimPacket | null;
}

export const SOURCE_TYPES = [
  "policy",
  "invoice",
  "receipt",
  "photo",
  "inspection",
  "permit",
  "voicenote",
  "other",
] as const;
