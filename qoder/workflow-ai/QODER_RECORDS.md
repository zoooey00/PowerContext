# Qoder 开发记录与归属

Qoder 账号 UID：01a17718-eab6-73d3-9f4b-5a6df25f7738。
原始任务会话：afd053ae-a951-4eb6-a886-44dddd96651e，日期 2026-11-05。

## 原始 Qoder 开发证据

用户提供的原始应用截图：
- evidence/qoder-task-start.png：Qoder 中的比赛任务与初始开发对话。
- evidence/qoder-account.png：Qoder 设置页的账号 ID（手机号已在原截图中遮挡）。

从本机该任务的原始 Qoder JSONL 导出 evidence/qoder-development.json，保留源日志 SHA-256、原始会话 ID、消息 UUID、工具调用 ID、时间、18 次 Write 的文件路径及内容哈希。核心后端和前端附原始源码片段。导出未包含登录信息、MCP 权限引用或其他任务记录，不是事后重建的对话。

以下为原记录对应的北京时间（UTC+8）：

| 阶段 | 时间 | 原始证据 |
| --- | --- | --- |
| 配置与模型 | 15:28 | Write requirements.txt、config.py、models.py |
| 数据与记忆客户端 | 15:29 | Write database.py、powercontext_client.py |
| 后端功能 | 15:29:41 | Write backend/main.py，消息 50e2ab52-777b-4143-928c-5376072c5df5 |
| 前端界面与交互 | 15:30–15:31 | Write index.html、style.css、app.js |
| 调试及运行说明 | 15:31 起、16:02 | Bash 安装/启动检查，Write start.bat、start.sh、SUBMISSION.md |
| 网站制作与发布 | 16:30–16:35 | Write site-demo/index.html；Sites prepare/publish；最终回执 publication_completed |

原始调试记录代表当时执行过的操作，不能替代修复后真实 PowerContext 联调。其接口问题由本次后续检查发现并修复。

## 发布证据

原始 Qoder Sites MCP 回执已脱敏保存在 evidence/qoder-publication.json，显示 published=true、committed=true、access_mode=public、auth_integration_status=not_required。网址：
https://workflow-ai-h5uhif9j8sv.qoder.zone

本次又用独立无登录 Chrome 配置访问并保存 HTTP 200 截图。网站为浏览器本地演示，完整后端按 README 复现。

## 本次后续修复的实际归属

2026-11-05，用户在 Codex 中继续请求完成项目。Codex 完成：
- 对齐官方 PowerContext 请求、响应与真实 Scope；修复 GET/POST 搜索；
- 让周报和问答使用真实记忆内容及引用；加入编辑/删除生命周期；
- 修复统计、输入校验、前端转义、启动方式和错误处理；
- 执行真实 HTTP 与 Chrome 自测，整理证据和提交说明。

这些后续工作没有记作 Qoder 生成。赛事对“主要开发工作”的最终认定由评审依据原始 Qoder 任务和 UID 核对。建议在原 Qoder 会话中补充导出编码、调试阶段的原生截图或录屏，与本导出交叉核验。
