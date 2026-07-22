import { API_URL } from "./health";

export interface Project {
  id: number;
  name: string;
  created_at: string;
}

export interface Material {
  id: number;
  filename: string;
  source_type: string;
  status: string;
  created_at: string;
}

async function jsonOrThrow<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const detail = await resp.text().catch(() => "");
    throw new Error(`API ${resp.status}: ${detail}`);
  }
  return (await resp.json()) as T;
}

export async function listProjects(): Promise<Project[]> {
  return jsonOrThrow(await fetch(`${API_URL}/projects`, { cache: "no-store" }));
}

export async function createProject(name: string): Promise<Project> {
  return jsonOrThrow(
    await fetch(`${API_URL}/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  );
}

export async function listMaterials(projectId: number): Promise<Material[]> {
  return jsonOrThrow(
    await fetch(`${API_URL}/projects/${projectId}/materials`, {
      cache: "no-store",
    }),
  );
}

export async function uploadFile(
  projectId: number,
  file: File,
): Promise<Material> {
  const form = new FormData();
  form.append("file", file);
  return jsonOrThrow(
    await fetch(`${API_URL}/projects/${projectId}/materials`, {
      method: "POST",
      body: form,
    }),
  );
}

export async function uploadText(
  projectId: number,
  text: string,
): Promise<Material> {
  const form = new FormData();
  form.append("text", text);
  return jsonOrThrow(
    await fetch(`${API_URL}/projects/${projectId}/materials`, {
      method: "POST",
      body: form,
    }),
  );
}
