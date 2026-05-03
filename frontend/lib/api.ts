export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type DocSummary = {
  id: number;
  title: string;
  updated_at: string;
  bytes: number;
};

export type RagFile = {
  name: string;
  size: number;
  modified_at: string;
  sha256: string;
};

export type AiResponse = {
  request_id: string;
  answer: string;
  replacement?: string;
  citations: Array<{ file: string; chunk_id: string; score: number; quote: string }>;
  metadata: {
    retrieval_ms: number;
    generation_ms: number;
    tokens_per_second: number;
    prompt_tokens_estimate: number;
    context_window: number;
  };
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listDocs: (user: string) => call<DocSummary[]>(`/users/${encodeURIComponent(user)}/documents`),
  getDoc: (user: string, id: number) => call<{ id: number; title: string; content: string }>(`/users/${encodeURIComponent(user)}/documents/${id}`),
  saveDoc: (user: string, id: number | null, title: string, content: string) =>
    call<{ id: number }>(`/users/${encodeURIComponent(user)}/documents${id && id > 0 ? `/${id}` : ""}`, {
      method: id && id > 0 ? "PUT" : "POST",
      body: JSON.stringify({ title, content })
    }),
  listFiles: (user: string) => call<RagFile[]>(`/users/${encodeURIComponent(user)}/files`),
  uploadFile: async (user: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE}/users/${encodeURIComponent(user)}/files`, { method: "POST", body: form });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<RagFile>;
  },
  askAi: (user: string, payload: Record<string, unknown>) =>
    call<AiResponse>(`/users/${encodeURIComponent(user)}/assistant`, {
      method: "POST",
      body: JSON.stringify(payload)
    })
};
