<!-- ChatUI.vue -->
<!-- utf-8-sig -->
<template>
  <div
    class="layout"
    :class="{
      'dark-mode': isDark,
      'sidebar-collapsed': sidebarHidden && !isNarrowViewport,
    }"
  >
    <!-- 左側：會話清單 -->
    <aside
      class="sidebar"
      :class="{ hidden: sidebarHidden }"
      aria-label="會話清單側欄"
      :aria-hidden="sidebarHidden"
    >
      <header class="side-head">
        <div class="brand">
          <img class="brand-icon" src="/favicon.ico" alt="芒狗時事標誌" />
          <span>芒狗時事</span>
        </div>
        <div class="side-head-actions">
          <button
            class="btn ghost xs"
            @click="toggleTheme"
            :title="isDark ? '切換為亮色主題' : '切換為暗色主題'"
          >
            {{ isDark ? "暗色" : "亮色" }}
          </button>
          <button class="btn ghost xs" @click="onLogout" title="登出">
            登出
          </button>
          <button
            class="btn ghost xs"
            @click="refreshAll"
            :disabled="loadingList || loadingHighlights"
            title="重整清單"
          >
            重整
          </button>
        </div>
      </header>

      <!-- 左側上方：開新對話 -->
      <section class="side-new">
        <button class="btn primary block" @click="newChat" :disabled="loading">
          ＋ 新對話
        </button>
      </section>

      <!-- 熱門事件卡片 -->
      <section class="side-highlights" :class="{ collapsed: highlightsCollapsed }">
        <button
          class="side-highlights-head"
          type="button"
          @click="toggleHighlightsPanel"
          :aria-expanded="!highlightsCollapsed"
          aria-controls="side-highlights-body"
        >
          <div class="side-highlights-label">
            <span class="label">今日熱門事件三則</span>
            <p v-if="highlightOverview && !highlightsCollapsed" class="overview">
              {{ highlightOverview }}
            </p>
          </div>
          <span class="side-highlights-toggle" aria-hidden="true">
            {{ highlightsCollapsed ? "＋" : "－" }}
          </span>
        </button>
        <transition name="collapse">
          <div
            v-show="!highlightsCollapsed"
            id="side-highlights-body"
            class="side-highlights-body"
          >
            <div v-if="loadingHighlights" class="muted small">
              載入熱門事件中…
            </div>
            <div v-else-if="highlightError" class="muted small">
              {{ highlightError }}
            </div>
            <button
              v-for="item in highlights"
              :key="item.id"
              class="highlight-card"
              :class="{ active: expandedHighlightId === item.id }"
              type="button"
              @click="toggleHighlight(item.id)"
            >
              <div class="title">{{ item.title }}</div>
              <div class="meta">
                <span>{{ item.source || "未知來源" }}</span>
                <span v-if="item.published_at">
                  · {{ formatHighlightDate(item.published_at) }}
                </span>
              </div>
              <p v-if="expandedHighlightId === item.id" class="summary">
                {{ item.llm_summary || item.snippet || "暫無摘要" }}
              </p>
              <div
                v-if="expandedHighlightId === item.id"
                class="highlight-actions"
              >
                <button
                  class="btn ghost xs"
                  type="button"
                  @click.stop="askHighlight(item)"
                >
                  ↗️ 聊聊
                </button>
                <button
                  class="btn ghost xs"
                  type="button"
                  @click.stop="openHighlightLink(item)"
                  :disabled="!item.link"
                >
                  🔗 詳情
                </button>
              </div>
            </button>
          </div>
        </transition>
      </section>

      <!-- 左側中段：歷史清單 -->
      <section class="side-list">
        <div class="side-list-head">
          <span>對話紀錄</span>
          <span v-if="loadingList" class="muted">載入中…</span>
        </div>
        <div class="side-list-body" ref="listEl" aria-label="歷史對話清單">
          <div v-if="history.length === 0 && !loadingList" class="empty-tip">
            尚無對話紀錄，請先在右側開始一則新對話。
          </div>
          <button
            v-for="item in history"
            :key="item.chat_id"
            class="side-item"
            :class="{ active: item.chat_id === currentChatId }"
            type="button"
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
          </button>
        </div>
      </section>

      <!-- 左下角：目前登入帳號 -->
      <footer class="side-foot">
        <div class="me-label">登入帳號</div>
        <div class="me-name" :title="me || '未登入'">
          {{ me || "（未登入）" }}
        </div>
      </footer>
    </aside>

    <div
      v-if="isNarrowViewport && !sidebarHidden"
      class="sidebar-mask"
      @click="closeSidebar"
      aria-hidden="true"
    ></div>

    <!-- 右側：聊天主畫面 -->
    <main class="main">
      <header class="topbar">
        <button
          class="btn ghost xs sidebar-switch"
          @click="toggleSidebar"
          :aria-expanded="!sidebarHidden"
          :aria-label="sidebarHidden ? '展開側欄' : '收合側欄'"
          :title="sidebarHidden ? '展開側欄' : '收合側欄'"
        >
          {{ sidebarHidden ? "☰" : "⮜" }}
        </button>
        <div class="top-title">
          <strong>{{ currentTitle || "新對話" }}</strong>
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
        </div>
      </header>

      <!-- 主體：訊息列表 + 輸入區 -->
      <section class="chat-shell">
        <!-- 訊息區：獨立滾動 -->
        <div class="messages" ref="bodyEl" aria-label="對話內容">
          <div v-if="messages.length === 0" class="empty-state">
            <p class="empty-title">開始一段新的對話吧</p>
            <p class="empty-text">
              在下方輸入問題，或附加檔案讓系統一併分析。
            </p>
          </div>

          <article
            v-for="m in messages"
            :key="m.id"
            class="msg"
            :class="m.role === 'bot' ? 'assistant' : 'user'"
          >
            <header class="msg-head">
              <span class="who">
                {{ m.role === "user" ? "使用者" : "系統" }}
              </span>
              <span class="time">{{ m.time }}</span>
            </header>
            <div class="msg-body">
              <p class="msg-text">{{ m.text }}</p>
            </div>
          </article>

          <!-- 請求中的 loading 狀態 -->
          <div v-if="loading" class="msg assistant pending">
            <div class="msg-head">
              <span class="who">系統</span>
              <span class="time">思考中…</span>
            </div>
            <div class="msg-body">
              <span class="dot dot1"></span>
              <span class="dot dot2"></span>
              <span class="dot dot3"></span>
            </div>
          </div>
        </div>

        <!-- 底部輸入區：獨立固定在主畫面內部 -->
        <footer class="composer">
          <!-- 上方：附檔按鈕 + 已選清單 -->
          <div class="attach-row">
            <button
              class="btn ghost xs"
              type="button"
              @click="openFilePicker"
              title="附加檔案"
            >
              📎 附加檔案
            </button>
            <input
              ref="fileInput"
              type="file"
              multiple
              class="file-input-hidden"
              @change="onFilesSelected"
            />
            <div class="chips" v-if="selectedFiles.length">
              <span
                v-for="(f, i) in selectedFiles"
                :key="f.name + i"
                class="chip"
                :title="`${f.name}（${formatFileSize(f.size)}）`"
              >
                {{ f.name }}
              </span>
              <button class="chip clear" @click="clearFiles" title="清除所有附檔">
                清除
              </button>
            </div>
          </div>

          <!-- 下方：文字輸入 + 送出 -->
          <div class="form-row">
            <textarea
              ref="composerInput"
              v-model="inputText"
              class="input"
              :placeholder="loading ? '處理中…' : '輸入問題，Shift+Enter 換行，Enter 送出…'"
              rows="2"
              @keydown.enter.exact.prevent="send"
              @keydown.shift.enter.stop
            ></textarea>
            <button
              class="btn primary send-btn"
              type="button"
              @click="send"
              :disabled="loading || (!inputText.trim() && selectedFiles.length === 0)"
              title="送出訊息"
            >
              送出
            </button>
          </div>
        </footer>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import { API_BASE } from "@/config";
import { api } from "@/services/api";
import { logout as authLogout } from "@/stores/auth";

/** ====== JWT & /auth/me ====== */
function getToken(): string | null {
  try {
    return localStorage.getItem("token");
  } catch {
    return null;
  }
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
  } catch {
    return null;
  }
}

/** ====== 型別 ====== */
type Msg = { id: string; role: "user" | "bot"; text: string; time: string };
type HistoryRow = { chat_id: string; title: string; created_at: string };
type HighlightCard = {
  id: string;
  title: string;
  link?: string | null;
  source?: string | null;
  published_at?: string | null;
  snippet?: string | null;
  llm_summary?: string | null;
};

const router = useRouter();

const messages = ref<Msg[]>([]);
const inputText = ref("");
const composerInput = ref<HTMLTextAreaElement | null>(null);
const loading = ref(false);
const bodyEl = ref<HTMLElement | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const selectedFiles = ref<File[]>([]);
const highlights = ref<HighlightCard[]>([]);
const highlightOverview = ref("");
const highlightError = ref<string | null>(null);
const loadingHighlights = ref(false);
const expandedHighlightId = ref<string | null>(null);
const highlightsCollapsed = ref(false);

/** RWD 側欄狀態（手機預設收起） */
const isNarrowViewport = ref(
  typeof window !== "undefined" ? window.innerWidth <= 860 : false,
);
const sidebarHidden = ref(isNarrowViewport.value);
const desktopSidebarCollapsed = ref(false);

/** 亮／暗色主題 */
const isDark = ref(false);

/** 會話清單 */
const history = ref<HistoryRow[]>([]);
const loadingList = ref(false);
const deletingId = ref<string | null>(null);

// 讓同一個瀏覽分頁期間保持 chat_id
const currentChatId = ref<string | null>(
  sessionStorage.getItem("currentChatId") || null,
);
const currentTitle = ref<string | null>(null);

/** 登入者 */
const me = ref<string | null>(null);

function resolveUserId(): string | null {
  const username = me.value?.trim();
  return username && username.length > 0 ? username : null;
}

function nowHM(): string {
  const d = new Date();
  const hh = `${d.getHours()}`.padStart(2, "0");
  const mm = `${d.getMinutes()}`.padStart(2, "0");
  return `${hh}:${mm}`;
}

function formatFileSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function formatHighlightDate(value: string): string {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString();
}

function addMessage(role: "user" | "bot", text: string): void {
  messages.value.push({
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    text,
    time: nowHM(),
  });
}

function openFilePicker(): void {
  fileInput.value?.click();
}

function onFilesSelected(e: Event): void {
  const input = e.target as HTMLInputElement;
  const files = input.files;
  if (!files || files.length === 0) return;
  selectedFiles.value = Array.from(files);
  input.value = "";
}

/** 一鍵清除所有附檔 */
function clearFiles(): void {
  selectedFiles.value = [];
  if (fileInput.value) {
    fileInput.value.value = "";
  }
}

/** 單一檔案刪除（目前模板未用，但保留以後擴充） */
function removeFile(index: number): void {
  selectedFiles.value.splice(index, 1);
}

async function refreshHighlights(): Promise<void> {
  loadingHighlights.value = true;
  highlightError.value = null;
  try {
    const data = await api.summary.highlights("daily", 3);
    highlights.value = data.items || [];
    highlightOverview.value = data.overview || "";
    expandedHighlightId.value = highlights.value[0]?.id || null;
  } catch (err: any) {
    highlightError.value = err?.message || "熱門事件暫時無法取得，請稍後再試。";
    highlights.value = [];
    highlightOverview.value = "";
    expandedHighlightId.value = null;
  } finally {
    loadingHighlights.value = false;
  }
}

async function refreshAll(): Promise<void> {
  await Promise.allSettled([refreshList(), refreshHighlights()]);
}

function toggleHighlight(id: string): void {
  expandedHighlightId.value = expandedHighlightId.value === id ? null : id;
}

function toggleHighlightsPanel(): void {
  highlightsCollapsed.value = !highlightsCollapsed.value;
}

function askHighlight(item: HighlightCard): void {
  const question = `嗨，幫我用讀者視角看懂 [${item.title}]：先用 3–5 點說清背景、關鍵人物/組織/時間/地點、目前進展與短中期走向，並標註仍不確定或待釐清處。接著依序處理：全貌速覽—條列來龍去脈、關鍵人物與時間線、下一步可能發展；事實核對—把已證實/待查/有爭議分開列，簡述依據與不確定性；利害地圖—整理主要利害關係人（立場/訴求/可能影響）與互動風險；影響評估—評估對政策/市場/民眾的短中期影響，列出最佳/最差/最可能情境；時間線—建立精簡事件時間線（關鍵節點、行動者、下一個關鍵時點）；新舊差異—點出相較過往同類事件的 3–5 個主要差異與意義；關鍵數字—整理時間、金額、比例、規模等指標並說明意義；爭議點—列出主要爭點與對立觀點、各自論據與潛在盲點；懶人包—濃縮為背景一句話＋數個重點＋接下來看什麼；提問清單—提供可驗證的後續追問題目。`;
  clearChat();
  inputText.value = question;
  closeSidebar();
  nextTick(() => {
    composerInput.value?.focus();
  });
}

function openHighlightLink(item: HighlightCard): void {
  if (!item.link) return;
  window.open(item.link, "_blank", "noopener,noreferrer");
}

/** ====== 後端：聊天 ====== */
async function send(): Promise<void> {
  if (loading.value) return;
  const text = inputText.value.trim();
  if (!text && selectedFiles.value.length === 0) return;

  const userId = resolveUserId();
  if (!userId) {
    alert("尚未取得使用者資訊，請重新登入後再試。");
    return;
  }

  if (text) addMessage("user", text);
  if (!text && selectedFiles.value.length > 0) {
    addMessage("user", "（附帶檔案）");
  }

  loading.value = true;
  try {
    let reply = "（無回覆內容）";
    const token = getToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    if (selectedFiles.value.length > 0) {
      const fd = new FormData();
      fd.append("user_id", userId);
      fd.append("message", text);
      if (currentChatId.value) {
        fd.append("chat_id", currentChatId.value);
        fd.append("conversation_id", currentChatId.value);
      }
      selectedFiles.value.forEach((f) => fd.append("files", f));
      const resp = await fetch(`${API_BASE}/api/v1/chat/with-attachments`, {
        method: "POST",
        headers,
        body: fd,
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      reply = typeof data?.reply === "string" ? data.reply : reply;
      const rid = pickChatId(data);
      if (rid) {
        currentChatId.value = rid;
        sessionStorage.setItem("currentChatId", rid);
      }
      const rtitle = pickTitle(data, currentTitle.value);
      if (rtitle) currentTitle.value = rtitle;
      clearFiles();
    } else {
      const resp = await fetch(`${API_BASE}/api/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({
          user_id: userId,
          message: text,
          chat_id: currentChatId.value || undefined,
          conversation_id: currentChatId.value || undefined,
        }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      reply = typeof data?.reply === "string" ? data.reply : reply;
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
    await autoSaveUpsert();
    await refreshList();
  } catch {
    addMessage("bot", "抱歉，剛剛處理時出了點問題。");
  } finally {
    loading.value = false;
  }
}

/** 清空當前聊天（不影響已保存的歷史） */
async function clearChat(): Promise<void> {
  messages.value = [];
  inputText.value = "";
  selectedFiles.value = [];
  currentChatId.value = null;
  sessionStorage.removeItem("currentChatId");
  currentTitle.value = null;

  const userId = resolveUserId();
  if (!userId) {
    return;
  }

  try {
    const token = getToken();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    await fetch(`${API_BASE}/api/v1/memory/clear`, {
      method: "POST",
      headers,
      body: JSON.stringify({ user_id: userId }),
    });
  } catch {
    // 靜默處理
  }
}

/** 新對話：重置右側編輯區 */
function newChat(): void {
  clearChat();
}

/** 鍵盤快捷鍵：Ctrl/Cmd + N 開新對話 + Esc 關側欄（手機） */
function onKeydown(e: KeyboardEvent): void {
  const isMac = navigator.platform.toLowerCase().includes("mac");
  const hitNew = (isMac ? e.metaKey : e.ctrlKey) && e.key.toLowerCase() === "n";
  if (hitNew) {
    e.preventDefault();
    if (!loading.value) newChat();
    return;
  }
  if (e.key === "Escape") closeSidebar();
}

function toggleSidebar(): void {
  const next = !sidebarHidden.value;
  sidebarHidden.value = next;
  if (!isNarrowViewport.value) {
    desktopSidebarCollapsed.value = next;
  }
}

function closeSidebar(): void {
  if (isNarrowViewport.value) {
    sidebarHidden.value = true;
  }
}

function updateViewportMode(): void {
  if (typeof window === "undefined") return;
  const mobile = window.innerWidth <= 860;
  if (mobile === isNarrowViewport.value) return;
  isNarrowViewport.value = mobile;
  if (mobile) {
    desktopSidebarCollapsed.value = sidebarHidden.value;
    sidebarHidden.value = true;
  } else {
    sidebarHidden.value = desktopSidebarCollapsed.value;
  }
}

/** 自動保存（upsert）：第一次建立；其後一律續寫同一 chat_id */
async function autoSaveUpsert(): Promise<void> {
  if (messages.value.length === 0) return;
  const payload = messages.value.map((m) => ({
    role: m.role === "bot" ? "assistant" : "user",
    content: m.text,
  }));
  if (currentChatId.value) {
    const r = await api.chats.save(payload, undefined, currentChatId.value);
    const id = pickChatId(r) || currentChatId.value;
    const title = pickTitle(r, currentTitle.value);
    currentChatId.value = id;
    currentTitle.value = title;
    if (id) sessionStorage.setItem("currentChatId", id);
  } else {
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

/** 刪除某筆聊天 */
async function deleteChat(chatId: string): Promise<void> {
  const ok = confirm("確定要刪除此筆聊天紀錄嗎？");
  if (!ok) return;
  deletingId.value = chatId;
  try {
    if (typeof api.chats.delete === "function") {
      await api.chats.delete(chatId);
    } else {
      alert("後端未提供刪除 API：請新增 DELETE /api/v1/chats/{chat_id}");
      return;
    }
    if (currentChatId.value === chatId) {
      clearChat();
    }
    await refreshList();
  } catch {
    alert("刪除失敗，請稍後再試。");
  } finally {
    deletingId.value = null;
  }
}

/** 讀取歷史列表 */
async function refreshList(): Promise<void> {
  loadingList.value = true;
  try {
    const r = await api.chats.list();
    const map = new Map<string, HistoryRow>();
    for (const x of r.items || []) {
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
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
  } finally {
    loadingList.value = false;
  }
}

/** 載入某筆聊天 */
async function loadChat(chatId: string): Promise<void> {
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
    if (currentChatId.value) {
      sessionStorage.setItem("currentChatId", currentChatId.value);
    } else {
      sessionStorage.removeItem("currentChatId");
    }
    await nextTick();
    if (bodyEl.value) bodyEl.value.scrollTop = bodyEl.value.scrollHeight;
  } catch {
    // 需時再補錯誤提示
  }
}

/** 後端回傳容錯：擷取 chat_id 與 title */
function pickChatId(resp: any): string | null {
  return resp?.meta?.chat_id ?? resp?.chat_id ?? resp?.id ?? resp?.meta?.id ?? null;
}

function pickTitle(resp: any, fallback?: string | null): string | null {
  return resp?.meta?.title ?? resp?.title ?? fallback ?? null;
}

/** 登出 */
async function onLogout(): Promise<void> {
  const ok = confirm("確定要登出嗎？");
  if (!ok) return;
  authLogout();
  await router.replace({ path: "/login" });
}

/** 自動捲到底 */
watch(
  () => messages.value.length,
  async () => {
    await nextTick();
    if (bodyEl.value) {
      bodyEl.value.scrollTop = bodyEl.value.scrollHeight;
    }
  },
);

/** 主題切換 */
function toggleTheme(): void {
  isDark.value = !isDark.value;
  try {
    const mode = isDark.value ? "dark" : "light";
    localStorage.setItem("theme", mode);
  } catch {
    // ignore
  }
}

onMounted(async () => {
  try {
    const stored = localStorage.getItem("theme");
    isDark.value = stored === "dark";
  } catch {
    isDark.value = false;
  }

  updateViewportMode();
  me.value = await fetchMe();
  await refreshAll();
  window.addEventListener("keydown", onKeydown);
  window.addEventListener("resize", updateViewportMode);
  const persisted = sessionStorage.getItem("currentChatId");
  if (persisted && !currentChatId.value) currentChatId.value = persisted;
});

onUnmounted(() => {
  window.removeEventListener("keydown", onKeydown);
  window.removeEventListener("resize", updateViewportMode);
});
</script>

<style scoped>
/* ===== 色票（亮色清爽） ===== */
:root {
  --bg: #f6f8fb;
  --panel: #ffffff;
  --border: #d1d5db;
  --divider: #1f2937;
  --text: #0f172a;
  --muted: #64748b;
  --primary: #2563eb;
  --primary-weak: #93c5fd;
  --shadow: 0 12px 28px rgba(2, 6, 23, 0.08), 0 2px 8px rgba(2, 6, 23, 0.06);
}

/* ===== 版面 ===== */
.layout {
  --sidebar-width: 300px;
  display: grid;
  grid-template-columns: minmax(0, var(--sidebar-width)) 1fr;
  /* iOS Safari：避免 100vh 把底部工具列算進來，吃掉 composer */
  height: 100vh; /* fallback */
  height: 100dvh; /* override */
  background: var(--bg);
  position: relative;
}

.layout.sidebar-collapsed {
  --sidebar-width: 0px;
}

.layout.dark-mode {
  --bg: #020617;
  --panel: #020617;
  --border: #4b5563;
  --divider: #e5e7eb;
  --text: #f9fafb;
  --muted: #9ca3af;
  --primary: #60a5fa;
  --primary-weak: #1d4ed8;
  --shadow: 0 12px 28px rgba(15, 23, 42, 0.7), 0 2px 8px rgba(15, 23, 42, 0.5);
  color: var(--text);
}

/* 左側：側欄固定，獨立滾動 */
.sidebar {
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background: var(--panel);
  box-shadow: 2px 0 4px rgba(15, 23, 42, 0.05);
  max-height: 100%;
  width: var(--sidebar-width);
  transition: width 0.2s ease, opacity 0.15s ease;
}

/* 讓側欄內部本身可滾動，而不是整頁滾動 */
.sidebar,
.main {
  overflow: hidden;
}

.side-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 800;
  letter-spacing: 0.2px;
  white-space: nowrap; /* 不換行顯示「芒狗時事」 */
}

.brand-icon {
  width: 24px;
  height: 24px;
  border-radius: 4px;
}

.side-head-actions {
  display: inline-flex;
  gap: 8px;
}

.side-head {
  padding: 12px 12px 8px;
  border-bottom: 1px solid var(--border);
}

/* 新對話區塊 */
.side-new {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
}

.side-new .btn.primary {
  background: linear-gradient(135deg, #e5edff, #d5e4ff);
  color: #374151; /* 左側新對話：深灰字 */
  border-color: #cbd5f5;
  box-shadow: none;
}

.layout.dark-mode .side-new .btn.primary {
  background: linear-gradient(135deg, #1e3a8a, #1d4ed8);
  color: #f9fafb;
  border-color: #1d4ed8;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.35);
}

.side-highlights {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
  background: rgba(148, 163, 184, 0.1);
}

.side-highlights.collapsed {
  padding-bottom: 6px;
}

.layout.dark-mode .side-highlights {
  background: rgba(96, 165, 250, 0.08);
}

.side-highlights-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
  width: 100%;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
}

.side-highlights-head:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
}

.side-highlights-toggle {
  font-size: 14px;
  color: var(--muted);
}

.side-highlights-label .label {
  font-size: 14px;
  font-weight: 700;
}

.layout.dark-mode .side-highlights-label .label {
  color: #ffffff;
}

.side-highlights-label .overview {
  margin-top: 4px;
  font-size: 12px;
  color: var(--muted);
  /* 手機避免摘要太長把下方卡片與清單擠爆 */
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  overflow: hidden;
}

.side-highlights-body {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;

  /* 熱門事件區塊：固定高度上限 + 自身滾動，避免擠爆 sidebar */
  overflow-y: auto;
  max-height: clamp(180px, 32vh, 520px);
  padding-right: 4px;

  /* iOS 滾動體驗 */
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
}

.highlight-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 8px;
  background: var(--panel);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.highlight-card.active {
  border-color: var(--primary);
  background: rgba(37, 99, 235, 0.08);
}

.layout.dark-mode .highlight-card.active {
  background: rgba(96, 165, 250, 0.12);
}

.highlight-card .title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 4px;
}

.highlight-card .meta {
  font-size: 12px;
  color: var(--muted);
}

.highlight-card .summary {
  font-size: 13px;
  color: var(--text);
  margin: 6px 0;
  line-height: 1.4;
}

.highlight-actions {
  display: flex;
  gap: 6px;
}

.highlight-actions .btn {
  flex: 1;
}

.muted {
  color: var(--muted);
}

.muted.small {
  font-size: 12px;
}

.collapse-enter-active,
.collapse-leave-active {
  overflow: hidden;
  transition: max-height 0.18s ease, opacity 0.18s ease;
}

.collapse-enter-from,
.collapse-leave-to {
  max-height: 0;
  opacity: 0;
}

.collapse-enter-to,
.collapse-leave-from {
  /* 展開上限提高，避免內容較長時被動畫上限卡住 */
  max-height: 900px;
  opacity: 1;
}

/* 中段清單：自身滾動 */
.side-list {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.side-list-head {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px 4px;
  font-size: 13px;
  color: var(--muted);
}

.side-list-body {
  flex: 1 1 auto;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
  padding: 0 6px 0 8px;
}

/* 左側 item 設計 */
.side-item {
  width: 100%;
  border: none;
  background: transparent;
  text-align: left;
  padding: 6px 6px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 2px;
  transition: background 0.15s ease, transform 0.05s ease;
}

.side-item:hover {
  background: rgba(148, 163, 184, 0.16);
}

.side-item.active {
  background: rgba(37, 99, 235, 0.08);
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.18);
}

.side-item .row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 6px;
}

.side-item .title {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

.side-item .meta {
  margin-top: 2px;
  font-size: 12px;
  color: var(--muted);
}

.icon.del {
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  opacity: 0.6;
}

.icon.del:hover {
  opacity: 1;
}

/* 左下角目前登入帳號 */
.side-foot {
  padding: 10px 12px 12px;
  border-top: 1px solid var(--border);
  font-size: 12px;
  color: var(--muted);
  background: rgba(148, 163, 184, 0.05);
}

.me-label {
  margin-bottom: 2px;
}

.me-name {
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

/* 右側主畫面 */
.main {
  display: flex;
  flex-direction: column;
  max-height: 100%;
  min-height: 0;
}

/* 頂部列 */
.topbar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  border-bottom: 1px solid var(--divider);
  background: rgba(248, 250, 252, 0.96);
  backdrop-filter: blur(12px);
}

.layout.dark-mode .topbar {
  background: rgba(15, 23, 42, 0.97);
  border-bottom-color: #4b5563;
}

.top-title {
  flex: 1;
  padding: 0 12px;
  font-size: 15px;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

.top-title strong {
  font-weight: 600;
  color: var(--text);
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 主體區：上下切成 messages + composer */
.chat-shell {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-height: 0;

  /* iOS safe-area：避免底部輸入列被 home indicator / 工具列擋住 */
  padding: 10px 14px calc(12px + env(safe-area-inset-bottom)) 14px;
  gap: 10px;
}

/* 訊息列表：獨立滾動容器 */
.messages {
  flex: 1 1 auto;
  min-height: 0;

  /* 關鍵：沒有 overflow-y，手機只會看到可捲但不穩定的滾動區 */
  overflow-y: auto;

  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
  padding: 4px 4px 8px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.4);
  background: radial-gradient(circle at top, #ffffff, #f3f4f6);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
}

.layout.dark-mode .messages {
  background: radial-gradient(circle at top, #020617, #020617);
  border-color: #4b5563;
  box-shadow: inset 0 1px 0 rgba(15, 23, 42, 0.9);
}

/* 空狀態 */
.empty-state {
  padding: 40px 16px;
  text-align: center;
  color: var(--muted);
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 6px;
}

.empty-text {
  font-size: 14px;
}

/* 一則訊息 */
.msg {
  margin-bottom: 10px;
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(248, 250, 252, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.45);
}

.msg.user {
  border-color: rgba(59, 130, 246, 0.5);
  background: linear-gradient(120deg, #eff6ff, #e0f2fe);
}

.msg.assistant {
  border-color: rgba(148, 163, 184, 0.6);
}

/* 暗色訊息泡泡 */
.layout.dark-mode .msg {
  background: #020617;
  border-color: #4b5563;
}

.layout.dark-mode .msg.user {
  background: linear-gradient(120deg, #0f172a, #020617);
  border-color: #1d4ed8;
}

.layout.dark-mode .msg.assistant {
  background: #020617;
  border-color: #4b5563;
}

.msg-head {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  margin-bottom: 2px;
}

.msg-head .who {
  font-weight: 600;
  color: #1f2933;
}

.msg-head .time {
  color: var(--muted);
}

.layout.dark-mode .msg-head .who {
  color: #e5e7eb;
}

.layout.dark-mode .msg-head .time {
  color: #9ca3af;
}

.msg-body {
  font-size: 14px;
  line-height: 1.5;
}

.msg-text {
  white-space: pre-wrap;
  color: var(--text);
}

.layout.dark-mode .msg-text {
  color: #e5e7eb;
}

/* loading dots */
.msg.assistant.pending {
  display: inline-flex;
  flex-direction: column;
  gap: 6px;
}

.msg.assistant.pending .msg-body {
  display: inline-flex;
  gap: 4px;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: #9ca3af;
  animation: bounce 1s infinite ease-in-out;
}

.dot2 {
  animation-delay: 0.15s;
}

.dot3 {
  animation-delay: 0.3s;
}

@keyframes bounce {
  0%,
  80%,
  100% {
    transform: scale(0);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* 輸入區 */
.composer {
  flex: 0 0 auto;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.5);

  /* iOS safe-area：避免送出鍵/輸入列貼底被遮 */
  padding: 8px 10px calc(10px + env(safe-area-inset-bottom));

  background: rgba(248, 250, 252, 0.98);
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.12);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.layout.dark-mode .composer {
  background: #020617;
  border-color: #4b5563;
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.6);
}

/* 附檔列 */
.attach-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.chips {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  justify-content: flex-end;
}

.chip {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.7);
  background: rgba(255, 255, 255, 0.96);
  max-width: 180px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chip.clear {
  cursor: pointer;
  font-weight: 600;
  background: rgba(239, 246, 255, 0.9);
}

/* file input 隱藏 */
.file-input-hidden {
  display: none;
}

/* 底部輸入 + 送出 */
.form-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.input {
  flex: 1;
  resize: none;
  padding: 6px 8px;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.7);
  font-size: 14px;
  line-height: 1.5;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #ffffff;
  color: #0f172a;
}

.input:focus {
  outline: none;
  border-color: rgba(37, 99, 235, 0.8);
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.15);
}

.layout.dark-mode .input {
  background: #020617;
  color: #e5e7eb;
  border-color: #4b5563;
}

.layout.dark-mode .input::placeholder {
  color: #6b7280;
}

/* 按鈕共用樣式 */
.btn {
  border-radius: 999px;
  border: 1px solid transparent;
  padding: 0 14px;
  height: 34px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  transition: background 0.15s ease, border-color 0.15s ease, box-shadow 0.1s ease,
    transform 0.05s ease;
}

/* 基本 primary（給一般情境使用，保留藍底白字） */
.btn.primary {
  background: linear-gradient(135deg, var(--primary), #1d4ed8);
  color: #ffffff;
  border-color: #1d4ed8;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.35);
}

/* Composer 的送出按鈕（亮色模式）：白底＋深灰字 */
button.btn.primary.send-btn {
  background: #ffffff;
  color: #111827;
  border-color: #93c5fd;
  box-shadow: 0 3px 8px rgba(59, 130, 246, 0.25);
}

button.btn.primary.send-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: #ffffff;
  border-color: #1d4ed8;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.35);
}

/* disabled 狀態仍維持深灰字，只降低透明度 */
button.btn.primary.send-btn:disabled {
  color: #111827;
  opacity: 0.6;
  cursor: not-allowed;
}

/* 暗色模式下：藍底白字 */
.layout.dark-mode button.btn.primary.send-btn,
.layout.dark-mode button.btn.primary.send-btn:hover {
  background: linear-gradient(135deg, #1e3a8a, #1d4ed8);
  color: #f9fafb;
  border-color: #1d4ed8;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.35);
}

.btn.primary:hover {
  background: linear-gradient(135deg, #1d4ed8, #1e40af);
  transform: translateY(-0.5px);
}

.btn.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn.ghost {
  background: rgba(248, 250, 252, 0.95);
  border-color: rgba(148, 163, 184, 0.7);
}

.btn.ghost:hover {
  background: rgba(229, 231, 235, 0.9);
}

.layout.dark-mode .btn.ghost {
  background: #020617;
  border-color: #4b5563;
  color: #e5e7eb;
}

.layout.dark-mode .btn.ghost:hover {
  background: #0b1120;
}

.btn.xs {
  height: 30px;
  padding: 0 10px;
  font-size: 12px;
}

.btn.block {
  width: 100%;
}

.sidebar-switch {
  width: 34px;
  padding: 0;
  font-size: 16px;
}

.sidebar-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(2px);
  z-index: 15;
}

@media (max-width: 860px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    width: 280px;
    max-width: 80%;

    /* iOS Safari：側欄高度也走 dvh，避免工具列影響可視區 */
    height: 100vh; /* fallback */
    height: 100dvh; /* override */

    z-index: 20;
    transform: translateX(-100%);
    transition: transform 0.2s ease-out, box-shadow 0.2s ease-out;
    box-shadow: none;
  }

  .sidebar.hidden {
    transform: translateX(-100%);
    box-shadow: none;
  }

  .sidebar:not(.hidden) {
    transform: translateX(0);
    box-shadow: 8px 0 18px rgba(15, 23, 42, 0.45);
  }

  .side-head {
    flex-direction: column; /* 改成上下排 */
    align-items: flex-start;
    gap: 6px;
  }

  .side-head-actions {
    width: 100%;
    justify-content: flex-start; /* 按鈕從左到右排 */
    flex-wrap: wrap; /* 不夠寬就自動換行 */
    gap: 6px;
  }

  .side-head-actions .btn.xs {
    padding: 0 8px; /* 手機時按鈕窄一點 */
    font-size: 11px;
  }

  .main {
    position: relative;
  }
}

/* 桌機：左右中間黑線 */
@media (min-width: 861px) {
  .sidebar {
    border-right: none;
    box-shadow: 2px 0 0 #000 inset;
  }
  .sidebar.hidden {
    opacity: 0;
    pointer-events: none;
    border-right: none;
    box-shadow: none;
  }
}

/* ===== 全域：阻止整頁滾動，只讓左右欄自己滾 ===== */
:global(html),
:global(body),
:global(#app) {
  height: 100%;
  overflow: hidden;
}
</style>
