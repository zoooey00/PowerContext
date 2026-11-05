# Qoder 赛题提交材料

## 可直接填写的字段

| 平台字段 | 内容 |
| --- | --- |
| 项目名称 | WorkFlow AI — 可追溯的工作日志与周报助手 |
| 作品链接 / 项目网站 | https://workflow-ai-h5uhif9j8sv.qoder.zone |
| 代码仓库 | https://github.com/zoooey00/PowerContext |
| Branch | 2026-competition-ecosystem |
| Commit ID | 使用本次最终交付的完整 hash；检出该提交后 git rev-parse HEAD 获取。聊天最终交付和压缩包根目录 SUBMISSION_VALUES.txt 提供精确值 |
| 项目目录 | qoder/workflow-ai/ |
| Qoder 账号 UID | 01a17718-eab6-73d3-9f4b-5a6df25f7738 |

## 验收对应表

| 检查项 | 状态 | 证据 / 下一步 | 规则来源 |
| --- | --- | --- | --- |
| 指定基分支开发 | 已确认 | 官方分支 HEAD d647275c308e09b7b623f322a26f5c4e85734fb0；同仓库 compare 的 merge base 为该值，behind_by=0 | 题面开头 |
| 对应 qoder 目录 | 已确认 | 本目录源码、证据与材料；本次提交只修改此项目 | 题面开头 |
| 网站通过 Qoder Sites 发布 | 已确认 | evidence/qoder-publication.json 原始 MCP 回执，published=true | 2.3、3.1 |
| 网站任何人可访问 | 已确认 | 原始 access_mode=public；evidence/site-public-check.json：独立匿名 Chrome，HTTP 200，附截图 | 2.3、3.1 |
| 主功能运行 | 已确认自测 | evidence/integration.json，10 组检查；browser-check.json，6 组检查 | 3.1 |
| 指定技术实际作用 | 已确认自测 | 真实 PowerContext 写入/召回引用、双服务重启持久性、周报与问答、编辑删除；没有 mock 或本地检索降级 | 2.2、3.1 |
| 运行说明 | 已交付 | README.md、bootstrap.py、run.py、requirements.txt、.env.example | 第四部分 |
| 验证样例 | 已交付 | VALIDATION.md，输入、步骤、预期、真实响应和日志 | 第四部分 |
| Qoder 开发记录 | 已整理 | 两张用户原始截图、18 次文件写入的原任务日志摘录、消息 UUID 与文件哈希；见 QODER_RECORDS.md | 2.1、第四部分 |
| Qoder UID | 已确认 | 用户提供文本与账号设置截图一致 | 第四部分 |
| 网站补充展示页 | 待处理（改进项） | site-submission/index.html 已准备；在原 Qoder Sites 更新并再次发布可把真实截图、运行入口和验证说明放到首页。现有线上版本仍是原本地演示 | 2.3 |
| 真实用户使用效果 | 不适用 | 尚未采集，不编造人数和提效百分比；工程自测不当作使用效果 | 2.4，鼓励项 |
| 最终测评平台提交 | 待处理 | 登录比赛平台填写以上字段、上传材料并保存成功页面；代码上传不能代替提测 | 第五部分 |

已从本机原始 Qoder 日志核对到主要初始源码创建与网站发布。后续接口修复、真实联调与材料整理由 Codex 完成，未伪称为 Qoder 操作。赛事对“主要开发”的最终判断仍由评审依据原 Qoder 任务记录和 UID 核对。建议补充原会话编码、调试阶段的原生截图/录屏。

## 建议上传的材料

1. 本目录完整源码（也可直接给出上述仓库、分支和精确 commit）。
2. README.md：环境、固定 PowerContext 来源、安装与双服务启动。
3. VALIDATION.md：至少一组完整验证输入、预期和操作步骤。
4. QODER_RECORDS.md 与 evidence/qoder-development.json、qoder-task-start.png、qoder-account.png。
5. evidence/integration.json、services.log、browser-check.json 和应用截图。
6. evidence/qoder-publication.json、site-public-check.json、site-public.png。

所有样例为合成测试数据，证据不包含真实 API Key、密码或用户日志。环境文件、数据库与浏览器配置不打包。语雀补充页本次读取失败，以用户提供规则逐项整理，未假定读取了无法访问的正文。

## 最后操作

- 若更新展示页，在 Qoder 打开本项目，把原站点的网页目录更新为 site-submission，再次发布；保持「任何人都可访问」。不要新建替代站点或删除原站点。
- 上传原生编码、调试截图（若平台要求独立截图附件，可在原 Qoder 任务中直接截取，与导出的消息 UUID 对应）。
- 在测评平台填写最终 hash 与 Branch，上传材料，保存提交成功回执。
- 评审结束前不要暂停或删除站点。
