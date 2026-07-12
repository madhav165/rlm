"""
Integration tests for MCP tools in REPL.

Run with: uv run pytest tests/repl/test_mcp_tools.py -v
"""

import asyncio
import importlib.util
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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

    def test_streamable_http_transport_closes_in_owning_task(self):
        class TrackingContext:
            def __init__(self, value):
                self.value = value
                self.owner = None
                self.exited = False

            async def __aenter__(self):
                self.owner = asyncio.current_task()
                return self.value

            async def __aexit__(self, exc_type, exc, traceback):
                assert asyncio.current_task() is self.owner
                self.exited = True

        transport = TrackingContext((object(), object(), None))
        session = SimpleNamespace(
            initialize=AsyncMock(),
            list_tools=AsyncMock(return_value=SimpleNamespace(tools=[])),
        )
        session_context = TrackingContext(session)

        with (
            patch(
                "rlm.clients.mcp_manager.streamable_http_client",
                return_value=transport,
            ),
            patch("rlm.clients.mcp_manager.ClientSession", return_value=session_context),
        ):
            manager = MCPClientManager(
                {"remote": {"type": "streamable-http", "url": "https://example.com/mcp"}}
            )
            manager.connect_all()
            manager.disconnect_all()

        assert transport.exited
        assert session_context.exited


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


# =============================================================================
# Tests for Isolated Environments (Docker, Modal, Prime)
# =============================================================================


class TestMCPInDocker:
    """Tests for MCP tools in DockerREPL."""

    def test_mcp_tool_execution_in_docker_repl(self):
        """Test executing an MCP tool through DockerREPL."""
        pytest.importorskip("docker")
        from rlm.environments.docker_repl import DockerREPL

        config = {
            "time": {
                "type": "stdio",
                "command": "uvx",
                "args": ["mcp-server-time"],
            }
        }

        manager = MCPClientManager(config)
        manager.connect_all()

        repl = DockerREPL(mcp_servers=config)

        # Call the tool through REPL - get_current_time requires timezone argument
        result = repl.execute_code("result = get_current_time(timezone='UTC')")

        # Should have executed without error
        assert result.stderr == "", f"Unexpected error: {result.stderr}"

        # Result should be in locals
        assert "result" in result.locals, f"result not in locals: {list(result.locals.keys())}"

        repl.cleanup()
        manager.disconnect_all()

    def test_mcp_tool_with_timezone_in_docker_repl(self):
        """Test executing an MCP tool with arguments through DockerREPL."""
        pytest.importorskip("docker")
        from rlm.environments.docker_repl import DockerREPL

        config = {
            "time": {
                "type": "stdio",
                "command": "uvx",
                "args": ["mcp-server-time"],
            }
        }

        manager = MCPClientManager(config)
        manager.connect_all()

        repl = DockerREPL(mcp_servers=config)

        # Call the tool with arguments through REPL
        result = repl.execute_code(
            "result = convert_time(source_timezone='UTC', target_timezone='America/Los_Angeles', time='2024-06-15T15:00:00Z')"
        )

        # Should have executed without error
        assert result.stderr == "", f"Unexpected error: {result.stderr}"

        # Result should be in locals
        assert "result" in result.locals, f"result not in locals: {list(result.locals.keys())}"

        repl.cleanup()
        manager.disconnect_all()


class TestMCPInModal:
    """Tests for MCP tools in ModalREPL."""

    def test_mcp_tool_execution_in_modal_repl(self):
        """Test executing an MCP tool through ModalREPL."""
        if importlib.util.find_spec("modal") is None:
            pytest.skip("modal not installed")

        from rlm.environments.modal_repl import ModalREPL

        config = {
            "time": {
                "type": "stdio",
                "command": "uvx",
                "args": ["mcp-server-time"],
            }
        }

        manager = MCPClientManager(config)
        manager.connect_all()

        repl = ModalREPL(mcp_servers=config)

        # Call the tool through REPL - get_current_time requires timezone argument
        result = repl.execute_code("result = get_current_time(timezone='UTC')")

        # Should have executed without error
        assert result.stderr == "", f"Unexpected error: {result.stderr}"

        # Result should be in locals
        assert "result" in result.locals, f"result not in locals: {list(result.locals.keys())}"

        repl.cleanup()
        manager.disconnect_all()

    def test_mcp_tool_with_timezone_in_modal_repl(self):
        """Test executing an MCP tool with arguments through ModalREPL."""
        if importlib.util.find_spec("modal") is None:
            pytest.skip("modal not installed")

        from rlm.environments.modal_repl import ModalREPL

        config = {
            "time": {
                "type": "stdio",
                "command": "uvx",
                "args": ["mcp-server-time"],
            }
        }

        manager = MCPClientManager(config)
        manager.connect_all()

        repl = ModalREPL(mcp_servers=config)

        # Call the tool with arguments through REPL
        result = repl.execute_code(
            "result = convert_time(source_timezone='UTC', target_timezone='America/Los_Angeles', time='2024-06-15T15:00:00Z')"
        )

        # Should have executed without error
        assert result.stderr == "", f"Unexpected error: {result.stderr}"

        # Result should be in locals
        assert "result" in result.locals, f"result not in locals: {list(result.locals.keys())}"

        repl.cleanup()
        manager.disconnect_all()


class TestMCPInPrime:
    """Tests for MCP tools in PrimeREPL."""

    def test_mcp_tool_execution_in_prime_repl(self):
        """Test executing an MCP tool through PrimeREPL."""
        if importlib.util.find_spec("prime_sandboxes") is None:
            pytest.skip("prime_sandboxes not installed")

        from rlm.environments.prime_repl import PrimeREPL

        config = {
            "time": {
                "type": "stdio",
                "command": "uvx",
                "args": ["mcp-server-time"],
            }
        }

        manager = MCPClientManager(config)
        manager.connect_all()

        repl = PrimeREPL(mcp_servers=config)

        # Call the tool through REPL - get_current_time requires timezone argument
        result = repl.execute_code("result = get_current_time(timezone='UTC')")

        # Should have executed without error
        assert result.stderr == "", f"Unexpected error: {result.stderr}"

        # Result should be in locals
        assert "result" in result.locals, f"result not in locals: {list(result.locals.keys())}"

        repl.cleanup()
        manager.disconnect_all()

    def test_mcp_tool_with_timezone_in_prime_repl(self):
        """Test executing an MCP tool with arguments through PrimeREPL."""
        if importlib.util.find_spec("prime_sandboxes") is None:
            pytest.skip("prime_sandboxes not installed")

        from rlm.environments.prime_repl import PrimeREPL

        config = {
            "time": {
                "type": "stdio",
                "command": "uvx",
                "args": ["mcp-server-time"],
            }
        }

        manager = MCPClientManager(config)
        manager.connect_all()

        repl = PrimeREPL(mcp_servers=config)

        # Call the tool with arguments through REPL
        result = repl.execute_code(
            "result = convert_time(source_timezone='UTC', target_timezone='America/Los_Angeles', time='2024-06-15T15:00:00Z')"
        )

        # Should have executed without error
        assert result.stderr == "", f"Unexpected error: {result.stderr}"

        # Result should be in locals
        assert "result" in result.locals, f"result not in locals: {list(result.locals.keys())}"

        repl.cleanup()
        manager.disconnect_all()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
