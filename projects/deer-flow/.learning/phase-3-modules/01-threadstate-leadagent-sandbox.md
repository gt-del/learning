# Phase 3：模块精读

## 模块 1️⃣：ThreadState 数据模型

### 职责

**ThreadState 是整个 agent 系统的单一真值源（Single Source of Truth）。** 它集中管理线程级别的所有状态，避免状态分散在对象树中导致不一致。

### 完整定义

```python
from typing import Annotated, NotRequired, TypedDict
from langchain.agents import AgentState

class SandboxState(TypedDict):
    sandbox_id: NotRequired[str | None]

class ThreadDataState(TypedDict):
    workspace_path: NotRequired[str | None]
    uploads_path: NotRequired[str | None]
    outputs_path: NotRequired[str | None]

class ViewedImageData(TypedDict):
    base64: str
    mime_type: str

class ThreadState(AgentState):
    # LangChain AgentState 提供的基础字段
    # ├─ messages: list[BaseMessage]    # 对话历史
    # ├─ next_action: str | None        # 下一步动作
    # └─ updates: dict                  # 状态更新
    
    # DeerFlow 扩展字段
    sandbox: NotRequired[SandboxState | None]
    thread_data: NotRequired[ThreadDataState | None]
    title: NotRequired[str | None]
    artifacts: Annotated[list[str], merge_artifacts]      # 自定义 reducer
    todos: NotRequired[list | None]
    uploaded_files: NotRequired[list[dict] | None]
    viewed_images: Annotated[dict[str, ViewedImageData], merge_viewed_images]
```

### 现场位置 & 架构

**[backend/packages/harness/deerflow/agents/thread_state.py](backend/packages/harness/deerflow/agents/thread_state.py)**

### 字段详解

| 字段 | 类型 | 来源 | 由谁管理 | 生命周期 |
|------|------|------|---------|---------|
| **messages** | `list[BaseMessage]` | AgentState | LangGraph core | 不断追加 |
| **sandbox** | `SandboxState` | 扩展 | SandboxMiddleware | init → cleanup |
| **thread_data** | `ThreadDataState` | 扩展 | ThreadDataMiddleware | init → cleanup |
| **title** | `str \| None` | 扩展 | TitleMiddleware | None → generated |
| **artifacts** | `list[str]` | 扩展 | ToolMessages / tools | 逐步追加（deduplicated）|
| **todos** | `list[dict]` | 扩展 | TodoMiddleware | None → managed |
| **uploaded_files** | `list[dict]` | 扩展 | UploadsMiddleware | init → persist |
| **viewed_images** | `dict` | 扩展 | ViewImageMiddleware | {} → populated → {} |

### 关键设计：Reducer 函数

```python
def merge_artifacts(existing: list[str] | None, new: list[str] | None) -> list[str]:
    """Reducer for artifacts list - merges and deduplicates artifacts."""
    if existing is None:
        return new or []
    if new is None:
        return existing
    # Use dict.fromkeys to deduplicate while preserving order
    return list(dict.fromkeys(existing + new))

def merge_viewed_images(existing: dict[str, ViewedImageData] | None, new: dict[str, ViewedImageData] | None) -> dict[str, ViewedImageData]:
    """Reducer for viewed_images dict - merges image dictionaries.
    
    Special case: If new is an empty dict {}, it clears the existing images.
    This allows middlewares to clear the viewed_images state after processing.
    """
    if existing is None:
        return new or {}
    if new is None:
        return existing
    # Special case: empty dict means clear all viewed images
    if len(new) == 0:
        return {}
    # Merge dictionaries, new values override existing ones for same keys
    return {**existing, **new}
```

**为什么需要 Reducer？**

- **问题**：多个 middleware 可能同时更新 `artifacts`，如果简单覆盖会丢失数据
- **方案**：Annotated 类型 + reducer 函数，自动处理合并
- **对标**：Redux / Pydantic 的字段自定义逻辑

### 在整个系统中的位置

```
┌─────────────────────────────────────────────────────────┐
│              各个 Middleware                             │
│  ├─ 都读 ThreadState（获取 messages, sandbox_id 等）   │
│  ├─ 都可能写 ThreadState（修改特定字段）                │
│  └─ LangGraph 自动处理 merge（via reducer 函数）       │
└────────────┬──────────────────────────────────────────┘
             │
      read / write
             │
┌────────────▼──────────────────────────────────────────────┐
│            ThreadState 【中央数据通道】                    │
│                                                            │
│  总是扮演"共享全局状态"的角色，不是传参                   │
│  （LangGraph 强制要求状态集中在一个对象里）               │
└────────────┬──────────────────────────────────────────────┘
             │
      LangGraph Runtime
             │
   每次迭代自动：
   ├─ 收集 middleware 的修改
   ├─ 应用 reducer 合并
   └─ 生成新的 ThreadState 版本
```

### 输入 / 输出

**输入**（初始化时）：
```python
{
    "messages": [HumanMessage(content="用户问题")],
    "thread_id": "thread_xxx",  # 用于辅助加载 thread_data
}
```

**输出**（提交时）：
```python
{
    "messages": [ ... 完整对话历史 ... ],
    "sandbox": {"sandbox_id": "local:xxx"},
    "thread_data": {
        "workspace_path": "/tmp/thread_xxx",
        "uploads_path": "/tmp/thread_xxx/uploads",
        "outputs_path": "/tmp/thread_xxx/outputs",
    },
    "title": "生成的对话标题",
    "artifacts": ["/tmp/xxx/file1.txt", "/tmp/xxx/file2.pdf"],
    "todos": [...],
    "uploaded_files": [...],
    "viewed_images": {},  # 已清空
}
```

### 边界

**ThreadState 的职责**：
- ✅ 存储**线程级别**的状态（与 thread_id 一一对应）
- ✅ 支持多个 middleware 的**并发读写**（via reducer）

**ThreadState 的边界**：
- ❌ 不存储全局配置（用 config.yaml）
- ❌ 不存储用户认证信息（用 context.user）
- ❌ 不存储模型参数（在每次调用时通过 cfg 传）

**为什么**：状态应该是"变化的"，配置应该是"静态的"。混淆这两者会导致难以调试的 bug。

### 约束

1. **大小约束**：messages 历史过长时由 SummarizationMiddleware 压缩
2. **一致性约束**：messages 中 tool_calls 必须有对应的 ToolMessage（由 DanglingToolCallMiddleware 保证）
3. **安全约束**：sandbox_id 必须有效（由 SandboxMiddleware 获取后设置）
4. **顺序约束**：viewed_images 在 ViewImageMiddleware 处理后清空（by merge_viewed_images 的特殊情况）

### 失败模式 & 预防

| 失败模式 | 症状 | 预防 |
|---------|------|------|
| **状态分散** | middleware A 写的数据，middleware B 看不到 | ✅ 集中在 ThreadState 里 |
| **并发写冲突** | artifacts 被覆盖而非合并 | ✅ 用 Annotated reducer |
| **历史泄漏** | 旧对话数据混进新对话 | ✅ 每个 thread_id 独立 ThreadState |
| **图像缓存未清** | viewed_images 里有上一轮的数据 | ✅ 特殊 merge 处理（empty dict 清空） |

### 可迁移做法

如果你要在自己的系统中实现类似 ThreadState：

1. **集中管理线程状态**
   ```python
   # ❌ 避免这样做
   class MyAgent:
       self.state = {...}
       self.memory = {...}
       self.context = {...}
   
   # ✅ 这样做
   class MyThreadState(TypedDict):
       state: dict
       memory: dict
       context: dict
   ```

2. **为可能并发更新的字段定义 Reducer**
   ```python
   # ❌ 简单覆盖
   ThreadState.artifacts = new_artifacts
   
   # ✅ 定义 Reducer 并自动合并
   artifacts: Annotated[list[str], merge_artifacts]
   ```

3. **使用 TypedDict 而非 Dataclass（如果需要 LangGraph 兼容）**
   ```python
   # ❌ Dataclass 不兼容 LangGraph
   @dataclass
   class ThreadState:
       messages: list
   
   # ✅ TypedDict 兼容
   class ThreadState(TypedDict):
       messages: list
   ```

4. **对字段的生命周期有明确的文档**
   ```python
   # ✅ 清楚地标注
   sandbox: NotRequired[SandboxState]      # init by ThreadDataMiddleware
   title: NotRequired[str | None]          # generated by TitleMiddleware
   artifacts: list[str]                    # accumulated by tool executions
   ```

### 我准备做的实验

[ ] Phase 7+ 中，设计类似的 StateSchema for mini-impl
[ ] 测试 Reducer 函数在高并发场景下的行为
[ ] 对比 ThreadState vs 分散状态的优缺点

### 还有哪些待验证问题

- [ ] NotRequired 字段可以在运行时被访问吗？需要 .get() 还是直接访问？
- [ ] Reducer 函数什么时候被调用（每次 update 时？还是 END 时？）
- [ ] 是否可以定义 setter 来阻止某些字段的修改？

---

## 模块 2️⃣：Lead Agent & make_lead_agent

### 职责

**`make_lead_agent()` 是整个系统的大脑工厂。** 它根据运行时配置，动态构建一个完整的 agent graph（包含模型、工具、middleware、系统提示词）。

### 现场位置

[backend/packages/harness/deerflow/agents/lead_agent/agent.py](backend/packages/harness/deerflow/agents/lead_agent/agent.py) - 第 273-340 行

### 完整流程（代码级实现）

```python
def make_lead_agent(config: RunnableConfig):
    # [Step 1] 解析运行时配置
    cfg = config.get("configurable", {})
    thinking_enabled = cfg.get("thinking_enabled", True)
    reasoning_effort = cfg.get("reasoning_effort", None)
    requested_model_name: str | None = cfg.get("model_name") or cfg.get("model")
    is_plan_mode = cfg.get("is_plan_mode", False)
    subagent_enabled = cfg.get("subagent_enabled", False)
    max_concurrent_subagents = cfg.get("max_concurrent_subagents", 3)
    is_bootstrap = cfg.get("is_bootstrap", False)
    agent_name = cfg.get("agent_name")
    
    # [Step 2] 模型名称解析（3 层 fallback）
    agent_config = load_agent_config(agent_name) if not is_bootstrap else None
    agent_model_name = agent_config.model if agent_config and agent_config.model else _resolve_model_name()
    model_name = requested_model_name or agent_model_name
    # fallback chain: request override → agent config → global default
    
    # [Step 3] 模型能力检查
    app_config = get_app_config()
    model_config = app_config.get_model_config(model_name) if model_name else None
    
    if model_config is None:
        raise ValueError("No chat model could be resolved...")
    
    if thinking_enabled and not model_config.supports_thinking:
        logger.warning(f"Thinking mode not supported; fallback to non-thinking")
        thinking_enabled = False
    
    # [Step 4] 日志 & LangSmith 元数据
    logger.info(f"Create Agent({agent_name}) → thinking_enabled: {thinking_enabled}...")
    
    if "metadata" not in config:
        config["metadata"] = {}
    config["metadata"].update({
        "agent_name": agent_name or "default",
        "model_name": model_name or "default",
        "thinking_enabled": thinking_enabled,
        "is_plan_mode": is_plan_mode,
        "subagent_enabled": subagent_enabled,
    })
    
    # [Step 5] 根据模式选择不同的 agent
    if is_bootstrap:
        # 特殊模式：最小化提示词，用于自定义 agent 创建
        return create_agent(
            model=create_chat_model(name=model_name, thinking_enabled=thinking_enabled),
            tools=get_available_tools(model_name=model_name, subagent_enabled=subagent_enabled) + [setup_agent],
            middleware=_build_middlewares(config, model_name=model_name),
            system_prompt=apply_prompt_template(subagent_enabled=subagent_enabled, ...),
            state_schema=ThreadState,
        )
    
    # [Step 6] 默认模式：完整 lead_agent
    return create_agent(
        model=create_chat_model(
            name=model_name,
            thinking_enabled=thinking_enabled,
            reasoning_effort=reasoning_effort,  # o1 style reasoning
        ),
        tools=get_available_tools(
            model_name=model_name,
            groups=agent_config.tool_groups if agent_config else None,
            subagent_enabled=subagent_enabled,
        ),
        middleware=_build_middlewares(config, model_name=model_name, agent_name=agent_name),
        system_prompt=apply_prompt_template(
            subagent_enabled=subagent_enabled,
            max_concurrent_subagents=max_concurrent_subagents,
            agent_name=agent_name,
        ),
        state_schema=ThreadState,
    )
```

### 上游 / 下游

**上游**：
- LangGraph Server（通过 langgraph.json 调用这个函数）
- FastAPI Gateway（通过 client call 传递 config）

**下游**：
- `create_agent()` - LangChain 函数（构建 agent graph）
- 所有 middleware - 由构建出来的 agent 自动执行
- 模型 API - 由构建出来的 agent 调用

### 关键参数详解

| 参数 | 来源 | 作用 | 备注 |
|------|------|------|------|
| **model** | `create_chat_model()` | 推理引擎 | supports_thinking, reasoning_effort 可动态控制 |
| **tools** | `get_available_tools()` | Agent 能做什么 | 从 skills + subagents + builtin 和并 |
| **middleware** | `_build_middlewares()` | 质量控制链 | 15 层，顺序很关键 |
| **system_prompt** | `apply_prompt_template()` | Agent 的角色和行为 | 在这里列出所有 skills |
| **state_schema** | `ThreadState` | 状态模型 | 强制 TypedDict 格式 |

### 三层 Model Name 解析（关键设计）

```
请求中的 model_name
        ↓
    （如果有）
        ↓
agent_config.model
        ↓
    （如果有）
        ↓
_resolve_model_name()（全局默认）
        ↓
    （必须有，否则 ValueError）
```

**为什么需要三层？**
- 请求时可以临时覆盖模型
- Agent 可以指定偏好的模型
- 全局有默认模型
- 三层都失败 = 配置错误（立即 fail-fast）

### 边界

**make_lead_agent 的职责**：
- ✅ 组装各个组件（模型、工具、middleware、提示词）
- ✅ 做模型能力检查（thinking support？）
- ✅ 生成 LangSmith 元数据
- ✅ 决定是 bootstrap 模式还是常规模式

**make_lead_agent 的边界**：
- ❌ 不运行 agent（由 LangGraph runtime 完成）
- ❌ 不持久化配置（由 config.yaml 完成）
- ❌ 不处理单个工具调用的细节（由 middleware 完成）

### 约束

1. **模型必须存在**：无效的 model_name 会立即抛异常
2. **思考模式检查**：thinking_enabled=true 但模型不支持自动降级
3. **Thinking 成本**：thinking 会增加 token 成本，应该可配置
4. **工具列表稳定**：一旦 agent 创建，工具列表不再改变

### 失败模式 & 预防

| 失败模式 | 症状 | 预防 |
|---------|------|------|
| **模型不存在** | "Model 'gpt-999' not found" | ✅ config.yaml 中明确定义 |
| **思考模式不支持** | thinking 被静默忽略 | ✅ 日志警告 + 自动降级 |
| **工具列表空** | 模型没有可用工具 | ✅ bootstrap 模式有 `setup_agent` 工具 |
| **Middleware 顺序错** | 质量控制失效 | ✅ `_build_middlewares()` 严格顺序 |

### 可迁移做法

如果你要写自己的 agent factory：

1. **三层配置 fallback**
   ```python
   # ❌ 只支持一层
   model = config["model"] or raise ValueError()
   
   # ✅ 支持多层 fallback
   model = (
       request_model or
       agent_config.model or
       global_default_model or
       raise ValueError(...)
   )
   ```

2. **能力检查与自动降级**
   ```python
   # ❌ 盲目使用
   agent.thinking_enabled = true
   
   # ✅ 检查后自动降级
   if thinking_enabled and not model.supports_thinking:
       logger.warning("Downgrading...")
       thinking_enabled = false
   ```

3. **元数据用于可观测性**
   ```python
   # ✅ 为每个 agent 记录完整的配置状态
   metadata = {
       "agent_name": ...,
       "model_name": ...,
       "thinking_enabled": ...,
       "is_plan_mode": ...,
   }
   # 这样 downstream tools（LangSmith）能追踪完整的上下文
   ```

4. **模式多样化（bootstrap vs normal）**
   ```python
   # ✅ 根据需要选择不同的模板
   if is_bootstrap:
       return create_agent(..., system_prompt=minimal_prompt)
   else:
       return create_agent(..., system_prompt=full_prompt)
   ```

### 我准备做的实验

[ ] Phase 8+ 中，实现自己的 make_agent() 函数
[ ] 测试三层 model 解析的实际行为
[ ] 对比 bootstrap 模式和常规模式生成的 agent

### 还有哪些待验证问题

- [ ] 为什么用 `RunnableConfig` 而不是普通 dict？
- [ ] `reasoning_effort` 具体如何传给模型？
- [ ] 能否动态增加或移除工具而不重建 agent？

---

## 模块 3️⃣：SandboxProvider 隔离架构

### 职责

**`SandboxProvider` 是安全执行的守门人。** 它定义了一套统一的接口，支持三种隔离级别：local（直接文件系统）、docker（容器）、provisioner（Kubernetes）。

### 现场位置

[backend/packages/harness/deerflow/sandbox/sandbox_provider.py](backend/packages/harness/deerflow/sandbox/sandbox_provider.py)

### 完整接口

```python
class SandboxProvider(ABC):
    """Abstract base class for sandbox providers"""

    @abstractmethod
    def acquire(self, thread_id: str | None = None) -> str:
        """Acquire a sandbox environment and return its ID.
        
        Returns: The ID of the acquired sandbox environment.
        """
        pass

    @abstractmethod
    def get(self, sandbox_id: str) -> Sandbox | None:
        """Get a sandbox environment by ID.
        
        Args:
            sandbox_id: The ID of the sandbox environment to retain.
        """
        pass

    @abstractmethod
    def release(self, sandbox_id: str) -> None:
        """Release a sandbox environment.
        
        Args:
            sandbox_id: The ID of the sandbox environment to destroy.
        """
        pass
```

### 三种实现对比

```
┌──────────────────────────────────────┐
│      SandboxProvider                  │
│  (Interface - Strategy Pattern)       │
└────┬──────────────────────┬─────────┬┘
     │                      │         │
┌────▼──────────────────────▼────┐┌──▼──────────────────┐┌──────────┐
│ LocalSandboxProvider           ││ DockerSandboxProvider││ Provisioner...
│                                ││                      ││
│ acquire() → "local:xxx"        ││ acquire() → "docker:yyy"  ││ "k8s:xxx"
│ (生成临时目录)                 ││ (启动容器)   ││ (启动 pod)
│                                ││                      ││
│ get(id) → LocalSandbox         ││ get(id) → DockerSandbox  ││ RemoteSandbox
│ (操作本地文件)                 ││ (通过 subprocess)  ││ (通过 HTTP/gRPC)
│                                ││                      ││
│ release() → 删除目录           ││ release() → 停止容器   ││ 删除 pod
└────────────────────────────────┘└──────────────────────┘└──────────┘

【操作界面】都一样：execute_command, read_file, write_file, ...
【执行位置】完全不同
【隔离级别】逐级增强：filesystem → subprocess → pod
```

### 上游 / 下游

**上游**：
- ThreadState（记录 sandbox_id）
- SandboxMiddleware（获取 provider）
- config.yaml（指定使用哪个 provider）

**下游**：
- Sandbox 实现类（LocalSandbox, DockerSandbox, ...）
- Tool 执行器（bash, file_ops）

### 工作流程

```
【Thread 启动】
    ↓
ThreadDataMiddleware 调用 SandboxProvider.acquire(thread_id)
    ↓
provider 根据 config 选择实现: 
    ├─ LocalSandboxProvider → 返回 "local:tmp_xxx"
    ├─ DockerSandboxProvider → 返回 "docker:container_xxx"
    └─ ProvisionerProvider → 返回 "k8s:pod_xxx"
    ↓
ThreadState.sandbox = { sandbox_id: "local:tmp_xxx" }
    ↓
【当有工具调用时】
    ↓
Tool Handler 调用 SandboxProvider.get(sandbox_id)
    ↓
provider 根据 ID 前缀返回对应的 Sandbox 实例
    ├─ "local:xxx" → LocalSandbox (已有的对象，从缓存取)
    ├─ "docker:xxx" → DockerSandbox (已有的对象)
    └─ "k8s:xxx" → RemoteSandbox (通过网络调用)
    ↓
调用 sandbox.execute_command() / sandbox.read_file() / ...
    ↓
执行完成，检索结果
    ↓
【Thread 结束】
    ↓
SandboxMiddleware 调用 SandboxProvider.release(sandbox_id)
    ↓
provider 清理资源:
    ├─ LocalSandboxProvider → 删除临时目录
    ├─ DockerSandboxProvider → 停止并删除容器
    └─ ProvisionerProvider → 删除 pod
```

### 获取 SandboxProvider 的方式

```python
def get_sandbox_provider(**kwargs) -> SandboxProvider:
    """Get the sandbox provider singleton."""
    global _default_sandbox_provider
    
    if _default_sandbox_provider is not None:
        return _default_sandbox_provider
    
    # 从 config.yaml 读取
    app_config = get_app_config()
    sandbox_config = app_config.sandbox
    
    # 使用 resolve_class 动态加载实现类
    provider_class = resolve_class(sandbox_config.use, SandboxProvider)
    _default_sandbox_provider = provider_class(**sandbox_config.kwargs)
    
    return _default_sandbox_provider
```

**关键点**：使用 `resolve_class()` 通过字符串路径加载类，实现完整的 DI。

### 边界

**SandboxProvider 的职责**：
- ✅ 管理沙箱生命周期（acquire, get, release）
- ✅ 提供统一的 Sandbox 接口
- ✅ 处理环境差异（local vs docker vs k8s）

**SandboxProvider 的边界**：
- ❌ 不定义具体的执行命令逻辑（由 Sandbox 类定义）
- ❌ 不处理工具安全审查（由 SandboxAuditMiddleware 完成）
- ❌ 不处理认证授权（由更上层完成）

### 约束

1. **Singleton 模式**：`_default_sandbox_provider` 全局唯一
2. **Per-Thread 隔离**：同一个 thread_id 始终返回同一个 sandbox
3. **Cleanup 必须成功**：release() 失败会导致资源泄漏
4. **ID 前缀约定**：`"local:xxx"`, `"docker:yyy"`, `"k8s:zzz"` 严格遵守

### 失败模式 & 预防

| 失败模式 | 症状 | 预防 |
|---------|------|------|
| **创建失败** | acquire() 返回失败 | ✅ 在 ThreadDataMiddleware 中提前检查 |
| **资源泄漏** | release() 未被调用 | ✅ try-finally 或 context manager |
| **错误隔离** | local 模式下，任意 thread 可访问其他 thread 的文件 | ✅ thread_id → 独立的 workspace_path |
| **配置错误** | use 字段不存在 | ✅ resolve_class 会抛异常 |

### 可迁移做法

如果你要实现自己的隔离执行系统：

1. **用 Strategy Pattern 支持多实现**
   ```python
   # ❌ 硬编码选择
   if environment == "docker":
       exec = DockerExecutor()
   elif environment == "k8s":
       exec = K8sExecutor()
   
   # ✅ 通过接口多态
   class Executor(ABC):
       def execute(self): pass
   
   executor = create_executor(config.engine_type)  # 动态选择
   ```

2. **用 Singleton + Factory 管理实例
   ```python
   _provider = None
   
   def get_provider():
       global _provider
       if _provider is None:
           _provider = create_provider_from_config()
       return _provider
   ```

3. **Per-Resource 命名空间**
   ```python
   # ✅ 用前缀区分不同的隔离级别
   sandbox_id = f"{provider_type}:{unique_id}"
   # "local:tmp_xxx", "docker:container_xxx", "k8s:pod_xxx"
   ```

4. **三阶段生命周期管理**
   ```python
   # ✅ acquire, get, release 清晰分离
   sandbox = provider.acquire()        # 分配资源
   result = provider.get(id).execute() # 使用资源
   provider.release(id)                # 释放资源
   ```

### 我准备做的实验

[ ] Phase 8+ 中，实现 LocalSandboxProvider 的最小版本
[ ] 对比三种隔离级别的 security model
[ ] 测试 acquire/release 的完整生命周期

### 还有哪些待验证问题

- [ ] 多个 thread 的沙箱是否真的独立，还是共享了什么？
- [ ] resolve_class 如何处理不存在的类？
- [ ] 在 release 时，是否有 "graceful shutdown" 的机制？

---

✅ **Phase 3 部分完成**（前 3 个模块）

接下来还有 2 个关键模块会继续深度分析：
- **模块 4️⃣：Skills 生态系统** - 能力如何注册和使用
- **模块 5️⃣：Subagent 执行模型** - 后台执行的系统设计

由于篇幅限制，这两个模块将在单独的文件中完成。
