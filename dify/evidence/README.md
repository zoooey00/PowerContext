# 本版证据

- backend-run.json / services.log：真实PowerContext适配器及独立端口临时数据库，Dify Code源码本地执行；不冒充Cloud。
- dify-live.json：真实发布API三个独立会话；口令已移除；检查确切交易而非只看数字。
- dify-web-run.json / dify-web-1.png 至3.png：匿名正式网页实际三会话。
- limit-and-security.json：真实Cloud第21回合拒绝、原档20条不变、同API user不同口令隔离、注入不改规则；20条初始记录是明确夹具。
- dify-reimport.json：11节点含分支的新DSL实际导入响应。
- dify-node-trace.json：本版实际Cloud预览中节点事件摘要，含Dify规则与gate执行及模型返回。
- dify-runtime.json：公开入口与DeepSeek active状态快照，非API Key。

模型只选择有限语气，未让模型自由改写历史。游戏状态、历史账本和最终收据由DSL中的Code生成。不同测试使用不同存档，不要拼接成一段记录。截图与日志只能证明对应时刻的实际执行，不保证临时隧道永久在线。旧版本证据可从历史commit查看，不作为本版成功材料。
