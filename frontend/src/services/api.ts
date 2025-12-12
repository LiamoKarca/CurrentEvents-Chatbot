// utf-8-sig
// Simple API wrapper with bearer token.

export const API_BASE =
  (import.meta.env.VITE_API_BASE as string) || "http://127.0.0.1:8000";

export function setToken(token: string | null) {
  if (token) localStorage.setItem("token", token);
  else localStorage.removeItem("token");
}

export function getToken(): string | null {
  return localStorage.getItem("token");
}

/**
 * 更聰明的 req():
 * - 不強制 JSON：若 body 是 FormData / URLSearchParams，就不要塞 Content-Type
 * - 友善錯誤訊息：把 FastAPI 的 {detail:[...]} 或 {detail:"..."} 展開成人話
 */
async function req(path: string, opts: RequestInit = {}) {
  const headers: Record<string, string> = {
    ...(opts.headers as Record<string, string>),
  };

  // 自動帶入 Bearer
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  // 除非外部已指定 Content-Type，否則預設為 JSON
  const body = (opts as any).body;
  const isFormBody =
    typeof FormData !== "undefined" && body instanceof FormData;
  const isUrlEncoded =
    typeof URLSearchParams !== "undefined" && body instanceof URLSearchParams;

  if (!headers["Content-Type"] && !isFormBody && !isUrlEncoded) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, { ...opts, headers });

  if (!res.ok) {
    // 優先嘗試 JSON 錯誤物件
    let msg = "";
    try {
      const j = await res.clone().json();
      if (Array.isArray(j?.detail)) {
        // FastAPI 422 常見: detail: [{loc, msg, type}, ...]
        msg = j.detail
          .map((d: any) => d?.msg || d?.detail || JSON.stringify(d))
          .join("\n");
      } else if (j?.detail) {
        msg =
          typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
      } else {
        msg = JSON.stringify(j);
      }
    } catch {
      try {
        msg = await res.text();
      } catch {
        /* ignore */
      }
    }
    throw new Error(msg || `HTTP ${res.status}`);
  }

  // 成功回應
  return res.json();
}

export const api = {
  auth: {
    async register(username: string, password: string) {
      // 後端 register 接 JSON（Pydantic 模型）
      const r = await req("/api/v1/auth/register", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      if (r?.access_token) setToken(r.access_token);
      return r;
    },

    async login(username: string, password: string) {
      // ✅ 後端 login 亦接 JSON（Pydantic 模型）
      const r = await req("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      if (r?.access_token) setToken(r.access_token);
      return r;
    },

    async me() {
      return req("/api/v1/auth/me");
    },

    async firebaseLogin(idToken: string) {
      const r = await req("/api/v1/auth/firebase-login", {
        method: "POST",
        body: JSON.stringify({ id_token: idToken }),
      });
      if (r?.access_token) setToken(r.access_token);
      return r;
    },
  },

  chats: {
    async save(
      messages: Array<{ role: string; content: string }>,
      title?: string,
      chatId?: string
    ) {
      // 已有 chatId 時，不要再送 title，避免後端視為新檔；payload 僅含 chat_id + messages
      const payload: any = { messages };
      if (chatId) payload.chat_id = chatId;
      else if (title) payload.title = title;
      return req("/api/v1/chats/save", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    async list() {
      return req("/api/v1/chats/list");
    },
    async get(chatId: string) {
      return req(`/api/v1/chats/${chatId}`);
    },
    async delete(chatId: string) {
      return req(`/api/v1/chats/${chatId}`, { method: "DELETE" });
    },
  },

  summary: {
    async highlights(range: "daily" | "weekly" = "daily", limit = 3) {
      const params = new URLSearchParams();
      params.set("range", range);
      params.set("limit", String(limit));
      return req(`/api/v1/highlights?${params.toString()}`);
    },
  },
};
