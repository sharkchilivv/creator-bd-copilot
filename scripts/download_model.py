"""从 ModelScope 下载 Embedding 模型"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modelscope import snapshot_download  # noqa: E402

from app import config  # noqa: E402

print(f"下载模型: {config.EMBEDDING_MODEL_ID} -> {config.MODEL_DIR}")
path = snapshot_download(config.EMBEDDING_MODEL_ID, cache_dir=config.MODEL_DIR)
print(f"完成: {path}")
