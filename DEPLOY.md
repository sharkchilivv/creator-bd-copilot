# 部署指南：Creator BD Copilot → Railway（云端正式部署）

本指南把项目以 Docker 镜像部署到 Railway，让其他人能在任意设备的浏览器访问。

## 架构要点

- **镜像只包含代码 + 轻量依赖**（Python + FastAPI + CPU 版 torch + sentence-transformers + faiss）。
- **2.1GB 的 Embedding 模型不在镜像内**：首次启动时由 `scripts/ensure_model.py` 自动下载到持久卷 `/data/models`，之后复用，不重复下载。
- **SQLite 数据库 + 模型**都落在 Railway 持久卷 `/data`，重部署不丢数据。
- **FAISS 索引**已烘焙进镜像（只读），无需联网。

## 前置条件

1. 注册 Railway 账号：https://railway.com （可用 GitHub 登录）。
2. **需要支持持久卷的套餐**（Trial 或 Hobby）。Free 套餐不支持持久卷，无法用于本应用。
3. 本机安装 Railway CLI（二选一）：
   - 有 Node：`npm install -g @railway/cli`
   - 有 Homebrew：`brew install railway`
   - 装好后执行 `railway login`（浏览器授权）。

## 部署步骤

```bash
# 1. 进入项目目录
cd /path/to/creator-bd-copilot

# 2. 登录并初始化项目（按提示操作）
railway login
railway init          # 创建一个新项目

# 3. 一键部署（自动检测 Dockerfile，上传当前目录构建）
railway up

# 4. 部署完成后，设置环境变量（把 key 换成你自己的智谱 Key）
railway variables set LLM_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
railway variables set LLM_API_KEY="你的智谱Key"
railway variables set LLM_MODEL="glm-4-flash"

# 5. 添加持久卷（必须）：在 Railway 控制台
#    Service → 右上角 ⋯ → Add Volume → Mount Path 填 /data → Size 选 5GB → 保存后 Redeploy
#    （CLI 也可：railway volume create --mount /data --size 5）

# 6. 生成公网域名
#    Service → Settings → Networking → Generate Domain
#    得到的 https://xxx.up.railway.app 就是给别人访问的地址
```

## 首次启动注意事项

- 第一次启动会**下载 Embedding 模型（约 470MB）**到 `/data/models`，日志里能看到 `[ensure_model]` 进度，通常 1–3 分钟。
- 期间 `/api/health` 可能短暂不可用，等日志出现 `Application startup complete` 即可访问。
- 之后模型已缓存到卷，重启/重部署不再下载。
- 模型下载完成后，LLM 调用走你设置的智谱 Key，回复由真实模型生成。

## 环境变量说明

| 变量 | 容器内默认值 | 说明 |
|------|------|------|
| `DATA_DIR` | `/data` | 持久数据根目录（卷挂载点） |
| `MODEL_DIR` | `/data/models` | 模型下载目录（卷） |
| `INDEX_DIR` | `/app/kb_index` | 烘焙进镜像的只读索引 |
| `DB_FILE` | `/data/copilot.db` | SQLite（卷） |
| `KB_JSONL` | `/app/assets/kb.jsonl` | 知识库（烘焙） |
| `SYSTEM_PROMPT_FILE` | `/app/assets/system_prompt.md` | 系统指令词（烘焙） |
| `LLM_BASE_URL` | 空 | 需设置 |
| `LLM_API_KEY` | 空 | 需设置（建议走变量，不入 SQLite） |
| `LLM_MODEL` | 空 | 需设置，如 `glm-4-flash` |
| `PORT` | Railway 自动注入 | uvicorn 监听端口 |

> 前 6 项已在 Dockerfile 中设好，一般无需改动；只需设置 LLM_* 三项。

## 备选方案（若 Railway 因镜像体积拒绝）

本应用依赖 torch，镜像较大。若 Railway 提示镜像超限，同样这套 Dockerfile 可直接用于 **Render** 或 **Fly.io**（它们对镜像体积更宽松）：

- **Render**：New → Web Service → 选 "Docker" → 同一仓库 → 在 Dashboard 添加 Disk（Mount Path `/data`，5GB）→ 设置 LLM_* 环境变量 → Deploy。
- **Fly.io**：`fly launch`（检测 Dockerfile）→ 编辑 `fly.toml` 加 `[mounts]` 卷挂到 `/data` → `fly deploy`。

## 安全提示

- 公开域名后，任何人都能访问并使用你的智谱额度；建议把智谱 Key 放在 Railway 环境变量里（加密存储），**不要**在网页抽屉里填写（抽屉填写会写入 SQLite）。
- `/api/llm-config` 的 GET 接口已做了脱敏，不会返回明文 Key。
