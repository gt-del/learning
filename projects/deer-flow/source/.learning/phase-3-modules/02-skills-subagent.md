# 模块 4️⃣：Skills 生态系统 & 模块 5️⃣：Subagent 执行

## 模块 4️⃣：Skills 生态系统

### 职责

**Skills 将"能力"从代码中分离出来，转变为"清单驱动"模式。** Agent 需要什么能力，不是改代码，而是在 `skills/public/` 或 `skills/custom/` 中添加一个文件夹。

### 完整架构

```
┌─────────────────────────────────────┐
│   Skill Lifecycle                   │
└─────────────────────────────────────┘

[File System]
  skills/
  ├─ public/                   # 内置 skill（提交到仓库）
  │  ├─ deep-research/
  │  │  ├─ SKILL.md           # skill 定义
  │  │  ├─ manifest.json      # 元数据（name, description, tools）
  │  │  └─ __init__.py        # 工具实现
  │  └─ data-analysis/
  │     └─ ...
  └─ custom/                   # 自定义 skill（gitignored）
     ├─ my-skill-1/
     └─ ...

         ↓
   [load_skills()] → 扫描文件系统
         ↓
   [parse manifest] → 提取元数据
         ↓
   [create Skill object] → 数据结构化
         ↓
   ThreadState.available_skills
         ↓
   [system_prompt] → 列出所有 skills
         ↓
   [Agent] → "我有以下 skills：skill-1, skill-2, ..."
         ↓
   [when model calls skill] → SubagentExecutor 或 direct invocation
         ↓
   [execute in sandbox]
```

### Skill 数据模型

```python
@dataclass
class Skill:
    name: str                           # e.g., "deep-research"
    description: str                    # "Write original analysis of any topic"
    license: str | None                 # MIT, Apache 2.0, etc.
    skill_dir: Path                     # /path/to/skills/public/deep-research
    skill_file: Path                    # /path/to/skill_file.py or SKILL.md
    relative_path: Path                 # deep-research (from category root)
    category: str                       # 'public' or 'custom'
    enabled: bool = False               # is this skill available?

    @property
    def skill_path(self) -> str:
        """Returns: 'deep-research' or 'category/subcategory/skill'"""
        path = self.relative_path.as_posix()
        return "" if path == "." else path

    def get_container_path(self, container_base_path: str = "/mnt/skills") -> str:
        """Returns: '/mnt/skills/public/deep-research'"""
        ...

    def get_container_file_path(self, container_base_path: str = "/mnt/skills") -> str:
        """Returns: '/mnt/skills/public/deep-research/SKILL.md'"""
        ...
```

### manifest.json 结构（最在意的部分）

```json
{
  "name": "deep-research",
  "description": "Deep research into any topic with multiple perspectives",
  "author": "DeerFlow",
  "version": "1.0.0",
  "license": "MIT",
  
  "tools": [
    {
      "name": "search_web",
      "description": "Search the web for information",
      "parameters": {...},
    },
    {
      "name": "analyze_data",
      "description": "Analyze and visualize data",
      "parameters": {...},
    }
  ],
  
  "instructions": "When using this skill, follow these steps...",
  
  "example_usage": "User: Analyze recent trends in AI...",
  
  "dependencies": ["jina_ai_skill"],
  
  "categories": ["research", "analysis"],
  
  "supported_models": ["gpt-4", "claude-3"],
}
```

### 现场位置

- [backend/packages/harness/deerflow/skills/types.py](backend/packages/harness/deerflow/skills/types.py) - Skill 数据结构
- [backend/packages/harness/deerflow/skills/loader.py](backend/packages/harness/deerflow/skills/loader.py) - 加载逻辑
- [backend/packages/harness/deerflow/skills/validation.py](backend/packages/harness/deerflow/skills/validation.py) - 验证逻辑

### 上游 / 下游

**上游**：
- Lead Agent（初始化时指定 available_skills）
- System prompt template（需要所有 skills 的列表）

**下游**：
- Subagent executor（调用 skill tools）
- Container mount（容器中的 /mnt/skills）

### 工作流程

```
Agent 决策流程：
1. System prompt 中列出所有可用 skills
2. User 提出请求
3. Model: "我应该用 deep-research skill"
4. Model 生成 tool_call: "task(name='run_deep_research', input='...')"
5. SubagentExecutor 根据 name = "run_deep_research"
6. 找到对应的 skill manifest（name="deep-research"）
7. 从 manifest.json 提取所有 tools
8. 创建一个 subagent，绑定这些 tools
9. 在隔离的沙箱中执行
```

### 为什么这样设计（核心哲学）

| 缺点 | 传统方式 | Skills 方式 |
|------|---------|-----------|
| **扩展** | 改 harness 代码 | 新建文件夹 |
| **版本** | skill 版本 = 代码版本 | skill 独立版本 |
| **权限** | skill 作者受限 | 用户可自建 `skills/custom/` |
| **容器** | 手工管理依赖 | 自动挂载 `/mnt/skills` |
| **发现** | 硬编码列表 | 自动发现 |

### 边界

**Skill 管理的职责**：
- ✅ 发现并加载 skill 定义
- ✅ 验证 manifest.json 完整性
- ✅ 列出所有可用 skills
- ✅ 按需启用/禁用 skills

**Skill 管理的边界**：
- ❌ 不执行 skill 内的代码（由 subagent 完成）
- ❌ 不管理 skill 的依赖安装（Docker 层处理）
- ❌ 不处理 skill 间的冲突（delegate 到 model）

### 失败模式 & 预防

| 失败模式 | 症状 | 预防 |
|---------|------|------|
| **manifest 无效** | JSON parse 失败 | ✅ `_validate_skill_frontmatter()` |
| **skill 找不到** | "skill deep-research not found" | ✅ load_skills() 时检查 |
| **循环依赖** | A depends on B, B depends on A | ⚠️ 目前无检查，需要用户小心 |
| **tool 冲突** | 两个 skill 的 tool 同名 | ⚠️ subagent 后注册的覆盖前面的 |

### 可迁移做法

如果你要实现自己的"能力市场"：

1. **Manifest-based 而非代码**
   ```python
   # ❌ 能力写在代码里
   AVAILABLE_SKILLS = {
       "skill_1": lambda: ...,
       "skill_2": lambda: ...,
   }
   
   # ✅ 能力写在 manifest
   for skill_dir in os.listdir("skills/"):
       manifest = load_json(f"{skill_dir}/manifest.json")
       register_skill(manifest)
   ```

2. **自动发现而非手工注册**
   ```python
   # ✅ 在初始化时自动扫描
   def load_skills():
       return [Skill(...) for dir in discover_skill_dirs()]
   ```

3. **按分类隔离（public vs custom）**
   ```python
   # ✅ 公共库 vs 用户自定义
   skills_public = load_from("skills/public/")
   skills_custom = load_from("skills/custom/")  # gitignored
   ```

4. **容器友好的挂载点**
   ```python
   # ✅ 固定的挂载路径
   CONTAINER_SKILLS_PATH = "/mnt/skills"
   # 容器启动时: -v /host/skills:/mnt/skills:ro
   ```

### 我准备做的实验

[ ] Phase 3 后续中，写一个最小的 skill
[ ] Phase 8+ 中，实现 manifest.json 的验证
[ ] 测试循环依赖检测

---

## 模块 5️⃣：Subagent 执行模型

### 职责

**Subagent 让 lead agent 能够委托后台任务，而不需要阻塞等待。** 重点是**异步、超时、隔离**。

### 关键概念

```
Lead Agent (主线程)
    │
    ├─ [能做的] 立即处理（e.g., 回答问题）
    │
    └─ [做不了或耗时] 委托到后台
       │
       └─ SubagentExecutor.execute_async(task)
          ├─ 立即返回 task_id
          └─ 后台线程:
             ├─ 创建独立的 agent instance
             ├─ 运行完整的 agent loop
             ├─ 存储结果到 _background_tasks{}
             └─ 如果超时 → timeout 状态

Lead Agent 可以后续：
└─ 查询 task_id 的执行状态和结果
```

### 现场位置

[backend/packages/harness/deerflow/subagents/executor.py](backend/packages/harness/deerflow/subagents/executor.py)

### SubagentExecutor 的完整接口

```python
class SubagentExecutor:
    def __init__(
        self,
        config: SubagentConfig,
        tools: list[BaseTool],
        parent_model: str | None = None,
        sandbox_state: SandboxState | None = None,
        thread_data: ThreadDataState | None = None,
        thread_id: str | None = None,
        trace_id: str | None = None,
    ):
        """Initialize the executor.
        
        Args:
            config: SubagentConfig (name, description, system_prompt, tools, model, max_turns, timeout_seconds)
            tools: List of available tools (will be filtered by config.tools / disallowed_tools)
            parent_model: Parent agent's model (for "inherit" mode)
            sandbox_state: Sandbox isolation from parent
            thread_data: File system context from parent
            thread_id: For sandbox operations
            trace_id: For distributed tracing (links parent and subagent logs)
        """
        pass

    # Synchronous execution (blocks caller)
    def execute(self, task: str) -> SubagentResult:
        """Blocking execution - waits for subagent to complete."""
        pass

    # Asynchronous execution (returns immediately with task_id)
    def execute_async(self, task: str, task_id: str | None = None) -> str:
        """Non-blocking execution - returns task_id immediately."""
        return task_id

    # Check async task status
    def check_status(self, task_id: str) -> SubagentResult | None:
        """Get status and results of background task."""
        pass
```

### SubagentResult 数据结构

```python
@dataclass
class SubagentResult:
    task_id: str                        # unique identifier
    trace_id: str                       # for distributed tracing
    status: SubagentStatus              # PENDING | RUNNING | COMPLETED | FAILED | TIMED_OUT
    result: str | None = None           # final answer (if completed)
    error: str | None = None            # error message (if failed)
    started_at: datetime | None = None  # when execution started
    completed_at: datetime | None = None # when execution completed
    ai_messages: list[dict] | None = None # all AI messages during execution
```

### 执行流程（代码级）

```python
# [Global state]
_background_tasks: dict[str, SubagentResult] = {}
_scheduler_pool = ThreadPoolExecutor(max_workers=3)    # 调度线程池
_execution_pool = ThreadPoolExecutor(max_workers=3)    # 执行线程池

# [Async 执行入口]
def execute_async(self, task: str, task_id: str | None = None) -> str:
    if task_id is None:
        task_id = str(uuid.uuid4())
    
    # 立即创建 result 对象（状态 = PENDING）
    result = SubagentResult(
        task_id=task_id,
        trace_id=trace_id or generate_trace_id(),
        status=SubagentStatus.PENDING,
    )
    _background_tasks[task_id] = result
    
    # 提交到线程池（非阻塞）
    _scheduler_pool.submit(
        self._schedule_execution,  # 先调度
        task_id=task_id,
        task=task,
    )
    
    # 立即返回（!）
    return task_id

# [后台调度器]
def _schedule_execution(self, task_id: str, task: str):
    """Run in scheduler pool."""
    try:
        # 提交到执行线程池
        future = _execution_pool.submit(
            self._aexecute,  # 异步执行
            task=task,
            result_holder=_background_tasks[task_id],
        )
        
        # 等待完成（带超时）
        result = future.result(timeout=self.config.timeout_seconds)
        _background_tasks[task_id] = result
    except TimeoutError:
        _background_tasks[task_id].status = SubagentStatus.TIMED_OUT
    except Exception as e:
        _background_tasks[task_id].status = SubagentStatus.FAILED
        _background_tasks[task_id].error = str(e)

# [实际执行逻辑]
async def _aexecute(self, task: str, result_holder: SubagentResult | None = None) -> SubagentResult:
    """Run in execution pool - this is where the agent actually runs."""
    result_holder.status = SubagentStatus.RUNNING
    result_holder.started_at = datetime.now()
    
    try:
        # 构建 subagent
        agent = create_agent(...)
        
        # 运行 agent loop（with max_turns 限制）
        for turn in range(self.config.max_turns):
            # ... agent loop ...
        
        # 完成
        result_holder.status = SubagentStatus.COMPLETED
        result_holder.result = final_answer
    except Exception as e:
        result_holder.status = SubagentStatus.FAILED
        result_holder.error = str(e)
    
    result_holder.completed_at = datetime.now()
    return result_holder
```

### 关键特性：工具过滤

```python
def _filter_tools(
    all_tools: list[BaseTool],
    allowed: list[str] | None,       # allowlist
    disallowed: list[str] | None,    # denylist
) -> list[BaseTool]:
    """Filter tools based on subagent config.
    
    Priority: Allowlist > Denylist > All
    """
    filtered = all_tools
    
    # Allowlist 优先
    if allowed is not None:
        allowed_set = set(allowed)
        filtered = [t for t in filtered if t.name in allowed_set]
    
    # Denylist（默认 denied: ["task"]  防止 subagent 委托给另一个 subagent）
    if disallowed is not None:
        disallowed_set = set(disallowed)
        filtered = [t for t in filtered if t.name not in disallowed_set]
    
    return filtered
```

### 上游 / 下游

**上游**：
- Lead Agent（调用 execute_async）
- 用户（查询 check_status）

**下游**：
- SubagentConfig（确定如何执行）
- Thread Pool（实际执行）
- Sandbox（隔离执行环境）

### 内置 Subagents

```python
BUILTIN_SUBAGENTS = {
    "general-purpose": SubagentConfig(
        name="general-purpose",
        description="General-purpose AI agent for most tasks",
        system_prompt="You are a general-purpose assistant...",
        tools=None,  # 继承所有工具
        max_turns=50,
        timeout_seconds=900,  # 15 分钟
    ),
    
    "bash": SubagentConfig(
        name="bash",
        description="Specialized in bash scripting and command execution",
        system_prompt="You are a bash expert...",
        tools=["bash"],  # 仅 bash 工具
        max_turns=20,
        timeout_seconds=300,  # 5 分钟
    ),
}
```

### 为什么异步

| 同步 | 异步 |
|------|------|
| Lead agent 阻塞等待 | Lead agent 立即继续 |
| 用户感受"卡" | 用户感受"响应快" |
| 简单，但体验差 | 复杂，但体验好 |

### 为什么有超时

| 无超时 | 有超时 |
|-------|-------|
| Subagent 可能永不返回 | 所有任务都有时间限制 |
| 系统可能进入死锁 | 可预测的资源使用 |
| 用户永远等不到 | 5 分钟内 subagent 完成或超时 |

### 边界

**Subagent 的职责**：
- ✅ 异步执行任务
- ✅ 管理 max_turns 和 timeout
- ✅ 过滤工具
- ✅ 继承沙箱隔离

**Subagent 的边界**：
- ❌ 不定义子任务本身（由 model 决策）
- ❌ 不处理错误恢复（由 lead agent 处理）
- ❌ 不管理结果存储（result 存在内存中）

### 失败模式 & 预防

| 失败模式 | 症状 | 预防 |
|---------|------|------|
| **无限循环** | subagent 永不返回 | ✅ timeout + loop detection |
| **工具滥用** | subagent 调用 "task" 工具，导致无限委托 | ✅ 默认 disallowed=["task"] |
| **资源耗尽** | 太多后台任务，线程池满 | ✅ max_workers=3 限制 |
| **结果丢失** | 任务完成但用户查不到结果 | ✅ _background_tasks{} 持久化（或写数据库） |
| **Trace 丢失** | 无法追踪 subagent 执行 | ✅ trace_id 链接 parent 和 subagent |

### 可迁移做法

如果你要实现自己的异步执行系统：

1. **Async-first 设计**
   ```python
   # ❌ 用同步 API
   result = executor.execute(task)  # 阻塞
   
   # ✅ 用异步 API
   task_id = executor.execute_async(task)  # 立即返回
   result = await executor.check_status(task_id)  # 后续查询
   ```

2. **双线程池设计**
   ```python
   # ✅ 调度器 + 执行器分离
   _scheduler_pool = ThreadPoolExecutor(max_workers=3)
   _execution_pool = ThreadPoolExecutor(max_workers=5)
   # 调度器管理生命周期，执行器运行真正的任务
   ```

3. **全局任务表**
   ```python
   # ✅ 集中管理所有后台任务
   _background_tasks: dict[task_id, SubagentResult]
   # 便于查询、监控、清理
   ```

4. **工具隔离**
   ```python
   # ✅ Subagent 的工具不能包括 "task"
   disallowed = ["task"]  # 防止无限委托链
   ```

### 我准备做的实验

[ ] Phase 8+ 中，实现最小的 SubagentExecutor
[ ] 测试超时机制的实际行为
[ ] 模拟高并发场景下的线程池行为

### 还有哪些待验证问题

- [ ] _background_tasks{} 中的结果会否被清理？何时清理？
- [ ] 是否支持取消正在执行的任务？
- [ ] 多线程访问 _background_tasks{} 是否线程安全？（应该用 Lock）

---

✅ **Phase 3 全部完成**（5 个核心模块深度分析）

## 模块卡片汇总

| 模块 | 职责 | 关键设计 | 可迁移度 |
|------|------|---------|--------|
| ThreadState | 单一真值源 | Annotated + Reducer | ⭐⭐⭐⭐⭐ |
| Lead Agent | 编排大脑 | 三层 fallback | ⭐⭐⭐⭐ |
| SandboxProvider | 隔离执行 | Strategy Pattern | ⭐⭐⭐⭐⭐ |
| Skills Eco | 能力市场 | Manifest-based | ⭐⭐⭐⭐ |
| Subagent | 后台执行 | 异步 + 超时 | ⭐⭐⭐⭐⭐ |

---

**进入 Phase 4：架构决策提炼**

现在阶段已明确系统如何工作。Phase 4 会问：**作者为什么这样设计？有哪些取舍？**
