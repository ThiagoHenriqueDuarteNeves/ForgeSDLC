"use client";

import { useCallback, useEffect, useState } from "react";

import {
  type Fatia,
  type FatiasState,
  atualizarStatusFatia,
  getFatias,
  rodarFatias,
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

const ST_COR: Record<string, string> = {
  planejada: "#9ca3af",
  em_dev: "#fbbf24",
  entregue: "#34d399",
};

const STATUS = ["planejada", "em_dev", "entregue"];

export default function FatiasPanel({
  runId,
  onError,
}: {
  runId: number;
  onError: (m: string) => void;
}) {
  const [state, setState] = useState<FatiasState | null>(null);
  const [loading, setLoading] = useState(false);
  const [aberta, setAberta] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const s = await getFatias(runId);
      if (s.fatias.length > 0) setState(s);
    } catch {
      /* sem fatias ainda */
    }
  }, [runId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch pós-await
    refresh();
  }, [refresh]);

  async function run(fn: () => Promise<FatiasState>) {
    setLoading(true);
    try {
      setState(await fn());
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section style={card}>
      <h2 style={{ fontSize: "1rem", marginTop: 0 }}>Fatias Verticais (E6)</h2>

      {!state && (
        <>
          <button onClick={() => run(() => rodarFatias(runId))} disabled={loading} style={btn}>
            {loading ? "Fatiando (valida as 3 camadas)…" : "Fatiar"}
          </button>
          <p style={{ opacity: 0.5, fontSize: "0.8rem" }}>
            exige histórias aprovadas na E4; cada fatia atravessa UI + API + banco + testes.
          </p>
        </>
      )}

      {loading && state && <p style={{ opacity: 0.7 }}>Processando…</p>}

      {state && !loading && (
        <div>
          {state.fatias.map((f) => (
            <FatiaRow
              key={f.code}
              fatia={f}
              aberta={aberta === f.code}
              onToggle={() => setAberta(aberta === f.code ? null : f.code)}
              onStatus={(s) => run(() => atualizarStatusFatia(runId, f.code, s))}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function FatiaRow({
  fatia,
  aberta,
  onToggle,
  onStatus,
}: {
  fatia: Fatia;
  aberta: boolean;
  onToggle: () => void;
  onStatus: (status: string) => void;
}) {
  return (
    <div style={{ borderTop: "1px solid #2a2e37", padding: "0.75rem 0" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <strong style={{ fontFamily: "monospace" }}>{fatia.code}</strong>
        <span style={{ flex: 1 }}>{fatia.title}</span>
        <select
          value={fatia.status}
          onChange={(e) => onStatus(e.target.value)}
          style={{
            background: "#0f1115",
            color: ST_COR[fatia.status] ?? "#e6e6e6",
            border: `1px solid ${ST_COR[fatia.status] ?? "#2a2e37"}`,
            borderRadius: 8,
            padding: "0.25rem 0.5rem",
          }}
        >
          {STATUS.map((s) => (
            <option key={s} value={s} style={{ color: "#e6e6e6", background: "#0f1115" }}>
              {s}
            </option>
          ))}
        </select>
        <button
          onClick={onToggle}
          style={{ ...btn, padding: "0.25rem 0.7rem", borderColor: "#3a3f4b", color: "#93c5fd" }}
        >
          {aberta ? "ocultar pacote" : "ver pacote"}
        </button>
      </div>
      {aberta && (
        <pre
          style={{
            marginTop: 8,
            whiteSpace: "pre-wrap",
            fontSize: "0.8rem",
            background: "#0f1115",
            borderRadius: 8,
            padding: "0.75rem 1rem",
            border: "1px solid #2a2e37",
            maxHeight: 400,
            overflow: "auto",
          }}
        >
          {fatia.package_md ?? "(sem pacote)"}
        </pre>
      )}
      {fatia.package_path && (
        <div style={{ opacity: 0.4, fontSize: "0.72rem", marginTop: 4 }}>
          {fatia.package_path}
        </div>
      )}
    </div>
  );
}
