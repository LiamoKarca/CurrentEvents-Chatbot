<!-- utf-8-sig -->
<template>
  <div class="auth-page">
    <div class="bg"></div>

    <main class="card">
      <h1 class="brand">💬 ChatBot</h1>
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
  --bg: #0b1220;
  --bg-accent: #0b1220;
  --card: #ffffff;
  --text: #0f172a;
  --muted: #64748b;
  --primary: #2563eb;
  --primary-weak: #93c5fd;
  --danger: #dc2626;
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
}

/* 柔和漸層背景（radial-gradient） */
.bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(1200px 600px at 10% -10%, #c7d2fe33, transparent 60%),
    radial-gradient(900px 500px at 90% 10%, #a7f3d033, transparent 60%),
    radial-gradient(1000px 700px at 50% 120%, #fbcfe833, transparent 60%),
    linear-gradient(180deg, #f8fafc, #eef2ff 40%, #e0f2fe 100%);
  filter: saturate(110%);
  z-index: 0;
}

/* 卡片 */
.card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 420px;
  padding: 28px 26px;
  border-radius: 16px;
  background: var(--card);
  color: var(--text);
  box-shadow:
    0 10px 30px rgba(15, 23, 42, 0.12),
    0 2px 10px rgba(15, 23, 42, 0.06);
  border: 1px solid #e5e7eb;
}

/* 標題 */
.brand {
  margin: 0 0 6px;
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 0.2px;
  color: #0f172a;
  text-align: center;
}
.title {
  margin: 0 0 20px;
  font-size: 18px;
  font-weight: 700;
  color: #1f2937;
  text-align: center;
}

/* 表單 */
.form { display: grid; gap: 14px; }
.field { display: grid; gap: 8px; }
.field > span {
  font-size: 13px;
  color: var(--muted);
}
.field input {
  width: 100%;
  height: 42px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #0f172a;
  outline: none;
}
.field input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
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
  background: var(--primary);
  color: #fff;
  box-shadow: 0 6px 18px rgba(37, 99, 235, 0.25);
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
  color: var(--primary);
  text-decoration: none;
  font-weight: 700;
}
.link:hover { text-decoration: underline; }
</style>
