import { mkdir, writeFile } from "node:fs/promises";
const pairs = [
  [
    "gpu",
    "WebGPU accelerates neural network inference using the graphics processor. It allows parallel matrix multiplication in modern browsers.",
    "How can a browser use the graphics card for neural networks?",
  ],
  [
    "wasm",
    "WebAssembly is a portable binary instruction format. WASM runs embedding inference on the CPU when WebGPU is unavailable.",
    "What fallback runs inference without a graphics adapter?",
  ],
  [
    "int8",
    "INT8 quantization stores model weights in eight bit integers rather than thirty two bit floating point values. It reduces download size and memory consumption.",
    "How can we reduce neural network weight storage?",
  ],
  [
    "fp16",
    "Half precision floating point uses sixteen bits per value. FP16 often speeds up GPU arithmetic with less memory than FP32.",
    "What floating point precision uses sixteen bits?",
  ],
  [
    "rrf",
    "Reciprocal rank fusion combines ranked search lists using reciprocal position scores. RRF is performed by the database hybrid search engine.",
    "How are keyword and semantic rankings fused?",
  ],
  [
    "hnsw",
    "HNSW is a graph index for approximate nearest neighbor vector search. Its search parameter trades recall against query latency.",
    "Which graph structure accelerates nearest neighbor search?",
  ],
  [
    "bm25",
    "BM25 ranks documents by term frequency and inverse document frequency with document length normalization. It is a lexical retrieval method.",
    "Which lexical relevance algorithm normalizes document length?",
  ],
  [
    "cache",
    "Browser HTTP caching and persistent model caching avoid repeated model downloads. Warm requests reuse the loaded inference session.",
    "How can repeated model downloads be avoided?",
  ],
  [
    "batch",
    "Batch inference processes several texts in one model invocation. Padding very different sequence lengths can waste computation.",
    "How can we process multiple documents in one inference call?",
  ],
  [
    "refresh",
    "After inserting documents, refresh the vector and fulltext indexes before searching. Verify the newly imported documents are visible to both retrieval paths.",
    "Why might newly inserted text be missing from search?",
  ],
  [
    "cosine",
    "Cosine similarity measures the angle between vectors. Normalize embeddings to unit length for consistent semantic similarity comparisons.",
    "What similarity compares the direction of embeddings?",
  ],
  [
    "worker",
    "A Web Worker executes JavaScript away from the main UI thread. Moving embedding computation to a worker keeps the interface responsive.",
    "How can heavy model computation avoid freezing the interface?",
  ],
  [
    "privacy",
    "Local browser inference computes document and query embeddings on the user device. Raw documents and vectors are stored in the local seekdb database.",
    "Where does private document embedding computation happen?",
  ],
  [
    "recall",
    "Recall at K is the number of relevant documents in the top K results divided by the total number of relevant documents.",
    "How do we measure the fraction of relevant documents retrieved?",
  ],
  [
    "ndcg",
    "Normalized discounted cumulative gain rewards relevant documents ranked near the top. nDCG divides discounted gain by the ideal ranking gain.",
    "Which quality metric rewards relevant results at higher positions?",
  ],
  [
    "median",
    "The median is the middle value of sorted observations. Repeated latency measurements should report medians instead of the single fastest run.",
    "Which latency statistic is robust to a few slow outliers?",
  ],
  [
    "chunk",
    "Text chunking splits long documents into short passages. Overlap preserves context across adjacent passage boundaries.",
    "Why overlap adjacent text passages?",
  ],
  [
    "increment",
    "Incremental upsert updates existing document identifiers or inserts new ones. Content hashes make repeated imports idempotent.",
    "How can duplicate imports avoid creating duplicate records?",
  ],
  [
    "model",
    "MiniLM is a compact transformer sentence embedding model. The all MiniLM L6 v2 model produces 384 dimensional vectors and is best suited to English.",
    "How many dimensions does the selected sentence encoder output?",
  ],
  [
    "seekdb",
    "seekdb unifies vector search, fulltext retrieval and relational storage. Database hybrid search returns a fused ranking without client side merging.",
    "Which database stores text and vectors and fuses retrieval?",
  ],
  [
    "weather",
    "Rainfall is measured with a rain gauge. A weather station records precipitation, humidity and wind speed.",
    "Which instrument measures rainfall?",
  ],
  [
    "bread",
    "Bread dough rises because yeast ferments sugars and releases carbon dioxide. A warm environment supports fermentation.",
    "Why does yeast make dough rise?",
  ],
  [
    "ocean",
    "Ocean tides are caused mainly by the gravitational attraction of the Moon and the Sun. Coastal tide heights vary throughout the day.",
    "What causes coastal tides?",
  ],
  [
    "plants",
    "Photosynthesis converts light energy into chemical energy. Plants absorb carbon dioxide and release oxygen.",
    "How do plants convert sunlight into stored energy?",
  ],
];
await mkdir("public/fixtures", { recursive: true });
await writeFile(
  "public/fixtures/corpus.json",
  JSON.stringify(
    pairs.map(([id, text]) => ({ source: `${id}.txt`, text })),
    null,
    2,
  ),
);
await writeFile(
  "public/fixtures/queries.json",
  JSON.stringify(
    pairs.map(([id, , query]) => ({ query, relevant: [`${id}.txt`] })),
    null,
    2,
  ),
);
console.log(
  `${pairs.length} documents and queries written (synthetic topic sanity set, not a general benchmark)`,
);
