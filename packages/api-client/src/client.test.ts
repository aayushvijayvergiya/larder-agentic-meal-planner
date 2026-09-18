import { describe, expect, it, vi } from "vitest";
import { ApiError, createApi, unwrap } from "./client";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

describe("createApi", () => {
  it("adds the bearer token and converts the error envelope", async () => {
    const fetchMock = vi.fn(async (req: Request) => {
      expect(req.headers.get("authorization")).toBe("Bearer t");
      return json({ error: { code: "conflict", message: "dup", details: null } }, 409);
    });
    const api = createApi("http://x/api/v1/", async () => "t", fetchMock as unknown as typeof fetch);
    expect(api.baseUrl).toBe("http://x/api/v1");
    await expect(api.request("GET", "/pantry")).rejects.toMatchObject({ code: "conflict", status: 409, message: "dup" });
  });

  it("returns parsed json on success and sends json bodies", async () => {
    const fetchMock = vi.fn(async (req: Request) => {
      expect(req.method).toBe("POST");
      expect(req.headers.get("content-type")).toBe("application/json");
      expect(await req.json()).toEqual({ items: [{ name: "onion" }] });
      return json({ created: [], existing: [] }, 201);
    });
    const api = createApi("http://x", async () => null, fetchMock as unknown as typeof fetch);
    await expect(api.request("POST", "/pantry/items", { body: { items: [{ name: "onion" }] } })).resolves.toEqual({
      created: [],
      existing: [],
    });
  });

  it("typed client attaches the token through middleware", async () => {
    const fetchMock = vi.fn(async (req: Request) => {
      expect(req.headers.get("authorization")).toBe("Bearer typed");
      return json({ status: "ok", database: "ok", llm_provider: "fake" });
    });
    const api = createApi("http://x", async () => "typed", fetchMock as unknown as typeof fetch);
    const res = await api.raw.GET("/api/v1/health");
    expect(unwrap(res)).toMatchObject({ status: "ok" });
  });

  it("unwrap throws ApiError with a fallback message when the body is not an envelope", () => {
    const res = { data: undefined, error: "nope", response: new Response(null, { status: 500 }) };
    expect(() => unwrap(res)).toThrow(ApiError);
  });
});
