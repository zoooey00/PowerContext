# 财报 PDF 全页证据检索

公共接口位于 `src/powercontext/sources/pdf_pages.py`，请求内检索索引位于 `src/powercontext/sources/_pdf_retrieval.py`。

## 解析和来源

输入必须是完整 PDF 字节。pypdf 严格打开文件，逐页校验内容流、Form 内容及压缩完整性，再提取正文。没有正文的物理页仍保留。函数完成全部物理页后才返回元组；任意页无法完整解析则抛出 `ValueError`。空密码权限文件可以读取，需要用户密码的文件被拒绝。

Source Definition 的名称为 `pdf-page`，版本为 `1`。每页为 CAPTURED Source，输入和读取结果均为 `PDFPageInput`。原始 PDF 的完整 SHA-256、原文档 ID 和从 1 开始的物理页号保存在页级输入与标准文本投影中。

Source name 由文档 ID 的 SHA-256、原始 PDF 的完整 SHA-256 和物理页号构成。极长页号使用整段身份摘要以保持名称不超过 256 字符。身份不依赖提取正文。修订改变原文件摘要，因此不同修订不会共用页级身份。

标准文本投影保持 `DOCUMENT_ID\nPAGE_TEXT`，metadata 仅含 `document_id`、`document_sha256`、`page_number`。检索归一化只作用于派生索引，不改变原始页正文。

## 检索路径

1. 从传入 scoped Memory 的公开 `list` 接口读取当前活动页快照，只接收单一 pdf-page Source 的真实记录。
2. 根据问题中明确出现的发行人和报告年份选择文档范围；无法从 ID 匹配发行人时保留普通检索行为。
3. 对当前页目录计算词频与页级 IDF，同时构造页内滑动段落。通用会计概念将指标问题映射到报表输入项，不计算答案。
4. 融合页级 BM25、段落检索、报表类别和公开 Memory 全文搜索信号。全文搜索的候选截断不会决定哪些已存储页面可以进入重排。
5. 为长表和跨页披露预留最多五分之一、上限四页的相邻页预算。相邻关系来自 Source 身份中的物理页号，严格限制在相同文档 ID 和 PDF 摘要内。
6. 通过公开 `get` 回查所选记录，返回同一快照内的原始精确 citation，按 Source 去重并遵守 limit。

索引每次请求建立，不跨 Runtime、scope 或修订缓存。实现不读取文件系统中的语料、答案、证据标注或判题资产，不调用模型或在线服务，也不写源码目录。

每个问题需要扫描一次当前 scoped Memory 的活动记录。内存和索引构建成本随当前 scope 的页数、文本量增长；不能把此策略的成本解释为与语料规模无关。

## 验证

使用 Python 3.12、官方固定依赖和 Linux x86_64，在仓库根目录运行：

```bash
PYTHONPATH="$PWD/src:$PWD/competition" python -m pytest -q -s \
  -c competition/pytest.ini --confcutdir=competition \
  tests/test_pdf_pages.py tests/test_retrieval_quality_signals.py \
  competition/challenges/source-03-pdf-retrieval/acceptance
```

本机单核、源码只读、2 GiB 虚拟内存上限环境实测：21 项通过。覆盖完整 503 页公开财报、真实持久化与重启、页序、空页、密码权限、原子失败、完整摘要、不同修订、精确引用、上限、scope 隔离、发行人区分、报告年份区分、超长身份、干扰页以及不重复查询词的表格续页。

独立构造的指标问题验证了 EPS、流动比率、ROE、现金转换周期、EBITDA、capex 所需报表页能够进入前 20 条引用。

另一次公开输入审计实测：完整解析 503 页约 13.19 秒，解析、入库及五个问题检索和回查共约 29.75 秒；每题检索约 0.63–0.80 秒，进程峰值 RSS 约 185 MiB。数值只描述本机该次运行，不是其他环境的性能保证。

公开资产不提供质量 gold。上述结果不等于正式 FinanceBench evidence-page Recall@20，也不证明留出组的词项召回和整页 F1 门槛；这些仍须正式评测验证。

改动文件的 Ruff 检查和格式检查已通过。全仓库 pre-commit 未完成：本地工作树采用稀疏检出，uv 无法解析未检出的 `integrations/langchain` 工作区包；这项检查不计入上述通过结果。
