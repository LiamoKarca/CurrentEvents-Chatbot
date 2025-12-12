<template>
  <div class="auth-page">
    <div class="bg"></div>

    <main class="card">
      <h1 class="brand">
        <img src="/favicon.ico" alt="芒狗時事標誌" class="brand-icon" />
        <span>芒狗時事</span>
      </h1>
      <h2 class="title">登入帳號</h2>

      <!-- 使用 mail 登入 -->
      <form class="form" @submit.prevent="onLogin">
        <label class="field">
          <span>Email</span>
          <input v-model="email" type="email" placeholder="輸入 Email" />
        </label>

        <label class="field">
          <span>密碼</span>
          <input v-model="password" type="password" placeholder="輸入密碼（≥6字）" />
        </label>

        <button class="btn primary" :disabled="submitting">
          {{ submitting ? '登入中…' : '登入' }}
        </button>

        <p v-if="err" class="err">{{ err }}</p>
        <p v-if="infoMsg" class="info">{{ infoMsg }}</p>
      </form>

      <!-- 第三方登入區塊：Google -->
      <div class="oauth">
        <div class="oauth-divider">
          <span>或</span>
          <span class="oauth-line"></span>
        </div>

        <button
          class="btn secondary google-btn"
          type="button"
          @click="onGoogleLogin"
          :disabled="submitting"
        >
          使用 Google 登入
        </button>
      </div>

      <p class="hint">
        還沒有帳號？
        <RouterLink to="/register" class="link">建立新帳號</RouterLink>
      </p>
    </main>
  </div>
</template>

<!--登入邏輯-->
<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { User } from "firebase/auth";
import { authState } from "@/stores/auth";
import {
  signInWithEmail,
  signInWithGoogle,
  logout,
  sendVerificationEmail,
} from "@/services/firebase";
import { api } from "@/services/api";

const router = useRouter();
const route = useRoute();

const email = ref("");
const password = ref("");
const submitting = ref(false);
const err = ref("");
const infoMsg = ref("");

const redirectTarget = computed(() => {
  const q = route.query.redirect;
  return typeof q === "string" && q ? q : "/";
});

async function syncBackendSession(user: User) {
  const idToken = await user.getIdToken();
  const resp = await api.auth.firebaseLogin(idToken);
  const display = user.displayName || user.email || "";
  authState.username = resp?.username || display;
  authState.authed = true;
}

async function onLogin() {
  if (submitting.value) {
    return;
  }
  err.value = "";
  infoMsg.value = "";
  submitting.value = true;
  try {
    const credential = await signInWithEmail(
      email.value.trim(),
      password.value,
    );
    const user = credential.user;

    if (!user.emailVerified) {
      try {
        await sendVerificationEmail(user);
        infoMsg.value = "Email 尚未驗證，已重新寄出驗證信，請查收信件後再登入。";
      } catch (sendErr: any) {
        console.error("resend verification on login failed:", sendErr);
        err.value =
          sendErr?.message ||
          "Email 尚未驗證，且驗證信重送失敗，請稍後再試或聯絡管理者。";
      } finally {
        await logout();
      }
      if (!err.value) {
        err.value = "Email 尚未驗證，請完成驗證後再登入。";
      }
      return;
    }

    await syncBackendSession(user);
    await router.replace(redirectTarget.value);
  } catch (e: any) {
    console.error(e);
    await logout();
    err.value = e?.message || "登入失敗";
  } finally {
    submitting.value = false;
  }
}

async function onGoogleLogin() {
  if (submitting.value) {
    return;
  }
  err.value = "";
  infoMsg.value = "";
  submitting.value = true;
  try {
    const credential = await signInWithGoogle();
    const user = credential.user;
    await syncBackendSession(user);
    await router.replace(redirectTarget.value);
  } catch (e: any) {
    console.error(e);
    await logout();
    err.value = e?.message || "Google 登入失敗";
  } finally {
    submitting.value = false;
  }
}
</script>


<style scoped>
/* ===== 色票 ===== */
:root {
  --bg: #fff9eb;
  --bg-accent: #fff2cc;
  --card: #fffdf7;
  --text: #5c3b00;
  --muted: #a0772a;
  --primary: #f4b400;
  --primary-weak: #ffe193;
  --danger: #d65329;
  --border: #f3d6a2;
  --input-bg: #fff6de;
}

/* ===== 版面：全頁置中 ===== */
.auth-page {
  position: relative;
  min-height: 100vh;                 /* 讓 flex 置中可充滿高度（配合 justify/align） */
  display: flex;
  align-items: center;               /* 垂直置中（cross axis） */
  justify-content: center;           /* 水平置中（main axis） */
  padding: 24px;
  overflow: hidden;
  background: var(--bg);
}

/* 柔和漸層背景（radial-gradient） */
.bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(1200px 600px at 10% -10%, rgba(255, 210, 112, 0.45), transparent 60%),
    radial-gradient(900px 500px at 90% 10%, rgba(255, 246, 196, 0.6), transparent 60%),
    radial-gradient(1000px 700px at 50% 120%, rgba(255, 185, 122, 0.45), transparent 65%),
    linear-gradient(180deg, #fff7df, #ffe8aa 40%, #ffd36f 100%);
  filter: saturate(105%);
  z-index: 0;
}

/* 卡片 */
.card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 480px;
  padding: 40px 48px;
  border-radius: 16px;
  background: var(--card);
  color: var(--text);
  box-shadow:
    0 16px 40px rgba(199, 145, 48, 0.15),
    0 2px 12px rgba(92, 59, 0, 0.08);
  border: 1px solid var(--border);
}

/* 標題 */
.brand {
  margin: 0 auto 12px;
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 0.2px;
  color: var(--text);
  text-align: center;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.brand-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  box-shadow: 0 2px 6px rgba(92, 59, 0, 0.2);
}

.title {
  margin: 0 0 20px;
  font-size: 18px;
  font-weight: 700;
  color: #744400;
  text-align: center;
}

/* 表單 */
.form {
  display: grid;
  gap: 18px;
}
.field { display: grid; gap: 8px; }
.field > span {
  font-size: 13px;
  color: var(--muted);
}
.field input {
  width: 100%;
  height: 42px;
  padding: 0 18px;
  border-radius: 14px;
  border: 2px solid rgba(244, 180, 0, 0.5);
  background: var(--input-bg);
  color: var(--text);
  outline: none;
  box-sizing: border-box;
}
.field input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(244, 180, 0, 0.25);
}

/* 按鈕 */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 44px;
  padding: 0 16px;
  border-radius: 12px;
  border: 1px solid transparent;
  font-weight: 700;
  cursor: pointer;
  transition: transform .02s ease, box-shadow .2s ease, background .2s ease;
}
.btn.primary {
  background: linear-gradient(135deg, #ffd35c, #f4b400);
  color: #5c3b00;
  box-shadow: 0 10px 20px rgba(244, 180, 0, 0.35);
}
.btn.primary:hover { transform: translateY(-1px); }

/* 次要按鈕（Google 登入） */
.btn.secondary {
  background: #ffffff;
  color: var(--text);
  border-color: var(--border);
  box-shadow: 0 4px 10px rgba(92, 59, 0, 0.08);
}
.btn.secondary:hover {
  transform: translateY(-1px);
}

/* OAuth 區塊 */
.oauth {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.oauth-divider {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--muted);
  justify-content: center;
}

.oauth-line {
  flex: 1;
  height: 1px;
  border-radius: 999px;
  background: rgba(160, 119, 42, 0.35);
}

/* 針對 Google 做一點細微間距調整 */
.google-btn {
  width: 100%;
}

.btn:disabled { opacity: .6; cursor: not-allowed; }

/* 訊息／連結 */
.err {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--danger);
  text-align: center;
}
.info {
  margin: 6px 0 0;
  font-size: 13px;
  color: #62741b;
  text-align: center;
}
.hint {
  margin: 14px 0 0;
  font-size: 14px;
  color: var(--muted);
  text-align: center;
}
.link {
  color: #c47800;
  text-decoration: none;
  font-weight: 700;
}
.link:hover { text-decoration: underline; }

@media (max-width: 520px) {
  .card {
    padding: 32px 24px;
  }
}
</style>
