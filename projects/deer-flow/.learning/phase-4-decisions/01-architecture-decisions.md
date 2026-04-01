# Phase 4：架构决策提炼（ADR 视角）

## 决策 1️⃣：LangGraph 作为核心编排引擎（而非传统 REST 路由）

### 决策内容

使用 **LangGraph（StateGraph-based agent framework）** 作为系统的中枢，而不是传统的"FastAPI 路由 → 业务逻辑 → 数据库"模式。

### 仓库证据

- **langgraph.json**：定义了唯一的图"lead_agent"，这是系统的 entry point
- **make_lead_agent()**：不是一个 HTTP handler，而是生成一个 agent graph
- **Middleware Chain**：集成在 LangGraph 的 middleware 系统中，不是 HTTP middleware
- **ThreadState**：是 LangGraph 的 state schema，不是数据库模型

### 解决的问题

- **传统 REST 的问题**：一个 request → 一次 response，无法表达"迭代推理"的过程
- **状态管理复杂**：对话状态、工具调用状态、memory 状态容易散落
- **错误恢复困难**：无法在某个步骤暂停并等待用户澄清

### 被放弃的替代方案

| 方案 | 为什么不用 |
|------|-----------|
| **传统 REST API** | 无法表达"多轮对话的状态流" |
| **消息队列** | 增加复杂度，依赖另一个系统 |
| **状态机库** | 不够灵活，无法支持 LLM 的不确定性 |
| **自写编排层** | 重复造轮子，维护成本高 |

### 优点

1. **迭代思考内置**：LangGraph 天然支持 agent loop
2. **状态管理清晰**：ThreadState 是单一真值源
3. **中断/恢复**：可以在 ClarificationMiddleware 处暂停并等待用户
4. **观测友好**：每次状态转移都是可见的

### 代价

1. **学习曲线**：开发者需要理解 state graph 和 middleware 概念
2. **性能开销**：每次状态转移需要序列化/反序列化
3. **工具限制**：有些异步框架 (如 FastAPI 的特定中间件) 不兼容 LangGraph
4. **可视化困难**：对标准 REST 监控工具的支持不足

### 什么场景适合借鉴

✅ **适合**：
- 需要多轮推理的系统（agent, chatbot）
- 工作流有明确的"步骤"（ETL, pipeline）
- 需要在中途暂停和干预

❌ **不适合**：
- 简单的 CRUD 操作（用 REST 就够了）
- 低延迟实时系统（state graph 有序列化开销）

### 为什么 DeerFlow 选了这个

Agent 的本质是**多轮、有状态、需要干预**。REST 不行。

---

## 决策 2️⃣：15 层 Middleware 作为显式的质量流水线（而非隐式逻辑）

### 决策内容

质量控制不是"隐散在各个地方的检查"，而是**显式的、有序的 middleware chain**，每一层都有明确的职责和前置条件。

### 仓库证据

- **_build_middlewares()** 的代码注释：明确说明每个 middleware 的依赖
- **15 个独立文件**：每个 middleware 是一个独立的类（SingleResponsibility Principle）
- **ClarificationMiddleware 总是最后**：这不是约定，而是 code comment 强制

### 解决的问题

- **质量控制随意**：不清楚系统防守哪些问题
- **debug 困难**：当出问题时，不知道是哪一层的问题
- **新增功能复杂**：改现有的检查逻辑容易破坏其他检查

### 被放弃的替代方案

| 方案 | 为什么不用 |
|------|-----------|
| **装饰器堆叠** | 顺序不清，容易搞错 |
| **if-else 链** | 每多一个检查就多一层缩进 |
| **Hook 系统** | 太灵活，容易滥用 |
| **AOP（面向方面编程）** | 过度复杂 |

### 优点

1. **可预测性**：清楚地知道执行顺序
2. **独立测试**：每个 middleware 可单独测试
3. **组合性**：想加新的检查，就添加一个 middleware
4. **文档即代码**：code comments 强制说明依赖

### 代价

1. **锁死了顺序**：不能随意重排（有依赖约束）
2. **冗长**：15 个文件看起来"太多"
3. **配置复杂**：每个 middleware 可能有自己的配置

### 什么场景适合借鉴

✅ **适合**：
- 有多个质量检查点的系统（编译器、网关）
- 需要可视化和可审计的流水线

❌ **不适合**：
- 检查点很少的系统（< 3 个）

---

## 决策 3️⃣：Config-Driven Sandbox 选择（而非代码分支）

### 决策内容

不是 `if local: ... elif docker: ... elif k8s: ...`，而是通过 **config.yaml** 的 `sandbox.use` 字段动态加载 SandboxProvider 实现类。

### 仓库证据

```yaml
# config.yaml
sandbox:
  use: deerflow.sandbox.local:LocalSandboxProvider
  # 或改成: deerflow.sandbox.docker:DockerSandboxProvider
  # 或改成: deerflow.sandbox.provisioner:ProvisionerProvider
```

- **resolve_class()**：通过字符串路径动态加载类（reflection）
- **SandboxProvider 接口**：三种实现都实现相同的接口

### 解决的问题

- **部署时改代码**：环境不同需要改 if-else，增加错误风险
- **测试覆盖困难**：难以测试所有分支
- **配置透明**：隐含的逻辑（哪个分支被选中）

### 被放弃的替代方案

| 方案 | 为什么不用 |
|------|-----------|
| **编译时选择** | 某个环境需要两种 sandbox 就无法做 |
| **环境变量** | 字符串太长，易出错 |
| **工厂函数** | 仍需要中央的 if-else 用来选择 |
| **运行时参数** | 每次请求都要指定（太麻烦） |

### 优点

1. **零代码改动**：改 config 即可切换实现
2. **灵活组合**：同一个仓库可支持三种部署模式
3. **测试友好**：可以 mock 不同的 config
4. **成本优化**：开发用 local，测试用 docker，生产用 k8s

### 代价

1. **配置复杂**：用户需要理解 `sandbox.use` 的含义
2. **反射开销**：动态加载有微小的性能开销
3. **错误推迟**：错误的 class path 不会在启动时暴露，而是在使用时

### 什么场景适合借鉴

✅ **适合**：
- 多环境部署（dev/test/prod）
- 需要支持多种实现的 SPI (Service Provider Interface)

❌ **不适合**：
- 选择只有一两个的情况
- 性能敏感的 critical path

---

## 决策 4️⃣：Manifest-Based Skills（而非代码式注册）

### 决策内容

Skills（能力）不是通过 Python 代码注册到 harness 中，而是通过 **manifest.json + SKILL.md** 文件声明。

### 仓库证据

```
skills/public/deep-research/
├─ SKILL.md
├─ manifest.json
└─ __init__.py
```

- **load_skills()** 扫描文件系统而非代码
- **manifest.json** 包含元数据（name, description, tools）

### 解决的问题

- **能力扩展需要改 harness**：新增 skill 不应该需要改 agent 的代码
- **版本管理混乱**：skill 版本和代码版本绑定
- **用户权限**：skill 作者需要代码提交权限

### 被放弃的替代方案

| 方案 | 为什么不用 |
|------|-----------|
| **代码注册表** | `SKILLS = {"name": skill_func}` 需要改代码 |
| **PEP 508 entry points** | 太复杂，overkill |
| **数据库存储** | 添加外部依赖 |
| **API 动态注册** | 运行时才注册，不可预测 |

### 优点

1. **自动发现**：新建文件夹 → 自动被发现
2. **用户可扩展**：`skills/custom/` gitignored，用户可自建
3. **版本独立**：skill 可以有自己的版本号
4. **容器友好**：skills 可以作为独立的挂载卷

### 代价

1. **格式约定**：必须遵守 manifest.json 的格式
2. **验证复杂**：需要对 manifest 做完整性检查
3. **查询开销**：每次启动都要扫描文件系统

### 什么场景适合借鉴

✅ **适合**：
- 插件系统（VS Code extensions）
- 微服务网格（服务自动发现）
- AI 市场（能力商城）

❌ **不适合**：
- 能力选择很少的系统（直接代码注册就够了）

---

## 决策 5️⃣：异步 Subagent 执行（而非阻塞等待）

### 决策内容

当 lead_agent 需要委托长运行任务时，不阻塞等待，而是立即返回 task_id，后台执行。

### 仓库证据

- **execute_async()** 返回 task_id（立即）
- **_background_tasks{}** 存储所有后台任务状态
- **双线程池**：调度器 + 执行器分离

### 解决的问题

- **用户体验**：如果阻塞，用户长时间无反馈（等待 15 分钟的后台任务）
- **资源利用**：多个 lead_agent 实例可以并发处理不同的请求

### 被放弃的替代方案

| 方案 | 为什么不用 |
|------|-----------|
| **同步阻塞** | 用户体验差，lead_agent 无法并发 |
| **Webhook 回调** | 添加复杂度，需要持久化 |
| **消息队列** | 又是一个外部依赖 |

### 优点

1. **用户体验好**：立即获得 task_id，不卡
2. **可预查询**：用户可后续查询进度
3. **资源利用高**：lead_agent 不阻塞

### 代价

1. **结果持久化**：需要存储 task 结果（现在在内存，可能丢失）
2. **超时管理**：需要处理"任务超时但用户还在查询"的情况
3. **复杂度**：需要双线程池 + 全局任务表

### 什么场景适合借鉴

✅ **适合**：
- 长运行任务（数据处理、模型训练）
- 需要高并发的系统

❌ **不适合**：
- 短任务（< 1s）
- 严格要求任务完成的系统

---

## 决策 6️⃣：ThreadState 集中管理（vs 分散状态）

### 决策内容

所有线程级别的状态集中在一个 **ThreadState TypedDict** 中，中间件通过读写这个对象通信，而不是互相传参。

### 仓库证据

- **thread_state.py** 定义 ThreadState（10 个字段）
- **所有 middleware** 都读写 ThreadState
- **Annotated Reducer** 处理并发更新（merge_artifacts, merge_viewed_images）

### 解决的问题

- **状态散落**：状态分散在对象树中，难以追踪
- **通信困难**：middleware 间通信需要显式传参
- **一致性问题**：多个 middleware 更新同一个对象易冲突

### 被放弃的替代方案

| 方案 | 为什么不用 |
|------|-----------|
| **对象树** | 状态散落各处，难以一致性管理 |
| **全局变量** | 容易出现副作用和竞态 |
| **数据库** | 太慢，每次状态转移都要 I/O |
| **事件系统** | 过度解耦，难以追踪 |

### 优点

1. **单一真值源**：所有状态在一个地方
2. **并发安全**：Annotated Reducer 自动处理合并
3. **易于序列化**：保存/恢复对话状态容易
4. **LangGraph 原生支持**：state schema 就是这样设计的

### 代价

1. **字段增多时复杂度↑**：schema 越来越大
2. **Reducer 维护**：每个新字段可能需要自定义 reducer

### 什么场景适合借鉴

✅ **适合**：
- LangGraph-based 系统
- 需要状态一致性的工作流

❌ **不适合**：
- 没有统一状态观点的系统

---

## 决策 7️⃣：Config 作为 Dependency Injection 驱动

### 决策内容

不是在代码中硬编码依赖解析，而是通过 **config.yaml** 中的字符串路径（如 `deerflow.sandbox.local:LocalSandboxProvider`）动态加载实现。

### 仓库证据

```yaml
models:
  - name: gpt-4
    use: langchain_openai:ChatOpenAI
    model: gpt-4

sandbox:
  use: deerflow.sandbox.local:LocalSandboxProvider
```

- **resolve_class()** 实现 string → class 的映射
- **get_app_config()** 读取 config.yaml 并缓存

### 解决的问题

- **紧耦合**：改一个 model provider 需要改代码
- **不灵活**：无法在运行时选择实现
- **测试难**：mock 困难（需要改代码）

### 被放弃的替代方案

| 方案 | 为什么不用 |
|------|-----------|
| **硬编码** | 不灵活 |
| **工厂函数** | 仍需某处的 if-else |
| **Service locator** | 太复杂，反模式 |

### 优点

1. **灵活**：config 改变则实现改变
2. **可测试**：mock config 即可 mock 依赖
3. **扩展容易**：新增实现无需改代码

### 代价

1. **反射开销**：动态加载有性能开销
2. **运行时错误**：错误在运行时才暴露
3. **学习曲线**：开发者需要理解 DI 的概念

---

## 决策 8️⃣：Memory 异步入队（而非同步处理）

### 决策内容

对话记忆不是同步地存入数据库，而是异步地入队到 **MemoryQueue**，后台线程处理。

### 仓库证据

- **MemoryMiddleware** 只是入队，不是持久化
- **MemoryQueue** 后台线程处理
- **异步处理** 不阻塞 agent loop

### 解决的问题

- **延迟**：实时存入数据库慢
- **吞吐**：每个对话都要等 I/O 完成

### 优点

1. **不阻塞 agent**：agent 可继续推理
2. **吞吐量大**：多个对话的记忆可批量处理

### 代价

1. **结果不一致**：对话刚完成，memory 可能还没写入数据库
2. **数据丢失风险**：如果系统崩溃，队列中的 record 丢失

---

## 🎯 架构决策总结表

| # | 决策 | 核心权衡 | 适用范围 |
|-|-|-|-|
| 1 | LangGraph | 迭代能力 vs 学习曲线 | Agent systems |
| 2 | Middleware 链 | 可维护性 vs 锁死顺序 | 多质量检查点系统 |
| 3 | Config DI | 灵活性 vs 运行时错误 | 多环境部署 |
| 4 | Manifest Skills | 扩展易用性 vs 复杂性 | Plugin systems |
| 5 | 异步 Subagent | UX vs 结果一致性 | Long-running tasks |
| 6 | 集中 ThreadState | 一致性 vs Schema 复杂度 | Stateful workflows |
| 7 | Config DI (重复) | 灵活性 vs 反射开销 | Pluggable architectures |
| 8 | 异步 Memory | 吞吐 vs 一致性 | High-traffic systems |

---

## 我学到的最重要的设计原则

1. **Explicit is better than implicit** (PEP 20) - middleware 顺序、状态字段都明确声明
2. **Composition > Inheritance** - Strategy Pattern for Sandbox, 不用继承
3. **Convention over Configuration** - 但仍提供 Config 的灵活性
4. **Single Responsibility** - 每个 middleware 一个文件
5. **Dependency Injection** - config 驱动实现选择

---

✅ **Phase 4 完成**

**进入 Phase 5** 时，会用架构评分表来审视这些决策的优缺点。
