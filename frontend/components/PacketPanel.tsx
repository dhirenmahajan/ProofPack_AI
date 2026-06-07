"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ClaimPacket } from "@/lib/types";

export function PacketPanel({ claimId }: { claimId: string }) {
  const [packet, setPacket] = useState<ClaimPacket | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadLatest = useCallback(() => {
    api
      .latestPacket(claimId)
      .then(setPacket)
      .catch(() => setPacket(null));
  }, [claimId]);

  useEffect(() => {
    setPacket(null);
    loadLatest();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [claimId, loadLatest]);

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      const run = await api.generatePacket(claimId);
      if (run.packet) {
        setPacket(run.packet);
        setBusy(false);
        return;
      }
      // Async: poll the run until it completes.
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const r = await api.getRun(claimId, run.id);
          if (r.status === "completed" && r.packet) {
            setPacket(r.packet);
            setBusy(false);
            if (pollRef.current) clearInterval(pollRef.current);
          } else if (r.status === "failed") {
            setError(r.error || "Packet generation failed");
            setBusy(false);
            if (pollRef.current) clearInterval(pollRef.current);
          }
        } catch {
          /* keep polling */
        }
      }, 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Packet generation failed");
      setBusy(false);
    }
  }

  async function approve() {
    if (!packet) return;
    const updated = await api.reviewPacket(claimId, packet.id, true);
    setPacket(updated);
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">Claim packet</h3>
        <button
          onClick={generate}
          disabled={busy}
          className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {busy ? "Generating…" : packet ? "Regenerate" : "Generate packet"}
        </button>
      </div>

      <p className="text-xs text-slate-400">
        Runs the agent workflow: intake → extraction → FEMA/NWS verification →
        coverage RAG → gap analysis → report → human review.
      </p>

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {packet && (
        <div className="mt-4 space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span
              className={`rounded-full px-2 py-0.5 font-medium ${
                packet.verification?.verified
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-amber-100 text-amber-700"
              }`}
            >
              {packet.verification?.verified ? "FEMA verified" : "Unverified"}
            </span>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">
              confidence {((packet.confidence ?? 0) * 100).toFixed(0)}%
            </span>
            <span
              className={`rounded-full px-2 py-0.5 ${
                packet.needs_review
                  ? "bg-amber-100 text-amber-700"
                  : "bg-emerald-100 text-emerald-700"
              }`}
            >
              {packet.status}
            </span>
            {packet.has_pdf && (
              <a
                href={api.packetPdfUrl(claimId, packet.id)}
                target="_blank"
                rel="noreferrer"
                className="rounded-full bg-brand-50 px-2 py-0.5 font-medium text-brand-700 hover:bg-brand-100"
              >
                Download PDF
              </a>
            )}
          </div>

          {packet.gaps.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              <p className="font-medium">Missing evidence:</p>
              <ul className="mt-1 list-disc pl-5">
                {packet.gaps.map((g) => (
                  <li key={g.source_type}>{g.description}</li>
                ))}
              </ul>
            </div>
          )}

          <pre className="max-h-96 overflow-y-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-4 text-xs leading-relaxed text-slate-800">
            {packet.markdown}
          </pre>

          {packet.needs_review && (
            <button
              onClick={approve}
              className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-sm font-medium text-emerald-700 hover:bg-emerald-100"
            >
              Approve packet (human review)
            </button>
          )}
        </div>
      )}
    </section>
  );
}
