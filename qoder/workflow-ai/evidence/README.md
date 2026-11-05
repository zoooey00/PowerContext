# 证据索引

- integration.json / services.log：真实 PowerContext 与应用 HTTP 自测，10 组通过；含双进程重启和故障处理。
- browser-check.json / ui-services.log：真实 Chrome UI 自测，6 组通过，移动端无横向溢出。
- app-*.png：连接真实后端的实际页面；安全测试字符串被纯文本显示。
- qoder-task-start.png / qoder-account.png：用户提供的原始 Qoder 截图。
- qoder-development.json：仅本项目的原始 Qoder JSONL 摘录，18 次文件写入及来源哈希。
- qoder-publication.json：原始 Qoder MCP 公开发布成功回执。
- site-public-check.json / site-public.png：独立无登录 Chrome 访问原站点的实际 HTTP 200 结果。
- branch-base.json：官方比赛分支基点与当前仓库 ancestry 对照。

日期均为 2026-11-05；JSON 时间为 UTC（北京时间加 8 小时）。数据为自行构造的工程验证，未冒充真实用户使用效果。未打包原始完整会话、认证信息、环境凭据、数据库或浏览器配置。
