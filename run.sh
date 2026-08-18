#!/usr/bin/env bash
# Creator BD Copilot 一键启动脚本
set -e
cd "$(dirname "$0")"

PY="$(command -v python3 || command -v python)"

# 可选：配置 LLM（OpenAI 兼容接口），不配置则使用演示生成器
# export LLM_BASE_URL="https://api.openai.com/v1"
# export LLM_API_KEY="sk-xxx"
# export LLM_MODEL="gpt-4o-mini"

# 可选：指定知识库文件（默认读取项目内 assets/kb.jsonl）
# export KB_JSONL="/path/to/达人BD_AI知识库_v2.jsonl"

echo "==> 初始化数据库与 Demo 数据"
$PY scripts/seed_demo.py

echo "==> 检查向量索引"
$PY scripts/build_index.py

echo "==> 启动服务: http://127.0.0.1:8017"
exec $PY -m uvicorn app.main:app --host 0.0.0.0 --port 8017
