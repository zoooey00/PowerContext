# 记仇杂货铺 · Dify × PowerContext

纸箱精阿扣会记住玩家的恶作剧，也会在收到道歉后降价。玩家用「恶作剧：会打嗝的月亮」「交换：一双失眠的拖鞋」「道歉：薄荷糖」参与故事。每次交换都会产生准确的物品去向账本；恶作剧和道歉不算交换。

## 架构与规则归属

**核心规则全部在提交 DSL 的 Dify Code 节点中。** `game_nodes.py` 只是这些节点的可读源码，`build_dsl.py` 将函数全文嵌入 DSL；运行时网关从不导入它。

| Dify 节点 | 实际职责 |
| --- | --- |
| input | 输入校验、命令解析、随机口令派生存档能力标识 |
| recall (HTTP) | 从 PowerContext 读取原始记录；没有分数和价格返回 |
| settle (Code) | 重放历史，计算警惕值、价格、徽章、回合数、交易得到的物品、准确历史账本 |
| gate (If/Else) | 判断20回合上限；超过上限直接走 limit Answer，不调用模型、不写入 |
| npc (LLM) | DeepSeek 根据行动类别、警惕值和是否熟客选择有限语气 |
| render (Code) | 严格枚举校验模型返回；由真实事件生成剧情、交换结果和收据；未知模型文本回退 |
| save (HTTP) | 将 Dify 生成的事件追加到 PowerContext 并读回核对 |
| receipt / answer | 确认保存成功才展示成功收据 |

共11节点、10边，包含实际业务条件分支。警惕初始0，恶作剧+2、道歉-1，钳位0–5；价格为3+2×警惕。警惕达到4时徽章为老冤家，否则为熟客。每个存档20回合。交易按回合轮换得到打嗝消音罩、失眠计数器、月光收纳袋，并准确记录 offered / received；这是一种叙事交易，不是完整背包游戏。

`server.py` 只有 `/memory/read` 和 `/memory/append`：负责能力标识映射 Scope、Bearer鉴权、签名读写凭据、冲突检测、幂等追加和真实 PowerContext 读回。它不理解行动类别、不计算游戏状态、不设20回合上限、不生成剧情。两次HTTP分别承担读与写，规则不是交给后端计算。

指定技术选择为 **Dify + PowerContext**。PowerContext 使用其官方 SQLite 持久化；不声明使用 seekdb。题面2.2明确允许此选型，不能将 SQLite 描述成 seekdb。

## 历史一致性与输入边界

模型不再自由叙述历史。玩家物品、原始台词、口令、历史正文都不进入模型上下文；模型仅收到固定类别和数值。只接受 astonished / stern / soft 三种语气枚举，其他文字一律不展示、不存储。最终事件文字和只读历史由 Dify 根据结构化事件生成。因此模型即使返回“拿拖鞋换走月亮”，也会被回退处理，不会改写历史。模型的角色发挥受到限制，这是为保证可核对事实作出的明确选择。

存档由24–128字符随机口令和虚构名称共同决定，不依赖 `sys.user_id` 做身份鉴权。API里伪造 user 而不知道正确存档口令不能访问原存档。持有同一口令与名称的人可以继续同一存档，这是持有者能力，而不是实名账号认证。口令只交给可信 Dify 工作区与输入节点；工作区管理员能查看输入日志，勿把真实密码作为口令。只读账本中的物品会加引号展示，玩家输入本身不代表系统指令。

## 固定依赖与运行环境

- 实测：Windows 11，Python 3.12.16，Dify Cloud（2026-11-06，DSL schema 0.7.0）。云端服务器源码版本不可固定；其他自部署版本未实测。
- DeepSeek官方插件：`langgenius/deepseek` 0.0.26；精确安装包哈希在 DSL dependencies 中。模型 `deepseek-flash`，非思考模式，max_tokens=100。需要评审自己的模型服务凭据和额度；模型 Key 仅配置在 Dify。
- PowerContext官方源码固定 `c4b9b540a6daa6514be83f1696e0fccf18c5c147`。ZIP安装时构建版本元数据设为0.1.0，身份以源码commit为准。依赖固定在 requirements-lock.txt。
- 无知识库、Embedding、Rerank、外部素材或自定义插件。空存档自动创建。
- 安装需要可访问PyPI及GitHub；本机服务需要约1GB磁盘。云端还需可访问的HTTPS网关。未承诺资源基准或长期托管。

## 安装、自动配置、导入

```powershell
git clone --branch 2026-competition-ecosystem https://github.com/zoooey00/PowerContext.git
cd PowerContext/dify
python bootstrap.py
.\.venv\Scripts\python.exe run.py
```

bootstrap 自动创建虚拟环境并生成本机随机 SHOP_TOKEN、`.env` 与 `.local/grudge-shop.yml`。后端持久化目录为本作品 `.powercontext`，重启保留记忆。只监听127.0.0.1:8000/8099。若机器未安装Python3.12，先安装对应解释器并用该解释器执行。

Dify Cloud不能访问本机127.0.0.1。保持 run.py 运行，给网关提供稳定HTTPS地址，或使用实测的临时工具：从 [Cloudflare官方2026.10.7发布页](https://github.com/cloudflare/cloudflared/releases/tag/2026.10.7) 下载 Windows amd64 文件，SHA256必须为 `2493dbc168923bb3e59e5e7716f71deced92992eea9acd6e9d74f84ac7751343`，然后：

```powershell
.\cloudflared-windows-amd64.exe tunnel --no-autoupdate --protocol http2 --url http://127.0.0.1:8099
.\.venv\Scripts\python.exe configure.py --url https://终端打印的地址.trycloudflare.com
```

configure 自动复用本机 token 并输出**已绑定地址和凭据的私有** `.local/grudge-shop.yml`；无需手工修改HTTP节点或复制密钥。不要提交或分享此文件。推荐导入该文件，即可完成网关绑定。原始仓库 DSL 保持占位和空secret，是题面4.2要求的凭据卫生，不能把真实secret公开以追求无配置运行。模型凭据、安装网络和云端访问地址仍是必要前置条件，不宣称零依赖开箱运行。

在Dify工作室导入应用，安装锁定的DeepSeek插件，在供应商设置配置自己的Key，确认deepseek-flash可用，预览后发布。公开的 `grudge-shop.yml`、`grudge-shop-cloud.yml` 内容相同，`grudge-shop.dify`包含同一DSL；任选其一，不要依次导入。若直接导入仓库模板，须在环境变量填写 SHOP_URL / SHOP_TOKEN；推荐用configure生成已绑定文件。

如果Dify在Docker、后端在宿主机，可使用configure默认的host.docker.internal地址，但须将网关SHOP_HOST改为0.0.0.0并允许容器访问8099。仅在可信网络使用；PowerContext不暴露公网。正式托管请使用稳定HTTPS域名；临时Tunnel每次启动地址变化，需要重新configure、导入或更新变量并发布。

## 体验和复现

[演示入口](https://udify.app/chat/neneiRJSfXTqgv64) 依赖作者本机及临时隧道在线，不保证持续可用。评审应按上面步骤重建，不需要作者已有状态或密钥。

1. 用 `python -c "import secrets; print(secrets.token_hex(24))"` 生成随机存档口令，保存于本机。
2. 填虚构名称和口令，发送恶作剧消息，预期第1回合、警惕2、价格7，且明确未发生交换。
3. 开启新对话，点“新对话设置→编辑”，确认相同名称与口令；发送交换拖鞋，预期第2回合、换得失眠计数器、价格7，历史仍为月亮恶作剧。
4. 再开启新对话，确认相同名称与口令；道歉后第3回合、警惕1、价格5，账本准确保留拖鞋换得失眠计数器，不会说拖鞋换走月亮。
5. 使用不同随机口令，得到空档；同名但不同口令不是同一存档。

## 验证脚本与证据

```powershell
.\.venv\Scripts\python.exe check_dsl.py
.\.venv\Scripts\python.exe verify.py
# 本机.env另配 DIFY_API_URL 与应用的 DIFY_APP_API_KEY；不要入库
.\.venv\Scripts\python.exe verify_dify.py
.\.venv\Scripts\python.exe verify_limit.py
```

verify.py 在8011/8101启动临时真实PowerContext和适配器，验证重启持久化、幂等、口令隔离、确切交易账本、无效模型输出回退、Dify规则源代码上下限；它不冒充云端模型测试。verify_dify执行真正发布API的三个不同conversation_id，检查7/7/5价格及确切交易历史。verify_limit通过本机适配器预置明确标注的20条夹具，再调用真实Dify Cloud验证上限分支和注入；这不是20次LLM调用。MEMORY_TEST_URL可更改夹具接口，默认127.0.0.1:8099。

证据见evidence目录及VALIDATION.md。存档口令和请求鉴权从公开证据移除。旧提交的自由叙事记录不作为本版证据。

单进程适配器只保证本实例串行写入，禁止多个实例或其他客户端编辑同一Scope；签名票据10分钟有效，重启作废，重新发起即可。同一票据重复追加幂等；整个Dify工作流重跑是新请求。每个存档最多20回合，故全量重放有明确上限。重置请使用新的名称和口令，不自动删除旧数据。

源码及样例为原创，新增代码MIT；PowerContext、Dify、DeepSeek插件遵循上游许可。赛事分支基点为d647275c308e09b7b623f322a26f5c4e85734fb0，所有资产在dify目录。GitHub上传与测评平台提交是两个独立步骤，分数以平台复核为准。
