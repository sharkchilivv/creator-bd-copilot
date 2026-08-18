"""FAISS 向量库：构建、持久化、检索"""
import json
import os

import faiss
import numpy as np

from . import config
from . import kb as kb_mod

LIGHT_VEC_FILE = os.path.join(config.INDEX_DIR, "light_vecs.npy")


class VectorStore:
    def __init__(self):
        self.index: faiss.Index | None = None
        self.meta: list[dict] = []
        self.light_vecs: np.ndarray | None = None  # 轻量结构化字段向量（预计算）

    @property
    def ready(self) -> bool:
        return self.index is not None and len(self.meta) > 0

    def build(self, entries: list[dict], vectors: np.ndarray, light_vecs: np.ndarray):
        dim = vectors.shape[1]
        self.index = faiss.IndexFlatIP(dim)  # 内积 = 余弦（向量已归一化）
        self.index.add(vectors)
        self.light_vecs = light_vecs.astype("float32")
        self.meta = [
            {k: v for k, v in e.items() if not k.startswith("_")} for e in entries
        ]
        for e, m in zip(entries, self.meta):
            m["_chunk_text"] = e.get("_chunk_text", "")
            m["_light_text"] = e.get("_light_text", "")
        self.save()

    def save(self):
        os.makedirs(config.INDEX_DIR, exist_ok=True)
        faiss.write_index(self.index, config.INDEX_FILE)
        with open(config.META_FILE, "w", encoding="utf-8") as f:
            json.dump(self.meta, f, ensure_ascii=False, indent=1)
        if self.light_vecs is not None:
            np.save(LIGHT_VEC_FILE, self.light_vecs)

    def load(self) -> bool:
        if not (os.path.exists(config.INDEX_FILE) and os.path.exists(config.META_FILE)):
            return False
        self.index = faiss.read_index(config.INDEX_FILE)
        with open(config.META_FILE, "r", encoding="utf-8") as f:
            self.meta = json.load(f)
        if os.path.exists(LIGHT_VEC_FILE):
            self.light_vecs = np.load(LIGHT_VEC_FILE)
        return True

    def search(self, query_vec: np.ndarray, top_k: int = 10) -> list[dict]:
        """返回 [{entry, score, light_score}] 按相似度降序。"""
        if not self.ready:
            return []
        scores, idxs = self.index.search(query_vec.reshape(1, -1), top_k)
        light_scores = None
        if self.light_vecs is not None:
            light_scores = self.light_vecs @ query_vec  # (n,) 余弦（已归一化）
        results = []
        for score, i in zip(scores[0], idxs[0]):
            if i < 0 or i >= len(self.meta):
                continue
            entry = dict(self.meta[i])
            r = {"entry": entry, "score": round(float(score) * 100, 1)}
            if light_scores is not None:
                r["light_score"] = round(float(light_scores[i]) * 100, 1)
            results.append(r)
        return results

    def stats(self) -> dict:
        if not self.ready:
            return {"count": 0, "dim": 0}
        return {"count": len(self.meta), "dim": self.index.d}

    def get_by_id(self, kb_id: str) -> dict | None:
        for m in self.meta:
            if m.get("id") == kb_id:
                return m
        return None


def ensure_index() -> VectorStore:
    """构建或加载索引（含 Embedding 计算）。"""
    store = VectorStore()
    if store.load():
        print(f"[vs] loaded index: {store.stats()}")
        return store

    print("[vs] building index...")
    entries = kb_mod.load_all()
    texts = [e["_chunk_text"] for e in entries]
    light_texts = [e.get("_light_text", "") for e in entries]
    from . import embeddings

    vecs = embeddings.embed(texts, is_query=False)
    light_vecs = embeddings.embed(light_texts, is_query=False)
    store.build(entries, vecs, light_vecs)
    print(f"[vs] built index: {store.stats()}")
    return store
