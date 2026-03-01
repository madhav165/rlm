# Capture Nested JSON Fields in Custom Tools Schemas - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable proper capture, validation, and documentation of nested JSON fields in MCP tool schemas when they're added to custom tools in RLM environments.

**Architecture:** The plan involves three approaches to evaluate: (1) Enhance the custom tools schema to properly support nested JSON objects, (2) Create utility functions to flatten/extract nested fields for documentation, (3) Store full input_schema as stringified JSON for exact preservation. We'll implement approach #1 with proper recursive handling.

**Tech Stack:** Python 3.11+, MCP SDK, RLM custom tools infrastructure

---

## Analysis

The current implementation has:
- `ToolInfo` class in `base_env.py:27-34` with `input_schema: dict[str, Any] | None`
- `_create_mcp_tool_wrapper` in `local_repl.py:364-398` that reads `input_schema` to map arguments
- `MCPToolInfo` in `mcp_manager.py:14-18` with `input_schema: dict[str, Any]`
- Tools are added to prompts via `format_tools_for_prompt()` in `base_env.py:121-161`

**Problem:** When `input_schema` contains nested objects (e.g., `{"type": "object", "properties": {"address": {"type": "object", "properties": {"street": {...}}}}}`), the current code:
1. Doesn't properly flatten/nest parameter signatures in prompts
2. Loses nested structure when generating tool signatures for the model
3. Doesn't validate nested required fields

**Solution Options Evaluated:**
- **Option A:** Modify `format_tools_for_prompt()` to recursively render nested schemas → **RECOMMENDED** (keeps schema as dict, proper rendering)
- **Option B:** Store full schema as stringified JSON → Simpler but loses type info for model
- **Option C:** Flatten nested fields with dot notation (e.g., `address.street`) → Loses schema hierarchy

We'll implement Option A with proper recursive handling.

---

### Task 1: Write failing test for nested schema rendering

**Files:**
- Test: `tests/environments/test_nested_schemas.py`

**Step 1: Write the failing test**

Create `tests/environments/test_nested_schemas.py`:

```python
"""
Tests for nested JSON schema handling in custom tools.

Run with: uv run pytest tests/environments/test_nested_schemas.py -v
"""

import pytest

from rlm.environments.base_env import format_tools_for_prompt


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
                    "properties": {
                        "city": {"type": "string", "description": "City name"}
                    },
                    "required": ["city"]
                }
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
                                        "lon": {"type": "number", "description": "Longitude"}
                                    },
                                    "required": ["lat", "lon"]
                                }
                            },
                            "required": ["street", "city"]
                        }
                    },
                    "required": ["name", "address"]
                }
            }
        }
        
        result = format_tools_for_prompt(custom_tools)
        assert "create_user" in result
        assert "(name: str, address: object)" in result
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
                                    "value": {"type": "number"}
                                },
                                "required": ["id", "value"]
                            }
                        }
                    },
                    "required": ["items"]
                }
            }
        }
        
        result = format_tools_for_prompt(custom_tools)
        assert "process_items" in result
        assert "(items: array)" in result

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
                                    "items": {"type": "string"}
                                },
                                "range": {
                                    "type": "object",
                                    "description": "Numeric range",
                                    "properties": {
                                        "min": {"type": "number"},
                                        "max": {"type": "number"}
                                    }
                                }
                            }
                        }
                    },
                    "required": ["query"]
                }
            }
        }
        
        result = format_tools_for_prompt(custom_tools)
        assert "search" in result
        assert "(query: str, filters: object)" in result
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
                                    "zip": {"type": "string"}
                                },
                                "required": ["street", "city"]
                            }
                        },
                        "required": ["name", "email"]
                    },
                    "items": {
                        "type": "array",
                        "description": "Order items",
                        "items": {
                            "type": "object",
                            "properties": {
                                "product_id": {"type": "string"},
                                "quantity": {"type": "integer"},
                                "price": {"type": "number"}
                            },
                            "required": ["product_id", "quantity"]
                        }
                    }
                },
                "required": ["customer", "items"]
            },
            server_name="orders-mcp"
        )
        
        # Verify schema can be rendered
        sig, param_descs = _format_input_schema(tool_info.input_schema)
        assert "customer: dict" in sig
        assert "items: list" in sig
        assert "name: str" in "\n".join(param_descs)
        assert "address:" in "\n".join(param_descs)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/environments/test_nested_schemas.py -v`
Expected: FAIL with tests failing because nested schemas aren't properly rendered

**Step 3: Implement nested schema rendering**

Modify `/Users/madhavkandukuri/GitHub/madhav165/rlm/rlm/environments/base_env.py`:

```python
def _format_input_schema(schema: dict[str, Any], indent: int = 0) -> tuple[str, list[str]]:
    """Render an MCP input schema as a (signature, param_descriptions) tuple."""
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    if not props:
        return "()", []
    
    param_lines = []
    param_descs = []
    indent_str = "    " * (indent + 1)
    
    for param_name, param_info in props.items():
        param_type = _get_param_type(param_info)
        is_required = param_name in required
        
        if is_required:
            param_lines.append(f"{param_name}: {param_type}")
        else:
            param_lines.append(f"{param_name}: {param_type} = None")
        
        desc = param_info.get("description")
        if desc:
            param_descs.append(f"{indent_str}{param_name}: {desc}")
        
        # If this is an object or array, add nested descriptions
        if param_info.get("type") == "object" and "properties" in param_info:
            nested_sig, nested_descs = _format_input_schema(param_info, indent + 1)
            if nested_descs:
                param_descs.append(f"{indent_str}{param_name} object:")
                param_descs.extend(nested_descs)
        elif param_info.get("type") == "array" and "items" in param_info:
            items_info = param_info["items"]
            if items_info.get("type") == "object" and "properties" in items_info:
                nested_sig, nested_descs = _format_input_schema(items_info, indent + 1)
                if nested_descs:
                    param_descs.append(f"{indent_str}{param_name} items:")
                    param_descs.extend(nested_descs)
    
    return "(" + ", ".join(param_lines) + ")", param_descs


def _get_param_type(param_info: dict[str, Any]) -> str:
    """Get the Python type representation for a schema property."""
    param_type = param_info.get("type", "any")
    
    type_mapping = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "list",
        "object": "dict",
        "null": "None",
    }
    
    return type_mapping.get(param_type, param_type)
```

**Step 4: Update format_tools_for_prompt to use nested rendering**

Modify `/Users/madhavkandukuri/GitHub/madhav165/rlm/rlm/environments/base_env.py:121-161`:

```python
def format_tools_for_prompt(custom_tools: dict[str, Any] | None) -> str | None:
    """
    Format custom tools for inclusion in the system prompt.

    Args:
        custom_tools: Dictionary of tool names to values or {"tool": ..., "description": ...} dicts.

    Returns:
        Formatted string describing available tools, or None if no tools.
    """
    if not custom_tools:
        return None

    tool_infos = parse_custom_tools(custom_tools)
    if not tool_infos:
        return None

    lines = []
    for tool in tool_infos:
        if tool.input_schema is not None:
            sig, param_descs = _format_input_schema(tool.input_schema)
            line = f"- `{tool.name}{sig}`"
            if tool.description:
                line += f": {tool.description}"
            if param_descs:
                line += "\n" + "\n".join(param_descs)
        elif tool.is_callable:
            line = f"- `{tool.name}`"
            if tool.description:
                line += f": {tool.description}"
            else:
                line += ": A custom function"
        else:
            line = f"- `{tool.name}`"
            if tool.description:
                line += f": {tool.description}"
            else:
                line += f": A custom {type(tool.value).__name__} value"
        lines.append(line)

    return "\n".join(lines)
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/environments/test_nested_schemas.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add tests/environments/test_nested_schemas.py rlm/environments/base_env.py
git commit -m "feat: add nested JSON schema rendering for custom tools

- Implement _get_param_type() for type mapping
- Enhance _format_input_schema() with recursive nesting support
- Add tests for flat, nested, array, and mixed schemas"
```

---

### Task 2: Test with actual MCP tools

**Files:**
- Test: `tests/environments/test_nested_schemas.py` (add to existing file)

**Step 1: Add integration test**

Append to `tests/environments/test_nested_schemas.py`:

```python
    def test_local_repl_nested_wrapper(self):
        """Test LocalREPL wrapper with nested schemas."""
        from unittest.mock import Mock, patch
        from rlm.environments.local_repl import LocalREPL
        
        mock_manager = Mock()
        mock_manager.get_tools.return_value = {
            "test_tool": Mock(
                name="test_tool",
                description="Test tool",
                input_schema={
                    "type": "object",
                    "properties": {
                        "nested": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"}
                            }
                        }
                    }
                },
                server_name="test"
            )
        }
        
        repl = LocalREPL(mcp_manager=mock_manager)
        
        assert "test_tool" in repl.globals
        wrapper = repl.globals["test_tool"]
        
        # Test calling wrapper
        result = wrapper(nested={"field": "value"})
        assert "Error: MCP manager not available" in result
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/environments/test_nested_schemas.py::TestNestedSchemaRendering::test_local_repl_nested_wrapper -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/environments/test_nested_schemas.py
git commit -m "test: add MCP tool nested schema integration test"
```

---

### Task 3: Update LocalREPL wrapper to handle nested schemas

**Files:**
- Modify: `rlm/environments/local_repl.py:364-398`

**Step 1: Enhance _create_mcp_tool_wrapper**

Modify the wrapper to properly handle nested schemas:

```python
def _create_mcp_tool_wrapper(
    self, tool_name: str, input_schema: dict[str, Any]
) -> Callable[..., Any]:
    """Create a wrapper function for an MCP tool that calls it via the MCP manager."""

    def mcp_tool_wrapper(*args: Any, **kwargs: Any) -> Any:
        if self.mcp_manager is None:
            return "Error: MCP manager not available"

        arguments = kwargs.copy()

        if args:
            properties = input_schema.get("properties", {})
            prop_names = list(properties.keys())

            for i, arg in enumerate(args):
                if i < len(prop_names):
                    prop_name = prop_names[i]
                    arguments[prop_name] = arg

        try:
            result = self.mcp_manager.call_tool(tool_name, arguments)
            if hasattr(result, "content") and result.content:
                texts = []
                for item in result.content:
                    if hasattr(item, "text"):
                        texts.append(item.text)
                    else:
                        texts.append(str(item))
                return "\n".join(texts) if texts else str(result)
            return str(result)
        except Exception as e:
            return f"Error: MCP tool '{tool_name}' failed - {e}"

    return mcp_tool_wrapper
```

**Step 2: Add test**

Append to `tests/environments/test_nested_schemas.py`:

```python
    def test_local_repl_nested_wrapper(self):
        """Test LocalREPL wrapper with nested schemas."""
        from unittest.mock import Mock, patch
        from rlm.environments.local_repl import LocalREPL
        
        mock_manager = Mock()
        mock_manager.get_tools.return_value = {
            "test_tool": Mock(
                name="test_tool",
                description="Test tool",
                input_schema={
                    "type": "object",
                    "properties": {
                        "nested": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"}
                            }
                        }
                    }
                },
                server_name="test"
            )
        }
        
        repl = LocalREPL(mcp_manager=mock_manager)
        
        assert "test_tool" in repl.globals
        wrapper = repl.globals["test_tool"]
        
        # Test calling wrapper
        result = wrapper(nested={"field": "value"})
        assert "Error: MCP manager not available" in result
```

**Step 3: Run test to verify**

Run: `uv run pytest tests/environments/test_nested_schemas.py::TestNestedSchemaRendering::test_local_repl_nested_wrapper -v`
Expected: PASS

**Step 4: Commit**

```bash
git add rlm/environments/local_repl.py tests/environments/test_nested_schemas.py
git commit -m "test: add LocalREPL nested wrapper test"
```

---

### Task 4: Add documentation

**Files:**
- Create: `docs/nested-schemas.md`

**Step 1: Create documentation**

Create `docs/nested-schemas.md`:

```markdown
# Nested JSON Schema Support in Custom Tools

RLM now supports nested JSON schemas in custom tools and MCP tools.

## Schema Structure

Nested schemas use standard JSON Schema format:

```json
{
  "type": "object",
  "properties": {
    "field": {"type": "string"},
    "nested": {
      "type": "object",
      "properties": {
        "inner": {"type": "string"}
      }
    },
    "array_field": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "item_field": {"type": "string"}
        }
      }
    }
  },
  "required": ["field", "nested"]
}
```

## Python Type Mapping

The following JSON types map to Python types:

| JSON Type | Python Type | Signature |
|-----------|-------------|-----------|
| string | str | `str` |
| integer | int | `int` |
| number | float | `float` |
| boolean | bool | `bool` |
| array | list | `list` |
| object | dict | `dict` |
| null | None | `None` |

## Example: Create User Tool

### Schema

```python
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "User name"},
        "address": {
            "type": "object",
            "description": "User address",
            "properties": {
                "street": {"type": "string", "description": "Street"},
                "city": {"type": "string", "description": "City"},
                "coordinates": {
                    "type": "object",
                    "properties": {
                        "lat": {"type": "number"},
                        "lon": {"type": "number"}
                    }
                }
            },
            "required": ["street", "city"]
        }
    },
    "required": ["name", "address"]
}
```

### Generated Prompt

```
- `create_user(name: str, address: dict)`
  Create a new user
    name: User name
    address: User address
    address.street: Street
    address.city: City
    address.coordinates: GPS coordinates
    address.coordinates.lat: Latitude
    address.coordinates.lon: Longitude
```

## MCP Tools

MCP tools automatically support nested schemas:

```python
from rlm.clients.mcp_manager import MCPClientManager

manager = MCPClientManager({
    "orders": {
        "type": "stdio",
        "command": "uvx",
        "args": ["mcp-server-orders"]
    }
})

manager.connect_all()
tools = manager.get_tools()

# Tools with nested schemas are rendered properly
for name, info in tools.items():
    print(f"Tool: {name}")
    print(f"Schema: {info.input_schema}")
```

## LocalREPL Integration

LocalREPL wraps MCP tools with proper argument handling:

```python
from rlm.environments.local_repl import LocalREPL

repl = LocalREPL(mcp_manager=manager)

# Nested arguments work as expected
repl.execute_code("result = create_user(name='John', address={'street': '123 Main', 'city': 'NYC'})")
```
```

**Step 2: Commit**

```bash
git add docs/nested-schemas.md
git commit -m "docs: add nested schemas documentation"
```

---

### Task 5: Run full test suite

**Step 1: Run all tests**

Run: `uv run pytest tests/environments/test_nested_schemas.py tests/repl/test_mcp_tools.py -v`
Expected: All tests PASS

**Step 2: Run full suite**

Run: `uv run pytest`
Expected: All tests PASS

**Step 3: Final commit**

```bash
git add .
git commit -m "refactor: support nested JSON schemas in custom tools

- Implement recursive schema rendering
- Add type mapping for JSON Schema types
- Update documentation"
```

---

## Execution Handoff

**Subagent-Driven (this session)** - Fresh subagent per task + code review

Dispatching subagents to execute tasks...
