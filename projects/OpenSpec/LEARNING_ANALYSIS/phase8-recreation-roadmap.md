# Phase 8：微型重现路线图 - 从零到完整的 3 个阶段

## 目标

设计一个**学习路线**，通过从零开始逐步重现 OpenSpec 的核心功能，深化对架构的理解。

**关键约束**：
- 每个阶段都是一个**完整的、可用的系统**（不是玩具）
- 每个阶段教授**特定的架构原则**
- 代码量逐步增加，但始终保持清晰

---

## 总体设计：3 个阶段

```
阶段 v1.0（第 1 周）: 核心状态机
  ├─ 目标：理解"文件系统即状态"
  ├─ LOC：~800
  └─ 架构课程：State Machine, File System as State
  
阶段 v2.0（第 2-3 周）: 完整的 1 个工作流
  ├─ 目标：理解"Schema 驱动 + Instructions 生成"
  ├─ LOC：~3000
  └─ 架构课程：Schema-driven, Artifact Graph, DAG
  
阶段 v3.0（第 4-5 周）: 完整的多工作流 + Archive
  ├─ 目标：理解"Delta Specs + Merge + All-or-nothing"
  ├─ LOC：~7000
  └─ 架构课程：Branching Model, ACID, Distributed Validation
```

---

## 阶段 v1.0：核心状态机（第 1 周）

### 学习目标

- ✅ 理解"文件系统即状态"的威力
- ✅ 实现有限状态机（7 个状态）
- ✅ 理解"Status" 命令的核心逻辑

### 系统规格

**用户故事**：
```
作为开发者，我想：
1. 创建新的变更 (mkdir change/)
2. 查看当前状态 (openspec status)
3. 理解下一步是什么 (哪些工件已完成，哪些可以做)
```

**功能**：
- ✅ `openspec new-change <name>` - 创建 change 目录
- ✅ `openspec status [<change-name>]` - 显示状态
- ❌ 暂无指令生成
- ❌ 暂无 archive
- ❌ 暂无 delta specs

### 代码结构

```
v1.0/
├─ src/
│  ├─ index.ts                 # CLI 入口 (100 LOC)
│  ├─ core/
│  │  ├─ state-machine.ts      # FSM 定义 (150 LOC)
│  │  ├─ artifact-graph.ts     # 依赖追踪 (200 LOC)
│  │  └─ types.ts              # 类型定义 (100 LOC)
│  └─ commands/
│     ├─ new-change.ts         # new-change 命令 (100 LOC)
│     └─ status.ts             # status 命令 (150 LOC)
│
├─ test/
│  └─ state-machine.test.ts    # 状态机测试 (100 LOC)
│
├─ schema.yaml                 # 固定的 spec-driven schema
├─ templates/
│  └─ proposal.md              # proposal 模板
│
└─ README.md
```

### 代码示例

**state-machine.ts**：
```typescript
// 定义 7 个状态
type ChangeState = 
  | 'SCAFFOLDED'
  | 'PLANNING_IN_PROGRESS'
  | 'PLANNING_COMPLETE'
  | 'IMPLEMENTING'
  | 'IMPLEMENTATION_COMPLETE'
  | 'READY_FOR_MERGE'
  | 'ARCHIVED';

// 计算当前状态
function computeState(changeDir: string): ChangeState {
  // 检查文件系统
  if (!fs.existsSync(changeDir)) return 'SCAFFOLDED';
  if (fs.existsSync(`${changeDir}/proposal.md`)) {
    // 继续检查后续工件...
  }
  // ...
}
```

**artifact-graph.ts**：
```typescript
interface Artifact {
  id: string;
  generates: string;
  requires: string[];
}

const DEFAULT_SCHEMA_ARTIFACTS: Artifact[] = [
  { id: 'proposal', generates: 'proposal.md', requires: [] },
  { id: 'specs', generates: 'specs/**/*.md', requires: ['proposal'] },
  { id: 'design', generates: 'design.md', requires: ['specs'] },
  { id: 'tasks', generates: 'tasks.md', requires: ['design'] },
];

function getNextArtifacts(changeDir: string): string[] {
  const completed = detectCompleted(changeDir);
  const next: string[] = [];
  
  for (const artifact of DEFAULT_SCHEMA_ARTIFACTS) {
    if (!completed.has(artifact.id)) {
      // 检查所有依赖是否完成
      if (artifact.requires.every(req => completed.has(req))) {
        next.push(artifact.id);
      }
    }
  }
  
  return next;
}

function detectCompleted(changeDir: string): Set<string> {
  const completed = new Set<string>();
  
  if (fs.existsSync(`${changeDir}/proposal.md`)) {
    completed.add('proposal');
  }
  if (fs.globSync(`${changeDir}/specs/**/*.md`).length > 0) {
    completed.add('specs');
  }
  // ... etc
  
  return completed;
}
```

**commands/status.ts**：
```typescript
async function statusCommand(changeName: string) {
  const changeDir = `./openspec/changes/${changeName}`;
  
  if (!fs.existsSync(changeDir)) {
    console.error(`Change ${changeName} not found`);
    return;
  }
  
  const state = computeState(changeDir);
  const next = getNextArtifacts(changeDir);
  
  console.log(`📊 Change: ${changeName}`);
  console.log(`   State: ${state}`);
  console.log(`\n✅ Completed artifacts:`);
  // 显示已完成的工件
  
  console.log(`\n⏳ Next available:`);
  for (const artifact of next) {
    console.log(`   - ${artifact}`);
  }
}
```

**commands/new-change.ts**：
```typescript
async function newChangeCommand(changeName: string) {
  // Validate kebab-case
  if (!/^[a-z0-9]+-*[a-z0-9]+$/.test(changeName)) {
    throw Error(`Invalid name format. Use kebab-case.`);
  }
  
  const changeDir = `./openspec/changes/${changeName}`;
  
  if (fs.existsSync(changeDir)) {
    throw Error(`Change ${changeName} already exists`);
  }
  
  fs.mkdirSync(changeDir, { recursive: true });
  fs.mkdirSync(`${changeDir}/specs`, { recursive: true });
  
  console.log(`✅ Created change: ${changeName}`);
  console.log(`\nNext: openspec status ${changeName}`);
}
```

### 学习重点

**架构原则 1：文件系统即状态**
```
不是：const state = db.query('SELECT state ...')
而是：
  fs.existsSync('proposal.md') ? 'PLANNING_COMPLETE' : ...
```

**架构原则 2：有限状态机**
```
定义清晰的状态 + 显式的转移规则
无需复杂的状态机框架，简单的 if 就够了
```

**架构原则 3：依赖追踪 via DAG**
```
const next = [
  artifact 
  for artifact in schema.artifacts
  if artifact.requires.all(dep in completed)
]
```

### 测试和验证

```typescript
// test/state-machine.test.ts

describe('State Machine', () => {
  it('should start in SCAFFOLDED state', () => {
    const state = computeState('./non-existent');
    expect(state).toBe('SCAFFOLDED');
  });
  
  it('should transition to PLANNING_IN_PROGRESS after proposal', () => {
    createMockChange('test-change', ['proposal']);
    const state = computeState('./openspec/changes/test-change');
    expect(state).toBe('PLANNING_IN_PROGRESS');
  });
  
  it('should return next artifacts correctly', () => {
    createMockChange('test-change', ['proposal']);
    const next = getNextArtifacts('./openspec/changes/test-change');
    expect(next).toContain('specs');
    expect(next).not.toContain('proposal');
  });
});
```

### 第 1 周学到什么

✅ 文件系统作为状态存储很有效
✅ 简单的 if-then 足以实现复杂的状态转移
✅ DAG 依赖追踪可以用纯函数实现
✅ 无需数据库、ORM、复杂框架

---

## 阶段 v2.0：完整工作流 + 指令生成（第 2-3 周）

### 新增学习目标

- ✅ 理解"Schema 驱动配置"
- ✅ 实现"三层配置级联"
- ✅ 生成"丰富的 AI 指令"
- ✅ 实现"工件依赖的上下文传递"

### 新增功能

- ✅ 读取 openspec/config.yaml
- ✅ 读取 openspec/schemas/ 中的 schema
- ✅ `openspec instructions [<artifact>]` - 生成指令
- ✅ 返回 JSON 格式的指令（包含 background + dependency content + template）

### 代码增量

```
v2.0/
├─ src/
│  ├─ core/
│  │  ├─ state-machine.ts    (←从 v1.0)
│  │  ├─ artifact-graph.ts   (←从 v1.0，扩展支持 schema 加载)
│  │  ├─ schema-loader.ts    (新) 加载和验证 schema
│  │  ├─ config-loader.ts    (新) 读取 config.yaml
│  │  ├─ instruction-generator.ts (新) 生成指令
│  │  └─ types.ts            (←从 v1.0，添加新类型)
│  │
│  ├─ commands/
│  │  ├─ new-change.ts       (←从 v1.0)
│  │  ├─ status.ts           (←从 v1.0，集成 schema)
│  │  └─ instructions.ts     (新)
│  │
│  └─ utils/
│     ├─ yaml-parser.ts      (新)
│     └─ template-loader.ts  (新)
│
├─ openspec/
│  ├─ config.yaml
│  ├─ schemas/
│  │  └─ spec-driven/
│  │     ├─ schema.yaml
│  │     └─ templates/
│  │        ├─ proposal.md
│  │        ├─ specs.md
│  │        └─ ...
│  └─ changes/
│
└─ test/
   ├─ schema-loader.test.ts
   ├─ config-loader.test.ts
   └─ instruction-generator.test.ts

总 LOC：~3000
```

### 关键代码

**schema-loader.ts**：
```typescript
interface Artifact {
  id: string;
  generates: string;
  requires: string[];
  description?: string;
  template?: string;    // ← 指向模板文件
}

interface Schema {
  name: string;
  artifacts: Artifact[];
}

function loadSchema(name: string): Schema {
  // 三层分辨率：项目 > 用户全局 > 包内置
  
  // 1. Project-local
  let schemaPath = `./openspec/schemas/${name}/schema.yaml`;
  if (!fs.existsSync(schemaPath)) {
    // 2. User global
    schemaPath = `~/.openspec/schemas/${name}/schema.yaml`;
    if (!fs.existsSync(schemaPath)) {
      // 3. Package built-in (这里固定 spec-driven)
      schemaPath = `./node_modules/@openspec/schemas/${name}/schema.yaml`;
    }
  }
  
  // 加载 + 验证
  const content = fs.readFileSync(schemaPath, 'utf-8');
  const parsed = YAML.parse(content);
  
  // 验证无循环
  validateNoCycles(parsed.artifacts);
  
  return parsed;
}
```

**config-loader.ts**：
```typescript
interface ProjectConfig {
  schema: string;
  context?: string;        // ← 项目背景，会被注入到每个指令
  rules?: Record<string, string[]>;  // ← 工件特定的规则
}

function loadProjectConfig(projectRoot: string): ProjectConfig {
  const configPath = `${projectRoot}/openspec/config.yaml`;
  
  if (!fs.existsSync(configPath)) {
    return { schema: 'spec-driven' };  // 默认值
  }
  
  const content = fs.readFileSync(configPath, 'utf-8');
  const parsed = YAML.parse(content);
  
  // 验证 context 大小 < 50KB
  if (parsed.context && parsed.context.length > 50 * 1024) {
    console.warn(`context exceeds 50KB, will be truncated`);
    parsed.context = parsed.context.slice(0, 50 * 1024);
  }
  
  return parsed;
}
```

**instruction-generator.ts**：
```typescript
interface ArtifactInstructions {
  projectContext: string;          // 项目背景
  artifactDescription: string;     // 这个工件的说明
  artifactRules: string[];         // 这个工件的规则
  template: string;                // 模板内容
  dependencyContent: DependencyContent[];  // 依赖工件的内容
  nextArtifacts: string[];         // 完成后会解锁什么
}

async function generateInstructions(
  changePath: string,
  artifactId: string
): Promise<ArtifactInstructions> {
  const config = loadProjectConfig('.');
  const schema = loadSchema(config.schema);
  const artifact = schema.artifacts.find(a => a.id === artifactId);
  
  if (!artifact) {
    throw Error(`Artifact ${artifactId} not found in schema`);
  }
  
  // 1. 项目背景
  const projectContext = config.context || '';
  
  // 2. 工件描述
  const artifactDescription = artifact.description || '';
  
  // 3. 工件规则（从 config）
  const artifactRules = config.rules?.[artifactId] || [];
  
  // 4. 加载模板
  const templatePath = `./openspec/schemas/${config.schema}/templates/${artifact.template}`;
  const template = fs.readFileSync(templatePath, 'utf-8');
  
  // 5. 依赖工件内容（这里是 v2.0 的新特性）
  const dependencyContent: DependencyContent[] = [];
  for (const reqId of artifact.requires) {
    const depFilePath = `${changePath}/${reqId}.md`;  // 假设简化的命名
    if (fs.existsSync(depFilePath)) {
      dependencyContent.push({
        artifactId: reqId,
        content: fs.readFileSync(depFilePath, 'utf-8')
      });
    }
  }
  
  // 6. 计算下一步（会解锁什么）
  const completed = detectCompleted(changePath);
  completed.add(artifactId);  // 假设这个工件已完成
  const nextArtifacts = getNextArtifacts(
    changePath,
    schema,
    completed
  );
  
  return {
    projectContext,
    artifactDescription,
    artifactRules,
    template,
    dependencyContent,
    nextArtifacts
  };
}
```

**commands/instructions.ts**：
```typescript
async function instructionsCommand(options: {
  change: string;
  artifact?: string;
}) {
  const changePath = `./openspec/changes/${options.change}`;
  
  if (!fs.existsSync(changePath)) {
    throw Error(`Change not found: ${options.change}`);
  }
  
  // 如果没指定 artifact，使用第一个"下一步可以做的"
  let artifactId = options.artifact;
  if (!artifactId) {
    const next = getNextArtifacts(changePath);
    artifactId = next[0];
    if (!artifactId) {
      console.log('All artifacts completed!');
      return;
    }
  }
  
  const instructions = await generateInstructions(changePath, artifactId);
  
  // 输出为结构化格式（JSON 或 XML）
  console.log(JSON.stringify(instructions, null, 2));
}
```

### Schema 示例

**openspec/schemas/spec-driven/schema.yaml**：
```yaml
name: spec-driven
artifacts:
  - id: proposal
    generates: proposal.md
    requires: []
    description: |
      High-level overview of what this change proposes.
      Include: problem, solution, impact.
    template: proposal.md
    
  - id: specs
    generates: specs/**/*.md
    requires: [proposal]
    description: |
      Detailed specifications of the change.
      Should reference proposal.
    template: specs.md
    
  - id: design
    generates: design.md
    requires: [specs]
    description: |
      Architecture/design decisions.
      Should reference specs.
    template: design.md
    
  - id: tasks
    generates: tasks.md
    requires: [design]
    description: |
      Implementation tasks extracted from design.
    template: tasks.md
```

**openspec/config.yaml**：
```yaml
schema: spec-driven

context: |
  We are building an AI-driven workflow system.
  Tech stack: TypeScript, Node.js
  Key constraint: must work offline
  
rules:
  proposal:
    - Include rollback plan
    - Reference GitHub issue if available
  specs:
    - Use Given/When/Then scenario format
    - Each spec should reference a proposal requirement
  design:
    - Document trade-offs explicitly
    - Include diagram description
```

### 第 2-3 周学到什么

✅ Schema 驱动使工作流完全可定制
✅ 三层配置级联简洁而强大
✅ 上下文生成的"5 层堆栈"很有用（背景 + 规则 + 模板 + 依赖 + 下一步）
✅ 模板系统减少了"AI 提示词"的维护成本

---

## 阶段 v3.0：完整系统 + Archive + Delta Specs（第 4-5 周）

### 新增学习目标

- ✅ 理解"分支模型"（Specs vs Changes）
- ✅ 实现"Delta Specs 格式"
- ✅ 实现"Archive 命令"（验证→合并→提交）
- ✅ 理解"All-or-nothing 事务"

### 新增功能

- ✅ `openspec archive <change-name>` - 归档变更
- ✅ 支持 delta spec 格式（ADDED/MODIFIED/REMOVED/RENAMED）
- ✅ Merge main specs 和 delta specs
- ✅ 多层验证门禁
- ✅ 移动到 archive/

### 代码增量

```
v3.0/
├─ src/
│  ├─ core/
│  │  ├─ [v1-v2 的所有文件]
│  │  ├─ delta-spec-parser.ts  (新) 解析 delta 格式
│  │  ├─ spec-merger.ts         (新) 应用 delta → 新 spec
│  │  ├─ validator.ts           (新) 多层验证
│  │  └─ archiver.ts            (新) 7-step archive 流程
│  │
│  ├─ commands/
│  │  ├─ [v1-v2 的命令]
│  │  └─ archive.ts             (新)
│  │
│  └─ parsers/
│     └─ requirement-blocks.ts (新) 解析需求块
│
├─ openspec/
│  ├─ [v1-v2 的结构]
│  ├─ specs/                    # Main specs
│  │  └─ auth/
│  │     └─ spec.md
│  └─ changes/
│     └─ feature-A/
│        ├─ proposal.md
│        ├─ specs/
│        │  └─ auth/
│        │     └─ spec.md       # Delta spec
│        └─ design.md
│
├─ archive/                     # Archive 目录
│  └─ 2025-01-24-feature-A/
│     └─ [完成的 change 副本]
│
└─ test/
   ├─ delta-spec-parser.test.ts
   ├─ spec-merger.test.ts
   ├─ validator.test.ts
   └─ archiver.test.ts

总 LOC：~7000（v1.0: 800 + v2.0: 2200 + v3.0: 4000）
```

### 关键代码

**delta-spec-parser.ts**：
```typescript
interface DeltaPlan {
  added: RequirementBlock[];
  modified: RequirementBlock[];
  removed: string[];                    // ← 只需要名字
  renamed: { oldName: string; newName: string }[];
}

interface RequirementBlock {
  name: string;
  content: string;  // 完整的 markdown 格式
}

function parseDeltaSpec(content: string): DeltaPlan {
  // 按 ## ADDED / ## MODIFIED / ## REMOVED / ## RENAMED 分段
  
  const plan: DeltaPlan = {
    added: [],
    modified: [],
    removed: [],
    renamed: []
  };
  
  // 提取 ## ADDED Requirements 块
  const addedMatch = content.match(
    /^##\s+ADDED\s+Requirements\s*\n([\s\S]*?)(?=^##|\Z)/m
  );
  if (addedMatch) {
    plan.added = parseRequirementBlocks(addedMatch[1]);
  }
  
  // 提取 ## MODIFIED Requirements 块
  const modifiedMatch = content.match(
    /^##\s+MODIFIED\s+Requirements\s*\n([\s\S]*?)(?=^##|\Z)/m
  );
  if (modifiedMatch) {
    plan.modified = parseRequirementBlocks(modifiedMatch[1]);
  }
  
  // 提取 ## REMOVED Requirements 块
  const removedMatch = content.match(
    /^##\s+REMOVED\s+Requirements\s*\n([\s\S]*?)(?=^##|\Z)/m
  );
  if (removedMatch) {
    plan.removed = parseRequirementNames(removedMatch[1]);
  }
  
  // 提取 ## RENAMED Requirements 块
  const renamedMatch = content.match(
    /^##\s+RENAMED\s+Requirements\s*\n([\s\S]*?)(?=^##|\Z)/m
  );
  if (renamedMatch) {
    plan.renamed = parseRenamedRequirements(renamedMatch[1]);
  }
  
  return plan;
}

function parseRequirementBlocks(text: string): RequirementBlock[] {
  const blocks: RequirementBlock[] = [];
  
  // 按 ### Requirement: 分割
  const regex = /^###\s+Requirement:\s+(.+?)$/m;
  const matches = [...text.matchAll(regex)];
  
  for (let i = 0; i < matches.length; i++) {
    const match = matches[i];
    const name = match[1];
    const startPos = match.index! + match[0].length;
    const endPos = i < matches.length - 1 
      ? matches[i + 1].index! 
      : text.length;
    const content = text.slice(startPos, endPos).trim();
    
    blocks.push({ name, content });
  }
  
  return blocks;
}
```

**spec-merger.ts**：
```typescript
async function mergeSpecs(
  mainSpecPath: string,
  deltaSpecPath: string,
  changeName: string
): Promise<string> {
  // 读取 main spec 和 delta spec
  const mainContent = await fs.promises.readFile(mainSpecPath, 'utf-8');
  const deltaContent = await fs.promises.readFile(deltaSpecPath, 'utf-8');
  
  // 解析 main spec 到结构化形式
  const mainRequirements = parseRequirementsFromSpec(mainContent);
  
  // 解析 delta 到操作清单
  const plan = parseDeltaSpec(deltaContent);
  
  // 应用操作（顺序很关键）
  
  // 1. REMOVED 操作
  for (const name of plan.removed) {
    delete mainRequirements[name];
  }
  
  // 2. RENAMED 操作
  for (const { oldName, newName } of plan.renamed) {
    mainRequirements[newName] = mainRequirements[oldName];
    delete mainRequirements[oldName];
  }
  
  // 3. MODIFIED 操作
  for (const block of plan.modified) {
    // 验证原始需求存在
    if (!mainRequirements[block.name]) {
      throw Error(`Modified requirement not found: ${block.name}`);
    }
    mainRequirements[block.name] = block.content;
  }
  
  // 4. ADDED 操作
  for (const block of plan.added) {
    // 验证不存在冲突
    if (mainRequirements[block.name]) {
      throw Error(`Added requirement already exists: ${block.name}`);
    }
    mainRequirements[block.name] = block.content;
  }
  
  // 重建 markdown
  const rebuilt = rebuildSpecMarkdown(
    mainContent,
    mainRequirements,
    changeName
  );
  
  return rebuilt;
}
```

**validator.ts**：
```typescript
interface ValidationReport {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
}

interface ValidationError {
  gate: string;  // "artifact_completeness", "delta_format", etc.
  message: string;
}

async function validateArchive(
  changePath: string,
  mainSpecsPath: string
): Promise<ValidationReport> {
  const errors: ValidationError[] = [];
  
  // GATE 1: 工件完整性
  const required = ['proposal.md', 'design.md', 'specs/', 'tasks.md'];
  for (const file of required) {
    if (!fs.existsSync(`${changePath}/${file}`)) {
      errors.push({
        gate: 'artifact_completeness',
        message: `Missing required artifact: ${file}`
      });
    }
  }
  
  if (errors.length > 0) {
    return { valid: false, errors, warnings: [] };
  }
  
  // GATE 2: 格式验证（proposal 是有效的 markdown）
  try {
    const proposal = fs.readFileSync(`${changePath}/proposal.md`, 'utf-8');
    validateMarkdownStructure(proposal);
  } catch (e) {
    errors.push({
      gate: 'format_validation',
      message: `proposal.md failed validation: ${e}`
    });
  }
  
  if (errors.length > 0) {
    return { valid: false, errors, warnings: [] };
  }
  
  // GATE 3: Delta specs 格式
  const deltaSpecsDir = `${changePath}/specs`;
  for (const file of fs.readdirSync(deltaSpecsDir)) {
    if (file.endsWith('.md')) {
      try {
        const deltaContent = fs.readFileSync(`${deltaSpecsDir}/${file}`, 'utf-8');
        const plan = parseDeltaSpec(deltaContent);
        
        // 验证不存在操作冲突
        validateNoDuplicateOperations(plan);
        validateNoCrossConflicts(plan);
      } catch (e) {
        errors.push({
          gate: 'delta_format',
          message: `${file} failed delta validation: ${e}`
        });
      }
    }
  }
  
  if (errors.length > 0) {
    return { valid: false, errors, warnings: [] };
  }
  
  // GATE 4: 模拟 merge 看是否会失败
  for (const file of fs.readdirSync(deltaSpecsDir)) {
    try {
      const mainSpecPath = `${mainSpecsPath}/${file}`;
      const deltaSpecPath = `${deltaSpecsDir}/${file}`;
      
      // 试运行 merge（不写入）
      await mergeSpecs(mainSpecPath, deltaSpecPath, '[dry-run]');
    } catch (e) {
      errors.push({
        gate: 'merge_simulation',
        message: `${file} would fail during merge: ${e}`
      });
    }
  }
  
  return {
    valid: errors.length === 0,
    errors,
    warnings: []
  };
}
```

**archiver.ts**：
```typescript
async function archiveChange(changeName: string) {
  const changePath = `./openspec/changes/${changeName}`;
  const mainSpecsPath = `./openspec/specs`;
  const archivePath = `./archive`;
  
  console.log(`📦 Starting archive: ${changeName}`);
  
  // GATE 1-4: 验证（如上所述）
  console.log(`   [1/7] Validating...`);
  const report = await validateArchive(changePath, mainSpecsPath);
  if (!report.valid) {
    for (const error of report.errors) {
      console.error(`      ❌ ${error.gate}: ${error.message}`);
    }
    throw Error('Validation failed, archive aborted');
  }
  console.log(`   ✅ Validation passed`);
  
  // GATE 5: 应用 delta 到 main specs（但不写入）
  console.log(`   [2/7] Simulating merge...`);
  const merged: Record<string, string> = {};
  
  for (const file of fs.readdirSync(`${changePath}/specs`)) {
    if (file.endsWith('.md')) {
      const mainFile = `${mainSpecsPath}/${file}`;
      const deltaFile = `${changePath}/specs/${file}`;
      const newContent = await mergeSpecs(mainFile, deltaFile, changeName);
      merged[file] = newContent;
    }
  }
  console.log(`   ✅ Merge simulation succeeded`);
  
  // GATE 6: 现在开始真正写入（all-or-nothing）
  console.log(`   [3/7] Writing merged specs...`);
  try {
    for (const [file, content] of Object.entries(merged)) {
      const targetPath = `${mainSpecsPath}/${file}`;
      await fs.promises.writeFile(targetPath, content, 'utf-8');
    }
  } catch (e) {
    throw Error(`Failed to write specs: ${e}. Archive aborted.`);
  }
  console.log(`   ✅ Specs written`);
  
  // GATE 7: 移动 change 到 archive
  console.log(`   [4/7] Archiving change...`);
  const timestamp = new Date().toISOString().split('T')[0];
  const archiveDir = `${archivePath}/${timestamp}-${changeName}`;
  
  fs.mkdirSync(archivePath, { recursive: true });
  fs.renameSync(changePath, archiveDir);
  console.log(`   ✅ Change archived to: ${archiveDir}`);
  
  console.log(`\n✅ Archive complete!`);
  console.log(`   Main specs updated with ${Object.keys(merged).length} file(s)`);
}
```

**commands/archive.ts**：
```typescript
async function archiveCommand(options: { change: string }) {
  try {
    await archiveChange(options.change);
  } catch (e) {
    console.error(`\n❌ Archive failed: ${e.message}`);
    process.exit(1);
  }
}
```

### 第 4-5 周学到什么

✅ Delta specs 格式优雅且易于解析
✅ 所有验证在 merge 前完成，之后全部成功或全部失败
✅ Archive 流程的"验证→模拟→提交"三阶段模式很强大
✅ All-or-nothing 事务虽然用文件系统实现，但很可靠

---

## 学习路线总结

| 阶段 | 周 | LOC | 核心概念 | 难度 |
|------|----|----|---------|------|
| v1.0 | 1 | 800 | 文件系统状态，有限状态机 | ⭐ |
| v2.0 | 2-3 | 3000 | Schema 驱动，DAG 依赖 | ⭐⭐ |
| v3.0 | 4-5 | 7000 | Delta merge，All-or-nothing | ⭐⭐⭐ |

**总时间投入**：5 周（每周 15-20 小时）
**总代码量**：~7000 LOC（远小于 OpenSpec 的 15000+）
**学习密度**：每周学一个主要架构概念

---

## 为什么这样设计学习路线

### 原则 1：递进式复杂度

```
v1.0: 理解最简单的核心（状态 + DAG）
  ↓
v2.0: 添加配置和指令（Schema + Context）
  ↓
v3.0: 完整的工作流和合并（Delta + Archive）
```

每个阶段都是前一个的自然延伸，不会有"突然的复杂性跳跃"。

### 原则 2：每个阶段都是完整的、可用的系统

```
v1.0: 可以创建 change，查看状态（不能生成指令）
v2.0: 可以生成 AI 指令（不能 archive）
v3.0: 完整的工作流（可以生产使用）
```

这样你可以在每个阶段都看到价值，而不是等到最后才有完整系统。

### 原则 3：深化特定的架构原则

```
v1.0 深化："文件系统即状态"这一观念有多强大？
v2.0 深化："配置驱动"比代码更清晰吗？
v3.0 深化："Delta + All-or-nothing"真的无懈可击吗？
```

每个阶段通过构建来验证一个关键的架构假设。

### 原则 4：测试从第 1 周开始

```
v1.0: 测试状态机（容易）
v2.0: 测试配置加载（中等）
v3.0: 测试 merge 和 archive（复杂但值得）
```

通过测试来加深理解，而不是事后才补测试。

---

## 可选进阶路线

完成 v3.0 后，如果还想继续学习，可以：

1. **添加 Prompts 系统**（生成更丰富的指令）
2. **添加 Rules 引擎**（验证自定义规则）
3. **添加 Skills 插件**（扩展功能）
4. **实现并发锁定**（多人同时工作时的保护）
5. **Telemetry 和分析**（理解系统使用情况）

但这些都是可选的"第 6 周及以后"的东西，不是核心必须。

---

## 最终建议

**开始这个学习路线前，记住**：

✅ 这不是"照搬 OpenSpec"，而是"通过构建来理解架构"
✅ 每个阶段的代码应该尽可能简洁，逻辑清晰
✅ 不要试图一次性实现 v3.0，分阶段进行
✅ 通过测试来验证每一步
✅ 最后对比你的 v3.0 和真正的 OpenSpec，看看差异在哪里

**这样做的好处**：
- 理解比"阅读文档"更深
- 遇到设计选择时，你会理解"为什么这样"
- 可以应用到自己的项目中
