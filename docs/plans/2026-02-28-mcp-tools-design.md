# MCP Tools Support - Implementation Plan

**Feature**: Connect RLM as an MCP client to external MCP servers
**Date**: 2026-02-28
**Status**: Planned

## Overview

Enable RLM to connect to external MCP servers and expose their tools to the model. RLM acts as an MCP client, using the MCP Python SDK to discover and invoke tools.

## Configuration Format

```python
mcp_servers={
    "weather": {
        "type": "stdio",
        "command": "python",
        "args": ["weather_server.py"],
        "env": {"API_KEY": "..."}
    },
    "database": {
        "type": "streamable-http", 
        "url": "http://localhost:8080/mcp"
    }
}
```

Supported transport types:
- `stdio` - Local process communication
- `streamable-http` - HTTP-based remote communication
- `sse` - Legacy HTTP SSE (for backwards compatibility)

## Implementation Steps

### Step 1: Add MCP SDK dependency

Add `mcp` to dependencies in `pyproject.toml`.

### Step 2: Create MCPClientManager

**File**: `rlm/clients/mcp_manager.py`

- `MCPClientManager` class
- `__init__(configs: dict[str, dict])` - Store server configs
- `connect_all()` - Initialize all MCP connections
- `disconnect_all()` - Cleanup all connections
- `call_tool(name: str, arguments: dict) -> ToolResult` - Invoke a tool
- `_connect_server(name: str, config: dict)` - Single server connection
- `_discover_tools(session: ClientSession)` - Get tools from server
- Internal storage: `dict[str, tuple[ClientSession, list[Tool]]]`

### Step 3: Integrate with RLM

**File**: `rlm/__init__.py`

- Add `mcp_servers: dict[str, dict] | None = None` parameter to `RLM.__init__()`
- Initialize `MCPClientManager` if `mcp_servers` provided
- Store in `self.mcp_manager`
- Call `mcp_manager.connect_all()` during RLM setup
- Call `mcp_manager.disconnect_all()` during cleanup

### Step 4: Integrate with LocalREPL

**File**: `rlm/environments/local_repl.py`

- Modify `__init__` to accept `mcp_manager: MCPClientManager | None = None`
- In `setup()`:
  - Get tools from `mcp_manager.call_tool()` for each tool
  - Wrap each tool as a callable that invokes MCP
  - Add to REPL globals
- The wrapper:
  1. Parses function name and arguments from the call
  2. Calls `mcp_manager.call_tool(name, arguments)`
  3. Returns the result

### Step 5: Write tests

**File**: `tests/clients/test_mcp_manager.py`

- Test `MCPClientManager` with mocked transport
- Test tool discovery
- Test tool invocation
- Test error handling

**File**: `tests/repl/test_mcp_tools.py`

- Integration tests with a simple FastMCP server
- Test tool availability in REPL
- Test tool invocation through REPL

## Key Design Decisions

1. **Per-session lifecycle** - Servers spawn/connect at RLM init, persist for session
2. **Error propagation** - MCP errors return as-is to the model
3. **Tool resolution** - Unique tool names across all servers (error on duplicates)
4. **Use MCP SDK** - Directly use `mcp` Python package, not custom implementation

## Files Modified

| File | Change |
|------|--------|
| `pyproject.toml` | Add `mcp` dependency |
| `rlm/clients/mcp_manager.py` | **New** - MCP client manager |
| `rlm/__init__.py` | Add `mcp_servers` param |
| `rlm/clients/__init__.py` | Export new classes |
| `rlm/environments/local_repl.py` | Integrate MCP tools |
| `tests/clients/test_mcp_manager.py` | **New** - Unit tests |
| `tests/repl/test_mcp_tools.py` | **New** - Integration tests |

## Testing Commands

```bash
# Run all MCP-related tests
uv run pytest tests/clients/test_mcp_manager.py tests/repl/test_mcp_tools.py -v

# Run full test suite
uv run pytest
```
