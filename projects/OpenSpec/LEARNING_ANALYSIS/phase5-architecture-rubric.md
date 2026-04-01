# Phase 5: 架构评测框架 - 9 维度架构评价

## 评测框架概述

这个框架从 9 个核心维度评价 OpenSpec 架构的优劣，帮助理解：
1. 系统在哪些方面设计得很好
2. 系统在哪些方面有短板
3. 哪些设计是超越必要的，哪些是不足的
4. 什么类型的项目应该借鉴这个架构

---

## 维度 1：模块边界清晰性（Module Boundary Clarity）

### 定义

系统的各个模块是否有明确的责任、明确的接口、低耦合。

### 评价

**强度：⭐⭐⭐⭐ ( 4/5 )**

#### 证据（优点）

1. **清晰的分层**：src/core/ 下的模块职责分明
   - `artifact-graph/` → 依赖追踪和工件可用性
   - `schemas/` → 工件/schema 结构定义
   - `parsers/` → markdown 解析
   - `validation/` → spec 格式检查

2. **专一的接口**：
   ```typescript
   // 创建图：
   const graph = new ArtifactGraph(schema);
   
   // 查询状态：
   const nextArtifacts = graph.getNextArtifacts(completed);
   
   // 每个模块接口非常单一
   ```

3. **清晰的依赖方向**：
   ```
   CLI commands
       ↓
   Workflow commands (status, instructions, archive)
       ↓
   Core modules (artifact-graph, specs-apply, validators)
       ↓
   Parsers & schemas
   ```
   *没有反向依赖（circular dependency）*

#### 证据（不足）

1. **状态共享不明确**：`ArtifactGraph` 和 `ProjectConfig` 的交互隐含在 `instruction-loader.ts` 中

2. **工件生成逻辑分散**：
   - `schema.ts` 中定义"什么是工件"
   - `state.ts` 中检测"工件是否完成"
   - `instruction-loader.ts` 中生成"工件的指令"
   - 三个地方都在处理"工件"的概念

3. **Archive 模块过于臃肿**：[src/core/archive.ts](src/core/archive.ts) 混合了：
   - 验证逻辑
   - 文件操作
   - 状态转换
   - 目录移动
   - 应该分拆成 validator + merger + mover

### 改进方向

```typescript
// 建议：创建 WorkflowState 接口
interface WorkflowState {
  graph: ArtifactGraph;
  config: ProjectConfig;
  completed: Set<string>;
  blocked: Map<string, string[]>;
}

// 所有命令基于这个统一状态，而不是单独查询
```

### 设计启发

✅ **适用**：当模块责任清晰时（处理 markdown、格式问题等）
❌ **不适用**：状态复杂的模块（archive 就是例子）

---

## 维度 2：工作流显式性（Workflow Explicitness）

### 定义

用户能否清楚地理解系统的执行流程、状态转换、何时发生什么。

### 评价

**强度：⭐⭐⭐⭐⭐ ( 5/5 )**

#### 证据（优点）

1. **工作流文档化**：docs/concepts.md 明确定义了 7 个状态和转换

2. **命令流程清晰**：
   ```
   openspec status
     ↓ 调用 workflow/status.ts
         ↓ 使用 artifact-graph 查询
             ↓ 返回"应该做什么"
   
   openspec workflow instructions
     ↓ 调用 workflow/instructions.ts
         ↓ 从 artifact-graph 获取下一步工件
             ↓ 生成指令
                 ↓ 显示给用户
   ```
   *每一步都是可追踪的*

3. **Schema 即文档**：
   ```yaml
   artifacts:
     - id: proposal
       generates: proposal.md
       requires: []
     - id: specs
       requires: [proposal]
   ```
   *查看这个 YAML，用户立刻明白工作流*

4. **文件位置即状态**：
   ```
   change-A/
     ├─ proposal.md      ✓ "proposal 已完成"
     ├─ design.md        ✓ "design 已完成"
     └─ specs/           ✗ "specs 未创建"
   ```
   *无需查询数据库，状态可视*

#### 证据（不足）

1. **Archive 流程模糊**：多个步骤发生在一个命令内，不清楚哪个门禁检查了什么

2. **错误信息有时不清楚**：
   ```
   Error: Validation failed
   ```
   *不知道哪个 gate 失败*

### 改进方向

```
建议：每个 gate 返回结构化错误
{
  gate: "delta-validation",
  phase: "merge",
  errors: [
    {section: "specs/auth/spec.md", issue: "duplicate requirement 'User login'"}
  ]
}
```

---

## 维度 3：质量门禁强度（Quality Gate Robustness）

### 定义

系统是否有足够的检查防止低质量数据进入系统。

### 评价

**强度：⭐⭐⭐⭐ ( 4/5 )**

#### 证据（优点）

1. **多层验证**：
   - Schema 验证（无循环、引用有效）
   - 工件完整性检查
   - Delta 格式检查
   - Spec 内容验证

2. **All-or-nothing archive**：
   ```
   验证所有 delta ──► 应用非-no-validate ──► 
   如果有任何失败 ──► 立即停止，零写入
   所有成功 ──► 原子写入 + 移动
   ```
   *没有部分成功状态*

3. **验证器是独立模块**：[src/core/validation/](src/core/validation/)
   - `validator.ts` - 主验证引擎
   - 可以单独测试
   - 可以独立替换

#### 证据（不足）

1. **没有"警告"级别**：所有失败都是错误
   ```
   系统不允许"通过但有警告"的工件
   （某些工作流可能需要这种灵活性）
   ```

2. **验证规则硬编码**：验证规则在 validator.ts 中，无法通过配置调整

3. **语义验证缺失**：系统检查格式，但不检查"这个要求在逻辑上是否合理"

### 改进方向

```typescript
// 建议：配置化验证规则
config.yaml:
  validation:
    level: "strict" | "moderate" | "lenient"
    customRules:
      - if: requirement.name.length < 10
        then: warn("Requirement name too short")
```

---

## 维度 4：上下文管理（Context Management）

### 定义

系统是否有效地管理工件之间的上下文、依赖的信息流。

### 评价

**强度：⭐⭐⭐⭐ ( 4/5 )**

#### 证据（优点）

1. **丰富的上下文生成**：[src/core/artifact-graph/instruction-loader.ts](src/core/artifact-graph/instruction-loader.ts)
   ```typescript
   async generateInstructions(
     context: ChangeContext,
     artifactId: string
   ): Promise<ArtifactInstructions> {
     return {
       background: config.context,              // 1. 项目背景
       artifactDescription: artifact.description,
       template: templateContent,               // 2. 模板
       rules: config.rules[artifactId],         // 3. 工件规则
       dependencies: [
         { id: 'proposal', content: proposal }  // 4. 依赖工件内容
       ],
       unlocks: [...]                           // 5. 这个工件会解锁什么
     };
   }
   ```
   *一个生成包含了 5 层上下文*

2. **config.context 的地位**：
   - 在 instruction-loader 中自动注入每个提示词
   - 项目可以设置全局背景，影响所有工件
   - 很有想象力的设计

3. **依赖工件自动传递**：当生成 specs 时，系统自动把 proposal 内容发给 AI

#### 证据（不足）

1. **上下文大小无限制**：
   - `config.context` 大小限制 50KB
   - 但对于大项目依赖内容可能超过 token 限制

2. **没有上下文"剪裁"机制**：
   - 即使 proposal 有 20KB，仍然全部包含
   - 可能超过 token 限制

3. **依赖可达性有限**：
   - 只能自动传递直接依赖的内容
   - 不能传递"上层工件的信息摘要"

### 改进方向

```typescript
// 建议：可配置的上下文策略
config.yaml:
  context_strategy:
    max_tokens: 2000
    dependency_depth: 1
    summarize_dependencies: true  // 自动摘要长依赖
```

---

## 维度 5：可扩展性（Extensibility）

### 定义

系统是否容易添加新功能、新工作流、自定义行为。

### 评价

**强度：⭐⭐⭐⭐⭐ ( 5/5 )**

#### 证据（优点）

1. **Schema 定制**：用户可以创建自己的 schema 而无需修改代码
   ```
   openspec/schemas/my-workflow/schema.yaml
   ```

2. **三层配置级联**：
   - 用户可以在 `~/.openspec/` 创建全局 schema
   - 项目可以在 `openspec/schemas/` 覆盖
   - 内置 schema 可以继承修改

3. **插件友好的结构**：
   - Validator 接口清晰，可以替换
   - 命令系统用 Commander，可以添加自定义命令
   - Parser 独立，可以扩展

4. **模板系统**：为每个工件配置模板，新用户不手工编写

#### 证据（不足）

1. **Schema 没有继承机制**：
   ```
   // 用户想要"在内置 spec-driven 基础上，加一个工件"
   // 无法做到，必须完整定义新 schema
   ```

2. **验证规则不可插件化**：验证逻辑硬编码，用户无法添加自定义检查

3. **没有钩子机制**：
   ```
   // 想在 archive 前执行自定义脚本？无法
   // 想在每个工件生成后有通知？无法
   ```

### 改进方向

```yaml
# 建议：Schema 继承
schema:
  extends: spec-driven       # 继承内置 schema
  artifacts:
    - id: validation        # 新增工件
      requires: [specs]
```

---

## 维度 6：可测试性（Testability）

### 定义

系统各模块是否容易编写单元测试、集成测试。

### 评价

**强度：⭐⭐⭐⭐⭐ ( 5/5 )**

#### 证据（优点）

1. **纯函数设计**：很多核心功能是纯函数
   ```typescript
   // 纯函数：无副作用，容易测试
   function parseDeltaSpec(content: string): DeltaPlan
   function parseSchema(yamlContent: string): SchemaYaml
   function getNextArtifacts(graph, completed): string[]
   ```

2. **依赖注入**：命令接收 context 对象
   ```typescript
   async statusCommand(options: {
     context: ChangeContext,    // 注入，可以 mock
     changeDir: string
   })
   ```

3. **测试 fixtures**：[test/fixtures/](test/fixtures/) 包含了示例项目
   - `test-project-a/openspec/schemas/`
   - `test-project-a/openspec/config.yaml`
   - 可以直接用这些测试

4. **集成测试完整**：[test/cli-e2e/](test/cli-e2e/)
   - 整个工作流测试
   - 实际调用 CLI 命令

#### 证据（不足）

1. **文件系统 I/O 不易隔离**：
   - 每个测试都要创建临时目录
   - 测试速度因此较慢

2. **Archive 模块测试复杂**：
   - 多个步骤，多个副作用
   - 难以只测试其中一个阶段

### 改进方向

```typescript
// 建议：使用虚拟文件系统
import { createMemoryFsSync } from 'vol';

const fs = createMemoryFsSync({
  '/project/openspec/config.yaml': 'schema: spec-driven'
});

// 测试使用虚拟 fs，速度快数倍
```

---

## 维度 7：可观测性（Observability）

### 定义

系统运行时是否提供足够的日志、指标、追踪来理解发生了什么。

### 评价

**强度：⭐⭐⭐ ( 3/5 )**

#### 证据（优点）

1. **清晰的命令输出**：
   ```
   openspec status
   ├─ ✓ proposal
   ├─ ─ specs (blocked: proposal)
   └─ ✗ design
   
   Next actions: Complete specs
   ```
   *用户可以立刻看到状态*

2. **验证错误很详细**：
   ```
   ❌ Spec validation failed:
      - File: specs/auth/spec.md
      - Line 42: Missing 'Given' in scenario
   ```

3. **日志友好的结构**：Telemetry 模块记录关键事件

#### 证据（不足）

1. **没有追踪 ID**：
   ```
   // 无法关联"这个 archive 是基于哪个前面的 status 调用的"
   // 对于调试问题很困难
   ```

2. **没有性能指标**：
   ```
   // 不知道:
   // - 查询工件需要多久?
   // - 验证需要多久?
   // - 应用 delta 需要多久?
   ```

3. **边界情况的日志不足**：
   ```
   // 当某个工件无法生成时，为什么？
   // 系统没有足够的诊断信息
   ```

### 改进方向

```typescript
// 建议：结构化日志
logger.info('delta_application_started', {
  traceId: '...',
  changeId: 'feature-A',
  specsCount: 3,
  timestamp: Date.now()
});

logger.info('delta_operation', {
  traceId: '...',
  operation: 'MODIFIED',
  requirement: 'User login',
  duration: 42  // ms
});
```

---

## 维度 8：人机交互友好性（Human-in-Loop Suitability）

### 定义

系统是否适合与人类协作，是否尊重用户的意图和自主权。

### 评价

**强度：⭐⭐⭐⭐⭐ ( 5/5 )**

#### 证据（优点）

1. **可选的自动化**：
   ```
   openspec workflow instructions     # 生成指令
   openspec workflow status          # 只查看状态，不干涉
   
   用户完全控制何时执行什么
   ```

2. **支持手工编辑**：
   ```
   System generates: proposal.md
   User edits: proposal.md 中修改了内容
   System 自动看到改变，无需重新生成
   ```
   *用户可以微调系统生成的内容*

3. **明确的"意图表达"**：
   - Delta 格式用 ADDED/MODIFIED/REMOVED 明确表达意图
   - 用户可以理解"系统想做什么"

4. **支持跳过步骤**：
   - 系统不强制顺序
   - 用户可以创意地改变流程

5. **Dry-run 支持**：
   ```
   openspec archive --dry-run   # 预览会发生什么
   ```

#### 证据（不足）

1. **没有"确认对话"**：
   ```
   openspec archive                # 直接执行
   // 应该问: "确定要 archive 吗？这会使得 tasks 工件无法更新"
   ```

2. **没有"撤销"机制**：
   - Archive 后可以在 archive/ 中找回
   - 但没有"一键撤销"命令

3. **缺乏上下文帮助**：
   ```
   Error: Validation failed
   // 应该显示: "这是最常见的 validation 失败原因..."
   ```

### 改进方向

```typescript
// 建议：交互式命令
openspec archive --interactive
  ✓ Delete existing specs? (可以 --keep 保留)
  ✓ Archive all tasks? (提示："Archive 后无法更新任务")
  ✓ Create backup before archiving? (Yes/No)
```

---

## 维度 9：复杂性控制（Complexity Control）

### 定义

系统本身的复杂性是否得到良好控制，是否易于学习和维护。

### 评价

**强度：⭐⭐⭐⭐ ( 4/5 )**

#### 证据（优点）

1. **概念数量少**：
   - Artifact（工件）
   - Change（变更）
   - Schema（工作流定义）
   - Delta spec（增量规格）
   - 这 4 个概念就覆盖了大部分
   
2. **功能划分清晰**：
   ```
   Create change
   ├─ 生成工件
   ├─ 在工件间移动（status）
   └─ Archive 变更
   
   (没有 "delete change"、"branch change" 等复杂操作)
   ```

3. **状态机简单**：
   ```
   SCAFFOLDED → PLANNING_IN_PROGRESS → ... → ARCHIVED
   
   只有 7 个状态，线性流程（不是复杂的条件转移）
   ```

4. **依赖关系是 DAG**：
   ```
   proposal → specs → design → tasks
   
   不允许循环，拓扑有序，容易推理
   ```

#### 证据（不足）

1. **Schema YAML 可能很复杂**：
   ```yaml
   # 用户的 schema 可能有 10-20 个工件，很难跟踪
   ```

2. **Template 系统的学习曲线**：
   - `artifacts[].template` 指定 template
   - Template 本身可能很复杂
   - 用户需要学习 template 语言

3. **Archive 流程虽然清晰，但步骤多**：
   ```
   7 个步骤，每个都有失败的可能
   对于新手可能很复杂
   ```

### 改进方向

```
建议 1：默认 schema（用户 99% 的情况都用它）
  spec-driven（现有的）
  快速流程（proposal → archive，跳过中间步骤）

建议 2：可视化 schema 编辑器
  图形界面配置工件和依赖
  而不是手工编辑 YAML
```

---

## 整体评测总结

| 维度 | 评分 | 评价 |
|-----|------|------|
| 1. 模块边界 | ⭐⭐⭐⭐ | 大部分清晰，Archive 有点臃肿 |
| 2. 工作流显式性 | ⭐⭐⭐⭐⭐ | 非常好，文件位置即状态 |
| 3. 质量门禁 | ⭐⭐⭐⭐ | 多层检查，All-or-nothing |
| 4. 上下文管理 | ⭐⭐⭐⭐ | 丰富的 5 层上下文 |
| 5. 可扩展性 | ⭐⭐⭐⭐⭐ | 完全可定制化 |
| 6. 可测试性 | ⭐⭐⭐⭐⭐ | 纯函数设计，易于测试 |
| 7. 可观测性 | ⭐⭐⭐ | 命令输出清晰，但缺少深层追踪 |
| 8. 人机交互 | ⭐⭐⭐⭐⭐ | 高度尊重用户，支持手工干预 |
| 9. 复杂性控制 | ⭐⭐⭐⭐ | 概念少，但 Schema YAML 可能复杂 |

**平均分：4.3/5**

---

## 系统最核心的设计选择（设计权衡）

### 选择 A：速度 vs 完整性

```
OpenSpec 选择：完整性优先

表现为：
- 验证严格（检查格式、无循环等）
- All-or-nothing archive（不允许部分成功）
- 强制要求所有工件存在

代价：
- 不够灵活（某些工作流无法用）
- 不够快（要等所有验证通过）

适用场景：
✅ 质量很重要的系统（医疗、金融）
❌ 快速迭代、宽松的项目
```

### 选择 B：自动 vs 显式

```
OpenSpec 选择：显式优先

表现为：
- 用户需要显式创建 change
- 用户需要显式指定 schema
- 系统不做"聪明的推断"

代价：
- 新手需要理解更多概念
- 配置需要更多手工填写

适用场景：
✅ 需要透明的系统（可审计、可追踪）
❌ 需要"开箱即用"，无需配置
```

### 选择 C：集中 vs 分布式

```
OpenSpec 选择：分布式检查

表现为：
- 多个 gate 分布在流程中
- 早期失败，及时反馈
- 不是单一的最后检查

代价：
- 代码流程复杂
- 多层检查，可能有重复

适用场景：
✅ 需要快速反馈（开发体验好）
❌ 只关心"最终结果对不对"
```

---

## 哪些项目应该借鉴这个架构？

### 完美匹配 ✅

1. **协作式编制系统**（多人并行工作，但需要最后合并）
   - 文档编制（Confluence-like）
   - 设计协作（Figma-like）
   - 合同起草系统

2. **质量很重要的工作流**（每个阶段都要检查）
   - 医疗记录系统
   - 法律文档审查
   - 财务报告生成

3. **AI 驱动的生成系统**（需要人类审视、编辑、合并）
   - 代码生成工具
   - 文档自动生成
   - 翻译协作平台

### 部分匹配 ⚠️

1. **有复杂工作流的系统**（OpenSpec 支持，但配置会很复杂）

2. **需要实时协作的系统**（OpenSpec 是异步设计）

### 不匹配 ❌

1. **高性能系统**（文件系统查询不够快）
2. **游戏/图形系统**（完全不同的架构需求）
3. **单人工作**（隔离的好处体现不出来）

---

## 学习这个架构的关键启发

### 启发 1：状态存储的选择 🎯

```
不要迷信"必须用数据库"
有时文件系统 + 约定更简单

OpenSpec 教科书案例：
- 文件本身是状态
- 无需同步
- 用户直观理解
- 成本极低
```

### 启发 2：显式 > 魔法 🎯

```
用户更信任"清晰但冗长"
而不是"神奇但不透明"

OpenSpec 选择"显式"的所有地方都成功了：
- 显式的依赖关系（在 schema 中）
- 显式的工件（在文件系统中）
- 显式的转换（ADDED/MODIFIED/REMOVED）
- 显式的错误（多层 gate）
```

### 启发 3：分离关注点 🎯

```
Specs vs Changes 的分离是绝妙的设计

好处：
1. Change 彼此隔离，无冲突
2. Main specs 始终稳定
3. Review 变得简单
4. Rollback 变得简单

可以借鉴到：
- 文档系统（main docs vs draft)
- 代码库（master branch vs feature branch）
- 配置系统（live config vs proposed config）
```

### 启发 4：三层级联的配置 🎯

```
不是"全有或全无"
而是"基础 → 团队 → 项目"逐层深入

好处：
1. 新用户：用内置配置，开箱即用
2. 团队：在 ~/.openspec/ 统一标准
3. 项目：在 project/openspec/ 特殊定制

可以借鉴到：
- IDE 配置（全局→工作区→项目）
- 构建系统（内置规则→公司规则→项目规则）
```

### 启发 5：Delta 而非完整 🎯

```
把"变更"和"现状"分离

好处：
1. 清晰表达意图
2. 合并逻辑简单
3. Audit trail 清晰

代价：
- 修改时需要复制原文
- 但对于文档系统很值得
```

---

## 关键失误点（如果重新设计会改进）

### 失误 1：Archive 模块过于庞大 ❌

```
当前：一个 archive.ts 文件做所有事情
建议：分拆为
  - archive-validator.ts（验证）
  - archive-merger.ts（应用 delta）
  - archive-writer.ts（写入文件）
  - archive-mover.ts（移动目录）

好处：
- 每个模块可独立测试
- 错误定位更清楚
- 复用性更高
```

### 失误 2：Validation 不可定制 ❌

```
当前：验证规则硬编码在 validator.ts
建议：规则可通过 config 注册

config.yaml:
  validation:
    customRules:
      - name: requirement_name_min_length
        check: len(name) >= 10
        level: warn  # vs error
```

### 失误 3：没有追踪能力 ❌

```
当前：log 是离散的，无法串联
建议：每个操作带上 traceId

这样可以：
- 回溯"某个工件为何卡住"
- 调试工作流问题
- 性能分析
```

### 失误 4：Schema 没有继承 ❌

```
当前：用户想基于内置 schema 做小改，需要完全复制
建议：Schema 继承机制

inherited-schema.yaml:
  extends: spec-driven
  artifacts:
    - id: new-artifact
      requires: [specs]
```

---

## 最终结论

OpenSpec 是一个**设计均衡、充分考虑用户需求、文件系统友好的生产级架构**。

### ✅ 最擅长
- 多人异步协作
- 需要完全可定制工作流
- AI + 人工混合工作

### ⚠️ 有改进空间
- 模块粒度（Archive 太大）
- 规则灵活性（验证硬编码）
- 可观测性（缺思追踪）

### 📚 最值得学习的模式
1. 文件系统即状态（简洁有力）
2. 显式胜过魔法（值得付出配置代价）
3. 分离关注点（Specs vs Changes 绝妙设计）
4. 分布式验证（多层 gate 很有启发）
5. 三层级联（向下兼容，向上定制）
