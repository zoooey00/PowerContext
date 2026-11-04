# 规有所依：MiniMax × OceanBase SDD 上下文模块

项目资产全部在 `minimax/`。比赛基线：`oceanbase/powercontext` 的 `2026-competition-ecosystem`，提交 `d647275c308e09b7b623f322a26f5c4e85734fb0`。

## 环境与依赖

应用使用 Python 3.11+、PyMySQL 1.1.1，通过 MySQL 协议连接 seekdb/OceanBase；MiniMax 使用 OpenAI 兼容 HTTP API；PowerContext 使用 HTTP API。PowerContext 服务源码固定到 `2853ed98a6ab767f6bbfe35098024d5f9cec9a2b`。服务与应用请使用不同虚拟环境，避免 PowerContext 的 PyMySQL 版本约束冲突。

以下命令均从仓库 `minimax/` 执行。先安装应用依赖：

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt
```

复制 `.env.example` 为 `.env`，填写实际连接配置与 MiniMax Key。支持进程环境变量、项目 `.env`；Windows 还会读取当前用户持久环境变量。进程环境变量优先。不要提交 `.env` 或 `runtime/seekdb-instance.json`。

本次真实模型使用国内接口 `https://api.minimaxi.com/v1`、`MiniMax-M3.1-Flash`。国内新文档地址为 `https://api.minimax.cn/v1`；国际账户使用 `https://api.minimax.io/v1`。Key 必须匹配账户地区，认证错误不会自动切换或伪造返回。

## 初始化数据库

已有 seekdb/OceanBase 时，使用独立数据库 `minimax_sdd`：

```sql
CREATE DATABASE IF NOT EXISTS minimax_sdd;
```

只在这个独立数据库导入。`import` 会事务替换 `sdd_documents` 全表，请勿与其他项目共用此表。应用不自动创建远程数据库。

无服务时可用官方免费七天实例：

```bash
python scripts/provision.py
```

凭据仅写入被 Git 忽略的 `runtime/seekdb-instance.json`，应用自动读取并使用 TLS。此方式不要在 `.env` 设置示例 DB 值，否则会覆盖实例配置。免费实例会到期，评审需要新建实例，不能依赖本次实例。

也可以运行官方容器 `oceanbase/seekdb:latest`，映射 `2881:2881`，按官方说明创建数据库，并记录实际镜像 digest 和 SQL `SELECT VERSION()`。`latest` 不是版本锁，最终复现时优先使用技术记录中的镜像 digest 或明确数据库版本。

## 启动真实 PowerContext

服务使用独立虚拟环境安装，不需要额外模型 Key（显式 remember / prepare）：

```bash
python -m venv runtime/pc-venv
# Linux/macOS 将下面的 Scripts/python.exe 改为 bin/python
runtime/pc-venv/Scripts/python.exe -m pip install "powercontext[cli,server] @ git+https://github.com/oceanbase/powercontext.git@2853ed98a6ab767f6bbfe35098024d5f9cec9a2b"
```

若 Git 网络受限，可 `python scripts/fetch_pc.py` 下载同一固定提交的归档。该归档没有 Git 版本元数据，安装前设置 `SETUPTOOLS_SCM_PRETEND_VERSION=1.4.0+git.2853ed98`，再安装 `powercontext[cli,server] @ file:///绝对路径/runtime/powercontext.zip`。此版本标签是归档构建标签，源码身份以上述 commit 为准。

Windows 路径过长可能使第三方包安装失败。建议把仓库放在较短路径；或设置 `$env:PC_VENV='C:/sdd-pc-env'`，再运行 `./scripts/prepare_pc.ps1` 与 `./scripts/start_pc.ps1`。此变量只决定本作品的隔离服务环境位置，不修改系统 Python。

PowerShell 启动：`./scripts/start_pc.ps1`。Linux/macOS：

```bash
export POWERCONTEXT_SERVER_DATABASE_KIND=sqlite
export POWERCONTEXT_SERVER_DATABASE_URL=sqlite+aiosqlite:///./runtime/powercontext.db
runtime/pc-venv/bin/powercontext server run --host 127.0.0.1 --port 8000 --no-env-file
```

保持服务器运行。应用的 `POWERCONTEXT_URL` 默认是 `http://127.0.0.1:8000`。PowerContext 自身使用 SQLite 保存状态；工程资料及检索实际使用 seekdb，二者分工不同。

## 调用入口

```bash
python -m sdd import
python -m sdd context --output runtime/context.json
python -m sdd save --state examples/state.json
python -m sdd refresh-check --output runtime/spec-refresh.json
python -m sdd demo --output runtime/acceptance.json
```

输入：`task.json` 中任务、搜索词、必要来源；`specs/*.json` 规格；`business/*.py` 代码；`tests/*.py` 测试。`save` 的 JSON 包含 `completed`、`todo`、`validation`。

输出：JSON 上下文包含规格 ID、真实路径、Python 符号、内容、SHA-256、规格版本、PowerContext 召回结果和下一步动作。DB 使用参数化 LIKE 查询；本作品小数据集采用词项检索，没有向量模型依赖。代码/规格变动未重新导入会报过期索引错误。

`demo` 会从 before 快照重置业务代码，创建独立空 Scope，导入资料并调用 MiniMax；将生成结果放临时目录运行不变的测试，通过后写入业务代码，记录 diff；保存验证结果到 PowerContext，再启动独立 Python 进程召回状态并使用它构造后续上下文；最后验证规格更新。失败会以非零退出，不会伪造成功或回退到参考补丁。模型生成的代码会作为 Python 运行，请在比赛专用环境执行。

## 本地测试与重置

```bash
python -m sdd verify-local
python -B -m unittest -v tests.test_target tests.test_regression
python -B -m unittest discover -s qa -v
python scripts/check_submission.py
python scripts/verify_services.py
```

`verify-local` 在临时副本验证 before/after 两个快照，不调用模型，不代表 MiniMax 参与证明；日志记录命令、退出码、源码 SHA-256 和不变测试 SHA-256。`check_submission.py` 核对提交证据并重跑测试，不需要服务。`verify_services.py` 从新任务空状态开始验证真实 DB 与 PowerContext，需服务但不调用模型。完整模型调用记录在 `evidence/`。

重置业务：将 `fixtures/before/tickets.py` 复制到 `business/tickets.py`，再执行 `python -m sdd import`。再次运行 `demo` 会新建空任务 Scope；不要求删除旧状态。`refresh-check` 会真正修改规格文本、重新导入并检查新标记，最后恢复文件并重新导入。

## 提交

参见 `SUBMISSION.md`、`docs/VALIDATION.md`、`docs/TECHNICAL.md`。必须把真实运行后的脱敏 `runtime` 证据复制进 `evidence/live/` 并提交，运行目录本身被忽略。不提交模型私有推理、数据库密码、API Key 或本机虚拟环境。API Key 不由评审重新生成相同补丁；评审可核对记录与差异，再执行相同测试。

限制：仅面向单项目串行任务，LIKE 检索对大仓库性能有限；没有生产级多租户权限与并发索引切换。PowerContext Windows 支持为实验状态。首次安装服务依赖较多，需网络或预先准备依赖包。

来源：业务工程和上下文代码为本作品新建；数据库与 PowerContext API 用法参考 [seekdb](https://github.com/oceanbase/seekdb)、[PowerContext API quickstart](https://powercontext.oceanbase.io/en/docs/develop/api-quickstart/)、[MiniMax OpenAI API](https://platform.minimax.io/docs/api-reference/text-openai-api)。比赛空目录基线保持不变。
