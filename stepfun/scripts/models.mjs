import { mkdir, writeFile, readFile, rename } from "node:fs/promises";
import { createHash } from "node:crypto";
import { MODEL } from "../config.mjs";
const root = `models/${MODEL}`;
const endpoint = process.env.HF_ENDPOINT || "https://huggingface.co";
await mkdir(`${root}/onnx`, { recursive: true });
let revision, locked;
try {
  locked = JSON.parse(await readFile("evidence/model-manifest.json", "utf8"));
  revision = locked.revision;
} catch {
  const r = await fetch(`${endpoint}/api/models/${MODEL}`);
  if (!r.ok) throw new Error(`HF ${r.status}`);
  revision = (await r.json()).sha;
}
const files = [
  "config.json",
  "tokenizer.json",
  "tokenizer_config.json",
  "special_tokens_map.json",
  "onnx/model.onnx",
  "onnx/model_quantized.onnx",
  "onnx/model_fp16.onnx",
];
const records = [];
for (const file of files) {
  let bytes;
  try {
    bytes = await readFile(`${root}/${file}`);
  } catch {
    console.log(`Downloading ${file}`);
    const r = await fetch(`${endpoint}/${MODEL}/resolve/${revision}/${file}`);
    if (!r.ok) throw new Error(`${file}: ${r.status}`);
    bytes = Buffer.from(await r.arrayBuffer());
    await writeFile(`${root}/${file}.part`, bytes);
    await rename(`${root}/${file}.part`, `${root}/${file}`);
  }
  const record = {
    file,
    bytes: bytes.length,
    sha256: createHash("sha256").update(bytes).digest("hex"),
  };
  const expected = locked?.files.find((r) => r.file === file);
  if (
    expected &&
    (expected.bytes !== record.bytes || expected.sha256 !== record.sha256)
  )
    throw new Error(`校验失败: ${file}`);
  records.push(record);
}
const fp32 = records.find((r) => r.file === "onnx/model.onnx").bytes,
  q8 = records.find((r) => r.file === "onnx/model_quantized.onnx").bytes;
const fp16 = records.find((r) => r.file === "onnx/model_fp16.onnx").bytes;
const manifest = {
  model: MODEL,
  revision,
  files: records,
  fp32Bytes: fp32,
  q8Bytes: q8,
  fp16Bytes: fp16,
  compressionRatio: fp32 / q8,
  fp16CompressionRatio: fp32 / fp16,
  scope: "ONNX weights; shared tokenizer/config excluded from all",
};
await writeFile("models/manifest.json", JSON.stringify(manifest, null, 2));
await mkdir("evidence", { recursive: true });
await writeFile(
  "evidence/model-manifest.json",
  JSON.stringify(manifest, null, 2),
);
console.log(manifest);
