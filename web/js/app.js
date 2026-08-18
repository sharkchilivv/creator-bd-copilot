/* 主工作台逻辑 */
let currentCreator = null;
let creatorsCache = [];
let lastResult = null; // 最近一次完整生成结果
let kbStats = null;

const DEMO_CASES = {
  1: {
    message: "ありがとうございます！\n少し興味があります☺️",
    stage: "达人感兴趣", goal: "推进样品申请",
  },
  2: {
    message: "動画制作の場合、固定報酬はいくらですか？",
    stage: "报价沟通", goal: "保持合作意愿",
  },
  3: {
    message: "まだ撮影できていません。\n最近少し忙しくて…",
    stage: "催拍/催发", goal: "催视频",
  },
  4: {
    message: "スタンド付きのケースはありますか？",
    stage: "样品申请", goal: "引导换样品",
  },
  5: {
    message: "TikTokでは配達済みになっていますが、\nまだ届いていません。",
    stage: "物流异常", goal: "解释异常",
  },
};

/* ---------- 初始化 ---------- */
async function init() {
  await loadCreatorList();
  await loadProducts();
  const h = await API.get("/api/health");
  if (h.ok && h.kb) {
    kbStats = h.kb;
    document.getElementById("kb-count-line").querySelector(".step-txt").textContent =
      `索引就绪：${h.kb.count} 条 Chunk · ${h.kb.dim} 维 · ${h.embedding_model}`;
  }
}
init();

async function loadProducts() {
  const rules = await getRules();
  const sel = document.getElementById("cfg-product");
  sel.innerHTML = '<option value="">（未指定）</option>';
  (rules.current_products || []).forEach((p) => {
    const name = typeof p === "string" ? p : p.name;
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    sel.appendChild(opt);
  });
}

async function loadCreatorList() {
  const res = await API.get("/api/creators");
  creatorsCache = res.creators || [];
  const box = document.getElementById("creator-list");
  if (!creatorsCache.length) {
    box.innerHTML = '<div class="empty" style="padding:16px">暂无达人，点击右上「新建达人」</div>';
    return;
  }
  box.innerHTML = creatorsCache
    .map(
      (c) => `
    <div class="kb-item" onclick="selectCreator(${c.id}, this)" style="padding:10px 12px">
      <div class="flex-between">
        <div class="flex" style="gap:8px">
          <div class="avatar" style="width:32px;height:32px;font-size:13px">${esc((c.nickname || "?").slice(0, 1))}</div>
          <div>
            <div style="font-weight:700;font-size:13.5px">${esc(c.nickname || "未命名达人")}</div>
            <div style="font-size:11.5px;color:var(--text-3)">${esc(c.account || "")}</div>
          </div>
        </div>
        <span class="tag ${stageTagClass(c.cooperation_stage)}">${esc(c.cooperation_stage || "—")}</span>
      </div>
    </div>`
    )
    .join("");
}

function stageTagClass(s) {
  const map = {
    报价沟通: "tag-red", 物流异常: "tag-red", 投诉: "tag-red", 拒绝合作: "tag-red",
    催拍: "tag-orange", "催拍/催发": "tag-orange",
    达人感兴趣: "tag-green", 样品申请: "tag-purple", 发布: "tag-green",
  };
  return map[s] || "tag-gray";
}

function selectCreator(id, el) {
  currentCreator = creatorsCache.find((c) => c.id === id) || null;
  renderCreatorDetail(currentCreator);
  // 联动中栏
  if (currentCreator) {
    if (currentCreator.cooperation_stage && stageOptions.includes(currentCreator.cooperation_stage)) {
      document.getElementById("cfg-stage").value = currentCreator.cooperation_stage;
    }
    if (currentCreator.current_product) {
      const sel = document.getElementById("cfg-product");
      if (![...sel.options].some((o) => o.value === currentCreator.current_product)) {
        const opt = document.createElement("option");
        opt.value = currentCreator.current_product;
        opt.textContent = currentCreator.current_product;
        sel.appendChild(opt);
      }
      sel.value = currentCreator.current_product;
    }
  }
  // 高亮
  document.querySelectorAll("#creator-list .kb-item").forEach((x) => (x.style.borderColor = ""));
  if (el) el.style.borderColor = "var(--primary)";
}

const stageOptions = ["首次邀约", "达人感兴趣", "合作机制确认", "报价沟通", "样品申请", "样品审核",
  "发货", "到货", "视频制作", "催拍", "催发", "发布", "广告投放", "二次合作", "投诉", "拒绝合作", "物流异常", "其他"];

function renderCreatorDetail(c) {
  const el = document.getElementById("creator-detail");
  if (!c) {
    el.innerHTML = '<div class="empty" style="padding:16px">点击左侧达人查看档案，或新建达人</div>';
    return;
  }
  const items = [
    ["等级", c.level], ["内容领域", c.vertical], ["粉丝画像", c.audience_profile],
    ["历史合作", c.history], ["当前产品", c.current_product], ["佣金偏好", c.commission_pref],
    ["报价情况", c.quote_status], ["特殊要求", c.special_requirements],
  ].filter(([, v]) => v);
  el.innerHTML = `
    <div class="divider"></div>
    <div class="info-grid">
      ${items.map(([k, v]) => `<div class="info-item"><span class="k">${k}</span><span class="v">${esc(v)}</span></div>`).join("")}
      ${c.notes ? `<div class="info-item"><span class="k">运营备注</span><span class="v">${esc(c.notes)}</span></div>` : ""}
      ${c.conversation_summary ? `<div class="info-item"><span class="k">沟通摘要</span><span class="v">${esc(c.conversation_summary)}</span></div>` : ""}
    </div>`;
}

function refreshCreators() { loadCreatorList(); }

/* ---------- Demo 案例 ---------- */
function loadDemo(n, el) {
  const d = DEMO_CASES[n];
  if (!d) return;
  document.getElementById("msg-input").value = d.message;
  document.getElementById("cfg-stage").value = d.stage;
  document.getElementById("cfg-goal").value = d.goal;
  document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
  if (el) el.classList.add("active");
  toast(`已载入 Demo ${n}：${d.message.split("\n")[0].slice(0, 24)}…`);
}

/* ---------- 流程状态：5 步可视化 AI 处理链路 ---------- */
const PIPELINE_STEPS = [
  { id: 1, title: "分析达人意图", sub: "理解达人消息 · 情绪 · 合作阶段" },
  { id: 2, title: "检索达人BD知识库", sub: "Embedding 向量化 → FAISS 召回" },
  { id: 3, title: "召回相关历史话术", sub: "同场景历史经验" },
  { id: 4, title: "品牌规则与风险校验", sub: "权限边界 · 风险识别" },
  { id: 5, title: "生成个性化回复", sub: "结合品牌规则 + 达人上下文 + 历史经验" },
];

function renderPipeline() {
  const el = document.getElementById("pipeline");
  el.style.display = "block";
  el.innerHTML = PIPELINE_STEPS.map(
    (s) => `
    <div class="step-line" data-step="${s.id}" id="pline-${s.id}">
      <span class="step-dot">${s.id}</span>
      <div style="flex:1">
        <div class="step-txt" style="flex:1">${s.title} <span class="muted" style="font-weight:400">— ${s.sub}</span></div>
        <div class="step-detail muted" style="font-size:12px;display:none"></div>
      </div>
    </div>`
  ).join("");
}

/* stepId: 1-5, state: pending|running|done, detail: 完成后的详情文字 */
function setStepState(stepId, state, detail) {
  const row = document.getElementById("pline-" + stepId);
  if (!row) return;
  const dot = row.querySelector(".step-dot");
  const detailEl = row.querySelector(".step-detail");
  row.classList.remove("done");
  if (state === "running") {
    dot.innerHTML = '<span class="spinner" style="width:10px;height:10px;border-color:rgba(91,91,214,.3);border-top-color:var(--primary)"></span>';
    detailEl.style.display = "none";
  } else if (state === "done") {
    row.classList.add("done");
    dot.textContent = "✓";
    if (detail) {
      detailEl.textContent = detail;
      detailEl.style.display = "block";
    }
  }
}

/* ---------- 主流程：生成（5 步真实处理链路） ---------- */
async function generate() {
  const message = document.getElementById("msg-input").value.trim();
  if (!message) { toast("请先粘贴达人消息"); return; }

  const btn = document.getElementById("btn-generate");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> AI 分析中…';
  renderPipeline();

  const payload = {
    message,
    platform: document.getElementById("cfg-platform").value,
    stage: document.getElementById("cfg-stage").value,
    goal: document.getElementById("cfg-goal").value,
    tone: document.getElementById("cfg-tone").value,
    length: document.getElementById("cfg-length").value,
    product: document.getElementById("cfg-product").value,
    keywords: document.getElementById("cfg-keywords").value,
    creator_id: currentCreator ? currentCreator.id : null,
  };

  // Step1 播放动画的同时发起真实请求
  setStepState(1, "running");
  const requestPromise = API.post("/api/generate", payload)
    .then((r) => { res = r; return r; })
    .catch((e) => { toast("请求失败：" + e.message); throw e; });

  try {
    // 等待请求返回（约1秒内），随后逐步填充各步骤真实结果
    await Promise.race([
      requestPromise,
      new Promise((r) => setTimeout(r, 800)),
    ]);
    await requestPromise;
    if (!res || !res.ok) throw new Error("生成失败");
    lastResult = res.result;
    const a = res.result.analysis;

    // Step1 完成：意图识别
    setStepState(1, "done", `意图：${a.intent} · 情绪：${a.emotion} · 阶段：${a.cooperation_stage}`);
    await new Promise((r) => setTimeout(r, 380));

    // Step2 完成：知识库检索
    setStepState(2, "running");
    await new Promise((r) => setTimeout(r, 420));
    const kbCount = kbStats ? kbStats.count : 57;
    setStepState(2, "done", `${kbCount} 个达人沟通场景已向量检索 · 召回 Top ${res.retrieval_detail.results.length}`);
    await new Promise((r) => setTimeout(r, 300));

    // Step3 完成：召回结果展示
    setStepState(3, "running");
    await new Promise((r) => setTimeout(r, 420));
    const top3 = res.retrieval_detail.results.slice(0, 3);
    const kbDetail = top3.map((x) => `${x.entry.id}（匹配度 ${x.score}%）`).join(" · ");
    setStepState(3, "done", "命中：" + kbDetail);
    await new Promise((r) => setTimeout(r, 300));

    // Step4 完成：风险校验
    setStepState(4, "running");
    await new Promise((r) => setTimeout(r, 420));
    const rk = res.risk_engine || {};
    const rkLevel = rk.risk_level || "low";
    const riskDetail = rk.risk_flag
      ? `Risk Level：${rkLevel.toUpperCase()} · ${(res.result.analysis.manual_confirmation || []).join("；") || "需人工确认"}`
      : `Risk Level：LOW · 未触发高风险规则`;
    setStepState(4, "done", riskDetail);
    await new Promise((r) => setTimeout(r, 300));

    // Step5 完成：生成回复
    setStepState(5, "running");
    await new Promise((r) => setTimeout(r, 420));
    setStepState(5, "done", `已生成 3 个版本：${(res.result.replies || []).map((x) => x.style).join(" / ")}`);
    await new Promise((r) => setTimeout(r, 250));

    renderAnalysis(res.result.analysis, res.risk_engine);
    renderReplies(res.result.replies);
    renderKB(res.retrieval_detail, res.risk_engine);
  } catch (e) {
    toast("生成失败：" + e.message);
    console.error(e);
  } finally {
    btn.disabled = false;
    btn.innerHTML = "✨ AI 分析并生成回复";
  }
}

/* ---------- 渲染：分析 ---------- */
function renderAnalysis(a, riskEngine) {
  const el = document.getElementById("analysis-area");
  el.style.display = "block";
  const level = a.risk_level || riskEngine?.risk_level || "low";
  const riskBanner =
    a.risk_flag || (riskEngine && riskEngine.risk_flag)
      ? `<div class="risk-banner ${level === "high" ? "high" : "medium"}">
          <b>${level === "high" ? "HIGH RISK" : "风险提示"}</b> · 涉及敏感事项，AI 不得越权承诺。
          ${(a.manual_confirmation || []).length ? "需人工确认：" + esc(a.manual_confirmation.join("；")) : ""}
        </div>`
      : `<div class="risk-banner low"><b>风险较低</b> · 未触发高风险规则，可正常推进。</div>`;

  el.innerHTML = `
    <div class="card" style="margin-bottom:0">
      <div class="card-title"><span class="dot"></span>达人分析 <span class="spacer"></span>
        <span class="tag ${level === "high" ? "tag-red" : level === "medium" ? "tag-orange" : "tag-green"}">流失风险：${esc(a.risk_level === "high" ? "高" : a.risk_level === "medium" ? "中" : "低")}</span>
      </div>
      <div class="analysis-grid">
        <div class="analysis-cell"><div class="label">主要意图</div><div class="value">${esc(a.intent || "—")}</div></div>
        <div class="analysis-cell"><div class="label">情绪</div><div class="value">${esc(a.emotion || "—")}</div></div>
        <div class="analysis-cell wide"><div class="label">当前阶段</div><div class="value">${esc(a.cooperation_stage || "—")}</div></div>
        <div class="analysis-cell"><div class="label">需要回答的问题</div><div class="value" style="font-weight:500;white-space:pre-line">${esc((a.questions_to_answer || []).map((q) => "• " + q).join("\n") || "—")}</div></div>
        <div class="analysis-cell"><div class="label">潜在顾虑</div><div class="value" style="font-weight:500;white-space:pre-line">${esc((a.hidden_concerns || []).map((q) => "• " + q).join("\n") || "—")}</div></div>
        <div class="analysis-cell wide"><div class="label">推荐下一步</div><div class="value">${esc(a.recommended_next_action || "—")}</div></div>
      </div>
      <div class="mt12">${riskBanner}</div>
    </div>`;
}

/* ---------- 渲染：回复 ---------- */
function renderReplies(replies) {
  const el = document.getElementById("replies-area");
  el.style.display = "block";
  const styles = {
    真诚友好: ["适合大多数达人", "purple"],
    简洁直接: ["高频BD、熟悉达人", "gray"],
    高情商推进: ["达人犹豫/拒绝/报价/催稿", "green"],
  };
  el.innerHTML = `<div class="card" style="margin-bottom:0">
    <div class="card-title"><span class="dot"></span>AI 生成回复（3 个版本）<span class="spacer"></span>
      <button class="btn btn-sm" onclick="copyAll()">复制全部</button>
    </div>
    ${replies
      .map(
        (r, i) => `
      <div class="reply-card" id="reply-card-${i}">
        <div class="reply-head">
          <span class="reply-style">${esc(r.style)}版</span>
          <span class="reply-tagline">${styles[r.style] ? styles[r.style][0] : ""}</span>
          <span class="spacer" style="flex:1"></span>
          <span class="tag tag-${styles[r.style] ? styles[r.style][1] : "gray"}">版本 ${i + 1}</span>
        </div>
        <div class="reply-body" id="reply-body-${i}">${esc(r.text)}</div>
        ${r.translation ? `<div class="reply-translation" id="reply-translation-${i}"><span class="zh-label">中文翻译</span>${esc(r.translation)}</div>` : ""}
        <div class="reply-actions">
          <button class="btn btn-sm" onclick="copyReply(${i})">复制</button>
          <button class="btn btn-sm btn-primary" onclick="adoptReply(${i})">采用</button>
          <span class="divider-v" style="width:1px;background:var(--border);margin:0 2px"></span>
          <button class="btn btn-sm" onclick="restyle(${i},'更亲切')">更亲切</button>
          <button class="btn btn-sm" onclick="restyle(${i},'更真诚')">更真诚</button>
          <button class="btn btn-sm" onclick="restyle(${i},'缩短')">缩短</button>
          <button class="btn btn-sm" onclick="restyle(${i},'扩写')">扩写</button>
          <button class="btn btn-sm" onclick="restyle(${i},'不要催太明显')">不要催太明显</button>
          <button class="btn btn-sm" onclick="restyle(${i},'重新生成')">重新生成</button>
        </div>
      </div>`
      )
      .join("")}
  </div>`;
  lastResult.replies = replies;
}

/* ---------- 复制 / 采用 ---------- */
function copyReply(i) {
  const text = document.getElementById("reply-body-" + i).innerText;
  copyText(text, "回复已复制");
}

function copyAll() {
  const all = lastResult.replies.map((r) => `【${r.style}版】\n${r.text}`).join("\n\n—————\n\n");
  copyText(all, "全部版本已复制");
}

async function adoptReply(i) {
  const replies = lastResult.replies;
  const chosen = replies[i];
  // 允许编辑：弹出简单确认（用 prompt 支持修改）
  const edited = prompt("发送前可修改（留空则原文采用）：", chosen.text);
  if (edited === null) return;
  const finalText = edited.trim() || chosen.text;
  const modified = finalText !== chosen.text;

  const record = {
    creator_id: currentCreator ? currentCreator.id : null,
    creator_name: currentCreator ? currentCreator.nickname : "",
    original_message: document.getElementById("msg-input").value.trim(),
    analysis: lastResult.analysis,
    retrieved_kb_ids: lastResult.retrieval ? lastResult.retrieval.used_kb_ids : [],
    generated_version: { style: chosen.style, text: chosen.text },
    operator_edited: modified ? finalText : "",
    final_sent: finalText,
    style_used: chosen.style,
  };
  await API.post("/api/replies", record);
  toast(`已保存「${chosen.style}版」回复` + (modified ? "（含人工修改）" : "（AI 直接采用）"));
}

/* ---------- 二次改写 ---------- */
async function restyle(i, style) {
  const body = document.getElementById("reply-body-" + i);
  const oldText = body.innerText;
  body.innerHTML = '<span class="spinner" style="border-color:rgba(91,91,214,.3);border-top-color:var(--primary)"></span> 改写中…';
  const res = await API.post("/api/regenerate", {
    message: document.getElementById("msg-input").value.trim(),
    platform: document.getElementById("cfg-platform").value,
    stage: document.getElementById("cfg-stage").value,
    goal: document.getElementById("cfg-goal").value,
    tone: document.getElementById("cfg-tone").value,
    length: document.getElementById("cfg-length").value,
    product: document.getElementById("cfg-product").value,
    creator_id: currentCreator ? currentCreator.id : null,
    style: style === "重新生成" ? "更真诚" : style,
    base_text: oldText,
    previous: lastResult,
  });
  const newText = res.result && res.result.text ? res.result.text : oldText;
  body.textContent = newText;
  const transEl = document.getElementById("reply-translation-" + i);
  const prevTrans = (lastResult.replies[i] && lastResult.replies[i].translation) || "";
  const newTrans = (res.result && res.result.translation) ? res.result.translation : prevTrans;
  if (transEl) {
    if (newTrans) {
      transEl.style.display = "block";
      transEl.innerHTML = '<span class="zh-label">中文翻译</span>' + esc(newTrans);
    } else {
      transEl.style.display = "none";
    }
  }
  lastResult.replies[i] = { ...lastResult.replies[i], text: newText, translation: newTrans };
  toast(`已${style === "重新生成" ? "重新生成" : "改写"}：${style}`);
}

/* ---------- 渲染：RAG 检索结果 ---------- */
function renderKB(detail, riskEngine) {
  const el = document.getElementById("kb-results");
  const why = document.getElementById("kb-why");
  document.getElementById("kb-count").textContent = `${detail.results.length} 条召回`;

  const levelCls = (l) => (l === "high" ? "tag-red" : l === "medium" ? "tag-orange" : "tag-green");
  el.innerHTML = detail.results
    .map(
      (r, i) => `
    <div class="kb-item" id="kb-item-${i}" onclick="toggleKb(${i})">
      <div class="flex-between">
        <span class="kb-match ${r.score > 60 ? "high" : ""}">匹配度 ${r.score}%</span>
        <span class="tag ${levelCls(r.entry.risk_level)}">${esc(r.entry.risk_level === "high" ? "High" : r.entry.risk_level === "medium" ? "Med" : "Low")}</span>
      </div>
      <div class="kb-scenario">${esc(r.entry.scenario)}</div>
      <div class="kb-meta">分类：${esc(r.entry.category)} · 阶段：${esc(r.entry.cooperation_stage)}</div>
      <div class="kb-meta">策略：${esc(r.entry.communication_goal)}</div>
      <div class="kb-source" id="kb-source-${i}" style="display:none">${esc(r.entry.source_text)}</div>
      <div class="kb-notes" id="kb-notes-${i}" style="display:none">
        <b>ID：</b>${esc(r.entry.id)} · <b>来源：</b>${esc(r.entry.source_file)}<br/>
        ${r.entry.notes ? `<b>使用限制：</b>${esc(r.entry.notes)}` : ""}
      </div>
    </div>`
    )
    .join("");

  why.style.display = "block";
  why.innerHTML = `<b>检索说明</b>：${esc(detail.why)}`;
  why.title = detail.query_text;
}

function toggleKb(i) {
  const item = document.getElementById("kb-item-" + i);
  const src = document.getElementById("kb-source-" + i);
  const notes = document.getElementById("kb-notes-" + i);
  const open = item.classList.toggle("open");
  src.style.display = open ? "block" : "none";
  notes.style.display = open ? "block" : "none";
}

/* 品牌规则更新后刷新产品下拉 */
window.refreshRulesUI = function (rules) {
  const sel = document.getElementById("cfg-product");
  if (!sel) return;
  const keep = sel.value;
  sel.innerHTML = '<option value="">（未指定）</option>';
  (rules.current_products || []).forEach((p) => {
    const name = typeof p === "string" ? p : p.name;
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    sel.appendChild(opt);
  });
  if (keep) sel.value = keep;
};
