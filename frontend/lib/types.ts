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
