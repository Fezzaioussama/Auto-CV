import axios, { AxiosError } from "axios";

// The SPA is served by Flask at the same origin, so relative URLs are fine.
// In Vite dev the proxy in vite.config.ts forwards these to Flask at :5000.
export const api = axios.create({
  baseURL: "",
  withCredentials: true,
  // LLM-backed endpoints (parse-job, optimize-cv, …) can take 30–90s on slow
  // reasoning models. 0 disables the client-side timeout — the server's
  // LLM_TIMEOUT is the only ceiling.
  timeout: 0,
  headers: { "X-Requested-With": "XMLHttpRequest" },
});

let csrfToken: string | null = null;

async function fetchCsrfToken(): Promise<string> {
  // Flask-WTF emits a fresh token from /api/csrf-token (added by us in the
  // Flask side). We cache it in-memory; the cookie keeps it stable across
  // page reloads, but we still re-fetch on demand if a request gets a 400.
  const res = await axios.get("/api/csrf-token", { withCredentials: true });
  csrfToken = res.data?.csrf_token || null;
  return csrfToken || "";
}

api.interceptors.request.use(async (config) => {
  const method = (config.method || "get").toLowerCase();
  if (["post", "put", "patch", "delete"].includes(method)) {
    if (!csrfToken) {
      try {
        await fetchCsrfToken();
      } catch {
        /* token endpoint may not be reachable on first load; ignore */
      }
    }
    if (csrfToken) {
      config.headers = config.headers || {};
      (config.headers as Record<string, string>)["X-CSRFToken"] = csrfToken;
    }
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError<{ error?: string; code?: string }>) => {
    if (error.response?.status === 400 && csrfToken) {
      // CSRF token may have rotated — refresh and retry once.
      csrfToken = null;
      try {
        await fetchCsrfToken();
      } catch {
        /* ignore */
      }
    }
    return Promise.reject(error);
  },
);

export function apiErrorMessage(err: unknown, fallback = "Something went wrong."): string {
  const e = err as AxiosError<{ error?: string; message?: string }>;
  return e?.response?.data?.error || e?.response?.data?.message || e?.message || fallback;
}
