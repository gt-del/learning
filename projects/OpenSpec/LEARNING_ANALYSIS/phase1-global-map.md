# Phase 1：全局架构地图 - 系统的全景视图

## 🎯 目标

在60分钟内，绘制OpenSpec的完整架构地图，包括：
- One-liner 描述
- 主工作流关键路径
- 5大模块职责
- 顶层20% 的设计洞察

---

## 💡 One-Liner

> OpenSpec：一个 **AI原生的、spec驱动的、多人隔离的变更协调系统**，通过DAG定义工作流，用文件系统存储状态，支持delta merge实现无冲突合并。

---

## 🗺️ 系统全景图

```
┌─────────────────────────────────────────────────────────────────┐
│                   OpenSpec 系统架构（全景）                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ╔═══════════════════════════════════════════════════════════╗  │
│  ║         用户界面层：CLI Commands (src/cli/)              ║  │
│  ║  new-change | status | instructions | archive | show     ║  │
│  ╚═════════════════════╦═════════════════════════════════════╝  │
│                        ║                                        │
│  ╔═════════════════════╩═════════════════════════════════════╗  │
│  ║      业务逻辑层：Workflow Commands (src/commands/)        ║  │
│  ║                                                            ║  │
│  ║  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    ║  │
│  ║  │ new-change   │  │   status     │  │instructions  │    ║  │
│  ║  │ 创建变更容器  │  │ 查看进度状态 │  │ 生成AI指令    │    ║  │
│  ║  └──────────────┘  └──────────────┘  └──────────────┘    ║  │
│  ║                                                            ║  │
│  ║  ┌──────────────┐  ┌──────────────┐                       ║  │
│  ║  │  archive     │  │    show      │                       ║  │
│  ║  │ 合并并归档    │  │ 显示工件内容 │                       ║  │
│  ║  └──────────────┘  └──────────────┘                       ║  │
│  ╚═════════════════════╦═════════════════════════════════════╝  │
│                        ║                                        │
│  ╔═════════════════════╩═════════════════════════════════════╗  │
│  ║      核心模块层：Core Engines (src/core/)                ║  │
│  ║                                                            ║  │
│  ║  ┌──────────────────┐    ┌──────────────────┐             ║  │
│  ║  │  Artifact Graph  │    │  Schema System   │             ║  │
│  ║  │  • DAG依赖追踪   │    │  • 加载工作流    │             ║  │
│  ║  │  • 工件检测      │    │  • 三层级联      │             ║  │
│  ║  │  • 指令生成      │    │  • 验证Schema    │             ║  │
│  ║  └──────────────────┘    └──────────────────┘             ║  │
│  ║                                                            ║  │
│  ║  ┌──────────────────┐    ┌──────────────────┐             ║  │
│  ║  │ Archive Engine   │    │   Validator      │             ║  │
│  ║  │  • Delta解析     │    │  • 多层验证      │             ║  │
│  ║  │  • Merge应用     │    │  • 格式检查      │             ║  │
│  ║  │  • 状态转移      │    │  • All-or-nothing│             ║  │
│  ║  └──────────────────┘    └──────────────────┘             ║  │
│  ║                                                            ║  │
│  ╚═════════════════════╦═════════════════════════════════════╝  │
│                        ║                                        │
│  ╔═════════════════════╩═════════════════════════════════════╗  │
│  ║       存储层：文件系统 (openspec/)                         ║  │
│  ║                                                            ║  │
│  ║  ┌─────────────────┐  ┌──────────────┐  ┌────────────┐   ║  │
│  ║  │  specs/         │  │  changes/    │  │ archive/   │   ║  │
│  ║  │  (Main specs)   │  │ (Branches)   │  │(Completed) │   ║  │
│  ║  │                 │  │              │  │            │   ║  │
│  ║  │ auth/spec.md    │  │ feature-A/   │  │2025-01-01- │   ║  │
│  ║  │ payment/spec.md │  │   proposal   │  │ feature-A/ │   ║  │
│  ║  │                 │  │   specs/     │  │            │   ║  │
│  ║  └─────────────────┘  │   design     │  └────────────┘   ║  │
│  ║                       │              │                    ║  │
│  ║                       └──────────────┘                    ║  │
│  ║                                                            ║  │
│  ║  ┌──────────────────────────────────────────────────┐     ║  │
│  ║  │  openspec/schemas/spec-driven/schema.yaml       │     ║  │
│  ║  │  openspec/config.yaml                            │     ║  │
│  ║  └──────────────────────────────────────────────────┘     ║  │
│  ║                                                            ║  │
│  ╚════════════════════════════════════════════════════════════╝  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 主工作流关键路径

### 完整用户旅程

```
Step 1：初始化变更
┌─────────────────────────────┐
│ openspec new-change         │
│ feature-login               │
└────────────┬────────────────┘
             ↓  [创建目录结构]
    ┌────────────────┐
    │ changes/       │
    │ feature-login/ │
    │ ├─ specs/      │
    │ └─ [temp]      │
    └────────────┬───┘
                 ↓
            状态变更
        SCAFFOLDED → 
    PLANNING_IN_PROGRESS


Step 2：查看进度
┌─────────────────────────────┐
│ openspec status             │
│ feature-login               │
└────────────┬────────────────┘
             ↓  [检查文件存在性]
    ├─ proposal.md ✓ 存在
    ├─ specs/ ? 需要
    ├─ design.md ? 需要
    └─ tasks.md ? 需要
             ↓
    Next: 创建 proposal.md


Step 3：生成指令
┌─────────────────────────────┐
│ openspec instructions       │
│ feature-login               │
│ [artifact: proposal]        │
└────────────┬────────────────┘
             ↓  [加载上下文]
    ├─ 读 config.yaml
    ├─ 读 schema
    ├─ 加载模板
    └─ 组合成完整指令
             ↓
        [返回 JSON]
    {
      projectContext: "...",
      template: "...",
      rules: [...],
      nextArtifacts: ["specs"]
    }


Step 4：用户编辑
┌─────────────────────────────┐
│ [AI生成内容 +                │
│  用户手工编辑]              │
│ → proposal.md               │
│ → specs/auth/spec.md        │
└────────────┬────────────────┘
             ↓ [文件保存]
    状态变更
    PLANNING_IN_PROGRESS →
    PLANNING_COMPLETE


Step 5：再次检查进度
┌─────────────────────────────┐
│ openspec status             │
│ feature-login               │
└────────────┬────────────────┘
             ↓
    ├─ proposal.md ✓
    ├─ specs/ ✓
    ├─ design.md ? 需要
    └─ tasks.md ? 需要
             ↓
    状态：IMPLEMENTING


Step 6：持续生成和编辑
┌─────────────────────────────┐
│ [重复步骤3-5]               │
│ openspec instructions       │
│ → 生成 design.md 指令      │
│ [用户编辑]                  │
│ → 生成 tasks.md 指令       │
└────────────┬────────────────┘
             ↓
    状态：IMPLEMENTATION_COMPLETE
         → READY_FOR_MERGE


Step 7：最终验证和归档
┌─────────────────────────────┐
│ openspec archive            │
│ feature-login               │
└────────────┬────────────────┘
             ↓  [7步验证&合并]
    ├─ Gate 1: 工件完整性
    ├─ Gate 2: 格式检查
    ├─ Gate 3: Delta格式
    ├─ Gate 4: 内容验证
    ├─ Gate 5: 干跑merge
    ├─ Gate 6: 写入 specs/
    └─ Gate 7: 移动到archive/
             ↓ [All-or-nothing]
    ✅ 成功
    或
    ❌ 完全回滚


Step 8：完成
┌─────────────────────────────┐
│ Main specs已更新            │
│ feature-login→moved to      │
│ archive/2025-01-24-...      │
│ 状态：ARCHIVED              │
└─────────────────────────────┘
```

---

## 🏗️ 5大核心模块深度职责

### 模块 1：Artifact Graph  
**位置**：`src/core/artifact-graph/`  
**文件**：`state.ts`, `graph.ts`, `instruction-loader.ts`, `schema.ts`, `resolver.ts`

**核心职责**：
1. **依赖追踪** - 维护工件间的DAG关系
2. **状态检测** - 通过文件存在性判断工件完成
3. **指令生成** - 为工件打包完整的AI指令

**关键函数**：
```typescript
getNextArtifacts(changeDir, completed) 
  → 返回"现在能做什么"的工件列表

detectCompleted(changeDir) 
  → 扫描文件系统，返回已完成工件

generateInstructions(context, artifactId) 
  → 生成包含背景+规则+模板+依赖的指令
```

**设计精妙**：
- 无数据库，直接用文件系统状态
- 支持模板系统（每个工件有对应模板）
- 依赖内容自动传递给下游工件

---

### 模块 2：Schema System
**位置**：`src/core/schemas/`, `src/core/project-config.ts`  
**文件**：`schema-loader.ts`, `config-loader.ts`, `resolver.ts`

**核心职责**：
1. **工作流定义** - 加载schema.yaml定义工件和依赖
2. **配置级联** - 支持项目级、用户全局、包内置三层
3. **Schema验证** - 检查无循环、无重复ID等

**三层级联**：
```
1️⃣ Project-local: ./openspec/schemas/spec-driven/
2️⃣ User global: ~/.openspec/schemas/spec-driven/
3️⃣ Package built-in: node_modules/@openspec/schemas/
```

**设计精妙**：
- 不修改代码就能定制工作流
- 三层级联既保证通用性又保证灵活性
- Zod验证框架确保schema格式正确

---

### 模块 3：Archive & Merge Engine
**位置**：`src/core/archive.ts`, `src/core/specs-apply.ts`

**核心职责**：
1. **Delta解析** - 解析ADDED/MODIFIED/REMOVED/RENAMED
2. **Merge应用** - 将变更应用到main specs
3. **状态转移** - 完成后移动change到archive/

**关键算法**（REMOVED→RENAMED→MODIFIED→ADDED）：
```typescript
// 应用顺序很重要：
1. 删除（REMOVED）所有不需要的需求
2. 重命名（RENAMED）需求
3. 修改（MODIFIED）已有需求
4. 添加（ADDED）新需求

// 这样可以避免冲突
```

**设计精妙**：
- 顺序确定，无冲突
- All-or-nothing事务保证一致性
- 完整的错误处理和回滚

---

### 模块 4：Validator（多层验证）
**位置**：`src/core/validation/`

**核心职责**：
1. **Gate 1** - 工件完整性（是否所有必需文件存在）
2. **Gate 2** - 格式验证（markdown结构是否正确）
3. **Gate 3** - Delta格式验证（ADDED/MODIFIED等是否有效）
4. **Gate 4** - 内容验证（spec内容是否符合规则）
5. **Gate 5** - 干跑merge（模拟merge看是否失败）

**设计精妙**：
- 多个gate分布，快速反馈
- 每个gate独立，清晰职责
- 失败时给出具体的错误位置

---

### 模块 5：CLI Orchestrator
**位置**：`src/cli/`, `src/commands/`, `src/commands/workflow/`

**核心职责**：
1. **命令注册** - 用Commander.js注册所有命令
2. **生命周期管理** - 处理命令执行流程
3. **错误处理** - 统一的错误报告

**命令树**：
```
openspec
├── new-change         (workflow)
├── status            (workflow/status.ts)
├── workflow
│   ├── instructions  (workflow/instructions.ts)
│   ├── new-change    (workflow/new-change.ts)
│   └── archive       (workflow/archive.ts)
├── spec
│   ├── validate      (spec.ts)
│   ├── update        (spec.ts)
│   └── show          (spec.ts)
├── config            (config.ts)
├── show              (show.ts)
├── completion        (completion.ts)
└── [more...]
```

---

## 🎯 顶层20% 的设计洞察

### 洞察 1：✅ 文件系统即状态存储

**设计选择**：不用数据库，用文件存在性表达状态

**好处**：
- 简洁（无同步问题）
- 直观（用户可见）
- 版本控制友好（git兼容）

**代价**：
- 性能（文件I/O）
- 并发（无锁保护）
- 大规模（可能变慢）

**案例**：
```
proposal.md 存在    →  proposal 工件完成
specs/ 非空        →  specs 工件完成
design.md 存在     →  design 工件完成

状态完全由文件决定，无需查询DB
```

---

### 洞察 2：✅ Schema 驱动工作流定义

**设计选择**：工作流完全由YAML定义，无硬编码

**好处**：
- 可定制（项目间差异很大）
- 可复用（schema可以是通用的）
- 可演进（升级schema无需改代码）

**配置样例**：
```yaml
artifacts:
  - id: proposal
    requires: []
    generates: proposal.md
    description: "..."
    
  - id: specs
    requires: [proposal]
    generates: specs/**/*.md
    
  - id: design
    requires: [specs]
    generates: design.md
```

---

### 洞察 3：✅ Specs vs Changes 分支模型

**设计选择**：Main specs 和Feature changes 分离

**好处**：
- 隔离（各自独立工作，无冲突）
- 安全（main始终稳定）
- 审查友好（review单一变更）

**架构**：
```
openspec/
├── specs/           ← Main（稳定）
│   ├── auth/
│   └── payment/
│
└── changes/         ← Branches（隔离）
    ├── feature-login/
    │   ├── proposal.md
    │   ├── specs/
    │   └── design.md
    │
    └── feature-oauth/
        ├── proposal.md
        └── specs/
```

Archive时，将change的specs（delta格式）应用到main specs。

---

### 洞察 4：✅ Delta Spec 格式优雅

**设计选择**：用ADDED/MODIFIED/REMOVED/RENAMED表达变更

**好处**：
- 清晰（用户意图明确）
- 合并简单（操作顺序确定）
- 无冲突（大多数情况自动处理）

**格式样例**：
```markdown
## ADDED Requirements
### Requirement: OAuth Support
  OAuth2 provider integration for user auth

## MODIFIED Requirements
### Requirement: User Authentication  
  Support both JWT and OAuth2 tokens

## REMOVED Requirements
- Legacy LDAP Support
```

---

### 洞察 5：✅ 三层配置级联

**设计选择**：配置支持项目级、用户全局、包内置三层

**好处**：
- 新用户：用内置defaults（开箱即用）
- 团队：在~/.openspec/定义团队标准
- 项目：在project/openspec/定义特殊需求

**级联顺序**：
```
1. 检查项目: ./openspec/config.yaml
2. 检查用户: ~/.openspec/config.yaml
3. 使用默认: package built-in defaults
```

---

## 📊 模块关系图

```
┌────────────────────────────────────┐
│  Commands                          │
│  (new-change, status, archive...)  │
└──┬──┬──┬───────────────┬──────┬───┘
   │  │  │               │      │
   v  v  v               v      v
┌────────────────────────────────────┐
│  Artifact Graph  │  Schema System   │
│  • DAG依赖       │  • 工作流定义    │
│  • 工件检测      │  • 配置加载      │
│  • 指令生成      │  • 验证          │
└──┬──────────────┬──────────────┬───┘
   │              │              │
   v              v              v
┌────────────────────────────────────┐
│  Archive Engine  →  Validator      │
│  •Delta解析      │  • 多层验证     │
│  • Merge应用     │  • Gate检查     │
│  • 状态转移      │  • 错误收集     │
└────────┬──────────────────────────┘
         │
         v
┌────────────────────────────────────┐
│  File System (openspec/)           │
│  • specs/  • changes/  • archive/  │
└────────────────────────────────────┘
```

---

## 🎓 This Phase 学完了什么

✅ 系统的完整架构（5层）  
✅ 工作流的全过程（7步）  
✅ 5大模块的职责和接口  
✅ 顶层5个设计洞察  
✅ 模块之间如何协作  

**下一步**：深入学习 Phase 2（工作流FSM和关键路径）

