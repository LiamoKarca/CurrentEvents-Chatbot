"""
主應用程式入口
$ uvicorn backend.src.app.main:app --reload --log-level debug
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .api.v1.routes_chat import router as chat_router  # 相對匯入，確保套件化路徑正確
from .api.v1.routes_summary import router as summary_router
from backend.src.app.routers import auth as auth_router
from backend.src.app.routers import user_chat as user_chat_router

app = FastAPI(title="RAG Chatbot (FastAPI + OpenAI Vector Store)")

# ✅ CORS：允許前端的預檢請求（OPTIONS），避免 405
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 如需限制，改成你的前端網址
    allow_credentials=True,
    allow_methods=["*"],          # 包含 OPTIONS
    allow_headers=["*"],
)

# 根路由：提供簡易說明
@app.get("/", tags=["meta"])
def root():
    return JSONResponse({
        "status": "ok",
        "service": "RAG Chatbot (FastAPI + OpenAI Vector Store)",
        "endpoints": [
            "POST /api/v1/chat",
            "POST /api/v1/chat/with-attachments",
            "POST /api/v1/memory/clear",
            "GET  /api/v1/vector_store/debug",
            "GET  /healthz"
        ]
    })

# 健康檢查
@app.get("/healthz", tags=["meta"])
def healthz():
    return JSONResponse({"ok": True})

# 掛載聊天 API
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])
app.include_router(summary_router, prefix="/api/v1", tags=["summary"])

# 掛載路由
app.include_router(auth_router.router)
app.include_router(user_chat_router.router)


if __name__ == "__main__":
    import uvicorn
    # 使用完整模組路徑，讓 reloader 能正確載入
    uvicorn.run("backend.src.app.main:app", host="0.0.0.0", port=8000, reload=True)
