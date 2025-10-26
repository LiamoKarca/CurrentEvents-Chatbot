// utf-8-sig
import { reactive } from "vue";
import { api, setToken, getToken } from "@/services/api";

export const authState = reactive({
  authed: false,
  username: null as string | null,
  bootstrapped: false,
});

export async function bootstrapAuth() {
  if (authState.bootstrapped) return;
  const t = getToken();
  if (!t) {
    authState.authed = false;
    authState.username = null;
    authState.bootstrapped = true;
    return;
  }
  try {
    const me = await api.auth.me();
    authState.authed = true;
    authState.username = me?.username ?? null;
  } catch {
    setToken(null);
    authState.authed = false;
    authState.username = null;
  } finally {
    authState.bootstrapped = true;
  }
}

export function logout() {
  // 前端登出：清 token 與狀態，避免守衛仍判定已登入
  setToken(null);
  authState.authed = false;
  authState.username = null;
  authState.bootstrapped = true;
}