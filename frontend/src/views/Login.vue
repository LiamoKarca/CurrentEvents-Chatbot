<!-- utf-8-sig -->
<template>
  <div class="auth-page">
    <div class="bg"></div>

    <main class="card">
      <h1 class="brand">
        <img src="/favicon.ico" alt="芒狗時事標誌" class="brand-icon" />
        <span>芒狗時事</span>
      </h1>
      <h2 class="title">登入帳號</h2>

      <form class="form" @submit.prevent="onLogin">
        <label class="field">
          <span>帳號</span>
          <input v-model="username" placeholder="輸入帳號（3–32字）" />
        </label>

        <label class="field">
          <span>密碼</span>
          <input v-model="password" type="password" placeholder="輸入密碼（≥6字）" />
        </label>

        <button class="btn primary" :disabled="submitting">
          {{ submitting ? '登入中…' : '登入' }}
        </button>

        <p v-if="err" class="err">{{ err }}</p>
      </form>

      <p class="hint">
        還沒有帳號？
        <RouterLink to="/register" class="link">建立新帳號</RouterLink>
      </p>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { api } from "@/services/api";
import { authState } from "@/stores/auth";

const username = ref("");
const password = ref("");
const submitting = ref(false);
const err = ref("");

async function onLogin() {
  if (submitting.value) return;
  err.value = "";
  submitting.value = true;
  try {
    const r = await api.auth.login(username.value.trim(), password.value);
    authState.username = r.username;
    authState.authed = true;
    window.location.href = "/";
  } catch (e: any) {
    err.value = e?.message || "登入失敗";
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
.btn:disabled { opacity: .6; cursor: not-allowed; }

/* 訊息／連結 */
.err {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--danger);
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
