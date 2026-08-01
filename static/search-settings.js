// Shared search settings JS — used by index.html (modal) and profile_settings.html

const SOURCES = ["linkedin", "jobicy", "himalayas", "greenhouse"];

// ── Search rows ───────────────────────────────────────────────────────────────

function renderSearchRows(searches, containerId = "searches-list") {
  const groups = {};
  for (const s of searches) {
    const key = `${s.query}||${s.location || ""}||${s.remote ?? true}`;
    if (!groups[key]) groups[key] = { query: s.query, location: s.location || "United States", remote: s.remote !== false, sources: [] };
    groups[key].sources.push(s.source);
  }
  const list = document.getElementById(containerId);
  if (!list) return;
  list.innerHTML = "";
  for (const g of Object.values(groups)) addSearchRow(g, containerId);
}

function toggleSourceAll(row) {
  const cbs = row.querySelectorAll(".src-cb");
  const allChecked = [...cbs].every(c => c.checked);
  cbs.forEach(c => {
    c.checked = !allChecked;
    c.closest(".source-cb").classList.toggle("checked", !allChecked);
  });
}

function addSearchRow(s = {}, containerId = "searches-list") {
  const list = document.getElementById(containerId) || document.getElementById("search-rows");
  if (!list) return;
  const row = document.createElement("div");
  row.className = "search-row";
  const activeSources = Array.isArray(s.sources) ? s.sources : (s.source ? [s.source] : SOURCES);
  const sourceCbs = SOURCES.map(src => {
    const checked = activeSources.includes(src);
    return `<label class="source-cb ${checked ? "checked" : ""}" onclick="this.classList.toggle('checked',this.querySelector('input').checked)">
      <input type="checkbox" class="src-cb" value="${src}" ${checked ? "checked" : ""}> ${src}
    </label>`;
  }).join("");
  row.innerHTML = `
    <div class="search-row-fields">
      <input type="text" placeholder="e.g. Product Manager" value="${s.query || ""}" data-field="query">
      <input type="text" placeholder="United States" value="${s.location || "United States"}" data-field="location">
      <label class="toggle-remote"><input type="checkbox" data-field="remote" ${s.remote !== false ? "checked" : ""}> Remote</label>
      <button class="btn-icon" title="Remove" onclick="this.closest('.search-row').remove()">✕</button>
    </div>
    <div class="search-sources">
      <span style="font-size:0.7rem;color:#475569;font-weight:600;text-transform:uppercase;margin-right:4px">Sources:</span>
      ${sourceCbs}
      <button class="source-all-btn" type="button" onclick="toggleSourceAll(this.closest('.search-row'))">all/none</button>
    </div>`;
  list.appendChild(row);
}

function collectSearchRows(selector = ".search-row") {
  const results = [];
  document.querySelectorAll(selector).forEach(row => {
    const q = row.querySelector("[data-field=query]").value.trim();
    const loc = row.querySelector("[data-field=location]").value.trim();
    const remote = row.querySelector("[data-field=remote]").checked;
    const sources = [...row.querySelectorAll(".src-cb:checked")].map(c => c.value);
    if (!q || !sources.length) return;
    for (const src of sources) {
      results.push({ name: `${src} - ${q}`, source: src, query: q, location: loc, max_pages: 3, remote });
    }
  });
  return results;
}

// ── Tag inputs ────────────────────────────────────────────────────────────────

function renderTags(wrapId, inputId, tags) {
  const wrap = document.getElementById(wrapId);
  const input = document.getElementById(inputId);
  if (!wrap || !input) return;
  wrap.querySelectorAll(".tag").forEach(t => t.remove());
  tags.forEach(tag => wrap.insertBefore(makeTag(tag, wrapId, inputId), input));
}

function makeTag(value, wrapId, inputId) {
  const span = document.createElement("span");
  span.className = "tag";
  span.innerHTML = `${value} <button onclick="removeTag(this,'${wrapId}','${inputId}')" type="button">✕</button>`;
  span.dataset.value = value;
  return span;
}

function removeTag(btn) {
  btn.closest(".tag").remove();
}

function focusTagInput(inputId) {
  document.getElementById(inputId)?.focus();
}

function tagKeydown(e, wrapId, inputId) {
  if (e.key !== "Enter" && e.key !== ",") return;
  e.preventDefault();
  const input = document.getElementById(inputId);
  const val = input.value.trim().toLowerCase().replace(/,$/, "");
  if (!val) return;
  const wrap = document.getElementById(wrapId);
  if (!wrap.querySelector(`.tag[data-value="${val}"]`)) {
    wrap.insertBefore(makeTag(val, wrapId, inputId), input);
  }
  input.value = "";
}

function collectTags(wrapId) {
  return [...document.querySelectorAll(`#${wrapId} .tag`)].map(t => t.dataset.value);
}
