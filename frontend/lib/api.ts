import type {
  AgentRun,
  Claim,
  ClaimDocument,
  ClaimPacket,
  ProviderStatus,
  QAResponse,
  UploadResponse,
} from "./types";

const BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export const api = {
  async providers(): Promise<ProviderStatus> {
    return handle(await fetch(`${BASE}/providers`, { cache: "no-store" }));
  },

  async listClaims(): Promise<Claim[]> {
    return handle(await fetch(`${BASE}/claims`, { cache: "no-store" }));
  },

  async createClaim(payload: Partial<Claim>): Promise<Claim> {
    return handle(
      await fetch(`${BASE}/claims`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }),
    );
  },

  async listDocuments(claimId: string): Promise<ClaimDocument[]> {
    return handle(
      await fetch(`${BASE}/claims/${claimId}/documents`, { cache: "no-store" }),
    );
  },

  async uploadDocument(
    claimId: string,
    file: File,
    sourceType: string,
  ): Promise<UploadResponse> {
    const form = new FormData();
    form.append("file", file);
    form.append("source_type", sourceType);
    return handle(
      await fetch(`${BASE}/claims/${claimId}/documents`, {
        method: "POST",
        body: form,
      }),
    );
  },

  async ask(
    claimId: string,
    question: string,
    topK = 5,
  ): Promise<QAResponse> {
    return handle(
      await fetch(`${BASE}/claims/${claimId}/qa`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, top_k: topK }),
      }),
    );
  },

  async generatePacket(claimId: string): Promise<AgentRun> {
    return handle(
      await fetch(`${BASE}/claims/${claimId}/packet`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ regenerate: true }),
      }),
    );
  },

  async getRun(claimId: string, runId: string): Promise<AgentRun> {
    return handle(
      await fetch(`${BASE}/claims/${claimId}/packet/runs/${runId}`, {
        cache: "no-store",
      }),
    );
  },

  async latestPacket(claimId: string): Promise<ClaimPacket | null> {
    const res = await fetch(`${BASE}/claims/${claimId}/packet/latest`, {
      cache: "no-store",
    });
    if (res.status === 404) return null;
    return handle(res);
  },

  async reviewPacket(
    claimId: string,
    packetId: string,
    approve: boolean,
    markdown?: string,
  ): Promise<ClaimPacket> {
    return handle(
      await fetch(`${BASE}/claims/${claimId}/packet/${packetId}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approve, markdown }),
      }),
    );
  },

  packetPdfUrl(claimId: string, packetId: string): string {
    return `${BASE}/claims/${claimId}/packet/${packetId}/pdf`;
  },
};
