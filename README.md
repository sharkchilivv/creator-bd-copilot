# Creator BD Copilot — AI达人沟通回复工作台 (MVP)

TikTok Shop 日本站达人 BD / 达人运营的沟通回复工作台。
运营粘贴达人消息 → AI 理解意图/情绪/阶段 → RAG 检索知识库 → 风险校验 → 生成 3 种风格日语回复 → 运营修改/复制/保存。

**核心设计：知识库负责经验，规则库负责边界，AI 负责判断和表达。**

---

## 技术架构

```
达人消息
  ↓
运营填写合作信息（平台/阶段/目标/语气/产品）
  ↓
规则引擎初判风险（报价/法务/投诉/补偿/终止/未确认事实）
  ↓
组装检索 Query（含日→中业务词扩充）
  ↓
multilingual-e5-small Embedding 向量化（384维）
  ↓
FAISS 向量数据库（余弦相似度）
  ↓
召回 Top 12 → 双重打分（全文本 + 结构化轻量字段）+ 阶段/关键词加权 → Top 3
  ↓
品牌规则 + 达人档案 + 历史沟通 + RAG 案例 → LLM
  ↓
风险校验 → 生成 3 个回复版本（真诚友好 / 简洁直接 / 高情商推进）
  ↓
运营选择 / 修改 / 复制 / 采用 → 保存回复记录
```

## 技术选型

| 组件 | 选型 | 说明 |
|---|---|---|
| Embedding | `intfloat/multilingual-e5-small` (384维) | 支持日/中/英多语言，ModelScope 下载，本地加载 |
| 向量数据库 | FAISS (IndexFlatIP) | 部署最简单，索引持久化到 `data/kb_index/`，轻量字段向量预计算 |
| 后端 | Python FastAPI + Uvicorn | |
| 存储 | SQLite | 达人档案 / 品牌规则 / LLM配置 / 回复记录 |
| LLM | OpenAI 兼容接口（可配置） | 未配置 Key 时自动降级为演示生成器 |
| System Prompt | 从《AI达人沟通工作台_系统指令词_v2.md》加载 | 文件缺失时回退内置精简版 |
| 前端 | 原生 HTML/CSS/JS（三栏工作台） | 轻主题、蓝紫 AI 强调色 + 5 步处理链路可视化 |

## 目录结构

```
creator-bd-copilot/
├── app/
│   ├── main.py          # FastAPI 入口与全部 API（含 LLM 配置 API）
│   ├── kb.py            # JSONL 知识库解析 + Chunk 组装
│   ├── embeddings.py    # Embedding 服务（懒加载）
│   ├── vector_store.py  # FAISS 构建/持久化/检索（轻量向量预计算）
│   ├── rag.py           # Query 组装 + 召回 + 双重打分重排
│   ├── risk.py          # 风险规则引擎
│   ├── llm.py           # LLM 客户端 + 演示生成器 + 二次改写
│   ├── prompts.py       # 系统指令词（从 v2 文件加载）
│   └── store.py         # SQLite 存储
├── web/                 # 前端（工作台 / 搜索 / Dashboard）
├── scripts/
│   ├── download_model.py  # 从 ModelScope 下载模型
│   ├── build_index.py     # 构建向量索引
│   ├── seed_demo.py       # 预置 Demo 达人
│   └── mock_llm.py        # 本地 Mock LLM（验证真实链路，无需真实 Key）
└── run.sh               # 一键启动
```

## 启动

```bash
./run.sh
# 打开 http://127.0.0.1:8017
```

### 启用真实 LLM（两种方式，无需重启）

**方式一：环境变量**
```bash
export LLM_BASE_URL="https://api.openai.com/v1"   # 或任意 OpenAI 兼容接口
export LLM_API_KEY="sk-xxx"
export LLM_MODEL="gpt-4o-mini"
./run.sh
```

**方式二：页面配置（推荐演示用）**
点击右上角模式徽章（Demo Mode / AI Mode）→ 填入 base_url / api_key / model → 测试连接 → 保存。
配置持久化到 SQLite，立即生效，无需重启。

不配置时系统使用内置演示生成器（基于 RAG 案例 + 规则引擎），完整流程仍可跑通，
页面右上角显示 **Demo Mode**；配置后切换为 **AI Mode**，真正调用大模型。

> 无真实 Key 时可用 `scripts/mock_llm.py` 启动本地 Mock 服务验证真实链路：
> 配置 `base_url=http://127.0.0.1:8027/v1`、`api_key=mock-key`、`model=mock-llm` 即可。

### System Prompt 加载

核心 System Prompt 直接读取 `AI达人沟通工作台_系统指令词_v2.md`（含意图分析、情绪分析、
合作阶段判断、风险判断、不得虚构事实、不得超权限承诺、历史话术不代表当前政策、
3 种回复风格、JSON 输出规范等全部内容），并在末尾附加 JSON 硬性输出约束。
文件缺失时自动回退内置精简版。

## 页面

- `/` — **工作台**：三栏（达人档案 / AI 回复 / RAG 相关话术），含 5 个 Demo 案例
  - 点击「AI 分析并生成回复」后展示 **5 步处理链路**：意图分析 → 知识库检索 →
    召回展示（ID+匹配度）→ 品牌规则/风险校验 → 生成 3 个回复版本
- `/search` — **话术库搜索**：关键词 + 向量语义混合检索
- `/dashboard` — **Dashboard**：今日处理 / 采用率 / 高风险 / 场景分布 / 回复记录

## Demo 案例（页面一键载入）

| # | 达人消息 | 预期 |
|---|---|---|
| 1 | ありがとうございます！少し興味があります☺️ | 积极 / 感兴趣 → 引导申请样品 |
| 2 | 動画制作の場合、固定報酬はいくらですか？ | 报价沟通 / HIGH RISK / AI 不得自行报价 |
| 3 | まだ撮影できていません。最近少し忙しくて… | 有压力 / 不能催太明显 |
| 4 | スタンド付きのケースはありますか？ | 检索「支架款 / 替代样品」 |
| 5 | TikTokでは配達済み…まだ届いていません | 物流异常 / 不得承诺到货时间 |

## 风险机制

以下场景自动触发 `HIGH RISK` 并标记「需人工确认」，AI 不越权承诺：

- 报价 / 固定费用 / 提高佣金
- 合同 / 版权 / 税务 / 法律
- 投诉 / 舆情 / 公开负面表达
- 补偿 / 赔偿 / 额外资源
- 达人明确终止合作
- 未确认的库存 / 发货时间 / 恢复时间 / 广告预算 / 佣金 / 销量 / 产品参数

## 知识库与品牌规则分离

- **知识库**（`达人BD_AI知识库_v2.jsonl`，57 条场景）：告诉 AI 过去“通常怎么说”
- **品牌规则**（页面右上「⚙ 品牌规则」抽屉，存 SQLite）：告诉 AI 现在“到底能不能这么说”

历史话术中的 10% 佣金、2 万日元预算、缺货、恢复时间等均为**动态字段**，
必须被当前品牌规则覆盖，AI 不得直接照搬。

---

## 安装与配置

### 1. 安装依赖
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量（可选）
```bash
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY 等；留空则使用内置演示生成器
```
> `.env`、`.access_token`、`data/` 已在 `.gitignore` 中排除，不会进入版本库。

### 3. 运行
```bash
./run.sh
# 浏览器打开 http://127.0.0.1:8017
```

### 公开访问（访问门禁）
如需在其它设备访问，可在 `.env` 设置 `APP_ACCESS_TOKEN`，所有页面 / 接口需携带 `?token=` 才能访问。
