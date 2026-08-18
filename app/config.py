"""全局配置"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 数据根目录：云端部署时通过 DATA_DIR 指向持久卷（如 Railway 的 /data）
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
KB_JSONL = os.environ.get(
    "KB_JSONL", os.path.join(BASE_DIR, "assets", "kb.jsonl")
)
# 模型目录：云端指向持久卷内的 models（运行时按需下载）
MODEL_DIR = os.environ.get("MODEL_DIR", os.path.join(DATA_DIR, "models"))
# 索引目录：云端可指向镜像内已烘焙的只读索引（如 /app/kb_index）
INDEX_DIR = os.environ.get("INDEX_DIR", os.path.join(DATA_DIR, "kb_index"))
INDEX_FILE = os.path.join(INDEX_DIR, "faiss.index")
META_FILE = os.path.join(INDEX_DIR, "meta.json")
# SQLite 数据库：云端指向持久卷
DB_FILE = os.environ.get("DB_FILE", os.path.join(DATA_DIR, "copilot.db"))
WEB_DIR = os.path.join(BASE_DIR, "web")

# 系统指令词文件（用户提供的核心 System Prompt 源文件）
SYSTEM_PROMPT_FILE = os.environ.get(
    "SYSTEM_PROMPT_FILE",
    os.path.join(BASE_DIR, "assets", "system_prompt.md"),
)

EMBEDDING_MODEL_ID = "intfloat/multilingual-e5-small"
EMBEDDING_DIM = 384
TOP_K_CANDIDATES = 12   # 向量召回候选数
TOP_K_FINAL = 3         # 最终交给 LLM 的条数

# LLM 配置（OpenAI 兼容接口；未配置时降级为演示生成器）
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "").strip()
LLM_API_KEY = os.environ.get("LLM_API_KEY", "").strip()
LLM_MODEL = os.environ.get("LLM_MODEL", "").strip()
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.7"))
