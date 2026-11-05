import express from "express";
import {
  SeekdbClient,
  Schema,
  VectorIndexConfig,
  FulltextIndexConfig,
} from "seekdb";
import { performance } from "node:perf_hooks";
import { kbName, vector, MODEL } from "./config.mjs";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { guardCollection } from "./sql-guard.mjs";
const app = express();
app.use(express.json({ limit: "16mb" }));
// Bind only to loopback. No credentials or inference runtime are sent to the browser.
app.use((req, res, next) => {
  if (
    req.headers.origin &&
    !["http://127.0.0.1:5173", "http://localhost:5173"].includes(
      req.headers.origin,
    )
  )
    return res.status(403).json({ error: "Origin rejected" });
  next();
});
const client = new SeekdbClient(
  process.env.SEEKDB_HOST
    ? {
        host: process.env.SEEKDB_HOST,
        port: Number(process.env.SEEKDB_PORT || 2881),
        user: process.env.SEEKDB_USER || "root",
        password: process.env.SEEKDB_PASSWORD || "",
        database: "test",
      }
    : {
        path: resolve(process.env.SEEKDB_PATH || "./seekdb-data"),
        database: "test",
      },
);
// SDK hybridSearch uses session variables. Serialize all DB work on its connection.
let tail = Promise.resolve();
function serial(fn) {
  const p = tail.then(fn);
  tail = p.catch(() => {});
  return p;
}
const route = (method, path, fn) =>
  app[method](path, async (req, res, next) => {
    try {
      res.json(await serial(() => fn(req)));
    } catch (e) {
      next(e);
    }
  });
const profiles = new Set(["fp32", "fp16", "q8"]);
function collectionName(req) {
  const p = req.params.profile;
  if (!profiles.has(p)) throw new Error("Unknown precision");
  return `edge_${kbName(req.params.name)}_${p}`;
}
async function collection(req) {
  return guardCollection(
    await client.getCollection({
      name: collectionName(req),
      embeddingFunction: null,
    }),
  );
}
route("get", "/api/health", async () => ({
  version: await client.execute("SELECT VERSION() AS version"),
  model: MODEL,
}));
route("get", "/api/kbs", async () => ({
  collections: (
    await client.listCollections({ withEmbeddingFunction: false })
  ).map((c) => ({ name: c.name })),
}));
route("post", "/api/kbs/:name/:profile", async (req) => {
  const name = collectionName(req);
  const existing = await client.hasCollection(name);
  if (!existing)
    await client.createCollection({
      name,
      schema: new Schema({
        vectorIndex: new VectorIndexConfig({
          hnsw: { dimension: 384, distance: "cosine" },
          embeddingFunction: null,
        }),
        fulltextIndex: new FulltextIndexConfig("ik", { ik_mode: "smart" }),
      }),
      metadata: { model: MODEL, precision: req.params.profile },
    });
  return { name, count: await (await collection(req)).count() };
});
route("get", "/api/kbs/:name/:profile", async (req) => ({
  count: await (await collection(req)).count(),
}));
route("post", "/api/kbs/:name/:profile/import", async (req) => {
  const rows = req.body.rows;
  if (!Array.isArray(rows) || !rows.length || rows.length > 128)
    throw new Error("每批需要 1–128 个片段");
  for (const r of rows) {
    if (
      typeof r.id !== "string" ||
      !/^[a-f0-9]{64}$/.test(r.id) ||
      typeof r.text !== "string" ||
      !r.text.trim() ||
      r.text.length > 4000 ||
      typeof r.source !== "string" ||
      r.source.length > 300
    )
      throw new Error("Invalid document");
    vector(r.embedding);
  }
  const c = await collection(req),
    t = performance.now();
  await c.upsert({
    ids: rows.map((r) => r.id),
    documents: rows.map((r) => r.text),
    embeddings: rows.map((r) => r.embedding),
    metadatas: rows.map((r) => ({
      source: r.source,
      model: MODEL,
      precision: req.params.profile,
    })),
  });
  const writeMs = performance.now() - t;
  return { writeMs, count: await c.count() };
});
route("post", "/api/kbs/:name/:profile/refresh", async (req) => {
  const c = await collection(req),
    t = performance.now();
  // Explicit call: do not use SDK best-effort version detection which can silently no-op.
  await client.execute("CALL dbms_index_manager.refresh();");
  const probes = req.body.probes;
  if (!Array.isArray(probes) || !probes.length || probes.length > 128)
    throw new Error("Missing visibility probes");
  for (const p of probes) {
    vector(p.embedding);
    const found = await c.query({
      queryEmbeddings: [p.embedding],
      where: { source: p.source },
      nResults: 5,
      include: ["documents"],
    });
    if (!found.ids[0]?.includes(p.id))
      throw new Error("新增片段向量索引尚未可见，请重试刷新");
    const ft = await c.hybridSearch({
      query: {
        whereDocument: { $contains: p.keyword },
        where: { source: p.source },
        nResults: 1,
      },
      nResults: 1,
      include: ["documents"],
    });
    if (!ft.ids[0]?.length)
      throw new Error(
        `全文索引尚未可见：${p.source} / ${p.keyword}，请重试刷新`,
      );
  }
  return { refreshMs: performance.now() - t, count: await c.count() };
});
route("post", "/api/kbs/:name/:profile/search", async (req) => {
  const { text, embedding, mode = "hybrid", k = 5 } = req.body;
  if (
    typeof text !== "string" ||
    !text.trim() ||
    text.length > 2000 ||
    !Number.isInteger(k) ||
    k < 1 ||
    k > 50
  )
    throw new Error("Invalid query");
  vector(embedding);
  const c = await collection(req),
    t = performance.now();
  const result =
    mode === "vector"
      ? await c.query({
          queryEmbeddings: [embedding],
          nResults: k,
          include: ["documents", "metadatas"],
        })
      : await c.hybridSearch({
          query: { whereDocument: { $contains: text }, nResults: 50 },
          knn: { queryEmbeddings: [embedding], nResults: 50 },
          rank: { rrf: { rankConstant: 60, rankWindowSize: 50 } },
          nResults: k,
          include: ["documents", "metadatas"],
        });
  return { result, searchMs: performance.now() - t };
});
app.get("/api/model-manifest", async (req, res, next) => {
  try {
    res.json(JSON.parse(await readFile("models/manifest.json", "utf8")));
  } catch (e) {
    next(new Error("请先运行 node scripts/models.mjs"));
  }
});
app.use("/models", express.static("models", { immutable: true, maxAge: "1y" }));
if (process.argv.includes("--production")) app.use(express.static("dist"));
else {
  const { createServer } = await import("vite");
  const vite = await createServer({
    server: { middlewareMode: true },
    appType: "spa",
  });
  app.use(vite.middlewares);
}
app.use((e, req, res, next) => {
  console.error(e.message);
  res.status(400).json({ error: e.message });
});
app.listen(5173, "127.0.0.1", () =>
  console.log("Edge KB http://127.0.0.1:5173"),
);
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, async () => {
    await tail;
    await client.close();
    process.exit();
  });
