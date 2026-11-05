export const MODEL = "Xenova/all-MiniLM-L6-v2";
// Resolved by scripts/models.mjs; never silently follow a moving model revision.
export const DIMENSION = 384;
export const CHUNK_SIZE = 700;
export function chunks(text, size = CHUNK_SIZE) {
  const chars = Array.from(text.trim());
  const result = [];
  for (let i = 0; i < chars.length; i += size - 100)
    result.push(chars.slice(i, i + size).join(""));
  return result;
}
export function vector(v) {
  if (
    !Array.isArray(v) ||
    v.length !== DIMENSION ||
    !v.every(Number.isFinite) ||
    !v.some((x) => x !== 0)
  )
    throw new Error("需要浏览器生成的非零 384 维有限向量");
  return v;
}
export function kbName(name) {
  if (typeof name !== "string" || !/^[a-z][a-z0-9_]{0,39}$/.test(name))
    throw new Error(
      "知识库名称须以小写字母开头，最多 40 位小写字母、数字或下划线",
    );
  return name;
}
export function metrics(ids, relevant, k = 5) {
  const ranked = ids.slice(0, k),
    rel = new Set(relevant);
  const dcg = ranked.reduce(
    (s, id, i) => s + (rel.has(id) ? 1 / Math.log2(i + 2) : 0),
    0,
  );
  const ideal = Array.from(
    { length: Math.min(k, rel.size) },
    (_, i) => 1 / Math.log2(i + 2),
  ).reduce((a, b) => a + b, 0);
  return {
    recall: ranked.filter((id) => rel.has(id)).length / rel.size,
    ndcg: ideal ? dcg / ideal : 0,
  };
}
