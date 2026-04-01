# Phase 2：关键路径与FSM - 工作流状态机详解

## 🎯 目标

45分钟内完全理解OpenSpec的工作流状态转移机制：
- 7个状态的完整定义
- 状态转移规则
- 5个质量门禁
- Archive 7步流程
- 状态转移异常处理

---

## 📊 7状态工作流FSM

### 完整状态图

```
START
  ↓
┌─────────────────────────────────────────────────────────────┐
│ State 1: SCAFFOLDED                                         │
│ ─────────────────────────                                   │
│ 定义: 变更容器已创建，但无任何工件                            │
│                                                               │
│ 进入条件：                                                    │
│   • 用户运行 openspec new-change                             │
│   • 系统创建 openspec/changes/[name]/                        │
│                                                               │
│ 检测方法：                                                    │
│   fs.existsSync('changes/[name]') && no artifacts           │
│                                                               │
│ 退出条件：                                                    │
│   • 用户创建 proposal.md（第一个工件）                        │
│                                                               │
│ 有效转移：→ PLANNING_IN_PROGRESS                             │
└─────────────────────────────────────────────────────────────┘
  ↓ [proposal.md 被创建]
  
┌─────────────────────────────────────────────────────────────┐
│ State 2: PLANNING_IN_PROGRESS                               │
│ ────────────────────────────────                             │
│ 定义: proposal 已完成，用户正在创建其他规划工件               │
│                                                               │
│ 进入条件：                                                    │
│   • fs.existsSync('proposal.md')                             │
│   • 但 specs, design, tasks 尚未全部完成                     │
│                                                               │
│ 子状态转移（在此状态内流动）：                                │
│   • 初期：只有 proposal                                      │
│   • 中期：proposal + 某些 specs                              │
│   • 末期：proposal + specs + design（但无 tasks）            │
│                                                               │
│ 退出条件：                                                    │
│   • proposal AND design 都完成（通常意味着规划完成）          │
│                                                               │
│ 有效转移：→ PLANNING_COMPLETE                                │
└─────────────────────────────────────────────────────────────┘
  ↓ [proposal + design 都完成]
  
┌─────────────────────────────────────────────────────────────┐
│ State 3: PLANNING_COMPLETE                                  │
│ ─────────────────────────                                   │
│ 定义: 规划阶段所有关键工件（proposal + design）已完成         │
│                                                               │
│ 进入条件：                                                    │
│   • fs.existsSync('proposal.md')                             │
│   • fs.existsSync('design.md')                               │
│   • 但 tasks 可能未完成（tasks 可跳过）                      │
│                                                               │
│ 特殊性：                                                      │
│   • 这个状态表示"可以开始实现"                                │
│   • tasks 不是硬性要求                                       │
│                                                               │
│ 有效转移：→ IMPLEMENTING                                     │
└─────────────────────────────────────────────────────────────┘
  ↓ [开始实现工作]
  
┌─────────────────────────────────────────────────────────────┐
│ State 4: IMPLEMENTING                                       │
│ ────────────────                                             │
│ 定义: 规划完成，正在进行实现工作                              │
│                                                               │
│ 进入条件：                                                    │
│   • proposal, design 已完成                                  │
│   • 开始生成或编辑 tasks                                     │
│                                                               │
│ 流动模式：                                                    │
│   • specs 从部分 → 完成 → 完整                               │
│   • tasks 从无 → 部分 → 完整                                 │
│   • 用户持续迭代这两个工件                                    │
│                                                               │
│ 有效转移：→ IMPLEMENTATION_COMPLETE                          │
└─────────────────────────────────────────────────────────────┘
  ↓ [所有 tasks 完成]
  
┌─────────────────────────────────────────────────────────────┐
│ State 5: IMPLEMENTATION_COMPLETE                            │
│ ────────────────────────────────                             │
│ 定义: 所有实现工件都完成（proposal, design, specs, tasks）   │
│                                                               │
│ 进入条件：                                                    │
│   • 所有必需工件都存在                                        │
│   • 系统验证通过 Gate 1-4                                    │
│                                                               │
│ 准备状态：                                                    │
│   • 可以进行最终检查                                          │
│   • 可以进行 archive 操作                                    │
│                                                               │
│ 有效转移：→ READY_FOR_MERGE                                  │
└─────────────────────────────────────────────────────────────┘
  ↓ [最终验证通过]
  
┌─────────────────────────────────────────────────────────────┐
│ State 6: READY_FOR_MERGE                                    │
│ ──────────────────────                                       │
│ 定义: 所有验证通过，可以合并到 main specs                     │
│                                                               │
│ 特征：                                                        │
│   • 这是 archive 前的最后一个状态                            │
│   • 用户执行 openspec archive 时进入此状态                   │
│   • 系统进行 7-step 验证和合并                               │
│                                                               │
│ 验证阶段：                                                    │
│   • Gate 5: 干跑 merge（不写入）                             │
│   • Gate 6: 应用到 main specs（原子写入）                    │
│   • Gate 7: 移动到 archive/（原子操作）                      │
│                                                               │
│ 有效转移：→ ARCHIVED（成功）或 IMPLEMENTATION_COMPLETE（失败） │
└─────────────────────────────────────────────────────────────┘
  ↓ [成功应用和移动] 或 [失败回滚]
  
┌─────────────────────────────────────────────────────────────┐
│ State 7: ARCHIVED                                           │
│ ──────────────                                               │
│ 定义: 变更已成功合并到 main specs 并归档                      │
│                                                               │
│ 操作完成：                                                    │
│   • Main specs 已更新（包含本次 delta）                      │
│   • Change 目录已移动到 archive/YYYY-MM-DD-[name]/           │
│   • 变更流程结束                                              │
│                                                               │
│ 终止状态：                                                    │
│   • 不能再转移到其他状态                                      │
│   • 旧的 change 可在 archive 中查询历史                       │
│                                                               │
│ 有效转移：无（终止）                                          │
└─────────────────────────────────────────────────────────────┘
  ↓
END
```

---

## 📋 状态转移规则表

| 当前状态 | 转移条件 | 下一状态 | 触发方式 |
|---------|--------|--------|---------|
| SCAFFOLDED | proposal.md 创建 | PLANNING_IN_PROGRESS | 用户创建文件 |
| PLANNING_IN_PROGRESS | proposal + design 都完成 | PLANNING_COMPLETE | 用户创建文件 |
| PLANNING_COMPLETE | design 完成 | IMPLEMENTING | 系统检测 |
| IMPLEMENTING | 所有必需工件完成 | IMPLEMENTATION_COMPLETE | 系统检测 |
| IMPLEMENTATION_COMPLETE | 验证通过 | READY_FOR_MERGE | openspec status 时 |
| READY_FOR_MERGE | archive 成功 | ARCHIVED | openspec archive |
| READY_FOR_MERGE | archive 失败 | IMPLEMENTATION_COMPLETE | Archive失败回滚 |
| ARCHIVED | 无 | 无 | 终止 |

---

## 🚪 5个质量门禁（Quality Gates）

### Gate 1：工件完整性检查

**检查内容**：确保所有必需的工件文件/目录存在

```
检查项目：
  ✓ proposal.md 存在 ？
  ✓ specs/ 目录存在 ？
  ✓ design.md 存在 ？
  ✓ tasks.md 存在 ？

失败行为：立即返回错误，不继续
错误信息：
  ❌ Missing required artifact: specs/
  
设计目的：
  快速发现不完整的工作
```

**代码模式**：
```typescript
for (const file of REQUIRED_ARTIFACTS) {
  if (!fs.existsSync(`${changeDir}/${file}`)) {
    throw Error(`Missing: ${file}`);
  }
}
```

---

### Gate 2：格式验证

**检查内容**：确保工件文件格式正确（特别是markdown结构）

```
检查项目：
  ✓ proposal.md 是有效的 markdown ？
  ✓ 有明确的标题和内容分节 ？
  ✓ design.md 是有效的 markdown ？
  ✓ tasks.md 有清晰的任务列表 ？

失败行为：列出所有格式问题
错误示例：
  ❌ proposal.md:42: Invalid markdown structure
  ❌ Missing H1 header
  
设计目的：
  在 merge 前发现格式问题
```

---

### Gate 3：Delta Spec 格式验证

**检查内容**：确保 specs/ 中的 delta 文件格式正确

```
检查项目：
  ✓ 每个 spec 文件是有效的 delta 格式 ？
  ✓ 包含 ## ADDED/MODIFIED/REMOVED/RENAMED 块 ？
  ✓ 每个需求有明确的格式 ？
  ✓ 没有操作冲突（同一需求多次操作）？

失败行为：报错并停止
错误示例：
  ❌ specs/auth/spec.md
      Requirement "Login" appears in both ADDED and MODIFIED

设计目的：
  确保 delta 格式正确，为 merge 做准备
```

---

### Gate 4：Spec 内容验证

**检查内容**：验证 spec 的语义一致性和冲突检测

```
检查项目：
  ✓ 所有被 MODIFIED 的需求在 main spec 中存在 ？
  ✓ 所有被 REMOVED 的需求在 main spec 中存在 ？
  ✓ 所有被 ADDED 的需求在 main spec 中不存在 ？
  ✓ RENAMED 的新名称不与其他需求冲突 ？

失败行为：列出具体的冲突
错误示例：
  ❌ Modified requirement not found: "OAuth Support"
  ❌ Renamed 'Auth' to 'Authentication' but 'Authentication' exists

设计目的：
  发现语义冲突，避免 merge 失败
```

---

### Gate 5：干跑 Merge 验证

**检查内容**：模拟 merge 过程，看是否会成功

```
流程：
  1. 按照 REMOVED → RENAMED → MODIFIED → ADDED 顺序应用
  2. 如果任何步骤失败，记录错误但不写入
  3. 返回"如果真的执行，会成功吗"

失败行为：报错，不进行真正的写入
示例成功场景：
  ✓ 删除 "Legacy Auth"
  ✓ 重命名 "Auth" → "Authentication"
  ✓ 修改 "JWT Support" 
  ✓ 添加 "OAuth2 Support"
  → 模拟成功，可以进行真正的 merge

设计目的：
  这是最后一个"safe check"，如果通过这个 gate，
  真正的 merge（写入）会 100% 成功
```

---

## 🔄 Archive 7步流程（All-or-Nothing）

### 完整的 Archive 执行流程

```
命令: openspec archive feature-login
  ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 1: 验证阶段（阶段1-4）                            │
│ ━━━━━━━━━━━━━━━━━━━━━                                  │
│                                                          │
│ Step 1: Gate 1-4 全部运行（完整性、格式、内容）          │
│   检查结果：✓ or ✗                                      │
│                                                          │
│ 如果任何 gate 失败：                                     │
│   → 立即停止，返回"验证失败"                             │
│   → 零操作，不写任何文件                                 │
│                                                          │
│ 结果：                                                   │
│   ✅ 所有 gate 通过 → 进入 Phase 2                       │
│   ❌ 任何 gate 失败 → 结束（失败）                       │
└─────────────────────────────────────────────────────────┘
  ↓ [所有验证通过]
  
┌─────────────────────────────────────────────────────────┐
│ Phase 2: 模拟阶段（Step 5）                             │
│ ━━━━━━━━━━━━━━━                                        │
│                                                          │
│ Step 5: 干跑 merge（Gate 5）                            │
│   对每个 delta spec：                                    │
│   1. 读取 main spec                                     │
│   2. 读取 delta spec                                    │
│   3. 模拟应用 delta                                     │
│   4. 如果失败，记录并停止                                │
│                                                          │
│ 输出：                                                   │
│   merged = {                                            │
│     "auth/spec.md": "[完整的新内容]",                    │
│     "payment/spec.md": "[完整的新内容]"                  │
│   }                                                     │
│                                                          │
│ 如果失败：                                               │
│   → 整个 archive 停止，修改零文件                        │
│   → 用户修复问题后重试                                   │
│                                                          │
│ 结果：                                                   │
│   ✅ 模拟成功 → 进入 Phase 3                             │
│   ❌ 模拟失败 → 结束（失败，零修改）                     │
└─────────────────────────────────────────────────────────┘
  ↓ [模拟成功]
  
┌─────────────────────────────────────────────────────────┐
│ Phase 3: 提交阶段（Steps 6-7）                          │
│ ━━━━━━━━━━━━━━━━━━━━━━                                 │
│                                                          │
│ **这里开始有副作用，必须 100% 成功**                     │
│                                                          │
│ Step 6: 写入更新的 specs                                │
│   for each (file, content) in merged:                   │
│     fs.writeFileSync(                                   │
│       'specs/' + file,                                  │
│       content                                           │
│     )                                                   │
│                                                          │
│ 失败处理：                                               │
│   如果写入失败：                                         │
│   → 理论上 rollback 要恢复（但很难）                     │
│   → 用户必须手工修复（风险！）                           │
│                                                          │
│ Step 7: 移动 change 到 archive                          │
│   timestamp = "2025-01-24"                              │
│   fs.renameSync(                                        │
│     'changes/feature-login',                            │
│     'archive/2025-01-24-feature-login'                  │
│   )                                                     │
│                                                          │
│ 结果：                                                   │
│   ✅ 两步都成功 → Archive 完成！                         │
│   ❌ 任何失败 → 系统处于不一致状态（风险）               │
└─────────────────────────────────────────────────────────┘
  ↓ [成功]
  
┌─────────────────────────────────────────────────────────┐
│ 最终状态                                                │
│ ━━━━━━━                                                 │
│                                                          │
│ ✅ Archive 完成                                          │
│   • main specs/ 已更新                                  │
│   • changes/feature-login/ 已移除                        │
│   • archive/2025-01-24-feature-login/ 已创建（备份）     │
│   • 状态 → ARCHIVED                                     │
│                                                          │
│ 对外影响：                                               │
│   • 其他 change 现在看到的是更新后的 main specs          │
│   • 历史保存在 archive 中                                │
│   • 可以继续创建新 change 基于新的 main specs            │
└─────────────────────────────────────────────────────────┘
```

---

## ⚠️ 4大失败模式

### 失败模式 1：工件不完整

```
症状：openspec archive 报错
  ❌ Missing required artifact: tasks/

原因：
  用户没有创建所有必需的工件

解决：
  1. openspec status 检查缺少什么
  2. openspec instructions 生成缺失工件
  3. 创建缺失文件
  4. 重试 archive
```

---

### 失败模式 2：Delta 格式错误

```
症状：openspec archive 报错
  ❌ specs/auth/spec.md:10
     Requirement "OAuth" in both ADDED and MODIFIED

原因：
  delta spec 格式错误（同一需求多个操作）

解决：
  1. 编辑 specs/auth/spec.md
  2. 确保每个需求只在一个操作块中
  3. 重试 archive
```

---

### 失败模式 3：Merge 冲突

```
症状：openspec archive 报错 (Gate 4 或 5)
  ❌ Modified requirement not found: "OAuth Support"

原因：
  • 想修改的需求在 main spec 中不存在
  • 或者被其他 change 先删除了

解决：
  1. 检查 openspec/specs/ 中实际存在的需求
  2. 修改 delta spec，使用正确的需求名
  3. 或者，改用 ADDED 而非 MODIFIED
  4. 重试 archive
```

---

### 失败模式 4：写入权限问题

```
症状：openspec archive 报错 (Phase 3)
  ❌ EACCES: permission denied, open 'specs/auth/spec.md'

原因：
  • 文件系统权限问题
  • 文件被其他进程锁定

解决：
  1. 检查文件权限（chmod）
  2. 确保没有其他进程在修改 specs/
  3. 重试 archive
  
注意：这是最危险的失败，可能导致系统不一致！
```

---

## 🎯 状态转移图（完整版）

```
                ┌──────────────────┐
                │  START / CREATE  │
                └────────┬─────────┘
                         │
                         ↓
        ┌────────────────────────────────┐
        │  SCAFFOLDED                    │ ← 初始状态
        │ (change 已创建，无工件)         │
        └────────────┬───────────────────┘
                     │ [proposal 创建]
                     ↓
        ┌────────────────────────────────┐
        │  PLANNING_IN_PROGRESS          │ ← 规划中
        │ (有 proposal，继续创建其他工件) │
        │                                │
        │ 可循环：添加更多工件             │
        └────────────┬───────────────────┘
                     │ [proposal + design 完成]
                     ↓
        ┌────────────────────────────────┐
        │  PLANNING_COMPLETE             │ ← 规划完成
        │ (proposal + design 都有)       │
        └────────────┬───────────────────┘
                     │ [开始实现]
                     ↓
        ┌────────────────────────────────┐
        │  IMPLEMENTING                  │ ← 实现中
        │ (规划完成，编辑 specs/tasks)   │
        │                                │
        │ 可循环：迭代工件内容             │
        └────────────┬───────────────────┘
                     │ [所有工件完成]
                     ↓
        ┌────────────────────────────────┐
        │  IMPLEMENTATION_COMPLETE       │ ← 实现完成
        │ (所有工件都有，验证通过)       │
        └────────────┬───────────────────┘
                     │ [通过所有验证]
                     ↓
        ┌────────────────────────────────┐
        │  READY_FOR_MERGE               │ ← 准备合并
        │ (所有检查通过，可以 archive)  │
        └──────┬───────────────────┬────┘
               │ [archive 成功]    │ [archive 失败]
               ↓                   ↓
        ┌────────────┐    [回滚到上一状态]
        │  ARCHIVED  │    (IMPLEMENTATION_COMPLETE)
        │ (完成!)    │
        └────────────┘
```

---

## 📊 状态迁移决策表

**系统如何决定当前状态？**

```typescript
function computeCurrentState(changeDir) {
  const completed = new Set();
  
  // 检测已完成的工件
  if (fs.existsSync(`${changeDir}/proposal.md`))
    completed.add('proposal');
  if (fs.globSync(`${changeDir}/specs/**/*.md`).length > 0)
    completed.add('specs');
  if (fs.existsSync(`${changeDir}/design.md`))
    completed.add('design');
  if (fs.existsSync(`${changeDir}/tasks.md`))
    completed.add('tasks');
    
  // 根据 completed set 判断状态
  if (completed.has('archived'))
    return 'ARCHIVED';
    
  if (completed.has('proposal') && completed.has('design') 
      && completed.has('specs') && completed.has('tasks'))
    return 'READY_FOR_MERGE';
    
  if (completed.has('proposal') && completed.has('design'))
    return 'IMPLEMENTING';
    
  if (completed.has('proposal'))
    return 'PLANNING_COMPLETE';
    
  if (completed.size > 0)
    return 'PLANNING_IN_PROGRESS';
    
  return 'SCAFFOLDED';
}
```

---

## 🎓 本Phase学完了什么

✅ 7个状态的完整定义  
✅ 状态转移规则  
✅ 5个质量门禁的详细检查  
✅ 7步 archive 流程（Phase 1/2/3）  
✅ 4大失败模式及解决方案  
✅ 状态转移决策的代码逻辑  

**下一步**：深入学习 Phase 3（核心模块详解）

