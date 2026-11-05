# 提交清单

**当前可以上传工程，但仍缺真实 Dify 导入与模型运行证据。完成下表待处理项后再进行最终提测。**

| 检查项 | 当前状态 | 文件或下一步 | 依据 |
| --- | --- | --- | --- |
| 继承比赛分支 | 已确认 | 源基点 d647275；发布时再次核对 ancestry | 题面开头 |
| 资产放 dify 目录 | 已确认 | 本目录全部文件 | 题面开头 |
| Dify DSL | 已确认文件存在，实际导入待处理 | grudge-shop.yml，唯一文件；check_dsl.py 只做静态检查 | 4.1 |
| Dify 核心编排 | 已实现，真实运行待处理 | Code / HTTP / LLM / Answer 节点 | 2.2、3.1 |
| 指定技术实际作用 | PowerContext 已实测 | backend-run.json + services.log，写入、读回、重启、状态变化 | 2.2、3.1 |
| 配置与启动说明 | 已交付 | README.md、bootstrap.py、requirements-lock.txt、run.py、.env.example | 4.2、4.4 |
| 初始数据 | 已确认不需要 | 自动创建空 Scope；独立存档名重置 | 4.4 |
| 模型与供应商插件 | 待处理 | 在 Dify 配置实际模型，记录官方插件的实际安装版本 | 4.2 |
| 完整样例与预期 | 已交付 | VALIDATION.md 样例 A | 4.3 |
| 完整样例实际结果 | 待处理 | 运行 verify_dify.py，审核后加入 dify-live.json 及截图 | 3.1、4.3 |
| 可体验应用入口 | 待处理 | 发布 Dify Web App，保存可访问地址 | 2.1、4.2 |
| 凭据 | 不入库 | .env 和 DIFY_APP_API_KEY 仅本机；DSL 使用 secret 占位值 | 4.2 |
| 语雀补充页面 | 待核实 | 本次读取失败；提交前检查主办方平台最新说明 | 题面参考链接 |
| GitHub 上传 | 以远端 commit 查询为准 | 提交后由聊天交付精确 commit hash | 用户请求 |
| 测评平台提交 | 待用户操作 | 截图中的 Branch / Commit id 表单 | 用户截图 |

## 表单对应

- 代码仓库地址：`https://github.com/zoooey00/PowerContext.git`（截图固定字段）。
- Branch：工程上传到 `2026-competition-ecosystem` 后填写这个分支。
- Commit id：必须填写最后一次完整交付对应的 **40 位真实远端 commit hash**，由上传完成的结果提供。不要填写官方依赖 c4b9b54 或比赛基点 d647275。

GitHub 上传成功不表示测评平台已提交；平台出现成功提示或提交记录后，才算完成提测。当前仓库经连接器返回为 public；如主办方仍要求私有仓库，需按比赛平台说明核实归属及可见性，未擅自改变仓库设置。

## 文件清单

- grudge-shop.yml：可导入的应用定义。
- README.md：创意、玩法、依赖、部署、网络、导入与已知限制。
- VALIDATION.md：完整人工验证步骤和可观察标准。
- server.py：规则和真实 PowerContext HTTP 网关。
- build_dsl.py / check_dsl.py：重建 DSL 与静态检查。
- bootstrap.py / requirements-lock.txt / .env.example / run.py：隔离安装及持久化启动。
- verify.py：独立后端验证；verify_dify.py：真实发布应用验证。
- evidence/backend-run.json / evidence/services.log：真实后端证据。
- LICENSE：原创新增代码许可。

没有自定义插件包、前端、Embedding / Rerank 服务或知识库导入文件。
