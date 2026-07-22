"use client";

import { useCallback, useEffect, useState } from "react";

import {
  type EstagioMetrica,
  type RunMetricas,
  getMetricas,
} from "@/lib/api";

const card = {
  padding: "1.25rem 1.5rem",
  borderRadius: 12,
  border: "1px solid #2a2e37",
  background: "#161a22",
  marginTop: "1.5rem",
} as const;

const btn = {
  padding: "0.4rem 0.9rem",
  borderRadius: 8,
  border: "1px solid #3a3f4b",
  background: "transparent",
  color: "#93c5fd",
  cursor: "pointer",
} as const;

const th = { padding: "0.4rem 0.5rem", textAlign: "left", opacity: 0.6 } as const;
const td = { padding: "0.4rem 0.5rem", borderTop: "1px solid #2a2e37" } as const;
const num = { ...td, textAlign: "right", fontVariantNumeric: "tabular-nums" } as const;

const STAGE_LABEL: Record<string, string> = {
  E2: "E2 · Grill Me",
  E3: "E3 · Regras",
  E4: "E4 · Histórias",
  E5: "E5 · Arquiteto ∥ Testes",
  E6: "E6 · Fatiador",
};

const usd = (v: number) => `$${v.toFixed(4)}`;
const secs = (ms: number) => `${(ms / 1000).toFixed(1)}s`;

export default function MetricsPanel({
  runId,
  onError,
}: {
  runId: number;
  onError: (m: string) => void;
}) {
  const [state, setState] = useState<RunMetricas | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setState(await getMetricas(runId));
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [runId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch pós-await
    refresh();
  }, [refresh]);

  const vazio = !state || state.estagios.length === 0;

  return (
    <section style={card}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <h2 style={{ fontSize: "1rem", margin: 0, flex: 1 }}>
          Observabilidade — custo &amp; tempo por estágio (Fase 7)
        </h2>
        <button onClick={refresh} disabled={loading} style={btn}>
          {loading ? "…" : "atualizar"}
        </button>
      </div>

      {vazio && (
        <p style={{ opacity: 0.5, fontSize: "0.85rem" }}>
          nenhuma métrica ainda — rode uma etapa do pipeline (E2–E6) neste run.
        </p>
      )}

      {state && !vazio && (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem", marginTop: 8 }}>
          <thead>
            <tr>
              <th style={th}>Estágio</th>
              <th style={{ ...th, textAlign: "right" }}>Chamadas</th>
              <th style={{ ...th, textAlign: "right" }}>Tokens in</th>
              <th style={{ ...th, textAlign: "right" }}>Tokens out</th>
              <th style={{ ...th, textAlign: "right" }}>Custo</th>
              <th style={{ ...th, textAlign: "right" }}>Tempo</th>
            </tr>
          </thead>
          <tbody>
            {state.estagios.map((e: EstagioMetrica) => (
              <tr key={e.stage}>
                <td style={td}>{STAGE_LABEL[e.stage] ?? e.stage}</td>
                <td style={num}>{e.chamadas}</td>
                <td style={num}>{e.tokens_in.toLocaleString()}</td>
                <td style={num}>{e.tokens_out.toLocaleString()}</td>
                <td style={num}>{usd(e.cost_usd)}</td>
                <td style={num}>{secs(e.latency_ms)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr style={{ fontWeight: 600, color: "#34d399" }}>
              <td style={td}>Total</td>
              <td style={num}>{state.total.chamadas}</td>
              <td style={num}>{state.total.tokens_in.toLocaleString()}</td>
              <td style={num}>{state.total.tokens_out.toLocaleString()}</td>
              <td style={num}>{usd(state.total.cost_usd)}</td>
              <td style={num}>{secs(state.total.latency_ms)}</td>
            </tr>
          </tfoot>
        </table>
      )}

      <p style={{ opacity: 0.4, fontSize: "0.72rem", marginTop: 8 }}>
        &ldquo;Chamadas&rdquo; por estágio serve de proxy de iterações (ex.: refinador rodando 2×).
        Custo estimado por tokens × preço do modelo.
      </p>
    </section>
  );
}
