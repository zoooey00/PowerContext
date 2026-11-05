import "./style.css";
import { chunks } from "./config.mjs";
const $ = (s) => document.querySelector(s),
  worker = new Worker(new URL("./worker.js", import.meta.url), {
    type: "module",
  });
let sequence = 0,
  pending = new Map(),
  busy = false,
  opened = "",
  probes = [];
const logs = [];
function status(s) {
  $("#status").textContent = s;
}
worker.onmessage = ({ data: d }) => {
  if (d.backend && d.profile)
    $("#backend").textContent =
      `● ${d.backend.toUpperCase()} · ${d.profile}${d.reason ? " / " + d.reason : ""}`;
  if (d.progress?.status === "progress")
    status(`加载 ${d.progress.file}：${Math.round(d.progress.progress || 0)}%`);
  if (d.total) {
    $("#progress").max = d.total;
    $("#progress").value = d.completed;
    status(`本地向量化 ${d.completed} / ${d.total}`);
  }
  if (pending.has(d.id)) {
    const { resolve, reject } = pending.get(d.id);
    pending.delete(d.id);
    d.error ? reject(new Error(d.error)) : resolve(d);
  }
};
worker.onerror = (e) => {
  for (const p of pending.values()) p.reject(new Error(e.message));
  pending.clear();
};
async function api(path, body) {
  const r = await fetch(
    `/api/${path}`,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const d = await r.json();
  if (!r.ok) throw new Error(d.error);
  return d;
}
function config() {
  return {
    name: $("#kb").value,
    profile: $("#profile").value,
    forceWasm: $("#wasm").checked,
    batchSize: Number($("#batch").value),
  };
}
const base = (c) => `kbs/${encodeURIComponent(c.name)}/${c.profile}`;
async function embed(texts, c = config()) {
  const id = ++sequence;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    worker.postMessage({ id, texts, ...c });
  });
}
async function guard(fn) {
  if (busy) return;
  busy = true;
  document
    .querySelectorAll("button,input,select,textarea")
    .forEach((e) => (e.disabled = true));
  try {
    return await fn();
  } catch (e) {
    status(`失败：${e.message}`);
    throw e;
  } finally {
    busy = false;
    document
      .querySelectorAll("button,input,select,textarea")
      .forEach((e) => (e.disabled = false));
  }
}
async function open(c = config()) {
  const d = await api(base(c), {});
  opened = base(c);
  $("#count").textContent = `${c.name} / ${c.profile} · ${d.count} 个片段`;
  return d;
}
async function list() {
  const d = await api("kbs");
  $("#collections").replaceChildren(new Option("选择已有知识库", ""));
  for (const entry of d.collections) {
    const name = typeof entry === "string" ? entry : entry.name;
    const m = /^edge_(.+)_(fp32|fp16|q8)$/.exec(name);
    if (m)
      $("#collections").add(new Option(`${m[1]} / ${m[2]}`, `${m[1]}:${m[2]}`));
  }
}
async function hash(s) {
  return Array.from(
    new Uint8Array(
      await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)),
    ),
    (b) => b.toString(16).padStart(2, "0"),
  ).join("");
}
async function prepare(documents) {
  const rows = [];
  for (const doc of documents)
    for (const text of chunks(doc.text))
      rows.push({
        id: await hash(`${doc.source}\0${text}`),
        text,
        source: doc.source,
      });
  return rows;
}
async function refresh(c = config()) {
  if (!probes.length) throw new Error("本次会话尚无待刷新数据，请导入资料");
  status("正在刷新并验证向量与全文索引可见性…");
  let r = { refreshMs: 0, count: 0 };
  for (let i = 0; i < probes.length; i += 128) {
    const d = await api(`${base(c)}/refresh`, {
      probes: probes.slice(i, i + 128),
    });
    r.refreshMs += d.refreshMs;
    r.count = d.count;
  }
  probes = [];
  logs.push({ type: "refresh", ...r, ...c });
  status(`索引刷新完成，${r.count} 个片段可检索`);
  await open(c);
  return r;
}
async function ingest(documents, c = config(), refreshEveryBatch = false) {
  await open(c);
  const rows = await prepare(documents);
  if (!rows.length) throw new Error("请提供非空文本");
  let embedMs = 0,
    writeMs = 0,
    refreshMs = 0;
  const start = performance.now();
  probes = [];
  for (let i = 0; i < rows.length; i += 64) {
    const batch = rows.slice(i, i + 64),
      e = await embed(
        batch.map((r) => r.text),
        c,
      );
    embedMs += e.embedMs;
    batch.forEach((r, j) => (r.embedding = e.vectors[j]));
    const w = await api(`${base(c)}/import`, { rows: batch });
    writeMs += w.writeMs;
    const seen = new Set(probes.map((p) => p.source));
    for (const row of batch)
      if (!seen.has(row.source)) {
        seen.add(row.source);
        probes.push({
          id: row.id,
          source: row.source,
          embedding: row.embedding,
          keyword: row.text,
        });
      }
    if (refreshEveryBatch) refreshMs += (await refresh(c)).refreshMs;
  }
  if (probes.length) refreshMs += (await refresh(c)).refreshMs;
  const record = {
    type: "import",
    ...c,
    chunks: rows.length,
    embedMs,
    writeMs,
    refreshMs,
    totalMs: performance.now() - start,
  };
  logs.push(record);
  await list();
  return { rows, record };
}
async function search(text, c = config(), mode = $("#mode").value) {
  if (opened !== base(c)) await open(c);
  const start = performance.now(),
    e = await embed([text], c);
  const d = await api(`${base(c)}/search`, {
    text,
    embedding: e.vectors[0],
    mode,
    k: 5,
  });
  const record = {
    type: "query",
    ...c,
    mode,
    text,
    backend: e.backend,
    loadMs: e.loadMs,
    embedMs: e.embedMs,
    searchMs: d.searchMs,
    totalMs: performance.now() - start,
  };
  logs.push(record);
  return { ...d, record };
}
function render(d) {
  $("#results").replaceChildren();
  for (const [i, id] of d.result.ids[0].entries()) {
    const article = document.createElement("article");
    article.className = "result";
    const title = document.createElement("h3"),
      text = document.createElement("pre");
    title.textContent = `${i + 1}. ${d.result.metadatas[0][i]?.source || id}`;
    text.textContent = d.result.documents[0][i];
    article.append(title, text);
    $("#results").append(article);
  }
  if (!d.result.ids[0].length)
    $("#results").textContent = "当前知识库没有匹配结果。";
  $("#timing").textContent =
    `查询向量化 ${d.record.embedMs.toFixed(1)} ms · seekdb ${d.searchMs.toFixed(1)} ms · 端到端 ${d.record.totalMs.toFixed(1)} ms`;
}
function action(selector, fn) {
  $(selector).onclick = () => guard(fn).catch(() => {});
}
action("#connect", async () => {
  await open();
  await list();
  status("知识库已打开");
});
action("#import", async () => {
  const docs = [];
  for (const f of $("#files").files) {
    if (!/\.(txt|md)$/i.test(f.name) || f.size > 5e6)
      throw new Error("仅接受不超过 5 MB 的 TXT/MD");
    docs.push({ source: f.name, text: await f.text() });
  }
  if ($("#text").value.trim())
    docs.push({ source: "粘贴文本", text: $("#text").value });
  await ingest(docs);
});
action("#sample", async () => {
  const d = await (await fetch("/fixtures/corpus.json")).json();
  await ingest(d);
});
action("#refresh", () => refresh());
$("#search").onsubmit = (e) => {
  e.preventDefault();
  guard(async () => render(await search($("#query").value))).catch(() => {});
};
for (const id of ["#profile", "#kb"])
  $(id).onchange = () => {
    opened = "";
    probes = [];
    $("#results").replaceChildren();
    $("#count").textContent = "配置已改变，请打开知识库";
  };
$("#collections").onchange = () => {
  const v = $("#collections").value;
  if (v) {
    const [name, p] = v.split(":");
    $("#kb").value = name;
    $("#profile").value = p;
    opened = "";
    probes = [];
    $("#results").replaceChildren();
    guard(() => open()).catch(() => {});
  }
};
$("#export").onclick = () => {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(
    new Blob(
      [
        JSON.stringify(
          {
            userAgent: navigator.userAgent,
            hardwareConcurrency: navigator.hardwareConcurrency,
            logs,
          },
          null,
          2,
        ),
      ],
      { type: "application/json" },
    ),
  );
  a.download = "edge-kb-timings.json";
  a.click();
  URL.revokeObjectURL(a.href);
};
// Used by the real-browser benchmark; this executes the same application paths.
window.edgeKB = { ingest, search, embed, open, api, logs, render, guard };
list().catch((e) => status(`数据库未就绪：${e.message}`));
