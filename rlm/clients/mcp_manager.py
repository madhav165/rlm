from __future__ import annotations

import asyncio
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession, types
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import StreamableHTTPTransport


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

    def connect_all(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._exit_stack = AsyncExitStack()

        async def connect_all_async() -> None:
            for name, config in self._configs.items():
                await self._connect_server_async(name, config)

        self._loop.run_until_complete(connect_all_async())

    def disconnect_all(self) -> None:
        if self._exit_stack is not None:
            try:
                self._loop.run_until_complete(self._exit_stack.aclose())
            except Exception:
                pass
            self._exit_stack = None
        if self._loop is not None:
            self._loop.close()
            self._loop = None
        self._sessions.clear()
        self._tools.clear()

    def get_tools(self) -> dict[str, MCPToolInfo]:
        return self._tools.copy()

    def call_tool(self, name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        if name not in self._tools:
            raise MCPError(f"Unknown tool: {name}")

        tool_info = self._tools[name]
        session = self._sessions[tool_info.server_name]

        async def _call_tool() -> types.CallToolResult:
            return await session.call_tool(name, arguments)

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

        transport = StreamableHTTPTransport(url=url)
        read, write = await transport.connect()
        session = ClientSession(read, write)
        await self._exit_stack.enter_async_context(session)
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
