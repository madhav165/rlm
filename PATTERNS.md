# RLM Patterns Guide

This document describes the patterns developers and agents should follow when updating the RLM repository. It is organized as a tree of increasingly bigger concepts, from small component-level patterns to large architectural principles.

---

## Level 1: Component-Level Patterns (Single Functions/Classes)

### 1.1 LM Client Pattern
All language model clients must:
- Inherit from `BaseLM` in `rlm/clients/base_lm.py`
- Implement all four abstract methods: `completion()`, `acompletion()`, `get_usage_summary()`, `get_last_usage()`
- Track per-model usage (calls, input/output tokens, cost)
- Handle both string and message list prompts
- Register the client in `rlm/clients/__init__.py` under `BACKEND_TO_CLIENT_TYPE`
- Use `DEFAULT_TIMEOUT` (300s) as the default timeout parameter

```python
from rlm.clients.base_lm import BaseLM
from rlm.core.types import ModelUsageSummary, UsageSummary

class MyClient(BaseLM):
    def completion(self, prompt: str | list[dict[str, Any]]) -> str:
        # Handle both str and message list formats
        # Track usage with _track_cost()
        # Return response string

    def get_usage_summary(self) -> UsageSummary:
        # Return aggregated usage across all calls
```
### 1.2 Environment Pattern
All environment implementations must:
- Inherit from either `NonIsolatedEnv` or `IsolatedEnv` in `rlm/environments/base_env.py`
- Implement three abstract methods: `setup()`, `load_context()`, `execute_code()`
- Return `REPLResult` from `execute_code()`
- Provide `llm_query`, `llm_query_batched`, `rlm_query`, and `rlm_query_batched` in environment globals
- Implement `cleanup()` for resource management
- Restore reserved names (`llm_query`, `rlm_query`, `context`, `history`, `FINAL_VAR`, `SHOW_VARS`) after each execution
- Register the environment in `rlm/environments/__init__.py` under `ENV_TO_TYPE`

### 1.3 Reserved Names Protection
Never allow custom tools or user code to override these names:
- `llm_query`, `llm_query_batched` - Single LM completion functions
- `rlm_query`, `rlm_query_batched` - Recursive RLM call functions
- `FINAL_VAR`, `SHOW_VARS` - Built-in helper functions
- `context`, `history` - Input context and conversation history variables

Use `validate_custom_tools()` before injecting custom tools. Restore scaffold after each execution.

### 1.4 Safe Builtins Pattern
The `LocalREPL` uses `_SAFE_BUILTINS` to block dangerous operations:
- Block: `input`, `eval`, `exec`, `compile`, `globals`, `locals`
- Allow: Standard Python builtins (print, len, str, int, etc.)
- Custom builtins should be carefully audited before adding

### 1.5 Tool Info Parsing Pattern
Custom tools support two formats:
1. Plain value: `{"name": callable_or_value}`
2. With description: `{"name": {"tool": callable_or_value, "description": "..."}}`

Use `parse_tool_entry()` to convert entries to `ToolInfo` objects. Use `format_tools_for_prompt()` to generate prompt-friendly descriptions.

### 1.6 Usage Tracking Pattern
- `ModelUsageSummary`: Per-model tracking (calls, input_tokens, output_tokens, cost)
- `UsageSummary`: Aggregates across models via `model_usage_summaries` dict
- Use `to_dict()` / `from_dict()` for serialization
- Aggregate with `UsageSummary.total_cost`, `total_input_tokens`, `total_output_tokens` properties

### 1.7 Final Answer Detection Pattern
Supports two patterns in model output:
1. `FINAL(answer text)` - Direct final answer
2. `FINAL_VAR(variable_name)` - Returns value of an existing REPL variable

Use `find_final_answer()` in `rlm/utils/parsing.py`. Check REPL code blocks first via `block.result.final_answer`, then fall back to text parsing.

---

## Level 2: Module-Level Patterns

### 2.1 RLM Iteration Loop Pattern
Each completion call follows this loop:
```
for i in range(max_iterations):
    1. Check timeout
    2. Check compaction (summarize if near context limit)
    3. Build current_prompt = message_history + user_prompt
    4. Call _completion_turn() -> RLMIteration
    5. Check iteration limits (errors, budget, tokens)
    6. Detect final_answer (from code blocks or text)
    7. Store best partial answer
    8. Log iteration (if logger enabled)
    9. Format iteration and append to message_history
    10. If final_answer found, return RLMChatCompletion
```

### 2.2 Compaction Pattern
When context approaches model's context limit:
1. Check if current_tokens >= threshold (default 85% of limit)
2. Prompt model to summarize progress with specific structure:
   - Steps completed vs remaining
   - Concrete intermediate results (preserve exactly)
   - Next action
3. Replace message_history with: system + summary + continue instruction
4. Append summary to compaction history (`history` variable)

### 2.3 Persistence Pattern
For multi-turn conversations:
1. Set `persistent=True` when creating RLM
2. Reuse environment across completion calls
3. Environment must implement `SupportsPersistence` protocol:
   - `update_handler_address()`
   - `add_context()` with versioning
   - `get_context_count()`
   - `add_history()` with deep copy
   - `get_history_count()`
4. Context and history are versioned (context_0, context_1, ...)
5. Unversioned names alias to index 0

### 2.4 Subcall Routing Pattern
- depth=0: Use default_client (main backend)
- depth=1: Use other_backend_client if exists, else default_client
- If model specified and registered: use that client directly
- Support only one additional backend for recursive sub-calls

### 2.5 Prompt Building Pattern
Build prompts in three layers:
1. System prompt (RLM_SYSTEM_PROMPT + custom tools section)
2. Query metadata (context type, lengths, total size)
3. User prompt (iteration context + root prompt if provided)

Use `build_rlm_system_prompt()` and `build_user_prompt()` from `rlm/utils/prompts.py`.

### 2.6 Code Block Extraction Pattern
Use regex `r"```repl\s*\n(.*?)\n```"` to find code blocks. Truncate results exceeding 20,000 chars.

### 2.7 Error Handling Pattern
Follow "fail fast, fail loud" philosophy:
- Missing API key -> raise ValueError immediately
- No graceful fallbacks for configuration errors
- Track consecutive errors, raise `ErrorThresholdExceededError`
- Budget exceeded -> raise `BudgetExceededError`
- Token limit exceeded -> raise `TokenLimitExceededError`
- Timeout exceeded -> raise `TimeoutExceededError`
- User cancellation -> raise `CancellationError`

### 2.8 Callback Pattern
RLM supports lifecycle callbacks:
- `on_subcall_start(depth, model, prompt_preview)`
- `on_subcall_complete(depth, model, duration, error_or_none)`
- `on_iteration_start(depth, iteration_num)`
- `on_iteration_complete(depth, iteration_num, duration)`

---

## Level 3: Architecture-Level Patterns

### 3.1 Two-Tier Architecture
```
RLM (main process)
    --> LMHandler (ThreadingTCPServer)
            --> Environment (REPL)
                    --> Code execution with llm_query() access
```
- RLM: Orchestrates iterations, manages state, handles limits
- LMHandler: Routes LLM requests via TCP sockets
- Environment: Executes code, manages REPL namespace

### 3.2 Isolated vs Non-Isolated Environments
- **NonIsolatedEnv** (`local`): Same process/machine, uses socket TCP
- **IsolatedEnv** (`modal`, `prime`): Separate machine, uses HTTP broker
- Choose base class based on deployment needs
- Isolated envs cannot connect directly to LMHandler socket

### 3.3 Socket Protocol Pattern
Non-isolated environments communicate via:
- 4-byte big-endian length prefix + UTF-8 JSON payload
- LMRequest/LMResponse dataclasses
- send_lm_request() and send_lm_request_batched() helpers
- ThreadingLMServer for concurrent handling

### 3.4 Context Window Management
Two strategies:
1. **Versioned contexts**: Multiple contexts via context_0, context_1, ...
2. **Compaction**: Summarize trajectory when approaching limit
3. **History versioning**: Multiple conversation histories via history_0, history_1, ...

### 3.5 State Management Pattern
- Separate globals (builtins, helper functions) from locals (user variables)
- Restore scaffold after each execution to prevent namespace corruption
- Use threading lock for thread-safe output capture
- Use temporary working directory for file operations

### 3.6 MCP Integration Pattern
1. Configure MCP servers in RLM constructor via `mcp_servers`
2. MCPClientManager handles connections
3. For local envs: shared manager instance
4. For isolated envs: raw config dict passed through
5. Tools wrapped as callables with schema parsing
6. Validate MCP tools don't conflict with reserved names

### 3.7 Logging and Visualization
1. RLMLogger captures full trajectory
2. Store in log_dir as JSON
3. Use visualizer for tree display
4. Metadata logged at initialization (filtered sensitive keys)
5. Iterations logged per completion call

---

## Level 4: Repository Development Patterns

### 4.1 Code Style Standards
- **Formatting**: Strict ruff enforcement (`ruff check --fix .`)
- **Typing**: Explicit types preferred; cast/assert for narrowing
- **Naming**:
  - Methods: snake_case
  - Classes: PascalCase
  - Variables: snake_case
  - Constants: UPPER_CASE
- **No `_` prefix** for private methods unless explicitly requested
- **No `# type: ignore`** without strong justification

### 4.2 Testing Strategy
- pytest under `tests/` directory
- Simple, deterministic unit tests
- Update tests when changing functionality
- Mock external services for isolated environments
- Run: `uv run pytest`

### 4.3 Dependency Management
- Avoid new core dependencies
- Use optional extras for non-essential features (`[modal]`, `[prime]`)
- Exception: tiny deps that simplify widely-used code
- Document API keys as environment variables only

### 4.4 Scope and PR Guidelines
- Small, focused diffs
- One change per PR
- Backward compatibility only without excessive maintenance burden
- Delete dead code (don't guard it)
- Keep documentation concise and actionable
- Update README when behavior changes

### 4.5 Pre-PR Checklist
```bash
uv run ruff check --fix .
uv run ruff format .
uv run pre-commit run --all-files
uv run pytest
```

### 4.6 Configuration Guidelines
- **Environment variables**: ONLY for API keys
- **Hardcode**: Default base URLs, reasonable defaults
- **Arguments**: Essential customization via `__init__()`

---

## Level 5: Anti-Patterns and Warnings

### 5.1 What NOT to Do
- Do not add silent fallbacks for missing configuration
- Do not use `# type: ignore` without justification
- Do not prefix private methods with `_` unless required
- Do not create new core dependencies without strong justification
- Do not guard dead code - delete it
- Do not allow custom tools to override reserved names
- Do not return references instead of deep copies for history
- Do not use eval/exec/input in environment code
- Do not add `_` prefix for private methods unless explicitly requested

### 5.2 Common Mistakes
- FINAL_VAR called without first creating the variable in a repl block
- Not restoring reserved names after code execution
- Forgetting to register new clients/environments in __init__.py
- Not implementing all abstract methods from BaseLM or BaseEnv
- Using mutable default arguments in dataclasses
- Not handling both string and message list prompts in clients
- Not tracking usage in client implementations
- Not calling cleanup() for resource management in environments

---

## Quick Reference: Key Files

| File | Purpose |
|------|---------|
| `rlm/core/rlm.py` | Main RLM class, iteration loop |
| `rlm/core/lm_handler.py` | LM request routing via TCP |
| `rlm/core/types.py` | Dataclasses for types |
| `rlm/environments/base_env.py` | Base environment classes |
| `rlm/environments/local_repl.py` | Default REPL implementation |
| `rlm/clients/base_lm.py` | Base LM client class |
| `rlm/utils/parsing.py` | Code block and final answer extraction |
| `rlm/utils/prompts.py` | System/user prompt building |
| `rlm/utils/exceptions.py` | Custom exception classes |
| `rlm/logger/rlm_logger.py` | Trajectory logging |
| `rlm/clients/mcp_manager.py` | MCP server integration |

## Quick Reference: Key Classes

| Class | Inheritance | Purpose |
|-------|-------------|---------|
| `RLM` | - | Main orchestration class |
| `LMHandler` | - | TCP server for LM requests |
| `BaseLM` | ABC | LM client base class |
| `BaseEnv` | ABC | Environment base class |
| `NonIsolatedEnv` | BaseEnv | Same-machine environments |
| `IsolatedEnv` | BaseEnv | Cloud sandbox environments |
| `LocalREPL` | NonIsolatedEnv | Default local environment |
| `RLMIteration` | dataclass | Single iteration record |
| `REPLResult` | dataclass | Code execution result |
| `RLMChatCompletion` | dataclass | Final completion record |
| `ToolInfo` | dataclass | Custom tool metadata |
| `RLMLogger` | - | Trajectory logging |
| `MCPClientManager` | - | MCP server management |

---

## Summary

This guide presents a hierarchy of patterns from component-level details to architectural principles. When updating the repository:

1. **Follow Level 1 patterns** for all new components (clients, environments, tools)
2. **Respect Level 2 patterns** for module behavior (iteration loops, error handling, callbacks)
3. **Understand Level 3 patterns** for architectural decisions (isolation, persistence, logging)
4. **Adhere to Level 4 patterns** for repository development (code style, testing, PRs)
5. **Avoid Level 5 anti-patterns** to maintain code quality and consistency
