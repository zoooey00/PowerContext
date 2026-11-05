# 验证样例与实际证据

## 样例 A：保存记忆，跨会话检索，再生成周报

初始状态：全新空 Scope 和空应用数据库。启动步骤见 README.md。默认全文模式，无需模型 Key。

1. 打开 http://127.0.0.1:8000，确认顶部显示 PowerContext 已连接、fts。
2. 新增日志：标题「完成登录模块」；内容「实现 JWT 认证和登录页面」；分类开发；标签 JWT；日期今天。
3. 保存后日志卡片显示 atomic-memory/真实ID@版本；在浏览器网络面板查看 POST /api/work-logs 的 memory_ref。
4. 关闭页面，打开新的浏览器页面，进入记忆检索，输入 JWT。预期召回该条记录，memory_ref 与保存时一致。
5. 选择包含今天的日期范围生成周报。预期正文包含 JWT 工作，记忆依据列出真实引用；展开上下文与记忆依据可查看实际 PreparedContext。
6. 进入问答，输入 JWT。预期回答包含召回内容，sources 包含同一引用；这是规则与检索回答，不是大模型生成。

指定技术的作用：保存使用 PowerContext remember；检索使用 search 的 hits[].memory；周报以这些实际记忆内容生成；准备的 Context 与记忆引用作为可检查证据展示。

## 样例 B：编辑、删除与故障

1. 编辑上述日志：内容改为「完成 OAuth2 集成」，标签改为 OAuth2。
2. 搜索 JWT 不再返回旧版本；搜索 OAuth2 返回新版本和新的记忆引用。
3. 删除该日志，再搜索 OAuth2 不再出现它。应用调用官方 lifecycle 将旧记忆 forgotten；本地映射也被移除。
4. 只停止 PowerContext，保持应用运行。检索和保存请求应返回 HTTP 502，页面显示错误。保存失败的本地插入回滚，不能把本地关键词匹配当作技术接入成功。

## 自动复现与当前实测

执行 python verify.py（使用安装好的 .venv Python）。脚本自动启动真正的 PowerContext 与应用进程，生成样例数据，并实际重启两个进程验证持久性。

- evidence/integration.json：实际输入对应的 HTTP 响应、真实 Scope 与 Artifact 引用、依赖版本、固定 PowerContext 安装来源；10 组检查 passed=true。
- evidence/services.log：同次验证的真实服务日志。没有请求头或 API Key。
- evidence/browser-check.json：6 组 Chrome 浏览器界面检查；包括保存、检索、周报、问答、编辑、HTML 转义；移动端无横向溢出。
- evidence/app-logs.png、app-search.png、app-report.png、app-mobile.png：本次实际完整后端页面截图。包含安全测试字符串时，它们仅作纯文本展示，不是可执行 HTML。
- evidence/site-public-check.json、site-public.png：独立无登录 Chrome 配置访问已发布 Qoder Sites，HTTP 200。
- evidence/qoder-publication.json：原 Qoder MCP 发布成功且 access_mode=public 的原始回执摘录。

浏览器检查可选执行：python verify_browser.py。需要 Node（内置 fetch/WebSocket）与本机 Chrome，默认路径见 scripts/browser-check.mjs；评审验证主要功能无需执行此辅助截图脚本。

以上均为工程自测，不是主办方评分，不是使用人数或提效实验。FTS 已实测；向量检索和 Linux/macOS 环境未实测。
