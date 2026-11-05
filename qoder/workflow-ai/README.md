# WorkFlow AI - 智能工作日志与周报助手

基于 PowerContext 的智能工作日志管理与周报生成工具，帮助团队和个人高效记录、检索和总结工作内容。

## 项目简介

WorkFlow AI 解决的核心痛点：
- **工作记录分散**：日常工作记录散落在各处，难以统一管理和检索
- **周报撰写耗时**：每周需要手动整理工作内容，耗时且容易遗漏
- **历史工作难追溯**：无法快速找到过去某项工作的详细信息

本项目通过 PowerContext 的 Memory 能力实现工作日志的语义存储和智能检索，让工作记录更有价值。

## 核心功能

| 功能 | 说明 | PowerContext 作用 |
|------|------|-------------------|
| 工作日志管理 | 创建、查看、编辑、删除工作日志 | Memory 存储日志内容，支持语义检索 |
| 语义搜索 | 自然语言搜索工作记录 | Memory Search 实现语义匹配 |
| 周报生成 | 自动生成结构化周报 | Context Prepare 汇总工作上下文 |
| 智能问答 | 自然语言查询工作历史 | Memory Search + 本地规则引擎 |

## 技术栈

- **后端**: Python 3.11+ / FastAPI / aiosqlite
- **前端**: HTML5 / CSS3 / Vanilla JavaScript
- **AI 上下文**: PowerContext (HTTP API)
- **部署**: Qoder Sites

## 快速开始

### 1. 安装 PowerContext

```bash
# 使用 uv 安装
uv tool install --force "powercontext[cli,server]==1.5.0"

# 初始化配置
powercontext config init --language zh --output .env

# 启动 PowerContext 服务
powercontext server run --env-file .env
```

### 2. 配置项目

```bash
# 复制环境变量配置
cp .env.example .env

# 编辑 .env 文件，配置 PowerContext 连接信息
# POWERCONTEXT_SERVER_URL=http://localhost:18080
# POWERCONTEXT_API_TOKEN=your_token
# POWERCONTEXT_SCOPE_ID=workflow-ai-scope
```

### 3. 安装依赖并启动

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 启动后端服务
cd backend
python main.py

# 访问 http://localhost:8000
```

### 4. 通过 Qoder Sites 发布

在 Qoder 中使用 Sites 功能发布项目网站，设置可见范围为「任何人都可访问」。

## 项目结构

```
workflow-ai/
├── backend/
│   ├── main.py              # FastAPI 主应用
│   ├── models.py            # 数据模型
│   ├── database.py          # SQLite 数据库操作
│   ├── powercontext_client.py  # PowerContext API 客户端
│   └── config.py            # 配置管理
├── frontend/
│   ├── index.html           # 主页面
│   ├── style.css            # 样式
│   └── app.js               # 前端逻辑
├── requirements.txt         # Python 依赖
├── .env.example             # 环境变量示例
└── README.md                # 项目说明
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/work-logs` | POST | 创建日志 |
| `/api/work-logs` | GET | 获取日志列表 |
| `/api/work-logs/{id}` | GET | 获取单条日志 |
| `/api/work-logs/{id}` | PUT | 更新日志 |
| `/api/work-logs/{id}` | DELETE | 删除日志 |
| `/api/search` | POST | 语义搜索 |
| `/api/weekly-report` | POST | 生成周报 |
| `/api/chat` | POST | 智能问答 |

## PowerContext 集成说明

### Memory 存储

每条工作日志创建时，自动通过 `POST /v1/memory/remember` 存入 PowerContext：

```python
await powercontext_client.store_work_log_memory(
    log_id, title, content, category, tags, date
)
```

存储的内容包含结构化元数据（分类、标签、日期），支持后续语义检索。

### 语义搜索

搜索时通过 `POST /v1/memory/search` 进行语义匹配：

```python
result = await powercontext_client.search_work_logs(query, limit=10)
```

返回与查询语义最相关的工作记录，支持自然语言查询。

### 上下文准备

生成周报时通过 `POST /v1/context/prepare` 汇总工作上下文：

```python
context = await powercontext_client.build_weekly_context(logs)
```

将指定时间范围内的工作记录组织为结构化上下文。

## 验证样例

### 样例 1：创建并搜索工作日志

1. 启动服务后访问 http://localhost:8000
2. 点击「+ 新增日志」，创建以下日志：
   - 标题：完成用户登录模块开发
   - 内容：实现了 JWT 认证、OAuth2 集成、登录页面 UI
   - 分类：开发
   - 标签：后端, 认证, JWT
3. 切换到「语义搜索」标签，输入"认证相关的工作"
4. 应能看到刚才创建的日志出现在搜索结果中

### 样例 2：生成周报

1. 创建多条不同日期的工作日志
2. 切换到「周报生成」标签
3. 选择日期范围（包含已创建日志的日期）
4. 点击「生成周报」
5. 应能看到结构化的周报，包含统计信息和详细工作内容

### 样例 3：智能问答

1. 确保已有若干工作日志
2. 切换到「智能问答」标签
3. 输入"这周做了多少工作？"
4. 应能看到工作统计回复

## 开发记录

本项目完全在 Qoder 中开发完成，主要开发环节：

1. **需求分析**：通过 Qoder 分析比赛要求，确定项目方向
2. **架构设计**：Qoder 协助设计前后端分离架构
3. **后端开发**：Qoder 生成 FastAPI 后端代码、数据模型、数据库操作
4. **PowerContext 集成**：Qoder 协助编写 PowerContext HTTP API 客户端
5. **前端开发**：Qoder 生成响应式前端界面和交互逻辑
6. **测试调试**：Qoder 协助排查和修复问题

## 许可证

Apache 2.0
