"""SQLite 存储：达人档案、品牌规则、回复记录、Dashboard 统计"""
import json
import os
import sqlite3
import threading
from datetime import datetime

from . import config

_lock = threading.Lock()

CREATOR_FIELDS = [
    "nickname", "account", "level", "vertical", "audience_profile",
    "history", "current_product", "cooperation_stage", "commission_pref",
    "quote_status", "special_requirements", "notes", "conversation_summary",
]


def _conn():
    db_dir = os.path.dirname(config.DB_FILE)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(config.DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _lock, _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS creators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nickname TEXT, account TEXT, level TEXT, vertical TEXT,
                audience_profile TEXT, history TEXT, current_product TEXT,
                cooperation_stage TEXT, commission_pref TEXT, quote_status TEXT,
                special_requirements TEXT, notes TEXT, conversation_summary TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS brand_rules (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                rules TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS replies_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER,
                creator_name TEXT,
                original_message TEXT,
                analysis TEXT,
                retrieved_kb_ids TEXT,
                generated_version TEXT,
                operator_edited TEXT,
                final_sent TEXT,
                style_used TEXT,
                modified INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS llm_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                config TEXT NOT NULL
            );
            """
        )
        # 默认品牌规则
        row = conn.execute("SELECT id FROM brand_rules WHERE id=1").fetchone()
        if row is None:
            default = {
                "brand": "CASEKOO",
                "market": "JP",
                "platform": "TikTok Shop",
                "current_commission": "10% 成果报酬（佣金）",
                "fixed_fee_allowed": False,
                "fixed_fee_range": "不提供固定报酬",
                "ad_support": "单条视频 2 万日元以上广告预算（需内部确认）",
                "current_products": [
                    {"name": "KORI 高透明クリアケース", "desc": "高透明・黄ばみ防止・耐衝撃"},
                    {"name": "マット指紋防止ケース", "desc": "マット質感・指紋防止・多色展開"},
                    {"name": "LINKOO ストラップケース", "desc": "ストラップ付き・未発売"},
                    {"name": "MagicStand Pro", "desc": "360°回転スタンド・MagSafe"},
                    {"name": "iPhone 18 冰透ケース（透明系）", "desc": "还原原机配色・镜头加高防护・四角防摔・抗黄变不发黄"},
                    {"name": "iPhone 18 質簡ケース（磨砂系）", "desc": "磨砂防指纹・裸机质感・多色展開"},
                ],
                "new_machine_policy": {
                    "new_machine": "iPhone 18",
                    "main_lines": ["冰透（透明系）", "质简（磨砂系）"],
                    "claimable_selling_points": [
                        "还原原机配色", "镜头加高防护", "四角防摔",
                        "抗黄变不发黄", "磨砂防指纹", "裸机质感",
                    ],
                    "forbidden_claims": [
                        "未送测防摔等级/军规认证", "100%不发黄",
                        "磁吸/钛金属（脚本库未出现，需官方确认）", "具体发货日期", "具体库存数量",
                    ],
                },
                "inventory_status": {},
                "sample_policy": "免费寄送样品1件，达人需在 TikTok Shop 自行申请",
                "shipping_policy": "申请确认后尽快安排发货",
                "promotion_info": "暂无限时促销配置",
                "forbidden_promises": [
                    "固定报酬金额", "具体发货日期", "缺货恢复时间", "广告预算额度",
                    "佣金比例变更", "销量数据", "产品参数（磁力/25W/MIL等）",
                    "iPhone 18 未确认产品参数（防摔等级/军规/磁力/材质）", "新机具体发货日期",
                ],
                "forbidden_words": ["最安値", "最低价", "限时赠品", "HIKAKIN使用中（未确认）", "軍規級防摔（未送測）", "100%不发黄（未確認）"],
            }
            conn.execute(
                "INSERT INTO brand_rules (id, rules) VALUES (1, ?)",
                (json.dumps(default, ensure_ascii=False),),
            )
        conn.commit()


# ---------------------------------------------------------------------------
# 达人档案
# ---------------------------------------------------------------------------
def list_creators() -> list[dict]:
    with _lock, _conn() as conn:
        rows = conn.execute("SELECT * FROM creators ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def get_creator(cid: int) -> dict | None:
    with _lock, _conn() as conn:
        row = conn.execute("SELECT * FROM creators WHERE id=?", (cid,)).fetchone()
    return dict(row) if row else None


def upsert_creator(data: dict) -> int:
    with _lock, _conn() as conn:
        cid = data.get("id")
        fields = {f: data.get(f, "") for f in CREATOR_FIELDS}
        if cid:
            sets = ", ".join(f"{f}=?" for f in CREATOR_FIELDS)
            conn.execute(f"UPDATE creators SET {sets} WHERE id=?", (*fields.values(), cid))
            return cid
        cols = ", ".join(CREATOR_FIELDS)
        ph = ", ".join("?" for _ in CREATOR_FIELDS)
        cur = conn.execute(
            f"INSERT INTO creators ({cols}) VALUES ({ph})", tuple(fields.values())
        )
        conn.commit()
        return cur.lastrowid


def delete_creator(cid: int):
    with _lock, _conn() as conn:
        conn.execute("DELETE FROM creators WHERE id=?", (cid,))
        conn.commit()


# ---------------------------------------------------------------------------
# 品牌规则
# ---------------------------------------------------------------------------
def get_brand_rules() -> dict:
    with _lock, _conn() as conn:
        row = conn.execute("SELECT rules FROM brand_rules WHERE id=1").fetchone()
    return json.loads(row["rules"]) if row else {}


def save_brand_rules(rules: dict):
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO brand_rules (id, rules) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET rules=excluded.rules",
            (json.dumps(rules, ensure_ascii=False),),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# 回复记录
# ---------------------------------------------------------------------------
def save_reply_log(record: dict) -> int:
    with _lock, _conn() as conn:
        cur = conn.execute(
            """INSERT INTO replies_log
               (creator_id, creator_name, original_message, analysis,
                retrieved_kb_ids, generated_version, operator_edited,
                final_sent, style_used, modified)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                record.get("creator_id"),
                record.get("creator_name", ""),
                record.get("original_message", ""),
                json.dumps(record.get("analysis", {}), ensure_ascii=False),
                json.dumps(record.get("retrieved_kb_ids", []), ensure_ascii=False),
                json.dumps(record.get("generated_version", {}), ensure_ascii=False),
                record.get("operator_edited", ""),
                record.get("final_sent", ""),
                record.get("style_used", ""),
                1 if record.get("modified") else 0,
            ),
        )
        conn.commit()
        return cur.lastrowid


def list_reply_logs(limit: int = 100) -> list[dict]:
    with _lock, _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM replies_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("analysis", "retrieved_kb_ids", "generated_version"):
            if d.get(k):
                try:
                    d[k] = json.loads(d[k])
                except json.JSONDecodeError:
                    pass
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Dashboard 统计（真实统计 + Demo 基线）
# ---------------------------------------------------------------------------
DEMO_STATS = {
    "today_creators": 42,
    "avg_reply_seconds": 8,
    "direct_use_rate": 68,
    "manual_edit_rate": 22,
    "high_risk_messages": 5,
    "top_scenarios": [
        {"name": "样品申请", "count": 12},
        {"name": "催视频", "count": 9},
        {"name": "报价沟通", "count": 7},
        {"name": "Ad Code", "count": 5},
        {"name": "换样品", "count": 4},
    ],
    "style_distribution": [
        {"style": "真诚友好", "count": 58},
        {"style": "简洁直接", "count": 23},
        {"style": "高情商推进", "count": 19},
    ],
}


def dashboard_stats() -> dict:
    with _lock, _conn() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM replies_log").fetchone()["c"]
        modified = conn.execute(
            "SELECT COUNT(*) c FROM replies_log WHERE modified=1"
        ).fetchone()["c"]
        styles = conn.execute(
            "SELECT style_used, COUNT(*) c FROM replies_log WHERE style_used!='' GROUP BY style_used"
        ).fetchall()
    stats = dict(DEMO_STATS)
    stats["saved_replies"] = total
    if total > 0:
        stats["direct_use_rate"] = round((total - modified) / total * 100)
        stats["manual_edit_rate"] = round(modified / total * 100)
        style_map = {r["style_used"]: r["c"] for r in styles}
        stats["style_distribution"] = [
            {"style": s["style"], "count": style_map.get(s["style"], 0)}
            for s in DEMO_STATS["style_distribution"]
        ]
    return stats


# ---------------------------------------------------------------------------
# LLM 配置（页面可配置，持久化到数据库；优先于环境变量）
# ---------------------------------------------------------------------------
def get_llm_config() -> dict:
    with _lock, _conn() as conn:
        row = conn.execute("SELECT config FROM llm_config WHERE id=1").fetchone()
    if row is None:
        return {}
    try:
        return json.loads(row["config"])
    except json.JSONDecodeError:
        return {}


def save_llm_config(cfg: dict):
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO llm_config (id, config) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET config=excluded.config",
            (json.dumps(cfg, ensure_ascii=False),),
        )
        conn.commit()
