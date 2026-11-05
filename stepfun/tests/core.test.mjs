import { test } from "node:test";
import assert from "node:assert/strict";
import { chunks, metrics, vector, kbName } from "../config.mjs";
test("chunking preserves Unicode and overlapping coverage", () => {
  const text = "😀".repeat(1500);
  const out = chunks(text);
  assert.equal(out[0].length, 1400);
  assert.equal(out.length, 3);
  assert.equal(out[1], out[0]);
  assert.equal(out[2], "😀".repeat(300));
});
test("ranking quality respects order and relevant set", () => {
  assert.deepEqual(metrics(["a", "b"], ["a", "b"]), { recall: 1, ndcg: 1 });
  assert.equal(metrics(["x"], ["a"]).recall, 0);
  assert.ok(metrics(["x", "a"], ["a"]).ndcg < 1);
});
test("reject invalid namespace and embeddings before write", () => {
  assert.throws(() => kbName("../x"));
  assert.throws(() => vector(Array(384).fill(NaN)));
  assert.throws(() => vector(Array(384).fill(0)));
  assert.equal(kbName("personal_1"), "personal_1");
});
