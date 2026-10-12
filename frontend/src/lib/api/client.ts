import { mockApi } from "./mock";
import type { Api } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) throw new Error(`API ${res.status} on ${path}`);
  return (await res.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

const realApi: Api = {
  listPatients: () => http("/patients"),
  getBrief: (id) => http(`/patients/${id}/brief`),
  getSource: (id, chunkId) => http(`/patients/${id}/sources/${encodeURIComponent(chunkId)}`),
  chat: (id, question) => http(`/patients/${id}/chat`, json({ question })),
  review: (insightId, action) => http(`/insights/${insightId}/review`, json({ action })),
  upload: (id, file) => {
    const form = new FormData();
    form.append("file", file);
    return http(`/patients/${id}/files`, { method: "POST", body: form });
  },
  audit: () => http("/audit"),
};

export const isMockMode = !BASE;

export function getApi(): Api {
  return isMockMode ? mockApi : realApi;
}
