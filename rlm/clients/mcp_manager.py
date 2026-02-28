from __future__ import annotations

import os
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

    def connect_all(self) -> None:
        for name, config in self._configs.items():
            self._connect_server(name, config)

    def disconnect_all(self) -> None:
        self._sessions.clear()
        self._tools.clear()

    def get_tools(self) -> dict[str, MCPToolInfo]:
        return self._tools.copy()

    def call_tool(self, name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        if name not in self._tools:
            raise MCPError(f"Unknown tool: {name}")

        tool_info = self._tools[name]
        session = self._sessions[tool_info.server_name]

        return session.call_tool(name, arguments)

    def _connect_server(self, name: str, config: dict[str, Any]) -> None:
        server_type = config.get("type", "stdio")

        if server_type == "stdio":
            self._connect_stdio_server(name, config)
        elif server_type in ("streamable-http", "sse"):
            self._connect_http_server(name, config)
        else:
            raise ValueError(f"Unknown MCP server type: {server_type}")

    def _connect_stdio_server(self, name: str, config: dict[str, Any]) -> None:
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

        import asyncio

        async def connect() -> None:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    self._sessions[name] = session
                    self._register_tools(name, tools)

        asyncio.run(connect())

    def _connect_http_server(self, name: str, config: dict[str, Any]) -> None:
        url = config.get("url")
        if not url:
            raise ValueError(f"MCP server {name} requires 'url' for HTTP transport")

        import asyncio

        async def connect() -> None:
            transport = StreamableHTTPTransport(url=url)
            async with transport.connect() as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    self._sessions[name] = session
                    self._register_tools(name, tools)

        asyncio.run(connect())

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
