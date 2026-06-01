-- Enable pgvector for embedding similarity search.
CREATE EXTENSION IF NOT EXISTS vector;

-- Trigram + full-text helpers for hybrid (keyword) retrieval.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
