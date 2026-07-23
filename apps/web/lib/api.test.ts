import { afterEach, describe, expect, it, vi } from "vitest";

import { createProject, criarNota, listarNotas, uploadText } from "./api";

afterEach(() => vi.restoreAllMocks());

describe("api client", () => {
  it("createProject envia POST com o nome", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, name: "P", created_at: "now" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const p = await createProject("P");
    expect(p.id).toBe(1);
    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body).name).toBe("P");
  });

  it("uploadText manda o texto como form-data", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 2,
        filename: "texto colado",
        source_type: "paste",
        status: "pendente",
        created_at: "now",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const m = await uploadText(5, "conteudo");
    expect(m.source_type).toBe("paste");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/projects/5/materials");
    expect(init.body).toBeInstanceOf(FormData);
  });

  it("criarNota faz POST com o texto (fatia F-EX01)", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 7, text: "oi", created_at: "now" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const n = await criarNota(3, "oi");
    expect(n.id).toBe(7);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/projects/3/notes");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body).text).toBe("oi");
  });

  it("listarNotas faz GET no endpoint do projeto", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ id: 1, text: "n", created_at: "now" }],
    });
    vi.stubGlobal("fetch", fetchMock);

    const lista = await listarNotas(9);
    expect(lista).toHaveLength(1);
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/projects/9/notes");
  });

  it("envia os headers que pulam o interstitial do zrok", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
    vi.stubGlobal("fetch", fetchMock);

    await listarNotas(1);
    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers["skip-zrok-interstitial"]).toBe("true");
    expect(init.headers["zrok-skip-interstitial"]).toBe("true");
  });

  it("mantem o Content-Type ao somar os headers do tunel", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, name: "P", created_at: "now" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await createProject("P");
    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(init.headers["skip-zrok-interstitial"]).toBe("true");
  });

  it("lanca em resposta de erro", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 400, text: async () => "ruim" }),
    );
    await expect(createProject("x")).rejects.toThrow("400");
  });
});
