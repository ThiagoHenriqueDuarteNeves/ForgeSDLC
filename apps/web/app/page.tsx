"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  type Material,
  type Project,
  createProject,
  listMaterials,
  listProjects,
  uploadFile,
  uploadText,
} from "@/lib/api";

const card = {
  padding: "1.25rem 1.5rem",
  borderRadius: 12,
  border: "1px solid #2a2e37",
  background: "#161a22",
} as const;

const STATUS_COLOR: Record<string, string> = {
  pendente: "#9ca3af",
  processando: "#fbbf24",
  processado: "#34d399",
  erro: "#f87171",
};

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<Project | null>(null);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refreshProjects = useCallback(async () => {
    try {
      setProjects(await listProjects());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch assíncrono: setState ocorre pós-await
    refreshProjects();
  }, [refreshProjects]);

  async function handleCreate() {
    if (!newName.trim()) return;
    try {
      const p = await createProject(newName.trim());
      setNewName("");
      await refreshProjects();
      setSelected(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <main style={{ maxWidth: 820, margin: "0 auto", padding: "3rem 1.5rem" }}>
      <h1 style={{ fontSize: "1.75rem", marginBottom: "0.25rem" }}>Forge SDLC</h1>
      <p style={{ opacity: 0.7, marginTop: 0 }}>Ingestão de materiais (E1)</p>

      {error && (
        <div style={{ ...card, borderColor: "#7f1d1d", color: "#f87171", marginBottom: "1rem" }}>
          {error}
        </div>
      )}

      <section style={{ ...card, marginBottom: "1.5rem" }}>
        <h2 style={{ fontSize: "1rem", marginTop: 0 }}>Projetos</h2>
        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            placeholder="Nome do novo projeto"
            style={inputStyle}
          />
          <button onClick={handleCreate} style={btnStyle}>
            Criar
          </button>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {projects.map((p) => (
            <button
              key={p.id}
              onClick={() => setSelected(p)}
              style={{
                ...chipStyle,
                borderColor: selected?.id === p.id ? "#34d399" : "#2a2e37",
                color: selected?.id === p.id ? "#34d399" : "#e6e6e6",
              }}
            >
              {p.name}
            </button>
          ))}
          {projects.length === 0 && <span style={{ opacity: 0.5 }}>nenhum projeto ainda</span>}
        </div>
      </section>

      {selected && <ProjectPanel project={selected} onError={setError} />}
    </main>
  );
}

function ProjectPanel({
  project,
  onError,
}: {
  project: Project;
  onError: (m: string) => void;
}) {
  const [materials, setMaterials] = useState<Material[]>([]);
  const [paste, setPaste] = useState("");
  const [drag, setDrag] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      setMaterials(await listMaterials(project.id));
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    }
  }, [project.id, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch assíncrono: setState ocorre pós-await
    refresh();
  }, [refresh]);

  // Polling enquanto houver material em processamento.
  useEffect(() => {
    const pending = materials.some(
      (m) => m.status === "pendente" || m.status === "processando",
    );
    if (!pending) return;
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, [materials, refresh]);

  async function sendFiles(files: FileList | File[]) {
    for (const f of Array.from(files)) {
      try {
        await uploadFile(project.id, f);
      } catch (e) {
        onError(e instanceof Error ? e.message : String(e));
      }
    }
    refresh();
  }

  async function sendPaste() {
    if (!paste.trim()) return;
    try {
      await uploadText(project.id, paste);
      setPaste("");
      refresh();
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <section style={{ ...card }}>
      <h2 style={{ fontSize: "1rem", marginTop: 0 }}>
        Material de <span style={{ color: "#34d399" }}>{project.name}</span>
      </h2>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (e.dataTransfer.files.length) sendFiles(e.dataTransfer.files);
        }}
        onClick={() => fileInput.current?.click()}
        style={{
          border: `1.5px dashed ${drag ? "#34d399" : "#3a3f4b"}`,
          borderRadius: 10,
          padding: "1.5rem",
          textAlign: "center",
          cursor: "pointer",
          background: drag ? "#12261d" : "transparent",
          marginBottom: 12,
        }}
      >
        Arraste PDF/DOCX/MD/TXT aqui, ou clique para escolher
        <input
          ref={fileInput}
          type="file"
          multiple
          accept=".pdf,.docx,.md,.txt"
          style={{ display: "none" }}
          onChange={(e) => e.target.files && sendFiles(e.target.files)}
        />
      </div>

      <div style={{ marginBottom: 16 }}>
        <textarea
          value={paste}
          onChange={(e) => setPaste(e.target.value)}
          placeholder="…ou cole texto livre aqui"
          rows={3}
          style={{ ...inputStyle, width: "100%", resize: "vertical", fontFamily: "inherit" }}
        />
        <button onClick={sendPaste} style={{ ...btnStyle, marginTop: 8 }}>
          Enviar texto
        </button>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
        <thead>
          <tr style={{ textAlign: "left", opacity: 0.6 }}>
            <th style={thtd}>Arquivo</th>
            <th style={thtd}>Tipo</th>
            <th style={thtd}>Status</th>
          </tr>
        </thead>
        <tbody>
          {materials.map((m) => (
            <tr key={m.id} style={{ borderTop: "1px solid #2a2e37" }}>
              <td style={thtd}>{m.filename}</td>
              <td style={{ ...thtd, fontFamily: "monospace", opacity: 0.7 }}>{m.source_type}</td>
              <td style={thtd}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      background: STATUS_COLOR[m.status] ?? "#9ca3af",
                      display: "inline-block",
                    }}
                  />
                  {m.status}
                </span>
              </td>
            </tr>
          ))}
          {materials.length === 0 && (
            <tr>
              <td colSpan={3} style={{ ...thtd, opacity: 0.5 }}>
                nenhum material ainda
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}

const inputStyle = {
  padding: "0.5rem 0.75rem",
  borderRadius: 8,
  border: "1px solid #2a2e37",
  background: "#0f1115",
  color: "#e6e6e6",
  flex: 1,
} as const;

const btnStyle = {
  padding: "0.5rem 1rem",
  borderRadius: 8,
  border: "1px solid #34d399",
  background: "transparent",
  color: "#34d399",
  cursor: "pointer",
} as const;

const chipStyle = {
  padding: "0.35rem 0.8rem",
  borderRadius: 999,
  border: "1px solid #2a2e37",
  background: "transparent",
  color: "#e6e6e6",
  cursor: "pointer",
} as const;

const thtd = { padding: "0.5rem 0.5rem" } as const;
