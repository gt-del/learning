# Phase 0：快速侦察 - 30分钟理解仓库本质

## 🎯 目标

在30分钟内抓住OpenSpec仓库的本质，回答这些关键问题：
1. 这是什么类型的系统？（code-first vs workflow-first）
2. 解决什么核心问题？
3. 5大关键模块是什么？
4. 隐含的主要工程问题是什么？

---

## 📋 快速扫描结果

### 系统分类：**Workflow-First（工作流优先）**

**证据**：
- 没有核心的"业务逻辑库"
- 所有代码围绕"工作流管理和协调"
- 配置文件（YAML）定义系统行为
- CLI是唯一的用户接口（没有API库）
- 主工作流：创建变更 → 生成工件 → 合并 → 归档

**不是 Code-First** 的证据：
- 没有"解析代码、分析代码"的模块
- 没有编程语言特定的依赖
- 没有"项目类型检测"

---

## 🎯 核心问题域

### OpenSpec 解决什么？

**问题**：在AI时代，如何管理多人异步的工程变更？
```
传统方式（Git）：
  ✓ 代码级别支持很好
  ✗ "需求级别"的并发编辑不支持

OpenSpec 方式：
  ✓ Requirement/Spec 级别支持
  ✓ 多人隔离工作（无冲突）
  ✓ AI友好（结构化输入输出）
```

### 主控制平面（2层）

```
业务层：CLI 命令与用户工作流
  ├─ new-change（创建新工作）
  ├─ status（查看进度）
  ├─ instructions（获取下一步指令）
  ├─ archive（合并和归档）
  └─ show（查看内容）
       ↓
技术层：核心架构与数据处理
  ├─ Artifact Graph（依赖追踪）
  ├─ Schema System（工作流定义）
  ├─ Archive/Merge Engine（变更应用）
  ├─ Validator（多层验证）
  └─ Telemetry（事件记录）
```

---

## 🧩 5大核心模块抽样

### 模块 1: Artifact Graph（核心）
**文件**：src/core/artifact-graph/  
**职责**：依赖追踪，工件可用性检测  
**关键函数**：
- `getNextArtifacts()` → 返回"现在能做什么"
- `detectCompleted()` → 通过文件存在性检测完成状态
- `generateInstructions()` → 为工件生成AI指令

**设计精妙之处**：文件存在 = 工件完成 ✅

### 模块 2: Schema System
**文件**：src/core/schemas/  
**职责**：加载和验证工作流定义  
**关键概念**：
- 位置1：项目本地（project/openspec/schemas/）
- 位置2：用户全局（~/.openspec/schemas/）
- 位置3：包内置（node_modules/@openspec/schemas/）

**设计精妙之处**：三层级联，灵活性很强 ✅

### 模块 3: Archive & Merge
**文件**：src/core/archive.ts  
**职责**：应用delta spec，验证，归档  
**流程**：验证 → 模拟 → 写入 → 移动  

**关键特性**：All-or-nothing（全成功或全失败）✅

### 模块 4: Validator
**文件**：src/core/validation/  
**职责**：多层验证  
**验证层**：
1. Schema 验证（无循环）
2. 工件完整性
3. Delta 格式
4. Spec 内容

**设计精妙之处**：验证点分布，快速反馈 ✅

### 模块 5: CLI & Commands
**文件**：src/cli/ 和 src/commands/  
**职责**：命令注册和生命周期管理  
**拓展点**：
- 新命令可以通过 Commander.js 添加
- 工作流命令在 src/commands/workflow/
- Spec 操作在 src/commands/spec.ts

**设计精妙之处**：清晰的命令结构，易于扩展 ✅

---

## 🏗️ 主工作流（Implicit FSM）

```
用户故事流程：

1. openspec new-change feature-login
   → 创建 openspec/changes/feature-login/
   → 初始化子目录（specs/, 等）
   
2. openspec status feature-login
   → 检测文件存在性
   → 计算当前状态（SCAFFOLDED, PLANNING_IN_PROGRESS, ...）
   → 显示"下一步可以做什么"
   
3. openspec instructions feature-login
   → 读取 config.yaml（项目背景）
   → 读取 schema.yaml（工件定义）
   → 读取已完成的工件内容（作为依赖上下文）
   → 生成结构化的 AI 指令（JSON）
   
4. [用户创建/编辑工件文件]
   
5. openspec status feature-login
   → 重新检测（现在 proposal.md 存在了）
   → 状态变为 PLANNING_IN_PROGRESS
   → 下一步可以做 specs
   
6. openspec archive feature-login
   → 验证所有工件存在
   → 验证 delta spec 格式正确
   → 模拟 merge 看是否成功
   → 写入更新到 openspec/specs/
   → 移动 change 目录到 archive/
```

---

## 📊 隐含的关键工程问题

### 问题 1：工件状态如何表达？
**答案**：文件系统 ✓
- proposal.md 存在 = proposal 完成
- specs/ 非空 = specs 完成
- 无需数据库，无需API

### 问题 2：工作流如何定制？
**答案**：Schema YAML ✓
- 定义 artifacts 数组（id, requires, generates）
- 定义 rules（每个工件的规则）
- 定义 templates（模板文件）

### 问题 3：多人如何隔离工作？
**答案**：分支模型 ✓
- specs/（主干）
- changes/feature-A/（分支A）
- changes/feature-B/（分支B）
- Archive 时合并 Δ（delta）到 main

### 问题 4：变更如何应用无冲突？
**答案**：Delta Spec 格式 ✓
```markdown
## ADDED Requirements
### Requirement: New Auth
  [内容]

## MODIFIED Requirements  
### Requirement: Old Requirement
  [修改后的内容]
```

### 问题 5：验证如何分布？
**答案**：多层 Gates ✓
- Gate 1: 工件完整性
- Gate 2: 格式验证
- Gate 3: Delta 格式
- Gate 4: Spec 内容
- Gate 5: 干跑merge

---

## 🎯 系统的"高明之处"排序

| 排名 | 设计 | 理由 |
|-----|-----|------|
| 🥇 | 文件系统即状态 | 无需DB，版本控制友好 |
| 🥈 | 分支模型隔离 | 多人无冲突 |
| 🥉 | Schema 驱动配置 | 不修改代码即可定制 |
| 4️⃣ | Delta Spec 格式 | 明确意图，易合并 |
| 5️⃣ | 三层配置级联 | 既有通用又有定制 |

---

## ⚠️ 一眼看出的限制

### 限制 1：没有并发保护
- 两个 archive 同时执行会怎样？
- 没有看到锁机制
- **影响**：多人同时work可能有race condition

### 限制 2：DAG 只支持线性依赖
- 不支持条件性依赖（如果...则...）
- 不支持可选工件
- **影响**：某些工作流无法表达

### 限制 3：Schema 假设单一版本
- 系统升级时，旧 change 怎么办？
- 没有看到 migration 机制
- **影响**：跨版本升级可能有风险

### 限制 4：性能假设
- 用 fs.globSync() 查询工件
- 大规模工程可能变慢
- **影响**：未知规模上限

---

## 🎓 关键洞察（15个字以内）

1. **文件系统是状态存储** → 简洁而有力
2. **配置优于代码** → Schema YAML控制一切
3. **显式大于隐约** → 用户清楚发生什么
4. **分离关注点** → Specs vs Changes设计
5. **验证分布** → 多个gate快速反馈

---

## 📚 进阶阅读

- Phase 1：全局架构地图（工作流图）
- Phase 2：关键路径和FSM详解
- Phase 3：模块深度分析

---

## ✅ 30分钟快速理解检查清单

- [x] 仓库类型确认（Workflow-First）
- [x] 核心问题识别（多人异步协作）
- [x] 5大模块定位（Artifact Graph, Schema, Archive, Validator, CLI）
- [x] 主工作流理解（new-change → status → instructions → archive）
- [x] 关键设计洞察（文件系统状态、Schema驱动、分支模型）
- [x] 已知限制列出（并发、DAG限制、版本管理）

**理解度评估**：✅ 80% （足以进入 Phase 1 深化）

