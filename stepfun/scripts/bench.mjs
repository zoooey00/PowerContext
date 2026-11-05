import { chromium } from "playwright";
import { writeFile, mkdir } from "node:fs/promises";
import os from "node:os";
import { metrics } from "../config.mjs";
await mkdir("evidence", { recursive: true });
const browser = await chromium.launch({
  channel: process.env.BROWSER_CHANNEL || "chrome",
  headless: true,
  args: ["--enable-unsafe-webgpu"],
});
const page = await browser.newPage();
const externalRequests = [];
await page.route("**/*", (route) => {
  const u = new URL(route.request().url());
  if (!["127.0.0.1", "localhost"].includes(u.hostname)) {
    externalRequests.push(u.origin);
    return route.abort();
  }
  return route.continue();
});
page.on("console", (m) => console.log("browser", m.type(), m.text()));
page.on("pageerror", (e) => console.error(e));
await page.goto("http://127.0.0.1:5173");
await page.waitForFunction(() => window.edgeKB);
const corpus = await page.evaluate(() =>
  fetch("/fixtures/corpus.json").then((r) => r.json()),
);
const queries = await page.evaluate(() =>
  fetch("/fixtures/queries.json").then((r) => r.json()),
);
const output = {
  time: new Date().toISOString(),
  browser: browser.version(),
  os: os.version(),
  cpu: os.cpus()[0].model,
  memoryBytes: os.totalmem(),
  externalRequests,
  corpusSize: corpus.length,
  queries: queries.length,
  model: await page.evaluate(() =>
    fetch("/api/model-manifest").then((r) => r.json()),
  ),
  database: await page.evaluate(() => window.edgeKB.api("health")),
  runs: [],
};
try {
  for (const [profile, forceWasm, batchSize, label] of [
    ["fp32", true, 1, "baseline"],
    ["fp16", false, 1, "fp16-webgpu"],
    ["fp16", true, 1, "fp16-wasm"],
    ["q8", true, 8, "int8-wasm"],
    ["q8", true, 1, "int8-wasm-batch1"],
  ]) {
    const c = { name: `bench_${Date.now()}`, profile, forceWasm, batchSize };
    const run = { label, config: c, imports: [], queries: [], quality: [] };
    output.runs.push(run);
    const cold = await page.evaluate(
      async (c) => window.edgeKB.embed(["warmup"], c),
      c,
    );
    run.backend = cold.backend;
    run.gpuInfo = cold.gpuInfo;
    run.modelTransfers = cold.modelTransfers;
    run.loadMs = cold.loadMs;
    console.log(label, "model ready", cold.backend, cold.loadMs);
    if (!forceWasm && cold.backend !== "webgpu") run.webgpuUnavailable = true;
    for (let repeat = 0; repeat < 3; repeat++) {
      const imported = await page.evaluate(
        async ({ corpus, c }) => (await window.edgeKB.ingest(corpus, c)).record,
        { corpus, c },
      );
      run.imports.push(imported);
      for (const q of queries) {
        const d = await page.evaluate(
          async ({ text, c }) => window.edgeKB.search(text, c, "hybrid"),
          { text: q.query, c },
        );
        const sources = d.result.metadatas[0].map((m) => m.source);
        run.queries.push(d.record);
        run.quality.push({
          query: q.query,
          repeat,
          sources,
          ...metrics(sources, q.relevant),
        });
      }
    }
    // Separate vector-only quality prevents lexical retrieval from concealing quantization loss.
    run.vectorQuality = [];
    for (const q of queries) {
      const d = await page.evaluate(
        ({ text, c }) => window.edgeKB.search(text, c, "vector"),
        { text: q.query, c },
      );
      const sources = d.result.metadatas[0].map((m) => m.source);
      run.vectorQuality.push({
        query: q.query,
        sources,
        ...metrics(sources, q.relevant),
      });
    }
    // Incremental visibility, repeated-import count and collection isolation are real DB assertions.
    const before = await page.evaluate((c) => window.edgeKB.open(c), c);
    if (before.count !== corpus.length)
      throw new Error("Repeated import produced duplicates");
    const extra = {
      source: "increment-check.txt",
      text: "Zephyrquartz special incremental visibility check for the newly imported document.",
    };
    await page.evaluate(({ extra, c }) => window.edgeKB.ingest([extra], c), {
      extra,
      c,
    });
    const d = await page.evaluate(
      (c) =>
        window.edgeKB.search("Zephyrquartz special incremental visibility", c),
      c,
    );
    if (!d.result.metadatas[0].some((m) => m.source === extra.source))
      throw new Error("Incremental result not visible");
    const empty = { ...c, name: `empty_${Date.now()}` };
    await page.evaluate((c) => window.edgeKB.open(c), empty);
    const isolated = await page.evaluate(
      (c) => window.edgeKB.search("Zephyrquartz", c),
      empty,
    );
    if (isolated.result.ids[0].length)
      throw new Error("Collection state leaked");
    run.stateChecks = "passed";
    console.log(label, "completed");
    await writeFile(
      "evidence/benchmark-raw.json",
      JSON.stringify(output, null, 2),
    );
  }
} catch (e) {
  output.error = e.stack;
  throw e;
} finally {
  await writeFile(
    "evidence/benchmark-raw.json",
    JSON.stringify(output, null, 2),
  );
  await page.screenshot({ path: "evidence/app.png", fullPage: true });
  await browser.close();
}
const median = (arr) => {
  const a = [...arr].sort((a, b) => a - b);
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
};
output.summary = output.runs.map((r) => ({
  label: r.label,
  backend: r.backend,
  loadMs: r.loadMs,
  embedDocsPerSecond: median(
    r.imports.map((x) => x.chunks / (x.embedMs / 1000)),
  ),
  writeMs: median(r.imports.map((x) => x.writeMs)),
  refreshMs: median(r.imports.map((x) => x.refreshMs)),
  queryEmbedMs: median(r.queries.map((x) => x.embedMs)),
  searchMs: median(r.queries.map((x) => x.searchMs)),
  e2eMs: median(r.queries.map((x) => x.totalMs)),
  recall5: r.quality.reduce((a, x) => a + x.recall, 0) / r.quality.length,
  ndcg5: r.quality.reduce((a, x) => a + x.ndcg, 0) / r.quality.length,
  vectorRecall5:
    r.vectorQuality.reduce((a, x) => a + x.recall, 0) / r.vectorQuality.length,
  vectorNdcg5:
    r.vectorQuality.reduce((a, x) => a + x.ndcg, 0) / r.vectorQuality.length,
}));
await writeFile("evidence/benchmark-raw.json", JSON.stringify(output, null, 2));
console.table(output.summary);
