# Nested JSON Schema Support

RLM supports nested JSON schemas in custom tools and MCP tools, enabling complex data structures in tool arguments.

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
```

### Generated Prompt Output

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

LocalREPL wraps MCP tools with proper nested argument handling:

```python
from rlm.environments.local_repl import LocalREPL

repl = LocalREPL(mcp_manager=manager)

# Nested arguments work as expected
result = repl.execute_code(
    "user = create_user("
    "name='John', "
    "address={'street': '123 Main St', 'city': 'NYC', "
    "         'coordinates': {'lat': 40.7128, 'lon': -74.0060}}"
    ")"
)
```

## Usage Notes

- **Required fields** appear without default values
- **Optional fields** appear with `= None` default
- **Nested objects** are rendered as `dict` type with indented property descriptions
- **Arrays** are rendered as `list` type with indented item descriptions when items are objects
