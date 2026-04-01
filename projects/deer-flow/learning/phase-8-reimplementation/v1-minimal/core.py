# Phase 8：最小重实现（第 1 版 - 最小可运行）

## 🎯 V1 的目标

创建**最小的可运行的 agent 系统**，演示：
1. ThreadState（中央状态）
2. LeadAgent loop（状态机）
3. 单个工具调用

**不包括**：Middleware, Sandbox, Memory...

---

## 🔨 V1: core.py - 最小系统

```python
"""
DeerFlow V1: 最小可运行的 Agent

演示核心概念：
- ThreadState: 中央状态
- Agent Loop: 状态机
- Tool Execution: 最简单的工具调用
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Any, Literal

# ============================================================================
# 1. Constants
# ============================================================================

SYSTEM_PROMPT = """You are a helpful assistant. When the user asks you to do something:
1. Think about what tools you might need
2. Call the appropriate tool
3. Process the result
4. Return the answer to the user

Available tools:
- search(query): Search for information
- calculate(expression): Calculate a math expression
"""

# ============================================================================
# 2. Enums
# ============================================================================

class AgentState(Enum):
    """Agent 的执行状态"""
    INIT = "init"              # 初始化
    THINKING = "thinking"      # 思考/推理
    TOOL_CALLING = "tool_calling"  # 调用工具
    RESPONDING = "responding"  # 生成回复
    DONE = "done"              # 完成


# ============================================================================
# 3. Data Models
# ============================================================================

@dataclass
class ToolCall:
    """工具调用表示"""
    tool_name: str
    arguments: dict[str, Any]
    
    def __repr__(self):
        return f"ToolCall({self.tool_name}, {self.arguments})"


@dataclass
class ToolResult:
    """工具执行结果"""
    tool_name: str
    result: Any
    error: Optional[str] = None
    
    def __repr__(self):
        if self.error:
            return f"ToolResult({self.tool_name}, ERROR: {self.error})"
        return f"ToolResult({self.tool_name}, {self.result})"


@dataclass
class Message:
    """对话消息"""
    role: Literal["user", "assistant", "tool"]
    content: str
    
    def __repr__(self):
        prefix = f"[{self.role.upper()}] "
        return prefix + self.content[:100]


@dataclass
class ThreadState:
    """
    中央状态（核心概念 #1）
    
    所有执行过程中的信息都存在这里。
    Agent loop 通过修改这个 state 来通信。
    """
    # 基本信息
    thread_id: str
    current_state: AgentState = AgentState.INIT
    
    # 对话历史
    messages: list[Message] = field(default_factory=list)
    
    # 工具相关
    pending_tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    
    # 执行计数
    iterations: int = 0
    max_iterations: int = 10
    
    # 最终结果
    final_response: Optional[str] = None
    
    def add_message(self, role: str, content: str):
        """添加一条消息到历史"""
        self.messages.append(Message(role, content))
    
    def is_done(self) -> bool:
        """检查是否完成"""
        return self.current_state == AgentState.DONE or self.iterations >= self.max_iterations
    
    def __repr__(self):
        return (
            f"ThreadState("
            f"thread_id={self.thread_id}, "
            f"state={self.current_state.value}, "
            f"messages={len(self.messages)}, "
            f"iterations={self.iterations}"
            f")"
        )


# ============================================================================
# 4. Tools
# ============================================================================

def search(query: str) -> str:
    """简单的搜索工具"""
    # 这是 mock，真实系统会调用真实的搜索引擎
    results = {
        "python": "Python is a high-level programming language.",
        "json": "JSON is a lightweight data format.",
        "agent": "An AI agent is an autonomous system that takes actions.",
        "langraph": "LangGraph is a framework for building agent systems.",
    }
    return results.get(query.lower(), f"No results for '{query}'")


def calculate(expression: str) -> str:
    """简单的计算工具"""
    try:
        result = eval(expression)
        return f"Result: {result}"
    except Exception as e:
        return f"Error: {e}"


# 工具注册表
TOOLS: dict[str, Callable] = {
    "search": search,
    "calculate": calculate,
}


def execute_tool(tool_call: ToolCall) -> ToolResult:
    """
    执行工具（模拟 Executor 角色）
    """
    tool_name = tool_call.tool_name
    args = tool_call.arguments
    
    if tool_name not in TOOLS:
        return ToolResult(
            tool_name=tool_name,
            result=None,
            error=f"Unknown tool: {tool_name}"
        )
    
    try:
        tool_func = TOOLS[tool_name]
        result = tool_func(**args)
        return ToolResult(tool_name=tool_name, result=result)
    except Exception as e:
        return ToolResult(tool_name=tool_name, result=None, error=str(e))


# ============================================================================
# 5. Mock Model / Reasoning（简化版本）
# ============================================================================

def mock_model_reasoning(state: ThreadState) -> tuple[str, list[ToolCall]]:
    """
    模拟 LLM 的推理过程
    返回：(thought, tool_calls)
    """
    # 这是 mock，真实系统会调用真实的 LLM
    
    user_message = state.messages[-1].content if state.messages else ""
    
    # 简单的规则
    if "python" in user_message.lower() or "search" in user_message.lower():
        return (
            "User is asking about Python. I should search for information.",
            [ToolCall(tool_name="search", arguments={"query": "python"})]
        )
    elif any(op in user_message for op in ["+", "-", "*", "/"]):
        # 提取表达式
        expr = user_message.split()[-1]
        return (
            f"User wants to calculate {expr}",
            [ToolCall(tool_name="calculate", arguments={"expression": expr})]
        )
    else:
        return (
            "I can directly answer this question.",
            []
        )


def mock_model_respond(state: ThreadState) -> str:
    """
    模拟 LLM 的回复生成
    """
    # 收集最后的工具结果
    if state.tool_results:
        last_result = state.tool_results[-1]
        if last_result.error:
            return f"I encountered an error: {last_result.error}"
        else:
            return f"Based on my search, here's what I found: {last_result.result}"
    
    # 如果没有工具调用，就直接回复
    user_message = state.messages[-1].content if state.messages else ""
    return f"You said: {user_message}. I'm here to help!"


# ============================================================================
# 6. Agent Loop（核心概念 #2 - 状态机）
# ============================================================================

class SimpleAgent:
    """
    最小的 Agent 实现
    
    流程：
    1. 初始化 ThreadState
    2. Loop:
       a. Thinking: 用模型推理下一步干什么
       b. Tool Calling: 如果需要，调用工具
       c. Responding: 生成回复
       d. 检查是否完成 or 循环
    """
    
    def __init__(self, thread_id: str, max_iterations: int = 10, verbose: bool = True):
        self.thread_id = thread_id
        self.max_iterations = max_iterations
        self.verbose = verbose
    
    def _log(self, msg: str):
        """调试日志"""
        if self.verbose:
            print(msg)
    
    def run(self, user_input: str) -> str:
        """运行 agent"""
        # 初始化
        state = ThreadState(
            thread_id=self.thread_id,
            max_iterations=self.max_iterations,
        )
        state.add_message("user", user_input)
        state.current_state = AgentState.THINKING
        
        self._log(f"🚀 Starting agent ({state.thread_id})")
        
        # Main loop
        while not state.is_done():
            state.iterations += 1
            self._log(f"\n--- Iteration {state.iterations} ---")
            
            # Phase 1: Thinking
            self._log("⚙️  [THINKING] Model is reasoning...")
            thought, tool_calls = mock_model_reasoning(state)
            self._log(f"   Thought: {thought}")
            state.current_state = AgentState.THINKING
            
            # Phase 2: Tool Calling
            if tool_calls:
                self._log(f"🔧 [TOOL_CALLING] Calling {len(tool_calls)} tool(s)...")
                state.current_state = AgentState.TOOL_CALLING
                state.pending_tool_calls = tool_calls
                
                for tool_call in tool_calls:
                    self._log(f"   Calling: {tool_call.tool_name}({tool_call.arguments})")
                    result = execute_tool(tool_call)
                    state.tool_results.append(result)
                    self._log(f"   Result: {result.result if not result.error else 'ERROR'}")
                    
                    # 继续思考（在真实系统中，这会进入新的对话轮次）
            
            # Phase 3: Responding
            self._log("💬 [RESPONDING] Generating response...")
            state.current_state = AgentState.RESPONDING
            response = mock_model_respond(state)
            state.add_message("assistant", response)
            self._log(f"   Response: {response[:100]}...")
            
            # Phase 4: Check done
            if not tool_calls or len(state.tool_results) > 0:
                # 如果没有工具调用，或已经有结果，就完成
                state.current_state = AgentState.DONE
                state.final_response = response
                break
        
        self._log(f"\n✅ Agent done ({state.iterations} iterations)")
        return state.final_response or "No response generated"


# ============================================================================
# 7. Main - 演示
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("DeerFlow V1: Minimal Implementation Demo")
    print("=" * 70)
    
    agent = SimpleAgent(thread_id="thread-001", verbose=True)
    
    # Test 1: Simple question
    print("\n\n[TEST 1] Simple Search")
    result = agent.run("Tell me about Python")
    print(f"\nFinal output:\n{result}")
    
    # Test 2: Calculation
    print("\n\n[TEST 2] Calculation")
    agent2 = SimpleAgent(thread_id="thread-002", verbose=True)
    result = agent2.run("What is 2 + 2 * 3?")
    print(f"\nFinal output:\n{result}")
    
    print("\n" + "=" * 70)
    print("Demo complete!")
    print("=" * 70)
```

---

## 🧪 V1: test.py - 单元测试

```python
"""
V1 的单元测试
"""

import pytest
from core import (
    ThreadState, AgentState, ToolCall, ToolResult, Message,
    execute_tool, search, calculate, SimpleAgent
)

# ============================================================================
# ThreadState 测试
# ============================================================================

def test_thread_state_creation():
    """测试 ThreadState 创建"""
    state = ThreadState(thread_id="test-001")
    assert state.thread_id == "test-001"
    assert state.current_state == AgentState.INIT
    assert len(state.messages) == 0
    assert state.iterations == 0


def test_thread_state_add_message():
    """测试添加消息"""
    state = ThreadState(thread_id="test-001")
    state.add_message("user", "Hello")
    assert len(state.messages) == 1
    assert state.messages[0].role == "user"
    assert state.messages[0].content == "Hello"


def test_thread_state_is_done():
    """测试完成检查"""
    state = ThreadState(thread_id="test-001", max_iterations=5)
    assert not state.is_done()
    
    state.iterations = 5
    assert state.is_done()
    
    state2 = ThreadState(thread_id="test-002")
    state2.current_state = AgentState.DONE
    assert state2.is_done()


# ============================================================================
# Tools 测试
# ============================================================================

def test_search_tool():
    """测试搜索工具"""
    result = search("python")
    assert "Python" in result or "python" in result
    
    result = search("unknown_query_12345")
    assert "No results" in result


def test_calculate_tool():
    """测试计算工具"""
    result = calculate("2 + 2")
    assert "4" in result
    
    result = calculate("10 * 5")
    assert "50" in result


def test_execute_tool_success():
    """测试工具执行成功"""
    tool_call = ToolCall(tool_name="search", arguments={"query": "python"})
    result = execute_tool(tool_call)
    assert result.tool_name == "search"
    assert not result.error
    assert result.result


def test_execute_tool_unknown():
    """测试调用未知工具"""
    tool_call = ToolCall(tool_name="unknown_tool", arguments={})
    result = execute_tool(tool_call)
    assert result.error
    assert "Unknown tool" in result.error


def test_execute_tool_error():
    """测试工具执行出错"""
    tool_call = ToolCall(tool_name="calculate", arguments={"expression": "1/"})
    result = execute_tool(tool_call)
    assert result.error


# ============================================================================
# Agent 测试
# ============================================================================

def test_agent_initialization():
    """测试 agent 初始化"""
    agent = SimpleAgent(thread_id="test-agent", verbose=False)
    assert agent.thread_id == "test-agent"
    assert agent.max_iterations == 10


def test_agent_run_simple():
    """测试 agent 简单运行"""
    agent = SimpleAgent(thread_id="test-001", verbose=False)
    result = agent.run("Tell me about python")
    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 0


def test_agent_run_calculation():
    """测试 agent 计算"""
    agent = SimpleAgent(thread_id="test-002", verbose=False)
    result = agent.run("What is 2 + 3")
    assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

## 📖 V1: README.md

```markdown
# V1: Minimal Implementation

## 🎯 目标

展示 DeerFlow 的**核心概念**：

1. **ThreadState** - 中央状态管理
2. **Agent Loop** - 状态机执行
3. **Tool Execution** - 工具调用

## 🔧 运行方式

### 方式 1: 查看输出

```bash
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
```

---

## 核心学到的

✅ **这个 V1 版本展示了**：
- ThreadState 使用
- 状态机设计
- 最小化的工具调用

❌ **没包括的**（V2/V3 中会加）：
- Middleware 系统
- 质量检查
- 错误处理
- 沙箱隔离
- 并发执行

---

✅ **Phase 8.1（V1）完成**

现在创建 V2 和完整的 Phase 8 文档...
