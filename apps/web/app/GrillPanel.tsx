"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";

import { type GrillState, answerRun, startRun } from "@/lib/api";

const card = {
  padding: "1.25rem 1.5rem",
  borderRadius: 12,
  border: "1px solid #2a2e37",
  background: "#161a22",
  marginTop: "1.5rem",
} as const;

const btn = {
  padding: "0.5rem 1rem",
  borderRadius: 8,
  border: "1px solid #34d399",
  background: "transparent",
  color: "#34d399",
  cursor: "pointer",
} as const;

export default function GrillPanel({
  projectId,
  onError,
  onRun,
}: {
  projectId: number;
  onError: (m: string) => void;
  onRun?: (runId: number) => void;
}) {
  const [state, setState] = useState<GrillState | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  async function run(fn: () => Promise<GrillState>) {
    setLoading(true);
    try {
      const s = await fn();
      setState(s);
      setAnswers({});
      onRun?.(s.run_id);
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const start = () => run(() => startRun(projectId));
  const submit = (encerrar: boolean) =>
    state && run(() => answerRun(state.run_id, answers, encerrar));

  return (
    <section style={card}>
      <h2 style={{ fontSize: "1rem", marginTop: 0 }}>Grill Me — entrevista (E2)</h2>

      {!state && (
        <button onClick={start} disabled={loading} style={btn}>
          {loading ? "Iniciando…" : "Iniciar entrevista"}
        </button>
      )}

      {loading && state && <p style={{ opacity: 0.7 }}>O agente está pensando…</p>}

      {state && state.status === "aguardando_respostas" && !loading && (
        <div>
          <Cobertura cobertura={state.cobertura} />
          {state.perguntas.map((p) => (
            <div key={p.id} style={{ marginBottom: 14 }}>
              <label style={{ display: "block", marginBottom: 4 }}>
                <strong>{p.id}</strong>{" "}
                <span style={{ opacity: 0.5, fontSize: "0.8rem" }}>
                  [{p.item_checklist}]
                </span>
                <br />
                {p.texto}
                <span style={{ display: "block", opacity: 0.5, fontSize: "0.8rem" }}>
                  motivo: {p.motivo}
                </span>
              </label>
              <textarea
                rows={2}
                value={answers[p.id] ?? ""}
                onChange={(e) =>
                  setAnswers((a) => ({ ...a, [p.id]: e.target.value }))
                }
                placeholder="sua resposta (deixe vazio se não souber)"
                style={{
                  width: "100%",
                  padding: "0.5rem",
                  borderRadius: 8,
                  border: "1px solid #2a2e37",
                  background: "#0f1115",
                  color: "#e6e6e6",
                  fontFamily: "inherit",
                  resize: "vertical",
                }}
              />
            </div>
          ))}
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={() => submit(false)} style={btn}>
              Enviar respostas
            </button>
            <button
              onClick={() => submit(true)}
              style={{ ...btn, borderColor: "#9ca3af", color: "#9ca3af" }}
            >
              Encerrar entrevista
            </button>
          </div>
        </div>
      )}

      {state && state.status === "concluido" && !loading && (
        <div>
          <div style={{ color: "#34d399", marginBottom: 12 }}>
            ✅ Entrevista encerrada — Dossiê do Sistema
          </div>
          <div
            style={{
              background: "#0f1115",
              borderRadius: 8,
              padding: "1rem 1.25rem",
              border: "1px solid #2a2e37",
              lineHeight: 1.5,
            }}
          >
            <ReactMarkdown>{state.dossie ?? ""}</ReactMarkdown>
          </div>
        </div>
      )}
    </section>
  );
}

function Cobertura({ cobertura }: { cobertura: Record<string, string> }) {
  const cor: Record<string, string> = {
    coberto: "#34d399",
    parcial: "#fbbf24",
    ausente: "#f87171",
  };
  const itens = Object.entries(cobertura);
  if (itens.length === 0) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
      {itens.map(([item, estado]) => (
        <span
          key={item}
          style={{
            fontSize: "0.75rem",
            padding: "2px 8px",
            borderRadius: 999,
            border: `1px solid ${cor[estado] ?? "#9ca3af"}`,
            color: cor[estado] ?? "#9ca3af",
          }}
        >
          {item}: {estado}
        </span>
      ))}
    </div>
  );
}
