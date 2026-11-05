# 记仇杂货铺 · Dify × PowerContext

纸箱精掌柜阿扣经营一家只收纽扣的怪物杂货铺。你可以拿“会打嗝的月亮”恶作剧，用“失眠的拖鞋”交换商品，再用薄荷糖赔礼。阿扣会在新会话中记住你，警惕值和交换价也会延续。体验入口为 Dify 发布后的 Chatflow Web App 或 API，不需要额外前端。

**已完成真实 Dify Cloud 导入、DeepSeek 调用、PowerContext 读写、发布后的三独立会话 API 验证，以及匿名网页三会话体验。最终交付的云端 DSL 已重新导入，返回 completed、无警告，并重新发布复测。** 真实证据见 [evidence](evidence/)，逐项对应见 [验收清单](SUBMISSION.md)。这些是实际自测结果，不代表赛事已评分或平台已提测。

体验入口：[记仇杂货铺](https://udify.app/chat/neneiRJSfXTqgv64)。**演示后端目前运行在作者本机，经临时 Cloudflare Tunnel 提供访问；电脑关机或隧道停止后不能体验。** 评审应按下面步骤重建自己的后端、重新配置地址和凭据；正式长期在线应换成稳定 HTTPS 部署。

## 玩法

填一个虚构角色存档名（例如“月亮来客”），发送下列消息。每条行动内容 1–150 字，无前缀默认“看看”。每个存档最多 20 回合；改存档名可另开一局。

| 输入 | 后果 |
| --- | --- |
| `恶作剧：会打嗝的月亮` | 警惕 +2，上限 5；掌柜会反击并记住物品 |
| `交换：一双失眠的拖鞋` | 按当前交换价演绎交易 |
| `道歉：一颗薄荷糖` | 警惕 -1，下限 0 |
| `看看：柜台上的新品` | 看看离谱商品，保持警惕值 |

初始警惕 0，交换价 = 3 + 警惕 × 2 枚纽扣。每回合结束显示实际状态收据。纽扣只是虚构价格，没有支付功能。第一次是“初来乍到”，有记录后是“熟客”，警惕 ≥4 是“老冤家”。台词可自由变化，数值由代码确定。

## 技术分工与数据

`Dify Start → Code 解析输入 → HTTP 召回 → Code 检查 → LLM 台词 → Code JSON 编码 → HTTP 保存并读回 → Code 收据 → Answer`

- Dify 承担核心编排、输入解析、模型调用和输出；模型不在配套后端调用。
- PowerContext HTTP `/v1/scopes` 创建幂等玩家 Scope；`/v1/memory/remember` 写入实际经历；`/v1/memory/entries/list` 读回全部游戏记录，计算状态并取最近 5 条给模型。使用官方显式记忆读写能力，不需要 Embedding、Rerank 或 PowerContext 推理模型。
- 后端只实现固定规则、网关鉴权与签名回合票据，无应用数据库替代 PowerContext。PowerContext 使用其内置 SQLite 持久化；本作品选择 **Dify + PowerContext**，不声明使用 seekdb。
- Scope 由服务端对 `Dify sys.user_id + NUL + 角色存档名` 哈希生成。同一 Dify 用户的不同会话、同一存档共享经历；不同用户隔离。API 调用方必须由可信客户端固定 `user`，不能把玩家可随意填写的账号当鉴权。浏览器换设备、清理标识可能被 Dify 视为新用户。
- 只保存游戏行动、物品、NPC 回复、回合号及请求标识；勿输入真实个人信息。模型收到的历史及物品是资料，不作为系统指令。系统状态与最后的收据不由模型修改。

## 版本与准备

| 项目 | 声明 |
| --- | --- |
| 配套后端实测 | Windows 11，Python 3.12.16；依赖逐项固定在 requirements-lock.txt |
| PowerContext 源码 | 官方 `c4b9b540a6daa6514be83f1696e0fccf18c5c147`，ZIP 构建元数据设为 0.1.0，不能用这个包版本号替代源码 commit |
| Dify 实测环境 | Dify Cloud，2026-11-05；接口返回 DSL schema 0.7.0；云服务未提供可固定的服务器源码版本。自部署 Dify 未实测 |
| 模型 | 官方 DeepSeek `deepseek-flash`，聊天模式，thinking=false、temperature=0.8、max_tokens=700；工作区状态 active，真实调用通过 |
| 插件 | 官方 `langgenius/deepseek` 0.0.26，Dify Marketplace 安装；精确包标识已固定在两个 DSL 中，无自定义插件 |
| 外部数据 | 无知识库，无下载素材，无预置记忆。空 Scope 自动创建，例子为自行设计 |

准备 Python 3.12、Git，以及能访问 PyPI / GitHub 的安装网络。模型服务需要由 Dify 工作区获取并配置有效凭据和额度。后端无需模型 Key。建议给 Dify 使用独立 Docker 环境，并按其官方部署要求分配资源；本机后端安装需预留约 1 GB 磁盘。Linux/macOS 及云端 Dify 连本机后端未实测。

## 启动配套服务（PowerShell）

```powershell
git clone --branch 2026-competition-ecosystem https://github.com/zoooey00/PowerContext.git
cd PowerContext/dify
python bootstrap.py
Copy-Item .env.example .env
# 生成随机值后写进 .env 的 SHOP_TOKEN；不要提交 .env
python -c "import secrets; print(secrets.token_hex(24))"
.\.venv\Scripts\python.exe run.py
```

保持终端运行。首次 PowerContext 导入依赖和初始化可能需要一两分钟。数据保存在 `dify/.powercontext/pc.db`；关闭再启动 `run.py` 会保留记忆。PowerContext 监听 `127.0.0.1:8000`，网关默认 `127.0.0.1:8099`。`http://127.0.0.1:8099/health` 只说明网关进程可访问，不能证明记忆功能正常。

`bootstrap.py` 通过官方固定 commit ZIP 安装，不依赖本机未交付的源码。`SETUPTOOLS_SCM_PRETEND_VERSION=0.1.0` 只解决 ZIP 缺少 Git 元数据的构建问题，不修改官方运行源码。

## Dify Cloud 导入及发布

在 [Dify Cloud](https://cloud.dify.ai) 登录自己的工作区。提交不包含账号或供应商 Key；评审需配置自己的模型服务。自部署时应使用支持对应 DSL schema 与插件版本的 Dify，参照 [官方部署说明](https://docs.dify.ai/en/self-host/quick-start/docker-compose)；自部署环境本次未实测。

1. 在模型供应商中安装官方 DeepSeek 0.0.26 插件，在供应商设置里配置自己的 Key，确认 deepseek-flash 为 active；不要把 Key 写入 DSL。若选择其他型号，须在“掌柜阿扣接招”节点重新绑定并检查其参数，不能沿用本次模型已实测的声明。
2. 在 Studio 选择“导入应用”，优先导入 `grudge-shop-cloud.yml`（正式云端导出 DSL 0.7.0，已重新导入实测），或等价的官方格式包 `grudge-shop.dify`。**二选一，不需要连续导入。** `grudge-shop.yml` 是 `build_dsl.py` 可重建的 DSL 0.4.0 版本，曾在同一云工作区导入并运行；云端会提示版本差异。它是另一个可选入口，不要再创建一遍应用。没有知识库导入顺序。
3. 打开环境变量，设置 `SHOP_URL`（无末尾 `/`）和 secret 类型的 `SHOP_TOKEN`，后者必须与网关 `.env` 一致。DSL 不包含真实凭据。
4. **Dify 在 Docker、后端在宿主机**：在本作品 `.env` 设置 `SHOP_HOST=0.0.0.0` 后重启 `run.py`；DSL 的 `SHOP_URL=http://host.docker.internal:8099` 适用于 Docker Desktop。宿主机防火墙需允许 Dify 容器访问该端口；网关依赖 Bearer token 鉴权。PowerContext 继续仅监听回环。
5. **Dify 与后端都在宿主机**：`SHOP_URL=http://127.0.0.1:8099`。Linux Docker 需给实际发起 HTTP 的容器（含 ssrf_proxy）设置 `host.docker.internal:host-gateway`，或使用容器可达的宿主机地址。Dify 的 SSRF 代理也必须允许访问此网关；用 HTTP 节点调试验证，不要只测浏览器打开 health。
6. Dify 云端不能访问你的 `127.0.0.1`；须把鉴权网关部署到云端可达的 HTTPS 地址并更改 SHOP_URL。只需开放网关，不暴露 PowerContext 或数据库。也可以按下一节使用与本次验收相同的临时隧道。
7. 选中“掌柜阿扣接招”节点，确认绑定有效聊天模型。预览运行，检查两处 HTTP 节点状态均为 200，再发布应用。发布页生成的 Web App 链接就是你重建的体验入口。

正常交互前必须保持 Dify Sandbox（Code 节点）、模型提供商和网关可用。模型失败不会进入保存节点；保存失败停止流程，不输出成功收据。Dify 发布前预览不代替发布后的 API 验证。

### 与本次实测相同的临时 HTTPS 连接（Windows x64）

从 [Cloudflare 官方 2026.10.7 发布页](https://github.com/cloudflare/cloudflared/releases/tag/2026.10.7) 下载 `cloudflared-windows-amd64.exe`，本次文件长度 55,390,512 字节，官方 SHA-256：`2493dbc168923bb3e59e5e7716f71deced92992eea9acd6e9d74f84ac7751343`。无需 Cloudflare 账号或域名。保持 `run.py` 运行，在另一终端执行：

```powershell
Get-FileHash .\cloudflared-windows-amd64.exe -Algorithm SHA256
.\cloudflared-windows-amd64.exe tunnel --no-autoupdate --protocol http2 --url http://127.0.0.1:8099
```

核对哈希后再运行。把终端打印的 `https://....trycloudflare.com` 写入 Dify 的 SHOP_URL，SHOP_TOKEN 仍是本机 `.env` 的随机值。需要本机可向 Cloudflare 建立 HTTP/2 隧道并保持进程运行。本次已验证该网络链路；下载工具不打包进仓库。

隧道每次启动的地址不同，必须相应更新 Dify 环境变量并重新发布。Quick Tunnel 无长期可用性保证，详见 [官方限制](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)。DSL 内只放占位地址，不依赖作者的临时 URL。

## 验证与证据

先关闭 `run.py`，避免端口冲突，执行：

```powershell
.\.venv\Scripts\python.exe check_dsl.py
.\.venv\Scripts\python.exe verify.py
```

`verify.py` 在临时数据库启动真实 PowerContext，执行 9 项断言并重启真实进程检查持久化；结束关闭自身进程。输出 `evidence/backend-run.json` 和 `evidence/services.log`。测试台词是明确标注的固定字符串，不是模型结果。运行会覆盖这两份证据，请用版本控制保留需要的记录。脚本需要 8000 和 8099 端口空闲；Windows 受限沙箱可能无法启动子进程或清理临时目录，应在正常本地终端执行。

发布 Dify 后重新启动 `run.py`，从应用“访问 API”获取该应用 API Key，仅放入当前终端环境：

```powershell
$env:DIFY_API_URL='http://localhost/v1'
# 在本机安全设置 DIFY_APP_API_KEY，不要发送到聊天或写入仓库
.\.venv\Scripts\python.exe verify_dify.py
```

该脚本也会从本机 `.env` 读取上述两个变量。它创建同一 end-user 的三个独立会话，检查 3 个连续回合的价格和收据，并要求第二轮提到“月亮”。成功时才生成 `evidence/dify-live.json`，其中包括真实模型回复、conversation_id 和 metadata。文件默认忽略；本次实际证据已审核后显式加入提交。`dify-node-trace.json` 包含真实节点状态、召回、LLM 输出与保存返回的 Artifact 引用，已移除请求头和签名票据。详细人工步骤见 [VALIDATION.md](VALIDATION.md)，网页实际截图为 `dify-web-1.png` 至 `dify-web-3.png`。

## 约束与故障处理

- 网关仅支持单进程实例；线程锁协调同一实例。禁止多个网关写同一游戏 Scope，也不要从其他客户端编辑游戏记忆。独立 Atomic Memory 的新写入不是整个 Scope 的原子 compare-and-swap；目前不声明分布式并发支持。
- `/prepare` 签名票据 10 分钟有效，网关重启后作废，重新发送行动即可。同一成功票据再次 commit 不重复计分；重新触发整个 Dify 运行具有新 workflow_run_id，会被视为新回合。
- 存储全部最近 20 回合；模型仅见最近 5 回合，不能保证回忆所有细节。价格结算会遍历全部记录。免费看看和道歉也各算一回合。
- 交易是叙事互动，没有库存或物品所有权校验。输入命令决定行动，模型不会自动把自然语言猜成恶作剧。
- 模型输出不保证完全遵循角色或措辞；收据数值确定。模型返回过长、空白、超时或额度不足时，检查 Dify trace 并重试。
- 更换存档名可恢复“新角色”的初始状态，不删除旧记忆。要物理清理演示数据，先停止所有相关进程，再由操作者备份并移除本作品专用 `.powercontext` 目录；不要删除其他应用的数据。

## 来源与许可

本作品玩法、DSL、配套代码及样例为本次原创，未复制题面列出的娱乐工作流或数据。新增代码采用 [MIT](LICENSE)。PowerContext 与 Dify 的使用遵循各自上游许可证；不重新分发其源码。

- [比赛基分支](https://github.com/oceanbase/powercontext/tree/2026-competition-ecosystem)：所有资产放在 dify 目录，继承基点 `d647275c308e09b7b623f322a26f5c4e85734fb0`。
- [PowerContext API 快速开始](https://powercontext.oceanbase.io/zh/docs/develop/api-quickstart/)；运行接口以固定源码 commit 的生成模型为准。
- [Dify HTTP 节点](https://docs.dify.ai/en/cloud/use-dify/nodes/http-request)、[DeepSeek 官方插件源码](https://github.com/langgenius/dify-official-plugins/tree/main/models/deepseek)。最初生成器曾对照 Dify 1.9.1 的字段，最终兼容性结论以上述真实云端导入与运行结果为准。

题面引用的语雀补充提交说明本次未能读取，未假定其内容已核实。上传 GitHub 不等于测评平台提交成功。
