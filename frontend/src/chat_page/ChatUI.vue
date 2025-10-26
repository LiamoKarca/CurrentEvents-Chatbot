<!-- utf-8-sig -->
<template>
  <div class="layout">
    <!-- 左側：會話清單 -->
    <aside
      class="sidebar"
      :class="{ hidden: sidebarHidden }"
      aria-label="會話清單側欄"
      :aria-hidden="sidebarHidden"
    >
      <header class="side-head">
        <div class="brand">💬 ChatBot</div>
        <div class="side-head-actions">
          <button class="btn ghost xs" @click="onLogout" title="登出">登出</button>
          <button class="btn ghost xs" @click="refreshList" :disabled="loadingList" title="重整清單">重整</button>
        </div>
      </header>

      <div class="side-actions">
        <button class="btn primary block" @click="newChat">＋ 新對話</button>
        <!-- 自動保存；隱藏舊的手動保存按鈕 -->
        <button class="btn block" style="display:none">💾 保存聊天</button>
      </div>

      <div class="side-list" v-if="history.length">
        <a
          v-for="item in history"
          :key="item.chat_id"
          href="#"
          class="side-item"
          :class="{ active: item.chat_id === currentChatId }"
          @click.prevent="loadChat(item.chat_id)"
          :title="`${item.title}（${item.created_at}）`"
        >
          <div class="row">
            <div class="title">{{ item.title }}</div>
            <button
              class="icon del"
              title="刪除聊天"
              @click.stop="deleteChat(item.chat_id)"
              :disabled="deletingId === item.chat_id"
            >
              🗑
            </button>
          </div>
          <div class="meta">{{ item.created_at }}</div>
        </a>
      </div>

      <div v-else class="side-empty">尚無保存的聊天</div>

      <!-- 左下角：目前登入帳號 -->
      <footer class="side-foot">
        <div class="me-label">登入帳號</div>
        <div class="me-name" :title="me || '未登入'">{{ me || '（未登入）' }}</div>
      </footer>
    </aside>

    <!-- 右側：聊天主畫面 -->
    <main class="main">
      <header class="topbar">
        <button
          class="btn ghost xs only-mobile"
          @click="toggleSidebar"
          :aria-expanded="!sidebarHidden"
          aria-label="切換側欄"
          title="切換側欄"
        >
          ☰
        </button>
        <div class="top-title">
          <strong>{{ currentTitle || '新對話' }}</strong>
        </div>
        <div class="top-actions">
          <!-- 頂部也能一鍵開新對話 -->
          <button
            class="btn ghost"
            @click="newChat"
            :disabled="loading"
            title="新對話（Ctrl/Cmd + N）"
          >
            新對話
          </button>
          <button class="btn ghost" @click="clearChat" :disabled="loading || messages.length === 0">
            清除
          </button>
        </div>
      </header>

      <!-- 手機：側欄展開時顯示遮罩，點擊可關閉 -->
      <div
        v-if="!sidebarHidden"
        class="backdrop only-mobile"
        aria-hidden="true"
        @click="closeSidebar"
      ></div>

      <section class="chat-body" ref="bodyEl">
        <div v-if="messages.length === 0" class="empty">
          開始輸入訊息與 ChatBot 對話吧！
        </div>

        <div
          v-for="m in messages"
          :key="m.id"
          class="msg-row"
          :class="m.role === 'bot' ? 'is-bot' : 'is-user'"
        >
          <div v-if="m.role === 'bot'" class="avatar bot">🤖</div>
          <div class="bubble">
            <div class="meta">
              <span class="who">{{ m.role === 'bot' ? 'Bot' : '我' }}</span>
              <span class="time">{{ m.time }}</span>
            </div>
            <div class="text" v-text="m.text"></div>
          </div>
        </div>
      </section>

      <footer class="composer">
        <!-- 附件列（有選檔時顯示） -->
        <div v-if="selectedFiles.length" class="attachments">
          <div
            v-for="(f, i) in selectedFiles"
            :key="f.name + i"
            class="chip"
            :title="f.name"
          >
            <span class="chip-name">{{ f.name }}</span>
            <button class="chip-x" @click="removeFile(i)" :disabled="loading">×</button>
          </div>
        </div>

        <div class="composer-inner">
          <button class="btn icon ghost" title="附加檔案" @click="openFilePicker" :disabled="loading">
            +
          </button>
          <input ref="fileInput" type="file" class="file-input" multiple @change="onFilesSelected" />

          <input
            v-model="inputText"
            class="composer-input"
            type="text"
            :placeholder="loading ? '處理中…' : '輸入訊息…'"
            :disabled="loading"
            @keyup.enter="send"
          />
          <button
            class="btn send"
            @click="send"
            :disabled="loading || (!inputText.trim() && selectedFiles.length === 0)"
          >
            傳送
          </button>
        </div>
      </footer>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted, computed } from "vue";
import { useRouter } from "vue-router";
import { API_BASE, USER_ID } from "@/config";
import { api } from "@/services/api";
import { logout as authLogout, authState } from "@/stores/auth";

/** ====== JWT & /auth/me ====== */
function getToken(): string | null {
  try { return localStorage.getItem("token"); } catch { return null; }
}
async function fetchMe(): Promise<string | null> {
  try {
    const token = getToken();
    if (!token) return null;
    const resp = await fetch(`${API_BASE}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!resp.ok) return null;
    const data = await resp.json();
    return data?.username || null;
  } catch { return null; }
}

/** ====== 型別 ====== */
type Msg = { id: string; role: "user" | "bot"; text: string; time: string };
type HistoryRow = { chat_id: string; title: string; created_at: string };

const router = useRouter();

const messages = ref<Msg[]>([]);
const inputText = ref("");
const loading = ref(false);
const bodyEl = ref<HTMLElement | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const selectedFiles = ref<File[]>([]);

/** 重要：RWD 側欄狀態（手機預設收起） */
const sidebarHidden = ref(true);

/** 會話清單 */
const history = ref<HistoryRow[]>([]);
const loadingList = ref(false);
const deletingId = ref<string | null>(null);

// 讓同一個瀏覽分頁期間保持 chat_id，不會因為某些流程重設而遺失
const currentChatId = ref<string | null>(sessionStorage.getItem("currentChatId") || null);
const currentTitle = ref<string | null>(null);

/** 登入者 */
const me = ref<string | null>(null);

// 自動保存模式不再需要本地簽名去重

function nowHM() {
  const d = new Date();
  const hh = `${d.getHours()}`.padStart(2, "0");
  const mm = `${d.getMinutes()}`.padStart(2, "0");
  return `${hh}:${mm}`;
}

function addMessage(role: "user" | "bot", text: string) {
  messages.value.push({
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    text,
    time: nowHM(),
  });
}

function openFilePicker() { fileInput.value?.click(); }
function onFilesSelected(e: Event) {
  const input = e.target as HTMLInputElement;
  const files = input.files;
  if (!files || files.length === 0) return;
  selectedFiles.value = Array.from(files);
  input.value = ""; // 允許重選
}
function removeFile(index: number) { selectedFiles.value.splice(index, 1); }

/** ====== 後端：聊天 ====== */
async function send() {
  if (loading.value) return;
  const text = inputText.value.trim();
  if (!text && selectedFiles.value.length === 0) return;

  if (text) addMessage("user", text);
  if (!text && selectedFiles.value.length > 0) addMessage("user", "（附帶檔案）");

  loading.value = true;
  try {
    let reply = "（無回覆內容）";
    const token = getToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    if (selectedFiles.value.length > 0) {
      const fd = new FormData();
      fd.append("user_id", USER_ID);
      fd.append("message", text);
      // ✅ 告訴後端這次對話屬於哪個原檔（兩個鍵同送以兼容）
      if (currentChatId.value) {
        fd.append("chat_id", currentChatId.value);
        fd.append("conversation_id", currentChatId.value);
      }
      selectedFiles.value.forEach((f) => fd.append("files", f));
      const resp = await fetch(`${API_BASE}/api/v1/chat/with-attachments`, { method: "POST", headers, body: fd });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      reply = typeof data?.reply === "string" ? data.reply : reply;
      // ✅ 後端若回傳 chat_id/title，就即時更新並固化
      const rid = pickChatId(data);
      if (rid) {
        currentChatId.value = rid;
        sessionStorage.setItem("currentChatId", rid);
      }
      const rtitle = pickTitle(data, currentTitle.value);
      if (rtitle) currentTitle.value = rtitle;
      selectedFiles.value = [];
    } else {
      const resp = await fetch(`${API_BASE}/api/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({
          user_id: USER_ID,
          message: text,
          // ✅ 同步帶上 chat_id / conversation_id，避免後端另開新檔
          chat_id: currentChatId.value || undefined,
          conversation_id: currentChatId.value || undefined,
        }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      reply = typeof data?.reply === "string" ? data.reply : reply;
      // ✅ 吃回傳的 chat_id/title（若後端有回）
      const rid = pickChatId(data);
      if (rid) {
        currentChatId.value = rid;
        sessionStorage.setItem("currentChatId", rid);
      }
      const rtitle = pickTitle(data, currentTitle.value);
      if (rtitle) currentTitle.value = rtitle;
    }

    if (text) inputText.value = "";
    addMessage("bot", reply);
    // ✅ 送出即自動保存（建立或續寫原檔）
    await autoSaveUpsert();
    await refreshList();
  } catch (err) {
    addMessage("bot", "抱歉，剛剛處理時出了點問題。");
  } finally {
    loading.value = false;
  }
}

/** 清空當前聊天（不影響已保存的歷史） */
async function clearChat() {
  messages.value = [];
  inputText.value = "";
  selectedFiles.value = [];
  currentChatId.value = null;
  sessionStorage.removeItem("currentChatId");
  currentTitle.value = null;

  try {
    const token = getToken();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    await fetch(`${API_BASE}/api/v1/memory/clear`, { method: "POST", headers, body: JSON.stringify({ user_id: USER_ID }) });
  } catch { /* 靜默 */ }
}

/** 新對話：重置右側編輯區 */
function newChat() { clearChat(); }

/** 鍵盤快捷鍵：Ctrl/Cmd + N 開新對話 + Esc 關側欄（手機） */
function onKeydown(e: KeyboardEvent) {
  const isMac = navigator.platform.toLowerCase().includes("mac");
  const hitNew = (isMac ? e.metaKey : e.ctrlKey) && e.key.toLowerCase() === "n";
  if (hitNew) {
    e.preventDefault();
    if (!loading.value) newChat();
    return;
  }
  if (e.key === "Escape") closeSidebar();
}

function toggleSidebar() {
  sidebarHidden.value = !sidebarHidden.value;
}
function closeSidebar() {
  sidebarHidden.value = true;
}

// ===== Lifecycle =====

/** 自動保存（upsert）：第一次建立；其後一律續寫同一 chat_id */
async function autoSaveUpsert() {
  if (messages.value.length === 0) return;
  const payload = messages.value.map((m) => ({
    role: m.role === "bot" ? "assistant" : "user",
    content: m.text,
  }));
  if (currentChatId.value) {
    // 續寫：不傳 title
    const r = await api.chats.save(payload, undefined, currentChatId.value);
    // 容錯抓 id/title
    const id = pickChatId(r) || currentChatId.value;
    const title = pickTitle(r, currentTitle.value);
    currentChatId.value = id;
    currentTitle.value = title;
    if (id) sessionStorage.setItem("currentChatId", id);
  } else {
    // 首次：用第一則使用者訊息當標題
    const firstUser = messages.value.find((m) => m.role === "user");
    const titleSeed = (firstUser?.text || "新對話").trim().slice(0, 20);
    const r = await api.chats.save(payload, titleSeed, undefined);
    const id = pickChatId(r);
    const title = pickTitle(r, titleSeed);
    currentChatId.value = id;
    currentTitle.value = title;
    if (id) sessionStorage.setItem("currentChatId", id);
  }
}

/** 刪除某筆聊天（需要後端提供 DELETE /api/v1/chats/{chat_id}） */
async function deleteChat(chatId: string) {
  const ok = confirm("確定要刪除此筆聊天紀錄嗎？");
  if (!ok) return;
  deletingId.value = chatId;
  try {
    if (typeof api.chats.delete === "function") {
      await api.chats.delete(chatId);
    } else {
      // 若尚未實作 api.chats.delete，提供提示
      alert("後端未提供刪除 API：請新增 DELETE /api/v1/chats/{chat_id}");
      return;
    }
    // UI 刷新
    if (currentChatId.value === chatId) {
      clearChat();
    }
    await refreshList();
  } catch (e) {
    alert("刪除失敗，請稍後再試。");
  } finally {
    deletingId.value = null;
  }
}

/** 讀取歷史列表 */
async function refreshList() {
  loadingList.value = true;
  try {
    const r = await api.chats.list();
    // 去重 + 排序（新到舊）
    const map = new Map<string, HistoryRow>();
    for (const x of (r.items || [])) {
      if (!x?.chat_id) continue;
      if (!map.has(x.chat_id)) {
        map.set(x.chat_id, {
          chat_id: x.chat_id,
          title: x.title,
          created_at: x.created_at,
        });
      }
    }
    history.value = Array.from(map.values()).sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  } finally {
    loadingList.value = false;
  }
}

/** 載入某筆聊天 */
async function loadChat(chatId: string) {
  try {
    const data = await api.chats.get(chatId);
    const items: Msg[] = (data.messages || []).map((m: any) => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      role: m.role === "assistant" ? "bot" : "user",
      text: m.content,
      time: nowHM(),
    }));
    messages.value = items;
    currentChatId.value = data.chat_id || chatId;
    currentTitle.value = data.title || null;
    await nextTick();
    if (bodyEl.value) bodyEl.value.scrollTop = bodyEl.value.scrollHeight;
  } catch (e) {
    // 可加錯誤提示
  }
}

/** 後端回傳容錯：擷取 chat_id 與 title（可能長不一樣的鍵名） */
function pickChatId(resp: any): string | null {
  return (
    resp?.meta?.chat_id ??
    resp?.chat_id ??
    resp?.id ??
    resp?.meta?.id ??
    null
  );
}
function pickTitle(resp: any, fallback?: string | null): string | null {
  return resp?.meta?.title ?? resp?.title ?? fallback ?? null;
}

/** 登出 */
async function onLogout() {
  const ok = confirm("確定要登出嗎？");
  if (!ok) return;
  // 1) 清除 token + auth 狀態
  authLogout();
  // 2) 以 replace 前往登入頁，避免回上一頁又回到受保護頁面
  await router.replace({ path: "/login" });
}

/** 自動捲到底 */
watch(
  () => messages.value.length,
  async () => {
    await nextTick();
    if (bodyEl.value) bodyEl.value.scrollTop = bodyEl.value.scrollHeight;
  }
);

onMounted(async () => {
  me.value = await fetchMe();
  await refreshList();
  // 綁定快捷鍵
  window.addEventListener("keydown", onKeydown);
  // 若有既存 chat_id 且目前右側有訊息，確保續寫同檔
  const persisted = sessionStorage.getItem("currentChatId");
  if (persisted && !currentChatId.value) currentChatId.value = persisted;
});
onUnmounted(() => window.removeEventListener("keydown", onKeydown));
</script>

<style scoped>
/* ===== 色票（亮色清爽） ===== */
:root {
  --bg: #f6f8fb;
  --panel: #ffffff;
  --border: #d1d5db;     /* 全域基本邊線 */
  --divider: #1f2937;    /* 分界線（更明確、深色 2px） */
  --text: #0f172a;
  --muted: #64748b;
  --primary: #2563eb;
  --primary-weak: #93c5fd;
  --shadow: 0 12px 28px rgba(2, 6, 23, 0.08), 0 2px 8px rgba(2, 6, 23, 0.06);
}

/* ===== 版面 ===== */
.layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  /* 使用動態視窗高（手機位址列不影響），並給 100vh 後備 */
  height: 100dvh;
  height: 100vh;
  background: var(--bg);
  position: relative;
}
/* 明確分界線：2px 深色，整頁一致 */
.sidebar {
  background: var(--panel);
  border-right: 2px solid var(--divider);
  /* 頂/側內距；底部不再需要預留空間 */
  padding: 14px 12px 12px;
  display: grid;
  /* 新：四列 → header / actions / list(可捲) / foot(固定) */
  grid-template-rows: auto auto minmax(0,1fr) auto;
  gap: 12px;
  position: relative;
  z-index: 10;
  height: 100%;
  /* 由清單自己捲動，不讓整個側欄捲動以免跟主畫面搶滾動 */
  overflow: hidden;
}

/* .sidebar.hidden：桌機不套用隱藏，交由 RWD 區塊處理 */

.side-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.brand {
  font-weight: 800;
  letter-spacing: .2px;
}
.side-head-actions { display: inline-flex; gap: 8px; }

.side-actions { display: grid; gap: 8px; }

/* ✅ 左側：只有清單區可捲動 */
.side-list {
  overflow-y: auto;
  padding-right: 6px;
  min-height: 0; /* 關鍵：允許在 grid/flex 內縮小以產生滾動 */
}

/* ✅ 右側：主聊天區保持固定高度並獨立滾動 */
.chat-body {
  flex: 1;
  overflow-y: auto;
  max-height: calc(100vh - 130px); /* 頂部與輸入框高度總和 */
  scroll-behavior: smooth;
}


.side-item {
  display: block;
  padding: 10px 10px;
  border-radius: 10px;
  border: 1px solid transparent;
  color: var(--text);
  text-decoration: none;
  background: #fff;
  box-shadow: var(--shadow);
  margin-bottom: 10px;
}
.side-item .row {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
}
.side-item .title { font-weight: 700; font-size: 14px; }
.side-item .meta { font-size: 12px; color: var(--muted); }
.side-item .icon.del {
  all: unset; cursor: pointer; font-size: 14px; line-height: 1;
  padding: 2px 6px; border-radius: 8px; color: #b91c1c;
}
.side-item .icon.del:disabled { opacity: .5; cursor: not-allowed; }
.side-item:hover { border-color: var(--primary-weak); }
.side-item.active {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.side-empty {
  color: var(--muted);
  font-size: 14px;
  display: grid;
  place-content: center;
}

/* 左下角：登入帳號作為 Grid 最後一列，天然固定 */
.side-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px 24px;
  border-top: 1px solid var(--border);
  background: var(--panel);
}
.me-label { font-size: 12px; color: var(--muted); }
.me-name {
  max-width: 170px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* 右側主區 */
.main {
  display: grid;
  /* 只讓中間這列可伸縮並承擔滾動 */
  grid-template-rows: auto minmax(0,1fr) auto;
  height: 100%;
  overflow: hidden; /* 自己不捲，避免把 topbar/composer 捲走 */
  position: relative;
}


.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 14px;
  background: var(--panel);
  border-bottom: 1px solid var(--border);
  position: sticky;  /* 固定在主欄頂部 */
  top: 0;
  z-index: 5;
}
.top-title { font-weight: 800; }

/* 主體區域（承擔滾動） */
.chat-body {
  padding: 16px;
  overflow-y: auto; /* ✅ 只有聊天內容會滾動 */
  scroll-behavior: smooth;
  min-height: 0;    /* 關鍵：否則會把父層撐高，導致整頁在滾 */
}
.empty { color: var(--muted); text-align: center; padding: 40px 0; }

.msg-row { display: flex; gap: 10px; margin: 10px 0; }
.msg-row.is-user { justify-content: flex-end; }

.avatar.bot {
  width: 36px; height: 36px; border-radius: 50%;
  background: #eef2ff; color: #1d4ed8;
  display: grid; place-items: center;
  border: 1px solid #dbeafe;
}

.bubble {
  max-width: min(760px, 78vw);
  border-radius: 14px;
  padding: 10px 12px;
  background: #ffffff;
  color: var(--text);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
}
.msg-row.is-user .bubble {
  background: #0f172a;
  color: #f8fafc;
  border-color: #0b1324;
}

.meta {
  font-size: 12px;
  opacity: 0.7;
  margin-bottom: 4px;
  display: flex;
  gap: 8px;
}
.text { white-space: pre-wrap; word-break: break-word; }

/* Composer */
.composer {
  padding: 12px 16px 18px;
  background: var(--panel);
  border-top: 1px solid var(--border);
  /* 不需要 fixed；在 grid 第三列自然固定。若需更保險可打開：
  position: sticky; bottom: 0;
  */
}
.attachments {
  display: flex; flex-wrap: wrap; gap: 8px;
  padding: 8px 0 10px;
}
.chip {
  display: inline-flex; align-items: center; gap: 6px;
  max-width: 60%; padding: 4px 8px;
  border-radius: 999px; background: #f1f5f9;
  border: 1px solid #e2e8f0;
}
.chip-name {
  font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.chip-x {
  all: unset; cursor: pointer; font-weight: 700; padding: 0 4px; color: #334155;
}

.composer-inner { display: flex; align-items: center; gap: 10px; }
.file-input { display: none; }

.composer-input {
  flex: 1; height: 44px; padding: 0 12px;
  border-radius: 12px; border: 1px solid #cbd5e1;
  background: #ffffff; color: #111111; outline: none;
}
.composer-input::placeholder { color: #64748b; }

.btn {
  padding: 8px 12px;
  border-radius: 12px;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: var(--text);
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
}
.btn.primary { background: var(--primary); color: #fff; border-color: var(--primary); }
.btn.ghost { background: transparent; color: #334155; border-color: #cbd5e1; }
.btn.xs { height: 30px; padding: 0 10px; font-size: 12px; }
.btn.block { width: 100%; }
.btn:disabled { opacity: .6; cursor: not-allowed; }

/* 手機：側欄可滑入滑出；漢堡與遮罩顯示 */
.only-mobile { display: none; }

@media (max-width: 860px) {
  .layout { grid-template-columns: 1fr; }

  /* 讓側欄浮在畫面上，由 transform 控制顯/隱 */
  .sidebar {
    position: fixed;
    top: 0; left: 0;
    width: 280px;
    height: 100dvh;
    height: 100vh;
    transform: translateX(0);
    transition: transform 0.28s ease;
    z-index: 60; /* 高於內容、低於漢堡鈕 */
    overflow: hidden; /* 由內部 side-list 捲動 */
  }
  .sidebar.hidden {
    transform: translateX(-100%);
  }

  .only-mobile { display: inline-flex; }

  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,.45);
    z-index: 50; /* 在側欄之下、內容之上 */
  }


/* === 桌機版：左欄與右欄之間顯示黑色分隔線 === */
@media (min-width: 861px) {
  .sidebar {
    border-right: 2px solid #000; /* 黑線 */
  }
}

/* 更柔和的陰影分界，而不是純黑直線 */
@media (min-width: 861px) {
  .sidebar { border-right: none; box-shadow: 2px 0 0 #000 inset; }
}

}

/* ===== 全域：阻止整頁滾動，只讓左右欄自己滾 ===== */
:global(html), :global(body), :global(#app) {
  height: 100%;
  overflow: hidden;    /* 頁面不滾，避免 topbar 消失 */
}

</style>
