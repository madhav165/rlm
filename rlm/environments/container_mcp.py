"""Shared MCP initialization code for isolated environment sandbox scripts.

This module generates the Python code string that runs inside container sandboxes
to initialize MCP servers, register tool wrappers, and provide cleanup/invocation
functions. Used by ModalREPL, PrimeREPL, and DockerREPL to avoid duplicating the
MCP setup logic across three files.
"""

import base64
import json
import textwrap


def generate_mcp_init_code(mcp_config: dict, globals_target: str = "_globals") -> str:
    """Generate MCP initialization code for embedding in a sandbox script.

    Args:
        mcp_config: MCP server configurations dict (server name → config).
        globals_target: Variable name for the globals dict where tool wrappers
            will be injected. Use "_globals" (default) when the target dict is
            defined before this code block, or "globals" when the target is the
            module-level globals dict (e.g. Docker).

    Returns:
        A Python code string to embed in the sandbox execution script.
    """
    config_b64 = base64.b64encode(json.dumps(mcp_config).encode()).decode()

    # For "globals" target, use globals() call; for other targets (e.g. "_globals"),
    # use the variable directly since it's already a dict.
    globals_ref = "globals()" if globals_target == "globals" else globals_target

    return textwrap.dedent(
        f"""
import asyncio
import json
import base64
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

_mcp_configs = json.loads(base64.b64decode("{config_b64}").decode())
_mcp_sessions = {{}}
_mcp_tools = {{}}
_exit_stack = AsyncExitStack()
_mcp_loop = None


async def _connect_mcp_server(name, config):
    server_type = config.get("type", "stdio")
    if server_type == "stdio":
        command = config.get("command")
        args = config.get("args", [])
        env = config.get("env", {{}})
        import os
        merged_env = os.environ.copy()
        merged_env.update(env)
        server_params = StdioServerParameters(command=command, args=args, env=merged_env)
        read, write = await _exit_stack.enter_async_context(stdio_client(server_params))
        session = await _exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        tools_result = await session.list_tools()
        for tool in tools_result.tools:
            if tool.name in _mcp_tools:
                raise ValueError(f"Duplicate MCP tool name '{{tool.name}}' across servers")
            _mcp_tools[tool.name] = {{"session": session, "tool": tool}}
        _mcp_sessions[name] = session
    elif server_type in ("streamable-http", "sse"):
        url = config.get("url")
        read, write, _ = await _exit_stack.enter_async_context(streamable_http_client(url))
        session = await _exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        tools_result = await session.list_tools()
        for tool in tools_result.tools:
            if tool.name in _mcp_tools:
                raise ValueError(f"Duplicate MCP tool name '{{tool.name}}' across servers")
            _mcp_tools[tool.name] = {{"session": session, "tool": tool}}
        _mcp_sessions[name] = session


async def _connect_all_mcp():
    await _exit_stack.__aenter__()
    for name, config in _mcp_configs.items():
        await _connect_mcp_server(name, config)


def _init_mcp():
    global _mcp_loop
    _mcp_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_mcp_loop)
    _mcp_loop.run_until_complete(_connect_all_mcp())


def _cleanup_mcp():
    if _mcp_loop is not None and not _mcp_loop.is_closed():
        try:
            _mcp_loop.run_until_complete(_exit_stack.aclose())
        except Exception:
            pass
        _mcp_loop.close()


def _call_mcp_tool(name, arguments):
    if name not in _mcp_tools:
        return f"Error: Unknown tool: {{name}}"
    try:
        result = _mcp_loop.run_until_complete(
            asyncio.wait_for(
                _mcp_tools[name]["session"].call_tool(name, arguments),
                timeout=120,
            )
        )
        if hasattr(result, "content") and result.content:
            texts = []
            for item in result.content:
                if hasattr(item, "text"):
                    texts.append(item.text)
                else:
                    texts.append(str(item))
            return "\\n".join(texts) if texts else str(result)
        return str(result)
    except asyncio.TimeoutError:
        return f"Error: MCP tool '{{name}}' timed out after 120s"
    except Exception as e:
        return f"Error: MCP tool '{{name}}' failed: {{e}}"


# Initialize MCP servers
_init_mcp()

# Add MCP tools to {globals_target} so they are available in exec'd user code
for _tool_name in list(_mcp_tools.keys()):
    def _make_wrapper(_name):
        _tool = _mcp_tools[_name]["tool"]
        _props = list((_tool.inputSchema.get("properties") or {{}}).keys())
        def _wrapper(*args, **kwargs):
            for _i, _arg in enumerate(args):
                if _i < len(_props):
                    kwargs[_props[_i]] = _arg
            return _call_mcp_tool(_name, kwargs)
        _wrapper.__name__ = _name
        _wrapper.__doc__ = _tool.description
        return _wrapper
    {globals_ref}[_tool_name] = _make_wrapper(_tool_name)
"""
    )
