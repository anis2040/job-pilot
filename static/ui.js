let _toastTimer;
function showToast(msg, type = "ok") {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.className = `toast ${type} show`;
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove("show"), 2600);
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

async function addNewProfile() {
  const res = await fetch("/api/profiles/new", { method: "POST" });
  const data = await res.json();
  if (data.ok) window.location.href = "/setup";
}

async function apiPost(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

// ── SVG icons (Lucide, 1.5px stroke, currentColor) ─────────────────────────
const ICONS = {
  search:   '<path d="M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z"/><path d="m21 21-4.3-4.3"/>',
  settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2Z"/><circle cx="12" cy="12" r="3"/>',
  zap:      '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
  refresh:  '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
  check:    '<path d="M20 6 9 17l-5-5"/>',
  x:        '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  chevronDown: '<path d="m6 9 6 6 6-6"/>',
  chevronLeft: '<path d="m15 18-6-6 6-6"/>',
  external: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  mapPin:   '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
  globe:    '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
  building: '<rect width="16" height="20" x="4" y="2" rx="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01M16 6h.01M12 6h.01M12 10h.01M12 14h.01M16 10h.01M16 14h.01M8 10h.01M8 14h.01"/>',
  fileText: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8M16 13H8M16 17H8"/>',
  mail:     '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
  eye:      '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  eyeOff:   '<path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><path d="m2 2 20 20"/>',
  trash:    '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
  alert:    '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4M12 17h.01"/>',
};

function icon(name, size = 16) {
  const path = ICONS[name] || "";
  return `<svg class="icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${path}</svg>`;
}

// ── Focus trap ─────────────────────────────────────────────────────────────
const _FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

// Trap Tab focus inside `container`. Returns a cleanup function that restores
// focus to the element that was active before the trap engaged.
function trapFocus(container, { onEscape } = {}) {
  const previouslyFocused = document.activeElement;
  const focusables = () => [...container.querySelectorAll(_FOCUSABLE)].filter(el => el.offsetParent !== null);

  function keydown(e) {
    if (e.key === "Escape" && onEscape) { e.preventDefault(); onEscape(); return; }
    if (e.key !== "Tab") return;
    const items = focusables();
    if (!items.length) return;
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  container.addEventListener("keydown", keydown);
  const initial = focusables()[0];
  if (initial) initial.focus();

  return function release() {
    container.removeEventListener("keydown", keydown);
    if (previouslyFocused && typeof previouslyFocused.focus === "function") previouslyFocused.focus();
  };
}

// ── Custom confirm dialog (promise-based, replaces native confirm) ─────────
function confirmDialog({ title, message, confirmLabel = "Confirm", cancelLabel = "Cancel", danger = false } = {}) {
  return new Promise((resolve) => {
    const backdrop = document.createElement("div");
    backdrop.className = "confirm-backdrop";
    backdrop.setAttribute("role", "dialog");
    backdrop.setAttribute("aria-modal", "true");
    backdrop.setAttribute("aria-labelledby", "confirm-title");
    backdrop.innerHTML = `
      <div class="confirm-box">
        <div class="confirm-head">
          ${danger ? `<span class="confirm-icon danger">${icon("alert", 20)}</span>` : ""}
          <h2 id="confirm-title">${escapeHtml(title || "Are you sure?")}</h2>
        </div>
        ${message ? `<p class="confirm-msg">${escapeHtml(message)}</p>` : ""}
        <div class="confirm-actions">
          <button class="btn btn-ghost" data-act="cancel">${escapeHtml(cancelLabel)}</button>
          <button class="btn ${danger ? "btn-danger" : "btn-primary"}" data-act="ok">${escapeHtml(confirmLabel)}</button>
        </div>
      </div>`;
    document.body.appendChild(backdrop);

    let release;
    function close(result) {
      if (release) release();
      backdrop.remove();
      resolve(result);
    }
    backdrop.querySelector('[data-act="cancel"]').onclick = () => close(false);
    backdrop.querySelector('[data-act="ok"]').onclick = () => close(true);
    backdrop.onclick = (e) => { if (e.target === backdrop) close(false); };

    requestAnimationFrame(() => backdrop.classList.add("open"));
    release = trapFocus(backdrop, { onEscape: () => close(false) });
    // Prefer the confirm button focused initially for keyboard users
    backdrop.querySelector('[data-act="ok"]').focus();
  });
}

// ── Custom prompt dialog (promise-based, replaces native prompt) ───────────
// Resolves to the entered string, or null if cancelled.
function promptDialog({ title, message, value = "", placeholder = "", confirmLabel = "Save", cancelLabel = "Cancel" } = {}) {
  return new Promise((resolve) => {
    const backdrop = document.createElement("div");
    backdrop.className = "confirm-backdrop";
    backdrop.setAttribute("role", "dialog");
    backdrop.setAttribute("aria-modal", "true");
    backdrop.setAttribute("aria-labelledby", "prompt-title");
    backdrop.innerHTML = `
      <div class="confirm-box">
        <div class="confirm-head"><h2 id="prompt-title">${escapeHtml(title || "")}</h2></div>
        ${message ? `<p class="confirm-msg">${escapeHtml(message)}</p>` : ""}
        <input class="prompt-input" type="text" value="${escapeHtml(value)}" placeholder="${escapeHtml(placeholder)}">
        <div class="confirm-actions">
          <button class="btn btn-ghost" data-act="cancel">${escapeHtml(cancelLabel)}</button>
          <button class="btn btn-primary" data-act="ok">${escapeHtml(confirmLabel)}</button>
        </div>
      </div>`;
    document.body.appendChild(backdrop);

    const input = backdrop.querySelector(".prompt-input");
    let release;
    function close(result) {
      if (release) release();
      backdrop.remove();
      resolve(result);
    }
    backdrop.querySelector('[data-act="cancel"]').onclick = () => close(null);
    backdrop.querySelector('[data-act="ok"]').onclick = () => close(input.value.trim());
    backdrop.onclick = (e) => { if (e.target === backdrop) close(null); };
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); close(input.value.trim()); }
    });

    requestAnimationFrame(() => backdrop.classList.add("open"));
    release = trapFocus(backdrop, { onEscape: () => close(null) });
    input.focus();
    input.select();
  });
}

