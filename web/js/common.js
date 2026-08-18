/* 公共工具：API、Toast、品牌规则抽屉、达人编辑抽屉 */
const API = {
  get: (url) => fetch(url).then((r) => r.json()),
  post: (url, body) =>
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => r.json()),
  del: (url) => fetch(url, { method: "DELETE" }).then((r) => r.json()),
};

function toast(msg) {
  let el = document.querySelector(".toast");
  if (!el) {
    el = document.createElement("div");
    el.className = "toast";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove("show"), 2200);
}

async function copyText(text, msg = "已复制到剪贴板") {
  try {
    await navigator.clipboard.writeText(text);
    toast(msg);
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
    toast(msg);
  }
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

/* ---------------- 品牌规则抽屉 ---------------- */
let _rulesCache = null;
async function getRules(force = false) {
  if (!_rulesCache || force) _rulesCache = (await API.get("/api/brand-rules")).rules;
  return _rulesCache;
}

function openBrandDrawer() {
  API.get("/api/brand-rules").then((res) => {
    const r = res.rules;
    document.getElementById("br-brand").value = r.brand || "";
    document.getElementById("br-market").value = r.market || "";
    document.getElementById("br-platform").value = r.platform || "";
    document.getElementById("br-commission").value = r.current_commission || "";
    document.getElementById("br-fixed").checked = !!r.fixed_fee_allowed;
    document.getElementById("br-fixed-range").value = r.fixed_fee_range || "";
    document.getElementById("br-ad").value = r.ad_support || "";
    document.getElementById("br-sample").value = r.sample_policy || "";
    document.getElementById("br-ship").value = r.shipping_policy || "";
    document.getElementById("br-promo").value = r.promotion_info || "";
    document.getElementById("br-forbidden-promises").value = (r.forbidden_promises || []).join("\n");
    document.getElementById("br-forbidden-words").value = (r.forbidden_words || []).join("\n");
    document.getElementById("br-products").value = (r.current_products || [])
      .map((p) => (typeof p === "string" ? p : `${p.name}：${p.desc}`))
      .join("\n");
    document.getElementById("br-inventory").value = JSON.stringify(r.inventory_status || {}, null, 1);
    showDrawer("brandDrawer");
  });
}

function saveBrandRules() {
  const rules = {
    brand: document.getElementById("br-brand").value,
    market: document.getElementById("br-market").value,
    platform: document.getElementById("br-platform").value,
    current_commission: document.getElementById("br-commission").value,
    fixed_fee_allowed: document.getElementById("br-fixed").checked,
    fixed_fee_range: document.getElementById("br-fixed-range").value,
    ad_support: document.getElementById("br-ad").value,
    sample_policy: document.getElementById("br-sample").value,
    shipping_policy: document.getElementById("br-ship").value,
    promotion_info: document.getElementById("br-promo").value,
    forbidden_promises: document.getElementById("br-forbidden-promises").value.split("\n").filter(Boolean),
    forbidden_words: document.getElementById("br-forbidden-words").value.split("\n").filter(Boolean),
    current_products: document.getElementById("br-products").value.split("\n").filter(Boolean).map((line) => {
      const [name, ...rest] = line.split(/[：:]/);
      return rest.length ? { name: name.trim(), desc: rest.join("：").trim() } : { name: line.trim(), desc: "" };
    }),
    inventory_status: (() => {
      try { return JSON.parse(document.getElementById("br-inventory").value || "{}"); }
      catch { toast("库存状态 JSON 格式有误"); return null; }
    })(),
  };
  if (!rules.inventory_status) return;
  API.post("/api/brand-rules", rules).then((res) => {
    _rulesCache = res.rules;
    toast("品牌规则已保存");
    hideDrawer("brandDrawer");
    if (window.refreshRulesUI) window.refreshRulesUI(res.rules);
  });
}

/* ---------------- 抽屉通用 ---------------- */
function showDrawer(id) { document.getElementById(id).classList.add("show"); document.getElementById("mask").classList.add("show"); }
function hideDrawer(id) { document.getElementById(id).classList.remove("show"); document.getElementById("mask").classList.remove("show"); }

/* ---------------- 达人编辑抽屉 ---------------- */
function openCreatorDrawer(creator) {
  const c = creator || {};
  const fields = ["nickname", "account", "level", "vertical", "audience_profile", "history",
    "current_product", "cooperation_stage", "commission_pref", "quote_status",
    "special_requirements", "notes", "conversation_summary"];
  fields.forEach((f) => {
    const el = document.getElementById("cr-" + f);
    if (el) el.value = c[f] || "";
  });
  document.getElementById("cr-id").value = c.id || "";
  showDrawer("creatorDrawer");
}

async function saveCreator() {
  const payload = {};
  const fields = ["nickname", "account", "level", "vertical", "audience_profile", "history",
    "current_product", "cooperation_stage", "commission_pref", "quote_status",
    "special_requirements", "notes", "conversation_summary"];
  fields.forEach((f) => { payload[f] = document.getElementById("cr-" + f).value; });
  payload.id = document.getElementById("cr-id").value ? parseInt(document.getElementById("cr-id").value) : null;
  const res = await API.post("/api/creators", payload);
  hideDrawer("creatorDrawer");
  toast("达人信息已保存");
  if (window.refreshCreators) window.refreshCreators();
  if (window.loadCreatorList) window.loadCreatorList();
}

async function deleteCreator(id) {
  if (!confirm("确定删除该达人档案吗？")) return;
  await API.del("/api/creators/" + id);
  toast("已删除");
  if (window.loadCreatorList) window.loadCreatorList();
  if (window.refreshCreators) window.refreshCreators();
}

/* ---------------- 初始化 ---------------- */
async function initTopbar() {
  await refreshLLMBadge();
}

async function refreshLLMBadge() {
  const badge = document.getElementById("llm-badge");
  if (!badge) return;
  const h = await API.get("/api/health");
  if (h.ok && h.llm) {
    if (h.llm.configured) {
      badge.textContent = "AI Mode";
      badge.classList.remove("off");
      badge.title = `真实LLM：${h.llm.base_url} / ${h.llm.model}`;
    } else {
      badge.textContent = "Demo Mode";
      badge.classList.add("off");
      badge.title = "未配置 LLM Key（规则生成模式）。点击可配置 OpenAI 兼容接口";
    }
  }
}

/* ---------------- LLM 配置抽屉 ---------------- */
async function openLLMDrawer() {
  const res = await API.get("/api/llm-config");
  const c = res.config || {};
  document.getElementById("llm-base-url").value = c.base_url || "";
  // 出于安全：GET 不再返回明文 Key，已配置时仅提示，修改需重新填写
  const keyInput = document.getElementById("llm-api-key");
  keyInput.value = "";
  keyInput.placeholder = c.api_key_set ? "已配置（如需修改请重新填写）" : "请输入 API Key";
  document.getElementById("llm-model").value = c.model || "";
  const st = c.status || {};
  document.getElementById("llm-current-status").innerHTML = st.configured
    ? `<span class="tag tag-green">已配置 · AI Mode</span>`
    : `<span class="tag tag-gray">未配置 · Demo Mode</span>`;
  showDrawer("llmDrawer");
}

async function saveLLMConfig() {
  const payload = {
    base_url: document.getElementById("llm-base-url").value.trim(),
    api_key: document.getElementById("llm-api-key").value.trim(),
    model: document.getElementById("llm-model").value.trim(),
  };
  if (!payload.base_url || !payload.api_key) {
    toast("base_url 与 api_key 必填（想清除配置请点“清除配置”）");
    return;
  }
  const res = await API.post("/api/llm-config", payload);
  await refreshLLMBadge();
  toast("LLM 配置已保存，模式：" + (res.status?.mode === "llm" ? "AI Mode" : "Demo Mode"));
}

async function clearLLMConfig() {
  if (!confirm("清除 LLM 配置并回到 Demo Mode？")) return;
  await API.post("/api/llm-config", { base_url: "", api_key: "", model: "" });
  await refreshLLMBadge();
  toast("已清除配置，回到 Demo Mode");
}

async function testLLM() {
  const btn = document.getElementById("llm-test-btn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> 测试中…';
  const res = await API.post("/api/llm-test");
  btn.disabled = false;
  btn.innerHTML = "测试连接";
  const r = res.result || {};
  if (r.ok) {
    toast("连接成功：" + (r.model || "") + " → " + (r.reply || ""));
  } else {
    toast("连接失败：" + (r.error || "未知错误"));
  }
}

document.addEventListener("DOMContentLoaded", initTopbar);
