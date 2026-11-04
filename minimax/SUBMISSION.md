# 提交材料与验收入口

提交目录：minimax/。平台需要填写团队仓库 URL、已推送的 branch 和完整 commit hash。以本次最终交付的提交信息文件为准，不要填写比赛基线 commit。

| 材料 | 路径 |
| --- | --- |
| 上下文模块和模型接入 | sdd/core.py、sdd/__main__.py |
| 业务工程及不变测试 | business/、tests/ |
| 依赖、配置和运行步骤 | README.md、requirements.txt、.env.example、scripts/ |
| 验证任务、初始数据、必要来源 | task.json、specs/tickets.json、tests/data.py、docs/VALIDATION.md |
| 修改前后快照 | fixtures/before/tickets.py、fixtures/after/tickets.py |
| 实际模型请求和最终代码 | evidence/live/minimax-generation.json |
| 代码差异和前后测试日志 | evidence/live/change.patch、evidence/live/generated-tests.json |
| 实际 DB 查询与 PowerContext 写读 | evidence/live/events.jsonl |
| 恢复后使用状态的上下文 | evidence/live/context-resumed.json |
| 实际规格变更重新导入 | evidence/live/spec-refresh.json |
| 一页技术说明与引用 | docs/TECHNICAL.md、NOTICE.md |

本地核对交付：

```bash
python scripts/check_submission.py
```

此命令不调用 MiniMax，不需要旧的免费实例，检查提交证据的一致性并重跑真实业务和来源校验测试。要验证数据库和状态服务的行为，需按 README 从干净环境初始化，再 import、context、refresh-check；要重新生成补丁则配置 MiniMax Key 运行 demo。

本作品的实际验证摘要由 evidence/live/acceptance.json 给出。环境失败与断言失败必须区分；只有 before_target 的目标断言失败是预期的非零退出，其余必需测试都应成功。

完成新的 demo 后，先运行 `python scripts/export_evidence.py`，再 `python scripts/check_submission.py`，然后提交新增证据。不得提交 runtime/、.env 或真实连接密码。所有关键证据都应随固定提交进入 Git，不能仅存在于本机运行目录。
