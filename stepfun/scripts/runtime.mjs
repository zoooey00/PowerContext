import { mkdir, copyFile } from "node:fs/promises";
await mkdir("public/ort", { recursive: true });
for (const file of [
  "ort-wasm-simd-threaded.jsep.mjs",
  "ort-wasm-simd-threaded.jsep.wasm",
])
  await copyFile(
    `node_modules/onnxruntime-web/dist/${file}`,
    `public/ort/${file}`,
  );
