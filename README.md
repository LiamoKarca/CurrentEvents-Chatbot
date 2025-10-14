# CurrentEvents-Chatbot
新聞時事聊天機器人，利用人工智慧與OpenAI RAG技術，在資訊爆炸的時代，協助大眾快速判斷新聞真偽，並提供持續對話的互動體驗。

# 新聞知識庫準備
```bash
python backend/src/knowledge_base_operation/news_pipeline.py
```

# RAG Chatbot 快速啟動

## 需求
- Python 3.10+
- 套件：`pip install fastapi uvicorn openai`
- 環境變數：
  - `OPENAI_API_KEY`：你的 OpenAI API Key
  - `OPENAI_CHAT_MODEL`：預設`gpt-4o`
  - `OPENAI_ASSISTANT_ID`：請至 OpenAI Platform 設置 Assistants，系統提示詞放在本專案`backend/src/app/prompts/system/bot.md`
  - `MONGODB_URI`：你的 MongoDB URI

## 後端啟動
```bash
uvicorn backend.src.app.main:app --reload --log-level debug
```

## 前端啟動
```bash
cd frontend
yarn install
yarn dev
```