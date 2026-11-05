# 端知 · 一页技术说明

**模型与量化**：Xenova/all-MiniLM-L6-v2，revision 751bff37182d3f1213fa05d7196b954e230abad9，Apache-2.0，英文、384 维、mean pooling + L2 归一化。采用发布者的 FP16 浮点转换与 INT8 动态量化 ONNX 文件；未训练模型。FP32 90387606 B，FP16 45297825 B（2.00 倍），INT8 22972370 B（3.93 倍）。同口径统计实际 ONNX 文件，公共 tokenizer/config 不计，逐文件 SHA-256 见 model-manifest.json。

**端侧执行**：Transformers.js 3.8.1 / ONNX Runtime Web。默认 FP16 显式 device=webgpu，先 requestAdapter 再运行真实预热；失败自动 device=wasm。界面显示后端与原因；INT8 选择 WASM。模型、运行时均由本机提供，Worker 执行文档与查询推理；seekdb SDK 关闭自动 embedding。Chrome 156.0.8078.80，GPU Intel gen-12lp；Edge 禁用 GPU 后的自动降级及完整检索见 ui-smoke.json。浏览器外部网络请求 0 次。

**seekdb 与状态**：seekdb-js 1.4.0 + 嵌入式 seekdb-v1.4.0.0。独立 edge_<name>_<precision> 集合；cosine HNSW(384)、IK smart 全文索引，保存 id/embedding/document/source/model/precision。浏览器 700 字符切片、重叠 100，内容哈希 upsert；每 64 片写入，整次结束刷新并探测向量与全文可见性。hybridSearch 在数据库中取两路各 50 候选，以 RRF(k=60) 排序取前 5，客户端不融合。任务中锁定配置，切换清空结果，数据库会话操作串行。

**测试条件与计时**：Windows 11 Home China，12th Gen Intel(R) Core(TM) i5-12500H，内存 15.73 GiB；24 篇自编英文主题文档、24 条单相关标注查询，非通用基准。每组导入 3 次、查询 72 次取中位数；质量为均值。加载含本机 HTTP/缓存、初始化及一次预热；冷模型传输逐请求记录于 modelTransfers。E2E 从提交至 JSON 可展示（不含下一帧绘制）；下载、向量化、写入、刷新含可见性探测、查询各阶段原始值均留存。

**优化与质量结论**：量化减小文件，模型复用避免重复初始化；保留 batch=1/8 对照，默认 B1。INT8 WebGPU 在本机纯向量质量异常，已从应用禁用，原始失败实验单独保留，GPU 采用 FP16。对比同一模型、后端的 B1/B8 才归因批处理；不同精度与后端组合不能归因单项优化。增量、重复导入、集合隔离在全部配置通过；浏览器界面测试另附。小测试集不能外推开放域质量。

|配置|模型 MiB|片段/s|DB ms|E2E ms|混合 R@5/nDCG|向量 R@5/nDCG|
|---|---|---|---|---|---|---|
|FP32 / WASM / B1|86.20|15.13|10.64|56.65|0.96/0.87|1.00/0.96|
|FP16 / WebGPU / B1|43.20|40.86|10.75|52.30|0.96/0.87|1.00/0.96|
|FP16 / WASM / B1|43.20|16.18|7.06|46.10|0.96/0.87|1.00/0.96|
|INT8 / WASM / B8|21.91|54.37|5.32|24.00|0.96/0.89|1.00/0.98|
|INT8 / WASM / B1|21.91|57.17|5.32|24.25|0.96/0.87|1.00/0.95|

复现：README.md；原始日志：evidence/benchmark-raw.json；源码：worker.js / server.mjs。
