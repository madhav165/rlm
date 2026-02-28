"""
Integration tests for MCP tools in REPL.

Run with: uv run pytest tests/repl/test_mcp_tools.py -v
"""

import pytest

from rlm.clients.mcp_manager import MCPClientManager, MCPError
from rlm.environments.local_repl import LocalREPL


class TestMCPClientManager:
    """Tests for MCPClientManager with stdio server."""

    def test_connect_to_time_server_stdio(self):
        """Test connecting to the time MCP server via stdio."""
        config = {
            "time": {
                "type": "stdio",
                "command": "uvx",
                "args": ["mcp-server-time"],
            }
        }

        manager = MCPClientManager(config)
        manager.connect_all()

        tools = manager.get_tools()
        assert len(tools) > 0
        tool_names = list(tools.keys())
        print(f"Available tools: {tool_names}")

        # The time server should have time-related tools
        assert any("time" in name.lower() for name in tool_names)

        manager.disconnect_all()

    def test_call_tool_on_time_server(self):
        """Test calling a tool on the time MCP server."""
        config = {
            "time": {
                "type": "stdio",
                "command": "uvx",
                "args": ["mcp-server-time"],
            }
        }

        manager = MCPClientManager(config)
        manager.connect_all()

        # Get the current time
        result = manager.call_tool("get_current_time", {})

        # Should have content
        assert result.content is not None
        assert len(result.content) > 0
        print(f"Time result: {result.content}")

        manager.disconnect_all()

    def test_call_tool_with_timezone(self):
        """Test calling a tool with timezone parameter."""
        config = {
            "time": {
                "type": "stdio",
                "command": "uvx",
                "args": ["mcp-server-time"],
            }
        }

        manager = MCPClientManager(config)
        manager.connect_all()

        # Get time in a specific timezone
        result = manager.call_tool(
            "convert_time",
            {
                "source_timezone": "UTC",
                "target_timezone": "America/New_York",
                "time": "2024-01-01T12:00:00Z",
            },
        )

        assert result.content is not None
        print(f"Converted time: {result.content}")

        manager.disconnect_all()

    def test_error_on_unknown_tool(self):
        """Test that calling an unknown tool raises MCPError."""
        config = {
            "time": {
                "type": "stdio",
                "command": "uvx",
                "args": ["mcp-server-time"],
            }
        }

        manager = MCPClientManager(config)
        manager.connect_all()

        with pytest.raises(MCPError) as exc_info:
            manager.call_tool("nonexistent_tool_xyz", {})

        assert "Unknown tool" in str(exc_info.value)

        manager.disconnect_all()


class TestMCPToolsInREPL:
    """Tests for MCP tools integrated into LocalREPL."""

    def test_mcp_tools_available_in_repl(self):
        """Test that MCP tools are available in REPL execution."""
        config = {
            "time": {
                "type": "stdio",
                "command": "uvx",
                "args": ["mcp-server-time"],
            }
        }

        manager = MCPClientManager(config)
        manager.connect_all()

        repl = LocalREPL(mcp_manager=manager)

        # The tool should be available in globals
        assert "get_current_time" in repl.globals

        repl.cleanup()
        manager.disconnect_all()

    def test_mcp_tool_execution_in_repl(self):
        """Test executing an MCP tool through REPL."""
        config = {
            "time": {
                "type": "stdio",
                "command": "uvx",
                "args": ["mcp-server-time"],
            }
        }

        manager = MCPClientManager(config)
        manager.connect_all()

        repl = LocalREPL(mcp_manager=manager)

        # Call the tool through REPL
        result = repl.execute_code("result = get_current_time()")

        # Should have executed without error
        assert result.stderr == "", f"Unexpected error: {result.stderr}"

        # Result should be in locals
        assert "result" in repl.locals
        print(f"Result value: {repl.locals['result']}")

        repl.cleanup()
        manager.disconnect_all()

    def test_mcp_tool_with_arguments_in_repl(self):
        """Test executing an MCP tool with arguments through REPL."""
        config = {
            "time": {
                "type": "stdio",
                "command": "uvx",
                "args": ["mcp-server-time"],
            }
        }

        manager = MCPClientManager(config)
        manager.connect_all()

        repl = LocalREPL(mcp_manager=manager)

        # Call the tool with arguments through REPL
        result = repl.execute_code(
            "result = convert_time(source_timezone='UTC', target_timezone='America/Los_Angeles', time='2024-06-15T15:00:00Z')"
        )

        # Should have executed without error
        assert result.stderr == "", f"Unexpected error: {result.stderr}"

        # Result should be in locals
        assert "result" in repl.locals
        print(f"Result value: {repl.locals['result']}")

        repl.cleanup()
        manager.disconnect_all()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
