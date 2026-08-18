"""Embedding 服务：基于 multilingual-e5-small（ModelScope 下载，本地加载）"""
import glob
import os
import threading

import numpy as np

from . import config

_model = None
_model_lock = threading.Lock()

# E5 系列模型建议的指令前缀
QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "


def _locate_model_dir() -> str:
    """在 data/models 下找到实际模型目录。"""
    if not os.path.isdir(config.MODEL_DIR):
        return ""
    candidates = glob.glob(os.path.join(config.MODEL_DIR, "**", "config.json"), recursive=True)
    for c in candidates:
        d = os.path.dirname(c)
        # 模型目录必须包含 tokenizer 文件
        if os.path.exists(os.path.join(d, "tokenizer.json")) or os.path.exists(
            os.path.join(d, "tokenizer_config.json")
        ):
            return d
    return ""


def get_model():
    """懒加载模型（单例）。"""
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        model_dir = _locate_model_dir()
        if not model_dir:
            raise RuntimeError(
                "Embedding 模型未找到，请先运行 scripts/download_model.py"
            )
        from sentence_transformers import SentenceTransformer

        print(f"[embedding] loading from {model_dir}")
        _model = SentenceTransformer(model_dir)
        return _model


def embed(texts: list[str], is_query: bool = False) -> np.ndarray:
    """向量化文本列表，返回归一化的 (n, dim) float32 数组。"""
    model = get_model()
    prefix = QUERY_PREFIX if is_query else PASSAGE_PREFIX
    if is_query:
        prepared = [prefix + t for t in texts]
    else:
        # 文档文本本身已含结构化信息，统一加 passage 前缀
        prepared = [prefix + t for t in texts]
    vecs = model.encode(
        prepared,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return np.asarray(vecs, dtype="float32")


def embed_one(text: str, is_query: bool = False) -> np.ndarray:
    return embed([text], is_query=is_query)[0]


def is_ready() -> bool:
    return bool(_locate_model_dir())
