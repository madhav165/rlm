from __future__ import annotations

import asyncio
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession, types
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client


@dataclass
class MCPToolInfo:
    name: str
    description: str | None
    input_schema: dict[str, Any]
    server_name: str


class MCPError(Exception):
    pass


class MCPClientManager:
    def __init__(self, configs: dict[str, dict[str, Any]] | None = None):
        self._configs = configs or {}
        self._sessions: dict[str, ClientSession] = {}
        self._tools: dict[str, MCPToolInfo] = {}
        self._exit_stack: AsyncExitStack | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lifecycle_task: asyncio.Task[None] | None = None
        self._ready_event: asyncio.Event | None = None
        self._shutdown_event: asyncio.Event | None = None

    def connect_all(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._ready_event = asyncio.Event()
        self._shutdown_event = asyncio.Event()
        self._lifecycle_task = self._loop.create_task(self._run_lifecycle())
        self._loop.run_until_complete(self._ready_event.wait())

        if self._lifecycle_task.done():
            self._lifecycle_task.result()

    async def _run_lifecycle(self) -> None:
        try:
            async with AsyncExitStack() as exit_stack:
                self._exit_stack = exit_stack
                for name, config in self._configs.items():
                    await self._connect_server_async(name, config)
                self._ready_event.set()
                await self._shutdown_event.wait()
        finally:
            self._ready_event.set()

    def disconnect_all(self) -> None:
        if self._lifecycle_task is not None and not self._lifecycle_task.done():
            self._shutdown_event.set()
            try:
                self._loop.run_until_complete(self._lifecycle_task)
            except Exception:
                pass
        self._lifecycle_task = None
        self._ready_event = None
        self._shutdown_event = None
        self._exit_stack = None
        if self._loop is not None:
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.close()
            self._loop = None
        self._sessions.clear()
        self._tools.clear()

    def get_tools(self) -> dict[str, MCPToolInfo]:
        return self._tools.copy()

    def call_tool(
        self, name: str, arguments: dict[str, Any], timeout: float = 30.0
    ) -> types.CallToolResult:
        if name not in self._tools:
            raise MCPError(f"Unknown tool: {name}")

        tool_info = self._tools[name]
        session = self._sessions[tool_info.server_name]

        async def _call_tool() -> types.CallToolResult:
            try:
                return await asyncio.wait_for(session.call_tool(name, arguments), timeout=timeout)
            except TimeoutError as err:
                raise MCPError(f"Tool '{name}' timed out after {timeout}s") from err
            except asyncio.CancelledError as err:
                raise MCPError(f"Tool '{name}' was cancelled") from err
            except Exception as err:
                raise MCPError(f"Tool '{name}' failed: {err}") from err

        result = self._loop.run_until_complete(_call_tool())
        return result

    async def _connect_server_async(self, name: str, config: dict[str, Any]) -> None:
        server_type = config.get("type", "stdio")

        if server_type == "stdio":
            await self._connect_stdio_server_async(name, config)
        elif server_type in ("streamable-http", "sse"):
            await self._connect_http_server_async(name, config)
        else:
            raise ValueError(f"Unknown MCP server type: {server_type}")

    async def _connect_stdio_server_async(self, name: str, config: dict[str, Any]) -> None:
        command = config.get("command")
        if not command:
            raise ValueError(f"MCP stdio server '{name}' requires 'command' in config")
        args = config.get("args", [])
        env = config.get("env", {})

        merged_env = os.environ.copy()
        merged_env.update(env)

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=merged_env,
        )

        stdio_transport = await self._exit_stack.enter_async_context(stdio_client(server_params))
        read, write = stdio_transport
        session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._sessions[name] = session

        tools_result = await session.list_tools()
        self._register_tools(name, tools_result)

    async def _connect_http_server_async(self, name: str, config: dict[str, Any]) -> None:
        url = config.get("url")
        if not url:
            raise ValueError(f"MCP server {name} requires 'url' for HTTP transport")

        read, write, _ = await self._exit_stack.enter_async_context(streamable_http_client(url))
        session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._sessions[name] = session

        tools_result = await session.list_tools()
        self._register_tools(name, tools_result)

    def _register_tools(self, server_name: str, tools_result: types.ListToolsResult) -> None:
        for tool in tools_result.tools:
            if tool.name in self._tools:
                raise MCPError(f"Duplicate tool name '{tool.name}' across MCP servers")

            self._tools[tool.name] = MCPToolInfo(
                name=tool.name,
                description=tool.description,
                input_schema=tool.inputSchema,
                server_name=server_name,
            )
