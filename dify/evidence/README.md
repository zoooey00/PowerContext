# 实际运行证据索引

本目录区分真实模型运行与固定台词后端测试。所有凭据均不入库；提交中没有 Dify、DeepSeek 或网关的真实 API Key / token。

| 文件 | 实际执行与证明范围 |
| --- | --- |
| `backend-run.json`、`services.log` | 真实官方 PowerContext HTTP 与网关的 9 项检查；包括进程重启后仍可读回。使用固定“测试台词”，不宣称执行 Dify 或模型 |
| `dify-reimport.json` | 最终 `grudge-shop-cloud.yml` 在 Dify Cloud 重新导入，服务端与文件 DSL 均为 0.7.0，结果 completed，无警告 |
| `dify-live.json` | 最终重新导入并重新发布后的应用，通过正式 API 调用 DeepSeek 完成 3 个独立会话；有完整实际回答及真实 conversation_id |
| `dify-node-trace.json` | 首次成功预览的真实 SSE 节点事件摘要，9 个节点成功；保留召回、模型结果、保存与读回的实际 Artifact 引用，移除请求头及签名票据 |
| `dify-web-run.json` | 未登录 Dify 控制台的独立浏览器上下文，在正式 Web App 执行新建聊天与三回合玩法的可见文本记录 |
| `dify-web-intro.png`、`dify-web-1.png` 至 `dify-web-3.png` | 实际网页初始表单及三回合截图；第 2 次提到旧物品，第 3 次道歉降价 |
| `dify-runtime.json` | 实际工作区模型 active 状态、发布工作流信息、Web 与 API 启用状态和体验入口；没有供应商凭据 |

最终 API 样例的三回合价格依次为 **7、7、5** 枚纽扣，警惕值依次为 **2、2、1**。第二个独立会话的回答提到了第一个会话中的“月亮”。网页样例使用另一个玩家，也得到相同规则状态；不能把两组样例的回合标识混为一组。

API 证据由 `verify_dify.py` 生成；其每次使用随机 end-user，可反复从空档执行。后端独立证据由 `verify.py` 生成。网页操作与期望行为见 `../VALIDATION.md`。

公开体验入口为 https://udify.app/chat/neneiRJSfXTqgv64 。当前演示依赖作者本机服务和临时 Cloudflare Tunnel 持续运行；机器或隧道停止会导致无法体验。评审可根据 `../README.md` 使用自己的 Dify、模型凭据、后端及 HTTPS 网关重新复现，不需要任何作者本机已有状态。
