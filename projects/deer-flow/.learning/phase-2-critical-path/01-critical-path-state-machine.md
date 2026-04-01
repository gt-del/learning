# Phase 2：关键路径 & 状态机

## 🎯 一句话总结

**DeerFlow 的关键路径不是传统的"request → controller → business logic → database"，而是"input → LangGraph agent loop → middleware pipeline → tool execution → state update → stream output"，其中 middleware chain 构成了整个质量控制系统。**

---

## 📊 完整的状态转移图（Critical Path）

```
┌───────────────────────────────────────────────────────────────────────────┐
│ PHASE 0: 请求入场                                                         │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Input Source:                                                           │
│  ├─ HTTP Request (via FastAPI Gateway)                                  │
│  ├─ Embedded Client (Python SDK)                                        │
│  └─ IM Platform (Slack, Telegram, Lark)                                 │
│                                                                           │
│  State: ThreadState = {}（空）                                            │
│                                                                           │
└────────┬──────────────────────────────────────────────────────────────────┘
         │
┌────────▼──────────────────────────────────────────────────────────────────┐
│ PHASE 1: 初始化 & 沙箱获取                                                 │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  State Init:                                                              │
│  ├─ thread_id（从请求或生成）                                             │
│  ├─ ThreadState.messages = [ HumanMessage(content=user_input) ]          │
│  ├─ ThreadState.thread_data = {}                                         │
│  ├─ ThreadState.artifacts = []                                           │
│  └─ ThreadState.sandbox_id = ？（待获取）                                  │
│                                                                            │
│  Sandbox Acquisition:                                                     │
│  └─ SandboxProvider.acquire(thread_id)                                   │
│     └─ ThreadState.sandbox_id = new_id                                   │
│                                                                            │
│  Quality Entry Point: ⚠️ 如果这里失败，整个任务无法运行                    │
│                                                                            │
└────────┬──────────────────────────────────────────────────────────────────┘
         │
┌────────▼─────────────────────────────────────────────────────────────────┐
│ PHASE 2a: Lead Agent 第一次推理                                          │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Input: ThreadState + messages + sandbox_id                              │
│                                                                            │
│  Model Call:                                                              │
│  ├─ system_prompt = apply_prompt_template(...)                           │
│  │   ├─ 在提示词中列出所有可用 skills（manifest.name）                     │
│  │   ├─ 列出所有可用 tools（builtin + MCP）                              │
│  │   ├─ 列出所有 subagents（如果启用）                                    │
│  │   └─ 设置角色和行为指南                                                │
│  ├─ model = create_chat_model(thinking_enabled, reasoning_effort)       │
│  ├─ tools = get_available_tools(model_name, group_filter, ...)          │
│  └─ run_agent(state, tools, model, system_prompt)                       │
│                                                                            │
│  Output: AIMessage(content=text, tool_calls=[...])                        │
│  New State: ThreadState.messages += [ AIMessage(...) ]                   │
│                                                                            │
│  ⚠️ First Gate: 模型是否有效？工具列表是否正确注入？                      │
│                                                                            │
└────────┬──────────────────────────────────────────────────────────────────┘
         │
┌────────▼──────────────────────────────────────────────────────────────────┐
│ PHASE 2b: MIDDLEWARE PIPELINE（质量流水线 — 最核心的控制点）               │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  【所有 middleware 在模型推理之后、工具执行之前运行】                      │
│                                                                           │
│  所有 middleware 共享：                                                   │
│  ├─ Input State: 包含最新的 AIMessage（with tool_calls）                │
│  ├─ Output State: 可修改 state、拦截 tool_calls、注入消息                 │
│  └─ after_model() vs aafter_model(): 同步 vs 异步处理                   │
│                                                                           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  Layer 1: ThreadDataMiddleware                                           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  职责: 初始化 thread_data（workspace_path, uploads_path）                │
│  依赖: ✓ 必须第一个（其他 middleware 用 thread_id）                      │
│  Gate: ❌ thread_id 无法解析 → 后续都无法继续                             │
│  修改: ThreadState.thread_data                                           │
│  风险预防: 阻止 "没有工作目录" 的情形                                     │
│                                                                           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  Layer 2: UploadsMiddleware                                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  职责: 处理用户文件上传（验证、移动、记录）                                │
│  依赖: ✓ 在 ThreadDataMiddleware 之后（需要 thread_id）                  │
│  Gate: ❌ 上传文件超过 size limit                                         │
│        ❌ 文件格式不被允许                                                 │
│  修改: ThreadState.uploaded_files 和 messages                            │
│  风险预防: 阻止 "恶意大文件" 和 "可执行程序上传"                          │
│                                                                           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  Layer 3: DanglingToolCallMiddleware                                    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  职责: 补全缺失的 ToolMessage（LangGraph bug workaround）                 │
│  为什么?: 模型生成 tool_calls 但上一轮没有对应的 ToolMessage                │
│  修改: ThreadState.messages（补充 ToolMessages）                         │
│  风险预防: 阻止 "消息历史不一致" 导致模型困惑                             │
│                                                                           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  Layer 4: SummarizationMiddleware ⚡ (optional, Langchain built-in)      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  职责: 当消息或 token 超过阈值时，自动摘要历史                             │
│  条件: config.summarization.enabled = true                               │
│  修改: ThreadState.messages（用 summary message 压缩历史）                │
│  风险预防: 阻止 "context window 溢出"                                     │
│                                                                           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  Layer 5: TodoMiddleware (conditional, plan_mode)                        │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  职责: 让 agent 能够创建和管理 todo 列表                                   │
│  条件: config.is_plan_mode = true                                        │
│  修改: ThreadState.todos                                                 │
│  风险预防: 防止复杂多步任务中"丢失进度"                                   │
│                                                                           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  Layer 6: TokenUsageMiddleware (conditional)                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  职责: 记录每次模型调用的 token 成本                                      │
│  条件: config.token_usage.enabled = true                                 │
│  修改: 无（只是日志）                                                     │
│  风险预防: 防止 "控制不住成本"                                            │
│                                                                           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  Layer 7: TitleMiddleware                                                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  职责: 在第一次交互后生成对话标题                                         │
│  条件: (first user message already exchanged) && !title                  │
│  流程:                                                                   │
│    1. 检查是否应该生成（只在 first turn）                               │
│    2. 提取用户信息和助手回复                                             │
│    3. 调用模型生成标题（lightweight model）                              │
│    4. 存储到 ThreadState.title                                           │
│  修改: ThreadState.title                                                │
│  风险预防: 用户看不到对话的"名字"                                        │
│                                                                           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  Layer 8: MemoryMiddleware （在 TitleMiddleware 之后！）                 │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  职责: 将对话入队到异步内存处理系统                                       │
│  依赖: ✓ 在 TitleMiddleware 之后（需要 title）                          │
│  流程:                                                                   │
│    1. 过滤消息（移除 tool message 和中间步骤）                          │
│    2. 移除 <uploaded_files> 块（session-scoped）                        │
│    3. 入队到 MemoryQueue（异步处理）                                    │
│    4. 后台线程维护 embedding + persistence                              │
│  修改: 无（MemoryQueue 是独立的）                                        │
│  风险预防: 防止"用户数据没有被保存"                                       │
│                                                                           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  Layer 9: ViewImageMiddleware (conditional, vision support)             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  职责: 诱导模型查看已上传的图像（通过 view_image tool）                   │
│  条件: model_config.supports_vision = true                               │
│  流程:                                                                   │
│    1. 检测消息中是否有图像引用                                           │
│    2. 如果有，自动调用 view_image 工具以最小化 token 使用               │
│  修改: ThreadState.viewed_images 和 messages                             │
│  风险预防: 防止"模型看到图像引用但不知道内容"                             │
│                                                                           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  Layer 10: DeferredToolFilterMiddleware (conditional)                    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  职责: 隐藏工具搜索工具（不让模型调用 tool_search）                        │
│  条件: config.tool_search.enabled = true                                 │
│  修改: 模型的工具绑定（移除搜索工具）                                     │
│  风险预防: 防止 "模型浪费 token 搜索工具"                                 │
│                                                                           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  Layer 11: SubagentLimitMiddleware (conditional)                         │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  职责: 限制单个模型响应中的并发 subagent 任务                              │
│  条件: subagent_enabled = true                                           │
│  动作:                                                                   │
│    1. 数一下 tool_calls 中有多少 "task" 调用                            │
│    2. 如果 > max_concurrent（默认 3），删除超过的调用                    │
│    3. 记录警告日志                                                       │
│  修改: AIMessage.tool_calls（truncate）                                  │
│  风险预防: 防止 "资源耗尽" 和 "后台任务爆炸"                             │
│                                                                           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  Layer 12: LoopDetectionMiddleware                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  职责: 检测和破坏重复的工具调用循环                                       │
│  算法:                                                                   │
│    1. Hash 当前的 tool_calls（name + args）                             │
│    2. 追踪最近 N 个 hash（滑动窗口）                                     │
│    3. 相同 hash 出现 3 次 → 注入警告消息                                 │
│    4. 相同 hash 出现 5 次 → 删除所有 tool_calls，强制生成文本答案        │
│  修改: ThreadState.messages（注入警告）或 tool_calls（强制停止）         │
│  风险预防: 防止 "无限循环"                                               │
│                                                                           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  Layer 13: SandboxAuditMiddleware                                        │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  职责: 审计 bash 命令的安全性                                             │
│  分类:                                                                   │
│    - HIGH_RISK (block): rm -rf /, curl|sh, dd, cat /etc/shadow         │
│    - MEDIUM_RISK (warn): chmod 777, pip install                         │
│    - SAFE (pass): 其他                                                   │
│  修改: 拦截 tool call 或在结果中添加警告                                 │
│  风险预防: 阻止 "destructive 命令" 和 "不安全操作"                       │
│                                                                           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  Layer 14: ToolErrorHandlingMiddleware                                  │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  职责: 将工具执行异常转为 ToolMessage                                     │
│  流程:                                                                   │
│    1. 捕获工具执行中的异常                                               │
│    2. 转为 ToolMessage(type="error", content=error_text)                │
│    3. 加入 ThreadState.messages（让模型看到）                            │
│  修改: ThreadState.messages（补充 error ToolMessages）                   │
│  风险预防: 防止 "异常导致整个任务失败"，让模型能修复错误                 │
│                                                                           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  Layer 15: ClarificationMiddleware ⭐ (ALWAYS LAST)                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  职责: 拦截澄清请求（ask_clarification tool）并暂停执行                 │
│  依赖: ✓ 必须最后一个（所有其他 middleware 已完成）                      │
│  动作:                                                                   │
│    1. 检测 ask_clarification tool call                                   │
│    2. 格式化问题（emoji, options）                                      │
│    3. 返回 Command(goto=END, update={})（中止执行）                     │
│    4. 等待用户响应                                                       │
│  修改: 不修改 state，但中止流程                                          │
│  风险预防: 防止 "模型瞎猜关键决定"                                       │
│                                                                           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  🔴 QUALITY GATES 总结                                                    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│                                                                            │
│  [阶段]              [质量门禁]            [放行条件]       [拒绝后果]      │
│  ────────────────────────────────────────────────────────────────────    │
│  1. ThreadData      thread_id resolve    ✓ 成功          ❌ task fails   │
│  2. Uploads         file size/format     ✓ 符合规则       ❌ task fails   │
│  3. DanglingCall   message consistency   ✓ 一致           ⚠️ 日志         │
│  4. Summarization  context length       ✓ 压缩成功       ⚠️ 日志         │
│  5. Title          first exchange?      ✓ 生成           ⚠️ skip        │
│  6. Memory         queue?               ✓ 入队           ⚠️ skip async  │
│  7. ViewImage      vision support?      ✓ 调用           ⚠️ skip        │
│  8. LoopDetection  same hash count      🟨 3x→warn      🟥 5x→block    │
│  9. SandboxAudit   bash command         🟨 medium warn   🟥 high→block  │
│  10. ClarifyUser   ask_clarification?   🟥 中断执行      ⏸️ await input│
│                                                                            │
└────────┬───────────────────────────────────────────────────────────────┘
         │
         │ 【注意】: 如果任何 hard gate 失败，任务立即终止
         │ 【如果】: 如果 warn gate 触发，记录但继续
         │
┌────────▼──────────────────────────────────────────────────────────────┐
│ PHASE 3: 工具执行（Tool Execution）                                   │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  Conditional: 如果模型没有生成 tool_calls                             │
│  └─ 跳过工具执行，直接进入 PHASE 4                                    │
│                                                                        │
│  For each tool_call in AIMessage.tool_calls:                          │
│  ├─ Tool Type: "bash", "read_file", "write_file", "str_replace"     │
│  │  └─ Execute via SandboxProvider (thread_id → sandbox_id)         │
│  │                                                                    │
│  ├─ Tool Type: "task" (subagent)                                   │
│  │  ├─ 如果 async: SubagentExecutor.execute_async()                 │
│  │  │  └─ 返回 task_id（非阻塞）                                    │
│  │  └─ 如果 sync: SubagentExecutor.execute()                        │
│  │     └─ 等待结果（阻塞）                                          │
│  │                                                                   │
│  ├─ Tool Type: skill 工具                                            │
│  │  └─ 调用对应的 skill endpoint                                    │
│  │                                                                   │
│  └─ Tool Type: builtin                                              │
│     ├─ present_files: 列出文件并添加到 artifacts                    │
│     ├─ ask_clarification: → 由 ClarificationMiddleware 处理          │
│     └─ view_image: 读取 base64 + 返回图像信息                       │
│                                                                        │
│  Collect Results:                                                     │
│  └─ ToolMessage(tool_use_id=..., content=result)                    │
│                                                                        │
│  State Update:                                                        │
│  └─ ThreadState.messages += [ ToolMessage(...) ]                    │
│                                                                        │
└────────┬──────────────────────────────────────────────────────────────┘
         │
┌────────▼──────────────────────────────────────────────────────────────┐
│ PHASE 4: 迭代判断 & 循环控制                                          │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  Agent Loop Condition:                                                │
│  ├─ 如果最后一条消息是 ToolMessage                                     │
│  │  └─ 继续：回到 PHASE 2a（再次调用模型）                            │
│  │                                                                    │
│  └─ 如果最后一条消息是 AIMessage（text only，不含 tool_calls）        │
│     └─ 终止：进入 PHASE 5                                            │
│                                                                        │
│  迭代上限:                                                             │
│  ├─ max_iterations（通常由 LangGraph 自动管理）                       │
│  ├─ subagent 的 max_turns（SubagentConfig.max_turns）                │
│  └─ Timeout（CancellationToken / asyncio.CancelledError）           │
│                                                                        │
└────────┬──────────────────────────────────────────────────────────────┘
         │
┌────────▼──────────────────────────────────────────────────────────────┐
│ PHASE 5: 清理与输出（Cleanup & Output）                               │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  Final State:                                                         │
│  ├─ ThreadState.messages（完整对话列表）                              │
│  ├─ ThreadState.artifacts（所有生成物路径）                           │
│  ├─ ThreadState.title（已生成）                                       │
│  ├─ ThreadState.viewed_images（已处理的图像）                         │
│  └─ ThreadState.sandbox_id（即将被 release）                         │
│                                                                        │
│  Cleanup:                                                             │
│  ├─ SandboxMiddleware.release(sandbox_id)                            │
│  │  └─ 删除临时文件/容器/pod                                         │
│  │                                                                    │
│  ├─ MemoryMiddleware.flush()                                         │
│  │  └─ 等待队列中的记忆处理完成                                      │
│  │                                                                    │
│  └─ Clear viewed_images（清空缓存）                                  │
│                                                                        │
│  Stream Output:                                                       │
│  ├─ HTTP: 返回 JSON 响应(status, messages, artifacts)               │
│  ├─ WebSocket: 流式发送 final state                                 │
│  └─ IM: 转发消息到 Slack/Telegram                                   │
│                                                                        │
│  Observability:                                                       │
│  ├─ LangSmith trace 标记 (metadata)                                  │
│  ├─ 日志输出编排过程                                                  │
│  └─ 统计 token, 成本, 耗时                                           │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 关键状态转移细节

### ThreadState 生命周期

```
初始: {}

初始化后:
├─ messages = [ HumanMessage(content=user_input) ]
├─ sandbox = { sandbox_id: "local:xxx" }
├─ thread_data = { workspace_path: "/tmp/xxx", ... }
├─ title = None
├─ artifacts = []
├─ todos = None
├─ uploaded_files = None
└─ viewed_images = {}

第 1 轮模型推理后:
├─ messages += [ AIMessage(content=..., tool_calls=[...]) ]
├─ title = "生成的标题" (by TitleMiddleware)
├─ viewed_images = {"img1": {"base64": "...", "mime_type": "..."}}
└─ (artifacts 还是空的)

工具执行后:
├─ messages += [ ToolMessage(tool_use_id=..., content=result) ]
├─ artifacts = ["/tmp/xxx/file1.txt", "/tmp/xxx/file2.pdf"]
└─ (状态继续积累)

最终:
├─ messages = 完整对话记录（human + ai + tool messages）
├─ artifacts = 所有生成物
├─ title = "最终标题"
├─ todos = [ {id: 1, title: "task1", status: "completed"}, ... ]
└─ viewed_images = {} (被清空了)
```

---

## ⚖️ 为什么要这样分阶段

| 阶段 | 设计 | 目的 | 代价 |
|------|------|------|------|
| **初始化** | 先获取沙箱 | 尽早发现不可逆的环境错误 | 额外的 I/O |
| **模型推理** | 一次性推理 | LLM 在充分信息下决策 | token 成本 |
| **Middleware 链** | 15 层显式处理 | 质量控制和风险隔离 | 代码复杂度 ↑ |
| **工具执行** | 仅在确认安全后 | 执行前已过多个检查点 | 延迟 |
| **循环判断** | 显式的状态检查 | 避免隐式的"永不停止" | 逻辑额外 |
| **清理** | 集中管理 | 资源不泄漏，可审计 | cleanup 延迟 |

---

## 🛡️ 质量门禁映射表

| 门禁号 | Middleware | 防止的失败模式 | 激活条件 | 响应 |
|-------|-----------|---------------|---------|------|
| **Gate 1** | ThreadData | 没有工作目录 | thread_id 无法解析 | ❌ HARD FAIL |
| **Gate 2** | Uploads | 恶意文件上传 | file size > limit | ❌ HARD FAIL |
| **Gate 3** | DanglingCall | 消息历史不一致 | 缺失 ToolMessage | ⚠️ warn & fix |
| **Gate 4** | Summarization | Context 溢出 | messages+tokens > limit | ⚠️ compress |
| **Gate 5** | Title | 用户体验差 | first exchange | ℹ️ generate |
| **Gate 6** | Memory | 不保存用户数据 | enabled=true | ℹ️ async queue |
| **Gate 7** | ViewImage | 图像内容未传达 | vision model & has images | ℹ️ call tool |
| **Gate 8** | LoopDetection | 无限循环 | same hash 3x | 🟨 warn; 5x | 🟥 block |
| **Gate 9** | SandboxAudit | 安全漏洞 | high-risk cmd | 🟥 BLOCK |
| **Gate 10** | ToolErrorHandling | 异常导致失败 | tool exception | ⚠️ convert & retry |
| **Gate 11** | Clarification | 模型瞎猜 | ask_clarification | 🟥 INTERRUPT |

---

## 🔑 Middleware 执行顺序的正确性证明

**为什么 ClarificationMiddleware 必须最后？**
- 如果提前，会发现并拦截 clarification，但其他 middleware（如 loopDetection）还没有运行
- 可能导致循环被忽略而 clarification 被推送给用户

**为什么 MemoryMiddleware 必须在 TitleMiddleware 之后？**
- TitleMiddleware 生成 title（可能是内存保存的关键字段）
- MemoryMiddleware 需要这个 title 作为对话的一部分

**为什么 LoopDetectionMiddleware 在 SandboxAuditMiddleware 之前？**
- 如果顺序反过来，危险命令可能先通过但然后被检测为循环
- 现在的顺序保证：先检查循环（stop if looping），再审计命令（block if dangerous）

---

## 🎓 关键洞察

**① 显式 Pipeline 强制思考**
- 不能随意添加 middleware，必须声明在哪一层
- 代码注释强制变成文档（"ThreadData 必须第一个"）

**② 错误分类很重要**
- HARD FAIL（❌）：任务不能继续
- WARN（🟨）：记录但继续
- INFO（ℹ️）：静默处理

**③ 状态是线程隔离的**
- ThreadState 是对标准状态管理的突破（分布式系统常用）
- 每个 thread_id 对应独立的 state 机器

**④ Middleware 可以规范模型行为**
- 不是提示词调整，而是在模型输出后直接修改
- LoopDetectionMiddleware 强制停止比提示词更可靠

---

## 📚 模板：添加新 Middleware 的清单

如果你要添加新的 middleware：

1. **定义职责**：这个 middleware 要做什么？
2. **定义位置**：应该在哪一层？
3. **定义依赖**：需要哪些前置 middleware 已经运行？
4. **定义修改**：哪些 ThreadState 字段会被修改？
5. **定义门禁**：这是 hard fail 还是 warn？
6. **编写代码**：implement `after_model()` / `aafter_model()`
7. **添加到 _build_middlewares()**：在正确的位置加入链
8. **编写测试**：测试正常情况和边界情况

---

✅ **Phase 2 完成**。

**现在的理解**：
- ✅ 15 个 middleware 各自的职责
- ✅ 它们之间的依赖关系
- ✅ 每个质量门禁防止什么失败
- ✅ 为什么要这样分阶段

**进入 Phase 3 时**，会对关键 modules 进行深度剖析。
