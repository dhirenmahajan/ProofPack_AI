"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { QAResponse } from "@/lib/types";

const SUGGESTIONS = [
  "Does this policy cover flood damage?",
  "What is the deductible?",
  "What is the total of the contractor invoice?",
  "What documentation is required to file the claim?",
];

export function QAPanel({ claimId }: { claimId: string }) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<QAResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask(q: string) {
    const query = q.trim();
    if (!query) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await api.ask(claimId, query));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <h3 className="mb-3 text-sm font-semibold text-slate-700">
        Ask the claim evidence
      </h3>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
        }}
        className="flex gap-2"
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about the uploaded evidence…"
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <button
          disabled={busy}
          className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {busy ? "Thinking…" : "Ask"}
        </button>
      </form>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => {
              setQuestion(s);
              ask(s);
            }}
            className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-200"
          >
            {s}
          </button>
        ))}
      </div>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      {result && (
        <div className="mt-5">
          <div className="rounded-lg bg-slate-50 p-4">
            <div className="mb-1 flex items-center gap-2 text-xs text-slate-500">
              <span className="rounded bg-slate-200 px-1.5 py-0.5 font-medium">
                {result.provider}
              </span>
              <span>{result.latency_ms} ms</span>
            </div>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">
              {result.answer}
            </p>
          </div>

          <h4 className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Citations ({result.citations.length})
          </h4>
          <ul className="space-y-2">
            {result.citations.map((c) => (
              <li
                key={`${c.index}-${c.chunk_id}`}
                className="rounded-lg border border-slate-200 p-3"
              >
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="font-semibold text-brand-600">
                    [{c.index}] {c.filename}
                    {c.page_number != null ? ` · p.${c.page_number}` : ""}
                  </span>
                  <span className="text-slate-400">
                    {c.source_type} · score {c.score.toFixed(3)}
                  </span>
                </div>
                <p className="text-sm text-slate-600">{c.snippet}…</p>
              </li>
            ))}
            {result.citations.length === 0 && (
              <li className="text-xs text-slate-400">
                No citations — answer was not grounded in retrieved evidence.
              </li>
            )}
          </ul>
        </div>
      )}
    </section>
  );
}
