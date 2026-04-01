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
