# Phase 3: 单模块精读 - Archive & Merge 引擎

## 模块：Archive & Specs Apply - 系统的关键门禁

### 职责定位

**核心职责**：
- 🔀 将 delta specs 安全合并回 main specs
- ✅ 执行最严格的质量检查
- 📦 整理和归档已完成的 change
- 🛡️ 防止并发冲突和数据损失

**不负责**：
- ❌ 生成 delta specs（那是 AI 的工作）
- ❌ 验证代码改动（那是 linter/tests 的工作）
- ❌ 执行具体的任务（那是 apply 的工作）

### 在系统中的位置

```
一个 change 的完整生命周期：

[PLANNING]          [EXECUTING]          [MERGING]
proposal.md  ───►   tasks.md apply  ───►  /opsx:archive
specs/            implemented                   │
design.md                                       ├─→ 验证工件完整性
                                                ├─→ 验证 delta specs 格式
                                                ├─→ 解析并应用 delta
                                                ├─→ 写入 main specs
                                                └─→ 移到 archive/

                    Archive & Merge 是最后的关卡，
                    决定 change 是否真正被接受。
```

### 上游 / 下游

**上游**：
- CLI: 用户运行 `/opsx:archive`
- validation/: 检查工件格式是否有效
- task-progress: 查询 task 完成状态

**下游**：
- 文件系统: 读取 change/ 中的文件，写入 specs/ 和 archive/
- parsers/requirement-blocks.ts: 解析 delta spec 格式
- validation/validator.ts: 验证最终的 spec 合并结果

### 输入 / 输出

#### 输入

```typescript
ArchiveCommand.execute(
  changeName: string,          // "add-logout-button"
  options: {
    yes?: boolean;             // 跳过交互确认
    skipSpecs?: boolean;       // 不合并 specs
    noValidate?: boolean;      // 跳过验证
    validate?: boolean;        // 强制验证
  }
)
```

#### 输出

**成功情况**：
```
✅ Archived add-logout-button
   ├─ Merged specs: auth (+1 requirement), ui (+2 requirements)
   ├─ Moved to: openspec/changes/archive/2025-01-24-add-logout-button/
   └─ Ready for next change
```

**失败情况**：
```
❌ Archive failed: Validation errors
   spec/auth/spec.md: duplicate requirement "User login"
   Please fix the errors before archiving.
```

### 核心数据流

#### 数据流 1: Delta Specs 的解析和应用

```
Change 中的 delta spec:
  /openspec/changes/add-logout/specs/auth/spec.md
  
  ## ADDED Requirements
  ### Requirement: User logout
  - WHEN user clicks logout button
  - THEN session is cleared
  
  ## MODIFIED Requirements
  ### Requirement: User authentication
  [修改后的完整 requirement 内容]
  
  ## REMOVED Requirements
  ### Requirement: Legacy cookie-based auth
  
  ## RENAMED Requirements
  Old Name ──► New Name
  
                       ↓ [parseDeltaSpec()]
                       
  DeltaPlan {
    added: [RequirementBlock { name: "User logout", raw: "..." }],
    modified: [RequirementBlock { name: "User authentication", raw: "..." }],
    removed: ["Legacy cookie-based auth"],
    renamed: [{from: "Old Name", to: "New Name"}]
  }
  
                       ↓ [buildUpdatedSpec()]
                       ↓ [applyDeltaOperations()]
                       
  Main spec 更新为：
  /openspec/specs/auth/spec.md
  
  # Auth Specification
  [保留原来的其他 requirement]
  
  ### Requirement: User authentication    ← MODIFIED (更新)
  [新的内容]
  
  ### Requirement: User logout           ← ADDED (新增)
  [新增的内容]
  
  [Legacy cookie-based auth 被删除]      ← REMOVED
  
  [Old Name 被改名为 New Name]            ← RENAMED
```

### 核心算法

#### 算法 1: 7 步 Archive 流程

```
步骤 1: 基础检查
├─ change 目录存在?
└─ 提示选择（如果未指定 changeName）

步骤 2: 工件完整性检查
├─ proposal.md 存在?
├─ specs/ 存在?
├─ design.md 存在?
└─ tasks.md 存在?

步骤 3: Proposal 验证（可选，非阻塞）
├─ 读取 proposal.md
├─ 验证格式
└─ 警告（但不阻止）

步骤 4: Delta specs 验证（如果有）
├─ 读取 specs/*/spec.md
├─ 检查是否 delta 格式 (有 ## ADDED/MODIFIED/...)
├─ 解析格式
├─ 检查重复、循环、缺失等
└─ 如果有错误，中止

步骤 5: 任务完成检查
├─ 读取 tasks.md
├─ 统计 [x] vs [ ]
├─ 如果不全完成，警告但不阻塞

步骤 6: 应用 Delta Specs
├─ 对每个 spec update:
│   ├─ 读取 change/specs/*/
│   ├─ 读取 main/specs/*/
│   ├─ 应用 ADDED/MODIFIED/REMOVED/RENAMED
│   ├─ 生成新的 spec 内容
│   ├─ 验证新 spec 的格式
│   └─ 写入文件
└─ 如果任何 spec 写入失败，全部回滚

步骤 7: 清理和归档
├─ 移动 change 目录到 archive/YYYY-MM-DD-name/
├─ 记录 archived_at 时间戳
└─ 更新元数据
```

**时间复杂度**：O(n × m)，其中 n = spec 文件数，m = requirement 平均数

#### 算法 2: Delta 应用算法

```typescript
function applyDeltaOperations(
  mainSpec: RequirementsSectionParts,
  deltaPlan: DeltaPlan
): string {
  // 1️⃣ 准备工作：验证操作有效性
  validateNoDuplicates(deltaPlan);
  validateNoConflicts(deltaPlan);
  
  // 2️⃣ 建立 index：main spec 中的所有 requirement by name
  const mainIndex = new Map<string, RequirementBlock>();
  for (const req of mainSpec.bodyBlocks) {
    mainIndex.set(normalizeRequirementName(req.name), req);
  }
  
  // 3️⃣ 执行 REMOVED - 从 main 中删除
  const toRemove = new Set(deltaPlan.removed.map(normalizeRequirementName));
  const afterRemoval = mainSpec.bodyBlocks.filter(
    req => !toRemove.has(normalizeRequirementName(req.name))
  );
  
  // 4️⃣ 执行 RENAMED - 改名
  for (const { from, to } of deltaPlan.renamed) {
    const normalized = normalizeRequirementName(from);
    const block = afterRemoval.find(
      b => normalizeRequirementName(b.name) === normalized
    );
    if (block) {
      block.name = to;
      block.headerLine = `### Requirement: ${to}`;
    }
  }
  
  // 5️⃣ 执行 MODIFIED - 替换内容
  for (const modReq of deltaPlan.modified) {
    const normalized = normalizeRequirementName(modReq.name);
    const idx = afterRemoval.findIndex(
      b => normalizeRequirementName(b.name) === normalized
    );
    if (idx >= 0) {
      afterRemoval[idx] = modReq;  // 完全替换
    }
  }
  
  // 6️⃣ 执行 ADDED - 追加到末尾
  for (const addReq of deltaPlan.added) {
    afterRemoval.push(addReq);
  }
  
  // 7️⃣ 重建 main spec 文本
  return rebuildSpecContent(mainSpec, afterRemoval);
}
```

**关键设计**：
- 每个操作都有明确的顺序（REMOVED → RENAMED → MODIFIED → ADDED）
- 操作基于 requirement 名称（规范化后的），不是位置
- 操作是互斥的（一个 requirement 不能同时 REMOVED 和 MODIFIED）

### 边界定义

**Archive 负责**：
- ✅ 验证工件存在且有效
- ✅ 解析 delta spec 格式
- ✅ 按规则应用 delta 操作
- ✅ 验证最终的 spec 结果
- ✅ 原子性地写入和移动文件

**Archive 不负责**：
- ❌ 生成或编辑 delta spec 内容
- ❌ 验证实现（code review）
- ❌ 执行测试
- ❌ 部署或发布

### 约束与设计规则

#### 约束 #1: Requirement 的唯一性

```yamL
main spec auth/spec.md:
  ## Requirements
  ### Requirement: User login      ← 已存在
  ### Requirement: User logout

change delta auth/spec.md:
  ## ADDED Requirements
  ### Requirement: User login      ← ❌ 冲突! 已在 main!
```

**防护**：
```typescript
validateRequirementNotInMain(deltaPlan.added, mainSpec);
// 如果 ADDED 中的 requirement 已在 main，throw error
```

#### 约束 #2: Delta 操作的互斥性

```yaml
# ❌ 不允许
## ADDED Requirements
### Requirement: User login

## MODIFIED Requirements
### Requirement: User login       ← 同一个不能既 ADDED 又 MODIFIED!

## REMOVED Requirements
### Requirement: User login       ← 也不能既 ADDED 又 REMOVED!
```

**防护**：
```typescript
function validateNoConflicts(plan) {
  for (const added of plan.added) {
    const name = normalizeRequirementName(added.name);
    if (plan.modified.some(m => normalizeRequirementName(m.name) === name)) {
      throw new Error(`Requirement in both ADDED and MODIFIED`);
    }
    if (plan.removed.some(r => normalizeRequirementName(r) === name)) {
      throw new Error(`Requirement in both ADDED and REMOVED`);
    }
  }
  // ... 类似地检查其他组合
}
```

#### 约束 #3: RENAMED 后的名字不能与其他操作冲突

```yaml
# ❌ 不允许
## RENAMED Requirements
Old Name ──► User login

## ADDED Requirements
### Requirement: User login       ← 新增的 name 与 RENAMED TO 冲突!
```

**防护**：
```typescript
const renamedToNames = new Set(plan.renamed.map(r => normalizeRequirementName(r.to)));
for (const added of plan.added) {
  if (renamedToNames.has(normalizeRequirementName(added.name))) {
    throw new Error(`RENAMED TO name collides with ADDED`);
  }
}
```

#### 约束 #4: Requirement 名称规范化

```typescript
function normalizeRequirementName(name: string): string {
  return name.trim();
}

// "User login" == "User login"       ✅
// " User login" == "User login"      ✅
// "User login " == "User login"      ✅
// "USER LOGIN" != "User login"       ❌ 区分大小写
```

**设计意图**：
- 防止因空格导致的冲突
- 保留大小写区分（User login ≠ user login）

### 失败模式与防护

#### 失败 #1: Delta spec 格式不正确

```
## Added Requirements        ← ❌ 应该是 "## ADDED Requirements"
### Requirement: ...
```

**防护**：
```typescript
const plan = parseDeltaSpec(content);
// 大小写敏感，必须是精确的 ## ADDED / MODIFIED / REMOVED / RENAMED
```

#### 失败 #2: Requirement 名称在 MODIFIED 中不存在于 main

```
main specs/auth/spec.md:
  ### Requirement: User authentication

delta specs/auth/spec.md:
  ## MODIFIED Requirements
  ### Requirement: User authorisation   ← ❌ 拼写错误，main 中不存在!
```

**防护**：
```typescript
function validateModifiedRequirementsExistInMain(deltaPlan, mainSpec) {
  for (const mod of deltaPlan.modified) {
    const name = normalizeRequirementName(mod.name);
    const exists = mainSpec.bodyBlocks.some(
      b => normalizeRequirementName(b.name) === name
    );
    if (!exists) {
      throw new Error(
        `MODIFIED requirement "${mod.name}" not found in main spec`
      );
    }
  }
}
```

#### 失败 #3: 并发修改同一个 spec

```
User A: /opsx:archive change-A   (更新 auth/spec.md)
User B: /opsx:archive change-B   (也更新 auth/spec.md)
                    ↓ 竞争条件 (Race condition)
```

**防护机制（当前）**：
- 没有显式的锁
- 依赖操作系统的文件系统 atomicity
- Bulk archive 有 heuristic 检测（检查代码是否都实现了）

**改进建议**：
```typescript
// 可以加：
const lockFile = path.join(mainSpecsDir, '.archive.lock');
try {
  const fd = fs.openSync(lockFile, 'wx');  // 独占创建
  // 执行 archive
  fs.closeSync(fd);
  fs.unlinkSync(lockFile);
} catch (e) {
  if (e.code === 'EEXIST') {
    throw new Error(`Another archive operation in progress`);
  }
}
```

#### 失败 #4: Spec merge 后内容无效

```
delta: 删除了 requirement"User login"
result: "## Requirements" section 现在是空的   ← ❌ 规格无效!
```

**防护**：
```typescript
// archive.ts 中的步骤 6
const report = await validator.validateSpecContent(
  specName,
  rebuiltContent   // ← 验证最终结果，不就是 delta
);
if (!report.valid) {
  throw new Error(`Rebuilt spec is invalid`);
}
```

### 可迁移做法

#### 做法 #1: 分段操作的原子性模式

```javascript
// 不要这样（容易失败中途）：
for (const file in files) {
  writeFile(file);    // ← 如果这一步失败，前面的已写入
  applyDelta(file);   // ← 状态不一致
  cleanup(file);
}

// 应该这样（验证-全部写入-清理）：
// 验证阶段
for (const file in files) {
  validateDataWillNotBeCorrupted(file);
}

// 写入阶段（成功或全部失败）
for (const file in files) {
  writeFile(file);
}

// 清理阶段
for (const file in files) {
  cleanup(file);
}
```

**OpenSpec 的实现**：
```typescript
// archive.ts 中
// Phase 1: 准备阶段（验证，不写入）
const prepared = [];
for (const update of specUpdates) {
  const built = await buildUpdatedSpec(update);
  prepared.push(built);  // 只收集，不写入
}

// Phase 2: 写入阶段
for (const p of prepared) {
  await writeUpdatedSpec(p.update.target, p.rebuilt);
}

// Phase 3: 清理阶段
await moveDirectory(changeDir, archiveDir);
```

**可迁移地方**：
- Git commit（stage → write → finalize）
- 数据库事务（验证 → 写入 → 提交）
- 文件批量操作（检查 → 修改 → 确认）

#### 做法 #2: Requirement 块的结构化解析

```
问题：直接用字符串处理 markdown 很脆弱

OpenSpec 的做法：
RequirementBlock {
  headerLine: string;   // "### Requirement: User Login"
  name: string;         // "User Login"
  raw: string;          // 包含所有 scenario 的原始文本
}

DeltaPlan {
  added: RequirementBlock[];
  modified: RequirementBlock[];
  removed: string[];    // ← 只需要名称
  renamed: [{from, to}];
}
```

**优势**：
- 有类型安全
- 操作基于结构而非字符串搜索
- 重建时保留原有的格式和空白

#### 做法 #3: 三维验证（对最终结果，不是过程）

```
不验证每一步（Step A done? Step B done? ...）
而是验证最终结果：

最终 spec 有效吗？
  ├─ 格式正确？
  ├─ 所有 requirement 有 scenario？
  ├─ 没有重复？
  └─ 语义一致？

如果最终结果有效，流程就有效。
如果最终结果无效，整个流程失败并回滚。
```

这个模式特别适合有多个变换步骤的系统。

---

## 这个模块教会我们什么

### 教学 #1: "All-or-Nothing" 的重要性

```
弱设计：
  写入 spec A ✅
  写入 spec B ✅
  移到 archive → ❌ 失败
  结果：spec 已改，change 还在 changes/ 中。状态不一致。

强设计（OpenSpec）：
  验证所有文件（不写入）
  如果全部通过：
    写入所有文件  ┐
    移到 archive  ├ 一起成功
                  ┘
  如果任何验证失败：
    不写入任何东西
    结果：要么全部成功，要么回到最初状态
```

### 教学 #2: 名称规范化的微妙之处

```
问题：Requirement 名称可能在多个地方出现
  - Delta spec 中的 MODIFIED 名称
  - Main spec 中的现有名称
  - 用户输入中的名称

解决：定义规范化规则
  normalizeRequirementName(name) = name.trim()
  
这样即使有空格差异也不会产生问题。
```

### 教学 #3: 验证应该发生在最终

不是：
- 检查 proposal 有效 ✅
- 检查 specs 有效 ✅
- 检查 design 有效 ✅
- 检查 tasks 有效 ✅
- → 核实通过，执行 archive ✅

而是：
- 所有工件都存在 ✅
- Delta spec 格式有效 ✅
- 应用 delta 后的 spec 有效 ✅
- → 核实通过，执行 archive ✅

第一种验证工件本身。
第二种验证"应用 delta 后的结果"。

OpenSpec 会先生成、再验证、再合并，因为最关键的是最终的 spec 有效。
