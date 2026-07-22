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

// ─── Anotações do projeto (fatia-exemplo F-EX01 / E7) ──────────────────────
export interface Nota {
  id: number;
  text: string;
  created_at: string;
}

export async function listarNotas(projectId: number): Promise<Nota[]> {
  return jsonOrThrow(
    await fetch(`${API_URL}/projects/${projectId}/notes`, { cache: "no-store" }),
  );
}

export async function criarNota(projectId: number, text: string): Promise<Nota> {
  return jsonOrThrow(
    await fetch(`${API_URL}/projects/${projectId}/notes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
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

// ─── E5: ADR (arquiteto) + cenários de teste (designer) ────────────────────
export interface Adr {
  title: string;
  context: string;
  options: string;
  decision: string;
  consequences: string;
}

export interface Cenario {
  kind: string; // feliz | alternativo | erro
  gherkin: string;
}

export interface HistoriaCenarios {
  story_id: number;
  title: string;
  cenarios: Cenario[];
}

export interface E5State {
  run_id: number;
  status: string; // pendente | concluido
  adr: Adr | null;
  historias: HistoriaCenarios[];
}

export async function rodarE5(runId: number): Promise<E5State> {
  return jsonOrThrow(
    await fetch(`${API_URL}/runs/${runId}/e5`, { method: "POST" }),
  );
}

export async function getE5(runId: number): Promise<E5State> {
  return jsonOrThrow(
    await fetch(`${API_URL}/runs/${runId}/e5`, { cache: "no-store" }),
  );
}

// ─── E6: fatias verticais ──────────────────────────────────────────────────
export interface Fatia {
  code: string;
  title: string;
  status: string; // planejada | em_dev | entregue
  package_path: string | null;
  package_md: string | null;
}

export interface FatiasState {
  run_id: number;
  status: string;
  fatias: Fatia[];
}

export async function rodarFatias(runId: number): Promise<FatiasState> {
  return jsonOrThrow(
    await fetch(`${API_URL}/runs/${runId}/fatias`, { method: "POST" }),
  );
}

export async function getFatias(runId: number): Promise<FatiasState> {
  return jsonOrThrow(
    await fetch(`${API_URL}/runs/${runId}/fatias`, { cache: "no-store" }),
  );
}

export async function atualizarStatusFatia(
  runId: number,
  code: string,
  status: string,
): Promise<FatiasState> {
  return jsonOrThrow(
    await fetch(`${API_URL}/runs/${runId}/fatias/${code}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }),
  );
}

// ─── Observabilidade: métricas por estágio (Fase 7) ────────────────────────
export interface EstagioMetrica {
  stage: string; // E2..E6
  chamadas: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  latency_ms: number;
}

export interface TotalMetrica {
  chamadas: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  latency_ms: number;
}

export interface RunMetricas {
  run_id: number;
  estagios: EstagioMetrica[];
  total: TotalMetrica;
}

export async function getMetricas(runId: number): Promise<RunMetricas> {
  return jsonOrThrow(
    await fetch(`${API_URL}/runs/${runId}/metrics`, { cache: "no-store" }),
  );
}
