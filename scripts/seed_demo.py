"""预置 Demo 达人档案（可在页面中管理）"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import store  # noqa: E402

store.init_db()

DEMO_CREATORS = [
    {
        "nickname": "ももんがちゃん",
        "account": "@momo_nga_chan",
        "level": "中腰部达人 (10万-50万粉)",
        "vertical": "美妆 / 日常 / 手机配件",
        "audience_profile": "女性为主 18-35岁，关注性价比与新品",
        "history": "暂无合作记录",
        "current_product": "KORI 高透明クリアケース",
        "cooperation_stage": "达人感兴趣",
        "commission_pref": "成果报酬可接受，未明确报价",
        "quote_status": "未报价",
        "special_requirements": "偏好高透明款，喜欢安静风格内容",
        "notes": "回复积极，可优先推进样品申请",
        "conversation_summary": "已发送邀约与样品卡，达人回复有兴趣",
    },
    {
        "nickname": "ヒカルちゃん",
        "account": "@hikaru_review",
        "level": "头部达人 (100万+粉)",
        "vertical": "数码 / 测评",
        "audience_profile": "男性为主 20-40岁，关注参数与实用性",
        "history": "无",
        "current_product": "MagicStand Pro",
        "cooperation_stage": "报价沟通",
        "commission_pref": "要求固定报酬",
        "quote_status": "达人询问单条固定报酬",
        "special_requirements": "需要制作费，倾向有偿合作",
        "notes": "高风险场景，报价需人工确认，不得自行承诺",
        "conversation_summary": "达人询问视频制作固定报酬金额",
    },
    {
        "nickname": "ゆきち",
        "account": "@yukichi_life",
        "level": "尾部达人 (1万-10万粉)",
        "vertical": "生活 / 收纳 / 手机壳",
        "audience_profile": "女性为主 25-40岁，家居生活向",
        "history": "已接收样品",
        "current_product": "マット指紋防止ケース",
        "cooperation_stage": "催拍/催发",
        "commission_pref": "未特别要求",
        "quote_status": "",
        "special_requirements": "近期较忙",
        "notes": "避免施压，轻量跟进",
        "conversation_summary": "达人表示最近忙，还没开始拍摄",
    },
    {
        "nickname": "テック男子ケン",
        "account": "@ken_gadget",
        "level": "中腰部达人 (10万-50万粉)",
        "vertical": "数码 / 3C",
        "audience_profile": "男性为主，极客向",
        "history": "无",
        "current_product": "LINKOO ストラップケース",
        "cooperation_stage": "样品申请",
        "commission_pref": "未明确",
        "quote_status": "",
        "special_requirements": "询问是否有支架款",
        "notes": "产品咨询场景，确认库存与型号后回复",
        "conversation_summary": "达人询问是否有带支架的手机壳",
    },
    {
        "nickname": "ミナミ",
        "account": "@minami_daily",
        "level": "尾部达人 (1万-10万粉)",
        "vertical": "生活 / Vlog",
        "audience_profile": "女性为主 20-35岁",
        "history": "样品已发货",
        "current_product": "KORI 高透明クリアケース",
        "cooperation_stage": "物流异常",
        "commission_pref": "未特别要求",
        "quote_status": "",
        "special_requirements": "物流显示送达但未收到",
        "notes": "物流异常：不得承诺到货时间，人工查单",
        "conversation_summary": "达人反馈 TikTok 显示配达済み但实际未收到",
    },
]

for c in DEMO_CREATORS:
    store.upsert_creator(c)
    print(f"seeded: {c['nickname']}")

print(f"\n当前共 {len(store.list_creators())} 位达人")
