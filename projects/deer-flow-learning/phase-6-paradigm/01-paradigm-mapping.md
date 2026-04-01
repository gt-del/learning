# Phase 6：范式映射（抽象到通用架构）

## 🎯 目标

将 DeerFlow 的具体实现映射回通用的 **Agent 系统范式**，帮助理解：
1. 这个系统哪些是"通用模式"，哪些是"DeerFlow 特有的"
2. 这些模式在其他系统中如何体现
3. 对自己的系统设计有什么启发

---

## 📋 7 种通用 Agent 角色

### 1️⃣ 🤖 Planner - 计划者（决策者）

#### 定义
"如何将一个大任务拆分成多个小任务？"

#### 在 DeerFlow 中的体现

| 组件 | 机制 | 效果 |
|------|------|------|
| LeadAgent | TaskMiddleware 会检查是否需要拆分 | 决定是否进入"Plan Mode" |
| Plan Mode | ReasoningMiddleware + 特殊的 model | 通过推理生成计划，而不是直接执行 |
| TodoMiddleware | 把计划转换为 todo list | 结构化的任务清单 |

#### 代码位置
```python
# backend/packages/harness/deerflow/agents/middlewares/
- task_middleware.py         # 识别任务类型
- reasoning_middleware.py    # 推理生成计划
- todo_middleware.py         # 维护 todo list
```

#### 设计模式
- **决策树**：根据 task complexity 决定是否规划
- **分解策略**：用大模型推理来分解

#### 评估
- ⅆ 什么时候需要计划？（Task 足够复杂时）
- ✗ 什么时候不需要？（简单查询）

---

### 2️⃣ 📋 Decomposer - 分解者

#### 定义
"将计划转换为可执行的子任务"

#### 在 DeerFlow 中的体现

| 组件 | 机制 | 效果 |
|------|------|------|
| TodoMiddleware | 维护 `thread_state.todos` | 清单结构 |
| SubagentMiddleware | 为每个 todo 生成 subagent | 分配执行者 |
| 执行顺序 | 按 todo order | 顺序或并行 |

#### 代码位置
```python
# TodoMiddleware
- 从 model output 中解析 todo
- 转存入 ThreadState.todos
- 标记 done/pending

# SubagentMiddleware
- 检查是否需要 subagent
- 生成合适的 subagent
- 限制 subagent 数量
```

#### 设计模式
- **清单模式**：待办事项列表
- **任务队列**：FIFO 执行

#### 评估
- ✓ 子任务的定义清晰
- ✗ 并行执行能力有限（主要是顺序）
- ? 任务之间的依赖关系如何表达

---

### 3️⃣ ⚙️ Executor - 执行者（工具调用者）

#### 定义
"真正调用工具、执行代码、产生实际结果"

#### 在 DeerFlow 中的体现

| 组件 | 机制 | 效果 |
|------|------|------|
| LangGraph Agent | Tool-use loop | 自动选择和调用工具 |
| SandboxProvider | 隔离执行环境 | 安全地运行代码 |
| SkillSystem | 注册可用工具 | 动态扩展工具库 |
| ToolErrorHandling | 异常处理 | 优雅降级 |

#### 代码位置
```python
# backend/packages/harness/deerflow/
- sandbox/sandbox_provider.py  # 执行隔离
- skills/                      # 工具定义
- middlewares/tool_error_handling_middleware.py
```

#### 设计模式
- **Strategy Pattern**：多种 sandbox provider
- **Plugin Architecture**：skills 即插件
- **Retry + Fallback**：工具失败的容错

#### 评估
- ✓ 工具调用非常灵活（支持任何可执行代码）
- ✓ 隔离保障（沙箱 + 审计）
- ✗ 工具组合能力有限（主要是顺序调用）

---

### 4️⃣ 🔍 Reviewer / Critic - 评论者（验证者）

#### 定义
"检查结果是否满足要求？有没有犯错？"

#### 在 DeerFlow 中的体现

| 组件 | 机制 | 效果 |
|------|------|------|
| LoopDetectionMiddleware | 检测无限循环 | 防止反复失败 |
| DanglingToolCallMiddleware | 检查不完整的 tool call | 防止幽灵工具调用 |
| SandboxAuditMiddleware | 检查危险命令 | 安全审计 |
| ToolErrorHandlingMiddleware | 检查工具输出 | 错误分类和处理 |
| ClarificationMiddleware | 检查理解是否正确 | 向用户确认 |

#### 代码位置
```python
# backend/packages/harness/deerflow/agents/middlewares/
- loop_detection_middleware.py
- dangling_tool_call_middleware.py
- sandbox_audit_middleware.py
- tool_error_handling_middleware.py
- clarification_middleware.py
```

#### 设计模式
- **Quality Gate Pattern**：多层验收
- **Passive Check**：middleware 被动检查
- **Escalation**：发现问题可升级为 hard fail 或 clarification

#### 评估
- ✓ 质量门禁非常完善
- ✓ 对危险操作的防守
- ✗ 对"语义正确性"的评审有限（主要是形式检查）

---

### 5️⃣ ✅ Validator - 校验者

#### 定义
"输出是否符合初始需求？质量是否合格？"

#### 在 DeerFlow 中的体现

| 组件 | 机制 | 效果 |
|------|------|------|
| ArtifactMiddleware | 收集生成物 | 归档最终输出 |
| TitleMiddleware | 自动生成标题 | 对话可检索性 |
| SummarizationMiddleware | 总结关键结果 | 用户快速了解 |
| 用户 UI | 显示 artifacts | 用户最终确认 |

#### 代码位置
```python
# backend/packages/harness/deerflow/agents/middlewares/
- artifact_middleware.py
- title_middleware.py
- summarization_middleware.py
```

#### 设计模式
- **Final Checkpoint**：最后关卡
- **Metadata Enrichment**：添加元数据便于查找
- **Human Review**：返回 UI 让用户验证

#### 评估
- ✓ 自动标题和总结提升可用性
- ✓ Artifacts 集中管理
- ✗ 没有"用户确认后才保存"的工作流

---

### 6️⃣ 🚦 Router / Orchestrator - 路由者（指挥官）

#### 定义
"选择该用哪个执行者？调用顺序？branching logic？"

#### 在 DeerFlow 中的体现

| 组件 | 机制 | 效果 |
|------|------|------|
| LeadAgent | LangGraph 图 | 定义状态转移 |
| 15 层 Middleware | 按顺序执行检查 | 隐式的路由决策 |
| SubagentMiddleware | 决定何时调用 subagent | 动态路由 |
| Model Choice | 根据 task 选择模型 | 功能路由 |

#### 代码位置
```python
# backend/packages/harness/deerflow/agents/
- lead_agent/agent.py         # LeadAgent 构建
- lead_agent/graph.py         # 状态图定义

# backend/langgraph.json       # 图的宣言
```

#### 设计模式
- **State Machine**：明确的状态转移
- **Middleware Chain**：隐式的分支逻辑
- **Policy-based**：根据 config 选择 sandbox/model

#### 评估
- ✓ 状态机设计清晰
- ✓ 中间件非常灵活
- ✗ 显式的条件分支很少（主要通过中间件隐含）

---

### 7️⃣ 🧠 Context / Memory Manager - 内存管理者

#### 定义
"管理执行过程中的信息？长期记忆？中期缓存？"

#### 在 DeerFlow 中的体现

| 组件 | 机制 | 效果 |
|------|------|------|
| ThreadState | 当前执行的所有上下文 | 中期缓存（当前对话） |
| MemoryMiddleware | 保存关键信息到外部存储 | 长期记忆 |
| MemoryQueue | 异步写入记忆 | 不阻塞主循环 |
| ThreadDataState | 工作目录结构 | 文件系统缓存 |

#### 代码位置
```python
# backend/packages/harness/deerflow/
- agents/thread_state.py              # 中期缓存
- agents/middlewares/memory_middleware.py   # 长期记忆
- memory/queue.py              # 异步存储
- models/thread_data_state.py  # 目录缓存
```

#### 设计模式
- **Layered Memory**：
  - L1（热）：ThreadState（内存）
  - L2（温）：MemoryQueue（buffer）
  - L3（冷）：外部数据库
- **Reducer Pattern**：并发合并
- **Async Queue**：不阻塞主流程

#### 评估
- ✓ 分层记忆设计很好
- ✓ ThreadState 并发安全（via Reducer）
- ✗ 外部存储的一致性保证不清楚
- ✗ 长期记忆的检索策略有限

---

## 🎯 DeerFlow 的 Agent 架构模式总结

### 架构：Lead-Agent 驱动的 Middleware Pipeline

```
User Request
    ↓
┌─ LeadAgent ─────────────────────────┐
│  (LangGraph 状态机)                  │
│  ┌─ 初始化                          │
│  │  ThreadDataMiddleware             │ Planner + Decomposer
│  │  MemoryMiddleware                 │
│  │                                  │
│  ├─ 推理 & 规划                      │ Planner
│  │  TaskMiddleware                   │
│  │  ReasoningMiddleware              │
│  │  TodoMiddleware                   │
│  │  ClarificationMiddleware          │ Critic + Router
│  │                                  │
│  ├─ 工具执行 (LangGraph tool loop)  │ Executor
│  │  ToolSelectionMiddleware          │
│  │  SandboxMiddleware                │
│  │  SkillMiddleware                  │
│  │  SandboxAuditMiddleware           │ Critic (安全审计)
│  │  DanglingToolCallMiddleware       │ Critic (形式检查)
│  │                                  │
│  ├─ 后处理                          │
│  │  ToolErrorHandlingMiddleware      │ Critic + Executor
│  │  LoopDetectionMiddleware          │ Critic (防循环)
│  │  SubagentMiddleware               │ Router + Executor
│  │  SubagentLimitMiddleware          │ Router (限流)
│  │                                  │
│  ├─ 收尾                            │
│  │  ArtifactMiddleware               │ Validator
│  │  TitleMiddleware                  │ Validator
│  │  SummarizationMiddleware          │ Validator
│  │  MemoryMiddleware (save)          │ Context Manager
│  │                                  │
│  └─ 返回用户
└──────────────────────────────────────┘
    ↓
User Interface
```

### 关键设计原则

1. **Workflow First**（不是 REST）
   - 状态机驱动，而非请求-响应
   - 支持多轮交互、暂停、恢复

2. **Explicit Pipeline**（不是隐含逻辑）
   - 15 层 middleware 完全可见和可排序
   - 每层职责清晰
   - 依赖文档化

3. **Quality Gates** 作为一等公民
   - 不是"异常处理"，而是"质量检查流水线"
   - Hard fail / Warn / Info 三种级别
   - 防守在前，执行在后

4. **Extensibility by Config**（不是代码分支）
   - Sandbox provider 选择：config 指定
   - Model 选择：config 指定  
   - Skills：manifest 自动发现

5. **Context as Single Source of Truth**
   - ThreadState 是唯一的全局状态
   - Thread-safe（via Reducer）
   - 所有 middleware 通过修改它来通信

---

## 🧭 对其他系统的启示

### 如果我在构建自己的 AI Agent 系统，我会...

✅ **一定做的**
1. 用 state machine（LangGraph / 自己的图框架）
2. 设计明确的中间件链，而不是 if-else
3. 用 config 驱动关键决策
4. 建立 ThreadState 概念
5. 分离"规划"和"执行"

❌ **避免的**
1. 用 REST route 作为控制流
2. 隐含的中间件（如 Flask 的 before_request）
3. 硬编码的 if-else 分支
4. 全局变量
5. 工具调用的同步阻塞

❓ **待考虑的**
1. 如何处理"subagent 后台执行"的用户体验
2. 多个 middleware 并发修改 state 的一致性保证
3. 长期记忆和短期缓存的界限

---

## 📊 7 种角色的完备性

| 角色 | DeerFlow | 其他系统 | 备注 |
|------|---------|---------|------|
| Planner | ✅ 超强 | 中等 | 用 reasoning model |
| Decomposer | ✅ 很好 | 有 | 但支持并行度有限 |
| Executor | ✅ 超强 | 中等 | 隔离 + 灵活 |
| Reviewer | ✅ 超强 | 弱 | 15 层质量门禁 |
| Validator | ✅ 好 | 有 | 自动化程度高 |
| Router | ✅ 超强 | 中等 | State machine 很清晰 |
| Context Mgr | ✅ 很好 | 弱 | 分层记忆设计 |

**DeerFlow 相对特别强的**：Planner、Executor、Reviewer、Router

**需要加强的**：并行执行能力，长期记忆的检索

---

## 🎬 结论

DeerFlow 是一个**Middleware-first, State-machine-driven, Quality-first** 的 Agent 系统。

与其他系统对比：
- 🆚 vs LangChain Agents - DeerFlow 更显式、更可控
- 🆚 vs 脚本型 Agent - DeerFlow 有完整的质量保证
- 🆚 vs REST API - DeerFlow 支持复杂的多轮工作流

最有价值的教学是：**不要让复杂性隐藏在代码里，而要让它显式化为管道和配置**。

---

✅ **Phase 6 完成**

现在有了"DeerFlow 在通用范式中的位置"。**Phase 7** 会设计学习仓库的最终结构。
