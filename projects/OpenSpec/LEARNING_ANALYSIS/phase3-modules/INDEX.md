# Phase 3：核心模块深度分析 - 3个主力模块详解

## 🎯 目标

120分钟内完整理解OpenSpec的3个最关键的模块：
1. **Artifact Graph** - DAG依赖追踪 + 工件检测 + 指令生成
2. **Schema System** - 工作流定义 + 三层级联 + 验证
3. **Archive & Merge** - Delta解析 + 应用 + 事务保证

---

## 📁 模块分析结构

每个模块分析包含：
- **快速整理** - 位置、职责、主要导出
- **职责和边界** - 输入、处理、输出
- **核心算法** - 关键函数逻辑（代码+流程）
- **数据结构** - TypeScript 类型定义
- **约束和失败模式** - 硬约束、软约束、故障处理
- **可迁移模式** - 可用于其他系统
- **关键启发** - 最值得学习的地方
- **参考链接** - 相关代码位置

---

## 🧩 3个模块一览

### 模块 1：Artifact Graph
**文件位置**：src/core/artifact-graph/  
**关键责任**：DAG依赖追踪 + 工件状态检测 + AI指令生成  
**核心概念**：文件系统即状态

**关键函数**：
- `getNextArtifacts(changeDir, completed)` → [artifact]
- `detectCompleted(changeDir)` → Set<string>
- `generateInstructions(context, artifactId)` → {background, rules, template, dependencies, ...}

**设计精妙**：
- 无数据库依赖，直接查询文件系统
- 支持模板系统和上下文注入
- 依赖工件内容自动传递

**详见**：→ [phase3-artifact-graph](phase3-artifact-graph.md)

---

### 模块 2：Schema System
**文件位置**：src/core/schemas/, src/core/project-config.ts  
**关键责任**：工作流定义 + 三层配置级联 + Schema验证  
**核心概念**：配置优于代码

**关键概念**：
- 三层级联：project-local > user-global > package built-in
- 完整的Schema YAML支持
- Zod验证框架

**设计精妙**：
- 用户无需改代码即可定制完整工作流
- 三层级联同时保证通用性和灵活性
- Schema可以完全版本控制

**详见**：→ [phase3-schema-system](phase3-schema-system.md)

---

### 模块 3：Archive & Merge Engine
**文件位置**：src/core/archive.ts, src/core/specs-apply.ts  
**关键责任**：Delta解析 + Merge应用 + All-or-nothing事务  
**核心概念**：显式的变更意图 + 确定的操作顺序 + 原子性保证

**关键流程**：
1. 解析Delta格式（ADDED/MODIFIED/REMOVED/RENAMED）
2. 应用顺序很关键：REMOVED → RENAMED → MODIFIED → ADDED
3. All-or-nothing：全验证通过才写入，否则全部回滚

**设计精妙**：
- Delta格式清晰表达用户意图
- 操作顺序确定性保证无冲突
- 原子性保证系统一致性

**详见**：→ [phase3-archive-merge](phase3-archive-merge.md)

---

## 📊 三个模块的关系

```
┌──────────────────┐
│  CLI Commands    │
│  (user input)    │
└────────┬─────────┘
         │
    ┌────┴──────────────────────┐
    │                           │
    ↓                           ↓
┌─────────────────┐      ┌──────────────────┐
│ Artifact Graph  │      │  Schema System   │
│                 │      │                  │
│ • DAG 追踪      │◄─────┤ • 工作流定义    │
│ • 工件检测      │      │ • 三层级联       │
│ • 指令生成      │      │ • 验证           │
└────────┬────────┘      └────────┬─────────┘
         │                        │
         └────────────┬───────────┘
                      ↓
             ┌─────────────────────┐
             │ Archive & Merge     │
             │                     │
             │ • Delta 解析        │
             │ • Merge 应用        │
             │ • All-or-nothing    │
             └────────┬────────────┘
                      ↓
             ┌─────────────────────┐
             │ File System (specs) │
             │ 更新后的状态        │
             └─────────────────────┘
```

---

## 🎓 学完后能做什么

- [x] 理解文件系统状态的优缺点
- [x] 设计自己的Schema系统
- [x] 实现delta-based的merge算法
- [x] 构建可靠的事务保证
- [x] 设计多人隔离的工作流

---

## 📚 推荐学习顺序

1. **快速概览**（10分钟）：本文 + 快速整理表
2. **深度理解**（100分钟）：依次阅读3个模块
3. **对标应用**（10分钟）：查看"可迁移模式"

---

## 🔗 相关文档

- 前置：[Phase 2 - 关键路径](../phase2-critical-path.md)
- 后续：[Phase 4 - 架构决策](../phase4-architecture-decisions.md)
- 应用：[Phase 8 - 重现路线](../phase8-recreation-roadmap.md)

