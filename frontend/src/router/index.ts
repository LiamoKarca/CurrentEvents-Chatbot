// utf-8-sig
import { createRouter, createWebHistory } from "vue-router";
import type { RouteRecordRaw } from "vue-router";
import ChatUI from "../chat_page/ChatUI.vue";
import Login from "../views/Login.vue";
import Register from "../views/Register.vue";
import { authState, bootstrapAuth } from "../stores/auth";

const routes: RouteRecordRaw[] = [
  { path: "/", name: "Chat", component: ChatUI, meta: { requiresAuth: true } },
  { path: "/login", name: "Login", component: Login, meta: { guestOnly: true } },
  { path: "/register", name: "Register", component: Register, meta: { guestOnly: true } },
  { path: "/:pathMatch(.*)*", redirect: "/" },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

let didBootstrap = false;

router.beforeEach(async (to) => {
  if (!didBootstrap) {
    await bootstrapAuth();
    didBootstrap = true;
  }
  const authed = authState.authed;

  if (to.matched.some((r) => r.meta?.requiresAuth) && !authed) {
    // 用 return 導向（等價 next('/login')），避免在守衛裡呼叫 router.push()
    return { path: "/login", query: { redirect: to.fullPath } };
  }
  if (to.matched.some((r) => r.meta?.guestOnly) && authed) {
    return { path: "/" };
  }
  return true;
});

export default router;
