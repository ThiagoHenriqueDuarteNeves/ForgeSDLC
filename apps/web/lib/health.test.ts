import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchHealth } from "./health";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("fetchHealth", () => {
  it("retorna o status quando a API responde 200", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "ok", service: "forge-api", version: "0.1.0" }),
      }),
    );

    const health = await fetchHealth("http://api.test");
    expect(health.status).toBe("ok");
    expect(health.service).toBe("forge-api");
  });

  it("lança quando a API responde erro", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 503 }),
    );

    await expect(fetchHealth("http://api.test")).rejects.toThrow("503");
  });
});
