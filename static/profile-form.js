// Shared profile form JS — used by setup.html and profile_settings.html

// ── Dynamic form builders ─────────────────────────────────────────────────────

function addRow(listId, cls, placeholder, value = "") {
  const list = document.getElementById(listId);
  const row = document.createElement("div");
  row.className = "dynamic-row " + cls;
  row.innerHTML = `<input type="text" placeholder="${placeholder}" value="${value.replace(/"/g,'&quot;')}">
    <button class="btn-icon" onclick="this.closest('.dynamic-row').remove()" title="Remove">✕</button>`;
  list.appendChild(row);
  if (!value) row.querySelector("input").focus();
}

function addExpBlock() {
  const list = document.getElementById("exp-list");
  const idx = list.children.length + 1;
  const block = document.createElement("div");
  block.className = "exp-block";
  block.innerHTML = `
    <div class="exp-block-header">
      <span>Role ${idx}</span>
      <button class="btn-icon" onclick="this.closest('.exp-block').remove()">✕</button>
    </div>
    <div class="field-row cols-2">
      <div class="field"><label>Job Title *</label><input class="exp-title" placeholder="Product Owner"></div>
      <div class="field"><label>Company *</label><input class="exp-company" placeholder="Acme Corp"></div>
    </div>
    <div class="field-row cols-3">
      <div class="field"><label>Location</label><input class="exp-location" placeholder="Tunis, Tunisia"></div>
      <div class="field"><label>Start Date</label><input class="exp-start" placeholder="Oct 2020"></div>
      <div class="field"><label>End Date</label><input class="exp-end" placeholder="Present"></div>
    </div>
    <div class="sublabel">Key bullets (what you did and the outcome)</div>
    <div class="dynamic-list exp-bullets"></div>
    <button class="btn-add-row" onclick="addBullet(this)" style="margin-bottom:10px">+ Add bullet</button>
    <div class="sublabel">Key Projects (optional)</div>
    <div class="dynamic-list exp-projects"></div>
    <button class="btn-add-row" onclick="addProject(this)">+ Add project</button>`;
  list.appendChild(block);
  addBullet(block.querySelectorAll(".btn-add-row")[0]);
}

function addBullet(btn) {
  const list = btn.previousElementSibling;
  const row = document.createElement("div");
  row.className = "dynamic-row";
  row.innerHTML = `<input type="text" placeholder="Led delivery of X, resulting in Y">
    <button class="btn-icon" onclick="this.closest('.dynamic-row').remove()">✕</button>`;
  list.appendChild(row);
}

function addProject(btn) {
  const list = btn.previousElementSibling;
  const row = document.createElement("div");
  row.className = "dynamic-row";
  row.innerHTML = `<div style="flex:1;display:flex;gap:6px">
      <input style="width:140px;flex-shrink:0" type="text" placeholder="Project Name">
      <input type="text" placeholder="What it was, your role, and the outcome">
    </div>
    <button class="btn-icon" onclick="this.closest('.dynamic-row').remove()">✕</button>`;
  list.appendChild(row);
}

function addEduRow() {
  const list = document.getElementById("edu-list");
  const row = document.createElement("div");
  row.className = "exp-block";
  row.innerHTML = `
    <div class="exp-block-header">
      <span>Degree</span>
      <button class="btn-icon" onclick="this.closest('.exp-block').remove()">✕</button>
    </div>
    <div class="field-row cols-2">
      <div class="field"><label>Full Degree Name</label><input class="edu-degree" placeholder="Master of Science in Information Systems Management"></div>
      <div class="field"><label>Institution</label><input class="edu-school" placeholder="University Name"></div>
    </div>
    <div class="field-row cols-2">
      <div class="field"><label>Year</label><input class="edu-year" placeholder="2024"></div>
      <div class="field"><label>Location</label><input class="edu-loc" placeholder="City, Country"></div>
    </div>`;
  list.appendChild(row);
}

function initProfileForm() {
  if (!document.getElementById("competencies-list").children.length)
    for (let i = 0; i < 3; i++) addRow("competencies-list", "competency-row", "e.g. Agile / SAFe Methodologies");
  if (!document.getElementById("exp-list").children.length) addExpBlock();
  if (!document.getElementById("edu-list").children.length) addEduRow();
}

// ── Build markdown from form ──────────────────────────────────────────────────

function buildProfileMd() {
  const v = id => (document.getElementById(id)?.value || "").trim();
  const lines = [];
  const name = v("p-name");

  lines.push(`# ${name || "Your Name"} — Full Profile`, "");
  lines.push("## Contact");
  if (v("p-location")) lines.push(`- Location: ${v("p-location")}`);
  if (v("p-phone"))    lines.push(`- Phone: ${v("p-phone")}`);
  if (v("p-email"))    lines.push(`- Email: ${v("p-email")}`);
  if (v("p-linkedin")) lines.push(`- LinkedIn: ${v("p-linkedin")}`);
  if (v("p-auth"))     lines.push(`- Work authorization: ${v("p-auth")}`);
  lines.push("", "---", "");

  const summary = v("p-summary");
  if (summary) lines.push("## Professional Summary", "", summary, "", "---", "");

  const competencies = [...document.querySelectorAll(".competency-row input")]
    .map(i => i.value.trim()).filter(Boolean);
  if (competencies.length) {
    lines.push("## Core Competencies", "");
    competencies.forEach(c => lines.push(`- ${c}`));
    lines.push("", "---", "");
  }

  const expBlocks = document.querySelectorAll("#exp-list .exp-block");
  if (expBlocks.length) {
    lines.push("## Professional Experience", "");
    expBlocks.forEach(b => {
      const title    = b.querySelector(".exp-title")?.value.trim() || "";
      const company  = b.querySelector(".exp-company")?.value.trim() || "";
      const location = b.querySelector(".exp-location")?.value.trim() || "";
      const start    = b.querySelector(".exp-start")?.value.trim() || "";
      const end      = b.querySelector(".exp-end")?.value.trim() || "";
      if (!title && !company) return;
      lines.push(`### ${title} — ${company}`);
      if (location) lines.push(`**Location:** ${location}`);
      if (start)    lines.push(`**Dates:** ${start} – ${end || "Present"}`);
      lines.push("");
      const bullets = [...b.querySelectorAll(".exp-bullets .dynamic-row input")]
        .map(i => i.value.trim()).filter(Boolean);
      if (bullets.length) {
        lines.push("**Bullets:**");
        bullets.forEach(bl => lines.push(`- ${bl}`));
        lines.push("");
      }
      const projects = [...b.querySelectorAll(".exp-projects .dynamic-row")];
      if (projects.length) {
        lines.push("**Key Projects:**");
        projects.forEach(p => {
          const inputs = p.querySelectorAll("input");
          const pname = inputs[0]?.value.trim();
          const pdesc = inputs[1]?.value.trim();
          if (pname || pdesc) lines.push(`- **${pname || "Project"}:** ${pdesc || ""}`);
        });
        lines.push("");
      }
    });
    lines.push("---", "");
  }

  const eduBlocks = document.querySelectorAll("#edu-list .exp-block");
  if (eduBlocks.length) {
    lines.push("## Education", "");
    eduBlocks.forEach(b => {
      const degree = b.querySelector(".edu-degree")?.value.trim() || "";
      const school = b.querySelector(".edu-school")?.value.trim() || "";
      const year   = b.querySelector(".edu-year")?.value.trim() || "";
      const loc    = b.querySelector(".edu-loc")?.value.trim() || "";
      if (!degree) return;
      lines.push(`### ${degree}`);
      if (school) lines.push(`- **Institution:** ${school}`);
      if (loc)    lines.push(`- **Location:** ${loc}`);
      if (year)   lines.push(`- **Year conferred:** ${year}`);
      lines.push("");
    });
    lines.push("---", "");
  }

  const certs = [...document.querySelectorAll(".cert-row input")]
    .map(i => i.value.trim()).filter(Boolean);
  if (certs.length) {
    lines.push("## Certifications", "");
    certs.forEach(c => lines.push(`- ${c}`));
  }

  return lines.join("\n");
}

// ── Parse markdown back into form ─────────────────────────────────────────────

function parseProfileMdIntoForm(md) {
  if (!md) return;

  const set = (id, val) => { const el = document.getElementById(id); if (el && val) el.value = val; };
  const lines = md.split("\n");
  let section = "";

  const contact = {}, summary = [], competencies = [], experience = [], education = [], certifications = [];
  let currentExp = null, currentEdu = null, inBullets = false, inProjects = false;

  for (const raw of lines) {
    const line = raw.trimEnd();

    if (line.startsWith("## Contact")) { section = "contact"; continue; }
    if (line.startsWith("## Professional Summary")) { section = "summary"; continue; }
    if (line.startsWith("## Core Competencies")) { section = "competencies"; continue; }
    if (line.startsWith("## Professional Experience")) { section = "experience"; continue; }
    if (line.startsWith("## Education")) { section = "education"; continue; }
    if (line.startsWith("## Certifications")) { section = "certifications"; continue; }
    if (line.startsWith("---")) continue;

    if (section === "contact" && line.startsWith("- ")) {
      const m = line.slice(2).match(/^([\w ]+):\s*(.+)/);
      if (m) contact[m[1].toLowerCase().trim()] = m[2].trim();
    }

    if (section === "summary" && line.trim()) summary.push(line.trim());

    if (section === "competencies" && line.startsWith("- ")) competencies.push(line.slice(2).trim());

    if (section === "experience") {
      if (line.startsWith("### ")) {
        const parts = line.slice(4).split(" — ");
        currentExp = { title: parts[0]?.trim()||"", company: parts.slice(1).join(" — ").trim()||"", location:"", start:"", end:"", bullets:[], projects:[] };
        experience.push(currentExp);
        inBullets = false; inProjects = false;
      } else if (currentExp) {
        const locM = line.match(/^\*\*Location:\*\*\s*(.+)/);
        const dateM = line.match(/^\*\*Dates:\*\*\s*(.+)/);
        if (locM) currentExp.location = locM[1].trim();
        else if (dateM) {
          const dp = dateM[1].split(" – ");
          currentExp.start = dp[0]?.trim()||"";
          currentExp.end = dp[1]?.trim()||"";
        } else if (line.trim() === "**Bullets:**") { inBullets = true; inProjects = false; }
        else if (line.trim() === "**Key Projects:**") { inProjects = true; inBullets = false; }
        else if (inBullets && line.startsWith("- ")) currentExp.bullets.push(line.slice(2).trim());
        else if (inProjects && line.startsWith("- ")) {
          const pm = line.slice(2).match(/^\*\*(.+?):\*\*\s*(.*)/);
          if (pm) currentExp.projects.push({ name: pm[1].trim(), desc: pm[2].trim() });
        }
      }
    }

    if (section === "education") {
      if (line.startsWith("### ")) {
        currentEdu = { degree: line.slice(4).trim(), school:"", year:"", location:"" };
        education.push(currentEdu);
      } else if (currentEdu && line.startsWith("- ")) {
        const m = line.slice(2).match(/^\*\*(.+?):\*\*\s*(.*)/);
        if (m) {
          const key = m[1].toLowerCase();
          if (key.includes("institution")) currentEdu.school = m[2].trim();
          else if (key.includes("location")) currentEdu.location = m[2].trim();
          else if (key.includes("year")) currentEdu.year = m[2].trim();
        }
      }
    }

    if (section === "certifications" && line.startsWith("- ")) certifications.push(line.slice(2).trim());
  }

  // Fill contact
  set("p-name",     contact["name"] || contact["full name"] || "");
  set("p-location", contact["location"] || "");
  set("p-phone",    contact["phone"] || "");
  set("p-email",    contact["email"] || "");
  set("p-linkedin", contact["linkedin"] || "");
  if (contact["work authorization"]) {
    const auth = contact["work authorization"].toLowerCase();
    const sel = document.getElementById("p-auth");
    if (sel) {
      if (auth.includes("citizen"))       sel.value = "US Citizen — no sponsorship required";
      else if (auth.includes("green"))    sel.value = "Green Card holder — legally authorized to work in the U.S.";
      else if (auth.includes("h-1b") || auth.includes("sponsor")) sel.value = "Requires H-1B sponsorship";
      else if (auth.includes("authoriz")) sel.value = "Authorized to work in the US · No sponsorship required";
    }
  }

  set("p-summary", summary.join(" "));

  // Fill competencies
  const compList = document.getElementById("competencies-list");
  if (compList && competencies.length) {
    compList.innerHTML = "";
    competencies.forEach(c => addRow("competencies-list", "competency-row", "e.g. Agile / SAFe Methodologies", c));
  }

  // Fill experience
  const expList = document.getElementById("exp-list");
  if (expList && experience.length) {
    expList.innerHTML = "";
    experience.forEach(exp => {
      addExpBlock();
      const block = expList.lastElementChild;
      const q = cls => block.querySelector(cls);
      if (q(".exp-title"))    q(".exp-title").value    = exp.title;
      if (q(".exp-company"))  q(".exp-company").value  = exp.company;
      if (q(".exp-location")) q(".exp-location").value = exp.location;
      if (q(".exp-start"))    q(".exp-start").value    = exp.start;
      if (q(".exp-end"))      q(".exp-end").value      = exp.end;
      const bulletList = block.querySelector(".exp-bullets");
      if (bulletList && exp.bullets.length) {
        bulletList.innerHTML = "";
        exp.bullets.forEach(b => {
          const row = document.createElement("div");
          row.className = "dynamic-row";
          row.innerHTML = `<input type="text" value="${b.replace(/"/g,'&quot;')}"><button class="btn-icon" onclick="this.closest('.dynamic-row').remove()">✕</button>`;
          bulletList.appendChild(row);
        });
      }
      const projList = block.querySelector(".exp-projects");
      if (projList && exp.projects.length) {
        projList.innerHTML = "";
        exp.projects.forEach(p => {
          const row = document.createElement("div");
          row.className = "dynamic-row";
          row.innerHTML = `<div style="flex:1;display:flex;gap:6px"><input style="width:140px;flex-shrink:0" type="text" value="${(p.name||'').replace(/"/g,'&quot;')}"><input type="text" value="${(p.desc||'').replace(/"/g,'&quot;')}"></div><button class="btn-icon" onclick="this.closest('.dynamic-row').remove()">✕</button>`;
          projList.appendChild(row);
        });
      }
    });
  }

  // Fill education
  const eduList = document.getElementById("edu-list");
  if (eduList && education.length) {
    eduList.innerHTML = "";
    education.forEach(edu => {
      addEduRow();
      const block = eduList.lastElementChild;
      const q = cls => block.querySelector(cls);
      if (q(".edu-degree")) q(".edu-degree").value = edu.degree;
      if (q(".edu-school")) q(".edu-school").value = edu.school;
      if (q(".edu-year"))   q(".edu-year").value   = edu.year;
      if (q(".edu-loc"))    q(".edu-loc").value    = edu.location;
    });
  }

  // Fill certifications
  const certList = document.getElementById("certs-list");
  if (certList && certifications.length) {
    certList.innerHTML = "";
    certifications.forEach(c => addRow("certs-list", "cert-row", "e.g. PSPO I, Scrum.org", c));
  }
}

// ── Autofill from uploaded resume ─────────────────────────────────────────────

async function autofillFromResume(input) {
  const file = input.files[0];
  if (!file) return;
  const statusEl = document.getElementById("autofill-status");
  if (statusEl) statusEl.innerHTML = `<span class="spinner" style="border-color:#60a5fa;border-top-color:transparent"></span> Extracting…`;

  const fd = new FormData();
  fd.append("file", file);

  try {
    const res = await fetch("/api/setup/parse-resume", { method: "POST", body: fd });
    const data = await res.json();
    if (!data.ok) {
      if (statusEl) statusEl.innerHTML = `<span style="color:#f87171">⚠ ${data.error}</span>`;
      return;
    }
    fillForm(data.data);
    if (statusEl) statusEl.innerHTML = `<span style="color:#4ade80">✓ Form filled from ${file.name}</span>`;
  } catch (e) {
    if (statusEl) statusEl.innerHTML = `<span style="color:#f87171">⚠ Upload failed. Try again.</span>`;
  }
  input.value = "";
}

function fillForm(d) {
  const set = (id, val) => { const el = document.getElementById(id); if (el && val) el.value = val; };
  set("p-name", d.name); set("p-email", d.email); set("p-phone", d.phone);
  set("p-location", d.location); set("p-linkedin", d.linkedin); set("p-summary", d.summary);
  if (d.auth) {
    const sel = document.getElementById("p-auth");
    if (sel) {
      const lower = d.auth.toLowerCase();
      if (lower.includes("citizen"))     sel.value = "US Citizen — no sponsorship required";
      else if (lower.includes("green"))  sel.value = "Green Card holder — legally authorized to work in the U.S.";
      else if (lower.includes("h-1b") || lower.includes("sponsor")) sel.value = "Requires H-1B sponsorship";
      else sel.value = "Authorized to work in the US · No sponsorship required";
    }
  }
  const compList = document.getElementById("competencies-list");
  if (compList && d.competencies?.length) {
    compList.innerHTML = "";
    d.competencies.forEach(c => addRow("competencies-list", "competency-row", "e.g. Agile / SAFe Methodologies", c));
  }
  const expList = document.getElementById("exp-list");
  if (expList && d.experience?.length) {
    expList.innerHTML = "";
    d.experience.forEach(exp => {
      addExpBlock();
      const block = expList.lastElementChild;
      const q = cls => block.querySelector(cls);
      if (q(".exp-title"))    q(".exp-title").value    = exp.title    || "";
      if (q(".exp-company"))  q(".exp-company").value  = exp.company  || "";
      if (q(".exp-location")) q(".exp-location").value = exp.location || "";
      if (q(".exp-start"))    q(".exp-start").value    = exp.start    || "";
      if (q(".exp-end"))      q(".exp-end").value      = exp.end      || "";
      const bulletList = block.querySelector(".exp-bullets");
      if (bulletList && exp.bullets?.length) {
        bulletList.innerHTML = "";
        exp.bullets.forEach(b => { const row = document.createElement("div"); row.className = "dynamic-row"; row.innerHTML = `<input type="text" value="${b.replace(/"/g,'&quot;')}"><button class="btn-icon" onclick="this.closest('.dynamic-row').remove()">✕</button>`; bulletList.appendChild(row); });
      }
      const projList = block.querySelector(".exp-projects");
      if (projList && exp.projects?.length) {
        projList.innerHTML = "";
        exp.projects.forEach(p => { const row = document.createElement("div"); row.className = "dynamic-row"; row.innerHTML = `<div style="flex:1;display:flex;gap:6px"><input style="width:140px;flex-shrink:0" type="text" value="${(p.name||'').replace(/"/g,'&quot;')}"><input type="text" value="${(p.desc||'').replace(/"/g,'&quot;')}"></div><button class="btn-icon" onclick="this.closest('.dynamic-row').remove()">✕</button>`; projList.appendChild(row); });
      }
    });
  }
  const eduList = document.getElementById("edu-list");
  if (eduList && d.education?.length) {
    eduList.innerHTML = "";
    d.education.forEach(edu => {
      addEduRow();
      const block = eduList.lastElementChild;
      const q = cls => block.querySelector(cls);
      if (q(".edu-degree")) q(".edu-degree").value = edu.degree   || "";
      if (q(".edu-school")) q(".edu-school").value = edu.school   || "";
      if (q(".edu-year"))   q(".edu-year").value   = edu.year     || "";
      if (q(".edu-loc"))    q(".edu-loc").value    = edu.location || "";
    });
  }
  const certList = document.getElementById("certs-list");
  if (certList && d.certifications?.length) {
    certList.innerHTML = "";
    d.certifications.forEach(c => addRow("certs-list", "cert-row", "e.g. PSPO I, Scrum.org", c));
  }
}
