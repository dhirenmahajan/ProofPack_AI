"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Claim } from "@/lib/types";

const INCIDENT_TYPES = ["flood", "hurricane", "hail", "fire", "storm", "other"];

export function ClaimSidebar({
  claims,
  selectedId,
  onSelect,
  onCreated,
}: {
  claims: Claim[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCreated: (claim: Claim) => void;
}) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [claimant, setClaimant] = useState("");
  const [incidentType, setIncidentType] = useState("flood");
  const [incidentDate, setIncidentDate] = useState("");
  const [location, setLocation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const claim = await api.createClaim({
        title: title.trim(),
        claimant_name: claimant.trim() || null,
        incident_type: incidentType,
        incident_date: incidentDate || null,
        location: location.trim() || null,
      });
      onCreated(claim);
      setOpen(false);
      setTitle("");
      setClaimant("");
      setIncidentDate("");
      setLocation("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create claim");
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="flex w-72 flex-col border-r border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Claims
        </h2>
        <button
          onClick={() => setOpen((v) => !v)}
          className="rounded-md bg-brand-500 px-2.5 py-1 text-sm font-medium text-white hover:bg-brand-600"
        >
          {open ? "Cancel" : "New"}
        </button>
      </div>

      {open && (
        <form onSubmit={submit} className="space-y-2 border-b border-slate-200 p-4">
          <input
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Claim title *"
            className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
          <input
            value={claimant}
            onChange={(e) => setClaimant(e.target.value)}
            placeholder="Claimant name"
            className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
          <select
            value={incidentType}
            onChange={(e) => setIncidentType(e.target.value)}
            className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          >
            {INCIDENT_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <input
            type="date"
            value={incidentDate}
            onChange={(e) => setIncidentDate(e.target.value)}
            className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
          <input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Location (address / city)"
            className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
          {error && <p className="text-xs text-red-600">{error}</p>}
          <button
            disabled={busy}
            className="w-full rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {busy ? "Creating…" : "Create claim"}
          </button>
        </form>
      )}

      <div className="flex-1 overflow-y-auto">
        {claims.length === 0 ? (
          <p className="p-4 text-sm text-slate-400">No claims yet.</p>
        ) : (
          <ul>
            {claims.map((c) => (
              <li key={c.id}>
                <button
                  onClick={() => onSelect(c.id)}
                  className={`block w-full border-b border-slate-100 px-4 py-3 text-left hover:bg-slate-50 ${
                    selectedId === c.id ? "bg-brand-50" : ""
                  }`}
                >
                  <span className="block truncate text-sm font-medium text-slate-800">
                    {c.title}
                  </span>
                  <span className="mt-0.5 block text-xs text-slate-500">
                    {c.incident_type ?? "—"} · {c.status}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
