# Phase 3: 单模块精读 - Schema 驱动系统

## 模块：Schema System - "代码就是配置"的体现

### 职责定位

**核心职责**：
- 📋 定义工作流（artifact 序列）
- 🎯 提供 AI 生成的模板
- ⚙️ 接收项目自定义配置
- 🔀 支持多个工作流并存

**不负责**：
- ❌ 生成 artifact 内容（这是 AI 的工作）
- ❌ 验证 artifact 内容（这是 validation/ 的工作）
- ❌ 追踪 artifact 完成状态（这是 artifact-graph/ 的工作）

### 在系统中的位置

```
用户配置层：
  openspec/config.yaml        ← Project-level 配置
    └─ 指定 schema 名称
    └─ 注入 context（项目背景）
    └─ 定义规则
  
Schema 选择层：
  openspec/schemas/           ← Project-local schemas（优先度 #1）
  ~/.openspec/schemas/        ← User global schemas（优先度 #2）
  @openspec/schemas/          ← Package built-in（优先度 #3）
  
被 Artifact Graph 使用：
  loadSchema() 
    └─ 读取 schema.yaml
    └─ 验证结构
    └─ 构建 ArtifactGraph
    
被指令生成使用：
  generateInstructions()
    ├─ 加载 template 文件
    ├─ 注入 config 的 context
    ├─ 注入 config 的 rules
    └─ 生成 XML 给 AI
```

### 上游 / 下游

**上游**（谁调用 Schema）：
- src/commands/workflow/ - 所有命令都需要 resolveSchema()
- src/core/artifact-graph/ - 构建图时需要加载 schema.yaml

**下游**（Schema 依赖什么）：
- 文件系统：读取 schema.yaml 和 templates/
- yaml 库：解析 YAML 文件
- Zod：验证数据结构

### 输入 / 输出

#### 输入

```typescript
resolveSchema("spec-driven", projectRoot)
  ↓
输入文件：
  // 按优先级查找
  (1) projectRoot/openspec/schemas/spec-driven/schema.yaml
  (2) ~/.openspec/schemas/spec-driven/schema.yaml
  (3) @openspec/schemas/spec-driven/schema.yaml
  
文件内容示例：
  name: spec-driven
  version: 1
  artifacts:
    - id: proposal
      generates: proposal.md
      requires: []
    - id: specs
      generates: specs/**/*.md
      requires: [proposal]
```

#### 输出

```typescript
SchemaYaml {
  name: "spec-driven",
  version: 1,
  description: "Default workflow",
  artifacts: [
    {
      id: "proposal",
      generates: "proposal.md",
      description: "...",
      template: "proposal.md",  // 从 templates/ 读取
      instruction: "...",       // 额外指引
      requires: []
    },
    // ... 其他工件
  ],
  apply?: {
    requires: ["proposal", "specs", "design", "tasks"],
    tracks: "tasks.md"
  }
}
```

### 核心数据结构

#### 三层配置系统

```
┌─────────────────────────────────────────┐
│ Layer 1: Schema Definition              │
│ (工作流是什么)                            │
│                                         │
│ artifacts:                              │
│   - id: proposal                        │
│     requires: []                        │
│   - id: specs                           │
│     requires: [proposal]                │
│   - id: design                          │
│     requires: [specs]                   │
│   - id: tasks                           │
│     requires: [design]                  │
└─────────────────────────────────────────┘
           ↓ 被 artifact-graph 使用
┌─────────────────────────────────────────┐
│ Layer 2: Project Config                 │
│ (这个项目的规则是什么)                   │
│                                         │
│ openspec/config.yaml:                   │
│   schema: spec-driven                   │
│   context: |                            │
│     Tech stack: TypeScript, React       │
│     API style: RESTful                  │
│   rules:                                │
│     proposal:                           │
│       - Include rollback plan           │
│     specs:                              │
│       - Use Given/When/Then format      │
└─────────────────────────────────────────┘
           ↓ 被指令生成使用
┌─────────────────────────────────────────┐
│ Layer 3: Instructions for AI             │
│ (告诉 AI 如何生成这个工件)                │
│                                         │
│ <artifact id="specs">                   │
│   <task>Create spec files</task>        │
│   <project_context>                     │
│     Tech stack: TypeScript, React       │
│   </project_context>                    │
│   <rules>                               │
│     - Use Given/When/Then format        │
│   </rules>                              │
│   <template>[模板内容]</template>       │
│   <dependencies>                        │
│     [前置工件的内容]                    │
│   </dependencies>                       │
│ </artifact>                             │
└─────────────────────────────────────────┘
```

### 三层 Schema 解析体系

#### 解析层级 1: YAML 文件 → JSON

```typescript
// src/core/artifact-graph/schema.ts
function parseSchema(yamlContent: string): SchemaYaml {
  const parsed = parseYaml(yamlContent);  // yaml → JSON
  
  // Zod 验证
  const result = SchemaYamlSchema.safeParse(parsed);
  if (!result.success) {
    throw new SchemaValidationError(...);
  }
  
  return result.data;
}
```

#### 解析层级 2: 依赖图验证

```typescript
validateNoDuplicateIds(schema.artifacts)
  // ✔️ 所有工件 ID 唯一

validateRequiresReferences(schema.artifacts)
  // ✔️ requires 中的每个 ID 都存在

validateNoCycles(schema.artifacts)
  // ✔️ 没有循环依赖
  // 使用 DFS 检测
```

#### 解析层级 3: 分辨率 (Resolution Order)

```typescript
function getSchemaDir(name: string, projectRoot?: string): string | null {
  // 1️⃣ 项目本地 (最高优先级)
  if (projectRoot) {
    const projectDir = projectRoot/openspec/schemas/name/
    if (schema.yaml 存在) return projectDir;
  }
  
  // 2️⃣ 全局用户目录
  const userDir = ~/.openspec/schemas/name/
  if (schema.yaml 存在) return userDir;
  
  // 3️⃣ 包内置目录 (最低优先级)
  const packageDir = @openspec/schemas/name/
  if (schema.yaml 存在) return packageDir;
  
  return null;  // 未找到
}
```

**设计意图**：
- 用户可以覆盖任何 schema（包括内置的）
- 不同项目可用不同 schema
- 全局 schema 在所有项目间共享
- 级联查找，最近的优先

### 边界定义

**Schema 负责定义**：
- ✅ 工件 ID 和名称
- ✅ 生成的文件路径
- ✅ 工件间的依赖关系
- ✅ 各工件的模板
- ✅ AI 生成的基础指引

**Schema 不负责**：
- ❌ 工件内容的具体格式（由模板决定）
- ❌ 项目特定的规则（由 config 决定）
- ❌ 工件的验证标准
- ❌ 工件的实际生成（由 AI 决定）

### 核心算法

#### 算法 1: 循环检测

```typescript
function validateNoCycles(artifacts): void {
  const artifactMap = Map(artifacts.map(a => [a.id, a]));
  const visited = Set;
  const inStack = Set;  // 当前 DFS 路径上的节点
  
  function dfs(id): string | null {
    visited.add(id);
    inStack.add(id);
    
    const artifact = artifactMap.get(id);
    for (const dep of artifact.requires) {
      if (!visited.has(dep)) {
        const cycle = dfs(dep);
        if (cycle) return cycle;
      } else if (inStack.has(dep)) {
        // 找到循环!
        return reconstructCyclePath(id, dep);
      }
    }
    
    inStack.delete(id);
    return null;
  }
  
  // 对每个未访问的节点运行 DFS
  for (const artifact of artifacts) {
    if (!visited.has(artifact.id)) {
      const cycle = dfs(artifact.id);
      if (cycle) throw new Error(`Cycle: ${cycle}`);
    }
  }
}

/**
 * 输出示例：
 * Cycle: proposal → specs → design → proposal
 */
```

**时间复杂度**：O(V + E)，其中 V = 工件数，E = 依赖关系数

#### 算法 2: Schema 分辨率

```typescript
function resolveSchema(name, projectRoot): SchemaYaml {
  const schemaDir = getSchemaDir(name, projectRoot);
  if (!schemaDir) {
    const available = listSchemas(projectRoot);
    throw new Error(
      `Schema '${name}' not found. Available: ${available.join(', ')}`
    );
  }
  
  const schemaPath = path.join(schemaDir, 'schema.yaml');
  const content = fs.readFileSync(schemaPath, 'utf-8');
  return parseSchema(content);
}
```

**分辨率过程**（level by level）：
1. 尝试项目本地目录
2. 尝试全局用户目录
3. 尝试包内置目录
4. 如果都没找到，列出所有可用的并提示错误

### 约束与设计规则

#### 约束 #1: Schema ID 全局唯一

```yaml
# ❌ 不允许
artifacts:
  - id: proposal
  - id: proposal  ← 重复!
```

**防护机制**：
```typescript
validateNoDuplicateIds(artifacts)
  // 在 parseSchema 时检查
  // 拒绝加载有重复 ID 的 schema
```

#### 约束 #2: Requires 必须指向已存在的工件

```yaml
# ❌ 不允许
artifacts:
  - id: proposal
    requires: [nonexistent]  ← nonexistent 未定义!
```

**防护机制**：
```typescript
validateRequiresReferences(artifacts)
  // 检查所有 requires 中的 ID 都在 artifacts 中定义
```

#### 约束 #3: 不允许循环依赖

```yaml
# ❌ 不允许
artifacts:
  - id: proposal
    requires: [specs]
  - id: specs
    requires: [proposal]  ← 循环!
```

**防护机制**：
```typescript
validateNoCycles(artifacts)
  // 使用 DFS 检测
```

#### 约束 #4: Config size 上限

```typescript
const MAX_CONTEXT_SIZE = 50 * 1024;  // 50KB

// readProjectConfig() 检查
if (contextSize > MAX_CONTEXT_SIZE) {
  console.warn(`Context too large, ignoring...`);
}
```

**原因**：
- 防止 config 变成垃圾堆
- Token 成本考虑（context 会被注入到 AI 提示词）

### 项目配置系统 (Project Config)

#### 配置结构

```typescript
interface ProjectConfig {
  schema: string;           // "spec-driven"
  context?: string;         // 项目背景信息（<50KB）
  rules?: {
    [artifactId]: string[]  // 按工件类型定义规则
  }
}
```

#### 配置示例

```yaml
# openspec/config.yaml
schema: spec-driven

context: |
  Tech stack: TypeScript, React, Node.js, PostgreSQL
  API style: RESTful with JSON payloads
  Testing: Jest + React Testing Library
  Database: PostgreSQL 14+
  Key principle: Backwards compatibility for all public APIs

rules:
  proposal:
    - Include rollback plan if backwards-incompatible
    - Identify affected teams and systems
    - Link to related RFCs or design docs
  
  specs:
    - Use Given/When/Then format for all scenarios
    - Reference existing capabilities in openspec/specs/
    - Don't invent new vocabulary, follow existing patterns
    - Mark breaking changes explicitly with **BREAKING**
  
  design:
    - Explain trade-offs vs alternative approaches
    - Include security and performance considerations
    - Link to architectural patterns we follow
  
  tasks:
    - Break down into testable units
    - Include e2e tests for new features
    - Add migration scripts if schema changes
```

#### 配置注入流程

```
Phase: 生成 proposal

用户：/opsx:continue
  ↓
readProjectConfig(projectRoot)
  ├─ 读取 openspec/config.yaml
  ├─ 解析 schema, context, rules
  └─ 返回 ProjectConfig
  
generateInstructions(context, "proposal")
  ├─ 加载这个config
  ├─ 提取 context 字段
  ├─ 提取 rules.proposal
  └─ 构建指令
  
printInstructionsText()
  └─ 输出给 AI:
    <project_context>
    Tech stack: TypeScript, React...
    API style: RESTful...
    </project_context>
    
    <rules>
    - Include rollback plan
    - Identify affected teams
    </rules>
    
    <template>
    # Proposal: {name}
    
    ## Why
    ...
    </template>
```

**设计意图**：
- 用户编写一次规则，所有工件都受约束
- Context 对所有工件可见
- 工件特定的规则针对性更强

### 失败模式

#### 失败 #1: Schema 不存在

```
用户运行：/opsx:new --schema nonexistent feature-name
```

**防护**：
```typescript
const available = listSchemas(projectRoot);
throw new Error(
  `Schema 'nonexistent' not found. Available: ${available.join(', ')}`
);
```

#### 失败 #2: Schema 有循环依赖

```yaml
artifacts:
  - id: a
    requires: [b]
  - id: b
    requires: [c]
  - id: c
    requires: [a]  ← 循环!
```

**防护**：
```typescript
// 在 parseSchema 中立即检测
throw new SchemaValidationError(
  `Cyclic dependency: a → b → c → a`
);
```

#### 失败 #3: Config.yaml 中 context 过大

**防护**：
```typescript
if (contextSize > MAX_CONTEXT_SIZE) {  // 50KB
  console.warn(`Context too large, ignoring...`);
  config.context = undefined;
}
```

#### 失败 #4: Config.yaml 格式错误

```yaml
# ❌ 错误
schema: ["array", "not", "string"]  ← schema 必须是 string
context: 123                         ← context 必须是 string
rules: "not an object"              ← rules 必须是 object
```

**防护**：
```typescript
// Zod validates each field independently (resilient parsing)
const schemaResult = z.string().min(1).safeParse(raw.schema);
if (!schemaResult.success) {
  console.warn(`Invalid 'schema' field`);
  // config.schema 不被设置，使用默认值
}
```

### 可迁移做法

#### 做法 #1: 多层级配置与优先级

```
Project-local >> User global >> Package built-in
```

**适用场景**：
- 不同项目有不同规则
- 队伍有全局规则想共享
- 有内置默认行为

**实现模板**：
```typescript
function resolve(name, projectRoot) {
  // 1. projectRoot/local/
  if (exists(projectRoot/local/name)) return load(...);
  
  // 2. ~/.global/
  if (exists(HOME/.global/name)) return load(...);
  
  // 3. /package/default/
  if (exists(/package/default/name)) return load(...);
  
  throw new Error(`Not found`);
}
```

#### 做法 #2: 分离定义层和约束层

```
定义层（Schema）:
  ├─ 工件是什么
  ├─ 依赖关系
  └─ 通用模板

约束层（Config）:
  ├─ 项目特定背景
  ├─ 规则和最佳实践
  └─ 工件特定指引
```

**优势**：
- Schema 可以跨项目复用
- Config 可以针对项目定制
- 二者独立变化

#### 做法 #3: Zod 的 "resilient parsing"

```typescript
// 而不是一个错误就全部失败
const config: Partial<ProjectConfig> = {};

const schemaResult = schemaField.safeParse(raw.schema);
if (schemaResult.success) {
  config.schema = schemaResult.data;
} else {
  console.warn(`Invalid schema field`);
  // 继续处理其他字段
}

const contextResult = contextField.safeParse(raw.context);
if (contextResult.success) {
  config.context = contextResult.data;
} else {
  console.warn(`Invalid context field`);
  // 继续处理
}

// 返回部分的 config，而不是完全失败
return config as Partial<ProjectConfig>;
```

**优势**：
- 一个字段错误不阻止整个系统
- 用户能逐步修复问题
- 不言自明的错误信息

---

## Schema System 的关键洞察

### 教学 #1: "配置 > 代码" 的力量

传统系统：工作流硬编码在代码中
```typescript
// 要改工作流，必须改代码
if (proposal_done) {
  enable_specs_command();
} else if (specs_done) {
  enable_design_command();
}
```

OpenSpec 模式：工作流在配置中
```yaml
# 要改工作流，只需改 YAML
artifacts:
  - id: proposal
    requires: []
  - id: specs
    requires: [proposal]
```

**优势**：
- 非技术人员可以改工作流
- 不需要重新编译/部署
- 多个工作流可以共存
- 用户可以 fork 和自定义

### 教学 #2: 层级化信息流

```
Global (Package)
  ├─ Default schema（内置工作流）
  └─ Default templates（标准模板）

    ↓ 可被覆盖

User Local (~/.openspec)
  ├─ Custom schema（用户的最佳实践）
  └─ Custom templates

    ↓ 可被覆盖

Project Local (openspec/)
  ├─ Project schema（这个项目特有的流程）
  ├─ Project config（规则、背景）
  └─ Custom templates（针对这个项目）
```

这个级联结构让 OpenSpec 既有坚实的默认值，又支持深度定制。

### 教学 #3: 验证，但不要失败

```typescript
// Schema 验证：严格（不允许有问题）
parseSchema(content)
  // 任何问题都 throw，系统无法继续

// Config 验证：宽松（忽略问题，用默认值）
readProjectConfig(projectRoot)
  // 字段错误 → 警告 + 跳过该字段 + 返回部分 config
  // 不会 throw
```

**原因**：
- Schema 是系统必须依赖的结构，必须严格
- Config 是可选的优化，应该容错
- 一个工件特定的规则错误不应该破坏整个系统
