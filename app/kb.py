"""知识库加载：解析 JSONL，每一行为一个完整业务场景 Chunk"""
import json
import os

from . import config


def load_kb_entries(jsonl_path=None) -> list[dict]:
    """解析 JSONL 知识库，返回条目列表。"""
    path = jsonl_path or config.KB_JSONL
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[kb] skip bad line: {e}")
    return entries


def build_chunk_text(entry: dict) -> str:
    """将单条知识组装为 Embedding 文本（与需求文档一致）。"""
    keywords = entry.get("keywords", [])
    if isinstance(keywords, list):
        keywords_str = "、".join(keywords)
    else:
        keywords_str = str(keywords)
    return "\n".join(
        [
            f"分类：{entry.get('category', '')}",
            f"具体场景：{entry.get('scenario', '')}",
            f"合作阶段：{entry.get('cooperation_stage', '')}",
            f"沟通目标：{entry.get('communication_goal', '')}",
            f"关键词：{keywords_str}",
            f"使用限制：{entry.get('notes', '')}",
            f"历史话术：{entry.get('source_text', '')}",
        ]
    )


def build_query_text(message: str, stage: str, goal: str, product: str, keywords: str) -> str:
    """组装检索 Query 文本。"""
    parts = [
        f"达人消息：{message}",
        f"当前合作阶段：{stage}",
        f"回复目标：{goal}",
        f"产品：{product}",
        f"关键词：{keywords}",
    ]
    return "\n".join([p for p in parts if p.split("：", 1)[-1].strip()])


def build_light_text(entry: dict) -> str:
    """轻量结构化文本（不含长话术），用于二次打分加权。"""
    keywords = entry.get("keywords", [])
    if isinstance(keywords, list):
        keywords_str = "、".join(keywords)
    else:
        keywords_str = str(keywords)
    return "\n".join(
        [
            f"分类：{entry.get('category', '')}",
            f"具体场景：{entry.get('scenario', '')}",
            f"合作阶段：{entry.get('cooperation_stage', '')}",
            f"沟通目标：{entry.get('communication_goal', '')}",
            f"关键词：{keywords_str}",
        ]
    )


def load_all() -> list[dict]:
    entries = load_kb_entries()
    for e in entries:
        e["_chunk_text"] = build_chunk_text(e)
        e["_light_text"] = build_light_text(e)
    return entries
