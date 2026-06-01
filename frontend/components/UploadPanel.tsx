"use client";

import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { SOURCE_TYPES, type ClaimDocument } from "@/lib/types";

export function UploadPanel({
  claimId,
  documents,
  onChanged,
}: {
  claimId: string;
  documents: ClaimDocument[];
  onChanged: () => void;
}) {
  const [sourceType, setSourceType] = useState<string>("policy");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function uploadFiles(files: FileList | File[]) {
    setBusy(true);
    setError(null);
    try {
      for (const file of Array.from(files)) {
        await api.uploadDocument(claimId, file, sourceType);
      }
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">Evidence</h3>
        <select
          value={sourceType}
          onChange={(e) => setSourceType(e.target.value)}
          className="rounded-md border border-slate-300 px-2 py-1 text-sm"
        >
          {SOURCE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-4 py-8 text-center transition ${
          dragOver
            ? "border-brand-500 bg-brand-50"
            : "border-slate-300 hover:border-brand-400"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => e.target.files && uploadFiles(e.target.files)}
        />
        <p className="text-sm text-slate-600">
          {busy ? "Uploading & ingesting…" : "Drop files or click to upload"}
        </p>
        <p className="mt-1 text-xs text-slate-400">
          PDFs & text are parsed now · images/audio via hosted OCR when keys are set
        </p>
      </div>

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}

      <ul className="mt-4 space-y-2">
        {documents.map((d) => (
          <li
            key={d.id}
            className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-2 text-sm"
          >
            <div className="min-w-0">
              <span className="block truncate font-medium text-slate-800">
                {d.filename}
              </span>
              <span className="text-xs text-slate-500">
                {d.source_type} · {d.page_count ?? 0} pages · OCR{" "}
                {d.ocr_confidence != null
                  ? `${Math.round(d.ocr_confidence * 100)}%`
                  : "—"}
              </span>
            </div>
            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700">
              {d.status}
            </span>
          </li>
        ))}
        {documents.length === 0 && (
          <li className="text-xs text-slate-400">No documents uploaded yet.</li>
        )}
      </ul>
    </section>
  );
}
