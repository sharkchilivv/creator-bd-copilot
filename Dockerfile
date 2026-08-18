# Creator BD Copilot - 生产镜像
# 策略：镜像只装代码 + 轻量依赖；2.1GB 的 Embedding 模型不在镜像内，
# 首次启动时由 scripts/ensure_model.py 下载到持久卷（如 Railway 的 /data/models）。
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 系统依赖：torch/faiss 需要的 OpenMP 运行时等
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates libgomp1 wget \
    && rm -rf /var/lib/apt/lists/*

# 单独安装 CPU 版 torch（避免默认 CUDA 版本撑爆镜像）
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 安装其余依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码与静态资源
COPY app ./app
COPY web ./web
COPY scripts ./scripts
COPY assets ./assets
# 预构建的 FAISS 索引（只读，直接烘焙进镜像，无需运行时联网）
COPY data/kb_index ./kb_index

# 持久卷挂载点（模型、SQLite 数据库都落在这里）
RUN mkdir -p /data

# 运行路径：索引/话术资源烘焙在镜像内只读，模型与数据库写入持久卷 /data
ENV DATA_DIR=/data \
    MODEL_DIR=/data/models \
    INDEX_DIR=/app/kb_index \
    DB_FILE=/data/copilot.db \
    KB_JSONL=/app/assets/kb.jsonl \
    SYSTEM_PROMPT_FILE=/app/assets/system_prompt.md

EXPOSE 8017

CMD ["sh", "scripts/start.sh"]
