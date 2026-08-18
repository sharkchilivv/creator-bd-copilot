"""RAG 检索：Query 组装 → 向量召回 → 规则重排 → Top K"""
from . import config, kb as kb_mod
from .vector_store import VectorStore

# 达人BD场景日→中业务词映射（用于跨语言关键词扩充，提升检索命中）
JA_ZH_MAP = {
    "スタンド": "支架",
    "スタンド付き": "支架款",
    "ケース": "手机壳",
    "固定報酬": "固定报酬",
    "報酬": "报酬",
    "ギャラ": "费用",
    "いくら": "多少钱",
    "単価": "单价",
    "動画": "视频",
    "配達済み": "已送达",
    "届いていません": "未收到",
    "届かない": "未到货",
    "サンプル": "样品",
    "申請": "申请",
    "在庫": "库存",
    "欠品": "缺货",
    "広告": "广告",
    "コラボ": "合作",
    "撮影": "拍摄",
    "投稿": "发布",
    "発送": "发货",
    "リンク": "链接",
    "機種": "机型",
    "マット": "磨砂",
    "透明": "透明",
    "ストラップ": "挂绳",
    "磁力": "磁力",
    "MagSafe": "磁吸",
    "充電": "充电",
    "納期": "交期",
    "レビュー": "测评",
    "対面撮影": "对镜拍",
    "鏡": "镜子",
    "ライブ": "直播",
    "二次": "二次合作",
}


def expand_keywords(text: str) -> list[str]:
    """将达人消息中的日语业务词翻译为中文，用于关键词加权。"""
    extra = []
    for ja, zh in JA_ZH_MAP.items():
        if ja.lower() in text.lower() and zh not in extra:
            extra.append(zh)
    return extra


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _kw_overlap(kw_list: list, text: str) -> int:
    """关键词命中数（用于加权重排）。"""
    t = _norm(text)
    hit = 0
    for kw in kw_list or []:
        if _norm(kw) and _norm(kw) in t:
            hit += 1
    return hit


def rerank(results: list[dict], stage: str, goal: str, keywords: str, product: str) -> list[dict]:
    """
    在向量相似度基础上加权：
    +8  stage 一致；+5 category 关键词命中；+3 回复目标一致；+3 产品命中；+2 priority=recommended
    """
    ctx_text = " ".join([stage, goal, keywords, product])
    for r in results:
        e = r["entry"]
        bonus = 0.0
        if stage and _norm(e.get("cooperation_stage", "")) == _norm(stage):
            bonus += 8
        if _norm(e.get("cooperation_stage", "")) in _norm(stage) or _norm(stage) in _norm(
            e.get("cooperation_stage", "")
        ):
            bonus += 4
        # category 与关键词命中
        if e.get("category") and _norm(e.get("category")) in _norm(ctx_text):
            bonus += 5
        if e.get("communication_goal") and _norm(e.get("communication_goal")) in _norm(goal):
            bonus += 3
        if product and _norm(product) in _norm(e.get("source_text", "")):
            bonus += 3
        # 关键词重叠：entry.keywords 命中 ctx_text（含跨语言扩充后的中文词）
        kw_hits = _kw_overlap(e.get("keywords", []), ctx_text)
        if kw_hits:
            bonus += min(kw_hits, 4) * 4.0
        if e.get("priority") == "recommended":
            bonus += 2
        r["score"] = round(r["score"] + bonus, 1)
        r["score_detail"] = {
            "semantic": round(r["score"] - bonus, 1),
            "stage_bonus": 8 if bonus >= 8 else (4 if bonus >= 4 else 0),
            "keyword_bonus": bonus,
        }
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def retrieve(
    store: VectorStore,
    message: str,
    stage: str = "",
    goal: str = "",
    product: str = "",
    keywords: str = "",
    top_k: int | None = None,
) -> dict:
    """执行检索，返回 {results, used_ids, why, query_text}。

    双重打分：
    1) 全文本 Chunk 语义分（主）
    2) 轻量结构化字段（分类/场景/阶段/目标/关键词）语义分（辅，提升场景辨识度）
    """
    from . import embeddings

    top_k = top_k or config.TOP_K_FINAL
    # 跨语言关键词扩充：把日语业务词翻译为中文，追加到关键词域
    ja_terms = expand_keywords(message)
    if ja_terms:
        keywords = " ".join([keywords, *ja_terms]) if keywords else " ".join(ja_terms)
    query_text = kb_mod.build_query_text(message, stage, goal, product, keywords)
    qv = embeddings.embed_one(query_text, is_query=True)
    candidates = store.search(qv, config.TOP_K_CANDIDATES)

    # 轻量字段二次打分（向量已在索引构建时预计算，无需运行时 Embedding）
    for c in candidates:
        c["score"] = round(c["score"] * 0.75 + c.get("light_score", c["score"]) * 0.25, 1)

    ranked = rerank(candidates, stage, goal, keywords, product)
    final = ranked[:top_k]

    used_ids = [r["entry"]["id"] for r in final]
    why = (
        f"检索Query：{query_text[:80]}{'…' if len(query_text) > 80 else ''}；"
        f"按语义相似度 + 合作阶段一致 + 关键词命中综合重排，召回 {len(final)} 条相关案例"
    )
    return {
        "results": final,
        "used_ids": used_ids,
        "why": why,
        "query_text": query_text,
        "top_k": top_k,
    }
