# Phase 1：全局架构地图

## 📍 仓库一句话定位

**DeerFlow 是一个 workflow-first 的 AI 代理编排框架**，通过 LangGraph 驱动的 `lead_agent` 中枢、15 层显式的 middleware 质量流水线、config-driven 的 sandbox 隔离、以及 manifest-based 的 skills 生态，来对复杂 AI 任务进行**有序编排、质量控制和安全隔离**。

---

## 🔄 主状态流（关键路径）

从"任务入场"到"结果返回"的完整状态转移：

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Request Entry                              │
│   HTTP (FastAPI Gateway) / Embedded Client                          │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│   [Init]  ThreadState 初始化 & Sandbox 获取                         │
│   ├─ thread_id, sandbox_id                                         │
│   ├─ workspace_path, uploads_path                                  │
│   └─ 消息历史 (messages from context                               │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│   Lead Agent 第 1 次推理                                            │
│   Model: ChatModel(thinking_enabled, reasoning_effort)             │
│   Tools: skills + subagents + builtins                             │
│   State: ThreadState (messages, sandbox_id, artifacts...)          │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│   [Quality Pipeline]  Middleware Chain (15 层)                       │
│                                                                      │
│   Preprocess:                                                       │
│   ├─ ThreadDataMiddleware        → 初始化 thread_data              │
│   ├─ UploadsMiddleware           → 处理文件上传                     │
│   ├─ DanglingToolCallMiddleware  → 补全缺失的 ToolMessage          │
│   └─ SummarizationMiddleware    → 早期上下文压缩                    │
│                                                                      │
│   Feature:                                                          │
│   ├─ TodoMiddleware             → plan_mode 时启用任务跟踪          │
│   ├─ TokenUsageMiddleware       → 统计 token 成本                  │
│   ├─ TitleMiddleware            → 生成对话标题                      │
│   ├─ MemoryMiddleware           → 队列化长期对话储存                │
│   └─ ViewImageMiddleware        → 视觉模型注入图像细节              │
│                                                                      │
│   Safety & Control:                                                 │
│   ├─ DeferredToolFilterMiddleware → 隐藏工具搜索工具                │
│   ├─ SubagentLimitMiddleware     → 限制并发子任务                   │
│   ├─ LoopDetectionMiddleware     → 检测重复调用循环                 │
│   ├─ SandboxAuditMiddleware      → 沙箱操作审计                     │
│   └─ ToolErrorHandlingMiddleware → tool 异常转为 ToolMessage       │
│                                                                      │
│   Final:                                                            │
│   └─ ClarificationMiddleware     → 最后拦截澄清请求               │
│                                                                      │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│   [Tool Execution]  工具调用                                         │
│   ├─ Skill Tools        → skills/public/* 暴露的功能               │
│   ├─ Subagents        → 后台委托(general-purpose / bash)           │
│   ├─ Builtin Tools      → present_files / ask_clarification        │
│   ├─ MCP Tools         → 动态加载的外部工具                         │
│   └─ Sandbox Execute    → bash/file_ops 在 ThreadState.sandbox     │
│                                                                      │
│   Execution Context:                                                │
│   ├─ sandbox_id       → 隔离执行环境 (local/docker/provis)         │
│   ├─ workspace_path   → 文件系统入口                                │
│   └─ artifacts        → 生成物积累                                  │
│                                                                      │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│   [Agent Loops]  迭代推理                                            │
│   While not terminal_state:                                         │
│   ├─ Model call with updated ThreadState                            │
│   ├─ Middleware chain (again)                                       │
│   ├─ Tool execution (if needed)                                     │
│   └─ Update ThreadState (messages, artifacts, title)                │
│                                                                      │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│   [Cleanup & Output]                                                 │
│   ├─ MemoryMiddleware flush → 长期记忆入库                          │
│   ├─ SandboxMiddleware      → release sandbox_id                    │
│   ├─ artifacts list        → 生成物清单                             │
│   └─ Stream/Return final state                                      │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🧩 5个核心模块

### 1️⃣ **Lead Agent + Middleware Chain**（编排中枢 🫀）

**所在位置**：
- [`backend/packages/harness/deerflow/agents/lead_agent/agent.py`](backend/packages/harness/deerflow/agents/lead_agent/agent.py)
- [`backend/packages/harness/deerflow/agents/middlewares/`](backend/packages/harness/deerflow/agents/middlewares/) (15 individual files)

**职责**：
- 通过 LangGraph 的 `create_agent()` 组织整个编排流程
- 定义 15 层 middleware 的**执行顺序**和**激活条件**
- 管理模型推理的完整生命周期

**关键设计**：
- Middleware 不是可选的装饰器，而是**硬编码的质量流水线**
- 每个 middleware 都有显式的依赖和前置条件（见代码注释）
- 特例：`ClarificationMiddleware` 总是最后一个

**数据承载**：ThreadState（见下文）

**✅ 为什么这样设计**：
- Middleware 是一种 **explicit pipeline** 而非「猜谜游戏」
- 新增 middleware 时，开发者必须明确声明它在链中的位置
- 强制思考跨模块之间的**依赖和副作用**

---

### 2️⃣ **ThreadState 数据模型**（数据飞地 🏛️）

**所在位置**：
- [`backend/packages/harness/deerflow/agents/thread_state.py`](backend/packages/harness/deerflow/agents/thread_state.py)

**数据结构**：
```python
ThreadState (extends LangChain AgentState):
├─ messages[]           # 对话历史（来自 AgentState）
├─ sandbox              # { sandbox_id: str | None }
├─ thread_data          # { workspace_path, uploads_path, outputs_path }
├─ title                # 生成的对话标题（TitleMiddleware）
├─ artifacts[]          # 生成物路径列表（merge_artifacts reducer）
├─ todos[]              # 任务清单（TodoMiddleware in plan_mode）
├─ uploaded_files[]     # 文件元数据（UploadsMiddleware）
└─ viewed_images{}      # 图像缓存（ViewImageMiddleware）
```

**关键特性**：
- **单一真值源**（Single Source of Truth）：所有状态在这一个对象里
- **Reducer 函数**：`merge_artifacts`, `merge_viewed_images` 自定义合并策略而非简单覆盖
- **NotRequired 字段**：使用 TypedDict 的 NotRequired 表示可选字段，类型安全

**✅ 为什么这样设计**：
- LangGraph 要求显式定义状态 schema
- ThreadState 是整个 middleware 链的"共享通道"
- 每个 middleware 可以安全地读写特定字段而不破坏其他字段

---

### 3️⃣ **Sandbox 隔离系统**（安全执行 🔒）

**所在位置**：
- [`backend/packages/harness/deerflow/sandbox/`](backend/packages/harness/deerflow/sandbox/)

**三层架构**：
```
[ThreadState.sandbox_id]
        ↓
[Abstract Sandbox (interface)]
  ├─ execute_command(cmd) → str
  ├─ read_file(path) → str
  ├─ write_file(path, content)
  ├─ list_dir(path) → [str]
  └─ str_replace_file(path, old, new)
        ↓
[SandboxProvider (factory)]
  └─ acquire(thread_id) → sandbox_id
  └─ get(sandbox_id) → Sandbox instance
  └─ release(sandbox_id)
        ↓
[Concrete Implementations]
├─ LocalSandboxProvider    (local filesystem)
├─ DockerSandboxProvider   (Docker container)
└─ ProvisionerProvider     (Kubernetes pod)
```

**职责**：
- 提供统一的文件和命令执行接口
- 根据 `config.yaml` 选择具体实现（local | docker | provisioner）
- 管理沙箱的生命周期（acquire → use → release）

**关键设计**：
- **Strategy Pattern**：同一个接口，多种实现
- **Dependency Injection**：config 驱动的实现选择
- **Per-Thread 隔离**：每个 thread_id 对应独立的沙箱

**✅ 为什么这样设计**：
- 本地开发用 local，生产用 docker，云端用 provisioner，**无需改代码**
- 沙箱是安全的核心—显式的抽象层强制所有执行都经过这一层

---

### 4️⃣ **Skills 生态系统**（能力注册库 📦）

**所在位置**：
- [`backend/packages/harness/deerflow/skills/`](backend/packages/harness/deerflow/skills/)
- [`skills/public/`](skills/public/) (commitment)
- [`skills/custom/`](skills/custom/) (gitignored)

**Skill 结构**：
```
skills/public/
├─ deep-research/
│  ├─ SKILL.md          # Markdown 格式的 skill definition
│  ├─ manifest.json     # 元数据（name, description, tools）
│  ├─ __init__.py       # 工具函数
│  └─ ...
├─ skill-creator/
├─ data-analysis/
└─ ...
```

**Skill 的生命周期**：
1. **发现**：`load_skills()` 扫描 `skills/public/` 和 `skills/custom/`
2. **注册**：从 manifest.json 提取工具定义
3. **绑定**：工具被添加到 agent 的系统提示和工具列表
4. **执行**：通过 Subagent 或直接调用执行

**Skill 数据模型**：
```python
@dataclass
class Skill:
    name: str           # e.g., "deep-research"
    description: str    # Agent 看到的描述
    license: str | None
    skill_dir: Path     # 本地引用
    skill_file: Path    # SKILL.md 路径
    category: str       # 'public' | 'custom'
    enabled: bool
```

**✅ 为什么这样设计**：
- **Manifest-based** 而非代码侵入：新增 skill 不需要改 harness 代码
- **自动发现**：添加文件夹 → 自动归入工具箱
- **容器友好**：skill 可以挂载到容器 `/mnt/skills/`

---

### 5️⃣ **Subagents + Memory 系统**（后台执行与记忆）

**位置**：
- Subagents: [`backend/packages/harness/deerflow/subagents/`](backend/packages/harness/deerflow/subagents/)
- Memory: [`backend/packages/harness/deerflow/agents/memory/`](backend/packages/harness/deerflow/agents/memory/)

#### **Subagents**（后台委托）

**职责**：
- 让 lead_agent 创建后台任务而非阻塞等待
- 在独立线程池执行，支持超时和取消

**内置 Subagents**：
- `general-purpose`：通用 AI 代理
- `bash`：纯线性脚本执行

**执行模型**：
```
Lead Agent 调用 "execute_async(task)"
    ↓
SubagentExecutor.execute_async()
    ├─ 立即返回 task_id
    └─ 后台线程执行
        ├─ 创建独立的 agent instance
        ├─ 设置 tools 过滤（allowed/disallowed）
        ├─ 运行循环（max_turns, timeout_seconds）
        └─ 存储结果到 _background_tasks{}

Lead Agent 后续可以调用 "check_task_status(task_id)"
    ↓
查询 _background_tasks 获取进度/结果
```

#### **Memory 系统**（长期记忆）

**职责**：
- 从每个对话提取关键信息
- 存储到长期记忆库供后续对话查询

**流程**：
```
[MemoryMiddleware]
├─ 在 TitleMiddleware 之后启动
├─ 收集对话信息（title, messages）
├─ 入队到 MemoryQueue
└─ 异步处理（存储到配置的后端）

存储后端可配置：
├─ Memory Embedding (向量化)
├─ Persistence (LanceDB, vector DB等)
└─ Retrieval (semantic search)
```

**✅ 为什么这样设计**：
- Subagent 执行与 lead_agent 解耦，适合长运行任务
- Memory 异步处理，不阻塞主流程
- Config-driven 存储后端，支持多种持久化方案

---

## 🎯 Top 20% 核心设计（最值得学习的部分）

### 🏆 Design 1：Middleware Chain 作为显式质量流水线

| 方面 | 传统 | **DeerFlow** |
|------|------|------------|
| 质量控制 | Implicit (随机编用各种中间件) | ✅ Explicit (15 层流水线) |
| 依赖管理 | 代码隐含 | ✅ 注释说明每个 middleware 的前置条件 |
| 新增功能 | 添加参数或条件分支 | ✅ 新增 middleware，声明在链中的位置 |
| 调试难度 | 高（需要跟踪隐含的流程） | ✅ 低（流程在代码中明确可见） |

**学到的**：
- 将隐含的流程**显式化**有助于代码可维护性
- Pipeline 模式强制开发者思考** Cross-Cutting Concerns**

---

### 🏆 Design 2：ThreadState 作为单一飞地

| 方面 | 传统 | **DeerFlow** |
|------|------|------------|
| 状态管理 | 分散在各个对象 | ✅ 集中在 ThreadState TypedDict |
| 数据一致性 | 需要同步逻辑 | ✅ Reducer 函数自动合并 |
| 中间件通信 | 显式传参 | ✅ 隐式通过 ThreadState 读写 |
| LangGraph 兼容 | N/A | ✅ 原生支持 LangGraph 状态管理 |

**学到的**：
- 将所有线程级别的状态集中在一个数据结构中，而不是分散在对象树中
- 使用 TypedDict 而非 Dataclass 以保留 LangGraph 兼容性

---

### 🏆 Design 3：Config-Driven 沙箱模式

| 方面 | 传统 | **DeerFlow** |
|------|------|------------|
| 环境差异 | 代码分支（if local: ... elif docker: ...) | ✅ Config 选择实现 |
| 扩展性 | 新环境需要改代码 | ✅ 实现 SandboxProvider 接口即可 |
| 测试覆盖 | 难以测试所有分支 | ✅ 可模拟不同配置 |
| 部署风险 | 代码改动多 | ✅ 统一代码，配置不同 |

**学到的**：
- 用 Dependency Injection（通过 config）代替条件分支
- 使用 Abstract Base Class + Factory Pattern 支持多实现

---

### 🏆 Design 4：Manifest-Based Skills Discovery

| 方面 | 传统 | **DeerFlow** |
|------|------|-----------|
| 能力扩展 | 代码注册（改 harness 代码）| ✅ 文件系统注册（新建文件夹）|
| 工具列表 | 代码中硬编码 | ✅ manifest.json 声明 |
| 版本管理 | 代码版本 | ✅ Skill 版本独立 |
| 用户自定义 | 需要分叉仓库 | ✅ skills/custom/ gitignored |

**学到的**：
- 将能力声明**分离**出来为静态文件（manifest.json）
- 利用文件系统自动发现代替中央注册表

---

### 🏆 Design 5：Subagent 异步执行模型

| 方面 | 传统 | **DeerFlow** |
|------|------|-----------|
| 长运行任务 | lead_agent 阻塞等待 | ✅ 立即返回 task_id |
| 资源利用 | 单线程顺序执行 | ✅ 线程池并发执行 |
| 用户体验 | 卡顿（阻塞） | ✅ 可询问进度（非阻塞） |
| 超时管理 | 手工管理 | ✅ SubagentConfig.timeout_seconds |

**学到的**：
- 长运行任务与主流程解耦，提升用户体验
- 使用线程池而非递归或顺序执行

---

## 🚫 现在可以暂时忽略

为了加快学习速度，这些可以先跳过：

| 部分 | 原因 | 何时看 |
|------|------|--------|
| Channel 集成（`app/channels/`） | IM 平台适配层，不涉及核心架构 | Phase 6（范式映射）后 |
| Frontend 代码 | 前端不涉及架构核心 | 学完后端后可选 |
| 每个 Skill 的具体实现 | 只需理解 manifest + entry point | 需要扩展时 |
| LangSmith 集成 | 可观测性，不涉及核心流程 | 生产部署时 |
| MCP 细节 | 工具集成协议，与架构正交 | 需要集成新工具时 |

---

## 📚 推荐阅读顺序（按学习价值排序）

### 🟥 **第 1 层：数据模型（理解什么流动）**
1. [thread_state.py](backend/packages/harness/deerflow/agents/thread_state.py) — ThreadState 详细定义
2. [Skill type 定义](backend/packages/harness/deerflow/skills/types.py) — Skill 数据结构
3. [SubagentConfig](backend/packages/harness/deerflow/subagents/config.py) — Subagent 配置schema

### 🟧 **第 2 层：核心编排（理解怎样流）**
4. [lead_agent/agent.py](backend/packages/harness/deerflow/agents/lead_agent/agent.py) — make_lead_agent() 函数（重点看 _build_middlewares）
5. [SandboxProvider 接口](backend/packages/harness/deerflow/sandbox/sandbox_provider.py) — 沙箱抽象
6. [SubagentExecutor](backend/packages/harness/deerflow/subagents/executor.py) — 后台执行引擎（首 200 行）

### 🟨 **第 3 层：质量控制（理解怎样验证）**
7. [middlewares/ 目录列表](backend/packages/harness/deerflow/agents/middlewares/) — 15 个 middleware 的清单
   - 逐个阅读 docstring（不需要看全部代码，只看 class docstring）
8. [config.yaml 范例](config.example.yaml) — 理解系统有多少配置旋钮

### 🟩 **第 4 层：扩展生态（理解怎样扩展）**
9. [skills/ 类型定义](backend/packages/harness/deerflow/skills/types.py) — Skill 的生命周期
10. [skills/public/ 几个范例](skills/public/) — 看 2-3 个 skill 的 manifest.json

### 🟦 **第 5 层：网关适配（理解怎样进出）**
11. [app/gateway/ 快速扫描](backend/app/gateway/) — FastAPI 路由结构（不需要深入）

---

## 🎓 检查清单（验证理解）

- [ ] ThreadState 有哪些字段？各字段的职责是什么？
- [ ] 15 个 middleware 按什么顺序执行？为什么前后有依赖？
- [ ] Sandbox 的三层结构分别是什么？
- [ ] Skill 是如何被发现和注册的？
- [ ] Subagent 如何实现后台执行的？
- [ ] Config 如何驱动沙箱模式选择？

---

## 📌 关键设计的代价

| 设计点 | 优点 | 代价 |
|-------|------|------|
| 显式 Middleware 链 | 可维护性高 | 添加新功能需要修改链顺序逻辑 |
| 单一 ThreadState | 状态一致性好 | 字段增多时 schema 会变复杂 |
| Config-Driven Sandbox | 部署灵活 | 需要测试所有配置组合 |
| Manifest-Based Skills | 扩展容易 | skill 版本管理变复杂 |
| Async Subagents | 用户体验好 | 需要处理任务超时、取消、结果查询 |

---

## 🗺️ 系统全景图

```
                    ┌────────────────────────────────┐
                    │      External Input             │
                    │  (HTTP / Embedded Client)       │
                    └────────────┬───────────────────┘
                                 │
                    ┌────────────▼───────────────────┐
                    │   FastAPI Gateway (Adapter)    │
                    │   (REST routes)                │
                    └────────────┬───────────────────┘
                                 │
        ┌────────────────────────▼──────────────────────────┐
        │                 LangGraph Runtime                │
        │ ┌──────────────────────────────────────────────┐ │
        │ │   Lead Agent (LangGraph Graph)              │ │
        │ ├──────────────────────────────────────────────┤ │
        │ │  Model: ChatModel(thinking, reasoning)      │ │
        │ │  Tools: merge(skills + subagents + builtin) │ │
        │ │  State: ThreadState (single source of truth)│ │
        │ ├──────────────────────────────────────────────┤ │
        │ │   Middleware Pipeline (15 layers)           │ │
        │ │  ┌─────────────────────────────────────────┐│ │
        │ │  │ thread_data → uploads → dangling_call  ││ │
        │ │  │ → todo → title → memory → view_image   ││ │
        │ │  │ → deferred_filter → subagent_limit    ││ │
        │ │  │ → loop_detection → clarification       ││ │
        │ │  └─────────────────────────────────────────┘│ │
        │ └──────────────────────────────────────────────┘ │
        └────────────┬───────────────┬────────────────────┘
                     │               │
        ┌────────────▼────┐  ┌──────▼──────────────┐
        │   Tool Exec     │  │  Subagent Pool     │
        ├─────────────────┤  ├────────────────────┤
        │ Skill Tools     │  │ general-purpose    │
        │ Builtin (files) │  │ bash               │
        │ MCP Tools       │  │ [async, timeout]   │
        │ [in Sandbox]    │  └────────────────────┘
        └────────┬────────┘
                 │
        ┌────────▼────────────────────────────┐
        │   Sandbox Provider (Strategy)       │
        ├─────────────────────────────────────┤
        │ ├─ Local (filesystem direct)        │
        │ ├─ Docker (container subprocess)    │
        │ └─ Provisioner (K8s pod)            │
        └────────┬────────────────────────────┘
                 │
        ┌────────▼────────────────────────────┐
        │   Execution & File System           │
        │ bash execute | file read/write      │
        └─────────────────────────────────────┘

┌─────────────────┐       ┌────────────────┐
│  Skills Eco     │       │  Memory Store  │
│ skills/public   │       │  (async queue) │
│ skills/custom   │       │  persist→DB    │
└─────────────────┘       └────────────────┘

┌─────────────────┐       ┌────────────────┐
│  Config.yaml    │       │  Model Catalog │
│  (DI driver)    │       │  (GPT/Claude)  │
└─────────────────┘       └────────────────┘
```

---

## 🔑 关键洞察

1. **这不是传统的 REST 应用**：没有控制器→业务逻辑→数据库的模式。而是 LangGraph 驱动的 Agent 系统。

2. **质量控制是一级公民**：Middleware 不是事后的装饰器，而是系统设计的核心。

3. **配置优于代码**：沙箱、模型、工具、subagent 都通过配置选择，不是代码分支。

4. **能力即资产**：Skill 是一等公民，manifest.json 就是能力的产权证书。

5. **异步是隐含的**：Subagent、Memory 都是后台执行，lead_agent 不阻塞。

---

**✅ Phase 1 完成**。进入 **Phase 2** 时，会详细分析：
- 15 个 middleware 各自在做什么
- ThreadState 的详细字段映射和生命周期
- 每个质量门禁是在防止什么失败模式
