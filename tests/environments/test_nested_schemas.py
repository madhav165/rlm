"""
Tests for nested JSON schema handling in custom tools.

Run with: uv run pytest tests/environments/test_nested_schemas.py -v
"""

from rlm.environments.base_env import _format_input_schema, format_tools_for_prompt


class TestNestedSchemaRendering:
    """Tests for rendering nested JSON schemas in tool descriptions."""

    def test_flat_schema_rendering(self):
        """Test that flat schemas are rendered correctly."""
        custom_tools = {
            "get_weather": {
                "tool": lambda city: None,
                "description": "Get weather for a city",
                "input_schema": {
                    "type": "object",
                    "properties": {"city": {"type": "string", "description": "City name"}},
                    "required": ["city"],
                },
            }
        }

        result = format_tools_for_prompt(custom_tools)
        assert "get_weather" in result
        assert "(city: str)" in result

    def test_nested_schema_rendering(self):
        """Test that nested schemas are rendered with proper indentation."""
        custom_tools = {
            "create_user": {
                "tool": lambda user: None,
                "description": "Create a new user",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "User name"},
                        "address": {
                            "type": "object",
                            "description": "User address",
                            "properties": {
                                "street": {"type": "string", "description": "Street name"},
                                "city": {"type": "string", "description": "City name"},
                                "coordinates": {
                                    "type": "object",
                                    "description": "GPS coordinates",
                                    "properties": {
                                        "lat": {"type": "number", "description": "Latitude"},
                                        "lon": {"type": "number", "description": "Longitude"},
                                    },
                                    "required": ["lat", "lon"],
                                },
                            },
                            "required": ["street", "city"],
                        },
                    },
                    "required": ["name", "address"],
                },
            }
        }

        result = format_tools_for_prompt(custom_tools)
        assert "create_user" in result
        assert "(name: str, address: dict)" in result
        # Should have nested param descriptions
        assert "address:" in result
        assert "street:" in result
        assert "city:" in result
        assert "coordinates:" in result

    def test_array_schema_rendering(self):
        """Test that array schemas are rendered correctly."""
        custom_tools = {
            "process_items": {
                "tool": lambda items: None,
                "description": "Process multiple items",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "description": "List of items to process",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "value": {"type": "number"},
                                },
                                "required": ["id", "value"],
                            },
                        }
                    },
                    "required": ["items"],
                },
            }
        }

        result = format_tools_for_prompt(custom_tools)
        assert "process_items" in result
        assert "(items: list)" in result

    def test_mixed_nested_schema(self):
        """Test schema with mixed types and nesting."""
        custom_tools = {
            "search": {
                "tool": lambda query, filters: None,
                "description": "Search with filters",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "filters": {
                            "type": "object",
                            "description": "Filter options",
                            "properties": {
                                "tags": {
                                    "type": "array",
                                    "description": "Tag filter",
                                    "items": {"type": "string"},
                                },
                                "range": {
                                    "type": "object",
                                    "description": "Numeric range",
                                    "properties": {
                                        "min": {"type": "number"},
                                        "max": {"type": "number"},
                                    },
                                },
                            },
                        },
                    },
                    "required": ["query"],
                },
            }
        }

        result = format_tools_for_prompt(custom_tools)
        assert "search" in result
        assert "(query: str, filters: dict = None)" in result
        assert "filters:" in result
        assert "tags:" in result
        assert "range:" in result

    def test_mcp_tool_with_nested_args(self):
        """Test that MCP tools with nested schemas work end-to-end."""
        from rlm.clients.mcp_manager import MCPToolInfo

        tool_info = MCPToolInfo(
            name="create_order",
            description="Create a new order",
            input_schema={
                "type": "object",
                "properties": {
                    "customer": {
                        "type": "object",
                        "description": "Customer information",
                        "properties": {
                            "name": {"type": "string"},
                            "email": {"type": "string"},
                            "address": {
                                "type": "object",
                                "properties": {
                                    "street": {"type": "string"},
                                    "city": {"type": "string"},
                                    "zip": {"type": "string"},
                                },
                                "required": ["street", "city"],
                            },
                        },
                        "required": ["name", "email"],
                    },
                    "items": {
                        "type": "array",
                        "description": "Order items",
                        "items": {
                            "type": "object",
                            "properties": {
                                "product_id": {"type": "string"},
                                "quantity": {"type": "integer"},
                                "price": {"type": "number"},
                            },
                            "required": ["product_id", "quantity"],
                        },
                    },
                },
                "required": ["customer", "items"],
            },
            server_name="orders-mcp",
        )

        # Verify schema can be rendered
        sig, param_descs = _format_input_schema(tool_info.input_schema)
        assert "customer: dict" in sig
        assert "items: list" in sig
        assert "customer:" in str(param_descs)
        assert "items:" in str(param_descs)

    def test_local_repl_nested_wrapper(self):
        """Test LocalREPL wrapper with nested schemas."""
        from unittest.mock import Mock

        from rlm.environments.local_repl import LocalREPL

        mock_manager = Mock()
        mock_manager.get_tools.return_value = {
            "test_tool": Mock(
                name="test_tool",
                description="Test tool",
                input_schema={
                    "type": "object",
                    "properties": {
                        "nested": {"type": "object", "properties": {"field": {"type": "string"}}}
                    },
                },
                server_name="test",
            )
        }
        mock_manager.call_tool.side_effect = Exception("MCP manager not available")

        repl = LocalREPL(mcp_manager=mock_manager)

        assert "test_tool" in repl.globals
        wrapper = repl.globals["test_tool"]

        result = wrapper(nested={"field": "value"})
        assert "MCP manager not available" in result
