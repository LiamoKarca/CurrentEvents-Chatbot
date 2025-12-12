# CurrentEvents-Chatbot

以 Prompt Engineering 建構新聞時事聊天機器人，整合 OpenAI `web_search` / `file_search` 能力，協助快速掌握事件脈絡、比對多方來源、標註不確定點，並提供可持續對話的互動體驗。系統採前後端分離架構：前端部署於 Firebase Hosting，後端容器化後部署至 Google Cloud Run；使用者與聊天紀錄以 Firestore 為主。

> 安全提醒：API Key、Service Account、Token Secret 等機密資訊一律放在 `.env`、Cloud Run 環境變數或 Secret Manager，禁止提交到 Git。

---

## 功能概覽

- 新聞時事對話：背景、關鍵人物/組織、時間線、可能走向
- 引用與查證：透過 `web_search` / `file_search` 取得多來源參考
- 使用者登入：Firebase Authentication（Email / Google）
- 對話記憶：Firestore 儲存 chat session 與 message 紀錄
- 部署：後端 Cloud Run、前端 Firebase Hosting

---

## 專案結構（摘要）

- `backend/`：FastAPI 後端（RAG / 工具呼叫 / Firestore）
- `frontend/`：Vite + Vue 前端（登入、聊天 UI、呼叫後端 API）
- `backend/src/knowledge_base_operation/`：新聞知識庫建置流程

---

## 新聞知識庫準備

```bash
python backend/src/knowledge_base_operation/news_pipeline.py
````

---

## 環境需求

### 後端

* Python 3.12.3
* 建議套件：

  ```bash
  pip install fastapi uvicorn openai python-dotenv
  ```

### 前端

* Node.js 18+
* Yarn（或 npm）

---

## 環境變數

### 後端（`.env`）

依實作可能增減，常見欄位如下：

* `OPENAI_API_KEY`
* `OPENAI_CHAT_MODEL`（例：`gpt-4o`）
* `OPENAI_ASSISTANT_ID`（系統提示詞可維護於 `backend/src/app/prompts/system/bot.md`）
* `FIREBASE_SERVICE_ACCOUNT_BASE64`（Firebase Admin SDK 服務帳戶 JSON 的 base64）
* （若有）`MONGODB_URI`、`AUTH_SECRET`、`TOKEN_EXPIRE_MINUTES`

#### Firebase Admin SDK 金鑰取得

Firebase Console → 專案設定（齒輪）→ 服務帳戶 → Firebase Admin SDK → 選 Python → 產生新的私密金鑰

> 建議：避免把整份 JSON 直接放進 repo；採 base64 後以 Cloud Run 環境變數注入，或改用 Secret Manager。

---

### 前端（`frontend/.env.local`）

```bash
# 後端 API 位址（本機或 Cloud Run）
VITE_API_BASE=http://localhost:8000

# Firebase Web App（Vite 環境變數）
VITE_FIREBASE_API_KEY=
VITE_FIREBASE_AUTH_DOMAIN=
VITE_FIREBASE_PROJECT_ID=
VITE_FIREBASE_STORAGE_BUCKET=
VITE_FIREBASE_MESSAGING_SENDER_ID=
VITE_FIREBASE_APP_ID=
VITE_FIREBASE_MEASUREMENT_ID=

#（選用）Firebase Emulator
VITE_USE_AUTH_EMULATOR=false
# 使用方式：firebase emulators:start --only auth

# Hosting 登入的 URL
HOSTED_LOGIN_URL=<Hosting 預設網址>/login
```

> 注意：鍵名需與程式碼 `import.meta.env.VITE_FIREBASE_*` 完全一致（大小寫不可混用）。

---

## 本機啟動

### 後端（本地）

```bash
uvicorn backend.src.app.main:app --reload --log-level debug
```

### 前端（本地）

```bash
cd frontend
yarn install
yarn dev
```

---

## Firebase（前端）Authentication + Hosting 設置與部署

### 1) 安裝 Firebase SDK

```bash
cd frontend
yarn add firebase
# 或 npm install firebase
```

### 2) Firebase Console：建立 Web App（取得設定）

Firebase Console →（專案）→「新增應用程式」→ 選 `</>`（Web）→ 註冊
取得的設定值請放入 `frontend/.env.local`（不要硬編碼在程式碼內）。

### 3) 建立 `src/services/firebase.ts`

（檔案需自行新增）

```ts
import { initializeApp } from "firebase/app";
import { getAnalytics } from "firebase/analytics";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID,
};

const app = initializeApp(firebaseConfig);
const analytics = getAnalytics(app);

export { app, analytics };
```

> 修改 `.env.local` 後需重跑 `yarn dev` 或 `yarn build`，Vite 才會載入最新設定。

---

### 4) Firebase Console：啟用 Authentication（Email / Google）

Firebase Console → Authentication → Sign-in method（登入方式）：

* 啟用 **Email/Password**
* 啟用 **Google**

同時建議檢查：

* Authentication → Settings（設定）→ **Authorized domains**

  * 確認已包含 Firebase Hosting 網域（例如 `*.web.app` / `*.firebaseapp.com`）
  * 若使用自訂網域，也需加入

---

### 5) 安裝 Firebase CLI 並登入

```bash
npm install -g firebase-tools
firebase login
```

---

### 6) 初始化 Hosting（務必在 `frontend/` 內執行）

```bash
cd frontend
firebase init
```

建議選項：

* 勾選 **Hosting**
* 視需求可一併勾選 **Firestore**（若要用 CLI 管理 Rules/Indexes）
* 選擇已存在的 Firebase 專案
* Deploy to GitHub：選 `n`

> 補充：`firebase.json` 需與 `package.json` 同層（皆在 `frontend/`），`firebase deploy` 才能正確辨識前端專案。

---

### 7) 設定 `firebase.json` 指向 Vite 輸出目錄

`frontend/firebase.json`（重點是 `public: "dist"`）：

```json
{
  "hosting": {
    "public": "dist"
  }
}
```

---

### 8) 部署到 Firebase Hosting（標準流程）

```bash
cd frontend
yarn install
yarn run build
firebase deploy --only hosting
```

部署完成後，點擊 Hosting URL：

* 若看到專案畫面即代表成功
* 若仍是 Firebase Welcome Page，通常是 `dist/index.html` 沒更新或快取造成（見下方 Troubleshooting）

---

### 9) 前端更新後重新部署（以此為準）

```bash
cd frontend
yarn install
yarn run build
firebase deploy --only hosting
```

---

## Firestore 啟用與設置

Firebase Console → Firestore Database → 建立資料庫即可。
Rules 文件（官方）：[https://firebase.google.com/docs/rules/get-started?hl=zh-TW](https://firebase.google.com/docs/rules/get-started?hl=zh-TW)

> 後端使用 Admin SDK 可進行伺服端存取；前端存取需搭配 Security Rules 設計。

---

## 後端部署到 Google Cloud Run（Docker + Artifact Registry）

### 1) gcloud 初始化與設定區域

```bash
gcloud init
gcloud config set run/region asia-east1
gcloud config get-value project
```

### 2) 撰寫 Dockerfile 與 .dockerignore

* 後端需有 `Dockerfile`
* 建議 `.dockerignore` 排除 `frontend/`、`node_modules/`、`dist/` 等內容，縮小 image 體積

### 3) 本機 build（tag 可先用 dev）

```bash
cd ~/dev/CurrentEvents-Chatbot
docker build -t ce-backend:dev -f Dockerfile .
```

### 4) 本機執行（建議用 .env 注入，避免把機密寫在指令）

```bash
docker run --rm -p 8080:8080 --env-file .env ce-backend:dev
```

驗證 Swagger：

* [http://localhost:8080/docs](http://localhost:8080/docs)

---

### 5) 建立 Artifact Registry（只需一次）

```bash
PROJECT_ID=$(gcloud config get-value project)
REGION=asia-east1
REPO=currentevents-backend
IMAGE_NAME=backend-api

gcloud artifacts repositories create $REPO \
  --repository-format=docker \
  --location=$REGION \
  --description="Container images for CurrentEvents-Chatbot backend"

gcloud auth configure-docker $REGION-docker.pkg.dev
```

---

### 6) Build 正式 image 並 push

```bash
cd ~/dev/CurrentEvents-Chatbot

PROJECT_ID=$(gcloud config get-value project)
REGION=asia-east1
REPO=currentevents-backend
IMAGE_NAME=backend-api
TAG=v1

docker build -t $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/$IMAGE_NAME:$TAG -f Dockerfile .
docker push $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/$IMAGE_NAME:$TAG
```

---

### 7) 部署到 Cloud Run

```bash
gcloud run deploy currentevents-backend \
  --image=$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/$IMAGE_NAME:$TAG \
  --platform=managed \
  --region=$REGION \
  --allow-unauthenticated \
  --port=8080 \
  --cpu=1 \
  --memory=512Mi \
  --concurrency=80 \
  --min-instances=0 \
  --max-instances=5 \
  --set-env-vars="ENV=prod"
```

> 環境變數（如 `OPENAI_API_KEY`、`FIREBASE_SERVICE_ACCOUNT_BASE64`）建議於 Cloud Run Console：
> 服務 → 編輯及部署新修訂版本 → 容器 →「變數與密鑰」設定後再部署。

---

## 串接到前端（上線）

1. 取得 Cloud Run 服務 URL
2. 更新 `frontend/.env.local`：

```bash
VITE_API_BASE=https://<cloud-run-service-url>
```

3. 重新部署前端：

```bash
cd frontend
yarn install
yarn run build
firebase deploy --only hosting
```

---

## 後端版本更新（建議做法：換 tag 便於回滾）

```bash
cd ~/dev/CurrentEvents-Chatbot

PROJECT_ID=$(gcloud config get-value project)
REGION=asia-east1
REPO=currentevents-backend
IMAGE_NAME=backend-api
TAG=v9

FULL_IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/$IMAGE_NAME:$TAG"

docker build -t "$FULL_IMAGE" -f Dockerfile .
docker push "$FULL_IMAGE"

gcloud run deploy currentevents-backend \
  --image="$FULL_IMAGE" \
  --platform=managed \
  --region=$REGION \
  --allow-unauthenticated
```

Cloud Run 會建立新 revision 並切換流量到新版；舊版保留可回滾。

---

##（選用）Firebase Emulator：離線整合測試

```bash
firebase init emulators
# 勾 Auth emulator、Firestore emulator 等
```

前端可在開發模式連 emulator（示意）：

```ts
import { getAuth, connectAuthEmulator } from "firebase/auth";

export const auth = getAuth(app);

if (import.meta.env.VITE_USE_AUTH_EMULATOR === "true") {
  connectAuthEmulator(auth, "http://localhost:9099", { disableWarnings: true });
}
```

`.env.local`：

```bash
VITE_USE_AUTH_EMULATOR=true
```

---

## Troubleshooting

### 1) 部署後仍顯示 Firebase Welcome Page

* 確認 `frontend/firebase.json` 的 `public` 為 `dist`
* 確認已執行 `yarn run build` 且 `dist/index.html` 存在：

  ```bash
  cd frontend
  yarn run build
  ls dist
  ```
* 用無痕視窗檢查，或清除快取

### 2) 前端讀不到 Firebase 設定

* 檢查 `.env.local` 變數鍵名是否與 `import.meta.env.VITE_FIREBASE_*` 完全一致
* 修改 `.env.local` 後需重跑 `yarn dev` / `yarn run build`

### 3) Cloud Run 啟動失敗

* 優先檢查 Cloud Run 的環境變數是否已補齊
* 檢查容器是否監聽在 8080（Cloud Run 預設）