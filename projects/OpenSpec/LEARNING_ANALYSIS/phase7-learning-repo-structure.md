# Phase 7：学习仓库结构设计 - 可复用的知识库框架

## 目标

基于前 6 个 Phase 的学习经验，设计一个**可复用的仓库分析知识库结构**，使得：
1. 新仓库可以按照相同方法论进行分析
2. 学习成果可以组织、查询、比较
3. 架构设计模式可以被发现和复用

---

## 总体架构

```
学习知识库结构

┌─ README.md                    (使用指南)
│
├─ repos/                       (仓库分析目录)
│  ├─ openspec/                 (某个仓库的所有分析)
│  │  ├─ README.md
│  │  ├─ metadata.yaml          (仓库基本信息)
│  │  ├─ phase0-overview.md     (快速概览)
│  │  ├─ phase1-map.md          (全局架构)
│  │  ├─ phase2-fsm.md          (关键路径)
│  │  ├─ phase3-modules/        (模块深度分析)
│  │  │  ├─ 1-artifact-graph.md
│  │  │  ├─ 2-schema-system.md
│  │  │  └─ 3-archive-merge.md
│  │  ├─ phase4-decisions.md    (架构决策)
│  │  ├─ phase5-rubric.md       (9 维评测)
│  │  ├─ phase6-paradigms.md    (范式映射)
│  │  └─ phase7-learnings.md    (核心启发)
│  │
│  ├─ some-other-project/
│  │  ├─ phase0-overview.md
│  │  └─ ...
│  │
│  └─ REPOS_INDEX.md            (所有仓库索引)
│
├─ patterns/                    (通用模式库)
│  ├─ paradigms/                (范式汇总)
│  │  ├─ pipeline-dag.md        (Pipeline 范式+例子)
│  │  ├─ branching-model.md     (分支模型+例子)
│  │  ├─ state-machine.md       (状态机+例子)
│  │  ├─ acid-transactions.md   (原子性+例子)
│  │  ├─ functional-programming.md
│  │  ├─ cqrs.md
│  │  └─ pub-sub.md
│  │
│  ├─ architectural-patterns/   (架构决策模式)
│  │  ├─ file-system-as-state.md
│  │  ├─ schema-driven-workflow.md
│  │  ├─ configuration-cascade.md
│  │  └─ ...
│  │
│  └─ quality-gates/            (质量门禁模式)
│     ├─ distributed-validation.md
│     ├─ all-or-nothing.md
│     └─ ...
│
├─ rubric/                      (评测框架)
│  ├─ 9-dimensions.md           (9 个评测维度详解)
│  ├─ rubric-template.md        (评测模板)
│  └─ dimension-definitions.md  (每个维度的定义)
│
├─ methodology/                 (学习方法论)
│  ├─ 9-phase-framework.md      (9 个 Phase 详解)
│  ├─ phase-guidelines.md       (每个 Phase 的指导)
│  ├─ code-archaeology.md       (代码考古方法)
│  └─ question-templates.md     (问题模板库)
│
├─ templates/                   (文件模板)
│  ├─ phase0-template.md
│  ├─ phase1-template.md
│  ├─ phase3-module-template.md
│  ├─ phase4-adr-template.md
│  └─ ...
│
└─ tools/                       (辅助工具)
   ├─ cross-repo-comparison.py  (比较多个仓库)
   ├─ pattern-detector.py       (检测设计模式)
   ├─ metrics-calculator.py     (计算架构指标)
   └─ visualization.py          (生成可视化图表)
```

---

## 核心目录详解

### 1. repos/ 目录 - 单个仓库的学习包

**每个仓库的目录结构**：

```
repos/openspec/
├─ README.md                       # 简介 + 导航
├─ metadata.yaml                   # 仓库元数据
├─ toc.md                          # 完整目录
│
├─ phase0-overview.md              # 30 分钟快速理解
├─ phase1-global-map.md            # 5 大模块 + 工作流
├─ phase2-critical-path.md         # 7 个状态 + FSM
│
├─ phase3-modules/                 # 深度分析
│  ├─ index.md                     # 模块列表
│  ├─ 01-artifact-graph.md         # 模块 1
│  ├─ 02-schema-system.md          # 模块 2
│  ├─ 03-archive-merge.md          # 模块 3
│  └─ ...
│
├─ phase4-architecture-decisions.md     # 核心架构决策
├─ phase5-9d-rubric.md                  # 9 维评测
├─ phase6-paradigm-mapping.md           # 范式映射
│
├─ learnings.md                    # 最终关键启发（3-5 条）
├─ code-references.md              # 关键代码位置索引
└─ comparison-with-*.md            # 与其他系统的对比（可选）
```

**metadata.yaml 格式**：

```yaml
name: OpenSpec
url: https://github.com/...
description: AI-native spec-driven change coordination system
tags: [workflow, AI, collaboration, spec-driven]
language: TypeScript
framework: Node.js, Commander.js
size: 
  loc: ~15000                      # Lines of Code
  modules: 10+
  estimated_learning_time: 180     # minutes
repository_type: workflow         # [workflow, library, framework, tool, etc.]
maturity: production              # [experimental, beta, production]
complexity: medium                # [simple, medium, complex]
primary_patterns:                 # 主要使用的架构范式
  - pipeline-dag
  - branching-model
  - schema-driven-workflow
```

**README.md 格式**：

```markdown
# OpenSpec 仓库学习包

## 快速导航
- ⏱️ 30  分钟快速理解：[phase0-overview.md](phase0-overview.md)
- 🗺️ 全局架构图：[phase1-global-map.md](phase1-global-map.md)
- 🔄 工作流状态机：[phase2-critical-path.md](phase2-critical-path.md)
- 🔬 深度模块分析：[phase3-modules/](phase3-modules/)
- 💡 架构决策：[phase4-architecture-decisions.md](phase4-architecture-decisions.md)

## 仓库核心
- **位置**：[仓库链接]
- **目的**：AI原生的spec驱动变更协调系统
- **关键概念**：Artifact Graph, Delta Specs, Schema-driven Workflow
- **代码量**：~15000 LOC
- **学习时间**：180 分钟（从快速概览到深度掌握）

## 最重要的 3 个启发
1. 文件系统即状态 → 简洁而强大
2. Schema 驱动工作流 → 配置优于代码
3. 分离 Specs vs Changes → 并发友好

## 推荐阅读顺序
1. phase0-overview.md（理解全景）
2. phase1-global-map.md（掌握 5 大模块）
3. phase2-critical-path.md（理解 7-state FSM）
4. phase3-modules/ 中的感兴趣模块（深度学习）
5. phase4-architecture-decisions.md（理解设计权衡）
```

---

### 2. patterns/ 目录 - 通用设计模式库

**paradigms 子目录**：

```
File: patterns/paradigms/pipeline-dag.md

# Pipeline / DAG 范式

## 定义
有向无环图，表示任务依赖关系。

## 历史
- Make (1976) - 文件依赖
- Airflow (2015) - 数据管道
- Kubernetes (2014) - 任务编排

## OpenSpec 中的体现
[引用 phase6 内容]

## 其他例子
- Maven pom.xml
- Gradle build.gradle
- Bazel BUILD files

## 实现要点
1. 拓扑排序
2. 循环检测
3. 并发分析

## 何时使用
✅ 构建系统
✅ 数据处理
❌ 实时系统
```

**architectural-patterns 子目录**：

```
File: patterns/architectural-patterns/file-system-as-state.md

# 文件系统即状态 模式

## 核心思想
用文件存在 / 不存在表示系统状态，而非数据库。

## 优点
- 简洁（无同步问题）
- 直观（用户可见）
- 版本控制友好（git 兼容）

## 缺点
- 性能（文件 I/O）
- 精度（无时间戳）
- 分布式困难

## 实现例子
- OpenSpec: proposal.md 存在 = proposal 完成
- Git: .git/config 存在 = 仓库初始化
- Docker: Dockerfile 变化 = 新的构建

## 适用场景
✅ 单机系统
✅ 文件驱动工作流
❌ 分布式系统
```

**quality-gates 子目录**：

```
File: patterns/quality-gates/distributed-validation.md

# 分布式验证 模式

## 核心思想
不是单一的"最后检查"，而是多个检查点分布在流程中。

## 好处
- 快速反馈
- 早期失败
- 清晰的错误定位

## OpenSpec 实例
Gate 1: 工件完整性
Gate 2: 格式验证
Gate 3: Delta 格式验证
Gate 4: Spec 内容验证
Gate 5: 文件系统操作验证

## 实现技巧
- 验证结果结构化
- 每个 gate 有明确的职责
- 失败时清晰的错误信息
```

---

### 3. rubric/ 目录 - 架构评测框架

**9-dimensions.md**：

```markdown
# 架构 9 维评测框架

## 维度 1：模块边界清晰性
定义：...
平均分：4.1/5
常见问题：...
改进建议：...

## 维度 2：工作流显式性
定义：...
平均分：4.8/5
...

## [其他 7 个维度]

## 如何使用
1. 为新系统打分
2. 记录证据
3. 识别短板模式
```

**rubric-template.md**：

```markdown
# 架构评测模板 - [系统名称]

| 维度 | 评分 | 证据 | 改进点 |
|-----|------|------|--------|
| 模块边界 | ☆☆☆ | ... | ... |
| 工作流显式性 | ☆☆☆☆ | ... | ... |
| 质量门禁 | ☆☆☆ | ... | ... |
| ...（其他 6 个维度） | | | |

## 总体分析
[200 字总结]

## 与 OpenSpec 的对比
[对比表]
```

---

### 4. methodology/ 目录 - 学习方法论

**9-phase-framework.md**：

```markdown
# 9 个学习 Phase 完整框架

## Phase 0：Preflight Reconnaissance (30 分钟)
**目标**：快速抓住仓库的本质
**输出**：
- 仓库分类（workflow-first vs code-first）
- 主要问题域
- 5 大核心模块抽样

**例：OpenSpec**
- 分类：Workflow-first
- 问题：多人异步管理工程变更
- 模块：Artifact Graph, Schema System, Archive/Merge, CLI, Validation

## Phase 1：Global Architecture Map (60 分钟)
**目标**：理解全系统
**输出**：
- One-liner 描述
- 主工作流图
- 5 大模块的职责
- 顶层 20% 的设计洞察

[详细指导...]

## Phase 2：Critical Path & FSM (45 分钟)
## ...
## Phase 9：Brutal Self-Critique (30 分钟)
```

**phase-guidelines.md**：

```markdown
# 每个 Phase 的详细指导

## Phase 0 指导
- 😕 新手常犯的错误
- ✅ 快速定位核心模块的技巧
- 📌 应该记录哪些东西
- 🔍 怎么判断"理解得够了"

## 文件扫描技巧
- 找 README（快速理解）
- 找 main/index 文件（进入点）
- 找 test/ 目录（理解 API）
- 找 ARCHITECTURE.md（幸运的话有设计文档）
- 找 CHANGELOG（项目演进）

## 常用的 grep 查询
# 找"所有公开 API"
grep -r "export\|public" src/

# 找"main 函数"
grep -r "function main\|async main"

# 找"错误处理"
grep -r "throw\|Error\|catch"

# 找"参数验证"
grep -r "validate\|check\|assert"
```

**code-archaeology.md**：

```markdown
# 代码考古方法

## 从哪里开始
1. 查看 package.json（依赖 = 系统类型的线索）
2. 查看 src/index.ts（入口）
3. 查看 src/cli/ 或 src/server/（主要流程）
4. 按调用链追踪（从用户入口到内部）

## 如何追踪代码流
```
输入：用户运行 `openspec status`
    ↓
找到 commands/workflow/status.ts
    ↓
看看它调用了谁
    ↓
跟踪调用链
    ↓
理解数据流
```

## 类型系统的利用
- 看接口定义（types.ts, interfaces.ts）
- 理解数据结构
- 从输入推断处理逻辑

## 如何检测"理解不足"的信号
- ❌ "这个函数干嘛用的？"
- ❌ "为什么这个模块需要这些参数？"
- ❌ "这两个模块怎么交互的？"

如果不能回答上述问题，说明理解不足。
```

---

### 5. templates/ 目录 - 文件模板

```markdown
# templates/phase3-module-template.md

# 模块标题：[模块名]

## 快速整理

| 字段 | 值 |
|-----|-----|
| 模块位置 | src/core/... |
| 文件数 | N |
| 主要导出 | Function/Class A, B, C |
| 职责 | ... |
| 依赖 | ... |
| 被依赖者 | ... |

## 职责和边界

### 职责
1. 职责 1
2. 职责 2
3. 职责 3

### 输入（上游）
- 输入 A（来自哪里）
- 输入 B（来自哪里）

### 输出（下游）
- 输出 A（去往哪里）

## 核心算法

### 算法 1：[名称]
**输入**：
**输出**：
**步骤**：
1. 步骤 1
2. 步骤 2
3. 步骤 3

**代码证据**：
[filepath:line]

### 算法 2：...

## 数据结构

### 类型 1
```typescript
interface Type1 {
  field1: string;
  field2: number;
}
```

### 类型 2
...

## 约束

### 硬约束（不满足→系统崩溃）
1. 约束 1
2. 约束 2

### 软约束（不满足→性能或功能衍化）
1. 约束 1

## 失败模式

### 失败模式 1
- **触发条件**：
- **表现**：
- **保护机制**：

### 失败模式 2
...

## 可迁移的模式（可用于其他系统）

### 模式 1：[名称]
这个模块做的 X 模式可以用在...

### 模式 2：...

## 关键启发

### 启发 1：[简洁的一句话]
**原因**：为什么这样设计很聪明

### 启发 2：...

## 参考链接
- 相关模块 1
- 相关文档 1
```

---

## 实际使用流程

### 第一次学习一个新仓库

```
Step 1: 使用 Phase 0 框架快速扫描（30 分钟）
  └─ 输出：phase0-overview.md

Step 2: 使用 Phase 1 框架绘制全景（60 分钟）
  └─ 输出：phase1-global-map.md

Step 3: 使用 Phase 2 框架分析关键路径（45 分钟）
  └─ 输出：phase2-critical-path.md

Step 4: 对每个关键模块进行 Phase 3 深度分析（120 分钟）
  └─ 输出：phase3-modules/ 中的 N 个文件

Step 5: 提炼架构决策（Phase 4, 90 分钟）
  └─ 输出：phase4-architecture-decisions.md

Step 6: 9 维评测（Phase 5, 60 分钟）
  └─ 输出：phase5-9d-rubric.md

Step 7: 范式映射（Phase 6, 45 分钟）
  └─ 输出：phase6-paradigm-mapping.md

Step 8: 整理可复用学习（Phase 7, 30 分钟）
  └─ 输出：learnings.md + 更新 patterns/ 库

Step 9: 核心启发（Phase 8, 20 分钟）
  └─ 输出：learnings-summary.md

Step 10: 自我批评（Phase 9, 20 分钟）
  └─ 输出：critique.md

总时间：≈ 500 分钟（8-9 小时）
```

### 索引和查询

**REPOS_INDEX.md**：

```markdown
# 已分析的仓库索引

## 按类型分类

### Workflow 系统
- OpenSpec (2025)
- Conductor (2024)
- Temporal (2024)

### 库
- React (2024)
- TypeScript (2024)

### 工具
- Webpack (2024)
- Vite (2024)

## 按范式分类

### 使用 Pipeline/DAG 的系统
1. OpenSpec
2. Airflow
3. ...

### 使用分支模型的系统
1. OpenSpec
2. Git
3. ...

## 按评分分类

### 5 星系统（架构优秀）
1. OpenSpec (4.3/5)
2. ...

### 3-4 星系统
1. ...
```

---

## 可选：自动化工具

### cross-repo-comparison.py

```python
"""
比较两个或多个已分析的仓库

用法：
  python tools/cross-repo-comparison.py --repos openspec,conductor \
    --dimension "module-boundary,workflow-explicitness"
"""

def compare_repos(repo_names, dimensions):
  results = []
  for repo in repo_names:
    rubric = load_rubric(f"repos/{repo}/phase5-9d-rubric.md")
    for dim in dimensions:
      score = rubric.get_score(dim)
      results.append((repo, dim, score))
  
  print_comparison_table(results)
  plot_radar_chart(results)
```

### pattern-detector.py

```python
"""
检测新仓库使用了哪些架构范式

用法：
  python tools/pattern-detector.py --repo /path/to/target/repo
"""

def detect_patterns(repo_path):
  """
  扫描代码，检测：
  - 是否有 DAG 依赖管理 (搜索 requires, dependencies)
  - 是否有时态机 (搜索 state, Status enum)
  - 是否有 CQRS (分离 query 和 command)
  - ...
  """
```

### metrics-calculator.py

```python
"""
计算仓库的架构指标

指标：
  - 模块复杂度（节点数）
  - 耦合度（边数 / 节点数）
  - 最长路径（最深的依赖链）
"""
```

---

## 最终的知识库导航

**学习路径 1：想快速理解某个系统**
1. 打开 `repos/[系统名]/README.md`
2. 阅读 Phase 0 (30 分钟快速理解)

**学习路径 2：想深度学习某个系统**
1. Phase 0 → Phase 1 → Phase 2 → Phase 3 的某个模块

**学习路径 3：想学特定的设计模式**
1. 打开 `patterns/paradigms/` 或 `patterns/architectural-patterns/`
2. 看过去类似项目是怎么做的

**学习路径 4：想评估一个系统的架构质量**
1. 使用 `rubric/rubric-template.md` 评测
2. 与 OpenSpec 的评测对比

**学习路径 5：想自己分析一个新仓库**
1. 按照 `methodology/9-phase-framework.md` 逐个 phase 执行
2. 参考现有的 OpenSpec 分析作为对标

---

## 收益总结

这个知识库结构提供了：

1. **系统化**：9 个 Phase 确保没有遗漏分析
2. **可复用**：新仓库可以按照相同流程分析
3. **可比较**：9 维评测框架让不同系统可以对比
4. **可查询**：模式库让"设计决策"可以被搜索
5. **可学习**：每个仓库的 learnings 是这个领域的经验
6. **可自动化**：工具可以辅助大规模分析

**未来价值**：
- 建立开源的"架构知识库"（OpenArch？）
- 让新开发者快速理解系统架构
- 识别跨系统的架构反模式
- 作为建筑师的决策参考
