"use strict";
const $ = (s, root = document) => root.querySelector(s);
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const arrowIcon =
  '<svg class="inline-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg>';
const names = {
  dashboard: "Overview",
  brand: "Brand Brain",
  planner: "Content Planner",
  studio: "Content Studio",
  campaigns: "Campaigns",
  analytics: "Analytics",
  ask: "Ask your CMO",
};
const channels = ["LinkedIn", "Email", "Instagram", "Blog", "Landing page"];
let state,
  page = "dashboard",
  selectedAsset = null,
  selectedPlan = null,
  dirty = false,
  busy = false,
  toastTimer,
  generatedInsights = null;
const money = (n) =>
  n == null
    ? "—"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 2,
      }).format(n);
const num = (n) => (n == null ? "—" : new Intl.NumberFormat("en-US").format(n));
const localMode = () => state.usage.mode === "local";
const sourceLabel = (source) =>
  source === "local"
    ? "Local templates"
    : source === "deepseek"
      ? "DeepSeek"
      : "OpenAI";
const badge = (label, color = "gray") =>
  `<span class="badge ${color}">${esc(label)}</span>`;
const assetStatus = (a) => (a.needs_review ? "Needs review" : a.status);
const sourceBadge = (source) =>
  badge(sourceLabel(source), source === "local" ? "gray" : "purple");
const fmtDate = (d) =>
  new Date(d + "T12:00:00").toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
const todayISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const monday = () => {
  const d = new Date();
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
function toast(message, error = false) {
  const t = $("#toast");
  t.textContent = message;
  t.className = "toast show" + (error ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(
    () => t.classList.remove("show"),
    error ? 10000 : 4500,
  );
}
async function api(path, data) {
  const response = await fetch(
    path,
    data === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        },
  );
  const result = await response.json();
  if (!response.ok)
    throw new Error(result.error || "Request failed. Please try again.");
  return result;
}
async function refresh() {
  state = await api("/api/state");
  $("#workspace-name").textContent = state.brand.name;
  $("#workspace-initial").textContent = state.brand.name.slice(0, 1);
  $("#engine-label").textContent = localMode()
    ? "Local drafting active"
    : `${sourceLabel(state.usage.mode)} · key configured`;
  $("#mode-pill").textContent = localMode()
    ? "Local mode"
    : sourceLabel(state.usage.mode);
}
function heading(kicker, title, subtitle, actions = "") {
  return `<div class="page-heading"><div><div class="eyebrow">${kicker}</div><h1>${title}</h1><p class="subtitle">${subtitle}</p></div><div class="actions">${actions}</div></div>`;
}
function button(label, action, classes = "", attrs = "") {
  return `<button class="btn ${classes}" data-action="${action}" ${attrs}>${label}</button>`;
}
function empty(title, desc, action = "") {
  return `<div class="empty"><div class="empty-icon">✳</div><h3>${title}</h3><p>${desc}</p>${action}</div>`;
}
function note() {
  return localMode()
    ? '<div class="notice">Local mode uses templates and rules from your saved brand context. Connect DeepSeek in server settings for AI-generated content. Nothing is auto-published.</div>'
    : "";
}
function kpis() {
  const t = state.analytics.totals;
  return `<div class="grid kpis">${[
    ["Qualified leads", num(t.leads), "↗", "From your imported metrics"],
    ["Marketing spend", money(t.spend), "$", "Last 30 days · USD"],
    [
      "Cost per lead",
      money(t.cpl),
      "◎",
      t.cpl === null ? "Import leads to calculate" : "Spend ÷ leads",
    ],
    [
      "Approved assets",
      state.assets.filter((a) => assetStatus(a) === "Approved").length,
      "✓",
      "Ready for manual publishing",
    ],
  ]
    .map(
      ([label, val, icon, hint]) =>
        `<div class="card kpi"><div class="kpi-top">${label}<span class="kpi-icon">${icon}</span></div><div class="kpi-value">${val}</div><small>${hint}</small></div>`,
    )
    .join("")}</div>`;
}
function insightList() {
  return state.analytics.observations
    .slice(0, 3)
    .map(
      (x, i) =>
        `<div class="insight"><span class="insight-icon">${i ? "↗" : "✳"}</span><div><h3>${i ? "What the numbers say" : "Your marketing signal"}</h3><p>${esc(x)}</p></div></div>`,
    )
    .join("");
}
function dashboard() {
  const b = state.brand;
  const pending = state.assets.filter(
    (a) => assetStatus(a) !== "Approved",
  ).length;
  return (
    heading(
      "A LITTLE CLARITY. A LOT OF MOMENTUM.",
      `Your marketing, <em>in good hands.</em>`,
      `Here’s the big picture for ${esc(b.name)}. Let’s make your next move count.`,
      button("✳ &nbsp; Plan my week", "go-planner", "primary"),
    ) +
    `<div class="hero-banner"><div><div class="eyebrow">YOUR AI CMO IS ON YOUR TEAM</div><h2>Small team.<br><em>Full marketing potential.</em></h2><p>One place to find your voice, plan the week, and turn ideas into work you’re proud to publish. You lead. Your CMO helps you move.</p><div class="actions">${button("Let’s build something &nbsp; ↗", "new-asset", "lime")}<a class="btn" href="#ask">Ask your CMO</a></div></div><div class="hero-decoration" aria-hidden="true"><span>✳</span></div></div>` +
    kpis() +
    `<div class="grid split"><section class="card panel"><div class="section-head"><div><h2>Your next best moves</h2><span class="muted">A little structure goes a long way.</span></div>${badge("Your workflow", "green")}</div><div class="flow-steps">${[
      [
        "01",
        "Set your foundation",
        "Keep your brand voice, audience and offer in one source of truth.",
        "Review brand",
        "brand",
      ],
      [
        "02",
        "Make a plan",
        state.plans.length
          ? `${state.plans.length} saved plan${state.plans.length === 1 ? "" : "s"}. Turn your next idea into a draft.`
          : "Start with a realistic, seven-day content plan.",
        "Open planner",
        "planner",
      ],
      [
        "03",
        "Give it your approval",
        pending
          ? `${pending} asset${pending === 1 ? "" : "s"} waiting for your review.`
          : "Review every word before it goes out into the world.",
        "Review assets",
        "studio",
      ],
    ]
      .map(
        ([n, title, desc, label, link]) =>
          `<div class="flow-step"><div class="flow-number">${n}</div><h3>${title}</h3><p>${esc(desc)}</p><a class="btn small" href="#${link}">${label} ↗</a></div>`,
      )
      .join(
        "",
      )}</div></section><section class="card panel"><div class="section-head"><div><h2>A little insight</h2><span class="muted">Real signals. Better decisions.</span></div><a href="#analytics" class="text-button">View all ↗</a></div>${insightList()}</section></div>
 <section class="card panel"><div class="section-head"><div><h2>On your desk</h2><span class="muted">Your latest marketing assets, all in one place.</span></div>${button("+ Create asset", "new-asset", "small")}</div>${
   state.assets.length
     ? `<div class="table-wrap"><table><thead><tr><th>ASSET</th><th>CHANNEL</th><th>STATUS</th><th>CREATED</th><th></th></tr></thead><tbody>${state.assets
         .slice(0, 5)
         .map(
           (a) =>
             `<tr><td class="table-title">${esc(a.title)}</td><td>${esc(a.channel)}</td><td>${badge(assetStatus(a), assetStatus(a) === "Approved" ? "green" : "orange")}</td><td>${fmtDate(a.created_at.slice(0, 10))}</td><td>${button("Open ↗", "open-asset", "small", `data-id="${a.id}"`)}</td></tr>`,
         )
         .join("")}</tbody></table></div>`
     : empty(
         "Room for your next great idea",
         "Create an asset or start with a weekly plan. Your saved drafts will appear here.",
       )
 }</section>`
  );
}
function field(key, label, value, opts = {}) {
  return `<div class="field ${opts.wide ? "span-2" : ""}"><label for="${key}">${label}</label>${opts.area ? `<textarea id="${key}" name="${key}" maxlength="${opts.max || 2000}" ${opts.optional ? "" : "required"}>${esc(value)}</textarea>` : `<input id="${key}" name="${key}" type="${opts.type || "text"}" value="${esc(value)}" ${opts.type === "number" ? 'min="0" step="0.01"' : ""} maxlength="${opts.max || 500}" ${opts.optional ? "" : "required"}>`}${opts.hint ? `<small>${opts.hint}</small>` : ""}</div>`;
}
function selectField(key, label, options, selected) {
  return `<div class="field"><label for="${key}">${label}</label><select id="${key}" name="${key}">${options.map((x) => `<option ${x === selected ? "selected" : ""}>${esc(x)}</option>`).join("")}</select></div>`;
}
function brand() {
  const b = state.brand;
  return (
    heading(
      "YOUR SOURCE OF TRUTH",
      "A brand that <em>sounds like you.</em>",
      "Give your CMO the context to keep every message consistent.",
    ) +
    `<div class="grid split"><form class="card panel" id="brand-form"><div class="form-section"><h2>The foundation</h2><p>What you do. Who you help. Why it matters.</p></div><div class="form-grid">${field("name", "Brand name", b.name, { max: 100 })}${field("product", "Product or service", b.product)}${field("audience", "Who are you speaking to?", b.audience, { wide: true })}${field("positioning", "Your positioning", b.positioning, { area: true, wide: true })}${field("voice", "How should your brand sound?", b.voice, { area: true, wide: true, max: 1000, hint: "Example: Practical, warm, concise. Explain the why. Avoid jargon." })}${field("cta", "Your primary call to action", b.cta, { max: 300 })}${field("website", "Website (optional)", b.website, { type: "url", optional: true })}${field("banned_words", "Words and phrases to avoid", b.banned_words, { wide: true, optional: true, max: 1000, hint: "Separate phrases with commas. These block asset approval." })}${field("monthly_budget", "Monthly marketing budget (USD)", b.monthly_budget, { type: "number" })}</div><div class="form-footer"><span class="muted">Brand updates require re-approval of existing assets.</span><button class="btn primary" type="submit">Save Brand Brain &nbsp; ✓</button></div></form><aside class="stack"><div class="aside-note"><h3>Consistency starts here.</h3><p>Your Brand Brain becomes context for every plan, draft, review and conversation.</p><ul><li>Be specific about your audience.</li><li>Describe what makes your product useful.</li><li>Use a voice your customers would recognize.</li></ul></div><div class="card panel"><h3>Your current direction</h3><p class="muted">${esc(b.positioning)}</p><div class="checklist"><strong>Primary CTA</strong><br>${esc(b.cta)}</div></div></aside></div>`
  );
}
function planner() {
  const plan = state.plans.find((p) => p.id === selectedPlan) || state.plans[0];
  return (
    heading(
      "A CLEAR PLAN. A CALMER WEEK.",
      "Make space for <em>good marketing.</em>",
      "Build a seven-day plan around one business goal, then turn ideas into assets.",
    ) +
    note() +
    `<form id="plan-form" class="card panel planner-controls">${field("goal", "This week’s business goal", "Generate qualified leads", { max: 500 })}${field("week_start", "Week starting", monday(), { type: "date" })}<button class="btn primary" type="submit">✳ Generate weekly plan</button></form>${
      plan
        ? `<div class="toolbar"><div><h2>Week of ${fmtDate(plan.week_start)}</h2><span class="muted">Goal: ${esc(plan.goal)}</span></div><div class="actions">${sourceBadge(plan.source)}<select class="btn" id="plan-picker" aria-label="Saved plan">${state.plans.map((p) => `<option value="${p.id}" ${p.id === plan.id ? "selected" : ""}>${fmtDate(p.week_start)} · ${esc(p.goal.slice(0, 35))}</option>`).join("")}</select></div></div><div class="calendar">${plan.items
            .map((i, index) => {
              const existing = state.assets.find(
                (a) => a.plan_id === plan.id && a.plan_index === index,
              );
              return `<article class="day-card"><div class="day-date"><strong>${new Date(i.date + "T12:00:00").toLocaleDateString(undefined, { weekday: "long" })}</strong><span>${fmtDate(i.date)}</span></div><div>${badge(i.channel, i.channel === "Email" ? "purple" : "green")}</div><h3>${esc(i.title)}</h3><p>${esc(i.brief)}</p>${existing ? button("Open draft ↗", "open-asset", "small", `data-id="${existing.id}"`) : button("✳ Draft this idea", "draft-plan", "small", `data-plan="${plan.id}" data-index="${index}"`)}</article>`;
            })
            .join("")}</div>`
        : `<div class="card">${empty("A little planning. A lot less scrambling.", "Choose a goal and a starting date. Your CMO will suggest one realistic idea for each day.")}</div>`
    }`
  );
}
function studio() {
  const a = state.assets.find((x) => x.id === selectedAsset) || state.assets[0];
  if (a) selectedAsset = a.id;
  return (
    heading(
      "FROM FIRST DRAFT TO READY TO GO.",
      "Good ideas, <em>beautifully put.</em>",
      "Draft with your brand context. Edit it your way. Approve when it feels right.",
      button("+ New asset", "new-asset", "primary"),
    ) +
    note() +
    `<div class="toolbar"><span class="muted">${state.assets.length} saved asset${state.assets.length === 1 ? "" : "s"} · Editing approved copy resets it to Draft.</span><a class="btn small" href="/api/export/assets" download>↓ Export approved CSV</a></div>${a ? `<div class="studio"><aside class="card asset-list" aria-label="Saved assets">${state.assets.map((x) => `<button class="asset-option ${x.id === a.id ? "active" : ""}" data-action="select-asset" data-id="${x.id}"><strong>${esc(x.title)}</strong><div class="meta"><span>${esc(x.channel)}</span>${badge(assetStatus(x), assetStatus(x) === "Approved" ? "green" : "orange")}</div></button>`).join("")}</aside><section class="card panel"><div class="section-head"><div class="actions">${badge(a.channel, "green")}${sourceBadge(a.source)}</div>${badge(assetStatus(a), assetStatus(a) === "Approved" ? "green" : "orange")}</div><label class="muted" for="editor-title">Asset title</label><input id="editor-title" class="editor-title" maxlength="200" value="${esc(a.title)}"><label class="muted" for="editor-body">Content</label><textarea id="editor-body" class="editor-body" maxlength="16000">${esc(a.body)}</textarea><div class="editor-footer"><div><span id="dirty-label" class="dirty-label">All changes saved</span><div class="muted">Revision ${a.revision}</div></div><div class="actions">${button("Save draft", "save-asset")}${button("✳ Variation", "variation")}${button("Approve asset ✓", "approve-asset", "primary", assetStatus(a) === "Approved" ? "disabled" : "")}</div></div><div class="checklist ${a.brand_check.issues.length || a.needs_review ? "warning" : ""}"><strong>Brand check · ${a.brand_check.score}/100</strong>${a.needs_review ? "<div>Your Brand Brain changed. Review and approve this asset again.</div>" : ""}${a.brand_check.issues.length ? `<ul>${a.brand_check.issues.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "<div>Name, CTA, restricted phrases and content length checked.</div>"}<div>${esc(a.brand_check.note)}</div></div></section></div>` : `<div class="card">${empty("Your content starts with one idea.", "Generate an email, social post, blog draft or landing page. Each asset is saved for review.", button("Create your first asset", "new-asset", "primary"))}</div>`}`
  );
}
function campaigns() {
  return (
    heading(
      "A LITTLE STRATEGY BEFORE YOU HIT GO.",
      "Launch with <em>more confidence.</em>",
      "Define the offer, check the essentials, and get recommendations before committing budget.",
      button("+ New campaign", "new-campaign", "primary"),
    ) +
    note() +
    (state.campaigns.length
      ? state.campaigns
          .map(
            (c) =>
              `<article class="card campaign-card"><div class="section-head"><div><h2>${esc(c.name)}</h2><span class="muted">${esc(c.goal)}</span></div>${badge(c.status, c.review ? "green" : "gray")}</div><div class="campaign-info"><span>◈ ${esc(c.channel)}</span><span>Budget ${money(c.budget)}</span><span>Due ${fmtDate(c.deadline)}</span><span>Audience: ${esc(c.audience)}</span></div><p class="campaign-offer">${esc(c.offer)}</p><div class="toolbar"><span class="muted">CTA: ${esc(c.cta)}</span>${button(c.review ? "Review again ↗" : "✳ Review campaign", "review-campaign", "small", `data-id="${c.id}"`)}</div>${c.review ? `<div class="review-box"><div class="section-head"><div><h3>Readiness check</h3><span class="muted">Five transparent rules, 20 points each. Not a performance prediction.</span></div><span class="review-score">${c.review.score}<small>/100</small></span></div><div class="checks">${c.review.checks.map((x) => `<span title="${esc(x.detail)}">${badge((x.passed ? "✓ " : "! ") + x.name, x.passed ? "green" : "orange")}</span>`).join("")}</div><p>${esc(c.review.summary)}</p><ul class="recommendations">${c.review.recommendations.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>${sourceBadge(c.review.source)}</div>` : ""}</article>`,
          )
          .join("")
      : `<div class="card">${empty("Give your next campaign a clear direction.", "Set an audience, offer, budget and deadline. Then get a review before you launch.", button("Create a campaign", "new-campaign", "primary"))}</div>`)
  );
}
function chart() {
  const series = state.analytics.series,
    max = Math.max(...series.map((x) => x.leads), 1);
  return `<div class="chart" aria-label="Leads over the last 30 days in five-day buckets">${series.map((x) => `<div class="chart-col"><span class="chart-value">${num(x.leads)}</span><div class="chart-track"><div class="chart-bar" data-height="${Math.max(1, (x.leads / max) * 100)}"></div></div><span class="chart-label">${fmtDate(x.date)}</span></div>`).join("")}</div>`;
}
function analytics() {
  const a = state.analytics,
    t = a.totals;
  return (
    heading(
      "LESS GUESSWORK. BETTER NEXT STEPS.",
      "Find the signal. <em>Make your move.</em>",
      `Your imported results · ${fmtDate(a.period.start)} – ${fmtDate(a.period.end)} · USD`,
      button("↑ Import metrics", "import-metrics", "primary"),
    ) +
    kpis() +
    `<div class="grid split"><section class="card panel"><div class="section-head"><div><h2>Leads over time</h2><span class="muted">Five-day totals · imported data only</span></div>${badge(a.row_count ? "Your data" : "No data", a.row_count ? "green" : "gray")}</div>${chart()}</section><section class="card panel"><div class="section-head"><div><h2>What to do next</h2><span class="muted">Observations, not attribution</span></div>${button("✳ Analyze", "analyze", "small")}</div>${generatedInsights ? `<p class="muted">${esc(generatedInsights.summary)}</p><ul class="recommendations">${generatedInsights.recommendations.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>${sourceBadge(generatedInsights.source)}` : insightList() + `<ul class="recommendations">${a.recommendations.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`}</section></div><section class="card panel"><div class="section-head"><div><h2>Channel performance</h2><span class="muted">CTR = clicks ÷ impressions · CPL = spend ÷ leads · ROAS = revenue ÷ spend</span></div><a href="/api/export/metrics" class="btn small" download>↓ Export CSV</a></div>${a.channels.length ? `<div class="table-wrap"><table><thead><tr><th>CHANNEL</th><th>SPEND</th><th>IMPRESSIONS</th><th>CLICKS</th><th>LEADS</th><th>CTR</th><th>CPL</th><th>ROAS</th></tr></thead><tbody>${a.channels.map((c) => `<tr><td><strong>${esc(c.channel)}</strong></td><td>${money(c.spend)}</td><td>${num(c.impressions)}</td><td>${num(c.clicks)}</td><td>${num(c.leads)}</td><td>${c.ctr === null ? "—" : num(c.ctr) + "%"}</td><td>${money(c.cpl)}</td><td>${c.roas === null ? "—" : num(c.roas) + "×"}</td></tr>`).join("")}</tbody></table></div>` : empty("Your numbers tell a story.", "Import a CSV from your own reports. No analytics integrations or invented performance data.", button("Import a CSV", "import-metrics"))}</section><section class="card panel mt"><div class="section-head"><div><h2>Imported records</h2><span class="muted">${state.metrics.length} rows total · re-importing the same date, channel and campaign updates that record.</span></div></div><div class="metric-table"><div class="table-wrap"><table><thead><tr><th>DATE</th><th>CAMPAIGN</th><th>CHANNEL</th><th>SPEND</th><th>LEADS</th><th>REVENUE</th></tr></thead><tbody>${state.metrics
      .slice(0, 100)
      .map(
        (r) =>
          `<tr><td>${esc(r.date)}</td><td>${esc(r.campaign)}</td><td>${esc(r.channel)}</td><td>${money(r.spend)}</td><td>${num(r.leads)}</td><td>${money(r.revenue)}</td></tr>`,
      )
      .join("")}</tbody></table></div></div></section>`
  );
}
function ask() {
  const u = state.usage;
  return (
    heading(
      "SOMEONE TO THINK IT THROUGH WITH.",
      "Meet your <em>marketing co-pilot.</em>",
      "Grounded in your brand, saved plans, campaigns and imported performance.",
    ) +
    `<div class="chat-layout"><section class="card chat-panel"><div class="messages" id="messages">${state.messages.length ? state.messages.map((m) => `<div class="message user">${esc(m.question)}</div><div class="message assistant">${esc(m.answer)}<small>${sourceLabel(m.source)} · ${new Date(m.created_at).toLocaleString()}</small></div>`).join("") : `<div class="chat-welcome"><div class="spark">✳</div><h2>What’s on your mind?</h2><p>Bring a question, an idea, or a marketing decision. Let’s work out a useful next step.</p>${localMode() ? "<p>Local mode offers rule-based guidance. Connect DeepSeek for open-ended AI advice.</p>" : ""}</div>`}</div><form id="chat-form" class="chat-input"><input id="question" name="question" placeholder="What should we focus on this week?" maxlength="2000" aria-label="Message your CMO" required autocomplete="off"><button class="btn primary" type="submit">Send ↗</button></form></section><aside class="stack"><div class="card panel"><h3>A place to start</h3>${["What should we post this week?", "What does our performance data tell us?", "Which channel should we focus on?", "How can we improve our positioning?"].map((q) => `<button class="prompt" data-action="prompt" data-question="${esc(q)}">${q} ↗</button>`).join("")}</div><div class="aside-note"><h3>The context behind the advice</h3><div>✓ Your saved Brand Brain</div><div>✓ ${state.plans.length} saved content plans</div><div>✓ ${state.campaigns.length} campaigns</div><div>✓ ${state.metrics.length} imported metric rows</div></div><div class="card panel"><h3>A thoughtful use of AI</h3><span class="muted">${u.today} / ${u.limit} daily generation attempts</span><div class="usage-meter"><div class="usage-fill" data-width="${Math.min(100, (u.today / u.limit) * 100)}"></div></div><small class="muted">${u.tokens} provider tokens today. The request cap limits use; it is not a dollar budget.</small></div></aside></div>`
  );
}
function render() {
  if (!state) return;
  page = names[location.hash.slice(1)] ? location.hash.slice(1) : "dashboard";
  $("#page-label").textContent = names[page];
  document
    .querySelectorAll("nav a")
    .forEach((a) => a.classList.toggle("active", a.dataset.page === page));
  $("#main").innerHTML = {
    dashboard,
    brand,
    planner,
    studio,
    campaigns,
    analytics,
    ask,
  }
    [page]()
    .replaceAll("↗", arrowIcon);
  dirty = false;
  if (page === "ask") {
    $("#messages").scrollTop = $("#messages").scrollHeight;
  }
  drawBars();
}
// CSP keeps styles in the stylesheet; set chart dimensions through DOM style APIs.
function drawBars() {
  document
    .querySelectorAll("[data-height]")
    .forEach((e) => (e.style.height = e.dataset.height + "%"));
  document
    .querySelectorAll("[data-width]")
    .forEach((e) => (e.style.width = e.dataset.width + "%"));
}
function showModal(html) {
  $("#modal-content").innerHTML = html.replaceAll("↗", arrowIcon);
  $("#modal").showModal();
}
function closeModal() {
  $("#modal").close();
}
function newAsset() {
  showModal(
    `<h1>Create something useful.</h1><p class="dialog-subtitle">Start with a clear brief. Your saved brand context comes with it.</p><form id="asset-form"><div class="form-grid">${field("title", "Asset title (optional)", "", { optional: true, max: 200 })}${selectField("channel", "Channel", channels, "LinkedIn")}${field("brief", "What should this asset say?", "", { area: true, wide: true, max: 3000, hint: "Describe the message, offer, and purpose. Include only claims you can support." })}</div><div class="form-footer"><span class="muted">${sourceLabel(state.usage.mode)} · starts as Draft</span><button class="btn primary" type="submit">✳ Generate asset</button></div></form>`,
  );
}
function newCampaign() {
  const b = state.brand;
  showModal(
    `<h1>Give your campaign a direction.</h1><p class="dialog-subtitle">A clear audience, a useful offer, and one next step.</p><form id="campaign-form"><div class="form-grid">${field("name", "Campaign name", "", { max: 150 })}${selectField("channel", "Channel", channels, "LinkedIn")}${field("goal", "Business goal", "Generate qualified leads", { wide: true, max: 1000 })}${field("audience", "Audience", b.audience, { wide: true })}${field("offer", "Product or offer", b.product, { area: true, wide: true })}${field("cta", "Call to action", b.cta, { wide: true, max: 300 })}${field("budget", "Campaign budget (USD)", Math.min(100, b.monthly_budget), { type: "number" })}${field("deadline", "Deadline", todayISO(), { type: "date" })}</div><div class="form-footer"><span class="muted">Saved first. Review when you’re ready.</span><button class="btn primary" type="submit">Create campaign ↗</button></div></form>`,
  );
}
function importMetrics() {
  showModal(
    `<h1>Bring your numbers together.</h1><p class="dialog-subtitle">Upload up to 1,000 rows. All dates use YYYY-MM-DD and all money is USD.</p><div class="notice">Re-imports update records matching date + channel + campaign. The whole file is validated before anything is saved.</div><form id="import-form"><label class="field" for="csv-file"><strong>Choose a CSV file</strong><input class="file-input" type="file" id="csv-file" name="csv-file" accept=".csv,text/csv" required></label><p class="muted">Required column order:</p><div class="code">date,channel,campaign,spend,impressions,clicks,leads,revenue</div><p class="muted">Channels: LinkedIn, Email, Instagram, Blog, Landing page. Use nonnegative numbers. Leads ≤ clicks ≤ impressions.</p><div class="form-footer">${button("↓ Download sample CSV", "sample-csv")}<button class="btn primary" type="submit">Import metrics ↑</button></div></form>`,
  );
}
function settings() {
  const u = state.usage;
  showModal(
    `<h1>Your workspace, your way.</h1><p class="dialog-subtitle">One local workspace. Your data stays in your SQLite database.</p><div class="aside-note"><h3>Generation: ${sourceLabel(u.mode)}</h3><p>${esc(u.model)}</p><p>${u.today} of ${u.limit} daily attempts used · ${u.tokens} tokens reported today.</p></div><h3 class="mt">Connect DeepSeek</h3><p class="muted">Set these variables securely on the server, then restart it. Never put a key in the browser or commit it to Git.</p><div class="code">CMO_LLM_PROVIDER=deepseek<br>CMO_LLM_MODEL=deepseek-chat<br>DEEPSEEK_API_KEY=[use your existing server environment variable]<br>CMO_DAILY_GENERATION_LIMIT=30</div><p class="muted">Live generation sends brand context, recent chat, campaign details and aggregate metrics to the selected provider. A configured key does not prove provider access until a request succeeds. Local mode makes no AI API calls.</p><div class="danger-zone"><h3>Your data</h3><p class="muted">Download a JSON export for inspection. For a restorable backup, stop the server and copy the SQLite database. This version has no JSON restore tool.</p><a class="btn" href="/api/export/workspace" download>↓ Download workspace JSON</a></div>`,
  );
}
function download(text, name, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function perform(action, btn) {
  if (busy) return;
  busy = true;
  const buttons = [...document.querySelectorAll("button")];
  const disabled = buttons.map((b) => b.disabled);
  buttons.forEach((b) => (b.disabled = true));
  try {
    await action();
  } catch (e) {
    toast(e.message, true);
  } finally {
    busy = false;
    buttons.forEach((b, i) => {
      if (b.isConnected) b.disabled = disabled[i];
    });
  }
}
function confirmDiscard() {
  return (
    !dirty || window.confirm("You have unsaved asset edits. Discard them?")
  );
}
async function saveAsset() {
  const a = state.assets.find((x) => x.id === selectedAsset);
  await api(`/api/assets/${a.id}/save`, {
    title: $("#editor-title").value,
    body: $("#editor-body").value,
    revision: a.revision,
  });
  dirty = false;
  await refresh();
  render();
}
document.addEventListener("input", (e) => {
  if (["editor-title", "editor-body"].includes(e.target.id)) {
    dirty = true;
    $("#dirty-label").textContent = "Unsaved changes";
  }
});
document.addEventListener("change", (e) => {
  if (e.target.id === "plan-picker") {
    selectedPlan = Number(e.target.value);
    render();
  }
});
document.addEventListener("click", (e) => {
  const nav = e.target.closest('a[href^="#"]');
  if (nav && (!confirmDiscard() || busy)) {
    e.preventDefault();
    return;
  }
  const b = e.target.closest("[data-action]");
  if (!b) return;
  const action = b.dataset.action;
  if (action === "close-modal") {
    closeModal();
    return;
  }
  if (action === "settings") {
    settings();
    return;
  }
  if (action === "new-asset") {
    newAsset();
    return;
  }
  if (action === "new-campaign") {
    newCampaign();
    return;
  }
  if (action === "import-metrics") {
    importMetrics();
    return;
  }
  if (action === "go-planner") {
    location.hash = "planner";
    return;
  }
  if (action === "sample-csv") {
    download(
      `date,channel,campaign,spend,impressions,clicks,leads,revenue\n${todayISO()},LinkedIn,Example campaign,50,2000,80,8,200\n`,
      "cmo-metrics-example.csv",
      "text/csv",
    );
    return;
  }
  if (action === "select-asset" || action === "open-asset") {
    if (!confirmDiscard()) return;
    selectedAsset = Number(b.dataset.id);
    dirty = false;
    if (page !== "studio") location.hash = "studio";
    else render();
    return;
  }
  if (action === "prompt") {
    $("#question").value = b.dataset.question;
    $("#chat-form").requestSubmit();
    return;
  }
  perform(async () => {
    if (action === "draft-plan") {
      const p = state.plans.find((x) => x.id === Number(b.dataset.plan)),
        index = Number(b.dataset.index),
        i = p.items[index];
      toast("Drafting with your brand context…");
      const result = await api("/api/assets", {
        ...i,
        plan_id: p.id,
        plan_index: index,
      });
      selectedAsset = result.id;
      await refresh();
      location.hash = "studio";
      toast("Draft saved. Make it yours before approving.");
    } else if (action === "save-asset") {
      await saveAsset();
      toast("Draft saved.");
    } else if (action === "approve-asset") {
      if (dirty) await saveAsset();
      const a = state.assets.find((x) => x.id === selectedAsset);
      await api(`/api/assets/${a.id}/approve`, { revision: a.revision });
      await refresh();
      render();
      toast("Approved. Ready for manual export and publishing.");
    } else if (action === "variation") {
      if (dirty) await saveAsset();
      const instruction = window.prompt(
        localMode()
          ? "Local mode creates an alternate template layout. What direction would you like to give it? (For detailed rewrites, connect DeepSeek.)"
          : "How should your CMO improve this draft?",
        "Make it more concise and emphasize the audience benefit.",
      );
      if (!instruction) return;
      const a = state.assets.find((x) => x.id === selectedAsset);
      toast("Creating a new variation…");
      await api(`/api/assets/${a.id}/variation`, {
        revision: a.revision,
        instruction,
      });
      await refresh();
      render();
      toast("Variation saved as Draft.");
    } else if (action === "review-campaign") {
      toast("Reviewing the campaign…");
      await api(`/api/campaigns/${b.dataset.id}/review`, {});
      await refresh();
      render();
      toast("Campaign review saved.");
    } else if (action === "analyze") {
      toast("Analyzing your imported metrics…");
      generatedInsights = await api("/api/insights", {});
      await refresh();
      render();
      toast("Analysis complete.");
    }
  });
});
document.addEventListener("submit", (e) => {
  const form = e.target;
  if (
    ![
      "brand-form",
      "plan-form",
      "asset-form",
      "campaign-form",
      "import-form",
      "chat-form",
    ].includes(form.id)
  )
    return;
  e.preventDefault();
  perform(async () => {
    let data = Object.fromEntries(new FormData(form));
    if (form.id === "brand-form") {
      data.monthly_budget = Number(data.monthly_budget);
      await api("/api/brand", data);
      await refresh();
      render();
      toast("Brand Brain saved. Earlier approvals now need review.");
    } else if (form.id === "plan-form") {
      toast("Building your weekly plan…");
      const plan = await api("/api/plans", data);
      selectedPlan = plan.id;
      await refresh();
      render();
      toast("Your seven-day plan is saved.");
    } else if (form.id === "asset-form") {
      toast("Drafting with your brand context…");
      const a = await api("/api/assets", data);
      selectedAsset = a.id;
      await refresh();
      closeModal();
      if (page === "studio") render();
      else location.hash = "studio";
      toast("New draft saved.");
    } else if (form.id === "campaign-form") {
      data.budget = Number(data.budget);
      await api("/api/campaigns", data);
      await refresh();
      closeModal();
      if (page === "campaigns") render();
      else location.hash = "campaigns";
      toast("Campaign saved. Run a review before launching.");
    } else if (form.id === "import-form") {
      const file = $("#csv-file").files[0];
      if (!file) throw new Error("Choose a CSV file.");
      if (file.size > 200000) throw new Error("CSV must be under 200 KB.");
      const result = await api("/api/metrics/import", {
        csv: await file.text(),
      });
      generatedInsights = null;
      await refresh();
      closeModal();
      render();
      toast(`${result.added} rows added, ${result.updated} updated.`);
    } else if (form.id === "chat-form") {
      toast("Your CMO is thinking…");
      await api("/api/chat", data);
      await refresh();
      render();
      $("#question").focus();
      toast("Reply saved.");
    }
  });
});
window.addEventListener("hashchange", () => {
  render();
  window.scrollTo(0, 0);
});
window.addEventListener("beforeunload", (e) => {
  if (dirty) {
    e.preventDefault();
    e.returnValue = "";
  }
});
$("#today").textContent = new Date().toLocaleDateString(undefined, {
  weekday: "short",
  month: "short",
  day: "numeric",
  year: "numeric",
});
(async () => {
  try {
    await refresh();
    render();
  } catch (e) {
    $("#main").innerHTML = empty(
      "We couldn’t open your workspace.",
      "Start the app with python3 server.py, then reload this page.",
    );
    toast(e.message, true);
  }
})();
