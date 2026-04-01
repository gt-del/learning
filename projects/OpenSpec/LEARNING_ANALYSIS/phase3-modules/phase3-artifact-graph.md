# Phase 3: 单模块精读 - 工件图系统 (Artifact Graph)

## 模块：Artifact Graph - 系统的神经中枢

### 职责定位

**核心功能**：
- 🧠 追踪工件间的依赖关系
- 📊 检测工件完成状态
- 🚦 决定下一步可用命令
- 📝 生成AI提示词的上下文

**产品形态**：
```
用户运行 /opsx:status
  ↓ [调用 artifact-graph]
  ├─ 加载 schema.yaml
  ├─ 构建依赖图
  ├─ 检测文件系统状态 (proposal.md 存在？)
  ├─ 计算可用工件
  └─ 格式化输出给用户
```

### 在整个系统状态机中的位置

```
系统流程：

New Change           Artifact Graph       AI 生成           Artifact Graph
                     检测初始状态                           检测新状态
   │                      │                   │                  │
   ├─→ 创建容器  ─→  [都是空的]  ─→  何时调用 continue ─→ [proposal done]
   │                  getNextArtifacts          │
   │                  返回 ['proposal']         │
   │                                          ↓
   │         Artifact Graph 再次检测     [specs ready]
   │         getNextArtifacts 返回       
   │         ['specs']
   └──────────────────────────────────────→ ...一直循环直到全部完成

Apply Phase         Artifact Graph        执行所有 tasks    Artifact Graph
   │                    │                      │                  │
   ├─→ isComplete?  ─→ true ───────────→  继续运行  ─→  progress tracking
   │                                        (内存态)      (不在 AG 负责)
   │
   └─→ false ─→ 拒绝执行 (输出 BLOCKED)
```

### 上游 / 下游

**上游（输入方）**：
- `src/commands/workflow/*.ts` - 所有 workflow 命令都调用我
  - status.ts: `loadChangeContext()` → `formatChangeStatus()`
  - instructions.ts: `generateInstructions()` - 生成提示词
  - new-change.ts: `resolveSchema()` - 选择 schema

**下游（被调用方）**：
- `src/core/schemas/` - 读取 schema 定义
- `src/core/artifact-graph/state.ts` - 检测文件系统状态
- 文件系统 - 读取工件文件 (proposal.md, specs/, 等)

### 输入 / 输出

#### 输入类型

**Input #1: Change Context 加载**
```typescript
loadChangeContext(projectRoot, changeName, schemaName?)
  ↓
输入：
  - projectRoot: string          // 项目根目录
  - changeName: string           // "add-logout-button"
  - schemaName?: string          // "spec-driven" (可选，会自动检测)
  
返回：
  ChangeContext {
    graph: ArtifactGraph         // 依赖图对象
    completed: Set<string>       // {"proposal", "specs"}
    schemaName: string           // "spec-driven"
    changeName: string
    changeDir: string
    projectRoot: string
  }
```

**Input #2: Status 查询**
```typescript
formatChangeStatus(context)
  ↓
输入：完整的 ChangeContext
  
返回：
  ChangeStatus {
    changeName: "add-logout-button"
    schemaName: "spec-driven"
    isComplete: false            // 还有未完成的工件
    applyRequires: ["proposal", "specs", "design", "tasks"]
    artifacts: [
      { id: "proposal", outputPath: "proposal.md", status: "done" },
      { id: "specs", outputPath: "specs/**/*.md", status: "ready" },
      { id: "design", outputPath: "design.md", status: "blocked", missingDeps: ["specs"] },
      { id: "tasks", outputPath: "tasks.md", status: "blocked", missingDeps: ["design"] }
    ]
  }
```

### 核心数据结构

#### ArtifactGraph - 依赖图对象

```typescript
class ArtifactGraph {
  // 内部：所有工件的定义 Map
  private artifacts: Map<string, Artifact>;
  private schema: SchemaYaml;
  
  // 读操作
  getArtifact(id: string): Artifact | undefined
  getAllArtifacts(): Artifact[]
  getName(): string
  getVersion(): number
  
  // 依赖分析
  getBuildOrder(): string[]                    // Kahn 算法计算拓扑排序
  getNextArtifacts(completed): string[]        // 返回可立即执行的工件
  getBlocked(completed): BlockedArtifacts      // 返回被 block 的工件及其原因
  isComplete(completed): boolean               // 是否全部完成
}
```

#### Artifact - 单个工件定义

```typescript
interface Artifact {
  id: string;                   // "proposal" / "specs" / "design" / "tasks"
  generates: string;            // "proposal.md" 或 "specs/**/*.md"
  description: string;          // UI 显示的文本
  template: string;             // 从 schema 的 templates/ 目录读取
  instruction?: string;         // 额外的 AI 指引
  requires: string[];           // ["proposal"] - 依赖列表
}
```

### 边界定义

**Module 内部负责**：
- ✅ 依赖图构建 (graph.ts)
- ✅ 工件完成状态检测 (state.ts)
- ✅ 下一步工件推荐 (graph.getNextArtifacts)
- ✅ 提示词格式化 (instruction-loader.ts)
- ✅ Schema 加载和验证 (schema.ts, resolver.ts)

**Module 外部负责**：
- ❌ 文件写入 (由 commands/workflow/ 负责)
- ❌ 提示词补全 (由 prompts/ 和每个 command 负责)
- ❌ AI 调用 (由上层 AI 集成负责)
- ❌ 工件内容验证 (由 core/validation/ 负责)

### 约束与设计规则

#### 约束 #1: 文件系统即状态存储

```typescript
// src/core/artifact-graph/state.ts
function detectCompleted(graph: ArtifactGraph, changeDir: string): CompletedSet {
  const completed = new Set<string>();
  
  for (const artifact of graph.getAllArtifacts()) {
    // 检查 artifact.generates 指向的文件是否存在
    if (isArtifactComplete(artifact.generates, changeDir)) {
      completed.add(artifact.id);
    }
  }
  
  return completed;
}

// 这意味着：
// - 没有数据库
// - 没有 .metadata.json 的完成标记
// - 唯一的真实来源是：proposal.md 文件本身存在
// - 用户手工删除 proposal.md → 系统立即认为 proposal 未完成
```

**设计意图**：
- "文件系统即状态机" - 用户直观可见
- 无需同步多个状态存储
- 支持用户手工编辑返工

#### 约束 #2: 全局拓扑序必须确定性

```typescript
// src/core/artifact-graph/graph.ts
getBuildOrder(): string[] {
  // 使用 Kahn 算法计算拓扑序
  // 但关键是：有多个同级节点时，必须排序确保确定性
  
  const queue = [...artifacts.keys()]
    .filter(id => inDegree.get(id) === 0)
    .sort();  // ← 这一行保证确定性
    
  // 新增节点时也要排序
  queue.push(...newlyReady.sort());
  
  return result;
}
```

**设计意图**：
- 用户运行两次 `status`，输出完全相同
- 不依赖 Map 的遍历顺序（JS Map 虽然有顺序但不保证稳定）
- AI 生成基于相同顺序的列表

#### 约束 #3: 工件 ID 在 Schema 中全局唯一

```yaml
# schema.yaml
artifacts:
  - id: proposal        # ← 全局唯一，不能重复
  - id: specs           # ← 全局唯一
  - id: design
  - id: tasks
```

**验证方法**：
```typescript
// 在 schema 加载时
const ids = schema.artifacts.map(a => a.id);
const uniqueIds = new Set(ids);
if (uniqueIds.size !== ids.length) {
  throw new Error('Duplicate artifact IDs in schema');
}
```

### 失败模式与防护

#### 失败 #1: Circular Dependency

```
如果 schema 定义了：
- proposal requires: []
- specs requires: ['proposal']
- design requires: ['specs']
- proposal requires: ['design']  ← 后来有人加了这个
```

**防护**：
```typescript
// getBuildOrder() 使用 Kahn 算法
// 如果有循环，最后会有节点 in-degree 仍 > 0
// 由于遍历完所有节点就停止，会导致 result.length !== artifacts.length
// → 可检测并报错
```

**防护位置**：schema validation 时

#### 失败 #2: 工件文件被意外删除

```
用户在 /opsx:continue 后、生成 proposal.md 前意外删除了它
```

**防护**：
- `isArtifactComplete()` 每次都从文件系统检查
- 如果文件被删除，下一次 status 或 continue 会自动检测到
- 系统会重新标记为未完成

#### 失败 #3: Schema 中引用不存在的工件

```
task 的 requires: ['proposal', 'nonexistent']
```

**防护**：
```typescript
// artifact-graph 没有显式防护
// 在 getNextArtifacts 时：
const allDepsCompleted = artifact.requires.every(req => completed.has(req));
// 如果 'nonexistent' 不在 completed 中，它永远不会被标记为完成
// → 该工件永远 blocked

// 防护应该在 schema validation 时进行（但当前没实现）
```

#### 失败 #4: Windows 路径兼容性

```typescript
// src/core/artifact-graph/state.ts
function hasGlobMatches(pattern: string): boolean {
  // "specs/**/spec.md" 在 Windows 中变成 "specs\**\spec.md"
  const normalizedPattern = FileSystemUtils.toPosixPath(pattern);
  const matches = fg.sync(normalizedPattern);  // glob 库需要 posix 格式
  return matches.length > 0;
}
```

### 可迁移做法

#### 做法 #1: 文件系统 + 依赖图的状态模式

**可迁移到**：
- 其他文件驱动的 workflow 系统
- Git 工作流（branch 作为容器，commit message 作为工件）
- 文档生成系统（markdown 文件的依赖追踪）

**关键点**：
```
1. 用文件存在性作为"完成"标志
2. 从文件系统读状态，不用数据库
3. 依赖图是内存计算的，不持久化
4. 每次命令都重新计算完整状态
```

**实现模板**：
```typescript
interface Artifact {
  id: string;
  generates: string;              // 文件路径
  requires: string[];             // 依赖的工件 ID
}

function detectCompleted(artifacts, workingDir): Set<string> {
  const completed = new Set();
  for (const artifact of artifacts) {
    if (fileOrGlobMatches(artifact.generates, workingDir)) {
      completed.add(artifact.id);
    }
  }
  return completed;
}

function getNextArtifacts(artifacts, completed): string[] {
  return artifacts
    .filter(a => !completed.has(a.id))
    .filter(a => a.requires.every(r => completed.has(r)))
    .map(a => a.id);
}
```

#### 做法 #2: 分层提示词生成

**OpenSpec 的做法**：
```typescript
function generateInstructions(context, artifactId, projectRoot) {
  // 获取已完成的所有工件内容
  const dependencies = context.graph
    .getArtifact(artifactId)
    .requires
    .map(id => ({
      id,
      path: getArtifactPath(id),
      content: readFileIfExists(getArtifactPath(id))
    }));
  
  // 构建多层次提示
  return {
    task: `Create ${artifactId}`,
    context: loadProjectContext(),       // 全局背景
    rules: loadRulesForArtifact(id),     // 工件特定规则
    dependencies: dependencies,           // 前置工件
    template: loadTemplate(id),          // 模板
  };
}
```

**可迁移性**：⭐⭐⭐⭐⭐
这个模式对所有"多步骤生成"系统都有效。

#### 做法 #3: Topological Sort 确保确定性输出

```typescript
// Kahn 算法 + 每步排序
getBuildOrder(): string[] {
  const queue = seeds.sort();  // ← 第一次排序
  while (queue.length > 0) {
    // 处理节点
    queue.push(...newlyReady.sort());  // ← 每次都排序
  }
  return result;
}
```

**为什么重要**：
- 用户看到的列表顺序必须连贯
- AI 看到的依赖关系必须一致
- 测试必须确定性

---

## 核心算法：Artifact Graph 的 3 个关键方法

### 算法 1: getNextArtifacts - 最关键的决策算法

```typescript
getNextArtifacts(completed: CompletedSet): string[] {
  const ready: string[] = [];
  
  // 逐个检查每个工件
  for (const artifact of this.artifacts.values()) {
    // 1️⃣ 已完成就跳过
    if (completed.has(artifact.id)) {
      continue;
    }
    
    // 2️⃣ 检查依赖是否全部满足
    const allDepsCompleted = artifact.requires.every(req => completed.has(req));
    
    // 3️⃣ 如果依赖全部满足，加入可用列表
    if (allDepsCompleted) {
      ready.push(artifact.id);
    }
  }
  
  // 4️⃣ 排序确保确定性
  return ready.sort();
}
```

**时间复杂度**：O(n × m)，其中 n = 工件数，m = 平均依赖数

**调用场景**：
```
/opsx:status
/opsx:continue (选择下一步)
任何需要显示"可用命令"的地方
```

**设计洞察**：
- 没有递归或深度遍历
- 每个工件独立评估
- 输出大小 = [0, 工件总数]

### 算法 2: detectCompleted - 状态检测

```typescript
function detectCompleted(graph, changeDir): CompletedSet {
  const completed = new Set<string>();
  
  if (!fs.existsSync(changeDir)) {
    return completed;  // 目录不存在，全部未完成
  }
  
  for (const artifact of graph.getAllArtifacts()) {
    // 检查 generates 字段
    // - 简单路径: "proposal.md" → fs.existsSync()
    // - Glob 模式: "specs/**/*.md" → fg.sync()
    
    if (isArtifactComplete(artifact.generates, changeDir)) {
      completed.add(artifact.id);
    }
  }
  
  return completed;
}

function isArtifactComplete(generates: string, changeDir: string): boolean {
  const fullPattern = path.join(changeDir, generates);
  
  if (isGlobPattern(generates)) {
    return hasGlobMatches(fullPattern);
  } else {
    return fs.existsSync(fullPattern);
  }
}
```

**关键设计决策**：
- "完成" = 文件存在且非空？ ❌ 不，只要存在即可
- "完成" = 文件是否被修改过？ ❌ 不，系统不追踪修改时间
- "完成" = 依赖的 mtime > 最后一次 continue？ ❌ 不

**原因**：
- 保持简单：用户编辑工件是正常操作
- 无 mtime 依赖：支持文件系统 copy/restore
- 文件系统即事实：没有隐藏状态

### 算法 3: generateInstructions - 提示词生成

```typescript
function generateInstructions(context, artifactId, projectRoot) {
  const artifact = context.graph.getArtifact(artifactId);
  
  // 1️⃣ 加载前置工件内容
  const dependencies = artifact.requires.map(reqId => {
    const req = context.graph.getArtifact(reqId);
    const outputPath = path.join(context.changeDir, req.generates);
    return {
      id: reqId,
      path: req.generates,
      done: context.completed.has(reqId),
      description: req.description,
      // 对于 glob 模式，这里需要找到实际文件
    };
  });
  
  // 2️⃣ 加载项目上下文（全局信息）
  const config = readProjectConfig(projectRoot);
  const context_text = config.context;
  
  // 3️⃣ 加载工件特定规则
  const rules = config.rules?.[artifactId] || [];
  
  // 4️⃣ 加载模板
  const template = loadTemplate(context.schemaName, artifact.template);
  
  // 5️⃣ 返回结构化指令
  return {
    artifactId,
    changeName: context.changeName,
    schemaName: context.schemaName,
    changeDir: context.changeDir,
    outputPath: artifact.generates,
    description: artifact.description,
    instruction: artifact.instruction,    // Schema 中定义的额外指引
    context: context_text,                // 项目上下文
    rules,                                // 规则
    template,                             // 模板
    dependencies,                         // 前置工件
    unlocks: this.getDependents(artifactId),  // 完成这个后能解锁什么
  };
}
```

**输出用途**：
```
这个结构体被传给 printInstructionsText()
→ 格式化为 XML 标签给 AI 看
→ AI 根据这些信息生成工件
```

---

## 系统与其他模块的交互模式

### 交互 1: Status 命令如何工作

```
用户: /opsx:status --change add-logout

Commands Layer (src/commands/workflow/status.ts)
  ├─ projectRoot = process.cwd()
  ├─ changeName = "add-logout"
  └─ 调用 loadChangeContext(projectRoot, changeName)
      │
      ↓ [Artifact Graph]
      │
      ├─ resolveSchema(projectRoot, changeName) → "spec-driven"
      ├─ 加载 artifacts from schema.yaml
      ├─ 构建 ArtifactGraph 对象
      ├─ 调用 detectCompleted() → 检查文件系统
      │   └─ proposal.md 存在? ✅ yes
      │   └─ specs/ 存在? ❌ no
      │   └─ 返回 {proposal}
      └─ 返回 ChangeContext { graph, completed: {proposal} }
  
          ↓
      
  调用 formatChangeStatus(context)
  ├─ graph.getNextArtifacts(completed)
  │   └─ proposal: 完成 ✅, 跳过
  │   └─ specs: 需要 proposal ✅, 可用 → [specs]
  │   └─ design: 需要 specs ❌, 被 block
  │   └─ tasks: 需要 design ❌, 被 block
  ├─ 构建 ChangeStatus 对象
  └─ 返回给 UI 层
      
UI Layer
  └─ 格式化输出:
      [x] proposal.md
      [ ] specs/      ← ready (can start)
      [-] design.md   ← blocked
      [-] tasks.md    ← blocked
```

### 交互 2: Continue 命令如何工作

```
用户: /opsx:continue --change add-logout (不指定工件)

Commands Layer (instructions.ts)
  ├─ loadChangeContext() → ChangeContext
  ├─ context.graph.getNextArtifacts(context.completed) → ["specs"]
  ├─ (如果多于 1 个，提示用户选择)
  ├─ 选中 "specs"
  └─ 调用 generateInstructions(context, "specs")
      │
      ↓ [Artifact Graph]
      │
      ├─ 获取 specs artifact
      │   └─ requires: ["proposal"]
      ├─ 加载前置工件内容
      │   └─ loadFileContent("proposal.md")
      ├─ 加载项目 context/rules
      ├─ 加载模板
      └─ 返回 ArtifactInstructions
         {
           artifactId: "specs",
           outputPath: "specs/**/*.md",
           dependencies: [{id: "proposal", done: true, ...}],
           template: "[模板内容]",
           rules: ["Create one spec per capability", ...],
           unlocks: ["design"]
         }
  
      ↓
  
  printInstructionsText()
  └─ 输出给 AI:
      <artifact id="specs" change="add-logout" schema="spec-driven">
      <task>
      Create spec files describing what the system should do.
      </task>
      
      <project_context>
      Tech stack: TypeScript, React...
      </project_context>
      
      <rules>
      - Create one spec per capability
      - Use Given/When/Then format
      </rules>
      
      <template>
      # [Capability Name] Specification
      
      ## Purpose
      ...
      </template>
      
      <dependencies>
        <dependency id="proposal" done="true">
          <path>proposal.md</path>
          [proposal.md 内容]
        </dependency>
      </dependencies>
      </artifact>

AI 生成内容
  └─ 根据 template 和 dependencies 生成 specs/**/*.md
  └─ ~/.openspec_ai_input 或通过 stdin 传回

File I/O Layer
  └─ 写入文件: specs/auth/spec.md 等
  
  ↓
  
下一次运行 status
  └─ detectCompleted() 会发现 specs/**/*.md 存在
  └─ design 变成 ready
```

---

## 这个模块教会我们什么

### 教学 #1: "状态 = 文件系统"的威力

传统系统：维护中央状态库（数据库/JSON）
```
├─ 应用当前状态
├─ 用户编辑文件
├─ 文件状态 ≠ 数据库状态
└─ 产生不一致
```

OpenSpec 模式：文件系统即源数据
```
├─ 应用从文件系统读状态
├─ 用户编辑文件
├─ 文件系统 = 唯一的真
└─ 永不不一致
```

### 教学 #2: 工件依赖的"启用器"模式

```
Traditional (强制线性):
  STEP 1 → STEP 2 → STEP 3  (必须这个顺序)

OPSX (依赖启用):
  [dependency check] → [enabled if deps met]
  
  优势：
  - 用户可以跳过某些步骤
  - 并行工作不冲突
  - 返工很容易（删除工件重来）
```

### 教学 #3: 多层次信息的分层传输

```
Layer 1: Schema 定义工件
  ├─ 工件是什么
  └─ 依赖关系

Layer 2: Artifact Graph 追踪状态
  ├─ 哪些完成了
  └─ 下一步是什么

Layer 3: Instructions 生成提示词
  ├─ 加入前置工件内容
  ├─ 加入项目背景
  └─ 生成结构化指令

Layer 4: AI 生成内容
  └─ 基于完整信息创建工件
```

每层都有清晰的职责边界。
