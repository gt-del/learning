# Phase 6：范式映射 - OpenSpec 的通用架构模式

## 核心问题

**OpenSpec 是什么的"实例"？** 

本阶段的目标是：识别 OpenSpec 底层遵循的更古老、更通用的架构范式，从而理解哪些设计是"领域特定"，哪些是"通用的架构原理"。

---

## 范式 1：管道（Pipeline）范式

### 概述

OpenSpec 的工作流本质是一个**有向无环图（DAG）管道**。

```
proposal ──────┐
               ├─> specs ──────┐
               │               ├─> design ──────┐
               │               │                ├─> tasks ──> archive
               │               │                │
               └─ (dependencies)                │
                                               └─ (dependencies)
```

### 具体体现

**1. 配置定义管道**
```yaml
# 这个 YAML 本质是"管道配置"
artifacts:
  - id: proposal
    requires: []
  - id: specs
    requires: [proposal]
  - id: design
    requires: [specs]
```

**代码证据**：[src/core/artifact-graph/graph.ts](src/core/artifact-graph/graph.ts)
```typescript
class ArtifactGraph {
  // 本质是一个 DAG
  private artifacts: Map<string, Artifact>;
  
  // DAG 查询操作
  getNextArtifacts(completed): string[]  // 输出"下一步可以执行的"
  getBlocked(completed): Map<string, string[]>  // 输出"被什么阻止"
  getBuildOrder(): string[]  // 拓扑排序
}
```

### 古老的相关范式

| 范式名 | 年代 | 例子 |
|------|------|------|
| **Make/Makefile** | 1976 | `spec.md: proposal.md` 定义依赖 |
| **DAG Scheduler** | 1990s | Airflow, Luigi, Dask |
| **Reactive Streams** | 2010s | RxJS, Project Reactor |
| **Build Systems** | 2000s+ | Gradle, Bazel, Buck |

### OpenSpec vs 传统 Pipeline 的差异

| 特性 | 传统 Pipeline | OpenSpec |
|-----|-------------|---------|
| **单位** | Task（执行一段代码） | Artifact（生成一个文件） |
| **触发** | 自动（文件改变） | 手动（用户生成） |
| **状态** | 数据库 | 文件系统 |
| **错误处理** | try-catch | 多层 gate |
| **人工参与** | 无 | 有（用户在中间编辑） |

### 何时应该借鉴这个模式

✅ **构建系统**（代码生成、编译流程）
✅ **数据处理管道**（ETL、数据清洗）
✅ **文档生成**（从源代码生成文档）
✅ **工作流编排**（多步骤业务流程）

❌ **实时系统**（反应时间敏感）
❌ **反馈循环系统**（需要多次迭代）

---

## 范式 2：源代码管理（SCM）范式

### 概述

OpenSpec 的 **Specs vs Changes** 分离，本质上是**分支模型**（如 Git）。

```
Main branch (specs/)
    ↑
    ├─ Feature branch A (change-feature-A/)
    ├─ Feature branch B (change-feature-B/)
    └─ Feature branch C (change-feature-C/)

Archive 就是 merge + delete branch
```

### 具体体现

**1. 隔离工作空间**
```
传统 Git：
  main/
  └─ feature-branch/

OpenSpec：
  specs/（main）
  └─ changes/feature-A/（branch）
```

**2. Merge 流程**
```typescript
// Git 的 3-way merge
base ──────┐
           ├─> MERGE CONFLICT?
feature ──┘
           ❌ 手工解决

// OpenSpec 的 delta merge
main specs ────────┐
                   ├─> apply delta ──→ ✅ 几乎无冲突
change delta ────┘
```

**代码证据**：[src/core/specs-apply.ts](src/core/specs-apply.ts)
```typescript
async function buildUpdatedSpec(update: SpecUpdate) {
  // 这个过程类似 3-way merge，但使用 delta 格式减少冲突
  
  const mainSpec = await readFile(update.target);
  const changeSpec = await readFile(update.source);
  const plan = parseDeltaSpec(changeSpec);
  
  // 应用：remove ─> rename ─> modify ─> add
  // 类似 patch 的应用顺序
  return {rebuilt};
}
```

### 古老的相关范式

| 范式名 | 年代 | 例子 |
|------|------|------|
| **Mainline branching** | 1990s | RCS, SCCS 时代的分支模型 |
| **3-way merge** | 1995+ | CVS, SVN |
| **Feature branch** | 2000s+ | Git workflow, GitHub Flow |
| **Patch-based merging** | 1990s+ | Linux kernel, GNU diff/patch |

### OpenSpec vs Git 的差异

| 特性 | Git | OpenSpec |
|-----|-----|---------|
| **冲突检测** | 行级 | 需求级（更高层） |
| **Merge 复杂度** | O(n) + 手工 | O(n)，通常无手工 |
| **Rebase 支持** | ✅ 支持 | ❌ 不支持 |
| **History** | ✅ 完整 | ⚠️ Archive 中 |
| **Conflict Resolution** | 手工 | 自动（delta 格式） |

### 何时应该借鉴这个模式

✅ **多人协作编写**（文档、配置、规格）
✅ **需要 review 流程**（每个分支 merge 前审查）
✅ **需要 rollback**（删除分支恢复旧状态）

❌ **需要 rebase**（交互式历史编辑）
❌ **需要 bisect**（二分查找 bug）
❌ **紧密的行级 merge**（代码级别）

### 核心洞察

> **Git 解决的是"代码级别的并发编辑"**
> **OpenSpec 解决的是"需求级别的并发编辑"**

两者用的核心思想相同（分支模型），但应用层次不同。

---

## 范式 3：酸性事务（ACID Transactions）范式

### 概述

OpenSpec 的 **All-or-nothing archive** 实现了**原子性（Atomicity）**。

```
传统流程：
  1. 验证 ──→ 失败❌ ──→ 系统混乱
  2. 写入
  3. 移动 ❌（从不执行到这）

OpenSpec 流程：
  验证所有 ───────┐
  应用所有 ───── ALL OK? ───→ ✅ 原子写入 + 原子移动
  移动所有 ───────┘         ❌ 全部回滚
```

### 具体体现

**代码证据**：[src/core/archive.ts](src/core/archive.ts#L100-L150)
```typescript
async execute(changeName: string) {
  // Phase 1: Verify (无侧作用)
  const prepared = [];
  for (const update of specUpdates) {
    const built = await buildUpdatedSpec(update);
    prepared.push({updated: built, ...});
  }
  
  // Phase 2: Write (原子执行，或全部回滚)
  for (const p of prepared) {
    const result = await validator.validateSpecContent(...);
    if (!result.valid) {
      throw Error('Validation failed');  // ← 立即停止，零写入
    }
  }
  
  // Phase 3: 只在所有验证通过后，才执行写入和移动
  for (const p of prepared) {
    await writeUpdatedSpec(p.update.target, p.rebuilt);
  }
  await moveDirectory(changeDir, archiveDir);
  
  // 如果执行到这里，说明已经原子地完成了所有操作
}
```

### 古老的相关范式

| 范式名 | 年代 | 例子 |
|------|------|------|
| **ACID 事务** | 1980s | 所有数据库 |
| **Two-phase commit** | 1978 | 分布式数据库 |
| **Copy-on-write** | N/A | 文件系统镜像 |
| **Rollback journal** | 1990s | SQLite 实现 |

### OpenSpec vs 数据库的差异

| 特性 | 数据库 | OpenSpec |
|------|------|---------|
| **事务隔离** | ACID 完整 | 仅 Atomicity |
| **并发控制** | 锁机制 | 文件系统隔离 |
| **Rollback** | 日志系统 | 完整 copy |
| **性能** | 高（优化过） | 中等（文件 I/O） |

### 何时应该借鉴这个模式

✅ **金融系统**（必须 ACID）
✅ **库存系统**（一致性关键）
✅ **订单处理**（原子性关键）

⚠️ **文档系统**（原子性有帮助，但非必须）
❌ **实时系统**（事务开销太大）
❌ **分布式系统**（难以实现 ACID）

### 核心洞察

> OpenSpec 的 archive 不是完整的 ACID 事务，但实现了**原子性**。
> 这对于"要么全部成功，要么全部失败"的场景足够了。

---

## 范式 4：函数式编程（FP）范式

### 概述

OpenSpec 的很多核心函数是**纯函数**，遵循函数式编程思想。

```
纯函数：
  input ──> 无副作用的计算 ──> output
  
例子：
  parseSchema(yamlContent) → SchemaYaml
  parseDeltaSpec(content) → DeltaPlan
  getNextArtifacts(graph, completed) → string[]
```

### 具体体现

**1. 不变性（Immutability）**
```typescript
// ✅ 好的模式（OpenSpec 采用）
function applyDelta(
  mainSpec: string,
  delta: string
): string {
  // 不修改 mainSpec 和 delta
  // 返回新的字符串
  return rebuiltSpec;
}

// ❌ 不好的模式
function applyDelta(mainSpec: string, delta: string) {
  mainSpec = mainSpec.replace(...);  // 直接修改
  return mainSpec;
}
```

**2. 高阶函数**
```typescript
// OpenSpec 中的高阶函数例子
async function generateInstructions(
  context: ChangeContext,
  artifactId: string
): Promise<ArtifactInstructions> {
  // 接收 context，返回一个"指令生成函数"
}

// 用户调用
const instructions = await generateInstructions(context, 'specs');
```

**3. 函数组合**
```typescript
// Pipeline of transformations
const schemaYaml = parseYaml(content);        // 字符串 → JSON
const validated = validateSchema(schemaYaml);  // JSON → 验证
const graph = buildArtifactGraph(validated);   // 验证 → Graph
const next = getNextArtifacts(graph, completed);  // Graph → 下一步
```

### 古老的相关范式

| 范式名 | 年代 | 语言 |
|------|------|------|
| **Lambda calculus** | 1936 | 理论基础 |
| **Lisp** | 1958 | 第一个 FP 语言 |
| **Functional Programming** | 1980s+ | Haskell, ML, Scheme |
| **Reactive Programming** | 2010s | RxJS, Elm |

### OpenSpec vs OOP 的差异

| 特性 | OOP | FP |
|-----|-----|----|
| **状态管理** | 对象内 | 参数传递 |
| **可测试性** | 需要 mock | 直接测试 |
| **并发安全** | 需要锁 | 天然安全（不变性） |
| **代码理解** | 对象生命周期 | 数据转换流 |

### 何时应该借鉴这个模式

✅ **数据处理**（ETL、解析）
✅ **测试密集型代码**（金融、医疗）
✅ **并发系统**（多线程、分布式）

❌ **状态连续变化**（游戏、UI 动画）
❌ **OOP 天然的领域**（UI 框架）

### 核心洞察

> OpenSpec 很多核心模块选择了 FP，使得系统高度可测试。
> 这是为什么 test/cli-e2e/ 能做完整的集成测试的原因。

---

## 范式 5：发布-订阅（Pub-Sub）范式

### 概述

虽然 OpenSpec 没有显式的 Pub-Sub 架构，但**命令之间的依赖**隐含了这个模式。

```
事件流：

  new-change --create--> Change scaffolded
       ↓
  status --check----> Get next artifacts
       ↓
  instructions --generate--> AI reads config + context + dependencies
       ↓
  [User edits file]
       ↓
  status --check---> See next available actions
       ↓
  archive --trigger--> Merge + Archive event
```

### 具体体现

**1. 隐含的事件**
```
发布者：archive.ts
  ├─ Event: "artifact_completed"
  ├─ Event: "delta_applied"
  └─ Event: "change_archived"

订阅者（隐含的）：
  ├─ 文件系统观察者（用户看到新文件）
  ├─ 日志系统（记录事件）
  └─ 状态查询系统（status 命令看到新状态）
```

**2. 时间解耦**
```
不是：  A command ──> B command ──> C command (同步)
而是：  A command ──> [state change] ──> B command 
       （命令之间通过状态变化解耦）
```

### 古老的相关范式

| 范式名 | 年代 | 例子 |
|------|------|------|
| **Observer Pattern** | 1994 | GoF Design Patterns |
| **Pub-Sub** | 1990s+ | Message queues |
| **Event Sourcing** | 2000s+ | CQRS pattern |
| **Reactive Extensions** | 2010s | RxJS, RxJava |

### OpenSpec vs 显式 Pub-Sub 的差异

| 特性 | 显式 Pub-Sub | OpenSpec (隐含) |
|-----|------------|----------|
| **耦合度** | 低 | 稍高（通过文件系统） |
| **复杂度** | 高 | 低 |
| **可观测性** | ✅ 高 | ⚠️ 中等 |
| **事件序列** | ✅ 清晰 | ❌ 隐含 |

### 何时应该借鉴这个模式

✅ **多个独立系统协作**（服务间通信）
✅ **需要异步处理**（消息队列）
✅ **需要事件历史**（审计、重放）

❌ **简单的单体系统**（OpenSpec 就是）
❌ **强时间顺序要求**（同步更清晰）

### 核心洞察

> OpenSpec 的**隐含 Pub-Sub** 通过"文件系统状态变化"实现。
> 这比显式 Pub-Sub 简单得多，但也不如灵活。

---

## 范式 6：模板方法（Template Method）范式

### 概述

OpenSpec 的**指令生成**使用了 Template Method 模式。

```
抽象模板：
  1. 读取项目背景
  2. 读取工件模板
  3. 读取工件规则
  4. 读取依赖工件内容
  5. 组合成完整的指令

具体实现：generateInstructions()
```

### 具体体现

**代码证据**：[src/core/artifact-graph/instruction-loader.ts](src/core/artifact-graph/instruction-loader.ts)
```typescript
async function generateInstructions(
  context: ChangeContext,
  artifactId: string,
  projectRoot: string
): Promise<ArtifactInstructions> {
  // Template Method 的骨架：
  
  // Step 1: 获取项目上下文
  const background = context.config.context;
  
  // Step 2: 获取工件描述
  const artifact = context.graph.getArtifact(artifactId);
  
  // Step 3: 加载模板
  const template = await loadTemplate(artifact.template);
  
  // Step 4: 获取工件规则
  const rules = context.config.rules[artifactId] || [];
  
  // Step 5: 获取依赖工件内容
  const dependencies = await Promise.all(
    artifact.requires.map(id => loadArtifactContent(id))
  );
  
  // Step 6: 组合成完整指令
  return {
    background,
    artifact,
    template,
    rules,
    dependencies,
    unlocks: getUnlocks(artifactId, context.graph)
  };
}
```

### 古老的相关范式

| 范式名 | 年代 | 书籍 |
|------|------|------|
| **Template Method** | 1994 | GoF Design Patterns |
| **Strategy Pattern** | 1994 | GoF Design Patterns |
| **Decorator Pattern** | 1994 | GoF Design Patterns |

### OpenSpec vs 其他方案的差异

| 方案 | 优点 | 缺点 |
|-----|------|------|
| **Template Method** | ✅ 清晰的顺序 | ❌ 扩展性受限 |
| **Strategy Pattern** | ✅ 灵活切换 | ❌ 更复杂 |
| **Hooks/Middleware** | ✅ 最灵活 | ❌ 最复杂 |

---

## 范式 7：状态机（State Machine）范式

### 概述

OpenSpec 的**7 个状态 + 转换规则**是一个典型的**有限状态机（FSM）**。

```
SCAFFOLDED
    ├─ PLANNING_IN_PROGRESS
    ├─ PLANNING_COMPLETE
    ├─ IMPLEMENTING
    ├─ IMPLEMENTATION_COMPLETE
    ├─ READY_FOR_MERGE
    └─ ARCHIVED

每个状态有进入条件、事件响应、退出行为
```

### 具体体现

**状态定义**：[docs/concepts.md](docs/concepts.md)
```
State: SCAFFOLDED
  Entry: 用户运行 new-change
  Valid transitions: PLANNING_IN_PROGRESS
  Artifacts: proposal.md 存在 = 进入下一个状态

State: PLANNING_IN_PROGRESS
  Entry: proposal.md 完成
  Valid transitions: PLANNING_COMPLETE
  Artifacts: specs/ 存在 = 进入下一个状态
  ...
```

**代码中的状态查询**：[src/commands/workflow/status.ts](src/commands/workflow/status.ts)
```typescript
// 计算当前状态（隐含的 FSM 转移函数）
function computeCurrentState(completed: Set<string>): ChangeState {
  if (completed.has('archived')) return 'ARCHIVED';
  if (completed.has('proposal') && completed.has('design') && 
      completed.has('specs') && completed.has('tasks')) {
    return 'READY_FOR_MERGE';
  }
  if (completed.has('proposal') && completed.has('design')) {
    return 'IMPLEMENTING';
  }
  if (completed.has('proposal')) {
    return 'PLANNING_COMPLETE';
  }
  return 'SCAFFOLDED';
}
```

### 古老的相关范式

| 范式名 | 年代 | 先驱 |
|------|------|------|
| **Automata Theory** | 1950s | Turing, 计算理论 |
| **Finite State Machine** | 1960s | 嵌入式系统 |
| **State Pattern** | 1994 | GoF Design Patterns |
| **State Machines as Models** | 2000s | UML State Diagrams |

### OpenSpec vs 其他状态建模的差异

| 方案 | 优点 | 缺点 |
|-----|------|------|
| **Explicit FSM class** | ✅ 清晰 | ❌ 冗长 |
| **State transition table** | ✅ 声明式 | ⚠️ 不易实现 |
| **Implicit（OpenSpec）** | ✅ 简单 | ❌ 难以验证 |

### 何时应该借鉴这个模式

✅ **工作流系统**（订单、审批、任务）
✅ **游戏逻辑**（敌人 AI、游戏流程）
✅ **通信协议**（TCP, HTTP）

---

## 范式 8：命令查询职责分离（CQRS）范式

### 概述

OpenSpec 隐含地实现了 **CQRS**（Command Query Responsibility Segregation）。

```
查询侧（Query）：
  openspec status        ← 只读，不改状态
  openspec show         ← 只读，查看工件

命令侧（Command）：
  openspec workflow new-change  ← 写入状态
  openspec workflow instructions ← 生成（改变系统）
  openspec workflow archive     ← 提交改变
```

### 具体体现

**1. 读操作（纯查询）**
```typescript
// src/commands/workflow/status.ts - 只查询，不修改
async function statusCommand(options) {
  const completed = await detectCompleted(graph, changeDir);
  const next = graph.getNextArtifacts(completed);
  console.log(formatStatus(completed, next));
  // 返回，无副作用
}
```

**2. 写操作（命令）**
```typescript
// src/commands/workflow/new-change.ts - 创建新 change
async function newChangeCommand(options) {
  // 这个命令**改变系统状态**（创建新目录）
  await createChangeDirectory(...);
}

// src/core/archive.ts - Archive 命令
async execute(changeName) {
  // 这个命令**改变系统状态**（应用 delta，移动目录）
  await applySpecs(...);
  await moveDirectory(...);
}
```

### 古老的相关范式

| 范式名 | 年代 | 推崇者 |
|------|------|------|
| **Command-Query Separation** | 1991 | Bertrand Meyer |
| **CQRS** | 2010 | Greg Young |
| **Event Sourcing** | 2000s | 同 CQRS |

### OpenSpec vs 传统架构的差异

| 特性 | 传统（混合） | CQRS（OpenSpec） |
|-----|----------|-----------|
| **读写路径** | 混杂 | 分离 |
| **可优化性** | ❌ 困难 | ✅ 容易 |
| **缓存策略** | 复杂 | 简单 |
| **事件追踪** | ❌ 困难 | ✅ 容易 |

### 何时应该借鉴这个模式

✅ **读多写少的系统**（大多数 Web 系统）
✅ **需要精确审计的系统**（金融、医疗）
✅ **高并发系统**（分离读写可以独立优化）

❌ **强一致性要求**（写后立即读）
❌ **简单的单体应用**（额外复杂度）

---

## 范式 9：声明式 vs 命令式混合

### 概述

OpenSpec 混合了两种编程范式：
- **声明式**：Schema YAML 定义"是什么"
- **命令式**：Commands 实现"做什么"

```
声明式（Schema）：
  artifacts:
    - id: proposal
      requires: []

命令式（Commands）：
  new-change ──> mkdir ──> create proposal.md
```

### 具体体现

**声明式部分**
```yaml
# openspec/schemas/spec-driven/schema.yaml
# 用户声明"工作流是什么样的"
artifacts:
  - id: proposal
    generates: proposal.md
    requires: []
```

**命令式部分**
```typescript
// src/commands/workflow/
// 系统命令式地"执行工作流"
if (nextArtifact.id === 'proposal') {
  // 执行：生成指令 ──> 显示给用户
}
```

### 古老的相关范式

| 范式名 | 年代 | 语言 |
|------|------|------|
| **Declarative** | 1990s+ | SQL, Prolog |
| **Imperative** | 1950s+ | Fortran, C |
| **Hybrid** | 2000s+ | XML-based configs + code |

---

## 范式总结表

| 范式 | 在 OpenSpec 中的体现 | 强度 | 源头 |
|-----|-----------------|------|------|
| Pipeline/DAG | Artifact Graph | ⭐⭐⭐⭐⭐ | Make (1976) |
| Branching (SCM) | Specs vs Changes | ⭐⭐⭐⭐⭐ | Git (2005) |
| ACID Transactions | All-or-nothing Archive | ⭐⭐⭐⭐ | DBMS (1980s) |
| Functional Programming | Pure functions | ⭐⭐⭐⭐ | Lisp (1958) |
| Pub-Sub (隐含) | State change events | ⭐⭐⭐ | Message queues |
| Template Method | Instruction generation | ⭐⭐⭐ | GoF (1994) |
| State Machine | 7-state workflow | ⭐⭐⭐⭐ | Automata theory |
| CQRS | Command vs Query | ⭐⭐⭐ | Greg Young (2010) |
| Declarative + Imperative | Schema + Commands | ⭐⭐⭐⭐ | XML-based systems |

---

## 核心洞察：OpenSpec 是这些范式的"最小化编排"

### 洞察 1：选择性使用范式

OpenSpec **没有用**：
- ❌ 完整的 ACID（太重）
- ❌ 完整的 CQRS（太复杂）
- ❌ 显式的 Pub-Sub（太复杂）

OpenSpec **最大化地用**：
- ✅ Pipeline/DAG（核心）
- ✅ Branching model（核心）
- ✅ Pure functions（高度应用）

### 洞察 2：范式之间的协同

```
Pipeline ──────────────────────┐
                               ├─> 支撑清晰的工作流
Branching model ────────────┘

Pure functions ────────────────┐
                               ├─> 支撑深层的可测试性
Template Method + CQRS ────────┘

All-or-nothing ────────────────┐
                               ├─> 支撑数据一致性
State Machine ──────────────┘
```

### 洞察 3：通用性 vs 专用性

```
最通用的范式（所有系统都能借鉴）：
✅ Pipeline/DAG
✅ Branching model
✅ Pure functions

领域特定的组合（适合协作系统）：
⚠️ Schema-driven workflow
⚠️ File-system-as-state
⚠️ Delta-based merging
```

---

## 实践建议：如何应用这些范式到其他系统

### 场景 1：文档协作系统

```
使用范式：
  ✅ Branching model (main docs vs draft)
  ✅ ACID transactions (保证一致性)
  ✅ Template Method (文档模板)
  ❌ Schema-driven (文档不需要定义工作流)
```

### 场景 2：代码生成系统

```
使用范式：
  ✅ Pipeline/DAG (输入 → 生成 → 验证)
  ✅ Pure functions (生成器无副作用)
  ✅ CQRS (查询可用生成 vs 执行生成)
  ⚠️ Schema-driven (定义代码模板)
```

### 场景 3：订单处理系统

```
使用范式：
  ✅ State Machine (订单状态)
  ✅ ACID transactions (金额处理)
  ✅ All-or-nothing (支付原子)
  ❌ Branching model (订单无需分支)
```

### 场景 4：AI 工作流系统

```
使用范式：
  ✅ Pipeline/DAG (AI ──> 验证 ──> 输出)
  ✅ Template Method (提示词模板)
  ✅ State Machine (任务状态)
  ✅ Pure functions (生成器无副作用)
  ⚠️ Branching model (多版本输出)
  ⚠️ CQRS (分离查询和执行)
```

---

## 最终结论

**OpenSpec 本质是**：

```
Modern Declarative Configuration
    ↓
+ Classic Pipeline/DAG Pattern (Make, 1976)
+ Branching Model Pattern (Git, 2005)
+ Functional Programming (Lisp, 1958)
+ State Machine (Theory, 1960s)
    ↓
= 一个"古老范式的现代精妙编排"
```

这不是"创新"，而是"在正确的地方应用正确的古老范式"。

**这就是为什么 OpenSpec 看起来简洁而优雅** — 它不是发明了什么新东西，而是清晰地整合了半个多世纪的计算机科学最佳实践。
