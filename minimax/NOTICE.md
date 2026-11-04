# 来源与修改记录

仓库目录基于 oceanbase/powercontext 的比赛生态分支 `d647275c308e09b7b623f322a26f5c4e85734fb0`，保留其他赛道空目录。

本作品新增：minimax/ 下的工单业务示例、规格条目、上下文检索 CLI、测试、状态和模型 HTTP 适配、复现脚本与文档。业务代码的目标改动限定为 status 筛选；MiniMax 的实际生成结果以 evidence/live/minimax-generation.json、change.patch 和 fixtures/after/tickets.py 为准。

运行依赖：PowerContext（OceanBase，Apache-2.0，源码固定提交见 README）；seekdb（OceanBase，Apache-2.0，独立服务）；PyMySQL（MIT，版本见 requirements.txt）；MiniMax API（独立在线服务，按供应商条款使用）。本仓库没有复制完整第三方依赖源码；依赖安装后的许可保留在各自分发包内。

API 使用依据：

- https://github.com/oceanbase/powercontext
- https://powercontext.oceanbase.io/en/docs/develop/api-quickstart/
- https://github.com/oceanbase/seekdb
- https://platform.minimax.io/docs/api-reference/text-openai-api

模型输出中不保存私有推理；开发记录仅保留任务上下文、最终代码、ID、usage、差异和验证结果。
