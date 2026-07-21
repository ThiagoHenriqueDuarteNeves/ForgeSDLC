export interface Health {
  status: string;
  service: string;
  version: string;
}

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Consulta GET /health da API. Lança em resposta não-2xx. */
export async function fetchHealth(baseUrl: string = API_URL): Promise<Health> {
  const resp = await fetch(`${baseUrl}/health`, { cache: "no-store" });
  if (!resp.ok) {
    throw new Error(`API respondeu ${resp.status}`);
  }
  return (await resp.json()) as Health;
}
