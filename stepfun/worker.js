import { pipeline, env } from "@huggingface/transformers";
import { MODEL } from "./config.mjs";
env.allowRemoteModels = false;
env.allowLocalModels = true;
env.localModelPath = "/models/";
env.useBrowserCache = true;
env.backends.onnx.wasm.numThreads = 1;
env.backends.onnx.wasm.wasmPaths = new URL("/ort/", self.location.origin).href;
let extractor,
  key,
  actualBackend,
  gpuInfo,
  loadMs = 0,
  queue = Promise.resolve();
async function load(profile, forceWasm) {
  const next = `${profile}:${forceWasm}`;
  if (extractor && key === next) return;
  if (extractor) {
    await extractor.dispose();
    extractor = null;
  }
  const start = performance.now();
  const options = {
    dtype: profile,
    progress_callback: (p) => postMessage({ progress: p }),
  };
  let reason = "";
  if (!forceWasm && profile !== "q8" && navigator.gpu) {
    try {
      const adapter = await navigator.gpu.requestAdapter();
      if (!adapter) throw new Error("无可用 GPU adapter");
      gpuInfo = adapter.info
        ? {
            vendor: adapter.info.vendor,
            architecture: adapter.info.architecture,
            device: adapter.info.device,
            description: adapter.info.description,
          }
        : null;
      extractor = await pipeline("feature-extraction", MODEL, {
        ...options,
        device: "webgpu",
      });
      // Test an actual dispatch, not just navigator.gpu presence.
      await extractor(["warmup"], { pooling: "mean", normalize: true });
      actualBackend = "webgpu";
    } catch (e) {
      reason = e.message;
      if (extractor) await extractor.dispose();
      extractor = null;
    }
  } else
    reason = forceWasm
      ? "用户/评测强制 WASM"
      : profile === "q8"
        ? "INT8 使用经质量验证的 WASM；GPU 请选 FP16"
        : "浏览器不支持 WebGPU";
  if (!extractor) {
    extractor = await pipeline("feature-extraction", MODEL, {
      ...options,
      device: "wasm",
    });
    actualBackend = "wasm";
    await extractor(["warmup"], { pooling: "mean", normalize: true });
  }
  loadMs = performance.now() - start;
  key = next;
  postMessage({ backend: actualBackend, reason, loadMs, profile });
}
async function handle({ id, texts, profile, forceWasm, batchSize = 8 }) {
  try {
    const reused = !!extractor && key === `${profile}:${forceWasm}`;
    const resourceStart = performance.getEntriesByType("resource").length;
    await load(profile, forceWasm);
    const start = performance.now(),
      vectors = [];
    const modelTransfers = performance
      .getEntriesByType("resource")
      .slice(resourceStart)
      .filter((r) => r.name.includes("/models/"))
      .map((r) => ({
        url: r.name,
        startMs: r.startTime,
        endMs: r.responseEnd,
        durationMs: r.duration,
        bytes: r.encodedBodySize,
      }));
    for (let i = 0; i < texts.length; i += batchSize) {
      const result = await extractor(texts.slice(i, i + batchSize), {
        pooling: "mean",
        normalize: true,
      });
      vectors.push(...result.tolist());
      postMessage({
        completed: Math.min(i + batchSize, texts.length),
        total: texts.length,
      });
    }
    postMessage({
      id,
      vectors,
      embedMs: performance.now() - start,
      backend: actualBackend,
      gpuInfo,
      modelTransfers,
      loadMs: reused ? 0 : loadMs,
      sessionLoadMs: loadMs,
    });
  } catch (e) {
    postMessage({ id, error: e.message });
  }
}
self.onmessage = (e) => {
  queue = queue.then(() => handle(e.data));
};
