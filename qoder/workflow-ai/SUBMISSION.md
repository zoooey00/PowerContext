# WorkFlow AI 提交材料

## 一、项目网站网址

（通过 Qoder Sites 发布后填写）

## 二、代码仓库

https://github.com/zoooey00/PowerContext

项目位于 `qoder/workflow-ai/` 目录

## 三、Qoder 账号 UID

（请填写你的 Qoder 账号 UID）

## 四、运行说明

### 环境要求

- Python 3.11+
- PowerContext 1.5.0（可选，用于语义搜索增强）

### 安装步骤

1. 克隆仓库
```bash
git clone https://github.com/zoooey00/PowerContext.git
cd PowerContext/qoder/workflow-ai
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量（可选）
```bash
cp .env.example .env
# 编辑 .env 配置 PowerContext 连接信息
```

4. 启动服务
```bash
# Windows
start.bat

# Linux/Mac
chmod +x start.sh
./start.sh
```

5. 访问 http://localhost:8000

### PowerContext 部署（可选）

```bash
# 安装 PowerContext
uv tool install --force "powercontext[cli,server]==1.5.0"

# 初始化配置
powercontext config init --language zh --output .env

# 启动服务
powercontext server run --env-file .env
```

## 五、验证样例

### 样例 1：创建工作日志并搜索

**初始数据**：无

**操作步骤**：
1. 启动服务，访问 http://localhost:8000
2. 点击「+ 新增日志」
3. 填写：
   - 标题：完成用户登录模块开发
   - 内容：实现了 JWT 认证、OAuth2 集成、登录页面 UI
   - 分类：开发
   - 标签：后端, 认证, JWT
   - 日期：今天
4. 点击保存
5. 切换到「语义搜索」标签
6. 输入"认证相关的工作"
7. 点击搜索

**预期结果**：
- 日志创建成功，显示在日志列表中
- 搜索结果中找到刚才创建的日志

**PowerContext 作用记录**：
- 创建日志时，自动调用 `POST /v1/memory/remember` 存储到 PowerContext
- 搜索时，调用 `POST /v1/memory/search` 进行语义匹配
- 如 PowerContext 未运行，自动降级为本地关键词匹配

### 样例 2：生成周报

**初始数据**：创建 3-5 条不同日期的工作日志

**操作步骤**：
1. 创建多条工作日志（不同日期、不同分类）
2. 切换到「周报生成」标签
3. 选择日期范围（包含已创建日志的日期）
4. 选择报告风格
5. 点击「生成周报」

**预期结果**：
- 显示工作统计（记录数、活跃天数）
- 显示摘要信息
- 显示结构化周报内容

**PowerContext 作用记录**：
- 调用 `build_weekly_context` 汇总工作上下文
- 如 PowerContext 未运行，使用本地数据生成

### 样例 3：智能问答

**初始数据**：已有若干工作日志

**操作步骤**：
1. 切换到「智能问答」标签
2. 输入"这周做了多少工作？"
3. 点击发送

**预期结果**：
- 返回工作统计信息

**PowerContext 作用记录**：
- 调用 `POST /v1/memory/search` 搜索相关工作记录
- 结合本地规则引擎生成回答

## 六、Qoder 开发记录

### 开发环节说明

1. **需求分析**（Qoder 完成）
   - 分析比赛要求，确定项目方向
   - 确定核心功能：工作日志管理、语义搜索、周报生成、智能问答

2. **架构设计**（Qoder 完成）
   - 设计前后端分离架构
   - 确定技术栈：FastAPI + SQLite + PowerContext
   - 设计数据库模型和 API 接口

3. **后端开发**（Qoder 完成）
   - 生成 FastAPI 主应用代码
   - 实现数据模型和数据库操作
   - 编写 PowerContext HTTP API 客户端
   - 实现周报生成和智能问答逻辑

4. **前端开发**（Qoder 完成）
   - 生成响应式 HTML 页面
   - 实现 CSS 样式和交互逻辑
   - 实现四个功能模块的前端界面

5. **测试调试**（Qoder 完成）
   - 测试所有 API 端点
   - 修复导入路径问题
   - 验证前后端集成

### Qoder 账号 UID

（请填写你的 Qoder 账号 UID）

## 七、技术结合说明

### PowerContext 集成

**使用方式**：HTTP API

**核心功能**：
1. **Memory 存储**：每条工作日志创建时，通过 `POST /v1/memory/remember` 存入 PowerContext，包含结构化元数据（分类、标签、日期）

2. **语义搜索**：搜索时通过 `POST /v1/memory/search` 进行语义匹配，返回与查询语义最相关的工作记录

3. **上下文准备**：生成周报时通过 `POST /v1/context/prepare` 汇总工作上下文

**降级策略**：如 PowerContext 服务不可用，自动降级为本地关键词匹配，确保基本功能可用

**代码位置**：
- `backend/powercontext_client.py` - PowerContext API 客户端
- `backend/main.py` - API 端点中调用 PowerContext

## 八、项目结构

```
workflow-ai/
├── backend/
│   ├── main.py              # FastAPI 主应用
│   ├── models.py            # 数据模型
│   ├── database.py          # SQLite 数据库操作
│   ├── powercontext_client.py  # PowerContext API 客户端
│   ├── config.py            # 配置管理
│   └── __init__.py
├── frontend/
│   ├── index.html           # 主页面
│   ├── style.css            # 样式
│   └── app.js               # 前端逻辑
├── requirements.txt         # Python 依赖
├── .env.example             # 环境变量示例
├── .gitignore
├── start.bat                # Windows 启动脚本
├── start.sh                 # Linux/Mac 启动脚本
└── README.md                # 项目说明
```

## 九、使用效果（鼓励提交）

（如有真实用户使用，请在此补充使用数据）
