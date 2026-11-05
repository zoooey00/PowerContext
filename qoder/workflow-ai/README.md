# WorkFlow AI — 可追溯的工作日志与周报助手

把分散的工作记录保存为 PowerContext 长期记忆；在新会话或服务重启后检索同一记忆，生成带原始记忆引用的周报和工作问答。

- **项目网站**：[Qoder Sites 展示与本地演示](https://workflow-ai-h5uhif9j8sv.qoder.zone)
- **比赛分支**：`2026-competition-ecosystem`；所有项目资产在 `qoder/workflow-ai/`。
- **验证证据**：[实际 HTTP 联调](evidence/integration.json)、[服务日志](evidence/services.log)、[验证步骤](VALIDATION.md)。
- **开发归属**：初始项目来自 Qoder；2026-11-05 的接口修复、联调与材料整理由 Codex 完成。[实际开发记录](QODER_RECORDS.md)区分两者。

## 解决的问题与实际能力

日常工作记录分散，周报整理容易遗漏，历史记录无法追溯。应用支持日志新增、编辑、删除、分类和日期筛选；PowerContext 记忆检索；带引用的周报；基于检索和规则的工作问答。

本地 SQLite 保存列表、日期条件和记忆引用映射；PowerContext 保存完整日志记忆并承担检索、上下文准备和生命周期管理。搜索结果展示的日志内容来自实际召回记忆，并验证其引用与当前本地日志一致。编辑旧记忆和删除日志会调用官方 lifecycle 遗忘接口。服务不可用时返回 502，**不会自动改用 SQLite 检索后宣称 PowerContext 已生效**。

默认使用 PowerContext FTS 全文检索，无需任何模型 Key。请搜索原文关键词（例如 JWT），不保证“认证相关的工作”这类语义改写匹配。需要语义检索时，在服务端配置向量能力后设置 `POWERCONTEXT_SEARCH_MODE=hybrid`；向量模式本次未实测。问答与周报采用确定性规则，不调用大模型。

## 环境与安装

实测：Windows 11、Python 3.12.16。应用依赖版本固定在 requirements.txt。PowerContext 固定为官方源码 commit：

`c4b9b540a6daa6514be83f1696e0fccf18c5c147`

本机安装来源及版本记录见 evidence/integration.json。源码 ZIP 缺少 Git 元数据，bootstrap 仅将构建分发版本标记为 0.1.0；该数字不能替代源码 commit。Windows 是上游的 experimental 平台，本项目已在上述 Windows 环境实测；Linux/macOS 启动路径已提供，未宣称实测。

在具备 GitHub/PyPI 安装网络的环境：

```bash
git clone --branch 2026-competition-ecosystem --single-branch https://github.com/zoooey00/PowerContext.git
cd PowerContext/qoder/workflow-ai
python bootstrap.py
```

安装会在本项目创建独立 .venv，并从官方固定 commit 安装 PowerContext cli/server。无需导入作者本机文件，不需要付费模型或 API Key。

## 启动

Windows：

```powershell
.\.venv\Scripts\python.exe run.py
```

Linux/macOS：

```bash
./.venv/bin/python run.py
```

或使用 start.bat / start.sh（默认使用本项目的 .venv）。访问 **http://127.0.0.1:8000**。保持终端运行，Ctrl+C 会停止本次启动的两个服务。

run.py 默认同时启动：
- PowerContext：127.0.0.1:18080；SQLite 数据在 .powercontext/pc.db；
- 应用：127.0.0.1:8000；本地列表在 data/workflow.db；
- 首次写入或健康检查通过官方 POST /v1/scopes 创建真实 Scope；之后用稳定 idempotency_key 复用。不要用手写示例 ID 代替真实 Scope。

无需 .env 即可启动。如需修改端口，复制 .env.example 到 .env 后编辑。服务配置与应用配置分开；应用启动读取固定的项目 .env，不因工作目录变化而读错文件。两类数据库都不提交 Git。

## 接入现有 PowerContext

在 .env 设置 `POWERCONTEXT_EXTERNAL=true`、实际 `POWERCONTEXT_SERVER_URL` 和必要的 `POWERCONTEXT_API_TOKEN`；有既有 Scope 时填写真实 `POWERCONTEXT_SCOPE_ID`。run.py 将只启动应用。应用连接私有服务时，token 仅留在后端，前端与网站不包含 token。

默认是单用户本地应用，监听回环地址，不提供多用户账号系统。Scope 是数据分区，不能代替鉴权。公开项目网站为静态展示和浏览器演示，**不会连接作者本机后端**；评审按本文运行完整功能。部署公网后端需要自行配置认证与 HTTPS，本项目未宣称完成公网后端部署。

## 复现验证

停止占用端口的其他测试后运行：

```powershell
.\.venv\Scripts\python.exe verify.py
```

Linux/macOS 使用 `./.venv/bin/python verify.py`。脚本使用空临时数据库和空闲回环端口，启动真正的 PowerContext 与应用 HTTP 进程；结束时清理自己创建的进程和临时数据。成功才写入 `evidence/integration.json` 的 `passed: true`，失败也会保存错误与日志。

验证覆盖记忆写入、GET/POST 检索、新 HTTP 客户端召回、两个服务重启后同引用召回、周报与上下文、问答、编辑遗忘旧记忆、删除、Scope 隔离、断网故障、输入校验。详细输入和预期见 VALIDATION.md。

## 主要接口

| 接口 | 方法 | 作用 |
| --- | --- | --- |
| /api/health | GET | 应用与 PowerContext 状态、Scope 和检索模式 |
| /api/work-logs | GET / POST | 列表 / 创建并写入真实记忆 |
| /api/work-logs/{id} | GET / PUT / DELETE | 查看 / 编辑并替换记忆 / 删除并遗忘 |
| /api/work-logs/{id}/sync | POST | 将旧版本遗留的未同步日志写入记忆 |
| /api/search?query=JWT | GET / POST | PowerContext 实际检索，附 memory_ref |
| /api/weekly-report | POST | 按日期生成周报，返回 memory_evidence 与 memory_context |
| /api/chat | POST | 基于实际记忆内容回答，附 sources |

## 当前边界

- 单次召回窗口最多 50 条；周报和全量统计发现缺失时返回 409，不将部分结果伪装成完整报告。面向个人小规模日志，规模化需扩展检索分页/分片。
- 启用同一 Scope 的多个应用实例不在当前支持范围；进程内修改串行化，跨进程事务一致性尚需扩展。
- 历史 PreparedContext 可能含周期外内容，前端独立标为参考；周报正文只使用所选日期内且引用一致的记忆。
- 没有收集真实用户规模或提效数据，验证记录属于工程自测。
- 已整理任务开始与账号原始截图，以及原 Qoder 任务中 18 次源码写入的脱敏记录；可补充原生编码/调试截图进一步核对。网站已匿名访问验证，最终提测状态见 SUBMISSION.md。

## 来源与许可

基于 [比赛基分支](https://github.com/oceanbase/powercontext/tree/2026-competition-ecosystem) 开发；原仓库基点 d647275c308e09b7b623f322a26f5c4e85734fb0。采用 [PowerContext 官方源码](https://github.com/oceanbase/powercontext/tree/c4b9b540a6daa6514be83f1696e0fccf18c5c147)，未修改上游运行源码。本项目测试日志与示例数据为自行构造；开源许可 Apache-2.0，保留仓库和上游的许可声明。
