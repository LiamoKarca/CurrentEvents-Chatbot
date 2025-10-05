# CurrentEvents-Chatbot
新聞時事聊天機器人，利用人工智慧與RAG技術，在資訊爆炸的時代，協助大眾快速判斷新聞真偽，並提供持續對話的互動體驗。


# RAG Chatbot 快速啟動

## 需求
- Python 3.10+
- 套件：`pip install fastapi uvicorn openai`
- 環境變數：
  - `OPENAI_API_KEY`：你的 OpenAI API Key
  - `OPENAI_VECTOR_STORE_IDS`：以逗號分隔的一個或多個向量庫 ID，例如 `vs_abc123,vs_xyz789`
  - （可選）`OPENAI_CHAT_MODEL`：預設 `gpt-4o-mini`

## 啟動
```bash
python backend/src/app/main.py
# or
uvicorn backend.src.app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 測試
```bash
curl -X POST http://localhost:8000/api/v1/chat       -H "Content-Type: application/json"       -d '{"user_id":"demo","message":"請用一句話介紹這個系統"}'
```
