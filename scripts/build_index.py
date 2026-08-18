"""构建 FAISS 向量索引（一次性脚本）"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import embeddings, kb, vector_store  # noqa: E402

if not embeddings.is_ready():
    print("模型未下载，先运行: python scripts/download_model.py")
    sys.exit(1)

print("加载知识库...")
entries = kb.load_all()
print(f"共 {len(entries)} 条知识")

print("计算 Embedding...")
texts = [e["_chunk_text"] for e in entries]
vecs = embeddings.embed(texts, is_query=False)
print(f"向量维度: {vecs.shape}")

print("计算轻量字段向量（预计算，检索时直接矩阵运算）...")
light_texts = [e.get("_light_text", "") for e in entries]
light_vecs = embeddings.embed(light_texts, is_query=False)

print("构建 FAISS 索引...")
store = vector_store.VectorStore()
store.build(entries, vecs, light_vecs)
print(f"索引已保存: {vector_store.config.INDEX_FILE}")
print(store.stats())
