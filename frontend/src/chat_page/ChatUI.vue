<!-- frontend/src/chat_page/ChatUI.vue -->
<template>
  <div class="chat-wrapper">
    <!-- Header -->
    <header class="chat-header">
      <div class="title">💬 ChatBot</div>
      <div class="actions">
        <button class="btn ghost" @click="clearChat" :disabled="loading || messages.length === 0">
          清除
        </button>
      </div>
    </header>

    <!-- Messages -->
    <main class="chat-body" ref="bodyEl">
      <div v-if="messages.length === 0" class="empty">開始輸入訊息與 ChatBot 對話吧！</div>

      <div
        v-for="m in messages"
        :key="m.id"
        class="msg-row"
        :class="m.role === 'bot' ? 'is-bot' : 'is-user'"
      >
        <!-- 只保留 BOT 頭像 -->
        <div v-if="m.role === 'bot'" class="avatar bot">🤖</div>

        <div class="bubble">
          <div class="meta">
            <span class="who">{{ m.role === 'bot' ? 'Bot' : '我' }}</span>
            <span class="time">{{ m.time }}</span>
          </div>
          <div class="text" v-text="m.text"></div>
        </div>
      </div>
    </main>

    <!-- Composer -->
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
        <!-- 附件：＋ 按鈕 -->
        <button class="btn icon ghost" title="附加檔案" @click="openFilePicker" :disabled="loading">
          +
        </button>
        <input
          ref="fileInput"
          type="file"
          class="file-input"
          multiple
          @change="onFilesSelected"
        />

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
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { API_BASE, USER_ID } from '@/config'

type Msg = {
  id: string
  role: 'user' | 'bot'
  text: string
  time: string
}

const messages = ref<Msg[]>([])
const inputText = ref('')
const loading = ref(false)
const bodyEl = ref<HTMLElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const selectedFiles = ref<File[]>([])

function nowHM() {
  const d = new Date()
  const hh = `${d.getHours()}`.padStart(2, '0')
  const mm = `${d.getMinutes()}`.padStart(2, '0')
  return `${hh}:${mm}`
}

function addMessage(role: 'user' | 'bot', text: string) {
  messages.value.push({
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    text,
    time: nowHM(),
  })
}

function openFilePicker() {
  fileInput.value?.click()
}

function onFilesSelected(e: Event) {
  const input = e.target as HTMLInputElement
  const files = input.files
  if (!files || files.length === 0) return
  // 實際上傳在 send()，這裡只先暫存與顯示
  selectedFiles.value = Array.from(files)
  // 允許再次選同一批檔案
  input.value = ''
}

function removeFile(index: number) {
  selectedFiles.value.splice(index, 1)
}

async function send() {
  if (loading.value) return
  const text = inputText.value.trim()
  if (!text && selectedFiles.value.length === 0) return

  if (text) addMessage('user', text)
  if (!text && selectedFiles.value.length > 0) addMessage('user', '（附帶檔案）')

  loading.value = true
  try {
    let reply = '（無回覆內容）'

    if (selectedFiles.value.length > 0) {
      // 有附件：走 multipart/form-data
      const fd = new FormData()
      fd.append('user_id', USER_ID)
      fd.append('message', text)
      selectedFiles.value.forEach(f => fd.append('files', f))
      const resp = await fetch(`${API_BASE}/api/v1/chat/with-attachments`, {
        method: 'POST',
        body: fd,
      })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      reply = typeof data?.reply === 'string' ? data.reply : reply
      selectedFiles.value = [] // 清空已上傳檔案
    } else {
      // 純文字：走 JSON
      const resp = await fetch(`${API_BASE}/api/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: USER_ID, message: text }),
      })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      reply = typeof data?.reply === 'string' ? data.reply : reply
    }

    if (text) inputText.value = ''
    addMessage('bot', reply)
  } catch (err) {
    addMessage('bot', '抱歉，剛剛處理時出了點問題。')
  } finally {
    loading.value = false
  }
}

async function clearChat() {
  messages.value = []
  inputText.value = ''
  selectedFiles.value = []
  try {
    await fetch(`${API_BASE}/api/v1/memory/clear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: USER_ID }),
    })
  } catch {
    // 靜默失敗，不阻塞 UI
  }
}

watch(
  () => messages.value.length,
  async () => {
    await nextTick()
    if (bodyEl.value) bodyEl.value.scrollTop = bodyEl.value.scrollHeight
  }
)
</script>

<!-- 全域 reset：移除白邊 + 設定全域背景為黑灰色 -->
<style>
html, body, #app {
  margin: 0;
  height: 100%;
  background: #0f1216; /* 黑灰主背景 */
}
</style>

<style scoped>
/* 主容器：黑灰 */
.chat-wrapper {
  min-height: 100vh;
  background: #0f1216; /* 黑灰 */
  color: #e6e6e6;
  display: grid;
  grid-template-rows: auto 1fr auto;
}

/* Header（比主背景亮一階） */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  position: sticky;
  top: 0;
  z-index: 10;
  background: #13161b; /* 深灰 */
  border-bottom: 1px solid #1e293b33;
}

.title {
  font-weight: 700;
  font-size: 16px;
}

.actions {
  display: flex;
  gap: 8px;
}

/* Buttons */
.btn {
  padding: 8px 12px;
  border-radius: 12px;
  border: 1px solid #3b82f6;
  background: #2563eb;
  color: #fff;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.btn.ghost {
  background: transparent;
  color: #93c5fd;
  border-color: #93c5fd66;
}

.btn.icon {
  width: 44px;
  height: 44px;
  padding: 0;
  font-size: 22px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
}

/* Messages */
.chat-body {
  padding: 16px;
  overflow-y: auto;
}

.empty {
  color: #cbd5e1;
  opacity: 0.6;
  text-align: center;
  padding: 40px 0;
}

.msg-row {
  display: flex;
  gap: 10px;
  margin: 10px 0;
}
.msg-row.is-user { justify-content: flex-end; }

.avatar.bot {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #1a1f27;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border: 1px solid #263042;
}

/* Bubbles */
.bubble {
  max-width: min(760px, 78vw);
  border-radius: 14px;
  padding: 10px 12px;
  background: #ffffff;     /* 白底 */
  color: #111827;          /* 深字 */
  border: 1px solid #e5e7eb;
  box-shadow: 0 2px 8px #00000022;
}
.msg-row.is-user .bubble {
  background: #151922;     /* 深灰藍 */
  color: #f3f4f6;
  border-color: #334155;
}

.meta {
  font-size: 12px;
  opacity: 0.7;
  margin-bottom: 4px;
  display: flex;
  gap: 8px;
}
.text { white-space: pre-wrap; word-break: break-word; }

/* Composer（深灰，比 header 更亮一點） */
.composer {
  padding: 12px 16px 18px;
  background: #13161b;
  border-top: 1px solid #1e293b33;
  position: sticky;
  bottom: 0;
  z-index: 10;
}

/* 附件列 */
.attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 16px 0;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 60%;
  padding: 4px 8px;
  border-radius: 999px;
  background: #1a1f27;
  border: 1px solid #2a3446;
}
.chip-name {
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chip-x {
  all: unset;
  cursor: pointer;
  font-weight: 700;
  padding: 0 4px;
  color: #93c5fd;
}

/* 輸入列：對齊 */
.composer-inner {
  display: flex;
  align-items: center; /* 讓傳送與輸入框垂直置中對齊 */
  gap: 10px;
}

.file-input { display: none; } /* 由 + 按鈕觸發 */

/* 白底黑字輸入框 */
.composer-input {
  flex: 1;
  height: 44px;
  padding: 0 12px;
  border-radius: 12px;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #111111;
  outline: none;
}
.composer-input::placeholder { color: #6b7280; }

/* 傳送按鈕與輸入框同高、同列對齊 */
.btn.send {
  height: 44px;
  padding: 0 14px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}

/* 捲動條 */
.chat-body::-webkit-scrollbar { width: 10px; }
.chat-body::-webkit-scrollbar-thumb { background: #2a303b; border-radius: 6px; }
.chat-body::-webkit-scrollbar-track { background: #0f1216; }
</style>
