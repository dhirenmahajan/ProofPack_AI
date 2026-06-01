import type { ProviderStatus } from "@/lib/types";

export function ProviderBadge({ providers }: { providers: ProviderStatus | null }) {
  if (!providers) return null;
  const items: { label: string; value: string }[] = [
    { label: "LLM", value: providers.llm },
    { label: "Embeddings", value: providers.embeddings },
    { label: "OCR", value: providers.ocr },
  ];
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((it) => {
        const hosted = it.value !== "stub";
        return (
          <span
            key={it.label}
            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${
              hosted
                ? "bg-emerald-100 text-emerald-700"
                : "bg-amber-100 text-amber-700"
            }`}
            title={hosted ? "Hosted inference active" : "Running on stub provider"}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-current" />
            {it.label}: {it.value}
          </span>
        );
      })}
    </div>
  );
}
