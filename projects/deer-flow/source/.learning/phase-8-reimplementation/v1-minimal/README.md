# V1: Minimal Implementation

## 🎯 目标

展示 DeerFlow 的**核心概念**：

1. **ThreadState** - 中央状态管理
2. **Agent Loop** - 状态机执行
3. **Tool Execution** - 工具调用

## 🔧 运行方式

### 方式 1: 查看输出

```bash
cd v1-minimal
python core.py
```

输出内容如下：
```
========================================================================
DeerFlow V1: Minimal Implementation Demo
========================================================================

[TEST 1] Simple Search
🚀 Starting agent (thread-001)

--- Iteration 1 ---
⚙️  [THINKING] Model is reasoning...
   Thought: User is asking about Python. I should search for information.
🔧 [TOOL_CALLING] Calling 1 tool(s)...
   Calling: search({'query': 'python'})
   Result: Python is a high-level programming language.
💬 [RESPONDING] Generating response...
   Response: Based on my search, here's what I found: Python is a h...

✅ Agent done (1 iterations)

Final output:
Based on my search, here's what I found: Python is a high-level programming language.
```

### 方式 2: 运行测试

```bash
pytest test.py -v
```

## 📊 代码结构

```
V1/
├── core.py         # 核心实现（250行）
│   ├── Enums
│   ├── Data Models (ThreadState, etc.)
│   ├── Tools
│   ├── Agent Loop
│   └── Main Demo
│
└── test.py         # 单元测试（~100行）
    ├── ThreadState Tests
    ├── Tool Tests
    └── Agent Tests
```

## 🧠 核心概念讲解

### 1️⃣ ThreadState（中央状态）

ThreadState 是这个系统中**唯一的全局状态**。所有的数据都存在这里：

```python
state = ThreadState(thread_id="thread-001")

# 所有组件都通过修改 state 来通信
state.add_message("user", "What is Python?")
state.pending_tool_calls = [ToolCall(...)]
state.tool_results = [ToolResult(...)]
state.current_state = AgentState.DONE
```

**为什么这样设计？**
- 避免全局变量污染
- 易于并发（对每个 thread 独立）
- 易于调试（看 state 就知道发生了什么）
- 易于保存/恢复（state 是可序列化的）

### 2️⃣ Agent Loop（状态机）

Agent 的执行是一个**显式的状态机**：

```
INIT 
  ↓
THINKING (模型推理)
  ↓
TOOL_CALLING (如果需要)
  ↓
RESPONDING (模型回复)
  ↓
DONE

每一步都是**显式**的，可以追踪和调试。
```

**为什么这样设计？**
- vs. 隐含的流程（if-else 分支）：显式更清晰
- vs. REST 请求-响应：支持多轮交互
- vs. Function call 链：结构清晰，易于理解

### 3️⃣ Tool Execution（工具执行）

```python
tool_call = ToolCall(tool_name="search", arguments={"query": "python"})
result = execute_tool(tool_call)
```

**为什么分离？**
- ToolCall 和 ToolResult 是**数据**，可独立处理
- execute_tool 是**执行逻辑**，可以在不同的环境运行（本地/沙箱/容器）
- 易于审计（记录所有工具调用）

## 📚 继续学习

完成 V1 后，应该理解：
- 什么是 ThreadState
- 什么是状态机
- 为什么要分离数据和逻辑

下一步（V2）会加入：
- ✨ Middleware 系统
- ✨ Quality gates
- ✨ Error handling

## 💡 练习题

1. **修改模型推理**：在 `mock_model_reasoning` 中添加新的规则
2. **添加新工具**：在 TOOLS 中添加一个新的工具函数
3. **改变状态机**：添加新的 AgentState 类型
4. **测试驱动**：写一个测试，然后实现功能

## 🎯 重要洞察

> DeerFlow 的设计哲学：**显式优于隐含**
> 
> 这个 V1 演示了最简单的"显式"：
> - 状态显式（ThreadState）
> - 流程显式（Agent Loop）
> - 工具显式（ToolCall + ToolResult）

---

### 下一步

看 [../v2-middleware/](../v2-middleware/) 了解如何添加 Middleware 系统。
