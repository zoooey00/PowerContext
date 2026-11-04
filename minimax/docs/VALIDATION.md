# 验证样例

任务：工单列表增加可选 status 筛选。有效规格为 `specs/tickets.json`，TICKET-001/002/003 都必须出现在上下文。无关 BILLING-001 不应命中当前任务。

初始数据：`tests/data.py`。id=3 Alice/open、id=1 Bob/open、id=2 Alice/closed，输入故意不排序。

必须改变：`status='open'` 得到 id `[1,3]`；`closed` 得到 `[2]`；`' OPEN '` 同 open；owner=alice 且 open 得到 `[3]`。无效状态（空字符串、pending、数字、布尔、列表、字典）抛 ValueError，空列表也要校验状态。

必须保持：省略 status 得到 `[1,2,3]`；owner=alice 得到 `[2,3]`；owner 大小写敏感；未知 owner、空数据返回空列表；返回独立的行字典，不修改原数据。

必须包含的代码来源：`business/tickets.py::list_tickets`。必须包含的测试来源：`tests/test_target.py::TargetTests`、`tests/test_regression.py::RegressionTests`、`tests/data.py::ROWS`。路径以 minimax/ 为根。入口在 task.json 声明必要来源并检查缺失，不以固定答案替代查询。

步骤：按 README 初始化数据库与 PowerContext；执行 import、context、demo、refresh-check。`demo` 用新的 Scope 验证从空状态开始；状态包含完成项、待办项、测试命令/退出码、代码和测试哈希；子进程仅接受任务 ID，重新从服务器查询状态，并选择 review/continue 动作。

前后目标测试为同一物理测试副本，代码分别来自 before 与 MiniMax 生成的 after；日志中的测试哈希必须一致。修改前必须是断言失败，不能是 ImportError、环境或依赖错误；回归前后都应返回 0。`verify-local` 是参考补丁验证，不能替代真实模型调用记录。

规格更新：refresh-check 给 TICKET-002 追加随机修订标记并提高 revision，写入 DB 后按任务检索，确认返回新的内容和哈希；finally 恢复原规格并导入。也可手工编辑任意规格文本、重新 import，再 context 核对更新。

复现提交的 MiniMax 补丁：直接运行业务测试即可，无需再调用模型；若要重新演示生成则配置自己的 Key 运行 demo。重置方法见 README。
