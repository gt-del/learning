# Phase 4: 架构决策提炼 - ADR 视角

## 系统最重要的 8 个架构决策

---

## 决策 1：文件系统即状态存储（而非数据库）

### 决策内容

**不使用中央状态数据库，而是通过检查文件系统来追踪工件完成状态。**

```
设计对比：

传统方式（中央数据库）：
  ├─ 用户生成一个工件 (AI 写入 proposal.md)
  ├─ 系统信号：INSERT INTO artifacts_completed ...
  ├─ 查询状态：SELECT * FROM artifacts WHERE ...
  └─ 问题：文件和数据库同步困难

OpenSpec 方式（文件系统状态）：
  ├─ 用户生成一个工件 (AI 写入 proposal.md)
  ├─ 系统状态：if (fs.existsSync('proposal.md')) { completed.add('proposal') }
  └─ 优势：文件即源数据，不需要同步
```

### 仓库证据

**文件检测**：[src/core/artifact-graph/state.ts](src/core/artifact-graph/state.ts#L1-L30)
```typescript
function detectCompleted(graph: ArtifactGraph, changeDir: string): CompletedSet {
  const completed = new Set<string>();
  if (!fs.existsSync(changeDir)) {
    return completed;  // 文件系统是唯一的真相
  }
  for (const artifact of graph.getAllArtifacts()) {
    if (isArtifactComplete(artifact.generates, changeDir)) {
      completed.add(artifact.id);
    }
  }
  return completed;
}

function isArtifactComplete(generates: string, changeDir: string): boolean {
  const fullPattern = path.join(changeDir, generates);
  if (isGlobPattern(generates)) {
    return hasGlobMatches(fullPattern);  // Glob 匹配
  } else {
    return fs.existsSync(fullPattern);   // 文件存在 = 完成
  }
}
```

**在 glob 中支持 glob 模式**：
- `proposal.md` → 检查单个文件
- `specs/**/*.md` → 检查 glob 匹配
- Windows 兼容性：用 `FileSystemUtils.toPosixPath()` 规范化

### 这个决策解决的问题

1. **同步困难**：多个写入方（IDE、用户手工编辑、AI）不需要通知系统
2. **用户直观性**：用户看得见文件，就知道"什么是完成"
3. **容错性**：用户可以删除工件重新生成，系统自动适应
4. **跨平台一致**：文件系统是通用的状态存储

### 可能被放弃的替代方案

1. **中央 SQLite 数据库**
   - 优：强事务性、可查询
   - 弱：需要数据库初始化、迁移、同步

2. **`.metadata.yaml` 追踪完成标志**
   ```yaml
   completed:
     - proposal
     - specs
   ```
   - 优：显式追踪，无需扫描文件系统
   - 弱：需要维护，容易与实际状态不一致

3. **记录最后修改时间**
   ```
   proposal_mtime: 2025-01-24T10:30:00Z
   ```
   - 优：知道何时完成
   - 弱：依赖文件系统 mtime 的精度

### 这个决策的优点

✅ **即时反映**：用户修改文件 → 系统立即看到新状态
✅ **无数据库运维**：无需 migrations、backups、恢复
✅ **版本控制友好**：工件可以 git commit，状态不需要
✅ **可调试性**：用户直接看到"为什么被认为完成"是查看的文件
✅ **支持并发**：多个 change 可以同时存在，不需要锁

### 这个决策的成本 / 代价

❌ **性能**：每次查询都要扫描文件系统（平均 0.5-1.6ms）
❌ **精度**：不知道工件是何时完成的（只知道是否存在）
❌ **Glob 复杂性**：`specs/**/*.md` 这样的模式需要特殊处理
❌ **用户困惑**：如果用户意外删除文件，可能觉得状态被"重置"了

### 什么场景适合借鉴

✅ **文件驱动的工作流**（Markdown 文档系统、代码生成器）
✅ **需要用户直观理解的系统**（不能有隐藏状态）
✅ **支持手工编辑的系统**（用户可能直接修改源文件）

### 什么场景不该照搬

❌ **需要精确状态历史的系统**（何时完成、谁完成的）
❌ **对性能敏感的系统**（频繁查询文件系统很慢）
❌ **分布式系统**（文件系统状态不可靠）
❌ **需要原子事务的系统**（文件系统操作不是事务性的）

---

## 决策 2：Schema 驱动工作流定义（配置优于代码）

### 决策内容

**不硬编码工作流逻辑，而是通过 YAML schema 定义工件和依赖。**

```
传统方式（代码定义工作流）：
  if (proposal_done) {
    enable_specs_command();
  } else if (specs_done) {
    enable_design_command();
  }
  // 要改工作流，必须改代码

OpenSpec 方式（配置定义工作流）：
  artifacts:
    - id: proposal
      requires: []
    - id: specs
      requires: [proposal]
  // 要改工作流，只需改 YAML
```

### 仓库证据

**Schema 验证**：[src/core/artifact-graph/schema.ts](src/core/artifact-graph/schema.ts)
```typescript
export function parseSchema(yamlContent: string): SchemaYaml {
  const parsed = parseYaml(yamlContent);
  const result = SchemaYamlSchema.safeParse(parsed);  // Zod 验证
  
  validateNoDuplicateIds(schema.artifacts);          // ID 唯一
  validateRequiresReferences(schema.artifacts);      // 引用有效
  validateNoCycles(schema.artifacts);                // 无循环
  
  return schema;
}
```

**Schema 应用**：[src/core/artifact-graph/graph.ts](src/core/artifact-graph/graph.ts)
```typescript
class ArtifactGraph {
  // Schema 定义了什么，Graph 就导出什么
  private artifacts: Map<string, Artifact> = 
    new Map(schema.artifacts.map(a => [a.id, a]));
  
  getNextArtifacts(completed): string[] {
    // 这个逻辑完全由 schema 中的 requires 决定
    // 改 schema，自动改行为
  }
}
```

**三层分辨率**：[src/core/artifact-graph/resolver.ts](src/core/artifact-graph/resolver.ts)
```typescript
export function getSchemaDir(name: string, projectRoot?: string): string | null {
  // 1. Project-local: openspec/schemas/<name>/
  // 2. User global: ~/.openspec/schemas/<name>/
  // 3. Package built-in: @openspec/schemas/<name>/
  
  // 用户可以覆盖任何 schema，甚至内置的
}
```

### 这个决策解决的问题

1. **工作流定制困难**：传统系统要改工作流必须改代码+编译+部署
2. **多工作流共存困难**：不同团队想要不同的工作流
3. **非技术人员无法调整**：工作流被锁在代码中

### 可能被放弃的替代方案

1. **工作流引擎（如 Workflow as Code）**
   - 优：功能强大，支持复杂逻辑
   - 弱：学习曲线陡，配置复杂

2. **命令行参数驱动**
   ```bash
   openspec --workflows proposal,specs,design,tasks
   ```
   - 优：简单
   - 弱：不能表达依赖关系

3. **硬编码多个预设**
   ```
   WORKFLOWS = {
     'spec-driven': [...],
     'rapid': [...],
   }
   ```
   - 优：简单
   - 弱：新工作流需要改代码

### 这个决策的优点

✅ **完全定制化**：用户可以创建 `openspec/schemas/my-workflow/schema.yaml`
✅ **现场调整**：改配置，立即生效（无需重启）
✅ **跨团队共享**：全局 schema 放在 `~/.openspec/schemas/`
✅ **清晰的 dependency model**：工作流变成可视化的 DAG
✅ **版本控制**：项目 schema 可以 git 管理

### 这个决策的成本 / 代价

❌ **配置复杂性**：用户需要学习 schema 结构
❌ **无法表达复杂逻辑**（如条件性步骤）
❌ **需要严格的验证**（循环依赖、缺失引用等）
❌ **Schema 版本管理**（不同项目可能用不兼容的 schema 版本）

### 什么场景适合借鉴

✅ **需要快速定制的系统**（不同客户不同流程）
✅ **多工作流共存**（platform 类产品）
✅ **非技术人员决策的领域**（工作流规则由 PM/BA 定义）

### 什么场景不该照搬

❌ **工作流本身很复杂**（很多条件判断、循环等）
❌ **工作流很少改变**（配置反而增加复杂性）
❌ **需要动态工作流**（根据运行时数据改流程）

---

## 决策 3：分离 Specs 与 Changes（命名空间隔离）

### 决策内容

**不在 main specs 中直接工作，而是在隔离的 changes/ 命名空间中工作，最后才合并。**

```
传统方式（直接修改 spec）：
  openspec/specs/
  ├─ auth.md    ← User A 正在编辑
  ├─ ui.md      ← User B 正在编辑
  └─ 编辑冲突！

OpenSpec 方式（隔离的 change 容器）：
  openspec/specs/           ← main（只有 archive 时改动）
  ├─ auth.md
  └─ ui.md
  
  openspec/changes/
  ├─ feature-A/specs/auth.md    ← User A 的改动（delta）
  ├─ feature-B/specs/ui.md      ← User B 的改动（delta）
  └─ 互不干扰！
```

### 仓库证据

**变更容器结构**：docs/concepts.md
```
两个分离的命名空间：
├─ specs/           [source of truth]
│  └─ domain/spec.md (完整的现有规格)
│
└─ changes/         [proposed modifications]
   └─ change-name/specs/domain/spec.md (只有变化部分)
```

**文件扫描时的处理**：[src/core/specs-apply.ts](src/core/specs-apply.ts)
```typescript
export async function findSpecUpdates(
  changeDir: string,
  mainSpecsDir: string
): Promise<SpecUpdate[]> {
  const updates: SpecUpdate[] = [];
  const changeSpecsDir = path.join(changeDir, 'specs');
  
  // 扫描 change/specs 中的文件
  const entries = await fs.readdir(changeSpecsDir);
  for (const entry of entries) {
    if (entry.isDirectory()) {
      const specFile = path.join(changeSpecsDir, entry.name, 'spec.md');
      const targetFile = path.join(mainSpecsDir, entry.name, 'spec.md');
      
      updates.push({
        source: specFile,       // 从 change 读取
        target: targetFile,     // 合并到 main
        exists: await checkExists(targetFile)
      });
    }
  }
  return updates;
}
```

**Archive 时的 3 层隔离**：[src/core/archive.ts](src/core/archive.ts)
```typescript
// 1. change 验证（不触碰 main）
// 2. delta 应用（生成新 main 内容但不写入）
// 3. 原子写入和移动
await moveDirectory(changeDir, archiveDir);  // 隔离 → 归档
```

### 这个决策解决的问题

1. **并发冲突**：多人同时修改会相互覆盖
2. **无法 review 变更**：用户无法在 merge 前看到人工审查
3. **无法回滚单个变更**：所有变更混在一起
4. **无法暂停/恢复工作**：一旦开始修改就无法中途切换

### 可能被放弃的替代方案

1. **分支模型（如 Git）**
   ```
   main branch (specs/)
   └─ feature branch (User A's spec changes)
   ```
   - 优：强大，支持 merge conflict 解决
   - 弱：对非技术用户复杂

2. **版本化 spec**
   ```
   spec-v1.md
   spec-v2.md (User A 的改动)
   spec-v3.md (User B 的改动)
   ```
   - 优：保留所有版本
   - 弱：无法跟踪变化来源于哪个逻辑事件

3. **中央锁定机制**
   ```
   User A: lock auth.md
   User B: 等待...
   User A: unlock auth.md
   ```
   - 优：简单（互斥）
   - 弱：低并发，用户体验差

### 这个决策的优点

✅ **完全的并行性**：无限数量的 change 可以同时存在
✅ **工作隔离**：一个 change 的问题不影响其他
✅ **易于 review**：每个 change 是独立单元
✅ **易于放弃**：删除整个 change 文件夹就回滚
✅ **时间旅行**：archive/ 保留变更历史

### 这个决策的成本 / 代价

❌ **复杂性**：用户需要理解 change 容器概念
❌ **合并冲突**：两个 change 修改同一 spec 需要冲突解决
❌ **元数据分散**：元数据在 change 和 main 中都有副本
❌ **回溯困难**：改变 main spec 后，旧 change 中的 delta 可能过时

### 什么场景适合借鉴

✅ **多人异步协作**（不同人不同时间工作）
✅ **需要频繁暂停/恢复**（工有可能中途打断切换）
✅ **需要变更可审计**（谁改了什么）

### 什么场景不该照搬

❌ **单人或同时很少人**（隔离的好处体现不出来）
❌ **频繁 merge 冲突**（对于复杂系统可能很常见）
❌ **需要实时同步**（change 模型是异步的）

---

## 决策 4：Delta Spec 格式（显式 ADDED/MODIFIED/REMOVED）

### 决策内容

**用 delta 格式描述变更而非完整规格。每个 change 的 spec 文件只包含增加、修改、删除的 requirement。**

```
完整 spec 方式：
  change-A/spec.md:
    # Auth Spec
    ## Requirements
    ### Requirement: User login
    [完整内容...]
    ### Requirement: User logout
    [完整内容...]
  
  合并时问题：怎么知道哪个是新增的？

Delta 方式（OpenSpec）：
  change-A/spec.md:
    ## ADDED Requirements
    ### Requirement: User logout
    [只有新增的内容]
    
    ## MODIFIED Requirements
    ### Requirement: User login
    [只有修改后的内容]
    
    (User authentication 没改，就不在 delta 中)
```

### 仓库证据

**Delta 格式定义**：schemas/spec-driven/templates/spec.md
```markdown
## ADDED Requirements
### Requirement: ...

## MODIFIED Requirements
### Requirement: ...

## REMOVED Requirements
### Requirement: ...

## RENAMED Requirements
Name 1 ──► New Name 1
```

**Delta 解析**：[src/core/parsers/requirement-blocks.ts](src/core/parsers/requirement-blocks.ts)
```typescript
export function parseDeltaSpec(content: string): DeltaPlan {
  // 按 ## ADDED / MODIFIED / REMOVED / RENAMED 分段
  // 每个 section 内解析 ### Requirement: 块
  
  return {
    added: [...],       // 新增的 requirement
    modified: [...],    // 修改的 requirement
    removed: [...],     // 删除的 requirement 名称
    renamed: [...]      // 改名的 requirement
  };
}
```

**应用 delta**：[src/core/specs-apply.ts](src/core/specs-apply.ts#L200-L250)
```typescript
async function buildUpdatedSpec(
  update: SpecUpdate,
  changeName: string
): Promise<{ rebuilt: string }> {
  const changeContent = await fs.readFile(update.source);
  const plan = parseDeltaSpec(changeContent);
  
  // 应用操作顺序：REMOVED → RENAMED → MODIFIED → ADDED
  // 1. 从 main 中删除 REMOVED requirements
  // 2. 改名 RENAMED requirements
  // 3. 替换 MODIFIED requirements
  // 4. 追加 ADDED requirements
  
  return { rebuilt: rebuiltSpecContent };
}
```

### 这个决策解决的问题

1. **明确的意图**：看到 ADDED/MODIFIED 就知道发生了什么
2. **合并冲突最小化**：多个 change 修改同一个 spec，可以分别处理 add/modify/remove
3. **变更审计**：能看到每个 change 改了什么（不是整个文件）
4. **提示词指引**：AI 知道"这个是修改现有的 requirement，请复制原文并更新"

### 可能被放弃的替代方案

1. **完整 spec（User 提供完整的新 spec 文件）**
   - 优：简单，AI 直观
   - 弱：无法区分"新增"vs"未改"，合并困难

2. **Patch 格式（unified diff）**
   ```
   --- openspec/specs/auth/spec.md
   +++ change/specs/auth/spec.md
   @@ ...
   ```
   - 优：标准格式（git diff）
   - 弱：对人阅读不友好，不适合 markdown

3. **YAML 格式**
   ```yaml
   operations:
     - type: add
       requirement: User logout
     - type: modify
       requirement: User authentication
       old_content: ...
       new_content: ...
   ```
   - 优：结构化
   - 弱：很难用 AI 生成准确的 YAML

### 这个决策的优点

✅ **清晰的语义**：标题就说明意图（ADDED vs MODIFIED）
✅ **易于解析**：规则简单，markdown 友好
✅ **易于人工编辑**：用户可以直接编辑 markdown
✅ **AI 友好**：提示词可以做针对性的指引
✅ **合并友好**：多个 delta 可以按顺序应用

### 这个决策的成本 / 代价

❌ **格式严格**：必须遵守 ADDED/MODIFIED/REMOVED/RENAMED 的头部
❌ **MODIFIED 冗长**：修改一个 requirement 需要复制整个原文
❌ **合并冲突**：两个 change 修改同一个 requirement 还是会冲突
❌ **验证复杂**：需要检查运算顺序、互斥性等

### 什么场景适合借鉴

✅ **需要澄清每个变更的意图**（不只是文件差异）
✅ **支持人工审阅**（markdown 格式易读）
✅ **长期存档和查询**（看历史能明白发生了什么）

### 什么场景不该照搬

❌ **代码变更**（code diff 已经很成熟）
❌ **复杂结构化数据**（YAML/JSON 更适合）
❌ **需要精确 3-way merge**（delta 格式不够）

---

## 决策 5：工件依赖的"启用器"模式（无硬性强制）

### 决策内容

**工件依赖关系是"启用器"而非"强制"。系统不强制执行工作流顺序，只指出什么是"可用"的。**

```
模式对比：

强制模式：
  if (!proposal_done) throw Error("Must do proposal first");
  // 系统不让用户跳过 proposal

启用器模式（OpenSpec）：
  if (!proposal_done) {
    // 不 throw，而是在 status 中标记 specs 为 "blocked"
    // 用户可以继续强行生成 specs，系统只是 warn
  }
```

### 仓库证据

**依赖检查是通知性的**：[src/core/artifact-graph/graph.ts](src/core/artifact-graph/graph.ts)
```typescript
getNextArtifacts(completed: CompletedSet): string[] {
  const ready: string[] = [];
  
  for (const artifact of this.artifacts.values()) {
    if (completed.has(artifact.id)) {
      continue;  // 已完成
    }
    
    // 关键：这里只是返回"可以做的"，不是"必须做的"
    const allDepsCompleted = artifact.requires.every(
      req => completed.has(req)
    );
    
    if (allDepsCompleted) {
      ready.push(artifact.id);  // 返回可用的
      // 没有 throw，没有阻止
    }
  }
  
  return ready;
}
```

**Blocked artifacts 作为信息，不作为阻塞**：[src/commands/workflow/status.ts](src/commands/workflow/status.ts)
```typescript
const blocked = context.graph.getBlocked(context.completed);

// 用于展示状态，不用于阻止操作
for (const artifact of context.artifacts) {
  if (blocked[artifact.id]) {
    console.log(`[-] ${artifact.id}`);  // 显示为 blocked
    console.log(`    Missing: ${blocked[artifact.id].join(', ')}`);
  }
}
```

### 这个决策解决的问题

1. **灵活工作流**：用户可能知道规格已经在脑子里，想先写 design
2. **多工作流支持**：某些项目可能跳过某些阶段
3. **AI 协作**：AI 可能能从上下文推断依赖（即使形式上依赖不满足）
4. **学习和探索**：新用户可以试验不同的工作流

### 可能被放弃的替代方案

1. **严格阶段锁定**
   ```
   Phase 1: Create proposal
   Phase 2: Create specs (locked until Phase 1 done)
   Phase 3: Create design (locked until Phase 2 done)
   ```
   - 优：强制约束，不容易"跳过"
   - 弱：没有灵活性，一刀切

2. **工件可选性标记**
   ```yaml
   artifacts:
     - id: proposal
       required: true
     - id: design
       required: false  ← 用户可以跳过
   ```
   - 优：显式
   - 弱：还是不如"启用器"模式灵活

### 这个决策的优点

✅ **最大灵活性**：用户完全控制顺序
✅ **平缘学习曲线**：新用户不被强制规则卡住
✅ **支持特殊工作流**：某些情况下可以创意地跳过某些工件
✅ **可视化帮助**：status 清晰地显示"下一步可以做什么"

### 这个决策的成本 / 代价

❌ **用户困惑**：不清楚为什么有些工件是灰色的
❌ **低质量输出**：用户跳过 proposal，后续工作可能无方向
❌ **追踪复杂**：很难推断"这个用户的工作流是什么"
❌ **缺乏约束**：没有"安全栏"防止明显的错误

### 什么场景适合借鉴

✅ **用户是专业人士**（知道自己在做什么）
✅ **多工作流共存**（不同人有不同流程）
✅ **我们信任用户的判断**

### 什么场景不该照搬

❌ **初学者系统**（需要强制引导）
❌ **合规性系统**（必须遵守流程）
❌ **用户可能完全迷茫**

---

## 决策 6：项目配置与全局配置的三层级联

### 决策内容

**配置分三层：项目本地 > 用户全局 > 包内置。后来者可以完全覆盖前者。**

```
优先级：
  1️⃣ openspec/schemas/<name>/          (项目本地 - 最高优先级)
  2️⃣ ~/.openspec/schemas/<name>/       (用户全局)
  3️⃣ @openspec/schemas/<name>/         (包内置 - 最低优先级)

同名文件时，优先级 1 的 schema 被使用。
```

### 仓库证据

**三层分辨率逻辑**：[src/core/artifact-graph/resolver.ts](src/core/artifact-graph/resolver.ts)
```typescript
export function getSchemaDir(
  name: string,
  projectRoot?: string
): string | null {
  // 1. Project-local (if provided)
  if (projectRoot) {
    const projectDir = path.join(getProjectSchemasDir(projectRoot), name);
    const projectSchemaPath = path.join(projectDir, 'schema.yaml');
    if (fs.existsSync(projectSchemaPath)) {
      return projectDir;  // ← 找到，直接返回
    }
  }
  
  // 2. User global
  const userDir = path.join(getUserSchemasDir(), name);
  const userSchemaPath = path.join(userDir, 'schema.yaml');
  if (fs.existsSync(userSchemaPath)) {
    return userDir;  // ← 找到，直接返回
  }
  
  // 3. Package built-in
  const packageDir = path.join(getPackageSchemasDir(), name);
  const packageSchemaPath = path.join(packageDir, 'schema.yaml');
  if (fs.existsSync(packageSchemaPath)) {
    return packageDir;
  }
  
  return null;  // 未找到
}
```

**项目 Config 读取**：[src/core/project-config.ts](src/core/project-config.ts)
```typescript
export function readProjectConfig(projectRoot: string): ProjectConfig | null {
  // 只在 projectRoot/openspec/config.yaml 中查找
  // 不查找全局或包级别的 config
  
  // 这意味着项目 config 不能被覆盖
  // 但 schema 可以被覆盖
}
```

### 这个决策解决的问题

1. **个人偏好**：用户有自己喜欢的 schema（放在 ~/.openspec/）
2. **团队标准**：团队有统一的工作流（放在项目 openspec/schemas/）
3. **开箱即用**：默认提供内置 schema，新项目无需配置就能用

### 可能被放弃的替代方案

1. **扁平设计（只有一层）**
   ```
   @openspec/schemas/spec-driven/
   ```
   - 优：简单
   - 弱：用户无法定制

2. **合并所有层**
   ```
   把三层的 schema 合并成一个（全局覆盖本地覆盖内置）
   ```
   - 优：有灵活性
   - 弱：复杂度高，容易混淆

### 这个决策的优点

✅ **多级别定制**：用户、团队、项目都能定制
✅ **向下兼容**：项目如果没有本地 schema，使用用户或内置的
✅ **清晰的优先级**：靠近 project 的优先级高
✅ **版本控制友好**：项目 schema 可以 git 管理

### 这个决策的成本 / 代价

❌ **路径复杂**：用户需要知道 ~/.openspec/schemas/ 在哪
❌ **版本冲突**：如果用户 schema vs 内置 schema 版本不同步会出问题
❌ **文档负担**：需要清楚解释优先级

### 什么场景适合借鉴

✅ **支持多层定制的系统**（CLI 工具、插件系统）
✅ **全球分布的用户**（不同地区、公司有不同规则）

---

## 决策 7：质量门禁的分布式设计（多处检查点）

### 决策内容

**不是单一的"发布前检查"，而是在系统的多个关键点分布式地进行检查。**

```
传统方式（单一门禁）：
  工作流 ──► 最后检查（发布前）
           ↓ 如果失败
           回滚整个工作
           
OpenSpec 方式（分布式门禁）：
  New      Proposal       delta      rebuild     move
   │          ↓           ↓           ↓          ↓
   ├─ 名称检查  │         │           │          │
         ├─ format validate
                         ├─ operation validate
                                    ├─ spec validate
                                              ├─ move verify
   
   每个阶段失败立即停止，不影响前面的工作。
```

### 仓库证据

**检查点分布**：[src/core/archive.ts](src/core/archive.ts)
```typescript
async execute(changeName, options) {
  // Gate 1: 工件完整性
  if (!proposal.md || !specs/ || !design.md || !tasks.md) {
    throw Error("Missing artifacts");
  }
  
  // Gate 2: 格式验证
  if (!options.noValidate) {
    const report = await validator.validateChange(changeFile);
    if (hasErrors) throw Error(...);
  }
  
  // Gate 3: Delta 格式验证
  const updates = await findSpecUpdates(changeDir, mainSpecsDir);
  for (const update of updates) {
    const {rebuilt} = await buildUpdatedSpec(update);  // ← 错误在这里被检测
  }
  
  // Gate 4: 最终 spec 验证
  for (const built of builtSpecs) {
    const report = await validator.validateSpecContent(...);
    if (!report.valid) throw Error(...);
  }
  
  // Gate 5: 文件系统操作
  await moveDirectory(changeDir, archiveDir);
}
```

### 这个决策解决的问题

1. **早期失败**：不要等到最后才发现问题
2. **清晰的错误**：每个门禁都有明确的错误信息
3. **防止部分失败**：如果第 2 个 gate 失败，第 3 个 gate 不会执行

### 可能被放弃的替代方案

1. **单一终极检查**
   ```
   finalValidate(everything)
     // 一次性检查所有
   ```
   - 优：代码简洁
   - 弱：难以定位问题

2. **宽松政策（几乎不检查）**
   - 优：快速
   - 弱：垃圾数据进系统

### 这个决策的优点

✅ **快速反馈**：立即知道什么错了
✅ **精确的错误信息**：每个 gate 的错误信息明确
✅ **可跳过的检查**：用户可以 --no-validate，但自己负责后果

### 这个决策的成本 / 代价

❌ **多层检查的冗余性**：某些检查可能被多个 gate 做
❌ **性能开销**：多次 I/O 和计算
❌ **复杂的代码流**：很多 if-throw

---

## 决策 8：显式机制优于魔法（Mechanism > Magic）

### 决策内容

**系统的行为应该是显式的、可预测的，而不是"魔法般"地工作。配置中明确列出规则，不要隐含。**

```
魔法方式：
  系统"智能地"检测项目使用什么工具（Python? Node? Ruby?）
  然后"自动"选择合适的工作流
  
显式方式（OpenSpec）：
  config.yaml 明确指定：
    schema: spec-driven
    rules: ...
  
  每个生成都要用到这个 config，显式可见。
```

### 仓库证据

**显式的规则**：openspec/config.yaml
```yaml
schema: spec-driven
context: |
  Tech stack: TypeScript, React, Node.js
  ...

rules:
  proposal:
    - Include rollback plan
  specs:
    - Use Given/When/Then format
  design:
    - Document trade-offs
```

**显式的工件追踪**：[src/core/archive.ts](src/core/archive.ts)
```typescript
// 对于"生成的工件"，系统需要知道它创建了什么
// 在 .metadata.yaml 中显式记录

// 不是：系统"神奇地"扫描并猜测哪些是生成的
// 而是：用户在 schema 中显式说 generates: "proposal.md"
```

### 这个决策解决的问题

1. **可预测性**：用户了解系统会做什么
2. **可审计性**：可以 review 配置理解系统行为
3. **可版本控制**：配置可以 git commit，记录历史变化

### 这个决策的优点

✅ **易于调试**：不清楚怎么了？查看配置就懂
✅ **易于文档化**：配置本身就是文档
✅ **易于自动化**：可以自动生成/修改配置

### 这个决策的成本 / 代价

❌ **更多配置**：新手需要填写更多字段
❌ **信息量大**：显式意味着更冗长
❌ **易出错**：需要正确填写配置

---

## 系统决策之间的内在联系

这 8 个决策形成了一个**相互支撑的系统**：

```
┌─ 决策 1: 文件系统即状态
│      ↓ 支撑
├─ 决策 3: Specs vs Changes 隔离
│      ↓ 需要
├─ 决策 4: Delta spec 格式
│      ↓ 依赖
├─ 决策 7: 分布式质量门禁
│      ↓ 由
├─ 决策 2: Schema 驱动
│      ↓ 配合
├─ 决策 6: 三层级联配置
│      ↓ 以及
├─ 决策 5: "启用器"模式
│      ↓ 都需要
└─ 决策 8: 显式机制
```

**移除任何一个决策，系统的优雅性都会大打折扣。**
