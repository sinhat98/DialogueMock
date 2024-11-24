# 実行ステージ
FROM python:3.10-slim

# 実行時に必要なパッケージをインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libsndfile1 \
    libsndfile-dev \
    ffmpeg \ 
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Pythonパッケージのインストール
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# アプリケーションコードのコピー
COPY main.py .
COPY src/ ./src/

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]