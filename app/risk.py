"""风险引擎：命中风险场景 → risk_flag / risk_level / 需人工确认事项"""

RISK_RULES = [
    {
        "name": "报价/佣金/固定费用",
        "level": "high",
        "keywords": [
            "固定報酬", "固定报酬", "有償", "有償案件", "報酬", "ギャラ",
            "いくら", "多少钱", "单条", "1本", "一本", "費用", "制作費", "制作费",
            "佣金", "コミッション", "手数料", "値上げ", "涨价", "提高", "報酬率",
            "単価", "单价", "支払", "支付",
        ],
        "confirm": ["当前是否允许固定报酬/提高佣金（需人工确认）"],
    },
    {
        "name": "法务/合同/版权/税务/法律",
        "level": "high",
        "keywords": [
            "契約", "合同", "法律", "法的", "税金", "税務", "税务", "著作権", "版权",
            "商標", "商标", "訴訟", "诉讼", "弁護士", "律师", "規約", "条款",
        ],
        "confirm": ["涉及法务条款，需法务/人工确认"],
    },
    {
        "name": "投诉/舆情",
        "level": "high",
        "keywords": [
            "ひどい", "酷い", "最悪", "抱怨", "投诉", "不满", "怒り", "怒って",
            "クレーム", "投诉", "晒す", "公开吐槽", "拡散", "扩散", "評判", "差评",
            "返金", "退款", "詐欺", "欺诈",
        ],
        "confirm": ["投诉/舆情类消息，需优先人工处理"],
    },
    {
        "name": "补偿/赔偿/额外资源",
        "level": "high",
        "keywords": [
            "補償", "赔偿", "补偿", "賠償", "追加", "特别対応", "特别资源",
            "特殊対応", "もう1本", "再来一个", "追加商品", "追加サンプル", "プレゼント",
        ],
        "confirm": ["补偿/额外资源请求，需人工确认"],
    },
    {
        "name": "终止合作",
        "level": "high",
        "keywords": [
            "もうやめ", "やめます", "やめたい", "辞退", "降りる", "不合作了",
            "キャンセル", "cancel", "解約", "終了", "もう無理", "これ以上",
        ],
        "confirm": ["达人明确终止合作，仅礼貌挽回一次，不反复纠缠"],
    },
    {
        "name": "物流/未确认事实",
        "level": "high",
        "keywords": [
            "届かない", "未着", "还没到", "配達済み", "显示到货", "没收到",
            "いつ届く", "何时到", "何日", "几天到",
        ],
        "confirm": ["物流时效未确认，不得承诺到货时间，必要时人工查单"],
    },
    {
        "name": "未确认库存/恢复时间",
        "level": "medium",
        "keywords": [
            "在庫", "库存", "欠品", "缺货", "いつ回復", "何时恢复", "いつ復旧",
            "いつ戻る", "発送いつ", "什么时候发", "何时发货",
        ],
        "confirm": ["库存/恢复时间未确认，不得自行承诺"],
    },
    {
        "name": "系统异常/维护",
        "level": "medium",
        "keywords": [
            "メンテナンス", "维护", "復旧", "修复中", "不具合", "故障", "エラー", "异常",
        ],
        "confirm": ["系统恢复时间未确认，不得承诺具体时间"],
    },
    {
        "name": "个人信息收集",
        "level": "medium",
        "keywords": ["住所", "電話番号", "個人情報", "个人信息", "氏名", "姓名", "郵便番号", "地址"],
        "confirm": ["涉及个人信息收集，确认必要性后最小化索取"],
    },
    {
        "name": "iPhone 18 新机未确认参数/发货",
        "level": "high",
        "keywords": [
            "防摔等级", "軍規", "军规", "磁力", "MIL", "ミル",
            "チタン", "钛金属", "何日発送", "いつ発送", "何时发货", "新機いつ", "新机何时",
        ],
        "confirm": ["iPhone 18 未确认产品参数（防摔等级/军规/磁力/材质）与发货时间不得承诺，需人工确认"],
    },
]

# 明确不允许 AI 自行补全的事实类表述
UNVERIFIED_FACT_PATTERNS = [
    "恢复时间", "发货日期", "几天到", "当日到", "库存", "有货", "缺货",
    "广告预算", "佣金比例", "优惠", "折扣", "限时", "销量", "爆款",
    "最安", "最低价", "在庫あり", "在庫", "プレゼント", "赠品", "月曜",
    "周一恢复", "次回", "固定報酬",     "25W", "磁力", "MIL", "跌落",
    "8年", "畅销", "HIKAKIN", "Red Dot", "iF",
    "防摔等级", "軍規", "军规", "チタン", "钛金属", "iPhone 18", "新機発送", "新机发货",
]


def analyze_risk(message: str) -> dict:
    """返回 {risk_flag, risk_level, triggers, manual_confirmation}"""
    triggers = []
    confirms = []
    for rule in RISK_RULES:
        hits = [k for k in rule["keywords"] if k.lower() in message.lower()]
        if hits:
            triggers.append({"rule": rule["name"], "hits": hits})
            confirms.extend(rule["confirm"])
    risk_flag = len(triggers) > 0
    high_rules = {r["name"] for r in RISK_RULES if r["level"] == "high"}
    med_rules = {r["name"] for r in RISK_RULES if r["level"] == "medium"}
    level = "low"
    if any(t["rule"] in high_rules for t in triggers):
        level = "high"
    elif any(t["rule"] in med_rules for t in triggers):
        level = "medium"

    manual_confirmation = list(dict.fromkeys(confirms))
    return {
        "risk_flag": risk_flag,
        "risk_level": level,
        "triggers": triggers,
        "manual_confirmation": manual_confirmation,
    }
