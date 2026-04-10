"""
Pydantic-based validation for tool calls.
Python port of TypeScript validation.ts
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..types import Tool, ToolCall


def validate_tool_call(tools: list[Tool], tool_call: ToolCall) -> Any:
    """
    Finds a tool by name and validates the tool call arguments against its schema.

    Args:
        tools: Array of tool definitions
        tool_call: The tool call from the LLM

    Returns:
        The validated arguments

    Raises:
        ValueError: if tool is not found or validation fails
    """
    tool = next((t for t in tools if t.name == tool_call.name), None)
    if not tool:
        raise ValueError(f'Tool "{tool_call.name}" not found')
    return validate_tool_arguments(tool, tool_call)


def validate_tool_arguments(tool: Tool, tool_call: ToolCall) -> Any:
    """
    Validates tool call arguments against the tool's JSON schema.

    Args:
        tool: The tool definition with JSON schema
        tool_call: The tool call from the LLM

    Returns:
        The validated (and potentially coerced) arguments

    Raises:
        ValueError: with formatted message if validation fails
    """
    try:
        from pydantic import BaseModel, ValidationError, create_model
    except ImportError:
        # Pydantic not available, return arguments as-is
        return tool_call.arguments

    # Convert JSON schema to Pydantic model
    schema = tool.parameters

    try:
        # Create a dynamic Pydantic model from the schema
        model = _schema_to_pydantic_model(tool.name, schema)

        # Validate and return
        validated = model(**tool_call.arguments)
        return validated.model_dump()
    except ValidationError as e:
        # Format validation errors nicely
        errors = []
        for err in e.errors():
            loc = ".".join(str(l) for l in err["loc"])
            errors.append(f"  - {loc}: {err['msg']}")

        error_message = (
            f'Validation failed for tool "{tool_call.name}":\n'
            + "\n".join(errors)
            + f"\n\nReceived arguments:\n{json.dumps(tool_call.arguments, indent=2)}"
        )
        raise ValueError(error_message)
    except Exception:
        # If schema conversion fails, return arguments as-is
        return tool_call.arguments


def _schema_to_pydantic_model(name: str, schema: dict[str, Any]) -> type:
    """
    Convert a JSON schema to a Pydantic model.

    This is a simplified conversion that handles basic schemas.
    """
    from typing import Optional

    from pydantic import Field, create_model

    # Extract properties and required fields
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    # Build field definitions
    fields: dict[str, Any] = {}

    for prop_name, prop_schema in properties.items():
        field_type = _json_schema_type_to_python(prop_schema)

        if prop_name in required:
            # Required field
            default = prop_schema.get("default", ...)
            if default is not ...:
                fields[prop_name] = (field_type, Field(default=default))
            else:
                fields[prop_name] = (field_type, ...)
        else:
            # Optional field
            default = prop_schema.get("default", None)
            fields[prop_name] = (Optional[field_type], default)

    # Create the model
    return create_model(name, **fields)


def _json_schema_type_to_python(schema: dict[str, Any]) -> Any:
    """Convert JSON schema type to Python type."""
    from typing import Any as AnyType
    from typing import Optional, Union

    schema_type = schema.get("type", "any")

    if schema_type == "string":
        return str
    elif schema_type == "integer":
        return int
    elif schema_type == "number":
        return float
    elif schema_type == "boolean":
        return bool
    elif schema_type == "array":
        items = schema.get("items", {})
        item_type = _json_schema_type_to_python(items)
        return list[item_type]
    elif schema_type == "object":
        return dict[str, AnyType]
    elif schema_type == "null":
        return type(None)
    else:
        # Handle anyOf, oneOf, allOf
        if "anyOf" in schema or "oneOf" in schema:
            sub_schemas = schema.get("anyOf") or schema.get("oneOf")
            types = [_json_schema_type_to_python(s) for s in sub_schemas]
            if len(types) == 2 and type(None) in types:
                # Optional type
                other_type = next(t for t in types if t is not type(None))
                return Optional[other_type]
            return Union[tuple(types)]

        return AnyType


__all__ = [
    "validate_tool_call",
    "validate_tool_arguments",
]
