# 实际技术使用记录

验证日期：2026-11-04（Asia/Shanghai）。

| 技术 | 本次实际方式与版本 | 证据 |
| --- | --- | --- |
| MiniMax | 国内 OpenAI 兼容 HTTP `/v1/chat/completions`，模型 MiniMax-M3.1-Flash | evidence/live/minimax-generation.json、events.jsonl |
| seekdb | 官方临时实例，MySQL 协议 TLS，服务版本 5.7.25-OceanBase seekdb-v1.2.0.0，应用 PyMySQL 1.1.1 | evidence/database-version.json、live/events.jsonl |
| PowerContext | 真正本地 HTTP 服务，源码提交 2853ed98a6ab767f6bbfe35098024d5f9cec9a2b；归档构建版本 1.4.0+git.2853ed98；独立 SQLite 持久存储 | evidence/live/events.jsonl、context-resumed.json |

模型生成：实际请求输入 2100 tokens，输出 653 tokens，总计 2753 tokens（供应商返回的 usage）。只交付最终代码和 token 计数，不交付模型 reasoning_content。源文件 SHA 与模型回答 SHA、测试记录一致。代码生成约束是只改 business/tickets.py；目标和回归测试始终不变。

工程资料：实际写入 8 条记录。任务查询命中 7 条：TICKET-001、TICKET-002、TICKET-003、business/tickets.py、tests/data.py、tests/test_target.py、tests/test_regression.py。无关 BILLING-001 未命中。结果用于实际 MiniMax 请求，check_submission.py 会核对请求与上下文一致。

状态写读：demo 创建新任务 Scope，首次 prepare 为空；remember 写入已完成事项、待办、四组验证摘要及代码/测试哈希；另起 Python 解释器，仅传任务 ID，重新从 PowerContext prepare，恢复验证标记并选择后续 review/continue 动作。恢复输出未读取 task-state.json。

规格更新：实际在 TICKET-002 附加随机修订内容、revision 从 1 改为 2，重新导入后查询返回新文本和哈希。随后恢复规格及数据库索引。

功能验证：修改前目标测试因断言失败返回 1；修改前回归为 0；MiniMax 修改后目标及回归均为 0。复验另有 5 项来源校验测试。完整命令、退出码和代码身份详见 generated-tests.json。

环境处理：Windows 深目录触发第三方依赖长路径限制，改用同一工作区短路径隔离虚拟环境解决；源码未更改。首次国际接口认证失败，国内接口曾有 TLS 临时中断，重试国内接口后完整 demo 成功。这些环境失败未计为目标功能失败。免费 DB 凭据、API Key、运行数据库及虚拟环境均不提交。
