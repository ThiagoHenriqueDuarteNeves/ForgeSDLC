"use client";

import { useCallback, useEffect, useState } from "react";

import { type Nota, criarNota, listarNotas } from "@/lib/api";

const card = {
  padding: "1.25rem 1.5rem",
  borderRadius: 12,
  border: "1px solid #2a2e37",
  background: "#161a22",
  marginTop: "1.5rem",
} as const;

const input = {
  padding: "0.5rem 0.75rem",
  borderRadius: 8,
  border: "1px solid #2a2e37",
  background: "#0f1115",
  color: "#e6e6e6",
  flex: 1,
} as const;

const btn = {
  padding: "0.5rem 1rem",
  borderRadius: 8,
  border: "1px solid #34d399",
  background: "transparent",
  color: "#34d399",
  cursor: "pointer",
} as const;

// Fatia-exemplo F-EX01 (E7): anotações livres do projeto, consumindo a API real.
export default function NotesPanel({
  projectId,
  onError,
}: {
  projectId: number;
  onError: (m: string) => void;
}) {
  const [notas, setNotas] = useState<Nota[]>([]);
  const [texto, setTexto] = useState("");
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setNotas(await listarNotas(projectId));
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    }
  }, [projectId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch pós-await
    refresh();
  }, [refresh]);

  async function anotar() {
    if (!texto.trim()) return;
    setSaving(true);
    try {
      await criarNota(projectId, texto.trim());
      setTexto("");
      await refresh();
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section style={card}>
      <h2 style={{ fontSize: "1rem", marginTop: 0 }}>Anotações</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && anotar()}
          placeholder="ex.: faltou o material de compliance"
          style={input}
        />
        <button onClick={anotar} disabled={saving} style={btn}>
          {saving ? "…" : "Anotar"}
        </button>
      </div>
      {notas.length === 0 ? (
        <p style={{ opacity: 0.5, fontSize: "0.85rem" }}>nenhuma anotação ainda</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {notas.map((n) => (
            <li
              key={n.id}
              style={{
                borderTop: "1px solid #2a2e37",
                padding: "0.5rem 0",
                fontSize: "0.9rem",
              }}
            >
              {n.text}
              <span style={{ opacity: 0.4, fontSize: "0.72rem", marginLeft: 8 }}>
                {new Date(n.created_at).toLocaleString()}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
