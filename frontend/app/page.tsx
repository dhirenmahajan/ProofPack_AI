"use client";

import { useCallback, useEffect, useState } from "react";
import { ClaimSidebar } from "@/components/ClaimSidebar";
import { PacketPanel } from "@/components/PacketPanel";
import { ProviderBadge } from "@/components/ProviderBadge";
import { QAPanel } from "@/components/QAPanel";
import { UploadPanel } from "@/components/UploadPanel";
import { api } from "@/lib/api";
import type {
  Claim,
  ClaimDocument,
  ProviderStatus,
} from "@/lib/types";

export default function Home() {
  const [providers, setProviders] = useState<ProviderStatus | null>(null);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<ClaimDocument[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    api.providers().then(setProviders).catch(() => setProviders(null));
    api
      .listClaims()
      .then((cs) => {
        setClaims(cs);
        if (cs.length && !selectedId) setSelectedId(cs[0].id);
      })
      .catch((err) =>
        setLoadError(
          err instanceof Error ? err.message : "Cannot reach the API",
        ),
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refreshDocuments = useCallback(() => {
    if (!selectedId) return;
    api.listDocuments(selectedId).then(setDocuments).catch(() => {});
  }, [selectedId]);

  useEffect(() => {
    setDocuments([]);
    refreshDocuments();
  }, [selectedId, refreshDocuments]);

  // Async ingestion: while any document is still processing, poll for updates.
  useEffect(() => {
    const processing = documents.some((d) => d.status === "processing");
    if (!processing) return;
    const t = setInterval(refreshDocuments, 2000);
    return () => clearInterval(t);
  }, [documents, refreshDocuments]);

  const selectedClaim = claims.find((c) => c.id === selectedId) ?? null;

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
        <div>
          <h1 className="text-lg font-bold text-slate-900">ProofPack AI</h1>
          <p className="text-xs text-slate-500">
            Multimodal Disaster Claim Intelligence
          </p>
        </div>
        <ProviderBadge providers={providers} />
      </header>

      <div className="flex flex-1 overflow-hidden">
        <ClaimSidebar
          claims={claims}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onCreated={(claim) => {
            setClaims((prev) => [claim, ...prev]);
            setSelectedId(claim.id);
          }}
        />

        <main className="flex-1 overflow-y-auto p-6">
          {loadError && (
            <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              {loadError}. Make sure the backend is running at the configured API URL.
            </div>
          )}

          {!selectedClaim ? (
            <div className="flex h-full items-center justify-center text-center text-slate-400">
              <div>
                <p className="text-lg font-medium">No claim selected</p>
                <p className="text-sm">
                  Create a claim on the left to start assembling evidence.
                </p>
              </div>
            </div>
          ) : (
            <div className="mx-auto max-w-4xl space-y-6">
              <div className="rounded-xl border border-slate-200 bg-white p-5">
                <h2 className="text-xl font-bold text-slate-900">
                  {selectedClaim.title}
                </h2>
                <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-sm text-slate-600 sm:grid-cols-4">
                  <Field label="Claimant" value={selectedClaim.claimant_name} />
                  <Field label="Incident" value={selectedClaim.incident_type} />
                  <Field label="Date" value={selectedClaim.incident_date} />
                  <Field label="Location" value={selectedClaim.location} />
                </div>
              </div>

              <UploadPanel
                claimId={selectedClaim.id}
                documents={documents}
                onChanged={refreshDocuments}
              />

              <QAPanel claimId={selectedClaim.id} />

              <PacketPanel claimId={selectedClaim.id} />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <span className="block text-xs uppercase tracking-wide text-slate-400">
        {label}
      </span>
      <span className="text-slate-700">{value || "—"}</span>
    </div>
  );
}
