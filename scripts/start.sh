#!/bin/sh
# 容器启动入口：先确保 Embedding 模型就位（缺失则下载到持久卷），再启动 uvicorn。
# Railway 会通过 PORT 环境变量传入监听端口；本地未设置时默认 8017。
set -e

echo "[start] 检查 Embedding 模型…"
python scripts/ensure_model.py

echo "[start] 启动服务，端口=${PORT:-8017}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8017}"
