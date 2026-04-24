import { beforeEach, describe, expect, it, vi } from "vitest";
import { clearTokens, getAccessToken, setTokens } from "./auth";
import { ApiError, apiFetch } from "./api";

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("apiFetch", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("sends JSON and bearer auth by default", async () => {
    setTokens("access-token", "refresh-token");
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/suppliers", { method: "POST", json: { name: "ACME" } })).resolves.toEqual({
      ok: true,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:6200/suppliers",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ name: "ACME" }),
      }),
    );
    const headers = fetchMock.mock.calls[0][1]?.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer access-token");
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it("refreshes access token once after a 401", async () => {
    setTokens("expired", "refresh-token");
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, { status: 401 }))
      .mockResolvedValueOnce(jsonResponse({ access_token: "fresh" }))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/me")).resolves.toEqual({ ok: true });

    expect(getAccessToken()).toBe("fresh");
    expect(fetchMock).toHaveBeenCalledTimes(3);
    const retryHeaders = fetchMock.mock.calls[2][1]?.headers as Headers;
    expect(retryHeaders.get("Authorization")).toBe("Bearer fresh");
  });

  it("clears tokens when refresh fails", async () => {
    setTokens("expired", "refresh-token");
    vi.stubGlobal(
      "fetch",
      vi
        .fn<typeof fetch>()
        .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, { status: 401 }))
        .mockResolvedValueOnce(jsonResponse({ detail: "bad refresh" }, { status: 401 })),
    );

    await expect(apiFetch("/me")).rejects.toBeInstanceOf(ApiError);

    expect(getAccessToken()).toBeNull();
    expect(clearTokens).toBeDefined();
  });
});
