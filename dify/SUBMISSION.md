# 提交核对

| 要求 | 对应交付 |
| --- | --- |
| Dify承担核心流程与玩法 | settle规则Code、gate条件分支、render事实输出Code均在DSL；后端不含游戏规则 |
| PowerContext实际作用 | 真实Scope记忆读写、后续新会话重放；SQLite已披露，不声称seekdb |
| 全部DSL | grudge-shop.yml、grudge-shop-cloud.yml为相同应用；.dify为等价包，任选其一 |
| 配置后可运行 | bootstrap自动生成随机凭据；configure --url生成私有已绑定DSL；模型Key在供应商配置 |
| 版本与网络 | README中的固定源码commit、依赖锁、DeepSeek0.0.26、DifyCloud0.7与HTTPS要求 |
| 初始化与重置 | 自动空Scope；新随机口令为新存档；不依赖作者已有数据 |
| 实际样例 | 三个独立会话的真实API与网页、严格交易账本、边界与隔离测试 |
| 不泄露凭据 | 原始DSL为空secret；.env、.local及口令不公开 |
| 提交目录和分支 | 全部资产在dify，继承2026-competition-ecosystem比赛基点 |

代码仓库：https://github.com/zoooey00/PowerContext.git
Branch：2026-competition-ecosystem
Commit id：以上传后交付的最新40位真实commit为准；不要复用旧提测a5c47ae。

原始模板含占位URL和空Token是有意不公开凭据；必须按步骤生成已绑定的本机导入文件。不能把示例值冒充在线可用服务。演示公网入口依赖本机与临时隧道，不承诺长期在线。

测评平台提交需用户在表单填写新hash并点击提交，GitHub推送不等于提测成功。已有失败记录不代表修订版获通过，最终成绩待平台复核。语雀补充页面此前未读取成功，不能声称已核实其额外规则。
