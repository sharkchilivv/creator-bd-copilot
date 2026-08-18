"""Creator BD Copilot - FastAPI 入口"""
import time
import os
import hmac

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, llm, rag, risk, store, vector_store

app = FastAPI(title="Creator BD Copilot", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# 访问令牌网关（公网暴露时保护隐私/商业数据与 LLM Key）
# 设置环境变量 APP_ACCESS_TOKEN 后，所有请求必须携带令牌（?token= / Cookie / Header）。
# 不设置则该网关自动关闭，本地使用无感。
# ---------------------------------------------------------------------------
ACCESS_TOKEN = (os.environ.get("APP_ACCESS_TOKEN") or "").strip()


@app.middleware("http")
async def access_gate(request: Request, call_next):
    if not ACCESS_TOKEN:
        return await call_next(request)
    tok = (
        request.query_params.get("token")
        or request.cookies.get("copilot_token")
        or request.headers.get("x-access-token")
        or (request.headers.get("authorization") or "")[len("Bearer "):].strip()
    )
    ok = bool(tok) and hmac.compare_digest(tok, ACCESS_TOKEN)
    if ok:
        resp = await call_next(request)
        # 通过 ?token= 首次进入时下发 HttpOnly Cookie，后续同源请求自动携带
        if request.query_params.get("token"):
            resp.set_cookie(
                "copilot_token", ACCESS_TOKEN, httponly=True,
                samesite="lax", max_age=60 * 60 * 24 * 30,
            )
        return resp
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            {"ok": False, "error": "未授权：请携带 ?token= 或 Cookie"},
            status_code=401,
        )
    return HTMLResponse(
        "<!doctype html><meta charset=utf-8><h3>需要访问令牌</h3>"
        "<p>请在网址后追加 <code>?token=你的令牌</code> 再访问。</p>",
        status_code=401,
    )

# 静态前端
app.mount("/static", StaticFiles(directory=config.WEB_DIR), name="static")

# 全局向量库（启动时构建/加载）
_vs: vector_store.VectorStore | None = None


def get_vs() -> vector_store.VectorStore:
    global _vs
    if _vs is None:
        _vs = vector_store.ensure_index()
    return _vs


@app.on_event("startup")
def _startup():
    store.init_db()
    try:
        get_vs()
    except Exception as e:
        print(f"[startup] vector store init failed: {e}")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class GenerateRequest(BaseModel):
    message: str
    platform: str = "TikTok DM"
    stage: str = "其他"
    goal: str = ""
    tone: str = "真诚友好"
    length: str = "中"
    product: str = ""
    keywords: str = ""
    creator_id: int | None = None
    operator_notes: str = ""


class CreatorPayload(BaseModel):
    id: int | None = None
    nickname: str = ""
    account: str = ""
    level: str = ""
    vertical: str = ""
    audience_profile: str = ""
    history: str = ""
    current_product: str = ""
    cooperation_stage: str = ""
    commission_pref: str = ""
    quote_status: str = ""
    special_requirements: str = ""
    notes: str = ""
    conversation_summary: str = ""


class SaveReplyRequest(BaseModel):
    creator_id: int | None = None
    creator_name: str = ""
    original_message: str = ""
    analysis: dict = Field(default_factory=dict)
    retrieved_kb_ids: list[str] = Field(default_factory=list)
    generated_version: dict = Field(default_factory=dict)
    operator_edited: str = ""
    final_sent: str = ""
    style_used: str = ""


class RegenerateRequest(BaseModel):
    message: str
    platform: str = "TikTok DM"
    stage: str = ""
    goal: str = ""
    tone: str = "真诚友好"
    length: str = "中"
    product: str = ""
    keywords: str = ""
    creator_id: int | None = None
    operator_notes: str = ""
    style: str = ""           # 目标重写风格：更亲切/更真诚/缩短/扩写/不要催太明显
    base_text: str = ""       # 原始文本（用于改写）
    previous: dict = Field(default_factory=dict)  # 上一次完整结果


# ---------------------------------------------------------------------------
# 业务 API
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    vs = get_vs()
    return {
        "ok": True,
        "llm": llm.llm_status(),
        "kb": vs.stats(),
        "embedding_model": config.EMBEDDING_MODEL_ID,
    }


# LLM 配置（页面可配置，持久化；环境变量为默认值）
class LLMConfigPayload(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""


@app.get("/api/llm-config")
def api_get_llm_config():
    db_cfg = store.get_llm_config()
    raw_key = db_cfg.get("api_key", config.LLM_API_KEY) or ""
    return {
        "ok": True,
        "config": {
            "base_url": db_cfg.get("base_url", config.LLM_BASE_URL),
            # 出于安全考虑，明文 Key 绝不通过 GET 接口返回（公网暴露时防泄露）
            "api_key": "",
            "api_key_set": bool(raw_key),
            "model": db_cfg.get("model", config.LLM_MODEL),
            "from_db": bool(db_cfg),
            "status": llm.llm_status(),
        },
    }


@app.post("/api/llm-config")
def api_save_llm_config(p: LLMConfigPayload):
    cfg = {
        "base_url": p.base_url.strip().rstrip("/"),
        "api_key": p.api_key.strip(),
        "model": p.model.strip(),
    }
    store.save_llm_config(cfg)
    return {"ok": True, "status": llm.llm_status()}


@app.post("/api/llm-test")
def api_test_llm():
    return {"ok": True, "result": llm.test_llm_connection()}


@app.post("/api/generate")
def generate(req: GenerateRequest):
    t0 = time.time()
    vs = get_vs()
    creator = store.get_creator(req.creator_id) if req.creator_id else None
    brand = store.get_brand_rules()

    # 1) 风险引擎（规则前置）
    risk_result = risk.analyze_risk(req.message)

    # 2) RAG 检索
    retrieval = rag.retrieve(
        vs,
        message=req.message,
        stage=req.stage,
        goal=req.goal,
        product=req.product,
        keywords=req.keywords,
    )

    # 3) LLM 生成
    result = llm.generate(
        message=req.message,
        stage=req.stage,
        goal=req.goal,
        tone=req.tone,
        length=req.length,
        product=req.product,
        platform=req.platform,
        creator=creator,
        brand_rules=brand,
        retrieval=retrieval,
        risk=risk_result,
        operator_notes=req.operator_notes,
    )

    # 4) 补充风险字段（确保 risk 信息完整）
    result["analysis"].setdefault("risk_flag", risk_result["risk_flag"])
    result["analysis"].setdefault("risk_level", risk_result["risk_level"])
    if risk_result["manual_confirmation"] and not result["analysis"].get(
        "manual_confirmation"
    ):
        result["analysis"]["manual_confirmation"] = risk_result["manual_confirmation"]

    return {
        "ok": True,
        "elapsed_ms": int((time.time() - t0) * 1000),
        "risk_engine": risk_result,
        "retrieval_detail": retrieval,
        "result": result,
    }


@app.post("/api/regenerate")
def regenerate(req: RegenerateRequest):
    """针对某版本做二次改写（更亲切/更真诚/缩短/扩写/不要催太明显）。"""
    t0 = time.time()
    result = llm.regenerate_style(req, store.get_creator(req.creator_id) if req.creator_id else None)
    return {
        "ok": True,
        "elapsed_ms": int((time.time() - t0) * 1000),
        "result": result,
    }


# 话术库搜索：关键词 + 向量语义
@app.get("/api/search")
def search_kb(q: str = "", top_k: int = 8):
    vs = get_vs()
    if not q.strip():
        return {"ok": True, "results": []}
    retrieval = rag.retrieve(vs, message=q, stage="", goal="", product="", keywords="", top_k=top_k)
    results = []
    for r in retrieval["results"]:
        e = r["entry"]
        results.append(
            {
                "id": e.get("id"),
                "category": e.get("category"),
                "scenario": e.get("scenario"),
                "cooperation_stage": e.get("cooperation_stage"),
                "communication_goal": e.get("communication_goal"),
                "keywords": e.get("keywords"),
                "risk_level": e.get("risk_level"),
                "priority": e.get("priority"),
                "notes": e.get("notes"),
                "source_text": e.get("source_text"),
                "source_file": e.get("source_file"),
                "match": r["score"],
            }
        )
    return {"ok": True, "results": results}


@app.get("/api/kb/stats")
def kb_stats():
    return {"ok": True, "stats": get_vs().stats()}


# 达人档案
@app.get("/api/creators")
def api_list_creators():
    return {"ok": True, "creators": store.list_creators()}


@app.post("/api/creators")
def api_upsert_creator(p: CreatorPayload):
    cid = store.upsert_creator(p.model_dump())
    return {"ok": True, "id": cid, "creator": store.get_creator(cid)}


@app.delete("/api/creators/{cid}")
def api_delete_creator(cid: int):
    store.delete_creator(cid)
    return {"ok": True}


# 品牌规则
@app.get("/api/brand-rules")
def api_get_rules():
    return {"ok": True, "rules": store.get_brand_rules()}


@app.post("/api/brand-rules")
def api_save_rules(rules: dict):
    store.save_brand_rules(rules)
    return {"ok": True, "rules": store.get_brand_rules()}


# 回复记录
@app.post("/api/replies")
def api_save_reply(req: SaveReplyRequest):
    rid = store.save_reply_log(req.model_dump())
    return {"ok": True, "id": rid}


@app.get("/api/replies")
def api_list_replies(limit: int = 100):
    return {"ok": True, "replies": store.list_reply_logs(limit)}


# Dashboard
@app.get("/api/dashboard")
def api_dashboard():
    return {"ok": True, "stats": store.dashboard_stats()}


# 页面
@app.get("/")
def index():
    return FileResponse(f"{config.WEB_DIR}/index.html")


@app.get("/search")
def search_page():
    return FileResponse(f"{config.WEB_DIR}/search.html")


@app.get("/dashboard")
def dashboard_page():
    return FileResponse(f"{config.WEB_DIR}/dashboard.html")
