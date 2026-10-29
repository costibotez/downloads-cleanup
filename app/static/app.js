const $ = (id) => document.getElementById(id);
const PILE_MAX = 320;
const BADGE_COLORS = {
  pdf: "#d0473f", zip: "#6b7688", gz: "#6b7688", dmg: "#5d6b8a", pkg: "#5d6b8a", app: "#5d6b8a",
  doc: "#4f73b8", docx: "#4f73b8", txt: "#8a96a8", md: "#8a96a8", csv: "#3f8f6b", xlsx: "#3f8f6b", xls: "#3f8f6b",
  json: "#b58a3a", xml: "#b58a3a", sql: "#b58a3a", svg: "#d07a4f", php: "#7660a8", html: "#d0644f", sh: "#4a4a4a",
  mp3: "#0f8a8a", m4a: "#0f8a8a", wav: "#0f8a8a", opus: "#0f8a8a", mov: "#2f3b55", mp4: "#2f3b55",
};

let S = { categories: [], config: {}, plan: null, history: [] };
let overrides = {};   // id -> { category?, include? }
let polling = null;

async function api(path, body) {
  const res = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "X-Token": window.TOKEN, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}

const fmt = (n) => n.toLocaleString("en-US");
const leaf = (cat) => cat.split("/").pop();
const effective = (item) => ({ ...item, ...(overrides[item.id] || {}) });

function groupOf(cat) {
  const hit = S.categories.find(([c]) => c === cat);
  return hit ? hit[1] : "Your folders";
}

function tile(item) {
  const t = el("div", "tile");
  if (item.thumb) {
    const img = new Image();
    img.decoding = "async";
    img.loading = "lazy";
    img.src = "/thumb/" + item.thumb;
    img.alt = "";
    t.append(img);
  } else {
    t.classList.add("badge");
    t.style.background = BADGE_COLORS[item.ext] || "#8a96a8";
    t.textContent = (item.ext || "file").slice(0, 4);
  }
  return t;
}

const FOLDER_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>';

function categoryOrder() {
  const custom = (S.config.rules || []).map((r) => r.folder);
  return [...custom, ...S.categories.map(([c]) => c)];
}

function buckets() {
  const map = new Map();
  for (const item of S.plan || []) {
    const e = effective(item);
    if (!e.include) continue;
    if (!map.has(e.category)) map.set(e.category, []);
    map.get(e.category).push(e);
  }
  return map;
}

function renderFolders({ fromZero = false } = {}) {
  const box = $("folders");
  box.replaceChildren();
  const map = buckets();
  if (!map.size) {
    box.append(el("div", "empty", S.plan ? "Nothing to sort here. Clean already!" : "Your folders appear here after a scan."));
    return;
  }
  const order = categoryOrder();
  const cats = [...map.keys()].sort((a, b) => order.indexOf(a) - order.indexOf(b));
  let lastGroup = null, grid = null;
  for (const cat of cats) {
    const group = groupOf(cat);
    if (group !== lastGroup) {
      box.append(el("div", "group-title", group));
      grid = el("div", "grid");
      box.append(grid);
      lastGroup = group;
    }
    const items = map.get(cat);
    const card = el("button", "card");
    card.dataset.cat = cat;
    card.title = cat;
    const head = el("div", "card-head");
    head.innerHTML = FOLDER_ICON;
    head.append(el("span", "", leaf(cat)), el("b", "", fromZero ? "0" : fmt(items.length)));
    const strip = el("div", "strip");
    if (!fromZero) items.filter((i) => i.thumb).concat(items.filter((i) => !i.thumb)).slice(0, 6).forEach((i) => strip.append(tile(i)));
    card.append(head, strip);
    card.addEventListener("click", () => openFolder(cat));
    grid.append(card);
  }
}

function seeded(i) {
  const x = Math.sin(i * 12.9898 + 78.233) * 43758.5453;
  return x - Math.floor(x);
}

function renderPile() {
  const pile = $("pile");
  pile.replaceChildren();
  const items = (S.plan || []).filter((i) => effective(i).include);
  const withThumb = items.filter((i) => i.thumb);
  const sample = withThumb.slice(0, Math.round(PILE_MAX * 0.75));
  sample.push(...items.filter((i) => !i.thumb).slice(0, PILE_MAX - sample.length));
  sample.sort((a, b) => seeded(a.id) - seeded(b.id));
  const size = pile.clientWidth || 440;
  const R = size / 2 - 26;
  sample.forEach((item, n) => {
    const t = tile(item);
    const r = R * Math.sqrt(seeded(n + 1));
    const a = seeded(n + 7) * Math.PI * 2;
    const rot = (seeded(n + 3) - 0.5) * 26;
    t.style.transform = `translate(-50%, -50%) translate(${Math.cos(a) * r}px, ${Math.sin(a) * r}px) rotate(${rot}deg)`;
    t.style.zIndex = n;
    t.dataset.id = item.id;
    pile.append(t);
  });
  $("pileCaption").textContent = items.length ? `a total mess · ${fmt(items.length)} files` : S.phase === "done" ? "all tidy" : "a total mess";
}

function setPhaseUI() {
  const busy = ["listing", "analyzing", "duplicates"].includes(S.phase);
  const ready = S.phase === "ready" && S.plan;
  const lastUndoable = (S.history || []).find((h) => !h.undone);
  $("scanBtn").classList.toggle("hidden", busy || ready || S.phase === "done");
  $("sortBtn").classList.toggle("hidden", !ready);
  $("rescanBtn").classList.toggle("hidden", !(ready || S.phase === "done"));
  $("undoBtn").classList.toggle("hidden", busy || !lastUndoable);
  $("progress").classList.toggle("hidden", !busy);
  const folder = S.config.folder || "";
  $("folderName").textContent = /^\/Users\/[^/]+\//.test(folder) ? folder.replace(/^\/Users\/[^/]+/, "~") : folder.split("/").pop();
  $("folderChip").title = folder + " (click to choose another folder)";
  $("windowTitle").textContent = "Sort my " + (S.config.folder || "").split("/").pop();
  if (ready) {
    const n = (S.plan || []).filter((i) => effective(i).include).length;
    const renamed = S.plan.filter((i) => effective(i).include && i.newName !== i.name).length;
    $("sortBtn").textContent = `Sort ${fmt(n)} files`;
    $("sortBtn").disabled = !n;
    $("hint").textContent = `Preview only, nothing has moved yet. ${fmt(renamed)} files get a name based on what's in them. Click a folder to check or change it.`;
    $("headline").innerHTML = `${fmt(n)} files. <em>Ready</em> to sort.`;
  } else if (busy) {
    const pct = S.total ? Math.round((S.done / S.total) * 100) : 5;
    $("bar").style.width = pct + "%";
    $("progressText").textContent = S.total ? `${S.message} · ${fmt(S.done)} / ${fmt(S.total)}` : S.message;
    $("hint").textContent = "The first scan takes a minute or two. After that it remembers what it has seen.";
  } else if (S.phase === "error") {
    $("hint").textContent = "Something went wrong: " + S.error;
  } else if (S.phase === "idle" && !S.message) {
    $("headline").replaceChildren("Sort my ", el("em", "", (S.config.folder || "").split("/").pop()), ".");
  }
}

async function refresh() {
  const data = await api("/api/state");
  const hadPlan = !!S.plan;
  S = data;
  setPhaseUI();
  if (S.plan && !hadPlan) {
    overrides = {};
    renderFolders();
    renderPile();
  }
  return data;
}

function poll() {
  clearInterval(polling);
  polling = setInterval(async () => {
    const d = await refresh().catch(() => null);
    if (d && !["listing", "analyzing", "duplicates"].includes(d.phase)) clearInterval(polling);
  }, 500);
}

async function startScan() {
  $("overlay").classList.add("hidden");
  S.plan = null;
  renderFolders();
  renderPile();
  try {
    await api("/api/scan", {});
  } catch (e) {
    $("hint").textContent = e.message;
    return;
  }
  S.phase = "listing";
  setPhaseUI();
  poll();
}

function wait(ms) { return new Promise((r) => setTimeout(r, ms)); }

async function sortNow() {
  const items = S.plan.map((i) => {
    const e = effective(i);
    return { id: i.id, category: e.category, include: e.include };
  });
  const total = items.filter((i) => i.include).length;
  if (total > 400 && !confirm(`Move ${fmt(total)} files into folders inside ${S.config.folder}?\n\nYou can undo this afterwards.`)) return;
  $("sortBtn").disabled = true;
  $("rescanBtn").classList.add("hidden");
  const request = api("/api/apply", { items });

  // Fly the pile into the folders.
  const byId = new Map(S.plan.map((i) => [String(i.id), effective(i)]));
  const counts = {};
  renderFolders({ fromZero: true });
  const cards = new Map([...document.querySelectorAll(".card")].map((c) => [c.dataset.cat, c]));
  const tiles = [...$("pile").children].reverse();
  const totals = Object.fromEntries([...buckets()].map(([k, v]) => [k, v.length]));
  const flights = tiles.map((t, n) => {
    const item = byId.get(t.dataset.id);
    const card = cards.get(item.category);
    if (!card) return Promise.resolve();
    const from = t.getBoundingClientRect();
    const to = card.getBoundingClientRect();
    t.classList.add("flying");
    t.style.transform = `translate(${from.left}px, ${from.top}px)`;
    const dx = to.left + 16 + seeded(n) * Math.max(10, to.width - 60);
    const dy = to.top + to.height - 40;
    const anim = t.animate([
      { transform: `translate(${from.left}px, ${from.top}px) rotate(${(seeded(n) - 0.5) * 30}deg) scale(1)` },
      { transform: `translate(${(from.left + dx) / 2}px, ${Math.min(from.top, dy) - 60}px) rotate(0deg) scale(.9)`, offset: 0.55 },
      { transform: `translate(${dx}px, ${dy}px) scale(.55)`, opacity: 0.2 },
    ], { duration: 750, delay: n * Math.max(4, 1400 / tiles.length), easing: "cubic-bezier(.5,0,.3,1)", fill: "forwards" });
    return anim.finished.then(() => {
      t.remove();
      counts[item.category] = (counts[item.category] || 0) + 1;
      const shown = Math.min(totals[item.category], Math.round((counts[item.category] / Math.max(1, tilesFor(item.category))) * totals[item.category]));
      card.querySelector(".card-head b").textContent = fmt(shown);
      const strip = card.querySelector(".strip");
      if (strip.children.length < 6) strip.append(tile(item));
      card.classList.remove("bump");
      void card.offsetWidth;
      card.classList.add("bump");
    });
  });
  function tilesFor(cat) { return tiles.filter((t) => byId.get(t.dataset.id).category === cat).length; }

  let result;
  try {
    [result] = await Promise.all([request, Promise.all(flights)]);
  } catch (e) {
    $("hint").textContent = "Could not sort: " + e.message;
    await refresh();
    return;
  }
  for (const [cat, card] of cards) card.querySelector(".card-head b").textContent = fmt(totals[cat] || 0);
  $("overlayCount").textContent = `${fmt(result.moved)} files.`;
  $("overlay").classList.remove("hidden");
  $("headline").innerHTML = `${fmt(result.moved)} files. <em>Sorted</em>.`;
  $("hint").textContent = result.errorCount
    ? `${result.errorCount} files were skipped: ${result.errors.slice(0, 3).join("; ")}`
    : "Click a folder to open it in Finder. Changed your mind? Undo puts everything back.";
  await refresh();
  S.phase = "done";
  $("pileCaption").textContent = "all tidy";
  setTimeout(() => $("overlay").classList.add("hidden"), 2600);
  document.querySelectorAll(".card").forEach((c) => c.replaceWith(c.cloneNode(true)));
  document.querySelectorAll(".card").forEach((c) => c.addEventListener("click", () =>
    api("/api/reveal", { path: S.config.folder + "/" + c.dataset.cat })));
}

function openFolder(cat) {
  const list = $("drawerList");
  list.replaceChildren();
  $("drawerTitle").textContent = leaf(cat);
  $("drawerGroup").textContent = cat.includes("/") ? cat.split("/").slice(0, -1).join(" / ") : groupOf(cat);
  const options = categoryOrder();
  const items = (S.plan || []).filter((i) => effective(i).category === cat);
  for (const item of items.slice(0, 600)) {
    const e = effective(item);
    const li = el("li", e.include ? "" : "off");
    const check = el("input");
    check.type = "checkbox";
    check.checked = e.include;
    check.title = "Include this file";
    check.addEventListener("change", () => {
      overrides[item.id] = { ...overrides[item.id], include: check.checked };
      li.classList.toggle("off", !check.checked);
      renderFolders(); renderPile(); setPhaseUI();
    });
    const names = el("div", "names");
    names.append(el("b", "", item.name));
    if (item.newName !== item.name) {
      const s = el("small");
      s.append("→ ", el("span", "to", item.newName));
      names.append(s);
    }
    names.append(el("small", "", item.reason));
    const sel = el("select");
    for (const c of options) {
      const o = el("option", "", c);
      o.value = c;
      o.selected = c === e.category;
      sel.append(o);
    }
    sel.addEventListener("change", () => {
      overrides[item.id] = { ...overrides[item.id], category: sel.value };
      li.remove();
      renderFolders(); renderPile(); setPhaseUI();
    });
    names.append(sel);
    li.append(check, tile(item), names);
    list.append(li);
  }
  if (items.length > 600) list.append(el("li", "", `…and ${fmt(items.length - 600)} more`));
  $("settings").classList.add("hidden");
  $("drawer").classList.remove("hidden");
}

function ruleRow(rule = { folder: "", keywords: [] }) {
  const row = el("div", "rule");
  const name = el("input");
  name.placeholder = "Folder name, e.g. Wedding";
  name.value = rule.folder;
  const kws = el("input");
  kws.placeholder = "keywords, e.g. wedding, bride, nunta";
  kws.value = rule.keywords.join(", ");
  const del = el("button", "", "×");
  del.title = "Remove";
  del.addEventListener("click", () => row.remove());
  row.append(name, kws, del);
  return row;
}

function openSettings() {
  const c = S.config;
  $("optRename").checked = c.rename;
  $("optDupes").checked = c.duplicates;
  $("optApps").checked = c.apps;
  $("rules").replaceChildren(...(c.rules || []).map(ruleRow));
  const hist = $("history");
  hist.replaceChildren();
  if (!S.history.length) hist.append(el("li", "", "No sorts yet."));
  for (const h of S.history) {
    const li = el("li");
    li.append(el("span", "", `${h.time.replace("T", " ")} · ${fmt(h.count)} files${h.undone ? " · undone" : ""}`));
    if (!h.undone) {
      const b = el("button", "soft", "Undo");
      b.addEventListener("click", () => undo(h.id));
      li.append(b);
    }
    hist.append(li);
  }
  $("drawer").classList.add("hidden");
  $("settings").classList.remove("hidden");
}

async function saveSettings() {
  const rules = [...document.querySelectorAll("#rules .rule")].map((r) => {
    const [name, kws] = r.querySelectorAll("input");
    return { folder: name.value.trim(), keywords: kws.value.split(",").map((k) => k.trim()).filter(Boolean) };
  }).filter((r) => r.folder && r.keywords.length);
  await api("/api/config", {
    rename: $("optRename").checked, duplicates: $("optDupes").checked, apps: $("optApps").checked, rules,
  });
  $("settings").classList.add("hidden");
  await refresh();
  startScan();
}

async function undo(id) {
  const target = id || (S.history.find((h) => !h.undone) || {}).id;
  if (!target) return;
  if (!confirm("Put every file from that sort back where it was?")) return;
  const r = await api("/api/undo", { id: target });
  $("settings").classList.add("hidden");
  $("overlay").classList.add("hidden");
  S.plan = null;
  await refresh();
  $("headline").innerHTML = `Put back <em>${fmt(r.restored)}</em> files.`;
  $("hint").textContent = r.errors.length ? r.errors.slice(0, 3).join("; ") : "Everything is back where it was.";
  renderFolders();
  renderPile();
}

async function pickFolder() {
  const r = await api("/api/pick-folder", {});
  if (r.folder) {
    S.plan = null;
    await refresh();
    renderFolders();
    renderPile();
    $("headline").replaceChildren("Sort my ", el("em", "", r.folder.split("/").pop()), ".");
  }
}

$("scanBtn").addEventListener("click", startScan);
$("rescanBtn").addEventListener("click", startScan);
$("sortBtn").addEventListener("click", sortNow);
$("undoBtn").addEventListener("click", () => undo());
$("folderChip").addEventListener("click", pickFolder);
$("settingsBtn").addEventListener("click", openSettings);
$("settingsClose").addEventListener("click", () => $("settings").classList.add("hidden"));
$("drawerClose").addEventListener("click", () => $("drawer").classList.add("hidden"));
$("quitBtn").addEventListener("click", async () => {
  await api("/api/quit", {}).catch(() => {});
  document.body.innerHTML = '<main><section class="hero"><h1>See you next <em>mess</em>.</h1><p class="lede">The sorter has stopped. You can close this tab.</p></section></main>';
});
$("addRule").addEventListener("click", () => $("rules").append(ruleRow()));
$("saveSettings").addEventListener("click", saveSettings);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { $("drawer").classList.add("hidden"); $("settings").classList.add("hidden"); }
});
window.addEventListener("resize", () => { if (S.plan) renderPile(); });

refresh().then((d) => {
  if (["listing", "analyzing", "duplicates"].includes(d.phase)) poll();
});
