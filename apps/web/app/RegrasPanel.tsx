"use client";

import { useState } from "react";

import {
  type Contestacao,
  type Regra,
  type RegrasState,
  decidirRegras,
  extrairRegras,
  getContestacao,
  getRegras,
  resolverContestacao,
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

const input = {
  width: "100%",
  padding: "0.5rem",
  borderRadius: 8,
  border: "1px solid #2a2e37",
  background: "#0f1115",
  color: "#e6e6e6",
  fontFamily: "inherit",
  resize: "vertical",
} as const;

const RN_COR: Record<string, string> = {
  proposta: "#9ca3af",
  aprovada: "#34d399",
  rejeitada: "#f87171",
  contestada: "#fbbf24",
  superseded: "#6b7280",
};

const ACOES = [
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
  const { state, setState, rodando, erro, disparar } = useEstagio<RegrasState>(
    () => getRegras(runId),
    () => extrairRegras(runId),
    onError,
  );
  const [decisoes, setDecisoes] = useState<Record<string, string>>({});
  const [motivos, setMotivos] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [contest, setContest] = useState<Contestacao | null>(null);
  const [respContest, setRespContest] = useState<Record<string, string>>({});

  async function run(fn: () => Promise<RegrasState>) {
    setLoading(true);
    try {
      setState(await fn());
      setDecisoes({});
      setMotivos({});
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function abrirContestacao(code: string) {
    setLoading(true);
    try {
      setContest(await getContestacao(runId, code));
      setRespContest({});
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function enviarResolucao() {
    if (!contest) return;
    setLoading(true);
    try {
      setState(await resolverContestacao(runId, contest.code, respContest));
      setContest(null);
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const aguardando = state?.status === "aguardando_aprovacao";
  const contestadas = state?.regras.filter((r) => r.status === "contestada") ?? [];

  return (
    <section style={card}>
      <h2 style={{ fontSize: "1rem", marginTop: 0 }}>
        Regras de Negócio — extração + refino (E3)
      </h2>

      {(!state || state.status === "erro") && (
        <button onClick={disparar} disabled={rodando} style={btn}>
          Extrair regras
        </button>
      )}

      {rodando && (
        <p style={{ opacity: 0.7 }}>
          Extraindo (3× em paralelo → crítico ⇄ refinador)… leva alguns minutos;
          pode fechar a aba e voltar depois.
        </p>
      )}

      {erro && (
        <p style={{ color: "#f87171", marginTop: 8 }}>
          A extração falhou: {erro}. Clique para tentar de novo.
        </p>
      )}

      {loading && state && <p style={{ opacity: 0.7 }}>Processando…</p>}

      {state && !loading && !rodando && state.status !== "erro" && (
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
              motivo={motivos[r.code] ?? ""}
              editavel={aguardando === true && r.status === "proposta"}
              onEscolher={(acao) => setDecisoes((d) => ({ ...d, [r.code]: acao }))}
              onMotivo={(m) => setMotivos((mm) => ({ ...mm, [r.code]: m }))}
            />
          ))}
          {state.regras.length === 0 && (
            <p style={{ opacity: 0.5 }}>nenhuma regra extraída ainda</p>
          )}
          {aguardando && (
            <button
              onClick={() => run(() => decidirRegras(runId, decisoes, motivos))}
              disabled={Object.keys(decisoes).length === 0}
              style={{ ...btn, marginTop: 8 }}
            >
              Enviar decisões
            </button>
          )}

          {/* Contestações abertas: resolver via rodada dirigida do Grill Me */}
          {!aguardando && contestadas.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <h3 style={{ fontSize: "0.9rem" }}>Contestações a resolver</h3>
              {contestadas.map((r) => (
                <div key={r.id} style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
                  <span style={{ fontFamily: "monospace" }}>{r.code}</span>
                  <span style={{ opacity: 0.6, fontSize: "0.8rem" }}>{r.motivo}</span>
                  <button onClick={() => abrirContestacao(r.code)} style={{ ...btn, padding: "0.25rem 0.7rem" }}>
                    Resolver contestação
                  </button>
                </div>
              ))}
            </div>
          )}

          {contest && (
            <div style={{ marginTop: 12, padding: "0.75rem 1rem", border: "1px solid #fbbf24", borderRadius: 10 }}>
              <div style={{ color: "#fbbf24", marginBottom: 8 }}>
                Rodada dirigida — {contest.code}: {contest.texto}
              </div>
              {contest.perguntas.map((p) => (
                <div key={p.id} style={{ marginBottom: 10 }}>
                  <label style={{ display: "block", marginBottom: 4 }}>
                    <strong>{p.id}</strong> {p.texto}
                  </label>
                  <textarea
                    rows={2}
                    value={respContest[p.id] ?? ""}
                    onChange={(e) => setRespContest((rr) => ({ ...rr, [p.id]: e.target.value }))}
                    style={input}
                  />
                </div>
              ))}
              <button onClick={enviarResolucao} style={btn}>
                Resolver → gerar RN corrigida (supersede)
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function RegraRow({
  regra,
  escolha,
  motivo,
  editavel,
  onEscolher,
  onMotivo,
}: {
  regra: Regra;
  escolha: string | undefined;
  motivo: string;
  editavel: boolean;
  onEscolher: (acao: string) => void;
  onMotivo: (m: string) => void;
}) {
  return (
    <div
      style={{
        borderTop: "1px solid #2a2e37",
        padding: "0.75rem 0",
        display: "flex",
        flexDirection: "column",
        gap: 6,
        opacity: regra.status === "superseded" ? 0.55 : 1,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
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
        {regra.supersedes && (
          <span style={{ fontSize: "0.72rem", color: "#93c5fd" }}>
            supera {regra.supersedes}
          </span>
        )}
      </div>
      <div style={{ textDecoration: regra.status === "superseded" ? "line-through" : "none" }}>
        {regra.text}
      </div>
      <div style={{ opacity: 0.5, fontSize: "0.8rem" }}>fonte: {regra.fonte}</div>
      {editavel && (
        <>
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
          {escolha === "contestar" && (
            <textarea
              rows={2}
              value={motivo}
              onChange={(e) => onMotivo(e.target.value)}
              placeholder="por que esta RN está errada? (motivo da contestação)"
              style={input}
            />
          )}
        </>
      )}
    </div>
  );
}
