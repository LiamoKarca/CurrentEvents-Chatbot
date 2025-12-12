<template>
  <div class="auth-page">
    <div class="bg"></div>

    <main class="card">
      <h1 class="brand">
        <img src="/favicon.ico" alt="芒狗時事標誌" class="brand-icon" />
        <span>芒狗時事</span>
      </h1>
      <h2 class="title">建立新帳號</h2>

      <!-- 使用 Email / 密碼註冊 -->
      <form class="form" @submit.prevent="onRegister">
        <label class="field">
          <span>Email</span>
          <input v-model="email" type="email" placeholder="輸入 Email" />
        </label>

        <label class="field">
          <span>密碼</span>
          <input
            v-model="password"
            type="password"
            placeholder="輸入密碼（≥6字）"
          />
        </label>

        <button class="btn primary" :disabled="submitting">
          {{ submitting ? "建立中…" : "建立帳號" }}
        </button>

        <!-- 錯誤訊息（註冊失敗、密碼錯誤等） -->
        <p v-if="err" class="err">{{ err }}</p>

        <!-- 提示訊息（驗證信已寄出等） -->
        <p v-if="infoMsg" class="info">{{ infoMsg }}</p>
        <button
          v-if="canResendVerification"
          class="btn secondary resend-btn"
          type="button"
          @click="resendVerificationLink"
          :disabled="submitting || resendSubmitting"
        >
          {{ resendSubmitting ? "重新寄送中…" : "重新發送開通驗證" }}
        </button>
      </form>

      <!-- 第三方註冊／登入區塊：Google -->
      <div class="oauth">
        <div class="oauth-divider">
          <span>或</span>
          <span class="oauth-line"></span>
        </div>

        <button
          class="btn secondary google-btn"
          type="button"
          @click="onGoogleRegister"
          :disabled="submitting"
        >
          使用 Google 建立帳號 / 登入
        </button>
      </div>

      <p class="hint">
        已經有帳號了？
        <RouterLink to="/login" class="link">前往登入</RouterLink>
      </p>
    </main>
  </div>
</template>

<!-- 註冊邏輯、驗證邏輯、防重複註冊＋自動登入、Google 註冊／登入 -->
<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { User } from "firebase/auth";
import { authState } from "@/stores/auth";
import {
  registerWithEmail,
  signInWithGoogle,
  sendVerificationEmail,
  logout,
  signInWithEmail,
} from "@/services/firebase";
import { api } from "@/services/api";

/**
 * 表單欄位狀態
 */
const email = ref("");
const password = ref("");

/**
 * UI 狀態：是否送出中、錯誤訊息、提示訊息
 */
const submitting = ref(false);
const err = ref("");
const infoMsg = ref("");
const resendSubmitting = ref(false);
const canResendVerification = ref(false);
const lastRegisteredEmail = ref("");
const lastRegisteredPassword = ref("");

const router = useRouter();
const route = useRoute();

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

/**
 * 註冊邏輯（Email / 密碼）：
 * 1. 基本前端檢查（Email 不為空、密碼長度 ≥ 6）。
 * 2. 呼叫 Firebase 的 registerWithEmail 建立帳號。
 * 3. 建立成功後，呼叫 sendVerificationEmail 寄出驗證信（驗證邏輯）。
 * 4. 寄信完成後，為避免未驗證狀態持續登入，呼叫 logout 登出。
 * 5. 若 Email 已經存在（auth/email-already-in-use），
 *    啟動「防重複註冊＋自動登入邏輯」：改用 signInWithEmail 直接登入。
 */
async function onRegister() {
  if (submitting.value) {
    return;
  }
  err.value = "";
  infoMsg.value = "";
  canResendVerification.value = false;
  submitting.value = true;

  try {
    // ---- 基本前端檢查 ----
    const trimmedEmail = email.value.trim();
    if (!trimmedEmail) {
      err.value = "Email 不可為空。";
      return;
    }
    if (password.value.length < 6) {
      err.value = "密碼長度至少需 6 碼。";
      return;
    }

    // ---- 1. 註冊邏輯：建立 Firebase 使用者帳號（Email / 密碼） ----
    const credential = await registerWithEmail(trimmedEmail, password.value);
    const user = credential.user;

    // ---- 2. 驗證邏輯：寄送 Email 驗證信 ----
    try {
      await sendVerificationEmail(user);
      infoMsg.value =
        "驗證信已寄出，請至信箱點擊驗證連結後，再回登入頁面登入系統。";
    } catch (verifyErr: any) {
      console.error("寄送驗證信失敗：", verifyErr);
      // 驗證信寄送失敗只顯示提示，不阻擋註冊結果
      infoMsg.value =
        "帳號已建立，但驗證信寄送失敗，請稍後到登入頁再試一次寄送或聯繫管理者。";
    }

    // ---- 3. 安全處理：為避免未驗證狀態直接登入，這裡主動登出 ----
    await logout();
    lastRegisteredEmail.value = trimmedEmail;
    lastRegisteredPassword.value = password.value;
    canResendVerification.value = true;

    console.log("Registered user:", user.uid);
  } catch (e: any) {
    console.error(e);

    /**
     * 防重複註冊＋自動登入邏輯：
     * - 若錯誤碼為 auth/email-already-in-use，代表此 Email 已有帳號。
     * - 此時改用 signInWithEmail 嘗試登入：
     *   - 若密碼正確：直接登入並導回首頁。
     *   - 若密碼錯誤：顯示清楚錯誤訊息，請使用者改到登入頁使用「忘記密碼」。
     */
    if (e?.code === "auth/email-already-in-use") {
      try {
        const trimmedEmail = email.value.trim();
        const loginCred = await signInWithEmail(trimmedEmail, password.value);
        const user = loginCred.user;

        await syncBackendSession(user);
        infoMsg.value = "此 Email 已註冊，已直接為登入。";
        await router.replace(redirectTarget.value);
        return;
      } catch (loginErr: any) {
        console.error("重複註冊自動登入失敗：", loginErr);
        await logout();

        if (loginErr?.code === "auth/wrong-password") {
          err.value =
            "此 Email 已註冊，但密碼不正確，請改用登入頁並使用「忘記密碼」重設密碼。";
        } else {
          err.value =
            loginErr?.message ||
            "此 Email 已註冊，但自動登入失敗，請改到登入頁重試。";
        }
        return;
      }
    }

    // 其他錯誤：維持一般註冊失敗訊息
    err.value = e?.message || "註冊失敗";
  } finally {
    submitting.value = false;
  }
}

/**
 * Google 註冊／登入邏輯：
 * 1. 呼叫 Firebase 的 signInWithGoogle，彈出 Google OAuth 視窗。
 * 2. 第一次使用時，Firebase 會自動建立對應帳號；之後再登入會直接簽入。
 * 3. Google 帳號的 Email 由 Google 驗證，Firebase 會標記為已驗證，因此通常不需額外寄驗證信。
 */
async function onGoogleRegister() {
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
    err.value = e?.message || "Google 註冊 / 登入失敗";
  } finally {
    submitting.value = false;
  }
}

async function resendVerificationLink() {
  if (resendSubmitting.value) {
    return;
  }
  err.value = "";
  infoMsg.value = "";
  const targetEmail = lastRegisteredEmail.value || email.value.trim();
  const targetPassword = lastRegisteredPassword.value || password.value;
  if (!targetEmail || targetPassword.length < 6) {
    err.value = "請先填寫 Email 與密碼後再重新寄送驗證信。";
    return;
  }
  resendSubmitting.value = true;
  try {
    const credential = await signInWithEmail(targetEmail, targetPassword);
    await sendVerificationEmail(credential.user);
    infoMsg.value = "驗證信已重新寄出，請至信箱確認。";
  } catch (resendErr: any) {
    console.error("resend verification failed:", resendErr);
    err.value =
      resendErr?.message || "重新寄送驗證信失敗，請稍後再試或聯絡管理者。";
  } finally {
    await logout().catch(() => {});
    resendSubmitting.value = false;
    canResendVerification.value = true;
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
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  overflow: hidden;
  background: var(--bg);
}

/* 柔和漸層背景（radial-gradient） */
.bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(
      1200px 600px at 10% -10%,
      rgba(255, 210, 112, 0.45),
      transparent 60%
    ),
    radial-gradient(
      900px 500px at 90% 10%,
      rgba(255, 246, 196, 0.6),
      transparent 60%
    ),
    radial-gradient(
      1000px 700px at 50% 120%,
      rgba(255, 185, 122, 0.45),
      transparent 65%
    ),
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
.field {
  display: grid;
  gap: 8px;
}
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
  transition:
    transform 0.02s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
}
.btn.primary {
  background: linear-gradient(135deg, #ffd35c, #f4b400);
  color: #5c3b00;
  box-shadow: 0 10px 20px rgba(244, 180, 0, 0.35);
}
.btn.primary:hover {
  transform: translateY(-1px);
}

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

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.resend-btn {
  margin-top: 8px;
  width: 100%;
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

/* Google 按鈕全寬 */
.google-btn {
  width: 100%;
}

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
.link:hover {
  text-decoration: underline;
}

@media (max-width: 520px) {
  .card {
    padding: 32px 24px;
  }
}
</style>
