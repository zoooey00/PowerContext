# WorkFlow AI 项目完成指南

## 项目已创建完成

项目位置：`C:\Users\赵美龙\Documents\Qoder\2026-11-05\afd053ae\workflow-ai\`

## 第一步：上传到你的 GitHub 仓库

### 方法 1：手动上传（推荐）

1. 打开你的仓库：https://github.com/zoooey00/PowerContext

2. 切换到 `2026-competition-ecosystem` 分支

3. 点击「Add file」→「Upload files」

4. 将 `workflow-ai` 整个文件夹上传到 `qoder/` 目录下

   最终路径应为：`qoder/workflow-ai/`

5. 提交 commit

### 方法 2：使用 Git 命令行

```bash
# 克隆你的仓库
git clone https://github.com/zoooey00/PowerContext.git
cd PowerContext

# 切换到比赛分支
git checkout 2026-competition-ecosystem

# 复制项目文件到 qoder 目录
mkdir -p qoder
cp -r ../workflow-ai qoder/workflow-ai

# 提交并推送
git add qoder/workflow-ai/
git commit -m "Add WorkFlow AI project for competition"
git push origin 2026-competition-ecosystem
```

## 第二步：通过 Qoder Sites 发布项目网站

1. 打开 Qoder Desktop 应用

2. 点击左侧「Sites」图标

3. 点击「Create Site」

4. 填写站点信息：
   - 站点名称：workflow-ai
   - 描述：智能工作日志与周报助手

5. 上传项目文件：
   - 将 `workflow-ai/frontend/` 目录下的文件上传
   - 注意：Qoder Sites 是静态托管，只能托管前端文件
   - 后端需要单独部署

6. 设置可见范围为「任何人都可访问」

7. 点击「Publish」发布

**重要说明**：
- Qoder Sites 只能托管静态前端文件
- 后端服务（FastAPI）需要单独部署
- 建议将前端部署到 Qoder Sites，后端部署到其他平台（如 Render、Railway 等）
- 或者提供一个演示视频展示完整功能

## 第三步：准备提交材料

### 必须提交的材料

1. **项目网站网址**
   - Qoder Sites 发布后的完整访问网址
   - 确保未登录状态下也能打开

2. **代码仓库地址**
   - https://github.com/zoooey00/PowerContext
   - 分支：2026-competition-ecosystem
   - 项目路径：qoder/workflow-ai/

3. **Qoder 账号 UID**
   - 在 Qoder 应用中查看你的 UID

4. **运行说明**
   - 见 SUBMISSION.md 文件

5. **验证样例**
   - 见 SUBMISSION.md 文件

6. **Qoder 开发记录**
   - 截取 Qoder 开发过程的截图
   - 包含需求分析、编码、调试等环节

### 鼓励提交的材料

- 使用效果数据（如有真实用户使用）
- 用户反馈
- 提效对比数据

## 第四步：提交到测试平台

1. 登录大赛测试平台

2. 进入 Qoder 赛题的提交入口

3. 填写：
   - 项目网站网址
   - 代码仓库地址
   - Qoder 账号 UID

4. 上传其余材料（运行说明、验证样例、开发记录等）

5. 提交前用浏览器无痕窗口打开项目网站，确认可以正常访问

## 项目功能说明

### 核心功能

1. **工作日志管理**
   - 创建、查看、编辑、删除工作日志
   - 支持分类和标签
   - 自动同步到 PowerContext Memory

2. **语义搜索**
   - 自然语言搜索工作记录
   - 基于 PowerContext Memory Search
   - 降级策略：PowerContext 不可用时使用本地关键词匹配

3. **周报生成**
   - 选择日期范围自动生成周报
   - 包含工作统计和摘要
   - 结构化输出

4. **智能问答**
   - 自然语言查询工作历史
   - 基于 PowerContext Memory Search + 本地规则引擎

### PowerContext 集成点

- `POST /v1/memory/remember` - 存储工作日志
- `POST /v1/memory/search` - 语义搜索
- `POST /v1/context/prepare` - 准备上下文（周报生成）

## 本地测试

### 启动后端服务

```bash
cd workflow-ai
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000

### 启动 PowerContext（可选）

```bash
uv tool install --force "powercontext[cli,server]==1.5.0"
powercontext config init --language zh --output .env
powercontext server run --env-file .env
```

## 注意事项

1. **分支要求**：提交时必须基于 `2026-competition-ecosystem` 分支

2. **目录要求**：项目必须放在 `qoder/` 目录下

3. **PowerContext 集成**：必须展示 PowerContext 在项目中的实际作用

4. **网站可访问性**：Qoder Sites 发布的网站必须设置为「任何人都可访问」

5. **配置安全**：不要提交真实的 API Key 或密码，使用占位值

## 提交清单

- [ ] 项目已上传到 GitHub 仓库的 `qoder/workflow-ai/` 目录
- [ ] 代码基于 `2026-competition-ecosystem` 分支
- [ ] Qoder Sites 网站已发布，可见范围为「任何人都可访问」
- [ ] 运行说明文档已准备
- [ ] 验证样例已准备
- [ ] Qoder 开发记录截图已准备
- [ ] Qoder 账号 UID 已获取
- [ ] 提交材料已上传到测试平台

## 联系支持

如有问题，请查看：
- PowerContext 文档：https://powercontext.oceanbase.io/
- Qoder Sites 文档：Qoder 应用内帮助
- 大赛官方文档：https://oceanbase.yuque.com/org-wiki-obtech-vh7w9r/hc3pio/uygu3273xzlrcmrm
