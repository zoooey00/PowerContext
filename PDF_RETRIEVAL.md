# 财报 PDF 全文解析与证据页检索

实现位置：`src/powercontext/sources/pdf_pages.py`。

`parse_pdf_document` 接收完整 PDF 字节，使用 pypdf 逐物理页提取正文，包含空白页。函数先完成所有页面的提取，再返回元组；加密文件仅尝试空密码，无法读取、缺页或内容流损坏时统一抛出 `ValueError`。文档摘要按全部原始字节计算 SHA-256。

`PDF_PAGE_SOURCE_DEFINITION` 的名称为 `pdf-page`，版本为 `1`。Source 保存页级输入，身份由文档 ID、完整摘要与物理页码的规范 JSON 编码生成 SHA-256，名称长度固定。正文不参与身份计算，PDF 字节变化则生成不同修订的身份。标准文本投影包含文档 ID、页面正文和三个约定的元数据字段。

`search_pdf_pages` 仅调用传入 scoped Memory 的公开 `search`、`get` 接口。检索使用离线财务术语扩展、多路全文搜索、BM25 重排与报表标题权重；显式提及发行人时对匹配的报告优先限定。候选引用保留原始 Memory 修订、entry ID 和 entry version ID，经回查并按页级 Source 去重后返回。实现不读取本地文件、标签、答案、证据清单或外部服务，不写入源码目录。

## 验证

使用官方 Linux x86_64、Python 3.12 和 `competition/requirements.txt` 固定依赖环境。在仓库根目录执行：

```bash
PYTHONPATH="$PWD/src:$PWD/competition" python -m pytest -q -s \
  -c competition/pytest.ini --confcutdir=competition \
  tests/test_pdf_pages.py \
  competition/challenges/source-03-pdf-retrieval/acceptance
```

回归测试涵盖页序、正文与数字、空页、完整摘要、修订身份、损坏内容流的原子失败、空密码权限、密码保护、文档 ID、真实入库与重启、多文档检索、不同页、上限和 scope 隔离。

检索回归还包含三十张干扰页：正文中多个实际章节共页时仍保留披露标题权重，经营区域页也能在没有照抄问句关键词的情况下被检索。通用财务词汇与章节标题的权重高于问句修饰词，年份仅作为弱排序信号。

公开验收验证完整 503 页财报及五个原始问题的引用行为。公开资产没有质量 gold，测试通过不证明完整评测的词项质量和证据页 Recall@20 门槛；这些指标由测评平台验证。
