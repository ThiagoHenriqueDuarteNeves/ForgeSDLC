"use client";

import { useCallback, useEffect, useState } from "react";

import { type E5State, getE5, rodarE5 } from "@/lib/api";

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

const KIND_COR: Record<string, string> = {
  feliz: "#34d399",
  alternativo: "#fbbf24",
  erro: "#f87171",
};

const bloco = {
  background: "#0f1115",
  borderRadius: 8,
  padding: "0.75rem 1rem",
  border: "1px solid #2a2e37",
  whiteSpace: "pre-wrap" as const,
  fontSize: "0.85rem",
  marginTop: 4,
};

export default function E5Panel({
  runId,
  onError,
}: {
  runId: number;
  onError: (m: string) => void;
}) {
  const [state, setState] = useState<E5State | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const s = await getE5(runId);
      if (s.adr || s.historias.length > 0) setState(s);
    } catch {
      /* sem E5 ainda */
    }
  }, [runId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch pós-await
    refresh();
  }, [refresh]);

  async function run() {
    setLoading(true);
    try {
      setState(await rodarE5(runId));
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section style={card}>
      <h2 style={{ fontSize: "1rem", marginTop: 0 }}>
        Arquitetura ∥ Testes (E5)
      </h2>

      {!state && (
        <>
          <button onClick={run} disabled={loading} style={btn}>
            {loading ? "Rodando arquiteto ∥ designer (paralelo)…" : "Rodar E5"}
          </button>
          <p style={{ opacity: 0.5, fontSize: "0.8rem" }}>
            exige histórias aprovadas na E4.
          </p>
        </>
      )}

      {loading && state && <p style={{ opacity: 0.7 }}>Processando…</p>}

      {state?.adr && !loading && (
        <div style={{ marginTop: 8 }}>
          <h3 style={{ fontSize: "0.95rem", color: "#93c5fd" }}>{state.adr.title}</h3>
          <Campo titulo="Contexto" texto={state.adr.context} />
          <Campo titulo="Opções consideradas" texto={state.adr.options} />
          <Campo titulo="Decisão" texto={state.adr.decision} />
          <Campo titulo="Consequências" texto={state.adr.consequences} />
        </div>
      )}

      {state && state.historias.length > 0 && !loading && (
        <div style={{ marginTop: 16 }}>
          <h3 style={{ fontSize: "0.95rem" }}>Cenários de teste por história</h3>
          {state.historias.map((h) => (
            <div key={h.story_id} style={{ marginTop: 10 }}>
              <div style={{ fontWeight: 600 }}>{h.title}</div>
              {h.cenarios.map((c, i) => (
                <div key={i} style={{ marginTop: 6 }}>
                  <span
                    style={{
                      fontSize: "0.7rem",
                      padding: "1px 8px",
                      borderRadius: 999,
                      border: `1px solid ${KIND_COR[c.kind] ?? "#9ca3af"}`,
                      color: KIND_COR[c.kind] ?? "#9ca3af",
                    }}
                  >
                    {c.kind}
                  </span>
                  <pre style={bloco}>{c.gherkin}</pre>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function Campo({ titulo, texto }: { titulo: string; texto: string }) {
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ opacity: 0.6, fontSize: "0.8rem" }}>{titulo}</div>
      <div style={bloco}>{texto}</div>
    </div>
  );
}
