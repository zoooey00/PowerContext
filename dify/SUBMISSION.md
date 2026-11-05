# 提交清单

**源码与交付 DSL 已完成真实云端导入、模型调用、PowerContext 读写与三会话自测，并提供公开体验入口。最终脱敏云端 DSL 已重新导入和重新发布后复测。GitHub 上传和测评平台提测仍是两个独立状态。**

| 检查项 | 当前状态 | 文件或下一步 | 依据 |
| --- | --- | --- | --- |
| 继承比赛分支 | 已确认 | 源基点 d647275；发布时再次核对 ancestry | 题面开头 |
| 资产放 dify 目录 | 已确认 | 本目录全部文件 | 题面开头 |
| Dify DSL | 已确认实际导入与重新导入 | grudge-shop-cloud.yml；dify-reimport.json 返回 completed，无警告 | 4.1 |
| Dify 核心编排 | 已确认实际运行 | 9 个节点成功，dify-node-trace.json；正式发布版 dify-live.json | 2.2、3.1 |
| 指定技术实际作用 | PowerContext 已实测 | backend-run.json + services.log，写入、读回、重启、状态变化 | 2.2、3.1 |
| 配置与启动说明 | 已交付 | README.md、bootstrap.py、requirements-lock.txt、run.py、.env.example | 4.2、4.4 |
| 初始数据 | 已确认不需要 | 自动创建空 Scope；独立存档名重置 | 4.4 |
| 模型与供应商插件 | 已确认 | 官方 langgenius/deepseek 0.0.26、deepseek-flash；精确包标识在 DSL 中 | 4.2 |
| 完整样例与预期 | 已交付 | VALIDATION.md 样例 A | 4.3 |
| 完整样例实际结果 | 已确认 | dify-live.json：3 个独立 conversation_id；dify-web-run.json 与 3 张截图 | 3.1、4.3 |
| 可体验应用入口 | 已发布并匿名验证 | https://udify.app/chat/neneiRJSfXTqgv64；后端依赖本机临时隧道，长期在线待稳定部署 | 2.1、4.2 |
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

- grudge-shop-cloud.yml：最终官方云端导出 DSL 0.7.0，重新导入与复测通过；推荐使用。
- grudge-shop.dify：含同一 app.yaml 的官方格式导出包，与上述文件二选一。
- grudge-shop.yml：生成器重建的 DSL 0.4.0 版本，可选替代；曾在本次云端导入与运行，会提示版本差异。三个文件表示同一应用，不需要依次导入。
- README.md：创意、玩法、依赖、部署、网络、导入与已知限制。
- VALIDATION.md：完整人工验证步骤和可观察标准。
- server.py：规则和真实 PowerContext HTTP 网关。
- build_dsl.py / check_dsl.py：重建 DSL 与静态检查。
- package_cloud_export.py：校验官方包哈希、清除凭据并生成占位配置的云端交付文件。
- bootstrap.py / requirements-lock.txt / .env.example / run.py：隔离安装及持久化启动。
- verify.py：独立后端验证；verify_dify.py：真实发布应用验证。
- evidence/backend-run.json / evidence/services.log：真实后端证据。
- evidence/dify-live.json / dify-node-trace.json / dify-reimport.json：正式 API 结果、节点追踪与重新导入证据。
- evidence/dify-web-run.json / dify-web-1.png 至 dify-web-3.png：匿名网页三会话体验和截图。
- LICENSE：原创新增代码许可。

没有自定义插件包、前端、Embedding / Rerank 服务或知识库导入文件。
