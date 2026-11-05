# 端知 Edge Knowledge — seekdb × 阶跃星辰

浏览器 Web Worker 使用 Transformers.js 对文档与查询执行本地 embedding，Node 仅代理 seekdb 的数据写入、索引刷新及检索。无云端推理服务，也不在服务端计算向量。界面显示实际推理后端，支持 TXT / Markdown / 粘贴文本、增量导入、幂等写入和多知识库。

## 本地启动

需要 Node.js 22 或 24、Chrome / Edge 最新版、约 1 GB 可用磁盘。首次启动需要网络获取依赖、模型及 seekdb 官方原生引擎；后续推理和检索在本机进行。嵌入式 SDK 支持 Windows x64、Linux x64 / arm64、macOS arm64。

```sh
cd stepfun
npm ci
node scripts/models.mjs
npm run build
npm start
```

打开 http://127.0.0.1:5173 。第一次打开知识库时会加载 seekdb 原生引擎。默认嵌入式数据目录 `stepfun/seekdb-data`，持久化保存原文、向量与元数据；不要同时启动两个进程访问相同目录。

**Windows 中文路径**：实测原生引擎不支持含中文的数据库路径。如工程位于中文用户目录，启动前在 PowerShell 设置 `$env:SEEKDB_PATH='C:\Users\Public\stepfun-seekdb-data'`，或改为自己有写权限的英文绝对路径。应用源码和模型文件可以放在中文路径。此设置只改变数据库文件位置。

如 Hugging Face 直连不可达，可在 PowerShell 执行 `$env:HF_ENDPOINT='https://hf-mirror.com'`，再运行模型脚本。版本与逐文件哈希固定在 `evidence/model-manifest.json`，镜像下载后仍须通过相同哈希检查。大文件慢速连接可使用 `scripts/download.py URL 输出路径 精确字节数` 分块续传（需 Python 与 curl）；最终仍运行模型脚本校验。

1. 点击“打开 / 创建知识库”。
2. 导入示例或选择 TXT / MD，点击“向量化并导入”。等待“索引刷新完成”。
3. 输入 `How can a browser use the graphics card for neural networks?`，观察排序与对应原文。
4. 再导入新文件检索新增内容；重复导入相同文件应不增加片段数。
5. 新建另一个知识库，确认没有先前集合的结果，再从已有集合下拉框切回。
6. 勾选“强制 WASM”验证降级流程；取消后会先尝试真实 WebGPU 调度，失败自动 WASM 并显示原因。

开发模式 `npm run dev`。所有资源均由本机服务提供，无 CDN 字体或外部推理接口。MiniLM 为英文模型，示例与质量评测采用英文；中文输入可运行，但不承诺中文语义检索质量。

## 数据库配置

默认使用已实测的嵌入式 seekdb，不需要 Docker。API `/api/health` 返回实际引擎版本。如果已有本地 seekdb server，可设置 `SEEKDB_HOST=127.0.0.1`、`SEEKDB_PORT=2881`、`SEEKDB_USER=root`、`SEEKDB_PASSWORD=`；数据库为 `test`，需要支持 `dbms_index_manager.refresh()` 与 `DBMS_HYBRID_SEARCH`。提交日志来自嵌入式模式，未对独立 server 模式作实测声明。

## 结构与检索契约

每个知识库和精度独立集合 `edge_<name>_<fp32|fp16|q8>`。384 维 cosine HNSW，IK smart 全文索引。SDK 管理表结构及 `_id`、`document`、`embedding`、`metadata` 字段。元数据保存 source / model / precision。700 Unicode 字符切片，100 字符重叠；超长文本在浏览器切分。按 `SHA256(source + NUL + chunk)` upsert；同名文件内容改变会新增片段，原有片段不会自动删除，这是追加知识库而非目录镜像。

每 64 片浏览器向量化后上传，整次导入结束统一调用 `CALL dbms_index_manager.refresh()`；随后分别探测新增来源的向量和全文可见性，失败不会提示已完成，可点击重试。请求携带明确集合名与精度；UI 在任务执行期间锁定配置，切换清空旧结果。API 的数据库操作串行，避免 SDK `hybridSearch()` 内部会话变量在并发请求中交叉污染。

混合检索调用 `collection.hybridSearch({query,knn,rank:{rrf:...}})`，两路候选均为 50，RRF 常数 60，Top K=5。SDK 调用数据库 `DBMS_HYBRID_SEARCH`，数据库生成并执行融合查询。应用只展示返回顺序，不在客户端合并。`getCollection(...,embeddingFunction:null)` 和 schema 的显式 `null` 禁用自动向量化；写入与查询必须提交浏览器非零 384 维向量。

`sql-guard.mjs` 修复 seekdb 1.4.0 SQL 校验器把字符串里的普通词 `call` / `update` 误判为 SQL 指令的问题：在校验副本中屏蔽字面量及普通注释，保留原 SDK 的 SELECT、危险关键字和多语句检查，实际执行数据库返回的原 SQL。可执行注释及未闭合字面量直接拒绝，回归测试覆盖正常词与危险结构。

默认 FP16 优先 WebGPU，自动降级 WASM；INT8 固定 WASM。Intel gen-12lp 上 INT8 WebGPU 的纯向量 Recall@5 仅 0.1667，已禁用该组合，异常记录见 `evidence/int8-webgpu-investigation.json`。FP16 WebGPU 和 FP16 WASM 与 FP32 在本测试集质量一致。批大小 1 / 8 可配置；本机 INT8 B1 比 B8 略快，默认采用 B1，不声称批处理一定加速。

## 复现验证

```sh
npm test
npm run build
# 在另一个终端保持 npm start 运行
npm run bench
node scripts/ui-smoke.mjs
node scripts/report.mjs
```

默认使用已安装 Chrome；Edge 使用环境变量 `BROWSER_CHANNEL=msedge`。脚本通过 Playwright 启动真实浏览器、调用相同 Worker 与 API，不能替代为 Node embedding。每组导入重复 3 次，24 查询重复 3 次，保留所有查询顺序、结果和计时；另测纯向量质量，避免全文掩盖量化损失。检查重复导入、增量索引可见性及空知识库隔离。运行会创建 `bench_*` / `empty_*` 集合。原始数据保存至 `evidence/benchmark-raw.json`，摘要使用中位数，不选择最快一次。

评测集 `public/fixtures/` 为自编的 24 个主题、每主题一个相关文档；Recall@5 与二值 nDCG@5 只是功能质量冒烟测试，不代表开放域质量。`node scripts/fixtures.mjs` 可重建。下载与运行时加载是两个不同阶段：模型脚本负责首次外网下载；浏览器加载计时含本机 HTTP / 缓存读取、ONNX 初始化及一次预热。后续文档和查询向量化单独计时；端到端查询从提交开始至 JSON 结果可用于展示，含本地加载（若需要）、向量化、HTTP 和数据库时间，不含屏幕下一帧绘制。

## 文件入口

- `TECHNICAL.pdf`：一页技术说明（同时提供 Markdown / HTML 源文件）。
- `evidence/`：真实模型清单、运行环境、逐次性能与质量日志、页面截图。
- `worker.js`：唯一 embedding 执行位置。
- `server.mjs`：seekdb 存储与检索。
- `scripts/bench.mjs`：真实浏览器复现实验。

项目代码采用 MIT，模型来自 [Xenova/all-MiniLM-L6-v2](https://huggingface.co/Xenova/all-MiniLM-L6-v2)，遵循其 Apache-2.0 许可证。使用发布者提供的 ONNX Runtime INT8 动态量化权重 `model_quantized.onnx` 和 FP16 转换权重 `model_fp16.onnx`，不宣称自行训练或量化。精度分别为 `q8` / `fp16`；FP32 对照使用同一 revision 的 `model.onnx`。依赖锁定于 package-lock.json。
