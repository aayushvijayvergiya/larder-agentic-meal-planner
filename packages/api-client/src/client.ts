import createClient, { type Client, type Middleware } from "openapi-fetch";
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];
export type GetToken = () => Promise<string | null>;

/** The API's single error envelope (LLD §2.3), surfaced as a thrown error. */
export class ApiError extends Error {
  code: string;
  status: number;
  details?: unknown;
  constructor(code: string, status: number, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export interface Api {
  baseUrl: string;
  raw: Client<paths>;
  /** Untyped convenience for the few places a path is built dynamically. Throws ApiError on non-2xx. */
  request<T = unknown>(method: string, path: string, init?: { body?: unknown; query?: Record<string, string> }): Promise<T>;
}

function toApiError(status: number, body: unknown): ApiError {
  const env = body as { error?: { code?: string; message?: string; details?: unknown } } | null;
  if (env && typeof env === "object" && env.error) {
    return new ApiError(env.error.code ?? "unknown", status, env.error.message ?? "Request failed", env.error.details);
  }
  return new ApiError(status === 401 ? "unauthorized" : "unknown", status, `Request failed with status ${status}`);
}

/** Unwraps an openapi-fetch result: returns data or throws ApiError. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || !result.response.ok) {
    throw toApiError(result.response.status, result.error);
  }
  return result.data as T;
}

/** Generated paths already carry the /api/v1 prefix, so the base URL is the API origin. A trailing /api/v1 is tolerated. */
export function createApi(baseUrl: string, getToken: GetToken, fetchImpl?: typeof fetch): Api {
  const base = baseUrl.replace(/\/$/, "").replace(/\/api\/v1$/, "");
  const raw = createClient<paths>({ baseUrl: base, fetch: fetchImpl });
  const auth: Middleware = {
    async onRequest({ request }) {
      const token = await getToken();
      if (token) request.headers.set("Authorization", `Bearer ${token}`);
      return request;
    },
  };
  raw.use(auth);
  const doFetch = fetchImpl ?? fetch;

  async function request<T>(method: string, path: string, init?: { body?: unknown; query?: Record<string, string> }) {
    const url = new URL(base + (path.startsWith("/api/") ? path : "/api/v1" + path));
    for (const [k, v] of Object.entries(init?.query ?? {})) url.searchParams.set(k, v);
    const headers = new Headers({ Accept: "application/json" });
    const token = await getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    if (init?.body !== undefined) headers.set("Content-Type", "application/json");
    const req = new Request(url.toString(), {
      method,
      headers,
      body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
    });
    const res = await doFetch(req);
    const text = await res.text();
    const body = text ? JSON.parse(text) : null;
    if (!res.ok) throw toApiError(res.status, body);
    return body as T;
  }

  return { baseUrl: base, raw, request };
}
