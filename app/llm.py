"""LLM 生成服务：
- 配置了 OpenAI 兼容接口（环境变量或页面配置）时走真实 LLM
- 未配置时降级为“演示生成器”（基于 RAG 案例 + 规则引擎的确定性生成），保证流程可跑通
"""
import json
import re
from copy import deepcopy

from . import config
from . import prompts
from . import store

REPLY_STYLES = ["真诚友好", "简洁直接", "高情商推进"]


# ---------------------------------------------------------------------------
# LLM 配置：环境变量优先，其次数据库（页面可配置）
# ---------------------------------------------------------------------------
def get_effective_llm_config() -> dict:
    cfg = {
        "base_url": config.LLM_BASE_URL,
        "api_key": config.LLM_API_KEY,
        "model": config.LLM_MODEL,
    }
    db_cfg = store.get_llm_config()
    for k in ("base_url", "api_key", "model"):
        v = db_cfg.get(k, "").strip()
        if v:
            cfg[k] = v
    return cfg


# ---------------------------------------------------------------------------
# OpenAI 兼容客户端
# ---------------------------------------------------------------------------
class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def chat(self, system: str, user: str, temperature: float = 0.7, timeout: int = 120) -> str:
        import httpx

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]


def _client() -> LLMClient | None:
    cfg = get_effective_llm_config()
    if cfg["base_url"] and cfg["api_key"]:
        return LLMClient(
            cfg["base_url"], cfg["api_key"], cfg["model"] or "gpt-4o-mini"
        )
    return None


def llm_status() -> dict:
    c = _client()
    cfg = get_effective_llm_config()
    return {
        "configured": c is not None,
        "base_url": cfg["base_url"] or "",
        "model": cfg["model"] or "",
        "mode": "llm" if c else "demo",
        "mode_label": "AI Mode（真实LLM）" if c else "Demo Mode（规则生成）",
    }


def test_llm_connection() -> dict:
    """测试 LLM 接口连通性（发一条最小请求）。"""
    c = _client()
    if c is None:
        return {"ok": False, "error": "未配置 LLM（缺少 base_url 或 api_key）"}
    try:
        raw = c.chat(
            "你是测试助手，请只回复 OK 两个字母。",
            "测试连通性。",
            temperature=0.0,
            timeout=20,
        )
        return {"ok": True, "model": c.model, "reply": raw.strip()[:100]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 演示生成器：确定性分析 + 基于案例改写回复（无 LLM Key 时保证流程可用）
# ---------------------------------------------------------------------------
def _demo_analysis(message: str, stage: str, risk: dict) -> dict:
    m = message.lower()

    # 意图识别
    intent = "其他"
    if any(k in m for k in ["興味", "感兴趣", "ありがとう"]):
        intent = "达人感兴趣"
    elif any(k in m for k in ["固定報酬", "いくら", "多少钱", "報酬", "費用"]):
        intent = "询问固定报酬/报价"
    elif any(k in m for k in ["まだ撮影", "できていません", "忙しく", "还没拍"]):
        intent = "视频进度说明（催拍场景）"
    elif any(k in m for k in ["ありますか", "ありますか？", "はありますか", "有没有"]):
        intent = "产品咨询"
    elif any(k in m for k in ["配達済み", "届いていません", "没收到", "届かない"]):
        intent = "物流异常反馈"
    elif any(k in m for k in ["キャンセル", "やめ", "不合作"]):
        intent = "终止合作意向"

    # 情绪识别
    emotion = "中性"
    if any(k in m for k in ["ありがとう", "興味", "嬉しい", "楽しみ"]):
        emotion = "积极 / 有合作兴趣"
    elif any(k in m for k in ["申し訳", "すみません", "抱歉"]):
        emotion = "礼貌 / 略带歉意"
    elif any(k in m for k in ["忙しく", "なかなか", "難しい"]):
        emotion = "有压力 / 中性"
    elif any(k in m for k in ["ひどい", "最悪", "怒", "投诉", "不满"]):
        emotion = "不满 / 情绪波动"

    # 流失风险
    loss_risk = "低"
    if any(k in m for k in ["やめ", "キャンセル", "不合作", "辞退"]):
        loss_risk = "高"
    elif any(k in m for k in ["固定報酬", "いくら", "報酬", "費用", "忙しく"]):
        loss_risk = "中"

    stage_guess = stage or "其他"
    if intent == "达人感兴趣":
        stage_guess = "达人感兴趣"
    elif intent == "询问固定报酬/报价":
        stage_guess = "报价沟通"
    elif intent == "视频进度说明（催拍场景）":
        stage_guess = "催拍/催发"
    elif intent == "物流异常反馈":
        stage_guess = "物流异常"

    return {
        "intent": intent,
        "emotion": emotion,
        "cooperation_stage": stage_guess,
        "questions_to_answer": _demo_questions(message),
        "hidden_concerns": _demo_concerns(message),
        "risk_level": risk["risk_level"],
        "risk_flag": risk["risk_flag"],
        "manual_confirmation": risk["manual_confirmation"],
        "recommended_next_action": _demo_next_action(intent, risk),
    }


def _demo_questions(message: str) -> list[str]:
    q = []
    m = message.lower()
    if any(k in m for k in ["固定報酬", "いくら", "多少钱", "報酬", "費用", "単価"]):
        q.append("是否支持固定报酬")
        q.append("一条视频报价是多少")
    if any(k in m for k in ["ありますか", "有没有"]):
        q.append("该产品是否有现货/对应型号")
    if any(k in m for k in ["配達済み", "届いていません", "没收到", "届かない"]):
        q.append("物流显示已送达但未收到，如何核实")
    if any(k in m for k in ["まだ撮影", "できていません"]):
        q.append("（说明拍摄尚未完成，需确认新计划）")
    if not q:
        q.append("（无明确待回答问题，可推进合作）")
    return q


def _demo_concerns(message: str) -> list[str]:
    c = []
    m = message.lower()
    if any(k in m for k in ["固定報酬", "報酬", "費用", "いくら", "多少钱"]):
        c.append("达人希望确认创作成本是否有保障，不希望无偿制作内容")
    if any(k in m for k in ["忙しく", "まだ撮影"]):
        c.append("达人近期时间紧张，担心承诺后无法按时交付")
    if any(k in m for k in ["配達済み", "届いていません"]):
        c.append("达人担心包裹丢失或平台信息不准，影响合作信任")
    if any(k in m for k in ["ありますか", "有没有"]):
        c.append("达人希望确认产品是否匹配自己的机型/需求")
    if not c:
        c.append("达人希望明确下一步如何推进")
    return c


def _demo_next_action(intent: str, risk: dict) -> str:
    if risk["risk_flag"]:
        return "说明当前合作政策，同时保留后续合作空间（涉及权限，先确认再承诺）"
    if intent == "达人感兴趣":
        return "引导达人申请样品，推进到样品环节"
    if intent == "视频进度说明（催拍场景）":
        return "表示理解并给出轻量确认，约定一个不施压的跟进时间"
    if intent == "物流异常反馈":
        return "承接问题，说明将内部核实物流状态并回复"
    if intent == "产品咨询":
        return "介绍当前可提供的产品/型号并引导选择"
    return "回应达人来意并给出清晰的下一步动作"


# 回复改写：基于检索案例 + 风险规则生成 3 个风格版本
def _demo_replies(message: str, examples: list[dict], risk: dict, tone: str, length: str) -> list[dict]:
    m = message.lower()
    is_fixed_fee = any(k in m for k in ["固定報酬", "いくら", "多少钱", "報酬", "費用", "有償"])
    is_video_delay = any(k in m for k in ["まだ撮影", "できていません", "忙しく"])
    is_interest = any(k in m for k in ["興味", "ありがとう"])
    is_logistics = any(k in m for k in ["配達済み", "届いていません", "届かない", "没收到"])
    is_product = any(k in m for k in ["ありますか", "はありますか", "有没有", "スタンド"])

    # 从案例中提取可用策略（仅作风格参考，不复制数字）
    example_hints = []
    for ex in examples:
        goal = ex.get("communication_goal", "")
        if goal:
            example_hints.append(goal)
    hint = "；".join(example_hints[:2]) if example_hints else "保持礼貌、清晰给出下一步"

    def wrap(text: str) -> str:
        return text.strip()

    if is_fixed_fee:
        t1 = (
            "ご質問ありがとうございます😊\n"
            "恐れ入りますが、現時点では固定報酬でのお取り組みは行っておりません。"
            "現在は「無料サンプル＋成果報酬（コミッション）＋広告サポート」の形でご一緒いただいております。"
            "初回の結果が良好でしたら、次回以降のご相談も可能になる可能性がございますので、"
            "まずは一度、商品をお試しいただく形はいかがでしょうか？"
        )
        c1 = (
            "谢谢您的询问😊。非常抱歉，目前我们不接受固定报酬。"
            "现在采用「免费样品＋佣金（CPS）＋广告支持」的形式合作。"
            "如果首次效果不错，后续再商议也是可能的，不如先试用一次样品？"
        )
        t2 = (
            "ご質問ありがとうございます。現時点では固定報酬はお受けしておりません。"
            "現在は無料サンプル＋成果報酬＋広告サポートでのご協力となります。"
            "初回の成果次第で次回以降のご相談が可能になりますので、ご検討いただけますと幸いです。"
        )
        c2 = (
            "谢谢您的询问。目前我们不接受固定报酬，采用免费样品＋佣金＋广告支持的形式。"
            "若首次成果良好，后续可再商议，请考虑一下。"
        )
        t3 = (
            "ご質問ありがとうございます🙏 率直に申し上げますと、現段階では固定報酬のご用意がなく、"
            "大変申し訳ございません。ただ、私どもは初回コラボで実績を出していただいた方には"
            "「広告サポートを重点投入」するなど、結果にコミットした形でサポートさせていただいております。"
            "まずは一度お試しいただき、相性を見ていただくのはいかがでしょうか？"
            "詳細は担当者に確認して改めてご連絡いたします。"
        )
        c3 = (
            "谢谢您的询问🙏。坦率地说，现阶段我们没有固定报酬预算，非常抱歉。"
            "不过对于首次合作能出成绩的达人，我们会以「重点投放广告支持」等方式，按结果来配合支持。"
            "不如先试用一次，看看彼此合不合拍？详情我会让负责人确认后再联系您。"
        )
    elif is_video_delay:
        t1 = (
            "こんにちは😊 お忙しいところ、ご連絡ありがとうございます。"
            "お忙しいとのこと、無理なさらないでくださいね。"
            "商品はお手元にあるようですので、落ち着いたタイミングで撮影いただければ大丈夫です。"
            "もし撮影で何かお困りのことがあれば、いつでもご相談ください！"
        )
        c1 = (
            "您好😊。谢谢您百忙之中联系。听说您最近很忙，请别勉强自己。"
            "商品应该已经在您手上了，您方便的时候拍摄就好。拍摄中如果有什么困难，随时商量！"
        )
        t2 = (
            "お世話になっております。お忙しいとのこと、承知しました。"
            "撮影はご都合の良いタイミングで大丈夫です。"
            "もし撮影のご予定が立った際に教えていただけますと、こちらもサポートできます。"
        )
        c2 = (
            "辛苦了。知道您忙，我们明白了。拍摄请在您方便的时候进行即可。"
            "如果定下拍摄计划请告诉我们，我们也好配合支持。"
        )
        t3 = (
            "こんにちは！お返事ありがとうございます。お忙しい中すみません🙇‍♀️"
            "撮影のことは急かせていただきませんので、ご自身のペースで進めてくださいね。"
            "ただ、もし「素材が足りない」「構成が迷っている」などありましたら、"
            "台本や参考動画をすぐお送りしますので、遠慮なく言ってください✨"
        )
        c3 = (
            "您好！谢谢您的回复。知道您最近很忙，打扰了很抱歉🙇‍♀️。"
            "拍摄的事我们不会催，请按您自己的节奏来。如果「素材不够」「不知道怎么构图」之类的情况，"
            "我们可以马上发脚本或参考视频，请别客气直接说✨"
        )
    elif is_logistics:
        t1 = (
            "ご連絡ありがとうございます🙇‍♀️ システム上は配達完了と表示されているのに"
            "お手元に届いていないとのこと、ご不安をおかけして申し訳ございません。"
            "実際の配送状況を確認いたしますので、少々お時間をいただけますでしょうか。"
            "確認でき次第、すぐにご連絡いたします。"
        )
        c1 = (
            "谢谢您的联系🙇‍♀️。系统上显示已送达，却还没到您手上，让您担心了，非常抱歉。"
            "我们会去确认实际配送情况，请稍等。确认后立刻联系您。"
        )
        t2 = (
            "ご連絡ありがとうございます。配達完了表示があるものの未着とのこと、"
            "配送状況を確認いたします。確認後にご連絡いたしますので、今しばらくお待ちください。"
        )
        c2 = (
            "谢谢您的联系。系统显示已送达但您未收到，我们会确认配送状态。"
            "确认后联系您，请再稍等一下。"
        )
        t3 = (
            "ご不便をおかけして申し訳ございません🙏 システム上は「配達済み」になっているのに"
            "お手元に届いていないとのこと、本当に心配ですね。"
            "私から配送状況を調べさせていただきます。もしお近くの配送状況をご確認いただける場合は、"
            "追跡番号をお知らせいただけると確認がスムーズです。結果をご連絡しますね。"
        )
        c3 = (
            "给您带来不便非常抱歉🙏。系统显示「已送达」却没到您手上，真的很让人担心。"
            "我去查一下配送情况。如果您方便确认附近的配送状态或提供追踪号，会更快。确认后联系您。"
        )
    elif is_product:
        t1 = (
            "お問い合わせありがとうございます😊 スタンド付きケースについてですね。"
            "現在ご用意できる商品を確認し、ご希望に合うものをご案内させていただきます。"
            "お使いのiPhone機種を教えていただけますか？"
        )
        c1 = (
            "谢谢您的咨询😊。您问的是带支架的手机壳对吧。"
            "我们会确认现在可提供的商品，给您推荐合适的。请告诉我您使用的 iPhone 机型好吗？"
        )
        t2 = (
            "お問い合わせありがとうございます。スタンド付きケースの在庫・商品について確認いたします。"
            "お使いのiPhone機種をお教えいただけますと、ご案内がスムーズです。"
        )
        c2 = (
            "谢谢您的咨询。关于带支架手机壳的库存和商品，我们会确认。"
            "请告知您的 iPhone 机型，方便我们推荐。"
        )
        t3 = (
            "ご質問ありがとうございます！スタンド付きケースをご希望とのこと、"
            "現在のラインナップを確認させてくださいね。もし現行品に該当がなければ、"
            "似たご要望に合う代替商品をご提案いたします。機種を教えていただけますか？"
        )
        c3 = (
            "谢谢您的咨询！您想要带支架的手机壳，我们会先确认现有的产品线。"
            "如果目前没有正好合适的，也会推荐类似的替代商品。请告诉我机型好吗？"
        )
    elif is_interest:
        t1 = (
            "ご返信ありがとうございます！ご興味をお持ちいただき嬉しいです😊"
            "もしよろしければ、サンプルカードからお好みのケースを1点お選びいただき、"
            "TikTok Shopよりご申請ください。確認でき次第、すぐに発送準備を進めます📦✨"
        )
        c1 = (
            "谢谢您的回复！很高兴您感兴趣😊。如果可以的话，请从样品卡中挑选一款喜欢的手机壳，"
            "通过 TikTok Shop 申请。我们确认后会马上安排发货📦✨"
        )
        t2 = (
            "ご返信ありがとうございます。ご興味いただけて嬉しいです。"
            "お手数ですがサンプルカードから1点お選びいただき、TikTok Shopで申請をお願いします。"
            "確認後すぐ発送手配します。"
        )
        c2 = (
            "谢谢您的回复，很高兴您感兴趣。麻烦您从样品卡中选一款，在 TikTok Shop 申请。"
            "确认后我们立刻安排发货。"
        )
        t3 = (
            "ご返信ありがとうございます！興味を持っていただけて本当に嬉しいです✨"
            "まずは実際に手に取っていただくのが一番かと思いますので、"
            "サンプルを1点ご申請ください。ご希望のタイプが分かれば、より合う商品もご案内できます😊"
        )
        c3 = (
            "谢谢您的回复！您能感兴趣我们真的很开心✨。建议您先实际拿到手体验一下，请申请一款样品。"
            "如果知道您喜欢的类型，我们也能推荐更合适的商品😊"
        )
    else:
        t1 = (
            "ご連絡ありがとうございます😊 お話を伺いました。"
            "ご希望に沿えるよう確認いたしますので、少々お時間をいただけますでしょうか。"
            "確認でき次第、改めてご連絡いたします。"
        )
        c1 = (
            "谢谢您的联系😊。我们已经了解您的情况。我们会确认以便符合您的需求，请稍等。"
            "确认后我们会再联系您。"
        )
        t2 = "ご連絡ありがとうございます。内容を確認いたします。確認後改めてご連絡いたします。"
        c2 = "谢谢您的联系。我们会确认内容，之后回复您。"
        t3 = (
            "ご連絡ありがとうございます！大切なご相談をいただき、ありがとうございます。"
            "すぐに担当者と確認し、最適なご案内を準備いたします。今しばらくお待ちいただけますか？"
        )
        c3 = (
            "谢谢您的联系！收到您重要的咨询，非常感谢。我们会马上和负责人确认，"
            "准备最合适的方案。请稍等片刻可以吗？"
        )

    replies = [
        {"style": "真诚友好", "text": wrap(t1), "translation": c1},
        {"style": "简洁直接", "text": wrap(t2), "translation": c2},
        {"style": "高情商推进", "text": wrap(t3), "translation": c3},
    ]

    # 长度控制（日文与中文翻译同步截断）
    if length == "短":
        for r in replies:
            sentences = re.split(r"(?<=[。！？!?])", r["text"])
            r["text"] = "".join(sentences[:2]).strip()
            zh_sent = re.split(r"(?<=[。！？!?])", r.get("translation", ""))
            r["translation"] = "".join(zh_sent[:2]).strip()
    elif length == "长":
        for r in replies:
            r["text"] = r["text"]

    return replies


# ---------------------------------------------------------------------------
# 统一入口
# ---------------------------------------------------------------------------
def _extract_json(text: str) -> dict:
    """从 LLM 输出中稳健提取 JSON。"""
    text = text.strip()
    # 去除 ```json 包裹
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    raise ValueError("LLM 输出不是合法 JSON")


def _merge_demo(demo: dict, llm_raw: dict | None, risk: dict) -> dict:
    """真实 LLM 结果与演示结果的合并策略：
    - LLM 成功时：analysis 文本字段 / replies / retrieval 用 LLM 的
    - 风险字段（risk_flag/risk_level/manual_confirmation）一律以规则引擎为准（权限优先于话术）
    """
    if llm_raw is None:
        return demo
    merged = deepcopy(demo)
    llm_analysis = llm_raw.get("analysis", {}) or {}
    analysis = merged.get("analysis", {})

    # 文本判断字段（intent/emotion/questions/concerns/next_action 等）用 LLM 的
    for k, v in llm_analysis.items():
        if k in ("risk_flag", "risk_level", "manual_confirmation"):
            continue  # 风险字段由规则引擎兜底
        if v not in (None, "", [], {}):
            analysis[k] = v
    merged["analysis"] = analysis

    if llm_raw.get("replies"):
        demo_replies = demo.get("replies", [])
        merged_replies = []
        for idx, lr in enumerate(llm_raw["replies"]):
            if not lr.get("translation") and idx < len(demo_replies):
                lr["translation"] = demo_replies[idx].get("translation", "")
            merged_replies.append(lr)
        merged["replies"] = merged_replies
    if llm_raw.get("retrieval"):
        merged["retrieval"] = llm_raw["retrieval"]
    return merged


def generate(
    message: str,
    stage: str,
    goal: str,
    tone: str,
    length: str,
    product: str,
    platform: str,
    creator: dict | None,
    brand_rules: dict | None,
    retrieval: dict,
    risk: dict,
    operator_notes: str = "",
) -> dict:
    """生成完整响应：analysis + replies + retrieval。"""
    examples = [r["entry"] for r in retrieval["results"]]
    demo = {
        "analysis": _demo_analysis(message, stage, risk),
        "replies": _demo_replies(message, examples, risk, tone, length),
        "retrieval": {
            "used_kb_ids": retrieval["used_ids"],
            "why_these_examples": retrieval["why"],
        },
    }

    client = _client()
    if client is None:
        demo["mode"] = "demo"
        return demo

    # 组装 LLM 上下文
    creator = creator or {}
    brand_rules = brand_rules or {}
    products = brand_rules.get("current_products", [])
    product_lines = "\n".join(
        f"- {p.get('name', p) if isinstance(p, dict) else p}"
        + (f"：{p.get('desc', '')}" if isinstance(p, dict) and p.get("desc") else "")
        for p in products
    ) or "（未配置）"

    examples_text = ""
    for i, ex in enumerate(examples, 1):
        examples_text += (
            f"[案例{i}] id={ex.get('id')} 分类={ex.get('category')} "
            f"场景={ex.get('scenario')} 阶段={ex.get('cooperation_stage')} "
            f"沟通目标={ex.get('communication_goal')} 风险={ex.get('risk_level')}\n"
            f"使用限制：{ex.get('notes', '')}\n"
            f"历史话术片段（仅作策略参考，动态数字必须按品牌规则覆盖）：\n{ex.get('source_text', '')[:800]}\n\n"
        )

    forbidden_words = "、".join(brand_rules.get("forbidden_words", []) or []) or "（无）"
    forbidden_promises = "、".join(brand_rules.get("forbidden_promises", []) or []) or "（无）"

    user_prompt = f"""请完成达人消息分析并生成3种回复（JSON输出）。

达人消息：
{message}

沟通平台：{platform}
回复语言：日语（自然、达人BD口吻）
回复语气：{tone}　回复长度：{length}

【达人档案】
达人昵称：{creator.get('nickname', '未指定')}
达人等级：{creator.get('level', '')}
内容领域：{creator.get('vertical', '')}
粉丝画像：{creator.get('audience_profile', '')}
历史合作：{creator.get('history', '')}
历史沟通摘要：{creator.get('conversation_summary', '')}
当前合作阶段：{stage or '未指定'}
本轮沟通目标：{goal or '自动判断'}

【当前品牌规则】（知识库历史话术中的动态信息一律以本规则为准）
品牌：CASEKOO（{brand_rules.get('market', 'JP')} / {brand_rules.get('platform', 'TikTok Shop')}）
当前佣金规则：{brand_rules.get('current_commission', '未配置')}
固定费用权限：{'允许' if brand_rules.get('fixed_fee_allowed') else '不允许'}（{brand_rules.get('fixed_fee_range', '')}）
广告支持：{brand_rules.get('ad_support', '未配置')}
样品规则：{brand_rules.get('sample_policy', '未配置')}
物流规则：{brand_rules.get('shipping_policy', '未配置')}
促销配置：{brand_rules.get('promotion_info', '未配置')}
当前产品：\n{product_lines}
当前产品/型号：{product or '未指定'}
库存状态：{json.dumps(brand_rules.get('inventory_status', {}), ensure_ascii=False) or '未配置'}
禁用词：{forbidden_words}
不可承诺事项：{forbidden_promises}

【RAG检索到的历史案例】（仅提供“过去怎么说”的经验，不是当前政策，禁止照抄数字）
{examples_text}

【风险引擎判断】（必须遵循）
risk_flag={risk['risk_flag']} risk_level={risk['risk_level']}
需人工确认事项：{risk['manual_confirmation']}

运营备注：{operator_notes or '（无）'}

请严格按 System Prompt 中的 JSON 输出规范返回。"""
    try:
        raw = client.chat(prompts.SYSTEM_PROMPT, user_prompt, temperature=config.LLM_TEMPERATURE)
        llm_json = _extract_json(raw)
        result = _merge_demo(demo, llm_json, risk)
        result["mode"] = "llm"
        return result
    except Exception as e:
        print(f"[llm] LLM 调用失败，降级为演示生成器: {e}")
        demo["mode"] = "demo"
        demo["llm_error"] = str(e)[:200]
        return demo


# ---------------------------------------------------------------------------
# 二次改写（重新生成单个版本）
# ---------------------------------------------------------------------------
def _demo_restyle(text: str, style: str, length: str) -> dict:
    """演示模式的改写：基于规则做轻量变换。翻译交由前端沿用原版本（演示模式不重新翻译）。"""
    t = text.strip()
    if style == "缩短":
        sentences = re.split(r"(?<=[。！？!?])", t)
        return {"text": "".join(sentences[:2]).strip(), "translation": ""}
    if style == "扩写":
        return {"text": t.rstrip() + (
            "\nもしご不明な点やご希望がございましたら、いつでもお気軽にご連絡ください。"
            "できる限りサポートさせていただきます😊"
        ), "translation": ""}
    if style == "更亲切":
        t = t.replace("ご連絡ありがとうございます", "ご連絡ありがとうございます😊")
        t = t.replace("お忙しいところ", "お忙しいところ、本当にありがとうございます")
        if "無理なさらない" not in t:
            t += "\nどうぞご無理のない範囲でお願いいたします🙇‍♀️"
        return {"text": t, "translation": ""}
    if style == "更真诚":
        t = t.replace("恐れ入りますが", "正直にお伝えすると、恐れ入りますが")
        t += "\n率直なお気持ちをお聞かせいただき、ありがとうございます。私たちも真摯に対応させていただきます。"
        return {"text": t, "translation": ""}
    if style == "不要催太明显":
        t = t.replace("ご都合の良いタイミングで", "お気が向いたときで大丈夫です")
        t = t.replace("ご対応いただけますと幸いです", "ご対応いただける範囲で大丈夫です")
        t = t.replace("お手数ですが", "もしお手間でなければ")
        if "お時間" not in t:
            t += "\nお時間のご都合に合わせて、いつでもご連絡くださいね😊"
        return {"text": t, "translation": ""}
    return {"text": t, "translation": ""}


REWRITE_SYSTEM = (
    "你是达人合作沟通助手。你必须且只能输出一个 JSON 对象，"
    "格式：{\"text\": \"改写后的日语回复正文\", \"translation\": \"对应的中文翻译\"}，"
    "不要输出任何额外文字或代码块标记。"
)


def regenerate_style(req, creator: dict | None) -> dict:
    """针对已有文本按风格要求二次改写，同时产出中文翻译。"""
    style = req.style or "更亲切"
    length = req.length or "中"
    base_text = req.base_text or ""
    demo = _demo_restyle(base_text, style, length)

    client = _client()
    if client is None:
        return {"style": style, "text": demo["text"], "translation": demo["translation"], "based_on": "demo", "mode": "demo"}

    style_instructions = {
        "更亲切": "改写得更有人情味、更温暖，使用更多自然语气的关怀表达，但保持礼貌和专业。",
        "更真诚": "改写得更真诚坦诚，语气自然不客套，减少模板感。",
        "缩短": "大幅缩短，保留核心信息，直接给出下一步动作。",
        "扩写": "适当扩写，补充关心达人的表达，丰富细节但不冗长。",
        "不要催太明显": "降低催促感：去掉时间压力表达，改为完全尊重达人节奏的措辞，同时温和保留确认进度的意图。",
        "重新生成": "换一种自然表达重写一遍，保持原意与礼貌，不重复原句措辞。",
    }
    brand = store.get_brand_rules()
    prompt = f"""请把下面的日语回复改写为“{style}”版本。

改写要求：{style_instructions.get(style, '')}
回复长度：{length}
达人消息原文：{req.message}
合作阶段：{req.stage or '未指定'}
达人昵称：{creator.get('nickname', '') if creator else ''}

【当前品牌规则】（改写时不得引入规则外的承诺）
当前佣金：{brand.get('current_commission', '未配置')}
固定费用权限：{'允许' if brand.get('fixed_fee_allowed') else '不允许'}（{brand.get('fixed_fee_range', '')}）
不可承诺：{'、'.join(brand.get('forbidden_promises', []) or []) or '（无）'}

原回复：
{base_text}

请输出 JSON：
{{"text": "改写后的日语回复正文", "translation": "对应的中文翻译"}}"""
    try:
        raw = client.chat(REWRITE_SYSTEM, prompt, temperature=0.8).strip()
        parsed = _extract_json(raw)
        text = (parsed.get("text") or "").strip()
        translation = (parsed.get("translation") or "").strip()
        if not text:
            text = re.sub(r"^```(?:text|md)?\s*|\s*```$", "", raw).strip()
        return {"style": style, "text": text, "translation": translation, "based_on": "llm", "mode": "llm"}
    except Exception as e:
        print(f"[llm] restyle fallback: {e}")
        return {"style": style, "text": demo["text"], "translation": demo["translation"], "based_on": "demo", "mode": "demo"}
