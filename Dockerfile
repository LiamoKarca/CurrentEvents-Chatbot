# syntax=docker/dockerfile:1

# ==== Base 層：建置 Python 虛擬環境與安裝依賴 ====
FROM python:3.12.3-slim AS base

# 在基底階段統一設定 Python 與 pip 環境（避免產生 pyc 與快取）
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# 預先建立應用程式工作目錄
WORKDIR /app

# 建立專屬虛擬環境並升級 pip，後續所有層都共用該 venv
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip
ENV PATH="/opt/venv/bin:$PATH"

# 只複製需求檔，讓依賴安裝層能被快取
COPY requirements.txt .

# 依序安裝專案所需套件與 FastAPI/uvicorn，確保啟動程式存在
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir fastapi uvicorn

# ==== Runtime 層：拷貝最終執行所需檔案並建立非 root 使用者 ====
FROM python:3.12.3-slim AS runtime

# 與 Base 層一致的環境變數，並設定預設服務埠
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

# 將 Base 層產出的虛擬環境複製進 Runtime，並確保 PATH 指向
COPY --from=base /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 建立獨立使用者以符合最佳實踐，避免以 root 身份啟動服務
RUN useradd --create-home --shell /bin/bash appuser

# 正式工作目錄僅放應用程式程式碼
WORKDIR /app

# 只複製後端程式碼（frontend 已在 .dockerignore 中排除）
COPY backend ./backend

# 調整檔案權限讓非 root 使用者可讀寫必要路徑
RUN chown -R appuser:appuser /app
USER appuser

# 開放預設服務埠，供 Cloud Run / K8s 等平台探測
EXPOSE 8080

# 預設 Cloud Run/Cloud Run Jobs 使用 0.0.0.0:${PORT} 啟動 uvicorn
CMD ["sh", "-c", "uvicorn backend.src.app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
