import { API_URL } from "./health";

export interface Project {
  id: number;
  name: string;
  created_at: string;
}

export interface Material {
  id: number;
  filename: string;
  source_type: string;
  status: string;
  created_at: string;
}

async function jsonOrThrow<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const detail = await resp.text().catch(() => "");
    throw new Error(`API ${resp.status}: ${detail}`);
  }
  return (await resp.json()) as T;
}

export async function listProjects(): Promise<Project[]> {
  return jsonOrThrow(await fetch(`${API_URL}/projects`, { cache: "no-store" }));
}

export async function createProject(name: string): Promise<Project> {
  return jsonOrThrow(
    await fetch(`${API_URL}/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  );
}

export async function listMaterials(projectId: number): Promise<Material[]> {
  return jsonOrThrow(
    await fetch(`${API_URL}/projects/${projectId}/materials`, {
      cache: "no-store",
    }),
  );
}

export async function uploadFile(
  projectId: number,
  file: File,
): Promise<Material> {
  const form = new FormData();
  form.append("file", file);
  return jsonOrThrow(
    await fetch(`${API_URL}/projects/${projectId}/materials`, {
      method: "POST",
      body: form,
    }),
  );
}

export async function uploadText(
  projectId: number,
  text: string,
): Promise<Material> {
  const form = new FormData();
  form.append("text", text);
  return jsonOrThrow(
    await fetch(`${API_URL}/projects/${projectId}/materials`, {
      method: "POST",
      body: form,
    }),
  );
}

// ─── Grill Me (E2) ─────────────────────────────────────────────────────────
export interface Pergunta {
  id: string;
  texto: string;
  motivo: string;
  item_checklist: string;
}

export interface GrillState {
  run_id: number;
  status: string; // aguardando_respostas | concluido
  cobertura: Record<string, string>;
  perguntas: Pergunta[];
  dossie: string | null;
}

export async function startRun(projectId: number): Promise<GrillState> {
  return jsonOrThrow(
    await fetch(`${API_URL}/projects/${projectId}/runs`, { method: "POST" }),
  );
}

export async function getRun(runId: number): Promise<GrillState> {
  return jsonOrThrow(
    await fetch(`${API_URL}/runs/${runId}`, { cache: "no-store" }),
  );
}

export async function answerRun(
  runId: number,
  respostas: Record<string, string>,
  encerrar: boolean,
): Promise<GrillState> {
  return jsonOrThrow(
    await fetch(`${API_URL}/runs/${runId}/answers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ respostas, encerrar }),
    }),
  );
}

// ─── Regras de negócio (E3) ────────────────────────────────────────────────
export interface Regra {
  id: number;
  code: string;
  text: string;
  fonte: string;
  status: string; // proposta | aprovada | rejeitada | contestada | superseded
  motivo: string | null;
  supersedes: string | null; // código da RN que esta supera
}

export interface RegrasState {
  run_id: number;
  status: string; // aguardando_aprovacao | concluido
  regras: Regra[];
}

export async function extrairRegras(runId: number): Promise<RegrasState> {
  return jsonOrThrow(
    await fetch(`${API_URL}/runs/${runId}/regras`, { method: "POST" }),
  );
}

export async function getRegras(runId: number): Promise<RegrasState> {
  return jsonOrThrow(
    await fetch(`${API_URL}/runs/${runId}/regras`, { cache: "no-store" }),
  );
}

export async function decidirRegras(
  runId: number,
  decisoes: Record<string, string>,
  motivos: Record<string, string> = {},
): Promise<RegrasState> {
  return jsonOrThrow(
    await fetch(`${API_URL}/runs/${runId}/regras/decisoes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decisoes, motivos }),
    }),
  );
}

// Contestação dirigida (E3.1)
export interface Contestacao {
  code: string;
  texto: string;
  motivo: string;
  perguntas: { id: string; texto: string; motivo: string; item_checklist: string }[];
}

export async function getContestacao(
  runId: number,
  code: string,
): Promise<Contestacao> {
  return jsonOrThrow(
    await fetch(`${API_URL}/runs/${runId}/regras/${code}/contestacao`, {
      cache: "no-store",
    }),
  );
}

export async function resolverContestacao(
  runId: number,
  code: string,
  respostas: Record<string, string>,
): Promise<RegrasState> {
  return jsonOrThrow(
    await fetch(`${API_URL}/runs/${runId}/regras/${code}/contestacao`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ respostas }),
    }),
  );
}

// ─── Épicos e histórias (E4) ───────────────────────────────────────────────
export interface Epico {
  id: number;
  title: string;
  description: string | null;
}

export interface Historia {
  id: number;
  epic_id: number;
  title: string;
  gherkin: string | null;
  status: string;
  rn_codes: string[];
}

export interface HistoriasState {
  run_id: number;
  status: string;
  epicos: Epico[];
  historias: Historia[];
}

export async function gerarHistorias(runId: number): Promise<HistoriasState> {
  return jsonOrThrow(
    await fetch(`${API_URL}/runs/${runId}/historias`, { method: "POST" }),
  );
}

export async function getHistorias(runId: number): Promise<HistoriasState> {
  return jsonOrThrow(
    await fetch(`${API_URL}/runs/${runId}/historias`, { cache: "no-store" }),
  );
}

export async function decidirHistorias(
  runId: number,
  decisoes: Record<string, string>,
): Promise<HistoriasState> {
  return jsonOrThrow(
    await fetch(`${API_URL}/runs/${runId}/historias/decisoes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decisoes }),
    }),
  );
}
