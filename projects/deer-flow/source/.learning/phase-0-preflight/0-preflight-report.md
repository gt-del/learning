# Phase 0：预侦察报告

## ✅ 仓库分类

**分类**：🎯 **workflow-first + orchestration-first**（不是传统code-first）

**理由**：

| 维度 | 观察 | 结论 |
|------|------|------|
| 运行时核心 | LangGraph（`langgraph.json` → `make_lead_agent`） | 不是HTTP路由驱动，而是图编排驱动 |
| 数据流 | 任务进入 → LangGraph状态机 → middleware链 → 输出 | workflow明确，不是单次API调用 |
| 扩展方式 | 通过 skills、subagents、tools、middlewares 注册 | 不是模块化，而是能力编排化 |
| 控制逻辑 | lead_agent 是"心脏"，FastAPI gateway 是"血管" | agent逻辑优先，API其次 |

---

## 🫀 主控制平面所在

### 第一层：LangGraph Agent Graph（最核心 🎯）

**位置**：
- [backend/packages/harness/deerflow/agents/lead_agent/agent.py](backend/packages/harness/deerflow/agents/lead_agent/agent.py) - `make_lead_agent()`
- [backend/langgraph.json](backend/langgraph.json) - 定义了唯一的、最顶层的图："lead_agent"

**职责**：
- 定义 agent 的核心状态机（ThreadState）
- 组织 10+ 个 middleware 的**执行顺序**
- 实现长期内存、工具、沙箱的生命周期管理

**其他控制层**：

1. **FastAPI Gateway**（`app/gateway/app.py`）- 入口，但不是主控   

   - 职责：REST API 路由、请求分发
   - 不是主控制平面，是HTTP适配层

2. **Middleware Chain**（`agents/middlewares/`）- 流量控制    

   - 10个中间件形成一条"质量流水线"
   - 每个 middleware 是独立的能力单元

---

## 🔗 主要扩展点（5个核心扩展轴）

### 1. **Skills** - 最常用的扩展点
- **位置**：`skills/public/` @ `backend/packages/harness/deerflow/skills/`
- **特征**：Agent 能做什么 → manifest.json + code
- **扩展方式**：
  - 放 skill folder → 声明 manifest → Agent 自动发现
  - 例子：`skills/public/deep-research/`、`skill-creator/`
- **限制**：skill 内部是"黑盒"，agent 通过定义的 tool 调用
- **📌 价值**：最常见的新功能入口

### 2. **Subagents** - 委托执行
- **位置**：`deerflow/subagents/`（registry + executor）
- **特征**：让 lead_agent 创建任务，后台执行（可迁移）
- **例子**：general-purpose / bash 专用子代理
- **🔑 关键**：`SubagentExecutor.execute()` 是任务入口

### 3. **Sandbox** - 沙箱提供商
- **位置**：`deerflow/sandbox/` + config.yaml
- **特征**：抽象了 local / docker / provisioner（Kubernetes）三种模式
- **扩展方式**：实现 `SandboxProvider` 接口，在 config 中注册
- **📌 价值**：核心安全隔离机制

### 4. **Tools** - 原始API暴露
- **位置**：`deerflow/tools/builtins/`（内置）+ MCP 集成
- **特征**：
  - 内置：present_files, ask_clarification, view_image
  - 扩展：通过 MCP 动态加载
- **限制**：工具列表是 agent 系统提示的一部分

### 5. **Middlewares** - 流水线插入点
- **位置**：`agents/middlewares/` (10个模块)
- **特征**：每个 middleware 拦截 agent 的输出，做专门处理
- **📌 价值**：质量门禁 / 风险控制就体现在这里
- **例子**：GuardrailsMiddleware, FileUploadValidationMiddleware

---

## 🎯 初始证据切入点（优先级排序）

按"最快理解系统运作逻辑"的顺序：

| 优先级 | 证据 | 为什么看 | 预计时间 |
|--------|------|----------|---------|
| 🔴 **高** | [backend/CLAUDE.md](backend/CLAUDE.md) | 项目方自写的架构概览 + 命令大全 | 10 分钟 |
| 🔴 **高** | [backend/langgraph.json](backend/langgraph.json) | 系统的"大脑"定义 | 1 分钟 |
| 🔴 **高** | [backend/packages/harness/deerflow/agents/thread_state.py](backend/packages/harness/deerflow/agents/thread_state.py) | ThreadState 是整个状态机的"承载体" | 5 分钟 |
| 🟠 **中** | [backend/packages/harness/deerflow/agents/lead_agent/agent.py](backend/packages/harness/deerflow/agents/lead_agent/agent.py)（首 100 行） | 看 make_lead_agent 的结构 | 10 分钟 |
| 🟠 **中** | `agents/middlewares/` 目录列表 + 各 middleware 的 docstring | 质量流水线长什么样 | 10 分钟 |
| 🟠 **中** | [config.example.yaml](config.example.yaml) | 系统有多少配置旋钮（代表可扩展性） | 5 分钟 |
| 🟡 **低** | `skills/public/` 几个示例 | Skill 的最小结构 | 5 分钟 |
| 🟡 **低** | `tests/test_client.py` + `test_channels.py` | 从测试反推"哪些行为是不可破坏的" | 10 分钟 |

---

## 📋 30分钟侦察顺序

### 🕐 第 0-5 分钟：建立全局观
1. 再读一遍 [README.md](README.md) 开头（只看 "What is DeerFlow" 部分）
2. 注意关键词：super agent harness / sub-agents / sandbox / skills / memory

### 🕐 第 5-15 分钟：找到"心脏"
1. 打开 [backend/langgraph.json](backend/langgraph.json) → 确认 `make_lead_agent`
2. 看 [backend/packages/harness/deerflow/agents/thread_state.py](backend/packages/harness/deerflow/agents/thread_state.py)：所有状态存在什么里面？
3. 结论：**lead_agent 是1个大的图，ThreadState 是整个数据载体**

### 🕐 第 15-25 分钟：理解中间层
1. 查看 [backend/packages/harness/deerflow/agents/middlewares/](backend/packages/harness/deerflow/agents/middlewares/) 里有什么
2. 每个 middleware 的名字是什么？（不用看代码，只看 `__init__.py` 或 ls）
3. 结论：**10 个 middleware = 10 个质量门禁 + 能力扩展点**

### 🕐 第 25-30 分钟：理解扩展轴
1. ls [skills/public/](skills/public/) → 看 skill 的多样性
2. 看 [backend/packages/harness/deerflow/sandbox/](backend/packages/harness/deerflow/sandbox/)，理解沙箱三层（local/docker/provisioner）
3. 结论：**这个系统的可扩展性在于 skills + sandbox + subagents，不是代码改动**

---

## 🔍 仓库复杂性在哪里（需要格外注意）

### ⚠️ 复杂点 1：中文用户的陷阱
- README / docs / CLAUDE.md 都有中文、日文、俄文版本
- **建议**：统一看英文版或官方文档，避免翻译偏差

### ⚠️ 复杂点 2：Sandbox 的三层架构
```
ThreadState 
   ↓
SandboxMiddleware 
   ↓
SandboxProvider（local | docker | provisioner）
```
- 这里从**逻辑隔离** 到 **物理隔离** 的过程不简单
- 如果是学 local 模式，要理解为什么要有这层抽象

### ⚠️ 复杂点 3：LangGraph 不等于"单个 agent"
- DeerFlow = lead_agent（主要编排）+ subagents（后台任务）+ 10 个 middleware
- 新手容易误认为 LangGraph 就整个系统，实际上只是一层

### ⚠️ 复杂点 4：Config 驱动的模式选择
- 同一份代码，通过 `config.yaml` 选择是 local|docker|provisioner
- 这需要对 **dependency injection** 有理解

### ⚠️ 复杂点 5：FastAPI gateway 不是主角
- 很多人第一反应是从 `app/gateway/` 开始学
- **错误**：gateway 只是把 LangGraph 包装成 HTTP
- **正确**：学 LangGraph 部分的逻辑，gateway 只是适配层

---

## 🎓 预测结论：为什么是 Workflow-First？

| 特征 | Code-First | Workflow-First | DeerFlow |
|------|-----------|-----------------|----------|
| 核心单位 | 类 / 函数 | 状态 / 流 | ✅ ThreadState + middleware chain |
| 编程模式 | OOP / FP | 状态机 / graph | ✅ LangGraph |
| 扩展方式 | 继承 / 组合 | 插件注册 | ✅ Skills / subagents / middleware |
| 测试方式 | unit test | behavior test | ✅ 看测试也是按"场景"写的 |
| 控制流 | 显式调用 | 隐式调度 | ✅ middleware 自动执行 |

**🔑 关键证据**：如果改一行业务逻辑，应该改 skill 的 manifest 或 agent 的 middleware，而不是改 harness 代码。

---

## 🗂️ 下一步（进入 Phase 1）

一旦你同意"这是 workflow-first"的分类，Phase 1 会问：

1. **整个 workflow 的状态有哪些？**（ThreadState 里现在有啥？）
2. **这些状态之间怎么流转？**（10 个 middleware 执行顺序）
3. **最值得学的 top 20% 设计是什么？**
4. **哪些设计代价最大？**

---

**预侦察完成** ✅。信号待命 📡
