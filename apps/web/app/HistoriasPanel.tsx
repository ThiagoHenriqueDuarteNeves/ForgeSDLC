"use client";

import { useState } from "react";

import {
  type Epico,
  type Historia,
  type HistoriasState,
  decidirHistorias,
  gerarHistorias,
  getHistorias,
} from "@/lib/api";
import { useEstagio } from "@/lib/useEstagio";

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

const ST_COR: Record<string, string> = {
  proposta: "#9ca3af",
  aprovada: "#34d399",
  rejeitada: "#f87171",
};

export default function HistoriasPanel({
  runId,
  onError,
}: {
  runId: number;
  onError: (m: string) => void;
}) {
  const { state, setState, rodando, erro, disparar } = useEstagio<HistoriasState>(
    () => getHistorias(runId),
    () => gerarHistorias(runId),
    onError,
  );
  const [decisoes, setDecisoes] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  async function run(fn: () => Promise<HistoriasState>) {
    setLoading(true);
    try {
      setState(await fn());
      setDecisoes({});
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const aguardando = state?.status === "aguardando_aprovacao";
  const set = (id: number, acao: string) =>
    setDecisoes((d) => ({ ...d, [String(id)]: acao }));

  return (
    <section style={card}>
      <h2 style={{ fontSize: "1rem", marginTop: 0 }}>
        Histórias de Usuário — INVEST + Gherkin (E4)
      </h2>

      {(!state || state.status === "erro") && (
        <>
          <button onClick={disparar} disabled={rodando} style={btn}>
            Gerar histórias
          </button>
          <p style={{ opacity: 0.5, fontSize: "0.8rem" }}>
            exige RNs aprovadas na E3 (a aprovação bloqueia o avanço).
          </p>
        </>
      )}

      {rodando && (
        <p style={{ opacity: 0.7 }}>
          Gerando (valida matriz RN↔US)… leva alguns minutos; pode fechar a aba
          e voltar depois.
        </p>
      )}

      {erro && (
        <p style={{ color: "#f87171", marginTop: 8 }}>
          A geração falhou: {erro}. Clique para tentar de novo.
        </p>
      )}

      {loading && state && <p style={{ opacity: 0.7 }}>Processando…</p>}

      {state && !loading && !rodando && state.status !== "erro" && (
        <>
          {state.epicos.map((ep) => (
            <EpicoBloco
              key={ep.id}
              epico={ep}
              historias={state.historias.filter((h) => h.epic_id === ep.id)}
              aguardando={!!aguardando}
              decisoes={decisoes}
              onDecidir={set}
            />
          ))}
          {aguardando && (
            <button
              onClick={() => run(() => decidirHistorias(runId, decisoes))}
              disabled={Object.keys(decisoes).length === 0}
              style={{ ...btn, marginTop: 12 }}
            >
              Enviar decisões
            </button>
          )}
        </>
      )}
    </section>
  );
}

function EpicoBloco({
  epico,
  historias,
  aguardando,
  decisoes,
  onDecidir,
}: {
  epico: Epico;
  historias: Historia[];
  aguardando: boolean;
  decisoes: Record<string, string>;
  onDecidir: (id: number, acao: string) => void;
}) {
  return (
    <div style={{ marginTop: 14 }}>
      <div style={{ fontWeight: 600, color: "#93c5fd" }}>{epico.title}</div>
      {epico.description && (
        <div style={{ opacity: 0.6, fontSize: "0.85rem", marginBottom: 6 }}>
          {epico.description}
        </div>
      )}
      {historias.map((h) => (
        <div
          key={h.id}
          style={{
            borderLeft: "2px solid #2a2e37",
            padding: "0.5rem 0 0.5rem 0.75rem",
            marginBottom: 8,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span>{h.title}</span>
            <span
              style={{
                fontSize: "0.7rem",
                padding: "1px 8px",
                borderRadius: 999,
                border: `1px solid ${ST_COR[h.status] ?? "#9ca3af"}`,
                color: ST_COR[h.status] ?? "#9ca3af",
              }}
            >
              {h.status}
            </span>
          </div>
          <div style={{ marginTop: 4, display: "flex", flexWrap: "wrap", gap: 4 }}>
            {h.rn_codes.length === 0 && (
              <span style={{ fontSize: "0.72rem", color: "#f87171" }}>
                sem RN de origem
              </span>
            )}
            {h.rn_codes.map((c) => (
              <span
                key={c}
                style={{
                  fontFamily: "monospace",
                  fontSize: "0.72rem",
                  padding: "1px 6px",
                  borderRadius: 6,
                  background: "#0f1115",
                  border: "1px solid #2a2e37",
                }}
              >
                {c}
              </span>
            ))}
          </div>
          {h.gherkin && (
            <pre
              style={{
                marginTop: 6,
                whiteSpace: "pre-wrap",
                fontSize: "0.8rem",
                background: "#0f1115",
                borderRadius: 6,
                padding: "0.5rem 0.75rem",
                border: "1px solid #2a2e37",
              }}
            >
              {h.gherkin}
            </pre>
          )}
          {aguardando && h.status === "proposta" && (
            <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
              {[
                { acao: "aprovar", cor: "#34d399" },
                { acao: "rejeitar", cor: "#f87171" },
              ].map((a) => (
                <button
                  key={a.acao}
                  onClick={() => onDecidir(h.id, a.acao)}
                  style={{
                    padding: "0.2rem 0.6rem",
                    borderRadius: 8,
                    cursor: "pointer",
                    background: decisoes[String(h.id)] === a.acao ? a.cor : "transparent",
                    color: decisoes[String(h.id)] === a.acao ? "#0f1115" : a.cor,
                    border: `1px solid ${a.cor}`,
                  }}
                >
                  {a.acao}
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
