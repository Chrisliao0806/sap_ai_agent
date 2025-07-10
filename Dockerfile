# 使用官方的 Python 3.11 slim 映像檔作為基礎映像檔
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 設定環境變數
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py \
    FLASK_ENV=production \
    FLASK_DEBUG=0

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 複製 requirements.txt 並安裝 Python 依賴
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 複製應用程式代碼
COPY app.py .
COPY purchase_agent.py .
COPY prompts.py .
COPY choose_state.py .
COPY data_manager.py .

# 創建日誌目錄和資料目錄
RUN mkdir -p /app/logs /app/data

# 創建非 root 用戶
RUN useradd --create-home --shell /bin/bash app_user && \
    chown -R app_user:app_user /app
USER app_user

# 暴露端口
EXPOSE 12000

# 健康檢查
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:12000/ || exit 1

# 啟動命令 - 使用 Gunicorn 作為生產級 WSGI 伺服器
CMD ["gunicorn", "--bind", "0.0.0.0:12000", "--workers", "4", "--timeout", "120", "--keep-alive", "2", "--max-requests", "1000", "--max-requests-jitter", "100", "app:app"]
