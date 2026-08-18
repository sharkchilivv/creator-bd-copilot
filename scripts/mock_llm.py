"""本地 Mock OpenAI 兼容 LLM 服务：用于验证真实 LLM 链路（无真实 Key 时演示）"""
import json
import re

from fastapi import FastAPI, Request

app = FastAPI()


@app.post("/v1/chat/completions")
async def chat(req: Request):
    body = await req.json()
    messages = body.get("messages", [])
    system = messages[0]["content"] if messages else ""
    user = messages[-1]["content"] if messages else ""
    model = body.get("model", "mock-model")

    # 从 user 上下文里提取达人消息
    m = re.search(r"达人消息：\n(.*?)\n\n", user, re.S)
    creator_msg = m.group(1).strip() if m else ""

    # 从 system prompt 检查是否加载了指令词文件内容
    has_system_rules = "达人合作沟通助手" in system and "不得虚构信息" in system

    # 从 user 上下文提取品牌规则
    has_brand_rules = "当前品牌规则" in user
    # 从 user 上下文提取 RAG 案例
    rag_ids = re.findall(r"\[案例\d+\] id=(\S+)", user)
    risk_flag = "risk_flag=True" in user

    # 从达人消息生成 mock 回复
    if "固定報酬" in creator_msg or "いくら" in creator_msg:
        intent = "询问固定报酬"
        emotion = "中性"
        stage = "报价沟通"
        reply_text = (
            "ご質問ありがとうございます😊 恐れ入りますが、現在は初期プロモーション段階のため、"
            "固定報酬でのお取り組みは行っておりません。現在は「無料サンプル＋成果報酬（コミッション）＋"
            "広告サポート」の形でご一緒いただいております。まずは一度お試しいただき、"
            "初回の結果が良好でしたら次回以降のご相談も可能でございます。ご検討のほどよろしくお願いいたします✨"
        )
        questions = ["是否支持固定报酬", "一条视频报价是多少"]
    elif "興味" in creator_msg:
        intent = "达人感兴趣"
        emotion = "积极 / 有合作兴趣"
        stage = "达人感兴趣"
        reply_text = (
            "ご返信ありがとうございます！ご興味をお持ちいただき嬉しいです😊 "
            "お手数ですが、サンプルカードからお好みのケースを1点お選びいただき、"
            "TikTok Shopよりご申請ください。確認でき次第すぐに発送準備を進めます📦✨"
        )
        questions = ["希望申请哪种样品"]
    else:
        intent = "一般咨询"
        emotion = "中性"
        stage = "其他"
        reply_text = "ご連絡ありがとうございます。内容を確認いたしました。ご希望に沿えるよう対応いたします。"
        questions = []

    content = {
        "analysis": {
            "intent": intent,
            "emotion": emotion,
            "cooperation_stage": stage,
            "questions_to_answer": questions,
            "hidden_concerns": ["达人希望确认投入产出，不希望无偿制作内容"] if "固定報酬" in creator_msg else [],
            "risk_level": "high" if risk_flag else "low",
            "risk_flag": risk_flag,
            "manual_confirmation": ["当前是否允许固定报酬（Mock确认）"] if risk_flag else [],
            "recommended_next_action": "说明当前政策并保留未来合作机会" if risk_flag else "推进样品申请",
        },
        "replies": [
            {"style": "真诚友好", "text": reply_text},
            {"style": "简洁直接", "text": "ご質問ありがとうございます。現時点では固定報酬はお受けしておりません。無料サンプル＋成果報酬＋広告サポートでのご協力となります。ご検討ください。"},
            {"style": "高情商推进", "text": reply_text + " まずはお互いの相性を見る形で、ぜひ一度ご一緒できれば嬉しいです。"},
        ],
        "retrieval": {
            "used_kb_ids": rag_ids,
            "why_these_examples": "与当前报价沟通场景高度相关（Mock LLM 返回）",
        },
    }

    # 记录本次调用证据（供验证）
    evidence = {
        "system_loaded_rules": has_system_rules,
        "has_brand_rules": has_brand_rules,
        "rag_ids_from_prompt": rag_ids,
        "model": model,
    }
    print("MOCK_CALL", json.dumps(evidence, ensure_ascii=False))

    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(content, ensure_ascii=False),
                },
                "finish_reason": "stop",
            }
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8027)
