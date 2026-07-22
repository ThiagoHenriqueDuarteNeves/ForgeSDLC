"use client";

import { useCallback, useEffect, useState } from "react";

import {
  type Regra,
  type RegrasState,
  decidirRegras,
  extrairRegras,
  getRegras,
} from "@/lib/api";

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

const RN_COR: Record<string, string> = {
  proposta: "#9ca3af",
  aprovada: "#34d399",
  rejeitada: "#f87171",
  contestada: "#fbbf24",
  superseded: "#6b7280",
};

const ACOES: { acao: string; rotulo: string; cor: string }[] = [
  { acao: "aprovar", rotulo: "Aprovar", cor: "#34d399" },
  { acao: "rejeitar", rotulo: "Rejeitar", cor: "#f87171" },
  { acao: "contestar", rotulo: "Contestar", cor: "#fbbf24" },
];

export default function RegrasPanel({
  runId,
  onError,
}: {
  runId: number;
  onError: (m: string) => void;
}) {
  const [state, setState] = useState<RegrasState | null>(null);
  const [decisoes, setDecisoes] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const s = await getRegras(runId);
      if (s.regras.length > 0 || s.status !== "concluido") setState(s);
    } catch {
      /* run ainda sem regras — silêncio */
    }
  }, [runId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch pós-await
    refresh();
  }, [refresh]);

  async function run(fn: () => Promise<RegrasState>) {
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

  return (
    <section style={card}>
      <h2 style={{ fontSize: "1rem", marginTop: 0 }}>
        Regras de Negócio — extração + refino (E3)
      </h2>

      {!state && (
        <button onClick={() => run(() => extrairRegras(runId))} disabled={loading} style={btn}>
          {loading ? "Extraindo (3× em paralelo → crítico ⇄ refinador)…" : "Extrair regras"}
        </button>
      )}

      {loading && state && <p style={{ opacity: 0.7 }}>Processando…</p>}

      {state && !loading && (
        <>
          {aguardando && (
            <p style={{ opacity: 0.7, marginTop: 0 }}>
              Regras propostas. Aprove, rejeite ou conteste — <strong>não há editar</strong>:
              RN aprovada é imutável (correção vira RN nova).
            </p>
          )}
          {state.regras.map((r) => (
            <RegraRow
              key={r.id}
              regra={r}
              escolha={decisoes[r.code]}
              editavel={aguardando && r.status === "proposta"}
              onEscolher={(acao) => setDecisoes((d) => ({ ...d, [r.code]: acao }))}
            />
          ))}
          {state.regras.length === 0 && (
            <p style={{ opacity: 0.5 }}>nenhuma regra extraída ainda</p>
          )}
          {aguardando && (
            <button
              onClick={() => run(() => decidirRegras(runId, decisoes))}
              disabled={Object.keys(decisoes).length === 0}
              style={{ ...btn, marginTop: 8 }}
            >
              Enviar decisões
            </button>
          )}
        </>
      )}
    </section>
  );
}

function RegraRow({
  regra,
  escolha,
  editavel,
  onEscolher,
}: {
  regra: Regra;
  escolha: string | undefined;
  editavel: boolean;
  onEscolher: (acao: string) => void;
}) {
  return (
    <div
      style={{
        borderTop: "1px solid #2a2e37",
        padding: "0.75rem 0",
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <strong style={{ fontFamily: "monospace" }}>{regra.code}</strong>
        <span
          style={{
            fontSize: "0.72rem",
            padding: "1px 8px",
            borderRadius: 999,
            border: `1px solid ${RN_COR[regra.status] ?? "#9ca3af"}`,
            color: RN_COR[regra.status] ?? "#9ca3af",
          }}
        >
          {regra.status}
        </span>
      </div>
      <div>{regra.text}</div>
      <div style={{ opacity: 0.5, fontSize: "0.8rem" }}>fonte: {regra.fonte}</div>
      {editavel && (
        <div style={{ display: "flex", gap: 6 }}>
          {ACOES.map((a) => (
            <button
              key={a.acao}
              onClick={() => onEscolher(a.acao)}
              style={{
                padding: "0.25rem 0.7rem",
                borderRadius: 8,
                cursor: "pointer",
                background: escolha === a.acao ? a.cor : "transparent",
                color: escolha === a.acao ? "#0f1115" : a.cor,
                border: `1px solid ${a.cor}`,
              }}
            >
              {a.rotulo}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
