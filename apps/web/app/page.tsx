"use client";

import { useEffect, useState } from "react";

import { type Health, fetchHealth } from "@/lib/health";

type State =
  | { kind: "loading" }
  | { kind: "ok"; health: Health }
  | { kind: "error"; message: string };

export default function Home() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    fetchHealth()
      .then((health) => setState({ kind: "ok", health }))
      .catch((err: unknown) =>
        setState({
          kind: "error",
          message: err instanceof Error ? err.message : String(err),
        }),
      );
  }, []);

  return (
    <main style={{ maxWidth: 640, margin: "0 auto", padding: "4rem 1.5rem" }}>
      <h1 style={{ fontSize: "1.75rem", marginBottom: "0.5rem" }}>Forge SDLC</h1>
      <p style={{ opacity: 0.7, marginTop: 0 }}>
        Primeira fatia vertical: a web consome GET /health da API.
      </p>

      <div
        style={{
          marginTop: "2rem",
          padding: "1.25rem 1.5rem",
          borderRadius: 12,
          border: "1px solid #2a2e37",
          background: "#161a22",
        }}
      >
        {state.kind === "loading" && <span>Consultando a API…</span>}

        {state.kind === "ok" && (
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span
                aria-hidden
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  background: "#34d399",
                  display: "inline-block",
                }}
              />
              <strong>API online</strong>
            </div>
            <dl style={{ margin: "1rem 0 0", display: "grid", gap: 4 }}>
              <Row label="status" value={state.health.status} />
              <Row label="service" value={state.health.service} />
              <Row label="version" value={state.health.version} />
            </dl>
          </div>
        )}

        {state.kind === "error" && (
          <div style={{ color: "#f87171" }}>
            <strong>API indisponível.</strong>
            <p style={{ margin: "0.5rem 0 0", opacity: 0.85 }}>{state.message}</p>
          </div>
        )}
      </div>
    </main>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", gap: 12 }}>
      <dt style={{ opacity: 0.6, width: 80 }}>{label}</dt>
      <dd style={{ margin: 0, fontFamily: "monospace" }}>{value}</dd>
    </div>
  );
}
